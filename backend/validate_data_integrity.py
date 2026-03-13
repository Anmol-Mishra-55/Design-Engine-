"""
Data Integrity Validator
Ensures spec JSON stored locally, no ghost artifacts, audit completeness > 70%
"""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

# Import platform adapter if available
try:
    from platform_adapter import run_prompt
except ImportError:
    run_prompt = None


class DataIntegrityValidator:
    def __init__(self, data_dir: str = "data"):
        # Sanitize path to prevent traversal attacks
        safe_dir = os.path.basename(data_dir) if data_dir else "data"
        self.data_dir = Path(safe_dir)
        self.specs_dir = self.data_dir / "specs"
        self.specs_dir.mkdir(parents=True, exist_ok=True)

    def save_spec_locally(self, spec_id: str, spec_json: Dict) -> str:
        """Save spec JSON locally - enforced storage"""
        # Sanitize spec_id to prevent path traversal
        safe_id = "".join(c for c in spec_id if c.isalnum() or c in "_-")
        if not safe_id:
            raise ValueError("Invalid spec_id")

        spec_file = self.specs_dir / f"{safe_id}.json"
        with open(spec_file, "w") as f:
            json.dump(spec_json, f, indent=2)
        return str(spec_file)

    def load_spec_locally(self, spec_id: str) -> Dict:
        """Load spec from local storage"""
        # Sanitize spec_id to prevent path traversal
        safe_id = "".join(c for c in spec_id if c.isalnum() or c in "_-")
        if not safe_id:
            raise ValueError("Invalid spec_id")

        spec_file = self.specs_dir / f"{safe_id}.json"
        if not spec_file.exists():
            raise FileNotFoundError(f"Spec {spec_id} not found locally")
        with open(spec_file) as f:
            return json.load(f)

    def find_ghost_artifacts(self) -> List[str]:
        """Find files that don't have corresponding database entries"""
        ghosts = []
        for spec_file in self.specs_dir.glob("*.json"):
            spec_id = spec_file.stem
            # Check if spec exists in database would go here
            # For now, just check if file is valid JSON
            try:
                with open(spec_file) as f:
                    data = json.load(f)
                    if not data or "spec_id" not in data:
                        ghosts.append(str(spec_file))
            except (json.JSONDecodeError, IOError) as e:
                logging.warning(f"Failed to process spec file {spec_file}: {e}")
                ghosts.append(str(spec_file))
        return ghosts

    def calculate_completeness(self, spec_json: Dict) -> float:
        """Calculate spec completeness score (0-100)"""
        required_fields = [
            "spec_id",
            "city",
            "building_type",
            "floors",
            "units",
            "plot_area",
        ]
        optional_fields = [
            "amenities",
            "parking",
            "setbacks",
            "fsi",
            "height",
            "materials",
        ]

        score = 0.0
        total_weight = 100.0

        # Required fields: 60% weight
        required_weight = 60.0 / len(required_fields)
        for field in required_fields:
            if field in spec_json and spec_json[field]:
                score += required_weight

        # Optional fields: 40% weight
        optional_weight = 40.0 / len(optional_fields)
        for field in optional_fields:
            if field in spec_json and spec_json[field]:
                score += optional_weight

        return round(score, 2)

    def audit_data_integrity(self) -> Dict:
        """Run complete data integrity audit"""
        total_specs = len(list(self.specs_dir.glob("*.json")))
        ghosts = self.find_ghost_artifacts()

        completeness_scores = []
        for spec_file in self.specs_dir.glob("*.json"):
            try:
                with open(spec_file) as f:
                    spec = json.load(f)
                    score = self.calculate_completeness(spec)
                    completeness_scores.append(score)
            except (json.JSONDecodeError, IOError) as e:
                logging.warning(f"Failed to process completeness for {spec_file}: {e}")

        avg_completeness = sum(completeness_scores) / len(completeness_scores) if completeness_scores else 0.0

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_specs": total_specs,
            "ghost_artifacts": len(ghosts),
            "ghost_files": ghosts,
            "avg_completeness": round(avg_completeness, 2),
            "completeness_threshold": 70.0,
            "passed": avg_completeness >= 70.0 and len(ghosts) == 0,
            "specs_analyzed": len(completeness_scores),
        }


def validate_data_integrity() -> Tuple[bool, Dict]:
    """Run validation and return (passed, report)"""
    validator = DataIntegrityValidator()
    report = validator.audit_data_integrity()
    return report["passed"], report


if __name__ == "__main__":
    passed, report = validate_data_integrity()
    print(json.dumps(report, indent=2))
    print(f"\nValidation: {'PASSED' if passed else 'FAILED'}")
    exit(0 if passed else 1)


def process_integrity_command(prompt: str) -> Dict:
    """Process natural language integrity commands using platform adapter"""
    if not run_prompt:
        return {"error": "Platform adapter not available"}

    result = run_prompt(prompt)
    if result.get("status") != "success":
        return result

    instruction = result.get("instruction", {})
    intent = instruction.get("intent", "")
    data = instruction.get("data", {})

    validator = DataIntegrityValidator()

    if "validate" in intent or "audit" in intent:
        passed, report = validate_data_integrity()
        return {"action": "audit", "result": report, "passed": passed}

    elif "save" in intent:
        spec_id = data.get("parameters", {}).get("spec_id")
        if spec_id:
            # Extract spec data from prompt or use default structure
            spec_data = {"spec_id": spec_id, "timestamp": datetime.now(timezone.utc).isoformat()}
            file_path = validator.save_spec_locally(spec_id, spec_data)
            return {"action": "save", "spec_id": spec_id, "file_path": file_path}

    return {"error": "Unknown intent", "instruction": instruction}
