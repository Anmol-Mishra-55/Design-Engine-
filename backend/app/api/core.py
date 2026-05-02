import logging

logger = logging.getLogger(__name__)
from typing import Any, Dict, List

from app.auth_mongodb import get_current_user, get_db
from app.schemas import EvaluateRequest, GenerateRequest, IterateRequest
from app.schemas.core import CoreRunRequest as OldCoreRunRequest
from pydantic import BaseModel


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
    raise HTTPException(
        status_code=403,
        detail="Forbidden: /core/run is disabled. All requests must go through /api/v1/generate via Core.",
    )


@router.get("/status")
async def core_status(current_user: str = Depends(get_current_user)):
    return {"message": "Core services operational", "user": current_user}
