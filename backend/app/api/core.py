import logging

# Import functions will be called dynamically to avoid circular imports

logger = logging.getLogger(__name__)
from typing import Any, Dict, List

from app.auth_mongodb import get_current_user, get_db
from app.schemas import EvaluateRequest, GenerateRequest, IterateRequest
from app.schemas.core import CoreRunRequest as OldCoreRunRequest
from pydantic import BaseModel


# Use the correct schema for pipeline execution
class CoreRunRequest(BaseModel):
    pipeline: List[str]
    input: Dict[str, Any]


from fastapi import APIRouter, Depends, HTTPException

router = APIRouter()


@router.post("/run")
async def core_run(
    request: CoreRunRequest,
    current_user: str = Depends(get_current_user),
):
    outputs = {}

    try:
        for step in request.pipeline:
            if step == "generate":
                outputs["generate"] = {"message": "Generate step placeholder", "spec_id": "mock_spec_123"}
                request.input["spec_id"] = "mock_spec_123"

            elif step == "evaluate":
                outputs["evaluate"] = {"message": "Evaluate step placeholder", "rating": 4.5}

            elif step == "iterate":
                outputs["iterate"] = {"message": "Iterate step placeholder", "iteration_id": "mock_iter_456"}

            elif step == "store":
                # Store or finalize step (placeholder)
                outputs["store"] = {"ok": True, "message": "Design stored successfully"}

            else:
                raise HTTPException(status_code=400, detail=f"Unknown step: {step}")

        return outputs  # aggregated outputs

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {str(e)}")


@router.get("/status")
async def core_status(current_user: str = Depends(get_current_user)):
    return {"message": "Core services operational", "user": current_user}
