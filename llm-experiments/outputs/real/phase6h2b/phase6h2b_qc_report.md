# Phase 6H.2B QC Report

Final scoring used only frozen Phase 6G.5, Phase 6H.1, and Phase 6H.2A artifacts.

## Top-1 Accuracy
- GPT-5.5 / non_history: 45/198 = 0.227 [0.174, 0.291]
- GPT-5.5 / personalised_history: 68/198 = 0.343 [0.281, 0.412]
- Claude Sonnet 5 / non_history: 41/198 = 0.207 [0.156, 0.269]
- Claude Sonnet 5 / personalised_history: 71/198 = 0.359 [0.295, 0.427]
- Llama 3.1 70B Instruct / non_history: 49/198 = 0.247 [0.193, 0.312]
- Llama 3.1 70B Instruct / personalised_history: 51/198 = 0.258 [0.202, 0.323]
- Centaur / non_history: 49/198 = 0.247 [0.193, 0.312]
- Centaur / personalised_history: 52/198 = 0.263 [0.206, 0.328]
- Mixed-effects primary acoustic / baseline: 68/198 = 0.343 [0.281, 0.412]

## QC
- Centaur rating excluded: True
- Same mixed-effects/LLM target count: True

## Gates
- `FINAL_LLM_SCORING_COMPLETE=true`
- `FINAL_MIXED_EFFECTS_PREDICTIVE_SCORING_COMPLETE=true`
- `PERSONALISATION_ANALYSIS_COMPLETE=true`
- `FAIR_LLM_MIXED_EFFECTS_COMPARISON_COMPLETE=true`
- `CENTRAL_MIXED_EFFECTS_RESULTS_READY=true`
- `RQ1_EVIDENCE_READY=true`
- `RQ2_EVIDENCE_READY=true`
- `RQ3_EVIDENCE_READY=true`
- `RQ4_EVIDENCE_READY=true`
- `DISSERTATION_RESULT_TABLES_READY=true`
- `DISSERTATION_RESULT_FIGURES_READY=true`
- `PHASE6H2B_COMPLETE=true`
