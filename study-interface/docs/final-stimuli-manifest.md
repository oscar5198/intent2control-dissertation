# Final Stimuli Manifest

This researcher-facing manifest documents the experimental audio files integrated into the study interface on 2026-08-03.

Participant-facing pages must not display artist names, song titles, source filenames, original mix names, analytical roles, candidate-category names, or internal mix identifiers. Participants should see only:

- `Music excerpt: Song A` or `Music excerpt: Song B`
- `Version A`, `Version B`, and `Version C`
- The contextual listening scenario text

## Stimulus Configuration Version

- Current frontend stimulus configuration version: `rating_stratification_v2_2026-08-03`
- Target integrated loudness: `-20.8 LUFS`
- Frontend filenames are researcher-readable inside the controlled consolidated audio folder, but do not encode participant-facing Version A/B/C labels.
- Source candidate audio remains unchanged under `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/`.

## Source Materials

Revised Main Study stimuli were selected from the rating-stratified supervisor-review outputs:

- `outputs/stimulus_selection/06_rating_stratification/tables/supervisor_shortlist.csv`
- `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/`
- `outputs/stimulus_selection/05_alignment_verification/tables/alignment_summary.csv`
- `outputs/stimulus_selection/05_alignment_verification/tables/pairwise_alignment_verification.csv`

Participant-group allocation is unchanged from the existing frontend configuration.

## Group Mapping

| Frontend group | Participant excerpt | Artist | Researcher-facing song | Chosen category | Rejected category |
| --- | --- | --- | --- | --- | --- |
| `group_01` | Song A | The DoneFors | Lead Me | Wide Ratings | Similar Ratings |
| `group_01` | Song B | Broken Crank | Red To Blue | Wide Ratings | Similar Ratings |
| `group_02` | Song A | Fredy V | In The Meantime | Wide Ratings | Similar Ratings |
| `group_02` | Song B | The DoneFors | Pouring Room | Similar Ratings | Wide Ratings |

## Candidate Sets Reviewed

| Song | Similar Ratings candidate set | Wide Ratings candidate set | Final choice | Evidence-based rationale |
| --- | --- | --- | --- | --- |
| Lead Me | `DU-D|DU-E|QUT-F`; spread 0.0564; QC clear|clear|clear | `PXL-L1|PXL-L4|McG-pro2`; spread 0.2156; QC clear|clear|clear | Wide Ratings | Selected over Similar Ratings because it keeps QC-clear mixes while providing broader prior-rating strata (low/medium/high; spread 0.2156). The Similar set is QC-clear but has very narrow prior-rating spread (0.0564; all low), making it less informative for contextual preference ratings. Both Lead Me sets carry alignment review flags, so the category choice follows the stronger rating-stratification evidence while documenting the residual alignment-review note. |
| Red To Blue | `McG-B|McG-G|McG-F`; spread 0.2073; QC review|clear|clear | `McG-C|McG-H|McG-pro1`; spread 0.2284; QC clear|clear|clear | Wide Ratings | Selected over Similar Ratings because it is QC-clear, has a PASS alignment summary with 0 ms maximum offset, and gives slightly broader low/medium/high rating separation (spread 0.2284). The Similar set has a QC review flag on one mix. |
| In The Meantime | `QUT-B|DU-H|DU-I`; spread 0.3908; QC clear|clear|clear | `DU-K|QUT-pro|DU-N`; spread 0.4483; QC clear|clear|clear | Wide Ratings | Selected over Similar Ratings because it has QC-clear mixes, a suitable-for-supervisor-review alignment recommendation, and the broader prior-rating spread (0.4483 versus 0.3908). The Similar set has an automatic alignment fail in the alignment summary. |
| Pouring Room | `McG-R|McG-T|McG-X`; spread 0.0756; QC clear|clear|clear | `McG-pro1|McG-U|McG-V`; spread 0.2821; QC clear|clear|clear | Similar Ratings | Selected over Wide Ratings because the Wide set has documented alignment failures up to about 58 ms. The Similar set has 0 ms maximum offset in the alignment summary and is marked suitable for supervisor review, despite its narrower prior-rating spread. |

## Integrated Main Study Stimulus Files

| Group | Participant excerpt | Artist | Song | Slot | Source mix | Internal mix ID | Source WAV | Frontend WAV | Source LUFS | Final LUFS | True peak dBTP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: |
| `group_01` | Song A | The DoneFors | Lead Me | `mix_01` | PXL-L1 | `mix_d5b28dfc8a93` | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/Lead Me/Wide Ratings/PXL-L1_28sec.wav` | `assets/audio/study-stimuli/main-study/group_01/song_a_lead_me/pxl_l1.wav` | -22.187 | -20.800 | -6.018 |
| `group_01` | Song A | The DoneFors | Lead Me | `mix_02` | PXL-L4 | `mix_c7d9a071ba25` | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/Lead Me/Wide Ratings/PXL-L4_28sec.wav` | `assets/audio/study-stimuli/main-study/group_01/song_a_lead_me/pxl_l4.wav` | -22.264 | -20.800 | -7.024 |
| `group_01` | Song A | The DoneFors | Lead Me | `mix_03` | McG-pro2 | `mix_d3e3580b6e30` | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/Lead Me/Wide Ratings/McG-pro2_28sec.wav` | `assets/audio/study-stimuli/main-study/group_01/song_a_lead_me/mcg_pro2.wav` | -21.239 | -20.800 | -1.802 |
| `group_01` | Song B | Broken Crank | Red To Blue | `mix_01` | McG-C | `mix_5143d2ee3859` | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/Red To Blue/Wide Ratings/McG-C_28sec.wav` | `assets/audio/study-stimuli/main-study/group_01/song_b_red_to_blue/mcg_c.wav` | -23.576 | -20.800 | -6.353 |
| `group_01` | Song B | Broken Crank | Red To Blue | `mix_02` | McG-H | `mix_5b76bf1a027d` | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/Red To Blue/Wide Ratings/McG-H_28sec.wav` | `assets/audio/study-stimuli/main-study/group_01/song_b_red_to_blue/mcg_h.wav` | -23.392 | -20.800 | -8.792 |
| `group_01` | Song B | Broken Crank | Red To Blue | `mix_03` | McG-pro1 | `mix_808780e357c9` | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/Red To Blue/Wide Ratings/McG-pro1_28sec.wav` | `assets/audio/study-stimuli/main-study/group_01/song_b_red_to_blue/mcg_pro1.wav` | -24.954 | -20.800 | -6.483 |
| `group_02` | Song A | Fredy V | In The Meantime | `mix_01` | DU-K | `mix_56e65a3ce054` | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/In The Meantime/Wide Ratings/DU-K_28sec.wav` | `assets/audio/study-stimuli/main-study/group_02/song_a_in_the_meantime/du_k.wav` | -23.260 | -20.800 | -1.111 |
| `group_02` | Song A | Fredy V | In The Meantime | `mix_02` | QUT-pro | `mix_cdaef40f2b94` | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/In The Meantime/Wide Ratings/QUT-pro_28sec.wav` | `assets/audio/study-stimuli/main-study/group_02/song_a_in_the_meantime/qut_pro.wav` | -22.619 | -20.800 | -8.942 |
| `group_02` | Song A | Fredy V | In The Meantime | `mix_03` | DU-N | `mix_29131e66c9d7` | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/In The Meantime/Wide Ratings/DU-N_28sec.wav` | `assets/audio/study-stimuli/main-study/group_02/song_a_in_the_meantime/du_n.wav` | -22.785 | -20.800 | -6.185 |
| `group_02` | Song B | The DoneFors | Pouring Room | `mix_01` | McG-R | `mix_0ba76f420c1d` | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/Pouring Room/Similar Ratings/McG-R_28sec.wav` | `assets/audio/study-stimuli/main-study/group_02/song_b_pouring_room/mcg_r.wav` | -21.962 | -20.800 | -5.837 |
| `group_02` | Song B | The DoneFors | Pouring Room | `mix_02` | McG-T | `mix_be2ccd4c43ff` | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/Pouring Room/Similar Ratings/McG-T_28sec.wav` | `assets/audio/study-stimuli/main-study/group_02/song_b_pouring_room/mcg_t.wav` | -21.978 | -20.800 | -2.439 |
| `group_02` | Song B | The DoneFors | Pouring Room | `mix_03` | McG-X | `mix_cbf8555ee2b2` | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/Pouring Room/Similar Ratings/McG-X_28sec.wav` | `assets/audio/study-stimuli/main-study/group_02/song_b_pouring_room/mcg_x.wav` | -21.739 | -20.800 | -3.257 |

## Excerpt Timing

| Song | Approved excerpt start | Approved excerpt end | Duration |
| --- | ---: | ---: | ---: |
| Lead Me | 9.573107 s | 37.573107 s | 28.000 s |
| Red To Blue | 3.005442 s | 31.005442 s | 28.000 s |
| In The Meantime | 35.300431 s | 63.300431 s | 28.000 s |
| Pouring Room | 23.020408 s | 51.020408 s | 28.000 s |

## Technical Validation

All 12 frontend WAV files were decoded after integration and checked with Python `soundfile`, `pyloudnorm`, NumPy, and 4x oversampled true-peak estimation.

| Check | Result |
| --- | --- |
| File count | 12 WAV files |
| Duration | 28.000 seconds each |
| Sample rate | 44,100 Hz |
| Channels | Stereo |
| Bit depth | 16-bit PCM frontend copies, matching the revised candidate-review WAV subtype |
| Integrated loudness | -20.800 LUFS for all frontend copies |
| True peak | Safe after integration; highest measured frontend value was -1.111 dBTP |
| Non-silent audio | Passed; all selected files contain valid non-silent stereo audio |
| Duplicate-file check | Passed; all selected source SHA-256 hashes are distinct within song sets |

## Normalisation

The candidate-review WAV files were not already at -20.8 LUFS. The frontend copies were therefore loudness-normalised to -20.8 LUFS. Source files under `outputs/` were not modified.

| Song | Slot | Mix | Source LUFS | Gain target | Normalisation method | Final LUFS | Final true peak dBTP |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: |
| Lead Me | `mix_01` | PXL-L1 | -22.187 | 1.387 dB | integrated_loudness_gain_only | -20.800 | -6.018 |
| Lead Me | `mix_02` | PXL-L4 | -22.264 | 1.464 dB | integrated_loudness_gain_only | -20.800 | -7.024 |
| Lead Me | `mix_03` | McG-pro2 | -21.239 | 0.439 dB | integrated_loudness_gain_only | -20.800 | -1.802 |
| Red To Blue | `mix_01` | McG-C | -23.576 | 2.776 dB | integrated_loudness_gain_only | -20.800 | -6.353 |
| Red To Blue | `mix_02` | McG-H | -23.392 | 2.592 dB | integrated_loudness_gain_only | -20.800 | -8.792 |
| Red To Blue | `mix_03` | McG-pro1 | -24.954 | 4.154 dB | integrated_loudness_gain_only | -20.800 | -6.483 |
| In The Meantime | `mix_01` | DU-K | -23.260 | 2.460 dB | integrated_loudness_gain_plus_minimal_soft_peak_safety | -20.800 | -1.111 |
| In The Meantime | `mix_02` | QUT-pro | -22.619 | 1.819 dB | integrated_loudness_gain_only | -20.800 | -8.942 |
| In The Meantime | `mix_03` | DU-N | -22.785 | 1.985 dB | integrated_loudness_gain_only | -20.800 | -6.185 |
| Pouring Room | `mix_01` | McG-R | -21.962 | 1.162 dB | integrated_loudness_gain_only | -20.800 | -5.837 |
| Pouring Room | `mix_02` | McG-T | -21.978 | 1.178 dB | integrated_loudness_gain_only | -20.800 | -2.439 |
| Pouring Room | `mix_03` | McG-X | -21.739 | 0.939 dB | integrated_loudness_gain_only | -20.800 | -3.257 |

Only `In The Meantime / DU-K` required the peak-safety path because direct LUFS gain would have exceeded full scale. The frontend copy uses minimal soft peak-safety during loudness normalisation; all other selected files use integrated loudness gain only.

## Alignment Evidence

Alignment values below come from the existing Stage 5 alignment-verification tables.

| Song | Category | Maximum offset | Minimum correlation | Automatic result | Overall recommendation |
| --- | --- | ---: | ---: | --- | --- |
| Lead Me | Wide Ratings | 46.440 ms | 0.492 | FAIL | requires_alignment_review_before_supervisor_review |
| Red To Blue | Wide Ratings | 0.000 ms | 0.710 | PASS | suitable_for_supervisor_review |
| In The Meantime | Wide Ratings | 23.220 ms | 0.682 | REVIEW | suitable_for_supervisor_review |
| Pouring Room | Similar Ratings | 0.000 ms | 0.364 | REVIEW | suitable_for_supervisor_review |

| Song | Pair | Offset | Correlation | Quality |
| --- | --- | ---: | ---: | --- |
| Lead Me | PXL-L1-PXL-L4 | -11.610 ms | 0.833 | REVIEW |
| Lead Me | PXL-L1-McG-pro2 | -46.440 ms | 0.492 | FAIL |
| Lead Me | PXL-L4-McG-pro2 | -34.830 ms | 0.600 | FAIL |
| Red To Blue | McG-C-McG-H | 0.000 ms | 0.833 | PASS |
| Red To Blue | McG-C-McG-pro1 | 0.000 ms | 0.710 | PASS |
| Red To Blue | McG-H-McG-pro1 | 0.000 ms | 0.734 | PASS |
| In The Meantime | DU-K-QUT-pro | 0.000 ms | 0.704 | PASS |
| In The Meantime | DU-K-DU-N | 23.220 ms | 0.682 | REVIEW |
| In The Meantime | QUT-pro-DU-N | 23.220 ms | 0.719 | REVIEW |
| Pouring Room | McG-R-McG-T | 0.000 ms | 0.364 | REVIEW |
| Pouring Room | McG-R-McG-X | 0.000 ms | 0.389 | REVIEW |
| Pouring Room | McG-T-McG-X | 0.000 ms | 0.765 | PASS |

Lead Me remains marked for alignment review in both candidate categories. It is integrated here because the Wide Ratings set is the stronger rating-stratified set and the task requested integration of the revised outputs; this residual review note is retained for researcher awareness. Pouring Room uses Similar Ratings specifically because its Wide Ratings set had larger documented alignment failures.

## Runtime Randomisation Requirements

The active Main Study stimulus files are consolidated under `frontend/assets/audio/study-stimuli/main-study/` and fixed in `frontend/config/stimuli.json`, but participant presentation remains randomised:

- A participant is assigned one group.
- Scenario order is randomised once and persisted.
- The two assigned song tasks within each scenario remain adjacent.
- Song A/Song B order may be randomised within each scenario pair.
- Version A/B/C mapping is randomised independently for each listening task and persisted.
- The analysis payload stores neutral display labels separately from internal mix identifiers.
- Stored trial orders now include `stimulusConfigurationVersion` so stale local mappings are not silently reused after stimulus updates.

## Licensing and Usage Notes

This manifest documents frontend integration only. Any remaining licensing or permission checks for the Mix Evaluation Dataset materials should be confirmed through the study permissions workflow before public deployment.

## Remaining Non-Stimulus Dependencies

The Main Study stimulus files are integrated for supervisor review and pilot preparation. This does not mean the full study is deployed or production-ready. The following remain outside this manifest:

- Final server-side balanced group assignment.
- Production backend submission and secure storage.
- Final setup-test audio.
- Final pre-study listening-task stimuli, pass threshold, and failure/exclusion policy.
- Final hosting and deployment confirmation.
