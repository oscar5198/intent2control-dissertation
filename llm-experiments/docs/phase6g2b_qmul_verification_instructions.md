# Phase 6G.2B QMUL Verification Instructions

Run this only on the QMUL environment. Do not use participant data and do not
send study prompts.

1. Copy or pull the repository on QMUL.
2. Activate the QMUL Python/runtime environment used for model serving.
3. Set only safe runtime variables needed by the verification script, such as
   `QMUL_LLM_ENDPOINT_URL`. Do not write credentials into repository files.
4. If endpoint/model metadata cannot be discovered automatically, prepare a
   local JSON metadata file keyed by `gpt`, `claude_sonnet`, and
   `llama_3_1_70b_instruct`.
5. Run:

```bash
python llm-experiments/scripts/remote/verify_qmul_models.py --output llm-experiments/outputs/real/phase6g2_remote/phase6g2b_qmul_model_verification.json
```

Optional placeholders:

```bash
python llm-experiments/scripts/remote/verify_qmul_models.py \
  --config <qmul-safe-model-metadata.json> \
  --endpoint <model-endpoint-url> \
  --model-list-endpoint <metadata-or-model-list-url> \
  --health-endpoint <health-url> \
  --output llm-experiments/outputs/real/phase6g2_remote/phase6g2b_qmul_model_verification.json
```

6. Inspect the JSON and confirm it contains no credentials or authenticated
   URLs.
7. Copy the result back locally to:

```text
llm-experiments/outputs/real/phase6g2_remote/phase6g2b_qmul_model_verification.json
```

8. After the RunPod artifact is also copied back, run the local import command:

```bash
python llm-experiments/scripts/import_phase6g2_remote_verification.py --qmul llm-experiments/outputs/real/phase6g2_remote/phase6g2b_qmul_model_verification.json --runpod llm-experiments/outputs/real/phase6g2_remote/phase6g2c_runpod_centaur_verification.json --output llm-experiments/outputs/real/phase6g2a/phase6g2d_production_registry_scaffold.json
```
