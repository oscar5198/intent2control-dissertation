# Statistical Modeling

This component contains the final statistical modeling support for the MSc
dissertation listening study. It covers the inferential multilevel models,
acoustic-feature model, held-out mixed-effects prediction, and compact
machine-readable outputs used to verify the reported statistical results.

## Final Inputs

The submitted reproducibility path starts from the curated scientific data:

- `../data/processed/participants_final.csv`
- `../data/processed/ratings_final.csv`
- `../data/processed/trial_preferences_final.csv`

The private raw Netlify workbook is intentionally not retained in this
Supporting Material repository. Ancillary audit files that are not duplicated
in `data/processed/` remain in `data/real/`, including the cleaning manifest,
validation summaries, exclusion log, and tie table.

## Acoustic Features

The retained feature-extraction evidence is:

- `notebooks/acoustic_feature_extraction.ipynb`
- `outputs/acoustic-features/final_20_stimulus_feature_table.csv`

The feature table contains the 20 final study stimuli and the scalar acoustic
features used by the final feature model, including RMS, crest factor, stereo
width, and their standardised model predictors.

The notebook is retained as **final feature-table reproduction / verification**
evidence. It reconstructs and validates the final 20-stimulus feature table from
retained processed feature evidence under
`../experimental-design/stimulus-selection/final-selection/source-evidence/`
and the final five-mix traceability package. It does not claim to be a complete
raw-WAV-to-feature extraction pipeline. The final study WAVs are retained under
`../study-interface/frontend-5mix/assets/audio/study-stimuli/main-study/` for
stimulus verification and interface reproducibility.

## Sample-Size Design Evidence

Appendix C of the dissertation reports a design-stage sample-size simulation.
Compact retained evidence is in `outputs/sample-size-analysis/`, including the
sample sizes evaluated, the 180 shortened-chain fits, the N=50 recommendation,
and the four-chain confirmation fit. The full historical simulation archive is
not required for the final submitted results and is intentionally not restored.

## Runnable Entry Points

- `scripts/check_bayesian_environment.py`
- `scripts/fit_final_models.py`
- `scripts/evaluate_heldout_predictions.py`
- `scripts/freeze_final_statistical_results.py`

The model-fitting scripts are intended for an environment with Bambi, PyMC,
ArviZ, and the configured sampler stack. Do not run the expensive Bayesian
models during routine repository checks.

## Final Model Formulas

Stimulus/context model:

```text
rating ~ episode + group + (1 | participant_id) + (1 | stimulus_id)
```

Primary acoustic-feature model:

```text
rating ~ episode + group + z_RMS + z_CF + z_SW + (1 | participant_id) + (1 | stimulus_id)
```

Sensitivity models include a stereo-imbalance extension and a transformed-Beta
bounded-rating check. Dissertation-facing compact coefficients, ICCs,
convergence checks, and held-out metrics are copied to `../results/statistical/`.

## Internal Modules

The internal Python package remains named `statistical_baseline` for import
stability. The final retained modules are:

- `real_data_cleaning.py`
- `real_stimulus_model.py`
- `real_feature_model.py`
- `real_heldout_evaluation.py`
- `heldout.py`
- `phase6h2a_finalize.py`

## Retained Outputs

- `outputs/acoustic-features/`: authoritative final acoustic feature table and
  compact validation summaries.
- `outputs/stimulus-model/`: final stimulus/random-effects model summaries,
  diagnostics, manifests, and posterior summaries.
- `outputs/feature-model/`: final acoustic-feature model summaries,
  diagnostics, manifests, and posterior summaries.
- `outputs/heldout-evaluation/`: retained held-out mixed-effects evaluation and
  final frozen prediction tables.
- `outputs/final-model-summaries/`: compact N=33 empirical summary tables used
  by the final statistical result freeze.

Dissertation-facing final tables and figures are curated in
`../results/statistical/` and `../dissertation/`.
