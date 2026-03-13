#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import get_database
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_admin_user():
    db = next(get_db())

    existing = db.query(User).filter(User.username == "admin").first()
    if existing:
        print("Admin user already exists")
        return

    hashed_password = pwd_context.hash("bhiv2024")

    new_user = User(
        id="admin",
        username="admin",
        email="admin@bhiv.com",
        password_hash=hashed_password,
        is_admin=True,
        is_active=True,
    )

    db.add(new_user)
    db.commit()
    print("Created admin user: admin / bhiv2024")


if __name__ == "__main__":
    create_admin_user()
