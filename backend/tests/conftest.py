"""
Pytest configuration and shared fixtures for all tests
"""

import os
import warnings

import pytest
import warnings_filter  # Must be first import
from app.database_mongodb import Base, get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

# Suppress all warnings
warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"


# Use SQLite in-memory database for tests
SQLALCHEMY_TEST_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def test_engine():
    """Create test database engine"""
    engine = create_engine(
        SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False}, pool_pre_ping=True, pool_recycle=300
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_db(test_engine):
    """Create test database session"""
    # Ensure tables are created for this test session
    Base.metadata.create_all(bind=test_engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = TestingSessionLocal()

    try:
        # Seed with demo user
        demo_user = User(email="demo@test.com", hashed_password="hashed_demo123")
        db.add(demo_user)
        db.commit()

        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture(scope="function")
def client(test_engine):
    """Create test client with overridden database dependency"""
    # Create tables for this test session
    Base.metadata.create_all(bind=test_engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            try:
                db.rollback()
                db.close()
            except:
                pass

    app.dependency_overrides[get_db] = override_get_db

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with TestClient(app) as test_client:
            yield test_client

    app.dependency_overrides.clear()
    try:
        test_engine.dispose()
    except:
        pass


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
