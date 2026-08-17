# Phase 6F.2 Synthetic Metric Validation Report

Synthetic/mock metric values are pipeline-validation outputs only and must not be interpreted as model performance.

- Metric protocol version: `phase6f_metric_protocol_v1`
- Nominal single-winner chance reference: `0.2`
- Ground-truth join valid: `true`
- Strict denominator valid: `true`
- LLM scored rows: `88`
- Baseline scored rows: `2`
- LLM continuous coverage: `1`
- LLM ranking coverage: `1`
- Baseline continuous coverage: `1`
- Baseline ranking coverage: `1`

## Denominator Rule

Strict top-1 accuracy includes every expected prediction record for the evaluated subset. Invalid outputs, backend failures, and missing/not-run expected records remain in the denominator and count as non-successes. Valid-only accuracy is diagnostic only.

## Continuous Metrics

MAE and RMSE are computed per valid trial across A-E and aggregated as the mean of per-trial values. They are always reported with valid-output coverage.

## Rank Metrics

Predicted ranks are tie-aware mid-ranks derived from predicted numeric ratings. Explicit ranking is used only to resolve predicted-rating ties for the canonical top label. Spearman is null when observed or predicted rank vectors are constant.

## Baseline Caveat

Phase 6C synthetic smoke baseline currently covers only available aligned smoke rows, not all 11 targets.

No confidence intervals, bootstrap distributions, p-values, hypothesis tests, Bayesian comparisons, scientific plots, or model-ranking claims are emitted in Phase 6F.2.
