from app.api.evaluate import evaluate

# from app.api.generate import generate  # Avoid circular import
from app.api.iterate import iterate

# from app.api.switch import switch  # Avoid circular import
from app.auth_mongodb import get_current_user, get_db
from app.schemas import EvaluateRequest, GenerateRequest, IterateRequest, SwitchRequest
from fastapi import APIRouter, Depends

router = APIRouter()


@router.post("/mobile/generate")
async def mobile_generate(
    req: GenerateRequest,
    current_user: str = Depends(get_current_user),
):
    """Mobile wrapper for generate endpoint"""
    # Import locally to avoid circular dependency
    from app.api.generate import generate_design

    return await generate_design(req)


@router.post("/mobile/evaluate")
async def mobile_evaluate(
    req: EvaluateRequest,
    current_user: str = Depends(get_current_user),
):
    """Mobile wrapper for evaluate endpoint"""
    return await evaluate(req, current_user, db)


@router.post("/mobile/iterate")
async def mobile_iterate(
    req: IterateRequest,
    current_user: str = Depends(get_current_user),
):
    """Mobile wrapper for iterate endpoint"""
    return await iterate(req, current_user, db)


@router.post("/mobile/switch")
async def mobile_switch(
    req: SwitchRequest,
    current_user: str = Depends(get_current_user),
):
    """Mobile wrapper for switch endpoint - converts to query format"""
    from app.api.switch import SwitchRequest as SwitchReq
    from app.api.switch import switch_material

    # Convert target/update format to natural language query
    target = req.target.object_id or req.target.object_query or "object"

    query_parts = [f"change {target}"]

    if req.update.material:
        query_parts.append(f"material to {req.update.material}")
    if req.update.color_hex:
        query_parts.append(f"color to {req.update.color_hex}")

    query = " ".join(query_parts)

    # Create request with query format
    switch_req = SwitchReq(spec_id=req.spec_id, query=query)
    return await switch_material(switch_req, db)


@router.get("/mobile/health")
async def mobile_health():
    """Mobile-specific health check"""
    return {"status": "ok", "platform": "mobile", "api_version": "v1"}
