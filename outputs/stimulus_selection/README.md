# Stimulus Selection Outputs

Start with `MASTER_STIMULUS_SELECTION_INDEX.md`.

## Current Authoritative Sources

- Active frontend stimulus configuration: `../study-interface/frontend/config/stimuli.json`.
- Researcher-facing frontend manifest: `../study-interface/docs/final-stimuli-manifest.md`.
- Current frontend-derived stimulus table: `09_current_frontend_integration/tables/current_frontend_stimuli.csv`.
- Corrected acoustic candidate pools: `04_mix_selection_v2/tables/acoustic_candidate_pool.csv`.
- Prior-rating integration: `05_ratings_integration/tables/mix_preference_rating_summary_within_song.csv`.
- Similar/Wide triplet recommendations: `06_rating_stratification/tables/supervisor_shortlist.csv`.
- Perceptual review status: `07_perceptual_review/PERCEPTUAL_REVIEW_STATUS.md`.

The old `04_mix_selection/` and `06_final_summaries/` folders have been archived under `archive/medoid_contrast_legacy/`. They preserve the earlier representative/contrast work and are not authoritative for the active frontend stimuli.

## Current Pipeline Order

1. `01_dataset_and_song_selection/`: dataset inventory and four-song allocation.
2. `02_excerpt_selection/`: aligned 28-second excerpt decisions and diagnostics.
3. `03_feature_extraction/`: validated Diff-MST features.
4. `04_mix_selection_v2/`: corrected acoustic candidate pools.
5. `05_ratings_integration/`: prior no-context preference ratings.
6. `06_rating_stratification/`: Similar/Wide recommendation triplets.
7. `05_alignment_verification/`: alignment QA for recommended triplets.
8. `07_supervisor_review_package/`: supervisor review materials.
9. `09_current_frontend_integration/`: tables and validation derived from active frontend configuration.
10. `07_perceptual_review/`: pending perceptual approval status.

Current frontend status: technically integrated; perceptual approval pending.
