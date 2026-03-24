"""
Service Health Monitor
Reduces dependency on mock responses by monitoring external services
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class ServiceMonitor:
    """Monitor external service health and availability"""

    def __init__(self):
        self.service_status = {}
        self.last_check = {}
        self.check_interval = 300  # 5 minutes

    async def check_service_health(self, service_name: str, url: str, timeout: float = 10.0) -> bool:
        """Check if a service is healthy"""
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(f"{url}/health")
                is_healthy = response.status_code == 200

                self.service_status[service_name] = {
                    "healthy": is_healthy,
                    "last_check": datetime.now(),
                    "response_time": response.elapsed.total_seconds() if hasattr(response, "elapsed") else 0,
                }

                return is_healthy

        except Exception as e:
            logger.warning(f"Service {service_name} health check failed: {e}")
            self.service_status[service_name] = {"healthy": False, "last_check": datetime.now(), "error": str(e)}
            return False

    async def is_service_available(self, service_name: str) -> bool:
        """Check if service is available (with caching)"""
        now = datetime.now()
        last_check = self.last_check.get(service_name)

        # Check if we need to refresh status
        if not last_check or (now - last_check).seconds > self.check_interval:
            await self._refresh_service_status(service_name)

        return self.service_status.get(service_name, {}).get("healthy", False)

    async def _refresh_service_status(self, service_name: str):
        """Refresh status for a specific service"""
        service_urls = {
            "sohum_mcp": getattr(settings, "SOHAM_URL", ""),
            "ranjeet_rl": getattr(settings, "RANJEET_RL_URL", ""),
            "openai": "https://api.openai.com",
        }

        url = service_urls.get(service_name)
        if url:
            await self.check_service_health(service_name, url)
            self.last_check[service_name] = datetime.now()

    async def get_all_service_status(self) -> Dict:
        """Get status of all monitored services"""
        services = ["sohum_mcp", "ranjeet_rl", "openai"]

        # Refresh all services
        tasks = [self._refresh_service_status(service) for service in services]
        await asyncio.gather(*tasks, return_exceptions=True)

        return {
            "services": self.service_status,
            "summary": {
                "total": len(services),
                "healthy": sum(1 for s in self.service_status.values() if s.get("healthy", False)),
                "unhealthy": sum(1 for s in self.service_status.values() if not s.get("healthy", False)),
            },
        }


# Global service monitor instance
service_monitor = ServiceMonitor()


async def should_use_mock_response(service_name: str) -> bool:
    """Determine if we should use mock response based on service availability"""
    return not await service_monitor.is_service_available(service_name)


async def get_service_health_summary() -> Dict:
    """Get comprehensive service health summary"""
    return await service_monitor.get_all_service_status()
