# Phase 6G.2C RunPod Centaur Production Verification Report

Scope: RunPod/Centaur production verification only. No study prompts, no 396 real predictions, no hidden ground truth, and no Phase 6D prompt-package changes are included.

## Status

No live RunPod/Centaur verification evidence has been copied back locally yet. The current JSON artifact is a safe pending artifact that records the required fields and unresolved status without inventing model identity, revision, runtime, GPU, precision, or tokenizer facts.

| Field | Status |
| --- | --- |
| Scientific model | Centaur |
| Exact checkpoint | `UNVERIFIED` |
| Revision | `UNVERIFIED` |
| Deployment form | `UNVERIFIED` |
| Base model | unresolved; required if adapter deployment is used |
| Runtime versions | `UNVERIFIED` until collected inside RunPod |
| GPU | `UNVERIFIED` until collected inside RunPod |
| Precision/quantisation | `UNVERIFIED` |
| Context limit | `UNVERIFIED` |
| Message serialization | planned official tokenizer chat template if verified |
| Decoding | planned greedy, `do_sample=false`, `max_new_tokens=256` |
| Structured output | ordinary text generation plus local `preference_prediction_response_v1` validation and one formatting-only repair |
| `<< >>` convention | unresolved; do not modify Phase 6D prompts unless technically required |
| Adapter readiness | guarded RunPod HTTP adapter prepared; endpoint contract not live-verified |

## Required Live RunPod Evidence

Run `llm-experiments/scripts/remote/verify_runpod_centaur.py` inside the actual RunPod Centaur environment with a safe metadata JSON and, when ready, `--probe-load --probe-generation` for one trivial non-study prompt:

```bash
python llm-experiments/scripts/remote/verify_runpod_centaur.py \
  --config <runpod-safe-centaur-metadata.json> \
  --probe-load \
  --probe-generation \
  --local-files-only \
  --output llm-experiments/outputs/real/phase6g2_remote/phase6g2c_runpod_centaur_verification.json
```

The metadata/probe result must resolve:

- deployed Centaur repository and exact revision;
- full checkpoint vs adapter, including base model if adapter;
- Python, PyTorch, Transformers, PEFT, bitsandbytes, accelerate, CUDA, GPU, and VRAM;
- precision or quantisation;
- tokenizer class, chat template, and context limit;
- official message serialization for frozen system/user messages;
- `<< >>` convention technical requirement;
- model-load health and trivial generation result;
- RunPod request/response contract and adapter readiness.

## Gates

- `RUNPOD_CENTAUR_EXECUTION_ARCHITECTURE_VERIFIED`: `false`
- `RUNPOD_CENTAUR_PRODUCTION_CONFIG_VERIFIED`: `false`
- `RUNPOD_CENTAUR_VERIFIED`: `false`

Remaining blocker before Phase 6G.2D: live RunPod/Centaur deployment evidence.
