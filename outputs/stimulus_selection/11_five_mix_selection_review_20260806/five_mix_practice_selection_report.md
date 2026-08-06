# Five-Mix Practice Selection Report

The current practice song/excerpt/vignette/rating scale/anchors/purpose/validation separation were preserved. The previous fixed practice versions remain CNS-A, CNS-B, and CNS-C.

No repository evidence was found for existing MST/Diff-MST practice-song features for ColdStar. For this practice-only choice, I computed lightweight QA features from the existing frontend WAV files only: RMS, peak/crest, zero-crossing proxy, spectral centroid/flatness/rolloff summaries. These are not MST/Diff-MST feature extraction and do not modify audio.

## Candidate Result

| Candidate additions | Minimum distance | Median distance | Mean distance | Selected |
|---|---:|---:|---:|---|
| CNS-D + CNS-5 | 2.350 | 4.053 | 4.459 | no |
| CNS-D + CNS-pro | 2.350 | 3.724 | 3.845 | no |
| CNS-5 + CNS-pro | 3.237 | 5.288 | 4.987 | yes |

`CNS-5 + CNS-pro` was selected as Versions D and E because it produced the largest minimum pairwise distance after retaining the fixed CNS-A/B/C base.

## Final Practice Mapping

| Version | Mix | File | SHA-256 |
|---|---|---|---|
| A | CNS-A | `study-interface\frontend-5mix\assets\audio\study-stimuli\practice-trial\coldstar\cns_a.wav` | `be074d39eea697501f26d9ad250c0ea0172075d7a92d4d48313cdc0299f47b78` |
| B | CNS-B | `study-interface\frontend-5mix\assets\audio\study-stimuli\practice-trial\coldstar\cns_b.wav` | `72743b8641b9bdccead69b92a53de545863518f59e8e8fc3efabe53a459b6404` |
| C | CNS-C | `study-interface\frontend-5mix\assets\audio\study-stimuli\practice-trial\coldstar\cns_c.wav` | `888e6a255f3863133218eb82deb155707a728cffa97e4a8b77c98044ba7c1103` |
| D | CNS-5 | `study-interface\frontend-5mix\assets\audio\study-stimuli\practice-trial\coldstar\cns_5.wav` | `453fdc66d4e1f97ad5b5029392f095d2bfaf1850c06ca20c7555f6165ba042b7` |
| E | CNS-pro | `study-interface\frontend-5mix\assets\audio\study-stimuli\practice-trial\coldstar\cns_pro.wav` | `7f9044a39c7cacc41be9815a805ed0018f51aa2a0d305f4086215f6926b8b11e` |

Full candidate metrics are in `five_mix_practice_selection_distances.csv`.
