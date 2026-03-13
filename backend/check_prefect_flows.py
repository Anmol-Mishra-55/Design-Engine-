#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio


async def get_available_flow_runs():
    print("CHECKING AVAILABLE FLOW RUNS")
    print("=" * 40)

    if not minimal_client.client:
        print("Prefect client not available")
        return []

    try:
        # Get recent flow runs
        flow_runs = await minimal_client.client.read_flow_runs(limit=5)

        if flow_runs:
            print(f"Found {len(flow_runs)} flow runs:")
            for run in flow_runs:
                print(f"- ID: {run.id}")
                print(f"  Name: {run.name}")
                print(f"  State: {run.state.type.value if run.state else 'unknown'}")
                print()
            return [str(run.id) for run in flow_runs]
        else:
            print("No flow runs found")
            return []

    except Exception as e:
        print(f"Error getting flow runs: {e}")
        return []


if __name__ == "__main__":
    asyncio.run(get_available_flow_runs())
