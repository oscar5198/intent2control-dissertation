# Acoustic Selection v2 Report

Stereo imbalance was removed from the acoustic-diversity distance after supervisor feedback. The concern is that a signed left/right imbalance descriptor, originally used in Diff-MST as part of a minimised reference-matching loss, can be rewarded when the dissertation pipeline maximises feature-space diversity.

## Revised Feature Set

- Scalar diversity block: `rms_mean`, `crest_factor_mean`, `stereo_width`.
- Spectral diversity block: `bark_mid_01` through `bark_mid_24`, and `bark_side_01` through `bark_side_24`.
- QC-only feature: `stereo_imbalance`.
- No Brecht preference ratings were used in this phase.

## Transformation

Within each song, scalar and Bark dimensions are robust-scaled as `(x - median) / IQR`, with zero or near-zero IQR dimensions set to zero. PCA is fitted only to the robust-scaled Bark block, retaining the minimum number of components explaining at least 95% cumulative variance. The scalar block and retained Bark-PC block are each divided by `sqrt(mean(row_squared_norm))` before concatenation, giving equal expected squared contribution to the combined acoustic distance.

## Stereo-Imbalance Exclusion Proof

Automated assertions verified that `stereo_imbalance` is absent from the v2 scalar diversity list, combined coordinate names, and all distance matrices. The proof table is `tests_and_validation/diversity_feature_assertions.csv`.

## Song Summaries

| Song | Retained | Pool | Bark PCs | Variance | Medoid | Min pool distance | Mean pool distance | SI flags in pool | Unrated in pool |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| No Prize | 9 | 9 | 3 | 0.969 | McG-M | 0.583 | 1.821 | 0 | 0 |
| I'd Like To Know | 7 | 7 | 5 | 0.980 | PXL-S2 | 0.949 | 2.021 | 0 | 0 |
| Vermont | 7 | 7 | 5 | 0.976 | PXL-L1 | 0.896 | 1.891 | 0 | 0 |
| New Skin | 7 | 7 | 4 | 0.969 | DU-P | 0.837 | 1.987 | 0 | 0 |

## Candidate Pool Composition

- No Prize: McG-K, McG-M, McG-P, McG-I, McG-L, McG-pro2, McG-N, McG-J, McG-O
- I'd Like To Know: PXL-S3, PXL-S2, PXL-S5, PXL-S1, PXL-S6, PXL-S4, PXL-S7
- Vermont: PXL-L1, DU-P2, PXL-L2, DU-O2, PXL-L4, PXL-L5, PXL-L3
- New Skin: DU-Q, DU-R, DU-O, DU-P, DU-U, DU-T, DU-S

## Stereo-Imbalance QC Flags

- No mixes exceeded the robust stereo-imbalance QC threshold.

## v1 Selection Comparison

- No Prize: v1 retained in v2 pool: none; v1 displaced: none.
- I'd Like To Know: v1 retained in v2 pool: none; v1 displaced: none.
- Vermont: v1 retained in v2 pool: none; v1 displaced: none.
- New Skin: v1 retained in v2 pool: none; v1 displaced: none.

## Preview Audio

- Review previews generated: 30.
- Location: `outputs/stimulus_selection/04_mix_selection_v2/candidate_pool_previews/`.
- Policy: raw level with review fade; no loudness normalisation, limiting, or compression.

## Phase 2 Readiness

The corrected acoustic candidate pools are ready for Phase 2 preference-rating integration. These pools are not final stimuli and do not encode final six-mix recommendations.
