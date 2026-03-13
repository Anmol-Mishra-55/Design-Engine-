#!/usr/bin/env python3
"""
Check compliance_checks table for PDF automation data
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import SessionLocal


def check_compliance_table():
    db = SessionLocal()
    try:
        # Check compliance_checks table structure
        result = db.execute(
            text(
                "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'compliance_checks' ORDER BY ordinal_position"
            )
        )
        columns = result.fetchall()

        print("=== COMPLIANCE_CHECKS TABLE STRUCTURE ===")
        for col in columns:
            print(f"  {col[0]} - {col[1]}")

        # Check recent entries
        result = db.execute(text("SELECT COUNT(*) FROM compliance_checks"))
        total_count = result.fetchone()[0]
        print(f"\nTotal compliance checks: {total_count}")

        if total_count > 0:
            # Get recent entries
            result = db.execute(text("SELECT * FROM compliance_checks ORDER BY created_at DESC LIMIT 5"))
            recent_checks = result.fetchall()

            print(f"\n=== RECENT COMPLIANCE CHECKS ===")
            for check in recent_checks:
                print(f"ID: {check[0]}")
                print(f"Created: {check[-1] if len(check) > 1 else 'N/A'}")  # Assuming created_at is last column
                print("---")
        else:
            print("No compliance checks found")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    check_compliance_table()
