# Study Interface Specification

## Purpose

This document defines the initial requirements for the web-based listening study interface for the MSc dissertation project, *Intent2Control with Controllable Intent Strength*.

The interface will support anonymous participant completion of a contextual listening study in which participants rate different mix versions of music excerpts.

## Scope

The study interface will eventually provide:

- Participant information and consent screens.
- An audio screening test.
- Listening instructions and a practice trial.
- Experimental listening trials.
- Demographic and post-task questionnaires.
- Final submission of anonymous study responses.

This foundation has begun implementing a static framework-free participant interface. It does not implement the final backend, database, final server-side balancing, or secure production data storage.

## Study design

Participants are randomly assigned to one of two experimental groups.

Each participant evaluates:

- Three contextual listening episodes.
- Two assigned music excerpts per episode.
- Three mix versions per excerpt.

This produces:

- Six experimental listening tasks per participant.
- Eighteen mix ratings per participant.
- Six required comparative trial comments per participant.

Each trial contains one music excerpt presented as three mix versions. Mix versions must be shown with neutral labels: Version A, Version B, and Version C.

Participants may replay audio as many times as they wish.

The estimated study duration is 15-20 minutes.

Target sample sizes:

- Main study: approximately 40-50 participants.
- Pilot study: 6-8 participants.

## Participant flow

The intended participant flow is:

1. Landing page.
2. Study Information and Consent.
3. Listening setup.
4. Audio screening.
5. Instructions.
6. Practice trial.
7. Main Study transition.
8. Six experimental listening tasks.
9. Post-task questionnaire.
10. Demographic questionnaire.
11. Review and final submission.
12. Completion page.

The approved Participant Information Sheet and Consent Form remain separate documents, but they are presented through one combined participant-facing web page.

Final participant-facing wording for screens not governed directly by the approved Participant Information Sheet or consent form is TBC.

## Functional requirements

- The interface must guide participants through the study in the required order.
- Participants must not be able to submit experimental data without providing required consent.
- Participants must be assigned to one experimental group.
- The interface must present only the excerpts assigned to the participant's group.
- The interface must display neutral mix labels rather than internal mix identifiers.
- The interface must collect one preference rating for each presented mix.
- The interface must provide one required comparative comment field for each trial.
- The interface must include demographic and post-task questionnaire sections.
- The interface must provide a final review or confirmation step before submission.
- Responses must be stored anonymously.
- The interface must record response-time timestamps.

## Randomisation requirements

- Participants must be randomly assigned to one of two experimental groups.
- Group assignment must be recorded without direct identifiers.
- The mapping between Version A, Version B, Version C, and the real mix identifiers must be controlled by the application.
- Any randomisation strategy for ordering scenarios, excerpts, or mix versions is TBC.
- Whether randomisation should be balanced across participants is TBC.

## Audio requirements

- Audio stimuli must be served reliably through the study interface.
- Audio playback must be repeatable during trials, with no fixed replay limit.
- Audio files must not be committed to Git unless explicitly cleared for repository storage.
- The final audio format, loudness preparation, duration, and normalisation policy are TBC.
- The setup test-audio file, exact screening-test stimuli, correct answers, and pass rule are TBC.
- Detailed audio playback-event logging remains TBC and must be treated separately from response-time collection.

## Rating and comment requirements

- Each mix must be rated using a continuous 0-100 preference scale.
- The scale endpoints and any midpoint label are TBC.
- Each trial must have one associated required comparative comment field covering all displayed mix versions.
- A participant cannot proceed from a trial until all three ratings and the comparative comment are completed.
- Empty or whitespace-only comments must not be accepted.
- The minimum meaningful response threshold is TBC.

## Response-time requirements

- Response-time collection is confirmed.
- Timing must be recorded at least at study start, page entry, page exit or completion, trial start, trial submission, and final submission.
- Exact technical timing fields may be refined during implementation.
- Response duration should be derived from recorded timestamps.
- Detailed audio playback-event logging remains TBC and must not be treated as the same feature as response-time collection.

## Data protection requirements

- Responses must be anonymous.
- The system must not collect names, email addresses, IP addresses, or other direct identifiers.
- Participant data, local databases, exported datasets, logs, uploaded files, secrets, and research audio must not be committed to Git.
- The data retention period is five years.
- The five-year period must remain consistent with the final approved QMUL Participant Information Sheet, consent documentation, and institutional policy.
- The retention start point is TBC.
- The deletion or archival procedure is TBC.
- The responsible data custodian is TBC.
- The final storage location and access controls must be confirmed with QMUL.

## Participant materials requirements

- The final Participant Information Sheet and consent form already exist.
- Approved Participant Information Sheet and consent files belong under `docs/participant-materials/`.
- Participant-facing PDF copies belong under `frontend/assets/documents/`.
- The approved documents are the authoritative source for participant-facing wording.
- Participant-facing interface text must be checked against those documents before implementation.
- Changes to approved wording must not be made silently.

## Demographic questionnaire requirements

The demographic questionnaire must include:

- Age range.
- Gender, optional.
- Country that most influenced the participant's musical and cultural background.
- Music listening habits.
- Music production or audio engineering experience.
- Hearing difficulty.

Final response options are TBC.

## Post-task questionnaire requirements

The post-task questionnaire must include:

- Ability to immerse in the scenarios.
- Task difficulty.
- Prior familiarity with the excerpts.
- Headphones or earphones used.
- Location or environment where the study was completed.
- Additional comments.

Final response options are TBC.

## Accessibility requirements

- The interface should be usable with keyboard navigation.
- Form controls should have clear labels.
- Visual progress information should not be the only cue for study state.
- Text contrast should be sufficient for comfortable reading.
- Audio-related requirements for participants with hearing differences are TBC.

## Reliability requirements

- The interface should avoid data loss during ordinary navigation.
- The system should validate required fields before final submission.
- The system should handle interrupted or failed submissions gracefully.
- Whether partial progress should be saved server-side is TBC.
- Response-time collection is confirmed.
- Whether detailed playback events will be collected is TBC.

## Deployment constraints

- The application must eventually be deployable on QMUL-managed infrastructure.
- The final hosting technology has not yet been confirmed.
- The deployment must support HTTPS.
- The deployment must support secure server-side processing and data storage.
- The deployment must keep configuration and secrets outside source control.

## Open decisions

- QMUL hosting environment: TBC.
- Supported backend language: TBC.
- Database availability: TBC.
- HTTPS configuration: TBC.
- Server access method: TBC.
- Retention start point: TBC.
- Deletion or archival procedure: TBC.
- Responsible data custodian: TBC.
- Exact setup test-audio file: TBC.
- Exact screening-test stimuli, correct answers, and pass rule: TBC.
- Final demographic response options: TBC.
- Whether detailed playback events will be collected: TBC.
