#!/usr/bin/env python3
"""
Complete test for history endpoint
"""
import sys

sys.path.append(".")

import uuid
from datetime import datetime, timezone

from app.database_mongodb import get_database


def test_history_complete():
    """Test history endpoint with real data"""
    print("Testing History Endpoint")
    print("=" * 40)

    db = next(get_db())

    # 1. Check existing data
    spec = db.query(Spec).filter(Spec.id == "spec_2810cc7fe9b6").first()
    if not spec:
        print("Spec not found")
        return False

    print(f"Spec: {spec.id}, Version: {spec.version}")

    # 2. Create test iteration
    iteration = Iteration(
        id=f"iter_{uuid.uuid4().hex[:8]}",
        spec_id=spec.id,
        user_id=spec.user_id,
        query="Test iteration for history",
        nlp_confidence=0.9,
        diff={"test": "data"},
        spec_json=spec.spec_json,
        changed_objects="foundation,walls",
        preview_url="https://test.glb",
        cost_delta=5000.0,
        new_total_cost=50000.0,
        processing_time_ms=1000,
        created_at=datetime.now(timezone.utc),
    )

    db.add(iteration)

    # 3. Create test evaluation
    evaluation = Evaluation(
        spec_id=spec.id,
        user_id=spec.user_id,
        rating=4.2,
        notes="Test evaluation for history",
        created_at=datetime.now(timezone.utc),
    )

    db.add(evaluation)
    db.commit()

    print(f"Created iteration: {iteration.id}")
    print(f"Created evaluation: {evaluation.id}")

    # 4. Verify data exists
    iterations = db.query(Iteration).filter(Iteration.spec_id == spec.id).all()
    evaluations = db.query(Evaluation).filter(Evaluation.spec_id == spec.id).all()

    print(f"Total iterations for spec: {len(iterations)}")
    print(f"Total evaluations for spec: {len(evaluations)}")

    for iter in iterations:
        print(f"  Iteration: {iter.id} - {iter.query}")

    for eval in evaluations:
        print(f"  Evaluation: {eval.id} - Rating: {eval.rating}")

    db.close()
    return True


if __name__ == "__main__":
    success = test_history_complete()
    if success:
        print("\nHistory test data created successfully!")
    else:
        print("\nHistory test failed!")
