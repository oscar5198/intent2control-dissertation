# Master Stimulus Selection Index

This is the repository-level source map for the current final stimulus-selection design. It documents which files are authoritative for the active four-song, two-group study and which files are preserved only as legacy or exploratory work.

## Current Authoritative Design

The active frontend configuration is the authoritative source for the stimuli currently used in the study interface.

| Element | Authoritative file(s) | Notes |
| --- | --- | --- |
| Final song list | `outputs/stimulus_selection/01_dataset_and_song_selection/tables/four_song_selection.csv`; reflected in `study-interface/frontend/config/stimuli.json` | Four songs: Lead Me; Red To Blue; In The Meantime; Pouring Room. |
| Participant-group allocation | `study-interface/frontend/config/stimuli.json`; `study-interface/docs/final-stimuli-manifest.md` | `group_01`: Lead Me, Red To Blue. `group_02`: In The Meantime, Pouring Room. |
| Selected three mixes per song | `study-interface/frontend/config/stimuli.json`; derived table `outputs/stimulus_selection/09_current_frontend_integration/tables/current_frontend_stimuli.csv` | This supersedes legacy `final_selected_mixes.csv` files. |
| Similar/Wide category decisions | `study-interface/frontend/config/stimuli.json`; `study-interface/docs/final-stimuli-manifest.md` | Lead Me, Red To Blue, and In The Meantime use Wide Ratings. Pouring Room uses Similar Ratings. |
| Frontend runtime configuration | `study-interface/frontend/config/stimuli.json`; `study-interface/frontend/config/study-config.json` | Current status: technically integrated; perceptual approval pending. |
| Candidate pools | `outputs/stimulus_selection/04_mix_selection_v2/tables/acoustic_candidate_pool.csv`; `outputs/stimulus_selection/04_mix_selection_v2/tables/acoustic_candidate_pool_summary.csv` | Corrected acoustic candidate pools; stereo imbalance retained as QC, not diversity distance. |
| Prior-rating data | `outputs/stimulus_selection/05_ratings_integration/tables/mix_preference_rating_summary_within_song.csv`; `outputs/stimulus_selection/05_ratings_integration/tables/mix_preference_rating_summary.csv` | Brecht/Mix Evaluation no-context prior ratings integrated by mix. |
| Rating-stratified recommendations | `outputs/stimulus_selection/06_rating_stratification/tables/supervisor_shortlist.csv` | Contains Similar Ratings and Wide Ratings triplets for each song. |
| Current acoustic-selection outputs | `outputs/stimulus_selection/04_mix_selection_v2/` and `outputs/stimulus_selection/06_rating_stratification/diagnostics/` | Diagnostic and candidate-pool outputs supporting the active procedure. |
| Perceptual review status | `outputs/stimulus_selection/07_perceptual_review/PERCEPTUAL_REVIEW_STATUS.md` | Final researcher/supervisor perceptual approval is pending. |

## Active Study Allocation

| Group | Participant excerpt | Artist | Song | Active category | Active mixes |
| --- | --- | --- | --- | --- | --- |
| `group_01` | Song A | The DoneFors | Lead Me | Wide Ratings | PXL-L1; PXL-L4; McG-pro2 |
| `group_01` | Song B | Broken Crank | Red To Blue | Wide Ratings | McG-C; McG-H; McG-pro1 |
| `group_02` | Song A | Fredy V | In The Meantime | Wide Ratings | DU-K; QUT-pro; DU-N |
| `group_02` | Song B | The DoneFors | Pouring Room | Similar Ratings | McG-R; McG-T; McG-X |

## Current Pipeline

```text
Dataset inspection and four-song allocation
-> excerpt selection and alignment
-> Diff-MST feature extraction
-> corrected acoustic candidate-pool generation
-> prior-rating integration
-> Similar/Wide rating stratification
-> alignment verification and supervisor review package
-> frontend integration in stimuli.json
-> researcher/supervisor perceptual quality review (pending)
```

Song-level selection, acoustic candidate-pool generation, within-song mix selection, rating stratification, frontend integration, and perceptual review are distinct stages. The current frontend uses the rating-stratified Similar/Wide choices listed above; the earlier medoid/contrast triplets are not current final study stimuli.

## Important Quality Caveat

Algorithmic rating/acoustic diversity does not guarantee acceptable production quality. Informal researcher listening found that several selected mixes, particularly in Wide Ratings sets, sounded subjectively poor or production-unbalanced. The active frontend triplets have been technically integrated, but final perceptual quality review by the researcher and supervisor is still required before final study deployment.

Candidate-pool outputs remain available so the supervisor can request replacement decisions without losing the corrected acoustic/rating context.

## Current Output Map

| Folder | Purpose | Status |
| --- | --- | --- |
| `01_dataset_and_song_selection/` | Dataset inspection, inventory, and four-song selection | Current song-selection evidence. |
| `02_excerpt_selection/` | Approved 28-second excerpt decisions and diagnostics | Current excerpt evidence. |
| `03_feature_extraction/` | Diff-MST feature extraction and feature diagnostics | Current objective feature source. |
| `04_mix_selection_v2/` | Corrected acoustic candidate pools and diagnostics | Current acoustic-selection output. |
| `05_ratings_integration/` | Prior-rating aggregation and validation | Current prior-rating source. |
| `05_alignment_verification/` | Alignment QA for rating-stratified triplets | Current alignment evidence. |
| `06_rating_stratification/` | Similar/Wide rating-stratified recommendations and candidate-review audio | Current recommendation source. |
| `07_perceptual_review/` | Current perceptual review status and pending supervisor decisions | Current approval-status source. |
| `07_supervisor_review_package/` | Supervisor-facing main review package | Current review package. |
| `09_current_frontend_integration/` | Frontend-derived current stimulus table and validation notes | Current frontend integration record. |
| `archive/medoid_contrast_legacy/` | Earlier representative/contrast outputs and old final summaries | Legacy only; not authoritative. |
| `08_backup_song_expansion/` | Backup-song candidate material | Backup only; not active frontend stimuli. |
| `logs_and_provenance/` | Reorganisation and provenance logs | Historical/provenance support. |

## Legacy Work

The earlier medoid/contrast outputs have been moved to `outputs/stimulus_selection/archive/medoid_contrast_legacy/`. They are preserved for methodological history and comparison, but they should not be cited as current active study stimuli.

Archived legacy paths:

- `outputs/stimulus_selection/archive/medoid_contrast_legacy/04_mix_selection/`
- `outputs/stimulus_selection/archive/medoid_contrast_legacy/06_final_summaries/`
- `outputs/stimulus_selection/archive/medoid_contrast_legacy/final_stimuli/`

## Validation Status

- Active frontend WAV references exist: see `outputs/stimulus_selection/09_current_frontend_integration/validation/frontend_stimulus_integrity.md`.
- Each active song has exactly three configured mixes.
- Participant-facing labels remain neutral in the frontend config.
- Manifest and `stimuli.json` agree on group allocation, category choices, and active mix names.
- Final perceptual approval remains pending.
