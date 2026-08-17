# Phase 6E.2 Primary Inference Configuration

Status: configuration and verification scaffold complete; production inference
is not yet allowed.

Configuration version:

```text
phase6e_primary_inference_config_v1
```

Prompt package requirement:

```text
phase6d_prompt_package_v1
```

Response schema:

```text
preference_prediction_response_v1
```

## Verification Principle

Exact model identities, checkpoints, endpoint shapes, capabilities, context
limits, tokenizer behavior, and supported parameters are recorded only when
verified from the actual execution environment or authoritative deployment
configuration. Repository inspection found no authoritative QMUL serving
contract and no Centaur RunPod deployment contract. Therefore these fields are
explicitly marked `UNVERIFIED` rather than guessed.

## Scientific Models

| Model key | Display name | Deployment | Exact identity status |
| --- | --- | --- | --- |
| `gpt` | GPT-family model | QMUL | `UNVERIFIED` |
| `claude_sonnet` | Claude Sonnet-family model | QMUL | `UNVERIFIED` |
| `llama_3_1_70b_instruct` | Llama 3.1 70B Instruct | QMUL | `UNVERIFIED` |
| `centaur` | Centaur | RunPod | `UNVERIFIED` |

Scientific model identity remains independent of temporary hostnames,
endpoint URLs, ports, and authentication configuration.

## Shared Inference Philosophy

Primary inference should be reproducible and low variance:

- one primary generation per model x rendered prompt;
- no best-of-N;
- no self-consistency voting;
- no few-shot examples;
- no requested chain-of-thought;
- no rationale or reasoning field;
- no prompt changes by model;
- local validation against `preference_prediction_response_v1`.

Preferred canonical sampling policy:

- temperature: `0` where supported;
- top-p: backend default with temperature 0, or explicit `1` if required by
  a verified backend contract;
- project seed: `20260814` where seed control is supported;
- max output allowance: `256` tokens.

These values are not chosen from model performance. Backend-specific effective
settings remain `UNVERIFIED` until the deployments are inspected.

## Backend Contracts

Current tracked runtime placeholders:

- QMUL endpoint URL environment variable: `QMUL_LLM_ENDPOINT_URL`
- QMUL token environment variable: `QMUL_LLM_API_TOKEN`
- RunPod Centaur endpoint URL environment variable:
  `RUNPOD_CENTAUR_ENDPOINT_URL`
- RunPod token environment variable: `RUNPOD_API_TOKEN`

Tracked files must not contain credentials, authenticated URLs, authorization
headers, runtime tokens, or secret values.

Operational timeout defaults:

- QMUL: `300` seconds;
- RunPod Centaur: `600` seconds.

These are finite infrastructure defaults for later connectivity testing, not
scientific sampling settings or model-quality judgments.

## Structured Output

Each model must use one of these mechanisms when verified:

- native JSON Schema enforcement;
- native JSON mode plus local schema validation;
- text generation plus local schema validation.

Regardless of backend mechanism, the semantic response contract remains
`preference_prediction_response_v1`.

## Context Compatibility

The largest current synthetic rendered prompt is recorded by character count.
Tokenizer-specific prompt-token counts and model context limits are
`UNVERIFIED` for all four models because no actual tokenizers or serving
contracts are available in the repository.

Prompt content must not be shortened or changed in Phase 6E.2 to fit an
unverified context assumption.

## Freeze Gates

Current gate status:

```text
MODEL_IDENTITIES_FROZEN=false
INFERENCE_BACKENDS_VERIFIED=false
PRIMARY_INFERENCE_CONFIG_FROZEN=false
```

`MODEL_IDENTITIES_FROZEN` can become true only after all four exact model IDs
and checkpoints/revisions are verified.

`INFERENCE_BACKENDS_VERIFIED` can become true only after QMUL and RunPod
request/response contracts, serving modes, required capabilities, and health
checks are verified.

`PRIMARY_INFERENCE_CONFIG_FROZEN` can become true only after model identities,
backend contracts, prompt-package preflight, structured-output strategy,
generation settings, context compatibility, and semantic adapter constraints
all pass.

## Commands

Validate Phase 6E.2 configuration and write synthetic structural artifacts:

```powershell
python llm-experiments\scripts\validate_phase6e2_config.py
```

This command does not call real models, does not send Phase 6D prompts to
endpoints, and does not inspect ground truth.

## Phase 6E.3 Boundary

Phase 6E.3 may build execution planning/logging on this configuration scaffold,
but production inference must remain blocked until the Phase 6E.2 gates are
updated from verified deployment evidence.
