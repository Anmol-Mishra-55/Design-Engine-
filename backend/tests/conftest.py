"""
Pytest configuration and shared fixtures for all tests
"""

import os
import warnings

import pytest
import warnings_filter  # Must be first import
from app.main import app
from fastapi.testclient import TestClient

# Suppress all warnings
warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"


@pytest.fixture(scope="function")
def client():
    """Create test client"""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with TestClient(app) as test_client:
            yield test_client


@pytest.fixture(scope="function")
def auth_token(client):
    """Get JWT token for authenticated requests"""
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "demo", "password": "demo123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture(scope="function")
def auth_headers(auth_token):
    """Headers with JWT token for authenticated requests"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="function")
def sample_spec_data():
    """Sample spec data for testing"""
    return {
        "version": "1.0",
        "objects": [
            {
                "id": "floor_1",
                "type": "floor",
                "material": "wood_oak",
                "color_hex": "#8B4513",
                "dimensions": {"width": 5.0, "length": 7.0},
            },
            {
                "id": "sofa_1",
                "type": "furniture",
                "material": "fabric",
                "color_hex": "#808080",
                "dimensions": {"width": 2.5, "depth": 1.0, "height": 0.8},
            },
        ],
        "style": "modern",
        "budget": 50000,
    }
