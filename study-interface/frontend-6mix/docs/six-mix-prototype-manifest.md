# Six-Mix Prototype Manifest

This manifest describes the separate six-mix frontend prototype in `study-interface/frontend-6mix/`.

## Scope

- Original approved frontend: `study-interface/frontend/`
- Six-mix prototype frontend: `study-interface/frontend-6mix/`
- localStorage namespace: `intent2control.study.6mix.dev.`
- stimulus/schema version: `six_mix_frontend_prototype_v1_2026-08-05`
- backend behaviour: local-only payload; production Netlify submission disabled

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

## Local Payload

Final Submit stores the complete six-mix payload locally under the six-mix namespace. It includes nested `trial_records_json` with six version records per trial, flattened `responses_json` with 36 rows, mix mapping, presentation order, derived preferences, and client validation totals.

Six-mix payloads must not be posted to the active three-mix production backend until backend schema approval is complete.

## Old State Invalidation

Unfinished old six-mix Main Study state is invalidated when the stored trial order:

- uses an older stimulus configuration version;
- has fewer or more than six mapped versions per trial;
- contains duplicated physical mix IDs;
- contains duplicated audio paths;
- references mixes not configured for the active song.

Only Main Study trial-order, unsaved-response, playback, and Main Study timing keys inside `intent2control.study.6mix.dev.` are cleared. Earlier flow progress is preserved where safe.
