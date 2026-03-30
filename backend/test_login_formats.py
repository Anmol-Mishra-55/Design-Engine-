#!/usr/bin/env python3
"""
Test what the login endpoint receives
"""
import requests

url = "http://localhost:8000/api/v1/auth/login"

# Test 1: Simple form data
print("Test 1: Simple form data")
print("=" * 70)
data = {"username": "admin", "password": "bhiv2024"}
response = requests.post(url, data=data)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
print()

# Test 2: OAuth2 format (like Swagger UI sends)
print("Test 2: OAuth2 format")
print("=" * 70)
data = {
    "grant_type": "password",
    "username": "admin",
    "password": "bhiv2024",
    "scope": "",
    "client_id": "",
    "client_secret": "",
}
response = requests.post(url, data=data)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
print()

# Test 3: OAuth2 format with client_id and client_secret
print("Test 3: OAuth2 format with client credentials")
print("=" * 70)
data = {
    "grant_type": "password",
    "username": "admin",
    "password": "bhiv2024",
    "scope": "",
    "client_id": "string",
    "client_secret": "string",
}
response = requests.post(url, data=data)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
