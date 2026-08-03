# Ratings Integration Report

Canonical source: `C:\Users\oscar\OneDrive\Public share - Mix Eval Dataset\mix_evaluation_relationship_tables\data\evaluations.csv`.
Schema: `C:\Users\oscar\OneDrive\Public share - Mix Eval Dataset\mix_evaluation_relationship_tables\SCHEMA.md`.
Rating column: `preference_score_0_1`; observed scale 0 to 1.
Rows: 5473; participants: 181; songs: 20; mixes: 205; sessions: 230; experiments: 10.

## Coverage By Song

| Song | Retained | Rated | Unrated | Pool | Rated Pool | Rating Rows | Count Range | Institutions | Years |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| I'd Like To Know | 7 | 7 | 0 | 7 | 7 | 210 | 30-30 | PXL|QM|SMC | 2015 |
| New Skin | 7 | 7 | 0 | 7 | 7 | 371 | 53-53 | DU|QM|SMC | 2015 |
| No Prize | 9 | 9 | 0 | 9 | 9 | 342 | 38-38 | McG|QM|SMC | 2013|2015 |
| Vermont | 7 | 7 | 0 | 7 | 7 | 171 | 13-29 | PXL|QM|SMC | 2015 |

## Unrated Mixes


## Aggregation Method

Ratings were aggregated per retained mix using the canonical `mix_id` join key. For rated mixes, the table reports mean, median, standard deviation, variance, standard error, quartiles, IQR, min, max, range, and a 95% Student-t confidence interval where n > 1. Confidence intervals are not fabricated for unrated or single-rating cases.

## Self-Rating Inspection

Exact producer/self-ratings could not be identified from the available canonical metadata. The schema and tables expose participant/session/evaluator identifiers and mix/institution codes, but no explicit participant-to-mixer identity mapping or creator/evaluator flag. Institution equality alone was not treated as reliable self-rating evidence. Therefore no self-excluded summary was produced.

## Heterogeneity And Use

Ratings are on a common 0-1 scale, but they were collected across different sessions, evaluator institutions, experiments, years, and participant groups. The safest Phase 2B use is within-song stratification. Raw cross-song mean comparisons are not recommended.

## Warnings

Low-count/unrated/narrow-coverage warning rows: 0.

## Readiness

Phase 2A is ready for Phase 2B rating stratification. No acoustic distances were modified and no final selections were made.
