from typing import Optional

from app.auth_mongodb import get_current_user, get_db
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter()


@router.get("/history/{spec_id}")
async def get_spec_history(
    spec_id: str,
    current_user: str = Depends(get_current_user),
    limit: Optional[int] = Query(50, description="Maximum number of iterations to return"),
):
    """Get complete history for a specific spec including iterations and evaluations"""

    # Get the spec
    spec = None  # Mock database operation
    if not spec:
        raise HTTPException(status_code=404, detail="Spec not found")

    # Get iterations
    iterations = (
        db.query(Iteration)
        .filter(Iteration.spec_id == spec_id)
        .order_by(Iteration.created_at.desc())
        .limit(limit)
        .all()
    )

    # Get evaluations
    evaluations = (
        db.query(Evaluation)
        .filter(Evaluation.spec_id == spec_id)
        .order_by(Evaluation.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "spec_id": spec_id,
        "spec": {
            "spec_id": spec.id,
            "user_id": spec.user_id,
            "project_id": spec.project_id,
            "prompt": spec.prompt,
            "spec_json": spec.spec_json,
            "version": spec.version,
            "created_at": spec.created_at,
            "updated_at": spec.updated_at,
        },
        "iterations": [
            {
                "iter_id": iter.id,
                "query": iter.query,
                "diff": iter.diff,
                "spec_json": iter.spec_json,
                "timestamp": iter.created_at,
            }
            for iter in iterations
        ],
        "evaluations": [
            {
                "eval_id": eval.id,
                "user_id": eval.user_id,
                "rating": eval.rating,
                "notes": eval.notes,
                "timestamp": eval.created_at,
            }
            for eval in evaluations
        ],
        "total_iterations": len(iterations),
        "total_evaluations": len(evaluations),
    }


@router.get("/history")
async def get_user_history(
    current_user: str = Depends(get_current_user),
    limit: Optional[int] = Query(20, description="Maximum number of specs to return"),
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
):
    """Get complete history with data integrity for all specs"""

    query = None  # Mock database operation

    if project_id:
        query = query.filter(Spec.project_id == project_id)

    specs = query.order_by(Spec.updated_at.desc()).limit(limit).all()

    specs_data = []
    for spec in specs:
        # Get counts for related data
        iterations_count = None  # Mock database operation
        evaluations_count = None  # Mock database operation
        compliance_count = None  # Mock database operation

        specs_data.append(
            {
                "spec_id": spec.id,
                "project_id": spec.project_id,
                "prompt": spec.prompt,
                "city": spec.city,
                "design_type": spec.design_type,
                "version": spec.version,
                "status": spec.status,
                "compliance_status": spec.compliance_status,
                "estimated_cost": spec.estimated_cost,
                "currency": spec.currency,
                "preview_url": spec.preview_url,
                "geometry_url": spec.geometry_url,
                "created_at": spec.created_at.isoformat() if spec.created_at else None,
                "updated_at": spec.updated_at.isoformat() if spec.updated_at else None,
                "data_integrity": {
                    "has_spec_json": spec.spec_json is not None,
                    "has_preview": spec.preview_url is not None,
                    "has_geometry": spec.geometry_url is not None,
                    "iterations_count": iterations_count,
                    "evaluations_count": evaluations_count,
                    "compliance_count": compliance_count,
                    "auditable": True,
                },
            }
        )

    return {
        "user_id": current_user,
        "specs": specs_data,
        "total_specs": len(specs),
        "data_integrity_summary": {
            "total_specs": len(specs),
            "specs_with_json": sum(1 for s in specs if s.spec_json is not None),
            "specs_with_preview": sum(1 for s in specs if s.preview_url is not None),
            "specs_with_geometry": sum(1 for s in specs if s.geometry_url is not None),
            "all_auditable": True,
        },
    }
