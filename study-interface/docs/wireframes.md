# Wireframes

This document designs the participant-facing screens for the listening study before implementation. It defines structure, content areas, interaction rules, and reusable page patterns only. It does not define HTML, CSS, JavaScript, backend code, or storage logic.

Primary source documents:

- `design-system.md` for visual style, layout, components, accessibility, and interaction tone.
- `specification.md` for study requirements.
- `study-configuration.md` for frozen study structure and totals.
- `ui-flow.md` for participant journey order.
- `participant-materials/PIS-template---April-26.docx` and `participant-materials/Consent-Form-template-April-26.docx` as the authoritative wording sources for the Participant Information Sheet and consent form.

The approved Participant Information Sheet and consent form must be checked again before implementation. The wireframes below intentionally avoid inventing final participant-facing copy where wording remains TBC.

## Overall Participant Journey

```text
[Landing]
    |
    v
[Study Information and Consent]
    |
    v
[Listening Setup]
    |
    v
[Audio Screening]
    |
    v
[Instructions]
    |
    v
[Practice Trial]
    |
    v
[Experimental Trial 1]
    |
    v
[Experimental Trial 2]
    |
    v
  ...
    |
    v
[Experimental Trial 10]
    |
    v
[Demographic Questionnaire]
    |
    v
[Post-task Questionnaire]
    |
    v
[Review and Submit]
    |
    v
[Completion]
```

## Shared Page Frame

All pages should use the same calm academic frame:

- Main background: soft neutral.
- Centred single-column content.
- Maximum width: 820 px for reading/form pages and 960 px for trial/review pages.
- Page title at top.
- Progress indicator near top, except possibly the first landing page.
- Main card or content area.
- Navigation actions at the bottom.
- Visible focus indicators and keyboard-operable controls.

```text
+------------------------------------------------------+
| [QMUL logo placeholder]        Study progress/status  |
+------------------------------------------------------+
|                                                      |
| Page title                                           |
| Short page-specific guidance                         |
|                                                      |
| +--------------------------------------------------+ |
| | Main content / form / trial components           | |
| +--------------------------------------------------+ |
|                                                      |
| [Back]                                  [Continue]   |
+------------------------------------------------------+
```

## 1. Landing Page

### Purpose

Introduce the study, establish trust, communicate basic participation requirements, and let eligible participants begin.

### Components Shown

- QMUL logo placeholder.
- Dissertation/study title.
- Short study description.
- Information banner with estimated duration.
- Setup recommendation list.
- 18+ requirement statement.
- Primary `Start Study` button.

### Information Displayed

- Study title from the approved PIS: `Choosing the Preferred Music Mix for Different Listening Situations - An Online Listening Study`.
- Relationship to MSc dissertation at Queen Mary University of London.
- Estimated duration: 15-20 minutes.
- Recommendation to use headphones or earphones.
- Recommendation to complete the study in a quiet environment.
- Requirement that participants are aged 18 or older.
- Brief note that participation is voluntary, with detailed wording deferred to the PIS.

### Participant Actions

- Read the introductory summary.
- Confirm they are ready to begin by selecting `Start Study`.

### Validation Rules

- No form validation on this page.
- The `Start Study` action records the study start timestamp.

### Navigation

- Forward: `Start Study` to Study Information and Consent.
- Back: none.

### Progress Indicator

- Show either no progress bar or a neutral `Step 1 of 11` indicator.
- Do not imply consent has been given.

### Notes for Implementation

- The QMUL logo should be a placeholder until the approved asset and usage rules are confirmed.
- Keep the page academic and minimal, not promotional.
- Do not collect participant identifiers here.

### ASCII Wireframe

```text
+------------------------------------------------------+
| [QMUL logo placeholder]                              |
+------------------------------------------------------+
|                                                      |
| Choosing the Preferred Music Mix for Different       |
| Listening Situations                                 |
|                                                      |
| Online listening study for an MSc dissertation       |
| at Queen Mary University of London                   |
|                                                      |
| +--------------------------------------------------+ |
| | Estimated time: 15-20 minutes                   | |
| | Recommended: headphones or earphones             | |
| | Recommended: quiet listening environment         | |
| | Requirement: aged 18 or older                    | |
| +--------------------------------------------------+ |
|                                                      |
|                                      [Start Study]   |
+------------------------------------------------------+
```

## 2. Study Information and Consent

### Purpose

Provide access to the approved Participant Information Sheet and Consent Form, collect acknowledgement that the PIS has been read and understood, and collect consent using one checkbox per approved consent statement.

### Components Shown

- Page title: `Study Information and Consent`.
- Participant Information section.
- View and download links for the Participant Information Sheet PDF.
- Concise key-information summary drawn from approved documents.
- Required PIS acknowledgement checkbox.
- Consent section.
- View and download links for the Consent Form PDF.
- One checkbox per approved consent statement.
- Accessible validation summary and inline errors.
- Primary `Continue` button.
- Secondary `Back` button if backward navigation is allowed at this stage.

### Information Displayed

- Relative PDF links to `frontend/assets/documents/participant-information-sheet.pdf` and `frontend/assets/documents/consent-form.pdf`.
- Concise key-information summary drawn from the approved PIS.
- Seven approved consent statements from the approved consent form.

### Participant Actions

- Open the PIS document.
- Optionally download the PIS document.
- Tick: `I have read and understood the Participant Information Sheet.`
- Open the Consent Form document.
- Optionally download the Consent Form document.
- Tick each required consent checkbox.
- Continue to Listening Setup.

### Validation Rules

- Participant cannot continue until the PIS has been opened at least once.
- Participant cannot continue until the PIS acknowledgement checkbox is checked.
- Participant cannot continue until the consent document has been opened at least once.
- All required consent boxes must be checked before continuing.
- No acknowledgement or consent checkbox may be pre-selected.
- If any requirement is missing, show a validation summary and inline errors.

### Navigation

- Forward: to Listening Setup only after all required information and consent items are complete.
- Back: to Landing Page.

### Progress Indicator

- Show `Step 2 of 11 - Study information and consent`.
- Progress text must be readable by screen readers.

### Notes for Implementation

- Do not render the full PIS inside the web page; link to the participant-facing PDF.
- Consent labels must follow the approved consent form wording.
- Do not include signature, printed-name, or date fields because the web study must not collect direct identifiers.

### ASCII Wireframe

```text
+------------------------------------------------------+
| Progress: Step 2 of 11                               |
+------------------------------------------------------+
| Study Information and Consent                        |
|                                                      |
| +------------ Participant Information -------------+ |
| | [View PIS] [Download PIS]                       | |
| | Key information summary                          | |
| | [ ] I have read and understood the PIS           | |
| +--------------------------------------------------+ |
|                                                      |
| +-------------------- Consent ---------------------+ |
| | [View Consent Form] [Download Consent Form]      | |
| | [ ] Consent statement 1                          | |
| | [ ] Consent statement 2                          | |
| | ...                                              | |
| | [ ] Consent statement 7                          | |
| +--------------------------------------------------+ |
|                                                      |
| Validation message area                              |
|                                                      |
| [Back]                                  [Continue]   |
+------------------------------------------------------+
```

Deprecated pages:

- `participant-information.html` redirects to `study-information-consent.html`.
- `consent.html` redirects to `study-information-consent.html`.

## 3. Listening Setup

### Purpose

Prepare participants for the audio screening and main listening task.

### Components Shown

- Page title.
- Information banner with setup reminders.
- Audio playback test component.
- Confirmation status for test audio playback.
- Primary `Continue` button.
- Secondary `Back` button.

### Information Displayed

- Headphone or earphone reminder.
- Quiet environment reminder.
- Device volume reminder.
- Short instruction to play the test audio and adjust volume to a comfortable level.
- No final screening stimuli should be described here.

### Participant Actions

- Read setup reminders.
- Play the test audio.
- Adjust device volume if needed.
- Continue after the test audio has been played.

### Validation Rules

- Continue is disabled until the test audio has been played at least once and all three setup confirmations are checked.
- If the configured setup test audio file is missing or playback fails, show a warning banner and keep progression disabled.

### Navigation

- Forward: to Audio Screening after test audio has been played and all setup confirmations are checked.
- Back: to Study Information and Consent.

### Progress Indicator

- Show `Step 3 of 11 - Listening setup`.

### Notes for Implementation

- Record page entry, page completion, and listening setup completion timestamps.
- Store temporary development-only state for setup test playback and the three setup confirmations.
- Playback-event logging remains TBC; only the gating state for test playback is required for this page.
- The configured setup test audio path is `frontend/assets/audio/setup-test-development.mp3`; this temporary development file must be replaced before pilot or production use and must not reveal experimental material.

### ASCII Wireframe

```text
+------------------------------------------------------+
| Progress: Step 3 of 11                               |
+------------------------------------------------------+
| Listening Setup                                      |
| Prepare your listening environment before screening. |
|                                                      |
| +--------------------------------------------------+ |
| | Use headphones or earphones                      | |
| | Choose a quiet environment                       | |
| | Set a comfortable device volume                  | |
| +--------------------------------------------------+ |
|                                                      |
| Audio playback test                                  |
| +--------------------------------------------------+ |
| | [Play]  Test audio                     [00:00]   | |
| +--------------------------------------------------+ |
|                                                      |
| [ ] Headphones/earphones [ ] Quiet [ ] Volume set     |
|                                                      |
| [Back]                       [Continue disabled]     |
+------------------------------------------------------+
```

## 4. Audio Screening

### Purpose

Check that participants can complete the listening task under suitable audio conditions before entering the study trials.

### Components Shown

- Page title.
- Screening instructions.
- Screening progress indicator.
- Development-only matching audio players for Version A, Version B, and Version C.
- Answer controls.
- Feedback/result area with score after full attempt submission.
- Retry button when attempts remain.
- Primary `Next` action for items 1-2 and `Submit screening` action for item 3.
- Secondary `Back` button only if allowed by protocol.

### Information Displayed

- Instructions for completing the screening test.
- Screening task number or progress: `Question X of 3` for the development implementation.
- Audio player labels that do not reveal stimuli identity.
- Answer options `Version B` and `Version C` in the current development configuration.
- Feedback after submission, according to final screening policy.

### Participant Actions

- Play the screening audio.
- Select or enter an answer.
- Submit the answer.
- Retry if permitted by final screening policy.
- Continue after passing the screening test.

### Validation Rules

- Participant cannot proceed from an item until Version A, Version B, and Version C have each been played and an answer is provided.
- Temporary development pass rule: at least 2 out of 3.
- Temporary development retry rule: maximum 2 attempts, retry enabled.
- Production pass rule, retry messaging, and exclusion behaviour are TBC.
- Failed or incomplete screening should show calm, specific feedback.
- Development screening can be passed for interface testing, but this must not be described as final validated screening.

### Navigation

- Forward: to Instructions after screening pass.
- Retry: remains on Audio Screening if retry is permitted.
- Back: to Listening Setup only if the final protocol allows it.
- Direct navigation to Instructions is blocked unless screening has passed in temporary development state.

### Progress Indicator

- Show `Step 4 of 11 - Audio screening`.
- If multiple screening items exist, also show `Screening item X of Y`.

### Notes for Implementation

- Do not invent production screening stimuli, correct answers, or pass criteria.
- Screening responses should be stored separately from experimental responses.
- Record page entry/page completion, screening attempt start/completion, and screening item start/submission timestamps.
- Development bypass must remain disabled by default and must not be available in production.
- Current development audio files are duplicated `DU-H.mp3` assets under `frontend/assets/audio/screening-development/`.
- `productionReady` remains `false`.

### ASCII Wireframe

```text
+------------------------------------------------------+
| Progress: Step 4 of 11       Question X of 3         |
+------------------------------------------------------+
| Audio Screening                                      |
| Follow the instructions and answer the screening      |
| Temporary audio screening for interface development.  |
|                                                      |
| +---- Version A ----+ +---- Version B ----+ +Version C|
| | [Audio player]    | | [Audio player]    | | [Audio] |
| +-------------------+ +-------------------+ +-------- |
|                                                      |
| Answer: Which version matches Version A?             |
| ( ) Version B                                        |
| ( ) Version C                                        |
|                                                      |
| Feedback/result area after final submission          |
|                                                      |
| [Back]                         [Next / Submit]       |
+------------------------------------------------------+
```

## 5. Instructions

### Purpose

Explain the listening task before the practice trial and experimental trials.

### Components Shown

- Page title.
- Step-by-step task explanation.
- Information banner summarising required actions.
- Example layout preview using neutral placeholders.
- Required acknowledgement checkbox.
- Primary `Continue to practice` button.
- Secondary `Back` button.

### Information Displayed

- Read each contextual listening scenario.
- Listen to three versions of the excerpt.
- Replay versions freely.
- Rate each version on the 0-100 preference scale.
- Write one required comment for each version.
- Explain that practice responses are not included in analysis.
- Avoid final scenario wording until approved.

### Participant Actions

- Read instructions.
- Review example layout.
- Continue to Practice Trial.

### Validation Rules

- The acknowledgement checkbox is required.
- Continue remains disabled until the acknowledgement is checked.
- Continue action records acknowledgement state and page completion timestamp.

### Navigation

- Forward: to Practice Trial after acknowledgement.
- Back: to Audio Screening if protocol allows.

### Progress Indicator

- Show `Step 5 of 11 - Instructions`.

### Notes for Implementation

- The example layout must not use real excerpt names, real mix identities, or real audio filenames.
- The instructions should be checked against the approved PIS before final implementation.
- Direct navigation to Instructions is blocked unless screening has passed.

### ASCII Wireframe

```text
+------------------------------------------------------+
| Progress: Step 5 of 11                               |
+------------------------------------------------------+
| Instructions                                         |
|                                                      |
| 1. Read the scenario.                                |
| 2. Listen to Version A, Version B, and Version C.    |
| 3. Replay audio as many times as needed.             |
| 4. Rate each version from 0 to 100.                  |
| 5. Write one comment for each version.               |
|                                                      |
| +--------------------------------------------------+ |
| | Example trial layout                             | |
| | [Scenario] [Version A] [Slider] [Comment]        | |
| |            [Version B] [Slider] [Comment]        | |
| |            [Version C] [Slider] [Comment]        | |
| +--------------------------------------------------+ |
|                                                      |
| [ ] I understand how to complete the listening task. |
|                                                      |
| [Back]                          [Continue to practice]|
+------------------------------------------------------+
```

## 6. Practice Trial

### Purpose

Let participants practise the exact trial interaction before data collection begins.

### Components Shown

- Persistent progress bar.
- Clear `Practice Trial` label.
- Information banner: responses are not included in analysis.
- Scenario title and description placeholder.
- Excerpt title placeholder.
- Three grouped task sections matching the experimental trial layout: Listen, Rate, Explain.
- Version A, Version B, and Version C audio controls grouped together.
- Version A, Version B, and Version C rating scales grouped together.
- Version A, Version B, and Version C required comment boxes grouped together.
- Primary `Submit practice trial` button.
- Secondary `Back` button if allowed.

### Information Displayed

- Practice scenario text from development configuration, final wording TBC.
- Practice excerpt label from development configuration, final label TBC.
- Version A, Version B, Version C.
- Audio player for each version.
- 0-100 slider for each version.
- Required comment text area for each version.

### Participant Actions

- Read practice scenario.
- Play each audio version.
- Rate each version.
- Enter one comment for each version.
- Submit the practice trial.

### Validation Rules

- Same validation as experimental trial.
- All three sliders must have participant-provided values.
- A slider counts only after deliberate participant interaction.
- All three comments must be completed.
- Empty or whitespace-only comments are invalid.
- Minimum meaningful response threshold is TBC.
- Practice audio playback is not required for completion in the current development configuration; the final requirement remains TBC.

### Navigation

- Forward: to Experimental Trial 1 after successful practice submission.
- Back: to Instructions if allowed.
- Direct navigation to Practice is blocked unless the instruction acknowledgement has been completed.

### Progress Indicator

- Show `Practice Trial` and study progress `Step 6 of 11`.
- Do not count the practice trial as `Trial 1 of 10`.

### Notes for Implementation

- Practice responses must be stored separately from experimental responses or excluded from analysis.
- Use the same grouped Listen -> Rate -> Explain component structure as experimental trials to reduce learning burden.
- The development practice configuration is `frontend/config/practice.json` with `productionReady: false`.
- Final practice wording and audio must be replaced before pilot if required by the protocol.

### ASCII Wireframe

```text
+------------------------------------------------------+
| Progress: Step 6 of 11             Practice Trial     |
+------------------------------------------------------+
| Practice Trial                                       |
| Responses on this page are not included in analysis. |
|                                                      |
| Scenario: [Practice scenario title TBC]              |
| [Practice scenario description TBC]                  |
|                                                      |
| Music Excerpt: [Practice excerpt TBC]                |
|                                                      |
| +---------------- Version A -----------------------+ |
| | [Audio player]                                  | |
| | Preference: [0 -------- slider -------- 100]    | |
| | Comment: [required text area]                   | |
| +--------------------------------------------------+ |
| +---------------- Version B -----------------------+ |
| | [Audio player] [Slider] [Required comment]      | |
| +--------------------------------------------------+ |
| +---------------- Version C -----------------------+ |
| | [Audio player] [Slider] [Required comment]      | |
| +--------------------------------------------------+ |
|                                                      |
| [Back]                         [Submit practice trial]|
+------------------------------------------------------+
```

## 7. Experimental Trial

### Purpose

Collect preference ratings and required comments for one music excerpt presented as three neutral mix versions within a contextual listening scenario.

### Components Shown

- Persistent progress bar.
- Trial count: `Trial X of 10`.
- Scenario title.
- Scenario description.
- Music excerpt title.
- Three grouped task sections: Listen to the versions, Rate the versions, and Explain your ratings.
- Listen section with Version A, Version B, and Version C audio cards.
- Rate section with Version A, Version B, and Version C 0-100 sliders.
- Explain section with Version A, Version B, and Version C required comment boxes.
- Played-state prompt for each audio version.
- Validation summary area.
- Primary `Submit trial` or `Continue` button.
- Secondary `Back` button only if allowed by final navigation policy.

### Information Displayed

- Scenario descriptive title without internal EDR/FM prefix.
- Scenario description.
- Music excerpt label shown as `Music excerpt: Song A` or `Music excerpt: Song B`.
- Version A, Version B, Version C.
- One audio player per version.
- One 0-100 preference slider per version.
- One required comment field per version.
- Required playback-start status for each version.
- Endpoint labels: `0 - Least preferred` and `100 - Most preferred`.
- Comment prompt: `Please briefly explain what influenced your preference for this mix.`
- Progress through ten trials.

### Participant Actions

- Read the scenario.
- Listen to Version A, Version B, and Version C.
- Replay any version as many times as they wish.
- Successfully start playback of all three versions.
- Provide a 0-100 preference rating for each version.
- Write a comment for each version.
- Submit the trial.

### Validation Rules

- Participant cannot continue until Version A, Version B, and Version C have each successfully started playback.
- Participant cannot continue until all three sliders have participant-provided values.
- Participant cannot continue until all three comments are completed.
- Full playback is not required.
- Empty or whitespace-only comments are invalid.
- Minimum meaningful response threshold is TBC.
- Missing fields should be identified by version label.
- The default slider position must not count as a rating unless the participant has interacted with it or explicitly confirmed it.

### Navigation

- Forward: to the next experimental trial after valid submission.
- Forward from Trial 10: to Demographic Questionnaire.
- Back: available from Trial 1 to Practice in the current development implementation.
- Back: hidden/disabled after later trials to avoid accidental editing of submitted trials or corruption of timing/randomisation state.

### Progress Indicator

- Persistent progress bar near top.
- Text must show `Trial X of 10`.
- Include wider study stage if useful, such as `Experimental trials`.

### Notes for Implementation

- This is the core study page and should be the highest design priority.
- Use 960 px maximum content width on desktop.
- Keep Version A, Version B, and Version C visually identical.
- Use the shared Listen -> Rate -> Explain layout for practice and experimental trials.
- Use 24-32 px vertical spacing between task sections.
- Avoid visual emphasis that could bias one version.
- Ensure audio controls, sliders, and text areas remain usable on mobile.
- Desktop may show three-column audio, rating, and comment grids where readable.
- Tablet may wrap to two columns while preserving A, B, C order.
- Mobile must stack controls vertically without horizontal scrolling.
- Record trial start and trial submission timestamps.
- Detailed audio playback-event recording remains TBC.
- The implemented development page is driven by `frontend/config/stimuli.json` and keeps `productionReady: false`.
- Actual mix IDs are stored internally and must not appear in participant-facing content.
- Trial order and Version A/B/C mappings are persisted so refresh does not regenerate them.
- Internal scenario IDs and EDR/FM prefixes are not shown to participants.
- Song A/Song B labels are stable for the participant's assigned excerpts throughout the session.
- Trial order is generated as five scenario pairs: both song trials for a scenario remain consecutive, song order may vary inside the pair, and Version A/B/C mappings remain independently randomised per trial.

### ASCII Wireframe

```text
+--------------------------------------------------------------+
| Experimental trials                         Trial X of 10     |
| [=========== progress bar =====================--------]       |
+--------------------------------------------------------------+
| Scenario descriptive title                                    |
| Scenario description text.                                    |
|                                                              |
| Music excerpt: Song A/B                                       |
|                                                              |
| 1. Listen to the versions                                    |
| +-- Version A --+ +-- Version B --+ +-- Version C --+        |
| | [Audio]      | | [Audio]      | | [Audio]      |        |
| | Played state | | Played state | | Played state |        |
| +--------------+ +--------------+ +--------------+        |
|                                                              |
| 2. Rate the versions                                         |
| +-- Version A --+ +-- Version B --+ +-- Version C --+        |
| | 0 Least pref. | | 0 Least pref. | | 0 Least pref. |        |
| | [slider]     | | [slider]     | | [slider]     |        |
| | 100 Most pref| | 100 Most pref| | 100 Most pref|        |
| +--------------+ +--------------+ +--------------+        |
|                                                              |
| 3. Explain your ratings                                      |
| +-- Version A --+ +-- Version B --+ +-- Version C --+        |
| | [comment]    | | [comment]    | | [comment]    |        |
| +--------------+ +--------------+ +--------------+        |
|                                                              |
| Validation summary area                                      |
|                                                              |
| [Back TBC]                                      [Submit trial]|
+--------------------------------------------------------------+
```

## 8. Demographic Questionnaire

### Purpose

Collect approved anonymous demographic information after the experimental trials.

### Components Shown

- Page title.
- Progress indicator.
- Form grouped into logical sections.
- Radio groups, select fields, or text fields as appropriate once response options are finalised.
- Primary `Continue` button.
- Secondary `Back` button if allowed.

### Information Displayed

Suggested organisation:

- About you:
  - Age range.
  - Gender, optional.
  - Nationality.
- Listening background:
  - Music listening habits.
  - Music production or audio engineering experience.
- Hearing:
  - Hearing difficulty.

### Participant Actions

- Complete demographic questions.
- Skip gender if they prefer, because gender is optional.
- Continue to the post-task questionnaire.

### Validation Rules

- Required fields must be completed.
- Gender must clearly indicate that it is optional.
- Response options are provided by `frontend/config/questionnaires.json` for development testing and remain final-approval TBC.
- Free-text fields must not request names, email addresses, or direct identifiers.

### Navigation

- Forward: to Post-task Questionnaire after required fields are valid.
- Back: to Experimental Trial page after the ten-trial completion rule is satisfied.

### Progress Indicator

- Show `Step 8 of 11 - Demographic questionnaire`.

### Notes for Implementation

- Keep fields grouped and scannable.
- Avoid intrusive wording.
- Ensure all response options are approved before implementation.

### ASCII Wireframe

```text
+------------------------------------------------------+
| Progress: Step 8 of 11                               |
+------------------------------------------------------+
| Demographic Questionnaire                            |
|                                                      |
| +---------------- About you -----------------------+ |
| | Age range:           [response control TBC]      | |
| | Gender (optional):   [response control TBC]      | |
| | Nationality:         [response control TBC]      | |
| +--------------------------------------------------+ |
|                                                      |
| +------------ Listening background ----------------+ |
| | Music listening habits:      [control TBC]       | |
| | Production/audio experience: [control TBC]       | |
| +--------------------------------------------------+ |
|                                                      |
| +---------------- Hearing -------------------------+ |
| | Hearing difficulty: [control TBC]                | |
| +--------------------------------------------------+ |
|                                                      |
| [Back TBC]                              [Continue]   |
+------------------------------------------------------+
```

## 9. Post-task Questionnaire

### Purpose

Collect participant feedback on the task experience and listening context after the experiment.

### Components Shown

- Page title.
- Progress indicator.
- Question groups.
- Rating controls, radio buttons, select fields, or text areas as appropriate once response options are finalised.
- Additional comments text area.
- Primary `Continue to review` button.
- Secondary `Back` button if allowed.

### Information Displayed

- Ability to immerse in the scenarios.
- Task difficulty.
- Prior familiarity with the songs.
- Listening device used.
- Location or environment where the study was completed.
- Additional comments.

### Participant Actions

- Answer post-task questions.
- Provide additional comments if they wish, depending on final approved response options.
- Continue to review.

### Validation Rules

- Required questions must be completed.
- Additional comments are optional in the current implementation unless final response options define otherwise.
- Free-text fields must not request direct identifiers.

### Navigation

- Forward: to Review and Submit.
- Back: to Demographic Questionnaire if allowed.

### Progress Indicator

- Show `Step 9 of 11 - Post-task questionnaire`.

### Notes for Implementation

- Keep response controls consistent with demographic questionnaire patterns.
- Listening location/environment should be broad and should not ask for identifiable addresses.

### ASCII Wireframe

```text
+------------------------------------------------------+
| Progress: Step 9 of 11                               |
+------------------------------------------------------+
| Post-task Questionnaire                              |
|                                                      |
| +---------------- Task experience -----------------+ |
| | Immersion in scenarios: [control TBC]            | |
| | Task difficulty:        [control TBC]            | |
| | Heard any songs before: [control TBC]            | |
| +--------------------------------------------------+ |
|                                                      |
| +---------------- Listening context ---------------+ |
| | Listening device:        [control TBC]          | |
| | Location/environment:     [control TBC]          | |
| +--------------------------------------------------+ |
|                                                      |
| +---------------- Additional comments ------------+ |
| | [text area]                                      | |
| +--------------------------------------------------+ |
|                                                      |
| [Back TBC]                         [Continue to review]|
+------------------------------------------------------+
```

## 10. Review and Submit

### Purpose

Let participants confirm that all required study sections are complete before final submission.

### Components Shown

- Page title.
- Progress indicator.
- Completion summary card.
- Final submission information.
- Primary `Final submit` button.
- Secondary `Back` action to Post-task Questionnaire.
- Development-only payload inspection/download controls, hidden unless explicit frontend development mode is enabled.

### Information Displayed

Completion summary:

- Success icon + Screening.
- Success icon + Experimental trials.
- Success icon + Questionnaires.

Also display:

- Ten trials completed.
- Thirty ratings completed.
- Thirty required comments completed.
- Reminder that after final submission, withdrawal may no longer be possible because responses are anonymised, as stated in the approved PIS/consent materials.

### Participant Actions

- Review completion summary.
- Select `Final submit`.

### Validation Rules

- Final submit is disabled until all required sections are complete.
- Must verify:
  - Consent completed.
  - Audio screening passed.
  - Practice trial completed.
  - Ten experimental trials submitted.
  - Thirty ratings submitted.
  - Thirty required comments submitted.
  - Required demographic questions completed.
  - Required post-task questions completed.
- Final submission records final submission timestamp.

### Navigation

- Forward: to Completion Page after successful final submission.
- Final submission creates a local development payload only and does not submit to a production backend.
- Duplicate final submission is blocked.

### Progress Indicator

- Show `Step 10 of 11 - Review and final submission`.

### Notes for Implementation

- Keep this page calm and confirmatory.
- Avoid showing raw trial answers unless review/edit behaviour is approved.
- Use success status text with icons, not icons alone.

### ASCII Wireframe

```text
+------------------------------------------------------+
| Progress: Step 10 of 11                              |
+------------------------------------------------------+
| Review and Final Submission                          |
|                                                      |
| +---------------- Completion summary --------------+ |
| | [success] Screening completed                    | |
| | [success] Experimental trials completed          | |
| |           10 trials, 30 ratings, 30 comments     | |
| | [success] Questionnaires completed               | |
| +--------------------------------------------------+ |
|                                                      |
| Final submission note from approved materials         |
|                                                      |
| [Back / Review TBC]                    [Final submit]|
+------------------------------------------------------+
```

## 11. Completion Page

### Purpose

Confirm successful submission, thank the participant, and provide a simple closing message.

### Components Shown

- Page title.
- Thank-you message.
- Anonymous development session ID display.
- Confirmation message.
- Close window instruction.

### Information Displayed

- Thank-you message, final wording TBC and checked against approved materials.
- Anonymous development session ID, development only.
- Confirmation that responses were recorded.
- Simple closing message.
- Close window instructions.

### Participant Actions

- Close the browser window or tab.

### Validation Rules

- Page is shown only after final submission succeeds.
- If submission fails, participant should remain on Review and Submit with a clear warning, not reach Completion.

### Navigation

- Forward: none.
- Back: should be disabled or discouraged after final submission.
- Close: participant may close the window.

### Progress Indicator

- Show `Step 11 of 11 - Complete` or a completed progress state.

### Notes for Implementation

- Development session ID must be anonymous and generated securely.
- Do not display direct identifiers.
- Do not repeat researcher contact information already available in the approved Participant Information Sheet.

### ASCII Wireframe

```text
+------------------------------------------------------+
| Progress: Complete                                   |
+------------------------------------------------------+
| Thank you                                            |
|                                                      |
| +--------------------------------------------------+ |
| | Your responses have been recorded.               | |
| |                                                  | |
| | Development session ID: dev_randomtoken          | |
| |                                                  | |
| | Thank you for taking part in this research.      | |
| |                                                  | |
| | You may now close this window.                   | |
| +--------------------------------------------------+ |
+------------------------------------------------------+
```

## Navigation Rules

- Landing Page -> Study Information and Consent when `Start Study` is selected.
- Study Information and Consent -> Listening Setup only after the PIS has been opened, the PIS acknowledgement checkbox is checked, the Consent Form has been opened, and all required consent statements are checked.
- Listening Setup -> Audio Screening only after test audio has been played.
- Audio Screening -> Instructions only after the screening test is passed.
- Audio Screening -> Audio Screening retry state if the participant fails and retry is permitted. Retry behaviour is TBC.
- Instructions -> Practice Trial only after the task acknowledgement checkbox is checked.
- Practice Trial -> Experimental Trial 1 only after all practice ratings and required comments are complete.
- Experimental Trial X -> Experimental Trial X+1 for trials 1-9 only after Version A, Version B, and Version C have each started playback, all three ratings are deliberately set, and all three required comments are complete.
- Experimental Trial 10 -> Demographic Questionnaire only after Version A, Version B, and Version C have each started playback, all three ratings are deliberately set, and all three required comments are complete.
- Direct Demographic Questionnaire access is blocked until ten submitted experimental trial records exist.
- Demographic Questionnaire -> Post-task Questionnaire after required demographic fields are complete.
- Post-task Questionnaire -> Review and Submit after required post-task fields are complete.
- Review and Submit -> Completion Page only after final submission succeeds.
- Completion Page has no forward transition.

Back navigation:

- Back navigation before consent may be allowed between Landing, PIS, and Consent.
- Back navigation after consent is TBC.
- Current development behavior allows Back from Trial 1 to Practice only; Back is hidden/disabled for later experimental trials.
- Any future back navigation during or after experimental trials must not compromise randomisation, response-time data, or submitted trial integrity.
- After final submission, back navigation should not allow response editing.

## Validation Summary

- PIS document must be opened at least once.
- PIS acknowledgement checkbox must be checked.
- Consent Form document must be opened at least once.
- All required consent statement checkboxes must be checked.
- Listening setup test audio must be played before continuing.
- Audio screening requires playback and an answer before submission.
- Development audio screening requires 2 out of 3 correct responses; production pass rule remains TBC.
- Instructions acknowledgement checkbox must be checked.
- Practice trial requires all three deliberately touched ratings and all three comments.
- Each experimental trial requires Version A, Version B, and Version C to have successfully started playback.
- Each experimental trial requires all three slider ratings.
- Each experimental trial requires all three comments.
- Empty or whitespace-only comments are invalid.
- Minimum meaningful comment threshold is TBC.
- Default slider position must not be counted as a submitted rating unless actively set or explicitly confirmed.
- Required demographic questions must be completed.
- Gender is optional.
- Required post-task questions must be completed.
- Additional comments in the post-task questionnaire follow final response-option rules, TBC.
- Final submission requires consent, screening, practice, exactly ten trials, thirty ratings, thirty comments, demographics, and post-task questionnaire completion.
- Completion page requires final submission.
- Submitted sessions must not reopen editable study pages during normal navigation.
- No form should request participant names, email addresses, IP addresses, signatures, postal addresses, phone numbers, student numbers, or other direct identifiers.

## Components Reused Across Pages

The following should become reusable UI components during implementation:

- Page frame.
- QMUL logo/header area.
- Progress indicator.
- Card container.
- Primary, secondary, and disabled buttons.
- Validation message.
- Information banner.
- Warning banner.
- Checkbox group.
- Radio group.
- Select/input field.
- Text area.
- Audio player.
- 0-100 preference slider.
- Trial version card.
- Scenario header.
- Questionnaire section.
- Completion summary item.

Reusable components must follow the design system for spacing, typography, accessibility, focus indicators, responsive behaviour, and calm academic tone.
