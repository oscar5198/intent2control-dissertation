# Stimulus Selection Outputs

Start with `MASTER_STIMULUS_SELECTION_INDEX.md`.

## Current Authoritative Sources

- Active five-mix frontend stimulus configuration: `../../study-interface/frontend-5mix/config/stimuli.json`.
- Final five-mix review and traceability package: `11_five_mix_selection_review_20260806/`.
- Final five-mix selection table: `11_five_mix_selection_review_20260806/recommended_five_mix_selections.csv`.
- Five-mix traceability: `11_five_mix_selection_review_20260806/five_mix_selection_traceability.md` and `.csv`.
- Historical six-mix proposal evidence retained for current provenance: `09_six_mix_proposals/`.
- Replacement-song evidence for `I'd Like To Know`: `08_backup_song_expansion/`.
- Earlier dataset, feature, ratings, and supervisor-review evidence retained where referenced by final traceability files.

The old `04_mix_selection/`, `06_final_summaries/`, and archive material are not
authoritative for the active interface, but some are retained as dissertation
provenance and should not be deleted unless final traceability references have
been reviewed.

## Active Five-Mix Experiment

| Group | Song | Five selected mixes |
| --- | --- | --- |
| `group_01` | Lead Me | DU-D, DU-E, PXL-L1, PXL-L4, McG-pro2 |
| `group_01` | I'd Like To Know | PXL-S3, PXL-S5, PXL-S1, PXL-S2, PXL-S7 |
| `group_02` | In The Meantime | QUT-B, DU-H, DU-I, DU-K, QUT-pro |
| `group_02` | Pouring Room | McG-R, McG-T, McG-X, McG-pro1, McG-V |

The active frontend randomises anonymous labels A-E at runtime, so fixed A-E
interpretation requires the participant-level Netlify fields
`mix_mapping_json`, `presentation_order_json`, and `responses_json`.

## Current Provenance Order

1. `01_dataset_and_song_selection/`: dataset inventory and initial song allocation.
2. `02_excerpt_selection/`: aligned 28-second excerpt decisions and diagnostics.
3. `03_feature_extraction/`: validated Diff-MST features.
4. `04_mix_selection_v2/`: corrected acoustic candidate pools.
5. `05_ratings_integration/`: prior no-context preference ratings.
6. `06_rating_stratification/`: Similar/Wide recommendation triplets.
7. `05_alignment_verification/`: alignment QA for recommended triplets.
8. `07_supervisor_review_package/`: supervisor review materials for original candidates.
9. `08_backup_song_expansion/`: replacement-song evidence, including active `I'd Like To Know`.
10. `09_six_mix_proposals/`: six-mix proposal evidence retained because the final five-mix package references it.
11. `11_five_mix_selection_review_20260806/`: current authoritative final five-mix selection package.
