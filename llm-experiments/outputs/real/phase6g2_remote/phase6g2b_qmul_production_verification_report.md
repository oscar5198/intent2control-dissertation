# Phase 6G.2B QMUL Production Verification Report

Scope: QMUL-side production verification only. No study prompts, production inference, hidden ground truth, or performance analysis are included.

| Model | Scientific identity | Execution | Exact version | Decoding | Status |
| --- | --- | --- | --- | --- | --- |
| GPT | GPT-5.5 | OpenAI API from QMUL (`/opt/conda/bin/python`) | `gpt-5.5-2026-04-23` returned from request alias `gpt-5.5` | provider-native; omit `temperature` and optional sampling controls | verified |
| Claude | Claude Sonnet 5 | Anthropic API from QMUL (`/opt/conda/bin/python`) | `claude-sonnet-5` | provider-native; omit deprecated `temperature` and optional sampling controls | verified |
| Llama | Llama 3.1 70B Instruct | local QMUL Transformers (`/tmp/unsloth_env/bin/python`) | HF revision `1605565b47bb9346c5515c34102e054115b4f98b` | greedy, `do_sample=false` | verified |

## Common Contract

- All three QMUL models consume the frozen Phase 6D system/user messages.
- GPT maps the system message through the OpenAI Responses API `instructions` field.
- Claude maps the system message through the Anthropic `system` parameter.
- Llama maps the system/user messages through the official tokenizer chat template via `tokenizer.apply_chat_template(..., tokenize=True, add_generation_prompt=True)`.
- All outputs are ordinary text validated locally against `preference_prediction_response_v1`, with at most one frozen formatting-only repair.
- The shared principle is verified low-variance/native primary inference, not uniform `temperature=0`.

## Llama Runtime

- Python: `3.11.7`
- PyTorch: `2.11.0+cu129`
- Transformers: `5.5.0`
- bitsandbytes: `0.50.0`
- accelerate: `1.14.0`
- requests: `2.34.2`
- CUDA: `12.9`
- GPU: `NVIDIA A40`, count `1`
- Quantisation: 4-bit BitsAndBytes NF4, double quantisation enabled, compute/model dtype `torch.bfloat16`
- Context: tokenizer/model config verified at `131072`
- Operational note: `/tmp/unsloth_env` may be ephemeral; package metadata is captured for recreation.

## Gates

- `QMUL_EXECUTION_ARCHITECTURES_VERIFIED`: `true`
- `QMUL_PRODUCTION_CONFIG_VERIFIED`: `true`
- `QMUL_BACKENDS_VERIFIED`: `true`
- `RUNPOD_CENTAUR_VERIFIED`: `false`
- `PRODUCTION_INFERENCE_READY`: `false`

Remaining blocker before overall Phase 6G.2 production readiness: Phase 6G.2C RunPod/Centaur verification and final reconciliation.
