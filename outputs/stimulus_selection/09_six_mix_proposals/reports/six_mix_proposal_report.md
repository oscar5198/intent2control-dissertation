# Six-Mix Proposal Report

This proposal layer responds to the supervisor request to inspect whether each main study song can support six mixes rather than a three-mix triplet.

No frontend implementation was performed. No participant-facing A-F labels were created. The four selected songs, approved 28-second excerpts, corrected acoustic methodology, Phase 2B Similar/Wide triplets and existing three-mix outputs were left unchanged.

The six-mix set for each song is the union of the non-overlapping Similar Ratings and Wide Ratings triplets. Acoustic diversity continues to use rms_mean, crest_factor_mean, stereo_width, and Bark mid/side features through the corrected within-song PCA distance outputs. Stereo imbalance remains QC-only and was not introduced into acoustic distance calculations.

Historical Brecht preference ratings are used only as second-stage within-song stratification context. They are not interpreted as ground-truth quality scores.

Review WAVs were loudness-normalised to -20.8 LUFS integrated, exported as 44.1 kHz stereo PCM 24-bit, and retained the 5 ms half-cosine boundary fade.

## Selected Sets

| song | rating_condition | original_mix_name | mean_previous_preference | technical_qc_status |
| --- | --- | --- | --- | --- |
| Lead Me | Similar Ratings | DU-D | 0.344928583221 | REVIEW |
| Lead Me | Similar Ratings | DU-E | 0.288513454805 | REVIEW |
| Lead Me | Similar Ratings | QUT-F | 0.320524872239 | REVIEW |
| Lead Me | Wide Ratings | PXL-L1 | 0.331806996292 | REVIEW |
| Lead Me | Wide Ratings | PXL-L4 | 0.516818070818 | REVIEW |
| Lead Me | Wide Ratings | McG-pro2 | 0.547365451895 | REVIEW |
| In The Meantime | Similar Ratings | QUT-B | 0.169540672643 | REVIEW |
| In The Meantime | Similar Ratings | DU-H | 0.560388064169 | REVIEW |
| In The Meantime | Similar Ratings | DU-I | 0.531178215151 | REVIEW |
| In The Meantime | Wide Ratings | DU-K | 0.136285256921 | REVIEW |
| In The Meantime | Wide Ratings | QUT-pro | 0.584611251475 | REVIEW |
| In The Meantime | Wide Ratings | DU-N | 0.428148862499 | REVIEW |
| Red To Blue | Similar Ratings | McG-B | 0.527445392944 | REVIEW |
| Red To Blue | Similar Ratings | McG-G | 0.513281921228 | REVIEW |
| Red To Blue | Similar Ratings | McG-F | 0.320184670736 | REVIEW |
| Red To Blue | Wide Ratings | McG-C | 0.589852124377 | REVIEW |
| Red To Blue | Wide Ratings | McG-H | 0.444788772745 | REVIEW |
| Red To Blue | Wide Ratings | McG-pro1 | 0.361486461668 | REVIEW |
| Pouring Room | Similar Ratings | McG-R | 0.391330644411 | REVIEW |
| Pouring Room | Similar Ratings | McG-T | 0.315778789267 | REVIEW |
| Pouring Room | Similar Ratings | McG-X | 0.326821477012 | REVIEW |
| Pouring Room | Wide Ratings | McG-pro1 | 0.741587086846 | REVIEW |
| Pouring Room | Wide Ratings | McG-U | 0.459458567457 | REVIEW |
| Pouring Room | Wide Ratings | McG-V | 0.510318833291 | REVIEW |

## Acoustic Summary

| song | similar_triplet_minimum_distance | wide_triplet_minimum_distance | full_six_mix_minimum_distance | full_six_mix_mean_distance | full_six_mix_maximum_distance | near_duplicate_count |
| --- | --- | --- | --- | --- | --- | --- |
| Lead Me | 3.16805889374 | 2.92257247514 | 1.62365090559 | 2.96606380999 | 3.49499417947 | 0 |
| In The Meantime | 3.41830268237 | 2.5855827592 | 1.83334921312 | 3.39725083956 | 5.56099797932 | 0 |
| Red To Blue | 2.59969815564 | 1.94841652108 | 1.58101498685 | 2.36862228953 | 3.21748310589 | 0 |
| Pouring Room | 1.88514897969 | 1.69525800496 | 1.50639550314 | 2.26644216568 | 3.07136962966 | 0 |

## Rating Summary

| song | similar_rating_spread | wide_rating_spread | full_six_mix_rating_range | minimum_rating_count | maximum_rating_count |
| --- | --- | --- | --- | --- | --- |
| Lead Me | 0.056415128416 | 0.215558455603 | 0.25885199709 | 6 | 45 |
| In The Meantime | 0.390847391526 | 0.448325994554 | 0.448325994554 | 16 | 54 |
| Red To Blue | 0.207260722208 | 0.228365662709 | 0.269667453641 | 26 | 26 |
| Pouring Room | 0.075551855144 | 0.282128519389 | 0.425808297579 | 40 | 40 |

## Alignment Summary

| song | maximum_offset_ms | automatic_status |
| --- | --- | --- |
| Lead Me | 46.4399092971 | FAIL |
| In The Meantime | 34.8299319728 | FAIL |
| Red To Blue | 11.6099773243 | REVIEW |
| Pouring Room | 58.0498866213 | FAIL |

Usability burden still needs to be tested separately before any six-mix design is treated as approved.
