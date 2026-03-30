import asyncio
import logging
import os

import httpx
from app.config import settings

logger = logging.getLogger(__name__)


async def generate_3d_with_meshy(prompt: str, dimensions: dict) -> dict:
    """Generate realistic 3D construction model using Meshy AI.
    Returns dict with keys: glb_bytes, thumbnail_bytes, video_url, task_id
    """
    MESHY_API_KEY = os.getenv("MESHY_API_KEY") or getattr(settings, "MESHY_API_KEY", None)

    if not MESHY_API_KEY:
        logger.warning("Meshy API key not configured")
        return None

    logger.info(f"Using Meshy API key: {MESHY_API_KEY[:10]}...")

    width = dimensions.get("width", 10)
    length = dimensions.get("length", 10)
    height = dimensions.get("height", 3)

    detailed_prompt = f"""Realistic 3D architectural construction model: {prompt}
Exact dimensions: {width}m wide × {length}m long × {height}m tall
Include: concrete foundation, brick/concrete walls, flat roof slab, wooden doors, aluminum windows
Modern residential construction style with realistic textures
Detailed architectural visualization"""

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            logger.info(f"Starting Meshy 3D generation...")
            response = await client.post(
                "https://api.meshy.ai/v2/text-to-3d",
                headers={"Authorization": f"Bearer {MESHY_API_KEY}"},
                json={
                    "mode": "preview",
                    "prompt": detailed_prompt,
                    "art_style": "realistic",
                    "negative_prompt": "cartoon, low quality, distorted",
                },
            )

            if response.status_code not in [200, 202]:
                logger.error(f"Meshy error: {response.status_code} - {response.text}")
                return None

            task_id = response.json()["result"]
            logger.info(f"Meshy task created: {task_id}, waiting for completion...")
            print(f"Task ID: {task_id}")
            print("Polling status every 2 seconds...")

            for attempt in range(120):  # Increased to 120 attempts (4 minutes)
                await asyncio.sleep(2)
                status_resp = await client.get(
                    f"https://api.meshy.ai/v2/text-to-3d/{task_id}",
                    headers={"Authorization": f"Bearer {MESHY_API_KEY}"},
                )

                if status_resp.status_code == 200:
                    result = status_resp.json()
                    status = result.get("status")
                    progress = result.get("progress", 0)
                    print(f"Attempt {attempt + 1}/120: Status={status}, Progress={progress}%")

                    if status == "SUCCEEDED":
                        glb_url = result.get("model_urls", {}).get("glb")
                        thumbnail_url = result.get("thumbnail_url")
                        video_url = result.get("video_url")

                        if glb_url:
                            print(f"Downloading GLB from: {glb_url}")
                            glb_resp = await client.get(glb_url)
                            logger.info(f"Meshy 3D generated: {len(glb_resp.content)} bytes")

                            thumbnail_bytes = None
                            if thumbnail_url:
                                thumb_resp = await client.get(thumbnail_url)
                                if thumb_resp.status_code == 200:
                                    thumbnail_bytes = thumb_resp.content
                                    logger.info(f"Meshy thumbnail downloaded: {len(thumbnail_bytes)} bytes")

                            return {
                                "glb_bytes": glb_resp.content,
                                "thumbnail_bytes": thumbnail_bytes,
                                "video_url": video_url,
                                "task_id": task_id,
                            }
                    elif status == "FAILED":
                        error = result.get("error", "Unknown error")
                        logger.error(f"Meshy failed: {error}")
                        print(f"Task failed: {error}")
                        return None
                else:
                    print(f"Status check failed: HTTP {status_resp.status_code}")

            logger.warning("Meshy timeout")
            return None
    except Exception as e:
        logger.error(f"Meshy error: {e}")
        return None
