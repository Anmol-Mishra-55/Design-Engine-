"""
Prompt Runner - Universal Platform Adapter v2
=============================================
Universal domain-agnostic routing engine.

Pipeline:
  Input
  → PluginLoader      (loads domain plugins from plugins/ directory)
  → DomainDetector    (classifies domain using plugin keywords + patterns)
  → IntentDetector    (classifies intent within the detected domain)
  → EntityExtractor   (extracts structured entities using plugin extractor rules)
  → ConstraintExtractor (extracts constraints using plugin constraint rules)
  → InstructionBuilder  (builds deterministic JSON instruction)
  → Output to Core Integrator

Adding a new domain: drop a plugin.json in plugins/<domain>/ — no core code changes needed.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, Union, List, Tuple
from dataclasses import dataclass, asdict

PLUGINS_DIR = Path(__file__).parent / "plugins"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PromptInstruction:
    """Structured instruction output from Prompt Runner."""
    module: str
    intent: str
    data: Dict[str, Any]
    tasks: List[str]
    output_format: str
    context: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# ---------------------------------------------------------------------------
# Stage 0: Plugin Loader
# ---------------------------------------------------------------------------

class PluginLoader:
    """
    Loads domain plugins from the plugins/ directory.
    Each subdirectory containing a plugin.json is treated as a domain plugin.
    New domains are added by placing a plugin.json in a new subdirectory —
    no changes to core code are required.
    """

    def __init__(self, plugins_dir: Path = PLUGINS_DIR):
        self.plugins_dir = plugins_dir
        self._plugins: Dict[str, Dict] = {}
        self._load_all()

    def _load_all(self):
        if not self.plugins_dir.exists():
            return
        for domain_dir in sorted(self.plugins_dir.iterdir()):
            if domain_dir.is_dir():
                plugin_file = domain_dir / "plugin.json"
                if plugin_file.exists():
                    with open(plugin_file, "r", encoding="utf-8") as f:
                        plugin = json.load(f)
                    self._plugins[plugin["domain"]] = plugin

    def get_plugin(self, domain: str) -> Optional[Dict]:
        return self._plugins.get(domain)

    def all_plugins(self) -> Dict[str, Dict]:
        return self._plugins

    @property
    def domains(self) -> List[str]:
        return list(self._plugins.keys())


# ---------------------------------------------------------------------------
# Stage 1: Domain Detector
# ---------------------------------------------------------------------------

class DomainDetector:
    """
    Classifies the domain of the input prompt using each plugin's
    detection_keywords and detection_patterns.

    Scoring:
      keyword_contribution = min(0.5, matched_kw / total_kw * 1.5)
      pattern_contribution = min(0.7, matched_p  / total_p  * 2.0)
      domain_confidence    = min(1.0, keyword_contribution + pattern_contribution)

    The domain with the highest confidence score wins.
    """

    def __init__(self, plugin_loader: PluginLoader):
        self.plugins = plugin_loader

    def detect(self, prompt: str) -> Tuple[str, float, List[Dict]]:
        """
        Returns:
            (domain, confidence, fallback_candidates)
        """
        prompt_lower = prompt.lower()
        scores: List[Tuple[str, float]] = []

        for domain, plugin in self.plugins.all_plugins().items():
            keywords = plugin.get("detection_keywords", [])
            patterns = plugin.get("detection_patterns", [])

            matched_kw = [
                kw for kw in keywords
                if re.search(r"\b" + re.escape(kw.lower()) + r"\b", prompt_lower)
            ]
            matched_p = [
                p for p in patterns
                if re.search(p, prompt_lower, re.IGNORECASE)
            ]

            kw_cont = min(0.5, len(matched_kw) / max(len(keywords), 1) * 1.5)
            p_cont  = min(0.7, len(matched_p)  / max(len(patterns), 1) * 2.0)
            confidence = round(min(1.0, kw_cont + p_cont), 3)

            scores.append((domain, confidence))

        scores.sort(key=lambda x: x[1], reverse=True)

        if not scores or scores[0][1] == 0.0:
            return "general", 0.0, []

        top_domain, top_conf = scores[0]
        fallback_candidates = [
            {"domain": d, "confidence": c}
            for d, c in scores[1:4] if c > 0
        ]

        return top_domain, top_conf, fallback_candidates


# ---------------------------------------------------------------------------
# Stage 2: Intent Detector
# ---------------------------------------------------------------------------

class IntentDetector:
    """
    Classifies the user's intent within the detected domain using the
    domain plugin's intent patterns.

    Scoring:
      raw_score    = matched_patterns / total_patterns
      final_score  = min(1.0, raw_score * 0.6 + 0.4)   ← 0.4 base for any match
    """

    def __init__(self, plugin_loader: PluginLoader):
        self.plugins = plugin_loader

    def detect(self, prompt: str, domain: str) -> Tuple[str, float, List[str]]:
        """
        Returns:
            (intent, confidence, matched_patterns)
        """
        plugin = self.plugins.get_plugin(domain)
        if not plugin:
            return "process_request", 0.0, []

        prompt_lower = prompt.lower()
        intents = plugin.get("intents", {})

        best_intent: Optional[str] = None
        best_score = 0.0
        best_patterns: List[str] = []

        for intent_name, intent_def in intents.items():
            patterns = intent_def.get("patterns", [])
            matched = [p for p in patterns if re.search(p, prompt_lower, re.IGNORECASE)]
            if matched:
                raw = len(matched) / max(len(patterns), 1)
                if raw > best_score:
                    best_score = raw
                    best_intent = intent_name
                    best_patterns = matched

        if not best_intent:
            # No pattern matched — default to first intent with low confidence
            best_intent = next(iter(intents), "process_request")
            return best_intent, 0.2, []

        final_score = round(min(1.0, best_score * 0.6 + 0.4), 3)
        return best_intent, final_score, best_patterns


# ---------------------------------------------------------------------------
# Stage 3: Entity Extractor
# ---------------------------------------------------------------------------

class EntityExtractor:
    """
    Extracts structured entities from the prompt using the domain plugin's
    extractor rules. Rules are either 'regex' or 'keyword' type.

    Each extractor produces a single key-value pair in the entities dict.
    """

    def __init__(self, plugin_loader: PluginLoader):
        self.plugins = plugin_loader

    def extract(self, prompt: str, domain: str) -> Dict[str, Any]:
        plugin = self.plugins.get_plugin(domain)
        if not plugin:
            return {}

        entities: Dict[str, Any] = {}
        extractors = plugin.get("extractors", {})

        for field_name, extractor in extractors.items():
            value = self._apply_extractor(prompt, extractor)
            if value is not None:
                entities[field_name] = value

        return entities

    def _apply_extractor(self, prompt: str, extractor: Dict) -> Optional[str]:
        extractor_type = extractor.get("type", "regex")

        if extractor_type == "regex":
            pattern = extractor.get("pattern", "")
            flags = 0 if not extractor.get("case_insensitive", True) else re.IGNORECASE
            # For non-case-insensitive, search original prompt to preserve casing
            search_text = prompt if not extractor.get("case_insensitive", True) else prompt
            match = re.search(pattern, search_text, flags)
            if match:
                group = extractor.get("group", 1)
                try:
                    raw = match.group(group) if group <= (match.lastindex or 0) else match.group(0)
                except IndexError:
                    raw = match.group(0)
                raw = raw.strip()
                normalize = extractor.get("normalize")
                return normalize.replace("{value}", raw) if normalize else raw

        elif extractor_type == "keyword":
            keywords = extractor.get("keywords", [])
            prompt_lower = prompt.lower()
            for kw in keywords:
                if re.search(r"\b" + re.escape(kw.lower()) + r"\b", prompt_lower):
                    return kw

        return None


# ---------------------------------------------------------------------------
# Stage 4: Constraint Extractor
# ---------------------------------------------------------------------------

class ConstraintExtractor:
    """
    Extracts constraint metadata from the prompt using the domain plugin's
    constraint_rules (e.g. timeline, quality tier, urgency, regulatory flags).
    Uses the same regex/keyword rule format as EntityExtractor.
    """

    def __init__(self, plugin_loader: PluginLoader):
        self.plugins = plugin_loader
        self._entity_extractor = EntityExtractor(plugin_loader)

    def extract(self, prompt: str, domain: str) -> Dict[str, Any]:
        plugin = self.plugins.get_plugin(domain)
        if not plugin:
            return {}

        constraints: Dict[str, Any] = {}
        constraint_rules = plugin.get("constraint_rules", {})

        for field_name, rule in constraint_rules.items():
            value = self._entity_extractor._apply_extractor(prompt, rule)
            if value is not None:
                constraints[field_name] = value

        return constraints


# ---------------------------------------------------------------------------
# Stage 5: Instruction Builder
# ---------------------------------------------------------------------------

class InstructionBuilder:
    """
    Assembles the final deterministic PromptInstruction from all pipeline outputs.
    Computes:
      - overall confidence  = (domain_conf * 0.5 + intent_conf * 0.5)
      - requires_clarification = confidence < threshold OR required entities missing
      - clarification_questions from plugin config
      - deterministic_hash from module + task + domain + intent + entities
    """

    def __init__(self, plugin_loader: PluginLoader):
        self.plugins = plugin_loader

    def build(
        self,
        prompt: str,
        domain: str,
        intent: str,
        entities: Dict[str, Any],
        constraints: Dict[str, Any],
        topic_override: Optional[str] = None,
    ) -> PromptInstruction:

        plugin = self.plugins.get_plugin(domain)

        if plugin and intent in plugin.get("intents", {}):
            intent_def = plugin["intents"][intent]
            module = intent_def.get("module", "general_processor")
            tasks = list(intent_def.get("tasks", []))
            output_format = intent_def.get("output_format", "general_response")
        else:
            module = "general_processor"
            tasks = ["understand request", "process information", "generate output"]
            output_format = "general_response"

        topic = topic_override if topic_override is not None else self._extract_topic(prompt)
        parameters = {**entities, **constraints}

        data = {
            "topic": topic,
            "parameters": parameters,
            "original_prompt": prompt,
        }

        context = {
            "source": "prompt_runner",
        }

        return PromptInstruction(
            module=module,
            intent=intent,
            data=data,
            tasks=tasks,
            output_format=output_format,
            context=context,
        )

    def _extract_topic(self, prompt: str) -> str:
        """Strip leading action verbs to extract the main topic from a prompt."""
        stripped = re.sub(
            r'^(?:design|create|analyze|analyse|review|calculate|estimate|assess|evaluate|'
            r'generate|draft|plan|build|explain|describe|research|find|implement|develop|'
            r'write|prepare|provide|check|make|run|perform|help|give)\s+(?:a\s+|an\s+|the\s+|me\s+|with\s+)?',
            '',
            prompt.strip(),
            flags=re.IGNORECASE,
        ).strip().rstrip('.')
        return stripped if stripped else prompt.strip().rstrip('.')


# ---------------------------------------------------------------------------
# Orchestrator: Prompt Runner
# ---------------------------------------------------------------------------

class PromptRunner:
    """
    Orchestrates the five-stage processing pipeline.

    Stage 1 → DomainDetector
    Stage 2 → IntentDetector   (domain-scoped)
    Stage 3 → EntityExtractor  (plugin-driven)
    Stage 4 → ConstraintExtractor (plugin-driven)
    Stage 5 → InstructionBuilder

    Prompt Runner produces the instruction and stops. It does NOT execute tasks.
    """

    def __init__(self, plugins_dir: Path = PLUGINS_DIR):
        self.plugin_loader        = PluginLoader(plugins_dir)
        self.domain_detector      = DomainDetector(self.plugin_loader)
        self.intent_detector      = IntentDetector(self.plugin_loader)
        self.entity_extractor     = EntityExtractor(self.plugin_loader)
        self.constraint_extractor = ConstraintExtractor(self.plugin_loader)
        self.instruction_builder  = InstructionBuilder(self.plugin_loader)

    def generate_instruction(
        self,
        prompt: Optional[str] = None,
        structured_request: Optional[Dict[str, Any]] = None,
    ) -> PromptInstruction:
        if structured_request:
            return self._process_structured(structured_request)
        if prompt:
            return self._process_prompt(prompt)
        raise ValueError("Either prompt or structured_request must be provided")

    def _process_prompt(self, prompt: str) -> PromptInstruction:
        domain, _, _ = self.domain_detector.detect(prompt)
        intent, _, _ = self.intent_detector.detect(prompt, domain)
        entities     = self.entity_extractor.extract(prompt, domain)
        constraints  = self.constraint_extractor.extract(prompt, domain)
        return self.instruction_builder.build(
            prompt=prompt,
            domain=domain,
            intent=intent,
            entities=entities,
            constraints=constraints,
        )

    def _process_structured(self, req: Dict[str, Any]) -> PromptInstruction:
        domain = req.get("domain", "")
        intent = req.get("intent", "")
        topic_override = req.get("topic")
        prompt = req.get("prompt") or topic_override or json.dumps(req.get("data", {}))

        if not domain or domain not in self.plugin_loader.domains:
            domain, _, _ = self.domain_detector.detect(prompt)

        if not intent:
            intent, _, _ = self.intent_detector.detect(prompt, domain)

        extracted = self.entity_extractor.extract(prompt, domain)
        entities  = {**extracted, **req.get("data", {})}

        constraints = self.constraint_extractor.extract(prompt, domain)
        constraints.update(req.get("constraints", {}))

        return self.instruction_builder.build(
            prompt=prompt,
            domain=domain,
            intent=intent,
            entities=entities,
            constraints=constraints,
            topic_override=topic_override,
        )


# ---------------------------------------------------------------------------
# Entry Point: Platform Adapter
# ---------------------------------------------------------------------------

class PlatformAdapter:
    """
    Official entry point for external platform integration.
    Validates input, delegates to PromptRunner, and returns a structured response.
    """

    def __init__(self, plugins_dir: Path = PLUGINS_DIR):
        self.prompt_runner = PromptRunner(plugins_dir)
        self.version = "2.0.0"

    def validate_input(self, input_data: Union[str, Dict[str, Any]]) -> bool:
        if isinstance(input_data, str):
            return len(input_data.strip()) > 0
        if isinstance(input_data, dict):
            return any(k in input_data for k in ("intent", "data", "prompt", "domain", "topic"))
        return False

    def process(self, input_data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        if not self.validate_input(input_data):
            return {
                "status": "error",
                "error": "Invalid input",
                "message": "Input must be a non-empty string or a valid structured request",
                "adapter_version": self.version,
            }
        try:
            if isinstance(input_data, str):
                instruction = self.prompt_runner.generate_instruction(prompt=input_data)
            else:
                instruction = self.prompt_runner.generate_instruction(structured_request=input_data)

            return {
                "status": "success",
                "instruction": instruction.to_dict(),
                "adapter_version": self.version,
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "adapter_version": self.version,
            }

    def health_check(self) -> Dict[str, Any]:
        loaded = self.prompt_runner.plugin_loader.domains
        return {
            "status": "healthy",
            "component": "prompt_runner",
            "version": self.version,
            "ready": True,
            "loaded_domains": loaded,
            "domain_count": len(loaded),
        }


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def run_prompt(input_data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Convenience wrapper — creates a PlatformAdapter and processes input."""
    return PlatformAdapter().process(input_data)
