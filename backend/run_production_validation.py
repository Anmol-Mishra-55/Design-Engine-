"""
Production Validation - Multi-City Full Flow
Calls CoreBucketCanonicalOrchestrator directly — no live server required.
Mocks bucket storage so the pipeline runs offline.
"""
import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

OUTPUT_DIR = Path("production_validation_results")

TEST_CASES = {
    "Mumbai": [
        "Design a 3BHK apartment with modern kitchen",
        "Create a commercial office space with parking",
        "Design a residential building with 4 floors",
        "Build a luxury penthouse with terrace",
        "Design a compact studio apartment",
    ],
    "Pune": [
        "Design a residential villa with garden and parking for 2 cars",
        "Create a tech office with open workspace",
        "Design a row house with 3 bedrooms",
        "Build a duplex with rooftop access",
        "Design a bungalow with swimming pool",
    ],
    "Ahmedabad": [
        "Design a traditional house with courtyard",
        "Create a commercial complex with shops",
        "Design a residential tower with amenities",
        "Build a warehouse with loading dock",
        "Design a farmhouse with guest rooms",
    ],
    "Nashik": [
        "Design a vineyard resort with cottages",
        "Create a residential colony layout",
        "Design a temple complex with halls",
        "Build a school building with playground",
        "Design a hospital with emergency wing",
    ],
}


def _mock_bucket_url(bucket: str, path: str, *args, **kwargs) -> str:
    return f"https://bhiv-bucket.onrender.com/bucket/artifact/{uuid.uuid4()}"


async def _run_case(city: str, prompt: str, case_index: int) -> dict:
    spec_id = f"val_{city.lower()}_{case_index}_{uuid.uuid4().hex[:8]}"
    payload = {
        "prompt": prompt,
        "city": city,
        "style": "modern",
        "user_id": "validation_runner",
        "constraints": {},
        "context": {},
    }

    start = time.monotonic()
    status = "failed"
    error = None
    trace_id = None
    artifact_urls = {}

    try:
        import app.core_bucket_pipeline as _pipeline_mod
        from app.core_bucket_pipeline import CoreBucketCanonicalOrchestrator

        orchestrator = CoreBucketCanonicalOrchestrator()
        # Blank AI keys at the module level so _generate_glb skips Meshy/Tripo
        with patch.object(_pipeline_mod.settings, "MESHY_API_KEY", "", create=True), patch(
            "app.storage.upload_to_bucket", new=AsyncMock(side_effect=_mock_bucket_url)
        ):
            result = await orchestrator.execute(spec_id, payload)

        trace_id = result.bucket_trace_id
        artifact_urls = {kind: loc.url for kind, loc in result.artifacts.items()}
        status = "passed"
    except Exception as exc:
        error = str(exc)

    latency_ms = round((time.monotonic() - start) * 1000, 1)

    record = {
        "spec_id": spec_id,
        "city": city,
        "prompt": prompt,
        "status": status,
        "trace_id": trace_id or "",
        "latency_ms": latency_ms,
        "artifact_urls": artifact_urls,
    }
    if error:
        record["error"] = error
    return record


async def _run_all() -> dict:
    (OUTPUT_DIR / "responses").mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "logs").mkdir(parents=True, exist_ok=True)

    all_results = []
    results_by_city = {}

    total = sum(len(v) for v in TEST_CASES.values())
    current = 0

    for city, prompts in TEST_CASES.items():
        city_results = []
        print(f"\n{'='*60}\nTESTING: {city.upper()}\n{'='*60}")

        for i, prompt in enumerate(prompts, 1):
            current += 1
            print(f"[{current}/{total}] {city} case {i}: {prompt[:55]}...")
            record = await _run_case(city, prompt, i)
            city_results.append(record)
            all_results.append(record)
            print(
                f"  > {record['status'].upper()}  {record['latency_ms']}ms  trace={record['trace_id'][:30] if record['trace_id'] else 'none'}"
            )

        passed = sum(1 for r in city_results if r["status"] == "passed")
        results_by_city[city] = {
            "total": len(city_results),
            "passed": passed,
            "failed": len(city_results) - passed,
            "cases": city_results,
        }

    passed_total = sum(1 for r in all_results if r["status"] == "passed")
    failed_total = len(all_results) - passed_total
    overall_status = "VALIDATED" if passed_total == len(all_results) else ("PARTIAL" if passed_total > 0 else "FAILED")

    summary = {
        "generated_by": "run_production_validation.py",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "status": overall_status,
        "cities_tested": len(TEST_CASES),
        "cases_per_city": 5,
        "total_cases": total,
        "passed": passed_total,
        "failed": failed_total,
        "pass_rate": round(passed_total / total * 100, 1),
        "results_by_city": results_by_city,
    }

    summary_path = OUTPUT_DIR / "validation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"VALIDATION COMPLETE: {overall_status}")
    print(f"Passed: {passed_total}/{total}  ({summary['pass_rate']}%)")
    print(f"Summary: {summary_path}")

    return summary


def main():
    print("=" * 60)
    print("PRODUCTION VALIDATION — MULTI-CITY FULL FLOW")
    print("=" * 60)
    summary = asyncio.run(_run_all())
    return 0 if summary["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    sys.exit(main())
