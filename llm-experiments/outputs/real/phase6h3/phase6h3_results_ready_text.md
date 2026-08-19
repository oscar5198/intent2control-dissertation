# Phase 6H.3 Results-Ready Text

## A. Listening Study and Preference Variation

The final listening-study dataset contained 33 analysable participants (17 in group_01 and 16 in group_02), 198 participant-song-episode trials, and 990 individual mix ratings. Each trial presented five randomized candidate mixes, with A-E labels reconstructed from the frozen candidate mappings. All expected trial-level comments were present, and no post-freeze additional responses were detected. This dataset therefore provides the empirical basis for both preference-variation modelling and held-out prediction.

## B. Mixed-Effects Empirical Model

The mixed-effects analysis used two N=33 models: a stimulus/context model and a primary acoustic-feature model. Both included participant and stimulus random intercepts and converged satisfactorily, with four chains, 1,000 posterior draws per chain, zero divergences, and maximum R-hat of 1.01. In the primary feature model, FM-1 was rated lower than EDR-1 (estimate -6.641, 95% CrI [-10.627, -2.677]), while group_02 was higher than group_01 (16.766, [2.029, 32.145]). Crest factor was negatively associated with ratings (-6.265, [-12.443, -0.369]); RMS was positive but crossed zero, and spectral width was negative but also crossed zero. Participant and stimulus ICCs remained non-trivial, supporting the claim that listener and stimulus differences shape mix preference.

## C. Held-Out Mix Preference Prediction

Held-out prediction used the frozen 198-trial target set and the Phase 6H.1 set-based Top-1 tie policy. Without participant history, LLM Top-1 accuracy ranged from 20.7% to 24.7%, close to the 20% chance reference. With participant history, GPT-5.5 reached 34.3% Top-1 accuracy and Claude Sonnet 5 reached 35.9%; both were above chance after BH adjustment. Llama 3.1 70B and Centaur improved only slightly with history. Mean Spearman correlations followed the same pattern, with the largest LLM ranking gains for GPT-5.5 and Claude Sonnet 5.

## D. Effect of Participant History

Participant history had model-dependent value. GPT-5.5 improved by 11.6 percentage points in Top-1 accuracy, helping 48 examples and hurting 25, while Claude Sonnet 5 improved by 15.2 percentage points, helping 52 and hurting 22. These paired changes were supported by exact McNemar tests. Llama 3.1 70B and Centaur showed much smaller Top-1 gains of 1.0 and 1.5 percentage points, respectively. For models with numeric ratings, history also reduced MAE, most strongly for GPT-5.5.

## E. Comparison with the Mixed-Effects Predictive Model

The matched mixed-effects predictive baseline achieved 34.3% Top-1 accuracy, a mean Spearman correlation of 0.347, MAE of 23.00, and RMSE of 27.59. Personalised GPT-5.5 matched the mixed-effects Top-1 point estimate, and personalised Claude Sonnet 5 was numerically higher by 1.5 percentage points, but neither difference was detectable in paired Top-1 testing. The mixed-effects model remained the strongest ranking model, and it had lower RMSE than GPT-5.5 despite GPT-5.5 having a slightly lower MAE.

