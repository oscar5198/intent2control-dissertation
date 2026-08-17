# Phase 6D.4 Prompt Package Freeze Report

Dataset class: synthetic validation
Package version: `phase6d_prompt_package_v1`
Prompt spec version: `phase6d_prompt_spec_v1`
Response schema version: `preference_prediction_response_v1`

## Conditions

- `non_history`: target and participant metadata only.
- `personalised_history`: same target and participant metadata plus eligible prior-trial evidence.

## Synthetic Counts

- Rendered prompts: 22
- Non-history prompts: 11
- Personalised-history prompts: 11
- Matched condition pairs: 11

## Validation

- Condition integrity: True
- Target leakage free: True
- Provenance leakage free: True
- Sensitivity-feature leakage free: True
- Deterministic rendering: True
- Artifact hashes valid at freeze: True
- Response-schema fixtures valid: True
- Prompt-size structural check: True

## Policies

- Reasoning: zero-shot primary inference; chain-of-thought requested = False.
- Few-shot examples: 0.
- Repair: one primary generation attempt, one formatting-only repair attempt, no ground truth or correctness feedback.

## Prompt Size Summary

- Non-history chars min/median/max: 2780/2802/2850
- Non-history words min/median/max: 370/377/379
- Personalised-history chars min/median/max: 7139/8166/8209
- Personalised-history words min/median/max: 1001/1149/1153
- Maximum history-trial count: 5

Completion gate `PHASE6D_PROMPT_PACKAGE_FROZEN`: `true`

No LLM calls, provider adapters, real participant outcomes, model IDs, temperatures, or provider token limits are included.
