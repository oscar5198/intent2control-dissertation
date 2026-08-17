# Phase 6E.4 Failure Handling

Status: deterministic mock/synthetic failure-handling layer. This phase does
not call real models, verify model identities, inspect participant outcomes,
score predictions, or change the frozen prompt/response contract.

Failure-handling version:

```text
phase6e_failure_handling_v1
```

Failure policy artifact:

```text
llm-experiments/config/phase6e_failure_policy_v1.json
```

## Scientific Principle

The scientific generation policy is fixed:

1. exactly one primary generation;
2. if a non-empty primary output is structurally invalid, allow exactly one
   formatting-only repair;
3. if the repair remains invalid, mark the prediction `invalid_after_repair`;
4. never keep asking until a favourable or valid-looking answer appears;
5. never provide ground truth, correctness feedback, new participant
   information, or preference hints during repair.

Transport retries are operational infrastructure retries. They are separate
from scientific generations and are used only when no meaningful model output
was obtained.

## Failure Taxonomy

Preflight:

- `prompt_package_invalid`
- `model_config_not_frozen`
- `backend_not_verified`
- `schema_missing`

Transport:

- `timeout`
- `connection_error`
- `http_client_error`
- `http_server_error`
- `backend_unavailable`
- `rate_limited`
- `bad_credentials`
- `unsupported_model`

Response extraction:

- `empty_response`
- `missing_text_field`
- `malformed_provider_response`

Structural validation:

- `invalid_json`
- `schema_invalid`

Internal:

- `logging_conflict`
- `duplicate_request_conflict`
- `unexpected_internal_error`

## Retry Policy

Default policy:

- maximum primary generations: 1
- maximum format-repair generations: 1
- maximum transport retries: 2
- retryable: `timeout`, `connection_error`, `http_server_error`,
  `backend_unavailable`, `rate_limited`, `empty_response`
- non-retryable: bad credentials, HTTP 400/client errors, unsupported model,
  preflight/configuration errors, malformed provider responses, and structural
  validation failures

Backoff is deterministic and configurable. The synthetic/test policy uses zero
delay so unit tests never wait on live-style sleep intervals. Retry-after
metadata is captured when present but provider-specific behavior is left to
future live adapters.

## Formatting Repair

Repair is triggered only when:

- the primary backend invocation completed;
- non-empty output exists;
- validation against `preference_prediction_response_v1` fails with
  `invalid_json` or `schema_invalid`.

The repair request reuses the frozen Phase 6D renderer. It contains only the
frozen repair instruction, the invalid output, and the exact response schema.
It uses the same scientific model, backend, inference config version, and
response schema.

No repair is attempted for valid output, timeout, empty response,
authentication failure, missing deployment, or preflight failure.

## Prediction States

The explicit prediction-level state vocabulary is:

- `pending`
- `primary_in_progress`
- `valid_primary`
- `repair_pending`
- `repair_in_progress`
- `valid_after_repair`
- `invalid_after_repair`
- `backend_retry_pending`
- `backend_failed`
- `blocked_by_preflight`
- `not_run`

Terminal run states are:

- `valid_primary`
- `valid_after_repair`
- `invalid_after_repair`
- `backend_failed`

## Attempt Logging

Phase 6E.4 extends Phase 6E.3 attempt records with:

- `failure_handling_version`
- `attempt_status`
- `failure_code`
- `failure_category`
- `retryable`
- `transport_attempt_number`
- `parent_inference_request_id`
- `scientific_generation_id`
- `transport_retry_of`

This preserves the distinction between scientific generation count and backend
transport attempt count. A primary generation with two transport failures then
a successful third transport attempt is still one scientific primary
generation.

## Resume And Crash Recovery

The attempt log is authoritative. On resume:

- `valid_primary`: do nothing;
- primary invalid and no repair: run exactly one repair;
- primary invalid and repair invalid: do nothing;
- transport failed and retries remain: resume remaining transport attempts;
- `backend_failed`: do not restart automatically.

If a crash happens after attempts are logged but before predictions or summary
files are updated, predictions and run summaries are reconstructed from
`attempt_log.jsonl`.

## Completion Gates

`INFERENCE_RUN_COMPLETE` is true only when every expected prediction record is
terminal. It may be true even when some predictions are invalid or backend
failed.

`ALL_EXPECTED_PREDICTIONS_VALID` is true only when every expected prediction is
`valid_primary` or `valid_after_repair`.

These gates are operational completeness checks, not predictive accuracy.

## Distributed QMUL/RunPod Operation

Failure status is per prediction unit:

```text
prediction_example_id x condition x model_key x inference_config_version
```

QMUL and RunPod runs can fail, retry, repair, and resume independently. Later
merge preserves primary/repair linkage through `prediction_record_id`,
`parent_inference_request_id`, and `scientific_generation_id`; conflicting
final predictions under the same scientific config remain merge conflicts.

## Synthetic Failure Matrix

Run:

```powershell
python llm-experiments\scripts\run_phase6e4_failure_matrix.py
```

Outputs:

```text
llm-experiments/outputs/synthetic/phase6e4/phase6e4_synthetic_failure_matrix/
```

The matrix covers:

- primary valid;
- invalid JSON -> repair valid;
- invalid JSON -> repair invalid;
- schema invalid -> repair valid;
- timeout -> retry success;
- timeout -> retry exhausted;
- HTTP 500 -> retry success;
- HTTP 429 -> retry success;
- HTTP 400 -> no retry;
- empty response -> bounded retry;
- connection failure -> retry exhausted;
- authentication failure -> no retry.

The state-transition audit proves that no third generation occurs after a
failed repair and that transport retries are bounded by policy.
