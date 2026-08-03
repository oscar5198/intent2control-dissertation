# Stage 4 Final Mix Selection Report

Formula: within each song, scalar and Bark dimensions are robust-scaled as `(x - median) / IQR`. Bark-only PCA is fitted to robust-scaled Bark bins and the minimum number of PCs explaining at least 95% variance is retained. The scalar block and retained Bark-PC block are each divided by `sqrt(mean(row_squared_norm))`, then concatenated so each block has expected squared contribution 1.

## Broken Crank - Red To Blue

- Retained mix count: 10
- Medoid: McG-A (internal ID: mix_e2654ec905ad)
- Selected representative: McG-A (internal ID: mix_e2654ec905ad)
- Selected contrasts: McG-B (internal ID: mix_7ac13e0b6376), McG-F (internal ID: mix_dcc6aef84d67)
- Pairwise distances: minimum 1.9011, mean 2.0238
- Bark PCA: 5 components, 96.26% variance explained
- Institutions represented: McG
- Sensitivity stability: 0.697
- QC and outlier review: 1 song-level warnings; selected high-outlier mixes: McG-B (internal ID: mix_7ac13e0b6376)
- Alternatives not selected: higher-dispersion alternatives were rejected when they omitted the medoid or contained Stage 3 near-duplicate pairs; institution diversity was used only as a secondary advantage.
## Fredy V - In The Meantime

- Retained mix count: 36
- Medoid: UCP-A4 (internal ID: mix_efdedc0a36e7)
- Selected representative: UCP-A4 (internal ID: mix_efdedc0a36e7)
- Selected contrasts: DU-J (internal ID: mix_22efc79c8253), QUT-B (internal ID: mix_c7bdcba64775)
- Pairwise distances: minimum 4.0176, mean 5.3933
- Bark PCA: 8 components, 95.59% variance explained
- Institutions represented: DU, QUT, UCP
- Sensitivity stability: 0.848
- QC and outlier review: 2 song-level warnings; selected high-outlier mixes: DU-J (internal ID: mix_22efc79c8253), QUT-B (internal ID: mix_c7bdcba64775)
- Alternatives not selected: higher-dispersion alternatives were rejected when they omitted the medoid or contained Stage 3 near-duplicate pairs; institution diversity was used only as a secondary advantage.
## The DoneFors - Lead Me

- Retained mix count: 37
- Medoid: McG-A (internal ID: mix_9346b5d4ade2)
- Selected representative: McG-A (internal ID: mix_9346b5d4ade2)
- Selected contrasts: PXL-L1 (internal ID: mix_d5b28dfc8a93), DU-D (internal ID: mix_f1f7973e5bac)
- Pairwise distances: minimum 2.5765, mean 2.8586
- Bark PCA: 9 components, 95.04% variance explained
- Institutions represented: DU, McG, PXL
- Sensitivity stability: 0.727
- QC and outlier review: 2 song-level warnings; selected high-outlier mixes: PXL-L1 (internal ID: mix_d5b28dfc8a93), DU-D (internal ID: mix_f1f7973e5bac)
- Alternatives not selected: higher-dispersion alternatives were rejected when they omitted the medoid or contained Stage 3 near-duplicate pairs; institution diversity was used only as a secondary advantage.

## The DoneFors - Pouring Room

- Retained mix count: 9
- Medoid: McG-Q (internal ID: mix_0ddb25d6180b)
- Selected representative: McG-Q (internal ID: mix_0ddb25d6180b)
- Selected contrasts: McG-pro1 (internal ID: mix_132e75f34470), McG-X (internal ID: mix_cbf8555ee2b2)
- Pairwise distances: minimum 1.9163, mean 2.0121
- Bark PCA: 5 components, 97.05% variance explained
- Institutions represented: McG
- Sensitivity stability: 0.727
- QC and outlier review: 1 song-level warnings; selected high-outlier mixes: none
- Alternatives not selected: higher-dispersion alternatives were rejected when they omitted the medoid or contained Stage 3 near-duplicate pairs; institution diversity was used only as a secondary advantage.
