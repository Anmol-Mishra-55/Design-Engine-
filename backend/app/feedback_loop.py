"""
Feedback loop integration - Mock implementation
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class FeedbackLoopOrchestrator:
    """Mock orchestrator for feedback collection"""

    def __init__(self, db=None):
        self.db = db
        self.min_feedback_pairs = 10

    def collect_user_feedback(self, user_id: str, spec_id: str, rating: float, notes: str) -> dict:
        """Mock feedback collection"""
        logger.info(f"Mock: Collecting feedback from {user_id} for spec {spec_id}: rating={rating}")

        return {"feedback_id": "mock_feedback_123", "pairs_created": 1, "spec_id": spec_id, "user_id": user_id}

    def aggregate_feedback(self, lookback_hours: int = 24) -> dict:
        """Mock feedback aggregation"""
        return {
            "total_feedback": 5,
            "average_rating": 4.2,
            "evaluation_count": 3,
            "feedback_count": 2,
            "feedback_distribution": {"explicit": 2, "implicit": 0},
            "lookback_hours": lookback_hours,
            "cutoff_time": datetime.now(timezone.utc).isoformat(),
        }

    def should_trigger_training(self) -> Tuple[bool, dict]:
        """Mock training trigger check"""
        stats = {
            "total_feedback_records": 5,
            "min_required": self.min_feedback_pairs,
            "ready_for_training": False,
        }
        return False, stats

    def create_training_dataset(self, limit: Optional[int] = None) -> List[dict]:
        """Mock training dataset creation"""
        return []

    def get_feedback_quality_metrics(self) -> dict:
        """Mock quality metrics"""
        return {
            "total_evaluations": 5,
            "total_feedback": 3,
            "evals_with_notes": 2,
            "explicit_feedback": 1,
            "avg_notes_rate": 0.4,
            "rating_distribution": {4: 2, 5: 3},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class IterativeFeedbackCycle:
    """Mock iterative feedback cycle"""

    def __init__(self, db=None):
        self.db = db
        self.orchestrator = FeedbackLoopOrchestrator(db)

    async def process_evaluation_feedback(self, user_id: str, spec_id: str, rating: float, notes: str) -> dict:
        """Mock feedback processing"""
        feedback_result = self.orchestrator.collect_user_feedback(user_id, spec_id, rating, notes)
        should_train, train_stats = self.orchestrator.should_trigger_training()

        return {
            "feedback_collected": feedback_result,
            "training_triggered": should_train,
            "training_stats": train_stats,
            "training_queued": False,
            "dataset_size": 0,
        }

    def get_cycle_status(self) -> dict:
        """Mock cycle status"""
        stats = self.orchestrator.aggregate_feedback()
        should_train, train_stats = self.orchestrator.should_trigger_training()
        quality = self.orchestrator.get_feedback_quality_metrics()

        return {
            "cycle_status": "collecting_feedback",
            "feedback_stats": stats,
            "training_readiness": train_stats,
            "quality_metrics": quality,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
