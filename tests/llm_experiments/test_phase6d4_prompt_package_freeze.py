import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.prompts.freeze_package import (  # noqa: E402
    INVALID_RESPONSE_FIXTURES,
    PHASE6D_PROMPT_PACKAGE_FROZEN_GATE,
    PROMPT_PACKAGE_VERSION,
    VALID_RESPONSE_FIXTURE,
    build_reference_prompt_pair,
    hash_reference_prompts,
    sha256_file,
    validate_response_fixtures,
    verify_prompt_package,
)
from llm_experiments.prompts.prompt_spec import (  # noqa: E402
    CONDITIONS,
    EXPECTED_LABELS,
    MISSING_VALUE,
    PARTICIPANT_METADATA_LABELS,
    PROMPT_ACOUSTIC_DECIMALS,
    PROMPT_SPEC_VERSION,
    RESPONSE_SCHEMA_VERSION,
)


MANIFEST = REPO_ROOT / "llm-experiments" / "prompts" / "phase6d_prompt_package_manifest.json"
PROMPT_DATA = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6b5" / "final_prompt_data_objects.jsonl"
RESPONSE_SCHEMA = REPO_ROOT / "llm-experiments" / "schema" / "preference_prediction_response_v1.json"
REFERENCE_PROMPTS = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6d4_prompt_freeze" / "phase6d_reference_prompt_pair.json"
FREEZE_AUDIT = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6d4_prompt_freeze" / "phase6d_prompt_freeze_audit.json"
SIZE_AUDIT = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6d4_prompt_freeze" / "prompt_size_reference_audit.json"


def test_package_manifest_has_required_fields():
    manifest = load_manifest()
    required = {
        "package_version",
        "prompt_spec_version",
        "response_schema_version",
        "rendered_prompt_schema_version",
        "template_artifact_path",
        "response_schema_path",
        "renderer_module_path",
        "condition_validator_module_path",
        "primary_experimental_conditions",
        "acoustic_input_contract",
        "participant_metadata_contract",
        "song_identity_policy",
        "reasoning_policy",
        "few_shot_policy",
        "structured_output_policy",
        "repair_policy",
        "artifact_hashes",
        "reference_prompt_hashes",
    }
    assert required <= set(manifest)


def test_package_prompt_and_schema_versions_are_fixed():
    manifest = load_manifest()
    assert manifest["package_version"] == PROMPT_PACKAGE_VERSION == "phase6d_prompt_package_v1"
    assert manifest["prompt_spec_version"] == PROMPT_SPEC_VERSION == "phase6d_prompt_spec_v1"
    assert manifest["response_schema_version"] == RESPONSE_SCHEMA_VERSION == "preference_prediction_response_v1"


def test_artifact_hashes_are_reproducible():
    manifest = load_manifest()
    for artifact in manifest["artifact_hashes"].values():
        assert sha256_file(REPO_ROOT / artifact["path"]) == artifact["sha256"]


def test_verifier_detects_changed_template(tmp_path):
    manifest = load_manifest()
    manifest["artifact_hashes"]["semantic_template"]["sha256"] = "0" * 64
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    result = verify_prompt_package(REPO_ROOT, path)
    assert result["artifact_hashes_valid"] is False
    assert any(row["artifact"] == "semantic_template" for row in result["artifact_hash_mismatches"])


def test_verifier_detects_changed_response_schema(tmp_path):
    manifest = load_manifest()
    manifest["artifact_hashes"]["response_schema"]["sha256"] = "0" * 64
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    result = verify_prompt_package(REPO_ROOT, path)
    assert result["artifact_hashes_valid"] is False
    assert any(row["artifact"] == "response_schema" for row in result["artifact_hash_mismatches"])


def test_canonical_synthetic_reference_prompt_regenerates_identically():
    frozen = json.loads(REFERENCE_PROMPTS.read_text(encoding="utf-8"))
    regenerated = build_reference_prompt_pair(PROMPT_DATA)
    assert regenerated == frozen
    assert frozen["package_version"] == PROMPT_PACKAGE_VERSION
    assert frozen["contains_ground_truth"] is False


def test_reference_prompt_hashes_match_manifest():
    manifest = load_manifest()
    frozen = json.loads(REFERENCE_PROMPTS.read_text(encoding="utf-8"))
    assert hash_reference_prompts(frozen) == manifest["reference_prompt_hashes"]


def test_valid_response_fixture_passes_schema():
    schema = json.loads(RESPONSE_SCHEMA.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(VALID_RESPONSE_FIXTURE))
    assert errors == []


def test_invalid_response_fixtures_fail_schema():
    schema = json.loads(RESPONSE_SCHEMA.read_text(encoding="utf-8"))
    result = validate_response_fixtures(schema, VALID_RESPONSE_FIXTURE, INVALID_RESPONSE_FIXTURES)
    assert result["valid_fixture_passed"] is True
    assert result["invalid_fixtures_failed"] is True
    assert set(result["invalid_fixture_results"]) == {
        "missing_rating",
        "duplicate_ranking_item",
        "invalid_label",
        "rating_above_100",
        "explanatory_text_outside_json",
    }


def test_reasoning_policy_recorded_as_none():
    policy = load_manifest()["reasoning_policy"]
    assert policy["primary_inference"] == "zero-shot"
    assert policy["chain_of_thought_requested"] is False
    assert policy["rationale_output_field"] is False
    assert policy["scored_fields_only"] == ["predicted_preferred_mix", "predicted_ratings", "predicted_ranking"]


def test_few_shot_count_recorded_as_zero():
    policy = load_manifest()["few_shot_policy"]
    assert policy["primary_few_shot_examples"] == 0
    assert policy["provider_adapters_may_inject_demonstrations"] is False
    assert policy["future_few_shot_requires_new_package_version"] is True


def test_primary_acoustic_features_and_z_si_exclusion_are_frozen():
    contract = load_manifest()["acoustic_input_contract"]
    assert contract["primary_features"] == ["z_RMS", "z_CF", "z_SW"]
    assert contract["rendered_precision_decimal_places"] == PROMPT_ACOUSTIC_DECIMALS == 2
    assert contract["sensitivity_only_features_excluded"] == ["z_SI"]


def test_participant_metadata_fields_are_exactly_correct():
    contract = load_manifest()["participant_metadata_contract"]
    assert contract["fields"] == list(PARTICIPANT_METADATA_LABELS)
    assert contract["missing_value"] == MISSING_VALUE


def test_condition_definitions_are_exactly_correct():
    manifest = load_manifest()
    assert manifest["primary_experimental_conditions"] == CONDITIONS
    contract = manifest["condition_contract"]
    assert contract["only_substantive_difference"] == "Previous listening evidence from this participant"
    assert contract["condition_integrity_gate_required"] is True


def test_candidate_order_policy_is_frozen():
    policy = load_manifest()["candidate_order_policy"]
    assert policy["target_candidates"] == EXPECTED_LABELS
    assert policy["history_candidates"] == EXPECTED_LABELS
    assert policy["history_trials"] == "original trial_order ascending"


def test_repair_policy_is_frozen():
    policy = load_manifest()["repair_policy"]
    assert policy["maximum_primary_generation_attempts"] == 1
    assert policy["maximum_format_repair_attempts"] == 1
    assert policy["repair_is_formatting_only"] is True
    assert policy["repair_receives_ground_truth"] is False
    assert policy["repair_receives_correctness_feedback"] is False
    assert policy["after_failed_repair"] == "mark invalid/missing"


def test_condition_integrity_gate_required_and_passed():
    manifest = load_manifest()
    audit = json.loads(FREEZE_AUDIT.read_text(encoding="utf-8"))
    assert manifest["condition_contract"]["condition_integrity_gate_required"] is True
    assert audit["condition_integrity"] is True
    assert audit[PHASE6D_PROMPT_PACKAGE_FROZEN_GATE] is True


def test_no_provider_specific_model_configuration_appears_in_package():
    manifest_text = MANIFEST.read_text(encoding="utf-8")
    forbidden = ["gpt-", "claude-", "llama", "centaur", "temperature", "max_tokens", "endpoint_url"]
    assert not any(token in manifest_text.lower() for token in forbidden)
    assert load_manifest()["provider_adapter_boundary"]["provider_specific_model_configuration_included"] is False


def test_prompt_size_reference_audit_is_frozen():
    audit = json.loads(SIZE_AUDIT.read_text(encoding="utf-8"))
    assert audit["package_version"] == PROMPT_PACKAGE_VERSION
    assert audit["size_summary"]["non_history"]["characters_min"] == 2780
    assert audit["size_summary"]["non_history"]["characters_median"] == 2802
    assert audit["size_summary"]["non_history"]["characters_max"] == 2850
    assert audit["size_summary"]["personalised_history"]["characters_min"] == 7139
    assert audit["size_summary"]["personalised_history"]["characters_median"] == 8166
    assert audit["size_summary"]["personalised_history"]["characters_max"] == 8209
    assert audit["max_history_trial_count"] == 5
    assert audit["prompt_size_structural_check"] is True


def test_preflight_verifier_passes_for_frozen_package():
    result = verify_prompt_package(REPO_ROOT)
    assert result["artifact_hashes_valid"] is True
    assert result["reference_prompt_hashes_valid"] is True
    assert result["condition_integrity"] is True
    assert result["deterministic_rendering"] is True
    assert result[PHASE6D_PROMPT_PACKAGE_FROZEN_GATE] is True


def load_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))
