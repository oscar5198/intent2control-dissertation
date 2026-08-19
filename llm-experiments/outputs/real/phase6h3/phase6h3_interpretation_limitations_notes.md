# Phase 6H.3 Interpretation and Limitations Notes

- Treat the mixed-effects models as the central empirical analysis and the LLMs as held-out predictive probes, not as an overall model leaderboard.
- Describe Top-1 accuracy as set-based preferred-mix credit under the frozen tie policy, because tied observed winners were retained rather than discarded.
- Emphasise absolute performance as modest: even the strongest methods select the observed top mix on roughly one third of held-out trials.
- Avoid claiming that participant history universally improves LLM prediction; the improvement is substantial for GPT-5.5 and Claude Sonnet 5, but small for Llama 3.1 70B and Centaur.
- Report Centaur MAE/RMSE as not applicable because its outputs are native likelihood scores, not calibrated 0-100 ratings.
- State that N=33 is the final usable dataset for this dissertation, while avoiding claims that it is conventionally powered for all effects.
- Keep causal language out of the Results chapter; phrase model coefficients as associations with ratings.
