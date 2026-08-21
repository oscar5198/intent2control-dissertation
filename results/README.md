# Curated Final Results

This directory is the compact examiner-facing result pack for the submitted dissertation. It keeps the machine-readable tables and final figures needed to verify the reported statistical and LLM findings; development outputs remain in the methodology folders only when needed for reproducibility.

## Statistical Results

`statistical/` contains the final mixed-effects evidence:

| File | Dissertation role |
| --- | --- |
| `mixed_effects_coefficients.csv` | Fixed effects, variance components, ICCs, and acoustic-feature coefficients. |
| `mixed_effects_icc.csv` | Compact ICC and residual-share table. |
| `mixed_effects_convergence.csv` | Convergence and diagnostic checks for final empirical models. |
| `heldout_mixed_effects_metrics.csv` | Held-out leave-one-trial-out predictive performance. |
| `heldout_mixed_effects_model_comparison.csv` | Categorical-design versus primary-acoustic held-out comparison. |
| `mixed_effects_coefficients.png` | Dissertation Figure 2 evidence copy. |

Key reported values: the final empirical dataset has 33 participants, 198 participant-song-episode trials, and 990 ratings. The stimulus reference model reports participant ICC 0.145 and stimulus ICC 0.173; the primary acoustic-feature model reports participant ICC 0.156 and stimulus ICC 0.128. `mixed_effects_icc.csv` is copied from `statistical-modeling/outputs/final-model-summaries/n33_primary_mixed_effects_icc.csv`. In held-out prediction, the matched primary acoustic mixed-effects baseline reaches 34.3% Top-1 accuracy.

## LLM Results

`llm/` contains the final LLM evaluation evidence:

| File | Dissertation role |
| --- | --- |
| `llm_model_performance.csv` | Top-1 and summary prediction results for each model and condition. |
| `personalisation_effects.csv` | Paired non-history versus personalised-history changes. |
| `ranking_metrics.csv` | Ranking-oriented metrics. |
| `rating_error_metrics.csv` | Rating-error metrics for models that output numeric ratings. |
| `llm_vs_mixed_effects.csv` | Paired comparison against the mixed-effects baseline. |
| `chance_tests.csv` | Chance-reference tests. |
| `llm_vs_mixed_effects.png` | Dissertation Figure 3 evidence copy. |

Key reported values: without participant history, LLM Top-1 accuracy is close to chance. With personalised history, GPT-5.5 reaches 34.3% Top-1 accuracy and Claude Sonnet 5 reaches 35.9%. The mixed-effects baseline remains the strongest ranking model, and no LLM consistently outperforms it across the retained metrics.

## Provenance

The statistical result sources are `statistical-modeling/outputs/final-model-summaries/` and `statistical-modeling/outputs/heldout-evaluation/mcmc-evaluation/`. The LLM result sources are the final pipeline artifacts under `llm-experiments/outputs/final/`.
