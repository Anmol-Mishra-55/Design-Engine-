#!/usr/bin/env python3
"""
Direct test for evaluate endpoint bypassing authentication
"""
import os
import sys

sys.path.append(".")

from app.api.evaluate import save_evaluation_to_file
from app.database_mongodb import get_database
from app.schemas import EvaluateRequest


def test_evaluate_database():
    """Test evaluate endpoint database storage"""
    print("Testing Evaluate Endpoint Database Storage")
    print("=" * 50)

    # Test data
    request = EvaluateRequest(
        spec_id="test_spec_123",
        user_id="test_user_456",
        rating=4,
        notes="Great design, love the layout",
        feedback_text="The kitchen island is perfect",
    )

    print(f"Test Data:")
    print(f"  spec_id: {request.spec_id}")
    print(f"  user_id: {request.user_id}")
    print(f"  rating: {request.rating}")
    print(f"  notes: {request.notes}")
    print("-" * 30)

    # Test 1: Database storage
    try:
        db = next(get_db())

        evaluation = Evaluation(
            spec_id=request.spec_id,
            user_id=request.user_id,
            rating=request.rating,
            notes=request.notes or "",
        )

        db.add(evaluation)
        db.commit()
        eval_id = f"eval_{evaluation.id}"

        print(f"✅ DATABASE: Saved evaluation {eval_id}")
        print(f"   Database ID: {evaluation.id}")

        # Verify it was saved
        saved = db.query(Evaluation).filter(Evaluation.id == evaluation.id).first()
        if saved:
            print(f"✅ VERIFY: Found evaluation in database")
            print(f"   spec_id: {saved.spec_id}")
            print(f"   rating: {saved.rating}")
            print(f"   notes: {saved.notes}")
        else:
            print(f"❌ VERIFY: Evaluation not found in database")

        db.close()

    except Exception as e:
        print(f"❌ DATABASE ERROR: {e}")
        print("Falling back to file storage...")

        # Test 2: File storage fallback
        try:
            eval_id = save_evaluation_to_file(request)
            print(f"✅ FILE STORAGE: Saved evaluation {eval_id}")

            # Check if file exists
            eval_file = f"data/evaluations/{eval_id}.json"
            if os.path.exists(eval_file):
                print(f"✅ FILE VERIFY: Found {eval_file}")
                with open(eval_file, "r") as f:
                    import json

                    data = json.load(f)
                    print(f"   rating: {data['rating']}")
                    print(f"   notes: {data['notes']}")
            else:
                print(f"❌ FILE VERIFY: {eval_file} not found")

        except Exception as e2:
            print(f"❌ FILE STORAGE ERROR: {e2}")

    print("-" * 50)
    print("Test completed!")


if __name__ == "__main__":
    test_evaluate_database()
