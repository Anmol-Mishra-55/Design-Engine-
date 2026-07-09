"""
Tests for validation/run_benchmarks.py

Covers:
  - collect_startup_metrics()
  - collect_runtime_metrics()
  - collect_api_metrics()
  - collect_replay_metrics()
  - generate_report()
  - generate_benchmark_results()

All external I/O (bucket, health checks, replay pipeline) is mocked so the
tests run offline and do not touch live services.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers — build minimal fixture data that mirrors real shapes
# ---------------------------------------------------------------------------

_FAKE_SUMMARY = {
    "generated_by": "run_production_validation.py",
    "run_at": "2026-07-09T16:11:18.931411+00:00",
    "status": "VALIDATED",
    "cities_tested": 2,
    "cases_per_city": 2,
    "total_cases": 4,
    "passed": 4,
    "failed": 0,
    "pass_rate": 100.0,
    "results_by_city": {
        "Mumbai": {
            "total": 2,
            "passed": 2,
            "failed": 0,
            "cases": [
                {
                    "spec_id": "val_mumbai_1",
                    "city": "Mumbai",
                    "prompt": "p1",
                    "status": "passed",
                    "trace_id": "t1",
                    "latency_ms": 5000.0,
                    "artifact_urls": {},
                },
                {
                    "spec_id": "val_mumbai_2",
                    "city": "Mumbai",
                    "prompt": "p2",
                    "status": "passed",
                    "trace_id": "t2",
                    "latency_ms": 4000.0,
                    "artifact_urls": {},
                },
            ],
        },
        "Pune": {
            "total": 2,
            "passed": 2,
            "failed": 0,
            "cases": [
                {
                    "spec_id": "val_pune_1",
                    "city": "Pune",
                    "prompt": "p3",
                    "status": "passed",
                    "trace_id": "t3",
                    "latency_ms": 4500.0,
                    "artifact_urls": {},
                },
                {
                    "spec_id": "val_pune_2",
                    "city": "Pune",
                    "prompt": "p4",
                    "status": "passed",
                    "trace_id": "t4",
                    "latency_ms": 3500.0,
                    "artifact_urls": {},
                },
            ],
        },
    },
}

_FAKE_DB_CHECK = {"status": "healthy", "latency_ms": 12.5}
_FAKE_REDIS_CHECK = {"status": "healthy", "latency_ms": 3.2}
_FAKE_BUCKET_CHECK = {"status": "healthy", "latency_ms": 45.0}
_FAKE_SOHUM_CHECK = {"status": "healthy", "latency_ms": 120.0}
_FAKE_RANJEET_CHECK = {"status": "healthy", "latency_ms": 130.0}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def validation_dir(tmp_path):
    """Redirect _VALIDATION_DIR to a temp directory for all write operations."""
    import validation.run_benchmarks as bm

    original = bm._VALIDATION_DIR
    bm._VALIDATION_DIR = tmp_path
    yield tmp_path
    bm._VALIDATION_DIR = original


@pytest.fixture()
def fake_summary_file(tmp_path):
    """Write a fake validation_summary.json and redirect _PROD_RESULTS."""
    import validation.run_benchmarks as bm

    summary_path = tmp_path / "validation_summary.json"
    summary_path.write_text(json.dumps(_FAKE_SUMMARY), encoding="utf-8")
    original = bm._PROD_RESULTS
    bm._PROD_RESULTS = summary_path
    yield summary_path
    bm._PROD_RESULTS = original


# ---------------------------------------------------------------------------
# TestStartupMetrics
# ---------------------------------------------------------------------------


class TestStartupMetrics:
    def test_returns_dict_with_required_keys(self, validation_dir):
        import validation.run_benchmarks as bm

        result = bm.collect_startup_metrics()
        for key in (
            "startup_duration_ms",
            "module_import_ms",
            "process_start_epoch",
            "application_ready_epoch",
            "source",
            "generated_by",
            "collected_at",
        ):
            assert key in result, f"Missing key: {key}"

    def test_startup_duration_is_positive(self, validation_dir):
        import validation.run_benchmarks as bm

        result = bm.collect_startup_metrics()
        assert result["startup_duration_ms"] >= 0

    def test_module_import_ms_is_non_negative(self, validation_dir):
        import validation.run_benchmarks as bm

        result = bm.collect_startup_metrics()
        assert result["module_import_ms"] >= 0

    def test_writes_startup_metrics_json(self, validation_dir):
        import validation.run_benchmarks as bm

        bm.collect_startup_metrics()
        assert (validation_dir / "startup_metrics.json").exists()

    def test_written_file_is_valid_json(self, validation_dir):
        import validation.run_benchmarks as bm

        bm.collect_startup_metrics()
        data = json.loads((validation_dir / "startup_metrics.json").read_text())
        assert data["generated_by"] == "run_benchmarks.py"

    def test_source_field_references_utils(self, validation_dir):
        import validation.run_benchmarks as bm

        result = bm.collect_startup_metrics()
        assert "app.utils" in result["source"]


# ---------------------------------------------------------------------------
# TestRuntimeMetrics
# ---------------------------------------------------------------------------


class TestRuntimeMetrics:
    def test_returns_dict_with_latency_block(self, validation_dir, fake_summary_file):
        import validation.run_benchmarks as bm

        result = bm.collect_runtime_metrics()
        assert "latency_ms" in result
        for key in ("mean", "median", "p95", "p99", "min", "max", "stdev"):
            assert key in result["latency_ms"], f"Missing latency key: {key}"

    def test_total_cases_matches_summary(self, validation_dir, fake_summary_file):
        import validation.run_benchmarks as bm

        result = bm.collect_runtime_metrics()
        assert result["total_cases"] == 4

    def test_pass_rate_is_100(self, validation_dir, fake_summary_file):
        import validation.run_benchmarks as bm

        result = bm.collect_runtime_metrics()
        assert result["pass_rate_pct"] == 100.0

    def test_mean_latency_is_correct(self, validation_dir, fake_summary_file):
        import validation.run_benchmarks as bm

        result = bm.collect_runtime_metrics()
        # latencies: 5000, 4000, 4500, 3500 → mean = 4250
        assert result["latency_ms"]["mean"] == 4250.0

    def test_min_max_latency(self, validation_dir, fake_summary_file):
        import validation.run_benchmarks as bm

        result = bm.collect_runtime_metrics()
        assert result["latency_ms"]["min"] == 3500.0
        assert result["latency_ms"]["max"] == 5000.0

    def test_by_city_contains_both_cities(self, validation_dir, fake_summary_file):
        import validation.run_benchmarks as bm

        result = bm.collect_runtime_metrics()
        assert "Mumbai" in result["by_city"]
        assert "Pune" in result["by_city"]

    def test_writes_runtime_metrics_json(self, validation_dir, fake_summary_file):
        import validation.run_benchmarks as bm

        bm.collect_runtime_metrics()
        assert (validation_dir / "runtime_metrics.json").exists()

    def test_raises_if_summary_missing(self, validation_dir):
        import validation.run_benchmarks as bm

        original = bm._PROD_RESULTS
        bm._PROD_RESULTS = Path("/nonexistent/validation_summary.json")
        try:
            with pytest.raises(FileNotFoundError):
                bm.collect_runtime_metrics()
        finally:
            bm._PROD_RESULTS = original

    def test_source_field_references_validation_summary(self, validation_dir, fake_summary_file):
        import validation.run_benchmarks as bm

        result = bm.collect_runtime_metrics()
        assert "validation_summary" in result["source"]


# ---------------------------------------------------------------------------
# TestApiMetrics
# ---------------------------------------------------------------------------


class TestApiMetrics:
    def _patch_health(self):
        return patch.multiple(
            "validation.run_benchmarks",
            **{},  # module-level patches applied below
        )

    def test_returns_dict_with_components(self, validation_dir):
        import validation.run_benchmarks as bm

        with (
            patch("app.api.health._check_redis", new=AsyncMock(return_value=_FAKE_REDIS_CHECK)),
            patch("app.api.health._check_bucket", new=AsyncMock(return_value=_FAKE_BUCKET_CHECK)),
            patch("app.api.health._check_external_service", new=AsyncMock(return_value=_FAKE_SOHUM_CHECK)),
            patch("app.database_mongodb.check_db_connection", new=AsyncMock(return_value=_FAKE_DB_CHECK)),
        ):
            result = bm.collect_api_metrics()
        assert "components" in result
        assert "external_services" in result

    def test_components_contain_database_redis_bucket(self, validation_dir):
        import validation.run_benchmarks as bm

        with (
            patch("app.api.health._check_redis", new=AsyncMock(return_value=_FAKE_REDIS_CHECK)),
            patch("app.api.health._check_bucket", new=AsyncMock(return_value=_FAKE_BUCKET_CHECK)),
            patch("app.api.health._check_external_service", new=AsyncMock(return_value=_FAKE_SOHUM_CHECK)),
            patch("app.database_mongodb.check_db_connection", new=AsyncMock(return_value=_FAKE_DB_CHECK)),
        ):
            result = bm.collect_api_metrics()
        for key in ("database", "redis", "bucket"):
            assert key in result["components"], f"Missing component: {key}"

    def test_external_services_contain_sohum_ranjeet(self, validation_dir):
        import validation.run_benchmarks as bm

        with (
            patch("app.api.health._check_redis", new=AsyncMock(return_value=_FAKE_REDIS_CHECK)),
            patch("app.api.health._check_bucket", new=AsyncMock(return_value=_FAKE_BUCKET_CHECK)),
            patch("app.api.health._check_external_service", new=AsyncMock(return_value=_FAKE_SOHUM_CHECK)),
            patch("app.database_mongodb.check_db_connection", new=AsyncMock(return_value=_FAKE_DB_CHECK)),
        ):
            result = bm.collect_api_metrics()
        for key in ("sohum_mcp", "ranjeet_rl"):
            assert key in result["external_services"], f"Missing service: {key}"

    def test_total_health_check_ms_is_present(self, validation_dir):
        import validation.run_benchmarks as bm

        with (
            patch("app.api.health._check_redis", new=AsyncMock(return_value=_FAKE_REDIS_CHECK)),
            patch("app.api.health._check_bucket", new=AsyncMock(return_value=_FAKE_BUCKET_CHECK)),
            patch("app.api.health._check_external_service", new=AsyncMock(return_value=_FAKE_SOHUM_CHECK)),
            patch("app.database_mongodb.check_db_connection", new=AsyncMock(return_value=_FAKE_DB_CHECK)),
        ):
            result = bm.collect_api_metrics()
        assert "total_health_check_ms" in result
        assert result["total_health_check_ms"] >= 0

    def test_writes_api_latency_json(self, validation_dir):
        import validation.run_benchmarks as bm

        with (
            patch("app.api.health._check_redis", new=AsyncMock(return_value=_FAKE_REDIS_CHECK)),
            patch("app.api.health._check_bucket", new=AsyncMock(return_value=_FAKE_BUCKET_CHECK)),
            patch("app.api.health._check_external_service", new=AsyncMock(return_value=_FAKE_SOHUM_CHECK)),
            patch("app.database_mongodb.check_db_connection", new=AsyncMock(return_value=_FAKE_DB_CHECK)),
        ):
            bm.collect_api_metrics()
        assert (validation_dir / "api_latency.json").exists()

    def test_written_file_is_valid_json(self, validation_dir):
        import validation.run_benchmarks as bm

        with (
            patch("app.api.health._check_redis", new=AsyncMock(return_value=_FAKE_REDIS_CHECK)),
            patch("app.api.health._check_bucket", new=AsyncMock(return_value=_FAKE_BUCKET_CHECK)),
            patch("app.api.health._check_external_service", new=AsyncMock(return_value=_FAKE_SOHUM_CHECK)),
            patch("app.database_mongodb.check_db_connection", new=AsyncMock(return_value=_FAKE_DB_CHECK)),
        ):
            bm.collect_api_metrics()
        data = json.loads((validation_dir / "api_latency.json").read_text())
        assert data["generated_by"] == "run_benchmarks.py"


# ---------------------------------------------------------------------------
# TestReplayMetrics
# ---------------------------------------------------------------------------

_FAKE_REPLAY_RESULT = MagicMock()
_FAKE_REPLAY_RESULT.replay_spec_id = "replay_spec_abc_12345678"
_FAKE_REPLAY_RESULT.status = "success"
_FAKE_REPLAY_RESULT.artifacts = {"glb": "https://example.com/glb", "stl": "https://example.com/stl"}
_FAKE_REPLAY_RESULT.error = None


class TestReplayMetrics:
    def test_returns_dict_with_replay_duration(self, validation_dir):
        import validation.run_benchmarks as bm

        with (
            patch("app.replay.replay_service.ReplayService.list_replayable_specs", return_value=["spec_6547c732a587"]),
            patch("app.replay.replay_service.ReplayService.replay", new=AsyncMock(return_value=_FAKE_REPLAY_RESULT)),
            patch("app.storage.upload_to_bucket", new=AsyncMock(return_value="https://example.com/artifact")),
        ):
            result = bm.collect_replay_metrics()
        assert "replay_duration_ms" in result
        assert result["replay_duration_ms"] >= 0

    def test_status_is_success(self, validation_dir):
        import validation.run_benchmarks as bm

        with (
            patch("app.replay.replay_service.ReplayService.list_replayable_specs", return_value=["spec_6547c732a587"]),
            patch("app.replay.replay_service.ReplayService.replay", new=AsyncMock(return_value=_FAKE_REPLAY_RESULT)),
            patch("app.storage.upload_to_bucket", new=AsyncMock(return_value="https://example.com/artifact")),
        ):
            result = bm.collect_replay_metrics()
        assert result["status"] == "success"

    def test_skipped_when_no_replayable_specs(self, validation_dir):
        import validation.run_benchmarks as bm

        with patch("app.replay.replay_service.ReplayService.list_replayable_specs", return_value=[]):
            result = bm.collect_replay_metrics()
        assert result["status"] == "skipped"
        assert "reason" in result

    def test_writes_replay_metrics_json(self, validation_dir):
        import validation.run_benchmarks as bm

        with (
            patch("app.replay.replay_service.ReplayService.list_replayable_specs", return_value=["spec_6547c732a587"]),
            patch("app.replay.replay_service.ReplayService.replay", new=AsyncMock(return_value=_FAKE_REPLAY_RESULT)),
            patch("app.storage.upload_to_bucket", new=AsyncMock(return_value="https://example.com/artifact")),
        ):
            bm.collect_replay_metrics()
        assert (validation_dir / "replay_metrics.json").exists()

    def test_written_file_is_valid_json(self, validation_dir):
        import validation.run_benchmarks as bm

        with (
            patch("app.replay.replay_service.ReplayService.list_replayable_specs", return_value=["spec_6547c732a587"]),
            patch("app.replay.replay_service.ReplayService.replay", new=AsyncMock(return_value=_FAKE_REPLAY_RESULT)),
            patch("app.storage.upload_to_bucket", new=AsyncMock(return_value="https://example.com/artifact")),
        ):
            bm.collect_replay_metrics()
        data = json.loads((validation_dir / "replay_metrics.json").read_text())
        assert data["generated_by"] == "run_benchmarks.py"

    def test_original_spec_id_recorded(self, validation_dir):
        import validation.run_benchmarks as bm

        with (
            patch("app.replay.replay_service.ReplayService.list_replayable_specs", return_value=["spec_6547c732a587"]),
            patch("app.replay.replay_service.ReplayService.replay", new=AsyncMock(return_value=_FAKE_REPLAY_RESULT)),
            patch("app.storage.upload_to_bucket", new=AsyncMock(return_value="https://example.com/artifact")),
        ):
            result = bm.collect_replay_metrics()
        assert result["original_spec_id"] == "spec_6547c732a587"


# ---------------------------------------------------------------------------
# TestReportGeneration
# ---------------------------------------------------------------------------

_STARTUP = {
    "generated_by": "run_benchmarks.py",
    "collected_at": "2026-07-09T16:00:00+00:00",
    "startup_duration_ms": 850.0,
    "module_import_ms": 12.3,
    "process_start_epoch": 1720540800.0,
    "application_ready_epoch": 1720540800.85,
    "source": "app.utils.START_TIME",
}
_RUNTIME = {
    "generated_by": "run_benchmarks.py",
    "collected_at": "2026-07-09T16:00:00+00:00",
    "source": "production_validation_results/validation_summary.json",
    "validation_run_at": "2026-07-09T16:11:18.931411+00:00",
    "total_cases": 20,
    "pass_rate_pct": 100.0,
    "latency_ms": {
        "mean": 4900.0,
        "median": 4807.0,
        "p95": 5685.7,
        "p99": 5944.0,
        "min": 4294.9,
        "max": 5944.0,
        "stdev": 380.0,
    },
    "by_city": {
        "Mumbai": {"count": 5, "mean_ms": 5143.9, "min_ms": 4779.4, "max_ms": 5343.4},
        "Pune": {"count": 5, "mean_ms": 4635.3, "min_ms": 4382.3, "max_ms": 4807.3},
    },
}
_API = {
    "generated_by": "run_benchmarks.py",
    "collected_at": "2026-07-09T16:00:00+00:00",
    "total_health_check_ms": 210.5,
    "components": {
        "database": {"status": "healthy", "latency_ms": 12.5},
        "redis": {"status": "healthy", "latency_ms": 3.2},
        "bucket": {"status": "healthy", "latency_ms": 45.0},
    },
    "external_services": {
        "sohum_mcp": {"status": "healthy", "latency_ms": 120.0},
        "ranjeet_rl": {"status": "healthy", "latency_ms": 130.0},
    },
}
_REPLAY = {
    "generated_by": "run_benchmarks.py",
    "collected_at": "2026-07-09T16:00:00+00:00",
    "original_spec_id": "spec_6547c732a587",
    "replay_spec_id": "replay_spec_6547c7_abcd1234",
    "status": "success",
    "replay_duration_ms": 4950.0,
    "artifacts_produced": ["glb", "stl", "step", "spec"],
    "error": None,
}


class TestReportGeneration:
    def test_report_is_string(self, validation_dir):
        import validation.run_benchmarks as bm

        report = bm.generate_report(_STARTUP, _RUNTIME, _API, _REPLAY)
        assert isinstance(report, str)
        assert len(report) > 100

    def test_report_contains_startup_section(self, validation_dir):
        import validation.run_benchmarks as bm

        report = bm.generate_report(_STARTUP, _RUNTIME, _API, _REPLAY)
        assert "Startup" in report
        assert "850.0" in report

    def test_report_contains_runtime_section(self, validation_dir):
        import validation.run_benchmarks as bm

        report = bm.generate_report(_STARTUP, _RUNTIME, _API, _REPLAY)
        assert "Runtime" in report
        assert "4900.0" in report  # mean

    def test_report_contains_p95(self, validation_dir):
        import validation.run_benchmarks as bm

        report = bm.generate_report(_STARTUP, _RUNTIME, _API, _REPLAY)
        assert "5685.7" in report  # p95

    def test_report_contains_health_section(self, validation_dir):
        import validation.run_benchmarks as bm

        report = bm.generate_report(_STARTUP, _RUNTIME, _API, _REPLAY)
        assert "Health" in report
        assert "210.5" in report

    def test_report_contains_replay_section(self, validation_dir):
        import validation.run_benchmarks as bm

        report = bm.generate_report(_STARTUP, _RUNTIME, _API, _REPLAY)
        assert "Replay" in report
        assert "4950.0" in report

    def test_report_contains_pass_rate(self, validation_dir):
        import validation.run_benchmarks as bm

        report = bm.generate_report(_STARTUP, _RUNTIME, _API, _REPLAY)
        assert "100.0" in report

    def test_report_contains_verdict(self, validation_dir):
        import validation.run_benchmarks as bm

        report = bm.generate_report(_STARTUP, _RUNTIME, _API, _REPLAY)
        assert "PRODUCTION READY" in report

    def test_writes_benchmark_report_md(self, validation_dir):
        import validation.run_benchmarks as bm

        bm.generate_report(_STARTUP, _RUNTIME, _API, _REPLAY)
        assert (validation_dir / "benchmark_report.md").exists()

    def test_written_report_is_markdown(self, validation_dir):
        import validation.run_benchmarks as bm

        bm.generate_report(_STARTUP, _RUNTIME, _API, _REPLAY)
        content = (validation_dir / "benchmark_report.md").read_text(encoding="utf-8")
        assert content.startswith("# Production Benchmark Report")


# ---------------------------------------------------------------------------
# TestBenchmarkResults
# ---------------------------------------------------------------------------


class TestBenchmarkResults:
    def test_writes_benchmark_results_json(self, validation_dir):
        import validation.run_benchmarks as bm

        bm.generate_benchmark_results(_STARTUP, _RUNTIME, _API, _REPLAY)
        assert (validation_dir / "benchmark_results.json").exists()

    def test_consolidated_file_contains_all_sections(self, validation_dir):
        import validation.run_benchmarks as bm

        bm.generate_benchmark_results(_STARTUP, _RUNTIME, _API, _REPLAY)
        data = json.loads((validation_dir / "benchmark_results.json").read_text())
        for key in ("startup", "runtime", "api_latency", "replay", "generated_by", "collected_at"):
            assert key in data, f"Missing key: {key}"

    def test_startup_section_preserved(self, validation_dir):
        import validation.run_benchmarks as bm

        bm.generate_benchmark_results(_STARTUP, _RUNTIME, _API, _REPLAY)
        data = json.loads((validation_dir / "benchmark_results.json").read_text())
        assert data["startup"]["startup_duration_ms"] == 850.0

    def test_runtime_section_preserved(self, validation_dir):
        import validation.run_benchmarks as bm

        bm.generate_benchmark_results(_STARTUP, _RUNTIME, _API, _REPLAY)
        data = json.loads((validation_dir / "benchmark_results.json").read_text())
        assert data["runtime"]["pass_rate_pct"] == 100.0

    def test_replay_section_preserved(self, validation_dir):
        import validation.run_benchmarks as bm

        bm.generate_benchmark_results(_STARTUP, _RUNTIME, _API, _REPLAY)
        data = json.loads((validation_dir / "benchmark_results.json").read_text())
        assert data["replay"]["replay_duration_ms"] == 4950.0

    def test_generated_by_field(self, validation_dir):
        import validation.run_benchmarks as bm

        result = bm.generate_benchmark_results(_STARTUP, _RUNTIME, _API, _REPLAY)
        assert result["generated_by"] == "run_benchmarks.py"
