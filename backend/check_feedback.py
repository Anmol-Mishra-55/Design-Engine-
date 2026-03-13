#!/usr/bin/env python3
"""
Verify BHIV Feedback Storage
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import SessionLocal


def check_feedback_storage():
    db = SessionLocal()
    try:
        # Get latest feedback entries
        evaluations = db.query(Evaluation).order_by(Evaluation.created_at.desc()).limit(5).all()

        print("=== RECENT FEEDBACK ENTRIES ===")
        for eval in evaluations:
            print(f"ID: {eval.id}")
            print(f"Spec ID: {eval.spec_id}")
            print(f"User ID: {eval.user_id}")
            print(f"Rating: {eval.rating}")
            print(f"Notes: {eval.notes}")
            print(f"Aspects: {eval.aspects}")
            print(f"Created: {eval.created_at}")
            print("---")

        print(f"Total feedback entries: {db.query(Evaluation).count()}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    check_feedback_storage()
