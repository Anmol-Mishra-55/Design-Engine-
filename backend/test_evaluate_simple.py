#!/usr/bin/env python3
"""
Simple test for evaluate endpoint using existing data
"""
import os
import sys

sys.path.append(".")

import json
from datetime import datetime, timezone

from app.database_mongodb import get_database


def test_evaluate_simple():
    """Test evaluate endpoint with existing or created data"""
    print("Testing Evaluate Endpoint")
    print("=" * 40)

    try:
        db = next(get_db())

        # 1. Find or create a user
        user = db.query(User).first()
        if not user:
            user = User(
                id="test_user_456",
                username="testuser",
                email="test@example.com",
                password_hash="dummy_hash",
                created_at=datetime.now(timezone.utc),
            )
            db.add(user)
            db.commit()
            print(f"Created test user: {user.id}")
        else:
            print(f"Using existing user: {user.id}")

        # 2. Find or create a spec
        spec = db.query(Spec).filter(Spec.user_id == user.id).first()
        if not spec:
            spec = Spec(
                id="test_spec_456",
                user_id=user.id,
                prompt="Test kitchen design",
                city="Mumbai",
                spec_json={"objects": [{"type": "kitchen", "style": "modern"}]},
                estimated_cost=50000.0,
                created_at=datetime.now(timezone.utc),
            )
            db.add(spec)
            db.commit()
            print(f"Created test spec: {spec.id}")
        else:
            print(f"Using existing spec: {spec.id}")

        # 3. Create evaluation
        evaluation = Evaluation(
            spec_id=spec.id,
            user_id=user.id,
            rating=4.5,
            notes="Great design, love the layout",
        )

        db.add(evaluation)
        db.commit()
        eval_id = f"eval_{evaluation.id}"

        print(f"SUCCESS: Saved evaluation {eval_id}")
        print(f"  Database ID: {evaluation.id}")
        print(f"  Spec ID: {evaluation.spec_id}")
        print(f"  User ID: {evaluation.user_id}")
        print(f"  Rating: {evaluation.rating}")
        print(f"  Notes: {evaluation.notes}")
        print(f"  Created: {evaluation.created_at}")

        # 4. Verify it exists
        saved = db.query(Evaluation).filter(Evaluation.id == evaluation.id).first()
        if saved:
            print(f"VERIFIED: Evaluation found in database")
        else:
            print(f"ERROR: Evaluation not found")

        # 5. Test file storage
        print("\nTesting file storage...")
        from app.api.evaluate import save_evaluation_to_file
        from app.schemas import EvaluateRequest

        request = EvaluateRequest(
            spec_id=spec.id, user_id=user.id, rating=5, notes="File storage test", feedback_text="Testing fallback"
        )

        file_eval_id = save_evaluation_to_file(request)
        print(f"File storage: {file_eval_id}")

        eval_file = f"data/evaluations/{file_eval_id}.json"
        if os.path.exists(eval_file):
            print(f"VERIFIED: File {eval_file} exists")

        db.close()
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        return False


if __name__ == "__main__":
    success = test_evaluate_simple()
    if success:
        print("\nSUCCESS: Evaluate endpoint working!")
    else:
        print("\nFAILED: Evaluate endpoint test failed")
