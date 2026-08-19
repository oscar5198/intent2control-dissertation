# Phase 6H.1 QC Report

Phase 6H.1 joins the frozen Phase 6G.5 prediction package to the frozen Phase 6B held-out human outcomes and freezes the evaluation protocol. Final model metrics are not computed here.

## Reconstruction
- Participants: 33 ({'group_01': 17, 'group_02': 16})
- Held-out examples: 198
- Request-condition targets: 396
- Joined model rows: 1584
- Rows per model: {'centaur': 396, 'claude_sonnet': 396, 'gpt': 396, 'llama_3_1_70b_instruct': 396}
- Condition counts by model: {'centaur': {'non_history': 198, 'personalised_history': 198}, 'claude_sonnet': {'non_history': 198, 'personalised_history': 198}, 'gpt': {'non_history': 198, 'personalised_history': 198}, 'llama_3_1_70b_instruct': {'non_history': 198, 'personalised_history': 198}}

## Ties
- Unique highest-rated trials: 182
- Top-rating tie trials: 16
- Non-top tie trials: 12
- Top-1 policy: set_based_credit_for_top_ties

## Metrics
- Primary metric: preferred_mix_top1_accuracy at nominal chance 0.2
- Ranking metric: spearman_rank_correlation
- Rating metrics: MAE over candidate A-E ratings and RMSE over candidate A-E ratings
- Centaur is excluded from rating-error metrics.

## Mixed-Effects Fairness
- Same held-out examples as LLMs: False
- Existing baseline examples: 180
- Frozen LLM examples: 198
- Refit required before final comparison: True
- N=33 convergence diagnostics satisfactory: True
- Incomplete rerun markers present: True

## Data Collection
- Total ratings: 990
- Trials: 198
- Songs: ['id_like_to_know', 'in_the_meantime', 'lead_me', 'pouring_room']
- Episodes: ['EDR-1', 'EDR-2', 'FM-1']

## Gates
- `GROUND_TRUTH_HELDOUT_JOIN_VALID=true`
- `ALL_396_TARGETS_RECONSTRUCTED=true`
- `ALL_1584_MODEL_ROWS_JOINED=true`
- `PERSONALISATION_PAIRING_VALID=true`
- `TIE_POLICY_FROZEN=true`
- `METRIC_PROTOCOL_FROZEN=true`
- `MIXED_EFFECTS_COMPARISON_FAIRNESS_AUDITED=true`
- `PHASE6H1_EVALUATION_PROTOCOL_FROZEN=true`

Final metrics computed: False
