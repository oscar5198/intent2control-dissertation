# Phase 6D.3 Experimental Condition Integrity Summary

Dataset class: synthetic/test
Prompt spec version: `phase6d_prompt_spec_v1`
Response schema version: `preference_prediction_response_v1`

## Counts

- Rendered prompts read: 396
- Matched pairs: 198
- Valid pairs: 198
- Non-history prompts: 198
- Personalised-history prompts: 198

## Validation

- Pair-equivalence failures: 0
- Target leakage failures: 0
- Identifier/provenance leakage failures: 0
- Sensitivity-feature leakage failures: 0
- Non-history contamination failures: 0
- History target-overlap failures: 0
- History-source correctness failures: 0
- Comment-boundary failures: 0
- Repair-prompt failures: 0
- Deterministic audit passed: True
- `EXPERIMENTAL_CONDITION_INTEGRITY`: `true`

No LLM calls, provider adapters, prompt alternatives, ground-truth scoring, or performance metrics are included.
