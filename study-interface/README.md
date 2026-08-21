# Study Interface

This folder contains the final static five-mix listening-study interface used
for the MSc dissertation. It is a plain HTML/CSS/JavaScript frontend deployed
to Netlify with Netlify Forms response storage.

## Final Design

- Two participant groups.
- Four final songs, two assigned to each group.
- Five anonymous mix versions per song, shown as A-E within each trial.
- Three listening contexts: Enjoyment (`EDR-1`), Relaxation-Distraction
  (`EDR-2`), and Focus-Motivation (`FM-1`).
- Six main-study trials per participant.
- 0-100 ratings for each presented mix.
- One comparative comment per trial.
- Netlify form submission using `listening-study-5mix` and
  `five_mix_netlify_forms_v1`.

## Final Interface

The participant-facing interface is:

```text
frontend-5mix/
```

Important files:

- `frontend-5mix/index.html`
- `frontend-5mix/pages/`
- `frontend-5mix/css/`
- `frontend-5mix/js/`
- `frontend-5mix/config/stimuli.json`
- `frontend-5mix/config/scenarios.json`
- `frontend-5mix/config/study-config.json`
- `frontend-5mix/js/randomisation.js`
- `frontend-5mix/js/netlify-submission.js`

The local interface can be opened from `frontend-5mix/index.html` or served by
any static web server from `frontend-5mix/`. No Node build step is required.

## Audio and Mapping

The 20 final main-study WAV files are under:

```text
frontend-5mix/assets/audio/study-stimuli/main-study/
```

Practice, setup, and pre-study screening audio used by the final runtime remain
under `frontend-5mix/assets/audio/`. The active stimulus IDs, real mix IDs,
anonymous A-E presentation mapping, and local audio paths are defined in
`frontend-5mix/config/stimuli.json`. The context text is defined in
`frontend-5mix/config/scenarios.json`; global study settings are defined in
`frontend-5mix/config/study-config.json`.

## Response Conversion

Runtime submission code remains in:

```text
frontend-5mix/js/netlify-submission.js
```

The final offline Netlify export converter belongs to the data pipeline:

```text
../data/scripts/convert_netlify_responses.py
```

The retained interface validator is:

```text
scripts/validate_frontend_5mix.py
```

## Data Interpretation

Participant responses are reconstructable because the form submission preserves
`mix_mapping_json`, `presentation_order_json`, `responses_json`, and stable
`actual_mix_id` / `stimulus_id` fields. The raw Netlify export should be kept
outside Git unless a separate approved retention/anonymisation decision is made.
