#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import SessionLocal


def get_real_users():
    db = SessionLocal()
    try:
        users = db.query(User).all()
        if users:
            print("Real users in database:")
            for user in users:
                print(f"ID: {user.id}")
                print(f"Username: {user.username}")
                print(f"Email: {user.email}")
                print("---")
        else:
            print("No users found in database")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    get_real_users()
