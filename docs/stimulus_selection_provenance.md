# Stimulus Selection Provenance

## Dataset Source

The stimulus-selection pipeline uses the local Mix Evaluation Dataset copy at:

`C:/Users/oscar/OneDrive/Public share - Mix Eval Dataset`

Canonical Stage 1 metadata is read from:

`C:/Users/oscar/OneDrive/Public share - Mix Eval Dataset/mix_evaluation_relationship_tables`

Public listening-test audio is read from:

`C:/Users/oscar/OneDrive/Public share - Mix Eval Dataset/MixEvaluation/audio`

The pipeline records song, mix, institution, public-audio, technical-validation, duplicate, and eligibility metadata. It does not modify source audio.

## Diff-MST Reference

Diff-MST is an external reference implementation and remains in its own repository.

- Local inspected repository: `C:/Users/oscar/Documents/7. QMUL UNIVERSITY/1. Master Program/3. MSc Project/Diff-MST`
- Remote URL inspected: `https://github.com/sai-soum/Diff-MST.git`
- Commit inspected for Stage 1 planning: `3b90ef838272b827c86610cf25b510a23a4147fd`
- Local paper copy: `bibliography/papers/04_Differentiable_DSP/DIFF-MST.pdf`

Citation to include in the dissertation bibliography: the Diff-MST paper associated with the external Diff-MST repository and local paper copy above. The repository currently does not contain a dedicated BibTeX entry for this paper, so the final citation details should be added to `bibliography/references.bib` before submission.

## Stage 3 Diff-MST Feature Reuse

Stage 3 vendors only the minimal Diff-MST audio-production feature transforms needed for stimulus selection. The full Diff-MST repository is not a runtime dependency because this dissertation stage needs reproducible descriptors of mix dynamics, spectral characteristics and spatialisation, not the neural model, training losses, model architecture, data loaders or inference scripts.

Vendored location:

`src/stimulus_selection/third_party/diffmst_features`

Copied from `mst/loss.py` and `mst/filter.py`:

- `mst.loss.compute_rms`
- `mst.loss.compute_crest_factor`
- `mst.loss.compute_barkspectrum`
- `mst.loss.compute_stereo_width`
- `mst.loss.compute_stereo_imbalance`
- `mst.filter.barkscale_fbanks`
- `mst.filter._hz_to_bark`
- `mst.filter._bark_to_hz`
- `mst.filter._create_triangular_filterbank`

Compatibility modifications:

- imports changed to package-local imports;
- unrelated Diff-MST neural components removed;
- input contract `(batch, channels, samples)` documented and enforced;
- stereo-only features require exactly two channels;
- NaN and Inf inputs are rejected before feature computation.

The Bark spectrum is treated as a multidimensional representation, not collapsed to one scalar. With the inspected reference defaults, `compute_barkspectrum(..., mode="mid-side")` returns `(batch, 24, 2)`.

## Licence And Attribution Considerations

- The Mix Evaluation Dataset includes songs with mixed licence labels, including Creative Commons and copyrighted material. Stage 1 preserves local licence labels where provided and does not redistribute audio.
- Generated inventory/report files are reproducible derivatives and should be reviewed before sharing outside the project.
- Diff-MST feature code is vendored under `src/stimulus_selection/third_party/diffmst_features` with `LICENSE_DIFF_MST.txt`, `ATTRIBUTION.md`, and `feature_definitions.json`. The vendored code remains attributed to Diff-MST and licensed under CC-BY-NC-SA 4.0.

## Stage 2 Decoding Provenance

- Decoder backend used for retained files: soundfile (73 files)
- soundfile version: 0.14.0
- linked libsndfile version: 1.2.2
- MP3 support available through soundfile/libsndfile: true
- Full waveform decode via `sf.read` verified for retained files: true (73/73)
- Decoded frame-derived durations consistent with updated `alignment_results.csv`: true
- `soundfile.info()` frame count exactly matches decoded frames: false (53/73); 20 48 kHz MP3 files have info/read deltas up to 4240 frames, so decoded waveform frame counts are recorded as authoritative for Stage 2 duration provenance.
- Detailed table: decoding_verification_report.csv
- Manual review mapping: manual_review_candidate_summary.csv and manual_review_candidate_summary.md

Stage 2 did not extract Diff-MST features, select final mix triplets, loudness-normalise stimuli, or alter original source audio.

## Stage 3 Validation Provenance

The Stage 3 validation command compares the vendored functions against a test-only import of the original Diff-MST functions:

```powershell
$env:PYTHONPATH = "src"
python -m stimulus_selection.cli validate-diffmst-features `
  --config configs/stimulus_selection.yaml `
  --reference-root "C:/Users/oscar/Documents/7. QMUL UNIVERSITY/1. Master Program/3. MSc Project/Diff-MST"
```

Generated reports:

- `outputs/stimulus_selection/03_feature_extraction/tables/reference_equivalence_report.csv`
- `outputs/stimulus_selection/03_feature_extraction/reports/diffmst_feature_validation_report.md`

Equivalence is tested using deterministic synthetic stereo signals, float32 and float64 tensors, numerical edge cases, and one real Stage 2 decoded approved-preview excerpt when present. The approved preview WAVs are used only as diagnostic validation examples; they are not treated as the final feature-extraction input pool.

These transforms are descriptors, not subjective quality scores. Stage 3 validation stops before extracting features for all mixes, normalising features, running PCA, calculating distances, selecting final triplets or loudness-normalising stimuli.

## Stage 3B Raw Feature Extraction Provenance

Stage 3B extracts the validated Diff-MST descriptors for every Stage-2-retained human mix of the four approved songs. The extractor uses the main Stage 2 alignment file plus `outputs/stimulus_selection/02_excerpt_selection/diagnostics/stage2_remaining/alignment_results.csv` for the two fallback songs.

Generated outputs:

- `outputs/stimulus_selection/03_feature_extraction/tables/raw_diffmst_features.csv`
- `outputs/stimulus_selection/03_feature_extraction/tables/feature_schema.json`
- `outputs/stimulus_selection/03_feature_extraction/tables/feature_quality_checks.csv`
- `outputs/stimulus_selection/03_feature_extraction/reports/feature_extraction_report.md`
- `outputs/stimulus_selection/03_feature_extraction/tables/feature_summary_by_song.csv`
- `outputs/stimulus_selection/03_feature_extraction/tables/bark_summary_by_song.csv`
- `outputs/stimulus_selection/03_feature_extraction/feature_diagnostics/`

Extraction uses `source_time = aligned_time + refined_lag_seconds`, decodes the 28.000-second section before diagnostic-preview fades, resamples to 44.1 kHz, preserves stereo, and computes RMS, crest factor, stereo width, stereo imbalance and all 48 Bark mid-side columns. The canonical Stage 2 retained population is 92 rows: Lead Me 37, In The Meantime 36, Red To Blue 10 and Pouring Room 9. The difference from the approximate 93-mix expectation is recorded in Stage 2: one Pouring Room mix was excluded for low alignment confidence; one Red To Blue automated/system row is excluded from the human population.

No Stage 3B output performs robust scaling, standardisation, PCA, pairwise distance calculation, triplet selection, final Version A/B/C labelling or loudness normalisation.
