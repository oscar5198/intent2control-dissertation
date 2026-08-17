# Phase 6E.3 Prediction Logging

Status: canonical logging and provenance layer for dry-run/mock/synthetic
inference only. This phase does not call real models, verify model IDs,
implement automatic repair/retry, score predictions, inspect ground truth, or
modify prompts.

Logging contract version:

```text
phase6e_prediction_logging_v1
```

## Record Layers

Phase 6E.3 keeps three layers separate:

1. backend raw response;
2. attempt log;
3. canonical final prediction record.

An attempt log record is one backend invocation. A canonical prediction record
is one scientific prediction unit:

```text
prediction_example_id x condition x model_key x inference_config_version
```

This separation allows Phase 6E.4 to add formatting repair and retry behavior
without overwriting primary-attempt evidence.

## Stable IDs

Attempt records reuse the Phase 6E.1 `inference_request_id`.

Prediction records use a deterministic ID derived from:

```text
prediction_example_id + condition + model_key + inference_config_version
```

Operational timestamps are recorded in logs but are excluded from scientific
IDs.

## Hashes

Each attempt records:

- `prompt_payload_sha256`: SHA-256 over the exact system/user message payload
  sent to the adapter;
- `inference_config_sha256`: SHA-256 over scientific configuration fields such
  as model identity, prompt package, response schema, temperature, top-p, seed,
  max output, and structured-output strategy.

Hashes exclude credentials, endpoint URLs, and transient transport wrappers.

## Output Structure

Synthetic Phase 6E.3 logs are written under:

```text
llm-experiments/outputs/synthetic/phase6e3/
```

A run directory contains:

- `run_manifest.json`
- `attempt_log.jsonl`
- `predictions.jsonl`
- `execution_summary.json`
- `raw_responses/`

The synthetic mock run uses:

```text
llm-experiments/outputs/synthetic/phase6e3/phase6e3_synthetic_mock_run/
```

## Token, Cost, And Latency

Token usage supports `input_tokens`, `output_tokens`, and `total_tokens`.
Unavailable values are `null`, not zero.

Cost metadata supports input, output, total cost, currency, and cost source.
Unavailable or non-meaningful costs are `null` with source `unavailable`.

Latency is recorded in seconds where available. Provider-reported and locally
measured latency sources remain distinguishable.

## Safe Logging

Provider metadata and error messages are sanitized before logging.
Authorization headers, runtime tokens, API tokens, authenticated URLs, and
secret-like values must not be serialized.

The logging framework operates without loading Phase 6B hidden ground truth.
Ground truth is joined only in later evaluation phases.

## Append And Resume

Attempt logs are JSONL and each completed attempt can be appended immediately.
Before appending, the logger checks whether the same `inference_request_id`
already exists. Exact duplicates are blocked, and conflicting duplicates are
reported as errors.

Resume state can be reconstructed from logged attempts and predictions without
querying backend state.

## Distributed Merge

QMUL and RunPod may write backend-local logs separately. Merge uses:

- `inference_request_id`;
- `prediction_record_id`;
- model identity/config version;
- prompt package version;
- response schema version.

The merge utility rejects conflicting duplicate attempts, incompatible prompt
packages, incompatible config versions, missing model identity, mixed
synthetic/production run types, and secret-like transferred metadata.

## Command

Run the synthetic logged mock integration:

```powershell
python llm-experiments\scripts\run_phase6e3_logging.py
```

Expected synthetic/mock structure:

- 88 attempt records;
- 88 canonical prediction records;
- all primary valid;
- no repairs;
- no duplicates;
- no ground truth;
- no real model responses.
