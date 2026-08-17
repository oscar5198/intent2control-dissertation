# Phase 6E.1 Multi-Model Inference Framework

Status: model-agnostic interface scaffold only. This phase does not call real
models, freeze final model IDs, set sampling parameters, add credentials,
benchmark throughput, score predictions, inspect real participant outcomes, or
modify the frozen Phase 6D prompt package.

Interface version:

```text
phase6e_inference_interface_v1
```

Required prompt package:

```text
phase6d_prompt_package_v1
```

## Architecture

```text
Rendered Prompt
-> Canonical Inference Request
-> Scientific Model Registry
-> Backend Registry
-> Backend Adapter
-> Canonical Raw Result
-> Response Schema Validator
```

Experiment-facing code consumes Phase 6D rendered prompt objects and selected
scientific model keys. It does not reconstruct prompts, load Phase 6B hidden
ground truth, or decide scoring. Backend adapters handle transport only.

## Model And Backend Separation

Scientific model identity is defined separately from execution backend.

Planned model keys:

- `gpt`
- `claude_sonnet`
- `llama_3_1_70b_instruct`
- `centaur`

Deployment mapping for Phase 6E.1:

- `gpt` -> QMUL backend placeholder;
- `claude_sonnet` -> QMUL backend placeholder;
- `llama_3_1_70b_instruct` -> QMUL backend placeholder;
- `centaur` -> RunPod backend placeholder.

Exact model IDs, checkpoints, endpoint URLs, endpoint shapes, capabilities,
and inference settings remain `TO_FREEZE_IN_PHASE_6E_2`.

## Adapter Boundary

Adapters may transform the canonical request into backend transport envelopes.
They may not change:

- system message text;
- user message text;
- task definition;
- candidate order;
- participant metadata;
- acoustic values;
- history evidence;
- response semantics.

QMUL and RunPod adapters are scaffolds in Phase 6E.1. They expose the common
interface but real invocation raises an error. Only the deterministic mock
adapter is executable in this phase.

## Request Identity

Inference request IDs are deterministic hashes derived from:

```text
rendered_prompt_id + model_key + inference_config_version + attempt_type + attempt_number
```

The ID is independent of endpoint URL, credential, random UUID, and hidden
human outcome. This makes requests suitable for resume and deduplication.

## Response Boundary

Adapters return canonical raw inference results. They do not silently repair or
score malformed responses. A separate validator parses raw text against:

```text
preference_prediction_response_v1
```

Validation statuses include:

- `valid`
- `invalid_json`
- `schema_invalid`
- `missing_response`

The full repair/retry state machine belongs to a later Phase 6E subphase.

## Credentials

Credentials must come from environment variables or secure runtime
configuration. Repository configs may contain only environment-variable names.
Do not commit keys, endpoint tokens, authentication headers, or credential
values, and do not write them into prediction artifacts.

## Commands

Dry-run, with no backend invocation:

```powershell
python llm-experiments\scripts\run_phase6e1_inference.py --mode dry_run
```

Synthetic mock run:

```powershell
python llm-experiments\scripts\run_phase6e1_inference.py --mode mock
```

Both modes run the Phase 6D prompt-package preflight before constructing
requests.

## Phase 6E.2 Responsibilities

Phase 6E.2 must freeze:

- exact model IDs/checkpoints;
- selected QMUL transport mode;
- Centaur RunPod endpoint contract;
- endpoint request and response shapes;
- supported schema-enforcement mechanisms;
- context and generation limits;
- timeout values;
- operational connectivity checks;
- final inference settings.
