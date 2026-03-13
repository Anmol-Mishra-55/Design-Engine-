#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import get_database


def check_workflow_runs():
    db = next(get_db())

    try:
        # Check if workflow_runs table exists and has data
        result = db.execute(text("SELECT * FROM workflow_runs LIMIT 5"))
        rows = result.fetchall()

        if rows:
            print("EXISTING WORKFLOW RUNS:")
            for row in rows:
                print(f"- Flow Run ID: {row[0]}")
                print(f"  Status: {row[1]}")
                print(f"  Created: {row[2]}")
                print()
        else:
            print("No workflow runs found in database")

        # Also check table structure
        result = db.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'workflow_runs'")
        )
        columns = result.fetchall()
        print("Table columns:", [col[0] for col in columns])

    except Exception as e:
        print(f"Error checking workflow_runs: {e}")


if __name__ == "__main__":
    check_workflow_runs()
