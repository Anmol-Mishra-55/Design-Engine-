"""
Simple tests without authentication
"""

import pytest


def test_user_model():
    """Test User model creation"""
    user = User(email="test@example.com", hashed_password="hashed123")
    assert user.email == "test@example.com"
    assert user.hashed_password == "hashed123"


def test_spec_model():
    """Test Spec model creation"""
    spec = Spec(spec_id="test_spec_001", user_id="test_user", prompt="test prompt", spec_json={"objects": []})
    assert spec.spec_id == "test_spec_001"
    assert spec.user_id == "test_user"
    assert spec.prompt == "test prompt"


def test_schemas_import():
    """Test that all schemas can be imported"""
    from app.schemas import (
        EvaluateRequest,
        EvaluateResponse,
        GenerateRequest,
        GenerateResponse,
        IterateRequest,
        IterateResponse,
        SwitchRequest,
        SwitchResponse,
    )

    # Test basic schema creation
    gen_req = GenerateRequest(user_id="test", prompt="test prompt")
    assert gen_req.user_id == "test"
    assert gen_req.prompt == "test prompt"
