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
| Red To Blue | 10 | 10 | 5 | 0.963 | McG-A | 0.000 | 2.007 | 1 | 1 |
| In The Meantime | 36 | 20 | 8 | 0.956 | UCP-A4 | 0.919 | 2.255 | 2 | 0 |
| Lead Me | 37 | 20 | 9 | 0.950 | CNS-C | 1.233 | 2.310 | 0 | 0 |
| Pouring Room | 9 | 9 | 5 | 0.971 | McG-W | 0.000 | 1.973 | 1 | 1 |

## Candidate Pool Composition

- Red To Blue: McG-C, McG-H, McG-B, McG-pro1, McG-D, McG-pro, McG-G, McG-F, McG-A, McG-E
- In The Meantime: UCP-A4, QUT-B, DU-K, DU-H, DU-I, QUT-pro, QUT-C, McG-D, DU-J, McG-H, DU-N, QUT-A, PXL-S5, McG-A, QUT-J, DU-L, QUT-G, PXL-S7, DU-M, McG-F
- Lead Me: CNS-C, DU-D, PXL-L1, QUT-A, DU-E, PXL-L4, QUT-pro, PXL-L3, DU-A, QUT-F, DU-F, DU-B, CNS-B, UCP-A2, DU-C, PXL-L2, McG-pro2, McG-H, McG-B, QUT-H
- Pouring Room: McG-R, McG-Q, McG-pro1, McG-U, McG-W, McG-pro, McG-T, McG-X, McG-V

## Stereo-Imbalance QC Flags

- Red To Blue / McG-B: score 4.11; signed imbalance 0.1268.
- In The Meantime / QUT-A: score 4.34; signed imbalance -0.1229.
- In The Meantime / DU-J: score 25.60; signed imbalance 0.5955.
- Pouring Room / McG-W: score 5.78; signed imbalance 0.1644.

## v1 Selection Comparison

- Red To Blue: v1 retained in v2 pool: McG-A, McG-B, McG-F; v1 displaced: none.
- In The Meantime: v1 retained in v2 pool: DU-J, QUT-B, UCP-A4; v1 displaced: none.
- Lead Me: v1 retained in v2 pool: DU-D, PXL-L1; v1 displaced: McG-A.
- Pouring Room: v1 retained in v2 pool: McG-Q, McG-X, McG-pro1; v1 displaced: none.

## Preview Audio

- Review previews generated: 59.
- Location: `outputs/stimulus_selection/04_mix_selection_v2/candidate_pool_previews/`.
- Policy: raw level with review fade; no loudness normalisation, limiting, or compression.

## Phase 2 Readiness

The corrected acoustic candidate pools are ready for Phase 2 preference-rating integration. These pools are not final stimuli and do not encode final six-mix recommendations.
