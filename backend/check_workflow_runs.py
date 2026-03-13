#!/usr/bin/env python3
"""
Check workflow_runs table for automation data
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import SessionLocal


def check_workflow_runs():
    db = SessionLocal()
    try:
        # Check workflow_runs table structure
        result = db.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'workflow_runs' ORDER BY ordinal_position"
            )
        )
        columns = result.fetchall()

        print("=== WORKFLOW_RUNS TABLE STRUCTURE ===")
        for col in columns:
            print(f"  {col[0]} - {col[1]}")

        # Check recent entries
        result = db.execute(text("SELECT COUNT(*) FROM workflow_runs"))
        total_count = result.fetchone()[0]
        print(f"\nTotal workflow runs: {total_count}")

        if total_count > 0:
            # Get recent entries
            result = db.execute(text("SELECT * FROM workflow_runs ORDER BY created_at DESC LIMIT 5"))
            recent_runs = result.fetchall()

            print(f"\n=== RECENT WORKFLOW RUNS ===")
            for run in recent_runs:
                print(f"ID: {run[0]}")
                print(f"Workflow Type: {run[1] if len(run) > 1 else 'N/A'}")
                print(f"Status: {run[2] if len(run) > 2 else 'N/A'}")
                print(f"Created: {run[-1] if len(run) > 1 else 'N/A'}")
                print("---")
        else:
            print("No workflow runs found")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    check_workflow_runs()
