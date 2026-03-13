#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import get_database


def check_users():
    db = next(get_db())
    users = db.query(User).all()

    print("EXISTING USERS:")
    for user in users:
        print(f"- Username: {user.username}")
        print(f"  ID: {user.id}")
        print(f"  Email: {user.email}")
        print()


if __name__ == "__main__":
    check_users()
