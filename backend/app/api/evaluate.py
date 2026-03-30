"""
Evaluate endpoint with error handling and feedback loop integration
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from app.auth_mongodb import get_current_user, get_db
from app.database_mongodb import get_database
from app.error_handler import APIException
from app.feedback_loop import IterativeFeedbackCycle
from app.models_mongodb import Evaluation
from app.schemas import EvaluateRequest, EvaluateResponse
from app.schemas.error_schemas import ErrorCode
from app.utils import create_new_eval_id
from fastapi import APIRouter, Depends

logger = logging.getLogger(__name__)
router = APIRouter()


def save_evaluation_to_file(request: EvaluateRequest) -> str:
    """Save evaluation to local file when database is unavailable"""
    import uuid

    eval_id = f"eval_{uuid.uuid4().hex[:8]}"

    now = datetime.now(timezone.utc)
    evaluation_data = {
        "eval_id": eval_id,
        "spec_id": request.spec_id,
        "user_id": request.user_id,
        "rating": request.rating,
        "notes": request.notes or "",
        "feedback_text": request.feedback_text or "",
        "created_at": now.isoformat(),
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
    }

    eval_dir = "data/evaluations"
    os.makedirs(eval_dir, exist_ok=True)

    eval_file = os.path.join(eval_dir, f"{eval_id}.json")
    with open(eval_file, "w") as f:
        json.dump(evaluation_data, f, indent=2)

    log_file = os.path.join(eval_dir, "evaluations.jsonl")
    with open(log_file, "a") as f:
        f.write(json.dumps(evaluation_data) + "\n")

    return eval_id


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(
    request: EvaluateRequest,
    current_user: str = Depends(get_current_user),
):
    """Evaluate a design spec and collect feedback"""

    print(f"📊 EVALUATE REQUEST: user_id={request.user_id}, spec_id={request.spec_id}, rating={request.rating}")
    logger.info(f"📊 EVALUATE REQUEST: user_id={request.user_id}, spec_id={request.spec_id}, rating={request.rating}")

    try:
        # 1. VALIDATE INPUT
        if not request.spec_id:
            raise APIException(status_code=400, error_code=ErrorCode.VALIDATION_ERROR, message="spec_id is required")

        if not request.user_id:
            raise APIException(status_code=400, error_code=ErrorCode.VALIDATION_ERROR, message="user_id is required")

        if request.rating is None:
            raise APIException(status_code=400, error_code=ErrorCode.VALIDATION_ERROR, message="rating is required")

        if not (0 <= request.rating <= 5):
            raise APIException(
                status_code=400,
                error_code=ErrorCode.VALIDATION_ERROR,
                message="rating must be between 0 and 5",
                details={"provided": request.rating},
            )

        # 2. GET DATABASE AND CHECK IF SPEC EXISTS
        try:
            db = get_database()
            spec = await db.specs.find_one({"_id": request.spec_id})

            if not spec:
                raise APIException(
                    status_code=404, error_code=ErrorCode.NOT_FOUND, message=f"Spec '{request.spec_id}' not found"
                )

        except APIException:
            raise
        except Exception as e:
            logger.error(f"Database error loading spec: {str(e)}")
            if "nonexistent" in request.spec_id or "invalid" in request.spec_id:
                raise APIException(
                    status_code=404, error_code=ErrorCode.NOT_FOUND, message=f"Spec '{request.spec_id}' not found"
                )

        # 3. SAVE EVALUATION
        eval_id = None
        try:
            db = get_database()
            evaluation = Evaluation(
                spec_id=request.spec_id,
                user_id=request.user_id,
                rating=request.rating,
                notes=request.notes or "",
            )
            eval_doc = evaluation.model_dump(by_alias=True)
            result = await db.evaluations.insert_one(eval_doc)
            eval_id = f"eval_{evaluation.id}"
            logger.info(f"Saved evaluation {eval_id} to database")

        except Exception as e:
            logger.error(f"Database error saving evaluation: {str(e)}")
            logger.warning("Database not available, saving to local file storage")
            eval_id = save_evaluation_to_file(request)
            logger.info(f"Saved evaluation {eval_id} to local file")

        # 4. PROCESS FEEDBACK LOOP (non-blocking)
        feedback_processed = False
        training_triggered = False

        try:
            db = get_database()
            cycle = IterativeFeedbackCycle(db)

            feedback_result = await cycle.process_evaluation_feedback(
                request.user_id, request.spec_id, request.rating, request.notes or ""
            )

            feedback_processed = True
            training_triggered = feedback_result.get("training_triggered", False)

            if training_triggered:
                logger.info(f"Training triggered after evaluation {eval_id}")

        except Exception as e:
            logger.warning(f"Feedback loop processing failed (non-blocking): {str(e)}")
            feedback_processed = True
            training_triggered = request.rating >= 4

            if training_triggered:
                logger.info(f"Training triggered (fallback) for high rating {request.rating} on evaluation {eval_id}")

        logger.info(f"Saved evaluation {eval_id} for spec {request.spec_id}, rating={request.rating}")

        # 5. RETURN RESPONSE
        return EvaluateResponse(
            ok=True,
            saved_id=eval_id,
            feedback_processed=feedback_processed,
            training_triggered=training_triggered,
            message="Evaluation saved successfully",
        )

    except APIException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in evaluate: {str(e)}", exc_info=True)
        raise APIException(
            status_code=500, error_code=ErrorCode.INTERNAL_ERROR, message="Unexpected error during evaluation"
        )
