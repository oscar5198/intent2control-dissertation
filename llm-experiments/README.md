# LLM Experiments

This folder contains the reproducible LLM methodology for the dissertation's
held-out mix-preference prediction experiment.

## Purpose

The task is to predict which of five mixes a participant preferred in a held-out listening trial. Each prediction uses the final 5-mix study data and is evaluated against the participant's observed A-E ratings.

## Models

The final evaluated models are GPT-5.5, Claude Sonnet 5, Llama 3.1 70B Instruct, and Centaur.

## Conditions

- `non_history`: target listening context, song/mix candidates, acoustic features, and participant metadata, without the participant's earlier trial history.
- `personalised_history`: the same target information plus the participant's prior trial ratings/comments available before the held-out target.

## Pipeline

```text
study data
-> prompt data
-> rendered prompts
-> model predictions
-> ground-truth join
-> evaluation
-> curated results
```

Final retained artifacts are under:

- `outputs/final/prompt-data/`
- `outputs/final/rendered-prompts/`
- `outputs/final/inference-config/`
- `outputs/final/model-predictions/`
- `outputs/final/evaluation/`

Curated dissertation-facing result files are in `../results/llm/`.

## Code Map

- `src/llm_experiments/data/` builds analysis-ready rows, held-out targets, prediction examples, and prompt-data objects.
- `src/llm_experiments/prompts/` defines, renders, freezes, and validates the final prompt package.
- `src/llm_experiments/inference/` contains shared inference infrastructure and final model-specific runners.
- `src/llm_experiments/inference/phase6g5_final_predictions.py` consolidates model-specific predictions into the authoritative final prediction package.
- `src/llm_experiments/evaluation/phase6h1_protocol_freeze.py` joins predictions to held-out ground truth and freezes the evaluation protocol.
- `src/llm_experiments/evaluation/phase6h2b_final_scoring.py` computes final LLM metrics and mixed-effects comparisons.
- `src/llm_experiments/evaluation/phase6h3_results_synthesis.py` builds dissertation-facing result tables and figures.

Internal module names retain historical phase identifiers where imports and
tests rely on them. The README uses the final scientific workflow names; the
phase-coded filenames are provenance/version identifiers.

## Entry Points

Final-facing script wrappers:

- `scripts/build_final_prompt_data.py`
- `scripts/render_final_prompts.py`
- `scripts/run_gpt55_predictions.py`
- `scripts/run_claude_sonnet5_predictions.py`
- `scripts/run_llama_3_1_70b_predictions.py`
- `scripts/run_centaur_predictions.py`
- `scripts/consolidate_final_predictions.py`
- `scripts/verify_prompt_package.py`
- `scripts/validate_experimental_conditions.py`

Model-running scripts call external providers/backends and should not be run
during repository maintenance.

Final scoring is retained as module entry points:

```powershell
$env:PYTHONPATH = "llm-experiments/src"
python -c "from pathlib import Path; from llm_experiments.evaluation.phase6h2b_final_scoring import run_phase6h2b_final_scoring; run_phase6h2b_final_scoring(Path('.'))"
python -m llm_experiments.evaluation.phase6h3_results_synthesis
```

## Prompts, Config, And Schemas

Final prompt assets:

- `prompts/phase6d_prompt_template_v1.json`
- `prompts/phase6d_prompt_package_manifest.json`
- `prompts/prompt_specification.md`

The prompt template and manifest are not renamed because the manifest records
their exact paths and SHA-256 hashes as part of the frozen prompt package.

Final configuration:

- `config/phase6e_backend_registry_v1.json`
- `config/phase6e_model_registry_v1.json`
- `config/phase6e_primary_inference_config_v1.json`
- `config/phase6e_capability_matrix_v1.json`
- `config/phase6e_failure_policy_v1.json`

Final schemas:

- `schema/analysis_ready_schema.csv`
- `schema/preference_target_schema.csv`
- `schema/preference_prediction_response_v1.json`
- `schema/rendered_prompt_v1.json`
- `schema/phase6e_*_v1.json`
- `schema/phase6g_*_v1.json`

## Final Prediction Evidence

The authoritative consolidated predictions are:

- `outputs/final/model-predictions/llm_heldout_predictions.jsonl`
- `outputs/final/model-predictions/llm_heldout_predictions.csv`
- `outputs/final/model-predictions/prediction_inventory.json`
- `outputs/final/model-predictions/prediction_freeze_manifest.json`

Model-specific retained sources are in `outputs/final/model-predictions/source/`.

## Evaluation

Final evaluation inputs and outputs are under `outputs/final/evaluation/`, including:

- `heldout_ground_truth.csv`
- `predictions_with_ground_truth.jsonl`
- `metric_protocol.json`
- `tie_policy.json`
- `top1_accuracy.csv`
- `ranking_metrics.csv`
- `rating_error_metrics.csv`
- `personalisation_effects.csv`
- `llm_vs_mixed_effects.csv`
- `chance_tests.csv`

The compact examiner-facing copies are in `../results/llm/`.

## External Environments

GPT-5.5 and Claude Sonnet 5 require provider/API access. Llama 3.1 70B Instruct
requires the QMUL/local GPU and Hugging Face runtime used for the final
prediction run. Centaur requires RunPod or an equivalent GPU environment with
the retained Centaur adapter/base-model configuration. No credentials are stored
in this repository.
