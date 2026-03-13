import time

import requests

BASE = "http://localhost:8000"

# Login
r = requests.post(f"{BASE}/api/v1/auth/login", data={"username": "admin", "password": "bhiv2024"})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Generate
print("Creating spec...")
r = requests.post(
    f"{BASE}/api/v1/generate", json={"user_id": "admin", "prompt": "Design a test room for validation"}, headers=headers
)
print(f"Generate status: {r.status_code}")

if r.status_code == 201:
    spec_id = r.json()["spec_id"]
    print(f"Spec ID: {spec_id}")

    # Wait for DB
    time.sleep(1)

    # Check if in DB
    from app.database_mongodb import SessionLocal

    db = SessionLocal()
    spec = db.query(Spec).filter(Spec.id == spec_id).first()
    db.close()

    if spec:
        print(f"PASS - Spec {spec_id} found in DB with user_id: {spec.user_id}")

        # Test reports
        r = requests.get(f"{BASE}/api/v1/reports/{spec_id}", headers=headers)
        print(f"Reports status: {r.status_code} {'PASS' if r.status_code == 200 else 'FAIL'}")

        # Test RL feedback
        r = requests.post(
            f"{BASE}/api/v1/rl/feedback",
            json={"design_a_id": spec_id, "design_b_id": spec_id, "preference": "A", "rating_a": 4, "rating_b": 3},
            headers=headers,
        )
        print(f"RL Feedback status: {r.status_code} {'PASS' if r.status_code == 200 else 'FAIL'}")
    else:
        print(f"FAIL - Spec {spec_id} NOT in DB")
else:
    print(f"Generate failed: {r.text}")
