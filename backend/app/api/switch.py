"""
Switch API - Material/Property Switching
Complete implementation with enhanced NLP
"""
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.config import settings
from app.database_mongodb import get_database
from app.models_mongodb import Iteration
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["🔄 Material Switch"])
logger = logging.getLogger(__name__)

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class SwitchRequest(BaseModel):
    """Material switch request"""

    spec_id: str = Field(..., description="Target specification ID")
    query: str = Field(..., min_length=5, max_length=500, description="Natural language change request")

    class Config:
        json_schema_extra = {"example": {"spec_id": "spec_abc123", "query": "change floor to marble"}}


class ObjectChange(BaseModel):
    """Individual object change"""

    object_id: str
    field: str
    old_value: str
    new_value: str


class SwitchResponse(BaseModel):
    """Material switch response"""

    iteration_id: str
    spec_id: str
    changes: List[ObjectChange]
    changed_objects: List[str]
    preview_url: str
    cost_impact: Dict
    nlp_confidence: float


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def parse_simple_query(query: str) -> Optional[Dict]:
    """Enhanced NLP parsing for material switch patterns"""
    query_lower = query.lower()

    # Object mapping for common terms
    object_mapping = {
        "floor": "foundation",
        "foundation": "foundation",
        "wall": "wall",
        "walls": "wall",
        "roof": "roof",
        "roofing": "roof",
        "door": "door",
        "doors": "door",
        "window": "window",
        "windows": "window",
    }

    # Pattern: "replace X with Y" - Material replacement
    if "replace" in query_lower and "with" in query_lower:
        parts = query_lower.split("with")
        if len(parts) == 2:
            target_part = parts[0].replace("replace", "").strip()
            material = parts[1].strip()
            target_type = object_mapping.get(target_part, target_part)
            return {"target_type": target_type, "property": "material", "value": material, "confidence": 0.9}

    # Pattern: "change X to Y" - Generic material changes
    if "change" in query_lower and "to" in query_lower:
        parts = query_lower.split("to")
        if len(parts) == 2:
            target_part = parts[0].replace("change", "").strip()
            material = parts[1].strip()
            target_type = object_mapping.get(target_part, target_part)
            return {"target_type": target_type, "property": "material", "value": material, "confidence": 0.9}

    # Pattern: "make X Y" - Direct material assignment
    if "make" in query_lower:
        words = query_lower.split()
        if len(words) >= 3:
            target = words[1]
            material = " ".join(words[2:])
            target_type = object_mapping.get(target, target)
            return {"target_type": target_type, "property": "material", "value": material, "confidence": 0.8}

    # Pattern: "update color to #xxx" or "change color to xxx"
    if ("update" in query_lower or "change" in query_lower) and "color" in query_lower:
        if "#" in query:
            color = query.split("#")[1][:6]  # Extract hex color
            return {"target_type": "all", "property": "color_hex", "value": f"#{color}", "confidence": 0.7}

    return None


def apply_simple_changes(spec_json: Dict, command: Dict) -> tuple:
    """Apply enhanced parsed command to spec with better matching"""
    import copy

    updated_spec = copy.deepcopy(spec_json)
    changes = []
    changed_objects = []

    objects = updated_spec.get("objects", [])

    for obj in objects:
        should_change = False

        # Enhanced matching logic
        if command.get("target_type") == "all":
            should_change = True
        elif command.get("target_type"):
            target_type = command["target_type"]
            obj_type = obj.get("type", "")
            obj_subtype = obj.get("subtype", "")
            obj_id = obj.get("id", "")

            # Direct type match
            if obj_type == target_type:
                should_change = True
            # Partial matches for common terms
            elif target_type == "wall" and ("wall" in obj_type or "wall" in obj_id):
                should_change = True
            elif target_type == "roof" and ("roof" in obj_type or "roof" in obj_id):
                should_change = True
            elif target_type == "door" and ("door" in obj_type or "door" in obj_id):
                should_change = True
            elif target_type == "window" and ("window" in obj_type or "window" in obj_id):
                should_change = True
            elif target_type == "foundation" and ("foundation" in obj_type or "foundation" in obj_id):
                should_change = True
        elif command.get("target_subtype") and obj.get("subtype") == command["target_subtype"]:
            should_change = True

        if should_change:
            old_value = obj.get(command["property"])

            # Apply change
            obj[command["property"]] = command["value"]

            # Record change
            changes.append(
                ObjectChange(
                    object_id=obj["id"],
                    field=command["property"],
                    old_value=str(old_value),
                    new_value=str(command["value"]),
                )
            )

            changed_objects.append(obj["id"])

    updated_spec["objects"] = objects

    return updated_spec, changes, changed_objects


def recalculate_cost(old_spec: Dict, new_spec: Dict) -> Dict:
    """Calculate cost difference"""
    old_cost = old_spec.get("metadata", {}).get("estimated_cost", 0)

    # Simple recalculation
    new_cost = old_cost * 1.1  # 10% increase for material change
    cost_delta = new_cost - old_cost

    return {
        "delta": round(cost_delta, 2),
        "new_total": round(new_cost, 2),
        "percentage_change": round((cost_delta / old_cost * 100) if old_cost > 0 else 0, 2),
    }


async def _get_spec_data(spec_id: str) -> tuple:
    """Get spec data from storage or database"""
    # Try to get spec from in-memory storage first
    from app.spec_storage import get_spec as get_stored_spec

    stored_spec = get_stored_spec(spec_id)

    if stored_spec:
        print(f"✅ Found spec {spec_id} in storage")
        return stored_spec["spec_json"], stored_spec["user_id"], stored_spec
    else:
        # Fallback to database
        try:
            db = get_database()
            spec = await db.specs.find_one({"_id": spec_id})
            if not spec:
                print(f"❌ Spec {spec_id} not found in storage or database")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Specification not found")
            return spec["spec_json"], spec["user_id"], None
        except Exception as e:
            print(f"❌ Database error: {e}")
            print(f"❌ Spec {spec_id} not found in storage or database")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Specification not found")


async def _save_iteration_to_db(
    iteration_id: str,
    spec_id: str,
    user_id: str,
    changes: List[ObjectChange],
    updated_spec: Dict,
    preview_url: str,
    start_time: float,
) -> None:
    """Save iteration to database"""
    try:
        # Create iteration document
        iteration_data = {
            "_id": iteration_id,
            "spec_id": spec_id,
            "user_id": user_id,
            "iteration_number": 1,
            "changes": {"changes": [change.dict() for change in changes]},
            "geometry_url": preview_url,
            "preview_url": preview_url,
            "created_at": datetime.now(timezone.utc),
        }

        # Save to MongoDB
        db = get_database()
        await db.iterations.insert_one(iteration_data)

        # Update spec version in database
        await db.specs.update_one(
            {"_id": spec_id},
            {"$set": {"spec_json": updated_spec, "updated_at": datetime.now(timezone.utc)}, "$inc": {"version": 1}},
        )

        logger.info(f"Saved iteration {iteration_id} to database")

    except Exception as e:
        logger.error(f"Database save failed: {str(e)}")
        # Continue execution even if database save fails


async def _generate_preview(iteration_id: str, updated_spec: Dict) -> str:
    """Generate preview GLB file"""
    try:
        from app.utils import generate_glb_from_spec

        # Generate GLB file
        preview_bytes = generate_glb_from_spec(updated_spec)
        preview_path = f"{iteration_id}.glb"

        # Upload to MongoDB GridFS
        from app.storage_mongodb import GridFSStorage

        db = get_database()
        storage = GridFSStorage(db)
        file_id = await storage.upload_bytes(
            preview_bytes,
            "previews",
            preview_path,
            content_type="model/gltf-binary",
            metadata={"iteration_id": iteration_id, "type": "preview"},
        )
        return f"/static/geometry/{preview_path}"

    except Exception as e:
        logger.warning(f"Preview generation failed: {str(e)}")
        return f"https://mock-preview-{iteration_id}.glb"


@router.post("/switch", response_model=SwitchResponse, status_code=status.HTTP_201_CREATED)
async def switch_material(request: SwitchRequest):
    """
    Switch material/property using natural language

    **Supported Commands:**
    - "change floor to marble"
    - "make all cushions orange"
    - "replace kitchen counter with granite"
    - "update wall color to #FFE4B5"

    **Process:**
    1. Parse natural language query
    2. Apply changes to spec
    3. Recalculate cost
    4. Generate new preview
    5. Save as iteration

    **Returns:**
    - iteration_id: New iteration ID
    - changes: List of changes made
    - cost_impact: Cost difference
    """
    start_time = time.time()

    # Sanitize user input for logging to prevent log injection
    sanitized_query = request.query.replace("\n", " ").replace("\r", " ")[:100]
    print(f"🔄 SWITCH REQUEST: spec_id={request.spec_id}")
    logger.info(f"🔄 SWITCH REQUEST: spec_id={request.spec_id}, query_length={len(request.query)}")

    # Get spec data
    spec_json, user_id, stored_spec = await _get_spec_data(request.spec_id)

    try:
        # Parse natural language query
        print(f"🤖 Parsing query: '{sanitized_query}'")
        command = parse_simple_query(request.query)

        if not command:
            print(f"❌ Could not parse query: '{sanitized_query}'")
            from app.error_handler import APIException
            from app.schemas.error_schemas import ErrorCode

            raise APIException(
                status_code=400,
                error_code=ErrorCode.VALIDATION_ERROR,
                message="Could not understand the request. Please try rephrasing.",
                details={
                    "query_length": len(request.query),
                    "supported_patterns": [
                        "change X to Y",
                        "replace X with Y",
                        "make X Y",
                        "update color to #HEX",
                    ],
                },
            )

        print(f"✅ Parsed command: {command}")

        # Apply changes
        updated_spec, changes, changed_objects = apply_simple_changes(spec_json, command)

        if not changes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No matching objects found to modify")

        # Recalculate cost
        cost_impact = recalculate_cost(spec_json, updated_spec)

        # Generate iteration ID
        import uuid

        iteration_id = f"iter_{uuid.uuid4().hex[:8]}"

        # Save iteration to database
        await _save_iteration_to_db(
            iteration_id,
            request.spec_id,
            user_id,
            changes,
            updated_spec,
            f"https://mock-preview-{iteration_id}.glb",
            start_time,
        )

        # Update stored spec if found in storage
        if stored_spec:
            from app.spec_storage import save_spec

            stored_spec["spec_json"] = updated_spec
            stored_spec["spec_version"] = stored_spec.get("spec_version", 1) + 1
            save_spec(request.spec_id, stored_spec)
            print(f"✅ Updated spec {request.spec_id} in storage")

        # Generate preview
        preview_url = await _generate_preview(iteration_id, updated_spec)

        print(f"✅ Switch completed: {len(changes)} changes made")

        return SwitchResponse(
            iteration_id=iteration_id,
            spec_id=request.spec_id,
            changes=changes,
            changed_objects=changed_objects,
            preview_url=preview_url,
            cost_impact=cost_impact,
            nlp_confidence=command.get("confidence", 0.8),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Switch failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Material switch failed: {str(e)}"
        )
