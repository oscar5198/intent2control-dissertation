# Six-Mix Prototype Final QA Report

Generated: 2026-08-05

## Purpose

This report documents final QA for the separate six-mix prototype in `study-interface/frontend-6mix/`. The approved current three-mix frontend in `study-interface/frontend/` remains the source of truth for study flow, questionnaires, randomisation pattern, validation, audio interaction, styling, and storage behavior. The only intended conceptual change in this prototype is that Main Study trials present six mix versions instead of three.

## Active Study Structure

- Main Study scenarios: 3
- Songs per participant: 2
- Main Study listening trials per participant: 6
- Versions per Main Study listening trial: 6, labelled Version A through Version F
- Ratings per participant: 36
- Shared required comments per participant: 6
- Practice trial: now uses 6 versions, labelled Version A through Version F
- Six-mix configuration version: `six_mix_frontend_prototype_v1_2026-08-05`
- Six-mix localStorage namespace: `intent2control.study.6mix.dev.`
- Original three-mix localStorage namespace: `intent2control.study.dev.`

## Active Frontend Audio Root

The participant browser loads Main Study audio from frontend-ready files under:

`study-interface/frontend-6mix/assets/audio/study-stimuli/main-study/`

Absolute root:

`C:\Users\oscar\Documents\7. QMUL UNIVERSITY\1. Master Program\3. MSc Project\intent2control-dissertation\study-interface\frontend-6mix\assets\audio\study-stimuli\main-study`

Runtime path construction is in `study-interface/frontend-6mix/js/trial.js`: the configured `audioPath` is converted to `../assets/audio/study-stimuli/main-study/...` and served with the stimulus configuration cache-buster query string. The participant browser does not load audio directly from `outputs/stimulus_selection/`.

The intended architecture is therefore:

`outputs/.../review_audio` and approved overlap assets -> copied frontend-ready WAVs -> loaded by `frontend-6mix`.

## Authoritative Review-Audio Folder

The six-mix proposal review folder was inspected recursively:

`C:\Users\oscar\Documents\7. QMUL UNIVERSITY\1. Master Program\3. MSc Project\intent2control-dissertation\outputs\stimulus_selection\09_six_mix_proposals\review_audio`

It contains exactly the expected six-mix sets:

- Lead Me: DU-D, DU-E, McG-pro2, PXL-L1, PXL-L4, QUT-F
- Red To Blue: McG-B, McG-C, McG-F, McG-G, McG-H, McG-pro1
- In The Meantime: DU-H, DU-I, DU-K, DU-N, QUT-B, QUT-pro
- Pouring Room: McG-pro1, McG-R, McG-T, McG-U, McG-V, McG-X

## Active Six-Mix Frontend Set

The active config contains these 24 paths and no duplicates within a song:

- Lead Me: `du_d.wav`, `du_e.wav`, `qut_f.wav`, `pxl_l1.wav`, `pxl_l4.wav`, `mcg_pro2.wav`
- Red To Blue: `mcg_b.wav`, `mcg_g.wav`, `mcg_f.wav`, `mcg_c.wav`, `mcg_h.wav`, `mcg_pro1.wav`
- In The Meantime: `qut_b.wav`, `du_h.wav`, `du_i.wav`, `du_k.wav`, `qut_pro.wav`, `du_n.wav`
- Pouring Room: `mcg_r.wav`, `mcg_t.wav`, `mcg_x.wav`, `mcg_pro1.wav`, `mcg_u.wav`, `mcg_v.wav`

## Source Split

Not all 24 active frontend files are byte-identical direct copies from `09_six_mix_proposals/review_audio`.

The active prototype uses the documented mixed provenance:

- 12 files are direct copies from `outputs/stimulus_selection/09_six_mix_proposals/review_audio`.
- 12 files are approved current three-mix frontend overlap assets, retained from the approved corrected-fade frontend set.

Direct six-mix review-audio copies:

- Lead Me: DU-D, DU-E, QUT-F
- Red To Blue: McG-B, McG-G, McG-F
- In The Meantime: QUT-B, DU-H, DU-I
- Pouring Room: McG-pro1, McG-U, McG-V

Approved current-frontend overlap assets:

- Lead Me: PXL-L1, PXL-L4, McG-pro2
- Red To Blue: McG-C, McG-H, McG-pro1
- In The Meantime: DU-K, QUT-pro, DU-N
- Pouring Room: McG-R, McG-T, McG-X

This split is already recorded in `study-interface/frontend-6mix/config/stimuli.json` and `study-interface/frontend-6mix/docs/six-mix-audio-verification.json`.

## Source, Frontend, and Served Hashes

HTTP serving was checked from `http://127.0.0.1:8064/`. All 24 served files were byte-identical to the active frontend copies.

Summary:

- Source review/overlap file == active frontend copy: 12 of 24
- Source review/overlap file differs from active frontend copy: 12 of 24, all approved three-mix overlap assets
- Active frontend copy == HTTP-served browser file: 24 of 24
- Full hash details are available in `study-interface/frontend-6mix/docs/six-mix-audio-verification.json`.

| Song | Mix ID | Source class | Source subfolder | Source file | Size | Modified | Source SHA | Frontend SHA | Src=Front | Dur | SR | Ch | LUFS | TP |
|---|---:|---|---|---|---:|---|---|---|---|---:|---:|---:|---:|---:|
| Lead Me | DU-D | six_mix_review_audio | `outputs/stimulus_selection/09_six_mix_proposals/review_audio/Lead Me` | `DU-D_28sec.wav` | 7408844 | 2026-08-05T02:11:59 | `c9f29238b0df` | `c9f29238b0df` | true | 28.000 | 44100 | 2 | -20.800021 | -6.221 |
| Lead Me | DU-E | six_mix_review_audio | `outputs/stimulus_selection/09_six_mix_proposals/review_audio/Lead Me` | `DU-E_28sec.wav` | 7408844 | 2026-08-05T02:12:00 | `0d4f37676553` | `0d4f37676553` | true | 28.000 | 44100 | 2 | -20.800029 | -5.002 |
| Lead Me | QUT-F | six_mix_review_audio | `outputs/stimulus_selection/09_six_mix_proposals/review_audio/Lead Me` | `QUT-F_28sec.wav` | 7408844 | 2026-08-05T02:12:00 | `18dc5f3c4bd2` | `18dc5f3c4bd2` | true | 28.000 | 44100 | 2 | -20.800090 | -6.839 |
| Lead Me | PXL-L1 | approved_three_mix_frontend_overlap | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/Lead Me/Wide Ratings` | `PXL-L1_28sec.wav` | 4939244 | 2026-08-04T01:53:46 | `714422df665a` | `36d9394d0373` | false | 28.000 | 44100 | 2 | -20.800000 | -6.189 |
| Lead Me | PXL-L4 | approved_three_mix_frontend_overlap | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/Lead Me/Wide Ratings` | `PXL-L4_28sec.wav` | 4939244 | 2026-08-04T01:53:48 | `4dcc5347b88e` | `f257def94cc6` | false | 28.000 | 44100 | 2 | -20.800000 | -7.199 |
| Lead Me | McG-pro2 | approved_three_mix_frontend_overlap | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/Lead Me/Wide Ratings` | `McG-pro2_28sec.wav` | 4939244 | 2026-08-04T01:53:55 | `0a5f9954acf7` | `82ead88ddd05` | false | 28.000 | 44100 | 2 | -20.800000 | -1.965 |
| Red To Blue | McG-B | six_mix_review_audio | `outputs/stimulus_selection/09_six_mix_proposals/review_audio/Red To Blue` | `McG-B_28sec.wav` | 7408844 | 2026-08-05T02:12:06 | `3f31d4d7195e` | `3f31d4d7195e` | true | 28.000 | 44100 | 2 | -20.800025 | -5.356 |
| Red To Blue | McG-G | six_mix_review_audio | `outputs/stimulus_selection/09_six_mix_proposals/review_audio/Red To Blue` | `McG-G_28sec.wav` | 7408844 | 2026-08-05T02:12:07 | `b8e447bfef77` | `b8e447bfef77` | true | 28.000 | 44100 | 2 | -20.800034 | -7.348 |
| Red To Blue | McG-F | six_mix_review_audio | `outputs/stimulus_selection/09_six_mix_proposals/review_audio/Red To Blue` | `McG-F_28sec.wav` | 7408844 | 2026-08-05T02:12:08 | `f6c05d2bf581` | `f6c05d2bf581` | true | 28.000 | 44100 | 2 | -20.800036 | -8.897 |
| Red To Blue | McG-C | approved_three_mix_frontend_overlap | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/Red To Blue/Wide Ratings` | `McG-C_28sec.wav` | 4939244 | 2026-08-04T01:53:31 | `853fa7ff05ce` | `728b38e0e7b0` | false | 28.000 | 44100 | 2 | -20.800000 | -6.469 |
| Red To Blue | McG-H | approved_three_mix_frontend_overlap | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/Red To Blue/Wide Ratings` | `McG-H_28sec.wav` | 4939244 | 2026-08-04T01:53:31 | `d7c85ff4cfcd` | `76d98aac014d` | false | 28.000 | 44100 | 2 | -20.800000 | -8.913 |
| Red To Blue | McG-pro1 | approved_three_mix_frontend_overlap | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/Red To Blue/Wide Ratings` | `McG-pro1_28sec.wav` | 4939244 | 2026-08-04T01:53:32 | `09d9638198b6` | `6714bfad9f0e` | false | 28.000 | 44100 | 2 | -20.800000 | -6.590 |
| In The Meantime | QUT-B | six_mix_review_audio | `outputs/stimulus_selection/09_six_mix_proposals/review_audio/In The Meantime` | `QUT-B_28sec.wav` | 7408844 | 2026-08-05T02:12:02 | `612d10598906` | `612d10598906` | true | 28.000 | 44100 | 2 | -20.800002 | -6.371 |
| In The Meantime | DU-H | six_mix_review_audio | `outputs/stimulus_selection/09_six_mix_proposals/review_audio/In The Meantime` | `DU-H_28sec.wav` | 7408844 | 2026-08-05T02:12:03 | `1f313be3c726` | `1f313be3c726` | true | 28.000 | 44100 | 2 | -20.800003 | -3.238 |
| In The Meantime | DU-I | six_mix_review_audio | `outputs/stimulus_selection/09_six_mix_proposals/review_audio/In The Meantime` | `DU-I_28sec.wav` | 7408844 | 2026-08-05T02:12:03 | `37cbf18b0bc2` | `37cbf18b0bc2` | true | 28.000 | 44100 | 2 | -20.800018 | -0.907 |
| In The Meantime | DU-K | approved_three_mix_frontend_overlap | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/In The Meantime/Wide Ratings` | `DU-K_28sec.wav` | 4939244 | 2026-08-04T01:53:37 | `faacc5ae6167` | `4dfaf9d47d7f` | false | 28.000 | 44100 | 2 | -20.800000 | -1.468 |
| In The Meantime | QUT-pro | approved_three_mix_frontend_overlap | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/In The Meantime/Wide Ratings` | `QUT-pro_28sec.wav` | 4939244 | 2026-08-04T01:53:38 | `a829c97141d5` | `f5e793e07d60` | false | 28.000 | 44100 | 2 | -20.800000 | -9.056 |
| In The Meantime | DU-N | approved_three_mix_frontend_overlap | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/In The Meantime/Wide Ratings` | `DU-N_28sec.wav` | 4939244 | 2026-08-04T01:53:40 | `a806093fd76d` | `053a3ac19875` | false | 28.000 | 44100 | 2 | -20.800000 | -6.283 |
| Pouring Room | McG-R | approved_three_mix_frontend_overlap | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/Pouring Room/Similar Ratings` | `McG-R_28sec.wav` | 4939244 | 2026-08-04T01:53:58 | `9c30a6036403` | `efbb12284dc8` | false | 28.000 | 44100 | 2 | -20.800000 | -5.827 |
| Pouring Room | McG-T | approved_three_mix_frontend_overlap | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/Pouring Room/Similar Ratings` | `McG-T_28sec.wav` | 4939244 | 2026-08-04T01:54:02 | `5a8f9c660507` | `66f3f66bd62f` | false | 28.000 | 44100 | 2 | -20.800000 | -2.461 |
| Pouring Room | McG-X | approved_three_mix_frontend_overlap | `outputs/stimulus_selection/06_rating_stratification/candidate_review_audio/Pouring Room/Similar Ratings` | `McG-X_28sec.wav` | 4939244 | 2026-08-04T01:54:02 | `a62c5e0b3958` | `c9e7246801f2` | false | 28.000 | 44100 | 2 | -20.800000 | -3.252 |
| Pouring Room | McG-pro1 | six_mix_review_audio | `outputs/stimulus_selection/09_six_mix_proposals/review_audio/Pouring Room` | `McG-pro1_28sec.wav` | 7408844 | 2026-08-05T02:12:11 | `0f8af8346480` | `0f8af8346480` | true | 28.000 | 44100 | 2 | -20.800020 | -4.723 |
| Pouring Room | McG-U | six_mix_review_audio | `outputs/stimulus_selection/09_six_mix_proposals/review_audio/Pouring Room` | `McG-U_28sec.wav` | 7408844 | 2026-08-05T02:12:11 | `3fb25fb85ff3` | `3fb25fb85ff3` | true | 28.000 | 44100 | 2 | -20.800060 | -5.602 |
| Pouring Room | McG-V | six_mix_review_audio | `outputs/stimulus_selection/09_six_mix_proposals/review_audio/Pouring Room` | `McG-V_28sec.wav` | 7408844 | 2026-08-05T02:12:12 | `dee45df61628` | `dee45df61628` | true | 28.000 | 44100 | 2 | -20.800012 | -2.255 |

## Audio Technical Validation

All 24 active frontend WAV files passed technical QA:

- Valid decode: pass
- Count: 24 WAV files
- Songs: 4
- Versions per song: 6
- Duration: 28.000 s for all files
- Sample rate: 44.1 kHz for all files
- Channels: stereo for all files
- Integrated loudness: approximately -20.8 LUFS for all files
- Peak safety: pass; no clipping found
- Boundary fades: 5 ms fade-in and 5 ms fade-out recorded in metadata
- Duplicates: none detected within any song set
- Corruption or unexpected silence: none detected
- Alignment: all four song sets retain the approved six-mix order and final manual decision `ACCEPT_WITH_NOTE`; automatic alignment metrics remain audit notes rather than blockers.

## Configuration Validation

`study-interface/frontend-6mix/config/stimuli.json` was validated:

- Exactly 2 groups: pass
- Exactly 2 excerpts per group: pass
- Exactly 6 mixes per excerpt: pass
- Exactly 24 active audio paths: pass
- All active paths exist: pass
- Internal mix IDs match active filenames: pass
- No duplicate mix ID inside a song: pass
- No duplicate audio path inside a song: pass
- Trial generation: 3 scenarios x 2 songs = 6 trials
- Ratings per participant: 36
- Comments per participant: 6

JavaScript syntax checks passed for the six-mix frontend scripts.

## Practice Trial

Practice now uses the ColdStar 12-40 s excerpt with six genuine Mix Evaluation Dataset mixes:

- CNS-A
- CNS-B
- CNS-C
- CNS-D
- CNS-5
- CNS-pro

All six practice WAV files are frontend-local under `study-interface/frontend-6mix/assets/audio/study-stimuli/practice-trial/coldstar/`. They are 28.000 s, 44.1 kHz stereo, normalized to approximately -20.8 LUFS, use safe peaks, and include 5 ms boundary fades. Practice requires all six versions played, all six markers deliberately rated, and one shared comparative comment.

## Participant Blinding

Rendered trial UI was checked in-browser. Participant-facing visible text, aria labels, and title attributes did not expose song titles, artist names, mix IDs, source filenames, proposal labels, engineer names, or source folders. Participants see Version A through Version F and scenario text only.

Audio `source` elements in the DOM contain relative frontend asset URLs such as `../assets/audio/study-stimuli/main-study/.../du_e.wav?v=six_mix_frontend_prototype_v1_2026-08-05`. These URLs are not displayed in the participant UI, but they remain visible to someone inspecting browser developer tools.

## UI and End-to-End QA

Browser QA was run against `http://127.0.0.1:8064/`.

Group 01 result:

- Viewport: 1366 x 768
- Main Study trial count: 6
- Marker labels: Version A, Version B, Version C, Version D, Version E, Version F
- One shared comment textarea per trial: pass
- Version responses per trial: 6, 6, 6, 6, 6, 6
- Unique physical mixes per trial: 6, 6, 6, 6, 6, 6
- Submitted trials: 6
- Comments: 6
- Final `trial_records_json` rows: 6
- Production POST requests: 0
- Console errors: 0

Group 02 result:

- Viewport: 1024 x 768
- Main Study trial count: 6
- Marker labels: Version A, Version B, Version C, Version D, Version E, Version F
- One shared comment textarea per trial: pass
- Version responses per trial: 6, 6, 6, 6, 6, 6
- Unique physical mixes per trial: 6, 6, 6, 6, 6, 6
- Submitted trials: 6
- Comments: 6
- Final `trial_records_json` rows: 6
- Production POST requests: 0
- Console errors: 0

The checked runtime behavior preserved click-to-play markers, drag-to-rate markers, a shared Stop Audio button, one active audio element at a time, and mappings that persist through localStorage.

## UI Refinement Verification

Additional browser checks were run after the practice/UI refinement pass at 1366 x 768, 1440 x 900, 1024 x 768, and 768 x 1024.

Results:

- Practice rendered six Version A-F markers at all four viewports.
- Main Study rendered six Version A-F markers at all four viewports.
- Marker vertical centre spread was 0 px in both Practice and Main Study at all four viewports.
- No rating-value summary boxes were rendered in Practice or Main Study.
- No horizontal overflow was detected.
- Initial Practice markers were all unrated with the yellow/amber outline.
- Clicking a marker to play did not mark it as rated.
- Dragging one marker changed only that marker to the rated blue/green outline.
- Refresh restored rated and unrated marker states without preserving a false playing state.
- Practice completion and Main Study validation messages still require all six versions played, all six ratings set, and one shared comparative comment.

## Backend and Payload

`study-interface/frontend-6mix/js/netlify-submission.js` is local-only for this prototype. Final submission builds and stores the payload locally; it does not send a production POST request.

Payload expectations were verified:

- Six submitted Main Study trial records
- Six version responses per trial
- 36 total ratings
- Six total shared comments
- Physical mix mapping retained in records
- `trial_records_json` present in final payload

## Practice-Trial Caveat

The earlier Phase 6 caveat is resolved. Practice and Main Study now both use six Version A-F markers. Practice remains independent from the four Main Study songs and uses ColdStar practice-only audio.

## Original Frontend Isolation

The approved original frontend remains untouched:

- `git diff -- study-interface/frontend/`: empty
- Original frontend still serves on `http://127.0.0.1:8063/`
- Original frontend still uses 3 mixes per excerpt
- Original frontend still has 6 trials, 18 ratings, and 6 comments
- Original namespace remains `intent2control.study.dev.`
- Six-mix namespace is separate: `intent2control.study.6mix.dev.`

## Remaining Supervisor Approval Item

The only issue requiring supervisor approval is provenance policy for the 12 overlapping mixes.

Option A: accept the current mixed-provenance prototype, where 12 active files are direct six-mix review-audio copies and 12 active files are approved current three-mix corrected-fade overlap assets.

Option B: require all 24 active frontend files to be byte-identical to `outputs/stimulus_selection/09_six_mix_proposals/review_audio`. This would replace the 12 approved overlap assets and should be treated as a separate audio-change phase.

This report was updated after the UI and practice-task refinement pass.
