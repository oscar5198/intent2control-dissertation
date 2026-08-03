# Stage 4 Manual Review Instructions

This review is a final technical sanity check of the twelve Stage 4 analytical mix selections. It is not a quality-ranking exercise and it must not assign participant-facing Version A/B/C labels.

Use the WAV files in `outputs/stimulus_selection/selected_mix_review_previews/` together with `outputs/stimulus_selection/stage4_manual_review.csv`.

For each row, listen to the 28-second preview and complete the blank review fields:

- `alignment_valid`: mark true only if the excerpt begins and ends at the intended musical region and is aligned with the other selected versions of the same song.
- `no_audio_corruption`: mark true only if there are no decoder artifacts, dropouts, unexpected truncations, severe clicks, or file/render failures.
- `no_missing_content`: mark true only if the excerpt contains meaningful musical content throughout and no accidental silence or wrong section.
- `no_pathological_stereo_issue`: mark true only if there is no obvious technical stereo fault such as collapsed/empty channel, severe unintended channel imbalance, polarity-like cancellation, or broken side content.
- `not_near_duplicate_by_listening`: mark true only if the selected mix is meaningfully distinguishable from the other two selected mixes for the same song.
- `technically_acceptable`: mark true only when all technical checks pass.
- `reviewer`, `review_notes`: record who reviewed it and any concise reason for concern or approval.

Unusual production choices are acceptable. A mix should only be rejected for technical invalidity, accidental corruption, failed alignment, or lack of meaningful distinction from another selected version. Do not reject a mix merely because it is loud, quiet, bright, dark, wide, dry, reverberant, sparse, dense, or aesthetically unconventional.

Rows with `flagged_for_review=true` were flagged by Stage 4 diagnostics as higher-outlier-risk selections and should receive extra attention, but the flag is not a rejection. Preserve the selected triplets unless the manual review identifies a real technical problem.

Approval mechanism:

1. Complete every blank review field in `stage4_manual_review.csv`.
2. If all twelve rows are technically acceptable, update `configs/stimulus_selection.yaml`:
   - set `stage4_review.status` to `approved`;
   - set `stage4_review.reviewer`;
   - set `stage4_review.reviewed_at` using an ISO-like date/time;
   - add any concise notes.
3. If any row is not technically acceptable, keep `stage4_review.status` as `pending` or set it to `rejected`, and document the issue in `review_notes` before changing any selection.

Stage 5 must not begin until `stage4_review.status` is `approved`.
