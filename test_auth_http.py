#!/usr/bin/env python3
"""
Test authentication with actual HTTP request
"""
import asyncio
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from app.main import app
from app.config import settings
from app.database_mongodb import connect_to_mongo
from fastapi.testclient import TestClient


async def setup_db():
    """Setup database connection"""
    try:
        await connect_to_mongo(settings.MONGODB_URL, settings.MONGODB_DATABASE)
        print("[OK] Database connected")
    except Exception as e:
        print(f"[ERROR] Database connection failed: {e}")
        raise


def test_login():
    """Test login endpoint"""
    print("=" * 70)
    print("AUTHENTICATION HTTP TEST")
    print("=" * 70)
    print()

    # Setup database
    print("Setting up database...")
    asyncio.run(setup_db())
    print()

    # Create test client
    print("Creating test client...")
    client = TestClient(app)
    print("[OK] Test client created")
    print()

    # Test login
    print("Testing login endpoint...")
    print("  URL: /api/v1/auth/login")
    print("  Method: POST")
    print("  Data: username=admin, password=bhiv2024")
    print()

    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "admin",
            "password": "bhiv2024"
        }
    )

    print(f"Response Status: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"Response Body: {response.text}")
    print()

    if response.status_code == 200:
        print("[SUCCESS] Login successful!")
        data = response.json()
        print(f"  Access Token: {data.get('access_token', 'N/A')[:50]}...")
        print(f"  Token Type: {data.get('token_type', 'N/A')}")
    else:
        print("[FAILED] Login failed!")
        try:
            error_data = response.json()
            print(f"  Error: {error_data}")
        except:
            print(f"  Raw response: {response.text}")

    print()
    print("=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    test_login()
