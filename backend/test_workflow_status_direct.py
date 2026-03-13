#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio


async def test_workflow_status():
    print("TESTING WORKFLOW STATUS ENDPOINT")
    print("=" * 50)

    # Test with the created flow_run_id
    test_flow_id = "test-flow-run-71910221"
    print(f"Testing with flow_run_id: {test_flow_id}")

    try:
        result = await get_workflow_status(test_flow_id)
        print("SUCCESS - Response:")
        print(result)
        return result
    except Exception as e:
        print(f"ERROR: {e}")
        return {"error": str(e)}


async def test_invalid_flow_id():
    print("\nTesting with invalid flow_run_id...")

    try:
        result = await get_workflow_status("invalid-flow-id-123")
        print("Response for invalid ID:")
        print(result)
        return result
    except Exception as e:
        print(f"ERROR for invalid ID: {e}")
        return {"error": str(e)}


async def main():
    # Test valid flow_run_id
    await test_workflow_status()

    # Test invalid flow_run_id
    await test_invalid_flow_id()


if __name__ == "__main__":
    asyncio.run(main())
