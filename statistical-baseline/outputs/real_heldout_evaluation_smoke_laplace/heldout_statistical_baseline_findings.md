# Held-Out Statistical Baseline Findings

Phase 6 split source: `llm-experiments/llm_evaluation_protocol.md`.
Evaluation used 1 leave-one-trial-out participant-trial targets from 30 participants; 16 targets had tied observed winners.

## Overall metrics
| baseline_model | n_trials | n_unique_winner_trials | n_tied_human_trials | strict_unique_winner_accuracy | tie_compatible_accuracy | top2_hit_rate | mean_spearman | mean_ndcg | mae | rmse | mean_predicted_winner_probability | mean_observed_winner_probability_mass | mean_entropy | mean_top2_margin | mean_expected_draws_outside_0_100_prop | predicted_exact_tie_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| categorical_design | 1 | 1 | 0 | 0.0000 | 0.0000 | 0.0000 | -0.1000 | 0.8989 | 15.6979 | 16.0062 | 0.8750 | 0.0060 | 0.4148 | 0.7590 | 0.0000 | 0 |
| primary_acoustic | 1 | 1 | 0 | 0.0000 | 0.0000 | 0.0000 | -0.1000 | 0.8989 | 16.0193 | 16.2500 | 0.8940 | 0.0060 | 0.3709 | 0.7960 | 0.0000 | 0 |

## Feature-minus-stimulus comparison
| metric | categorical_design | primary_acoustic | primary_acoustic_minus_categorical_design |
| --- | --- | --- | --- |
| strict_unique_winner_accuracy | 0.0000 | 0.0000 | 0.0000 |
| tie_compatible_accuracy | 0.0000 | 0.0000 | 0.0000 |
| top2_hit_rate | 0.0000 | 0.0000 | 0.0000 |
| mean_spearman | -0.1000 | -0.1000 | 0.0000 |
| mean_ndcg | 0.8989 | 0.8989 | 0.0000 |
| mae | 15.6979 | 16.0193 | 0.3214 |
| rmse | 16.0062 | 16.2500 | 0.2438 |
| mean_predicted_winner_probability | 0.8750 | 0.8940 | 0.0190 |
| mean_observed_winner_probability_mass | 0.0060 | 0.0060 | 0.0000 |
| mean_entropy | 0.4148 | 0.3709 | -0.0439 |
| mean_top2_margin | 0.7590 | 0.7960 | 0.0370 |

## Participant bootstrap comparison
| metric | difference_direction | bootstrap_replicates | mean_difference | ci_lower | ci_upper | probability_difference_gt_0 |
| --- | --- | --- | --- | --- | --- | --- |
| strict_unique_winner_accuracy | primary_acoustic_minus_categorical_design | 2000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| tie_compatible_accuracy | primary_acoustic_minus_categorical_design | 2000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| top2_hit_rate | primary_acoustic_minus_categorical_design | 2000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| mean_spearman | primary_acoustic_minus_categorical_design | 2000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| mean_ndcg | primary_acoustic_minus_categorical_design | 2000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| mae | primary_acoustic_minus_categorical_design | 2000 | 0.3214 | 0.3214 | 0.3214 | 1.0000 |
| rmse | primary_acoustic_minus_categorical_design | 2000 | 0.2438 | 0.2438 | 0.2438 | 1.0000 |
| mean_observed_winner_probability_mass | primary_acoustic_minus_categorical_design | 2000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## Validation
| check | passed | value |
| --- | --- | --- |
| every_fold_model_has_five_candidates | True | {5: 2} |
| posterior_probabilities_between_0_and_1 | True |  |
| posterior_probabilities_sum_to_one | True | min=1.000000000000; max=1.000000000000 |
| one_final_winner_unless_exact_tie | True | exact_predicted_ties=0 |
| all_fold_model_pairs_completed | True | 2/2 |

## Fold diagnostics
| fit_status | count |
| --- | --- |
| fit_ok | 2 |

Winner probabilities were derived draw by draw from posterior expected ratings, not from posterior predictive residual noise and not from posterior means alone.
