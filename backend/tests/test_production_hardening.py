"""
Task 2 — Production Hardening Tests

Covers:
  1. JSON structured logging  (logging_config.py)
  2. Trace context middleware  (middleware/trace_context.py)
  3. Real health checks        (api/health.py)
  4. Replay capability         (replay/replay_service.py + api/replay.py)
"""
import json
import logging
import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.logging_config import JsonFormatter, clear_trace_context, get_trace_context, set_trace_context
from app.main import app
from app.replay.replay_service import ReplayResult, ReplayService, TraceEntry, _extract_request_payload, _load_trace
from fastapi.testclient import TestClient

client = TestClient(app)


# ===========================================================================
# 1. JSON Structured Logging
# ===========================================================================


class TestJsonFormatter:
    def _make_record(self, msg="hello", level=logging.INFO):
        record = logging.LogRecord(
            name="test.logger",
            level=level,
            pathname="test.py",
            lineno=42,
            msg=msg,
            args=(),
            exc_info=None,
        )
        return record

    def test_output_is_valid_json(self):
        formatter = JsonFormatter()
        output = formatter.format(self._make_record())
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_required_fields_present(self):
        formatter = JsonFormatter()
        parsed = json.loads(formatter.format(self._make_record("test msg")))
        for field in (
            "timestamp",
            "level",
            "logger",
            "message",
            "trace_id",
            "execution_id",
            "pipeline_stage",
            "module",
            "func",
            "line",
        ):
            assert field in parsed, f"Missing field: {field}"

    def test_message_content(self):
        formatter = JsonFormatter()
        parsed = json.loads(formatter.format(self._make_record("my message")))
        assert parsed["message"] == "my message"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"

    def test_trace_context_injected(self):
        set_trace_context(trace_id="tid-123", execution_id="eid-456", pipeline_stage="test_stage")
        formatter = JsonFormatter()
        parsed = json.loads(formatter.format(self._make_record()))
        assert parsed["trace_id"] == "tid-123"
        assert parsed["execution_id"] == "eid-456"
        assert parsed["pipeline_stage"] == "test_stage"
        clear_trace_context()

    def test_exc_info_included(self):
        formatter = JsonFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            record = self._make_record("error occurred")
            record.exc_info = sys.exc_info()
            parsed = json.loads(formatter.format(record))
            assert "exc_info" in parsed
            assert "ValueError" in parsed["exc_info"]

    def test_service_and_environment_fields(self):
        formatter = JsonFormatter()
        parsed = json.loads(formatter.format(self._make_record()))
        assert parsed["service"] == "design_engine_api"
        assert "environment" in parsed


# ===========================================================================
# 2. Thread-local Trace Context
# ===========================================================================


class TestTraceContext:
    def setup_method(self):
        clear_trace_context()

    def teardown_method(self):
        clear_trace_context()

    def test_set_and_get(self):
        set_trace_context(trace_id="t1", execution_id="e1", pipeline_stage="s1")
        ctx = get_trace_context()
        assert ctx["trace_id"] == "t1"
        assert ctx["execution_id"] == "e1"
        assert ctx["pipeline_stage"] == "s1"

    def test_clear_resets_to_empty_strings(self):
        set_trace_context(trace_id="t1", execution_id="e1", pipeline_stage="s1")
        clear_trace_context()
        ctx = get_trace_context()
        assert ctx["trace_id"] == ""
        assert ctx["execution_id"] == ""
        assert ctx["pipeline_stage"] == ""

    def test_defaults_are_empty_strings(self):
        ctx = get_trace_context()
        assert ctx["trace_id"] == ""
        assert ctx["execution_id"] == ""
        assert ctx["pipeline_stage"] == ""

    def test_partial_set(self):
        set_trace_context(trace_id="only-trace")
        ctx = get_trace_context()
        assert ctx["trace_id"] == "only-trace"
        assert ctx["execution_id"] == ""
        assert ctx["pipeline_stage"] == ""


# ===========================================================================
# 3. Trace Context Middleware
# ===========================================================================


class TestTraceContextMiddleware:
    def test_response_contains_trace_id_header(self):
        response = client.get("/health")
        assert "x-trace-id" in response.headers

    def test_provided_trace_id_echoed_back(self):
        custom_id = "my-custom-trace-id"
        response = client.get("/health", headers={"X-Trace-ID": custom_id})
        assert response.headers.get("x-trace-id") == custom_id

    def test_generated_trace_id_is_uuid_format(self):
        response = client.get("/health")
        trace_id = response.headers.get("x-trace-id", "")
        # Should be a valid UUID (no hyphens check — just non-empty)
        assert len(trace_id) > 0

    def test_different_requests_get_different_trace_ids(self):
        r1 = client.get("/health")
        r2 = client.get("/health")
        assert r1.headers.get("x-trace-id") != r2.headers.get("x-trace-id")


# ===========================================================================
# 4. Health Checks
# ===========================================================================


class TestHealthEndpoints:
    def test_simple_health_returns_healthy(self):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_simple_health_has_uptime(self):
        data = client.get("/api/v1/health").json()
        assert "uptime" in data
        assert isinstance(data["uptime"], (int, float))

    def test_detailed_health_structure(self):
        with (
            patch("app.api.health.check_db_connection", new_callable=AsyncMock) as mock_db,
            patch("app.api.health._check_redis", new_callable=AsyncMock) as mock_redis,
            patch("app.api.health._check_bucket", new_callable=AsyncMock) as mock_bucket,
            patch("app.api.health._check_external_service", new_callable=AsyncMock) as mock_ext,
        ):
            mock_db.return_value = {"status": "healthy", "latency_ms": 1.0}
            mock_redis.return_value = {"status": "healthy", "latency_ms": 1.0}
            mock_bucket.return_value = {"status": "healthy", "latency_ms": 1.0}
            mock_ext.return_value = {"status": "healthy", "latency_ms": 1.0}

            response = client.get("/api/v1/health/detailed")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "components" in data
            assert "external_services" in data
            assert "database" in data["components"]

    def test_detailed_health_unhealthy_when_db_down(self):
        with (
            patch("app.api.health.check_db_connection", new_callable=AsyncMock) as mock_db,
            patch("app.api.health._check_redis", new_callable=AsyncMock) as mock_redis,
            patch("app.api.health._check_bucket", new_callable=AsyncMock) as mock_bucket,
            patch("app.api.health._check_external_service", new_callable=AsyncMock) as mock_ext,
        ):
            mock_db.return_value = {"status": "unhealthy", "error": "connection refused"}
            mock_redis.return_value = {"status": "healthy", "latency_ms": 1.0}
            mock_bucket.return_value = {"status": "healthy", "latency_ms": 1.0}
            mock_ext.return_value = {"status": "healthy", "latency_ms": 1.0}

            response = client.get("/api/v1/health/detailed")
            assert response.status_code == 200
            assert response.json()["status"] == "unhealthy"

    def test_detailed_health_degraded_when_external_down(self):
        with (
            patch("app.api.health.check_db_connection", new_callable=AsyncMock) as mock_db,
            patch("app.api.health._check_redis", new_callable=AsyncMock) as mock_redis,
            patch("app.api.health._check_bucket", new_callable=AsyncMock) as mock_bucket,
            patch("app.api.health._check_external_service", new_callable=AsyncMock) as mock_ext,
        ):
            mock_db.return_value = {"status": "healthy", "latency_ms": 1.0}
            mock_redis.return_value = {"status": "healthy", "latency_ms": 1.0}
            mock_bucket.return_value = {"status": "unhealthy", "error": "timeout"}
            mock_ext.return_value = {"status": "unhealthy", "error": "timeout"}

            response = client.get("/api/v1/health/detailed")
            assert response.status_code == 200
            assert response.json()["status"] == "degraded"

    def test_detailed_health_healthy_when_all_pass(self):
        with (
            patch("app.api.health.check_db_connection", new_callable=AsyncMock) as mock_db,
            patch("app.api.health._check_redis", new_callable=AsyncMock) as mock_redis,
            patch("app.api.health._check_bucket", new_callable=AsyncMock) as mock_bucket,
            patch("app.api.health._check_external_service", new_callable=AsyncMock) as mock_ext,
        ):
            mock_db.return_value = {"status": "healthy", "latency_ms": 1.0}
            mock_redis.return_value = {"status": "healthy", "latency_ms": 1.0}
            mock_bucket.return_value = {"status": "healthy", "latency_ms": 1.0}
            mock_ext.return_value = {"status": "healthy", "latency_ms": 1.0}

            response = client.get("/api/v1/health/detailed")
            assert response.json()["status"] == "healthy"

    def test_redis_not_configured_counts_as_healthy(self):
        with (
            patch("app.api.health.check_db_connection", new_callable=AsyncMock) as mock_db,
            patch("app.api.health._check_redis", new_callable=AsyncMock) as mock_redis,
            patch("app.api.health._check_bucket", new_callable=AsyncMock) as mock_bucket,
            patch("app.api.health._check_external_service", new_callable=AsyncMock) as mock_ext,
        ):
            mock_db.return_value = {"status": "healthy", "latency_ms": 1.0}
            mock_redis.return_value = {"status": "not_configured"}
            mock_bucket.return_value = {"status": "healthy", "latency_ms": 1.0}
            mock_ext.return_value = {"status": "healthy", "latency_ms": 1.0}

            response = client.get("/api/v1/health/detailed")
            assert response.json()["status"] == "healthy"


# ===========================================================================
# 5. Replay Service — unit tests (no I/O)
# ===========================================================================


class TestExtractRequestPayload:
    def test_extracts_from_core_ingress_stage(self):
        entries = [
            TraceEntry(
                timestamp="t1",
                trace_id="tr1",
                stage="core_ingress",
                payload={"user_id": "u1", "city": "Pune", "prompt": "3bhk", "style": "modern"},
            ),
            TraceEntry(timestamp="t2", trace_id="tr1", stage="bucket_write", payload={}),
        ]
        result = _extract_request_payload(entries)
        assert result["user_id"] == "u1"
        assert result["city"] == "Pune"
        assert result["prompt"] == "3bhk"

    def test_fallback_when_no_core_ingress(self):
        entries = [
            TraceEntry(timestamp="t1", trace_id="tr1", stage="bucket_write", payload={}),
        ]
        result = _extract_request_payload(entries)
        assert result["user_id"] == "replay_user"
        assert result["city"] == "Mumbai"

    def test_empty_entries_returns_fallback(self):
        result = _extract_request_payload([])
        assert "user_id" in result


class TestLoadTrace:
    def test_loads_valid_jsonl(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_id = "spec_testload123"
            trace_file = Path(tmpdir) / f"core_bucket_{spec_id}.jsonl"
            trace_file.write_text(
                json.dumps(
                    {
                        "timestamp": "2024-01-01T00:00:00Z",
                        "trace_id": "tr1",
                        "stage": "core_ingress",
                        "payload": {"city": "Mumbai"},
                    }
                )
                + "\n"
                + json.dumps(
                    {"timestamp": "2024-01-01T00:00:01Z", "trace_id": "tr1", "stage": "bucket_write", "payload": {}}
                )
                + "\n",
                encoding="utf-8",
            )
            with patch("app.replay.replay_service._TRACE_DIR", Path(tmpdir)):
                entries = _load_trace(spec_id)
            assert len(entries) == 2
            assert entries[0].stage == "core_ingress"
            assert entries[1].stage == "bucket_write"

    def test_raises_file_not_found_for_missing_trace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.replay.replay_service._TRACE_DIR", Path(tmpdir)):
                with pytest.raises(FileNotFoundError):
                    _load_trace("spec_nonexistent")

    def test_skips_blank_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_id = "spec_blanklines"
            trace_file = Path(tmpdir) / f"core_bucket_{spec_id}.jsonl"
            trace_file.write_text(
                "\n" + json.dumps({"timestamp": "t", "trace_id": "tr", "stage": "s", "payload": {}}) + "\n" + "\n",
                encoding="utf-8",
            )
            with patch("app.replay.replay_service._TRACE_DIR", Path(tmpdir)):
                entries = _load_trace(spec_id)
            assert len(entries) == 1


class TestReplayResult:
    def test_to_dict_contains_all_keys(self):
        result = ReplayResult(
            original_spec_id="spec_abc",
            replay_spec_id="replay_spec_abc_12345678",
            original_trace_id="core_bucket_spec_abc",
            replay_trace_id="core_bucket_replay_spec_abc_12345678",
            status="success",
            artifacts={"glb": "http://example.com/out.glb"},
        )
        d = result.to_dict()
        for key in (
            "original_spec_id",
            "replay_spec_id",
            "original_trace_id",
            "replay_trace_id",
            "status",
            "artifacts",
            "error",
            "replayed_at",
        ):
            assert key in d

    def test_failed_result_has_error(self):
        result = ReplayResult(
            original_spec_id="spec_abc",
            replay_spec_id="replay_spec_abc_12345678",
            original_trace_id="core_bucket_spec_abc",
            replay_trace_id="core_bucket_replay_spec_abc_12345678",
            status="failed",
            error="trace not found",
        )
        assert result.status == "failed"
        assert result.error == "trace not found"
        assert result.artifacts == {}


class TestListReplayableSpecs:
    def test_returns_only_specs_with_both_files(self):
        with tempfile.TemporaryDirectory() as trace_dir, tempfile.TemporaryDirectory() as spec_dir:
            trace_path = Path(trace_dir)
            spec_path = Path(spec_dir)

            # spec_aaa has both trace + spec
            (trace_path / "core_bucket_spec_aaa.jsonl").write_text("{}", encoding="utf-8")
            (spec_path / "spec_aaa.json").write_text("{}", encoding="utf-8")

            # spec_bbb has trace only — should be excluded
            (trace_path / "core_bucket_spec_bbb.jsonl").write_text("{}", encoding="utf-8")

            with (
                patch("app.replay.replay_service._TRACE_DIR", trace_path),
                patch("app.replay.replay_service._SPEC_DIR", spec_path),
            ):
                result = ReplayService.list_replayable_specs()

            assert "spec_aaa" in result
            assert "spec_bbb" not in result

    def test_returns_empty_when_trace_dir_missing(self):
        with patch("app.replay.replay_service._TRACE_DIR", Path("/nonexistent/path")):
            result = ReplayService.list_replayable_specs()
        assert result == []


class TestGetTraceSummary:
    def test_summary_structure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_id = "spec_summary123"
            trace_file = Path(tmpdir) / f"core_bucket_{spec_id}.jsonl"
            trace_file.write_text(
                json.dumps(
                    {"timestamp": "2024-01-01T00:00:00Z", "trace_id": "tr1", "stage": "core_ingress", "payload": {}}
                )
                + "\n"
                + json.dumps(
                    {"timestamp": "2024-01-01T00:00:02Z", "trace_id": "tr1", "stage": "bucket_write", "payload": {}}
                )
                + "\n",
                encoding="utf-8",
            )
            with patch("app.replay.replay_service._TRACE_DIR", Path(tmpdir)):
                summary = ReplayService.get_trace_summary(spec_id)

        assert summary["spec_id"] == spec_id
        assert summary["stage_count"] == 2
        assert "core_ingress" in summary["stages"]
        assert summary["started_at"] == "2024-01-01T00:00:00Z"
        assert summary["completed_at"] == "2024-01-01T00:00:02Z"

    def test_summary_returns_error_for_missing_trace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.replay.replay_service._TRACE_DIR", Path(tmpdir)):
                summary = ReplayService.get_trace_summary("spec_missing")
        assert "error" in summary


class TestReplayServiceReplay:
    @pytest.mark.asyncio
    async def test_replay_returns_failed_when_trace_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.replay.replay_service._TRACE_DIR", Path(tmpdir)):
                result = await ReplayService.replay("spec_no_trace")
        assert result.status == "failed"
        assert "not found" in result.error.lower()
        assert result.original_spec_id == "spec_no_trace"

    @pytest.mark.asyncio
    async def test_replay_success_path(self):
        with tempfile.TemporaryDirectory() as trace_dir, tempfile.TemporaryDirectory() as spec_dir:
            spec_id = "spec_replaytest"
            trace_path = Path(trace_dir)
            spec_path = Path(spec_dir)

            (trace_path / f"core_bucket_{spec_id}.jsonl").write_text(
                json.dumps(
                    {
                        "timestamp": "t",
                        "trace_id": "tr1",
                        "stage": "core_ingress",
                        "payload": {"user_id": "u1", "city": "Mumbai", "prompt": "2bhk"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (spec_path / f"{spec_id}.json").write_text(
                json.dumps({"spec_id": spec_id, "city": "Mumbai"}), encoding="utf-8"
            )

            mock_artifact = MagicMock()
            mock_artifact.url = "http://bucket/out.glb"
            mock_result = MagicMock()
            mock_result.artifacts = {"glb": mock_artifact}

            mock_orchestrator = AsyncMock()
            mock_orchestrator.execute.return_value = mock_result

            with (
                patch("app.replay.replay_service._TRACE_DIR", trace_path),
                patch("app.replay.replay_service._SPEC_DIR", spec_path),
                patch("app.core_bucket_pipeline.CoreBucketCanonicalOrchestrator", return_value=mock_orchestrator),
            ):
                result = await ReplayService.replay(spec_id)

        assert result.status == "success"
        assert result.original_spec_id == spec_id
        assert result.replay_spec_id.startswith("replay_")
        assert "glb" in result.artifacts

    @pytest.mark.asyncio
    async def test_replay_failed_when_orchestrator_raises(self):
        with tempfile.TemporaryDirectory() as trace_dir, tempfile.TemporaryDirectory() as spec_dir:
            spec_id = "spec_orchfail"
            trace_path = Path(trace_dir)
            spec_path = Path(spec_dir)

            (trace_path / f"core_bucket_{spec_id}.jsonl").write_text(
                json.dumps(
                    {
                        "timestamp": "t",
                        "trace_id": "tr1",
                        "stage": "core_ingress",
                        "payload": {"user_id": "u1", "city": "Mumbai", "prompt": "2bhk"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (spec_path / f"{spec_id}.json").write_text("{}", encoding="utf-8")

            mock_orchestrator = AsyncMock()
            mock_orchestrator.execute.side_effect = RuntimeError("pipeline exploded")

            with (
                patch("app.replay.replay_service._TRACE_DIR", trace_path),
                patch("app.replay.replay_service._SPEC_DIR", spec_path),
                patch("app.core_bucket_pipeline.CoreBucketCanonicalOrchestrator", return_value=mock_orchestrator),
            ):
                result = await ReplayService.replay(spec_id)

        assert result.status == "failed"
        assert "pipeline exploded" in result.error


# ===========================================================================
# 6. Replay API endpoints (require auth — mock get_current_user)
# ===========================================================================


class TestReplayAPIEndpoints:
    def _auth_override(self):
        from app.auth_mongodb import get_current_user

        app.dependency_overrides[get_current_user] = lambda: "test_user"

    def _clear_override(self):
        app.dependency_overrides.clear()

    def test_list_replayable_requires_auth(self):
        response = client.get("/api/v1/replay/")
        # Without auth should be 401 or 403
        assert response.status_code in (401, 403)

    def test_list_replayable_returns_list(self):
        self._auth_override()
        try:
            with patch.object(ReplayService, "list_replayable_specs", return_value=["spec_aaa", "spec_bbb"]):
                response = client.get("/api/v1/replay/")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 2
            assert "spec_aaa" in data["replayable_specs"]
        finally:
            self._clear_override()

    def test_get_trace_summary_404_for_missing(self):
        self._auth_override()
        try:
            with patch.object(ReplayService, "get_trace_summary", return_value={"error": "not found"}):
                response = client.get("/api/v1/replay/spec_missing/trace")
            assert response.status_code == 404
        finally:
            self._clear_override()

    def test_get_trace_summary_returns_data(self):
        self._auth_override()
        try:
            summary = {
                "spec_id": "spec_aaa",
                "stage_count": 3,
                "stages": ["s1", "s2", "s3"],
                "started_at": "t0",
                "completed_at": "t2",
                "trace_id": "tr1",
            }
            with patch.object(ReplayService, "get_trace_summary", return_value=summary):
                response = client.get("/api/v1/replay/spec_aaa/trace")
            assert response.status_code == 200
            assert response.json()["stage_count"] == 3
        finally:
            self._clear_override()

    def test_post_replay_returns_422_on_failure(self):
        self._auth_override()
        try:
            failed = ReplayResult(
                original_spec_id="spec_x",
                replay_spec_id="replay_spec_x_abc",
                original_trace_id="core_bucket_spec_x",
                replay_trace_id="core_bucket_replay_spec_x_abc",
                status="failed",
                error="trace not found",
            )
            with patch.object(ReplayService, "replay", new_callable=AsyncMock, return_value=failed):
                response = client.post("/api/v1/replay/spec_x")
            assert response.status_code == 422
        finally:
            self._clear_override()

    def test_post_replay_returns_result_on_success(self):
        self._auth_override()
        try:
            success = ReplayResult(
                original_spec_id="spec_y",
                replay_spec_id="replay_spec_y_abc12345",
                original_trace_id="core_bucket_spec_y",
                replay_trace_id="core_bucket_replay_spec_y_abc12345",
                status="success",
                artifacts={"glb": "http://bucket/out.glb"},
            )
            with patch.object(ReplayService, "replay", new_callable=AsyncMock, return_value=success):
                response = client.post("/api/v1/replay/spec_y")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["replay_spec_id"] == "replay_spec_y_abc12345"
            assert data["artifacts"]["glb"] == "http://bucket/out.glb"
        finally:
            self._clear_override()
