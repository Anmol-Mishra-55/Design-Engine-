"""
Create database tables for evaluations
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def create_tables():
    try:
        from app.database_mongodb import engine, init_db

        print("Creating database tables...")

        # Create all tables
        Base.metadata.create_all(bind=engine)
        print("Tables created successfully")

        # Test connection
        from app.database_mongodb import get_database_context

        with get_db_context() as db:
            # Check if tables exist
            try:
                eval_count = db.query(Evaluation).count()
                print(f"Evaluations table working: {eval_count} records")
            except Exception as e:
                print(f"Evaluations table issue: {e}")

        return True

    except Exception as e:
        print(f"Table creation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = create_tables()
    print(f"Result: {'SUCCESS' if success else 'FAILED'}")
