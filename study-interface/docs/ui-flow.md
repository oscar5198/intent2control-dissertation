# UI Flow

This document describes the intended screen sequence for the listening study interface. It is not final participant-facing copy.

## Screen sequence

1. Landing page.
2. Study Information and Consent.
3. Eligibility and listening setup.
4. Audio screening.
5. Instructions.
6. Practice trial.
7. Ten experimental trials.
8. Demographic questionnaire.
9. Post-task questionnaire.
10. Review and final submission.
11. Completion page.

## Landing page

The landing page will introduce the study route and provide entry into the participant flow. Final text is TBC.

## Study Information and Consent

This combined screen provides links to the approved Participant Information Sheet and Consent Form, collects PIS acknowledgement, and collects a single required Consent Form acknowledgement confirming that the participant has read and agrees to the consent statements contained in the PDF.

The participant cannot continue until the PIS and consent documents have each been opened at least once, the PIS acknowledgement is checked, and the Consent Form acknowledgement is checked.

## Eligibility and listening setup

This screen confirms the participant's listening setup before screening. It reminds participants to use headphones or earphones, choose a quiet environment, and set a comfortable device volume. The implemented placeholder requires the setup test audio to be played at least once and requires the three setup confirmations before continuing.

The setup test audio path is currently `frontend/assets/audio/setup-test-development.mp3`. This is temporary development audio and must be replaced before pilot or production use. If the configured file is absent or fails to load, progression is blocked and a warning is shown.

## Audio screening

This screen presents the configured audio screening structure using `frontend/config/screening.json`. The current development-only implementation supports three matching items using participant-facing labels Version A, Version B, and Version C. Each item requires all three versions to be played and asks which version matches Version A.

For development testing only, the temporary threshold is 2 out of 3, retry is enabled, and the maximum attempt count is 2. The temporary stimuli are duplicated `DU-H.mp3` assets under `frontend/assets/audio/screening-development/`; they are not final validated screening stimuli. The configuration is marked `productionReady: false`. Final screening stimuli, threshold, attempts policy, failure/exclusion behaviour, and production retry policy remain TBC. The development bypass is disabled by default and must not be enabled in production.

## Instructions

This screen explains the task structure before the practice trial and experimental trials. It tells participants that they will read scenarios, imagine themselves in the situation, listen to Version A, Version B, and Version C, replay freely, rate each version on the 0-100 preference scale, and provide one required comment per version.

The participant cannot continue until the acknowledgement `I understand how to complete the listening task.` is checked. This acknowledgement is stored separately from consent and practice responses.

## Practice trial

The practice trial allows participants to try the rating and playback interface before the experimental trials. It is clearly labelled as practice and states that responses are not included in the main analysis.

The current practice trial is development-only and configured by `frontend/config/practice.json` with `productionReady: false`. It uses temporary scenario wording, a temporary practice excerpt, neutral labels Version A, Version B, and Version C, and temporary audio copied from existing development assets. Final practice wording and audio remain TBC.

Practice uses the same grouped layout as the experimental trials: Listen to the versions, Rate the versions, then Explain your ratings. All three practice sliders must be deliberately interacted with; the default visual slider position does not count as a response. All three comments are required, and whitespace-only comments are invalid. Practice data is stored only under `practice.*` temporary keys and must not be mixed with main experimental responses. Practice audio playback is currently not required for completion; whether to require playback remains configurable/TBC.

## Experimental trials

The experimental section contains:

- Five contextual listening scenarios.
- Two excerpts in each scenario.
- Three mix versions for each excerpt.
- Ten total trials.
- Thirty mix ratings in total.
- Thirty required mix comments in total.
- Neutral version labels: Version A, Version B, and Version C.
- Repeatable audio playback with no fixed replay limit.
- One 0-100 rating per mix.
- One required comment field per mix.
- A progress display.

The interface should avoid showing real mix identifiers to participants. Display labels must remain neutral.

A participant cannot proceed from a trial until all three ratings and all three associated comments are completed. Empty or whitespace-only comments must not be accepted. The minimum meaningful response threshold is TBC.

The implemented trial page is driven by `frontend/config/stimuli.json`, which is marked `productionReady: true` for experimental stimuli only. Approved scenario titles and wording are inserted in `frontend/config/scenarios.json` and `frontend/config/stimuli.json`. Scenario prefixes such as EDR-1 and FM-2 remain internal only and must not be shown in participant-facing trial titles. Final excerpt names, mix identities, production audio files, and group allocation provenance are documented for researchers in `docs/final-stimuli-manifest.md` and must not be shown in participant-facing trial pages.

The trial interaction sequence is grouped as Listen to the versions, Rate the versions, then Explain your ratings. Desktop layouts present the three Version A/B/C audio controls, rating controls, and comment controls in grouped grids where space allows; tablet layouts may wrap to two columns; mobile stacks controls vertically without horizontal scrolling.

It assigns one of two groups using temporary frontend randomness, persists the assignment, maps the group's two assigned excerpts to stable participant-facing labels `Song A` and `Song B`, generates ten trials from five scenarios and the two songs assigned to the participant's group, and persists the generated order. Every scenario appears exactly twice and both assigned songs appear once within each scenario.

Trial generation randomises the five-scenario order once per participant. Within each scenario, the order of Song A and Song B may be randomised, but both song trials must remain adjacent before the participant moves to another scenario. Older unsubmitted development trial orders may be regenerated into this grouped scenario-pair structure; older submitted development sessions must be preserved and shown with a warning to start a fresh session for randomisation testing.

For each generated trial, three actual mix IDs are independently randomly mapped to neutral labels Version A, Version B, and Version C. The neutral labels are shown to participants; actual mix IDs are stored internally for analysis and are not displayed. Current audio paths are temporary development placeholders and must be replaced before pilot use.

A participant cannot submit an experimental trial until Version A, Version B, and Version C have each successfully started playback, all three sliders have been deliberately interacted with, and all three comments contain non-whitespace text. Full playback is not required. Only one version should play at a time.

Trial 1 allows Back to Practice. Back is hidden/disabled from later trials to avoid accidental editing of submitted trials or corruption of timing/randomisation state. Submitted trial records are append-once by trial index; refresh restores the current unsubmitted trial and unsaved current-trial responses without duplicating completed records.

Response-time recording is confirmed. Trial timing must include trial start and trial submission timestamps. Detailed audio playback-event logging remains TBC.

## Demographic questionnaire

This screen collects anonymous demographic responses for age range, optional gender, nationality, music listening habits, music production or audio engineering experience, and hearing difficulty. Age range, nationality, music listening habits, production/audio experience, and hearing difficulty are required. Gender is optional.

The current implementation uses structured development response options from `frontend/config/questionnaires.json`. Final response-option wording remains TBC and must be checked before pilot use.

## Post-task questionnaire

This screen collects post-task feedback on ability to immerse in the scenarios, task difficulty, prior familiarity with the songs, listening device used, location or environment where the study was completed, and additional comments. Additional comments are optional. The other current post-task fields are required.

The current implementation uses structured development response options from `frontend/config/questionnaires.json`. Final response-option wording remains TBC.

## Review and final submission

This screen allows participants to confirm final submission. It shows only a concise completion summary: consent, listening setup, screening, instructions, practice, ten experimental trials, demographics, and post-task questionnaire. It must not display all ratings, comments, or real mix mappings.

Final submission creates a temporary local development payload and marks the session as submitted. The payload is not production persistence and is not sent to a backend. Backend submission remains TBC.

## Completion page

This screen thanks the participant, shows the anonymous development session ID, states that responses have been recorded in the current study session, and tells the participant they may close the browser window. It must not claim secure QMUL submission until production backend submission exists. Contact information remains available in the approved Participant Information Sheet and is not repeated on the completion page.

## Development-only helpers

An optional trial-completion helper can create placeholder ratings, comments, playback states, first-play timestamps, trial start timestamps, and trial submission timestamps for remaining experimental trials. It preserves the generated group assignment, trial order, and mix-label mappings. It is disabled by default, hidden unless explicit frontend development mode is enabled, requires an explicit second button selection before use, and must never appear in production.
