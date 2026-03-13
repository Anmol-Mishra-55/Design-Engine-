#!/usr/bin/env python3

import sys

sys.path.insert(0, ".")

from app.database_mongodb import engine


def delete_empty_tables():
    """Delete empty tables from database"""

    print("=== DELETING EMPTY TABLES ===")

    # Tables to delete (empty ones)
    tables_to_delete = ["users", "audit_logs", "rlhf_preferences"]

    with engine.connect() as conn:
        for table in tables_to_delete:
            try:
                # Check if table exists and is empty
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.fetchone()[0]

                if count == 0:
                    # Drop the table
                    conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                    conn.commit()
                    print(f"SUCCESS: Deleted empty table '{table}'")
                else:
                    print(f"SKIP: Table '{table}' has {count} records, not deleting")

            except Exception as e:
                print(f"ERROR: Failed to delete table '{table}': {e}")

    # Verify remaining tables
    print("\n=== REMAINING TABLES ===")
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
            """
                )
            )

            remaining_tables = [row[0] for row in result.fetchall()]
            print(f"Remaining tables: {remaining_tables}")

    except Exception as e:
        print(f"Table check error: {e}")

    print("\n=== DELETION COMPLETE ===")


if __name__ == "__main__":
    delete_empty_tables()
