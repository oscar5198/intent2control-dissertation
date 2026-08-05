# Changelog

All notable changes to this study interface foundation will be documented in this file.

The format is based on Keep a Changelog.

## Unreleased

### Changed

- Updated the active Main Study design from five episodes and ten listening tasks to three episodes and six listening tasks while preserving grouped episode-pair randomisation, two-song group allocation, three-mix ratings, and comparative comments.
- Updated the active Practice Trial vignette to the EDR-2 relaxation-distraction scenario and clarified that practice ratings should reflect personal listening preference in the described situation.

### Added

- Initial `study-interface/` directory structure.
- Initial documentation.
- Initial technology-independent study configuration document.
- Participant materials directory documentation.
- Placeholder directories for frontend, backend, database, tests, scripts, and assets.
- Framework-free frontend architecture scaffold.
- Multi-page HTML shell structure.
- CSS architecture files for tokens, base styles, layout, components, and page placeholders.
- Vanilla JavaScript responsibility placeholder files.
- JSON configuration placeholder files.
- Frontend architecture README.
- Participant-facing landing page for the first frontend sprint.
- Combined Study Information and Consent page using approved participant-material sources.
- Participant-facing PDF copies of the Participant Information Sheet and Consent Form.
- QMUL logo image asset for the shared participant-facing header.
- Listening Setup page with headphone, quiet-environment, and comfortable-volume confirmations.
- Setup test-audio gate using the configured temporary development path `frontend/assets/audio/setup-test-development.mp3`.
- Temporary development setup audio copied to `frontend/assets/audio/setup-test-development.mp3`.
- Audio Screening page driven by the new `frontend/config/screening.json` development configuration.
- Three-item development-only ABX screening structure with X, A, and B audio choices and answer controls.
- Temporary development screening audio assets under `frontend/assets/audio/screening-development/`.
- Audited and regenerated development audio screening assets under `frontend/assets/audio/screening-development/`.
- Instructions page with required task acknowledgement.
- Development-only Practice Trial page driven by `frontend/config/practice.json`.
- Practice trial validation for deliberately touched 0-100 sliders and required comments.
- Shared multi-marker 0-100 preference scale for Practice Trial and Main Study ratings, with marker-triggered audio playback and unchanged stored rating semantics.
- Development-only experimental stimuli configuration in `frontend/config/stimuli.json`.
- Experimental Trial page driven by persisted group assignment, generated trial order, and per-trial Version A/B/C mappings.
- Experimental trial validation requiring playback start, deliberate rating, and required non-whitespace comment for Version A, Version B, and Version C.
- Experimental response records stored separately from practice responses under `experimental.*` temporary development keys.
- Approved experimental scenario titles and text in `frontend/config/scenarios.json` and `frontend/config/stimuli.json`.
- Grouped Listen -> Rate -> Explain layout for Practice Trial and Experimental Trial pages.
- Demographic Questionnaire page driven by structured `frontend/config/questionnaires.json` fields.
- Post-task Questionnaire page driven by structured `frontend/config/questionnaires.json` fields.
- Review and Final Submission page with completion summary and local development payload creation.
- Completion page with thank-you message, development session ID, and non-backend completion wording.
- Anonymous development session ID generation using browser crypto where available.
- Development-only trial-completion helper, hidden unless explicit frontend development mode is enabled.
- Route guards for Instructions, Practice Trial, and Experimental Trial shell.
- Route guard preventing direct demographic-questionnaire access until ten experimental trial records have been submitted.
- Route guards for Post-task Questionnaire, Review and Final Submission, and Completion.
- Temporary development storage keys for listening setup state, screening attempts, screening responses, screening scores, pass/fail state, and screening timing.
- Route guard preventing direct access to Instructions unless screening has passed.
- Final experimental WAV stimuli copied under `frontend/assets/audio/experimental/`.
- Researcher-facing final stimuli manifest documenting group, song, mix, source-file, internal-ID, and frontend-path mappings.

### Changed

- Replaced per-version Practice Trial and Main Study comment fields with one required trial-level comparative comment, submitted as `comparative_comment` and repeated on long-format rating rows for analysis.
- Updated the Pre-Study Listening Task to use participant-facing Reference, Version A, and Version B ABX terminology, with A/B answer mapping and incompatible old B/C local state invalidated.
- Hardened Pre-Study Listening Task rendering so stale saved audio-card labels cannot display old Version A/B/C headings.
- Updated Pre-Study Listening Task cache-busting and schema versioning to force the Reference/Version A/Version B interface after stale browser state.
- Refined Practice Trial and Main Study shared preference-scale interaction so marker click/tap plays audio without changing ratings, marker drag sets ratings, empty scale clicks do nothing, separate Version A/B/C playback controls are removed, one shared `Stop audio` button controls playback, and verbal anchors align precisely with 0, 25, 50, 75, and 100.
- Consolidated all active frontend audio into `frontend/assets/audio/study-stimuli/`, updated configuration paths, and added a researcher-facing master audio manifest.
- Refreshed the active Main Study frontend WAV files from corrected 5 ms boundary-fade source excerpts, retained the approved song/mix selection, updated the stimulus configuration version, and refreshed researcher-facing audio manifests.
- Added stimulus-version cache-busting to Main Study audio requests so browsers fetch the refreshed fade-corrected WAV files even when physical filenames are unchanged.
- Reordered the participant flow so the Post-task Questionnaire now appears before the Demographic Questionnaire, with route guards, page progress, and review prerequisites updated accordingly.
- Updated Post-task Questionnaire agreement questions to use a horizontal Strongly disagree to Strongly agree Likert layout where space allows.
- Removed `Prefer not to say` from the post-task listening-device and completion-location questions and added required conditional detail fields when `Other` is selected.
- Replaced native participant-facing audio controls with shared volume-free controls and rebuilt temporary Pre-Study Listening Task stimuli from same-song, same-excerpt Mix Evaluation Dataset mix versions.
- Updated the Main Study mix sets from the revised rating-stratification candidate-review outputs, normalised frontend copies to -20.8 LUFS, documented the new researcher-facing manifest, and added stimulus-configuration version handling for stale local trial orders.
- Renamed the participant-facing Audio Screening stage to Pre-Study Listening Task, prepared a six-item two-segment by three-repetition structure with persisted randomised order, hid participant-facing score feedback, and added shared reset-on-switch controlled audio behaviour.
- Revised the landing-page study title and description following supervisor feedback.
- Revised the Listening Setup introductory sentence following supervisor feedback.
- Refreshed the participant-facing Participant Information Sheet and Consent Form PDFs from the latest approved participant-material source files.
- Replaced the synthetic Practice Trial audio with a real unused Mix Evaluation Dataset song excerpt, stored separately from all experimental songs under `frontend/assets/audio/practice/`.
- Replaced the processed Practice Trial mix variants with three direct excerpts from existing Mix Evaluation Dataset mixes for the selected practice song.
- Updated the Practice Trial scenario presentation so `Practice scenario` appears as the section label and `Dinner Date` appears as the scenario title.
- Updated README documentation to state that the practice song is intentionally separate from all experimental songs.
- Added a frontend favicon asset so static browser review does not produce a default missing-favicon request.
- Added a Main Study transition page between Practice Trial and the first experimental listening task, and updated participant-facing trial count wording to `Listening Task X of 10`.
- Replaced the Demographic Questionnaire `Nationality` field with the approved cultural influence country question and helper text.
- Updated the landing-page duration to 20-25 minutes and simplified the Review and Final Submission page by removing the visible completion summary.
- Updated the Completion page visible identifier label from `Participant ID` to `Study ID`.
- Aligned documentation with the frozen experimental design.
- Documented required comment behaviour for every mix version.
- Documented estimated study duration and target sample sizes.
- Documented 30 required mix comments per participant.
- Documented confirmed response-time recording.
- Documented five-year data retention period, subject to final QMUL requirements.
- Documented retention start point, deletion or archival procedure, and responsible data custodian as remaining TBC items.
- Documented participant-material handling requirements for approved PIS and consent files.
- Documented the specified demographic and post-task questionnaire fields.
- Updated roadmap to reflect approved PIS and consent files now present under participant materials.
- Implemented shared progress, navigation, timing, validation, and temporary development storage behaviour for the first three pages.
- Refined the Phase 2B.1 shared header layout, removed duplicate persistent study title text, and prepared the header for the QMUL logo image asset.
- Updated the active flow to Landing -> Study Information and Consent -> Listening Setup.
- Redirected deprecated separate Participant Information and Consent pages to the combined page.
- Updated the active implemented flow to Landing -> Study Information and Consent -> Listening Setup -> Audio Screening -> Instructions guard.
- Updated frontend documentation, UI flow, wireframes, study configuration, and roadmap to describe the Listening Setup and Audio Screening placeholder implementation.
- Kept final setup audio, screening stimuli, correct answers, pass threshold, and failure/exclusion behaviour marked TBC.
- Replaced the missing setup-audio placeholder path with temporary development audio for interface testing, with documentation that it is not a final screening or experimental stimulus and must be replaced before pilot or production use.
- Implemented development-only screening scoring with a temporary 2 out of 3 threshold, maximum 2 attempts, retry behaviour, and `productionReady: false`.
- Updated Audio Screening participant-facing terminology from X/A/B labels to Version A, Version B, and Version C labels.
- Replaced invalid duplicated development screening audio with short ABX-style WAV clips generated from non-overlapping DU-H source-audio segments.
- Redesigned Audio Screening so all three screening items appear together on one scrollable page with one final `Submit screening` action.
- Refined the Instructions page example layout to mirror the real Listen, Rate, and Explain trial structure using non-interactive controls.
- Refined the Practice Trial page by removing the duplicate banner, centring the scenario card, adding a realistic practice-only restaurant scenario, replacing setup-test audio with independent practice WAV mixes, and requiring playback of all three practice versions before completion.
- Documented that practice responses are excluded from main analysis and stored under separate `practice.*` temporary keys.
- Documented untouched-slider validation behaviour and required whitespace-sensitive practice comments.
- Documented temporary frontend group assignment, persisted trial-order randomisation, excerpt-order randomisation, and mix-label mapping randomisation.
- Documented that final server-side balanced assignment and production stimuli remain TBC.
- Documented development-only final payload, temporary anonymous session ID, and absence of production backend persistence.
- Documented approved scenario wording insertion and the grouped trial interaction sequence.
- Refined Practice Trial and Experimental Trial layouts to move repeated rating endpoint and comment guidance into shared section-level instructions.
- Refined audio controls to discourage download, playback-speed, picture-in-picture, and remote-playback controls where supported while preserving native play, pause, replay, seek, and volume behaviour.
- Refined Experimental Trial randomisation and display to use adjacent scenario pairs, stable participant-facing Song A/Song B labels, prefix-free scenario titles, and compatibility handling for older development trial orders.
- Refined Post-task Questionnaire wording and listening-device options, and simplified the Completion page by removing the repeated researcher contact section.
- Removed participant-facing development terminology so the interface presents as a polished research study for supervisor review.
- Replaced experimental-trial placeholder audio paths in `frontend/config/stimuli.json` with final neutral frontend WAV paths while preserving participant-facing Song A/Song B and Version A/B/C labels.
- Marked the experimental stimulus configuration as production-ready while keeping full-study deployment, backend submission, screening stimuli, setup audio, and practice content unresolved where appropriate.
