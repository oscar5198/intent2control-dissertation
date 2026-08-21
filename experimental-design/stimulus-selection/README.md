# Stimulus Selection

## Purpose

Stimulus selection was required to turn the Mix Evaluation Dataset material into a controlled final listening study: four songs, five mixes per song, consistent excerpt duration, technical checks, acoustic feature coverage, prior-rating context, and traceable A-E stimulus mappings.

## Final Design

- Study design: final five-mix listening study.
- Songs: 4.
- Mixes per song: 5.
- Final song-mix stimuli: 20.
- Study groups: 2.
- Listening contexts: 3, defined by the active five-mix interface.

The live study interface remains the primary source of truth for participant presentation:

`study-interface/frontend-5mix/config/stimuli.json`

## Final Stimuli

| Group | Song | Final selected mixes |
| --- | --- | --- |
| `group_01` | Lead Me | DU-D, DU-E, McG-pro2, PXL-L1, PXL-L4 |
| `group_01` | I'd Like To Know | PXL-S1, PXL-S2, PXL-S3, PXL-S5, PXL-S7 |
| `group_02` | In The Meantime | DU-H, DU-I, DU-K, QUT-B, QUT-pro |
| `group_02` | Pouring Room | McG-pro1, McG-R, McG-T, McG-V, McG-X |

## Selection Workflow

The retained workflow is:

1. Inspect dataset/song eligibility and available human mix populations.
2. Select aligned 28-second excerpts and verify decoding/alignment.
3. Extract Diff-MST/MST-inspired acoustic descriptors: RMS, crest factor, stereo width, stereo imbalance for QC, and Bark mid-side spectral features.
4. Build corrected acoustic candidate pools and pairwise distance tables.
5. Integrate prior Mix Evaluation Dataset preference ratings.
6. Use similar-rating and range-broadening evidence to prepare supervisor-review sets.
7. Resolve the final five-mix design, replacing Red To Blue with I'd Like To Know.
8. Validate the final 20 frontend stimuli by stimulus ID, mix ID, audio path, hash, duration, sample rate, and channel count.

## Repository Map

- `config/stimulus_selection.yaml` - retained stimulus-selection configuration and scientific parameters.
- `src/stimulus_selection/` - reusable workflow source code and vendored Diff-MST feature descriptors.
- `final-selection/five-mix-selection-review-20260806/` - final five-mix selection tables, traceability, review report, and generation script.
- `final-selection/source-evidence/` - compact source tables and notes consumed by the final five-mix selection generator.
- `final-selection/frontend-integration/` - final frontend stimulus integrity table and validation report.

## Provenance And Feature Attribution

The dataset source was the local Mix Evaluation Dataset configured in `config/stimulus_selection.yaml`: the relationship tables under `C:/Users/oscar/OneDrive/Public share - Mix Eval Dataset/mix_evaluation_relationship_tables` and public audio under `C:/Users/oscar/OneDrive/Public share - Mix Eval Dataset/MixEvaluation/audio`. The stimulus-selection workflow records song, mix, institution, public-audio, technical-validation, duplicate, and eligibility metadata; it does not modify the source dataset audio.

The MST/Diff-MST descriptors were derived from the external Diff-MST repository, inspected at commit `3b90ef838272b827c86610cf25b510a23a4147fd` from `https://github.com/sai-soum/Diff-MST.git`. The retained package vendors only the needed feature functions under `src/stimulus_selection/third_party/diffmst_features`: RMS, crest factor, Bark spectrum, stereo width, stereo imbalance, and Bark filterbank helpers. Compatibility changes are limited to package-local imports, removal of unrelated neural components, a `(batch, channels, samples)` input contract, stereo-only checks, and NaN/Inf rejection. Bark spectrum is treated as a multidimensional mid-side descriptor, not one scalar. The vendored files retain Diff-MST attribution and licence material in `LICENSE_DIFF_MST.txt`, `ATTRIBUTION.md`, and `feature_definitions.json`.

The final acoustic feature chain is:

1. Participant-facing WAVs in `study-interface/frontend-5mix/assets/audio/study-stimuli/main-study/`.
2. Feature exploration notebook `statistical-modeling/notebooks/acoustic_feature_extraction.ipynb`.
3. Final 20-stimulus feature table `statistical-modeling/outputs/acoustic-features/final_20_stimulus_feature_table.csv`.
4. Human response table `data/processed/ratings_final.csv`.
5. Statistical modeling model `statistical-modeling/src/statistical_baseline/real_feature_model.py`.
6. LLM integration code `llm-experiments/src/llm_experiments/data/integration.py`.
7. Final LLM held-out prompt data `data/processed/llm_heldout_prompt_data_final.csv`.

## Reproducibility

Set the package path from the repository root:

```powershell
$env:PYTHONPATH = "experimental-design/stimulus-selection/src"
```

Load the consolidated config with:

```powershell
python -m stimulus_selection.cli validate-diffmst-features `
  --config experimental-design/stimulus-selection/config/stimulus_selection.yaml `
  --reference-root "C:/Users/oscar/Documents/7. QMUL UNIVERSITY/1. Master Program/3. MSc Project/Diff-MST"
```

The final five-mix review generator is retained at:

```powershell
python experimental-design/stimulus-selection/final-selection/five-mix-selection-review-20260806/generate_five_mix_review.py
```
