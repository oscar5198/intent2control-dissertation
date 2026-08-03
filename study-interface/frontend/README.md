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
7. `pages/main-study.html`
8. `pages/trial.html`
9. `pages/post-task.html`
10. `pages/demographics.html`
11. `pages/review.html`
12. `pages/completion.html`

Deprecated redirect pages:

- `pages/participant-information.html`
- `pages/consent.html`

## Configuration-driven Design

The frontend reads from JSON configuration files for study constants, scenarios, questionnaires, screening, practice, and stimuli metadata. Some configuration values remain temporary or unresolved, but `config/stimuli.json` now contains the final experimental audio mappings.

The approved Participant Information Sheet and consent form in `../docs/participant-materials/` remain the authoritative source for participant-facing wording.

Current configuration files include:

- `config/study-config.json` for frozen study constants, page sequence, retention, temporary setup audio metadata, and unresolved values.
- `config/screening.json` for the development-only Pre-Study Listening Task structure.
- `config/practice.json` for the practice trial structure, practice-only scenario, and independent practice audio paths.
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
- Pre-Study Listening Task placeholder flow.
- Instructions.
- Practice Trial.
- Main Study transition.
- Experimental listening task system.
- Demographic Questionnaire.
- Post-task Questionnaire.
- Review and Final Submission.
- Completion.

The participant-facing frontend flow is now implemented through Completion for development testing. The frontend includes the final experimental trial audio stimuli, but does not yet implement backend persistence, database storage, final randomisation balancing, or production data submission.

The Listening Setup page currently uses a temporary playback-test audio file:

```text
assets/audio/study-stimuli/listening-setup/setup_test_audio.wav
```

The active file is stored at `frontend/assets/audio/study-stimuli/listening-setup/setup_test_audio.wav`. It is temporary test audio for interface development only, is not a final screening or experimental stimulus, and must be replaced before pilot or production use. If the configured file is missing or cannot load, the page shows a warning and progression remains disabled.

The Pre-Study Listening Task page is driven by `config/screening.json`. It implements a development-only six-item matching flow using Version A, Version B, and Version C labels. The six presentations are generated as two internal segment identities repeated three times each, randomised once per attempt, and persisted under the existing localStorage namespace so refresh does not reshuffle the task. For every item, participants must play all three versions and answer whether Version A matches Version B or Version C before selecting `Submit listening task`.

If older local development sessions contain an incompatible pre-study presentation order from the previous three-item structure, the page removes only the current attempt's pre-study listening task keys and regenerates the six-item order. This avoids mixing old and new task schemas without wiping unrelated study progress.

```text
assets/audio/study-stimuli/pre-study-listening-task/
```

The previous duplicated MP3 screening files were audited and replaced because they were byte-for-byte identical. The current development files are WAV clips rebuilt from original Mix Evaluation Dataset files for `InTheMeantime`. Each temporary segment uses one common 6-second musical time region across all versions: Version A is a DU-H reference mix excerpt, the matching answer is an identical duplicate of that excerpt, and the non-matching option is a different mix of the same song and same aligned excerpt. Segment 1 uses DU-H and DU-M from 42-48 seconds; Segment 2 uses DU-H and DU-J from 54-60 seconds with a -0.00225 second comparison offset. For development testing only, the temporary pass threshold is 2 out of 6, retry is enabled, and the maximum attempt count is 2. Internal answers, correctness, attempt records, aggregate score, segment ID, repetition number, presentation order, and Version A/B/C mapping are stored, but no numerical score is shown to participants. `productionReady` is set to `false`. These files are not final validated pre-study stimuli. Final supervisor-approved segment/song selections, Brecht preference-based selection criteria/results, scientific pass criteria, attempts policy, and exclusion/failure procedure remain TBC.

Audio controls use a minimal shared custom interface with Play/Pause, Restart, progress, and time display. Native browser audio controls are hidden so participant-facing speaker/volume, download, and playback-speed controls are not shown. Shared audio behaviour enforces one comparative audio source at a time; when participants switch from one version to another, the previous version pauses and resets to 0:00, and the newly selected version starts from 0:00. The frontend also prevents participant seeking by restoring the last allowed playback position, fixes individual player volume at normal playback level, and keeps playback rate at 1. This is a convenience and consistency measure for the listening-test interface only; it is not a security mechanism.

The Instructions page requires the acknowledgement `I understand how to complete the listening task.` before Practice Trial can be opened.

The Practice Trial page is driven by `config/practice.json`. It uses a practice-only restaurant scenario and an independent real song excerpt from the Mix Evaluation Dataset that is not one of the four main experimental songs. Three existing dataset mix versions from that song are excerpted into practice WAV files and stored separately under:

```text
assets/audio/study-stimuli/practice-trial/coldstar/
```

The three versions are direct 28-second excerpts from existing dataset mixes using identical start and end timestamps. They are not newly processed, synthesised, or stem-rebalanced practice mixes. The practice song is intentionally separate from all experimental songs and is stored in the consolidated `study-stimuli` audio root outside the Main Study subfolder. Practice responses are stored only under `practice.*` temporary keys and are excluded from main analysis. Participants must play all three practice versions, deliberately position all three Version A/B/C markers on the shared 0-100 preference scale, and provide all three required comments before continuing. The default visual marker position does not count as a completed rating, and required comments reject empty or whitespace-only text.

The Main Study transition page appears after successful practice completion and before the first response-collecting listening task. The experimental listening task page is driven by `config/stimuli.json`. It assigns one of two groups using temporary frontend randomness, persists the assignment, generates ten scenario-by-excerpt trials as five adjacent scenario pairs, persists trial order, and randomly maps actual mix IDs to the neutral participant-facing labels Version A, Version B, and Version C for every task. Final server-side balanced group assignment remains TBC.

The approved experimental scenario titles and text are now configured in `config/scenarios.json` and embedded in `config/stimuli.json`. Scenario prefixes such as EDR-1 and FM-2 remain internal configuration identifiers only and are stripped from participant-facing trial titles. Each participant's two assigned excerpts are mapped once to stable neutral labels, `Song A` and `Song B`, and the mapping is persisted under `experimental.excerptLabelMapping` so it does not change on refresh. Researcher-facing final excerpt names, mix identities, and production audio files are documented in `../docs/final-stimuli-manifest.md`; they must not be displayed to participants.

Experimental trial randomisation uses the `scenario_pairs_v1` development algorithm:

1. Randomise the five-scenario order once per participant.
2. For each scenario, create the two assigned song trials.
3. Randomise the Song A/Song B order within that scenario.
4. Append both song trials as one consecutive pair before moving to the next scenario.
5. Randomise the Version A/B/C mix mapping independently within each trial.

If an older stored development trial order is found before any experimental trial has been submitted, the order is regenerated using the grouped scenario-pair structure. If submitted trials already exist, the current order is preserved and the trial page shows a development warning to start a fresh session when testing the updated randomisation.

Practice and main study listening task pages share the same grouped interaction sequence:

1. Listen to the versions.
2. Place Version A, Version B, and Version C on one shared preference scale.
3. Explain your ratings.

Each experimental trial requires successful playback start for Version A, Version B, and Version C, deliberate positioning of all three draggable 0-100 preference markers, and one non-whitespace comment for each version. The shared scale shows Bad, Poor, Fair, Good, and Excellent anchors at 0, 25, 50, 75, and 100 while preserving continuous integer ratings. Selecting a marker plays the corresponding version from 0:00 using the same controlled audio logic as the compact Play/Pause buttons. Desktop uses a horizontal shared scale; narrow mobile layouts switch to a vertical shared scale to avoid horizontal overflow. The page stores submitted trial records under `experimental.submittedTrials` separately from practice responses, with the rating field still containing one 0-100 value per version. After ten submitted trial records, the participant is routed to `post-task.html`.

The current experimental audio paths use revised rating-stratification WAV stimuli copied under:

```text
assets/audio/study-stimuli/main-study/
```

There are 12 experimental files in total: two groups, two songs per group, and three mix slots per song. The frontend filenames are neutral, for example `assets/audio/study-stimuli/main-study/group_01/song_a_lead_me/pxl_l1.wav`, while the researcher-facing source mapping is preserved in `../docs/final-stimuli-manifest.md` and `config/stimuli.json`. The current stimulus configuration version is `rating_stratification_v2_2026-08-03`. Stored Main Study trial orders include this version so stale local mappings can be regenerated before any submitted trial exists, or preserved with a compatibility warning if submitted trial records already exist. These files are final Main Study stimuli for supervisor review and pilot preparation, not setup-test, pre-study listening-task, or practice stimuli.

The consolidated active frontend audio root is documented in `assets/audio/study-stimuli/README.md` and `../docs/study-audio-manifest.md`. Older folders such as `assets/audio/experimental/`, `assets/audio/pre-experiment-normalized/`, `assets/audio/practice/`, and `assets/audio/screening-development/` remain as obsolete audit copies and are no longer active configuration paths.


The Post-task Questionnaire and Demographic Questionnaire are driven by `config/questionnaires.json`. The post-task questionnaire appears immediately after the ten main study listening tasks, followed by the demographic questionnaire and final review. Post-task agreement questions use a horizontal Strongly disagree to Strongly agree Likert layout where space allows. The listening-device and completion-location questions do not include a `Prefer not to say` option; selecting `Other` reveals a required detail text field while preserving the selected `Other` value. The required demographic fields are age range, country that most influenced the participant's musical and cultural background, music listening habits, music production or audio engineering experience, and hearing difficulty. Gender is optional. Post-task additional comments are optional. The structured options are development options and remain subject to final approval before pilot use.

The Review and Final Submission page creates a temporary local development payload only. This payload is stored in `localStorage` under `final.payload`, is not production-safe, and is not submitted to a backend. Production backend submission remains TBC.

The Completion page shows the anonymous development session ID and confirms only that responses have been recorded in the current study session. It must not claim that responses have been securely submitted to QMUL until backend submission exists.

An optional development-only trial-completion helper exists on the listening task page. It is hidden unless `appEnvironment` is `development` and `frontendDevelopmentMode` is explicitly `true` in `config/study-config.json`. It requires a second explicit button selection before creating placeholder trial records and must never be enabled in production.

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
- `timing.screeningItemStart.attempt1.prestudy_segment_01_rep1_order1`
- `timing.screeningItemSubmission.attempt1.prestudy_segment_01_rep1_order1`
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
- `screening.presentationOrder.attempt1`
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
