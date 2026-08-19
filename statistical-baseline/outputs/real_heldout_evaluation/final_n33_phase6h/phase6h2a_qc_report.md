# Phase 6H.2A QC Report

The full N=33 empirical mixed-effects analysis is preserved as the central statistical analysis. The matched N=33/198 held-out predictive baseline is frozen separately for later scoring.

## Empirical Models
- Stimulus model: `rating ~ episode + group + (1 | participant_id) + (1 | stimulus_id)`
- Feature model: `rating ~ episode + group + z_RMS + z_CF + z_SW + (1 | participant_id) + (1 | stimulus_id)`
- Convergence usable: stimulus=True, feature=True

## Predictive Baseline
- Candidate predictions: 990
- Trial predictions: 198
- Same Phase 6H.1 targets: True
- Final metrics computed: False

## Gates
- `N33_EMPIRICAL_MODELS_FOUND=true`
- `N33_STIMULUS_MODEL_CONVERGED=true`
- `N33_FEATURE_MODEL_CONVERGED=true`
- `N33_EMPIRICAL_RESULTS_READY=true`
- `N33_INCOMPLETE_MARKERS_RESOLVED=true`
- `N33_HELDOUT_SPLIT_MATCHES_PHASE6H1=true`
- `N33_HELDOUT_TARGET_LEAKAGE_ABSENT=true`
- `N33_HELDOUT_MODEL_READY=true`
- `N33_HELDOUT_990_CANDIDATE_PREDICTIONS_COMPLETE=true`
- `N33_HELDOUT_198_TRIAL_PREDICTIONS_COMPLETE=true`
- `N33_HELDOUT_PREDICTIONS_FROZEN=true`
- `MIXED_EFFECTS_LLM_FAIR_COMPARISON_READY=true`
