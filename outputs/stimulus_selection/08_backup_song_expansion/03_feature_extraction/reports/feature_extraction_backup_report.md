# Stage 3B Diff-MST Feature Extraction Report

Features were extracted from the aligned 28-second excerpts before preview fades, loudness normalisation, peak normalisation, limiting or compression.

## Approved Excerpts
- The Districts - Vermont: 21.000454 to 49.000454 seconds
- Filthybird - I'd Like To Know: 21.000454 to 49.000454 seconds
- Torres - New Skin: 6.010431 to 34.010431 seconds
- Dawn Langstroth - No Prize: 24.760431 to 52.760431 seconds

## Implementation

- Vendored implementation: `src/stimulus_selection/third_party/diffmst_features/`
- Reference validation: commit `3b90ef838272b827c86610cf25b510a23a4147fd`, 65/65 equivalence rows passed, 40/40 edge-case checks passed, max absolute and relative error 0.
- Bark mapping: `(batch, 24, 2)` in mid-side mode; `[..., 0]` -> `bark_mid_01..24`, `[..., 1]` -> `bark_side_01..24`.
- Feature parameters: sample rate 44100 Hz, 28.000 seconds, 1,234,800 samples, stereo, Bark FFT 32768, hop 8192, 24 bands, 20-20000 Hz, Hann window, magnitude STFT, temporal mean, log epsilon 1e-8.

## Decoder Environment

- ffmpeg: unavailable
- ffprobe: unavailable
- soundfile available: True
- librosa available: False
- audioread available: True
- Python: 3.10.14
- PyTorch: 2.5.1
- NumPy: 2.2.5

## Counts

- Total rows: 30
- Successful rows: 30
- Dawn Langstroth - No Prize: 9
- Filthybird - I'd Like To Know: 7
- The Districts - Vermont: 7
- Torres - New Skin: 7

## Stage 2 Population And Exclusions

- Dawn Langstroth - No Prize: retained 9, excluded 0.
- Filthybird - I'd Like To Know: retained 7, excluded 0.
- The Districts - Vermont: retained 7, excluded 0.
- Torres - New Skin: retained 7, excluded 0.

## Scalar Feature Ranges

| song | feature | min | max |
| --- | --- | ---: | ---: |
| Dawn Langstroth - No Prize | rms_left | 0.0393848 | 0.163519 |
| Dawn Langstroth - No Prize | rms_right | 0.0370271 | 0.163321 |
| Dawn Langstroth - No Prize | rms_mean | 0.0382059 | 0.162479 |
| Dawn Langstroth - No Prize | crest_factor_left | 13.1853 | 18.3561 |
| Dawn Langstroth - No Prize | crest_factor_right | 13.7412 | 18.7418 |
| Dawn Langstroth - No Prize | crest_factor_mean | 13.6817 | 18.5489 |
| Dawn Langstroth - No Prize | stereo_width | 0.0186138 | 0.129983 |
| Dawn Langstroth - No Prize | stereo_imbalance | -0.0910624 | 0.0103588 |
| Filthybird - I'd Like To Know | rms_left | 0.0547931 | 0.0628157 |
| Filthybird - I'd Like To Know | rms_right | 0.0530055 | 0.0636735 |
| Filthybird - I'd Like To Know | rms_mean | 0.0548075 | 0.0632446 |
| Filthybird - I'd Like To Know | crest_factor_left | 14.3201 | 17.7072 |
| Filthybird - I'd Like To Know | crest_factor_right | 15.2083 | 17.9067 |
| Filthybird - I'd Like To Know | crest_factor_mean | 14.7642 | 17.4849 |
| Filthybird - I'd Like To Know | stereo_width | 0.0243665 | 0.146867 |
| Filthybird - I'd Like To Know | stereo_imbalance | -0.0656843 | 0.0736308 |
| The Districts - Vermont | rms_left | 0.0503606 | 0.0564681 |
| The Districts - Vermont | rms_right | 0.0495591 | 0.0574136 |
| The Districts - Vermont | rms_mean | 0.0499599 | 0.0565968 |
| The Districts - Vermont | crest_factor_left | 11.964 | 18.3566 |
| The Districts - Vermont | crest_factor_right | 12.5755 | 17.9026 |
| The Districts - Vermont | crest_factor_mean | 12.2698 | 18.1297 |
| The Districts - Vermont | stereo_width | 0.0502258 | 0.128092 |
| The Districts - Vermont | stereo_imbalance | -0.0275271 | 0.0288573 |
| Torres - New Skin | rms_left | 0.0483078 | 0.0590911 |
| Torres - New Skin | rms_right | 0.0532619 | 0.0627601 |
| Torres - New Skin | rms_mean | 0.0537556 | 0.0609256 |
| Torres - New Skin | crest_factor_left | 13.6511 | 20.513 |
| Torres - New Skin | crest_factor_right | 14.784 | 20.9019 |
| Torres - New Skin | crest_factor_mean | 14.2176 | 20.7074 |
| Torres - New Skin | stereo_width | 0.0675236 | 0.230609 |
| Torres - New Skin | stereo_imbalance | -0.0783838 | 0.200627 |

## Quality-Control Warnings

- [warning] Dawn Langstroth - No Prize / highly_correlated_scalar_features: rms_left~rms_right=0.998; rms_left~rms_mean=0.999; rms_right~rms_mean=0.999
- [warning] The Districts - Vermont / highly_correlated_scalar_features: rms_right~rms_mean=0.986; crest_factor_left~crest_factor_right=0.980; crest_factor_left~crest_factor_mean=0.996; crest_factor_right~crest_factor_mean=0.994

## Determinism

- Small deterministic subset repeated identically: true
- Config hash: `61eecf7d3f30a000e66523cffa999daf10428d34506b149c991e37a4b8e86d11`
- Feature extraction source hash: `1d4f7b74f6549f2ea93662cce347e583edef715f6b4b9a06dc4acc5e1214c7e6`
- Vendored feature source hash: `bd693579b5b19add0b2b8c88727d05d90c6acafab599250138b7e3aecd0de588`

## Stage 4 Readiness

Ready for Stage 4 preprocessing and selection: yes

No robust scaling, standardisation, PCA, pairwise distances, triplet selection, final Version A/B/C labels, or loudness normalisation were performed.
