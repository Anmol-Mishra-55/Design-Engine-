#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import get_database
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_test_user():
    db = next(get_db())

    # Check if admin user exists
    existing = db.query(User).filter(User.username == "admin").first()
    if existing:
        print("Admin user already exists")
        return

    # Create admin user
    hashed_password = pwd_context.hash("admin123")

    new_user = User(
        id="admin",
        username="admin",
        email="admin@example.com",
        password_hash=hashed_password,
        is_admin=True,
        is_active=True,
    )

    db.add(new_user)
    db.commit()
    print("Created admin user: admin / admin123")


if __name__ == "__main__":
    create_test_user()
