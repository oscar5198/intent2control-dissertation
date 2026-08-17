# Intent2Control with Controllable Intent Strength

This repository contains the MSc dissertation project **Intent2Control with
Controllable Intent Strength**. The current work centres on an online listening
study that tests how semantic listening contexts relate to listener preference
for alternative music mixes.

## Active Final Listening Study

The live study is the five-mix interface in:

`study-interface/frontend-5mix/`

The active Netlify form is `listening-study-5mix`. While the study is live, do
not rename this folder or change its stimulus configuration, audio paths,
runtime A-E randomisation, trial randomisation, form fields, or response JSON
structure without a separate deployment plan.

Active songs and selected mixes:

| Group | Song | Five selected mixes |
| --- | --- | --- |
| `group_01` | Lead Me | DU-D, DU-E, PXL-L1, PXL-L4, McG-pro2 |
| `group_01` | I'd Like To Know | PXL-S3, PXL-S5, PXL-S1, PXL-S2, PXL-S7 |
| `group_02` | In The Meantime | QUT-B, DU-H, DU-I, DU-K, QUT-pro |
| `group_02` | Pouring Room | McG-R, McG-T, McG-X, McG-pro1, McG-V |

The obsolete three-mix and six-mix frontend folders were removed locally. The
current five-mix frontend remains the source of truth for the live interface.

## Repository Map

```text
intent2control-dissertation/
|-- data/                    # Raw and processed data areas
|-- study-interface/          # Live five-mix frontend, docs, export scripts
|-- results/                  # Reserved for final reported outputs
|-- outputs/                  # Reproducible/generated analysis outputs
|-- stimulus-selection/       # Top-level guide to selection code and evidence
|-- src/stimulus_selection/   # Reusable stimulus-selection source code
|-- configs/                  # Pipeline configuration
|-- statistical-baseline/     # Guide to baseline notebooks and outputs
|-- llm-experiments/          # Planned LLM evaluation protocol and checks
|-- dissertation/             # Dissertation drafts, figures, and tables
|-- tests/                    # Stimulus-selection and interface validation
|-- bibliography/             # Reference PDFs and bibliography material
`-- README.md
```

## Stimulus Selection

Reusable code lives in `src/stimulus_selection/`, with configuration in
`configs/stimulus_selection.yaml`.

The final five-mix selection evidence is in:

`outputs/stimulus_selection/11_five_mix_selection_review_20260806/`

Start with `stimulus-selection/README.md` and
`outputs/stimulus_selection/README.md` for the current provenance map. Some
folders with older names are intentionally retained because the final five-mix
traceability files still reference them, especially
`outputs/stimulus_selection/09_six_mix_proposals/` and shared material under
`outputs/stimulus_selection/08_backup_song_expansion/`.

## Statistical Baseline

The statistical baseline work is documented from `statistical-baseline/README.md`.
The notebooks, synthetic baseline data, and generated outputs are consolidated
under `statistical-baseline/`.

This area includes Bambi/PyMC/ArviZ modelling, participant random-effect models,
episode-by-stimulus models, acoustic-feature models, sample-size simulations,
posterior winner calculations, and final evaluation support.

## LLM Experiments

Planned personalised LLM prediction work is organised under `llm-experiments/`.
The current evaluation protocol and environment-testing notebook are preserved
there. Human-response comparisons and final model results should not be treated
as complete until the experiment has been run and frozen.

## Data, Results, And Responses

Raw/source datasets, processed data, participant exports, and generated results
should stay separated. Do not commit raw participant exports or modify response
data without a separate anonymisation and retention decision.

Response interpretation for the active study depends on Netlify JSON fields such
as `mix_mapping_json`, `presentation_order_json`, `responses_json`, and
`actual_mix_id`. Use:

`study-interface/scripts/netlify_forms_to_long_csv_with_mix_ids.py`

## Validation

Useful validation entry points include:

```powershell
python study-interface\scripts\validate_frontend_5mix.py
python -m pytest tests\study_interface tests\stimulus_selection
```

The five-mix validator checks stimulus IDs, real mix IDs, audio existence, group
assignment, and the absence of obsolete donor audio from the active frontend.

## Dissertation And References

Dissertation drafts, figures, and tables live in `dissertation/`. Reference PDFs
and bibliography material remain in `bibliography/` because they have not been
proven redundant.
