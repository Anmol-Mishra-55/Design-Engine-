from app.api.evaluate import evaluate
from app.api.iterate import iterate
from app.auth_mongodb import get_current_user, get_db
from app.schemas import EvaluateRequest, GenerateRequest, IterateRequest, SwitchRequest
from fastapi import APIRouter, Depends, HTTPException, Request

router = APIRouter()


@router.post("/mobile/generate")
async def mobile_generate(
    req: GenerateRequest,
    request: Request,
    current_user: str = Depends(get_current_user),
):
    """Mobile wrapper — routes through Core only."""
    from app.api.core_entry import core_generate

    return await core_generate(req, request, current_user)


@router.post("/mobile/evaluate")
async def mobile_evaluate(
    req: EvaluateRequest,
    current_user: str = Depends(get_current_user),
):
    """Mobile wrapper for evaluate endpoint"""
    return await evaluate(req, current_user)


@router.post("/mobile/iterate")
async def mobile_iterate(
    req: IterateRequest,
    current_user: str = Depends(get_current_user),
    db=Depends(get_db),
):
    """Mobile wrapper for iterate endpoint"""
    return await iterate(req, current_user, db)


@router.post("/mobile/switch")
async def mobile_switch(
    req: SwitchRequest,
    current_user: str = Depends(get_current_user),
    db=Depends(get_db),
):
    """Mobile wrapper for switch endpoint"""
    from app.api.switch import SwitchRequest as SwitchReq
    from app.api.switch import switch_material

    target = req.target.object_id or req.target.object_query or "object"
    query_parts = [f"change {target}"]
    if req.update.material:
        query_parts.append(f"material to {req.update.material}")
    if req.update.color_hex:
        query_parts.append(f"color to {req.update.color_hex}")
    switch_req = SwitchReq(spec_id=req.spec_id, query=" ".join(query_parts))
    return await switch_material(switch_req, db)


@router.get("/mobile/health")
async def mobile_health():
    """Mobile-specific health check"""
    return {"status": "ok", "platform": "mobile", "api_version": "v1"}
