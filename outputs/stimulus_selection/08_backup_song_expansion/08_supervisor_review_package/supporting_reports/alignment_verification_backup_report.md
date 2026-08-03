# Alignment Verification Report

Phase 2C verifies the Phase 2B recommended mixes using automatic pairwise alignment checks, stacked waveform figures, transient zoom figures, and rapid-switch listening files.

Automatic procedure: each 28-second stereo review WAV is reduced to a mono onset/RMS-change envelope. Pairwise normalized cross-correlation is searched within +/-100 ms. PASS is <=10 ms and correlation >=0.60; REVIEW is <=30 ms and correlation >=0.35; otherwise FAIL.

Visual inspection: `figures/` contains one stacked waveform and one strongest-transient zoom per triplet.

Perceptual inspection: `review_audio/` contains the original copied WAVs plus `RapidSwitch.wav` for each triplet. Rapid-switch files alternate 2-second segments with 5 ms crossfades and no loudness normalization.

## Triplet Summary

| Song | Condition | Maximum offset ms | Minimum correlation | Automatic result | Overall recommendation |
| --- | --- | ---: | ---: | --- | --- |
| I'd Like To Know | Similar Ratings | 0.000 | 0.629 | PASS | suitable_for_supervisor_review |
| I'd Like To Know | Wide Ratings | 0.000 | 0.697 | PASS | suitable_for_supervisor_review |
| New Skin | Similar Ratings | 0.000 | 0.691 | PASS | suitable_for_supervisor_review |
| New Skin | Wide Ratings | 11.610 | 0.793 | REVIEW | suitable_for_supervisor_review |
| No Prize | Similar Ratings | 11.610 | 0.553 | REVIEW | suitable_for_supervisor_review |
| No Prize | Wide Ratings | 0.000 | 0.506 | REVIEW | suitable_for_supervisor_review |
| Vermont | Similar Ratings | 11.610 | 0.672 | REVIEW | suitable_for_supervisor_review |
| Vermont | Wide Ratings | 0.000 | 0.741 | PASS | suitable_for_supervisor_review |

## Triplets Requiring Review

- New Skin / Wide Ratings: REVIEW, max offset 11.610 ms.
- No Prize / Similar Ratings: REVIEW, max offset 11.610 ms.
- No Prize / Wide Ratings: REVIEW, max offset 0.000 ms.
- Vermont / Similar Ratings: REVIEW, max offset 11.610 ms.

## Dissertation Statement

Alignment of the recommended stimuli was checked automatically by pairwise envelope cross-correlation, visually through stacked waveform and transient plots, and perceptually through rapid-switch listening files. Final acceptance remains subject to supervisor/manual review.
