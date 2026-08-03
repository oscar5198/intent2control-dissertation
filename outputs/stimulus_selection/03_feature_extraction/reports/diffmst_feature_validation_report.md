# Diff-MST Feature Validation Report

- Reference repository: `C:\Users\oscar\Documents\7. QMUL UNIVERSITY\1. Master Program\3. MSc Project\Diff-MST`
- Source repository: `https://github.com/sai-soum/Diff-MST.git`
- Source commit: `3b90ef838272b827c86610cf25b510a23a4147fd`
- Source paths: `mst/loss.py`, `mst/filter.py`
- Functions copied: `compute_rms`, `compute_crest_factor`, `compute_stereo_width`, `compute_stereo_imbalance`, `compute_barkspectrum`, `barkscale_fbanks`, `_hz_to_bark`, `_bark_to_hz`, `_create_triangular_filterbank`
- Compatibility changes: removed neural-model dependencies; converted imports to package-local paths; added shape and finite-value validation; preserved reference feature defaults for valid tensors.
- Package versions: Python 3.10.14, PyTorch 2.5.1, NumPy 2.2.5

## Bark Output Shape

- `mono`: `(1, 24, 1)`
- `stereo`: `(1, 24, 2)`
- `mid-side`: `(1, 24, 2)`

## Equivalence Summary

- Passed rows: 65/65
- Maximum absolute error: 0
- Maximum relative error: 0
- Test cases: identical stereo sine wave; different-amplitude stereo sine wave; left-only signal; correlated deterministic stereo noise; partially decorrelated stereo noise; impulse plus low-level noise; float32 and float64 variants; one Stage 2 decoded real preview excerpt when present.

| test_case | feature | max_abs | mean_abs | max_rel | passed |
| --- | --- | ---: | ---: | ---: | --- |
| identical_stereo_sine | RMS | 0 | 0 | 0 | true |
| identical_stereo_sine | CF | 0 | 0 | 0 | true |
| identical_stereo_sine | SW | 0 | 0 | 0 | true |
| identical_stereo_sine | SI | 0 | 0 | 0 | true |
| identical_stereo_sine | BS | 0 | 0 | 0 | true |
| different_amplitude_stereo_sine | RMS | 0 | 0 | 0 | true |
| different_amplitude_stereo_sine | CF | 0 | 0 | 0 | true |
| different_amplitude_stereo_sine | SW | 0 | 0 | 0 | true |
| different_amplitude_stereo_sine | SI | 0 | 0 | 0 | true |
| different_amplitude_stereo_sine | BS | 0 | 0 | 0 | true |
| left_only_signal | RMS | 0 | 0 | 0 | true |
| left_only_signal | CF | 0 | 0 | 0 | true |
| left_only_signal | SW | 0 | 0 | 0 | true |
| left_only_signal | SI | 0 | 0 | 0 | true |
| left_only_signal | BS | 0 | 0 | 0 | true |
| correlated_stereo_deterministic_noise | RMS | 0 | 0 | 0 | true |
| correlated_stereo_deterministic_noise | CF | 0 | 0 | 0 | true |
| correlated_stereo_deterministic_noise | SW | 0 | 0 | 0 | true |
| correlated_stereo_deterministic_noise | SI | 0 | 0 | 0 | true |
| correlated_stereo_deterministic_noise | BS | 0 | 0 | 0 | true |
| partially_decorrelated_stereo_noise | RMS | 0 | 0 | 0 | true |
| partially_decorrelated_stereo_noise | CF | 0 | 0 | 0 | true |
| partially_decorrelated_stereo_noise | SW | 0 | 0 | 0 | true |
| partially_decorrelated_stereo_noise | SI | 0 | 0 | 0 | true |
| partially_decorrelated_stereo_noise | BS | 0 | 0 | 0 | true |
| impulse_plus_low_level_noise | RMS | 0 | 0 | 0 | true |
| impulse_plus_low_level_noise | CF | 0 | 0 | 0 | true |
| impulse_plus_low_level_noise | SW | 0 | 0 | 0 | true |
| impulse_plus_low_level_noise | SI | 0 | 0 | 0 | true |
| impulse_plus_low_level_noise | BS | 0 | 0 | 0 | true |
| identical_stereo_sine | RMS | 0 | 0 | 0 | true |
| identical_stereo_sine | CF | 0 | 0 | 0 | true |
| identical_stereo_sine | SW | 0 | 0 | 0 | true |
| identical_stereo_sine | SI | 0 | 0 | 0 | true |
| identical_stereo_sine | BS | 0 | 0 | 0 | true |
| different_amplitude_stereo_sine | RMS | 0 | 0 | 0 | true |
| different_amplitude_stereo_sine | CF | 0 | 0 | 0 | true |
| different_amplitude_stereo_sine | SW | 0 | 0 | 0 | true |
| different_amplitude_stereo_sine | SI | 0 | 0 | 0 | true |
| different_amplitude_stereo_sine | BS | 0 | 0 | 0 | true |
| left_only_signal | RMS | 0 | 0 | 0 | true |
| left_only_signal | CF | 0 | 0 | 0 | true |
| left_only_signal | SW | 0 | 0 | 0 | true |
| left_only_signal | SI | 0 | 0 | 0 | true |
| left_only_signal | BS | 0 | 0 | 0 | true |
| correlated_stereo_deterministic_noise | RMS | 0 | 0 | 0 | true |
| correlated_stereo_deterministic_noise | CF | 0 | 0 | 0 | true |
| correlated_stereo_deterministic_noise | SW | 0 | 0 | 0 | true |
| correlated_stereo_deterministic_noise | SI | 0 | 0 | 0 | true |
| correlated_stereo_deterministic_noise | BS | 0 | 0 | 0 | true |
| partially_decorrelated_stereo_noise | RMS | 0 | 0 | 0 | true |
| partially_decorrelated_stereo_noise | CF | 0 | 0 | 0 | true |
| partially_decorrelated_stereo_noise | SW | 0 | 0 | 0 | true |
| partially_decorrelated_stereo_noise | SI | 0 | 0 | 0 | true |
| partially_decorrelated_stereo_noise | BS | 0 | 0 | 0 | true |
| impulse_plus_low_level_noise | RMS | 0 | 0 | 0 | true |
| impulse_plus_low_level_noise | CF | 0 | 0 | 0 | true |
| impulse_plus_low_level_noise | SW | 0 | 0 | 0 | true |
| impulse_plus_low_level_noise | SI | 0 | 0 | 0 | true |
| impulse_plus_low_level_noise | BS | 0 | 0 | 0 | true |
| real_stage2_decoded_excerpt:InTheMeantime_approved_preview_01.wav | RMS | 0 | 0 | 0 | true |
| real_stage2_decoded_excerpt:InTheMeantime_approved_preview_01.wav | CF | 0 | 0 | 0 | true |
| real_stage2_decoded_excerpt:InTheMeantime_approved_preview_01.wav | SW | 0 | 0 | 0 | true |
| real_stage2_decoded_excerpt:InTheMeantime_approved_preview_01.wav | SI | 0 | 0 | 0 | true |
| real_stage2_decoded_excerpt:InTheMeantime_approved_preview_01.wav | BS | 0 | 0 | 0 | true |

## Edge Cases

| case | feature | passed | notes |
| --- | --- | --- | --- |
| silence | RMS | true | finite output |
| silence | CF | true | finite output |
| silence | SW | true | finite output |
| silence | SI | true | finite output |
| silence | BS | true | finite output |
| near_silence | RMS | true | finite output |
| near_silence | CF | true | finite output |
| near_silence | SW | true | finite output |
| near_silence | SI | true | finite output |
| near_silence | BS | true | finite output |
| zero_energy_sum_signal | RMS | true | finite output |
| zero_energy_sum_signal | CF | true | finite output |
| zero_energy_sum_signal | SW | true | finite output |
| zero_energy_sum_signal | SI | true | finite output |
| zero_energy_sum_signal | BS | true | finite output |
| mono_input_to_stereo_feature | RMS | true | finite output |
| mono_input_to_stereo_feature | CF | true | finite output |
| mono_input_to_stereo_feature | SW | true | raised ValueError: Expected exactly two channels for this stereo feature; got 1. |
| mono_input_to_stereo_feature | SI | true | raised ValueError: Expected exactly two channels for this stereo feature; got 1. |
| mono_input_to_stereo_feature | BS | true | raised ValueError: Expected exactly two channels for this stereo feature; got 1. |
| nan_input | RMS | true | raised ValueError: Input contains NaN or Inf values. |
| nan_input | CF | true | raised ValueError: Input contains NaN or Inf values. |
| nan_input | SW | true | raised ValueError: Input contains NaN or Inf values. |
| nan_input | SI | true | raised ValueError: Input contains NaN or Inf values. |
| nan_input | BS | true | raised ValueError: Input contains NaN or Inf values. |
| inf_input | RMS | true | raised ValueError: Input contains NaN or Inf values. |
| inf_input | CF | true | raised ValueError: Input contains NaN or Inf values. |
| inf_input | SW | true | raised ValueError: Input contains NaN or Inf values. |
| inf_input | SI | true | raised ValueError: Input contains NaN or Inf values. |
| inf_input | BS | true | raised ValueError: Input contains NaN or Inf values. |
| very_short_input | RMS | true | finite output |
| very_short_input | CF | true | finite output |
| very_short_input | SW | true | finite output |
| very_short_input | SI | true | finite output |
| very_short_input | BS | true | raised RuntimeError: Argument #4: Padding size should be less than the corresponding input dimension, but got: padding (16384, 16384) at dimension 2 of input [1, 1, 8] |
| float64_cpu_input | RMS | true | finite output |
| float64_cpu_input | CF | true | finite output |
| float64_cpu_input | SW | true | finite output |
| float64_cpu_input | SI | true | finite output |
| float64_cpu_input | BS | true | finite output |

## Approval

Approved for dataset extraction: yes

These transforms describe mix dynamics, spectral characteristics and spatialisation. They are not subjective quality scores.
