# Six-Mix Prototype Manifest

This manifest describes the separate six-mix frontend prototype in `study-interface/frontend-6mix/`.

## Scope

- Original approved frontend: `study-interface/frontend/`
- Six-mix prototype frontend: `study-interface/frontend-6mix/`
- localStorage namespace: `intent2control.study.6mix.dev.`
- stimulus/schema version: `six_mix_frontend_prototype_v1_2026-08-05`
- backend behaviour: production Netlify Forms submission through separate form `listening-study-6mix`

## Study Design

- 3 scenarios
- 2 songs per participant
- 6 Main Study listening tasks
- 6 versions per Main Study task
- 6 versions in the Practice Trial
- 36 total Main Study ratings
- 6 total shared Main Study comments

The page order, questionnaires, scenario count, song count, and one-comment-per-trial design are inherited from the current approved three-mix frontend. The separate six-mix prototype now extends the Practice Trial to six versions so participants rehearse the same marker interaction used in the Main Study.

## Randomisation

The current approved three-mix frontend generates the Version A-C physical-mix mapping independently while each trial is created in `buildTrialOrder()`. It does not use one fixed mapping per song/session.

The six-mix prototype mirrors this: each generated Main Study task independently shuffles the six configured physical mixes for that song and maps them to Version A-F. The mapping is persisted in `experimental.trialOrder`, survives refresh, and is recoverable in submitted/local payload data.

## Main Study Mix Sets

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

## Trial Completion Requirements

Practice uses the ColdStar 12-40 s excerpt and six genuine dataset mixes: CNS-A, CNS-B, CNS-C, CNS-D, CNS-5, and CNS-pro. It requires all six practice audio sources played, all six markers deliberately rated, and one shared comparative comment.

Each Main Study task requires:

- all six Version A-F audio sources played;
- all six 0-100 preference markers deliberately dragged;
- one non-empty shared comparative comment.

Click/tap plays the marker audio from 0:00. Stop audio stops and resets the current version. The participant-facing page does not expose physical mix identities.

Practice and Main Study markers share one horizontal centreline on desktop and tablet layouts. Rating summary boxes are not rendered. Marker state is shown directly: yellow/amber outline means unrated, blue/green outline means rated, and a separate neutral outer ring marks the currently playing version.

## Backend and Payload

Final Submit builds and validates the complete six-mix payload, submits it to Netlify Forms, and stores it locally under the six-mix namespace after a successful response. The hidden Netlify form is in `study-interface/frontend-6mix/index.html` and uses the distinct form name `listening-study-6mix`, so six-mix CSV exports remain separate from the approved three-mix form.

The submitted schema uses top-level scalar fields plus JSON fields. Scalar fields include `study_id`, `study_version`, `schema_version`, `stimulus_configuration_version`, `source_version`, `submission_status`, `group_id`, `trial_count`, `version_count`, `rating_count`, `comment_count`, `started_at`, `completed_at`, `duration_seconds`, and `consent_confirmed`.

Structured JSON fields include `consent_json`, `listening_setup_json`, `pre_study_json`, `practice_json`, `demographics_json`, `post_task_json`, `scenario_order_json`, `song_order_json`, `trial_order_json`, `mix_mapping_json`, `presentation_order_json`, `trial_records_json`, `responses_json`, `derived_preferences_json`, `timing_json`, `device_browser_json`, `client_validation_json`, and `final_payload_json`.

`trial_records_json` contains six Main Study trial records with one shared comparative comment per trial and six nested version records. `responses_json` is the flattened analysis view with 36 Main Study rating records. Practice responses remain separate in `practice_json` and are not emitted as Main Study rows.

Duplicate protection mirrors the three-mix implementation: `final.submissionInProgress` blocks repeat clicks while the request is in flight, and `final.submissionCompleted`/`final.submitted` are set only after Netlify returns success. Failed submissions keep the participant on Review, preserve responses, and show a retry-safe error.

## Old State Invalidation

Unfinished old six-mix Main Study state is invalidated when the stored trial order:

- uses an older stimulus configuration version;
- has fewer or more than six mapped versions per trial;
- contains duplicated physical mix IDs;
- contains duplicated audio paths;
- references mixes not configured for the active song.

Only Main Study trial-order, unsaved-response, playback, and Main Study timing keys inside `intent2control.study.6mix.dev.` are cleared. Earlier flow progress is preserved where safe.
