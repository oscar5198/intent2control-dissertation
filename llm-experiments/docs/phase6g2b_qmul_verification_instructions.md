# QMUL Verification Instructions

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
python llm-experiments/scripts/remote/verify_qmul_models.py --output <local-qmul-verification.json>
```

Optional placeholders:

```bash
python llm-experiments/scripts/remote/verify_qmul_models.py \
  --config <qmul-safe-model-metadata.json> \
  --endpoint <model-endpoint-url> \
  --model-list-endpoint <metadata-or-model-list-url> \
  --health-endpoint <health-url> \
  --output <local-qmul-verification.json>
```

6. Inspect the JSON and confirm it contains no credentials or authenticated
   URLs.
7. Compare the result with the retained final configuration in:

```text
llm-experiments/outputs/final/inference-config/
```

Do not commit local verification artifacts if they contain operational endpoint
details.
