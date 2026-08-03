# Conceptual Data Model

This document describes a technology-independent data model for the listening study interface. It does not choose a database system or backend framework.

The final implementation must avoid direct identifiers such as names, email addresses, IP addresses, or other information that could directly identify participants.

## Anonymous participant ID

Each participant session should use an anonymous participant ID.

Proposed readable format:

```text
p_YYYYMMDD_randomtoken
```

Example:

```text
p_20260721_q8x4m2k9
```

The final implementation must generate IDs using a cryptographically secure random source. The example above is illustrative only.

The Phase 2B frontend also creates a temporary anonymous development session ID under `session.developmentId`. This ID is generated with browser crypto where available, persists across refresh, does not embed names or contact details, and is not a final server-issued participant ID.

## Entities

## Participant session

Represents one anonymous participant's progress through the study.

Suggested fields:

- Anonymous participant ID.
- Created timestamp.
- Overall study start timestamp.
- Current study state.
- Completion status.
- Assigned group reference.

## Consent record

Records consent decisions without direct identifiers.

Suggested fields:

- Anonymous participant ID.
- Consent version.
- Consent item responses.
- Consent timestamp.

## Screening attempt

Records the audio screening outcome.

Suggested fields:

- Anonymous participant ID.
- Attempt number.
- Screening stimuli references.
- Responses.
- Pass or fail result.
- Timestamp.

## Group assignment

Records which experimental group the participant was assigned to.

Suggested fields:

- Anonymous participant ID.
- Group identifier.
- Assignment timestamp.
- Assignment method or randomisation batch, if required.

The Phase 2B frontend uses temporary persisted frontend assignment only. Final server-side balanced assignment remains TBC.

## Trial

Represents one experimental trial for a participant.

Suggested fields:

- Anonymous participant ID.
- Trial index.
- Scenario identifier.
- Excerpt identifier.
- Group identifier.
- Trial start timestamp.
- Trial submission timestamp.
- Trial response duration derived from timestamps.
- Trial status.
- Submitted version responses.

Phase 2B stores one submitted trial record per trial index under temporary development storage. The record includes group ID, scenario ID, excerpt ID, trial start timestamp, trial submission timestamp, derived duration, and the three version responses.

## Mix presentation

Represents one mix version shown within a trial.

Suggested fields:

- Anonymous participant ID.
- Trial index.
- Display label, such as Version A.
- Real mix identifier.
- Presentation order.
- Audio asset reference.
- Audio played state.
- First-play timestamp.

Display labels such as Version A, Version B, and Version C must be stored separately from real mix identifiers. This allows neutral participant-facing labels while preserving analysis-ready mappings.

The participant-facing interface must consistently show Version A, Version B, and Version C. Actual mix IDs must not be displayed to participants.

The final experimental stimuli are configured in `frontend/config/stimuli.json` and documented for researchers in `docs/final-stimuli-manifest.md`. Participant-facing trial screens must continue to show only `Music excerpt: Song A` or `Music excerpt: Song B` plus neutral Version A/B/C labels, while response records preserve the internal mix IDs and neutral frontend audio paths needed for analysis.

The active Main Study stimulus configuration version is stored in `frontend/config/stimuli.json` as `stimulusConfigurationVersion`. Persisted local trial orders include this version so outdated development mappings can be detected after a stimulus update.

## Rating

Represents a participant's preference rating for one mix presentation.

Suggested fields:

- Anonymous participant ID.
- Trial index.
- Display label.
- Rating value from 0 to 100.
- Submitted timestamp.

The participant-facing Practice Trial and Main Study interface may collect these values through one shared multi-marker preference scale, but the stored semantics remain unchanged: each Version A/B/C presentation has exactly one integer 0-100 rating.

## Participant comment

Represents the participant's required comment associated with one mix rating.

Suggested fields:

- Anonymous participant ID.
- Trial index.
- Display label.
- Comment text.
- Submitted timestamp.

Comments are required for every mix version. Empty or whitespace-only comments must not be accepted. The minimum meaningful response threshold is TBC.

## Experimental response record

Represents the current Phase 2B submitted-trial structure.

Suggested fields:

- Anonymous participant ID in the final backend implementation.
- Group identifier.
- Trial index.
- Scenario identifier.
- Excerpt identifier.
- Neutral display label.
- Actual mix identifier.
- Audio path.
- Final experimental stimulus manifest reference, where needed for researcher-side analysis.
- Stimulus configuration version.
- Rating value from 0 to 100.
- Required comment text.
- Audio played state.
- First-play timestamp.
- Trial start timestamp.
- Trial submission timestamp.
- Derived trial duration.

Practice responses must remain separate from experimental responses and must be excluded from analysis.

## Page timing

Represents timing for study screens.

Suggested fields:

- Anonymous participant ID.
- Page identifier.
- Page entry timestamp.
- Page completion timestamp.
- Page response duration derived from timestamps.

Response-time collection is confirmed. Detailed audio playback-event logging remains TBC and should be modelled separately if it is later approved.

## Demographic response

Represents anonymous demographic questionnaire responses.

Suggested fields:

- Anonymous participant ID.
- Question identifier.
- Response value.
- Submitted timestamp.

The demographic questionnaire currently includes age range, optional gender, country that most influenced musical and cultural background, music listening habits, music production or audio engineering experience, and hearing difficulty. Final response options are TBC.

## Post-task response

Represents post-task questionnaire responses.

Suggested fields:

- Anonymous participant ID.
- Question identifier.
- Response value.
- Submitted timestamp.

The post-task questionnaire currently includes ability to immerse in the scenarios, task difficulty, prior familiarity with the songs, listening device used, location or environment where the study was completed, and additional comments. The listening-device and completion-location fields store the selected option as `other` when applicable and store the accompanying required detail in companion detail fields. Final response options are TBC.

## Final submission

Represents the participant's final submission event.

Suggested fields:

- Anonymous participant ID.
- Submission timestamp.
- Final submission timestamp.
- Submission status.
- Study version.
- Consent version.

## Temporary development payload

Represents the Phase 2B local-only payload used to test the complete frontend flow before production backend storage exists.

Suggested fields:

- Development session ID.
- Study version.
- Timing values.
- Consent states.
- Listening setup states.
- Screening attempts and result.
- Instruction acknowledgement.
- Practice completion metadata.
- Group assignment.
- Generated trial order.
- Mix-label mappings.
- Submitted experimental responses.
- Demographic responses.
- Post-task responses.
- Final submission timestamp.

This payload is not production-safe persistence and must not replace backend storage. It must not intentionally include names, email addresses, IP addresses, browser fingerprints, exact geolocation, or other direct identifiers.

## Excluded data

The model must not include:

- Names.
- Email addresses.
- Postal addresses.
- Phone numbers.
- IP addresses.
- Student numbers.
- Free-text fields that request direct identifiers.
