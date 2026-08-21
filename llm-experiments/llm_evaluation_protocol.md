# LLM Evaluation Protocol

Project: Intent2Control dissertation - Phase 6 LLM Modeling

Status: Phase 6A protocol freeze for the planned LLM evaluation. These decisions were established before final participant-result analysis. Human participant data are still being collected. No real-data LLM evaluation has been run. This is an internal protocol freeze, not a claim of external preregistration.

## 1. Purpose and Scope

This document freezes the methodological design for evaluating whether LLMs can predict an individual listener's preferred music mix on a held-out trial. It is intended to reduce researcher degrees of freedom before inspecting final human listening-study outcomes.

This protocol covers only the LLM evaluation design. It does not train models, query LLMs, analyse participant results, modify the dissertation text, or modify the statistical-modeling models.

The active study design is:

- four songs total;
- two participant song groups;
- two songs experienced by each participant;
- three fixed listening episodes/contexts;
- six experimental trials per participant;
- five alternative mixes per trial;
- continuous human suitability/preference ratings from 0 to 100;
- one comparative free-text preference comment per trial;
- anonymous presentation labels A-E within each trial.

The listening episodes are fixed experimental context conditions. They are not treated as evidence that the study tests generalisation across arbitrary natural-language contexts.

Generic mix-quality framings are superseded by this participant-level
held-out-trial protocol.

## 2. Protocol Freeze

The following Phase 6A.4 decisions are frozen before final participant-result analysis:

- primary held-out evaluation unit: leave-one-trial-out participant-trial prediction;
- principal information conditions: non-history and personalised-history;
- primary metric: preferred-mix top-1 accuracy against the observed highest-rated A-E label/set;
- secondary metrics: MAE/RMSE for predicted ratings and tie-aware Spearman rank correlation for rankings;
- human maximum-rating ties: all tied maximum labels form the acceptable ground-truth set;
- predicted-output consistency: predicted ratings are the canonical scored output;
- structured output: strict JSON with preferred label, five ratings, and complete A-E ranking;
- invalid-output handling: one format-repair retry, then invalid/missing;
- primary inference principle: fixed low-variance settings where supported;
- primary acoustic descriptors: `z_RMS`, `z_CF`, and `z_SW`;
- sensitivity acoustic descriptor: `z_SI` only as a secondary/sensitivity descriptor.

The final implementation freezes prompt wording, schemas, model registry,
inference configuration, rendered prompts, and retained predictions under
`llm-experiments/outputs/final/`. This protocol is retained as methodological
evidence for the evaluation design.

## 3. Primary Prediction Task

The primary LLM task is personalised held-out-trial prediction.

For participant `p`, one completed eligible experimental trial `t` is treated as the target. The LLM receives permitted target-trial information and, depending on condition, permitted evidence from `p`'s other completed eligible trials. The model must predict:

> Which anonymous candidate mix A-E will receive the highest human rating from this participant on the held-out target trial?

The target-trial human outcomes must not be shown to the model. Acoustic characteristics are predictor/input information, not ground-truth labels. The experimental target is the participant's human preference among the five candidate mixes in the specified fixed listening context, operationalised from the 0-100 ratings.

## 4. Held-Out Evaluation Unit

The primary evaluation scheme is leave-one-trial-out at the participant-trial level.

For each participant with completed eligible data, each of their six experimental trials is treated once as the held-out target. The remaining completed eligible trials from the same participant provide the available history in the personalised-history condition. This produces up to six target predictions per participant.

This scheme is frozen because it:

- uses all available participant-trial targets without arbitrary target selection;
- keeps each prediction genuinely held out;
- provides listener-specific evidence from other trials;
- is data efficient for the expected study sample size.

The resulting predictions are not statistically independent. Multiple target predictions can come from the same participant, the same song, and the same fixed contexts. Uncertainty estimates and inferential comparisons must account for this repeated-measures structure; participant-trial predictions must not be treated as independent Bernoulli observations.

An eligible target trial must contain the five candidate labels A-E, valid `stimulus_id`/mix mapping, valid 0-100 ratings for all five candidates, and the trial-level comparative comment expected by the study protocol. Incomplete or invalid target trials are excluded from the primary eligible-target set and reported.

## 5. Participant-History Construction

For target trial `t`, participant history must be constructed after selecting `t` and must exclude `t` completely.

In the personalised-history condition, history consists of the same participant's other completed eligible trials only. Each prior trial is preserved as a separate observation. The prompt-generation pipeline must not collapse all trials into a participant aggregate that could accidentally include the target.

Each included history trial should contain:

- prior trial identifier;
- prior context/episode;
- prior song/excerpt label as permitted for modelling;
- prior A-E candidate descriptors sufficient to interpret the prior ratings;
- prior A-E human ratings;
- prior comparative comment;
- the prior trial-specific A-E to stimulus/mix mapping as needed internally for prompt construction and evaluation auditing.

The participant-facing historical evidence shown to the LLM should remain anonymised and should avoid unnecessary original mix names, filenames, source engineers, or stimulus-selection roles.

History trials are ordered deterministically by original study trial order, using `trial_index` or the exported trial chronology. They must not be sorted by rating, preference strength, similarity to the target, model convenience, or any value derived from the target outcome.

If a participant has fewer than five completed eligible non-target trials, the pipeline must use only the available completed eligible history trials and log the reduced history count. It must not fabricate missing ratings, comments, or trials. A target with no available eligible history may remain eligible for the non-history condition but should be flagged for the personalised-history condition.

## 6. Information Conditions

The primary experiment has exactly two principal information conditions.

### Condition 1: Non-History

The model receives target-trial information only:

- target listening context;
- five anonymous candidates A-E;
- permitted acoustic descriptors;
- permitted participant metadata collected independently of trial outcomes.

The model receives no ratings, rankings, or comments from any other trial by the participant.

### Condition 2: Personalised History

The model receives exactly the same target information as the non-history condition plus permitted evidence from that participant's other completed eligible trials, constructed as described above.

The purpose of this contrast is to test whether prior listener-specific behavioural evidence improves prediction relative to target context, acoustic features, and permitted participant metadata alone.

Additional narrower information ablations may be run only as secondary
exploratory analyses. They must not replace the two principal conditions or be
presented as the primary confirmatory comparison.

## 7. Allowed Inputs

Allowed target-trial input information:

- fixed listening episode/context text or identifier;
- anonymous A-E candidate labels as presented in the target trial;
- primary acoustic descriptors `z_RMS`, `z_CF`, and `z_SW` for each candidate;
- participant metadata fields listed in this protocol, if available and included consistently across conditions.

Allowed personalised-history input information:

- other completed eligible trials from the same participant;
- prior contexts;
- prior A-E ratings;
- prior comparative comments;
- acoustic descriptors and anonymous candidate information needed to interpret those prior preferences.

Disallowed prompt information includes unnecessary original mix names, filenames, source engineer labels, internal selection roles, historical stimulus-selection ratings, and statistical-modeling predictions unless a later approved implementation note documents a non-leaking reason. The default is not to show these identifiers to the LLM.

## 8. Acoustic Descriptors and Participant Metadata

The primary acoustic descriptor set is frozen as:

- `z_RMS`: standardised RMS/energy proxy;
- `z_CF`: standardised crest-factor/dynamic-profile proxy;
- `z_SW`: standardised stereo-width proxy.

These are the repository-supported primary scalar predictors in the current statistical-modeling feature evidence.

`z_SI` is frozen as sensitivity-only. Repository evidence treats stereo imbalance as complete but QC-oriented, not part of the primary feature model. Bark-band or Bark/PCA descriptors are not part of the primary LLM input because the repository does not currently define a globally valid final-20 prompt-ready representation.

Feature wording, serialization format, and rounding precision are frozen in the
final prompt package under `llm-experiments/prompts/` and rendered prompt
artifacts under `llm-experiments/outputs/final/rendered-prompts/`.

Permitted participant metadata must be collected independently of target-trial outcomes and used consistently across both principal conditions if included. Based on the current five-mix questionnaire schema, eligible background metadata fields are:

- `age_range`;
- `gender`;
- `cultural_influence_country`;
- `music_listening_habits`;
- `music_production_or_audio_engineering_experience`;
- `hearing_difficulty`.

Post-task fields such as scenario immersion, task difficulty, prior excerpt familiarity, listening device, completion environment, and additional comments are not frozen as primary participant metadata for LLM prompting because they are collected after the listening task and may reflect the completed study experience. They may be considered only in a clearly labelled secondary sensitivity analysis if a later protocol addendum justifies their use without target leakage.

## 9. Data Leakage Rules

For target trial `t`, the prompt/input must never contain:

1. target-trial human ratings;
2. target-trial participant comment;
3. target-trial observed preferred mix;
4. target-trial ranking derived from human ratings;
5. any feature, label, summary, statistic, or variable derived from target-trial human outcomes;
6. any textual description that directly or indirectly reveals which candidate was preferred in the target trial;
7. statistical-modeling predictions for that target trial.

Legitimate target-trial information exists independently of the participant's response, such as target context, anonymous A-E candidate labels, and precomputed acoustic descriptors.

Any participant-level aggregate derived from ratings or comments must exclude the target trial. The pipeline must not calculate a participant's average preference, preferred acoustic profile, mean rating, comment summary, or similar personalised feature using all of their trials and then provide it to the LLM.

Prompt-generation logs must record the target participant, target trial identifier, included history trial identifiers, excluded target trial identifier, acoustic descriptor source/version, information condition, and any missing-history flags.

## 10. Anonymous A-E Mapping Rules

Predictions operate on A-E as presented in the target trial.

The evaluation pipeline must retain the mapping between:

- anonymous presentation label A-E;
- `stimulus_id`;
- actual underlying mix ID.

The LLM should receive anonymous labels and permitted descriptors only. Ground-truth evaluation compares the canonical predicted anonymous label against the observed preferred anonymous label/set after reconstructing the correct trial-specific mapping.

If predictions are later aggregated by underlying mix identity, that conversion must use the stored trial-specific mapping. No fixed global A-E mapping may be assumed.

## 11. Structured Output Schema

Each model response must be strict JSON equivalent to:

```json
{
  "predicted_preferred_mix": "C",
  "predicted_ratings": {
    "A": 62,
    "B": 48,
    "C": 81,
    "D": 70,
    "E": 55
  },
  "predicted_ranking": ["C", "D", "A", "E", "B"]
}
```

Validation requirements:

- `predicted_preferred_mix` is exactly one of `A`, `B`, `C`, `D`, `E`;
- `predicted_ratings` contains exactly five keys: `A`, `B`, `C`, `D`, `E`;
- every rating is numeric and in the inclusive range 0-100;
- `predicted_ranking` contains each of `A`, `B`, `C`, `D`, and `E` exactly once;
- no candidate is missing and no extra candidate is present.

Free-form chain-of-thought is not required. If a brief rationale is collected for qualitative inspection, it must not be required for scoring and must not be treated as faithful internal reasoning.

## 12. Predicted-Output Consistency Rule

The structured predicted ratings are the canonical scored output.

For every valid response:

1. validate all five predicted ratings;
2. derive the canonical ranking by sorting predicted ratings from highest to lowest;
3. when predicted ratings tie, use the model's valid explicit `predicted_ranking` only to order labels within the tied rating group;
4. derive the canonical top candidate from the first label in the canonical ranking;
5. retain the model's explicit `predicted_preferred_mix` and explicit `predicted_ranking` for diagnostics;
6. score the canonical top candidate, canonical predicted ratings, and canonical ranking.

If the explicit preferred mix conflicts with the canonical top candidate, the conflict is logged but the canonical top candidate is used for evaluation. This rule is deterministic and does not use the ground truth.

If the explicit ranking is invalid, the response is structurally invalid. If the explicit ranking is valid but conflicts with the rating-derived order for non-tied ratings, the conflict is logged and the rating-derived order controls.

## 13. Human Tie Handling

Human 0-100 ratings may produce ties for the maximum observed rating within a target trial.

The ground-truth preferred label is therefore represented as a set:

- if exactly one label has the maximum observed rating, the set contains one label;
- if multiple labels share the maximum observed rating, the set contains all tied maximum labels.

For categorical accuracy, the prediction is correct if the canonical predicted top candidate belongs to the ground-truth preferred set.

This avoids arbitrarily choosing between equally highest-rated mixes. The nominal 20% chance reference applies only to single-winner trials. Tied trials have a larger acceptable set and must be reported separately or summarised with tie prevalence.

For observed ranking metrics, equal observed ratings are represented with average ranks or another deterministic tie-aware rank representation. Equal human ratings must not be arbitrarily ordered.

## 14. Metrics

### Primary Metric

The primary metric is preferred-mix top-1 accuracy.

For each eligible held-out target:

```text
correct = canonical predicted top A-E label belongs to observed highest-rated A-E label/set
```

When exactly one ground-truth winner exists, nominal descriptive chance performance is 1/5 = 20%. This 20% value is a descriptive reference, not automatically an inferential null model.

Invalid/missing model outputs count as incorrect in the strict primary accuracy analysis and are also reported through invalid-output rates. A secondary valid-only sensitivity summary may be reported, clearly labelled as such.

### Secondary Metrics

Rating prediction error:

- MAE across the five candidate ratings in each held-out trial, then summarised across targets with participant-aware uncertainty;
- RMSE across the five candidate ratings in each held-out trial, then summarised across targets with participant-aware uncertainty.

Ranking agreement:

- Spearman rank correlation between canonical predicted ranking and observed A-E ranking, using tie-aware observed ranks for equal human ratings.

Secondary analyses must remain secondary. They do not replace the top-1 preferred-mix result.

## 15. Invalid-Output Policy

The invalid-output rule is identical across all evaluated LLMs:

1. run the initial generation using the frozen prompt and inference settings;
2. if the response is not parseable JSON or violates the schema, make one format-repair retry;
3. the repair retry may include the invalid output and the schema requirements, but no ground truth and no additional participant information;
4. if the repaired response is still invalid, record the prediction as invalid/missing.

The pipeline must store the raw invalid response, retry prompt, repaired response if any, parser errors, final validity flag, and retry count.

The evaluation must report invalid-output rates by model and information condition. Invalid cases must not be silently dropped from denominators.

## 16. Inference and Repeated-Run Principle

The primary evaluation uses fixed low-variance inference settings where
supported. Model-specific parameters, model identifiers, structured-output
settings, and retained backend metadata are recorded in
`llm-experiments/outputs/final/inference-config/` and the model-specific run
manifests under `llm-experiments/outputs/final/model-predictions/source/`.

Evaluation principles frozen now:

- identical prompt information must be used across models within a condition;
- model-specific formatting adaptations are allowed only when technically required;
- no model may receive participant information unavailable to another model in the same condition;
- predictions must be generated without access to ground truth;
- inference settings must be fixed before final evaluation;
- repeated stochastic querying is not part of the primary experiment.

Repeated-run stability analysis may be conducted as an optional secondary analysis if resources permit, using a separately frozen repeated-run plan.

## 17. Participant Splitting and Development Separation

Holding out a target trial from the LLM prompt is distinct from train/validation/test splitting participants.

For zero-shot or few-shot foundation-model inference with no parameter training on the study dataset, a conventional participant training split is not required for the primary prediction evaluation. The leave-one-trial-out design concerns what information is hidden from each prompt, not supervised training of model parameters.

However, anything learned, selected, calibrated, tuned, or constructed from study outcomes must use an explicit development/evaluation separation that prevents test leakage. This applies to prompt variants, few-shot examples from study data, calibration procedures, learned parsers, learned feature transformations, or any auxiliary model trained on participant outcomes.

No prompt variant may be selected based on final target-label performance.

## 18. LLM vs Mixed-Effects Baseline Comparison

The LLM and mixed-effects baseline should be compared on the same held-out human outcomes wherever methodologically possible.

For the primary categorical task, derive an equivalent baseline preferred-mix prediction from baseline-predicted ratings or preference probabilities for each aligned held-out participant-trial target. Compare:

- LLM top-1 preferred-mix accuracy;
- mixed-effects baseline top-1 preferred-mix accuracy;
- MAE/RMSE for predicted ratings where available.

Because multiple targets come from the same participant, uncertainty and comparison methods must account for clustering/repeated measures. Recommended reporting includes participant-cluster bootstrap confidence intervals and paired participant-level comparisons between conditions/models.

The existing statistical modeling is not modified or refit in this task. If the current baseline implementation cannot yet produce exactly matched leave-one-trial-out participant-trial predictions, that is an implementation gap for a later phase, not a reason to change the frozen LLM target.

## 19. Reporting Hierarchy

### Primary Confirmatory Evaluation

The primary confirmatory reporting hierarchy is:

- preferred-mix top-1 accuracy;
- principal model comparison across the selected LLMs;
- non-history versus personalised-history comparison;
- LLM versus mixed-effects baseline comparison where aligned baseline predictions are available.

### Secondary Evaluation

Secondary reporting may include:

- MAE/RMSE of predicted ratings;
- tie-aware ranking agreement;
- exploratory information ablations, if separately justified;
- invalid-output rates;
- output-consistency diagnostics;
- optional repeated-run/model-stability analysis;
- qualitative error analysis of comments and rationales, if collected.

Exploratory or secondary analyses must not be presented as the primary hypothesis test.

## 20. Final Implementation Artifacts

The final implementation artifacts are:

- prompt template, package manifest, and prompt specification in `llm-experiments/prompts/`;
- rendered prompts and request manifests in `llm-experiments/outputs/final/rendered-prompts/`;
- model and backend configuration in `llm-experiments/outputs/final/inference-config/`;
- consolidated predictions in `llm-experiments/outputs/final/model-predictions/`;
- held-out ground truth, scoring metrics, chance tests, and model comparisons in `llm-experiments/outputs/final/evaluation/`;
- compact examiner-facing copies in `results/llm/`.

Internal filenames retain historical version identifiers where those identifiers
are part of frozen hashes, tests, or provenance.
