# Phase 6G.2A Local Production Configuration Preparation

Scope: local preparation only. No QMUL or RunPod deployment was contacted, no LLM was called, no study prompt was rendered or sent, and no Phase 6D prompt artifact was modified.

## Intended Models

- `gpt`: GPT-5.5 -> QMUL
- `claude_sonnet`: Claude Sonnet 5 -> QMUL
- `llama_3_1_70b_instruct`: Llama 3.1 70B Instruct -> QMUL
- `centaur`: Centaur -> RunPod

## Known Locally

- Scientific model identities are selected at the intended model-name level.
- Exact served IDs, revisions, quantisation, serving frameworks, tokenizers, request contracts, and health checks remain unverified.
- Production inference remains blocked.

## Remote Commands

QMUL:

```bash
python llm-experiments/scripts/remote/verify_qmul_models.py --output llm-experiments/outputs/real/phase6g2_remote/phase6g2b_qmul_model_verification.json
```

RunPod:

```bash
python llm-experiments/scripts/remote/verify_runpod_centaur.py --output llm-experiments/outputs/real/phase6g2_remote/phase6g2c_runpod_centaur_verification.json
```

## Copy-Back Destinations

- QMUL result: `llm-experiments/outputs/real/phase6g2_remote/phase6g2b_qmul_model_verification.json`
- RunPod result: `llm-experiments/outputs/real/phase6g2_remote/phase6g2c_runpod_centaur_verification.json`

## Local Import/Reconciliation

```bash
python llm-experiments/scripts/import_phase6g2_remote_verification.py --qmul llm-experiments/outputs/real/phase6g2_remote/phase6g2b_qmul_model_verification.json --runpod llm-experiments/outputs/real/phase6g2_remote/phase6g2c_runpod_centaur_verification.json --output llm-experiments/outputs/real/phase6g2a/phase6g2d_production_registry_scaffold.json
```

## Planning Count

- Prompt source objects: `396`
- Intended scientific models: `4`
- Expected primary requests after verification: `1584`

## Gates

- `SCIENTIFIC_MODEL_IDENTITIES_SELECTED`: `true`
- `EXACT_DEPLOYMENT_IDENTITIES_VERIFIED`: `false`
- `QMUL_BACKENDS_VERIFIED`: `false`
- `RUNPOD_CENTAUR_VERIFIED`: `false`
- `PRODUCTION_INFERENCE_READY`: `false`
