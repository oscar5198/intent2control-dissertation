# Phase 6B.4 Prompt-Data Object Schema

Canonical format: deterministic JSONL, one JSON object per line.

Canonical unit:

```text
one object = one prediction example x one information condition
```

Phase 6B.4 produces structured prompt data only. It does not produce final
natural-language LLM prompts, API messages, model responses, predictions,
performance results, or hidden ground-truth answers.

## Conditions

Canonical exported condition labels:

- `non_history`
- `personalised_history`

Each prediction example always produces a `non_history` object. A
`personalised_history` object is produced only when Phase 6B.3 has
`personalised_history_available == true`.

## Top-Level Fields

| Field | Type | Description |
| --- | --- | --- |
| `condition_object_id` | string | Deterministic ID: `prediction_example_id + "__" + condition`. |
| `prediction_example_id` | string | Stable link back to the Phase 6B.3 prediction example and hidden scoring lookup. |
| `condition` | string | `non_history` or `personalised_history`. |
| `schema_version` | string | Phase 6B.4 prompt-data schema version. |
| `prompt_data_builder_version` | string | Deterministic builder version. |
| `pipeline_metadata` | object | Operational metadata for audit/provenance. Not consumed by the future prompt renderer. |
| `model_input` | object | The only block intended for future prompt rendering. Contains no hidden ground truth. |

## `pipeline_metadata`

Includes source schema/build versions, protocol reference, target trial ID,
history availability counts, primary acoustic feature list, excluded
sensitivity feature list, and the numeric precision rule.

Operational fields such as `n_history_trials_available` and
`personalised_history_available` stay in `pipeline_metadata`, not in
`model_input`, so the non-history condition does not receive participant-history
availability evidence.

## `model_input`

### Shared Fields

Both conditions contain:

- `participant_metadata`
- `target`

The paired `non_history` and `personalised_history` objects for the same
`prediction_example_id` must have structurally identical participant metadata
and target payloads.

### Participant Metadata

Only the Phase 6A frozen metadata fields are included:

- `age_range`
- `gender`
- `cultural_influence_country`
- `music_listening_habits`
- `music_production_or_audio_engineering_experience`
- `hearing_difficulty`

Missing values remain JSON `null`.

### Target

Target fields:

- `trial_order`
- `context`
- `song`
- `candidates`

Target `context` contains `episode_id`, `context_title`, `context_label`,
`context_text`, and `context_dominant_function`. Scenario wording is copied
without rewriting.

Target `song` contains `song_id`, `excerpt_id`, `participant_song_label`, and
`song_title`.

Each target candidate contains:

```json
{
  "label": "A",
  "acoustic_features": {
    "z_RMS": -1.0251,
    "z_CF": 0.52,
    "z_SW": -0.8666
  }
}
```

Candidates are ordered A-E. Primary acoustic values are rounded to four decimal
places for deterministic serialization. Human history ratings remain unrounded
0-100 values.

Primary model-facing candidates exclude:

- `z_SI` and `z_SI_role`
- `stimulus_id`
- `actual_mix_id`
- `audio_path`
- `acoustic_feature_table_used`
- target `human_rating`
- target `comparative_comment`
- target observed ranks/preferred-set/preferred-mix/tie fields

### Non-History

`non_history` contains no `history` field in `model_input`.

### Personalised History

`personalised_history` adds `history`, copied from Phase 6B.3 eligible history
evidence and transformed to primary prompt-data fields.

Each history trial contains:

- `trial_order`
- `context`
- `song`
- `candidates`
- `comparative_comment`

History candidates contain `label`, primary `acoustic_features`, and
`human_rating`. History comments are preserved verbatim when available and
represented as `null` when missing. No winner summaries, inferred listener
profiles, or aggregate behaviour features are derived.

## Validation

The builder validates:

- deterministic condition IDs;
- no duplicate condition objects;
- no `ground_truth` in condition objects;
- no hidden target outcome fields in `model_input.target`;
- no target ratings/comments in model-facing target payloads;
- no `z_SI` in primary model-facing payloads;
- no underlying candidate IDs, mix IDs, audio paths, or feature-source paths in
  `model_input`;
- history ratings only appear inside personalised-history history candidates;
- paired conditions have identical participant metadata and target payloads.

