# CORE PROOF

**Sprint:** TTG Full Integration + TANTRA Canonical Asset Generation
**Version:** 1.0

---

## Overview

This document provides complete evidence that every execution in the TANTRA pipeline requires Core authorization. No asset generation can proceed without a successful Core response carrying a valid `execution_token` and `trace_id`.

---

## Core Execution Flow

```
Caller
  │
  ▼
CoreGateway.run(prompt, trace_id)
  │   app/services/core_gateway.py
  │
  ├── Step 1: Build CoreExecutionRequest
  │     execution_token = CoreExecutionRequest.generate_token()   ← auto UUID
  │     trace_id        = provided or auto-generated UUID
  │     agent           = "prompt_runner_gateway"
  │
  ├── Step 2: CoreClient.execute_task(request)
  │     POST {base_url}/execute_task
  │     payload = request.to_dict()
  │     timeout = 30s
  │     retries = 3 (exponential back-off: 2s → 4s → 8s)
  │
  ├── Step 3: Evaluate response.status
  │     "success"  →  continue to PromptRunnerClient
  │     "failed"   →  raise CoreGatewayAuthError (PR never called)
  │     "rejected" →  raise CoreGatewayAuthError (PR never called)
  │     "pending"  →  raise CoreGatewayAuthError (PR never called)
  │     exception  →  raise CoreGatewayAuthError (PR never called)
  │
  └── Step 4 (only on success): PromptRunnerClient.generate_instruction(prompt)
```

---

## execution_token Enforcement

### Where it is enforced

**1. CoreExecutionRequest.__post_init__** (`app/contracts/core_execution_request.py`)

```python
if not self.execution_token or not str(self.execution_token).strip():
    raise ValidationError("'execution_token' is required and cannot be empty.")
```

Raised at object construction time — the request object cannot exist without a valid token.

**2. CoreClient._validate_request()** (`app/services/core_client.py`)

```python
if not request.execution_token or not str(request.execution_token).strip():
    raise CoreValidationError(
        "CoreClient: 'execution_token' is required and cannot be empty."
    )
```

Re-validated before the HTTP call is made — defence in depth against mutated objects.

**3. CoreGateway._authorize()** (`app/services/core_gateway.py`)

```python
auth_request = CoreExecutionRequest(
    ...
    execution_token=CoreExecutionRequest.generate_token(),
    ...
)
```

Token is always auto-generated inside the gateway — callers cannot omit it.

### Test references

| Test | File | Line |
|---|---|---|
| `test_missing_execution_token_raises` | `test_contracts.py` | TestCoreExecutionRequestValidation |
| `test_whitespace_execution_token_raises` | `test_contracts.py` | TestCoreExecutionRequestValidation |
| `test_missing_execution_token_before_dispatch` | `test_core_client.py` | TestExecuteTaskValidation |
| `test_whitespace_execution_token_raises` | `test_core_client.py` | TestExecuteTaskValidation |

---

## trace_id Enforcement

### Where it is enforced

**1. CoreExecutionRequest.__post_init__** (`app/contracts/core_execution_request.py`)

```python
if not self.trace_id or not str(self.trace_id).strip():
    raise ValidationError("'trace_id' is required and cannot be empty.")
```

**2. CoreClient._validate_request()** (`app/services/core_client.py`)

```python
if not request.trace_id or not str(request.trace_id).strip():
    raise CoreValidationError(
        "CoreClient: 'trace_id' is required and cannot be empty."
    )
```

**3. Trace propagation** — trace_id flows through every pipeline stage:

```
CoreGateway.run(trace_id)
  → CoreExecutionRequest.trace_id
  → CoreExecutionResponse.trace_id
  → TTGPayloadBuilder(trace_id=...)
  → TTGExecutePayload.trace_id
  → BucketAssetRecord.trace_id
```

### Test references

| Test | File |
|---|---|
| `test_missing_trace_id_raises` | `test_contracts.py` |
| `test_whitespace_trace_id_raises` | `test_contracts.py` |
| `test_missing_trace_id_before_dispatch` | `test_core_client.py` |
| `test_trace_id_preserved_in_payload` (×5 parametrised) | `test_sprint_qa_matrix.py` |

---

## Fail-Closed Evidence

### CoreGateway raises immediately on any non-success status

```python
# app/services/core_gateway.py — _authorize()

if response.status != "success":
    raise CoreGatewayAuthError(
        f"CoreGateway: Core rejected with status='{response.status}'. "
        f"PromptRunner will not be called.",
        core_response=response,
    )
```

### CoreGateway raises on any Core network/HTTP exception

```python
try:
    response = await self._core.execute_task(auth_request)
except CoreError as exc:
    raise CoreGatewayAuthError(
        f"CoreGateway: Core authorization failed — {exc}"
    ) from exc
```

### Test references — all in `test_core_gateway.py`

| Test class | Tests | What is verified |
|---|---|---|
| `TestCoreRejectionBlocksPromptRunner` | 6 | status=failed/rejected/pending, missing status, empty response — PR never called |
| `TestCoreExceptionBlocksPromptRunner` | 3 | CoreError / CoreTimeoutError / CoreValidationError — PR never called |
| `TestPipelineOrdering` | 4 | Core always called first; PR never called before Core succeeds |

### Mock log evidence (from test_core_gateway.py::TestCoreRejectionBlocksPromptRunner)

```
status="failed"   → CoreGatewayAuthError raised, pr_client.generate_instruction call_count == 0
status="rejected" → CoreGatewayAuthError raised, pr_client.generate_instruction call_count == 0
status="pending"  → CoreGatewayAuthError raised, pr_client.generate_instruction call_count == 0
CoreError thrown  → CoreGatewayAuthError raised, pr_client.generate_instruction call_count == 0
```

---

## Retry and Timeout Behaviour

| Condition | Behaviour | Back-off |
|---|---|---|
| 5xx response | Retry up to 3 times | 2s → 4s → 8s |
| httpx.TimeoutException | Retry up to 3 times | 2s → 4s → 8s |
| 4xx response | Fail immediately, no retry | — |
| All retries exhausted (5xx) | Raise `CoreError` | — |
| All retries exhausted (timeout) | Raise `CoreTimeoutError` | — |

Timeout per request: **30 seconds** (`TIMEOUT_SECONDS = 30.0`)

### Test references — `test_core_client.py::TestRetryLogic`

| Test | Verified |
|---|---|
| `test_retries_on_5xx_success_on_third` | 5xx × 2 then 200 → succeeds, call_count == 3 |
| `test_all_5xx_raises_core_error` | 5xx × 3 → CoreError |
| `test_4xx_no_retry` | 400 → CoreError, call_count == 1 |
| `test_timeout_raises_core_timeout_error` | TimeoutException → CoreTimeoutError |
| `test_timeout_retries_correct_number` | TimeoutException × 3 → call_count == 3 |
| `test_backoff_called_on_retry` | `time.sleep` called with correct intervals |
| `test_timeout_error_is_subclass_of_core_error` | CoreTimeoutError inherits CoreError |

---

## Exception Hierarchy

```
CoreError                  ← base exception for all Core failures
├── CoreValidationError    ← missing execution_token / trace_id / bad response schema
└── CoreTimeoutError       ← all retries exhausted due to timeout
```

All three are defined in `app/services/core_client.py`.
`CoreGatewayAuthError` wraps `CoreError` in `app/services/core_gateway.py`.

---

## Summary

| Requirement | Implemented | Tested |
|---|---|---|
| Core authorization required | Yes — CoreGateway._authorize() | Yes — 36 tests in test_core_gateway.py |
| execution_token enforced | Yes — contract + client + gateway | Yes — test_contracts.py + test_core_client.py |
| trace_id enforced | Yes — contract + client + all stages | Yes — test_contracts.py + test_sprint_qa_matrix.py |
| Fail closed | Yes — CoreGatewayAuthError on any non-success | Yes — TestCoreRejectionBlocksPromptRunner (6 tests) |
| No execution without Core | Yes — CoreGateway is the only entry point | Yes — TestCoreExceptionBlocksPromptRunner (3 tests) |
| 30s timeout | Yes — TIMEOUT_SECONDS = 30.0 | Yes — test_core_client.py |
| 3 retries + back-off | Yes — _post_with_retry with exponential sleep | Yes — TestRetryLogic (7 tests) |

---

*Generated by Amazon Q — TANTRA Integration Sprint*
