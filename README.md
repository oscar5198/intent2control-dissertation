# Intent2Control with Controllable Intent Strength

## Project Description

This repository contains the MSc dissertation project **Intent2Control with Controllable Intent Strength**. The project explores semantic audio control: mapping natural-language mixing intentions to audio processing parameters such as equalisation, compression, and reverberation.

The long-term aim is to investigate how mixing intent can be represented, interpreted, and translated into controllable audio-processing behaviour, including different degrees of intent strength.

## Academic Context

- **Programme:** MSc dissertation project
- **Supervisor:** Prof. Georgios Velissaridis
- **Current phase:** Phase 0 - Project Setup

## Planned Repository Structure

```text
intent2control-dissertation/
├── bibliography/       # Reference material and bibliography files
├── data/
│   ├── raw/            # Raw datasets and source audio files (not tracked)
│   └── processed/      # Processed datasets and derived data (not tracked)
├── dissertation/       # Dissertation drafts, outlines, and written material
├── docs/               # Project notes, design documents, and documentation
├── experiments/        # Experiment outputs and exploratory runs (not tracked)
├── notebooks/          # Jupyter notebooks for exploration and analysis
├── results/            # Generated figures, tables, and model outputs (not tracked)
├── src/                # Source code for the project
├── .gitignore
└── README.md
```

## Status

This repository is currently in initial setup. No implementation code, datasets, experiments, or results have been added yet.

## Stimulus Selection Pipeline

This repository now contains the dissertation-specific stimulus-selection pipeline used to prepare candidate audio for the online listening study. The code lives in `src/stimulus_selection`, with configuration in `configs/stimulus_selection.yaml`, tests in `tests/stimulus_selection`, and reproducible generated outputs in `outputs/stimulus_selection`.

The pipeline has five planned stages:

1. Stage 1 - canonical inventory and audio validation: join Mix Evaluation Dataset metadata, verify public audio availability, classify institution provenance, flag duplicate candidates, and rank eligible songs.
2. Stage 2 - excerpt alignment: align and trim public listening-test excerpts without modifying source files.
3. Stage 3 - feature extraction: compute mix-balance descriptors, including the vendored, attributed Diff-MST feature transforms.
4. Stage 4 - triplet selection: choose three mix versions per song according to the study design and reproducibility constraints.
5. Stage 5 - stimulus export and study-interface handoff: produce final manifests and audio assets for the online listening study.

Diff-MST is treated as an attributed external source. Stage 3 vendors only the five feature transforms needed for stimulus selection, plus the Bark filterbank helpers, under `src/stimulus_selection/third_party/diffmst_features`. The full Diff-MST model, training code and data loaders are not runtime dependencies. The features describe mix dynamics, Bark-spectrum characteristics and stereo spatialisation; they are not subjective quality scores.

To reproduce Stage 1 from the dissertation repository root:

```powershell
$env:PYTHONPATH = "src"
python -m stimulus_selection.cli inventory --config configs/stimulus_selection.yaml
python -m unittest discover -s tests\stimulus_selection -v
```

Stage 1 writes reproducible CSV and Markdown reports to `outputs/stimulus_selection/`. These generated outputs are ignored by git.

To validate the Stage 3 Diff-MST feature implementation against the external reference:

```powershell
$env:PYTHONPATH = "src"
python -m stimulus_selection.cli validate-diffmst-features `
  --config configs/stimulus_selection.yaml `
  --reference-root "C:/Users/oscar/Documents/7. QMUL UNIVERSITY/1. Master Program/3. MSc Project/Diff-MST"
```

This writes `outputs/stimulus_selection/03_feature_extraction/tables/reference_equivalence_report.csv` and `outputs/stimulus_selection/03_feature_extraction/reports/diffmst_feature_validation_report.md`. It does not extract features for every dataset mix.

To run Stage 3B raw feature extraction for the Stage-2-retained human mixes:

```powershell
$env:PYTHONPATH = "src"
python -m stimulus_selection.cli extract-features --config configs/stimulus_selection.yaml
```

This writes the raw Diff-MST feature table, schema, quality checks, summaries, report and diagnostic figures under `outputs/stimulus_selection/`. It stops before feature scaling, PCA, distance calculation, triplet selection and loudness normalisation.
