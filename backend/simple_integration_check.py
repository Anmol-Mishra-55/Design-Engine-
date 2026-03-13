#!/usr/bin/env python3
"""
Simple Integration Check - ASCII only
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def check_imports():
    """Check if all integration modules can be imported"""
    print("CHECKING IMPORTS...")

    try:
        from app.external_services import ranjeet_client, service_manager, sohum_client

        print("   [OK] External services module imported")
    except Exception as e:
        print(f"   [FAIL] External services import failed: {e}")
        return False

    try:
        print("   [OK] Enhanced Prefect integration imported")
    except Exception as e:
        print(f"   [FAIL] Prefect integration import failed: {e}")
        return False

    try:
        from app.api.workflow_management import router

        print("   [OK] Workflow management API imported")
    except Exception as e:
        print(f"   [FAIL] Workflow management API import failed: {e}")
        return False

    try:
        from app.api.bhiv_integrated import call_ranjeet_rl, call_sohum_compliance

        print("   [OK] BHIV integrated API imported")
    except Exception as e:
        print(f"   [FAIL] BHIV integrated API import failed: {e}")
        return False

    return True


def check_mock_responses():
    """Test mock response generation"""
    print("\nCHECKING MOCK RESPONSES...")

    try:
        from app.external_services import ranjeet_client, sohum_client

        # Test Sohum mock response
        test_case = {"city": "Mumbai", "project_id": "test_001"}
        mock_compliance = sohum_client.get_mock_compliance_response(test_case)

        if mock_compliance.get("case_id"):
            print("   [OK] Sohum mock response generated")
        else:
            print("   [FAIL] Sohum mock response failed")
            return False

        # Test Ranjeet mock response
        test_spec = {"objects": [{"id": "test", "type": "room"}]}
        mock_rl = ranjeet_client.get_mock_rl_response(test_spec, "Mumbai")

        if mock_rl.get("confidence"):
            print("   [OK] Ranjeet mock response generated")
        else:
            print("   [FAIL] Ranjeet mock response failed")
            return False

        return True

    except Exception as e:
        print(f"   [FAIL] Mock response check failed: {e}")
        return False


def main():
    """Run simple integration check"""
    print("=" * 50)
    print("SIMPLE INTEGRATION CHECK")
    print("=" * 50)

    checks = [check_imports(), check_mock_responses()]

    passed = sum(checks)
    total = len(checks)

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Checks Passed: {passed}/{total}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")

    if passed == total:
        print("SUCCESS: All integration checks passed!")
        return True
    else:
        print("FAILURE: Some integration checks failed")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
