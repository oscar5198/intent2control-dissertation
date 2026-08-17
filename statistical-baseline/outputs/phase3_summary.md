# Phase 3 Statistical Baseline Summary

This summary records the current final-design Phase 3 statistical baseline. The current design is the 5-mix, 3-episode, 20-stimulus design. Historical 3-mix, 5-context, 12-stimulus, interaction-model, and N=60 outputs are superseded and should not be used as the current dissertation result.

## Statistical Analysis Framework

The statistical baseline uses Bayesian multilevel regression implemented with Bambi/PyMC and ArviZ. The response variable is the continuous 0-100 contextual-suitability rating. Gaussian likelihoods are used for the synthetic baseline and planned real-data analysis so coefficients remain interpretable in rating-point units.

The final study structure is:

- 4 songs.
- 2 participant groups.
- 2 non-overlapping songs per group.
- 5 mixes per song.
- 20 unique song-mix stimuli.
- 3 listening contexts: `EDR-1`, `EDR-2`, and `FM-1`.
- 30 ratings per participant: 2 songs x 3 episodes x 5 mixes.

Group A/B is treated as a fixed factor because there are only two groups. Participant and stimulus identities are treated with partial pooling. The primary models are additive: no episode x stimulus, episode x feature, episode x group, random-slope, song-random-effect, or group-random-effect terms are part of the final primary specification.

## Stimulus-Based Model

Final stimulus model:

```text
rating ~ episode + group + (1 | participant_id) + (1 | stimulus_id)
```

This model estimates population-level episode and group effects while using participant random intercepts for repeated listener ratings and stimulus random intercepts for residual differences among the 20 song-mix stimuli. It captures unexplained stimulus identity variation but does not explain that variation using acoustic predictors.

The current final-design stimulus-model outputs are under:

```text
statistical-baseline/outputs/stimulus_model/
```

The completed stimulus model used 4 chains, 1,000 tuning draws, 1,000 posterior draws, `target_accept = 0.95`, and nutpie. It produced draw-by-draw posterior preferred-mix probabilities for exactly 5 candidate mixes within each `song_id x episode`.

## Feature-Based Model

Primary feature model:

```text
rating ~ episode + group + z_RMS + z_CF + z_SW + (1 | participant_id) + (1 | stimulus_id)
```

Sensitivity feature model:

```text
rating ~ episode + group + z_RMS + z_CF + z_SW + z_SI + (1 | participant_id) + (1 | stimulus_id)
```

The feature-based baseline uses the final Phase 3B.3 20-stimulus acoustic feature table. `z_RMS`, `z_CF`, and `z_SW` are retained as the primary acoustic predictors. Because the features are standardised, each acoustic coefficient represents the expected rating-point change associated with a one-standard-deviation increase in that descriptor, conditional on the other predictors and random effects.

`z_SI` remains sensitivity-only because it was retained as QC-related stereo-imbalance metadata. Bark-spectrum predictors are excluded from the primary model because the final 20-stimulus evidence did not support a stable primary Bark representation. The SI sensitivity model did not provide a meaningful improvement in the synthetic validation: PSIS-LOO was stable with 0 Pareto-k values above 0.7, and the primary model had slightly higher elpd_loo (`-4362.066`) than the SI model (`-4362.391`).

The completed primary feature model had 0 divergences, max R-hat 1.02, minimum bulk ESS 391, and minimum tail ESS 641. The feature-model posterior winner validation passed: each song-context contained exactly 5 candidates, posterior winning probabilities summed to 1 within each song-context, and exactly one final predicted winner was identified.

## ICC and Uncertainty

The final analysis calculates posterior draw-by-draw:

- participant ICC;
- stimulus ICC;
- residual variance share.

Participant ICC quantifies the proportion of unexplained rating variance attributable to stable between-listener differences after accounting for the fixed effects and other model variance components. Stimulus ICC quantifies residual between-stimulus variability after partial pooling. Residual share quantifies remaining observation-level variability.

Real-data reporting will include:

- posterior mean or median;
- posterior SD;
- 94% HDI;
- MCSE;
- R-hat;
- bulk ESS;
- tail ESS;
- divergence count.

Posterior SD and MCSE will be kept conceptually separate: posterior SD describes posterior uncertainty in a parameter, while MCSE describes Monte Carlo error in the numerical estimate of that posterior quantity.

## Simulation-Based Design Analysis

The final Phase 3C design analysis used:

- sample sizes: 20, 30, 40, 50, 60, and 80 analysable participants;
- scenarios: moderate/expected, smaller-effects/harder, and higher-noise;
- 10 replications per sample-size x scenario condition;
- 180 repeated Bayesian fits;
- reduced repeated-fit configuration: 2 chains, 400 tuning draws, 400 posterior draws, `target_accept = 0.95`, nutpie;
- 0 failed fits;
- 0 divergences across all repeated simulation fits.

The requested 20 replications per condition were reduced to 10 as an explicit computational fallback. The final simulation outputs therefore report Monte Carlo SD/SE and should not be read as exact deterministic quantities.

Operational success used zero divergences, max R-hat <= 1.05, and minimum bulk/tail ESS >= 50. Across the 180 shortened-chain simulation fits, operational success was 70.6%. Strict convergence was deliberately harder for the short chains, using zero divergences, max R-hat <= 1.01, and minimum bulk/tail ESS >= 100; the strict-convergence rate was 2.2%.

The repeated-fit runtime distribution was:

- median: 8.63 seconds;
- 90th percentile: 10.96 seconds;
- maximum: 26.40 seconds.

## Final Sample-Size Justification

Final recommended analysable sample size:

```text
N = 50
```

Recruitment should exceed 50 where practical to protect against incomplete responses, exclusions, or unusable data. No fixed attrition rate is assumed.

Approximately 40 analysable participants would still be usable, but interpretation would need to be more cautious and uncertainty-led. In the final 40/50/60 comparison, N=50 gave the best balance of practical runtime, expected-rating recovery, preferred-mix recovery, and uncertainty reduction across scenarios. Gains beyond 50 showed diminishing returns, with the final diminishing-return point recorded as `50->60`.

Full-quality N=50 confirmation fit:

- scenario: moderate/expected;
- rows: 1,500;
- 4 chains;
- 1,000 tuning draws;
- 1,000 posterior draws;
- `target_accept = 0.95`;
- nutpie sampler;
- runtime: 18.485 seconds;
- divergences: 0;
- max R-hat: 1.02;
- minimum bulk ESS: 372;
- minimum tail ESS: 641;
- cell-mean RMSE: 1.196;
- participant ICC truth inside posterior HDI: yes;
- stimulus ICC truth inside posterior HDI: yes;
- posterior predictive outside-range rate: 0.00960.

## Limitations

The Phase 3 simulation and synthetic-validation results have important limits:

- only 10 replications per condition were completed;
- repeated simulation fits used shortened MCMC chains;
- strict convergence was low under the deliberately reduced chains;
- all simulation scenarios are hypothetical design assumptions, not empirical listener behaviour;
- there are only 20 unique acoustic-feature stimuli, even though repeated ratings produce more rows;
- group is structurally linked to song assignment and should not be interpreted as a pure causal participant-group effect;
- primary models are additive and do not estimate context-specific acoustic effects.

These limitations should be reported rather than hidden.

## Planned Real-Data Analysis

When real participant ratings are available, the planned primary analyses are:

1. Fit the final stimulus-based model.
2. Fit the final primary feature-based model.
3. Fit the SI sensitivity feature model.
4. Recompute convergence diagnostics, posterior predictive checks, ICCs, posterior expected ratings, and draw-by-draw posterior preferred-mix probabilities.
5. Interpret dissertation conclusions from posterior estimates and uncertainty, not from coefficient signs alone.

The real-data analysis should preserve the additive primary specification unless later evidence justifies explicitly labelled exploratory sensitivity analyses.

## Superseded Results Audit

The current final-design source of truth is:

- `statistical-baseline/notebooks/_01_synthetic_data_generation.ipynb`
- `statistical-baseline/notebooks/_02_categorical_stimulus_model.ipynb`
- `statistical-baseline/notebooks/_03_mst_feature_exploration.ipynb`
- `statistical-baseline/notebooks/_04_feature_based_model.ipynb`
- `statistical-baseline/notebooks/_05_sample_size_simulation.ipynb`
- `statistical-baseline/outputs/stimulus_model/`
- `statistical-baseline/outputs/feature_exploration/`
- `statistical-baseline/outputs/feature_model/`
- `statistical-baseline/outputs/sample_size_simulation/`

Searches of `statistical-baseline/` found obsolete or historical references in the following non-archive paths. These are intentionally retained if they are historical output artefacts; they should not be cited as current final-design results:

- `statistical-baseline/outputs/categorical_model/`: superseded old categorical output directory, including an obsolete episode x stimulus formula in `execution_summary.csv` and related posterior-summary tables.
- `statistical-baseline/outputs/feature_based_model/`: superseded old feature-model output directory, including old 12-stimulus and interaction/sensitivity assumptions.
- `statistical-baseline/outputs/mst_feature_exploration/`: superseded old feature-exploration output directory, including 12-stimulus references.
- `statistical-baseline/data/synthetic/synthetic_*`: legacy synthetic files from the older design.
- `statistical-baseline/outputs/phase3_summary.md`: previously contained obsolete 3-mix, 360-fit, and N=60 statements; this file has now been replaced with the final-design summary.
- `statistical-baseline/README.md`: previously described episode x stimulus outputs as current; it has now been updated to distinguish current final-design outputs from superseded historical output directories.

Remaining references to N=60 in current final-design outputs are not obsolete when they appear as one tested sample size or as the `50->60` diminishing-return transition. The current final recommendation is N=50.

## Phase Status

- Phase 3A - Complete
- Phase 3B.1 - Complete
- Phase 3B.2 - Complete
- Phase 3B.3 - Complete
- Phase 3B.4 - Complete
- Phase 3C - Complete
- Phase 3D - Complete
- Phase 3 overall - Complete
