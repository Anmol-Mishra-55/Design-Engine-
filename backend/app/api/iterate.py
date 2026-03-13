"""
Iterate endpoint (UPDATED with service and error handling)
"""

import logging

from app.auth_mongodb import get_current_user, get_db
from app.error_handler import APIException
from app.schemas import IterateRequest, IterateResponse
from app.schemas.error_schemas import ErrorCode
from app.services.iterate_service import IterateService
from fastapi import APIRouter, Depends

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/iterate", response_model=IterateResponse)
async def iterate(request: IterateRequest, current_user: str = Depends(get_current_user), db=Depends(get_db)):
    """Iterate and improve a design spec"""

    print(f"🔄 ITERATE REQUEST: user_id={request.user_id}, spec_id={request.spec_id}, strategy={request.strategy}")
    logger.info(f"🔄 ITERATE REQUEST: user_id={request.user_id}, spec_id={request.spec_id}, strategy={request.strategy}")

    try:
        # Validate
        if not request.spec_id:
            raise APIException(status_code=400, error_code=ErrorCode.VALIDATION_ERROR, message="spec_id is required")

        if not request.user_id:
            raise APIException(status_code=400, error_code=ErrorCode.VALIDATION_ERROR, message="user_id is required")

        if not request.strategy:
            raise APIException(
                status_code=400,
                error_code=ErrorCode.VALIDATION_ERROR,
                message="strategy is required",
                details={
                    "valid_strategies": ["auto_optimize", "improve_materials", "improve_layout", "improve_colors"]
                },
            )

        # Delegate to service
        service = IterateService(db)
        result = await service.iterate_spec(request.user_id, request.spec_id, request.strategy)

        logger.info(f"Iterate completed for spec {request.spec_id} with strategy {request.strategy}")

        return IterateResponse(
            before=result["before"],
            after=result["after"],
            feedback=result["feedback"],
            iteration_id=result["iteration_id"],
            preview_url=result["preview_url"],
            spec_version=result["spec_version"],
            training_triggered=result.get("training_triggered", False),
            strategy=result.get("strategy", request.strategy),
        )

    except APIException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in iterate: {str(e)}", exc_info=True)
        raise APIException(
            status_code=500, error_code=ErrorCode.INTERNAL_ERROR, message="Unexpected error during iteration"
        )
