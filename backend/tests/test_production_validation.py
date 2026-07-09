"""
Tests for Task 3 — Production Validation Framework.
Verifies validation_summary.json structure, completeness, and report generation.
"""
import asyncio
import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

SUMMARY_PATH = Path(__file__).resolve().parents[1] / "production_validation_results" / "validation_summary.json"
README_PATH = Path(__file__).resolve().parents[1] / "production_validation_results" / "README.md"
EXPECTED_CITIES = {"Mumbai", "Pune", "Ahmedabad", "Nashik"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def summary() -> dict:
    assert SUMMARY_PATH.exists(), f"validation_summary.json not found at {SUMMARY_PATH}"
    with open(SUMMARY_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Summary file existence and provenance
# ---------------------------------------------------------------------------


class TestSummaryFile:
    def test_summary_exists(self):
        assert SUMMARY_PATH.exists(), "validation_summary.json must exist"

    def test_generated_by_runner(self, summary):
        assert summary.get("generated_by") == "run_production_validation.py"

    def test_run_at_is_iso_timestamp(self, summary):
        from datetime import datetime

        ts = summary.get("run_at", "")
        assert ts, "run_at must be present"
        datetime.fromisoformat(ts)  # raises if invalid

    def test_status_is_validated(self, summary):
        assert summary.get("status") == "VALIDATED"

    def test_pass_rate_is_100(self, summary):
        assert summary.get("pass_rate") == 100.0


# ---------------------------------------------------------------------------
# Case counts
# ---------------------------------------------------------------------------


class TestCaseCounts:
    def test_cities_tested(self, summary):
        assert summary.get("cities_tested") == 4

    def test_cases_per_city(self, summary):
        assert summary.get("cases_per_city") == 5

    def test_total_cases(self, summary):
        assert summary.get("total_cases") == 20

    def test_passed_count(self, summary):
        assert summary.get("passed") == 20

    def test_failed_count(self, summary):
        assert summary.get("failed") == 0

    def test_passed_plus_failed_equals_total(self, summary):
        assert summary["passed"] + summary["failed"] == summary["total_cases"]


# ---------------------------------------------------------------------------
# City coverage
# ---------------------------------------------------------------------------


class TestCityCoverage:
    def test_all_cities_present(self, summary):
        cities = set(summary.get("results_by_city", {}).keys())
        assert cities == EXPECTED_CITIES

    def test_each_city_has_5_cases(self, summary):
        for city, data in summary["results_by_city"].items():
            assert data["total"] == 5, f"{city} should have 5 cases"

    def test_each_city_all_passed(self, summary):
        for city, data in summary["results_by_city"].items():
            assert data["passed"] == 5, f"{city} should have 5 passed"

    def test_each_city_zero_failed(self, summary):
        for city, data in summary["results_by_city"].items():
            assert data["failed"] == 0, f"{city} should have 0 failed"


# ---------------------------------------------------------------------------
# Per-case record fields
# ---------------------------------------------------------------------------


class TestCaseRecords:
    def _all_cases(self, summary):
        for city_data in summary["results_by_city"].values():
            yield from city_data["cases"]

    def test_every_case_has_spec_id(self, summary):
        for r in self._all_cases(summary):
            assert r.get("spec_id"), f"Missing spec_id in {r}"

    def test_every_case_has_trace_id(self, summary):
        for r in self._all_cases(summary):
            assert r.get("trace_id"), f"Missing trace_id in {r}"

    def test_every_case_has_latency(self, summary):
        for r in self._all_cases(summary):
            assert r.get("latency_ms", 0) > 0, f"latency_ms must be > 0 in {r}"

    def test_every_case_has_artifact_urls(self, summary):
        for r in self._all_cases(summary):
            assert r.get("artifact_urls"), f"Missing artifact_urls in {r}"

    def test_every_case_status_passed(self, summary):
        for r in self._all_cases(summary):
            assert r["status"] == "passed", f"Expected passed, got {r['status']} in {r['spec_id']}"

    def test_spec_ids_are_unique(self, summary):
        ids = [r["spec_id"] for city_data in summary["results_by_city"].values() for r in city_data["cases"]]
        assert len(ids) == len(set(ids)), "spec_ids must be unique"

    def test_trace_ids_are_unique(self, summary):
        ids = [r["trace_id"] for city_data in summary["results_by_city"].values() for r in city_data["cases"]]
        assert len(ids) == len(set(ids)), "trace_ids must be unique"

    def test_artifact_urls_contain_glb(self, summary):
        for r in self._all_cases(summary):
            assert "glb" in r["artifact_urls"], f"Missing glb artifact in {r['spec_id']}"

    def test_no_fake_data_markers(self, summary):
        raw = json.dumps(summary)
        for marker in ["fake", "mock_data", "hand_written", "placeholder_result"]:
            assert marker not in raw.lower(), f"Found fake data marker '{marker}' in summary"


# ---------------------------------------------------------------------------
# README status
# ---------------------------------------------------------------------------


class TestReadmeStatus:
    def test_readme_exists(self):
        assert README_PATH.exists()

    def test_readme_shows_validated(self):
        content = README_PATH.read_text(encoding="utf-8")
        assert "VALIDATED" in content, "README must show VALIDATED status"

    def test_readme_not_not_validated(self):
        content = README_PATH.read_text(encoding="utf-8")
        assert "NOT VALIDATED" not in content, "README must not still say NOT VALIDATED"


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------


class TestReportGenerator:
    def test_report_txt_exists(self):
        report_path = SUMMARY_PATH.parent / "REPORT.txt"
        assert report_path.exists(), "REPORT.txt must exist after generate_validation_report.py runs"

    def test_report_contains_validated_status(self):
        report_path = SUMMARY_PATH.parent / "REPORT.txt"
        content = report_path.read_text(encoding="utf-8")
        assert "VALIDATED" in content

    def test_report_contains_all_cities(self):
        report_path = SUMMARY_PATH.parent / "REPORT.txt"
        content = report_path.read_text(encoding="utf-8")
        for city in EXPECTED_CITIES:
            assert city in content, f"{city} missing from REPORT.txt"

    def test_generate_report_function(self):
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from generate_validation_report import generate_report, load_validation_data

        data = load_validation_data()
        report = generate_report(data)
        assert "PRODUCTION VALIDATION REPORT" in report
        assert "VALIDATED" in report
        assert "20" in report  # total cases

    def test_load_rejects_hand_written_summary(self, tmp_path):
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import generate_validation_report as grv

        fake = tmp_path / "validation_summary.json"
        fake.write_text(json.dumps({"generated_by": "hand_written", "status": "VALIDATED"}))
        orig = grv.SUMMARY_FILE
        grv.SUMMARY_FILE = fake
        try:
            with pytest.raises(SystemExit):
                grv.load_validation_data()
        finally:
            grv.SUMMARY_FILE = orig


# ---------------------------------------------------------------------------
# _run_case unit test (mocked pipeline)
# ---------------------------------------------------------------------------


class TestRunCase:
    def test_run_case_returns_passed_on_success(self):
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

        mock_result = MagicMock()
        mock_result.bucket_trace_id = f"core_bucket_test_{uuid.uuid4().hex[:8]}"
        mock_result.artifacts = {
            "glb": MagicMock(url="https://bucket/test.glb"),
            "stl": MagicMock(url="https://bucket/test.stl"),
        }

        async def _fake_execute(self_orch, spec_id, payload):
            return mock_result

        with patch("app.core_bucket_pipeline.CoreBucketCanonicalOrchestrator.execute", new=_fake_execute), patch(
            "app.storage.upload_to_bucket", new=AsyncMock(return_value="https://bucket/x")
        ):
            from run_production_validation import _run_case

            record = asyncio.run(_run_case("Mumbai", "Design a 3BHK apartment", 1))

        assert record["status"] == "passed"
        assert record["trace_id"] == mock_result.bucket_trace_id
        assert record["latency_ms"] > 0
        assert "glb" in record["artifact_urls"]

    def test_run_case_returns_failed_on_exception(self):
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

        async def _raise(self_orch, spec_id, payload):
            raise RuntimeError("pipeline exploded")

        with patch("app.core_bucket_pipeline.CoreBucketCanonicalOrchestrator.execute", new=_raise), patch(
            "app.storage.upload_to_bucket", new=AsyncMock(return_value="https://bucket/x")
        ):
            from run_production_validation import _run_case

            record = asyncio.run(_run_case("Mumbai", "Design a 3BHK apartment", 1))

        assert record["status"] == "failed"
        assert "pipeline exploded" in record.get("error", "")
        assert record["trace_id"] == ""
