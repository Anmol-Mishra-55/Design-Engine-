#!/usr/bin/env python3

import sys

sys.path.insert(0, ".")

from app.database_mongodb import get_database


def check_all_tables():
    """Check all database tables and their data"""

    print("=== DATABASE TABLES ANALYSIS ===")

    db = next(get_db())

    # Check all tables
    tables = [
        ("users", User),
        ("specs", Spec),
        ("evaluations", Evaluation),
        ("iterations", Iteration),
        ("audit_logs", AuditLog),
        ("rlhf_feedback", RLHFFeedback),
        ("rlhf_preferences", RLHFPreferences),
    ]

    for table_name, model_class in tables:
        try:
            count = db.query(model_class).count()
            print(f"{table_name}: {count} records")

            if count > 0:
                # Show sample data
                sample = db.query(model_class).first()
                print(f"  Sample: {sample.__dict__}")

        except Exception as e:
            print(f"{table_name}: ERROR - {e}")

    # Check if tables exist in database
    print("\n=== TABLE EXISTENCE CHECK ===")
    try:
        result = db.execute(
            text(
                """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """
            )
        )

        existing_tables = [row[0] for row in result.fetchall()]
        print(f"Existing tables: {existing_tables}")

    except Exception as e:
        print(f"Table check error: {e}")

    db.close()
    print("\n=== ANALYSIS COMPLETE ===")


if __name__ == "__main__":
    check_all_tables()
