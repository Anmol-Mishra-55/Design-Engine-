#!/usr/bin/env python3
"""Check workflow data in database"""

from app.database_mongodb import engine


def check_tables():
    """Check available tables"""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
        tables = [row[0] for row in result]
        print("Available tables:", tables)
        return tables


def check_workflow_runs():
    """Check workflow runs table"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM workflow_runs ORDER BY created_at DESC LIMIT 5"))
            rows = result.fetchall()
            print(f"\nRecent workflow runs ({len(rows)} found):")
            for row in rows:
                print(f"  ID: {row[0]}, Status: {row[2]}, Created: {row[4]}")
    except Exception as e:
        print(f"Error checking workflow_runs: {e}")


def check_specs():
    """Check specs table"""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT spec_id, user_id, created_at FROM specs ORDER BY created_at DESC LIMIT 5")
            )
            rows = result.fetchall()
            print(f"\nRecent specs ({len(rows)} found):")
            for row in rows:
                print(f"  Spec ID: {row[0]}, User: {row[1]}, Created: {row[2]}")
    except Exception as e:
        print(f"Error checking specs: {e}")


def check_workflow_details():
    """Check workflow runs in detail"""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT workflow_id, flow_run_id, status, parameters, created_at FROM workflow_runs ORDER BY created_at DESC LIMIT 3"
                )
            )
            rows = result.fetchall()
            print(f"\nWorkflow runs details ({len(rows)} found):")
            for row in rows:
                print(f"  Workflow ID: {row[0]}")
                print(f"  Flow Run ID: {row[1]}")
                print(f"  Status: {row[2]}")
                print(f"  Parameters: {row[3]}")
                print(f"  Created: {row[4]}")
                print("  ---")
    except Exception as e:
        print(f"Error checking workflow details: {e}")


if __name__ == "__main__":
    print("Checking database for workflow data...")
    tables = check_tables()
    check_workflow_runs()
    check_workflow_details()
    check_specs()
