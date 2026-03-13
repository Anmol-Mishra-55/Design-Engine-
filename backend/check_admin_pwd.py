#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import get_database
from app.security import verify_password


def check_admin_password():
    db = next(get_db())
    admin = db.query(User).filter(User.username == "admin").first()

    if admin:
        print(f"Admin user found: {admin.username}")
        print(f"Password hash: {admin.hashed_password}")

        # Test common passwords
        test_passwords = ["admin", "admin123", "password", "password123", "bhiv123"]

        for pwd in test_passwords:
            if verify_password(pwd, admin.hashed_password):
                print(f"SUCCESS: Password is '{pwd}'")
                return pwd

        print("No matching password found from common list")
    else:
        print("Admin user not found")


if __name__ == "__main__":
    check_admin_password()
