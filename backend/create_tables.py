#!/usr/bin/env python3
"""
Create missing database tables using SQLAlchemy models
"""

from app.database_mongodb import init_db


def create_tables():
    """Initialize database tables"""
    print("Creating database tables...")

    try:
        success = init_db()
        if success:
            print("[SUCCESS] All database tables created successfully!")
        else:
            print("[ERROR] Failed to create some tables")
    except Exception as e:
        print(f"[ERROR] Error creating tables: {e}")


if __name__ == "__main__":
    create_tables()
