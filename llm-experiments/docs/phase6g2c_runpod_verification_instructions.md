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

If the model is already cached and a one-off infrastructure probe is safe, run
only the permitted non-study load/generation checks:

```bash
python llm-experiments/scripts/remote/verify_runpod_centaur.py \
  --config <runpod-safe-centaur-metadata.json> \
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

Required metadata to resolve before `RUNPOD_CENTAUR_VERIFIED` can become true:

- exact Centaur repository/checkpoint and revision;
- merged checkpoint vs adapter, and base model/revision for adapter deployments;
- Python, PyTorch, Transformers, PEFT, bitsandbytes, accelerate, CUDA, GPU, GPU count, and VRAM;
- precision or quantisation;
- tokenizer class, official chat template status, and context limit;
- message serialization method for the frozen Phase 6D system/user messages;
- `<< >>` convention audit and whether it is technically required;
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
