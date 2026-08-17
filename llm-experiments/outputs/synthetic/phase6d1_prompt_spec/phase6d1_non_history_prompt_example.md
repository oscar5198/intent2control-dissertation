# Synthetic non_history Prompt Example

Prompt spec version: `phase6d_prompt_spec_v1`
Response schema version: `preference_prediction_response_v1`
Prediction example ID: `SYNTHETIC_PHASE6B1_P001__heldout__SYNTHETIC_PHASE6B1_P001__trial_01`

## System Instruction

You are predicting individual listener preference in a music listening study. Infer this participant's likely 0-100 ratings and most preferred anonymous mix for the supplied target situation. Use only the supplied participant, context, acoustic-feature, and history information. Do not assume anything about underlying mixes beyond the supplied anonymous labels and feature values. Return only the specified JSON object, with no explanatory prose outside the JSON.

## User Message

## Task

Predict which anonymous mix A-E this specific participant is most likely to rate highest for the target listening situation.

Predicted ratings are the participant's expected 0-100 suitability/preference ratings for the five mixes in this target listening situation. They are not probabilities, confidence percentages, or objective audio-quality scores.

## Target listening situation

Context: You have some free time and no immediate responsibilities that require your attention. You are not feeling tired or worried, but you would like to enjoy your time rather than let it pass uneventfully. You decide to listen to music for entertainment, making your free time more enjoyable.
Study song: Song A

## Participant information

- Age range: 25_34
- Gender: woman
- Cultural influence country: Syntheticland
- Music listening habits: daily
- Music production/audio engineering experience: basic
- Hearing difficulty: no

## Acoustic feature guide

The acoustic values are z-scores standardized across the study stimulus set: 0 is approximately the study-stimulus average, positive values are above that average, and negative values are below that average. Positive or negative values are not inherently better.
- RMS level z-score: Standardized measure of average signal energy/level.
- Crest factor z-score: Standardized measure of peak-to-average contrast/dynamic character.
- Stereo width z-score: Standardized measure of stereo spatial spread.

## Target candidate mixes

Candidate A
- RMS z-score: -1.03
- Crest factor z-score: 0.52
- Stereo width z-score: -0.87

Candidate B
- RMS z-score: 0.00
- Crest factor z-score: -0.37
- Stereo width z-score: -1.28

Candidate C
- RMS z-score: -0.06
- Crest factor z-score: -0.84
- Stereo width z-score: 0.83

Candidate D
- RMS z-score: 2.98
- Crest factor z-score: 0.86
- Stereo width z-score: -0.93

Candidate E
- RMS z-score: 0.74
- Crest factor z-score: -1.55
- Stereo width z-score: 0.33

## Prediction/output instructions

Return exactly one JSON object and no prose outside the JSON.

Use this exact top-level structure:

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

Rules:
- `predicted_preferred_mix` must be one of `A`, `B`, `C`, `D`, or `E`.
- `predicted_ratings` must contain exactly A-E as JSON numbers from 0 to 100. Decimals are allowed.
- `predicted_ranking` must contain exactly A-E once each, ordered from most preferred to least preferred.
- Ideally, `predicted_preferred_mix`, the highest predicted rating, and the first ranking entry should agree.
- Do not include a rationale, explanation, reasoning trace, confidence field, or any extra top-level field.
