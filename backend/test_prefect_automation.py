"""
Test Prefect Automation - Verify Real Workflow Tracking
Tests: /api/v1/automation/workflow, /api/v1/automation/status
"""
import asyncio
import time

import httpx

BASE_URL = "http://localhost:8000"
TOKEN = None


async def login():
    """Get authentication token"""
    global TOKEN
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/auth/login", json={"username": "admin", "password": "bhiv2024"}
        )
        if response.status_code == 200:
            TOKEN = response.json()["access_token"]
            print("✅ Authentication successful")
            return True
        print(f"❌ Login failed: {response.status_code}")
        return False


async def test_automation_status():
    """Test /api/v1/automation/status endpoint"""
    print("\n" + "=" * 70)
    print("Testing /api/v1/automation/status")
    print("=" * 70)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/automation/status", headers={"Authorization": f"Bearer {TOKEN}"}
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS - /api/v1/automation/status")
            print(f"   Automation System: {data.get('automation_system', {}).get('prefect_available')}")
            print(f"   Execution Mode: {data.get('automation_system', {}).get('execution_mode')}")
            print(f"   Status: {data.get('status')}")
            print(f"   Recent Executions: {data.get('total_executions', 0)}")

            if data.get("recent_executions"):
                print(f"\n   Last 3 Executions:")
                for exec in data["recent_executions"][:3]:
                    print(f"     - {exec.get('flow_name')}: {exec.get('status')}")
                    print(f"       Run ID: {exec.get('run_id')}")
                    print(f"       Duration: {exec.get('duration_seconds')}s")

            return True
        else:
            print(f"❌ FAILED - /api/v1/automation/status")
            print(f"   Error: {response.text}")
            return False


async def test_trigger_workflow():
    """Test /api/v1/automation/workflow endpoint"""
    print("\n" + "=" * 70)
    print("Testing /api/v1/automation/workflow")
    print("=" * 70)

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/automation/workflow",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={
                "workflow_type": "design_optimization",
                "parameters": {"spec_id": "test_spec_123", "optimization_level": "high", "city": "Mumbai"},
            },
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS - Workflow triggered")
            print(f"   Workflow ID: {data.get('workflow_id')}")
            print(f"   Run ID: {data.get('run_id')}")
            print(f"   Workflow Type: {data.get('workflow_type')}")
            print(f"   Execution Mode: {data.get('execution_mode')}")
            print(f"   Traceable: {data.get('traceable')}")
            print(f"   Status Endpoint: {data.get('status_endpoint')}")

            return True, data.get("run_id")
        else:
            print(f"❌ FAILED - Workflow trigger")
            print(f"   Error: {response.text}")
            return False, None


async def test_workflow_status(run_id):
    """Test /api/v1/automation/workflow/{run_id}/status endpoint"""
    print("\n" + "=" * 70)
    print(f"Testing /api/v1/automation/workflow/{run_id}/status")
    print("=" * 70)

    if not run_id:
        print("⚠️  No run_id available, skipping test")
        return False

    # Wait a moment for workflow to start
    await asyncio.sleep(2)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/automation/workflow/{run_id}/status", headers={"Authorization": f"Bearer {TOKEN}"}
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS - Workflow status retrieved")
            print(f"   Workflow ID: {data.get('workflow_id')}")
            print(f"   State: {data.get('state')}")
            print(f"   Started At: {data.get('started_at')}")
            print(f"   Duration: {data.get('duration_seconds')}s")

            if data.get("database_record"):
                db_rec = data["database_record"]
                print(f"\n   Database Record:")
                print(f"     Flow Name: {db_rec.get('flow_name')}")
                print(f"     Deployment: {db_rec.get('deployment_name')}")
                if db_rec.get("error"):
                    print(f"     Error: {db_rec.get('error')}")

            return True
        else:
            print(f"❌ FAILED - Workflow status")
            print(f"   Error: {response.text}")
            return False


async def test_pdf_compliance_workflow():
    """Test PDF compliance automation"""
    print("\n" + "=" * 70)
    print("Testing /api/v1/automation/pdf-compliance")
    print("=" * 70)

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/automation/pdf-compliance",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={
                "pdf_url": "https://example.com/test.pdf",
                "city": "Mumbai",
                "sohum_url": "https://ai-rule-api-w7z5.onrender.com",
            },
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS - PDF compliance workflow triggered")
            print(f"   Workflow ID: {data.get('workflow_id')}")
            print(f"   Run ID: {data.get('run_id')}")
            return True, data.get("run_id")
        else:
            print(f"❌ FAILED - PDF compliance workflow")
            print(f"   Error: {response.text}")
            return False, None


async def verify_database_storage():
    """Verify workflows are stored in database"""
    print("\n" + "=" * 70)
    print("Verifying Database Storage")
    print("=" * 70)

    try:
        from app.database_mongodb import SessionLocal

        db = SessionLocal()
        try:
            # Get recent workflow runs
            recent_runs = db.query(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(5).all()

            print(f"✅ Database accessible")
            print(f"   Total recent runs: {len(recent_runs)}")

            for run in recent_runs:
                print(f"\n   Run ID: {run.flow_run_id}")
                print(f"     Flow: {run.flow_name}")
                print(f"     Status: {run.status}")
                print(f"     Created: {run.created_at}")
                print(f"     Duration: {run.duration_seconds}s")

            return True
        finally:
            db.close()
    except Exception as e:
        print(f"❌ Database verification failed: {e}")
        return False


async def main():
    print("=" * 70)
    print("PREFECT AUTOMATION VALIDATION TEST SUITE")
    print("=" * 70)

    # Login
    if not await login():
        print("\n❌ Authentication failed. Cannot proceed with tests.")
        return

    results = {}

    # Test 1: Automation status
    results["automation_status"] = await test_automation_status()

    # Test 2: Trigger workflow
    workflow_success, run_id = await test_trigger_workflow()
    results["trigger_workflow"] = workflow_success

    # Test 3: Check workflow status
    if run_id:
        results["workflow_status"] = await test_workflow_status(run_id)
    else:
        results["workflow_status"] = False

    # Test 4: PDF compliance workflow
    pdf_success, pdf_run_id = await test_pdf_compliance_workflow()
    results["pdf_compliance"] = pdf_success

    # Test 5: Database storage
    results["database_storage"] = await verify_database_storage()

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 AUTOMATION IS TRACEABLE - All workflows tracked!")
        print("\nKey Features Verified:")
        print("  ✅ workflow_id stored in database")
        print("  ✅ run_id tracked for each execution")
        print("  ✅ status endpoint shows real executions")
        print("  ✅ Full execution history available")
    else:
        print("\n⚠️  Some tests failed - check logs")


if __name__ == "__main__":
    asyncio.run(main())
