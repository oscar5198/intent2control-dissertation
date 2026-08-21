# Submission-Facing Study Data

This directory contains submission-minimised participant data for the final 5-mix listening study. It is a curated view for examination, not the full raw Netlify export.

## Dataset Overview

- Participants: 33
- Songs: 4
- Mixes per song: 5
- Final song-mix stimuli: 20
- Listening contexts: 3
- Trials per participant: 6
- Candidate ratings: 990
- Trial-level preference targets: 198

## Files

| File | Granularity | Rows | Purpose |
| --- | --- | ---: | --- |
| `processed/participants_final.csv` | One row per participant | 33 | Participant demographics, study group, post-task responses, assignment/order JSON, mix mapping JSON, and minimised participant response JSON needed to reconstruct the study. |
| `processed/ratings_final.csv` | One row per participant x trial x presented mix | 990 | Candidate-level human ratings, comments, context/song labels, stimulus IDs, real mix IDs, audio paths, acoustic features, and trial ground-truth fields. |
| `processed/trial_preferences_final.csv` | One row per participant trial | 198 | Held-out preference target per trial, including A-E ratings, observed ranks, preferred mix, context, participant group, and song information. |
| `processed/llm_heldout_prompt_data_final.csv` | One row per LLM held-out prompt condition | 396 | Final LLM prediction inputs and ground truth: participant metadata, target candidate acoustic features, candidate mapping, and prior-trial history for personalised-history conditions. |

## Provenance

The final data chain is:

```text
Netlify form export from `listening-study-5mix`
        ↓
response parsing and anonymised A-E/mix reconstruction
  data/scripts/convert_netlify_responses.py
        ↓
curated participant/rating/trial data
  data/processed/participants_final.csv
  data/processed/ratings_final.csv
  data/processed/trial_preferences_final.csv
        ↓
statistical analysis
  statistical-modeling/outputs/final-model-summaries/
  statistical-modeling/outputs/heldout-evaluation/mcmc-evaluation/
        ↓
LLM analysis-ready data
  data/processed/llm_heldout_prompt_data_final.csv
  llm-experiments/outputs/final/prompt-data/
        ↓
held-out prediction targets
  llm-experiments/outputs/final/evaluation/heldout_ground_truth.csv
  llm-experiments/outputs/final/evaluation/predictions_with_ground_truth.csv
```

The statistical and LLM datasets derive from the same final N=33 cohort. Participant IDs use the shared `P001`-style pseudonymous IDs. Trial IDs use the shared participant-trial form, for example `P001__trial_01`, so candidate ratings, trial preferences, and LLM held-out targets join on `participant_id` and `trial_id` or `heldout_trial_id`.

Personalised LLM evidence comes from earlier trials by the same participant. The curated LLM prompt-data file retains that prior-trial history as JSON, including prior context, song, acoustic features, human ratings, and participant comments where available.

## Data Minimisation

The original raw Netlify workbook is not copied here. These curated files exclude unnecessary operational web metadata such as IP address, user agent, referrer, browser/device metadata, exact operational/submission timestamps, Netlify/system metadata, and deployment metadata.

These files are not described as fully anonymous: they retain pseudonymous participant IDs, demographics, free-text comments, and participant-level study-response JSON where required to interpret or reconstruct the listening study.

## Analysis Mapping

- Statistical mixed-effects models: `processed/ratings_final.csv`
- Mixed-effects held-out prediction: `processed/ratings_final.csv` and `processed/trial_preferences_final.csv`
- LLM held-out prediction: `processed/llm_heldout_prompt_data_final.csv`
- Personalised prior-trial-history prediction: `processed/llm_heldout_prompt_data_final.csv`, with supporting candidate-level detail in `processed/ratings_final.csv`
