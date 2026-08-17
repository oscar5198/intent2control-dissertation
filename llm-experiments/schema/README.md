# Phase 6B Data Contracts

`analysis_ready_schema.csv` defines the canonical long-format contract for the
Phase 6B.1 LLM evaluation data pipeline.

The canonical row unit is:

```text
one row = one participant x one experimental trial x one candidate mix
```

A complete active five-mix participant should normally produce 30 rows: six
trials with five anonymous A-E candidates per trial.

The Phase 6B.1 schema intentionally preserves human ratings and comparative
comments but does not derive preferred labels, winner indicators, observed
rankings, or held-out examples.

Column levels:

- participant: constant across the participant's submitted study record.
- trial: shared by the five candidate rows within a participant-trial.
- candidate: specific to one A-E candidate within a participant-trial.

Acoustic features are joined by stable `stimulus_id`, never by anonymous A-E
presentation label alone.

## Phase 6B.2 Ground-Truth Targets

`preference_target_schema.csv` documents the deterministic human
ground-truth fields introduced in Phase 6B.2.

Phase 6B.2 produces:

- `candidate_ground_truth_enriched.csv`: the Phase 6B.1 candidate-level rows
  plus derived target fields.
- `trial_ground_truth_targets.csv`: one row per participant x trial with the
  complete rating-derived human target.

All Phase 6B.2 fields are human outcome-derived variables. They must never be
included in the target LLM prompt. Later held-out-example generation should
store these fields as hidden ground truth only.

Target eligibility is based on rating and mapping validity:

- exactly five candidate rows;
- labels exactly A-E once each;
- valid mapping with no mapping-response disagreement;
- no duplicate candidate mapping;
- one numeric 0-100 rating for each label.

Participant metadata missingness does not invalidate target construction.
Comment availability is tracked separately through `history_comment_available`
so Phase 6B.3 can distinguish rating-derived target eligibility from
personalised-history content availability.

Tie convention:

- `observed_preferred_set` is a deterministic JSON array string in A-E order.
- Single-winner trials also fill `observed_preferred_mix`.
- Tied maximum-rating trials leave `observed_preferred_mix` blank; no
  alphabetical or presentation-order tie breaker is applied.
- Observed ranks use descending average ranks, where the highest rating has
  rank 1 and tied ratings receive the average of the ranks they occupy.

## Phase 6B.3 Prediction Examples

`prediction_example_schema.md` documents the canonical nested JSONL contract
introduced in Phase 6B.3.

The canonical example unit is:

```text
one JSON object = one participant x one held-out target trial
```

Every Phase 6B.2 trial with `target_eligible == True` produces one prediction
example. Target-ineligible trials are skipped as targets and counted in the
audit summary with their existing Phase 6B.2 exclusion reasons.

History is constructed by explicit target exclusion:

- choose other trials from the same `participant_id`;
- exclude the held-out target by exact `trial_id`;
- retain only trials with `history_eligible == True`;
- order history by `trial_order` ascending, then `trial_id`.

The generator stores `n_history_trials` and
`personalised_history_available == True` when at least one usable history trial
exists. Non-history evaluation remains possible even when personalised history
is unavailable.

Phase 6B.3 enforces an explicit separation:

- `input_data`: model-facing participant metadata, target context/candidates,
  and eligible history evidence.
- `ground_truth`: hidden evaluation-only target ratings, ranks, preferred set,
  unique preferred mix where applicable, and tie fields.

Target ratings, target comparative comments, target ranks, target preferred
sets, and target preferred-mix fields are forbidden from `input_data.target`.
Automated leakage validation is part of the builder and test suite.

## Phase 6B.4 Prompt-Data Objects

`prompt_data_schema.md` documents the condition-specific structured prompt-data
contract introduced in Phase 6B.4.

The canonical unit is:

```text
one object = one prediction example x one information condition
```

Canonical conditions are `non_history` and `personalised_history`. Every
prediction example produces a `non_history` object. A `personalised_history`
object is produced only when the Phase 6B.3 example has usable participant
history.

Phase 6B.4 separates:

- `model_input`: the only block intended for future prompt rendering.
- `pipeline_metadata`: audit/provenance fields such as source schema versions,
  history availability, feature policy, and precision rule.

The paired conditions for a prediction example must be identical for
participant metadata and target payload. They differ only by the eligible
history evidence included in `personalised_history`.

Primary model-facing acoustic features are `z_RMS`, `z_CF`, and `z_SW`, rounded
to four decimal places. The sensitivity-only feature `z_SI`, underlying
stimulus IDs, actual mix IDs, audio paths, and feature-source paths are excluded
from `model_input`. Human ratings are allowed only for history candidates in
the personalised-history condition.

Phase 6B.4 still does not create natural-language prompts, LLM calls,
predictions, or performance results.

## Phase 6B.5 Synthetic Integration Freeze

Phase 6B.5 defines the end-to-end synthetic validation path:

```text
synthetic raw export
-> 6B.1 analysis-ready long data
-> 6B.2 hidden preference targets
-> 6B.3 prediction examples
-> 6B.4 prompt-data objects
```

The canonical command is:

```powershell
python llm-experiments\scripts\run_phase6b_synthetic_pipeline.py
```

The runner writes integration artifacts to
`llm-experiments/outputs/synthetic/phase6b5/`. Its audit report freezes
synthetic structural counts and validates schema shape, identifier integrity,
held-out target leakage prevention, provenance exclusion from `model_input`,
history rotation, A-E acoustic mapping, paired-condition equivalence, and
byte-for-byte determinism for canonical CSV/JSONL outputs.

The authoritative hidden scoring source remains the Phase 6B.3 prediction
example JSONL. Final prompt-data objects retain only `prediction_example_id` for
later joining and contain no hidden answer block.

`READY_FOR_LLM_INFERENCE` is a validation gate, not an execution trigger. It can
be true for the synthetic pipeline only when every Phase 6B.5 audit passes.
