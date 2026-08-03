# Stimulus Selection Outputs

## Start Here
- `06_final_summaries/pipeline_summary.md`
- `06_final_summaries/final_selected_mixes.md`
- `02_excerpt_selection/reports/final_excerpt_decision.md`
- `04_mix_selection/reports/final_mix_selection_report.md`
- `05_manual_review/tables/stage4_manual_review.csv`

Canonical frontend stimulus files are in `outputs/final_stimuli/stimuli/`.

## Pipeline Order
1. `01_dataset_and_song_selection/`: inputs and intermediate outputs for dataset inventory and song choice.
2. `02_excerpt_selection/`: alignment, approved 28-second excerpt decisions, diagnostic previews, and excerpt diagnostics.
3. `03_feature_extraction/`: validated Diff-MST features, feature quality checks, schema, and diagnostics.
4. `04_mix_selection/`: computational mix-selection tables, reports, figures, and selected review previews.
5. `05_manual_review/`: human approval records and manual-review instructions.
6. `06_final_summaries/`: compact final files for quick checking.
7. `logs_and_provenance/`: migration, cleanup, naming, and reorganisation records.
8. `archive_unused/`: superseded or legacy-layout files preserved for traceability.
