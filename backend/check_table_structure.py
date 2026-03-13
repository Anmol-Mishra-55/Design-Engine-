#!/usr/bin/env python3
"""Check table structures"""

from app.database_mongodb import engine


def check_table_structure(table_name):
    """Check table structure"""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table_name}'")
            )
            columns = result.fetchall()
            print(f"\n{table_name} table structure:")
            for col in columns:
                print(f"  {col[0]}: {col[1]}")
    except Exception as e:
        print(f"Error checking {table_name}: {e}")


def check_workflow_runs_data():
    """Check workflow runs data"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM workflow_runs ORDER BY id DESC LIMIT 3"))
            rows = result.fetchall()
            print(f"\nWorkflow runs data ({len(rows)} found):")
            for row in rows:
                print(f"  Row: {row}")
    except Exception as e:
        print(f"Error checking workflow_runs data: {e}")


def check_specs_data():
    """Check specs data"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM specs ORDER BY id DESC LIMIT 3"))
            rows = result.fetchall()
            print(f"\nSpecs data ({len(rows)} found):")
            for row in rows:
                print(f"  Row: {row}")
    except Exception as e:
        print(f"Error checking specs data: {e}")


if __name__ == "__main__":
    print("Checking table structures and data...")
    check_table_structure("workflow_runs")
    check_table_structure("specs")
    check_workflow_runs_data()
    check_specs_data()
