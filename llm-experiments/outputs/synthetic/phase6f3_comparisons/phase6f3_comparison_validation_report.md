# Phase 6F.3 Synthetic Comparison Validation Report

Synthetic/mock comparison values validate statistical plumbing only and are not evidence about LLM or baseline performance.

- Comparison protocol version: `phase6f_comparison_protocol_v1`
- Cluster unit: `participant_id`
- Production bootstrap replicates: `2000`
- Active bootstrap mode: `test`
- Active bootstrap replicates: `200`
- Master bootstrap seed: `20260814`
- CI method/level: `percentile` / `0.95`
- Personalisation rows: `16`
- LLM-vs-baseline rows: `64`
- Status counts: `{"insufficient_aligned_targets": 64, "ok": 16}`

## Estimand

proportion of eligible held-out participant-trial predictions correctly predicted across the study, with participant-cluster bootstrap uncertainty

## Sign Conventions

Personalisation comparisons use `personalised_history - non_history`. For MAE/RMSE, negative values indicate lower error under personalised history. LLM-vs-baseline comparisons use `LLM - baseline`; negative MAE/RMSE values indicate lower LLM error.

## Baseline Comparator Status

Repository documentation identifies both `categorical_design` and `primary_acoustic` as primary baseline models. No single principal baseline comparator is selected from synthetic values; confirmation is required before real-result reporting.

No p-values, independent-sample t-tests, significance claims, model rankings, final dissertation figures, or scientific interpretations are emitted in Phase 6F.3.
