# Stage 3B Diff-MST Feature Extraction Report

Features were extracted from the aligned 28-second excerpts before preview fades, loudness normalisation, peak normalisation, limiting or compression.

## Approved Excerpts
- The DoneFors - Lead Me: 9.573107 to 37.573107 seconds
- Fredy V - In The Meantime: 35.300431 to 63.300431 seconds
- Broken Crank - Red To Blue: 3.005442 to 31.005442 seconds
- The DoneFors - Pouring Room: 23.020408 to 51.020408 seconds

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

- Total rows: 92
- Successful rows: 92
- Broken Crank - Red To Blue: 10
- Fredy V - In The Meantime: 36
- The DoneFors - Lead Me: 37
- The DoneFors - Pouring Room: 9

## Stage 2 Population And Exclusions

- Broken Crank - Red To Blue: retained 10, excluded 1.
  - mix_1baafc9b5b1d: automated_or_system_generated
- Fredy V - In The Meantime: retained 36, excluded 0.
- The DoneFors - Lead Me: retained 37, excluded 1.
  - mix_95d77ba996e4: automated_or_system_generated
- The DoneFors - Pouring Room: retained 9, excluded 1.
  - mix_d1edc48dc058: low_alignment_confidence

## Scalar Feature Ranges

| song | feature | min | max |
| --- | --- | ---: | ---: |
| Broken Crank - Red To Blue | rms_left | 0.0425793 | 0.0522551 |
| Broken Crank - Red To Blue | rms_right | 0.0435292 | 0.0530042 |
| Broken Crank - Red To Blue | rms_mean | 0.0437414 | 0.052424 |
| Broken Crank - Red To Blue | crest_factor_left | 14.3211 | 18.4335 |
| Broken Crank - Red To Blue | crest_factor_right | 14.04 | 16.8053 |
| Broken Crank - Red To Blue | crest_factor_mean | 14.4259 | 17.6194 |
| Broken Crank - Red To Blue | stereo_width | 0.022538 | 0.249742 |
| Broken Crank - Red To Blue | stereo_imbalance | -0.0491484 | 0.126785 |
| Fredy V - In The Meantime | rms_left | 0.0351481 | 0.061243 |
| Fredy V - In The Meantime | rms_right | 0.0493548 | 0.0698107 |
| Fredy V - In The Meantime | rms_mean | 0.0503131 | 0.0623472 |
| Fredy V - In The Meantime | crest_factor_left | 12.9846 | 23.3778 |
| Fredy V - In The Meantime | crest_factor_right | 13.8832 | 22.9502 |
| Fredy V - In The Meantime | crest_factor_mean | 13.4339 | 22.9316 |
| Fredy V - In The Meantime | stereo_width | 0.000543583 | 0.220763 |
| Fredy V - In The Meantime | stereo_imbalance | -0.122863 | 0.595546 |
| The DoneFors - Lead Me | rms_left | 0.053191 | 0.0730575 |
| The DoneFors - Lead Me | rms_right | 0.0555637 | 0.0755444 |
| The DoneFors - Lead Me | rms_mean | 0.0543774 | 0.0730312 |
| The DoneFors - Lead Me | crest_factor_left | 11.032 | 20.6877 |
| The DoneFors - Lead Me | crest_factor_right | 11.5192 | 20.5632 |
| The DoneFors - Lead Me | crest_factor_mean | 11.2756 | 20.6254 |
| The DoneFors - Lead Me | stereo_width | 0.0144364 | 0.149042 |
| The DoneFors - Lead Me | stereo_imbalance | -0.112907 | 0.181386 |
| The DoneFors - Pouring Room | rms_left | 0.0549234 | 0.0661999 |
| The DoneFors - Pouring Room | rms_right | 0.0574258 | 0.0648362 |
| The DoneFors - Pouring Room | rms_mean | 0.0587656 | 0.0646217 |
| The DoneFors - Pouring Room | crest_factor_left | 15.3441 | 20.7986 |
| The DoneFors - Pouring Room | crest_factor_right | 17.0482 | 21.1563 |
| The DoneFors - Pouring Room | crest_factor_mean | 16.5152 | 20.8416 |
| The DoneFors - Pouring Room | stereo_width | 0.0750392 | 0.21738 |
| The DoneFors - Pouring Room | stereo_imbalance | -0.0638296 | 0.164419 |

## Quality-Control Warnings

- [warning] Broken Crank - Red To Blue / duplicate_or_near_duplicate_feature_vectors: McG-pro1 (internal ID: mix_808780e357c9)~McG-pro (internal ID: mix_906e7f7daf44)
- [warning] Fredy V - In The Meantime / highly_correlated_scalar_features: crest_factor_left~crest_factor_mean=0.985; crest_factor_right~crest_factor_mean=0.982
- [warning] Fredy V - In The Meantime / duplicate_or_near_duplicate_feature_vectors: McG-pro (internal ID: mix_027ec3f8b8f1)~McG-pro2 (internal ID: mix_690c5c454a9f)
- [warning] The DoneFors - Lead Me / highly_correlated_scalar_features: crest_factor_left~crest_factor_mean=0.982; crest_factor_right~crest_factor_mean=0.984
- [warning] The DoneFors - Lead Me / duplicate_or_near_duplicate_feature_vectors: McG-pro2 (internal ID: mix_d3e3580b6e30)~McG-pro (internal ID: mix_fa064711a381)
- [warning] The DoneFors - Pouring Room / duplicate_or_near_duplicate_feature_vectors: McG-pro1 (internal ID: mix_132e75f34470)~McG-pro (internal ID: mix_9f79c0810c7e)

## Determinism

- Small deterministic subset repeated identically: true
- Config hash: `d35fa7771f0000d20d85037e504a5a10e62b9e1f8b56ebf4c22b17fb6fb8314e`
- Feature extraction source hash: `dd934b9e93ed4ed1f01f16d74ccdc11273c2837482d1c46a6bb07cb9e65e1e00`
- Vendored feature source hash: `bd693579b5b19add0b2b8c88727d05d90c6acafab599250138b7e3aecd0de588`

## Stage 4 Readiness

Ready for Stage 4 preprocessing and selection: yes

No robust scaling, standardisation, PCA, pairwise distances, triplet selection, final Version A/B/C labels, or loudness normalisation were performed.
