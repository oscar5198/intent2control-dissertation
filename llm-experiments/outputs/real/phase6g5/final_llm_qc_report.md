# Phase 6G.5 Final LLM Prediction QC Report

Phase 6G.5 constructs the ground-truth-free prediction package that will be evaluated in Phase 6H.

## Authoritative final sources
- GPT-5.5 (`gpt`): `llm-experiments/outputs/real/phase6g4/gpt/recovery_run_05/final_gpt_predictions.jsonl`
  - rows: 396; conditions: {'non_history': 198, 'personalised_history': 198}; status: final_authoritative_after_targeted_run05
- Claude Sonnet 5 (`claude_sonnet`): `llm-experiments/outputs/real/phase6g4/claude/predictions.jsonl`
  - rows: 396; conditions: {'non_history': 198, 'personalised_history': 198}; status: final_authoritative
- Llama 3.1 70B Instruct (`llama_3_1_70b_instruct`): `llm-experiments/outputs/real/phase6g4/llama_canonical/canonical_predictions.jsonl`
  - rows: 396; conditions: {'non_history': 198, 'personalised_history': 198}; status: final_authoritative
- Centaur (`centaur`): `llm-experiments/outputs/real/phase6g4/centaur_native_run_02/native_predictions.jsonl`
  - rows: 396; conditions: {'non_history': 198, 'personalised_history': 198}; status: final_authoritative

## QC summary
- Total merged rows: 1584 / 1584
- Per-model rows: `{'gpt': 396, 'claude_sonnet': 396, 'llama_3_1_70b_instruct': 396, 'centaur': 396}`
- Condition counts per model: `{'gpt': {'non_history': 198, 'personalised_history': 198}, 'claude_sonnet': {'non_history': 198, 'personalised_history': 198}, 'llama_3_1_70b_instruct': {'non_history': 198, 'personalised_history': 198}, 'centaur': {'non_history': 198, 'personalised_history': 198}}`
- Cross-model request alignment: True
- Duplicate model/request pairs: 0
- Prompt hash mismatches: 0
- Ground truth loaded: False
- Evaluation metrics computed: False

## Capability matrix
- Winner metrics: GPT-5.5, Claude Sonnet 5, Llama 3.1 70B Instruct, Centaur.
- Ranking metrics: GPT-5.5, Claude Sonnet 5, Llama 3.1 70B Instruct, Centaur.
- Rating-error metrics: GPT-5.5, Claude Sonnet 5, and Llama 3.1 70B Instruct only.
- Centaur ratings are unsupported/null because native likelihood inference supplies A-E winner/ranking without a frozen 0-100 rating mapping.

## Gates
- `FINAL_LLM_PREDICTIONS_MERGED=true`
- `FINAL_LLM_PREDICTIONS_QC_PASSED=true`
- `FINAL_LLM_PREDICTIONS_FROZEN=true`
- `GROUND_TRUTH_NOT_LOADED_FOR_PHASE6G5=true`

No held-out human outcomes were loaded, joined, inspected, or scored during this package build.
