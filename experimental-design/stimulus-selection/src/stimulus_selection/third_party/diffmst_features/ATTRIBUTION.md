# Diff-MST Feature Attribution

This package contains a minimal dissertation-specific adaptation of five audio-production feature transforms from Diff-MST.

- Source repository: https://github.com/sai-soum/Diff-MST.git
- Reference commit: `3b90ef838272b827c86610cf25b510a23a4147fd`
- Local reference repository inspected: `C:/Users/oscar/Documents/7. QMUL UNIVERSITY/1. Master Program/3. MSc Project/Diff-MST`
- Licence: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
- Date vendored: 2026-07-24
- Paper citation: Diff-MST paper associated with the repository above and the local dissertation copy at `bibliography/papers/04_Differentiable_DSP/DIFF-MST.pdf`.

## Copied Functions

From `mst/loss.py`:

- `compute_rms`
- `compute_crest_factor`
- `compute_stereo_width`
- `compute_stereo_imbalance`
- `compute_barkspectrum`

From `mst/filter.py`:

- `barkscale_fbanks`
- `_hz_to_bark`
- `_bark_to_hz`
- `_create_triangular_filterbank`

## Compatibility Modifications

- Removed imports and code for the Diff-MST neural model, data loaders, losses, mel features, FX encoder and spectrogram encoder.
- Replaced `mst.filter` imports with package-local imports.
- Added explicit input validation for the dissertation contract `(batch, channels, samples)`.
- Added clear errors for unsupported stereo feature shapes.
- Added finite-value validation so NaN and Inf inputs are rejected before feature computation.
- Preserved reference numerical defaults for valid tensors, including Bark FFT size, hop length, Hann window, magnitude spectrum, time averaging and log epsilon.
