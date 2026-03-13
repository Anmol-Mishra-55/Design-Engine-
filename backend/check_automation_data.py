#!/usr/bin/env python3
"""
Check for automation and PDF compliance data
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import SessionLocal


def check_automation_data():
    db = SessionLocal()
    try:
        # Check if there are any automation-related tables
        result = db.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%automation%' OR name LIKE '%pdf%' OR name LIKE '%compliance%'"
            )
        )
        tables = result.fetchall()

        print("=== AUTOMATION/PDF RELATED TABLES ===")
        if tables:
            for table in tables:
                print(f"Table: {table[0]}")
        else:
            print("No automation/PDF specific tables found")

        # Check recent activity in logs
        print("\n=== CHECKING FOR RECENT AUTOMATION ACTIVITY ===")

        # Check if there are any workflow or automation entries in existing tables
        try:
            result = db.execute(
                text("SELECT COUNT(*) FROM specs WHERE prompt LIKE '%pdf%' OR prompt LIKE '%automation%'")
            )
            pdf_specs = result.fetchone()[0]
            print(f"Specs with PDF/automation keywords: {pdf_specs}")
        except Exception as e:
            print(f"Could not check specs: {e}")

        # Check for any recent entries
        try:
            result = db.execute(text("SELECT id, prompt, created_at FROM specs ORDER BY created_at DESC LIMIT 3"))
            recent_specs = result.fetchall()
            print(f"\nRecent specs:")
            for spec in recent_specs:
                print(f"  {spec[0]} - {spec[1][:50]}... - {spec[2]}")
        except Exception as e:
            print(f"Could not check recent specs: {e}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    check_automation_data()
