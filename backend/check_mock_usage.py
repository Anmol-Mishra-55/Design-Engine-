#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio

from app.config import settings


async def check_service_usage():
    """Check if system is using real or mock services"""
    print("SERVICE USAGE CHECK")
    print("=" * 40)

    # Check config values
    print("CONFIG VALUES:")
    print(f"  SOHUM_MCP_URL: {settings.SOHUM_MCP_URL}")
    print(f"  RANJEET_RL_URL: {settings.RANJEET_RL_URL}")
    print(f"  LAND_UTILIZATION_MOCK_MODE: {settings.LAND_UTILIZATION_MOCK_MODE}")
    print(f"  RANJEET_SERVICE_AVAILABLE: {settings.RANJEET_SERVICE_AVAILABLE}")
    print()

    # Check service monitor status
    print("SERVICE MONITOR STATUS:")
    try:
        status = await service_monitor.get_all_service_status()
        for service_name, service_info in status.get("services", {}).items():
            is_healthy = service_info.get("healthy", False)
            mock_active = not is_healthy
            print(f"  {service_name}: {'LIVE' if is_healthy else 'MOCK'} (healthy: {is_healthy})")

        summary = status.get("summary", {})
        print(f"  SUMMARY: {summary.get('healthy', 0)}/{summary.get('total', 0)} services healthy")
    except Exception as e:
        print(f"  ERROR: {e}")

    print()

    # Check specific service availability
    print("INDIVIDUAL SERVICE CHECKS:")
    services = ["sohum_mcp", "ranjeet_rl"]
    for service in services:
        try:
            is_available = await service_monitor.is_service_available(service)
            print(f"  {service}: {'AVAILABLE' if is_available else 'UNAVAILABLE'}")
        except Exception as e:
            print(f"  {service}: ERROR - {e}")


if __name__ == "__main__":
    asyncio.run(check_service_usage())
