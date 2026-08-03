# Alignment Verification Report

Phase 2C verifies the Phase 2B recommended mixes using automatic pairwise alignment checks, stacked waveform figures, transient zoom figures, and rapid-switch listening files.

Automatic procedure: each 28-second stereo review WAV is reduced to a mono onset/RMS-change envelope. Pairwise normalized cross-correlation is searched within +/-100 ms. PASS is <=10 ms and correlation >=0.60; REVIEW is <=30 ms and correlation >=0.35; otherwise FAIL.

Visual inspection: `figures/` contains one stacked waveform and one strongest-transient zoom per triplet.

Perceptual inspection: `review_audio/` contains the original copied WAVs plus `RapidSwitch.wav` for each triplet. Rapid-switch files alternate 2-second segments with 5 ms crossfades and no loudness normalization.

## Triplet Summary

| Song | Condition | Maximum offset ms | Minimum correlation | Automatic result | Overall recommendation |
| --- | --- | ---: | ---: | --- | --- |
| In The Meantime | Similar Ratings | 34.830 | 0.555 | FAIL | requires_alignment_review_before_supervisor_review |
| In The Meantime | Wide Ratings | 23.220 | 0.682 | REVIEW | suitable_for_supervisor_review |
| Lead Me | Similar Ratings | 46.440 | 0.460 | FAIL | requires_alignment_review_before_supervisor_review |
| Lead Me | Wide Ratings | 46.440 | 0.492 | FAIL | requires_alignment_review_before_supervisor_review |
| Pouring Room | Similar Ratings | 0.000 | 0.364 | REVIEW | suitable_for_supervisor_review |
| Pouring Room | Wide Ratings | 58.050 | 0.286 | FAIL | requires_alignment_review_before_supervisor_review |
| Red To Blue | Similar Ratings | 11.610 | 0.575 | REVIEW | suitable_for_supervisor_review |
| Red To Blue | Wide Ratings | 0.000 | 0.710 | PASS | suitable_for_supervisor_review |

## Triplets Requiring Review

- In The Meantime / Similar Ratings: FAIL, max offset 34.830 ms.
- In The Meantime / Wide Ratings: REVIEW, max offset 23.220 ms.
- Lead Me / Similar Ratings: FAIL, max offset 46.440 ms.
- Lead Me / Wide Ratings: FAIL, max offset 46.440 ms.
- Pouring Room / Similar Ratings: REVIEW, max offset 0.000 ms.
- Pouring Room / Wide Ratings: FAIL, max offset 58.050 ms.
- Red To Blue / Similar Ratings: REVIEW, max offset 11.610 ms.

## Dissertation Statement

Alignment of the recommended stimuli was checked automatically by pairwise envelope cross-correlation, visually through stacked waveform and transient plots, and perceptually through rapid-switch listening files. Final acceptance remains subject to supervisor/manual review.
