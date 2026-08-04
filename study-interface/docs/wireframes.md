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
[Pre-Study Listening Task]
    |
    v
[Instructions]
    |
    v
[Practice Trial]
    |
    v
[Main Study]
    |
    v
[Listening Task 1]
    |
    v
[Listening Task 2]
    |
    v
  ...
    |
    v
[Listening Task 10]
    |
    v
[Post-task Questionnaire]
    |
    v
[Demographic Questionnaire]
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

- Active landing-page study title: `Music Mix Preferences in Everyday Listening Situations`.
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

- Show either no progress bar or a neutral `Step 1 of 12` indicator.
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

- Show `Step 2 of 12 - Study information and consent`.
- Progress text must be readable by screen readers.

### Notes for Implementation

- Do not render the full PIS inside the web page; link to the participant-facing PDF.
- Consent labels must follow the approved consent form wording.
- Do not include signature, printed-name, or date fields because the web study must not collect direct identifiers.

### ASCII Wireframe

```text
+------------------------------------------------------+
| Progress: Step 2 of 12                               |
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

Prepare participants for the pre-study and main listening tasks.

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
- No final pre-study stimuli should be described here.

### Participant Actions

- Read setup reminders.
- Play the test audio.
- Adjust device volume if needed.
- Continue after the test audio has been played.

### Validation Rules

- Continue is disabled until the test audio has been played at least once and all three setup confirmations are checked.
- If the configured setup test audio file is missing or playback fails, show a warning banner and keep progression disabled.

### Navigation

- Forward: to Pre-Study Listening Task after test audio has been played and all setup confirmations are checked.
- Back: to Study Information and Consent.

### Progress Indicator

- Show `Step 3 of 12 - Listening setup`.

### Notes for Implementation

- Record page entry, page completion, and listening setup completion timestamps.
- Store temporary development-only state for setup test playback and the three setup confirmations.
- Playback-event logging remains TBC; only the gating state for test playback is required for this page.
- The configured setup test audio path is `frontend/assets/audio/setup-test-development.mp3`; this temporary development file must be replaced before pilot or production use and must not reveal experimental material.

### ASCII Wireframe

```text
+------------------------------------------------------+
| Progress: Step 3 of 12                               |
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

## 4. Pre-Study Listening Task

### Purpose

Provide a short neutral listening task before the study instructions without describing it as a formal test.

### Components Shown

- Page title.
- Concise listening task instructions.
- Six listening item panels on one scrollable page.
- Matching audio players for Reference, Version A, and Version B in each item.
- One answer fieldset per item.
- Neutral feedback/result area after full attempt submission.
- Retry button when attempts remain.
- Primary `Submit listening task` action after all six items are complete.
- Secondary `Back` button only if allowed by protocol.

### Information Displayed

- Instructions for completing the pre-study listening task.
- Listening item labels: `Listening item 1 of 6` through `Listening item 6 of 6`.
- Audio player labels that do not reveal stimuli identity.
- Answer options `Version A` and `Version B` in the current development configuration.
- Neutral completion/retry feedback after submission. Numerical score and correct/incorrect answers are not shown to participants.

### Participant Actions

- Play the Reference, Version A, and Version B for each listening item.
- Select one answer for each listening item.
- Submit all six answers together.
- Repeat the task if permitted by final policy.
- Continue after successful completion.

### Validation Rules

- The `Submit listening task` button remains disabled until the Reference, Version A, and Version B have each been played for all six items and one answer is selected for every item.
- Temporary development pass rule: configured internally as at least 2 correct responses; final scientific threshold remains TBC.
- Temporary development retry rule: maximum 2 attempts, retry enabled.
- Retry resets all six item responses and played states for the next attempt while keeping the same one-page layout.
- Production pass rule, retry messaging, and exclusion behaviour are TBC.
- Failed or incomplete task states should show calm, specific feedback without revealing score or correct answers.
- Development stimuli can be used for interface testing, but must not be described as final validated stimuli.

### Navigation

- Forward: to Instructions after successful completion.
- Retry: remains on Pre-Study Listening Task if retry is permitted.
- Back: to Listening Setup only if the final protocol allows it.
- Direct navigation to Instructions is blocked unless the task has passed in temporary development state.

### Progress Indicator

- Show `Step 4 of 12 - Pre-Study Listening Task`.
- Within the page, label each item as `Listening item X of 6`.

### Notes for Implementation

- Do not invent production pre-study stimuli, Brecht preference results, scientific thresholds, or exclusion criteria.
- Responses should be stored separately from experimental responses.
- Record page entry/page completion, attempt start/completion, and item start/submission timestamps.
- Generate two internal segment identities with three repetitions each, randomise presentation order once per attempt, and persist the order so refresh does not reshuffle it.
- Randomise whether Version A or Version B is the matching answer per presentation where supported.
- Store internal score, item correctness, segment ID, repetition number, presentation order, and Reference/Version A/Version B mapping, but do not display score to participants.
- Comparative audio controls should reset the previous version to 0:00 when switching, start the newly selected version from 0:00, prevent seeking, and keep individual player volume fixed.
- Development bypass must remain disabled by default and must not be available in production.
- Previous duplicated development files were audited and replaced because they were byte-for-byte identical.
- Current development audio files are short WAV clips generated from current DU-H source-audio segments; the current non-matching option is a different musical segment and final segment selection remains TBC.
- `productionReady` remains `false`.

### ASCII Wireframe

```text
+------------------------------------------------------+
| Progress: Step 4 of 12                               |
+------------------------------------------------------+
| Pre-Study Listening Task                             |
| Follow the instructions and answer all items.         |
|                                                      |
| Listening item 1 of 6                                |
| Which of A or B matches the Reference?              |
| +--- Reference ----+ +---- Version A ----+ +Version B|
| | [Audio player]    | | [Audio player]    | | [Audio] |
| +-------------------+ +-------------------+ +-------- |
|                                                      |
| Answer for listening item 1                          |
| ( ) Version A                                        |
| ( ) Version B                                        |
|                                                      |
| Listening item 2 of 6                                |
| [Reference] [Version A] [Version B]                  |
| Answer: ( ) Version A  ( ) Version B                 |
|                                                      |
| ...                                                  |
| Listening item 6 of 6                                |
| [Reference] [Version A] [Version B]                  |
| Answer: ( ) Version A  ( ) Version B                 |
|                                                      |
| Neutral completion/retry feedback after submission   |
|                                                      |
| [Back]                   [Submit listening task]     |
+------------------------------------------------------+
```

## 5. Instructions

### Purpose

Explain the listening task before the Practice Trial and main study listening tasks.

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
- Back: to Pre-Study Listening Task if protocol allows.

### Progress Indicator

- Show `Step 5 of 12 - Instructions`.

### Notes for Implementation

- The example layout must not use real excerpt names, real mix identities, or real audio filenames.
- The instructions should be checked against the approved PIS before final implementation.
- Direct navigation to Instructions is blocked unless screening has passed.

### ASCII Wireframe

```text
+------------------------------------------------------+
| Progress: Step 5 of 12                               |
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
- Marker-based task structure matching the experimental trial layout.
- Hidden Version A, Version B, and Version C audio elements controlled by the markers.
- One shared 0-100 preference scale with draggable Version A, Version B, and Version C markers and one shared Stop audio button.
- Version A, Version B, and Version C required comment boxes grouped together.
- Primary `Submit` button.
- Secondary `Back` button if allowed.

### Information Displayed

- Practice scenario text from development configuration, final wording TBC.
- Practice excerpt label from development configuration, final label TBC.
- Version A, Version B, Version C.
- Audio is controlled from the Version A, Version B, and Version C markers rather than separate visible audio-player cards.
- Shared 0-100 preference scale with Bad, Poor, Fair, Good, and Excellent anchors.
- Draggable Version A, Version B, and Version C markers.
- Required comment text area for each version.

### Participant Actions

- Read practice scenario.
- Play each audio version.
- Click or tap each marker to play the version, then drag each marker on the shared preference scale.
- Enter one comment for each version.
- Submit the practice trial.

### Validation Rules

- Same validation as experimental trial.
- All three markers must have participant-provided values.
- A marker counts only after deliberate participant interaction.
- All three comments must be completed.
- Empty or whitespace-only comments are invalid.
- Minimum meaningful response threshold is TBC.
- All three practice audio versions must be played before completion.

### Navigation

- Forward: to the Main Study transition page after successful practice submission.
- Back: to Instructions if allowed.
- Direct navigation to Practice is blocked unless the instruction acknowledgement has been completed.

### Progress Indicator

- Show `Practice Trial` and study progress `Step 6 of 12`.
- Do not count the practice trial as `Listening Task 1 of 10`.

### Notes for Implementation

- Practice responses must be stored separately from experimental responses or excluded from analysis.
- Use the same marker playback -> shared preference scale -> Explain component structure as the main study listening tasks to reduce learning burden.
- The development practice configuration is `frontend/config/practice.json` with `productionReady: false`.
- Final practice wording and audio must be replaced before pilot if required by the protocol.

### ASCII Wireframe

```text
+------------------------------------------------------+
| Progress: Step 6 of 12             Practice Trial     |
+------------------------------------------------------+
| Practice Trial                                       |
| Responses on this page are not included in analysis. |
|                                                      |
| Scenario: [Practice scenario title TBC]              |
| [Practice scenario description TBC]                  |
|                                                      |
| Music Excerpt: [Practice excerpt TBC]                |
|                                                      |
| Shared preference scale                              |
| Bad   Poor   Fair   Good   Excellent                 |
| 0 ---- A -------- B ---- C ----------------- 100      |
| [Stop audio]  No version is playing.                 |
| A: 30  B: 70  C: Not set                             |
|                                                      |
| Explain your ratings                                 |
| +-- Version A --+ +-- Version B --+ +-- Version C --+ |
| | [comment]    | | [comment]    | | [comment]    | |
| | [Required comment boxes for A, B, and C]        | |
| +--------------------------------------------------+ |
|                                                      |
| [Back]                                      [Submit]|
+------------------------------------------------------+
```

## 7. Main Study Transition

### Purpose

Clearly mark the end of the Practice Trial and prepare participants to begin the response-collecting part of the study.

### Components Shown

- Persistent progress bar.
- Page title: `Main Study`.
- Confirmation that the Practice Trial has been completed.
- Statement that the following listening tasks are included in the research analysis.
- Brief reminder that there are no right or wrong answers.
- Primary `Begin Main Study` button.
- Secondary `Back` button.

### Information Displayed

- `You have successfully completed the Practice Trial.`
- `The following listening tasks are part of the main study. From this point onwards, your responses will be included in the research analysis.`
- `Please complete each listening task carefully. There are no right or wrong answers-we are interested in your personal judgement.`

### Participant Actions

- Read the transition message.
- Begin the main study.
- Return to the Practice Trial if needed before starting the first listening task.

### Validation Rules

- No form validation is required.
- Direct navigation is blocked unless the Practice Trial has been completed.

### Navigation

- Forward: to Listening Task 1 of 10.
- Back: to Practice Trial.

### Progress Indicator

- Show `Main Study` and study progress `Step 7 of 12`.

### Notes for Implementation

- This page must not create experimental response records.
- It may record page entry and page completion timing like other participant-facing pages.
- It must not change trial generation, randomisation, or response schema.

### ASCII Wireframe

```text
+------------------------------------------------------+
| Progress: Step 7 of 12                  Main Study    |
+------------------------------------------------------+
| Main Study                                           |
|                                                      |
| You have successfully completed the Practice Trial.   |
|                                                      |
| The following listening tasks are part of the main    |
| study. From this point onwards, your responses will   |
| be included in the research analysis.                 |
|                                                      |
| Please complete each listening task carefully. There  |
| are no right or wrong answers-we are interested in    |
| your personal judgement.                             |
|                                                      |
| [Back]                              [Begin Main Study]|
+------------------------------------------------------+
```

## 8. Experimental Listening Task

### Purpose

Collect preference ratings and required comments for one music excerpt presented as three neutral mix versions within a contextual listening scenario.

### Components Shown

- Persistent progress bar.
- Listening task count: `Listening Task X of 10`.
- Scenario title.
- Scenario description.
- Music excerpt title.
- Marker-based task structure: play versions from the markers, drag markers on the shared preference scale, and explain your ratings.
- Hidden Version A, Version B, and Version C audio elements controlled by the markers.
- Shared 0-100 preference scale with draggable Version A, Version B, and Version C markers.
- Explain section with Version A, Version B, and Version C required comment boxes.
- Played-state prompt for each audio version.
- Validation summary area.
- Primary `Submit` button.
- Secondary `Back` button only if allowed by final navigation policy.

### Information Displayed

- Scenario descriptive title without internal EDR/FM prefix.
- Scenario description.
- Music excerpt label shown as `Music excerpt: Song A` or `Music excerpt: Song B`.
- Version A, Version B, Version C.
- Hidden audio for each version, controlled from the Version A, Version B, and Version C markers.
- One shared 0-100 preference scale with one marker per version.
- One required comment field per version.
- Required playback-start status for each version.
- Scale anchors: Bad, Poor, Fair, Good, Excellent at 0, 25, 50, 75, and 100.
- Comment prompt: `Please briefly explain what influenced your preference for this mix.`
- Progress through ten trials.

### Participant Actions

- Read the scenario.
- Click or tap Version A, Version B, and Version C markers to play audio.
- Replay any version as many times as they wish.
- Successfully start playback of all three versions.
- Drag the Version A, Version B, and Version C markers on the shared preference scale.
- Write a comment for each version.
- Submit the listening task.

### Validation Rules

- Participant cannot continue until Version A, Version B, and Version C have each successfully started playback.
- Participant cannot continue until all three markers have participant-provided values.
- Participant cannot continue until all three comments are completed.
- Full playback is not required.
- Empty or whitespace-only comments are invalid.
- Minimum meaningful response threshold is TBC.
- Missing fields should be identified by version label.
- The default marker position must not count as a rating unless the participant has interacted with it or explicitly confirmed it.

### Navigation

- Forward: to the next listening task after valid submission.
- Forward from Listening Task 10: to Post-task Questionnaire.
- Back: available from Listening Task 1 to the Main Study transition page in the current development implementation.
- Back: hidden/disabled after later listening tasks to avoid accidental editing of submitted trials or corruption of timing/randomisation state.

### Progress Indicator

- Persistent progress bar near top.
- Text must show `Listening Task X of 10`.
- Include wider study stage as `Main Study`.

### Notes for Implementation

- This is the core study page and should be the highest design priority.
- Use 960 px maximum content width on desktop.
- Keep Version A, Version B, and Version C visually identical.
- Use the shared marker playback -> shared preference scale -> Explain layout for practice and main study listening tasks.
- Use 24-32 px vertical spacing between task sections.
- Avoid visual emphasis that could bias one version.
- Ensure audio controls, shared rating markers, and text areas remain usable on mobile.
- Desktop may show three-column audio and comment grids with one horizontal shared rating scale.
- Tablet may wrap to two columns while preserving A, B, C order.
- Mobile may use a vertical shared rating scale to avoid horizontal scrolling.
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
| Main Study                         Listening Task X of 10     |
| [=========== progress bar =====================--------]       |
+--------------------------------------------------------------+
| Scenario descriptive title                                    |
| Scenario description text.                                    |
|                                                              |
| Music excerpt: Song A/B                                       |
|                                                              |
| 1. Shared preference scale                                  |
| Bad        Poor        Fair        Good        Excellent     |
| 0 ---------- A -------- B -------- C -------------- 100      |
| [Stop audio]  No version is playing.                        |
| A: 30              B: 55              C: Not set             |
|                                                              |
| 2. Explain your ratings                                      |
| +-- Version A --+ +-- Version B --+ +-- Version C --+        |
| | [comment]    | | [comment]    | | [comment]    |        |
| +--------------+ +--------------+ +--------------+        |
|                                                              |
| Validation summary area                                      |
|                                                              |
| [Back]                                           [Submit]|
+--------------------------------------------------------------+
```

## 9. Post-task Questionnaire

### Purpose

Collect participant feedback on the task experience and listening context after the ten main study listening tasks.

### Components Shown

- Page title.
- Progress indicator.
- Question groups.
- Horizontal Likert controls for agreement questions where space allows.
- Radio buttons and conditional text fields for listening-context questions.
- Primary `Continue` button.
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
- Provide details when selecting `Other` for listening device or completion location.
- Provide additional comments if they wish, depending on final approved response options.
- Continue to the demographic questionnaire.

### Validation Rules

- Required questions must be completed.
- `Other` for listening device requires the accompanying detail field.
- `Other environment` for completion location requires the accompanying detail field.
- Additional comments are optional in the current implementation unless final response options define otherwise.
- Free-text fields must not request names, email addresses, or direct identifiers.

### Navigation

- Forward: to Demographic Questionnaire after required fields are valid.
- Back: to the listening task flow after the ten-task completion rule is satisfied.

### Progress Indicator

- Show `Step 9 of 12 - Post-task questionnaire`.

### Notes for Implementation

- Keep response controls consistent with demographic questionnaire patterns.
- Listening location/environment should be broad and should not ask for identifiable addresses.

### ASCII Wireframe

```text
+------------------------------------------------------+
| Progress: Step 9 of 12                               |
+------------------------------------------------------+
| Post-task Questionnaire                              |
|                                                      |
| +---------------- Task experience -----------------+ |
| | Immersion: [Strongly disagree ... Strongly agree]| |
| | Task difficulty:        [control TBC]            | |
| | Heard any songs before: [control TBC]            | |
| +--------------------------------------------------+ |
|                                                      |
| +---------------- Listening context ---------------+ |
| | Listening device:        [control TBC]           | |
| | If Other:                [Please specify...]     | |
| | Location/environment:    [control TBC]           | |
| | If Other environment:    [Please specify...]     | |
| +--------------------------------------------------+ |
|                                                      |
| +---------------- Additional comments ------------+ |
| | [text area]                                      | |
| +--------------------------------------------------+ |
|                                                      |
| [Back TBC]                              [Continue]   |
+------------------------------------------------------+
```

## 10. Demographic Questionnaire

### Purpose

Collect approved anonymous demographic information after the post-task questionnaire.

### Components Shown

- Page title.
- Progress indicator.
- Form grouped into logical sections.
- Radio groups, select fields, or text fields as appropriate once response options are finalised.
- Primary `Continue to review` button.
- Secondary `Back` button if allowed.

### Information Displayed

Suggested organisation:

- About you:
  - Age range.
  - Gender, optional.
  - Country that most influenced musical and cultural background.
- Listening background:
  - Music listening habits.
  - Music production or audio engineering experience.
- Hearing:
  - Hearing difficulty.

### Participant Actions

- Complete demographic questions.
- Skip gender if they prefer, because gender is optional.
- Continue to review.

### Validation Rules

- Required fields must be completed.
- Gender must clearly indicate that it is optional.
- Response options are provided by `frontend/config/questionnaires.json` for development testing and remain final-approval TBC.
- Free-text fields must not request direct identifiers.

### Navigation

- Forward: to Review and Submit.
- Back: to Post-task Questionnaire if allowed.

### Progress Indicator

- Show `Step 10 of 12 - Demographic questionnaire`.

### Notes for Implementation

- Keep fields grouped and scannable.
- Avoid intrusive wording.
- Ensure all response options are approved before implementation.

### ASCII Wireframe

```text
+------------------------------------------------------+
| Progress: Step 10 of 12                              |
+------------------------------------------------------+
| Demographic Questionnaire                            |
|                                                      |
| +---------------- About you -----------------------+ |
| | Age range:           [response control TBC]      | |
| | Gender (optional):   [response control TBC]      | |
| | Cultural influence:  [required text input]       | |
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
| [Back TBC]                         [Continue to review]|
+------------------------------------------------------+
```

## 11. Review and Submit

### Purpose

Let participants confirm that all required study sections are complete before final submission.

### Components Shown

- Page title.
- Progress indicator.
- Completion summary card.
- Final submission information.
- Primary `Final submit` button.
- Secondary `Back` action to Demographic Questionnaire.
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
  - Ten main study listening tasks submitted.
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

- Show `Step 11 of 12 - Review and final submission`.

### Notes for Implementation

- Keep this page calm and confirmatory.
- Avoid showing raw trial answers unless review/edit behaviour is approved.
- Use success status text with icons, not icons alone.

### ASCII Wireframe

```text
+------------------------------------------------------+
| Progress: Step 11 of 12                              |
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

## 12. Completion Page

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

- Show `Step 12 of 12 - Complete` or a completed progress state.

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
- Study Information and Consent -> Listening Setup only after the PIS has been opened, the PIS acknowledgement checkbox is checked, the Consent Form has been opened, and the required Consent Form acknowledgement is checked.
- Listening Setup -> Pre-Study Listening Task only after test audio has been played.
- Pre-Study Listening Task -> Instructions only after the task is completed successfully.
- Pre-Study Listening Task -> Pre-Study Listening Task retry state if the participant does not meet the internal criterion and retry is permitted. Retry behaviour is TBC.
- Instructions -> Practice Trial only after the task acknowledgement checkbox is checked.
- Practice Trial -> Main Study transition only after all practice playback, ratings, and required comments are complete.
- Main Study transition -> Listening Task 1 after the participant selects `Begin Main Study`.
- Listening Task X -> Listening Task X+1 for tasks 1-9 only after Version A, Version B, and Version C have each started playback, all three ratings are deliberately set, and all three required comments are complete.
- Listening Task 10 -> Post-task Questionnaire only after Version A, Version B, and Version C have each started playback, all three ratings are deliberately set, and all three required comments are complete.
- Direct Post-task Questionnaire access is blocked until ten submitted experimental trial records exist.
- Post-task Questionnaire -> Demographic Questionnaire after required post-task fields are complete.
- Demographic Questionnaire -> Review and Submit after required demographic fields are complete.
- Review and Submit -> Completion Page only after final submission succeeds.
- Completion Page has no forward transition.

Back navigation:

- Back navigation before consent may be allowed between Landing, PIS, and Consent.
- Back navigation after consent is TBC.
- Current development behavior allows Back from Listening Task 1 to the Main Study transition page only; Back is hidden/disabled for later listening tasks.
- Any future back navigation during or after main study listening tasks must not compromise randomisation, response-time data, or submitted trial integrity.
- After final submission, back navigation should not allow response editing.

## Validation Summary

- PIS document must be opened at least once.
- PIS acknowledgement checkbox must be checked.
- Consent Form document must be opened at least once.
- All required consent statement checkboxes must be checked.
- Listening setup test audio must be played before continuing.
- Pre-Study Listening Task requires Reference, Version A, and Version B playback plus one A/B answer for each of the six listening items before submission.
- Development Pre-Study Listening Task stores internal score without showing it to participants; production pass rule remains TBC.
- Instructions acknowledgement checkbox must be checked.
- Practice trial requires all three deliberately positioned shared-scale markers and all three comments.
- Each experimental trial requires Version A, Version B, and Version C to have successfully started playback.
- Each experimental trial requires all three shared-scale marker ratings.
- Each experimental trial requires all three comments.
- Empty or whitespace-only comments are invalid.
- Minimum meaningful comment threshold is TBC.
- Default marker position must not be counted as a submitted rating unless actively set or explicitly confirmed.
- Required demographic questions must be completed.
- Gender is optional.
- Required post-task questions must be completed, including conditional detail fields when `Other` is selected for listening device or completion location.
- Additional comments in the post-task questionnaire follow final response-option rules, TBC.
- Final submission requires consent, screening, practice, exactly ten trials, thirty ratings, thirty comments, post-task questionnaire, and demographics completion.
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
- Shared 0-100 preference scale with Version A/B/C markers, marker-triggered playback, drag-only rating changes, and one Stop audio button.
- Trial version card.
- Scenario header.
- Questionnaire section.
- Completion summary item.

Reusable components must follow the design system for spacing, typography, accessibility, focus indicators, responsive behaviour, and calm academic tone.
