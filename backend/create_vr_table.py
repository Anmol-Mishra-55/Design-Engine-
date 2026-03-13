#!/usr/bin/env python3
"""
Create VR Render table in database
"""
import os
import sys
from pathlib import Path

# Add app to path
sys.path.append(str(Path(__file__).parent))

from app.database_mongodb import engine


def create_vr_table():
    """Create VR render table"""
    try:
        # Create the table
        VRRender.__table__.create(engine, checkfirst=True)
        print("VR render table created successfully")

    except Exception as e:
        print(f"Error creating VR table: {e}")
        return False

    return True


if __name__ == "__main__":
    success = create_vr_table()
    sys.exit(0 if success else 1)
