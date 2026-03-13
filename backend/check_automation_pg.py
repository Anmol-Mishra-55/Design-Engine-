#!/usr/bin/env python3
"""
Check for automation and PDF compliance data (PostgreSQL)
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import SessionLocal


def check_automation_data():
    db = SessionLocal()
    try:
        # Check if there are any automation-related tables (PostgreSQL)
        result = db.execute(
            text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND (table_name LIKE '%automation%' OR table_name LIKE '%pdf%' OR table_name LIKE '%compliance%')"
            )
        )
        tables = result.fetchall()

        print("=== AUTOMATION/PDF RELATED TABLES ===")
        if tables:
            for table in tables:
                print(f"Table: {table[0]}")
        else:
            print("No automation/PDF specific tables found")

        # Check recent activity
        print("\n=== CHECKING FOR RECENT AUTOMATION ACTIVITY ===")

        # Check if there are any workflow or automation entries in existing tables
        try:
            result = db.execute(
                text("SELECT COUNT(*) FROM specs WHERE prompt ILIKE '%pdf%' OR prompt ILIKE '%automation%'")
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

        # Check all tables to see what exists
        print(f"\n=== ALL TABLES IN DATABASE ===")
        result = db.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
        )
        all_tables = result.fetchall()
        for table in all_tables:
            print(f"  {table[0]}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    check_automation_data()
