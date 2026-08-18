# Phase 6G.2C RunPod Centaur Verification Instructions

Run this only inside the RunPod Centaur environment. Do not use participant
data and do not send study prompts.

1. Deploy or start the Centaur RunPod environment.
2. Make the repository or the `llm-experiments/scripts/remote` scripts
   available inside the pod.
3. Prepare a local JSON metadata file describing the exact Centaur deployment.
   Do not include secrets. Include only environment variable names, sanitized
   paths, model IDs, revisions, runtime versions, tokenizer/config metadata,
   and the trivial non-study probe result.
   You may start from:

```text
llm-experiments/docs/phase6g2c_runpod_centaur_metadata_template.json
```
4. Run:

```bash
python llm-experiments/scripts/remote/verify_runpod_centaur.py --output llm-experiments/outputs/real/phase6g2_remote/phase6g2c_runpod_centaur_verification.json
```

Optional placeholders:

```bash
python llm-experiments/scripts/remote/verify_runpod_centaur.py \
  --config <runpod-safe-centaur-metadata.json> \
  --endpoint <runpod-endpoint-url> \
  --deployed-model-source <exact-centaur-repository-or-path> \
  --deployment-form <merged|adapter|unknown> \
  --base-model <exact-base-llama-checkpoint-if-adapter> \
  --revision <revision-or-commit> \
  --serving-framework <serving-framework> \
  --choice-technically-required unknown \
  --choice-evidence-note <short-source-note> \
  --output llm-experiments/outputs/real/phase6g2_remote/phase6g2c_runpod_centaur_verification.json
```

For the current production Centaur adapter deployment, use the exact cached
adapter and base snapshots. The verifier creates a temporary non-repository
copy of `adapter_config.json` that points `base_model_name_or_path` to the
local base snapshot. It does not modify canonical Hugging Face cache files and
must not download anything.

Run this exact command inside RunPod:

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

The trivial probe is fixed to:

```text
Reply exactly with: Centaur connectivity verified.
```

Do not send participant metadata, listening contexts, acoustic features, study
candidates, or rendered study prompts.

5. Confirm the artifact states whether the deployed model is one of:

```text
marcelbinz/Llama-3.1-Centaur-70B
marcelbinz/Llama-3.1-Centaur-70B-adapter
```

If the adapter form is used, record the exact base Llama checkpoint.

Known live metadata now frozen in the verifier artifact:

- adapter repository: `marcelbinz/Llama-3.1-Centaur-70B-adapter`;
- adapter revision: `159600db8be99dc183c289923148dfd96cbd8e07`;
- adapter snapshot: `/workspace/huggingface/hub/models--marcelbinz--Llama-3.1-Centaur-70B-adapter/snapshots/159600db8be99dc183c289923148dfd96cbd8e07`;
- base model: `unsloth/Meta-Llama-3.1-70B-bnb-4bit`;
- base revision: `a009b8db2439814febe725486a5ed388f12a8744`;
- base snapshot: `/workspace/huggingface/hub/models--unsloth--Meta-Llama-3.1-70B-bnb-4bit/snapshots/a009b8db2439814febe725486a5ed388f12a8744`;
- production loader: `FastLanguageModel.from_pretrained(..., max_seq_length=32768, dtype=None, load_in_4bit=True)` followed by `FastLanguageModel.for_inference(model)`;
- tokenizer chat template: absent;
- underlying tokenizer limit: `131072`;
- effective production context limit: `32768`;
- message serialization: deterministic concatenation of frozen Phase 6D system and user content with no semantic wording changes;
- `<< >>` recommendation exists, but it is not technically required, so the primary experiment retains the common frozen Phase 6D prompt for cross-model equivalence.

Required live rerun evidence before `RUNPOD_CENTAUR_VERIFIED` can become true:

- model-load health and trivial generation result;
- RunPod endpoint request/response contract.

6. Inspect the JSON and confirm it contains no credentials or authenticated
   URLs.
7. Copy the result back locally to:

```text
llm-experiments/outputs/real/phase6g2_remote/phase6g2c_runpod_centaur_verification.json
```

8. After the QMUL artifact is also copied back, run the local import command:

```bash
python llm-experiments/scripts/import_phase6g2_remote_verification.py --qmul llm-experiments/outputs/real/phase6g2_remote/phase6g2b_qmul_model_verification.json --runpod llm-experiments/outputs/real/phase6g2_remote/phase6g2c_runpod_centaur_verification.json --output llm-experiments/outputs/real/phase6g2a/phase6g2d_production_registry_scaffold.json
```
