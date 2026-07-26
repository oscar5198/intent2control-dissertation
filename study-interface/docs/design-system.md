# Design System

This document defines the visual and interaction design system for the listening study interface. It should guide every page in the experiment without introducing application code.

The Participant Information Sheet and consent form in `docs/participant-materials/` are the authoritative source for participant-facing wording. This design system defines presentation, layout, and component behaviour only.

## 1. Design Philosophy

The interface should feel clean, modern, academic, trustworthy, calm, minimal, and accessible. It should support focused listening and careful reading without feeling commercial, decorative, or promotional.

The design should prioritise:

- Legibility during 15-20 minutes of use.
- Clear task progression through consent, screening, practice, trials, questionnaires, review, and completion.
- Low visual noise so participants can concentrate on the audio and their ratings.
- Consistent controls across the ten experimental trials.
- Neutral presentation of Version A, Version B, and Version C.
- Accessible interaction for keyboard, screen reader, desktop, tablet, and mobile users.

The visual tone should resemble a well-designed university research tool: measured, quiet, and dependable. Avoid marketing-style hero layouts, oversized decorative graphics, bright gradients, playful illustration, or anything that could bias the perceived quality of a mix version.

## 2. Colour Palette

Use soft neutral colours suitable for long reading sessions. The palette should keep the page light and calm while preserving strong contrast for controls and validation states.

| Role | HEX | Usage |
| --- | --- | --- |
| Background | `#F6F7F5` | Main page background. |
| Card | `#FFFFFF` | Content panels, forms, trial sections. |
| Primary | `#245C73` | Main actions, active progress, active slider state. |
| Secondary | `#6F7D68` | Secondary actions, supporting accents, non-critical status. |
| Success | `#2F7D55` | Successful completion, passed checks. |
| Warning | `#A86F18` | Cautionary states, incomplete but recoverable issues. |
| Error | `#B04444` | Validation errors and blocking issues. |
| Border | `#D7DDD8` | Card borders, dividers, input outlines. |
| Text Primary | `#1F2523` | Main text and headings. |
| Text Secondary | `#5F6A66` | Help text, metadata, secondary labels. |
| Disabled | `#AEB8B2` | Disabled text, unavailable controls, inactive steps. |

Guidance:

- Do not use colour alone to communicate status.
- Keep primary actions visually clear but not visually loud.
- Use warning and error colours sparingly.
- Use white cards against the neutral background to create structure without heavy shadows.
- Maintain consistent colour meaning across every page.

## 3. Typography

Recommended font stack:

- Primary: `Atkinson Hyperlegible`
- Fallback: `Source Sans 3`, `Segoe UI`, `Arial`, sans-serif

Atkinson Hyperlegible is recommended because it is designed for readability and accessibility. Source Sans 3 is a suitable secondary Google font for a modern academic interface.

Heading hierarchy:

| Level | Recommended size | Weight | Use |
| --- | --- | --- | --- |
| Page title | 30-34 px | 700 | Main page heading. |
| Section heading | 22-24 px | 700 | Major form or trial sections. |
| Subsection heading | 18-20 px | 600 | Mix version blocks, questionnaire groups. |
| Small heading | 16 px | 600 | Compact labels, review subsections. |

Body text:

- Standard paragraph: 17-18 px.
- Line height: 1.55-1.7.
- Long reading pages, such as PIS and consent: 18 px with generous line height.
- Help text and metadata: 14-15 px.
- Avoid text smaller than 14 px.

Button text:

- 16 px.
- Weight 600.
- Sentence case.
- Labels should be direct and action-oriented, such as `Continue`, `Back`, `Submit trial`, or `Final submit`.

Spacing:

- Paragraph spacing: 12-16 px.
- Section spacing: 32-48 px.
- Form field spacing: 20-24 px.
- Trial component spacing: 24-32 px between mix versions.

## 4. Layout

Maximum content width:

- Reading and form pages: 820 px.
- Trial pages: 960 px.
- Review pages: 960 px.

Card width:

- Standard card: full width within the content container.
- Narrow confirmation card: 640-720 px.
- Trial mix card: full width within the trial container.

Margins:

- Desktop page margin: 48 px minimum.
- Tablet page margin: 32 px.
- Mobile page margin: 16 px.

Padding:

- Standard card padding: 32 px desktop, 24 px tablet, 20 px mobile.
- Compact component padding: 16-20 px.
- Large reading section padding: 32-40 px.

Vertical spacing:

- Between page title and first content block: 24 px.
- Between cards or major sections: 24-32 px.
- Between related form controls: 16-20 px.
- Between unrelated form groups: 32 px.

Desktop layout:

- Use a centred single-column layout for reading, consent, eligibility, questionnaires, review, and completion.
- Trial pages may use a wider single-column layout with stacked mix cards.
- Keep progress visible near the top of the page.
- Place primary navigation at the bottom of the current step.

Tablet layout:

- Preserve the single-column structure.
- Reduce padding and margin slightly.
- Keep controls full width where useful.
- Avoid sidebars.

Mobile layout:

- Use a single column only.
- Keep audio controls, slider, and comment field stacked.
- Use full-width primary buttons.
- Ensure progress indicators remain readable without crowding.
- Avoid sticky elements that reduce usable screen height during listening or typing.

## 5. Components

### Buttons

Button types:

- Primary: main forward action, such as continuing or submitting a trial.
- Secondary: back, review, or non-destructive supporting action.
- Tertiary: low-emphasis text action where appropriate.
- Destructive: only for rare actions such as clearing a response, if implemented.

Specifications:

- Minimum height: 44 px.
- Recommended height: 48 px.
- Horizontal padding: 20-24 px.
- Border radius: 6 px.
- Disabled state must reduce contrast and remove pointer emphasis.
- Loading or submitting state should clearly indicate that the action is in progress.

Behaviour:

- The primary action should remain disabled until required fields for the current step are valid.
- For experimental trials, `Submit trial` must remain disabled until all three ratings and all three required comments are complete.
- Empty or whitespace-only comments must trigger validation.

### Cards

Cards should organise content without making the page feel decorative.

Specifications:

- Background: Card colour.
- Border: 1 px solid Border colour.
- Border radius: 8 px maximum.
- Shadow: none or very subtle.
- Padding: 24-32 px depending on viewport.

Usage:

- Use cards for PIS content sections, consent groups, screening tasks, trial mix blocks, questionnaires, review groups, and completion confirmation.
- Do not nest cards inside cards.
- Do not use cards as decorative landing-page marketing panels.

### Input Fields

Text, number, select, and similar input fields should be clear and predictable.

Specifications:

- Height: at least 44 px.
- Border: 1 px solid Border colour.
- Border radius: 6 px.
- Padding: 10-12 px.
- Label: always visible.
- Help text: below the label or field.
- Error text: directly below the affected field.

States:

- Default.
- Hover.
- Focus.
- Disabled.
- Error.
- Success, only when useful.

### Text Areas

Text areas are required for each mix comment.

Specifications:

- Minimum height: 96 px.
- Recommended trial comment height: 120 px.
- Resize behaviour: vertical resizing may be allowed.
- Label must identify the associated mix version clearly.
- Required status must be visible in text, not colour alone.

Validation:

- Empty comments are invalid.
- Whitespace-only comments are invalid.
- A minimum meaningful response threshold is TBC and must not be invented during UI implementation.

### Checkboxes

Checkboxes should be used for consent items and independent confirmations.

Specifications:

- Minimum target size: 44 x 44 px including label area.
- Checkbox control: at least 20 x 20 px.
- Label text should be clickable.
- Consent checkbox labels must follow the approved consent form wording.

### Radio Buttons

Radio buttons should be used when one option must be selected from a short set.

Specifications:

- Minimum target size: 44 x 44 px including label area.
- Radio control: at least 20 x 20 px.
- Group label must describe the question.
- Use vertical stacking for readability unless the choices are very short.

### Progress Bar

The progress bar should reassure participants and orient them in the study.

Specifications:

- Use a simple linear progress indicator.
- Include text such as current section and trial count.
- Do not rely on colour alone.
- For trials, show progress as `Trial X of 10`.
- Avoid showing hidden group assignment or real mix identity.

### Slider

The rating slider is used for the continuous 0-100 preference scale.

Specifications:

- Range: 0-100.
- Step: TBC by implementation, but should support sufficiently fine continuous preference input.
- Display current numeric value clearly.
- Track height: 6-8 px.
- Thumb size: at least 24 px desktop and 32 px touch devices.
- Include visible minimum and maximum labels once confirmed.
- Endpoint and midpoint wording are TBC.

Behaviour:

- The participant must actively provide a rating for each mix.
- Do not silently treat the default slider position as a submitted response unless the participant has interacted with it or explicitly confirms it.
- Keyboard adjustment must be supported.

### Audio Player

The audio player should support focused repeat listening without biasing mix versions.

Specifications:

- One player per mix version, or a consistent player pattern that makes the active mix unmistakable.
- Display only neutral version labels: Version A, Version B, Version C.
- Use identical visual treatment for all versions.
- Controls should be large enough for touch and keyboard use.
- Playback may be repeated as many times as the participant wishes.

Behaviour:

- The player should not expose real mix identity, filenames, internal condition names, or processing labels.
- Detailed playback-event recording remains TBC and should not be assumed by the UI design.

### Validation Messages

Validation should be clear, calm, and specific.

Specifications:

- Place messages near the relevant field or group.
- Use Error colour plus text and icon.
- Avoid blameful wording.
- Explain what is required to continue.

Trial validation should cover:

- Missing rating for Version A, B, or C.
- Missing required comment for Version A, B, or C.
- Empty or whitespace-only comments.

### Information Banners

Information banners should provide neutral guidance or context.

Specifications:

- Use subtle background tint.
- Include a short heading and concise body text.
- Do not interrupt the task unless necessary.
- Suitable for study instructions, privacy reminders, or playback setup notes.

### Warning Banners

Warning banners should be reserved for important issues that may block or affect participation.

Specifications:

- Use Warning colour with sufficient contrast.
- Include a clear action or next step.
- Avoid overuse, especially during trials.
- Suitable for incomplete required fields, failed screening, or submission problems.

## 6. Accessibility

Contrast:

- Text and controls must meet WCAG AA contrast as a baseline.
- Body text should target at least 4.5:1 contrast.
- Large headings and icons should remain clear against their background.
- Error and warning states must include text, not colour alone.

Keyboard navigation:

- Every interactive element must be reachable by keyboard.
- Tab order must follow the visual reading order.
- Audio controls, sliders, checkboxes, radios, text areas, and navigation buttons must all be operable by keyboard.
- Do not trap focus except inside modal dialogs, if any are later introduced.

Screen reader support:

- Each page should have a clear page heading.
- Form controls must have persistent accessible labels.
- Related controls should be grouped with clear group labels.
- Progress should be exposed as text, not only as a visual bar.
- Validation errors should be announced or clearly associated with the affected field.

Focus indicators:

- Use a visible focus ring on every interactive element.
- Recommended focus ring colour: Primary.
- Focus ring should be at least 2 px thick with enough offset to remain visible.
- Do not remove default focus styles unless replacing them with an equally visible style.

Minimum touch targets:

- Minimum: 44 x 44 px.
- Preferred for audio controls and slider thumbs: 48 x 48 px or larger.
- Maintain enough spacing between adjacent controls to prevent accidental activation.

Responsive behaviour:

- All pages must work on desktop, tablet, and mobile.
- Text must reflow without horizontal scrolling.
- Long words, labels, and validation messages must wrap safely.
- Sliders and audio controls must remain usable on small screens.

## 7. Icons

Recommended icon library: Lucide.

Lucide is suitable because it is simple, modern, open, and visually restrained. Use icons only when they improve recognition, such as playback, warning, success, back, continue, information, or completion states.

Guidance:

- Pair unfamiliar icons with text.
- Do not use icons as decoration.
- Keep stroke weight consistent.
- Ensure icons meet contrast requirements.
- Icons must not replace required text labels for consent, rating, or submission actions.

## 8. Motion

Motion should be subtle and functional.

Allowed motion:

- Short focus or hover transitions.
- Gentle progress updates.
- Small validation reveal transitions.
- Loading or submission indicators.

Avoid:

- Decorative animation.
- Parallax.
- Large page transitions.
- Looping motion near listening tasks.
- Motion that could distract from audio judgement.

Recommended duration:

- 120-180 ms for simple state changes.
- 200-250 ms maximum for validation or page transition cues.

Respect reduced-motion preferences. If a participant has reduced motion enabled, animations should be removed or reduced to instant state changes.

## 9. Page Consistency Rules

Every page should use the same:

- Content width rules.
- Typography scale.
- Card styling.
- Button hierarchy.
- Form control styling.
- Focus indicators.
- Validation message style.
- Progress indicator placement.
- Navigation placement.

Page-specific guidance:

- Reading pages should emphasise calm text layout and clear continuation.
- Consent pages should use explicit checkbox groups and approved wording.
- Screening and practice pages should use the same control patterns as the main study where possible.
- Trial pages should present Version A, Version B, and Version C with identical visual weight.
- Questionnaire pages should use consistent field spacing and clear grouping.
- Review and final submission should feel confirmatory, not celebratory or commercial.
- Completion should be calm, concise, and aligned with approved debriefing wording once available.

Do not introduce new visual styles for individual scenarios, excerpts, or mix versions. Visual variation must not imply that one mix version is more important or higher quality than another.

## 10. Future Development Notes

This design system should guide implementation after Phase 1 without dictating a specific frontend framework or backend stack.

Implementation should:

- Treat this document as the source of visual and interaction rules.
- Treat `specification.md`, `study-configuration.md`, and `ui-flow.md` as the source of study behaviour.
- Treat the approved PIS and consent files in `docs/participant-materials/` as the authoritative wording source.
- Preserve neutral Version A, Version B, and Version C presentation.
- Enforce required ratings and required comments before trial submission.
- Record response-time timestamps as required by the study documentation.
- Keep detailed playback-event logging separate until that requirement is resolved.
- Avoid collecting direct identifiers.
- Recheck accessibility before pilot testing.

Any future visual change should be assessed against the goals of calmness, trustworthiness, neutrality, readability, and accessibility.
