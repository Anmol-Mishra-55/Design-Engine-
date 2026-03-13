#!/usr/bin/env python3

import sys

sys.path.insert(0, ".")

from app.database_mongodb import engine


def check_specs_count():
    """Check actual specs count in database"""

    print("=== SPECS COUNT VERIFICATION ===")

    with engine.connect() as conn:
        # Count all specs
        result = conn.execute(text("SELECT COUNT(*) FROM specs"))
        total_count = result.fetchone()[0]
        print(f"Total specs in database: {total_count}")

        # Show first 10 specs with details
        result = conn.execute(
            text(
                """
            SELECT spec_id, user_id, prompt, created_at
            FROM specs
            ORDER BY created_at DESC
            LIMIT 10
        """
            )
        )

        print(f"\nFirst 10 specs:")
        for row in result.fetchall():
            spec_id, user_id, prompt, created_at = row
            print(f"  {spec_id} | {user_id} | {prompt[:50]}... | {created_at}")

        # Check if there are pagination issues
        result = conn.execute(
            text(
                """
            SELECT COUNT(*) as count, user_id
            FROM specs
            GROUP BY user_id
            ORDER BY count DESC
        """
            )
        )

        print(f"\nSpecs by user:")
        for row in result.fetchall():
            count, user_id = row
            print(f"  {user_id}: {count} specs")


if __name__ == "__main__":
    check_specs_count()
