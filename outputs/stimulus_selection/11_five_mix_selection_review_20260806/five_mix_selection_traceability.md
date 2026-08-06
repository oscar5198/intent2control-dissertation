# Five-Mix Selection Traceability Review

## Direct Answers

- **Were MST/Diff-MST features extracted again from WAVs?** No for Phase 2. Repository evidence shows `generate_five_mix_review.py` loaded existing `processed_features_v2.csv` and `processed_features_backup.csv`; it does not perform new raw feature extraction from WAVs.
- **Were pairwise acoustic distances recomputed for five-mix candidate sets?** Not from raw feature vectors in Phase 2. The script reused existing pairwise distance tables for selected/pool distances, then computed five-mix combination-level metrics and scores from those reused rows.
- **Were existing pairwise-distance results reused?** Yes: `six_mix_pairwise_distances.csv`, `pairwise_distances_backup.csv`, and `pairwise_distances_v2.csv` are the cited source tables.
- **Did original excerpts change for Lead Me, In The Meantime, or Pouring Room?** Repository evidence indicates no new excerpt selection for those three in Phase 2. The five-mix frontend uses the previously accepted Stage 9 / approved overlap 28 s excerpt family for the existing accepted songs.
- **Was a new excerpt generated or selected for I'd Like To Know?** It was selected from the Stage 8 backup expansion / supervisor review package as the replacement song. It is new relative to the final frontend replacement, but was not newly generated in this corrective pass.

## Authoritative Files

- `current_features`: `outputs/stimulus_selection/04_mix_selection_v2/tables/processed_features_v2.csv`
- `backup_features`: `outputs/stimulus_selection/08_backup_song_expansion/04_acoustic_candidate_pools/tables/processed_features_backup.csv`
- `current_pairwise`: `outputs/stimulus_selection/04_mix_selection_v2/tables/pairwise_distances_v2.csv`
- `six_pairwise`: `outputs/stimulus_selection/09_six_mix_proposals/tables/six_mix_pairwise_distances.csv`
- `backup_pairwise`: `outputs/stimulus_selection/08_backup_song_expansion/04_acoustic_candidate_pools/tables/pairwise_distances_backup.csv`
- `current_ratings`: `outputs/stimulus_selection/05_ratings_integration/tables/mix_preference_rating_summary_within_song.csv`
- `backup_ratings`: `outputs/stimulus_selection/08_backup_song_expansion/05_ratings_integration/tables/mix_preference_rating_summary_within_song_backup.csv`
- `six_qc`: `outputs/stimulus_selection/09_six_mix_proposals/qc/six_mix_technical_qc.csv`
- `six_alignment`: `outputs/stimulus_selection/09_six_mix_proposals/alignment_review/six_mix_alignment_summary.csv`
- `backup_review`: `outputs/stimulus_selection/08_backup_song_expansion/08_supervisor_review_package/tables/mix_level_summary_backup.csv`
- `backup_alignment`: `outputs/stimulus_selection/08_backup_song_expansion/08_supervisor_review_package/tables/alignment_summary_backup.csv`
- `perceptual_status`: `outputs/stimulus_selection/07_perceptual_review/PERCEPTUAL_REVIEW_STATUS.md`
- Phase 2 generator: `C:\Users\oscar\Documents\7. QMUL UNIVERSITY\1. Master Program\3. MSc Project\intent2control-dissertation\outputs\stimulus_selection\11_five_mix_selection_review_20260806\generate_five_mix_review.py`
- Selection table: `C:\Users\oscar\Documents\7. QMUL UNIVERSITY\1. Master Program\3. MSc Project\intent2control-dissertation\outputs\stimulus_selection\11_five_mix_selection_review_20260806\recommended_five_mix_selections.csv`
- Selected pairwise rows: `C:\Users\oscar\Documents\7. QMUL UNIVERSITY\1. Master Program\3. MSc Project\intent2control-dissertation\outputs\stimulus_selection\11_five_mix_selection_review_20260806\selected_pairwise_distances.csv`
- Role/rating table: `C:\Users\oscar\Documents\7. QMUL UNIVERSITY\1. Master Program\3. MSc Project\intent2control-dissertation\outputs\stimulus_selection\11_five_mix_selection_review_20260806\brecht_ratings_and_roles.csv`
- Candidate-song evaluation: `C:\Users\oscar\Documents\7. QMUL UNIVERSITY\1. Master Program\3. MSc Project\intent2control-dissertation\outputs\stimulus_selection\11_five_mix_selection_review_20260806\candidate_song_evaluation.csv`
- Combination scores: `C:\Users\oscar\Documents\7. QMUL UNIVERSITY\1. Master Program\3. MSc Project\intent2control-dissertation\outputs\stimulus_selection\11_five_mix_selection_review_20260806\five_mix_combination_scores.csv`

## Similar-Rating And Range Composition

| Song | Similar-rating subset | Range / bridge subset |
|---|---|---|
| Lead Me | DU-D, DU-E, PXL-L1 | PXL-L4 bridge, McG-pro2 |
| In The Meantime | DU-H, DU-I, QUT-pro | QUT-B bridge, DU-K |
| Pouring Room | McG-R, McG-T, McG-X | McG-pro1, McG-V bridge |
| I'd Like To Know | PXL-S3, PXL-S5, PXL-S2 | PXL-S1 bridge, PXL-S7 |

## Selected Mix Traceability

| Song | Order | Mix | Role | Rating | Nearest selected neighbour | Distance | Review copy preserves frontend bytes | Frontend equals cited source path |
|---|---:|---|---|---:|---|---:|---|---|
| Lead Me | 1 | DU-D | similar-rating subset | 0.345 | PXL-L4 | 2.520 | yes | yes |
| Lead Me | 2 | DU-E | similar-rating subset | 0.289 | PXL-L1 | 2.841 | yes | yes |
| Lead Me | 3 | PXL-L1 | similar-rating subset | 0.332 | DU-E | 2.841 | yes | no |
| Lead Me | 4 | PXL-L4 | range-broadening / rating bridge | 0.517 | DU-D | 2.520 | yes | no |
| Lead Me | 5 | McG-pro2 | range-broadening | 0.547 | PXL-L1 | 2.923 | yes | no |
| In The Meantime | 1 | QUT-B | range-broadening / rating bridge | 0.170 | DU-K | 4.131 | yes | yes |
| In The Meantime | 2 | DU-H | similar-rating subset | 0.560 | DU-K | 2.859 | yes | yes |
| In The Meantime | 3 | DU-I | similar-rating subset | 0.531 | DU-K | 2.106 | yes | yes |
| In The Meantime | 4 | DU-K | range-broadening | 0.136 | DU-I | 2.106 | yes | no |
| In The Meantime | 5 | QUT-pro | similar-rating subset | 0.585 | DU-I | 3.136 | yes | no |
| Pouring Room | 1 | McG-R | similar-rating subset | 0.391 | McG-pro1 | 2.121 | yes | no |
| Pouring Room | 2 | McG-T | similar-rating subset | 0.316 | McG-X | 1.885 | yes | no |
| Pouring Room | 3 | McG-X | similar-rating subset | 0.327 | McG-T | 1.885 | yes | no |
| Pouring Room | 4 | McG-pro1 | range-broadening | 0.742 | McG-V | 1.695 | yes | yes |
| Pouring Room | 5 | McG-V | range-broadening / rating bridge | 0.510 | McG-pro1 | 1.695 | yes | yes |
| I'd Like To Know | 1 | PXL-S3 | similar-rating subset | 0.387 | PXL-S2 | 1.368 | yes | yes |
| I'd Like To Know | 2 | PXL-S5 | similar-rating subset | 0.418 | PXL-S7 | 1.978 | yes | yes |
| I'd Like To Know | 3 | PXL-S1 | range-broadening / rating bridge | 0.522 | PXL-S7 | 1.597 | yes | yes |
| I'd Like To Know | 4 | PXL-S2 | similar-rating subset | 0.466 | PXL-S3 | 1.368 | yes | yes |
| I'd Like To Know | 5 | PXL-S7 | range-broadening | 0.633 | PXL-S2 | 1.530 | yes | yes |

## Evidence Boundary

- Raw acoustic feature extraction and Diff-MST/MST derivation happened upstream of this Phase 2 review. This review cites the processed feature tables, but the Phase 2 generator itself does not re-extract those features from WAV files.
- Pairwise acoustic-distance matrices were reused from upstream outputs. The Phase 2 generator scored candidate five-mix sets by looking up existing distances and calculating set-level metrics such as minimum/mean distance and rating spread.
- Manual listening/perceptual confirmation is represented as a required review status in the Phase 2 tables and linked perceptual review material; this traceability report does not claim new human listening was performed during this corrective pass.
- Byte equality is reported against the cited source path where that path exists. A `no` value means the active frontend copy does not byte-match that cited file; it does not by itself prove a different musical excerpt boundary without the associated alignment/provenance evidence.

Full row-level evidence is in `C:\Users\oscar\Documents\7. QMUL UNIVERSITY\1. Master Program\3. MSc Project\intent2control-dissertation\outputs\stimulus_selection\11_five_mix_selection_review_20260806\five_mix_selection_traceability.csv`.
