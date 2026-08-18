# Phase 6G.2D Final Production Reconciliation and Freeze

No LLM calls, study prompt rendering, production predictions, or hidden ground-truth reads were performed.

## Exact Model Identities

- `gpt`: GPT-5.5 -> `gpt-5.5` / `gpt-5.5-2026-04-23`
- `claude_sonnet`: Claude Sonnet 5 -> `claude-sonnet-5` / `claude-sonnet-5`
- `llama_3_1_70b_instruct`: Llama 3.1 70B Instruct -> `meta-llama/Llama-3.1-70B-Instruct` / `1605565b47bb9346c5515c34102e054115b4f98b`
- `centaur`: Centaur -> `marcelbinz/Llama-3.1-Centaur-70B-adapter` / `159600db8be99dc183c289923148dfd96cbd8e07`

## Backend Mapping

- `qmul_openai_provider_api_verified`: openai_responses_api on QMUL
- `qmul_anthropic_provider_api_verified`: anthropic_messages_api on QMUL
- `qmul_llama_transformers_local_verified`: qmul_local_transformers on QMUL
- `runpod_centaur_adapter_verified`: runpod_centaur_adapter on RunPod

## Decoding

- GPT-5.5: `provider_native_temperature_omitted`
- Claude Sonnet 5: `provider_native_temperature_omitted`
- Llama 3.1 70B Instruct: `greedy_do_sample_false`
- Centaur: `greedy_do_sample_false`
- Max output tokens: `256`
- Zero-shot, no requested chain-of-thought, one primary generation, one formatting repair maximum.
- Local response validation: `preference_prediction_response_v1`

## Counts

- Prediction examples: `198`
- Prompt-data condition objects: `396`
- Expected rendered prompts: `396`
- Expected primary requests: `1584`
- Dry-run manifest requests: `1584`

## Gates

- `MODEL_IDENTITIES_FROZEN`: `true`
- `EXACT_DEPLOYMENT_IDENTITIES_VERIFIED`: `true`
- `INFERENCE_BACKENDS_VERIFIED`: `true`
- `PRIMARY_INFERENCE_CONFIG_FROZEN`: `true`
- `PRODUCTION_INFERENCE_READY`: `true`

Phase 6G.2 complete: `true`
Phase 6G.3 can begin immediately: `true`
