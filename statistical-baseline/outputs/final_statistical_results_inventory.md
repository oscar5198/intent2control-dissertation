# Final Statistical Results Inventory

Created for the final N=33 empirical statistical analysis. Checkpoint folders are not dissertation outputs and are intentionally excluded from this inventory.

## Dataset And Cleaning Outputs

| Relative path | Contains | Why it matters | Dissertation use | Type |
|---|---|---|---|---|
| `statistical-baseline/data/real/raw/listening_preference_responses_33_immutable.xlsx` | Immutable raw participant workbook | Preserves the source data exactly as received | Provenance/audit only | Primary data provenance |
| `statistical-baseline/data/real/real_cleaning_manifest.json` | Cleaning run metadata, raw SHA-256, feature-table hash, output paths, transformations | Main proof of data provenance and canonicalisation | Methods appendix | Primary audit |
| `statistical-baseline/data/real/real_data_summary.csv` | Headline cleaning counts: N, rows, ties, missingness, validation gate | Quick dataset summary | Dataset table | Primary |
| `statistical-baseline/data/real/real_data_validation.csv` | Structural validation checks | Shows the cleaned data passed design checks | Supplementary audit | Diagnostic |
| `statistical-baseline/data/real/real_ratings_clean.csv` | Long-format rating rows, one row per participant x trial x mix | Main empirical analysis table | Methods/data description | Primary |
| `statistical-baseline/data/real/real_participants_clean.csv` | Participant-level table | Group split and participant metadata | Dataset summary | Primary |
| `statistical-baseline/data/real/real_trial_preferences.csv` | Trial-level observed preferred mix information | Defines observed winners and ties | Held-out evaluation explanation | Primary |
| `statistical-baseline/data/real/real_trial_ties_long.csv` | Long table of tied observed winners | Preserves ties instead of forcing one winner | Supplementary | Primary audit |
| `statistical-baseline/data/real/real_exclusion_log.csv` | Per-submission inclusion/review decision | Shows all 33 submissions are retained | Methods appendix | Diagnostic |
| `statistical-baseline/data/real/real_participant_metadata_audit.csv` | Metadata value counts and missingness | Documents demographics without overusing them analytically | Supplementary | Diagnostic |

Important verified counts: N=33, group_01=17, group_02=16, 990 rating rows, 198 participant x song x episode trials, 20 stimuli, 4 songs, 3 episodes, 5 candidate mixes per trial, 30 ratings per participant, 16 tied human trials.

## Real Stimulus Model

Directory: `statistical-baseline/outputs/real_stimulus_model/`

| Relative path | Contains | Why it matters | Dissertation use | Type |
|---|---|---|---|---|
| `fixed_effect_posterior_summary.csv` | Intercept, episode effects, group effect | Main full-data stimulus-model estimates | Results table | Primary |
| `final_model_icc_summary.csv` | Conditional/final-model ICCs from the final model | Primary variance-share result | Results table/text | Primary |
| `null_model_icc_summary.csv` | Unconditional/null-model ICCs | Baseline variance partition before fixed effects | Supplementary/methods | Diagnostic |
| `icc_posterior_summary.csv` | Compatibility alias of final ICC output | Older downstream compatibility | Avoid citing if using explicit final/null files | Supplementary |
| `posterior_predictive_summary.csv` | Gaussian PPC summaries and boundary leakage | Shows model fit and bounded-scale limitation | Diagnostic paragraph | Diagnostic |
| `posterior_expected_ratings.csv` | Posterior expected ratings for stimulus/song/episode combinations | Supports winner-probability calculation | Supplementary | Primary derived |
| `predicted_highest_rated_mixes.csv` | Draw-by-draw posterior winning probabilities and final predicted winners | Stimulus-level predicted preference table | Supplementary or selected examples | Primary derived |
| `posterior_winner_validation.csv` | Checks for candidate counts and probability sums | Validates winner probabilities | Supplementary audit | Diagnostic |
| `convergence_diagnostics.csv` | Divergences, R-hat, ESS, runtime | Confirms full-data MCMC quality | Methods/results diagnostics | Diagnostic |
| `runtime_execution_summary.csv` | Sampling settings and runtime | Reproducibility | Supplementary | Diagnostic |
| `real_stimulus_model_manifest.json` | Formula, sampling settings, dataset metadata | Main output provenance | Methods appendix | Primary audit |
| `empirical_stimulus_model_findings.md` | Report-ready stimulus-model findings | Draftable Results text | Writing source | Primary narrative |

Figures:

| Relative path | Shows | Dissertation use |
|---|---|---|
| `statistical-baseline/outputs/real_stimulus_model/figures/observed_rating_distribution.png` | Distribution of observed 0-100 ratings | Useful as a compact data-description figure |
| `statistical-baseline/outputs/real_stimulus_model/figures/posterior_predictive_episode_means.png` | Observed vs posterior-predictive episode means | Useful diagnostic/supplementary figure |
| `statistical-baseline/outputs/real_stimulus_model/figures/real_stimulus_model_trace_selected.png` | Selected trace plots | Supplementary diagnostics, not main Results |

## Real Feature Model

Directory: `statistical-baseline/outputs/real_feature_model/`

| Relative path | Contains | Why it matters | Dissertation use | Type |
|---|---|---|---|---|
| `primary_fixed_effect_posterior_summary.csv` | Episode, group, RMS, crest factor, stereo width estimates | Main acoustic association result | Results table | Primary |
| `si_sensitivity_posterior_summary.csv` | Same model with spectral irregularity added | Sensitivity check | Sensitivity paragraph/table | Sensitivity |
| `icc_posterior_summary.csv` | Conditional ICCs for primary feature and SI models | Shows variance shares after acoustic predictors | Results/supplementary | Primary/sensitivity |
| `posterior_predictive_summary.csv` | Gaussian PPC summaries for primary, SI, and bounded sensitivity | Checks model behaviour and boundary leakage | Diagnostics paragraph | Diagnostic |
| `primary_vs_si_loo.csv` | PSIS-LOO comparison of primary vs SI sensitivity | Tests whether SI materially improves predictive fit | Sensitivity paragraph | Diagnostic/sensitivity |
| `stimulus_vs_feature_loo.csv` | PSIS-LOO comparison of stimulus and feature full-data models | Checks predictive support for feature model | Results/supplementary | Diagnostic |
| `bounded_sensitivity_posterior_summary.csv` | Transformed Beta sensitivity estimates | Bounded-outcome robustness check | Sensitivity paragraph | Sensitivity |
| `bounded_sensitivity_ppc_summary.csv` | Bounded sensitivity PPC and zero/100 notes | Confirms no simulated values outside 0-100 | Sensitivity paragraph | Sensitivity |
| `posterior_expected_ratings.csv` | Posterior expected ratings under the primary feature model | Supports predicted winner table | Supplementary | Primary derived |
| `predicted_highest_rated_mixes.csv` | Feature-model draw-by-draw posterior winning probabilities | Preference prediction from features | Supplementary | Primary derived |
| `stimulus_vs_feature_comparison.csv` | Side-by-side key model summaries | Quick comparison | Drafting aid | Supplementary |
| `convergence_diagnostics.csv` | Divergences, R-hat, ESS, runtime | Confirms full-data feature MCMC quality | Methods/results diagnostics | Diagnostic |
| `real_feature_model_manifest.json` | Formula, sampling settings, dataset metadata | Output provenance | Methods appendix | Primary audit |
| `empirical_feature_model_findings.md` | Report-ready feature-model findings | Draftable Results text | Writing source | Primary narrative |

Figures:

| Relative path | Shows | Dissertation use |
|---|---|---|
| `statistical-baseline/outputs/real_feature_model/figures/ratings_by_z_RMS.png` | Ratings against z-scored RMS | Potential Results figure if redrawn cleanly |
| `statistical-baseline/outputs/real_feature_model/figures/ratings_by_z_CF.png` | Ratings against z-scored crest factor | Potential Results figure if redrawn cleanly |
| `statistical-baseline/outputs/real_feature_model/figures/ratings_by_z_SW.png` | Ratings against z-scored stereo width | Supplementary or combined feature plot |
| `statistical-baseline/outputs/real_feature_model/figures/ratings_by_z_SI.png` | Ratings against z-scored spectral irregularity | Sensitivity/supplementary |
| `statistical-baseline/outputs/real_feature_model/figures/primary_feature_trace_selected.png` | Trace plots for primary feature model | Supplementary diagnostics |
| `statistical-baseline/outputs/real_feature_model/figures/si_sensitivity_trace_selected.png` | Trace plots for SI sensitivity model | Supplementary diagnostics |

## Official Held-Out MCMC

Directory: `statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split/`

| Relative path | Contains | Why it matters | Dissertation use | Type |
|---|---|---|---|---|
| `evaluation_manifest.json` | N=33 MCMC run metadata, hashes, settings, validation status | Main held-out provenance file | Methods appendix | Primary audit |
| `official_n33_target_validation.csv` | N=33, 198 target, 396 fit validation checks | Confirms the official target structure | Supplementary audit | Diagnostic |
| `heldout_split_manifest.csv` | All 198 leave-one-trial-out targets | Defines the evaluation folds | Methods/supplementary | Primary |
| `frozen_target_manifest.csv` | Frozen copy of target manifest | Protects against target drift | Supplementary audit | Primary |
| `leakage_audit.csv` | Confirms each held-out trial was excluded and history retained | Critical anti-leakage evidence | Methods/results audit | Primary diagnostic |
| `candidate_predictions.csv` | Candidate-level posterior means, intervals, and winner probabilities | Most detailed prediction output | Supplementary/data appendix | Primary derived |
| `trial_predictions.csv` | Trial-level winner predictions and ranking metrics | Core held-out prediction table | Supplementary/analysis | Primary derived |
| `fold_diagnostics.csv` | Per-fold MCMC diagnostics | Convergence audit | Supplementary | Diagnostic |
| `fit_method_audit.csv` | Counts by model, fit method, and fit status | Shows 396 MCMC fits completed | Diagnostic paragraph | Diagnostic |
| `stimulus_model_metrics.csv` | Held-out metrics for categorical stimulus baseline | Headline comparator | Results table | Primary |
| `feature_model_metrics.csv` | Held-out metrics for acoustic feature baseline | Headline comparator | Results table | Primary |
| `model_comparison.csv` | Feature-minus-stimulus metric differences | Side-by-side comparison | Results table | Primary |
| `bootstrap_model_comparison.csv` | Participant bootstrap intervals for model differences | Uncertainty around held-out differences | Results/supplementary | Primary diagnostic |
| `participant_level_metrics.csv` | Metrics aggregated by participant | Supports bootstrap and heterogeneity checks | Supplementary | Diagnostic |
| `metrics_by_episode.csv` | Metrics by listening context | Context-specific prediction summary | Supplementary | Diagnostic |
| `metrics_by_group.csv` | Metrics by participant group/song set | Group/song-set prediction summary | Supplementary | Diagnostic |
| `metrics_by_song.csv` | Metrics by song | Song-specific prediction summary | Supplementary | Diagnostic |
| `runtime_summary.csv` | Runtime and fit-count totals | Reproducibility | Supplementary | Diagnostic |
| `heldout_statistical_baseline_findings.md` | Report-ready held-out findings | Draftable Results text | Writing source | Primary narrative |

Figures:

| Relative path | Shows | Dissertation use |
|---|---|---|
| `statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split/figures/heldout_preference_metrics.png` | Accuracy/ranking metrics by model | Strong candidate for Results, ideally redrawn with final styling |
| `statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split/figures/heldout_rating_error.png` | MAE/RMSE by model | Strong candidate for Results or supplementary |
| `statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split/figures/fold_runtime_distribution.png` | Runtime by model | Supplementary only |

## Recommended Dissertation Figures And Tables

Recommended figures:

1. `statistical-baseline/outputs/real_stimulus_model/figures/observed_rating_distribution.png` - shows how participants used the 0-100 scale; use in data/results background, preferably redrawn for publication.
2. A redrawn coefficient interval plot from `statistical-baseline/outputs/real_feature_model/primary_fixed_effect_posterior_summary.csv` - shows RMS, crest factor, and stereo width estimates with credible intervals; supports acoustic-association RQ.
3. `statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split/figures/heldout_preference_metrics.png` - shows held-out winner/ranking performance; supports statistical baseline comparison.
4. `statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split/figures/heldout_rating_error.png` - shows held-out rating error; use only if space allows.

Recommended tables:

1. Dataset summary table from `statistical-baseline/data/real/real_data_summary.csv`.
2. Full-data stimulus fixed effects plus final ICC from `fixed_effect_posterior_summary.csv` and `final_model_icc_summary.csv`.
3. Acoustic feature estimates from `primary_fixed_effect_posterior_summary.csv`, with SI sensitivity noted from `si_sensitivity_posterior_summary.csv`.
4. Held-out comparison table from `stimulus_model_metrics.csv`, `feature_model_metrics.csv`, and `bootstrap_model_comparison.csv`.
