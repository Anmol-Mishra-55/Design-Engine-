#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import SessionLocal


def check_database_data():
    db = SessionLocal()
    try:
        # Check users
        users = db.query(User).all()
        print("=== USERS IN DATABASE ===")
        for user in users:
            print(f"ID: {user.id}")
            print(f"Username: {user.username}")
            print(f"Email: {user.email}")
            print("---")

        # Check specs
        specs = db.query(Spec).all()
        print(f"\n=== SPECS IN DATABASE ({len(specs)} total) ===")
        for spec in specs[:5]:  # Show first 5
            print(f"ID: {spec.id}")
            print(f"User ID: {spec.user_id}")
            print(f"Prompt: {spec.prompt[:50]}...")
            print(f"City: {spec.city}")
            print(f"Status: {spec.status}")
            print(f"Created: {spec.created_at}")
            print("---")

        if len(specs) > 5:
            print(f"... and {len(specs) - 5} more specs")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    check_database_data()
