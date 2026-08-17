# Final Statistical Dissertation Summary

## Dataset

The final empirical dataset contains 33 analysable participants: 17 in `group_01` and 16 in `group_02`. Each participant provided 30 ratings, giving 990 total rating rows. The data contain 198 participant x song x episode trials, with 5 candidate mixes in each trial. The study covers 4 songs, 3 listening episodes, and 20 unique song-mix stimuli. Sixteen human trials contained tied highest ratings. No participants were excluded, and the final cleaning gate reports the data as ready for statistical modelling.

The immutable raw source is `statistical-baseline/data/real/raw/listening_preference_responses_33_immutable.xlsx`, with raw SHA-256 `5bab388fbf564e0caf5c1ca8a5a722bf8d517e23c018e48375d076e75dba0bdd`. The model output manifests point to the N=33 cleaned dataset. On Windows, direct byte hashes of CSV/JSON files can differ because of CRLF line endings; the recorded model-manifest hashes match the LF-normalized canonical content.

## Full-Data Stimulus Model

The final stimulus model is:

`rating ~ episode + group + (1 | participant_id) + (1 | stimulus_id)`

This is a Bayesian multilevel Gaussian model in native 0-100 rating units. It includes fixed effects for listening episode and group, plus varying intercepts for participant and stimulus. It does not include episode x mix interactions, song random effects, or group random effects. The null/intercept-only model is used only for unconditional ICC comparison, not as the final scientific model.

Full-data stimulus MCMC used 4 chains, 1000 tuning draws, 1000 posterior draws, target_accept 0.95, deterministic seed 20260817, and nutpie via PyMC fallback. Diagnostics: 0 divergences; maximum R-hat 1.01; minimum bulk ESS 553 for the final model.

## ICC / Listener And Stimulus Variability

The dissertation-primary ICC is the conditional/final-model ICC from `final_model_icc_summary.csv`, calculated draw-by-draw from posterior variance components.

Final stimulus-model variance shares:

- Participant ICC: 0.145, HDI 0.075 to 0.219.
- Stimulus ICC: 0.173, HDI 0.082 to 0.279.
- Residual share: 0.682, HDI 0.572 to 0.780.

Plainly, ratings vary meaningfully by listener and by stimulus, but most variation remains trial-level/residual.

## Context Effects

Stimulus-model fixed effects:

- Intercept: 50.302, HDI 40.279 to 60.146.
- EDR-2 relative to EDR-1: +2.202, HDI -1.860 to 5.874.
- FM-1 relative to EDR-1: -6.675, HDI -10.641 to -2.893.
- group_02 relative to group_01: +5.995, HDI -7.258 to 18.819.

The clearest context result is that FM-1 ratings are lower than EDR-1. The EDR-2 effect is uncertain. The group effect is also uncertain and is confounded with assigned song set, so it should not be interpreted causally.

## Acoustic Feature Model

The primary feature model is:

`rating ~ episode + group + z_RMS + z_CF + z_SW + (1 | participant_id) + (1 | stimulus_id)`

The primary acoustic results are:

- z_RMS: +5.284 rating points per SD, HDI -0.073 to 10.389.
- z_CF: -6.265 rating points per SD, HDI -12.443 to -0.369.
- z_SW: -2.795 rating points per SD, HDI -8.416 to 2.679.

Crest factor is the clearest acoustic association, with higher crest factor associated with lower ratings. RMS trends positive but remains uncertain because its interval narrowly crosses zero. Stereo width is uncertain.

Feature-model ICC:

- Participant ICC: 0.156.
- Stimulus ICC: 0.128.
- Residual share: 0.716.

The stimulus ICC is lower than in the stimulus model (0.128 vs 0.173), supporting the cautious statement that measured acoustic descriptors account for some between-stimulus variation, although substantial unexplained variation remains.

## Sensitivity Analyses

The SI sensitivity model adds z_SI:

`rating ~ episode + group + z_RMS + z_CF + z_SW + z_SI + (1 | participant_id) + (1 | stimulus_id)`

z_SI has posterior mean -2.089, HDI -7.891 to 4.337, so it is uncertain and should remain sensitivity-only. PSIS-LOO does not show a meaningful difference between the primary and SI models: SI elpd_loo = -4686.425, primary elpd_loo = -4686.613, difference about 0.188 with SE about 18.6.

The bounded transformed-Beta sensitivity model avoids impossible ratings outside 0-100. It produced 0% posterior-predictive values outside the range. The primary Gaussian feature model produced about 12.1% outside-range posterior-predictive values, similar to the stimulus model at about 12.0%. The bounded model is a robustness check, not a replacement for the main native rating-point coefficients.

## Held-Out Prediction

The official held-out evaluation used leave-one-trial-out prediction. For each of 198 participant x song x episode trials, all 5 candidate rows were withheld together. The model retained that participant's other 25 ratings and predicted which withheld mix would be rated highest.

The official evaluation used explicit PyMC MCMC matching the Bambi full-data fixed/random-effects structures. It ran 2 models over 198 targets, giving 396 target x model fits. Settings were nutpie, 2 chains, 500 tune, 500 posterior draws, target_accept 0.95. Leakage audit and output validation passed.

Headline held-out metrics:

- Stimulus model: strict unique-winner accuracy 0.3022; tie-compatible accuracy 0.3434; top-2 hit rate 0.5960; Spearman 0.3555; NDCG 0.9167; MAE 22.9765; RMSE 27.5935.
- Acoustic model: strict unique-winner accuracy 0.3022; tie-compatible accuracy 0.3434; top-2 hit rate 0.6162; Spearman 0.3637; NDCG 0.9180; MAE 23.0010; RMSE 27.5912.

## Statistical Baseline Comparison

The two statistical baselines perform very similarly. The acoustic model has a small top-2 and ranking advantage, but strict and tie-compatible winner accuracies are identical, and RMSE is effectively unchanged. The bootstrap comparison does not justify a strong claim that one statistical model is clearly superior.

Full-data PSIS-LOO also shows no meaningful difference between the stimulus and primary acoustic models: stimulus elpd_loo = -4686.598 and primary feature elpd_loo = -4686.613.

## Limitations

The achieved N is 33, below the pre-data preferred target of about 50 from the sample-size simulation. This should be acknowledged as a limitation rather than re-analysed post hoc. The acoustic conclusions are based on only 20 unique stimulus-level feature profiles, so they should be treated as associations rather than causal claims. The Gaussian likelihood is interpretable but produces some impossible posterior-predictive ratings outside 0-100. The held-out MCMC evaluation completed, but many fold-level fits received conservative convergence warnings under a strict 2-chain, 500-draw diagnostic threshold.

## Held-Out Convergence Caveat

The held-out diagnostics report 384 `convergence_warning` and 12 `fit_ok` fits. The warning rule is strict: a fit is `fit_ok` only if divergences = 0, max R-hat <= 1.01, min bulk ESS >= 100, and min tail ESS >= 100. All 396 fits had 0 divergences. Counts were: R-hat > 1.01 in 384 fits, R-hat > 1.05 in 17 fits, R-hat > 1.10 in 1 fit, bulk ESS < 100 in 103 fits, bulk ESS < 50 in 13 fits, tail ESS < 100 in 14 fits, tail ESS < 50 in 0 fits.

Most warnings are mild and expected from many small 2-chain x 500-draw fold fits. Aggregate held-out predictions do not show obvious instability. A smaller subset of 31 categorical-design folds has R-hat > 1.05 or bulk ESS < 50 or tail ESS < 100. A targeted escalated rerun is optional for a cleaner diagnostic appendix, but the current official held-out results are usable with caveat.

Optional targeted command:

```bash
python statistical-baseline/scripts/run_real_heldout_mcmc.py --escalated --parallel-folds 4 --fold-id 5 --fold-id 6 --fold-id 13 --fold-id 17 --fold-id 20 --fold-id 24 --fold-id 25 --fold-id 37 --fold-id 63 --fold-id 74 --fold-id 75 --fold-id 82 --fold-id 99 --fold-id 102 --fold-id 103 --fold-id 104 --fold-id 106 --fold-id 111 --fold-id 114 --fold-id 115 --fold-id 126 --fold-id 134 --fold-id 137 --fold-id 158 --fold-id 168 --fold-id 170 --fold-id 178 --fold-id 179 --fold-id 183 --fold-id 194 --fold-id 196
```

## What Remains For LLM Evaluation

The statistical framework is ready as a baseline comparator. It establishes what can be predicted using conventional statistical structure and acoustic descriptors. The LLM-specific research question remains open until the real Phase 6 LLM predictions are run and compared with these statistical baselines.

## Final Framework Verdict

| Area | Status |
|---|---|
| Framework status | Complete |
| Data integrity | PASS |
| Full-data stimulus model | PASS |
| Feature model | PASS |
| ICC implementation | PASS |
| Sensitivity analyses | PASS |
| Held-out split/leakage | PASS |
| Held-out MCMC execution | PASS |
| Held-out convergence | PASS WITH CAVEAT |
| Ready for dissertation statistical Results | YES |
| Ready as statistical comparator for Phase 6 LLM evaluation | YES |

Overall, the statistical analysis shows that context, listener differences, stimulus differences, and some acoustic descriptors matter, but prediction remains modest. The strongest empirical result is the lower FM-1 context rating and the clearest acoustic association is negative crest factor. The statistical baselines are scientifically usable, but conclusions should stay cautious because N=33 is modest, acoustic profiles are limited to 20 stimuli, and held-out fold-level diagnostics are conservative rather than uniformly clean.
