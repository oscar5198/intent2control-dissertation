# Frontend Stimulus Integrity Validation

Validation date: 2026-08-03

Validated source files:

- `study-interface/frontend/config/stimuli.json`
- `study-interface/docs/final-stimuli-manifest.md`
- `outputs/stimulus_selection/09_current_frontend_integration/tables/current_frontend_stimuli.csv`

## Result

Passed.

## Checks

| Check | Result |
| --- | --- |
| `stimuli.json` parses as JSON | Pass |
| Four active main-study excerpts are configured | Pass |
| Each configured song has exactly three active mixes | Pass |
| Total active configured mixes equals 12 | Pass |
| `group_01` contains Lead Me and Red To Blue | Pass |
| `group_02` contains In The Meantime and Pouring Room | Pass |
| Active categories match the current design | Pass |
| Every configured source WAV exists | Pass |
| Every configured frontend WAV exists | Pass |
| Participant-facing song labels are neutral | Pass |
| Manifest and config agree on song/category entries | Pass |
| `productionReady` is not misleading while perceptual approval is pending | Pass |

## Active Allocation Confirmed

| Group | Participant excerpt | Artist | Song | Active category | Mixes |
| --- | --- | --- | --- | --- | --- |
| `group_01` | Song A | The DoneFors | Lead Me | Wide Ratings | PXL-L1; PXL-L4; McG-pro2 |
| `group_01` | Song B | Broken Crank | Red To Blue | Wide Ratings | McG-C; McG-H; McG-pro1 |
| `group_02` | Song A | Fredy V | In The Meantime | Wide Ratings | DU-K; QUT-pro; DU-N |
| `group_02` | Song B | The DoneFors | Pouring Room | Similar Ratings | McG-R; McG-T; McG-X |

Current status: technically integrated; perceptual approval pending.
