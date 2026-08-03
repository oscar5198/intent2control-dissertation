# Stage 2 Excerpt Selection Report

Diagnostic previews are not final study stimuli and are not loudness normalised.

ffmpeg: unavailable
ffprobe: unavailable

## Decoding Provenance

- Decoder backend used for retained files: soundfile (73 files)
- soundfile version: 0.14.0
- linked libsndfile version: 1.2.2
- MP3 support available through soundfile/libsndfile: true
- Full waveform decode via `sf.read` verified for retained files: true (73/73)
- Decoded frame-derived durations consistent with updated `alignment_results.csv`: true
- `soundfile.info()` frame count exactly matches decoded frames: false (53/73); 20 48 kHz MP3 files have info/read deltas up to 4240 frames, so decoded waveform frame counts are recorded as authoritative for Stage 2 duration provenance.
- Detailed table: decoding_verification_report.csv
- Manual review mapping: manual_review_candidate_summary.csv and manual_review_candidate_summary.md

## Fredy V - In The Meantime
Reference mix: QUT-A (internal ID: mix_13f0eed08780)
Retained/excluded: 36/0
Common overlap: 73.488050 seconds
Confidence: min=0.748; median=0.870; max=1.000

Top candidate windows:
- Rank 1: 34.800431 to 62.800431 s, score 0.647475
- Rank 2: 42.800431 to 70.800431 s, score 0.535204
- Rank 3: 29.050431 to 57.050431 s, score 0.505191
- Rank 4: 15.300431 to 43.300431 s, score 0.382321
- Rank 5: 21.050431 to 49.050431 s, score 0.217878

## The DoneFors - Lead Me
Reference mix: DU-E (internal ID: mix_271852ba8676)
Retained/excluded: 37/1
Common overlap: 79.852480 seconds
Confidence: min=0.717; median=0.856; max=1.000

Top candidate windows:
- Rank 1: 12.573107 to 40.573107 s, score 1.448275
- Rank 2: 6.823107 to 34.823107 s, score 1.331904
- Rank 3: 18.323107 to 46.323107 s, score 1.176352
- Rank 4: 24.073107 to 52.073107 s, score 0.748757
- Rank 5: 30.073107 to 58.073107 s, score 0.588661
## Final Automatic Decisions

Selections were made by source-aware rescoring of the five Stage 2 candidates plus +/-3 second boundary refinements. Source-track mapping details are recorded in `source_track_mapping.csv`. No mix triplets were selected and no loudness normalisation or Diff-MST feature extraction was run.

- The DoneFors - Lead Me: approved 9.573107 to 37.573107 s from candidate 1 (shift -3.000 s), final score 0.989, confidence 0.907.
- Fredy V - In The Meantime: approved 35.300431 to 63.300431 s from candidate 1 (shift +0.500 s), final score 0.972, confidence 0.853.

## Consolidated Four-Song Stage 2 Approval

Final approved excerpt decisions now contain exactly four songs. Lead Me and In The Meantime were preserved exactly; Red To Blue and Pouring Room were aligned, scored and automatically approved in the remaining Stage 2 pass.

- The DoneFors - Lead Me: 9.573107 to 37.573107 s, score 0.989286, confidence 0.907197.
- Fredy V - In The Meantime: 35.300431 to 63.300431 s, score 0.972500, confidence 0.853055.
- Broken Crank - Red To Blue: 3.005442 to 31.005442 s, score 0.911071, confidence 0.829669.
- The DoneFors - Pouring Room: 23.020408 to 51.020408 s, score 0.685714, confidence 0.739246.

Approved diagnostic previews are consolidated in `approved_excerpt_previews/` with manifest `approved_excerpt_preview_manifest.csv`.
