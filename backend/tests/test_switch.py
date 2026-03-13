"""
Test cases for POST /api/v1/switch endpoint
"""

import pytest


def test_switch_valid_material(client, auth_headers):
    """Test switching material on existing spec"""
    # First generate a spec
    gen_response = client.post(
        "/api/v1/generate",
        json={"user_id": "demo_user_123", "prompt": "Design a modern living room", "project_id": "project_001"},
        headers=auth_headers,
    )
    assert gen_response.status_code == 200
    spec_id = gen_response.json()["spec_id"]

    # Now switch material
    response = client.post(
        "/api/v1/switch",
        json={
            "user_id": "demo_user_123",
            "spec_id": spec_id,
            "target": {"object_id": "floor_1"},
            "update": {"material": "marble_white", "color_hex": "#FFFFFF"},
            "note": "Change to white marble",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "spec_id" in data
    assert "iteration_id" in data
    assert "updated_spec_json" in data
    assert "changed" in data
    assert "saved_at" in data


def test_switch_nonexistent_spec(client, auth_headers):
    """Test switching on non-existent spec"""
    response = client.post(
        "/api/v1/switch",
        json={
            "user_id": "demo_user_123",
            "spec_id": "nonexistent_spec",
            "target": {"object_id": "floor_1"},
            "update": {"material": "marble"},
        },
        headers=auth_headers,
    )

    assert response.status_code == 404
    data = response.json()
    assert "error" in data


def test_switch_invalid_object_id(client, auth_headers):
    """Test switching invalid object ID"""
    # Generate spec
    gen_response = client.post(
        "/api/v1/generate",
        json={"user_id": "demo_user_123", "prompt": "Design a room", "project_id": "project_001"},
        headers=auth_headers,
    )
    assert gen_response.status_code == 200
    spec_id = gen_response.json()["spec_id"]

    # Try to switch non-existent object
    response = client.post(
        "/api/v1/switch",
        json={
            "user_id": "demo_user_123",
            "spec_id": spec_id,
            "target": {"object_id": "invalid_object_999"},
            "update": {"material": "marble"},
        },
        headers=auth_headers,
    )

    assert response.status_code == 400
    data = response.json()
    assert "error" in data


def test_switch_missing_target(client, auth_headers, test_db, sample_spec_data):
    """Test switch without target specification"""
    spec = Spec(
        spec_id="test_spec_003",
        user_id="demo_user_123",
        prompt="Test room",
        project_id="project_001",
        spec_json=sample_spec_data,
    )
    test_db.add(spec)
    test_db.commit()

    response = client.post(
        "/api/v1/switch",
        json={"user_id": "demo_user_123", "spec_id": "test_spec_003", "update": {"material": "marble"}},
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_switch_missing_update(client, auth_headers, test_db, sample_spec_data):
    """Test switch without update specification"""
    spec = Spec(
        spec_id="test_spec_004",
        user_id="demo_user_123",
        prompt="Test room",
        project_id="project_001",
        spec_json=sample_spec_data,
    )
    test_db.add(spec)
    test_db.commit()

    response = client.post(
        "/api/v1/switch",
        json={"user_id": "demo_user_123", "spec_id": "test_spec_004", "target": {"object_id": "floor_001"}},
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_switch_without_auth(client):
    """Test switch without authentication"""
    response = client.post(
        "/api/v1/switch",
        json={
            "user_id": "demo_user_123",
            "spec_id": "test_spec_001",
            "target": {"object_id": "floor_1"},
            "update": {"material": "marble"},
        },
    )

    assert response.status_code in [401, 403]


def test_switch_creates_iteration(client, auth_headers):
    """Test that switch creates iteration record"""
    # Generate spec
    gen_response = client.post(
        "/api/v1/generate",
        json={"user_id": "demo_user_123", "prompt": "Design a room", "project_id": "project_001"},
        headers=auth_headers,
    )
    assert gen_response.status_code == 200
    spec_id = gen_response.json()["spec_id"]

    # Switch material
    response = client.post(
        "/api/v1/switch",
        json={
            "user_id": "demo_user_123",
            "spec_id": spec_id,
            "target": {"object_id": "sofa_1"},
            "update": {"material": "leather_brown"},
            "note": "Switch to leather",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "iteration_id" in data


def test_switch_multiple_properties(client, auth_headers):
    """Test switching multiple properties at once"""
    # Generate spec
    gen_response = client.post(
        "/api/v1/generate",
        json={"user_id": "demo_user_123", "prompt": "Design a room with table", "project_id": "project_001"},
        headers=auth_headers,
    )
    assert gen_response.status_code == 200
    spec_id = gen_response.json()["spec_id"]

    response = client.post(
        "/api/v1/switch",
        json={
            "user_id": "demo_user_123",
            "spec_id": spec_id,
            "target": {"object_id": "sofa_1"},
            "update": {"material": "glass", "color_hex": "#CCCCCC"},
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "updated_spec_json" in data
    assert "changed" in data
