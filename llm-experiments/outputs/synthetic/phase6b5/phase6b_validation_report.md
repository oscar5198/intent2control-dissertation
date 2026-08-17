# Phase 6B Synthetic Validation Report

These are synthetic structural validation results only. They are not dissertation experiment results.

## Purpose

Validate the Phase 6B data pipeline from synthetic raw export structure through final model-facing prompt-data objects without LLM calls.

## Fixture

- Synthetic integration fixture: `llm-experiments/outputs/synthetic/phase6b5/phase6b5_integration_synthetic_raw_export.csv`
- Source fixture: `llm-experiments/fixtures/synthetic/phase6b1_five_mix_netlify_export.csv`

## Stages Executed

- 6B.1 raw export to analysis-ready long data
- 6B.2 hidden human preference targets
- 6B.3 leave-one-trial-out prediction examples
- 6B.4 condition-specific structured prompt-data objects

## Structural Counts

- Participants: 2
- Candidate rows: 59
- Trials: 12
- Complete trials: 10
- Incomplete/malformed trials: 2
- Target-eligible trials: 11
- Prediction examples: 11
- Non-history objects: 11
- Personalised-history objects: 11

## Audit Results

- structural_counts: PASS
- phase6b1: PASS
- phase6b2: PASS
- phase6b3: PASS
- phase6b4: PASS
- leakage: PASS
- provenance_leakage: PASS
- condition_equivalence: PASS
- schema: PASS
- identifier_integrity: PASS
- history_rotation: PASS
- acoustic_mapping: PASS
- metadata: PASS
- context: PASS
- hidden_ground_truth_separation: PASS
- determinism: PASS

## Pre-LLM Gate

- `READY_FOR_LLM_INFERENCE`: true
- Failed checks: none

## Conclusion

Phase 6B can be marked COMPLETE for the synthetic pipeline.

The future real-data pathway must run the same staged pipeline on the final complete raw export only, write outputs to a non-committed real-data location, and pass this validation gate before any LLM inference begins.
