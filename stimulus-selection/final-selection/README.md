# Final Selection

This folder documents the current final five-mix selection without moving the
authoritative artifacts from their provenance-preserving output paths.

## Authoritative Package

Current final package:

`../../outputs/stimulus_selection/11_five_mix_selection_review_20260806/`

Start with these files:

- `recommended_five_mix_selections.csv`
- `five_mix_selection_report.md`
- `five_mix_selection_traceability.md`
- `five_mix_selection_traceability.csv`
- `authoritative_sources_manifest.csv`
- `generate_five_mix_review.py`

## Selected Mixes

| Group | Song | Five selected mixes |
| --- | --- | --- |
| `group_01` | Lead Me | DU-D, DU-E, PXL-L1, PXL-L4, McG-pro2 |
| `group_01` | I'd Like To Know | PXL-S3, PXL-S5, PXL-S1, PXL-S2, PXL-S7 |
| `group_02` | In The Meantime | QUT-B, DU-H, DU-I, DU-K, QUT-pro |
| `group_02` | Pouring Room | McG-R, McG-T, McG-X, McG-pro1, McG-V |

## Runtime Interface

The deployed five-mix interface loads:

`../../study-interface/frontend-5mix/config/stimuli.json`

The final package is selection evidence. The interface config is the active
runtime source of truth for participant-facing songs, stimulus IDs, audio
paths, scenarios, group allocation, and submission fields.
