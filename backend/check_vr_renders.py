#!/usr/bin/env python3
"""
Check VR renders in database
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from app.database_mongodb import get_database


def check_vr_renders():
    """Check VR renders in database"""
    db = next(get_db())

    renders = db.query(VRRender).all()

    print(f"VR RENDERS IN DATABASE ({len(renders)} total):")
    for render in renders:
        print(f"- ID: {render.id}")
        print(f"  Spec: {render.spec_id}")
        print(f"  User: {render.user_id}")
        print(f"  Status: {render.status}")
        print(f"  Quality: {render.quality}")
        print(f"  Progress: {render.progress}%")
        print(f"  URL: {render.render_url}")
        print(f"  Local: {render.local_path}")
        print(f"  Size: {render.file_size_bytes} bytes")
        print(f"  Created: {render.created_at}")
        print()


if __name__ == "__main__":
    check_vr_renders()
