# Rating Stratification Report

Phase 2B combines fixed corrected acoustic candidate pools with Phase 2A prior preference ratings to recommend supervisor-review triplets. Acoustic distances are read from `pairwise_distances_v2.csv` and are not recomputed or modified.

Objective weighting: 0.8 acoustic diversity and 0.2 rating stratification. Similar-rating triplets minimise rating spread within acoustically diverse combinations; wide-rating triplets maximise rating spread while retaining acoustic diversity. QC review/caution statuses are penalised lightly and reported, not automatically excluded.

Unrated candidate-pool mixes are documented in Phase 2A but excluded from rating-based recommendation sets because no mean preference is available.

## Recommendations

| Song | Condition | Mixes | Rating spread | Minimum acoustic distance | QC statuses |
| --- | --- | --- | ---: | ---: | --- |
| In The Meantime | Similar Ratings | QUT-B|DU-H|DU-I | 0.391 | 3.418 | clear|clear|clear |
| In The Meantime | Wide Ratings | DU-K|QUT-pro|DU-N | 0.448 | 2.586 | clear|clear|clear |
| Lead Me | Similar Ratings | DU-D|DU-E|QUT-F | 0.056 | 3.168 | clear|clear|clear |
| Lead Me | Wide Ratings | PXL-L1|PXL-L4|McG-pro2 | 0.216 | 2.923 | clear|clear|clear |
| Pouring Room | Similar Ratings | McG-R|McG-T|McG-X | 0.076 | 1.885 | clear|clear|clear |
| Pouring Room | Wide Ratings | McG-pro1|McG-U|McG-V | 0.282 | 1.695 | clear|clear|clear |
| Red To Blue | Similar Ratings | McG-B|McG-G|McG-F | 0.207 | 2.600 | review|clear|clear |
| Red To Blue | Wide Ratings | McG-C|McG-H|McG-pro1 | 0.228 | 1.948 | clear|clear|clear |

## Overlap

- In The Meantime: overlap 0; unique mix count 6. Six unique mixes achieved.
- Lead Me: overlap 0; unique mix count 6. Six unique mixes achieved.
- Pouring Room: overlap 0; unique mix count 6. Six unique mixes achieved.
- Red To Blue: overlap 0; unique mix count 6. Six unique mixes achieved.

## Status

No final selection has been made. No participant stimuli, manual approvals, frontend files, or final-stimulus outputs were generated or modified.
