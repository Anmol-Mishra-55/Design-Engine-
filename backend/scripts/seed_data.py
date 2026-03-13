"""
Populate database with initial test data
"""

import json

from app.database_mongodb import SessionLocal


def seed_database():
    db = SessionLocal()

    try:
        # Create demo users
        demo_user = User(email="demo@example.com", hashed_password="$2b$12$...")  # Hash: demo123

        admin_user = User(email="admin@example.com", hashed_password="$2b$12$...")  # Hash: admin123

        db.add(demo_user)
        db.add(admin_user)
        db.commit()

        # Create sample spec
        sample_spec = Spec(
            spec_id="spec_sample_001",
            user_id="demo@example.com",
            project_id="project_001",
            prompt="Modern living room with marble floor",
            spec_json={
                "version": "1.0",
                "objects": [
                    {"id": "floor_001", "type": "floor", "material": "wood_oak", "color_hex": "#8B4513"},
                    {"id": "sofa_001", "type": "furniture", "material": "fabric", "color_hex": "#808080"},
                ],
                "style": "modern",
            },
        )

        db.add(sample_spec)
        db.commit()

        print("Database seeded successfully")

    except Exception as e:
        db.rollback()
        print(f"Seeding failed: {str(e)}")

    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
