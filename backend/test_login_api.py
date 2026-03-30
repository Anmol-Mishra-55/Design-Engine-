#!/usr/bin/env python3
"""
Test login via API
"""
import json

import requests


def test_login():
    url = "http://localhost:8000/api/v1/auth/login"

    data = {
        "grant_type": "password",
        "username": "admin",
        "password": "bhiv2024",
        "scope": "",
        "client_id": "",
        "client_secret": "",
    }

    headers = {"accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}

    print("Testing login...")
    print(f"URL: {url}")
    print(f"Username: {data['username']}")
    print(f"Password: {data['password']}")
    print()

    try:
        response = requests.post(url, data=data, headers=headers)

        print(f"Status Code: {response.status_code}")
        print()

        if response.status_code == 200:
            result = response.json()
            print("[SUCCESS] Login successful!")
            print(f"Access Token: {result.get('access_token', 'N/A')[:50]}...")
            print(f"Token Type: {result.get('token_type', 'N/A')}")
        else:
            print("[FAIL] Login failed")
            print(f"Response: {response.text}")

    except Exception as e:
        print(f"[ERROR] {e}")


if __name__ == "__main__":
    test_login()
