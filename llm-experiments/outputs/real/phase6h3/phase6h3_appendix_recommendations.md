# Phase 6H.3 Appendix Recommendations

- Include the full Phase 6H.1 protocol freeze artifacts as reproducibility appendices: metric protocol, tie policy, prediction/ground-truth join manifest, and QC report.
- Include Phase 6H.2B trial-level and candidate-level score CSVs as machine-readable supplementary material rather than main-body tables.
- Place `phase6h3_optional_table_3_personalisation.csv` in an appendix if the main results chapter is space-constrained.
- Use `phase6h3_supplementary_figure_personalisation_top1.png` as Supplementary Figure S1 unless the personalisation subsection needs a visual summary in the main text.
- Report Centaur rating-error metrics as not applicable because this condition uses native likelihood outputs rather than calibrated 0-100 ratings.
- Keep stale incomplete-marker notes from Phase 6H.2A in provenance/QC appendices only; the final N=33 diagnostics are the authoritative empirical outputs.

Recommended figure files:
- Figure 1: `phase6h3_figure1_mixed_effects_coefficients.png` (main)
- Figure 2: `phase6h3_figure2_top1_accuracy.png` (main)
- Supplementary Figure S1: `phase6h3_supplementary_figure_personalisation_top1.png` (appendix)
