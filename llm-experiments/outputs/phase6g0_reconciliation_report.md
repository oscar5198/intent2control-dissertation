# Phase 6G.0 Final-Input Reconciliation Report

Scope: repository reconciliation only. No LLMs were run, no statistical models were refit, prompt wording was not changed, and no new scientific comparisons were calculated.

## Final Phase 3 Status

- Final dataset locked: `true`
- Final empirical held-out predictions complete: `true`
- Participants/targets/candidate rows: `33` / `198` / `990`
- Authoritative baseline source: `statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split`

## Phase 3 To Phase 6 Alignment

- Baseline alignment valid: `true`
- Methodologically equivalent to Phase 6A LOTO: `true`
- Held-out target outcomes excluded from fit: `true`
- Covers all final eligible targets: `true`
- Phase 6F-ready compact export present: `false`

The final Phase 3 MCMC held-out predictions can replace the old Phase 6C synthetic/smoke baseline for final Phase 6 comparisons. A small adapter/export step is still needed to materialize the compact Phase 6F schema.

## Principal Baseline Comparator

`both_predefined_primary`. both categorical_design and primary_acoustic are retained as primary/predefined; no single comparator selected from empirical performance.

## Final Dataset And Phase 6B

- Final raw source: `statistical-baseline/data/real/raw/listening_preference_responses_33_immutable.xlsx`
- Raw SHA-256: `5bab388fbf564e0caf5c1ca8a5a722bf8d517e23c018e48375d076e75dba0bdd`
- Real Phase 6B outputs ready: `true`
- Next input: `statistical-baseline/data/real/raw/listening_preference_responses_33_immutable.xlsx or an exact CSV export of its listening-study-5mix sheet`
- Next command: `If exported as CSV: python llm-experiments/scripts/build_analysis_ready_dataset.py --input <final_netlify_export.csv> --output-dir llm-experiments/outputs/real/phase6b/phase6b1 ; then run build_preference_targets.py, build_prediction_examples.py, and build_prompt_data_objects.py on those outputs.`

## Phase 6D And 6E

- Prompt package verified: `true`
- Model identities frozen: `false`
- Inference backends verified: `false`
- Primary inference config frozen: `false`
- Production inference ready: `false`
- Unresolved live items:
  - Exact GPT-family model ID/checkpoint on QMUL
  - Exact Claude Sonnet-family model ID/checkpoint on QMUL
  - Exact Llama 3.1 70B Instruct checkpoint, revision, quantisation and serving framework on QMUL
  - Exact Centaur checkpoint/source/revision and RunPod deployment contract
  - QMUL request/response contract and authentication requirements
  - RunPod request/response contract and authentication requirements
  - Structured-output mechanism per backend
  - Tokenizer/context limits per model
  - Seed, temperature and top-p support per backend
  - Usage metadata and healthcheck availability

## Remaining Execution Plan

- 6G.1 Generate final real Phase 6B outputs and verify identifier compatibility with Phase 3 baseline prediction_example_id values.
- 6G.2 Freeze exact four model/checkpoint identities and live QMUL/RunPod backend contracts.
- 6G.3 Render/freeze final real prompts from Phase 6B prompt-data objects.
- 6G.4 Execute four-model production inference with Phase 6E logging/failure handling.
- 6G.5 Merge/freeze LLM prediction records and adapt final Phase 3 baseline predictions into the Phase 6F-ready compact schema.
- 6H Run real scoring, participant-aware comparisons, and reporting from frozen predictions only.

## Current Blocker To Real LLM Inference Today

Phase 6E.2 live model/backend gates remain unresolved. Do not start production LLM inference until exact model identities, backend contracts, and the primary inference config are frozen.
