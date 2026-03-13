#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import SessionLocal


def check_user_data():
    db = SessionLocal()
    try:
        user_id = "53ad6295-a001-45ed-8613-67725ba8879d"

        # Check if user still exists
        user = db.query(User).filter(User.id == user_id).first()
        print(f"User exists: {user is not None}")

        # Check user's data
        specs = db.query(Spec).filter(Spec.user_id == user_id).count()
        evaluations = db.query(Evaluation).filter(Evaluation.user_id == user_id).count()
        iterations = db.query(Iteration).join(Spec).filter(Spec.user_id == user_id).count()
        rl_feedback = db.query(RLFeedback).filter(RLFeedback.user_id == user_id).count()

        print(f"Specs: {specs}")
        print(f"Evaluations: {evaluations}")
        print(f"Iterations: {iterations}")
        print(f"RL Feedback: {rl_feedback}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    check_user_data()
