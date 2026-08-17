# Phase 6G.1 Real Phase 6B Dataset Freeze

Scope: final real Phase 6B data generation only. No LLM calls, prompt rendering, statistical refits, model-performance calculations, or prompt-specification changes were performed.

## Locked Input

- Path: `statistical-baseline/data/real/raw/listening_preference_responses_33_immutable.xlsx`
- Sheet: `listening-study-5mix`
- SHA-256: `5bab388fbf564e0caf5c1ca8a5a722bf8d517e23c018e48375d076e75dba0bdd`

## Counts

- Participants: `33`
- Candidate rows: `990`
- Trials: `198`
- Target-eligible trials: `198`
- Target-ineligible trials: `0`
- Prediction examples: `198`
- Non-history objects: `198`
- Personalised-history objects: `198`
- Prompt-data objects: `396`

## Alignment And Audits

- Phase 3 aligned targets: `198` / `198`
- A-E candidate mapping: `PASS`
- Leakage audit: `PASS`
- Deterministic rebuild: `PASS`

## Readiness

- `REAL_PHASE6B_READY`: `true`
- `PRODUCTION_INFERENCE_READY`: `false`
- Blocker: Phase 6E.2 live model identities and backend contracts remain unresolved.
