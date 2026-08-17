# Held-Out Statistical Baseline Findings

Phase 6 split source: `llm-experiments/llm_evaluation_protocol.md`.
Evaluation used 180 leave-one-trial-out participant-trial targets from 30 participants; 16 targets had tied observed winners.

## Overall metrics
| baseline_model | n_trials | n_unique_winner_trials | n_tied_human_trials | strict_unique_winner_accuracy | tie_compatible_accuracy | top2_hit_rate | mean_spearman | mean_ndcg | mae | rmse | mean_predicted_winner_probability | mean_observed_winner_probability_mass | mean_entropy | mean_top2_margin | mean_expected_draws_outside_0_100_prop | predicted_exact_tie_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| categorical_design | 180 | 164 | 16 | 0.2866 | 0.3389 | 0.6000 | 0.3355 | 0.9185 | 23.6288 | 28.2309 | 0.8318 | 0.3261 | 0.4474 | 0.6789 | 0.0044 | 0 |
| primary_acoustic | 180 | 164 | 16 | 0.2805 | 0.3333 | 0.6000 | 0.3352 | 0.9183 | 23.6060 | 28.2236 | 0.8311 | 0.3256 | 0.4264 | 0.6728 | 0.0050 | 0 |

## Feature-minus-stimulus comparison
| metric | categorical_design | primary_acoustic | primary_acoustic_minus_categorical_design |
| --- | --- | --- | --- |
| strict_unique_winner_accuracy | 0.2866 | 0.2805 | -0.0061 |
| tie_compatible_accuracy | 0.3389 | 0.3333 | -0.0056 |
| top2_hit_rate | 0.6000 | 0.6000 | 0.0000 |
| mean_spearman | 0.3355 | 0.3352 | -0.0003 |
| mean_ndcg | 0.9185 | 0.9183 | -0.0001 |
| mae | 23.6288 | 23.6060 | -0.0227 |
| rmse | 28.2309 | 28.2236 | -0.0073 |
| mean_predicted_winner_probability | 0.8318 | 0.8311 | -0.0008 |
| mean_observed_winner_probability_mass | 0.3261 | 0.3256 | -0.0006 |
| mean_entropy | 0.4474 | 0.4264 | -0.0209 |
| mean_top2_margin | 0.6789 | 0.6728 | -0.0061 |

## Participant bootstrap comparison
| metric | difference_direction | bootstrap_replicates | mean_difference | ci_lower | ci_upper | probability_difference_gt_0 |
| --- | --- | --- | --- | --- | --- | --- |
| strict_unique_winner_accuracy | primary_acoustic_minus_categorical_design | 2000 | -0.0054 | -0.0167 | 0.0000 | 0.0000 |
| tie_compatible_accuracy | primary_acoustic_minus_categorical_design | 2000 | -0.0054 | -0.0167 | 0.0000 | 0.0000 |
| top2_hit_rate | primary_acoustic_minus_categorical_design | 2000 | -0.0001 | -0.0333 | 0.0389 | 0.4115 |
| mean_spearman | primary_acoustic_minus_categorical_design | 2000 | 0.0004 | -0.0105 | 0.0112 | 0.5340 |
| mean_ndcg | primary_acoustic_minus_categorical_design | 2000 | -0.0001 | -0.0009 | 0.0005 | 0.3770 |
| mae | primary_acoustic_minus_categorical_design | 2000 | -0.0231 | -0.0843 | 0.0358 | 0.2330 |
| rmse | primary_acoustic_minus_categorical_design | 2000 | 0.0062 | -0.0519 | 0.0640 | 0.5785 |
| mean_observed_winner_probability_mass | primary_acoustic_minus_categorical_design | 2000 | -0.0006 | -0.0034 | 0.0021 | 0.3465 |

## Validation
| check | passed | value |
| --- | --- | --- |
| every_fold_model_has_five_candidates | True | {5: 360} |
| posterior_probabilities_between_0_and_1 | True |  |
| posterior_probabilities_sum_to_one | True | min=1.000000000000; max=1.000000000000 |
| one_final_winner_unless_exact_tie | True | exact_predicted_ties=0 |
| all_fold_model_pairs_completed | True | 360/360 |

## Fold diagnostics
| fit_status | count |
| --- | --- |
| fit_ok | 360 |

Winner probabilities were derived draw by draw from posterior expected ratings, not from posterior predictive residual noise and not from posterior means alone.
