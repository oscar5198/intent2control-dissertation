# Phase 6G.2C RunPod Centaur Verification Instructions

Run this only inside the RunPod Centaur environment. Do not use participant
data and do not send study prompts.

1. Deploy or start the Centaur RunPod environment.
2. Make the repository or the `llm-experiments/scripts/remote` scripts
   available inside the pod.
3. If deployment metadata is not discoverable automatically, prepare a local
   JSON metadata file describing the exact Centaur deployment.
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

5. Confirm the artifact states whether the deployed model is one of:

```text
marcelbinz/Llama-3.1-Centaur-70B
marcelbinz/Llama-3.1-Centaur-70B-adapter
```

If the adapter form is used, record the exact base Llama checkpoint.

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
