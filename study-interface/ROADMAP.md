# Roadmap

## Phase 1 - Requirements and project foundation

- [x] Create `study-interface/` repository structure.
- [x] Add initial documentation.
- [x] Align documentation with frozen study protocol.
- [x] Add frozen study configuration document.
- [x] Confirm comment requirement.
- [x] Confirm response-time collection.
- [x] Confirm five-year data retention period.
- [x] Create participant-materials directory.
- [x] Add approved Participant Information Sheet.
- [x] Add approved consent form.
- [ ] Verify Participant Information Sheet transcription.
- [ ] Verify consent transcription.
- [ ] Check interface wording against approved Participant Information Sheet.
- [ ] Check interface wording against approved consent form.
- [ ] Confirm QMUL hosting environment and deployment constraints.

## Phase 2 - Static participant flow

- [x] Create framework-free frontend architecture.
- [x] Add multi-page HTML shell structure.
- [x] Add CSS architecture files.
- [x] Add JavaScript responsibility placeholders.
- [x] Add JSON configuration placeholders.
- [x] Implement Phase 2B.1 landing page.
- [x] Combine Participant Information Sheet and consent form into one active page.
- [x] Add participant-facing PIS and consent PDF assets.
- [x] Redirect deprecated separate PIS and consent pages.
- [x] Implement Listening Setup page with setup confirmations and placeholder audio gate.
- [x] Implement configuration-driven development Pre-Study Listening Task page.
- [x] Implement Instructions page with required task acknowledgement.
- [x] Implement development Practice Trial page.
- [x] Implement development Experimental Trial page.
- [x] Insert approved experimental scenario wording.
- [x] Refine Practice and Experimental Trial layout to grouped Listen, Rate, Explain sections.
- [x] Replace separate rating sliders with shared multi-marker preference scale for Practice and Main Study.
- [x] Add temporary frontend group assignment.
- [x] Add persisted ten-trial generation.
- [x] Refine ten-trial generation to preserve adjacent scenario pairs.
- [x] Add stable participant-facing Song A and Song B excerpt labels.
- [x] Add persisted Version A, Version B, and Version C mix mapping.
- [x] Integrate final experimental audio stimuli.
- [x] Implement Demographic Questionnaire page.
- [x] Implement Post-task Questionnaire page.
- [x] Implement Review and Final Submission page.
- [x] Implement Completion page.
- [x] Add navigation between implemented study screens.
- [x] Build remaining static screen sequence.
- [x] Add navigation between all remaining study screens.
- [x] Add review completion summary.

## Phase 3 - Pre-study listening task and practice

- [x] Implement initial Pre-Study Listening Task flow scaffold.
- [x] Add temporary development pre-study listening stimuli.
- [x] Audit and replace invalid duplicated development pre-study listening stimuli.
- [x] Present all development pre-study listening items on one page.
- [x] Implement temporary development pre-study listening pass, fail, and retry paths.
- [x] Prepare six-item two-segment by three-repetition structure with persisted randomised order.
- [x] Hide numerical score feedback from participants while preserving internal scoring.
- [x] Implement shared reset-on-switch comparative playback behaviour.
- [x] Prevent seeking and individual player-volume changes in comparative listening controls.
- [ ] Add final pre-study listening stimuli.
- [ ] Define final pre-study pass rule.
- [ ] Confirm pre-study retry and failure/exclusion behaviour.
- [ ] Confirm Brecht preference-based segment-selection criteria and results.
- [x] Implement practice trial.
- [ ] Replace development practice content before pilot.

## Phase 4 - Experimental trial system

- [x] Implement temporary frontend group assignment.
- [ ] Replace temporary frontend group assignment with final server-side balanced assignment.
- [x] Implement scenario and excerpt presentation.
- [x] Hide internal scenario prefixes from participant-facing trial titles.
- [x] Implement Version A, Version B, and Version C display labels.
- [x] Implement shared 0-100 rating controls.
- [x] Implement required comment fields.
- [x] Require successful playback start for Version A, Version B, and Version C before trial submission.
- [x] Implement response-time recording for experimental trials.
- [x] Store submitted trial records separately from practice responses.
- [x] Replace development experimental stimuli before pilot.

## Phase 5 - Demographics and final submission

- [x] Implement demographic questionnaire.
- [x] Implement post-task questionnaire.
- [x] Implement review and final submission page.
- [x] Implement completion page.
- [x] Add temporary anonymous development session ID.
- [x] Add temporary local development payload.
- [ ] Replace local development payload with production backend submission.

## Phase 6 - Backend and secure data storage

- [ ] Select backend technology.
- [ ] Select database technology.
- [ ] Implement secure anonymous response storage.
- [ ] Implement protected administration or export method.

## Phase 7 - Testing and pilot study

- [ ] Replace temporary development setup audio before pilot.
- [ ] Test participant flow.
- [ ] Test audio playback.
- [ ] Test data validation and storage.
- [ ] Run pilot study.

## Phase 8 - QMUL deployment

- [ ] Confirm hosting environment.
- [ ] Configure HTTPS.
- [ ] Deploy to QMUL-managed infrastructure.
- [ ] Verify external participant access.

## Phase 9 - Study freeze and data collection

- [ ] Freeze study version.
- [ ] Lock participant-facing materials.
- [ ] Begin data collection.
