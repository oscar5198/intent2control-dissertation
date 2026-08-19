# N=33 Primary Mixed-Effects Results

## Fixed Effects
| Model | Term | Estimate | 95% CrI |
| --- | --- | ---: | --- |
| stimulus_model | Intercept | 50.302 | [40.279, 60.146] |
| stimulus_model | episode[EDR-2] | 2.202 | [-1.860, 5.874] |
| stimulus_model | episode[FM-1] | -6.675 | [-10.641, -2.893] |
| stimulus_model | group[group_02] | 5.995 | [-7.258, 18.819] |
| primary_feature_model | Intercept | 44.800 | [34.622, 55.207] |
| primary_feature_model | episode[EDR-2] | 2.231 | [-1.798, 6.130] |
| primary_feature_model | episode[FM-1] | -6.641 | [-10.627, -2.677] |
| primary_feature_model | group[group_02] | 16.766 | [2.029, 32.145] |
| primary_feature_model | z_RMS | 5.284 | [-0.073, 10.389] |
| primary_feature_model | z_CF | -6.265 | [-12.443, -0.369] |
| primary_feature_model | z_SW | -2.795 | [-8.416, 2.679] |

## Variance Components
| Model | Component | Estimate | 95% CrI |
| --- | --- | ---: | --- |
| stimulus_model | 1|participant_id_sigma | 12.314 | [8.841, 15.921] |
| stimulus_model | 1|stimulus_id_sigma | 13.460 | [9.018, 18.434] |
| stimulus_model | sigma | 26.851 | [25.696, 28.035] |
| primary_feature_model | 1|participant_id_sigma | 12.477 | [8.797, 16.065] |
| primary_feature_model | 1|stimulus_id_sigma | 11.246 | [7.061, 16.099] |
| primary_feature_model | sigma | 26.866 | [25.772, 28.107] |

## ICC
| Model | Component | Estimate | 95% CrI |
| --- | --- | ---: | --- |
| stimulus_model | participant_ICC | 0.145 | [0.075, 0.219] |
| stimulus_model | stimulus_ICC | 0.173 | [0.082, 0.279] |
| stimulus_model | residual_share | 0.682 | [0.572, 0.780] |
| primary_feature_model | participant_ICC | 0.156 | [0.084, 0.239] |
| primary_feature_model | stimulus_ICC | 0.128 | [0.044, 0.218] |
| primary_feature_model | residual_share | 0.716 | [0.613, 0.813] |

## Convergence
- Participants: 33; observations: 990; chains: 4; posterior draws per chain: 1000.
- Stimulus model: divergences 0, max R-hat 1.010, min bulk ESS 418.0, min tail ESS 718.0.
- Feature model: divergences 0, max R-hat 1.010, min bulk ESS 969.0, min tail ESS 1264.0.
