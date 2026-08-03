# Alignment Verification Booklet

Subtitle: Revised Stimulus Selection - Phase 2C

Generation date: 2026-08-03

Methodology status: Awaiting manual/supervisor alignment review

Phase 2C is quality assurance only. Selection recommendations have not been changed. Automatic confidence is not treated as sufficient on its own; final acceptance requires visual and perceptual review. REVIEW and FAIL labels mean manual inspection is required, not necessarily that the mixes must be discarded. The rapid-switch audio remains the primary perceptual verification material.

## Executive Summary

- 8 triplets verified
- 24 pairwise comparisons
- 8 rapid-switch files
- 16 visual figures
- maximum automatic offset: 58.050 ms
- maximum-offset triplet: Pouring Room / Wide Ratings

## Methods Summary

- Approved 28-second excerpts were retained.
- Pairwise residual alignment was recomputed for each recommended triplet.
- Lag was reported in samples and milliseconds.
- Waveform plots were inspected on a shared time axis.
- Zoomed transient plots were generated.
- Rapid-switch WAVs were created for direct perceptual comparison.
- No loudness normalisation was applied to review audio.
- No selection decisions were changed.
- Automatic thresholds: PASS <=10 ms and correlation >=0.60; REVIEW <=30 ms and correlation >=0.35; otherwise FAIL

## Overall Alignment Results

| Song | Condition | Mix names | Max lag ms | Min correlation | Automatic status | Manual status |
| --- | --- | --- | ---: | ---: | --- | --- |
| In The Meantime | Similar Ratings | QUT-B | DU-H | DU-I | 34.830 | 0.555 | FAIL | pending |
| In The Meantime | Wide Ratings | DU-K | QUT-pro | DU-N | 23.220 | 0.682 | REVIEW | pending |
| Lead Me | Similar Ratings | DU-D | DU-E | QUT-F | 46.440 | 0.460 | FAIL | pending |
| Lead Me | Wide Ratings | PXL-L1 | PXL-L4 | McG-pro2 | 46.440 | 0.492 | FAIL | pending |
| Pouring Room | Similar Ratings | McG-R | McG-T | McG-X | 0.000 | 0.364 | REVIEW | pending |
| Pouring Room | Wide Ratings | McG-pro1 | McG-U | McG-V | 58.050 | 0.286 | FAIL | pending |
| Red To Blue | Similar Ratings | McG-B | McG-G | McG-F | 11.610 | 0.575 | REVIEW | pending |
| Red To Blue | Wide Ratings | McG-C | McG-H | McG-pro1 | 0.000 | 0.710 | PASS | pending |

## In The Meantime - Similar Ratings

- Original mix names: QUT-B | DU-H | DU-I
- Automatic status: FAIL
- Maximum lag: 34.830 ms
- Minimum correlation: 0.555
- Stereo-imbalance QC flags: false|false|false
- Rapid-switch audio: review_audio/In The Meantime/Similar Ratings/RapidSwitch.wav
- Individual review audio:
  - review_audio/In The Meantime/Similar Ratings/QUT-B_28sec.wav
  - review_audio/In The Meantime/Similar Ratings/DU-H_28sec.wav
  - review_audio/In The Meantime/Similar Ratings/DU-I_28sec.wav
- Stacked waveform figure: figures/In The Meantime/Similar Ratings/stacked_waveforms.png
- Zoomed strongest-transient figure: figures/In The Meantime/Similar Ratings/strongest_transient_zoom.png

| Pair | Lag samples | Lag ms | Correlation | Result |
| --- | ---: | ---: | ---: | --- |
| QUT-B-DU-H | 0 | 0.000 | 0.582 | REVIEW |
| QUT-B-DU-I | -1024 | -23.220 | 0.555 | REVIEW |
| DU-H-DU-I | -1536 | -34.830 | 0.617 | FAIL |

Manual-review prompts:

- Do major transients align visually?
- Is there any apparent constant offset?
- Is there any timing drift across the 28-second excerpt?
- Does rapid switching reveal a perceptible timing jump?
- Is the issue alignment, or only a mix-production difference?
- Accept alignment?
- Reviewer comments.

## In The Meantime - Wide Ratings

- Original mix names: DU-K | QUT-pro | DU-N
- Automatic status: REVIEW
- Maximum lag: 23.220 ms
- Minimum correlation: 0.682
- Stereo-imbalance QC flags: false|false|false
- Rapid-switch audio: review_audio/In The Meantime/Wide Ratings/RapidSwitch.wav
- Individual review audio:
  - review_audio/In The Meantime/Wide Ratings/DU-K_28sec.wav
  - review_audio/In The Meantime/Wide Ratings/QUT-pro_28sec.wav
  - review_audio/In The Meantime/Wide Ratings/DU-N_28sec.wav
- Stacked waveform figure: figures/In The Meantime/Wide Ratings/stacked_waveforms.png
- Zoomed strongest-transient figure: figures/In The Meantime/Wide Ratings/strongest_transient_zoom.png

| Pair | Lag samples | Lag ms | Correlation | Result |
| --- | ---: | ---: | ---: | --- |
| DU-K-QUT-pro | 0 | 0.000 | 0.704 | PASS |
| DU-K-DU-N | 1024 | 23.220 | 0.682 | REVIEW |
| QUT-pro-DU-N | 1024 | 23.220 | 0.719 | REVIEW |

Manual-review prompts:

- Do major transients align visually?
- Is there any apparent constant offset?
- Is there any timing drift across the 28-second excerpt?
- Does rapid switching reveal a perceptible timing jump?
- Is the issue alignment, or only a mix-production difference?
- Accept alignment?
- Reviewer comments.

## Lead Me - Similar Ratings

- Original mix names: DU-D | DU-E | QUT-F
- Automatic status: FAIL
- Maximum lag: 46.440 ms
- Minimum correlation: 0.460
- Stereo-imbalance QC flags: false|false|false
- Rapid-switch audio: review_audio/Lead Me/Similar Ratings/RapidSwitch.wav
- Individual review audio:
  - review_audio/Lead Me/Similar Ratings/DU-D_28sec.wav
  - review_audio/Lead Me/Similar Ratings/DU-E_28sec.wav
  - review_audio/Lead Me/Similar Ratings/QUT-F_28sec.wav
- Stacked waveform figure: figures/Lead Me/Similar Ratings/stacked_waveforms.png
- Zoomed strongest-transient figure: figures/Lead Me/Similar Ratings/strongest_transient_zoom.png

| Pair | Lag samples | Lag ms | Correlation | Result |
| --- | ---: | ---: | ---: | --- |
| DU-D-DU-E | -1024 | -23.220 | 0.460 | REVIEW |
| DU-D-QUT-F | 1024 | 23.220 | 0.543 | REVIEW |
| DU-E-QUT-F | 2048 | 46.440 | 0.599 | FAIL |

Manual-review prompts:

- Do major transients align visually?
- Is there any apparent constant offset?
- Is there any timing drift across the 28-second excerpt?
- Does rapid switching reveal a perceptible timing jump?
- Is the issue alignment, or only a mix-production difference?
- Accept alignment?
- Reviewer comments.

## Lead Me - Wide Ratings

- Original mix names: PXL-L1 | PXL-L4 | McG-pro2
- Automatic status: FAIL
- Maximum lag: 46.440 ms
- Minimum correlation: 0.492
- Stereo-imbalance QC flags: false|false|false
- Rapid-switch audio: review_audio/Lead Me/Wide Ratings/RapidSwitch.wav
- Individual review audio:
  - review_audio/Lead Me/Wide Ratings/PXL-L1_28sec.wav
  - review_audio/Lead Me/Wide Ratings/PXL-L4_28sec.wav
  - review_audio/Lead Me/Wide Ratings/McG-pro2_28sec.wav
- Stacked waveform figure: figures/Lead Me/Wide Ratings/stacked_waveforms.png
- Zoomed strongest-transient figure: figures/Lead Me/Wide Ratings/strongest_transient_zoom.png

| Pair | Lag samples | Lag ms | Correlation | Result |
| --- | ---: | ---: | ---: | --- |
| PXL-L1-PXL-L4 | -512 | -11.610 | 0.833 | REVIEW |
| PXL-L1-McG-pro2 | -2048 | -46.440 | 0.492 | FAIL |
| PXL-L4-McG-pro2 | -1536 | -34.830 | 0.600 | FAIL |

Manual-review prompts:

- Do major transients align visually?
- Is there any apparent constant offset?
- Is there any timing drift across the 28-second excerpt?
- Does rapid switching reveal a perceptible timing jump?
- Is the issue alignment, or only a mix-production difference?
- Accept alignment?
- Reviewer comments.

## Pouring Room - Similar Ratings

- Original mix names: McG-R | McG-T | McG-X
- Automatic status: REVIEW
- Maximum lag: 0.000 ms
- Minimum correlation: 0.364
- Stereo-imbalance QC flags: false|false|false
- Rapid-switch audio: review_audio/Pouring Room/Similar Ratings/RapidSwitch.wav
- Individual review audio:
  - review_audio/Pouring Room/Similar Ratings/McG-R_28sec.wav
  - review_audio/Pouring Room/Similar Ratings/McG-T_28sec.wav
  - review_audio/Pouring Room/Similar Ratings/McG-X_28sec.wav
- Stacked waveform figure: figures/Pouring Room/Similar Ratings/stacked_waveforms.png
- Zoomed strongest-transient figure: figures/Pouring Room/Similar Ratings/strongest_transient_zoom.png

| Pair | Lag samples | Lag ms | Correlation | Result |
| --- | ---: | ---: | ---: | --- |
| McG-R-McG-T | 0 | 0.000 | 0.364 | REVIEW |
| McG-R-McG-X | 0 | 0.000 | 0.389 | REVIEW |
| McG-T-McG-X | 0 | 0.000 | 0.765 | PASS |

Manual-review prompts:

- Do major transients align visually?
- Is there any apparent constant offset?
- Is there any timing drift across the 28-second excerpt?
- Does rapid switching reveal a perceptible timing jump?
- Is the issue alignment, or only a mix-production difference?
- Accept alignment?
- Reviewer comments.

## Pouring Room - Wide Ratings

- Original mix names: McG-pro1 | McG-U | McG-V
- Automatic status: FAIL
- Maximum lag: 58.050 ms
- Minimum correlation: 0.286
- Stereo-imbalance QC flags: false|false|false
- Rapid-switch audio: review_audio/Pouring Room/Wide Ratings/RapidSwitch.wav
- Individual review audio:
  - review_audio/Pouring Room/Wide Ratings/McG-pro1_28sec.wav
  - review_audio/Pouring Room/Wide Ratings/McG-U_28sec.wav
  - review_audio/Pouring Room/Wide Ratings/McG-V_28sec.wav
- Stacked waveform figure: figures/Pouring Room/Wide Ratings/stacked_waveforms.png
- Zoomed strongest-transient figure: figures/Pouring Room/Wide Ratings/strongest_transient_zoom.png

| Pair | Lag samples | Lag ms | Correlation | Result |
| --- | ---: | ---: | ---: | --- |
| McG-pro1-McG-U | 0 | 0.000 | 0.494 | REVIEW |
| McG-pro1-McG-V | 2560 | 58.050 | 0.670 | FAIL |
| McG-U-McG-V | 2560 | 58.050 | 0.286 | FAIL |

Manual-review prompts:

- Do major transients align visually?
- Is there any apparent constant offset?
- Is there any timing drift across the 28-second excerpt?
- Does rapid switching reveal a perceptible timing jump?
- Is the issue alignment, or only a mix-production difference?
- Accept alignment?
- Reviewer comments.

## Red To Blue - Similar Ratings

- Original mix names: McG-B | McG-G | McG-F
- Automatic status: REVIEW
- Maximum lag: 11.610 ms
- Minimum correlation: 0.575
- Stereo-imbalance QC flags: true|false|false
- Rapid-switch audio: review_audio/Red To Blue/Similar Ratings/RapidSwitch.wav
- Individual review audio:
  - review_audio/Red To Blue/Similar Ratings/McG-B_28sec.wav
  - review_audio/Red To Blue/Similar Ratings/McG-G_28sec.wav
  - review_audio/Red To Blue/Similar Ratings/McG-F_28sec.wav
- Stacked waveform figure: figures/Red To Blue/Similar Ratings/stacked_waveforms.png
- Zoomed strongest-transient figure: figures/Red To Blue/Similar Ratings/strongest_transient_zoom.png

| Pair | Lag samples | Lag ms | Correlation | Result |
| --- | ---: | ---: | ---: | --- |
| McG-B-McG-G | 512 | 11.610 | 0.575 | REVIEW |
| McG-B-McG-F | 0 | 0.000 | 0.685 | PASS |
| McG-G-McG-F | 0 | 0.000 | 0.621 | PASS |

Manual-review prompts:

- Do major transients align visually?
- Is there any apparent constant offset?
- Is there any timing drift across the 28-second excerpt?
- Does rapid switching reveal a perceptible timing jump?
- Is the issue alignment, or only a mix-production difference?
- Accept alignment?
- Reviewer comments.

## Red To Blue - Wide Ratings

- Original mix names: McG-C | McG-H | McG-pro1
- Automatic status: PASS
- Maximum lag: 0.000 ms
- Minimum correlation: 0.710
- Stereo-imbalance QC flags: false|false|false
- Rapid-switch audio: review_audio/Red To Blue/Wide Ratings/RapidSwitch.wav
- Individual review audio:
  - review_audio/Red To Blue/Wide Ratings/McG-C_28sec.wav
  - review_audio/Red To Blue/Wide Ratings/McG-H_28sec.wav
  - review_audio/Red To Blue/Wide Ratings/McG-pro1_28sec.wav
- Stacked waveform figure: figures/Red To Blue/Wide Ratings/stacked_waveforms.png
- Zoomed strongest-transient figure: figures/Red To Blue/Wide Ratings/strongest_transient_zoom.png

| Pair | Lag samples | Lag ms | Correlation | Result |
| --- | ---: | ---: | ---: | --- |
| McG-C-McG-H | 0 | 0.000 | 0.833 | PASS |
| McG-C-McG-pro1 | 0 | 0.000 | 0.710 | PASS |
| McG-H-McG-pro1 | 0 | 0.000 | 0.734 | PASS |

Manual-review prompts:

- Do major transients align visually?
- Is there any apparent constant offset?
- Is there any timing drift across the 28-second excerpt?
- Does rapid switching reveal a perceptible timing jump?
- Is the issue alignment, or only a mix-production difference?
- Accept alignment?
- Reviewer comments.

## Appendix

- Alignment thresholds used: PASS <=10 ms and correlation >=0.60; REVIEW <=30 ms and correlation >=0.35; otherwise FAIL
- Lag is the residual pairwise offset estimated from the onset/RMS-change envelope.
- Correlation is the peak normalized cross-correlation within the search window.
- Source CSVs: tables/pairwise_alignment_verification.csv, tables/alignment_summary.csv, tables/manual_alignment_review.csv, tables/review_audio_manifest.csv.
- Figure folders: figures/<song>/<condition>/stacked_waveforms.png and figures/<song>/<condition>/strongest_transient_zoom.png.
- Review-audio folders: review_audio/<song>/<condition>/.
- Review WAV hashes match Phase 2B source WAVs according to tables/review_audio_manifest.csv.
- Protected upstream outputs remained unchanged during booklet generation.
