"""
Unit tests for CoreClient
==========================
All HTTP calls are mocked — no real network required.
Run with: pytest backend/tests/test_core_client.py -v
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from app.contracts.core_execution_request import CoreExecutionRequest
from app.contracts.core_execution_response import CoreExecutionResponse
from app.services.core_client import CORE_BASE_URL, CoreClient, CoreError, CoreTimeoutError, CoreValidationError

# ── Fixtures ──────────────────────────────────────────────────────────────────

VALID_RESPONSE = {
    "task_id": "task_001",
    "agent_output": {"spec": {"type": "2bhk"}},
    "status": "success",
    "trace_id": "trace_xyz789",
    "bucket_write": "bucket://outputs/task_001.glb",
}

VALID_HEALTH = {"status": "ok", "version": "1.0.0"}


def make_request(**overrides):
    defaults = {
        "input": "Design a 2BHK apartment",
        "agent": "architecture_generator",
        "execution_token": "tok_abc123",
        "trace_id": "trace_xyz789",
    }
    defaults.update(overrides)
    return CoreExecutionRequest(**defaults)


def make_mock_response(status_code: int, json_data: dict) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.text = str(json_data)
    return mock


def mock_httpx_post(return_value):
    """Context manager patch for httpx.AsyncClient POST."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=return_value)
    mock_client_cls = MagicMock()
    mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_client_cls, mock_client


def mock_httpx_get(return_value):
    """Context manager patch for httpx.AsyncClient GET."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=return_value)
    mock_client_cls = MagicMock()
    mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_client_cls, mock_client


# ══════════════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════════════


class TestCoreClientConfiguration:
    def test_default_base_url(self):
        client = CoreClient()
        assert client.base_url == "http://localhost:8000"

    def test_custom_base_url(self):
        client = CoreClient(base_url="http://core.internal:9000")
        assert client.base_url == "http://core.internal:9000"

    def test_trailing_slash_stripped(self):
        client = CoreClient(base_url="http://core.internal:9000/")
        assert client.base_url == "http://core.internal:9000"

    def test_default_timeout(self):
        client = CoreClient()
        assert client.timeout == 30.0

    def test_custom_timeout(self):
        client = CoreClient(timeout=10.0)
        assert client.timeout == 10.0

    def test_default_max_retries(self):
        client = CoreClient()
        assert client.max_retries == 3

    def test_custom_max_retries(self):
        client = CoreClient(max_retries=5)
        assert client.max_retries == 5


# ══════════════════════════════════════════════════════════════════════════════
# execute_task — happy path
# ══════════════════════════════════════════════════════════════════════════════


class TestExecuteTask:
    @pytest.mark.asyncio
    async def test_successful_execute_task(self):
        mock_cls, _ = mock_httpx_post(make_mock_response(200, VALID_RESPONSE))
        with patch("httpx.AsyncClient", mock_cls):
            client = CoreClient()
            response = await client.execute_task(make_request())

        assert isinstance(response, CoreExecutionResponse)
        assert response.task_id == "task_001"
        assert response.status == "success"
        assert response.trace_id == "trace_xyz789"
        assert response.bucket_write == "bucket://outputs/task_001.glb"
        assert response.agent_output == {"spec": {"type": "2bhk"}}

    @pytest.mark.asyncio
    async def test_execute_task_sends_to_correct_endpoint(self):
        captured_url = []

        async def mock_post(url, **kwargs):
            captured_url.append(url)
            return make_mock_response(200, VALID_RESPONSE)

        mock_cls = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", mock_cls):
            await CoreClient().execute_task(make_request())

        assert captured_url[0] == "http://localhost:8000/execute_task"

    @pytest.mark.asyncio
    async def test_execute_task_sends_correct_payload(self):
        captured_payload = {}

        async def mock_post(url, json=None, **kwargs):
            captured_payload.update(json or {})
            return make_mock_response(200, VALID_RESPONSE)

        mock_cls = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        req = make_request()
        with patch("httpx.AsyncClient", mock_cls):
            await CoreClient().execute_task(req)

        assert captured_payload["execution_token"] == "tok_abc123"
        assert captured_payload["trace_id"] == "trace_xyz789"
        assert captured_payload["agent"] == "architecture_generator"


# ══════════════════════════════════════════════════════════════════════════════
# execute_task — validation
# ══════════════════════════════════════════════════════════════════════════════


class TestExecuteTaskValidation:
    @pytest.mark.asyncio
    async def test_missing_execution_token_raises_before_http(self):
        req = make_request()
        req.execution_token = ""  # mutate after construction
        client = CoreClient()
        with pytest.raises(CoreValidationError, match="execution_token"):
            await client.execute_task(req)

    @pytest.mark.asyncio
    async def test_whitespace_execution_token_raises(self):
        req = make_request()
        req.execution_token = "   "
        client = CoreClient()
        with pytest.raises(CoreValidationError, match="execution_token"):
            await client.execute_task(req)

    @pytest.mark.asyncio
    async def test_missing_trace_id_raises_before_http(self):
        req = make_request()
        req.trace_id = ""
        client = CoreClient()
        with pytest.raises(CoreValidationError, match="trace_id"):
            await client.execute_task(req)

    @pytest.mark.asyncio
    async def test_whitespace_trace_id_raises(self):
        req = make_request()
        req.trace_id = "   "
        client = CoreClient()
        with pytest.raises(CoreValidationError, match="trace_id"):
            await client.execute_task(req)

    @pytest.mark.asyncio
    async def test_invalid_response_schema_raises_validation_error(self):
        bad_response = {"task_id": "t1"}  # missing status, trace_id, etc.
        mock_cls, _ = mock_httpx_post(make_mock_response(200, bad_response))
        with patch("httpx.AsyncClient", mock_cls):
            with pytest.raises(CoreValidationError):
                await CoreClient().execute_task(make_request())

    @pytest.mark.asyncio
    async def test_invalid_status_in_response_raises_validation_error(self):
        bad_response = {**VALID_RESPONSE, "status": "running"}
        mock_cls, _ = mock_httpx_post(make_mock_response(200, bad_response))
        with patch("httpx.AsyncClient", mock_cls):
            with pytest.raises(CoreValidationError):
                await CoreClient().execute_task(make_request())


# ══════════════════════════════════════════════════════════════════════════════
# health_check
# ══════════════════════════════════════════════════════════════════════════════


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_returns_dict(self):
        mock_cls, _ = mock_httpx_get(make_mock_response(200, VALID_HEALTH))
        with patch("httpx.AsyncClient", mock_cls):
            result = await CoreClient().health_check()

        assert result == VALID_HEALTH

    @pytest.mark.asyncio
    async def test_health_check_calls_correct_endpoint(self):
        captured_url = []

        async def mock_get(url, **kwargs):
            captured_url.append(url)
            return make_mock_response(200, VALID_HEALTH)

        mock_cls = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", mock_cls):
            await CoreClient().health_check()

        assert captured_url[0] == "http://localhost:8000/health"

    @pytest.mark.asyncio
    async def test_health_check_4xx_raises_core_error(self):
        mock_cls, _ = mock_httpx_get(make_mock_response(404, {"detail": "not found"}))
        with patch("httpx.AsyncClient", mock_cls):
            with pytest.raises(CoreError, match="404"):
                await CoreClient().health_check()


# ══════════════════════════════════════════════════════════════════════════════
# Retry logic — execute_task
# ══════════════════════════════════════════════════════════════════════════════


class TestRetryLogic:
    @pytest.mark.asyncio
    async def test_retries_on_5xx_then_succeeds(self):
        call_count = 0

        async def mock_post(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return make_mock_response(500, {"error": "server error"})
            return make_mock_response(200, VALID_RESPONSE)

        mock_cls = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", mock_cls), patch("app.services.core_client.time.sleep"):
            result = await CoreClient(max_retries=3).execute_task(make_request())

        assert call_count == 3
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_on_5xx_raises_core_error(self):
        async def mock_post(url, **kwargs):
            return make_mock_response(500, {"error": "down"})

        mock_cls = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", mock_cls), patch("app.services.core_client.time.sleep"):
            with pytest.raises(CoreError):
                await CoreClient(max_retries=3).execute_task(make_request())

    @pytest.mark.asyncio
    async def test_4xx_does_not_retry(self):
        call_count = 0

        async def mock_post(url, **kwargs):
            nonlocal call_count
            call_count += 1
            return make_mock_response(400, {"error": "bad request"})

        mock_cls = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", mock_cls):
            with pytest.raises(CoreError, match="400"):
                await CoreClient(max_retries=3).execute_task(make_request())

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_timeout_raises_core_timeout_error(self):
        async def mock_post(url, **kwargs):
            raise httpx.TimeoutException("timed out")

        mock_cls = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", mock_cls), patch("app.services.core_client.time.sleep"):
            with pytest.raises(CoreTimeoutError):
                await CoreClient(max_retries=3).execute_task(make_request())

    @pytest.mark.asyncio
    async def test_timeout_retries_correct_number_of_times(self):
        call_count = 0

        async def mock_post(url, **kwargs):
            nonlocal call_count
            call_count += 1
            raise httpx.TimeoutException("timed out")

        mock_cls = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", mock_cls), patch("app.services.core_client.time.sleep"):
            with pytest.raises(CoreTimeoutError):
                await CoreClient(max_retries=3).execute_task(make_request())

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_health_check_retries_on_5xx(self):
        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return make_mock_response(503, {"error": "unavailable"})
            return make_mock_response(200, VALID_HEALTH)

        mock_cls = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", mock_cls), patch("app.services.core_client.time.sleep"):
            result = await CoreClient(max_retries=3).health_check()

        assert call_count == 3
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_check_timeout_raises_core_timeout_error(self):
        async def mock_get(url, **kwargs):
            raise httpx.TimeoutException("timed out")

        mock_cls = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", mock_cls), patch("app.services.core_client.time.sleep"):
            with pytest.raises(CoreTimeoutError):
                await CoreClient(max_retries=3).health_check()


# ══════════════════════════════════════════════════════════════════════════════
# Exception hierarchy
# ══════════════════════════════════════════════════════════════════════════════


class TestExceptionHierarchy:
    def test_core_validation_error_is_core_error(self):
        assert issubclass(CoreValidationError, CoreError)

    def test_core_timeout_error_is_core_error(self):
        assert issubclass(CoreTimeoutError, CoreError)

    def test_core_error_is_exception(self):
        assert issubclass(CoreError, Exception)
