# LLM Experiments

This directory contains the planned LLM prediction work for the dissertation.
It does not yet represent completed model results.

## Current Files

- `llm_evaluation_protocol.md`: pre-registration-style protocol for the planned
  LLM evaluation.
- `LLM_Environment_Test.ipynb`: environment-testing notebook for future LLM work.
- `src/llm_experiments/data/`: Phase 6B.1 raw-to-analysis-ready data pipeline.
- `schema/analysis_ready_schema.csv`: canonical long-format data contract.
- `schema/preference_target_schema.csv`: Phase 6B.2 human ground-truth target
  contract.
- `schema/prediction_example_schema.md`: Phase 6B.3 nested JSONL prediction
  example contract.
- `schema/prompt_data_schema.md`: Phase 6B.4 condition-specific structured
  prompt-data contract.
- `schema/preference_prediction_response_v1.json`: Phase 6D.1 strict response
  JSON Schema for LLM preference predictions.
- `schema/rendered_prompt_v1.json`: Phase 6D.2 model-agnostic rendered-prompt
  object schema.
- `prompts/prompt_specification.md`: Phase 6D.1 frozen model-agnostic prompt
  specification.
- `prompts/phase6d_prompt_template_v1.json`: provider-neutral prompt template
  contract for later rendering/adapters.
- `prompts/phase6d_prompt_package_manifest.json`: Phase 6D.4 frozen
  prompt-package manifest with SHA-256 artifact hashes.
- `prompts/phase6e_provider_adapter_boundary.md`: explicit boundary for
  future provider adapters.
- `scripts/build_analysis_ready_dataset.py`: CLI wrapper for the Phase 6B.1
  transformation.
- `scripts/build_preference_targets.py`: CLI wrapper for deterministic Phase
  6B.2 target derivation from a Phase 6B.1 file.
- `scripts/build_prediction_examples.py`: CLI wrapper for deterministic Phase
  6B.3 leave-one-trial-out example generation from Phase 6B.2 files.
- `scripts/build_prompt_data_objects.py`: CLI wrapper for deterministic Phase
  6B.4 condition-specific prompt-data objects from Phase 6B.3 JSONL.
- `scripts/render_phase6d_synthetic_prompt_examples.py`: CLI wrapper for
  rendering Phase 6D.1 matched synthetic prompt examples and audits.
- `scripts/render_prompts.py`: CLI wrapper for Phase 6D.2 deterministic
  model-agnostic batch prompt rendering from Phase 6B.4 prompt-data objects.
- `scripts/validate_experimental_conditions.py`: CLI wrapper for Phase 6D.3
  matched-condition integrity, leakage, and manipulation validation.
- `scripts/verify_prompt_package.py`: Phase 6D.4 prompt-package hash
  verification and preflight command for Phase 6E.
- `scripts/run_phase6e1_inference.py`: Phase 6E.1 dry-run/mock runner for the
  model-agnostic inference interface.
- `scripts/validate_phase6e2_config.py`: Phase 6E.2 primary inference
  configuration validator and synthetic request-matrix builder.
- `scripts/run_phase6e3_logging.py`: Phase 6E.3 synthetic mock logging runner
  for attempt logs, prediction records, run manifests, and summaries.
- `scripts/run_phase6e4_failure_matrix.py`: Phase 6E.4 synthetic
  failure-matrix runner for bounded retry, repair, resume, and terminal-state
  handling.
- `scripts/run_phase6f_synthetic_pipeline.py`: Phase 6F.1 one-command
  synthetic end-to-end validation runner for Phase 6B-D-E orchestration and
  Phase 6C baseline alignment.
- `config/phase6e_failure_policy_v1.json`: Phase 6E.4 versioned
  failure-handling policy.
- `scripts/run_phase6b_synthetic_pipeline.py`: one-command Phase 6B.5
  synthetic end-to-end integration and validation runner.
- `phase6e1_inference_framework.md`: Phase 6E.1 architecture documentation for
  the unified inference interface.
- `phase6e2_primary_inference_configuration.md`: Phase 6E.2 model identity,
  backend capability, inference setting, and freeze-gate documentation.
- `phase6e3_prediction_logging.md`: Phase 6E.3 logging/provenance contract,
  output layout, resume behavior, and distributed merge notes.
- `phase6e4_failure_handling.md`: Phase 6E.4 failure taxonomy, state machine,
  retry/repair policy, completion gates, and synthetic failure-matrix notes.

## Scope

The planned evaluation asks whether text-based foundation models can predict
listener-preferred music mixes from the same semantic listening contexts used in
the human study. Final model identifiers, prompts, parameters, provider
metadata, raw responses, and comparison results should be frozen and saved here
only when the evaluation is actually run.

## Phase 6B.1 Data Pipeline

The analysis-ready pipeline converts a raw five-mix Netlify participant-level
CSV export into a canonical long-format table with one row per participant x
trial x candidate mix. It preserves ratings and comments but deliberately does
not derive preferred mixes, winners, rankings, held-out examples, prompts, or
LLM predictions.

Run on synthetic/test data:

```powershell
python llm-experiments\scripts\build_analysis_ready_dataset.py `
  --input llm-experiments\fixtures\synthetic\phase6b1_five_mix_netlify_export.csv `
  --output-dir llm-experiments\outputs\synthetic\phase6b1
```

Do not run this on real participant exports unless the output location is
approved for study data handling. Raw real exports and generated real
participant analysis files should not be committed.

Build synthetic/test preference targets:

```powershell
python llm-experiments\scripts\build_preference_targets.py `
  --input llm-experiments\outputs\synthetic\phase6b1\analysis_ready_long.csv `
  --output-dir llm-experiments\outputs\synthetic\phase6b2
```

Phase 6B.2 outputs are human outcome-derived. They are for hidden ground-truth
evaluation data only and must not be inserted into target LLM prompts.

Build synthetic/test prediction examples:

```powershell
python llm-experiments\scripts\build_prediction_examples.py `
  --candidates llm-experiments\outputs\synthetic\phase6b2\candidate_ground_truth_enriched.csv `
  --targets llm-experiments\outputs\synthetic\phase6b2\trial_ground_truth_targets.csv `
  --output-dir llm-experiments\outputs\synthetic\phase6b3
```

Phase 6B.3 produces deterministic JSONL data objects, not final LLM prompts.
Each object is one participant x held-out target trial. The target trial must
have `target_eligible == True`; personalised history is built from other trials
for the same participant with `history_eligible == True`, ordered by
`trial_order` then `trial_id`.

The nested example contract separates `input_data` from hidden `ground_truth`.
Only `input_data` is model-facing. The target's ratings, comparative comment,
observed ranks, preferred set, preferred mix, and maximum-rating fields are
retained only in `ground_truth` for later scoring. The builder validates this
boundary automatically.

Build synthetic/test condition-specific prompt-data objects:

```powershell
python llm-experiments\scripts\build_prompt_data_objects.py `
  --examples llm-experiments\outputs\synthetic\phase6b3\prediction_examples.jsonl `
  --output-dir llm-experiments\outputs\synthetic\phase6b4
```

Phase 6B.4 produces structured prompt data, not natural-language LLM prompts.
Each condition object has pipeline metadata and a separate `model_input` block.
The future prompt renderer should consume only `model_input`.

For each prediction example, Phase 6B.4 always creates a `non_history` object
and creates a `personalised_history` object only when usable participant
history is available. The two paired conditions have identical participant
metadata and target payloads; they differ only by the presence of eligible
history evidence.

Primary model-facing acoustic features are `z_RMS`, `z_CF`, and `z_SW`, rounded
to four decimal places for deterministic serialization. The sensitivity-only
feature `z_SI`, underlying stimulus IDs, mix IDs, audio paths, and feature-source
paths are excluded from `model_input`.

## Phase 6B.5 Synthetic Integration Freeze

Run the complete synthetic Phase 6B validation from the repository root:

```powershell
python llm-experiments\scripts\run_phase6b_synthetic_pipeline.py
```

This command deterministically runs:

```text
synthetic raw export
-> Phase 6B.1 analysis-ready long data
-> Phase 6B.2 hidden preference targets
-> Phase 6B.3 leave-one-trial-out prediction examples
-> Phase 6B.4 condition-specific prompt-data objects
```

It writes integration evidence to
`llm-experiments/outputs/synthetic/phase6b5/`, including machine-readable audit
JSON, deterministic final synthetic artifacts, and
`phase6b_validation_report.md`.

The runner executes leakage, provenance, paired-condition equivalence,
determinism, schema, identifier-integrity, history-rotation, acoustic mapping,
metadata, context, and hidden-ground-truth separation audits. It exits non-zero
if any validation fails.

`READY_FOR_LLM_INFERENCE` is a pre-LLM structural gate. It is `true` only when
all Phase 6B synthetic audits pass. This synthetic gate does not trigger LLM
inference and does not authorize inference on real data by itself.

## Phase 6D.1 Prompt Specification Freeze

Phase 6D.1 freezes the model-agnostic semantic prompt contract. It does not
call LLM APIs, benchmark prompt variants, choose model-specific wording, inspect
partial real participant outcomes, or implement provider adapters.

Prompt specification version:

```text
phase6d_prompt_spec_v1
```

Response schema version:

```text
preference_prediction_response_v1
```

Exact prediction-task wording:

```text
Predict which anonymous mix A-E this specific participant is most likely to rate highest for the target listening situation.
```

The same task instruction, feature guide, candidate rendering, response schema,
and output instructions are used for both principal conditions. The
`non_history` prompt contains target context, participant metadata, acoustic
feature guide, target A-E candidates, and output instructions. The
`personalised_history` prompt is identical except that it inserts eligible
previous listening evidence from the same participant before the output
instructions.

Participant metadata renders exactly the Phase 6A frozen fields:
`age_range`, `gender`, `cultural_influence_country`,
`music_listening_habits`,
`music_production_or_audio_engineering_experience`, and
`hearing_difficulty`. Missing values render as `Not provided`.

Natural-language acoustic z-scores render to two decimal places. The prompt
defines `z_RMS` as RMS level, `z_CF` as crest factor, and `z_SW` as stereo
width using neutral descriptions only; higher/lower values are not described as
inherently better.

Song identity renders only as the participant-facing within-study label, such
as `Song A` or `Song B`. Actual song titles, song IDs, excerpt IDs, stimulus
IDs, mix IDs, filenames, and paths are not rendered.

The primary response contract contains only:

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

No rationale, explanation, reasoning trace, confidence field, or few-shot
demonstration is part of the primary prompt/response contract.

Render matched synthetic/test examples from the repository root:

```powershell
python llm-experiments\scripts\render_phase6d_synthetic_prompt_examples.py `
  --prompt-data llm-experiments\outputs\synthetic\phase6b5\final_prompt_data_objects.jsonl `
  --output-dir llm-experiments\outputs\synthetic\phase6d1_prompt_spec
```

This writes:

- `phase6d1_non_history_prompt_example.md`
- `phase6d1_personalised_history_prompt_example.md`
- `phase6d1_matched_synthetic_prompt_examples.json`
- `phase6d1_prompt_audit.json`

The synthetic audit checks prompt-size counts, condition equivalence outside
the history section, and leakage restrictions. It does not include LLM outputs
or performance claims.

## Phase 6D.2 Deterministic Prompt Rendering

Phase 6D.2 converts Phase 6B.4 condition-specific prompt-data objects into the
exact frozen Phase 6D.1 system/user messages. Rendered prompts are
model-agnostic and contain no provider-specific transport syntax, model IDs,
response-format parameters, API request fields, chat-template tokens, LLM
responses, or performance metrics.

Canonical input unit:

```text
prediction_example_id x condition
```

The renderer consumes the Phase 6B.4 condition object, using `model_input` for
semantic prompt content plus stable operational IDs/versions. It does not read
Phase 6B.3 `ground_truth`.

Canonical rendered-prompt fields:

- `schema_version`
- `rendered_prompt_id`
- `condition_object_id`
- `prediction_example_id`
- `condition`
- `prompt_spec_version`
- `response_schema_version`
- `source_prompt_data_schema_version`
- `source_prompt_data_builder_version`
- `messages`

`messages` always contains exactly:

1. `{ "role": "system", "content": <frozen system instruction> }`
2. `{ "role": "user", "content": <rendered frozen user prompt> }`

Rendered prompt IDs are deterministic:

```text
condition_object_id + "__" + phase6d_prompt_spec_v1
```

Run synthetic/test batch rendering from the repository root:

```powershell
python llm-experiments\scripts\render_prompts.py `
  --prompt-data llm-experiments\outputs\synthetic\phase6b5\final_prompt_data_objects.jsonl `
  --output-dir llm-experiments\outputs\synthetic\phase6d2_rendered_prompts
```

Synthetic Phase 6D.2 outputs:

- `rendered_prompts.jsonl`
- `rendered_prompt_audit.json`
- `matched_rendered_prompt_pair.md`

The renderer validates fixed section order, six-field participant metadata
rendering, `Not provided` missing-value rendering, participant-facing song
labels only, two-decimal acoustic z-score rendering, A-E candidate ordering,
absence of target outcomes/provenance identifiers, absence of `z_SI`, and
condition-pair equivalence outside the personalised-history section.

History comments are rendered as participant-provided evidence under the
history section. They are not treated as model instructions. Missing comments
render as `Not provided`; supplied comments are preserved except for ordinary
prompt serialization.

The separate format-repair renderer uses the frozen Phase 6D.1 repair
instruction with the invalid model output and canonical response schema only.
It does not add participant evidence, ground truth, correctness feedback, or
candidate hints.

The audit records prompt-data objects read, rendered prompts written,
condition counts, rendering failures, leakage failures, condition-equivalence
failures, deterministic rerun status, maximum history-trial count, and
provider-neutral character/word-count summaries by condition. It does not use
provider tokenizers.

## Phase 6D.3 Experimental Condition Integrity Validation

Phase 6D.3 validates that rendered paired prompts are experimentally
comparable before any LLM inference. It does not alter prompt wording, call any
LLM, implement provider adapters, inspect real participant outcomes, or compute
model performance.

Run synthetic/test condition validation from the repository root:

```powershell
python llm-experiments\scripts\validate_experimental_conditions.py `
  --rendered-prompts llm-experiments\outputs\synthetic\phase6d2_rendered_prompts\rendered_prompts.jsonl `
  --prompt-data llm-experiments\outputs\synthetic\phase6b5\final_prompt_data_objects.jsonl `
  --prediction-examples llm-experiments\outputs\synthetic\phase6b5\final_prediction_examples.jsonl `
  --output-dir llm-experiments\outputs\synthetic\phase6d3_condition_validation
```

Synthetic Phase 6D.3 outputs:

- `condition_pair_validation.csv`
- `condition_pair_validation.json`
- `condition_integrity_audit.json`
- `condition_integrity_summary.md`

The validator compares matched `non_history` and `personalised_history` prompts
by structured prompt sections. The required invariant is that system
instruction, task wording, target listening context, participant metadata,
acoustic feature guide, target candidate mixes, and output instructions are
identical. The only allowed semantic difference is the additional
`Previous listening evidence from this participant` section in the
personalised-history condition.

Leakage checks prohibit target outcomes, target comments, ground-truth fields,
stimulus or mix provenance identifiers, audio paths, and the sensitivity-only
`z_SI` feature. The validator also checks non-history contamination, history
target overlap, history-source correctness, comment-boundary integrity,
format-repair prompt isolation, schema versions, deterministic rerun, and
provider-neutral prompt-size differences.

The synthetic validation currently reports 11 matched pairs, 11 valid pairs,
zero leakage or equivalence failures, deterministic audit passing, and
`EXPERIMENTAL_CONDITION_INTEGRITY` set to `true`. Prompt lengths are not
artificially balanced; personalised-history prompts are longer because the
experimental manipulation adds prior participant evidence.

## Phase 6D.4 Prompt Package Freeze

Phase 6D.4 freezes the provider-neutral prompt package for Phase 6E inference
preflight. The package-level identifier is:

```text
phase6d_prompt_package_v1
```

This package version covers the semantic prompt, renderer, response schema,
experimental-condition definition, validation rules, reasoning policy,
few-shot policy, repair policy, acoustic-input contract, participant-metadata
contract, candidate ordering, and provider-adapter boundary.

Run the one-command preflight verifier from the repository root:

```powershell
python llm-experiments\scripts\verify_prompt_package.py
```

Regenerate the frozen synthetic validation package only when intentionally
freezing a new package state:

```powershell
python llm-experiments\scripts\verify_prompt_package.py --write-freeze
```

Phase 6D.4 synthetic outputs are written to:

```text
llm-experiments/outputs/synthetic/phase6d4_prompt_freeze/
```

They include the human-readable freeze report, machine-readable freeze audit,
prompt-size reference audit, canonical matched synthetic reference prompt pair,
valid response fixture, invalid response fixtures, and verifier output.

The completion gate is:

```text
PHASE6D_PROMPT_PACKAGE_FROZEN=true
```

The gate is true only when prompt-spec and response-schema versions are
consistent, renderer and condition validation pass, rendered prompts are
deterministic, target/provenance/`z_SI` leakage checks pass, target/history
overlap checks pass, response fixtures validate correctly, reference prompt
hashes match, artifact hashes match the manifest, and the synthetic prompt-size
structural check passes.

After `phase6d_prompt_package_v1` is frozen, substantive changes to prompt
wording, history structure, metadata fields, feature descriptions, acoustic
inputs, output schema, reasoning/few-shot policy, candidate ordering, or
condition definition require a new package version. Phase 6E provider adapters
may alter API transport, schema-enforcement syntax, tokenizer-specific counts,
and endpoint parameters, but may not alter semantic prompt content.

## Phase 6E.1 Inference Interface Scaffold

Phase 6E.1 introduces the provider-neutral inference interface:

```text
phase6e_inference_interface_v1
```

The interface separates scientific model identity from execution backend. The
planned model keys are `gpt`, `claude_sonnet`, `llama_3_1_70b_instruct`, and
`centaur`. The first three currently map to a QMUL backend placeholder; Centaur
maps to a RunPod backend placeholder. Exact model IDs, checkpoints, endpoint
contracts, capabilities, and inference settings remain to be frozen in Phase
6E.2.

Dry-run, with no backend invocation:

```powershell
python llm-experiments\scripts\run_phase6e1_inference.py --mode dry_run
```

Synthetic mock run:

```powershell
python llm-experiments\scripts\run_phase6e1_inference.py --mode mock
```

Both commands first require the Phase 6D package preflight to pass. The
synthetic dry-run builds 88 primary request records from 22 rendered prompts
and four model keys. The mock run executes those requests through the
deterministic mock adapter only and validates raw mock outputs against
`preference_prediction_response_v1`; it does not score predictions.

Phase 6E.1 outputs are written to:

```text
llm-experiments/outputs/synthetic/phase6e1/
```

## Phase 6E.2 Primary Inference Configuration

Phase 6E.2 introduces the primary inference configuration version:

```text
phase6e_primary_inference_config_v1
```

The configuration records the four scientific model slots, deployment mapping,
shared low-variance inference philosophy, output-length policy, credential
environment-variable pattern, capability matrix, context-compatibility audit,
and production freeze gates.

Repository inspection found no authoritative QMUL serving contract and no
Centaur RunPod deployment contract, so exact model IDs/checkpoints, endpoint
contracts, tokenizer limits, and backend capabilities are marked
`UNVERIFIED`. The production gates are therefore intentionally false:

```text
MODEL_IDENTITIES_FROZEN=false
INFERENCE_BACKENDS_VERIFIED=false
PRIMARY_INFERENCE_CONFIG_FROZEN=false
```

Validate the configuration and generate the synthetic structural 88-request
matrix without model calls:

```powershell
python llm-experiments\scripts\validate_phase6e2_config.py
```

Phase 6E.2 outputs are written to:

```text
llm-experiments/outputs/synthetic/phase6e2/
```

## Phase 6E.3 Prediction Logging

Phase 6E.3 introduces the logging contract:

```text
phase6e_prediction_logging_v1
```

The logging layer separates backend attempts from canonical scientific
prediction records. Attempt records are one backend invocation; prediction
records are one `prediction_example_id x condition x model_key x
inference_config_version` unit. Raw response text is preserved separately from
parsed predictions and consistency diagnostics.

Run the synthetic mock logging integration:

```powershell
python llm-experiments\scripts\run_phase6e3_logging.py
```

The synthetic run writes:

```text
llm-experiments/outputs/synthetic/phase6e3/phase6e3_synthetic_mock_run/
```

It produces 88 attempt records and 88 final prediction records from the
existing mock adapter, with no real model calls, no repairs, no scoring, and no
ground-truth dependency.

## Phase 6E.4 Failure Handling

Phase 6E.4 introduces deterministic failure handling:

```text
phase6e_failure_handling_v1
```

The versioned policy is:

```text
llm-experiments/config/phase6e_failure_policy_v1.json
```

The scientific policy remains one primary generation and at most one
formatting-only repair generation. Transport retries are operational retries
for cases where no meaningful model output was obtained; they do not count as
additional scientific generations.

Run the synthetic failure matrix:

```powershell
python llm-experiments\scripts\run_phase6e4_failure_matrix.py
```

The synthetic run writes:

```text
llm-experiments/outputs/synthetic/phase6e4/phase6e4_synthetic_failure_matrix/
```

It covers valid primary responses, invalid JSON repair, schema-invalid repair,
failed repair, retryable timeouts/HTTP 5xx/HTTP 429/connection failures, empty
responses, non-retryable HTTP 400/auth failures, resume/idempotence, and
terminal completion gates. It does not score predictions or call real models.

`INFERENCE_RUN_COMPLETE` means every expected prediction reached a terminal
state. `ALL_EXPECTED_PREDICTIONS_VALID` is stricter and is true only if every
expected prediction is valid primary or valid after repair.

## Phase 6F.1 Synthetic End-To-End Validation

Phase 6F.1 introduces the synthetic dry-run/orchestration contract:

```text
phase6f_synthetic_e2e_v1
```

Run the complete synthetic validation package from the repository root:

```powershell
python llm-experiments\scripts\run_phase6f_synthetic_pipeline.py --check-determinism
```

This regenerates/reuses the synthetic Phase 6B data pathway, renders the
frozen Phase 6D prompt package, verifies prompt integrity, executes Phase 6E
four-model mock inference with canonical logging, and aligns the resulting LLM
prediction records with the Phase 6C synthetic baseline smoke outputs.

Outputs are written to:

```text
llm-experiments/outputs/synthetic/phase6f1_e2e/
```

The package separates:

- `llm_predictions_for_evaluation.csv`
- `baseline_predictions_for_evaluation.csv`
- `ground_truth_for_evaluation.csv`
- `prediction_alignment_manifest.jsonl`
- `phase6f1_end_to_end_audit.json`
- `phase6f1_hash_manifest.json`
- `phase6f1_end_to_end_report.md`

`ground_truth_for_evaluation.csv` is explicitly evaluation-only and is never
merged into LLM inference logs. Phase 6F.1 does not calculate predictive
accuracy, RMSE, MAE, rank correlations, model comparisons, statistical tests,
or scientific plots.

For the current synthetic state, the LLM path covers 22 rendered prompts x 4
mock model identities = 88 prediction records. The Phase 6C consolidated
baseline smoke output currently covers one target across the two primary
baseline models, so the common fully aligned target count is 1. This is an
alignment smoke validation, not a final evaluation.

## Phase 6F.2 Synthetic Metric Validation

Phase 6F.2 introduces the deterministic scoring contract:

```text
phase6f_metric_protocol_v1
```

Run the synthetic metric layer after Phase 6F.1 artifacts exist:

```powershell
python llm-experiments\scripts\run_phase6f2_metrics.py
```

Outputs are written to:

```text
llm-experiments/outputs/synthetic/phase6f2_metrics/
```

The package includes:

- `scored_llm_predictions.csv`
- `scored_baseline_predictions.csv`
- `llm_metric_summary.csv`
- `baseline_metric_summary.csv`
- `participant_llm_metrics.csv`
- `participant_baseline_metrics.csv`
- `metric_coverage_summary.json`
- `phase6f2_metric_audit.json`
- `phase6f2_metric_validation_report.md`

Strict top-1 accuracy uses all expected prediction records as the denominator.
Structurally invalid outputs, backend failures, and missing/not-run expected
records are retained and count as non-successes. Valid-only accuracy is emitted
only as a diagnostic quantity. MAE/RMSE are reported as mean per-trial
candidate-rating errors for structurally valid numeric predictions, with
coverage. Spearman uses tie-aware mid-ranks derived from predicted numeric
ratings and Phase 6B observed ranks; constant-rank cases are reported as
undefined rather than forced to a numeric value.

Synthetic/mock metric values are pipeline-validation outputs only and must not
be interpreted as model performance. Phase 6F.2 does not emit confidence
intervals, bootstrap distributions, p-values, inferential model comparisons,
scientific plots, or model-ranking claims. The current baseline values are only
smoke-subset plumbing checks because Phase 6C synthetic baseline predictions
cover one common target across the two primary baseline models.

## Phase 6F.3 Synthetic Comparison Scaffolding

Phase 6F.3 introduces the participant-aware comparison contract:

```text
phase6f_comparison_protocol_v1
```

Run the synthetic comparison layer after Phase 6F.2 artifacts exist:

```powershell
python llm-experiments\scripts\run_phase6f3_comparisons.py
```

Outputs are written to:

```text
llm-experiments/outputs/synthetic/phase6f3_comparisons/
```

The package includes:

- `personalisation_comparisons.csv`
- `llm_vs_baseline_comparisons.csv`
- `participant_personalisation_differences.csv`
- `participant_llm_vs_baseline_differences.csv`
- `comparison_coverage_summary.json`
- `phase6f3_bootstrap_audit.json`
- `phase6f3_comparison_validation_report.md`
- `phase6f3_hash_manifest.json`

The bootstrap cluster unit is `participant_id`: each sampled participant
contributes all eligible matched target rows, and repeated bootstrap draws of a
participant are retained as repeated clusters. The production configuration is
frozen at 2000 participant-cluster bootstrap replicates, master seed `20260814`,
percentile 95% confidence intervals. The default synthetic/test runner uses 200
replicates for fast validation and records that mode explicitly.

The primary accuracy estimand is the pooled proportion of eligible held-out
participant-trial predictions correctly predicted across the study, with
participant-cluster bootstrap uncertainty. Participant-level means and
differences are supporting diagnostics, not replacements for the pooled
estimand.

Personalisation comparisons are paired by `participant_id` and
`prediction_example_id`, using `personalised_history - non_history`. For
MAE/RMSE, negative differences mean lower error under personalised history.
LLM-vs-baseline comparisons are paired on exact `participant_id` and
`prediction_example_id`; the baseline has no condition dimension. Repository
documentation identifies both `categorical_design` and `primary_acoustic` as
primary baseline models, so no single principal comparator is selected from
synthetic values.

Synthetic/mock comparison values validate statistical plumbing only and are not
evidence about LLM or baseline performance. Phase 6F.3 does not emit p-values,
independent-sample t-tests, significance claims, model rankings, subgroup
fishing, final dissertation figures, or scientific interpretations.

## Phase 6F.4 Pre-Data Reporting Readiness

Phase 6F.4 introduces the synthetic reporting contract:

```text
phase6f_reporting_v1
```

Run the reporting layer after Phase 6F.1-6F.3 artifacts exist:

```powershell
python llm-experiments\scripts\run_phase6f4_reporting.py
```

Outputs are written to:

```text
llm-experiments/outputs/synthetic/phase6f4_predata_readiness/
```

The package includes automatic metric tables, comparison tables, participant
QC, context/song coverage, inference validity, baseline diagnostics, comparison
coverage, reusable synthetic PNG plots, a pre-real-data checklist, a
machine-readable readiness audit, a Markdown readiness report, and a hash
manifest.

The readiness gates are intentionally separated:

- `REAL_DATA_PIPELINE_READY`: data processing, baseline infrastructure, prompt
  generation, scoring, comparison, and reporting can run without redesign once
  the final survey CSV exists.
- `PRODUCTION_INFERENCE_READY`: remains false until Phase 6E.2 exact model
  identities and live backend contracts are verified.
- `PREDATA_ANALYSIS_READY`: true when the pre-data analysis/reporting
  infrastructure is complete, while live deployment inputs may still be
  pending.
- `PHASE6F_PREDATA_DRY_RUN_COMPLETE`: true when Phase 6F.1-6F.4 synthetic
  validations pass.

Check the gate without regenerating every upstream stage:

```powershell
python llm-experiments\scripts\check_phase6_predata_readiness.py
```

Run the full synthetic Phase 6F pre-data validation wrapper:

```powershell
python llm-experiments\scripts\run_phase6f_predata_validation.py
```

All synthetic reporting tables and plots are labelled
`SYNTHETIC / MOCK - NOT SCIENTIFIC RESULTS`. Phase 6F.4 does not run real
models, inspect real participant outcomes, resolve the baseline comparator,
emit p-values, make scientific claims, rank models, or create final
dissertation figures.

## Future Real-Data Pathway

When final data collection is complete, the expected real input is the final
five-mix Netlify participant-level CSV export with the same fields exercised by
the synthetic fixture. Do not run Phase 6B target derivation on partial exports.

The later real-data execution should use the same staged scripts with explicit
paths and a non-committed real-data output directory, for example:

```powershell
python llm-experiments\scripts\build_analysis_ready_dataset.py `
  --input <final-real-export.csv> `
  --output-dir <approved-real-output-dir>\phase6b1

python llm-experiments\scripts\build_preference_targets.py `
  --input <approved-real-output-dir>\phase6b1\analysis_ready_long.csv `
  --output-dir <approved-real-output-dir>\phase6b2

python llm-experiments\scripts\build_prediction_examples.py `
  --candidates <approved-real-output-dir>\phase6b2\candidate_ground_truth_enriched.csv `
  --targets <approved-real-output-dir>\phase6b2\trial_ground_truth_targets.csv `
  --output-dir <approved-real-output-dir>\phase6b3

python llm-experiments\scripts\build_prompt_data_objects.py `
  --examples <approved-real-output-dir>\phase6b3\prediction_examples.jsonl `
  --output-dir <approved-real-output-dir>\phase6b4
```

Before any Phase 6C/LLM inference begins, the real-data run must pass the same
validation gate: all relevant Phase 6B tests passing, no leakage failures,
valid target/history mappings, valid schemas, paired-condition equivalence,
deterministic rerun, expected candidate counts, and complete feature joins for
active target candidates.
