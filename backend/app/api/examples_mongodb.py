"""
Example MongoDB Endpoint Implementations
Shows how to convert endpoints from Supabase to MongoDB
"""

from datetime import datetime
from typing import List, Optional

from app.database_mongodb import get_database
from app.storage_mongodb import GridFSStorage, upload_geometry, upload_preview
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter()


# ============================================================================
# USER ENDPOINTS
# ============================================================================


@router.post("/users")
async def create_user(user_data: dict):
    """Create new user"""
    db = get_database()

    # Check if user exists
    existing = await db.users.find_one({"username": user_data["username"]})
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    # Insert user
    user_data["_id"] = user_data.get("id", str(ObjectId()))
    user_data["created_at"] = datetime.utcnow()
    user_data["updated_at"] = datetime.utcnow()

    result = await db.users.insert_one(user_data)
    return {"id": str(result.inserted_id)}


@router.get("/users/{user_id}")
async def get_user(user_id: str):
    """Get user by ID"""
    db = get_database()

    user = await db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Convert ObjectId to string
    user["_id"] = str(user["_id"])
    return user


@router.get("/users")
async def list_users(skip: int = 0, limit: int = 10):
    """List all users"""
    db = get_database()

    users = await db.users.find().skip(skip).limit(limit).to_list(None)

    # Convert ObjectIds
    for user in users:
        user["_id"] = str(user["_id"])

    return users


@router.put("/users/{user_id}")
async def update_user(user_id: str, update_data: dict):
    """Update user"""
    db = get_database()

    result = await db.users.update_one({"_id": user_id}, {"$set": {**update_data, "updated_at": datetime.utcnow()}})

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"updated": result.modified_count}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str):
    """Delete user"""
    db = get_database()

    result = await db.users.delete_one({"_id": user_id})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"deleted": True}


# ============================================================================
# SPEC ENDPOINTS
# ============================================================================


@router.post("/specs")
async def create_spec(spec_data: dict, user_id: str):
    """Create new specification"""
    db = get_database()

    spec_data["_id"] = str(ObjectId())
    spec_data["user_id"] = user_id
    spec_data["created_at"] = datetime.utcnow()
    spec_data["updated_at"] = datetime.utcnow()
    spec_data["status"] = "draft"
    spec_data["version"] = 1

    result = await db.specs.insert_one(spec_data)
    return {"id": str(result.inserted_id)}


@router.get("/specs/{spec_id}")
async def get_spec(spec_id: str):
    """Get specification by ID"""
    db = get_database()

    spec = await db.specs.find_one({"_id": spec_id})
    if not spec:
        raise HTTPException(status_code=404, detail="Spec not found")

    spec["_id"] = str(spec["_id"])
    return spec


@router.get("/users/{user_id}/specs")
async def list_user_specs(user_id: str, skip: int = 0, limit: int = 10):
    """List user's specifications"""
    db = get_database()

    specs = await db.specs.find({"user_id": user_id}).skip(skip).limit(limit).to_list(None)

    for spec in specs:
        spec["_id"] = str(spec["_id"])

    return specs


@router.put("/specs/{spec_id}")
async def update_spec(spec_id: str, update_data: dict):
    """Update specification"""
    db = get_database()

    update_data["updated_at"] = datetime.utcnow()

    result = await db.specs.update_one({"_id": spec_id}, {"$set": update_data})

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Spec not found")

    return {"updated": result.modified_count}


@router.delete("/specs/{spec_id}")
async def delete_spec(spec_id: str):
    """Delete specification"""
    db = get_database()

    result = await db.specs.delete_one({"_id": spec_id})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Spec not found")

    return {"deleted": True}


# ============================================================================
# ITERATION ENDPOINTS
# ============================================================================


@router.post("/specs/{spec_id}/iterations")
async def create_iteration(spec_id: str, iteration_data: dict, user_id: str):
    """Create new iteration"""
    db = get_database()

    # Get current iteration count
    count = await db.iterations.count_documents({"spec_id": spec_id})

    iteration_data["_id"] = str(ObjectId())
    iteration_data["spec_id"] = spec_id
    iteration_data["user_id"] = user_id
    iteration_data["iteration_number"] = count + 1
    iteration_data["created_at"] = datetime.utcnow()

    result = await db.iterations.insert_one(iteration_data)
    return {"id": str(result.inserted_id)}


@router.get("/specs/{spec_id}/iterations")
async def list_iterations(spec_id: str):
    """List all iterations for a spec"""
    db = get_database()

    iterations = await db.iterations.find({"spec_id": spec_id}).sort("iteration_number", -1).to_list(None)

    for iteration in iterations:
        iteration["_id"] = str(iteration["_id"])

    return iterations


# ============================================================================
# EVALUATION ENDPOINTS
# ============================================================================


@router.post("/specs/{spec_id}/evaluations")
async def create_evaluation(spec_id: str, eval_data: dict, user_id: str):
    """Create evaluation"""
    db = get_database()

    eval_data["_id"] = str(ObjectId())
    eval_data["spec_id"] = spec_id
    eval_data["user_id"] = user_id
    eval_data["created_at"] = datetime.utcnow()

    result = await db.evaluations.insert_one(eval_data)
    return {"id": str(result.inserted_id)}


@router.get("/specs/{spec_id}/evaluations")
async def list_evaluations(spec_id: str):
    """List evaluations for a spec"""
    db = get_database()

    evaluations = await db.evaluations.find({"spec_id": spec_id}).to_list(None)

    for eval in evaluations:
        eval["_id"] = str(eval["_id"])

    return evaluations


# ============================================================================
# FILE UPLOAD ENDPOINTS
# ============================================================================


@router.post("/specs/{spec_id}/upload-preview")
async def upload_spec_preview(spec_id: str, file_data: bytes):
    """Upload preview image"""
    db = get_database()
    storage = GridFSStorage(db)

    file_id = await upload_preview(storage, spec_id, file_data, format="png")

    # Update spec with preview URL
    await db.specs.update_one({"_id": spec_id}, {"$set": {"preview_url": file_id}})

    return {"file_id": file_id}


@router.post("/specs/{spec_id}/upload-geometry")
async def upload_spec_geometry(spec_id: str, file_data: bytes):
    """Upload geometry file"""
    db = get_database()
    storage = GridFSStorage(db)

    file_id = await upload_geometry(storage, spec_id, file_data)

    # Update spec with geometry URL
    await db.specs.update_one({"_id": spec_id}, {"$set": {"geometry_url": file_id}})

    return {"file_id": file_id}


@router.get("/files/{file_id}")
async def download_file(file_id: str, bucket: str = "files"):
    """Download file"""
    db = get_database()
    storage = GridFSStorage(db)

    file_data = await storage.download_file(file_id, bucket)

    return {"data": file_data.hex(), "size": len(file_data)}  # Convert bytes to hex for JSON


# ============================================================================
# AGGREGATION EXAMPLES
# ============================================================================


@router.get("/stats/specs-by-city")
async def get_specs_by_city():
    """Get spec count by city"""
    db = get_database()

    pipeline = [{"$group": {"_id": "$city", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]

    results = await db.specs.aggregate(pipeline).to_list(None)
    return results


@router.get("/stats/user-activity")
async def get_user_activity(user_id: str):
    """Get user activity stats"""
    db = get_database()

    specs_count = await db.specs.count_documents({"user_id": user_id})
    iterations_count = await db.iterations.count_documents({"user_id": user_id})
    evaluations_count = await db.evaluations.count_documents({"user_id": user_id})

    return {
        "specs": specs_count,
        "iterations": iterations_count,
        "evaluations": evaluations_count,
    }


# ============================================================================
# SEARCH ENDPOINTS
# ============================================================================


@router.get("/specs/search")
async def search_specs(query: str, user_id: Optional[str] = None):
    """Search specifications"""
    db = get_database()

    search_filter = {
        "$or": [
            {"title": {"$regex": query, "$options": "i"}},
            {"description": {"$regex": query, "$options": "i"}},
        ]
    }

    if user_id:
        search_filter["user_id"] = user_id

    specs = await db.specs.find(search_filter).to_list(None)

    for spec in specs:
        spec["_id"] = str(spec["_id"])

    return specs


__all__ = [router]
