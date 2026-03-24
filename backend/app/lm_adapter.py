import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict

import httpx
from app.config import settings

logger = logging.getLogger(__name__)

# AI Model Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", settings.GROQ_API_KEY if hasattr(settings, "GROQ_API_KEY") else None)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", settings.OPENAI_API_KEY if hasattr(settings, "OPENAI_API_KEY") else None)
ANTHROPIC_API_KEY = os.getenv(
    "ANTHROPIC_API_KEY", settings.ANTHROPIC_API_KEY if hasattr(settings, "ANTHROPIC_API_KEY") else None
)
USE_AI_MODEL = os.getenv("USE_AI_MODEL", "true").lower() == "true"

# Validate API keys
if GROQ_API_KEY and len(GROQ_API_KEY) < 20:
    logger.warning("Invalid Groq API key format, disabling Groq")
    GROQ_API_KEY = None

if OPENAI_API_KEY and (not OPENAI_API_KEY.startswith("sk-") or len(OPENAI_API_KEY) < 20):
    logger.warning("Invalid OpenAI API key format, disabling OpenAI")
    OPENAI_API_KEY = None

if ANTHROPIC_API_KEY and len(ANTHROPIC_API_KEY) < 20:
    logger.warning("Invalid Anthropic API key format, disabling Anthropic")
    ANTHROPIC_API_KEY = None

if USE_AI_MODEL and not (GROQ_API_KEY or OPENAI_API_KEY or ANTHROPIC_API_KEY):
    logger.debug("No AI API keys configured, will use template fallback (optional)")


async def run_local_lm(prompt: str, params: dict) -> dict:
    """Run inference using multiple AI models or fallback to enhanced templates"""
    logger.info(f"AI_LM: Processing prompt: '{prompt[:100]}...'")

    # Try AI generation with multi-model fallback
    if USE_AI_MODEL and (GROQ_API_KEY or OPENAI_API_KEY or ANTHROPIC_API_KEY):
        try:
            spec_json = await generate_with_ai(prompt, params)
            logger.info(f"✅ AI generated design: {spec_json.get('design_type')}")

            log_usage("ai_model", len(prompt), 0.0001, params.get("user_id"))

            return {
                "spec_json": spec_json,
                "preview_data": f"AI generated {spec_json.get('design_type', 'design')} for: {prompt[:50]}...",
                "provider": spec_json.get("model_used", "ai_model"),
                "feedback": f"AI model generated {spec_json.get('design_type', 'design')} with intelligent analysis",
            }
        except Exception as e:
            logger.warning(f"AI generation failed: {e}, falling back to templates")

    # Fallback to ENHANCED template-based generation
    try:
        from app.lm_adapter_enhanced import generate_enhanced_design_from_prompt

        spec_json = generate_enhanced_design_from_prompt(prompt, params)
        logger.info(f"✅ Enhanced template generated {len(spec_json.get('objects', []))} objects")
    except ImportError:
        spec_json = generate_design_from_prompt(prompt, params)
    except Exception as e:
        logger.warning(f"Enhanced template failed: {e}, using basic template")
        spec_json = generate_design_from_prompt(prompt, params)

    log_usage("template_fallback", len(prompt), 0.0001, params.get("user_id"))

    return {
        "spec_json": spec_json,
        "preview_data": f"Template generated {spec_json.get('design_type', 'design')} for: {prompt[:50]}...",
        "provider": "template_fallback",
        "feedback": f"Template-based {spec_json.get('design_type', 'design')} (AI unavailable)",
    }


async def generate_with_ai(prompt: str, params: dict) -> dict:
    """Generate design using Groq, OpenAI or Anthropic AI models with retry logic"""

    system_prompt = """You are an expert architectural and interior design AI. Generate detailed design specifications in JSON format.

Your response MUST be valid JSON with this exact structure:
{
  "objects": [
    {
      "id": "unique_id",
      "type": "foundation|wall|roof|door|window|furniture|fixture|etc",
      "subtype": "optional_subtype",
      "material": "material_name",
      "color_hex": "#HEXCODE",
      "dimensions": {"width": float, "length": float, "height": float},
      "count": int (optional)
    }
  ],
  "design_type": "house|apartment|kitchen|office|bathroom|bedroom|living_room",
  "style": "modern|traditional|contemporary|rustic|etc",
  "stories": int,
  "dimensions": {"width": float, "length": float, "height": float},
  "estimated_cost": {"total": float, "currency": "INR"}
}

Analyze the user's prompt carefully and generate ALL objects mentioned. Be creative and comprehensive."""

    budget = params.get("budget") or params.get("context", {}).get("budget", "Not specified")
    user_prompt = f"""Design request: {prompt}

Context:
- City: {params.get('city', 'Mumbai')}
- Budget: ₹{budget:,} if isinstance(budget, (int, float)) else budget
- Style preference: {params.get('style', 'modern')}

Generate a complete, detailed design specification in JSON format. Include ALL elements mentioned in the request."""

    # Try Groq first (fastest and free)
    if GROQ_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.7,
                        "response_format": {"type": "json_object"},
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    spec_json = json.loads(content)
                    spec_json.setdefault("tech_stack", ["Groq Llama 3.3 70B"])
                    spec_json.setdefault("model_used", "groq-llama-3.3-70b")
                    logger.info("✅ Groq AI generation successful")
                    return spec_json
                else:
                    logger.warning(f"Groq returned status {response.status_code}: {response.text[:200]}")
        except Exception as e:
            logger.warning(f"Groq failed: {e}, trying OpenAI")

    # Try OpenAI with retry logic
    if OPENAI_API_KEY:
        import asyncio

        max_retries = 3
        base_delay = 2

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
                        json={
                            "model": "gpt-4o-mini",
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                            "temperature": 0.7,
                            "response_format": {"type": "json_object"},
                        },
                    )

                    if response.status_code == 200:
                        result = response.json()
                        content = result["choices"][0]["message"]["content"]
                        spec_json = json.loads(content)

                        # Ensure required fields
                        spec_json.setdefault("tech_stack", ["OpenAI GPT-4"])
                        spec_json.setdefault("model_used", "gpt-4o-mini")

                        logger.info(f"✅ OpenAI success on attempt {attempt + 1}")
                        return spec_json

                    elif response.status_code == 429:
                        if attempt < max_retries - 1:
                            delay = base_delay * (2**attempt)
                            logger.warning(
                                f"Rate limit hit, retrying in {delay}s (attempt {attempt + 1}/{max_retries})"
                            )
                            await asyncio.sleep(delay)
                            continue
                        else:
                            logger.warning(f"Rate limit exceeded after {max_retries} attempts, trying Anthropic")
                    else:
                        logger.warning(f"OpenAI returned status {response.status_code}: {response.text[:200]}")

            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    logger.warning(f"OpenAI error: {e}, retrying in {delay}s")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"OpenAI failed after {max_retries} attempts: {e}")

    # Try Anthropic as fallback with retry
    if ANTHROPIC_API_KEY:
        import asyncio

        max_retries = 2
        base_delay = 2

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": ANTHROPIC_API_KEY,
                            "anthropic-version": "2023-06-01",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": "claude-3-5-sonnet-20241022",
                            "max_tokens": 4096,
                            "messages": [{"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"}],
                        },
                    )

                    if response.status_code == 200:
                        result = response.json()
                        content = result["content"][0]["text"]

                        # Extract JSON from response
                        json_match = re.search(r"\{[\s\S]*\}", content)
                        if json_match:
                            spec_json = json.loads(json_match.group())
                            spec_json.setdefault("tech_stack", ["Anthropic Claude"])
                            spec_json.setdefault("model_used", "claude-3-5-sonnet")
                            logger.info(f"✅ Anthropic success on attempt {attempt + 1}")
                            return spec_json

                    elif response.status_code == 429:
                        if attempt < max_retries - 1:
                            delay = base_delay * (2**attempt)
                            logger.warning(f"Anthropic rate limit, retrying in {delay}s")
                            await asyncio.sleep(delay)
                            continue

            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    logger.warning(f"Anthropic error: {e}, retrying in {delay}s")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Anthropic failed after {max_retries} attempts: {e}")

    raise Exception("All AI providers failed")


def generate_design_from_prompt(prompt: str, params: dict) -> dict:
    """FALLBACK: Generate design using templates (when AI unavailable)"""
    prompt_lower = prompt.lower()
    logger.info(f"TEMPLATE_FALLBACK: Analyzing prompt: {prompt_lower}")

    # Detect design type - prioritize specific rooms over general structures
    if any(word in prompt_lower for word in ["apartment", "flat", "bhk", "penthouse"]):
        logger.info("DESIGN_DEBUG: Detected APARTMENT design")
        return generate_apartment_design(prompt, params)
    elif (
        any(word in prompt_lower for word in ["kitchen", "cook", "cabinet", "countertop"])
        and "house" not in prompt_lower
    ):
        logger.info("DESIGN_DEBUG: Detected KITCHEN design")
        return generate_kitchen_design(prompt, params)
    elif (
        any(word in prompt_lower for word in ["office", "workspace", "corporate", "co-working"])
        and "commercial" not in prompt_lower
    ):
        logger.info("DESIGN_DEBUG: Detected OFFICE design")
        return generate_office_design(prompt, params)
    elif any(word in prompt_lower for word in ["bathroom", "bath", "shower", "toilet"]):
        logger.info("DESIGN_DEBUG: Detected BATHROOM design")
        return generate_bathroom_design(prompt, params)
    elif any(word in prompt_lower for word in ["bedroom", "bed", "sleep"]) and "house" not in prompt_lower:
        logger.info("DESIGN_DEBUG: Detected BEDROOM design")
        return generate_bedroom_design(prompt, params)
    elif any(word in prompt_lower for word in ["living room", "lounge", "family room"]):
        logger.info("DESIGN_DEBUG: Detected LIVING ROOM design")
        return generate_living_room_design(prompt, params)
    elif any(
        word in prompt_lower for word in ["villa", "bungalow", "duplex", "farmhouse", "townhouse", "independent house"]
    ):
        logger.info("DESIGN_DEBUG: Detected HOUSE design")
        return generate_house_design(prompt, params)
    elif any(word in prompt_lower for word in ["showroom", "commercial"]):
        logger.info("DESIGN_DEBUG: Detected COMMERCIAL design")
        return generate_commercial_design(prompt, params)
    elif any(word in prompt_lower for word in ["house", "building", "complex", "residential", "story"]):
        logger.info("DESIGN_DEBUG: Detected HOUSE design")
        return generate_house_design(prompt, params)
    else:
        logger.info("DESIGN_DEBUG: Using GENERIC design")
        return generate_generic_design(prompt, params)


def generate_kitchen_design(prompt: str, params: dict) -> dict:
    """Generate budget-aware kitchen design"""
    prompt_lower = prompt.lower()
    extracted_dims = params.get("extracted_dimensions", {})
    context = params.get("context", {})
    budget = context.get("budget", 800000)  # Default ₹8L

    # Budget-based kitchen sizing
    if budget <= 500000:  # ₹5L: Small kitchen
        width, length = 8, 10
    elif budget <= 1000000:  # ₹10L: Medium kitchen
        width, length = 10, 12
    else:  # ₹10L+: Large kitchen
        width, length = 12, 15

    # Use extracted dims if provided
    width = extracted_dims.get("width", width)
    length = extracted_dims.get("length", length)

    if "feet" in prompt_lower or "ft" in prompt_lower:
        width *= 0.3048
        length *= 0.3048

    style = "modern"
    if "traditional" in prompt_lower:
        style = "traditional"
    elif "rustic" in prompt_lower:
        style = "rustic"

    objects = [
        {
            "id": "kitchen_floor",
            "type": "floor",
            "material": "tile_ceramic",
            "color_hex": "#F5F5DC",
            "dimensions": {"width": width, "length": length},
        },
        {
            "id": "base_cabinets",
            "type": "cabinet",
            "material": "wood_oak",
            "color_hex": "#FFFFFF",
            "dimensions": {"width": width * 0.6, "depth": 0.6, "height": 0.9},
        },
        {
            "id": "countertop",
            "type": "countertop",
            "material": "granite" if "granite" in prompt_lower else "quartz",
            "color_hex": "#2F4F4F",
            "dimensions": {"width": width * 0.6, "depth": 0.6, "height": 0.05},
        },
    ]

    if "island" in prompt_lower:
        objects.append(
            {
                "id": "kitchen_island",
                "type": "island",
                "material": "wood_oak",
                "dimensions": {"width": 2.4, "depth": 1.2, "height": 0.9},
            }
        )

    return {
        "objects": objects,
        "design_type": "kitchen",
        "style": style,
        "dimensions": {"width": width, "length": length, "height": 2.7},
        "estimated_cost": {"total": min(budget * 1.1, width * length * 35000), "currency": "INR"},
    }


def generate_house_design(prompt: str, params: dict) -> dict:
    """Generate house/building design with budget optimization"""
    logger.info("DESIGN_DEBUG: Generating HOUSE design")
    prompt_lower = prompt.lower()
    extracted_dims = params.get("extracted_dimensions", {})
    context = params.get("context", {})
    budget = context.get("budget", 15000000)  # Default ₹1.5 crores

    # Budget-based dimension optimization
    width, length, height = optimize_house_dimensions_for_budget(budget, extracted_dims)

    logger.info(f"DESIGN_DEBUG: Budget ₹{budget:,} → Optimized dimensions {width}x{length}x{height}")

    if "feet" in prompt_lower or "ft" in prompt_lower:
        width *= 0.3048
        length *= 0.3048
        height *= 0.3048
        logger.info(f"DESIGN_DEBUG: Converted to meters - width: {width}, length: {length}, height: {height}")

    logger.info(f"DESIGN_DEBUG: Final dimensions - width: {width}, length: {length}, height: {height}")

    style = "modern"
    if "traditional" in prompt_lower:
        style = "traditional"
    elif "colonial" in prompt_lower:
        style = "colonial"
    elif "contemporary" in prompt_lower:
        style = "contemporary"

    stories = 1
    if "two story" in prompt_lower or "2 story" in prompt_lower or "2-story" in prompt_lower:
        stories = 2
    elif "three story" in prompt_lower or "3 story" in prompt_lower or "3-story" in prompt_lower:
        stories = 3

    logger.info(f"DESIGN_DEBUG: House style: {style}, stories: {stories}")

    objects = [
        {
            "id": "foundation",
            "type": "foundation",
            "material": "concrete",
            "color_hex": "#808080",
            "dimensions": {"width": width, "length": length, "height": 0.5},
        },
        {
            "id": "exterior_walls",
            "type": "wall",
            "subtype": "exterior",
            "material": "brick" if style == "traditional" else "siding",
            "color_hex": "#D2B48C",
            "dimensions": {"width": width, "length": length, "height": height},
        },
        {
            "id": "roof",
            "type": "roof",
            "material": "shingle_asphalt",
            "color_hex": "#2F4F4F",
            "dimensions": {"width": width + 2, "length": length + 2, "height": 3},
        },
        {
            "id": "front_door",
            "type": "door",
            "subtype": "entrance",
            "material": "wood_oak",
            "color_hex": "#8B4513",
            "dimensions": {"width": 1, "height": 2.1},
        },
        {
            "id": "windows",
            "type": "window",
            "material": "glass_double_pane",
            "color_hex": "#87CEEB",
            "count": 8,
            "dimensions": {"width": 1.2, "height": 1.5},
        },
    ]

    if "garage" in prompt_lower:
        objects.append(
            {
                "id": "garage",
                "type": "garage",
                "material": "concrete",
                "dimensions": {"width": 6, "length": 6, "height": 2.5},
            }
        )
        logger.info("DESIGN_DEBUG: Added garage")

    if "porch" in prompt_lower or "patio" in prompt_lower:
        objects.append(
            {
                "id": "porch",
                "type": "porch",
                "material": "wood_deck",
                "dimensions": {"width": width * 0.8, "length": 3, "height": 0.2},
            }
        )
        logger.info("DESIGN_DEBUG: Added porch")

    result = {
        "objects": objects,
        "design_type": "house",
        "style": style,
        "stories": stories,
        "dimensions": {"width": width, "length": length, "height": height * stories},
        "estimated_cost": {
            "total": min(budget * 1.05, calculate_actual_house_cost(width, length, stories, objects)),
            "currency": "INR",
        },
        "tech_stack": ["Local GPU"],
        "model_used": "local-rtx-3060",
    }

    logger.info(f"DESIGN_DEBUG: Generated house design with {len(objects)} objects")
    return result


def generate_office_design(prompt: str, params: dict) -> dict:
    """Generate office design"""
    prompt_lower = prompt.lower()
    extracted_dims = params.get("extracted_dimensions", {})
    context = params.get("context", {})

    logger.info(f"OFFICE_DEBUG: Prompt='{prompt}', Dims={extracted_dims}, Context={context}")

    # Enhanced detection for executive/private offices
    is_cabin = (
        any(word in prompt_lower for word in ["cabin", "small", "executive", "private", "individual"])
        or context.get("style_preference") == "executive"
        or context.get("space_type") == "private"
    )

    if is_cabin:
        # Small office cabin design
        width = extracted_dims.get("width", 3.6)  # 12 feet default
        length = extracted_dims.get("length", 3.0)  # 10 feet default

        # Convert feet to meters if needed
        if "feet" in prompt_lower or "ft" in prompt_lower:
            # Always convert if feet are mentioned, regardless of value
            width = width * 0.3048
            length = length * 0.3048
            logger.info(
                f"OFFICE_DEBUG: Converted {extracted_dims.get('width', 3.6)}x{extracted_dims.get('length', 3.0)} feet to {width:.2f}x{length:.2f} meters"
            )

        objects = [
            {
                "id": "cabin_floor",
                "type": "floor",
                "material": "vinyl_plank",
                "color_hex": "#D2B48C",
                "dimensions": {"width": width, "length": length},
            },
            {
                "id": "executive_desk",
                "type": "furniture",
                "subtype": "desk",
                "material": "wood_oak",
                "color_hex": "#8B4513",
                "dimensions": {"width": 1.5, "depth": 0.8, "height": 0.75},
            },
            {
                "id": "office_chair",
                "type": "furniture",
                "subtype": "chair",
                "material": "leather",
                "color_hex": "#000000",
                "dimensions": {"width": 0.6, "depth": 0.6, "height": 1.2},
            },
            {
                "id": "storage_cabinet",
                "type": "storage",
                "subtype": "cabinet",
                "material": "wood_oak",
                "color_hex": "#8B4513",
                "dimensions": {"width": 1.2, "depth": 0.4, "height": 1.8},
            },
            {
                "id": "meeting_table",
                "type": "furniture",
                "subtype": "table",
                "material": "wood_oak",
                "color_hex": "#8B4513",
                "dimensions": {"width": 1.0, "depth": 0.6, "height": 0.75},
            },
        ]

        # Add bookcase if mentioned in prompt
        if "bookcase" in prompt_lower or "book" in prompt_lower:
            objects.append(
                {
                    "id": "executive_bookcase",
                    "type": "storage",
                    "subtype": "bookcase",
                    "material": "wood_oak",
                    "color_hex": "#8B4513",
                    "dimensions": {"width": 1.0, "depth": 0.3, "height": 2.0},
                }
            )
            logger.info("OFFICE_DEBUG: Added bookcase to executive office")

        budget = context.get("budget", 400000)
        actual_cost = width * length * 15000  # ₹15k per sqm for office

        result = {
            "objects": objects,
            "design_type": "office_cabin",
            "style": "executive",
            "dimensions": {"width": width, "length": length, "height": 2.7},
            "estimated_cost": {"total": min(budget * 1.1, actual_cost), "currency": "INR"},
        }

        logger.info(
            f"OFFICE_DEBUG: Generated EXECUTIVE office with {len(objects)} objects: {[obj['id'] for obj in objects]}"
        )
        return result
    else:
        # Large office design
        width = extracted_dims.get("width", 20)
        length = extracted_dims.get("length", 30)

        objects = [
            {
                "id": "office_floor",
                "type": "floor",
                "material": "carpet_commercial",
                "color_hex": "#708090",
                "dimensions": {"width": width, "length": length},
            },
            {
                "id": "workstations",
                "type": "furniture",
                "subtype": "desk",
                "material": "laminate",
                "color_hex": "#F5F5DC",
                "count": 12,
                "dimensions": {"width": 1.5, "depth": 0.8, "height": 0.75},
            },
            {
                "id": "conference_room",
                "type": "room",
                "subtype": "meeting",
                "material": "glass_partition",
                "dimensions": {"width": 6, "length": 4, "height": 2.7},
            },
        ]

        budget = context.get("budget", 1500000)
        actual_cost = width * length * 15000  # ₹15k per sqm for office

        result = {
            "objects": objects,
            "design_type": "office",
            "style": "corporate",
            "dimensions": {"width": width, "length": length, "height": 2.7},
            "estimated_cost": {"total": min(budget * 1.1, actual_cost), "currency": "INR"},
        }

        logger.info(
            f"OFFICE_DEBUG: Generated CORPORATE office with {len(objects)} objects: {[obj['id'] for obj in objects]}"
        )
        return result


def generate_bathroom_design(prompt: str, params: dict) -> dict:
    """Generate bathroom design"""
    objects = [
        {
            "id": "bathroom_floor",
            "type": "floor",
            "material": "tile_ceramic",
            "color_hex": "#FFFFFF",
            "dimensions": {"width": 3, "length": 2.5},
        },
        {
            "id": "toilet",
            "type": "fixture",
            "subtype": "toilet",
            "material": "porcelain",
            "color_hex": "#FFFFFF",
            "dimensions": {"width": 0.4, "depth": 0.7, "height": 0.8},
        },
        {
            "id": "shower",
            "type": "fixture",
            "subtype": "shower",
            "material": "glass_tempered",
            "dimensions": {"width": 1, "length": 1, "height": 2},
        },
        {
            "id": "vanity",
            "type": "cabinet",
            "subtype": "vanity",
            "material": "wood_oak",
            "color_hex": "#8B4513",
            "dimensions": {"width": 1.2, "depth": 0.5, "height": 0.85},
        },
    ]

    return {
        "objects": objects,
        "design_type": "bathroom",
        "style": "modern",
        "dimensions": {"width": 3, "length": 2.5, "height": 2.4},
        "estimated_cost": {"total": 400000, "currency": "INR"},
    }


def generate_bedroom_design(prompt: str, params: dict) -> dict:
    """Generate bedroom design"""
    objects = [
        {
            "id": "bedroom_floor",
            "type": "floor",
            "material": "wood_hardwood",
            "color_hex": "#DEB887",
            "dimensions": {"width": 4, "length": 4.5},
        },
        {
            "id": "bed",
            "type": "furniture",
            "subtype": "bed",
            "material": "wood_oak",
            "color_hex": "#8B4513",
            "dimensions": {"width": 2, "length": 2.1, "height": 0.6},
        },
        {
            "id": "dresser",
            "type": "furniture",
            "subtype": "dresser",
            "material": "wood_oak",
            "color_hex": "#8B4513",
            "dimensions": {"width": 1.5, "depth": 0.5, "height": 1},
        },
        {
            "id": "closet",
            "type": "storage",
            "subtype": "closet",
            "material": "wood_oak",
            "dimensions": {"width": 2, "depth": 0.6, "height": 2.4},
        },
    ]

    return {
        "objects": objects,
        "design_type": "bedroom",
        "style": "modern",
        "dimensions": {"width": 4, "length": 4.5, "height": 2.4},
        "estimated_cost": {"total": 300000, "currency": "INR"},
    }


def generate_living_room_design(prompt: str, params: dict) -> dict:
    """Generate living room design"""
    objects = [
        {
            "id": "living_floor",
            "type": "floor",
            "material": "wood_hardwood",
            "color_hex": "#DEB887",
            "dimensions": {"width": 5, "length": 6},
        },
        {
            "id": "sofa",
            "type": "furniture",
            "subtype": "sofa",
            "material": "fabric",
            "color_hex": "#708090",
            "dimensions": {"width": 2.5, "depth": 1, "height": 0.8},
        },
        {
            "id": "coffee_table",
            "type": "furniture",
            "subtype": "table",
            "material": "wood_oak",
            "color_hex": "#8B4513",
            "dimensions": {"width": 1.2, "depth": 0.6, "height": 0.4},
        },
        {
            "id": "tv_stand",
            "type": "furniture",
            "subtype": "entertainment",
            "material": "wood_oak",
            "color_hex": "#8B4513",
            "dimensions": {"width": 1.8, "depth": 0.4, "height": 0.6},
        },
    ]

    return {
        "objects": objects,
        "design_type": "living_room",
        "style": "modern",
        "dimensions": {"width": 5, "length": 6, "height": 2.4},
        "estimated_cost": {"total": 400000, "currency": "INR"},
    }


def generate_apartment_design(prompt: str, params: dict) -> dict:
    """Generate apartment interior design (BHK)"""
    prompt_lower = prompt.lower()
    extracted_dims = params.get("extracted_dimensions", {})
    context = params.get("context", {})
    budget = context.get("budget", 5000000)

    # Extract BHK count
    bhk = 2
    if "penthouse" in prompt_lower:
        bhk = 4
    elif "3bhk" in prompt_lower or "3 bhk" in prompt_lower:
        bhk = 3
    elif "4bhk" in prompt_lower or "4 bhk" in prompt_lower:
        bhk = 4
    elif "1bhk" in prompt_lower or "1 bhk" in prompt_lower or "studio" in prompt_lower:
        bhk = 1
    elif "compact" in prompt_lower:
        bhk = 2

    # Detect materials
    floor_material = "tile_ceramic"
    if "marble" in prompt_lower:
        floor_material = "marble"
    elif "wood" in prompt_lower:
        floor_material = "wood_hardwood"

    # Detect style
    style = "modern"
    if "luxury" in prompt_lower or "penthouse" in prompt_lower:
        style = "luxury"
    elif "minimalist" in prompt_lower or "compact" in prompt_lower:
        style = "minimalist"
    elif "traditional" in prompt_lower:
        style = "traditional"

    # Use extracted dimensions if available
    if extracted_dims.get("width") and extracted_dims.get("length"):
        width = extracted_dims["width"]
        length = extracted_dims["length"]
        total_area = width * length
        logger.info(f"Using extracted dimensions: {width}x{length}m = {total_area:.2f} sqm")
    else:
        # Base dimensions based on BHK
        area_map = {1: 40, 2: 60, 3: 90, 4: 150}
        total_area = area_map.get(bhk, 60)

        # Luxury multiplier
        if style == "luxury":
            total_area = int(total_area * 1.5)

        width = (total_area * 0.6) ** 0.5
        length = (total_area / 0.6) ** 0.5

    objects = [
        {
            "id": "apartment_floor",
            "type": "floor",
            "material": floor_material,
            "color_hex": "#F5F5DC" if floor_material == "marble" else "#DEB887",
            "dimensions": {"width": width, "length": length},
        },
        {
            "id": "living_room",
            "type": "room",
            "subtype": "living",
            "material": "paint",
            "color_hex": "#FFFFFF",
            "dimensions": {"width": width * 0.4, "length": length * 0.4, "height": 3.0 if style == "luxury" else 2.7},
        },
    ]

    # Add bedrooms
    for i in range(bhk):
        objects.append(
            {
                "id": f"bedroom_{i+1}",
                "type": "room",
                "subtype": "bedroom",
                "material": "paint",
                "color_hex": "#F0F0F0",
                "dimensions": {
                    "width": 4 if style == "luxury" else 3.5,
                    "length": 4.5 if style == "luxury" else 4,
                    "height": 3.0 if style == "luxury" else 2.7,
                },
            }
        )

    # Add kitchen
    if "kitchen" in prompt_lower or "modular" in prompt_lower or bhk >= 2:
        objects.append(
            {
                "id": "modular_kitchen",
                "type": "room",
                "subtype": "kitchen",
                "material": "wood_oak",
                "color_hex": "#8B4513",
                "dimensions": {
                    "width": 3.5 if style == "luxury" else 3,
                    "length": 4 if style == "luxury" else 3.5,
                    "height": 3.0 if style == "luxury" else 2.7,
                },
            }
        )
        objects.append(
            {
                "id": "kitchen_cabinets",
                "type": "cabinet",
                "material": "wood_oak",
                "color_hex": "#FFFFFF",
                "dimensions": {
                    "width": 3 if style == "luxury" else 2.5,
                    "depth": 0.6,
                    "height": 2.4 if style == "luxury" else 2.1,
                },
            }
        )

    # Add bathrooms
    bathrooms = bhk  # Typically BHK count = bathroom count
    for i in range(bathrooms):
        objects.append(
            {
                "id": f"bathroom_{i+1}",
                "type": "room",
                "subtype": "bathroom",
                "material": "tile_ceramic",
                "color_hex": "#FFFFFF",
                "dimensions": {
                    "width": 2.5 if style == "luxury" else 2,
                    "length": 3 if style == "luxury" else 2.5,
                    "height": 3.0 if style == "luxury" else 2.7,
                },
            }
        )

    # Add furniture based on style and prompt
    if "glass" in prompt_lower:
        objects.append(
            {
                "id": "glass_walls",
                "type": "wall",
                "subtype": "partition",
                "material": "glass_tempered",
                "color_hex": "#E0FFFF",
                "dimensions": {"width": width * 0.3, "height": 3.0 if style == "luxury" else 2.7},
            }
        )

    if "wooden" in prompt_lower or "wood" in prompt_lower:
        objects.append(
            {
                "id": "wooden_interiors",
                "type": "furniture",
                "subtype": "paneling",
                "material": "wood_oak",
                "color_hex": "#8B4513",
                "dimensions": {"width": width * 0.5, "depth": 0.05, "height": 3.0 if style == "luxury" else 2.7},
            }
        )

    if "space-saving" in prompt_lower or "compact" in prompt_lower:
        objects.append(
            {
                "id": "space_saving_furniture",
                "type": "furniture",
                "subtype": "modular",
                "material": "wood_oak",
                "color_hex": "#D2B48C",
                "dimensions": {"width": 2, "depth": 0.5, "height": 2},
            }
        )

    # Calculate cost based on budget
    base_cost = total_area * 25000  # ₹25k per sqm for apartments
    if style == "luxury":
        base_cost *= 2.5
    elif style == "minimalist":
        base_cost *= 0.8

    # Use provided budget if it's reasonable
    if budget > 0 and budget < base_cost * 2:
        estimated_cost = budget
    else:
        estimated_cost = base_cost

    return {
        "objects": objects,
        "design_type": "apartment",
        "style": style,
        "stories": 1,
        "dimensions": {"width": width, "length": length, "height": 3.0 if style == "luxury" else 2.7},
        "estimated_cost": {"total": estimated_cost, "currency": "INR"},
        "metadata": {"bhk_count": bhk, "total_area_sqm": total_area, "budget_provided": budget},
    }


def generate_commercial_design(prompt: str, params: dict) -> dict:
    """Generate commercial space design"""
    prompt_lower = prompt.lower()

    width = 15
    length = 20

    objects = [
        {
            "id": "commercial_floor",
            "type": "floor",
            "material": "tile_ceramic",
            "color_hex": "#F5F5F5",
            "dimensions": {"width": width, "length": length},
        },
        {
            "id": "glass_facade",
            "type": "wall",
            "subtype": "exterior",
            "material": "glass_tempered",
            "color_hex": "#E0FFFF",
            "dimensions": {"width": width, "height": 4},
        },
    ]

    if "steel" in prompt_lower:
        objects.append(
            {
                "id": "steel_structure",
                "type": "structure",
                "material": "steel",
                "color_hex": "#808080",
                "dimensions": {"width": width, "length": length, "height": 4},
            }
        )

    return {
        "objects": objects,
        "design_type": "commercial",
        "style": "contemporary",
        "dimensions": {"width": width, "length": length, "height": 4},
        "estimated_cost": {"total": width * length * 30000, "currency": "INR"},
    }


def generate_generic_design(prompt: str, params: dict) -> dict:
    """Generate generic design for unspecified prompts"""
    return {
        "objects": [
            {
                "id": "base_structure",
                "type": "structure",
                "material": "concrete",
                "color_hex": "#808080",
                "dimensions": {"width": 10, "length": 10, "height": 3},
            }
        ],
        "design_type": "generic",
        "style": "modern",
        "dimensions": {"width": 10, "length": 10, "height": 3},
        "estimated_cost": {"total": 500000, "currency": "INR"},
    }


async def run_yotta_lm(prompt: str, params: dict) -> dict:
    """Run inference on Yotta cloud API"""
    logger.info(f"Running Yotta LM for prompt length: {len(prompt)}")

    # Always use mock response for testing (no paid API calls)
    logger.info("Using mock Yotta response (testing mode)")

    # Generate design for complex prompts
    spec_json = generate_design_from_prompt(prompt, params)
    spec_json["tech_stack"] = ["Yotta Cloud"]
    spec_json["model_used"] = "yotta-advanced-model"

    # Log mock usage for billing
    log_usage("yotta", len(prompt), 0.01, params.get("user_id"))  # $0.01 per token

    return {
        "spec_json": spec_json,
        "preview_data": f"Yotta cloud generated {spec_json.get('design_type', 'design')} for: {prompt[:50]}...",
        "provider": "yotta",
        "feedback": f"Yotta cloud generated advanced {spec_json.get('design_type', 'design')} using strategy: {params.get('strategy', 'premium')}",
    }


def extract_dimensions_from_prompt(prompt: str) -> dict:
    """Extract dimensions from natural language prompt"""
    dimensions = {}
    prompt_lower = prompt.lower()

    # Extract area (sq ft, sqft, square feet, sq m, sqm)
    area_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:sq\s*ft|sqft|square\s*feet|sq\s*feet|sq\s*m|sqm|square\s*meters?)", prompt_lower
    )
    if area_match:
        area_val = float(area_match.group(1))
        # Check if it's in sq ft or sq m
        if "sq m" in area_match.group(0) or "sqm" in area_match.group(0):
            area_sqm = area_val
        else:
            area_sqm = area_val * 0.092903  # Convert sq ft to sq m

        # Don't set width/length from area if length is already specified
        if "length" not in dimensions:
            side = area_sqm**0.5
            dimensions["width"] = side
            dimensions["length"] = side
        dimensions["area_sqm"] = area_sqm
        logger.info(f"Extracted area: {area_val} → {area_sqm:.2f} sqm")

    # Extract diameter/radius
    diameter_match = re.search(r"diameter\s*(\d+(?:\.\d+)?)\s*(?:feet|ft|meter|metres|m|cm|cms)?", prompt_lower)
    if diameter_match:
        diameter = float(diameter_match.group(1))
        if "cm" in prompt_lower:
            diameter *= 0.01
        elif "feet" in prompt_lower or "ft" in prompt_lower:
            diameter *= 0.3048
        dimensions["diameter"] = diameter
        dimensions["width"] = diameter
        dimensions["length"] = diameter

    radius_match = re.search(r"radius\s*(\d+(?:\.\d+)?)\s*(?:feet|ft|meter|metres|m|cm|cms)?", prompt_lower)
    if radius_match:
        radius = float(radius_match.group(1))
        if "cm" in prompt_lower:
            radius *= 0.01
        elif "feet" in prompt_lower or "ft" in prompt_lower:
            radius *= 0.3048
        dimensions["radius"] = radius
        dimensions["width"] = radius * 2
        dimensions["length"] = radius * 2

    # Extract individual dimensions (height, length, width, breadth) FIRST
    height_match = re.search(r"height\s*(\d+(?:\.\d+)?)\s*(?:feet|ft|meter|metres|m|cm|cms)?", prompt_lower)
    if height_match:
        dimensions["height"] = float(height_match.group(1))

    length_match = re.search(r"length\s*(\d+(?:\.\d+)?)\s*(?:feet|ft|meter|metres|m|cm|cms)?", prompt_lower)
    if length_match:
        dimensions["length"] = float(length_match.group(1))

    width_match = re.search(r"(?:width|breadth)\s*(\d+(?:\.\d+)?)\s*(?:feet|ft|meter|metres|m|cm|cms)?", prompt_lower)
    if width_match:
        dimensions["width"] = float(width_match.group(1))

    # Extract area (sq ft, sqft, square feet, sq m, sqm)
    area_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:sq\s*ft|sqft|square\s*feet|sq\s*feet|sq\s*m|sqm|square\s*meters?)", prompt_lower
    )
    if area_match:
        area_val = float(area_match.group(1))
        # Check if it's in sq ft or sq m
        if "sq m" in area_match.group(0) or "sqm" in area_match.group(0):
            area_sqm = area_val
        else:
            area_sqm = area_val * 0.092903  # Convert sq ft to sq m

        # Calculate missing dimension from area
        if "length" in dimensions and "width" not in dimensions:
            dimensions["width"] = area_sqm / dimensions["length"]
        elif "width" in dimensions and "length" not in dimensions:
            dimensions["length"] = area_sqm / dimensions["width"]
        elif "length" not in dimensions and "width" not in dimensions:
            side = area_sqm**0.5
            dimensions["width"] = side
            dimensions["length"] = side

        dimensions["area_sqm"] = area_sqm
        logger.info(f"Extracted area: {area_val} → {area_sqm:.2f} sqm, dims: {dimensions}")

    # Pattern matching for formats like "24x17x34" or "15x23"
    if not dimensions:
        patterns = [
            r"(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)",  # 3D: WxLxH
            r"(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)",  # 2D: WxL
        ]

        for pattern in patterns:
            matches = re.findall(pattern, prompt_lower)
            if matches:
                if len(matches[0]) == 3:  # 3D dimensions
                    dimensions = {
                        "width": float(matches[0][0]),
                        "length": float(matches[0][1]),
                        "height": float(matches[0][2]),
                    }
                elif len(matches[0]) == 2:  # 2D dimensions
                    dimensions = {
                        "width": float(matches[0][0]),
                        "length": float(matches[0][1]),
                        "height": 3.0,
                    }
                break

    # Unit conversion - check for feet, cm, or meters
    if dimensions:
        unit = "meters"  # default
        if "feet" in prompt_lower or " ft" in prompt_lower or "ft " in prompt_lower:
            unit = "feet"
        elif "cm" in prompt_lower or "cms" in prompt_lower:
            unit = "cm"

        # Convert to meters
        if unit == "feet":
            for key in ["width", "length", "height", "diameter", "radius"]:
                if key in dimensions:
                    dimensions[key] *= 0.3048
            logger.info(f"Converted from feet to meters: {dimensions}")
        elif unit == "cm":
            for key in ["width", "length", "height", "diameter", "radius"]:
                if key in dimensions:
                    dimensions[key] *= 0.01
            logger.info(f"Converted from cm to meters: {dimensions}")

    return dimensions


async def lm_run(prompt: str, params: dict = None) -> dict:
    """Main entry point - uses AI models for generation"""
    if params is None:
        params = {}

    logger.info(f"🤖 LM_RUN: Processing with AI models: '{prompt[:100]}...'")

    # Extract dimensions from prompt
    extracted_dims = extract_dimensions_from_prompt(prompt)
    if extracted_dims:
        params["extracted_dimensions"] = extracted_dims
        logger.info(f"📏 Extracted dimensions: {extracted_dims}")

    # Always try AI first, fallback to templates if needed
    return await run_local_lm(prompt, params)


def optimize_house_dimensions_for_budget(budget: float, extracted_dims: dict) -> tuple:
    """Optimize house dimensions to fit within budget"""
    # Budget tiers with corresponding dimensions (optimized for realistic costs)
    budget_tiers = [
        (5000000, (12, 15, 6)),  # ₹50L: 12x15m, 6m height (180 sqm)
        (8000000, (14, 18, 7)),  # ₹80L: 14x18m, 7m height (252 sqm)
        (12000000, (16, 22, 7)),  # ₹1.2Cr: 16x22m, 7m height (352 sqm)
        (20000000, (20, 28, 8)),  # ₹2Cr: 20x28m, 8m height (560 sqm)
        (50000000, (25, 35, 8)),  # ₹5Cr: 25x35m, 8m height (875 sqm)
        (float("inf"), (30, 40, 10)),  # ₹5Cr+: 30x40m, 10m height (1200 sqm)
    ]

    # Find appropriate tier for budget
    for budget_limit, (w, l, h) in budget_tiers:
        if budget <= budget_limit:
            # Use extracted dimensions if provided and reasonable
            width = extracted_dims.get("width", w)
            length = extracted_dims.get("length", l)
            height = extracted_dims.get("height", h)

            # Scale down if extracted dims would exceed budget
            if width * length > w * l * 1.5:  # 50% tolerance
                scale = ((w * l) / (width * length)) ** 0.5
                width *= scale
                length *= scale

            return width, length, height

    return 30, 40, 8  # Default fallback


def calculate_actual_house_cost(width: float, length: float, stories: int, objects: list) -> float:
    """Calculate budget-optimized house cost"""
    area = width * length

    # Reduced construction cost for budget optimization
    cost_per_sqm = 15000  # Reduced from ₹25k to ₹15k per sqm
    base_cost = area * stories * cost_per_sqm

    # Reduced object premiums
    premiums = {
        "garage": 100000,  # Reduced from ₹2L to ₹1L
        "roof": 75000,  # Reduced from ₹1.5L to ₹75k
        "foundation": 50000,  # Reduced from ₹1L to ₹50k
    }

    premium_cost = sum(premiums.get(obj.get("type"), 0) for obj in objects)

    return base_cost + premium_cost


def log_usage(provider: str, tokens: int, cost_per_token: float, user_id: str = None):
    """Log LM usage for billing with detailed tracking"""
    total_cost = cost_per_token * tokens
    usage_log = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "tokens": tokens,
        "cost_per_token": cost_per_token,
        "total_cost": total_cost,
        "user_id": user_id,
        "gpu_hours": tokens / 1000 if provider == "local" else 0,  # Estimate GPU usage
        "api_calls": 1 if provider == "yotta" else 0,
    }

    # Log for monitoring and billing
    logger.info(f"BILLING: {usage_log}")

    # Store in usage log file (with error handling)
    try:
        with open("lm_usage.log", "a") as f:
            f.write(f"{usage_log}\n")
    except Exception as e:
        logger.warning(f"Failed to write usage log: {e}")

    # Log to audit system (simplified)
    try:
        from app.utils import log_audit_event

        if user_id:
            log_audit_event(
                "lm_usage",
                user_id,
                {"provider": provider, "tokens": tokens, "cost": total_cost},
            )
    except ImportError:
        logger.debug("Audit logging not available - skipping")


class LMAdapter:
    async def generate(self, prompt: str, model: str = "default") -> str:
        result = await lm_run(prompt, {"model": model})
        return result["preview_data"]


lm_adapter = LMAdapter()
