# Phase 6G.2C RunPod Centaur Production Verification Report

Scope: RunPod/Centaur production verification only. No study prompts, no 396 real predictions, no hidden ground truth, and no Phase 6D prompt-package changes are included.

## Status

Live RunPod evidence now identifies the Centaur adapter, base model, runtime, tokenizer status, and production context policy. The artifact remains intentionally not production-verified because the corrected offline snapshot verifier has not yet been rerun live with both `--probe-load` and `--probe-generation`.

| Field | Status |
| --- | --- |
| Scientific model | Centaur |
| Adapter repository | `marcelbinz/Llama-3.1-Centaur-70B-adapter` |
| Adapter revision | `159600db8be99dc183c289923148dfd96cbd8e07` |
| Adapter snapshot | `/workspace/huggingface/hub/models--marcelbinz--Llama-3.1-Centaur-70B-adapter/snapshots/159600db8be99dc183c289923148dfd96cbd8e07` |
| Deployment form | adapter |
| Base model | `unsloth/Meta-Llama-3.1-70B-bnb-4bit` |
| Base revision | `a009b8db2439814febe725486a5ed388f12a8744` |
| Base snapshot | `/workspace/huggingface/hub/models--unsloth--Meta-Llama-3.1-70B-bnb-4bit/snapshots/a009b8db2439814febe725486a5ed388f12a8744` |
| Runtime | Python 3.12.3, torch 2.11.0+cu129, transformers 5.5.0, peft 0.20.0, bitsandbytes 0.50.0, accelerate 1.14.0, huggingface_hub 1.27.0, unsloth 2026.8.15, unsloth_zoo 2026.8.10, CUDA 12.9 |
| GPU | NVIDIA A100 80GB PCIe on `cuda:0` |
| Precision/quantisation | 4-bit bitsandbytes, `dtype=None`, production `load_in_4bit=True` |
| Production loader | `FastLanguageModel.from_pretrained(..., max_seq_length=32768, dtype=None, load_in_4bit=True)` followed by `FastLanguageModel.for_inference(model)` |
| Tokenizer | `TokenizersBackend`; chat template absent |
| Underlying tokenizer limit | `131072` |
| Effective production context limit | `32768` |
| Message serialization | deterministic concatenation of frozen Phase 6D system and user content; no semantic wording changes |
| Decoding | greedy, `do_sample=false`, `max_new_tokens=256` |
| Structured output | ordinary text generation plus local `preference_prediction_response_v1` validation and one formatting-only repair |
| `<< >>` convention | recommendation exists; technically required is false; primary experiment retains common frozen Phase 6D prompt for cross-model equivalence |
| Adapter readiness | corrected offline snapshot verifier prepared; live rerun required |

## Corrected Live Rerun Command

Run this inside RunPod:

```bash
/workspace/unsloth_env/bin/python llm-experiments/scripts/remote/verify_runpod_centaur.py \
  --deployed-model-source marcelbinz/Llama-3.1-Centaur-70B-adapter \
  --deployment-form adapter \
  --base-model unsloth/Meta-Llama-3.1-70B-bnb-4bit \
  --revision 159600db8be99dc183c289923148dfd96cbd8e07 \
  --base-revision a009b8db2439814febe725486a5ed388f12a8744 \
  --adapter-snapshot /workspace/huggingface/hub/models--marcelbinz--Llama-3.1-Centaur-70B-adapter/snapshots/159600db8be99dc183c289923148dfd96cbd8e07 \
  --base-snapshot /workspace/huggingface/hub/models--unsloth--Meta-Llama-3.1-70B-bnb-4bit/snapshots/a009b8db2439814febe725486a5ed388f12a8744 \
  --serving-framework unsloth.FastLanguageModel \
  --quantisation 4bit_bnb \
  --precision bnb_4bit_runtime_dtype_auto \
  --choice-recommendation-exists true \
  --choice-technically-required false \
  --choice-evidence-note "Centaur << >> recommendation exists but is not technically required for generation." \
  --probe-load \
  --probe-generation \
  --local-files-only \
  --output llm-experiments/outputs/real/phase6g2_remote/phase6g2c_runpod_centaur_verification.json
```

The trivial non-study generation remains:

```text
Reply exactly with: Centaur connectivity verified.
```

The verifier creates a temporary non-repository adapter copy and rewrites only that temporary `adapter_config.json` so `base_model_name_or_path` points to the exact local base snapshot. It does not modify canonical cached adapter files and does not download anything when `--local-files-only` is used.

## Gates

- `RUNPOD_CENTAUR_EXECUTION_ARCHITECTURE_VERIFIED`: `true`
- `RUNPOD_CENTAUR_PRODUCTION_CONFIG_VERIFIED`: `false`
- `RUNPOD_CENTAUR_VERIFIED`: `false`

Remaining blockers before Phase 6G.2D: successful live model-load health check and successful trivial non-study generation from the corrected offline snapshot verifier.
