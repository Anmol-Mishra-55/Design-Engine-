"""
Tripo AI 3D Model Generator - async version
"""
import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


async def generate_3d_with_tripo(prompt: str, dimensions: dict, api_key: str) -> Optional[bytes]:
    """Generate 3D model using Tripo AI (async)"""
    try:
        width = dimensions.get("width", 10)
        length = dimensions.get("length", 10)
        height = dimensions.get("height", 3)

        detailed_prompt = (
            f"Architectural building construction: {prompt}. "
            f"Realistic 3D model with dimensions {width}m width x {length}m length x {height}m height. "
            f"Include walls, roof, foundation, doors, windows. Professional architectural visualization."
        )

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.tripo3d.ai/v2/openapi/task",
                headers=headers,
                json={"type": "text_to_model", "prompt": detailed_prompt},
            )

            if response.status_code == 403:
                error_data = response.json()
                if error_data.get("code") == 2010:
                    logger.warning("Tripo AI: No credits remaining")
                return None

            if response.status_code != 200:
                logger.warning("Tripo task creation failed: %s", response.status_code)
                return None

            task_id = response.json()["data"]["task_id"]
            logger.info("Tripo task created: %s", task_id)

            # Poll for completion (max 2 minutes, 24 × 5s)
            for attempt in range(24):
                await asyncio.sleep(5)

                result = await client.get(
                    f"https://api.tripo3d.ai/v2/openapi/task/{task_id}",
                    headers=headers,
                )

                if result.status_code != 200:
                    logger.warning("Tripo status check failed: %s", result.status_code)
                    return None

                data = result.json()["data"]
                status = data["status"]
                logger.info("Tripo status (attempt %d/24): %s", attempt + 1, status)

                if status == "success":
                    glb_url = data["output"]["model"]
                    glb_response = await client.get(glb_url, timeout=60.0)
                    logger.info("✅ Tripo generated %d bytes", len(glb_response.content))
                    return glb_response.content

                elif status == "failed":
                    logger.warning("Tripo generation failed: %s", data.get("error", "Unknown"))
                    return None

        logger.warning("Tripo timeout after 2 minutes")
        return None

    except Exception as exc:
        logger.error("Tripo AI error: %s", exc, exc_info=True)
        return None
