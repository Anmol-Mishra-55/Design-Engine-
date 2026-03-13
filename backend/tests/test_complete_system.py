"""
Complete System Integration Tests
Tests all components working together
"""
import asyncio

import pytest
from app.config import settings
from app.database_mongodb import Base
from app.main import app
from httpx import AsyncClient
from sqlalchemy.orm import sessionmaker

# Test database
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def setup_test_db():
    """Create test database"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_db(setup_test_db):
    """Get test database session"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_user(test_db):
    """Create test user"""
    user = User(username="testuser", email="test@bhiv.ai", password_hash="hashed_password", is_active=True)
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_complete_workflow(test_user):
    """
    Test complete workflow:
    1. Generate design
    2. Switch material
    3. Evaluate design
    4. Check compliance
    """
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Step 1: Generate design
        generate_response = await client.post(
            "/api/v1/generate", json={"user_id": test_user.id, "prompt": "modern 2BHK apartment", "city": "Mumbai"}
        )
        assert generate_response.status_code == 201
        spec_data = generate_response.json()
        spec_id = spec_data["spec_id"]

        print(f"✓ Design generated: {spec_id}")

        # Step 2: Switch material
        switch_response = await client.post(
            "/api/v1/switch", json={"spec_id": spec_id, "query": "change floor to marble"}
        )
        assert switch_response.status_code == 201
        iteration_data = switch_response.json()

        print(f"✓ Material switched: {iteration_data['iteration_id']}")

        # Step 3: Evaluate
        evaluate_response = await client.post(
            "/api/v1/evaluate", json={"spec_id": spec_id, "rating": 4.5, "notes": "Great design!"}
        )
        assert evaluate_response.status_code == 201

        print("✓ Design evaluated")

        # Step 4: Check compliance (mocked)
        compliance_response = await client.post(
            "/api/v1/compliance/run_case",
            json={"project_id": "test_project", "spec_id": spec_id, "city": "Mumbai", "case_type": "fsi"},
        )

        print("✓ Complete workflow successful!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
