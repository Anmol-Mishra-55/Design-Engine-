"""
Unit tests for PromptRunnerClient
===================================
All HTTP calls are mocked — no real network required.
Run with: pytest backend/tests/test_prompt_runner_client.py -v
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from app.services.prompt_runner_client import (
    GenerateInstructionResponse,
    PromptRunnerClient,
    PromptRunnerError,
    PromptRunnerTimeoutError,
    PromptRunnerValidationError,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

# Matches confirmed live response from https://prompt-runner.onrender.com/docs
VALID_GENERATE_RESPONSE = {
    "prompt": "Make a 2bhk flat",
    "module": "architecture",
    "intent": "design_creation",
    "topic": "2bhk_flat",
    "tasks": ["floor_plan_design", "room_layout_planning", "elevation_design"],
    "output_format": "step_by_step_guide",
    "product_context": "creator_core",
}


def make_mock_response(status_code: int, json_data: dict) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.text = str(json_data)
    return mock_resp


# ── GenerateInstructionResponse validation ────────────────────────────────────


class TestGenerateInstructionResponse:
    def test_valid_response_parses_correctly(self):
        resp = GenerateInstructionResponse(VALID_GENERATE_RESPONSE)
        assert resp.prompt == "Make a 2bhk flat"
        assert resp.module == "architecture"
        assert resp.intent == "design_creation"
        assert resp.topic == "2bhk_flat"
        assert resp.tasks == ["floor_plan_design", "room_layout_planning", "elevation_design"]
        assert resp.output_format == "step_by_step_guide"
        assert resp.product_context == "creator_core"

    def test_to_dict_returns_all_seven_fields(self):
        resp = GenerateInstructionResponse(VALID_GENERATE_RESPONSE)
        d = resp.to_dict()
        assert set(d.keys()) == {"prompt", "module", "intent", "topic", "tasks", "output_format", "product_context"}

    def test_missing_module_raises_validation_error(self):
        bad = {k: v for k, v in VALID_GENERATE_RESPONSE.items() if k != "module"}
        with pytest.raises(PromptRunnerValidationError, match="module"):
            GenerateInstructionResponse(bad)

    def test_missing_intent_raises_validation_error(self):
        bad = {k: v for k, v in VALID_GENERATE_RESPONSE.items() if k != "intent"}
        with pytest.raises(PromptRunnerValidationError, match="intent"):
            GenerateInstructionResponse(bad)

    def test_missing_topic_raises_validation_error(self):
        bad = {k: v for k, v in VALID_GENERATE_RESPONSE.items() if k != "topic"}
        with pytest.raises(PromptRunnerValidationError, match="topic"):
            GenerateInstructionResponse(bad)

    def test_missing_tasks_raises_validation_error(self):
        bad = {k: v for k, v in VALID_GENERATE_RESPONSE.items() if k != "tasks"}
        with pytest.raises(PromptRunnerValidationError, match="tasks"):
            GenerateInstructionResponse(bad)

    def test_missing_output_format_raises_validation_error(self):
        bad = {k: v for k, v in VALID_GENERATE_RESPONSE.items() if k != "output_format"}
        with pytest.raises(PromptRunnerValidationError, match="output_format"):
            GenerateInstructionResponse(bad)

    def test_tasks_not_list_raises_validation_error(self):
        bad = {**VALID_GENERATE_RESPONSE, "tasks": "not_a_list"}
        with pytest.raises(PromptRunnerValidationError, match="list"):
            GenerateInstructionResponse(bad)

    def test_empty_tasks_list_is_valid(self):
        resp = GenerateInstructionResponse({**VALID_GENERATE_RESPONSE, "tasks": []})
        assert resp.tasks == []

    def test_product_context_defaults_to_creator_core_when_missing(self):
        without_ctx = {k: v for k, v in VALID_GENERATE_RESPONSE.items() if k != "product_context"}
        resp = GenerateInstructionResponse(without_ctx)
        assert resp.product_context == "creator_core"

    def test_repr_contains_key_fields(self):
        resp = GenerateInstructionResponse(VALID_GENERATE_RESPONSE)
        assert "architecture" in repr(resp)
        assert "design_creation" in repr(resp)
        assert "step_by_step_guide" in repr(resp)


# ── PromptRunnerClient.generate_instruction ───────────────────────────────────


class TestGenerateInstruction:
    @pytest.mark.asyncio
    async def test_successful_generate(self):
        mock_resp = make_mock_response(200, VALID_GENERATE_RESPONSE)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            client = PromptRunnerClient()
            result = await client.generate_instruction("Make a 2bhk flat")

        assert isinstance(result, GenerateInstructionResponse)
        assert result.module == "architecture"
        assert result.intent == "design_creation"
        assert result.topic == "2bhk_flat"
        assert result.output_format == "step_by_step_guide"
        assert result.product_context == "creator_core"
        assert isinstance(result.tasks, list)

    @pytest.mark.asyncio
    async def test_generate_sends_prompt_only_when_no_model(self):
        mock_resp = make_mock_response(200, VALID_GENERATE_RESPONSE)
        captured_payload = {}

        async def mock_post(url, json=None, **kwargs):
            captured_payload.update(json or {})
            return mock_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            client = PromptRunnerClient()
            await client.generate_instruction("Build a warehouse")

        assert captured_payload == {"prompt": "Build a warehouse"}

    @pytest.mark.asyncio
    async def test_generate_sends_model_when_provided(self):
        mock_resp = make_mock_response(200, VALID_GENERATE_RESPONSE)
        captured_payload = {}

        async def mock_post(url, json=None, **kwargs):
            captured_payload.update(json or {})
            return mock_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            client = PromptRunnerClient()
            await client.generate_instruction("Build a warehouse", model="ai architecture")

        assert captured_payload == {"prompt": "Build a warehouse", "model": "ai architecture"}

    @pytest.mark.asyncio
    async def test_generate_calls_correct_endpoint(self):
        mock_resp = make_mock_response(200, VALID_GENERATE_RESPONSE)
        captured_url = []

        async def mock_post(url, **kwargs):
            captured_url.append(url)
            return mock_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            client = PromptRunnerClient()
            await client.generate_instruction("test prompt")

        assert captured_url[0] == "https://prompt-runner.onrender.com/generate"

    @pytest.mark.asyncio
    async def test_invalid_response_raises_validation_error(self):
        bad_response = {"module": "x"}  # missing intent, topic, tasks, output_format
        mock_resp = make_mock_response(200, bad_response)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            client = PromptRunnerClient()
            with pytest.raises(PromptRunnerValidationError):
                await client.generate_instruction("test")


# ── PromptRunnerClient.convert ────────────────────────────────────────────────


class TestConvert:
    @pytest.mark.asyncio
    async def test_convert_returns_validated_response(self):
        mock_resp = make_mock_response(200, VALID_GENERATE_RESPONSE)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            client = PromptRunnerClient()
            result = await client.convert("Make a 2bhk flat")

        assert isinstance(result, GenerateInstructionResponse)
        assert result.module == "architecture"
        assert result.output_format == "step_by_step_guide"

    @pytest.mark.asyncio
    async def test_convert_calls_correct_endpoint(self):
        captured_url = []

        async def mock_post(url, **kwargs):
            captured_url.append(url)
            return make_mock_response(200, VALID_GENERATE_RESPONSE)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            client = PromptRunnerClient()
            await client.convert("Make a 2bhk flat")

        assert captured_url[0] == "https://prompt-runner.onrender.com/convert"

    @pytest.mark.asyncio
    async def test_convert_sends_model_when_provided(self):
        captured_payload = {}

        async def mock_post(url, json=None, **kwargs):
            captured_payload.update(json or {})
            return make_mock_response(200, VALID_GENERATE_RESPONSE)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            client = PromptRunnerClient()
            await client.convert("Make a 2bhk flat", model="ai architecture")

        assert captured_payload["model"] == "ai architecture"


# ── Retry logic ───────────────────────────────────────────────────────────────


class TestRetryLogic:
    @pytest.mark.asyncio
    async def test_retries_on_5xx_then_succeeds(self):
        """Returns 500 twice, then 200 on third attempt."""
        call_count = 0

        async def mock_post(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return make_mock_response(500, {"error": "server error"})
            return make_mock_response(200, VALID_GENERATE_RESPONSE)

        with patch("httpx.AsyncClient") as mock_client_cls, patch("app.services.prompt_runner_client.time.sleep"):
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            client = PromptRunnerClient(max_retries=3)
            result = await client.generate_instruction("test")

        assert call_count == 3
        assert result.module == "architecture"

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_on_5xx_raises_error(self):
        async def mock_post(url, **kwargs):
            return make_mock_response(500, {"error": "down"})

        with patch("httpx.AsyncClient") as mock_client_cls, patch("app.services.prompt_runner_client.time.sleep"):
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            client = PromptRunnerClient(max_retries=3)
            with pytest.raises(PromptRunnerError):
                await client.generate_instruction("test")

    @pytest.mark.asyncio
    async def test_4xx_does_not_retry(self):
        call_count = 0

        async def mock_post(url, **kwargs):
            nonlocal call_count
            call_count += 1
            return make_mock_response(400, {"error": "bad request"})

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            client = PromptRunnerClient(max_retries=3)
            with pytest.raises(PromptRunnerError, match="400"):
                await client.generate_instruction("test")

        assert call_count == 1  # no retries on 4xx

    @pytest.mark.asyncio
    async def test_timeout_raises_after_all_retries(self):
        async def mock_post(url, **kwargs):
            raise httpx.TimeoutException("timed out")

        with patch("httpx.AsyncClient") as mock_client_cls, patch("app.services.prompt_runner_client.time.sleep"):
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            client = PromptRunnerClient(max_retries=3)
            with pytest.raises(PromptRunnerTimeoutError):
                await client.generate_instruction("test")

    @pytest.mark.asyncio
    async def test_timeout_retries_correct_number_of_times(self):
        call_count = 0

        async def mock_post(url, **kwargs):
            nonlocal call_count
            call_count += 1
            raise httpx.TimeoutException("timed out")

        with patch("httpx.AsyncClient") as mock_client_cls, patch("app.services.prompt_runner_client.time.sleep"):
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            client = PromptRunnerClient(max_retries=3)
            with pytest.raises(PromptRunnerTimeoutError):
                await client.generate_instruction("test")

        assert call_count == 3


# ── Client configuration ──────────────────────────────────────────────────────


class TestClientConfiguration:
    def test_default_base_url(self):
        client = PromptRunnerClient()
        assert client.base_url == "https://prompt-runner.onrender.com"

    def test_custom_base_url(self):
        client = PromptRunnerClient(base_url="http://localhost:8001")
        assert client.base_url == "http://localhost:8001"

    def test_trailing_slash_stripped_from_base_url(self):
        client = PromptRunnerClient(base_url="http://localhost:8001/")
        assert client.base_url == "http://localhost:8001"

    def test_default_timeout(self):
        client = PromptRunnerClient()
        assert client.timeout == 30

    def test_custom_timeout(self):
        client = PromptRunnerClient(timeout=10)
        assert client.timeout == 10

    def test_default_max_retries(self):
        client = PromptRunnerClient()
        assert client.max_retries == 3

    def test_custom_max_retries(self):
        client = PromptRunnerClient(max_retries=5)
        assert client.max_retries == 5
