#!/usr/bin/env python3
"""
Start server and test authentication
"""
import subprocess
import time
import requests
import sys

print("=" * 70)
print("SERVER START AND AUTHENTICATION TEST")
print("=" * 70)
print()

# Kill any existing server
print("Step 1: Killing any existing server processes...")
try:
    subprocess.run(["taskkill", "/F", "/IM", "python.exe", "/FI", "WINDOWTITLE eq *uvicorn*"],
                   capture_output=True, timeout=5)
    time.sleep(2)
    print("[OK] Existing processes killed")
except:
    print("[OK] No existing processes")

print()

# Start the server
print("Step 2: Starting FastAPI server...")
print("  Command: python backend/start_server.py")
print()

server_process = subprocess.Popen(
    [sys.executable, "backend/start_server.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

# Wait for server to start
print("Waiting for server to start...")
max_wait = 30
waited = 0
server_ready = False

while waited < max_wait:
    try:
        response = requests.get("http://localhost:8000/health", timeout=2)
        if response.status_code == 200:
            server_ready = True
            print(f"[OK] Server is ready after {waited} seconds")
            break
    except:
        pass

    time.sleep(1)
    waited += 1
    if waited % 5 == 0:
        print(f"  Still waiting... ({waited}s)")

print()

if not server_ready:
    print("[ERROR] Server failed to start within 30 seconds")
    server_process.kill()
    sys.exit(1)

# Test authentication
print("Step 3: Testing authentication...")
print("  URL: http://localhost:8000/api/v1/auth/login")
print("  Username: admin")
print("  Password: bhiv2024")
print()

try:
    response = requests.post(
        "http://localhost:8000/api/v1/auth/login",
        data={
            "username": "admin",
            "password": "bhiv2024"
        },
        timeout=10
    )

    print(f"Response Status: {response.status_code}")
    print(f"Response Body: {response.text}")
    print()

    if response.status_code == 200:
        print("=" * 70)
        print("[SUCCESS] AUTHENTICATION WORKS!")
        print("=" * 70)
        data = response.json()
        print(f"Access Token: {data.get('access_token', 'N/A')[:50]}...")
        print(f"Token Type: {data.get('token_type', 'N/A')}")
    else:
        print("=" * 70)
        print("[FAILED] AUTHENTICATION FAILED")
        print("=" * 70)
        try:
            error_data = response.json()
            print(f"Error: {error_data}")
        except:
            print(f"Raw response: {response.text}")

except Exception as e:
    print(f"[ERROR] Request failed: {e}")

print()
print("Step 4: Stopping server...")
server_process.kill()
print("[OK] Server stopped")

print()
print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)
