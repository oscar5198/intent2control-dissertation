# Study Interface

This folder contains the foundation for a web-based listening study interface for the MSc dissertation project, *Intent2Control with Controllable Intent Strength*.

The interface will support a contextual listening study in which anonymous participants compare and rate music mix versions. It currently contains the documentation foundation and the early framework-free frontend scaffold.

## Dissertation context

The wider dissertation investigates semantic audio control: mapping natural-language mixing intentions to audio processing parameters such as equalisation, compression, and reverberation. This study interface will be used to collect listening preference data for evaluating mix versions in contextual scenarios.

## High-level participant flow

The intended participant flow is:

1. Landing page.
2. Study Information and Consent.
3. Listening setup.
4. Audio screening.
5. Instructions.
6. Practice trial.
7. Ten experimental trials.
8. Demographic questionnaire.
9. Post-task questionnaire.
10. Review and final submission.
11. Completion page.

## Experimental structure

Participants are randomly assigned to one of two experimental groups.

Each group evaluates two music excerpts across five contextual listening scenarios. Each scenario contains both assigned excerpts, producing ten experimental trials per participant.

Each trial contains one music excerpt presented as three mix versions. These mixes are shown to participants using neutral labels: Version A, Version B, and Version C. Each mix is rated using a continuous 0-100 preference scale, with a required comment field. Participants may replay audio as many times as they wish.

The estimated study duration is 15-20 minutes. The main-study target sample is approximately 40-50 participants, with a pilot-study target sample of 6-8 participants.

## Frozen Experimental Design

- Two experimental groups.
- Two music excerpts per group.
- Five contextual listening scenarios.
- Ten experimental trials per participant.
- Three mix versions per trial.
- Thirty mix preference ratings per participant.
- Thirty required mix comments per participant.

## Participant Materials

The approved Participant Information Sheet and consent form are stored under `docs/participant-materials/`. Participant-facing PDF copies are stored under `frontend/assets/documents/`. Those approved documents are the authoritative source for participant-facing wording. Interface text must continue to be checked against them before final release.

## Hosting and backend status

The final hosting and backend technology are still to be confirmed with QMUL. The application must eventually be deployable on QMUL-managed infrastructure, but no framework, package manager, backend, or database has been selected yet.

## Repository safety

Do not commit:

- Participant data.
- Audio stimuli.
- Secrets or real environment files.
- Local databases.
- Exported datasets.
- Logs or uploaded files.

Research audio may not be licensed for public distribution, so files inside `frontend/assets/audio/` are ignored except for `.gitkeep`.

## Current status

Current status: Phase 2B frontend scaffold.

Implemented participant-facing pages currently cover the landing page, combined Study Information and Consent page, Listening Setup page, and Audio Screening placeholder flow. Later pages remain shells. No backend, generated participant data, real audio files, real credentials, or deployment configuration have been added.
