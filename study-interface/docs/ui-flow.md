# UI Flow

This document describes the intended screen sequence for the listening study interface. It is not final participant-facing copy.

## Screen sequence

1. Landing page.
2. Study Information and Consent.
3. Eligibility and listening setup.
4. Pre-Study Listening Task.
5. Instructions.
6. Practice trial.
7. Main Study transition.
8. Ten main study listening tasks.
9. Post-task questionnaire.
10. Demographic questionnaire.
11. Review and final submission.
12. Completion page.

## Landing page

The landing page will introduce the study route and provide entry into the participant flow. Final text is TBC.

## Study Information and Consent

This combined screen provides links to the approved Participant Information Sheet and Consent Form, collects PIS acknowledgement, and collects a single required Consent Form acknowledgement confirming that the participant has read and agrees to the consent statements contained in the PDF.

The participant cannot continue until the PIS and consent documents have each been opened at least once, the PIS acknowledgement is checked, and the Consent Form acknowledgement is checked.

## Eligibility and listening setup

This screen confirms the participant's listening setup before the study. It reminds participants to use headphones or earphones, choose a quiet environment, and set a comfortable device volume. The implemented placeholder requires the setup test audio to be played at least once and requires the three setup confirmations before continuing.

The setup test audio path is currently `frontend/assets/audio/setup-test-development.mp3`. This is temporary development audio and must be replaced before pilot or production use. If the configured file is absent or fails to load, progression is blocked and a warning is shown.

## Pre-Study Listening Task

This screen presents the configured pre-study listening structure using `frontend/config/screening.json`. The current development-only implementation supports six ABX-style matching presentations using participant-facing labels Reference, Version A, and Version B. The six presentations are generated from two internal segment identities, with each segment repeated three times. Presentation order is randomised once per attempt and persisted so refresh does not reshuffle the task. Each item requires the Reference, Version A, and Version B to be played and asks: **Which of A or B matches the Reference?**

The current development audio alignment audit found that the matching pair inside each current item is sample-identical and aligned, while the non-matching option is a different musical segment. No audio correction has been made because the final two segment/song selections and scientific selection criteria remain TBC. Internal scoring remains stored for inclusion/exclusion analysis, but participant-facing numerical score feedback is hidden. For development testing only, the temporary threshold remains configured as 2, retry is enabled, and the maximum attempt count is 2. The configuration is marked `productionReady: false`. Final validated pre-study stimuli, scientific pass criteria, attempts policy, failure/exclusion behaviour, and production retry policy remain TBC. The development bypass is disabled by default and must not be enabled in production.

## Instructions

This screen explains the task structure before the Practice Trial and main study listening tasks. It tells participants that they will read scenarios, imagine themselves in the situation, listen to Version A, Version B, and Version C, replay freely, place the three version markers on one shared 0-100 preference scale, and provide one required comment per version.

The participant cannot continue until the acknowledgement `I understand how to complete the listening task.` is checked. This acknowledgement is stored separately from consent and practice responses.

## Practice trial

The practice trial allows participants to try the rating and playback interface before the main study listening tasks. It is clearly labelled as practice and states that responses are not included in the main analysis.

The current practice trial is configured by `frontend/config/practice.json` with `productionReady: false`. It uses the practice-only Dinner Date scenario, a real unused Mix Evaluation Dataset song excerpt, and neutral labels Version A, Version B, and Version C. Supervisor approval for the practice scenario and practice audio remains TBC.

Practice uses the same marker-based layout as the main study listening tasks: click or tap Version A, Version B, and Version C markers to play each version from 0:00, drag each marker to set its preference rating, then explain the ratings. Empty scale clicks do nothing, and one shared Stop audio button stops the active version without changing ratings. All three practice audio versions must be played, all three practice markers must be deliberately positioned, and the default visual marker position does not count as a response. All three comments are required, and whitespace-only comments are invalid. Practice data is stored only under `practice.*` temporary keys and must not be mixed with main experimental responses.

## Main Study transition

After a valid Practice Trial submission, participants are routed to `frontend/pages/main-study.html` before any experimental response is collected. This transition page confirms that the Practice Trial has finished and that the following listening tasks are part of the main study. Its primary action, `Begin Main Study`, routes to the first experimental listening task.

Direct navigation to the Main Study transition is blocked unless the Practice Trial has been completed. Direct navigation to the first listening task also remains blocked until practice completion.

## Main study listening tasks

The main study section contains:

- Five contextual listening scenarios.
- Two excerpts in each scenario.
- Three mix versions for each excerpt.
- Ten total listening tasks.
- Thirty mix ratings in total.
- Thirty required mix comments in total.
- Neutral version labels: Version A, Version B, and Version C.
- Repeatable audio playback with no fixed replay limit.
- One 0-100 rating per mix.
- One required comment field per mix.
- A progress display.

The interface should avoid showing real mix identifiers to participants. Display labels must remain neutral.

A participant cannot proceed from a trial until all three ratings and all three associated comments are completed. Empty or whitespace-only comments must not be accepted. The minimum meaningful response threshold is TBC.

The implemented listening-task page is driven by `frontend/config/stimuli.json`, which is technically integrated for the current experimental stimuli but marked `productionReady: false` while perceptual approval is pending. Approved scenario titles and wording are inserted in `frontend/config/scenarios.json` and `frontend/config/stimuli.json`. Scenario prefixes such as EDR-1 and FM-2 remain internal only and must not be shown in participant-facing listening-task titles. Final excerpt names, mix identities, production audio files, and group allocation provenance are documented for researchers in `docs/final-stimuli-manifest.md` and must not be shown in participant-facing pages.

The trial interaction sequence uses the Version A/B/C markers as the playback controls and rating controls. Clicking or tapping a marker plays that version from 0:00 without changing the rating. Dragging a marker changes only that marker's rating. Empty scale clicks do nothing. Desktop layouts present one horizontal shared rating scale with three draggable markers, one shared Stop audio button, rating/playback status values, and grouped comment boxes. Mobile keeps the shared-rating concept by switching the scale to a vertical orientation without horizontal scrolling.

It assigns one of two groups using temporary frontend randomness, persists the assignment, maps the group's two assigned excerpts to stable participant-facing labels `Song A` and `Song B`, generates ten listening tasks from five scenarios and the two songs assigned to the participant's group, and persists the generated order. Every scenario appears exactly twice and both assigned songs appear once within each scenario.

Trial generation randomises the five-scenario order once per participant. Within each scenario, the order of Song A and Song B may be randomised, but both song listening tasks must remain adjacent before the participant moves to another scenario. Older unsubmitted development trial orders may be regenerated into this grouped scenario-pair structure; older submitted development sessions must be preserved and shown with a warning to start a fresh session for randomisation testing.

For each generated trial, three actual mix IDs are independently randomly mapped to neutral labels Version A, Version B, and Version C. The neutral labels are shown to participants; actual mix IDs are stored internally for analysis and are not displayed. Current experimental audio paths point to the integrated rating-stratified WAV files, but perceptual approval is still pending.

A participant cannot submit a main study listening task until Version A, Version B, and Version C have each successfully started playback, all three shared-scale markers have been deliberately positioned, and all three comments contain non-whitespace text. Full playback is not required. Only one version should play at a time. Marker playback always starts from 0:00, while the shared Stop audio button stops and resets the active version without clearing played-state validation.

Listening Task 1 allows Back to the Main Study transition page. Back is hidden/disabled from later listening tasks to avoid accidental editing of submitted trials or corruption of timing/randomisation state. Submitted trial records are append-once by trial index; refresh restores the current unsubmitted trial and unsaved current-trial responses without duplicating completed records.

Response-time recording is confirmed. Trial timing must include trial start and trial submission timestamps. Detailed audio playback-event logging remains TBC.

## Post-task questionnaire

This screen collects post-task feedback on ability to immerse in the scenarios, task difficulty, prior familiarity with the songs, listening device used, location or environment where the study was completed, and additional comments. Additional comments are optional. The other current post-task fields are required.

The agreement-scale question uses a horizontal Strongly disagree to Strongly agree layout where space allows. The listening-device and completion-location questions omit `Prefer not to say`; selecting `Other` reveals a required detail field, and choosing another option clears that detail response.

The current implementation uses structured development response options from `frontend/config/questionnaires.json`. Final response-option wording remains TBC.

## Demographic questionnaire

This screen collects anonymous demographic responses for age range, optional gender, country that most influenced musical and cultural background, music listening habits, music production or audio engineering experience, and hearing difficulty. Age range, cultural influence country, music listening habits, production/audio experience, and hearing difficulty are required. Gender is optional.

The current implementation uses structured development response options from `frontend/config/questionnaires.json`. Final response-option wording remains TBC and must be checked before pilot use.

## Review and final submission

This screen allows participants to confirm final submission after consent, listening setup, screening, instructions, practice, ten main study listening tasks, post-task questionnaire, and demographic questionnaire are complete. It must not display all ratings, comments, or real mix mappings.

Final submission creates a temporary local development payload and marks the session as submitted. The payload is not production persistence and is not sent to a backend. Backend submission remains TBC.

## Completion page

This screen thanks the participant, shows the anonymous development session ID, states that responses have been recorded in the current study session, and tells the participant they may close the browser window. It must not claim secure QMUL submission until production backend submission exists. Contact information remains available in the approved Participant Information Sheet and is not repeated on the completion page.

## Development-only helpers

An optional trial-completion helper can create placeholder ratings, comments, playback states, first-play timestamps, trial start timestamps, and trial submission timestamps for remaining main study listening tasks. It preserves the generated group assignment, trial order, and mix-label mappings. It is disabled by default, hidden unless explicit frontend development mode is enabled, requires an explicit second button selection before use, and must never appear in production.
