"""
Unit tests for TANTRA execution contracts
==========================================
Run with: pytest backend/tests/test_contracts.py -v
"""

import pytest
from app.contracts.core_execution_request import CoreExecutionRequest, ValidationError
from app.contracts.core_execution_response import VALID_STATUSES, CoreExecutionResponse

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_request(**overrides):
    defaults = {
        "input": "Design a 2BHK apartment in Mumbai",
        "agent": "architecture_generator",
        "execution_token": "tok_abc123",
        "trace_id": "trace_xyz789",
    }
    defaults.update(overrides)
    return CoreExecutionRequest(**defaults)


def make_response(**overrides):
    defaults = {
        "task_id": "task_001",
        "agent_output": {"spec": {"type": "2bhk"}},
        "status": "success",
        "trace_id": "trace_xyz789",
        "bucket_write": "bucket://outputs/task_001.glb",
    }
    defaults.update(overrides)
    return CoreExecutionResponse(**defaults)


# ══════════════════════════════════════════════════════════════════════════════
# CoreExecutionRequest
# ══════════════════════════════════════════════════════════════════════════════


class TestCoreExecutionRequestConstruction:
    def test_valid_minimal_request(self):
        req = make_request()
        assert req.input == "Design a 2BHK apartment in Mumbai"
        assert req.agent == "architecture_generator"
        assert req.execution_token == "tok_abc123"
        assert req.trace_id == "trace_xyz789"

    def test_defaults_applied(self):
        req = make_request()
        assert req.task_id is None
        assert req.input_type == "text"
        assert req.tags == []
        assert req.retries == 0
        assert req.fallback_agent == ""

    def test_all_fields_set(self):
        req = make_request(
            task_id="task_001",
            input_type="json",
            tags=["urgent", "v2"],
            retries=3,
            fallback_agent="fallback_generator",
        )
        assert req.task_id == "task_001"
        assert req.input_type == "json"
        assert req.tags == ["urgent", "v2"]
        assert req.retries == 3
        assert req.fallback_agent == "fallback_generator"


class TestCoreExecutionRequestValidation:
    def test_missing_execution_token_raises(self):
        with pytest.raises(ValidationError, match="execution_token"):
            make_request(execution_token="")

    def test_whitespace_execution_token_raises(self):
        with pytest.raises(ValidationError, match="execution_token"):
            make_request(execution_token="   ")

    def test_missing_trace_id_raises(self):
        with pytest.raises(ValidationError, match="trace_id"):
            make_request(trace_id="")

    def test_whitespace_trace_id_raises(self):
        with pytest.raises(ValidationError, match="trace_id"):
            make_request(trace_id="   ")

    def test_negative_retries_raises(self):
        with pytest.raises(ValidationError, match="retries"):
            make_request(retries=-1)

    def test_tags_not_list_raises(self):
        with pytest.raises(ValidationError, match="tags"):
            make_request(tags="urgent")

    def test_zero_retries_is_valid(self):
        req = make_request(retries=0)
        assert req.retries == 0

    def test_positive_retries_is_valid(self):
        req = make_request(retries=5)
        assert req.retries == 5

    def test_empty_tags_list_is_valid(self):
        req = make_request(tags=[])
        assert req.tags == []


class TestCoreExecutionRequestSerialization:
    def test_to_dict_contains_all_keys(self):
        req = make_request()
        d = req.to_dict()
        assert set(d.keys()) == {
            "input",
            "agent",
            "task_id",
            "input_type",
            "tags",
            "retries",
            "fallback_agent",
            "execution_token",
            "trace_id",
        }

    def test_to_dict_values_match(self):
        req = make_request(task_id="t1", tags=["a"], retries=2)
        d = req.to_dict()
        assert d["task_id"] == "t1"
        assert d["tags"] == ["a"]
        assert d["retries"] == 2
        assert d["execution_token"] == "tok_abc123"
        assert d["trace_id"] == "trace_xyz789"

    def test_from_dict_roundtrip(self):
        original = make_request(task_id="t1", tags=["x"], retries=1)
        restored = CoreExecutionRequest.from_dict(original.to_dict())
        assert restored.to_dict() == original.to_dict()

    def test_from_dict_missing_token_raises(self):
        data = {
            "input": "test",
            "agent": "ag",
            "execution_token": "",
            "trace_id": "tr1",
        }
        with pytest.raises(ValidationError, match="execution_token"):
            CoreExecutionRequest.from_dict(data)


class TestCoreExecutionRequestHelpers:
    def test_generate_token_format(self):
        token = CoreExecutionRequest.generate_token()
        assert token.startswith("tok_")
        assert len(token) == 20  # "tok_" + 16 hex chars

    def test_generate_trace_id_format(self):
        trace_id = CoreExecutionRequest.generate_trace_id()
        assert trace_id.startswith("trace_")
        assert len(trace_id) == 22  # "trace_" + 16 hex chars

    def test_generated_tokens_are_unique(self):
        tokens = {CoreExecutionRequest.generate_token() for _ in range(100)}
        assert len(tokens) == 100

    def test_generated_trace_ids_are_unique(self):
        ids = {CoreExecutionRequest.generate_trace_id() for _ in range(100)}
        assert len(ids) == 100

    def test_generated_token_works_in_request(self):
        req = make_request(
            execution_token=CoreExecutionRequest.generate_token(),
            trace_id=CoreExecutionRequest.generate_trace_id(),
        )
        assert req.execution_token.startswith("tok_")
        assert req.trace_id.startswith("trace_")


# ══════════════════════════════════════════════════════════════════════════════
# CoreExecutionResponse
# ══════════════════════════════════════════════════════════════════════════════


class TestCoreExecutionResponseConstruction:
    def test_valid_success_response(self):
        resp = make_response()
        assert resp.task_id == "task_001"
        assert resp.status == "success"
        assert resp.trace_id == "trace_xyz789"
        assert resp.bucket_write == "bucket://outputs/task_001.glb"
        assert resp.agent_output == {"spec": {"type": "2bhk"}}

    def test_defaults_applied(self):
        resp = CoreExecutionResponse(task_id="t1", trace_id="tr1", status="success")
        assert resp.agent_output == {}
        assert resp.bucket_write == ""

    def test_all_valid_statuses_accepted(self):
        for status in VALID_STATUSES:
            resp = CoreExecutionResponse(task_id="t1", trace_id="tr1", status=status)
            assert resp.status == status


class TestCoreExecutionResponseValidation:
    def test_missing_task_id_raises(self):
        with pytest.raises(ValidationError, match="task_id"):
            make_response(task_id="")

    def test_whitespace_task_id_raises(self):
        with pytest.raises(ValidationError, match="task_id"):
            make_response(task_id="   ")

    def test_missing_trace_id_raises(self):
        with pytest.raises(ValidationError, match="trace_id"):
            make_response(trace_id="")

    def test_whitespace_trace_id_raises(self):
        with pytest.raises(ValidationError, match="trace_id"):
            make_response(trace_id="   ")

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError, match="status"):
            make_response(status="running")

    def test_unknown_status_raises(self):
        with pytest.raises(ValidationError, match="status"):
            make_response(status="unknown_xyz")

    def test_agent_output_not_dict_raises(self):
        with pytest.raises(ValidationError, match="agent_output"):
            make_response(agent_output="not_a_dict")


class TestCoreExecutionResponseSerialization:
    def test_to_dict_contains_all_keys(self):
        resp = make_response()
        d = resp.to_dict()
        assert set(d.keys()) == {"task_id", "agent_output", "status", "trace_id", "bucket_write"}

    def test_to_dict_values_match(self):
        resp = make_response()
        d = resp.to_dict()
        assert d["task_id"] == "task_001"
        assert d["status"] == "success"
        assert d["trace_id"] == "trace_xyz789"
        assert d["bucket_write"] == "bucket://outputs/task_001.glb"

    def test_from_dict_roundtrip(self):
        original = make_response()
        restored = CoreExecutionResponse.from_dict(original.to_dict())
        assert restored.to_dict() == original.to_dict()

    def test_from_dict_invalid_status_raises(self):
        data = {
            "task_id": "t1",
            "trace_id": "tr1",
            "status": "bad_status",
            "agent_output": {},
        }
        with pytest.raises(ValidationError, match="status"):
            CoreExecutionResponse.from_dict(data)


class TestCoreExecutionResponseFactories:
    def test_success_factory(self):
        resp = CoreExecutionResponse.success(
            task_id="t1",
            trace_id="tr1",
            agent_output={"result": "ok"},
            bucket_write="bucket://out/t1.glb",
        )
        assert resp.status == "success"
        assert resp.agent_output == {"result": "ok"}
        assert resp.bucket_write == "bucket://out/t1.glb"

    def test_success_factory_default_bucket(self):
        resp = CoreExecutionResponse.success(task_id="t1", trace_id="tr1", agent_output={})
        assert resp.bucket_write == ""

    def test_failed_factory(self):
        resp = CoreExecutionResponse.failed(task_id="t1", trace_id="tr1", reason="timeout")
        assert resp.status == "failed"
        assert resp.agent_output == {"error": "timeout"}
        assert resp.bucket_write == ""

    def test_failed_factory_no_reason(self):
        resp = CoreExecutionResponse.failed(task_id="t1", trace_id="tr1")
        assert resp.status == "failed"
        assert resp.agent_output == {"error": ""}


# ══════════════════════════════════════════════════════════════════════════════
# Contract interoperability
# ══════════════════════════════════════════════════════════════════════════════


class TestContractInterop:
    def test_trace_id_flows_from_request_to_response(self):
        req = make_request(trace_id="trace_shared_001")
        resp = CoreExecutionResponse.success(
            task_id="t1",
            trace_id=req.trace_id,
            agent_output={"done": True},
        )
        assert resp.trace_id == req.trace_id

    def test_request_to_dict_feeds_response_from_dict(self):
        req = make_request(task_id="t_inter")
        resp_data = {
            "task_id": req.task_id or "t_inter",
            "trace_id": req.trace_id,
            "status": "success",
            "agent_output": {"input_echo": req.input},
            "bucket_write": "",
        }
        resp = CoreExecutionResponse.from_dict(resp_data)
        assert resp.trace_id == req.trace_id
        assert resp.agent_output["input_echo"] == req.input
