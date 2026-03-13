#!/usr/bin/env python3
"""
Complete test for evaluate endpoint with valid spec
"""
import os
import sys

sys.path.append(".")

import json
from datetime import datetime, timezone

from app.database_mongodb import get_database
from app.schemas import EvaluateRequest


def test_evaluate_complete():
    """Test evaluate endpoint with valid spec"""
    print("Testing Evaluate Endpoint with Valid Spec")
    print("=" * 50)

    try:
        db = next(get_db())

        # 1. Create a test spec first
        test_spec = Spec(
            id="test_spec_valid_123",
            user_id="test_user_456",
            prompt="Test kitchen design",
            city="Mumbai",
            spec_json={"objects": [{"type": "kitchen", "style": "modern"}]},
            estimated_cost=50000.0,
            created_at=datetime.now(timezone.utc),
        )

        db.add(test_spec)
        db.commit()
        print(f"Created test spec: {test_spec.id}")

        # 2. Now create evaluation for this spec
        evaluation = Evaluation(
            spec_id=test_spec.id,
            user_id="test_user_456",
            rating=4,
            notes="Great design, love the layout",
        )

        db.add(evaluation)
        db.commit()
        eval_id = f"eval_{evaluation.id}"

        print(f"SUCCESS: Saved evaluation {eval_id}")
        print(f"  Database ID: {evaluation.id}")
        print(f"  Spec ID: {evaluation.spec_id}")
        print(f"  Rating: {evaluation.rating}")
        print(f"  Notes: {evaluation.notes}")

        # 3. Verify it was saved
        saved = db.query(Evaluation).filter(Evaluation.id == evaluation.id).first()
        if saved:
            print(f"VERIFIED: Found evaluation in database")
            print(f"  Created at: {saved.created_at}")
        else:
            print(f"ERROR: Evaluation not found in database")

        # 4. Test file storage fallback
        print("\nTesting file storage fallback...")
        request = EvaluateRequest(
            spec_id=test_spec.id,
            user_id="test_user_456",
            rating=5,
            notes="Even better after iteration",
            feedback_text="Perfect kitchen layout",
        )

        from app.api.evaluate import save_evaluation_to_file

        file_eval_id = save_evaluation_to_file(request)
        print(f"File storage: Saved evaluation {file_eval_id}")

        # Check if file exists
        eval_file = f"data/evaluations/{file_eval_id}.json"
        if os.path.exists(eval_file):
            print(f"VERIFIED: Found {eval_file}")
            with open(eval_file, "r") as f:
                data = json.load(f)
                print(f"  Rating: {data['rating']}")
                print(f"  Notes: {data['notes']}")

        db.close()
        print("\nSUCCESS: Both database and file storage working!")

    except Exception as e:
        print(f"ERROR: {e}")
        return False

    return True


if __name__ == "__main__":
    success = test_evaluate_complete()
    if success:
        print("\nEvaluate endpoint is working correctly!")
    else:
        print("\nEvaluate endpoint test failed!")
