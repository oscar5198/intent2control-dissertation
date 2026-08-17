# Phase 6D.1 Prompt Specification

Prompt specification version: `phase6d_prompt_spec_v1`

Response schema version: `preference_prediction_response_v1`

Status: frozen model-agnostic semantic prompt contract for later Phase 6 LLM
inference. This specification does not call LLM APIs, benchmark prompt variants,
select model-specific wording, inspect partial real participant outcomes, or
implement provider adapters.

## Task Definition

Exact prediction-task wording:

> Predict which anonymous mix A-E this specific participant is most likely to rate highest for the target listening situation.

The task predicts this participant's preference in this target listening
context among five anonymous candidate mixes A-E. It is not objective
audio-quality assessment, technical mix selection, population-average
preference prediction, or selection of the acoustically most balanced candidate.

Predicted ratings represent the participant's expected 0-100
suitability/preference ratings for the five mixes in the target listening
situation. They are not probabilities, confidence percentages, or objective
audio-quality scores.

## System Instruction

Exact frozen system instruction:

```text
You are predicting individual listener preference in a music listening study. Infer this participant's likely 0-100 ratings and most preferred anonymous mix for the supplied target situation. Use only the supplied participant, context, acoustic-feature, and history information. Do not assume anything about underlying mixes beyond the supplied anonymous labels and feature values. Return only the specified JSON object, with no explanatory prose outside the JSON.
```

No hidden reasoning, rationale, or chain-of-thought is requested.

## User Message Architecture

The same task wording, feature explanations, candidate presentation rules,
response schema, and output instructions are used for every evaluated model and
both principal conditions. The only substantive condition difference is whether
eligible previous participant trials are present.

### Non-History Section Order

1. Task
2. Target listening situation
3. Participant information
4. Acoustic feature guide
5. Target candidate mixes
6. Prediction/output instructions

The non-history condition must not mention that history exists but has been
withheld.

### Personalised-History Section Order

1. Task
2. Target listening situation
3. Participant information
4. Acoustic feature guide
5. Target candidate mixes
6. Previous listening evidence from this participant
7. Prediction/output instructions

Previous trials are rendered in deterministic original `trial_order`.

## Participant Metadata

Render exactly these Phase 6A frozen fields with these labels:

| Field | Display label |
| --- | --- |
| `age_range` | Age range |
| `gender` | Gender |
| `cultural_influence_country` | Cultural influence country |
| `music_listening_habits` | Music listening habits |
| `music_production_or_audio_engineering_experience` | Music production/audio engineering experience |
| `hearing_difficulty` | Hearing difficulty |

Missing metadata value: `Not provided`

Do not add participant variables outside this set.

## Target Context

Render the target listening situation under `Target listening situation`.
Copy the canonical Phase 6B context text without rewriting or paraphrasing. Do
not include target participant comments, target ratings, target ranks, target
preferred labels, or target tie information.

## Acoustic Feature Guide

Render the same feature guide in both conditions:

```text
The acoustic values are z-scores standardized across the study stimulus set: 0 is approximately the study-stimulus average, positive values are above that average, and negative values are below that average. Positive or negative values are not inherently better.
```

Feature glosses:

| Feature | Prompt label | Definition |
| --- | --- | --- |
| `z_RMS` | RMS level z-score | Standardized measure of average signal energy/level. |
| `z_CF` | Crest factor z-score | Standardized measure of peak-to-average contrast/dynamic character. |
| `z_SW` | Stereo width z-score | Standardized measure of stereo spatial spread. |

These descriptors are descriptive only. The prompt must not state that louder,
wider, higher/lower crest-factor, or any acoustic profile is inherently better
or more suitable for a scenario.

## Numeric Precision

Phase 6B structured prompt-data objects retain primary acoustic values to four
decimal places. Natural-language prompt rendering rounds acoustic z-scores to
exactly two decimal places for readability and consistency across models.

History ratings retain their recorded 0-100 values and are not rounded beyond
the recorded value.

## Candidate Rendering

Target candidates are rendered in fixed A-E order. For each candidate, display:

- anonymous label;
- RMS z-score;
- crest-factor z-score;
- stereo-width z-score.

Do not include target `stimulus_id`, `actual_mix_id`, audio filename/path,
target human rating, target preference, target rank, target comment, or
candidate source/provenance fields. Do not sort candidates by acoustic value.

## Song Identity Policy

Render only the participant-facing within-study song label, such as `Song A` or
`Song B`.

Rationale: the task needs enough song identity to distinguish target and
history trials within the participant's study experience, but actual song
titles, `song_id`, `excerpt_id`, filenames, and mix identities are unnecessary
for the prediction task and could introduce external memorisation shortcuts.
This is a rendering policy only; it does not modify Phase 6B source objects.

## History Rendering

The personalised-history section is titled:

```text
Previous listening evidence from this participant
```

Each prior trial shows:

- prior listening situation/context;
- participant-facing song label;
- candidate A-E primary acoustic descriptors;
- participant's human 0-100 rating for each candidate;
- participant comparative comment.

History ratings are explicitly described as ratings previously given by the
same participant. They are not confidence values.

Missing history comments render as `Not provided`. Do not generate replacement
comments.

Do not add derived preferred-mix labels, inferred listener profiles, acoustic
preference summaries, or averages across history trials.

## Response Schema

The LLM must return exactly three semantic outputs:

```json
{
  "predicted_preferred_mix": "C",
  "predicted_ratings": {
    "A": 62,
    "B": 48,
    "C": 81,
    "D": 70,
    "E": 55
  },
  "predicted_ranking": ["C", "D", "A", "E", "B"]
}
```

Rules:

- `predicted_preferred_mix` must be one of `A`, `B`, `C`, `D`, or `E`.
- `predicted_ratings` must contain exactly A-E as JSON numbers from 0 to 100.
- Predicted ratings may be integers or decimals.
- `predicted_ranking` must contain exactly A-E once each, ordered from most
  preferred to least preferred.
- Even if numeric ratings tie, the model must provide a complete ranking.
- Ideally, `predicted_preferred_mix`, the highest predicted rating, and the
  first ranking entry should agree. Phase 6A's deterministic consistency rule
  remains authoritative for later scoring.
- No rationale, explanation, reasoning trace, confidence field, or extra
  top-level field is part of the primary response contract.

Machine-readable schema:

```text
llm-experiments/schema/preference_prediction_response_v1.json
```

## Format-Repair Instruction

Phase 6A permits one structural repair retry. Exact semantic repair instruction:

```text
Your previous response did not match the required JSON format. Repair formatting only and return exactly one JSON object that conforms to the supplied schema. Do not add new participant information, do not include ground truth or correctness feedback, and do not hint which candidate should win.
```

The repair retry may contain the invalid response and required JSON Schema. It
must not contain ground truth, correctness feedback, candidate hints, or new
participant information.

## Prohibited Prompt Content

Primary prompts must not include:

- target human ratings;
- target comparative comment;
- observed preferred mix/set;
- observed ranks;
- target tie information;
- `ground_truth`;
- `stimulus_id`;
- `actual_mix_id`;
- audio filename/path;
- actual mix names or source engineer labels;
- sensitivity-only `z_SI`;
- statistical-baseline predictions;
- few-shot demonstrations;
- researcher-authored acoustic preference priors.

History ratings and comments are allowed only in the personalised-history
section and only for eligible non-target previous trials.

## Provider Neutrality

Provider adapters may change only technical transport mechanisms:

- system/user message API packaging;
- JSON-schema enforcement mechanism;
- provider-specific structured-output parameter;
- endpoint-specific serialization details.

They may not change semantic prompt content, task wording, section order,
feature definitions, candidate rendering, response fields, missing-value
rendering, or condition equivalence.

## Phase 6D.2 Renderer Implementation

The deterministic model-agnostic renderer is implemented in:

```text
llm-experiments/src/llm_experiments/prompts/render.py
```

The renderer consumes one Phase 6B.4 condition object at a time and emits a
canonical rendered-prompt object with exactly two messages: the frozen system
instruction and the frozen rendered user prompt. It also provides batch JSONL
rendering, leakage validation, matched-condition equivalence validation,
deterministic rendered prompt IDs, and a format-repair prompt renderer.

Rendered prompt IDs use:

```text
condition_object_id + "__" + phase6d_prompt_spec_v1
```

The canonical rendered-prompt schema is:

```text
llm-experiments/schema/rendered_prompt_v1.json
```

Synthetic rendered prompts and the provider-neutral size/equivalence/leakage
audit are written to:

```text
llm-experiments/outputs/synthetic/phase6d2_rendered_prompts/
```

## Phase 6D.3 Condition Integrity Validation

The Phase 6D.3 validator freezes the experimental-condition integrity gate for
the rendered prompt objects. It performs formal validation only; it does not
change the frozen prompt wording, call LLM APIs, implement provider adapters,
inspect real participant outcomes, or compute model-performance metrics.

The validator compares matched `non_history` and `personalised_history`
rendered prompts as structured system/user sections rather than relying only on
raw string diffs. The sections that must remain identical across conditions
are:

- system instruction;
- task wording;
- target listening situation;
- participant information;
- acoustic feature guide;
- target candidate mixes;
- prediction/output instructions.

The only allowed condition difference is that the personalised-history prompt
contains the additional section titled:

```text
Previous listening evidence from this participant
```

The validator also checks:

- target-outcome leakage;
- provenance/identifier leakage;
- sensitivity-only `z_SI` leakage;
- non-history contamination by previous-trial evidence;
- target-trial overlap inside personalised history;
- personalised-history consistency with the Phase 6B source object;
- comment-boundary integrity for participant-provided comments;
- format-repair prompt isolation;
- schema/version consistency;
- deterministic rerun stability;
- provider-neutral prompt-size differences.

Prompt lengths are intentionally not artificially balanced. The
personalised-history condition is longer only because the manipulation adds
eligible previous participant evidence.

Synthetic condition-integrity outputs are written to:

```text
llm-experiments/outputs/synthetic/phase6d3_condition_validation/
```

## Phase 6D.4 Prompt Package Freeze

The frozen Phase 6D package version is:

```text
phase6d_prompt_package_v1
```

This package version is separate from the semantic prompt-specification version
and represents the complete combination of semantic prompt, deterministic
renderer, response schema, condition definitions, validation rules, reasoning
policy, few-shot policy, repair policy, acoustic-input contract,
participant-metadata contract, and provider-adapter boundary.

The machine-readable package manifest is:

```text
llm-experiments/prompts/phase6d_prompt_package_manifest.json
```

The manifest records SHA-256 hashes for the canonical prompt-package artifacts
so Phase 6E preflight checks can detect accidental drift before inference.

The package completion gate is:

```text
PHASE6D_PROMPT_PACKAGE_FROZEN
```

It may be `true` only when prompt-spec and response-schema versions are
consistent, the renderer uses the frozen prompt specification, rendered prompts
are deterministic, matched-condition equivalence passes, leakage checks pass,
`z_SI` is absent, target/history overlap checks pass, the response schema is
machine-valid, representative synthetic prompts render successfully, and
relevant Phase 6D tests pass.

Primary inference policy:

- zero-shot;
- no requested chain-of-thought;
- no rationale or reasoning output field;
- no few-shot demonstrations;
- only `predicted_preferred_mix`, `predicted_ratings`, and
  `predicted_ranking` are scored.

Repair policy:

- maximum primary generation attempts: 1;
- maximum formatting-only repair attempts: 1;
- repair receives no ground truth;
- repair receives no correctness feedback;
- repair gives no candidate hint;
- failed repair is marked invalid/missing.

Phase 6E provider adapters may change API request format, message transport,
native schema-enforcement syntax, tokenizer-specific counting, and model
endpoint parameters. They may not change the system instruction, user-message
semantic content, history evidence, candidate order, participant metadata,
acoustic values, task definition, or response semantics.

Once `phase6d_prompt_package_v1` is frozen, any substantive modification to
prompt wording, history structure, metadata fields, feature descriptions,
output schema, reasoning/few-shot policy, acoustic-input contract, candidate
ordering, or condition definition requires a new package version. Cosmetic
documentation changes that do not affect semantic artifacts should be
distinguished from package-changing edits where practical.
