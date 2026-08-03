# Phase 3 Statistical Baseline Summary

## Phase 3A - Mixed-effects model planning

Phase 3A established the hierarchical repeated-measures structure for the final listening study: participants provide repeated 0-100 ratings across two assigned songs, three mixes per song, and five listening episodes. The planned analysis uses participant-level random intercepts to account for repeated measurements.

## Phase 3B - Statistical baselines

The categorical baseline fitted an Episode x Stimulus mixed-effects model to the original categorical synthetic ratings and produced draw-by-draw posterior winning probabilities. The MST feature exploration identified RMS, CF, SW, and SI as the defensible scalar feature predictors and excluded BS from the primary feature model. The feature-based model then generated a separate feature-driven synthetic dataset and fitted the reduced feature/context model used here.

## Phase 3C - Final simulation analysis

The final high-replication simulation attempted 360 fits across sample sizes [20, 30, 40, 50, 60, 80], three scenarios, and 20 replications per condition. Completed fits: 360; failed fits: 0. Operational convergence used zero divergences, max R-hat <= 1.05, and min ESS >= 50; strict convergence used zero divergences, max R-hat <= 1.01, and min ESS >= 100.

## Phase 3D - Final sample-size recommendation

Sixty analysable participants is recommended: 40 and 50 perform well under the moderate scenario, but 60 is the smallest tested sample clearing the final recovery/uncertainty criteria across all three scenarios.
At least 60 complete analysable participants should be retained, with recruitment above this number to accommodate incomplete responses, screening exclusions, or unusable data.

Focused 40-vs-50 results are saved in `sample_size_40_vs_50.csv`; the full summary is saved in `sample_size_summary.csv`.

- Phase 3A: Complete
- Phase 3B: Complete
- Phase 3C: Complete
- Phase 3D: Complete
