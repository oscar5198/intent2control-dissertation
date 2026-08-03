# LLM Evaluation Protocol

Project: Can Large Language Models Predict Listener-Preferred Music Mix Balance from Semantic Listening Contexts?

Status: pre-registration-style protocol for the planned MSc dissertation experiment. Human listening responses and LLM predictions have not yet been collected.

## 1. Research Objective

The LLM evaluation tests whether text-based foundation models can predict which of three alternative music mixes human listeners will judge most suitable for a semantic listening context. The model receives the same listening vignette concept as the human participant and an anonymised, text-only description of the three candidate mix versions. It must predict the human-preferred alternative before seeing any human responses.

The primary scientific question is cross-family generalisation: whether strong contemporary LLM families show above-chance agreement with human-derived preferences, and whether their predictions improve on or differ from the statistical baseline trained only on human response data.

## 2. Candidate Model Families

The primary evaluation should include approximately three strong model families/providers:

1. OpenAI GPT-family model: included as a widely used proprietary frontier language-model family with strong structured-output support.
2. Anthropic Claude-family model: included as an independently developed proprietary frontier model family, useful for testing whether performance generalises beyond one provider.
3. Google Gemini-family model: included as a third proprietary frontier model family with a distinct training and deployment ecosystem.

An open-weight model may be added as a secondary sensitivity analysis if time and compute allow. A suitable candidate would be a current Llama-family or comparable open-weight instruction model that can be run reproducibly with fixed weights and logged inference settings.

Exact model identifiers, API versions, provider endpoints and access dates must be frozen immediately before evaluation. The dissertation should not claim final exact commercial versions until those identifiers have been verified from provider documentation or API metadata at the time of the experiment.

## 3. Final-Model Freezing Procedure

Before any final human outcomes are inspected for LLM comparison:

1. Record the chosen provider, model family, exact model identifier and endpoint.
2. Record the date and time the identifier was verified.
3. Record API parameters and structured-output settings.
4. Save the prompt template and descriptor-generation script/version.
5. Save a manifest linking each model call to the prompt, descriptor values, permutation and raw response.

If a provider aliases a model name to a changing backend, the accessible model metadata and date accessed must be logged. The limitation should be reported rather than described as perfectly deterministic.

## 4. Input Representation

Each LLM trial contains:

1. The semantic listening vignette shown to the human listener.
2. Three anonymised alternatives labelled Version A, Version B and Version C.
3. A neutral glossary for the scalar descriptors.
4. Within-song standardised scalar descriptor values for each version:
   - z_RMS
   - z_CF
   - z_SW
   - z_SI

The descriptors are supplied as relative/standardised values within the same song so that the model compares the three versions without seeing source identity, filenames, engineer identity or selection roles. Values should be rounded consistently, for example to two decimal places, after the final descriptor table has been generated.

The model must not receive:

- human ratings
- human preferred alternatives
- original mix identity or source engineer identity
- representative/contrast labels
- selection rationale
- filenames or internal IDs that reveal provenance
- statistical-baseline predictions

## 5. Descriptor Definitions

The prompt glossary should use concise neutral wording:

- z_RMS: relative signal energy/loudness proxy after standardisation within the song.
- z_CF: relative crest factor, describing the peak-to-RMS relationship and therefore a proxy for peakiness or dynamic profile.
- z_SW: relative stereo width, describing side energy relative to total stereo energy.
- z_SI: relative stereo imbalance, describing left-right energy asymmetry.

The 24-band mid/side Bark-spectrum representation used during objective feature extraction and stimulus selection is excluded from the primary text-LLM representation. It is high-dimensional, difficult to express neutrally in natural language, and could encourage unstable prompt interpretations unrelated to the human task. A secondary sensitivity analysis may provide reduced Bark/PCA descriptors if the primary evaluation is complete and the transformation is frozen before human-outcome comparison.

## 6. Prompt Template

The prompt should be zero-shot and fixed before evaluation:

```text
You are predicting listener preferences in a music-mix evaluation study.

Task:
Given a listening situation and three alternative mixes of the same song, predict which version human listeners are most likely to rate as most suitable for that situation.

Important:
- You do not know the true human ratings.
- Use only the vignette and anonymised descriptor values below.
- The descriptors are relative within this song; 0 is near the song-specific centre, positive values are higher than typical for this song, and negative values are lower than typical for this song.
- Do not infer anything from the labels A, B or C.

Descriptor glossary:
- z_RMS: relative signal energy/loudness proxy.
- z_CF: relative crest factor / peak-to-RMS profile.
- z_SW: relative stereo width.
- z_SI: relative stereo imbalance.

Listening situation:
{vignette}

Candidate versions:
Version A: z_RMS={A_z_RMS}, z_CF={A_z_CF}, z_SW={A_z_SW}, z_SI={A_z_SI}
Version B: z_RMS={B_z_RMS}, z_CF={B_z_CF}, z_SW={B_z_SW}, z_SI={B_z_SI}
Version C: z_RMS={C_z_RMS}, z_CF={C_z_CF}, z_SW={C_z_SW}, z_SI={C_z_SI}

Return only valid JSON using this schema:
{
  "preferred_label": "A|B|C",
  "ratings": {
    "A": 0-100,
    "B": 0-100,
    "C": 0-100
  },
  "confidence": 0-1,
  "brief_rationale": "one sentence"
}
```

The rationale is logged for qualitative inspection only. It is not the primary evaluation target.

## 7. JSON Schema

Required fields:

- `preferred_label`: string, one of `A`, `B`, `C`.
- `ratings`: object with numeric `A`, `B`, `C` values in the inclusive range 0-100.
- `confidence`: numeric value in the inclusive range 0-1.
- `brief_rationale`: string, one sentence where possible.

The preferred label should normally correspond to the highest predicted rating. If a model returns inconsistent values, the parser should retain both the declared label and the numeric ratings, flag the inconsistency, and use the declared label for the primary metric unless pre-registered otherwise.

## 8. Label Permutations

Each underlying three-mix trial should be queried under repeated A/B/C label permutations. The physical candidate alternatives remain identical while their visible labels change. This estimates positional bias and avoids treating an arbitrary presentation order as meaningful.

Recommended primary setting:

- Use all six A/B/C permutations per model per vignette/trial if cost permits.
- If cost is constrained, use three balanced permutations selected before evaluation.
- Aggregate predictions across permutations by majority vote over the underlying mix identity.

If the majority vote ties, use the mean predicted rating across permutations to break the tie. If the tie remains, record the model prediction as tied/invalid for strict accuracy and score fractional accuracy of 1/k among tied alternatives in a sensitivity analysis.

## 9. Inference Settings

Primary evaluation should minimise unnecessary stochasticity:

- temperature: 0 or the lowest deterministic/near-deterministic setting supported
- top-p: 1 or provider default when temperature is fixed
- seed: fixed when supported
- maximum output tokens: sufficient for the JSON response, for example 200-300 tokens
- structured-output mode: enabled where supported
- retries: limited and logged

Commercial APIs should not be described as perfectly deterministic unless the provider explicitly guarantees this. If repeated calls at the same settings vary, the variation must be reported.

## 10. Invalid-Output Handling

An output is invalid if:

- it is not parseable JSON after permitted provider-level structured-output handling;
- `preferred_label` is not one of `A`, `B`, `C`;
- required fields are missing;
- ratings cannot be interpreted as numeric values in 0-100;
- confidence cannot be interpreted as a numeric value in 0-1.

Recommended handling:

1. Store the raw invalid response.
2. Retry once with the same prompt and settings, adding only a brief format reminder if pre-registered.
3. If still invalid, mark the trial as invalid for strict accuracy.
4. Report invalid-output rate by model.

## 11. Human Target Definition

The human task records participant-level contextual suitability ratings from 0-100 for each candidate mix. These ratings are the primary empirical data.

For LLM evaluation, the group-level human target for each vignette/song trial is derived from the expected or mean human contextual suitability rating for each candidate mix. The human-preferred alternative is the candidate with the highest group-level expected rating.

The protocol must distinguish:

- participant-level rating: one listener's 0-100 score;
- group-level/context-level expected rating: aggregate or model-estimated suitability for a candidate in a context;
- derived preferred alternative: the highest-rated candidate for comparison with LLM predictions.

## 12. Statistical Baseline

The LLMs should be compared against the same held-out prediction target used for the statistical baseline. The statistical baseline should be trained on appropriate human training data only and evaluated on held-out target units. LLM predictions must be generated without access to the held-out human responses or statistical-model predictions.

The feature-based baseline uses standardised objective descriptors z_RMS, z_CF, z_SW and z_SI, listening context factor `episode`, and pre-specified interaction terms where supported by the completed baseline analysis.

## 13. Chance Baseline

The chance reference for the primary preference task is 1/3 because each trial contains three candidate alternatives. If ties are present in human targets, report how they were treated and include a sensitivity analysis with fractional credit.

## 14. Primary Metric

Primary metric:

- agreement/accuracy between the LLM-predicted preferred alternative and the human-preferred alternative.

Predictions should be evaluated after mapping visible labels A/B/C back to the underlying anonymised candidate identities for each permutation.

## 15. Secondary Metrics

Secondary metrics may include:

- rank correlation between LLM-predicted ratings and human group-level ratings;
- mean absolute error or RMSE between LLM ratings and human group-level ratings, if rating calibration is defensible;
- context-specific accuracy;
- song-specific accuracy;
- label-order sensitivity;
- invalid-output rate;
- confidence calibration or probabilistic score if model confidence is treated quantitatively.

The brief rationale should be used only for exploratory qualitative interpretation.

## 16. Uncertainty Analysis

Report uncertainty for the primary accuracy estimate using confidence intervals appropriate to the number and dependency structure of evaluated trials. Recommended options include:

- exact or Wilson binomial intervals when each evaluated target is treated independently;
- bootstrap confidence intervals resampling at the song/context unit when repeated permutations are aggregated;
- Bayesian credible intervals for a binomial accuracy model.

Compare LLM accuracy with chance using a pre-specified binomial or permutation test. Compare LLM and statistical baseline performance using paired tests over the same held-out trials, such as an exact paired test for preference correctness or a bootstrap over paired accuracy differences.

## 17. Leakage Controls

Leakage controls:

- Generate LLM prompts before exposing the model to human responses.
- Do not include source mix names, filenames, engineer labels or selection roles.
- Do not include statistical-baseline predictions.
- Do not tune prompts on final human outcomes.
- Freeze descriptor rounding and prompt format before evaluation.
- Keep prompt variants limited and pre-specified.
- Store raw responses and parsed outputs separately from human-rating files until comparison.

## 18. Reproducibility Logging

For every model call, log:

- project version or commit hash;
- model family and exact model identifier;
- provider and endpoint;
- access timestamp and date;
- prompt template version;
- full rendered prompt;
- descriptor values supplied;
- vignette ID;
- song/stimulus unit;
- label permutation;
- decoding parameters;
- random seed where supported;
- raw response;
- parsed JSON;
- parser warnings;
- retry count;
- final validity flag.

No LLM experiment should be executed until this protocol and the human target definition have been approved.
