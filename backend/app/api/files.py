"""
File Download API — Phase 1 enforcement.

/api/v1/files/<bucket>/<file_id> now proxies from the live Bucket service.
GridFS is NOT used for geometry/spec artifacts.
If the Bucket lookup fails → 404. No local fallback.
"""
import logging

import httpx
from app.storage import _BUCKET_BASE, _INTEGRATION_ID, _READ_ENDPOINT, _REQUESTER_ID
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response

router = APIRouter()
logger = logging.getLogger(__name__)

CONTENT_TYPES = {
    "glb": "model/gltf-binary",
    "stl": "model/stl",
    "step": "application/step",
    "json": "application/json",
    "png": "image/png",
}


@router.get("/files/{bucket}/{file_id}")
async def download_file_endpoint(bucket: str, file_id: str):
    """
    Proxy file download from the live Bucket service.
    artifact_id = file_id (UUID stored during upload).
    No GridFS, no local disk — Bucket only.
    """
    payload = {
        "requester_id": _REQUESTER_ID,
        "integration_id": _INTEGRATION_ID,
        "artifact_id": file_id,
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(_READ_ENDPOINT, json=payload)
            if r.status_code == 404:
                raise HTTPException(status_code=404, detail="File not found in Bucket")
            r.raise_for_status()
            result = r.json()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Bucket proxy download failed: %s", exc)
        raise HTTPException(status_code=502, detail="Bucket service unavailable")

    if not result.get("success"):
        raise HTTPException(status_code=404, detail="Artifact not found")

    import base64

    artifact = result.get("data", {}).get("artifact", {})
    payload_data = artifact.get("payload", {})
    data_b64 = payload_data.get("data_base64")
    if not data_b64:
        raise HTTPException(status_code=404, detail="Artifact has no data")

    file_data = base64.b64decode(data_b64)
    content_type = payload_data.get("content_type", "application/octet-stream")
    path = payload_data.get("path", file_id)
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    content_type = content_type or CONTENT_TYPES.get(ext, "application/octet-stream")
    filename = path.split("/")[-1] if "/" in path else path

    return Response(
        content=file_data,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(file_data)),
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/viewer", response_class=HTMLResponse, tags=["File Download"])
async def glb_viewer(glb: str = "", artifact_id: str = "", title: str = "3D Viewer"):
    """
    Embedded 3D viewer.

    Option A — pass local proxy URL (recommended):
        /api/v1/viewer?glb=http://localhost:8000/api/v1/files/geometry/<artifact_id>&title=3BHK

    Option B — pass artifact_id directly (auto-builds proxy URL):
        /api/v1/viewer?artifact_id=5c57ed94-9895-4150-942a-9a3787685296&title=3BHK
    """
    if artifact_id and not glb:
        glb = f"/api/v1/files/geometry/{artifact_id}"
    model_tag = ""
    if glb:
        model_tag = (
            f'<model-viewer src="{glb}" alt="3D Model" camera-controls auto-rotate '
            f'shadow-intensity="1" exposure="0.8" ar ar-modes="webxr scene-viewer quick-look">'
            f'<div class="controls" slot="hotspot-0">'
            f'<button class="btn" onclick="mv().cameraOrbit=\'0deg 75deg 105%\'">Front</button>'
            f'<button class="btn" onclick="mv().cameraOrbit=\'90deg 75deg 105%\'">Side</button>'
            f'<button class="btn" onclick="mv().cameraOrbit=\'180deg 75deg 105%\'">Back</button>'
            f'<button class="btn" onclick="mv().cameraOrbit=\'0deg 0deg 105%\'">Top</button>'
            f'<a class="btn" href="{glb}" download>Download GLB</a>'
            f"</div>"
            f"</model-viewer>"
        )
        badge = "<span class='badge'>GLB loaded</span>"
    else:
        model_tag = (
            "<div class='empty'>"
            "<p>No GLB URL provided</p>"
            "<code>Usage: /api/v1/viewer?glb=https://bhiv-bucket.onrender.com/bucket/artifact/&lt;id&gt;</code>"
            "</div>"
        )
        badge = "<span class='badge'>no model</span>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>BHIV — {title}</title>
  <script type="module" src="https://unpkg.com/@google/model-viewer/dist/model-viewer.min.js"></script>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ background:#111; color:#eee; font-family:sans-serif; height:100vh; display:flex; flex-direction:column; }}
    header {{ padding:12px 20px; background:#1a1a2e; display:flex; align-items:center; gap:16px; flex-shrink:0; }}
    header h1 {{ font-size:16px; font-weight:600; color:#7eb8f7; }}
    .badge {{ font-size:11px; background:#2a2a4a; padding:3px 8px; border-radius:4px; color:#aaa; }}
    model-viewer {{ flex:1; width:100%; background:#1a1a1a; --progress-bar-color:#7eb8f7; }}
    .empty {{ flex:1; display:flex; align-items:center; justify-content:center; flex-direction:column; gap:12px; color:#555; }}
    .empty code {{ font-size:12px; background:#222; padding:8px 16px; border-radius:6px; color:#888; }}
    .controls {{ position:absolute; bottom:20px; right:20px; display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; }}
    .btn {{ background:#2a2a4a; border:1px solid #444; color:#ccc; padding:7px 14px; border-radius:6px;
            cursor:pointer; font-size:13px; text-decoration:none; display:inline-block; }}
    .btn:hover {{ background:#3a3a6a; color:#fff; }}
  </style>
</head>
<body>
  <header>
    <h1>BHIV — {title}</h1>
    {badge}
  </header>
  {model_tag}
  <script>function mv(){{ return document.querySelector('model-viewer'); }}</script>
</body>
</html>"""
    return HTMLResponse(content=html)
