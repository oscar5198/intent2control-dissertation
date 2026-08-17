# Medoid/Contrast Legacy Archive

This folder preserves the earlier Stage 4 representative/contrast stimulus-selection outputs.

## What The Old Approach Did

The archived pipeline used Diff-MST acoustic features, within-song robust scaling, Bark PCA diagnostics, and acoustic-distance scoring to choose one representative mix plus two contrast mixes for each selected song. The representative mix was anchored around an acoustic medoid, while contrast mixes were selected to increase objective distance within the same song.

## Why It Was Superseded

This approach is no longer the authoritative final stimulus-selection method for the study. It was superseded first by the corrected acoustic candidate-pool and rating-stratification workflow, then by the current five-mix final-selection review.

The key reason for supersession is methodological: the final study now uses the
five-mix selections documented in
`outputs/stimulus_selection/11_five_mix_selection_review_20260806/`, rather than
presenting the medoid/contrast triplets as final participant stimuli.

## Replacement Pipeline

The current five-mix source of truth is
`study-interface/frontend-5mix/config/stimuli.json`, with final selection
evidence in `outputs/stimulus_selection/11_five_mix_selection_review_20260806/`.
Earlier supporting evidence includes:

1. Four-song study allocation from `outputs/stimulus_selection/01_dataset_and_song_selection/tables/four_song_selection.csv`.
2. Corrected acoustic candidate pools from `outputs/stimulus_selection/04_mix_selection_v2/tables/acoustic_candidate_pool.csv`.
3. Prior-rating integration from `outputs/stimulus_selection/05_ratings_integration/tables/mix_preference_rating_summary_within_song.csv`.
4. Similar/Wide triplet recommendations from `outputs/stimulus_selection/06_rating_stratification/tables/supervisor_shortlist.csv`.
5. Historical six-mix proposal evidence in `outputs/stimulus_selection/09_six_mix_proposals/`.
6. Backup-song expansion evidence for `I'd Like To Know` in `outputs/stimulus_selection/08_backup_song_expansion/`.
7. Final five-mix review and traceability in `outputs/stimulus_selection/11_five_mix_selection_review_20260806/`.

## Archived Content

| Archived path | Former path | Status |
| --- | --- | --- |
| `04_mix_selection/` | `outputs/stimulus_selection/04_mix_selection/` | Legacy exploratory representative/contrast acoustic-selection outputs. |
| `06_final_summaries/` | `outputs/stimulus_selection/06_final_summaries/` | Legacy final summaries derived from the representative/contrast approach. |
| `final_stimuli/` | `outputs/final_stimuli/` | Legacy loudness-normalised representative/contrast final-stimuli package. |

Do not use files in this archive as the source of active study stimuli. They are retained for provenance, comparison, and dissertation method-history discussion only.
