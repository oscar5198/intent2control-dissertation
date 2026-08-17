# Statistical Baseline

This directory contains the dissertation statistical-baseline component. It keeps
the baseline notebooks, synthetic baseline data, and generated model outputs
together so the analysis can be understood without chasing files across the
repository.

The baseline is used to stress-test and document the planned human-response
analysis before final participant data are available. It does not replace the
later held-out comparison against the LLM experiments; instead it defines the
statistical analysis route that LLM predictions can later be compared against.

## Current Locations

- Notebooks: `notebooks/`
- Generated outputs: `outputs/`
- Synthetic baseline data: `data/synthetic/`
- Dissertation-ready tables: `../dissertation/tables/`
- Dissertation-ready figures: `../dissertation/figures/`

The baseline still reads shared stimulus-selection feature evidence from
`../outputs/stimulus_selection/` where needed. Those source files are shared
project evidence and are not duplicated here.

## Implemented Work

- Bambi/PyMC/ArviZ modelling notebooks
- participant random-effect models
- final additive stimulus mixed model
- final additive acoustic-feature mixed model
- SI sensitivity feature model
- final-design sample-size simulation
- draw-by-draw posterior winner calculations
- final evaluation support material
- Phase 6C.1 held-out baseline dry-run infrastructure for alignment with the
  Phase 6B leave-one-trial-out prediction examples
- Phase 6C.2 frozen execution protocol and synthetic posterior-prediction
  smoke test for the held-out Bayesian baseline
- Phase 6C.3 automatic consolidation, output validation, QC reporting, and
  Phase 6F-ready baseline prediction export

## Notebook Sequence

1. `notebooks/_01_synthetic_data_generation.ipynb`
2. `notebooks/_02_categorical_stimulus_model.ipynb`
3. `notebooks/_03_mst_feature_exploration.ipynb`
4. `notebooks/_04_feature_based_model.ipynb`
5. `notebooks/_05_sample_size_simulation.ipynb`

## Outputs

- `outputs/stimulus_model/`: current final-design stimulus mixed model outputs.
- `outputs/feature_exploration/`: current final 20-stimulus scalar acoustic-feature exploration.
- `outputs/feature_model/`: current final-design acoustic-feature model outputs and posterior winner checks.
- `outputs/sample_size_simulation/`: current final-design simulation-based sample-size results.
- `outputs/phase3_summary.md`: final Phase 3 baseline summary and status.

Historical output folders such as `outputs/categorical_model/`,
`outputs/mst_feature_exploration/`, and `outputs/feature_based_model/` are
superseded old-design artefacts and should not be used as the current
dissertation result.

Long PyMC/Bambi sampling should not be rerun casually during repository
maintenance. For structural validation, prefer path checks and lightweight data
loading unless the statistical analysis itself is being intentionally updated.

## Phase 6C Held-Out Baseline Alignment

Phase 6C prepares the existing Phase 3 Bayesian mixed-effects baseline for a
fair later comparison with the Phase 6 LLM predictions. It does not redesign the
statistical models.

The aligned prediction unit is one Phase 6B `prediction_example_id`, equivalent
to one participant x held-out target trial. For each target, all five
candidate-rating rows from that target `trial_id` are excluded from model
fitting. The same participant's other trials remain in training so the
participant random intercept can be estimated from non-target evidence. Ratings
from other participants for the same `stimulus_id` may remain because the target
is not an unseen-stimulus task; only the target participant's held-out trial
outcomes are forbidden.

Frozen Phase 3 formulas retained for Phase 6C:

- `categorical_design`:
  `rating ~ episode + group + (1 | participant_id) + (1 | stimulus_id)`
- `primary_acoustic`:
  `rating ~ episode + group + z_RMS + z_CF + z_SW + (1 | participant_id) + (1 | stimulus_id)`
- `si_sensitivity`:
  `rating ~ episode + group + z_RMS + z_CF + z_SW + z_SI + (1 | participant_id) + (1 | stimulus_id)`

Primary dry-run models are `categorical_design` and `primary_acoustic`.
`si_sensitivity` is available only when explicitly requested.

Configuration is centralized in:

```text
statistical-baseline/config/phase6c_baseline_models.json
```

The frozen Phase 6C.2 baseline prediction protocol is
`phase6c_baseline_prediction_v1`. The prediction quantity is the posterior
expected mean rating for each A-E candidate. Candidate intervals use the central
95% credible interval over posterior expected-rating draws. The candidate with
the highest posterior mean expected rating is the predicted preferred mix; exact
mean ties are marked as tied without consulting ground truth. Posterior winning
probability is calculated draw-by-draw, splitting a draw equally across tied
maxima.

Final production inference settings are locked to the Phase 3 Bayesian
configuration:

```text
draws=1000
tune=1000
chains=4
cores=1
target_accept=0.95
inference_method=nutpie
```

The smoke-test mode is intentionally non-analytical and synthetic-only:

```text
draws=5
tune=5
chains=1
cores=1
target_accept=0.95
inference_method=default
```

Participant random intercepts are included when the held-out participant has
non-target training rows. Stimulus random intercepts are included when the
candidate stimulus level exists in the target-specific training fit. Reference
categorical levels and unavailable random-effect levels contribute zero to the
posterior expected mean; no held-out target ratings are used to create those
terms.

Run the synthetic Phase 6C dry-run from the repository root:

```powershell
python statistical-baseline\scripts\run_heldout_baseline.py --dry-run `
  --analysis-ready llm-experiments\outputs\synthetic\phase6b5\final_analysis_ready_long.csv `
  --prediction-examples llm-experiments\outputs\synthetic\phase6b5\final_prediction_examples.jsonl `
  --output-dir statistical-baseline\outputs\phase6c1_synthetic_dry_run
```

The dry run loads data, constructs target-specific training/test slices,
validates that target rows are excluded, checks Phase 6B A-E/stimulus alignment,
reports expected fit count, writes fit plans, and does not sample Bayesian
models.

Run the Phase 6C.2 synthetic posterior-prediction smoke test:

```powershell
python statistical-baseline\scripts\run_heldout_baseline.py --smoke-test --no-resume `
  --analysis-ready llm-experiments\outputs\synthetic\phase6b5\final_analysis_ready_long.csv `
  --prediction-examples llm-experiments\outputs\synthetic\phase6b5\final_prediction_examples.jsonl `
  --output-dir statistical-baseline\outputs\phase6c2_synthetic_smoke_test `
  --smoke-targets 1
```

The current synthetic smoke test fits one deterministic synthetic held-out
target,
`SYNTHETIC_PHASE6B1_P001__heldout__SYNTHETIC_PHASE6B1_P001__trial_01`, for the
two primary models: `categorical_design` and `primary_acoustic`. It writes
`configuration_snapshot.json`, `fit_manifest.csv`, `fit_diagnostics.csv`,
`candidate_predictions.csv`, `trial_prediction_summary.csv`, and
`execution_summary.json`. With the deliberately tiny smoke-test chains, fit
diagnostics are expected to report `convergence_warning`; this confirms the
execution path, not dissertation-ready inference.

## Phase 6C.3 Baseline Output Consolidation

Phase 6C.3 consolidates Phase 6C.2 target-by-model fit outputs into canonical
prediction-side artifacts for later Phase 6 evaluation. It performs output
engineering and QC only. It does not join hidden human ground truth, calculate
accuracy, compare models, compare against LLMs, or alter the frozen baseline
formulas/configuration.

Run the synthetic smoke consolidation from the repository root:

```powershell
python statistical-baseline\scripts\consolidate_heldout_baseline_outputs.py `
  --fit-output-dir statistical-baseline\outputs\phase6c2_synthetic_smoke_test `
  --prediction-examples llm-experiments\outputs\synthetic\phase6b5\final_prediction_examples.jsonl `
  --output-dir statistical-baseline\outputs\phase6c3_synthetic_smoke_consolidated `
  --mode partial `
  --run-type synthetic_smoke
```

Canonical Phase 6C.3 outputs:

- `phase6c_canonical_candidate_predictions.csv`: one row per
  `prediction_example_id x baseline_model x presentation_label`, preserving
  posterior mean expected rating, posterior SD, 95% credible interval, posterior
  winning probability, model role, fit status, and protocol version.
- `phase6c_canonical_trial_predictions.csv`: one row per
  `prediction_example_id x baseline_model`, preserving predicted ratings A-E,
  predicted preferred label/tie state, winning probabilities A-E, model role,
  fit status, and protocol version.
- `phase6c_consolidated_fit_diagnostics.csv`: one row per
  `prediction_example_id x baseline_model` with Phase 6C.2 sampling and
  convergence fields.
- `phase6c_completion_manifest.csv`: one row per expected fit, marking
  expected/completed/missing/warning/failed/output-validated status.
- `phase6f_evaluation_ready_baseline_predictions.csv`: compact prediction-only
  table for later Phase 6F joining on `prediction_example_id`.
- `phase6c_baseline_output_qc_summary.json`: machine-readable QC counts and
  completion flags.
- `phase6c_baseline_output_summary.md`: human-readable summary generated from
  the QC data.

The Phase 6F-facing schema is documented in:

```text
statistical-baseline/schema/phase6f_evaluation_ready_baseline_prediction_schema.csv
```

This table contains predictions only. It must not contain hidden observed
outcome fields such as observed ratings, observed preferred labels, observed
ranks, target comparative comments, or Phase 6B `ground_truth`. Phase 6F will
join ground truth later using `prediction_example_id`.

The consolidator validates:

- all expected manifest fits are represented;
- completed fits have exactly five A-E candidate rows and one trial summary;
- duplicate candidate, trial, diagnostic, or manifest rows are detected;
- candidate probabilities are numeric, in `[0, 1]`, and sum to 1 within
  `1e-6`;
- trial-level ratings and winning probabilities exactly reproduce
  candidate-level values;
- `predicted_preferred_mix`, predicted ties, and tied labels follow the frozen
  posterior-mean winner rule;
- Phase 6B prediction-example alignment by participant ID, trial ID, and
  candidate `stimulus_id`;
- protocol/configuration consistency for formula, protocol version, inference
  mode, draws, tune, chains, target acceptance, and sampling backend;
- smoke-test outputs are not accepted as final production outputs;
- no observed-outcome leakage appears in canonical prediction files.

Partial mode writes QC artifacts for incomplete or resumed runs and marks
completion false when required outputs are absent. Final mode returns a non-zero
exit code when the primary completion gate fails.

`BASELINE_PRIMARY_OUTPUTS_COMPLETE=true` only when all expected primary fits are
present, no primary fit is missing or failed, completed primary fits validate
with exactly five A-E candidate rows and one trial summary, diagnostics exist,
Phase 6B alignment passes, probabilities and preferred-mix rules validate,
candidate/trial consistency validates, run configuration is compatible, and no
leakage is detected. `convergence_warning` counts as structurally completed but
remains flagged; `fit_failed` prevents complete evaluation coverage and no
evaluation-ready prediction row is fabricated for it.

Phase 6C prediction outputs are designed as:

- candidate-level predictions:
  `schema/phase6c_candidate_prediction_schema.csv`
- trial-level summaries:
  `schema/phase6c_trial_summary_schema.csv`
- fit diagnostics:
  `schema/phase6c_fit_diagnostic_schema.csv`

The primary baseline preferred mix is the candidate with the highest posterior
mean expected rating. Exact ties are marked as tied without using human ground
truth. Posterior winning probabilities, when generated, are computed
draw-by-draw; draw-level ties split probability equally across tied maxima.

Future real-data execution should use the same script paths with the final
complete Phase 6B analysis-ready dataset and prediction examples, writing to a
non-committed real-data output directory. The production CLI flag is present but
intentionally guarded until final survey data are locked; it must not be used on
partial participant outcomes.

Future production command template:

```powershell
python statistical-baseline\scripts\run_heldout_baseline.py --production `
  --analysis-ready <final_phase6_analysis_ready_long.csv> `
  --prediction-examples <final_phase6_prediction_examples.jsonl> `
  --output-dir <non_committed_final_baseline_output_dir>
```

Repeated leave-one-trial-out fitting is expected to be computationally heavier
than the original Phase 3 fits. The runner is structured for resumability:
completed valid candidate-level prediction outputs can be detected and skipped
on resume, fit status is recorded per `prediction_example_id x baseline_model`,
and failed or warning fits should be retained in diagnostics rather than
silently discarded.

The execution manifest records one row per
`prediction_example_id x baseline_model`, including the model formula, protocol
version, inference mode, target-exclusion counts, training-row counts, and
whether candidate/diagnostic outputs already exist. Resume mode treats a fit as
complete only when `candidate_predictions.csv` contains five `fit_ok` candidate
rows for that `prediction_example_id x baseline_model`; warning and failed fits
remain visible and can be rerun deliberately with `--no-resume`.

After final survey lock, the intended production sequence is:

1. Run the final real Phase 6B pipeline.
2. Pass Phase 6B readiness validation.
3. Run the Phase 6C dry-run.
4. Generate the final fit manifest.
5. Run Phase 6C.2 production fits with the frozen production settings.
6. Resume until required fits complete.
7. Run Phase 6C.3 consolidation in final production mode.
8. Verify `BASELINE_PRIMARY_OUTPUTS_COMPLETE=true`.
9. Freeze the consolidated baseline outputs.
10. Only then pass baseline predictions to Phase 6F evaluation.

Do not overwrite an already frozen final production output silently. Use a
versioned production output directory and retain the protocol/configuration
snapshot hash, input manifest identity, output row counts, and completion status
in the QC summary.
