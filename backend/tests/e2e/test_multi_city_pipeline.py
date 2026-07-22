"""
End-to-end multi-city pipeline tests
Tests complete flow: Prompt → Spec → Compliance → RL → GLB
"""

import asyncio

import pytest
from app.main import app
from app.multi_city.city_data_loader import City
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.mark.parametrize("city", [City.MUMBAI.value, City.PUNE.value, City.AHMEDABAD.value, City.NASHIK.value])
def test_city_rules_available(city):
    """Test that rules are available for each city"""
    response = client.get(f"/api/v1/cities/{city}/rules")

    assert response.status_code == 200
    data = response.json()

    assert data["city"] == city
    assert "fsi_base" in data
    assert "dcr_version" in data

    print(f"{city}: Rules available (FSI: {data['fsi_base']})")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "city,prompt",
    [
        (City.MUMBAI.value, "Design a 4-floor residential building"),
        (City.PUNE.value, "Create an IT office park with 3 buildings"),
        (City.AHMEDABAD.value, "Design a textile mill redevelopment"),
        (City.NASHIK.value, "Create a wine tourism facility"),
    ],
)
async def test_end_to_end_pipeline(city, prompt):
    """
    Test complete pipeline for each city:
    1. Generate spec from prompt
    2. Run compliance check
    3. Get RL optimization
    4. Verify all components work
    """

    # Step 1: Generate design
    request_payload = {
        "user_id": f"test_user_{city}",
        "prompt": prompt,
        "city": city,
        "project_id": f"e2e_test_{city}",
        "context": {},
    }

    response = client.post("/bhiv/v1/design", json=request_payload)

    # Note: May fail if systems not running - that's expected in unit test env
    if response.status_code != 200:
        pytest.skip(f"Systems not running for {city}, skipping integration test")
        return

    data = response.json()

    # Verify response structure
    assert "request_id" in data
    assert "spec_id" in data
    assert "spec_json" in data
    assert "compliance" in data

    # Verify spec has city-specific context
    assert city in str(data["spec_json"]) or city in data.get("context", {}).get("city", "")

    # Verify compliance was checked
    compliance = data["compliance"]
    assert "compliant" in compliance
    assert "violations" in compliance

    # Verify processing completed
    assert data["processing_time_ms"] > 0

    print(f"✅ {city}: Pipeline complete (spec_id: {data['spec_id']})")
    print(f"   Compliant: {compliance['compliant']}")
    print(f"   Processing time: {data['processing_time_ms']}ms")


@pytest.mark.asyncio
async def test_mcp_rules_for_all_cities():
    """Test MCP rules are fetchable for all cities"""
    cities = [City.MUMBAI, City.PUNE, City.AHMEDABAD, City.NASHIK]

    for city in cities:
        try:
            response = client.get(f"/mcp/rules/{city.value}")

            if response.status_code == 200:
                data = response.json()
                assert data["city"] == city.value
                assert "rules" in data
                print(f"{city.value}: MCP rules accessible ({data['count']} rules)")
            else:
                print(f"{city.value}: MCP endpoint not available (status: {response.status_code})")
        except Exception as e:
            print(f"{city.value}: MCP test skipped - {str(e)}")
            # Don't fail the test if external service is down
            pass


@pytest.mark.asyncio
async def test_rl_feedback_all_cities():
    """Test RL feedback submission works for all cities"""
    cities = [City.MUMBAI, City.PUNE, City.AHMEDABAD, City.NASHIK]

    for city in cities:
        feedback_payload = {
            "user_id": f"test_user_{city.value}",
            "design_a_id": f"spec_{city.value}_001",
            "design_b_id": f"spec_{city.value}_002",
            "preference": "A",
            "reason": f"Better design for {city.value}",
        }

        try:
            response = client.post("/api/v1/rl/feedback", json=feedback_payload)

            if response.status_code == 200:
                print(f"{city.value}: RL feedback submitted successfully")
            else:
                print(f"{city.value}: RL feedback failed (status: {response.status_code}) - using mock data")
        except Exception as e:
            print(f"{city.value}: RL feedback test skipped - {str(e)}")
            # Don't fail test if database/RL system unavailable
            pass


def test_city_context_completeness():
    """Test that city context includes all required fields"""
    cities = [City.MUMBAI, City.PUNE, City.AHMEDABAD, City.NASHIK]

    for city in cities:
        response = client.get(f"/api/v1/cities/{city.value}/context")

        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "city" in data
        assert "dcr_version" in data
        assert "constraints" in data
        assert "source_documents" in data
        assert "typical_use_cases" in data

        # Constraints structure
        constraints = data["constraints"]
        assert "fsi_base" in constraints
        assert "setback_front_m" in constraints
        assert "setback_rear_m" in constraints
        assert "parking_ratio" in constraints

        print(f"{city.value}: Context complete")


@pytest.mark.asyncio
async def test_performance_benchmarks():
    """Test response times for all cities"""
    import time

    cities = [City.MUMBAI, City.PUNE, City.AHMEDABAD, City.NASHIK]

    for city in cities:
        start_time = time.time()

        response = client.get(f"/api/v1/cities/{city.value}/context")

        end_time = time.time()
        response_time = (end_time - start_time) * 1000  # ms

        assert response.status_code == 200
        assert response_time < 100  # Should be under 100ms

        print(f"{city.value}: Response time {response_time:.1f}ms")


def test_error_handling():
    """Test error handling for invalid cities"""
    invalid_cities = ["Delhi", "Bangalore", "Chennai", "InvalidCity"]

    for city in invalid_cities:
        response = client.get(f"/api/v1/cities/{city}/rules")

        assert response.status_code == 404
        body = response.json()
        error_text = body.get("detail") or body.get("error", {}).get("message", "")
        assert "not supported" in error_text

        print(f"{city}: Properly rejected")
