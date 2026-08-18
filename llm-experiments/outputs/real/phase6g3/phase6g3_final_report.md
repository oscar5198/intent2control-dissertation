# Phase 6G.3 Final Real Rendered Prompt Freeze

No LLM calls, production inference, scoring, prompt wording changes, model configuration changes, or hidden ground-truth reads were performed.

## Source

- Phase 6B prompt data: `llm-experiments/outputs/real/phase6b/final_prompt_data_objects.jsonl`
- Phase 6B prompt data SHA-256: `c79bc5544659c219fb67a1b83281d6621e4e6e3ce0b99e0f5154c8f63adea0f4`
- Source hash verified: `true`

## Counts

- Rendered prompts: `396`
- Non-history: `198`
- Personalised-history: `198`
- Matched pairs: `198`
- History distribution: `{5: 198}`

## Audits

- Leakage failures: `0`
- Condition-equivalence failures: `0`
- Deterministic rendering: `true`

## Size

- Non-history characters min/median/max: `3227/3264.0/3369`
- Non-history words min/median/max: `435/443.0/460`
- Personalised-history characters min/median/max: `8396/9034.0/10632`
- Personalised-history words min/median/max: `1188/1326.5/1617`

## Context

- GPT max token estimate: `3672`
- Claude max token estimate: `3672`
- Llama max tokens: `3672` (conservative_character_estimate_no_weight_load_no_download)
- Centaur max tokens/structural margin: `3672` / `28840`
- Centaur serialization: `system_content + fixed delimiter + user_content`
- Centaur `<< >>` primary formatting introduced: `false`

## Requests

- GPT: `396`
- Claude: `396`
- Llama: `396`
- Centaur: `396`
- Total: `1584`
- QMUL shard total: `1188`
- RunPod shard total: `396`

## Gates

- Ground-truth isolation: `true`
- Prompt hash manifest: `bbbac0dcaf8b3715febeb62b27a12cefa21056dca6a42c0bdb27eb08f8d7a9f4`
- `REAL_PRODUCTION_PROMPTS_FROZEN`: `true`
- Phase 6G.3 complete: `true`
- Phase 6G.4 can begin immediately: `true`
