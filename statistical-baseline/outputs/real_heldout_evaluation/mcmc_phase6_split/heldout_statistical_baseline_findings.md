# Held-Out Statistical Baseline Findings

Phase 6 split source: `llm-experiments/llm_evaluation_protocol.md`.
Evaluation used 198 leave-one-trial-out participant-trial targets from 33 participants; 16 targets had tied observed winners.

## Overall metrics
| baseline_model | n_trials | n_unique_winner_trials | n_tied_human_trials | strict_unique_winner_accuracy | tie_compatible_accuracy | top2_hit_rate | mean_spearman | mean_ndcg | mae | rmse | mean_predicted_winner_probability | mean_observed_winner_probability_mass | mean_entropy | mean_top2_margin | mean_expected_draws_outside_0_100_prop | predicted_exact_tie_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| categorical_design | 198 | 182 | 16 | 0.3022 | 0.3434 | 0.5960 | 0.3555 | 0.9167 | 22.9765 | 27.5935 | 0.7987 | 0.3225 | 0.5213 | 0.6267 | 0.0032 | 0 |
| primary_acoustic | 198 | 182 | 16 | 0.3022 | 0.3434 | 0.6162 | 0.3637 | 0.9180 | 23.0010 | 27.5912 | 0.8172 | 0.3243 | 0.4740 | 0.6509 | 0.0034 | 0 |

## Feature-minus-stimulus comparison
| metric | categorical_design | primary_acoustic | primary_acoustic_minus_categorical_design |
| --- | --- | --- | --- |
| strict_unique_winner_accuracy | 0.3022 | 0.3022 | 0.0000 |
| tie_compatible_accuracy | 0.3434 | 0.3434 | 0.0000 |
| top2_hit_rate | 0.5960 | 0.6162 | 0.0202 |
| mean_spearman | 0.3555 | 0.3637 | 0.0082 |
| mean_ndcg | 0.9167 | 0.9180 | 0.0013 |
| mae | 22.9765 | 23.0010 | 0.0245 |
| rmse | 27.5935 | 27.5912 | -0.0023 |
| mean_predicted_winner_probability | 0.7987 | 0.8172 | 0.0185 |
| mean_observed_winner_probability_mass | 0.3225 | 0.3243 | 0.0018 |
| mean_entropy | 0.5213 | 0.4740 | -0.0473 |
| mean_top2_margin | 0.6267 | 0.6509 | 0.0242 |

## Participant bootstrap comparison
| metric | difference_direction | bootstrap_replicates | mean_difference | ci_lower | ci_upper | probability_difference_gt_0 |
| --- | --- | --- | --- | --- | --- | --- |
| strict_unique_winner_accuracy | primary_acoustic_minus_categorical_design | 2000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| tie_compatible_accuracy | primary_acoustic_minus_categorical_design | 2000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| top2_hit_rate | primary_acoustic_minus_categorical_design | 2000 | 0.0202 | -0.0253 | 0.0657 | 0.7835 |
| mean_spearman | primary_acoustic_minus_categorical_design | 2000 | 0.0084 | -0.0035 | 0.0211 | 0.9095 |
| mean_ndcg | primary_acoustic_minus_categorical_design | 2000 | 0.0012 | -0.0001 | 0.0028 | 0.9695 |
| mae | primary_acoustic_minus_categorical_design | 2000 | 0.0255 | -0.0271 | 0.0765 | 0.8265 |
| rmse | primary_acoustic_minus_categorical_design | 2000 | 0.0203 | -0.0418 | 0.0824 | 0.7290 |
| mean_observed_winner_probability_mass | primary_acoustic_minus_categorical_design | 2000 | 0.0018 | -0.0022 | 0.0058 | 0.8175 |

## Validation
| check | passed | value |
| --- | --- | --- |
| every_fold_model_has_five_candidates | True | {5: 396} |
| posterior_probabilities_between_0_and_1 | True |  |
| posterior_probabilities_sum_to_one | True | min=1.000000000000; max=1.000000000000 |
| one_final_winner_unless_exact_tie | True | exact_predicted_ties=0 |
| all_fold_model_pairs_completed | True | 396/396 |

## Fold diagnostics
| fit_status | count |
| --- | --- |
| convergence_warning | 384 |
| fit_ok | 12 |

Winner probabilities were derived draw by draw from posterior expected ratings, not from posterior predictive residual noise and not from posterior means alone.
