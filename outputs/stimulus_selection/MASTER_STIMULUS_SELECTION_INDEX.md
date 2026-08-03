# Master Stimulus Selection Index

This index is a documentation layer over the existing stimulus-selection outputs. It does not change, recompute, rename, move, or regenerate any scientific output.

## 1. Overview

The stimulus-selection pipeline starts from the public Mix Evaluation Dataset audio and metadata, chooses suitable songs, aligns a shared 28-second excerpt per song, extracts Diff-MST acoustic features, builds corrected acoustic-diversity pools with stereo imbalance retained as QC only, integrates prior Brecht no-context preference ratings, creates Similar/Wide rating recommendation triplets, verifies alignment, and packages materials for supervisor review.

```text
Dataset inspection
↓
Song selection
↓
Excerpt selection
↓
Feature extraction
↓
Corrected acoustic diversity
↓
Prior-rating integration
↓
Rating stratification
↓
Alignment verification
↓
Supervisor review package
↓
(Optional) Backup song expansion
```

## 2. Main Songs

| Artist | Song | Approved excerpt start | Approved excerpt end | Number of retained human mixes | Number of rated mixes | Current status | Supervisor package location |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| The DoneFors | Lead Me | 9.573107 | 37.573107 | 37 | 36 | Main supervisor-review recommendations prepared; supervisor approval pending before revised final regeneration | `07_supervisor_review_package/` |
| Fredy V | In The Meantime | 35.300431 | 63.300431 | 36 | 35 | Main supervisor-review recommendations prepared; supervisor approval pending before revised final regeneration | `07_supervisor_review_package/` |
| Broken Crank | Red To Blue | 3.005442 | 31.005442 | 10 | 9 | Main supervisor-review recommendations prepared; supervisor approval pending before revised final regeneration | `07_supervisor_review_package/` |
| The DoneFors | Pouring Room | 23.020408 | 51.020408 | 9 | 8 | Main supervisor-review recommendations prepared; supervisor approval pending before revised final regeneration | `07_supervisor_review_package/` |

## 3. Backup Songs

| Artist | Song | Approved excerpt start | Approved excerpt end | Number of retained human mixes | Number of rated mixes | Current status | Supervisor package location |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| The Districts | Vermont | 21.000454 | 49.000454 | 7 | 7 | Backup supervisor-review recommendations prepared; supervisor approval pending before any final use | `08_backup_song_expansion/08_supervisor_review_package/` |
| Filthybird | I'd Like To Know | 21.000454 | 49.000454 | 7 | 7 | Backup supervisor-review recommendations prepared; supervisor approval pending before any final use | `08_backup_song_expansion/08_supervisor_review_package/` |
| Torres | New Skin | 6.010431 | 34.010431 | 7 | 7 | Backup supervisor-review recommendations prepared; supervisor approval pending before any final use | `08_backup_song_expansion/08_supervisor_review_package/` |
| Dawn Langstroth | No Prize | 24.760431 | 52.760431 | 9 | 9 | Backup supervisor-review recommendations prepared; supervisor approval pending before any final use | `08_backup_song_expansion/08_supervisor_review_package/` |

## 4. Main Recommended Mixes

These are the original acoustic-diversity representative/contrast selections from Stage 4, using original Mix Evaluation Dataset names.

| Artist | Song | Representative | Contrast 1 | Contrast 2 |
| --- | --- | --- | --- | --- |
| The DoneFors | Lead Me | McG-A | PXL-L1 | DU-D |
| Fredy V | In The Meantime | UCP-A4 | DU-J | QUT-B |
| Broken Crank | Red To Blue | McG-A | McG-B | McG-F |
| The DoneFors | Pouring Room | McG-Q | McG-pro1 | McG-X |

## 5. Supervisor Recommendation Sets

These are the revised supervisor-review triplets produced by rating stratification after corrected acoustic screening.

### Main Songs

| Artist | Song | Similar Ratings | Wide Ratings |
| --- | --- | --- | --- |
| The DoneFors | Lead Me | DU-D|DU-E|QUT-F | PXL-L1|PXL-L4|McG-pro2 |
| Fredy V | In The Meantime | QUT-B|DU-H|DU-I | DU-K|QUT-pro|DU-N |
| Broken Crank | Red To Blue | McG-B|McG-G|McG-F | McG-C|McG-H|McG-pro1 |
| The DoneFors | Pouring Room | McG-R|McG-T|McG-X | McG-pro1|McG-U|McG-V |

### Backup Songs

| Artist | Song | Similar Ratings | Wide Ratings |
| --- | --- | --- | --- |
| The Districts | Vermont | DU-P2|DU-O2|PXL-L3 | PXL-L1|PXL-L4|PXL-L5 |
| Filthybird | I'd Like To Know | PXL-S3|PXL-S5|PXL-S1 | PXL-S2|PXL-S6|PXL-S7 |
| Torres | New Skin | DU-Q|DU-R|DU-O | DU-U|DU-T|DU-S |
| Dawn Langstroth | No Prize | McG-L|McG-pro2|McG-N | McG-K|McG-P|McG-O |

## 6. Pipeline Outputs

| Folder | Purpose | Examples |
| --- | --- | --- |
| `01_dataset_and_song_selection/` | Dataset inspection and original song/mix inventory | tables/candidate_song_ranking.csv; reports/dataset_inspection_report.md |
| `02_excerpt_selection/` | Main-song alignment and approved excerpt candidates | tables/excerpt_candidates.csv; approved_excerpt_previews/ |
| `03_feature_extraction/` | Main-song Diff-MST feature extraction | tables/raw_diffmst_features.csv |
| `04_mix_selection/` | Original representative/contrast acoustic selection | tables/recommended_triplets.csv |
| `04_mix_selection_v2/` | Corrected acoustic candidate pools excluding stereo imbalance from diversity | tables/acoustic_candidate_pool.csv; tables/pairwise_distances_v2.csv |
| `05_ratings_integration/` | Main-song Brecht prior-rating aggregation | tables/mix_preference_rating_summary_within_song.csv |
| `05_alignment_verification/` | Main-song Phase 2C alignment QA | reports/alignment_verification_booklet.pdf; tables/alignment_summary.csv |
| `05_manual_review/` | Earlier/manual review materials | tables/; instructions/ |
| `06_rating_stratification/` | Main-song Similar/Wide rating-stratified supervisor recommendations | tables/supervisor_shortlist.csv; candidate_review_audio/ |
| `06_final_summaries/` | Earlier final summary outputs | summary artifacts |
| `07_supervisor_review_package/` | Main supervisor-review package | supervisor_review_form.csv; alignment_verification_booklet.pdf |
| `08_backup_song_expansion/01_backup_song_selection/` | Backup song suitability ranking and selection report | backup_song_ranking.csv |
| `08_backup_song_expansion/02_excerpt_selection/` | Backup excerpt selection and approved previews | tables/excerpt_candidates.csv; approved_excerpt_previews/ |
| `08_backup_song_expansion/03_feature_extraction/` | Backup Diff-MST feature extraction | tables/raw_diffmst_features_backup.csv |
| `08_backup_song_expansion/04_acoustic_candidate_pools/` | Backup corrected acoustic candidate pools | tables/acoustic_candidate_pool_backup.csv |
| `08_backup_song_expansion/05_ratings_integration/` | Backup prior-rating aggregation | tables/mix_preference_rating_summary_within_song_backup.csv |
| `08_backup_song_expansion/06_rating_stratification/` | Backup Similar/Wide recommendations | tables/supervisor_shortlist_backup.csv; candidate_review_audio/ |
| `08_backup_song_expansion/07_alignment_verification/` | Backup alignment QA | tables/alignment_summary_backup.csv; figures/; review_audio/ |
| `08_backup_song_expansion/08_supervisor_review_package/` | Backup supervisor-review package | supervisor_review_form.csv; alignment_verification_booklet.pdf |
| `08_backup_song_expansion/reports/` | Backup validation summary | backup_expansion_validation.json |
| `archive_unused/` | Archived/unused outputs retained for provenance | archived artifacts |
| `logs_and_provenance/` | Pipeline provenance and logs | provenance records |

## 7. Supervisor Packages

| Package | Folder | ZIP | Alignment booklet |
| --- | --- | --- | --- |
| Main supervisor package | `07_supervisor_review_package/` | `07_supervisor_review_package.zip` | `07_supervisor_review_package/alignment_verification_booklet.pdf` |
| Backup supervisor package | `08_backup_song_expansion/08_supervisor_review_package/` | `08_backup_song_expansion/08_supervisor_review_package.zip` | `08_backup_song_expansion/08_supervisor_review_package/alignment_verification_booklet.pdf` |

## 8. Final Study Status

- Current approved/main supervisor-review songs: The DoneFors - Lead Me, Fredy V - In The Meantime, Broken Crank - Red To Blue, The DoneFors - Pouring Room.
- Current backup supervisor-review songs: The Districts - Vermont, Filthybird - I'd Like To Know, Torres - New Skin, Dawn Langstroth - No Prize.
- Frontend status: this index does not update the frontend. The revised main/backup supervisor packages have not been pushed into frontend stimulus configuration by this documentation task.
- Final participant stimuli status: this index does not regenerate final participant stimuli. Existing `outputs/final_stimuli/` files are separate from these pending supervisor-review recommendations.
- Supervisor approval status: still pending before final revised stimulus generation and any frontend update.

## 9. Reproducibility

- Diff-MST implementation: vendored implementation under `src/stimulus_selection/third_party/diffmst_features/`, validated by the project tests and used for RMS, crest factor, stereo width, stereo imbalance, and Bark mid/side features.
- Corrected acoustic methodology: `mix_selection_v2`, methodology version 2.0, uses robust within-song scaling, Bark PCA retaining at least 95% variance, equal scalar/Bark block weighting, and combined Euclidean distance.
- Stereo imbalance: retained in raw feature and QC tables, but excluded from diversity scaling, combined coordinates, medoid calculation, acoustic distances, and diversity ranking.
- Prior ratings: Brecht/Mix Evaluation prior no-context preference ratings are joined by `mix_id` and used only after acoustic candidate-pool selection for Similar/Wide stratification.
- Alignment verification: recommended triplets are checked using pairwise residual lag/correlation, stacked waveform figures, transient zoom figures, and rapid-switch listening files.
- Version/configuration: main config is `configs/stimulus_selection.yaml`; backup config block is `backup_song_expansion` in the same file.
- Repository: `C:/Users/oscar/Documents/7. QMUL UNIVERSITY/1. Master Program/3. MSc Project/intent2control-dissertation`.
- Random seed: deterministic seed 42 for corrected acoustic candidate-pool and related deterministic selection steps.

## Validation

- All referenced paths exist: true
- Excerpt times were read from canonical raw feature tables: true
- Main song list matches current recommendation table: true
- Backup song list matches current recommendation table: true
- No scientific outputs were modified to create this index.
