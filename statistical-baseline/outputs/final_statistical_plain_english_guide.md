# Final Statistical Plain-English Guide

## 1. What Data We Had

The final empirical dataset contains 33 valid participants. There are 17 in `group_01` and 16 in `group_02`. Each participant rated 30 mixes: 2 songs x 3 listening contexts x 5 candidate mixes. That gives 990 rating rows.

The study has 4 songs, but each participant only heard the 2 songs assigned to their group. Within each song/context trial, the participant rated 5 candidate mixes and wrote one comparative comment. Across all participants, there are 198 participant x song x context trials. Sixteen of those trials had tied highest human ratings, meaning the participant gave the same top score to more than one mix.

## 2. What Cleaning Did

The raw Excel workbook was copied into `statistical-baseline/data/real/raw/listening_preference_responses_33_immutable.xlsx` and treated as immutable. The cleaner parsed the JSON fields submitted by the web study, expanded each participant submission into long-format rating rows, reconstructed which real stimulus was behind each randomised A-E label, attached acoustic features, and wrote audit tables.

No participants were excluded. There were no missing ratings, no invalid ratings outside 0-100, no duplicate submissions requiring removal, and no manual-review cases. Ties were preserved: when a participant gave two or more mixes the same highest rating, the output records all tied winners instead of forcing one arbitrary winner.

## 3. Why Mixed/Multilevel Models Were Needed

The 990 ratings are not 990 independent people. Each participant gave 30 ratings, and each stimulus was rated many times. A multilevel model accounts for that repeated structure. It lets the model learn that some listeners generally rate high or low, and some stimuli generally receive higher or lower ratings.

## 4. Fixed Effects

Fixed effects are the main average comparisons in the model. Here they include listening context (`episode`), participant group (`group`), and, in the acoustic model, acoustic predictors.

For example, the `episode[FM-1]` coefficient asks: after accounting for listener and stimulus differences, are ratings in the FM-1 context higher or lower than in the reference context EDR-1?

## 5. Random Or Varying Effects

`(1 | participant_id)` means each participant gets their own baseline tendency to rate higher or lower.

`(1 | stimulus_id)` means each mix/stimulus gets its own baseline tendency to be rated higher or lower.

These are called varying intercepts because the baseline rating level varies by participant and stimulus.

## 6. ICC

ICC means intraclass correlation. In this project it answers: how much of the remaining rating variation is due to stable listener differences, how much is due to stable stimulus differences, and how much is still residual/noisy variation?

The primary ICC is the conditional/final-model ICC from the final stimulus model, not the unconditional/null-model ICC. It is calculated draw-by-draw from posterior variance components:

- participant variance = participant SD squared
- stimulus variance = stimulus SD squared
- residual variance = residual SD squared

Final stimulus-model ICC results:

- participant ICC = 0.145, HDI 0.075 to 0.219
- stimulus ICC = 0.173, HDI 0.082 to 0.279
- residual share = 0.682, HDI 0.572 to 0.780

Plain English: about 15% of remaining variation is associated with stable listener differences, about 17% with stable stimulus differences, and about 68% remains trial-level/residual variation.

## 7. Posterior Mean And HDI

The posterior mean is the model's average estimate after combining the data and priors. The HDI is a credible interval: a range containing the most credible posterior values. If an interval crosses zero, the direction of the effect is uncertain in this dataset.

This is Bayesian language, not frequentist significance testing. The dissertation should say "posterior mean" and "credible interval/HDI", not "statistically significant" unless a separate frequentist test was actually used.

## 8. Convergence Diagnostics

R-hat checks whether MCMC chains agree with each other. Values near 1 are good. ESS estimates how much independent information is in the posterior draws. Divergences are more serious warnings that the sampler struggled with the geometry of the posterior.

The full-data stimulus and feature models had 0 divergences, R-hat at about 1.00-1.01, and adequate ESS. They are ready for dissertation reporting.

The held-out evaluation used many small 2-chain x 500-draw MCMC fits. It completed all 396 target-model fits, but 384 were labelled `convergence_warning` because the diagnostic rule is strict: fit_ok requires 0 divergences, max R-hat <= 1.01, bulk ESS >= 100, and tail ESS >= 100. There were 0 divergences. Most warnings are mild R-hat flags just above 1.01. A smaller subset of 31 categorical-design folds has R-hat above 1.05 or low ESS and could be escalated if a cleaner diagnostics appendix is desired.

## 9. What The Stimulus Model Found

Formula:

`rating ~ episode + group + (1 | participant_id) + (1 | stimulus_id)`

This predicts ratings from listening context and group, while accounting for listener and stimulus differences.

Main fixed effects:

- Intercept = 50.302: the reference-condition average rating, after model adjustment.
- EDR-2 vs EDR-1 = +2.202, HDI -1.860 to 5.874: small positive estimate, but uncertain.
- FM-1 vs EDR-1 = -6.675, HDI -10.641 to -2.893: ratings were lower in FM-1 than EDR-1.
- group_02 vs group_01 = +5.995, HDI -7.258 to 18.819: uncertain and confounded with assigned song set.

The group effect must not be interpreted causally, because groups heard different songs.

## 10. What The Acoustic Model Found

Primary formula:

`rating ~ episode + group + z_RMS + z_CF + z_SW + (1 | participant_id) + (1 | stimulus_id)`

RMS is related to overall signal energy/loudness. Crest factor describes peakiness: high crest factor means peaks stand out more relative to average level. Stereo width describes how spread out the mix is across the stereo field.

The predictors are z-scored so a coefficient means "rating-point change per one standard deviation increase" and the predictors are on comparable scales.

Primary acoustic estimates:

- z_RMS = +5.284, HDI -0.073 to 10.389: louder/more energetic mixes tended to be rated higher, but the interval just crosses zero.
- z_CF = -6.265, HDI -12.443 to -0.369: higher crest factor was the clearest negative association.
- z_SW = -2.795, HDI -8.416 to 2.679: negative estimate, but uncertain.

SI was sensitivity-only because it was not part of the primary pre-specified acoustic set. In the SI model, z_SI = -2.089, HDI -7.891 to 4.337, so its association is uncertain.

## 11. Bounded Sensitivity

The primary Gaussian models are useful because coefficients stay in rating points on the original 0-100 scale. That makes the results easy to explain.

The limitation is that a Gaussian distribution can predict impossible values below 0 or above 100. The primary feature model PPC estimated about 12.1% posterior-predictive ratings outside 0-100. The stimulus model was similar at about 12.0%. The observed data also contain real boundary ratings: 73 exact zeros and 71 exact hundreds.

The bounded transformed-Beta sensitivity model produced 0% simulated values outside 0-100. This shows the boundary issue can be handled, but its coefficients are on a transformed scale and should not replace the main native-rating-point Gaussian coefficients.

## 12. Held-Out Prediction

Leave-one-trial-out means: for each participant x song x context trial, all 5 candidate ratings for that trial were withheld. The model was trained on everything else, including the same participant's other 25 ratings. Then it predicted which of the 5 withheld mixes would be rated highest.

There were 198 target trials and 2 models, so 396 target x model fits. All used MCMC with explicit PyMC, nutpie, 2 chains, 500 tune, 500 posterior draws, and target_accept 0.95. Leakage checks passed.

## 13. How Good Is About 30% Winner Accuracy?

There are 5 candidate mixes per trial, so a naive random choice would often be thought of as 20%. However, the alternatives are not necessarily exchangeable: some mixes may be more generally preferred, ratings can tie, and the model also has information from other participants and the participant's remaining ratings. So ~30% strict winner accuracy is better described as modest predictive signal, not as a simple "50% better than chance" claim.

Held-out headline metrics:

- Stimulus model: strict accuracy 0.3022, tie-compatible accuracy 0.3434, top-2 hit rate 0.5960, RMSE 27.5935.
- Acoustic model: strict accuracy 0.3022, tie-compatible accuracy 0.3434, top-2 hit rate 0.6162, RMSE 27.5912.

## 14. How The Two Statistical Baselines Compare

The acoustic model does not clearly outperform the stimulus model. Strict accuracy and tie-compatible accuracy are identical. Top-2 hit rate is slightly higher for the acoustic model (+0.0202), and RMSE is practically identical (-0.0023 in feature-minus-stimulus direction).

The bootstrap comparison intervals mostly include small differences around zero. It is safest to say the two statistical baselines perform similarly, with at most a small ranking advantage for the acoustic model.

## 15. Justified Conclusions

- The dataset is structurally clean and analysable at N=33.
- Context matters: FM-1 ratings are lower than EDR-1 in both stimulus and feature models.
- Listener and stimulus differences both explain meaningful portions of rating variation.
- The acoustic descriptors account for some between-stimulus variation: stimulus ICC drops from 0.173 in the stimulus model to 0.128 in the primary feature model.
- Crest factor shows the clearest acoustic association, negative in direction.
- Held-out prediction is modest, and the two statistical baselines perform very similarly.

## 16. Conclusions Not Justified

- Do not claim group_02 is causally more positive than group_01; group is confounded with song set.
- Do not claim acoustic features cause preferences; this is observational association over only 20 unique stimulus profiles.
- Do not claim SI is a confirmed predictor; it was sensitivity-only and uncertain.
- Do not claim the statistical analysis answers the LLM-specific research question before real LLM inference is evaluated.
- Do not ignore held-out convergence warnings; report them as a caveat.

## 17. What Remains For LLM Analysis

The statistical analysis gives the empirical baseline: what can be explained by context, group/song assignment, participant/stimulus variation, and simple acoustic features. The LLM phase still needs to test whether LLM-based predictions match or improve on these statistical baselines. Until that is run, any claim about LLM performance remains pending.
