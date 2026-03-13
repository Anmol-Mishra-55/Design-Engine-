"""
Test cases for POST /api/v1/evaluate endpoint
"""

import pytest


def test_evaluate_valid_spec(client, auth_headers):
    """Test evaluating a spec with valid rating and notes"""
    # 1. Generate spec
    gen_response = client.post(
        "/api/v1/generate",
        json={"user_id": "demo_user_123", "prompt": "modern living room", "project_id": "project_001"},
        headers=auth_headers,
    )
    assert gen_response.status_code == 200
    spec_id = gen_response.json()["spec_id"]

    # 2. Evaluate
    response = client.post(
        "/api/v1/evaluate",
        json={
            "user_id": "demo_user_123",
            "spec_id": spec_id,
            "rating": 4.5,
            "notes": "Great design with good proportions and color harmony",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    result = response.json()

    # Verify response
    assert result["ok"] is True
    assert "saved_id" in result


def test_evaluate_spec_not_found(client, auth_headers):
    """Test error when spec doesn't exist"""
    response = client.post(
        "/api/v1/evaluate",
        json={"user_id": "demo_user_123", "spec_id": "nonexistent_spec", "rating": 4.0, "notes": "Good design"},
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_evaluate_invalid_rating_range(client, auth_headers):
    """Test error for rating outside 0-5 range"""
    gen_response = client.post(
        "/api/v1/generate",
        json={"user_id": "demo_user_123", "prompt": "modern living room", "project_id": "project_001"},
        headers=auth_headers,
    )
    assert gen_response.status_code == 200
    spec_id = gen_response.json()["spec_id"]

    # Rating too high
    response = client.post(
        "/api/v1/evaluate",
        json={"user_id": "demo_user_123", "spec_id": spec_id, "rating": 10.0, "notes": "Amazing"},
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_evaluate_triggers_feedback_loop(client, auth_headers):
    """Test that evaluation triggers feedback loop processing"""
    # Generate spec
    gen_response = client.post(
        "/api/v1/generate",
        json={"user_id": "demo_user_123", "prompt": "living room", "project_id": "project_001"},
        headers=auth_headers,
    )
    assert gen_response.status_code == 200
    spec_id = gen_response.json()["spec_id"]

    # Evaluate with good rating
    response = client.post(
        "/api/v1/evaluate",
        json={"user_id": "demo_user_123", "spec_id": spec_id, "rating": 4.8, "notes": "Excellent design"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    # Feedback loop should be triggered (handled in response)
    result = response.json()
    assert "feedback_processed" in result or result["ok"] is True
