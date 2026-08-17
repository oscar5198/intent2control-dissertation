# Master Stimulus Selection Index

This is the repository-level source map for the current final five-mix stimulus
selection. The live interface is the source of truth for what participants see;
the files below explain how those final stimuli were selected and how older
evidence is retained.

## Current Authoritative Design

| Element | Authoritative file(s) | Notes |
| --- | --- | --- |
| Live frontend stimulus configuration | `study-interface/frontend-5mix/config/stimuli.json` | Current source of truth for songs, groups, stimulus IDs, real mix IDs, scenarios, and audio paths. |
| Final five-mix package | `outputs/stimulus_selection/11_five_mix_selection_review_20260806/` | Current final-selection review and traceability folder. |
| Final five-mix selections | `outputs/stimulus_selection/11_five_mix_selection_review_20260806/recommended_five_mix_selections.csv` | Researcher-facing table of the selected five mixes per active song. |
| Final traceability | `outputs/stimulus_selection/11_five_mix_selection_review_20260806/five_mix_selection_traceability.md` and `.csv` | Links final frontend stimuli to selection evidence, source audio, hashes, QC, and provenance. |
| Source manifest | `outputs/stimulus_selection/11_five_mix_selection_review_20260806/authoritative_sources_manifest.csv` | Lists the input evidence used by the final review script. |
| Review-generation script | `outputs/stimulus_selection/11_five_mix_selection_review_20260806/generate_five_mix_review.py` | Documents/reproduces the final five-mix review outputs. |
| Response interpretation | `study-interface/scripts/netlify_forms_to_long_csv_with_mix_ids.py` | Converts Netlify exports while preserving runtime labels and `actual_mix_id`. |

## Active Study Allocation

| Group | Participant excerpt | Song | Active mixes |
| --- | --- | --- | --- |
| `group_01` | Song A | Lead Me | DU-D; DU-E; PXL-L1; PXL-L4; McG-pro2 |
| `group_01` | Song B | I'd Like To Know | PXL-S3; PXL-S5; PXL-S1; PXL-S2; PXL-S7 |
| `group_02` | Song A | In The Meantime | QUT-B; DU-H; DU-I; DU-K; QUT-pro |
| `group_02` | Song B | Pouring Room | McG-R; McG-T; McG-X; McG-pro1; McG-V |

Anonymous Version A-E labels are randomised at runtime for each trial. Do not
interpret participant labels without `mix_mapping_json`,
`presentation_order_json`, and `responses_json` from the Netlify export.

## Current Provenance Flow

```text
dataset inspection and song allocation
-> excerpt selection and alignment
-> Diff-MST feature extraction
-> corrected acoustic candidate pools
-> prior-rating integration
-> Similar/Wide rating stratification and supervisor review
-> six-mix proposal evidence for main active songs
-> backup-song expansion evidence for I'd Like To Know
-> final five-mix selection review
-> frontend-5mix configuration
```

## Current Output Map

| Folder | Purpose | Status |
| --- | --- | --- |
| `01_dataset_and_song_selection/` | Dataset inspection, inventory, and initial song-selection evidence | Retained provenance. |
| `02_excerpt_selection/` | Approved 28-second excerpt decisions and diagnostics | Retained provenance. |
| `03_feature_extraction/` | Diff-MST feature extraction and feature diagnostics | Retained objective-feature source. |
| `04_mix_selection_v2/` | Corrected acoustic candidate pools and diagnostics | Retained acoustic-selection evidence. |
| `05_ratings_integration/` | Prior-rating aggregation and validation | Retained historical-rating source. |
| `05_alignment_verification/` | Alignment QA for earlier rating-stratified sets | Retained provenance. |
| `06_rating_stratification/` | Similar/Wide recommendation triplets and review audio | Retained supporting evidence. |
| `07_supervisor_review_package/` | Supervisor-facing review material for original candidates | Retained supporting evidence for active and replaced candidates. |
| `08_backup_song_expansion/` | Backup-song expansion and replacement-song evidence | Retained because active `I'd Like To Know` depends on it. |
| `09_six_mix_proposals/` | Six-mix proposal evidence, QC, distances, alignment, and audio manifests | Retained because final five-mix traceability references it. |
| `10_abx_fixed_excerpt_similarity_review/` | Fixed-excerpt similarity review | Retained supporting evidence. |
| `11_five_mix_selection_review_20260806/` | Final five-mix review and traceability | Current authoritative final-selection package. |
| `09_current_frontend_integration/` | Older frontend-derived three-mix/stale integration record | Historical only; not authoritative for the live five-mix interface. |
| `archive/medoid_contrast_legacy/` | Earlier representative/contrast outputs and old final summaries | Legacy only; retained for methodology history. |
| `logs_and_provenance/` | Reorganisation and provenance logs | Historical/provenance support. |

## Validation

Validate the active frontend with:

```powershell
python study-interface\scripts\validate_frontend_5mix.py
```

The validator checks the active five-mix configuration, group allocation,
stimulus IDs, real mix IDs, referenced audio files, and obsolete donor-audio
exclusion inside `study-interface/frontend-5mix/`.
