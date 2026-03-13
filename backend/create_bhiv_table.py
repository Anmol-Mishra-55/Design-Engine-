#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import engine


def create_bhiv_table():
    """Create BHIVActivation table"""
    try:
        BHIVActivation.__table__.create(engine, checkfirst=True)
        print("BHIVActivation table created successfully")
    except Exception as e:
        print(f"Error creating table: {e}")


if __name__ == "__main__":
    create_bhiv_table()
