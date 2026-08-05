# Intent2Control Six-Mix Frontend Prototype

This folder contains the separate six-mix frontend prototype. It was copied from the approved three-mix frontend and then adapted only where the six-mix Main Study requires it.

Do not treat this folder as the approved production frontend. The approved three-mix study remains in `study-interface/frontend/`.

## Scope

- Separate frontend root: `study-interface/frontend-6mix/`
- Separate localStorage namespace: `intent2control.study.6mix.dev.`
- Study structure: 3 scenarios x 2 songs = 6 Main Study listening tasks
- Main Study versions per task: 6, labelled Version A-F
- Practice trial versions: 6, labelled Version A-F
- Total Main Study responses per participant: 36 ratings and 6 shared comments
- Final payload: local-only, stored under the six-mix namespace
- Backend integration: pending approval; production Netlify submission is disabled in this prototype

## Participant Flow

The participant flow mirrors the current approved three-mix frontend:

1. Landing
2. Study information and consent
3. Listening setup
4. Pre-study listening task
5. Instructions
6. Practice trial
7. Main Study transition
8. Six Main Study listening tasks
9. Post-task questionnaire
10. Demographic questionnaire
11. Review and Final Submit
12. Completion

Changing from three to six Main Study mixes does not change the number of scenarios, songs, trials, questionnaires, or shared comments.

## Main Study Logic

For each Main Study listening task, the frontend:

- takes the six configured physical mixes for the active song;
- shuffles those six mixes independently when the trial order is generated;
- maps them to participant-facing Version A-F labels;
- persists the full mapping under `experimental.trialOrder`;
- reuses the persisted mapping after refresh;
- stores the real physical mix ID, stable stimulus ID, and audio path in submitted data;
- never displays physical mix identities to participants.

The approved three-mix source frontend also maps mixes independently per generated task, not once per song/session. This prototype mirrors that level of randomisation.

## Active Six-Mix Sets

Group 01, Song A, Lead Me:

- DU-D
- DU-E
- McG-pro2
- PXL-L1
- PXL-L4
- QUT-F

Group 01, Song B, Red To Blue:

- McG-B
- McG-C
- McG-F
- McG-G
- McG-H
- McG-pro1

Group 02, Song A, In The Meantime:

- DU-H
- DU-I
- DU-K
- DU-N
- QUT-B
- QUT-pro

Group 02, Song B, Pouring Room:

- McG-pro1
- McG-R
- McG-T
- McG-U
- McG-V
- McG-X

The active WAV files live under `assets/audio/study-stimuli/main-study/`. The verification report is `docs/six-mix-audio-verification.json`.

## Trial Requirements

The Practice Trial now rehearses the same six-marker interaction as the Main Study. It uses the ColdStar practice-only excerpt from 12-40 s with six genuine dataset mixes: CNS-A, CNS-B, CNS-C, CNS-D, CNS-5, and CNS-pro. The six frontend WAVs are 28.000 s, 44.1 kHz stereo, approximately -20.8 LUFS, and include 5 ms boundary fades.

Each Main Study trial requires:

- playback of Version A, B, C, D, E, and F using the same played-state rule as the approved frontend;
- one deliberately set 0-100 preference rating for each version;
- one shared required comparative comment for the whole trial.

Initial marker positions are placeholders and do not count as ratings. Clicking or tapping a marker plays that version from 0:00 without changing the rating. Dragging changes only the intended marker. Clicking empty scale space does nothing. Stop audio stops and resets the currently playing version.

Markers sit on one shared horizontal centreline on desktop and tablet layouts. Yellow/amber outline indicates an unrated marker; blue/green outline indicates a deliberately rated marker; the currently playing marker receives a separate neutral outer ring. Separate numeric rating summary boxes have been removed from both Practice and Main Study.

## Response Structure

Each submitted Main Study trial record is stored under `experimental.submittedTrials` and contains:

- participant group;
- trial index;
- scenario ID;
- excerpt/song ID;
- six-mix stimulus configuration version;
- trial timing;
- one shared `comparative_comment`;
- six nested `versionResponses`.

Each version response contains:

- neutral display label;
- internal physical mix ID;
- stable stimulus ID;
- audio path;
- rating;
- played state;
- first-play timestamp;
- trial timing metadata.

The final local payload additionally includes `trial_records_json`, `responses_json`, `mix_mapping_json`, `presentation_order_json`, derived preferences, and client validation totals.

## Local-Only Submission

`js/netlify-submission.js` is retained as the payload builder, but network submission is disabled for the six-mix prototype. Final Submit builds and validates the six-mix payload, stores it in localStorage as `final.payload`, records `final.submitted`, and routes to Completion.

The payload fields include:

- `submission_status: "local_only_completed"`
- `backend_submission: "disabled_for_six_mix_prototype_pending_approval"`
- `local_only: true`
- `network_submission_attempted: false`

The active three-mix Netlify backend must not receive six-mix prototype data.

## Old Prototype State

The active stimulus/schema version is:

```text
six_mix_frontend_prototype_v1_2026-08-05
```

Stored unfinished trial orders from older six-mix prototype phases are considered incompatible if they use another version, contain fewer than six mapped versions per trial, duplicate a physical mix, duplicate an audio path, or reference audio not configured for the active song.

When incompatible unfinished Main Study state is detected, only these six-mix namespace keys are reset:

- `experimental.trialOrder`
- `experimental.currentTrialIndex`
- `experimental.currentResponses`
- `experimental.completedTrialIndices`
- `experimental.unsavedTrial.*`
- `experimental.firstPlay.*`
- `audio.played.experimental.*`
- `timing.trialStart.experimental_trial_*`
- `timing.trialSubmission.experimental_trial_*`

Consent, setup, screening, instructions, and practice progress are preserved where safe. The original three-mix namespace is not touched.

## Verification

Phase 4 verification checks include:

- JSON parsing and JavaScript syntax checks;
- active audio/config verification for 24 WAV files;
- randomisation simulation over at least 100 generated sessions;
- browser checks for Group 01 and Group 02 Main Study tasks;
- local-only final payload check;
- isolation check against `study-interface/frontend/`.

Later UI refinement checks added six-version Practice support, same-height marker alignment, removal of rating summary boxes, rated/unrated marker states, and refreshed comparative comment wording.

No commits or pushes are made for this prototype work.
