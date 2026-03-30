"""
Downloads Gallery - Browse all generated designs with images and download links
Access at: http://localhost:8000/downloads  (no auth required for easy access)
"""
import logging

from app.database_mongodb import get_database
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/downloads", response_class=HTMLResponse, include_in_schema=False)
async def downloads_gallery():
    """Gallery of all generated designs with Meshy thumbnail and download links"""
    try:
        db = get_database()
        specs = await db.specs.find({}).sort("created_at", -1).to_list(length=100)
    except Exception as e:
        logger.error("DB error: %s", e)
        specs = []

    if not specs:
        cards = """
        <div style="text-align:center;padding:80px 20px;color:#94a3b8">
          <div style="font-size:48px;margin-bottom:16px">🏗️</div>
          <h2 style="font-size:20px;color:#64748b">No designs generated yet</h2>
          <p style="margin-top:8px">Use <a href="/docs#/Design%20Generation/generate_design_api_v1_generate_post"
             style="color:#6366f1">POST /api/v1/generate</a> to create your first design</p>
        </div>"""
    else:
        cards = ""
        for spec in specs:
            spec_id = spec.get("_id", "")
            prompt = spec.get("prompt", "No prompt")[:80]
            city = spec.get("city", "—")
            design_type = spec.get("design_type", "—")
            cost = spec.get("estimated_cost", 0)
            cost_str = f"₹{int(cost):,}" if cost else "—"
            created = spec.get("created_at")
            date_str = created.strftime("%d %b %Y, %I:%M %p") if created else "—"
            provider = spec.get("lm_provider", "—")

            # Extract URLs from spec_json metadata
            spec_json = spec.get("spec_json", {})
            metadata = spec_json.get("metadata", {}) if isinstance(spec_json, dict) else {}

            glb_url = metadata.get("export_urls", {}).get("glb") or spec.get("preview_url", "")
            stl_url = metadata.get("export_urls", {}).get("stl", "")
            step_url = metadata.get("export_urls", {}).get("step", "")
            thumbnail_url = metadata.get("meshy_thumbnail_url", "")
            video_url = metadata.get("meshy_video_url", "")
            glb_provider = metadata.get("glb_provider", "")

            # Thumbnail section
            if thumbnail_url:
                thumb_html = f"""
                <div style="position:relative">
                  <img src="{thumbnail_url}" alt="3D Preview"
                       style="width:100%;height:200px;object-fit:cover;border-radius:10px 10px 0 0;display:block"
                       onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
                  <div style="display:none;width:100%;height:200px;background:#1e293b;border-radius:10px 10px 0 0;
                              align-items:center;justify-content:center;flex-direction:column;color:#475569">
                    <div style="font-size:40px">🧊</div>
                    <div style="font-size:12px;margin-top:8px">Preview unavailable</div>
                  </div>
                  <div style="position:absolute;top:10px;right:10px;background:rgba(0,0,0,0.6);
                              color:#fff;padding:3px 8px;border-radius:12px;font-size:11px">
                    🤖 Meshy AI
                  </div>
                </div>"""
            else:
                thumb_html = f"""
                <div style="width:100%;height:200px;background:linear-gradient(135deg,#1e293b,#334155);
                            border-radius:10px 10px 0 0;display:flex;align-items:center;
                            justify-content:center;flex-direction:column;color:#475569">
                  <div style="font-size:40px">🏗️</div>
                  <div style="font-size:12px;margin-top:8px">{glb_provider or 'geometry'}</div>
                </div>"""

            # Download buttons
            def btn(url, label, color):
                if not url:
                    return ""
                return f"""<a href="{url}" download
                   style="flex:1;background:{color};color:#fff;padding:8px 4px;border-radius:7px;
                          text-decoration:none;font-size:12px;font-weight:600;text-align:center;
                          display:block">{label}</a>"""

            dl_buttons = f"""
            <div style="display:flex;gap:6px;margin-top:12px">
              {btn(glb_url, "⬇ GLB", "#6366f1")}
              {btn(stl_url, "⬇ STL", "#0891b2")}
              {btn(step_url, "⬇ STEP", "#059669")}
            </div>"""

            video_btn = ""
            if video_url:
                video_btn = f"""
                <a href="{video_url}" target="_blank"
                   style="display:block;margin-top:8px;background:#7c3aed;color:#fff;padding:8px;
                          border-radius:7px;text-decoration:none;font-size:12px;font-weight:600;
                          text-align:center">▶ View 360° Video</a>"""

            cards += f"""
            <div style="background:#fff;border-radius:12px;overflow:hidden;
                        box-shadow:0 2px 8px rgba(0,0,0,0.08);transition:transform 0.2s"
                 onmouseover="this.style.transform='translateY(-3px)'"
                 onmouseout="this.style.transform='translateY(0)'">
              {thumb_html}
              <div style="padding:16px">
                <div style="font-size:11px;color:#94a3b8;margin-bottom:6px;font-family:monospace">{spec_id}</div>
                <p style="font-size:13px;color:#334155;margin-bottom:10px;line-height:1.4">{prompt}…</p>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:11px;color:#64748b;margin-bottom:4px">
                  <span>🏙️ {city}</span>
                  <span>🏠 {design_type}</span>
                  <span>💰 {cost_str}</span>
                  <span>🤖 {provider.split("-")[0] if provider else "—"}</span>
                </div>
                <div style="font-size:10px;color:#94a3b8;margin-bottom:8px">📅 {date_str}</div>
                {dl_buttons}
                {video_btn}
              </div>
            </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Design Engine — Generated Designs</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f1f5f9; color: #1e293b; min-height: 100vh; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }}
    a[download]:hover {{ opacity: 0.88; }}
  </style>
</head>
<body>
  <div style="background:#0f172a;padding:20px 32px;display:flex;align-items:center;
              justify-content:space-between;position:sticky;top:0;z-index:10">
    <div>
      <h1 style="color:#fff;font-size:20px;font-weight:700">🏗️ Design Engine</h1>
      <p style="color:#64748b;font-size:12px;margin-top:2px">Generated Designs Gallery</p>
    </div>
    <div style="display:flex;gap:12px;align-items:center">
      <span style="background:#1e293b;color:#94a3b8;padding:6px 14px;border-radius:20px;font-size:12px">
        {len(specs)} design(s)
      </span>
      <a href="/docs" style="color:#6366f1;font-size:13px;text-decoration:none">API Docs →</a>
    </div>
  </div>

  <div style="max-width:1200px;margin:0 auto;padding:32px 24px">
    <div class="grid">
      {cards}
    </div>
  </div>
</body>
</html>"""

    return HTMLResponse(content=html)
