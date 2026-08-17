# Phase 6B.3 Prediction Example Schema

Canonical format: deterministic JSONL, one JSON object per line.

Canonical unit: one participant x one held-out target trial.

Phase 6B.3 produces data objects only. It does not produce natural-language
prompts, API messages, LLM responses, model predictions, or performance
statistics.

## Top-Level Fields

| Field | Type | Description |
| --- | --- | --- |
| `prediction_example_id` | string | Deterministic ID formed from `participant_id` and target `trial_id`; independent of ratings/preference outcomes. |
| `participant_id` | string | Anonymous participant ID copied from Phase 6B.1/6B.2. |
| `schema_version` | string | Phase 6B.3 nested example schema version. |
| `example_builder_version` | string | Deterministic builder version. |
| `protocol_reference` | string | Reference to the Phase 6A frozen protocol. |
| `input_data` | object | Model-facing data. This is the only block Phase 6B.4 may use to construct prompts. |
| `n_history_trials` | integer | Number of other history-eligible participant trials attached. |
| `personalised_history_available` | boolean | `true` when `n_history_trials >= 1`; non-history evaluation remains possible when `false`. |
| `ground_truth` | object | Hidden evaluation-only scoring data. This block must never be passed to the LLM. |

## `input_data`

| Field | Type | Description |
| --- | --- | --- |
| `participant_metadata` | object | Frozen Phase 6A metadata: `age_range`, `gender`, `cultural_influence_country`, `music_listening_habits`, `music_production_or_audio_engineering_experience`, `hearing_difficulty`. Missing values are `null`. |
| `target` | object | Held-out trial context and candidate acoustic/stimulus information. Target ratings, comments, preference sets, and ranks are excluded. |
| `history` | array | Other trials for the same participant with `history_eligible == True`, excluding the target by exact `trial_id`, ordered by `trial_order` then `trial_id`. |

## `input_data.target`

| Field | Type | Description |
| --- | --- | --- |
| `trial_id` | string | Held-out target trial ID. |
| `trial_order` | integer/null | Original study trial order. |
| `trial_index` | integer/null | Raw trial index. |
| `episode` | object | `episode_id`, `scenario_id`, `context_title`, `context_label`, `context_text`, `context_dominant_function`, `episode_position`. |
| `song` | object | `song_id`, `excerpt_id`, `song_position`, `participant_song_label`, `song_title`. |
| `candidates` | array | Five target candidates in deterministic A-E order. |

Target candidates contain only `presentation_label`, `stimulus_id`,
`actual_mix_id`, `audio_path`, `z_RMS`, `z_CF`, `z_SW`, `z_SI`, `z_SI_role`,
and `acoustic_feature_table_used`.

Target candidates must not contain `human_rating`, `observed_rank`,
`is_observed_preferred`, `observed_preferred_set`, `observed_preferred_mix`,
`observed_max_rating`, `is_single_winner`, `n_preferred_tied`, or the target
`comparative_comment`.

## `input_data.history[]`

Each history trial contains `trial_id`, `trial_order`, `trial_index`, `episode`,
`song`, `candidates`, `comparative_comment`, and
`history_comment_available`.

History candidates use the target-candidate fields plus `human_rating`.
History comments are copied only for the history trial itself. Missing comments
are represented as `null`; no text is fabricated.

## `ground_truth`

Hidden scoring fields:

| Field | Type | Description |
| --- | --- | --- |
| `target_trial_id` | string | Target trial ID for scoring alignment. |
| `human_ratings` | object | Ratings for A-E. |
| `observed_ranks` | object | Tie-aware observed ranks for A-E. |
| `observed_preferred_set` | array | All maximum-rated candidate labels in A-E order. |
| `observed_preferred_mix` | string/null | Unique preferred label only for single-winner trials. |
| `is_single_winner` | boolean | Whether the target has a unique maximum rating. |
| `n_preferred_tied` | integer | Number of labels in `observed_preferred_set`. |

This block is evaluation-only and is explicitly excluded from model-facing
prompt construction.

