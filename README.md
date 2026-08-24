# Individual Listener Preferences for Music Mixes Across Listening Contexts: Statistical Analysis and Personalised LLM Prediction

This repository contains the supporting material for Oscar Alejandro Gallegos Villarreal's MSc dissertation. The project studies listener-centred preference for alternative professional music mixes across controlled listening contexts.

The submitted study collected 990 mix-preference ratings across 198 participant-trial targets from 33 participants. Each participant heard two of four songs, with five professionally produced mixes per song, under three functional listening contexts: Enjoyment, Relaxation-Distraction, and Focus-Motivation. Ratings were given on a 0-100 scale, with one comparative free-text comment per trial.

The analysis has two linked parts. Bayesian multilevel models quantify context, listener, stimulus, and acoustic associations in the human ratings. Four large language models are then evaluated on held-out preferred-mix prediction, both without participant history and with participant history from the same listener.

## Research Questions

RQ1: How do listener, context, stimulus, and acoustic factors relate to preference ratings for alternative music mixes?

RQ2: Can large language models predict an individual listener's preferred music mix on a held-out trial?

RQ3: Does participant history, defined as ratings and qualitative comments from the same listener's other non-target trials, improve held-out LLM preference prediction?

RQ4: How do personalised LLM predictions compare with a matched mixed-effects predictive model?

## Repository Map

| Folder | Purpose |
| --- | --- |
| `data/` | Submission-minimised participant, rating, trial-preference, and LLM prompt-data tables. |
| `dissertation/` | Submitted dissertation PDF and final dissertation figures. |
| `experimental-design/` | Final stimulus-selection rationale, source evidence, generator, and final five-mix traceability. |
| `study-interface/` | Static Netlify five-mix listening interface, configuration documentation, and response-conversion notes. |
| `statistical-modeling/` | Bayesian mixed-effects scripts, acoustic-feature verification, held-out mixed-effects evaluation, and compact statistical outputs. |
| `llm-experiments/` | Final prompt package, rendered prompts, model runners, consolidated predictions, and LLM evaluation code. |
| `results/` | Compact examiner-facing statistical and LLM result tables/figures. |
| `tests/` | Lightweight validation tests for the retained interface, stimulus package, statistical finalisation, and LLM pipeline. |

## Study Design

- Participants: 33.
- Group split: 17 participants in `group_01`, 16 in `group_02`.
- Songs: 4, with 2 songs allocated to each participant group.
- Final stimuli: 20 song-mix stimuli, 5 mixes per song.
- Contexts: Enjoyment, Relaxation-Distraction, Focus-Motivation.
- Trials: 6 per participant, giving 198 held-out preference targets.
- Ratings: 990 candidate-level 0-100 ratings.
- Comments: one comparative free-text comment per trial.
- Presentation: anonymous A-E labels, per-trial label-to-mix mapping, and trial/song/context randomisation recorded for reconstruction.

Final group allocation:

| Group | Songs | Five selected mixes |
| --- | --- | --- |
| `group_01` | Lead Me | DU-D, DU-E, PXL-L1, PXL-L4, McG-pro2 |
| `group_01` | I'd Like To Know | PXL-S3, PXL-S5, PXL-S1, PXL-S2, PXL-S7 |
| `group_02` | In The Meantime | QUT-B, DU-H, DU-I, DU-K, QUT-pro |
| `group_02` | Pouring Room | McG-R, McG-T, McG-X, McG-pro1, McG-V |

## Reproducibility Map

```text
study interface
-> curated data
-> statistical modeling
-> LLM prompt data
-> LLM predictions
-> evaluation
-> results
```

Primary retained entry points:

```powershell
python data\scripts\convert_netlify_responses.py --help
python experimental-design\stimulus-selection\final-selection\five-mix-selection-review-20260806\generate_five_mix_review.py
python statistical-modeling\scripts\fit_final_models.py
python statistical-modeling\scripts\evaluate_heldout_predictions.py
python statistical-modeling\scripts\freeze_final_statistical_results.py
python llm-experiments\scripts\build_final_prompt_data.py --write-manifest
python llm-experiments\scripts\render_final_prompts.py
python llm-experiments\scripts\consolidate_final_predictions.py
```

The final LLM scoring function is currently retained as an internal module function rather than a wrapper script:

```powershell
$env:PYTHONPATH = "llm-experiments/src"
python -c "from pathlib import Path; from llm_experiments.evaluation.phase6h2b_final_scoring import run_phase6h2b_final_scoring; run_phase6h2b_final_scoring(Path('.'))"
python -m llm_experiments.evaluation.phase6h3_results_synthesis
```

Do not run model-fitting, LLM inference, or external-verification commands during routine repository inspection unless explicitly intending to reproduce those stages.

## Statistical Modeling

The retained empirical models use Bayesian multilevel regression over the curated candidate-level ratings in `data/processed/ratings_final.csv`.

Main stimulus model:

```text
rating ~ episode + group + (1 | participant_id) + (1 | stimulus_id)
```

Primary acoustic-feature model:

```text
rating ~ episode + group + z_RMS + z_CF + z_SW + (1 | participant_id) + (1 | stimulus_id)
```

The modeling scripts and retained outputs are in `statistical-modeling/`. Compact reported statistical results are copied to `results/statistical/`.

## LLM Experiments

The final evaluated models are:

- GPT-5.5
- Claude Sonnet 5
- Llama 3.1 70B Instruct
- Centaur

The two prompt conditions are:

- `non_history`: target context, participant metadata, candidate acoustic features, and A-E candidates only.
- `personalised_history`: the same target information plus participant-history ratings and comments from the same participant's other non-target trials.

The frozen prompt template and manifest retain historical internal version names because their filenames and hashes are part of provenance:

- `llm-experiments/prompts/phase6d_prompt_template_v1.json`
- `llm-experiments/prompts/phase6d_prompt_package_manifest.json`

Final predictions are retained in `llm-experiments/outputs/final/model-predictions/`. Final scoring artifacts are in `llm-experiments/outputs/final/evaluation/`, with compact examiner-facing copies in `results/llm/`.

## Final Results

Headline retained values:

- Stimulus model ICCs: participant 0.145; stimulus 0.173.
- Primary acoustic-feature model ICCs: participant 0.156; stimulus 0.128.
- Matched primary acoustic mixed-effects Top-1 accuracy: 34.3%.
- GPT-5.5 personalised-history Top-1 accuracy: 34.3%.
- Claude Sonnet 5 personalised-history Top-1 accuracy: 35.9%.

The full result pack is in `results/`, while detailed source outputs remain in `statistical-modeling/outputs/` and `llm-experiments/outputs/final/`.

## External Execution Environments

Local inspection and most validation do not require credentials. Full reproduction has external requirements:

- GPT-5.5 requires OpenAI-compatible provider/API access in the configured runtime.
- Claude Sonnet 5 requires Anthropic-compatible provider/API access in the configured runtime.
- Llama 3.1 70B Instruct requires the QMUL/local GPU and Hugging Face environment used for the final run.
- Centaur requires RunPod or an equivalent GPU environment with the retained adapter/base-model configuration.

Environment notes are in `ENVIRONMENTS.md`. Dependency specifications are in `requirements-statistical.txt` and `requirements-llm.txt`; these are reproducibility specifications, not exact lockfiles.

## Known Reproducibility Limits

- The final study interface is static and reproducible from `study-interface/frontend-5mix/`, but the live Netlify deployment and form dashboard are external.
- The acoustic notebook verifies/reconstructs the final 20-stimulus feature table from retained feature evidence; it is not a complete raw-WAV-to-feature extraction archive.
- Full LLM inference depends on provider, QMUL, and RunPod infrastructure that is not contained in this repository.
- Credentials, raw Netlify exports, and unnecessary operational participant metadata are intentionally not committed.

## Dissertation

Submitted paper:

`dissertation/OscarGallegos_PG_Project_Dissertation.pdf`
