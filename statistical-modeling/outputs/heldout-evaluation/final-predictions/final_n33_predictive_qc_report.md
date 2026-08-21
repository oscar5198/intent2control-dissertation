# Final N=33 Held-Out Mixed-Effects Predictive Baseline

Primary predictive model: `primary_acoustic`.
Formula: `rating ~ episode + group + z_RMS + z_CF + z_SW + (1 | participant_id) + (1 | stimulus_id)`.

## Counts
- Participants: 33
- Held-out trials: 198
- Candidate predictions: 990
- Trial predictions: 198

## Leakage
- Target leakage absent: True
- Max target rows in training: 0
- Participant history rows retained per fold: [25]

## Gates
- `N33_HELDOUT_SPLIT_MATCHES_PHASE6H1=true`
- `N33_HELDOUT_TARGET_LEAKAGE_ABSENT=true`
- `N33_HELDOUT_MODEL_READY=true`
- `N33_HELDOUT_990_CANDIDATE_PREDICTIONS_COMPLETE=true`
- `N33_HELDOUT_198_TRIAL_PREDICTIONS_COMPLETE=true`
- `N33_HELDOUT_PREDICTIONS_FROZEN=true`
- `MIXED_EFFECTS_LLM_FAIR_COMPARISON_READY=true`

Final metrics computed: false
