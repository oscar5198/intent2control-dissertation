# Stimulus Selection

This folder is the navigation layer for the stimulus-selection work. The
generated evidence remains in `../outputs/stimulus_selection/` because many
notebooks, tests, reports, CSV provenance fields, and active-study metadata
still refer to those paths.

## Start Here

- Final selected five mixes: `final-selection/`
- Selection provenance and retained historical evidence: `provenance/`
- Figure locations: `figures/`
- Data locations: `data/`

## Active Source Of Truth

The live five-mix listening-study interface remains the primary source of
truth:

`../study-interface/frontend-5mix/config/stimuli.json`

Do not edit that file while the Netlify study is live unless intentionally
changing the active experiment.

## Reusable Code And Configuration

- Source code: `../src/stimulus_selection/`
- Configuration: `../configs/stimulus_selection.yaml`
- Tests: `../tests/stimulus_selection/`

## Active Songs

| Group | Song | Five selected mixes |
| --- | --- | --- |
| `group_01` | Lead Me | DU-D, DU-E, PXL-L1, PXL-L4, McG-pro2 |
| `group_01` | I'd Like To Know | PXL-S3, PXL-S5, PXL-S1, PXL-S2, PXL-S7 |
| `group_02` | In The Meantime | QUT-B, DU-H, DU-I, DU-K, QUT-pro |
| `group_02` | Pouring Room | McG-R, McG-T, McG-X, McG-pro1, McG-V |

## Why The Output Tree Stayed Put

The final five-mix package and its supporting evidence are path-sensitive
provenance artifacts. Moving them would require broad rewrites across
generated reports, validation tests, notebooks, CSV metadata, dissertation
references, and non-runtime source metadata in the active interface. For this
cleanup pass, the safer reorganisation is a documented index rather than a
physical move.
