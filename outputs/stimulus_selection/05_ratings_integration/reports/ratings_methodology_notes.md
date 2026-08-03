# Ratings Methodology Notes

Brecht's prior Mix Evaluation Dataset ratings are used as an external second-stage stratification variable, after acoustic candidate pools have been generated without stereo imbalance in the diversity distance.

The prior ratings are context-free preference ratings from the existing dataset. They are not new study outcomes, not ground-truth quality labels, and not part of the acoustic distance. They are aggregated within song using `mix_id`, preserving unequal rating counts, session/evaluator/year metadata, and uncertainty estimates.

Phase 2B should use within-song descriptors, ranks, and uncertainty annotations to construct similar-rating and wide-rating comparisons. Cross-song raw mean comparisons should be avoided unless explicitly modelled.

Exact self-rating exclusion is not feasible from the current canonical metadata because no reliable participant-to-mixer identity mapping or explicit self-rating flag is present.
