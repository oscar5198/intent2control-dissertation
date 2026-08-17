# Phase 6E Provider-Adapter Boundary

Package version: `phase6d_prompt_package_v1`

Prompt specification version: `phase6d_prompt_spec_v1`

Response schema version: `preference_prediction_response_v1`

This document defines the boundary between the frozen Phase 6D prompt package
and future Phase 6E provider adapters. It is provider-neutral and does not
select models, endpoints, temperatures, max-token values, or hosting systems.

## Adapter Responsibilities

Provider adapters may change only technical transport details:

- API request envelope;
- message transport or role serialization;
- provider-native structured-output syntax;
- provider-specific schema-enforcement parameter names;
- tokenizer-specific counting;
- endpoint execution parameters recorded outside the prompt package.

Provider adapters must preserve the semantic prompt package exactly:

- frozen system instruction;
- rendered user-message semantic content;
- task definition;
- section order;
- participant metadata fields;
- acoustic feature values and rendered precision;
- candidate A-E order;
- eligible history evidence;
- output semantics;
- response schema version.

## No Prompt Augmentation

Adapters must not inject demonstrations, examples, hidden instructions,
provider-specific rationales, summaries of participant history, additional
features, extra metadata fields, target outcomes, statistical-baseline
predictions, or candidate hints into primary inference requests.

## Structured Output

Every primary inference request targets
`preference_prediction_response_v1`. Provider adapters may enforce this schema
using native response-format mechanisms. If a provider lacks native schema
enforcement, the adapter may request JSON text and must validate the parsed
object locally against the same schema.

Provider-specific response schemas are not part of the principal evaluation.

## Repair

Adapters must use the frozen repair policy:

- maximum primary generation attempts: 1;
- maximum formatting-only repair attempts: 1;
- repair receives no ground truth;
- repair receives no correctness feedback;
- repair gives no candidate hint;
- failed repair is marked invalid/missing.

## Versioning

Any substantive change to prompt wording, history structure, metadata fields,
feature descriptions, acoustic inputs, candidate ordering, response schema,
reasoning policy, few-shot policy, or condition definition requires a new
prompt-package version. Do not silently overwrite
`phase6d_prompt_package_v1`.
