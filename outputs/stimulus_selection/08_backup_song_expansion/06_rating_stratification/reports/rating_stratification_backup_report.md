# Rating Stratification Report

Phase 2B combines fixed corrected acoustic candidate pools with Phase 2A prior preference ratings to recommend supervisor-review triplets. Acoustic distances are read from `pairwise_distances_v2.csv` and are not recomputed or modified.

Objective weighting: 0.8 acoustic diversity and 0.2 rating stratification. Similar-rating triplets minimise rating spread within acoustically diverse combinations; wide-rating triplets maximise rating spread while retaining acoustic diversity. QC review/caution statuses are penalised lightly and reported, not automatically excluded.

Unrated candidate-pool mixes are documented in Phase 2A but excluded from rating-based recommendation sets because no mean preference is available.

## Recommendations

| Song | Condition | Mixes | Rating spread | Minimum acoustic distance | QC statuses |
| --- | --- | --- | ---: | ---: | --- |
| I'd Like To Know | Similar Ratings | PXL-S3|PXL-S5|PXL-S1 | 0.135 | 2.639 | clear|clear|clear |
| I'd Like To Know | Wide Ratings | PXL-S2|PXL-S6|PXL-S7 | 0.167 | 1.354 | clear|clear|clear |
| New Skin | Similar Ratings | DU-Q|DU-R|DU-O | 0.321 | 2.381 | clear|clear|clear |
| New Skin | Wide Ratings | DU-U|DU-T|DU-S | 0.291 | 1.286 | clear|clear|clear |
| No Prize | Similar Ratings | McG-L|McG-pro2|McG-N | 0.251 | 2.440 | clear|clear|clear |
| No Prize | Wide Ratings | McG-K|McG-P|McG-O | 0.227 | 1.194 | clear|clear|clear |
| Vermont | Similar Ratings | DU-P2|DU-O2|PXL-L3 | 0.245 | 1.999 | clear|clear|clear |
| Vermont | Wide Ratings | PXL-L1|PXL-L4|PXL-L5 | 0.314 | 1.111 | clear|clear|clear |

## Overlap

- I'd Like To Know: overlap 0; unique mix count 6. Six unique mixes achieved.
- New Skin: overlap 0; unique mix count 6. Six unique mixes achieved.
- No Prize: overlap 0; unique mix count 6. Six unique mixes achieved.
- Vermont: overlap 0; unique mix count 6. Six unique mixes achieved.

## Status

No final selection has been made. No participant stimuli, manual approvals, frontend files, or final-stimulus outputs were generated or modified.
