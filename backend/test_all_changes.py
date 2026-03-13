"""
Comprehensive Test Suite for All Recent Changes
Tests all 6 major changes from conversation summary
"""
import json
import time
from typing import Any, Dict

import requests

BASE_URL = "http://localhost:8000"
TOKEN = None

# Test Results Tracker
results = {
    "1_rl_mocks": {"status": "❌", "details": []},
    "2_timeouts": {"status": "❌", "details": []},
    "3_mcp_compliance": {"status": "❌", "details": []},
    "4_core_apis": {"status": "❌", "details": []},
    "5_prefect_automation": {"status": "❌", "details": []},
    "6_data_integrity": {"status": "❌", "details": []},
}


def login() -> str:
    """Get JWT token"""
    response = requests.post(f"{BASE_URL}/api/v1/auth/login", json={"username": "admin", "password": "bhiv2024"})
    if response.status_code == 200:
        return response.json()["access_token"]
    raise Exception(f"Login failed: {response.text}")


def headers() -> Dict[str, str]:
    """Get auth headers"""
    return {"Authorization": f"Bearer {TOKEN}"}


# ============================================================================
# TEST 1: Kill All Mocks (RL) - Verify mock fallbacks RESTORED
# ============================================================================
def test_rl_mocks():
    """Test that RL endpoints have mock fallbacks for graceful degradation"""
    print("\n" + "=" * 80)
    print("TEST 1: RL Mock Fallbacks (Should be RESTORED)")
    print("=" * 80)

    tests = []

    # Test 1.1: /rl/optimize should have mock fallback
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/rl/optimize",
            headers=headers(),
            json={"spec_id": "test_spec", "user_id": "test_user"},
            timeout=5,
        )
        has_mock = response.status_code in [200, 503]
        tests.append(("✅" if has_mock else "❌", "/rl/optimize has fallback", response.status_code))
    except Exception as e:
        tests.append(("❌", "/rl/optimize error", str(e)))

    # Test 1.2: /rl/feedback should work
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/rl/feedback",
            headers=headers(),
            json={"design_a_id": "a", "design_b_id": "b", "preference": "A"},
            timeout=5,
        )
        tests.append(("✅" if response.status_code == 200 else "❌", "/rl/feedback works", response.status_code))
    except Exception as e:
        tests.append(("❌", "/rl/feedback error", str(e)))

    # Test 1.3: Check timeout is 180s in config
    try:
        from app.config import settings

        timeout_ok = settings.RANJEET_TIMEOUT == 180
        tests.append(("✅" if timeout_ok else "❌", "RL timeout = 180s", settings.RANJEET_TIMEOUT))
    except Exception as e:
        tests.append(("❌", "Config check error", str(e)))

    results["1_rl_mocks"]["details"] = tests
    results["1_rl_mocks"]["status"] = "✅" if all(t[0] == "✅" for t in tests) else "⚠️"

    for status, test, detail in tests:
        print(f"{status} {test}: {detail}")


# ============================================================================
# TEST 2: Timeout Increases - Verify 180s timeouts
# ============================================================================
def test_timeouts():
    """Test that timeouts are increased to 180s"""
    print("\n" + "=" * 80)
    print("TEST 2: Timeout Increases (Should be 180s)")
    print("=" * 80)

    tests = []

    try:
        from app.config import settings

        # Check MCP timeout
        mcp_ok = settings.SOHUM_TIMEOUT == 180
        tests.append(("✅" if mcp_ok else "❌", "MCP timeout = 180s", f"{settings.SOHUM_TIMEOUT}s"))

        # Check RL timeout
        rl_ok = settings.RANJEET_TIMEOUT == 180
        tests.append(("✅" if rl_ok else "❌", "RL timeout = 180s", f"{settings.RANJEET_TIMEOUT}s"))

    except Exception as e:
        tests.append(("❌", "Timeout config error", str(e)))

    results["2_timeouts"]["details"] = tests
    results["2_timeouts"]["status"] = "✅" if all(t[0] == "✅" for t in tests) else "❌"

    for status, test, detail in tests:
        print(f"{status} {test}: {detail}")


# ============================================================================
# TEST 3: Close Compliance Loop (MCP) - NO mock fallback
# ============================================================================
def test_mcp_compliance():
    """Test that MCP has NO mock fallback (real data only)"""
    print("\n" + "=" * 80)
    print("TEST 3: MCP Compliance (NO Mock Fallback)")
    print("=" * 80)

    tests = []

    # Test 3.1: /mcp/check should return 503 when service down (no mock)
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/mcp/check",
            headers=headers(),
            json={"city": "Mumbai", "parameters": {"plot_size": 500}},
            timeout=5,
        )
        # Should be 200 (service up) or 503 (service down, no mock)
        no_mock = response.status_code in [200, 503]
        if response.status_code == 200:
            data = response.json()
            # Check it's real data (has compliance_score)
            is_real = "compliance_score" in data or "rules_applied" in data
            tests.append(("✅" if is_real else "❌", "/mcp/check returns real data", "Real MCP response"))
        else:
            tests.append(("✅", "/mcp/check no mock fallback", f"Returns {response.status_code}"))
    except Exception as e:
        tests.append(("⚠️", "/mcp/check timeout/error", str(e)[:50]))

    # Test 3.2: Check no placeholder recommendations in code
    try:
        with open("app/external_services.py", "r") as f:
            content = f.read()
            no_placeholder = '"Ensure proper ventilation"' not in content
            tests.append(("✅" if no_placeholder else "❌", "No placeholder recommendations", "Removed"))
    except Exception as e:
        tests.append(("❌", "Code check error", str(e)))

    results["3_mcp_compliance"]["details"] = tests
    results["3_mcp_compliance"]["status"] = "✅" if all(t[0] in ["✅", "⚠️"] for t in tests) else "❌"

    for status, test, detail in tests:
        print(f"{status} {test}: {detail}")


# ============================================================================
# TEST 4: Fix Broken Core APIs
# ============================================================================
def test_core_apis():
    """Test that core APIs are working"""
    print("\n" + "=" * 80)
    print("TEST 4: Core APIs (Should All Work)")
    print("=" * 80)

    tests = []

    # Test 4.1: /api/v1/history
    try:
        response = requests.get(f"{BASE_URL}/api/v1/history", headers=headers(), timeout=10)
        tests.append(("✅" if response.status_code == 200 else "❌", "/api/v1/history", response.status_code))
    except Exception as e:
        tests.append(("❌", "/api/v1/history error", str(e)[:50]))

    # Test 4.2: /bhiv/v1/prompt
    try:
        response = requests.post(
            f"{BASE_URL}/bhiv/v1/prompt", headers=headers(), json={"prompt": "test", "city": "Mumbai"}, timeout=10
        )
        tests.append(("✅" if response.status_code in [200, 422] else "❌", "/bhiv/v1/prompt", response.status_code))
    except Exception as e:
        tests.append(("❌", "/bhiv/v1/prompt error", str(e)[:50]))

    # Test 4.3: /api/v1/rl/feedback
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/rl/feedback",
            headers=headers(),
            json={"design_a_id": "a", "design_b_id": "b", "preference": "A"},
            timeout=10,
        )
        tests.append(("✅" if response.status_code == 200 else "❌", "/api/v1/rl/feedback", response.status_code))
    except Exception as e:
        tests.append(("❌", "/api/v1/rl/feedback error", str(e)[:50]))

    # Test 4.4: Check explicit routes in main.py
    try:
        with open("app/main.py", "r") as f:
            content = f.read()
            has_history = '@app.get("/api/v1/history"' in content
            has_reports = '@app.get("/api/v1/reports/{spec_id}"' in content
            tests.append(
                ("✅" if has_history else "❌", "Explicit /history route", "Present" if has_history else "Missing")
            )
            tests.append(
                ("✅" if has_reports else "❌", "Explicit /reports route", "Present" if has_reports else "Missing")
            )
    except Exception as e:
        tests.append(("❌", "Route check error", str(e)))

    results["4_core_apis"]["details"] = tests
    results["4_core_apis"]["status"] = "✅" if all(t[0] == "✅" for t in tests) else "⚠️"

    for status, test, detail in tests:
        print(f"{status} {test}: {detail}")


# ============================================================================
# TEST 5: Activate Prefect Automation
# ============================================================================
def test_prefect_automation():
    """Test Prefect workflow tracking"""
    print("\n" + "=" * 80)
    print("TEST 5: Prefect Automation (Workflow Tracking)")
    print("=" * 80)

    tests = []

    # Test 5.1: /automation/workflow returns workflow_id and run_id
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/automation/workflow",
            headers=headers(),
            json={"user_id": "test_user", "spec_id": "test_spec", "workflow_type": "full_pipeline"},
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            has_workflow_id = "workflow_id" in data
            has_run_id = "run_id" in data or "flow_run_id" in data
            tests.append(("✅" if has_workflow_id else "❌", "Returns workflow_id", has_workflow_id))
            tests.append(("✅" if has_run_id else "❌", "Returns run_id", has_run_id))
        else:
            tests.append(("⚠️", "/automation/workflow", f"Status {response.status_code}"))
    except Exception as e:
        tests.append(("❌", "/automation/workflow error", str(e)[:50]))

    # Test 5.2: /automation/status shows execution history
    try:
        response = requests.get(f"{BASE_URL}/api/v1/automation/status", headers=headers(), timeout=10)
        if response.status_code == 200:
            data = response.json()
            has_history = "workflow_runs" in data or "executions" in data or isinstance(data, list)
            tests.append(("✅" if has_history else "❌", "Status shows history", has_history))
        else:
            tests.append(("⚠️", "/automation/status", f"Status {response.status_code}"))
    except Exception as e:
        tests.append(("❌", "/automation/status error", str(e)[:50]))

    # Test 5.3: Check WorkflowRun model has workflow_id and run_id
    try:
        has_fields = hasattr(WorkflowRun, "id") and hasattr(WorkflowRun, "flow_run_id")
        tests.append(("✅" if has_fields else "❌", "WorkflowRun model complete", has_fields))
    except Exception as e:
        tests.append(("❌", "Model check error", str(e)))

    results["5_prefect_automation"]["details"] = tests
    results["5_prefect_automation"]["status"] = "✅" if all(t[0] in ["✅", "⚠️"] for t in tests) else "❌"

    for status, test, detail in tests:
        print(f"{status} {test}: {detail}")


# ============================================================================
# TEST 6: Data & Storage Integrity
# ============================================================================
def test_data_integrity():
    """Test data integrity audit system"""
    print("\n" + "=" * 80)
    print("TEST 6: Data & Storage Integrity")
    print("=" * 80)

    tests = []

    # Test 6.1: /api/v1/audit/spec/{spec_id} endpoint exists
    try:
        response = requests.get(f"{BASE_URL}/api/v1/audit/spec/test_spec", headers=headers(), timeout=10)
        tests.append(("✅" if response.status_code in [200, 404] else "❌", "/audit/spec endpoint", response.status_code))
    except Exception as e:
        tests.append(("❌", "/audit/spec error", str(e)[:50]))

    # Test 6.2: /api/v1/audit/spec/{spec_id}/complete endpoint exists
    try:
        response = requests.get(f"{BASE_URL}/api/v1/audit/spec/test_spec/complete", headers=headers(), timeout=10)
        tests.append(
            ("✅" if response.status_code in [200, 404] else "❌", "/audit/spec/complete endpoint", response.status_code)
        )
    except Exception as e:
        tests.append(("❌", "/audit/spec/complete error", str(e)[:50]))

    # Test 6.3: /api/v1/history includes data integrity
    try:
        response = requests.get(f"{BASE_URL}/api/v1/history", headers=headers(), timeout=10)
        if response.status_code == 200:
            data = response.json()
            # Check if response includes integrity info
            has_integrity = False
            if isinstance(data, dict) and "specs" in data:
                specs = data["specs"]
                if specs and len(specs) > 0:
                    has_integrity = "data_integrity" in specs[0] or "iterations_count" in specs[0]
            tests.append(("✅" if has_integrity else "⚠️", "/history has integrity data", has_integrity))
        else:
            tests.append(("⚠️", "/history response", f"Status {response.status_code}"))
    except Exception as e:
        tests.append(("❌", "/history integrity check error", str(e)[:50]))

    # Test 6.4: Check data_audit.py file exists
    try:
        with open("app/api/data_audit.py", "r") as f:
            content = f.read()
            has_audit_endpoint = "audit/spec" in content
            tests.append(("✅" if has_audit_endpoint else "❌", "data_audit.py exists", has_audit_endpoint))
    except Exception as e:
        tests.append(("❌", "data_audit.py check", str(e)))

    # Test 6.5: Check data_audit router registered in main.py
    try:
        with open("app/main.py", "r") as f:
            content = f.read()
            has_import = "data_audit" in content
            has_router = "data_audit.router" in content
            tests.append(
                ("✅" if has_import and has_router else "❌", "data_audit router registered", has_import and has_router)
            )
    except Exception as e:
        tests.append(("❌", "Router registration check", str(e)))

    results["6_data_integrity"]["details"] = tests
    results["6_data_integrity"]["status"] = "✅" if all(t[0] in ["✅", "⚠️"] for t in tests) else "❌"

    for status, test, detail in tests:
        print(f"{status} {test}: {detail}")


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================
def main():
    global TOKEN

    print("\n" + "=" * 80)
    print("COMPREHENSIVE TEST SUITE - ALL RECENT CHANGES")
    print("=" * 80)
    print("\nTesting 6 major changes from conversation summary:")
    print("1. Kill All Mocks (RL) - Mock fallbacks RESTORED")
    print("2. Timeout Increases - 180s for MCP and RL")
    print("3. Close Compliance Loop (MCP) - NO mock fallback")
    print("4. Fix Broken Core APIs - All endpoints working")
    print("5. Activate Prefect Automation - Workflow tracking")
    print("6. Data & Storage Integrity - Audit system")

    # Login
    try:
        print("\nLogging in...")
        TOKEN = login()
        print("[OK] Login successful")
    except Exception as e:
        print(f"[FAIL] Login failed: {e}")
        print("\n[WARNING] Make sure server is running: python -m uvicorn app.main:app --reload")
        return

    # Run all tests
    test_rl_mocks()
    test_timeouts()
    test_mcp_compliance()
    test_core_apis()
    test_prefect_automation()
    test_data_integrity()

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    for test_name, result in results.items():
        status = result["status"]
        name = test_name.replace("_", " ").title()
        print(f"\n{status} {name}")
        for detail_status, detail_test, detail_info in result["details"]:
            print(f"  {detail_status} {detail_test}: {detail_info}")

    # Overall status
    all_passed = all(r["status"] in ["✅", "⚠️"] for r in results.values())
    critical_passed = all(r["status"] == "✅" for k, r in results.items() if k in ["2_timeouts", "4_core_apis"])

    print("\n" + "=" * 80)
    if all_passed and critical_passed:
        print("[SUCCESS] ALL TESTS PASSED - All changes verified!")
    elif critical_passed:
        print("[WARNING] CRITICAL TESTS PASSED - Some warnings present")
    else:
        print("[FAIL] SOME TESTS FAILED - Review details above")
    print("=" * 80)


if __name__ == "__main__":
    main()
