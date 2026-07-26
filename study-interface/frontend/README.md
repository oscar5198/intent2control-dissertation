# Frontend Architecture

This folder contains the Phase 2B frontend architecture scaffold for the listening study interface.

The application is planned as a simple multi-page research web application using only:

- HTML.
- CSS.
- Vanilla JavaScript.
- JSON configuration.

No framework, package manager, build tool, external CDN, backend code, database, or Node dependency is used in this scaffold.

## Why Vanilla HTML, CSS, and JavaScript

The final QMUL hosting environment is still unresolved. A framework-free frontend keeps the application portable and easier to serve from a basic web server while the backend and deployment constraints are confirmed.

This architecture also keeps the study interface transparent, auditable, and suitable for an academic research workflow.

## Folder Structure

```text
frontend/
├── pages/                 # Multi-page HTML shells
├── css/                   # Shared design-system CSS architecture
├── js/                    # Vanilla JavaScript responsibility modules
├── config/                # JSON study configuration placeholders
└── assets/                # Audio, images, and icon placeholders
```

## Page Sequence

1. `pages/index.html`
2. `pages/study-information-consent.html`
3. `pages/listening-setup.html`
4. `pages/screening.html`
5. `pages/instructions.html`
6. `pages/practice.html`
7. `pages/trial.html`
8. `pages/demographics.html`
9. `pages/post-task.html`
10. `pages/review.html`
11. `pages/completion.html`

Deprecated redirect pages:

- `pages/participant-information.html`
- `pages/consent.html`

## Configuration-driven Design

The frontend reads from JSON configuration files for study constants, scenarios, questionnaires, screening, practice, and stimuli metadata. Some configuration values remain temporary or unresolved, but `config/stimuli.json` now contains the final experimental audio mappings.

The approved Participant Information Sheet and consent form in `../docs/participant-materials/` remain the authoritative source for participant-facing wording.

Current configuration files include:

- `config/study-config.json` for frozen study constants, page sequence, retention, temporary setup audio metadata, and unresolved values.
- `config/screening.json` for the development-only audio-screening structure.
- `config/practice.json` for the development-only practice trial structure.
- `config/stimuli.json` for the experimental trial structure, group definitions, internal scenario identifiers, final experimental excerpt mappings, three mix slots per excerpt, neutral Version A/B/C labels, and final experimental audio paths.
- `config/scenarios.json`, `config/questionnaires.json`, and `config/stimuli.example.json` for later study content.

## Local Development Server

The frontend can be tested locally by serving this directory with a simple static web server.

Python example:

```text
python -m http.server 8000
```

Then open:

```text
http://localhost:8000/pages/
```

Do not assume Python will be the production server. This is only a local development convenience.

## Storage

`js/storage.js` is a temporary local development state abstraction. Browser `localStorage` is not the final secure research-data store and must not be used as production persistence for participant responses.

Final data persistence depends on the confirmed QMUL backend, secure storage, and data governance requirements.

## Data and Asset Safety

Do not commit:

- Participant data.
- Exported responses.
- Real audio stimuli unless explicitly cleared.
- Secrets.
- Local databases.
- Logs.

Audio files under `assets/audio/` are ignored by Git except for `.gitkeep`.

## Current Status

Current status: Phase 2B frontend architecture scaffold with participant-facing screens implemented for:

- Landing page.
- Combined Study Information and Consent page.
- Listening Setup.
- Audio Screening placeholder flow.
- Instructions.
- Practice Trial.
- Experimental Trial system.
- Demographic Questionnaire.
- Post-task Questionnaire.
- Review and Final Submission.
- Completion.

The participant-facing frontend flow is now implemented through Completion for development testing. The frontend includes the final experimental trial audio stimuli, but does not yet implement backend persistence, database storage, final randomisation balancing, or production data submission.

The Listening Setup page currently uses a temporary development test-audio file:

```text
assets/audio/setup-test-development.mp3
```

The file is stored at `frontend/assets/audio/setup-test-development.mp3`. It is temporary test audio for interface development only, is not a final screening or experimental stimulus, and must be replaced before pilot or production use. If the configured file is missing or cannot load, the page shows a warning and progression remains disabled.

The Audio Screening page is driven by `config/screening.json`. It currently implements a development-only three-item matching flow using Version A, Version B, and Version C labels. Participants play all three versions and answer which version matches Version A. The duplicated `DU-H.mp3` assets are stored under:

```text
assets/audio/screening-development/
```

For development testing only, the temporary pass threshold is 2 out of 3, retry is enabled, and the maximum attempt count is 2. `productionReady` is set to `false`. These values and audio files are not final validated screening stimuli and must be replaced before pilot or production use. Final stimuli, threshold, attempts policy, and exclusion/failure procedure remain TBC.

Audio controls remain native browser controls so that play, pause, replay, seeking, and volume remain available and keyboard accessible. Where supported by the browser, the frontend discourages downloading, playback-speed changes, picture-in-picture, and remote playback through the native control surface using `controlsList`, `disablePictureInPicture`, and `disableRemotePlayback`. This is a convenience measure for the listening-test interface only; it is not a security mechanism, and browser support may differ.

The Instructions page requires the acknowledgement `I understand how to complete the listening task.` before Practice Trial can be opened.

The Practice Trial page is driven by `config/practice.json`. It uses temporary development content and the existing setup-test MP3 for all three neutral versions. Practice responses are stored only under `practice.*` temporary keys and are excluded from main analysis. Sliders must be deliberately interacted with; the default visual slider position does not count as a completed rating. Required comments reject empty or whitespace-only text. Final practice wording, audio, and any practice-specific audio-play requirement remain subject to replacement before pilot use.

The Experimental Trial page is driven by `config/stimuli.json`. It assigns one of two groups using temporary frontend randomness, persists the assignment, generates ten scenario-by-excerpt trials as five adjacent scenario pairs, persists trial order, and randomly maps actual mix IDs to the neutral participant-facing labels Version A, Version B, and Version C for every trial. Final server-side balanced group assignment remains TBC.

The approved experimental scenario titles and text are now configured in `config/scenarios.json` and embedded in `config/stimuli.json`. Scenario prefixes such as EDR-1 and FM-2 remain internal configuration identifiers only and are stripped from participant-facing trial titles. Each participant's two assigned excerpts are mapped once to stable neutral labels, `Song A` and `Song B`, and the mapping is persisted under `experimental.excerptLabelMapping` so it does not change on refresh. Researcher-facing final excerpt names, mix identities, and production audio files are documented in `../docs/final-stimuli-manifest.md`; they must not be displayed to participants.

Experimental trial randomisation uses the `scenario_pairs_v1` development algorithm:

1. Randomise the five-scenario order once per participant.
2. For each scenario, create the two assigned song trials.
3. Randomise the Song A/Song B order within that scenario.
4. Append both song trials as one consecutive pair before moving to the next scenario.
5. Randomise the Version A/B/C mix mapping independently within each trial.

If an older stored development trial order is found before any experimental trial has been submitted, the order is regenerated using the grouped scenario-pair structure. If submitted trials already exist, the current order is preserved and the trial page shows a development warning to start a fresh session when testing the updated randomisation.

Practice and Experimental Trial pages share the same grouped interaction sequence:

1. Listen to the versions.
2. Rate the versions.
3. Explain your ratings.

Each experimental trial requires successful playback start for Version A, Version B, and Version C, deliberate interaction with all three 0-100 sliders, and one non-whitespace comment for each version. Rating controls show `0 - Least preferred` and `100 - Most preferred` endpoint labels and no midpoint label. The page stores submitted trial records under `experimental.submittedTrials` separately from practice responses. After ten submitted trial records, the participant is routed to `demographics.html`.

The current experimental audio paths use final WAV stimuli copied under:

```text
assets/audio/experimental/
```

There are 12 experimental files in total: two groups, two songs per group, and three mix slots per song. The frontend filenames are neutral, for example `assets/audio/experimental/group_01/song_a/mix_01.wav`, while the researcher-facing source mapping is preserved in `../docs/final-stimuli-manifest.md` and `config/stimuli.json`. These files are final experimental stimuli, not setup-test, screening, or practice stimuli.

The Demographic Questionnaire and Post-task Questionnaire are driven by `config/questionnaires.json`. The required demographic fields are age range, nationality, music listening habits, music production or audio engineering experience, and hearing difficulty. Gender is optional. Post-task additional comments are optional. The structured options are development options and remain subject to final approval before pilot use.

The Review and Final Submission page creates a temporary local development payload only. This payload is stored in `localStorage` under `final.payload`, is not production-safe, and is not submitted to a backend. Production backend submission remains TBC.

The Completion page shows the anonymous development session ID and confirms only that responses have been recorded in the current study session. It must not claim that responses have been securely submitted to QMUL until backend submission exists.

An optional development-only trial-completion helper exists on the Experimental Trial page. It is hidden unless `appEnvironment` is `development` and `frontendDevelopmentMode` is explicitly `true` in `config/study-config.json`. It requires a second explicit button selection before creating placeholder trial records and must never be enabled in production.

## Temporary Development Storage Keys

The first sprint uses namespaced local development keys beginning with:

```text
intent2control.study.dev.
```

Current keys include:

- `timing.studyStart`
- `timing.pageEntry.landing`
- `timing.pageEntry.study-information-consent`
- `timing.pageCompletion.study-information-consent`
- `timing.studyInformationConsentCompletion`
- `timing.consentCompletion`
- `timing.pageEntry.listening-setup`
- `timing.pageCompletion.listening-setup`
- `timing.listeningSetupCompletion`
- `timing.pageEntry.screening`
- `timing.pageCompletion.screening`
- `timing.screeningStart.attempt1`
- `timing.screeningItemStart.attempt1.screening_item_01`
- `timing.screeningItemStart.attempt1.screening_item_02`
- `timing.screeningItemStart.attempt1.screening_item_03`
- `timing.screeningItemSubmission.attempt1.screening_item_01`
- `timing.screeningItemSubmission.attempt1.screening_item_02`
- `timing.screeningItemSubmission.attempt1.screening_item_03`
- `timing.screeningCompletion.attempt1`
- `timing.pageEntry.instructions`
- `timing.pageCompletion.instructions`
- `timing.instructionsCompletion`
- `timing.pageEntry.practice`
- `timing.pageCompletion.practice`
- `timing.practiceStart`
- `timing.trialStart.practice_trial`
- `timing.trialSubmission.practice_trial`
- `timing.practiceSubmission`
- `timing.practiceCompletion`
- `pis.documentOpened`
- `consent.documentOpened`
- `pis.acknowledged`
- `consent.items`
- `audio.played.setup-test-audio`
- `audio.played.screening.attempt1.screening_item_01.version_a`
- `audio.played.screening.attempt1.screening_item_01.version_b`
- `audio.played.screening.attempt1.screening_item_01.version_c`
- `listeningSetup.testAudioPlayed`
- `listeningSetup.headphones`
- `listeningSetup.quietEnvironment`
- `listeningSetup.comfortableVolume`
- `listeningSetup.completed`
- `screening.activeAttempt`
- `screening.attemptNumber`
- `screening.currentItemIndex`
- `screening.selectedAnswers`
- `screening.playedStates.attempt1`
- `screening.itemResponses`
- `screening.itemScores`
- `screening.totalScore`
- `screening.attemptScore.attempt1`
- `screening.attemptRecords`
- `screening.passed`
- `screening.failed`
- `screening.developmentBypassUsed`
- `instructions.acknowledged`
- `practice.currentResponses`
- `practice.ratings`
- `practice.ratingTouched`
- `practice.comments`
- `practice.completed`
- `audio.played.practice.practice_version_a`
- `audio.played.practice.practice_version_b`
- `audio.played.practice.practice_version_c`
- `experimental.groupAssignment`
- `experimental.excerptLabelMapping`
- `experimental.trialOrder`
- `experimental.currentTrialIndex`
- `experimental.currentResponses`
- `experimental.unsavedTrial.1`
- `experimental.submittedTrials`
- `experimental.completedTrialIndices`
- `experimental.firstPlay.trial1.version_a`
- `experimental.firstPlay.trial1.version_b`
- `experimental.firstPlay.trial1.version_c`
- `audio.played.experimental.trial1.version_a`
- `audio.played.experimental.trial1.version_b`
- `audio.played.experimental.trial1.version_c`
- `timing.trialStart.experimental_trial_01`
- `timing.trialSubmission.experimental_trial_01`
- `timing.pageEntry.demographics`
- `timing.pageCompletion.demographics`
- `timing.pageEntry.post-task`
- `timing.pageCompletion.post-task`
- `timing.pageEntry.review`
- `timing.pageCompletion.review`
- `timing.pageEntry.completion`
- `session.developmentId`
- `demographics.responses`
- `demographics.completed`
- `postTask.responses`
- `postTask.completed`
- `final.payload`
- `final.submitted`
- `timing.finalSubmission`

These keys are temporary development state only. They must not be treated as final secure research-data storage.
