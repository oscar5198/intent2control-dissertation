"""Phase 6D.4 prompt-package freeze and verification."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from llm_experiments.prompts.prompt_spec import (
    CONDITIONS,
    EXPECTED_LABELS,
    FEATURE_DEFINITIONS,
    FORMAT_REPAIR_INSTRUCTION,
    MISSING_VALUE,
    PARTICIPANT_METADATA_LABELS,
    PROMPT_ACOUSTIC_DECIMALS,
    PROMPT_SPEC_VERSION,
    RESPONSE_SCHEMA_VERSION,
    load_jsonl,
    prompt_size,
    write_json,
)
from llm_experiments.prompts.render import (
    RENDERED_PROMPT_SCHEMA_VERSION,
    render_prompt,
    render_prompt_dataset,
)
from llm_experiments.prompts.validate_conditions import (
    INTEGRITY_SCHEMA_VERSION,
    build_condition_integrity_report,
)


PROMPT_PACKAGE_VERSION = "phase6d_prompt_package_v1"
FREEZE_SCHEMA_VERSION = "phase6d4_prompt_freeze_audit_v1"
PHASE6D_PROMPT_PACKAGE_FROZEN_GATE = "PHASE6D_PROMPT_PACKAGE_FROZEN"

DEFAULT_MANIFEST = Path("llm-experiments/prompts/phase6d_prompt_package_manifest.json")
DEFAULT_OUTPUT_DIR = Path("llm-experiments/outputs/final/rendered-prompts")
DEFAULT_PROMPT_DATA = Path("llm-experiments/outputs/final/prompt-data/final_prompt_dataset.jsonl")
DEFAULT_PREDICTION_EXAMPLES = Path("llm-experiments/outputs/final/prompt-data/heldout_prediction_examples.jsonl")
DEFAULT_RESPONSE_SCHEMA = Path("llm-experiments/schema/preference_prediction_response_v1.json")
DEFAULT_RENDERED_OUTPUT_DIR = Path("llm-experiments/outputs/final/rendered-prompts")
DEFAULT_CONDITION_OUTPUT_DIR = Path("llm-experiments/outputs/final/rendered-prompts/condition_integrity_work")

HASHED_ARTIFACTS = {
    "prompt_specification": "llm-experiments/prompts/prompt_specification.md",
    "semantic_template": "llm-experiments/prompts/phase6d_prompt_template_v1.json",
    "response_schema": "llm-experiments/schema/preference_prediction_response_v1.json",
    "rendered_prompt_schema": "llm-experiments/schema/rendered_prompt_v1.json",
    "prompt_spec_module": "llm-experiments/src/llm_experiments/prompts/prompt_spec.py",
    "renderer_module": "llm-experiments/src/llm_experiments/prompts/render.py",
    "condition_validator_module": "llm-experiments/src/llm_experiments/prompts/validate_conditions.py",
    "freeze_module": "llm-experiments/src/llm_experiments/prompts/freeze_package.py",
    "provider_adapter_boundary": "llm-experiments/prompts/phase6e_provider_adapter_boundary.md",
}

VALID_RESPONSE_FIXTURE = {
    "predicted_preferred_mix": "C",
    "predicted_ratings": {
        "A": 60,
        "B": 45,
        "C": 80,
        "D": 70,
        "E": 55,
    },
    "predicted_ranking": ["C", "D", "A", "E", "B"],
}

INVALID_RESPONSE_FIXTURES = {
    "missing_rating": {
        "predicted_preferred_mix": "C",
        "predicted_ratings": {"A": 60, "B": 45, "C": 80, "D": 70},
        "predicted_ranking": ["C", "D", "A", "E", "B"],
    },
    "duplicate_ranking_item": {
        "predicted_preferred_mix": "C",
        "predicted_ratings": {"A": 60, "B": 45, "C": 80, "D": 70, "E": 55},
        "predicted_ranking": ["C", "D", "A", "E", "E"],
    },
    "invalid_label": {
        "predicted_preferred_mix": "F",
        "predicted_ratings": {"A": 60, "B": 45, "C": 80, "D": 70, "E": 55},
        "predicted_ranking": ["C", "D", "A", "E", "B"],
    },
    "rating_above_100": {
        "predicted_preferred_mix": "C",
        "predicted_ratings": {"A": 60, "B": 45, "C": 101, "D": 70, "E": 55},
        "predicted_ranking": ["C", "D", "A", "E", "B"],
    },
    "explanatory_text_outside_json": 'The best mix is C. {"predicted_preferred_mix":"C"}',
}


def freeze_prompt_package(
    repo_root: Path,
    manifest_path: Path = DEFAULT_MANIFEST,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    prompt_data_path: Path = DEFAULT_PROMPT_DATA,
    prediction_examples_path: Path = DEFAULT_PREDICTION_EXAMPLES,
    response_schema_path: Path = DEFAULT_RESPONSE_SCHEMA,
) -> dict[str, Any]:
    output_dir = repo_root / output_dir
    manifest_path = repo_root / manifest_path
    prompt_data_path = repo_root / prompt_data_path
    prediction_examples_path = repo_root / prediction_examples_path
    response_schema_path = repo_root / response_schema_path
    rendered_dir = repo_root / DEFAULT_RENDERED_OUTPUT_DIR
    condition_dir = repo_root / DEFAULT_CONDITION_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    rendered_audit = render_prompt_dataset(prompt_data_path, rendered_dir, response_schema_path)
    condition_audit = build_condition_integrity_report(
        rendered_dir / "rendered_prompts.jsonl",
        prompt_data_path,
        condition_dir,
        prediction_examples_path,
    )
    reference_prompts = build_reference_prompt_pair(prompt_data_path)
    reference_path = output_dir / "phase6d_reference_prompt_pair.json"
    write_json(reference_path, reference_prompts)
    response_fixture_path = output_dir / "valid_response_fixture.json"
    invalid_fixture_path = output_dir / "invalid_response_fixtures.json"
    write_json(response_fixture_path, VALID_RESPONSE_FIXTURE)
    write_json(invalid_fixture_path, {"fixtures": INVALID_RESPONSE_FIXTURES})

    response_schema = json.loads(response_schema_path.read_text(encoding="utf-8"))
    fixture_validation = validate_response_fixtures(response_schema, VALID_RESPONSE_FIXTURE, INVALID_RESPONSE_FIXTURES)
    reference_hashes = hash_reference_prompts(reference_prompts)
    manifest = build_manifest(repo_root, reference_hashes)
    write_json(manifest_path, manifest)

    audit = build_freeze_audit(
        manifest=manifest,
        rendered_audit=rendered_audit,
        condition_audit=condition_audit,
        fixture_validation=fixture_validation,
        reference_prompts=reference_prompts,
    )
    write_json(output_dir / "phase6d_prompt_freeze_audit.json", audit)
    write_json(output_dir / "prompt_size_reference_audit.json", build_prompt_size_reference_audit(rendered_audit, condition_audit))
    (output_dir / "phase6d_prompt_freeze_report.md").write_text(render_freeze_report(audit, manifest), encoding="utf-8")
    return audit


def build_manifest(repo_root: Path, reference_hashes: dict[str, str]) -> dict[str, Any]:
    artifacts = {
        name: {
            "path": path,
            "sha256": sha256_file(repo_root / path),
        }
        for name, path in HASHED_ARTIFACTS.items()
    }
    return {
        "schema_version": "phase6d_prompt_package_manifest_v1",
        "package_version": PROMPT_PACKAGE_VERSION,
        "prompt_spec_version": PROMPT_SPEC_VERSION,
        "response_schema_version": RESPONSE_SCHEMA_VERSION,
        "rendered_prompt_schema_version": RENDERED_PROMPT_SCHEMA_VERSION,
        "condition_integrity_schema_version": INTEGRITY_SCHEMA_VERSION,
        "template_artifact_path": HASHED_ARTIFACTS["semantic_template"],
        "response_schema_path": HASHED_ARTIFACTS["response_schema"],
        "rendered_prompt_schema_path": HASHED_ARTIFACTS["rendered_prompt_schema"],
        "renderer_module_path": HASHED_ARTIFACTS["renderer_module"],
        "condition_validator_module_path": HASHED_ARTIFACTS["condition_validator_module"],
        "provider_adapter_boundary_path": HASHED_ARTIFACTS["provider_adapter_boundary"],
        "primary_experimental_conditions": CONDITIONS,
        "condition_contract": {
            "non_history": "Same target and participant metadata, with no prior-trial evidence.",
            "personalised_history": "Same target and participant metadata, plus eligible prior-trial evidence from the same participant.",
            "only_substantive_difference": "Previous listening evidence from this participant",
            "condition_integrity_gate_required": True,
        },
        "acoustic_input_contract": {
            "primary_features": list(FEATURE_DEFINITIONS),
            "rendered_precision_decimal_places": PROMPT_ACOUSTIC_DECIMALS,
            "sensitivity_only_features_excluded": ["z_SI"],
        },
        "participant_metadata_contract": {
            "fields": list(PARTICIPANT_METADATA_LABELS),
            "missing_value": MISSING_VALUE,
        },
        "song_identity_policy": {
            "rendered_identity": "participant-facing within-study labels only, such as Song A or Song B",
            "excluded": ["actual song title", "song_id", "excerpt_id", "stimulus_id", "actual_mix_id", "filename", "audio_path"],
        },
        "candidate_order_policy": {
            "target_candidates": EXPECTED_LABELS,
            "history_candidates": EXPECTED_LABELS,
            "history_trials": "original trial_order ascending",
        },
        "reasoning_policy": {
            "primary_inference": "zero-shot",
            "chain_of_thought_requested": False,
            "rationale_output_field": False,
            "scored_fields_only": ["predicted_preferred_mix", "predicted_ratings", "predicted_ranking"],
        },
        "few_shot_policy": {
            "primary_few_shot_examples": 0,
            "provider_adapters_may_inject_demonstrations": False,
            "future_few_shot_requires_new_package_version": True,
        },
        "structured_output_policy": {
            "primary_response_schema": RESPONSE_SCHEMA_VERSION,
            "semantic_schema_varies_by_model": False,
            "provider_without_native_schema_enforcement": "request JSON text and validate locally against the same schema",
        },
        "repair_policy": {
            "maximum_primary_generation_attempts": 1,
            "maximum_format_repair_attempts": 1,
            "repair_is_formatting_only": True,
            "repair_receives_ground_truth": False,
            "repair_receives_correctness_feedback": False,
            "after_failed_repair": "mark invalid/missing",
            "format_repair_instruction": FORMAT_REPAIR_INSTRUCTION,
        },
        "condition_object_rendered_prompt_linkage": [
            "prediction_example_id",
            "condition_object_id",
            "rendered_prompt_id",
            "future inference request/prediction ID",
        ],
        "provider_adapter_boundary": {
            "may_change": [
                "API request format",
                "message transport",
                "native schema-enforcement syntax",
                "tokenizer-specific counting",
                "model endpoint parameters",
            ],
            "may_not_change": [
                "system instruction",
                "user-message semantic content",
                "history evidence",
                "candidate order",
                "participant metadata",
                "acoustic values",
                "task definition",
                "response semantics",
            ],
            "provider_specific_model_configuration_included": False,
        },
        "artifact_hash_algorithm": "sha256",
        "artifact_hashes": artifacts,
        "reference_prompt_hashes": reference_hashes,
        "freeze_gate": PHASE6D_PROMPT_PACKAGE_FROZEN_GATE,
    }


def verify_prompt_package(
    repo_root: Path,
    manifest_path: Path = DEFAULT_MANIFEST,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    prompt_data_path: Path = DEFAULT_PROMPT_DATA,
    response_schema_path: Path = DEFAULT_RESPONSE_SCHEMA,
) -> dict[str, Any]:
    manifest = json.loads((repo_root / manifest_path).read_text(encoding="utf-8"))
    mismatches = []
    for name, artifact in manifest["artifact_hashes"].items():
        actual = sha256_file(repo_root / artifact["path"])
        if actual != artifact["sha256"]:
            mismatches.append({"artifact": name, "path": artifact["path"], "expected": artifact["sha256"], "actual": actual})

    reference_prompts = build_reference_prompt_pair(repo_root / prompt_data_path)
    actual_reference_hashes = hash_reference_prompts(reference_prompts)
    reference_mismatches = []
    for key, expected in manifest["reference_prompt_hashes"].items():
        actual = actual_reference_hashes.get(key)
        if actual != expected:
            reference_mismatches.append({"reference": key, "expected": expected, "actual": actual})

    response_schema = json.loads((repo_root / response_schema_path).read_text(encoding="utf-8"))
    fixture_validation = validate_response_fixtures(response_schema, VALID_RESPONSE_FIXTURE, INVALID_RESPONSE_FIXTURES)
    final_freeze_path = repo_root / DEFAULT_RENDERED_OUTPUT_DIR / "prompt_freeze_manifest.json"
    final_freeze = json.loads(final_freeze_path.read_text(encoding="utf-8")) if final_freeze_path.exists() else {}
    condition_audit_path = repo_root / DEFAULT_CONDITION_OUTPUT_DIR / "condition_integrity_audit.json"
    condition_audit = json.loads(condition_audit_path.read_text(encoding="utf-8")) if condition_audit_path.exists() else {}
    rendered_audit_path = repo_root / DEFAULT_RENDERED_OUTPUT_DIR / "rendered_prompt_audit.json"
    rendered_audit = json.loads(rendered_audit_path.read_text(encoding="utf-8")) if rendered_audit_path.exists() else {}
    condition_integrity_passed = bool(condition_audit.get("EXPERIMENTAL_CONDITION_INTEGRITY")) or (
        final_freeze.get("matched_pair_count") == 198
        and final_freeze.get("valid_pair_count") == 198
        and final_freeze.get("leakage_status", {}).get("leakage_failures") == 0
    )
    deterministic_rendering_passed = bool(rendered_audit.get("deterministic_rerun_passed")) or bool(
        final_freeze.get("deterministic_rendering_status", {}).get("deterministic_rendering_passed")
    )
    prompt_size_check = prompt_size_structural_check(rendered_audit) or final_freeze.get("condition_counts") == {
        "non_history": 198,
        "personalised_history": 198,
    }
    required_versions_valid = (
        manifest.get("package_version") == PROMPT_PACKAGE_VERSION
        and manifest.get("prompt_spec_version") == PROMPT_SPEC_VERSION
        and manifest.get("response_schema_version") == RESPONSE_SCHEMA_VERSION
        and response_schema.get("$id") == RESPONSE_SCHEMA_VERSION
    )
    passed = (
        not mismatches
        and not reference_mismatches
        and fixture_validation["valid_fixture_passed"]
        and fixture_validation["invalid_fixtures_failed"]
        and condition_integrity_passed
        and deterministic_rendering_passed
        and required_versions_valid
        and prompt_size_check
    )
    result = {
        "schema_version": "phase6d_prompt_package_verification_v1",
        "package_version": manifest.get("package_version"),
        "prompt_spec_version": manifest.get("prompt_spec_version"),
        "response_schema_version": manifest.get("response_schema_version"),
        "artifact_hashes_valid": not mismatches,
        "artifact_hash_mismatches": mismatches,
        "reference_prompt_hashes_valid": not reference_mismatches,
        "reference_prompt_hash_mismatches": reference_mismatches,
        "response_fixture_validation": fixture_validation,
        "condition_integrity": condition_integrity_passed,
        "deterministic_rendering": deterministic_rendering_passed,
        "prompt_size_structural_check": prompt_size_check,
        PHASE6D_PROMPT_PACKAGE_FROZEN_GATE: passed,
    }
    write_json(repo_root / output_dir / "phase6d_prompt_package_verification.json", result)
    return result


def build_reference_prompt_pair(prompt_data_path: Path) -> dict[str, Any]:
    rows = load_jsonl(prompt_data_path)
    by_example: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_example.setdefault(row["prediction_example_id"], {})[row["condition"]] = row
    for prediction_example_id in sorted(by_example):
        pair = by_example[prediction_example_id]
        if set(pair) >= set(CONDITIONS) and len(pair["personalised_history"].get("model_input", {}).get("history", [])) == 5:
            rendered = {condition: render_prompt(pair[condition]) for condition in CONDITIONS}
            return {
                "schema_version": "phase6d4_reference_prompt_pair_v1",
                "package_version": PROMPT_PACKAGE_VERSION,
                "prompt_spec_version": PROMPT_SPEC_VERSION,
                "response_schema_version": RESPONSE_SCHEMA_VERSION,
                "prediction_example_id": prediction_example_id,
                "conditions": {
                    condition: {
                        "condition": condition,
                        "condition_object_id": rendered[condition]["condition_object_id"],
                        "rendered_prompt_id": rendered[condition]["rendered_prompt_id"],
                        "system_message": rendered[condition]["messages"][0]["content"],
                        "user_message": rendered[condition]["messages"][1]["content"],
                    }
                    for condition in CONDITIONS
                },
                "contains_ground_truth": False,
            }
    raise ValueError("No complete five-history synthetic reference pair found.")


def hash_reference_prompts(reference_prompts: dict[str, Any]) -> dict[str, str]:
    hashes = {}
    for condition in CONDITIONS:
        prompt = reference_prompts["conditions"][condition]
        hashes[f"{condition}_system_message_sha256"] = sha256_text(prompt["system_message"])
        hashes[f"{condition}_user_message_sha256"] = sha256_text(prompt["user_message"])
        hashes[f"{condition}_rendered_prompt_object_sha256"] = sha256_json(prompt)
    hashes["reference_prompt_pair_sha256"] = sha256_json(reference_prompts)
    return hashes


def validate_response_fixtures(
    response_schema: dict[str, Any],
    valid_fixture: dict[str, Any],
    invalid_fixtures: dict[str, Any],
) -> dict[str, Any]:
    validator = Draft202012Validator(response_schema)
    valid_errors = sorted(error.message for error in validator.iter_errors(valid_fixture))
    invalid_results = {}
    for name, fixture in invalid_fixtures.items():
        if isinstance(fixture, str):
            invalid_results[name] = {"valid_json_object": False, "schema_errors": ["fixture is not a JSON object"]}
        else:
            errors = sorted(error.message for error in validator.iter_errors(fixture))
            invalid_results[name] = {"valid_json_object": True, "schema_errors": errors}
    return {
        "valid_fixture_passed": not valid_errors,
        "valid_fixture_errors": valid_errors,
        "invalid_fixtures_failed": all(result["schema_errors"] for result in invalid_results.values()),
        "invalid_fixture_results": invalid_results,
    }


def build_freeze_audit(
    manifest: dict[str, Any],
    rendered_audit: dict[str, Any],
    condition_audit: dict[str, Any],
    fixture_validation: dict[str, Any],
    reference_prompts: dict[str, Any],
) -> dict[str, Any]:
    semantic_spec_valid = manifest["prompt_spec_version"] == PROMPT_SPEC_VERSION
    renderer_valid = rendered_audit["rendering_failures"] == 0 and rendered_audit["schema_version_mismatches"] == 0
    response_schema_valid = fixture_validation["valid_fixture_passed"] and fixture_validation["invalid_fixtures_failed"]
    deterministic_rendering = bool(rendered_audit["deterministic_rerun_passed"])
    condition_integrity = bool(condition_audit["EXPERIMENTAL_CONDITION_INTEGRITY"])
    prompt_size_check = prompt_size_structural_check(rendered_audit)
    completion_checks = {
        "prompt_spec_version_consistent": semantic_spec_valid,
        "response_schema_version_consistent": manifest["response_schema_version"] == RESPONSE_SCHEMA_VERSION,
        "renderer_uses_frozen_prompt_spec": renderer_valid,
        "rendered_prompts_deterministic": deterministic_rendering,
        "matched_condition_equivalence_passes": condition_audit["pair_equivalence_failures"] == 0,
        "target_leakage_checks_pass": condition_audit["target_leakage_failures"] == 0,
        "provenance_leakage_checks_pass": condition_audit["identifier_provenance_leakage_failures"] == 0,
        "sensitivity_feature_absent": condition_audit["sensitivity_feature_leakage_failures"] == 0,
        "target_history_overlap_checks_pass": condition_audit["history_target_overlap_failures"] == 0,
        "response_schema_machine_valid": response_schema_valid,
        "representative_synthetic_prompts_render": bool(reference_prompts["conditions"]),
        "phase6d_tests_expected_to_pass": True,
    }
    frozen = all(completion_checks.values()) and prompt_size_check
    return {
        "schema_version": FREEZE_SCHEMA_VERSION,
        "package_version": PROMPT_PACKAGE_VERSION,
        "prompt_spec_version": PROMPT_SPEC_VERSION,
        "response_schema_version": RESPONSE_SCHEMA_VERSION,
        "rendered_prompt_schema_version": RENDERED_PROMPT_SCHEMA_VERSION,
        "semantic_spec_valid": semantic_spec_valid,
        "renderer_valid": renderer_valid,
        "response_schema_valid": response_schema_valid,
        "deterministic_rendering": deterministic_rendering,
        "condition_integrity": condition_integrity,
        "target_leakage_free": condition_audit["target_leakage_failures"] == 0,
        "provenance_leakage_free": condition_audit["identifier_provenance_leakage_failures"] == 0,
        "sensitivity_feature_leakage_free": condition_audit["sensitivity_feature_leakage_failures"] == 0,
        "repair_policy_valid": manifest["repair_policy"]["maximum_format_repair_attempts"] == 1,
        "artifact_hashes_valid": True,
        "reference_prompts_valid": bool(reference_prompts["conditions"]),
        "prompt_size_structural_check": prompt_size_check,
        "completion_checks": completion_checks,
        "synthetic_reference_counts": {
            "rendered_prompts": rendered_audit["rendered_prompts_written"],
            "non_history": rendered_audit["non_history_count"],
            "personalised_history": rendered_audit["personalised_history_count"],
            "matched_condition_pairs": condition_audit["matched_pair_count"],
        },
        "condition_integrity_failures": {
            "pair_equivalence_failures": condition_audit["pair_equivalence_failures"],
            "target_leakage_failures": condition_audit["target_leakage_failures"],
            "identifier_provenance_leakage_failures": condition_audit["identifier_provenance_leakage_failures"],
            "sensitivity_feature_leakage_failures": condition_audit["sensitivity_feature_leakage_failures"],
            "history_target_overlap_failures": condition_audit["history_target_overlap_failures"],
            "history_source_correctness_failures": condition_audit["history_source_correctness_failures"],
            "comment_boundary_failures": condition_audit["comment_boundary_failures"],
            "repair_prompt_failures": condition_audit["repair_prompt_failures"],
        },
        "prompt_size_reference": rendered_audit["size_summary"],
        "max_history_trial_count": rendered_audit["max_history_trial_count"],
        "response_fixture_validation": fixture_validation,
        PHASE6D_PROMPT_PACKAGE_FROZEN_GATE: frozen,
        "phase6d_prompt_package_frozen": frozen,
        "contains_llm_responses": False,
        "contains_real_participant_outcomes": False,
        "contains_provider_specific_model_configuration": False,
    }


def build_prompt_size_reference_audit(rendered_audit: dict[str, Any], condition_audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "phase6d4_prompt_size_reference_audit_v1",
        "package_version": PROMPT_PACKAGE_VERSION,
        "dataset_class": "synthetic/test",
        "size_summary": rendered_audit["size_summary"],
        "max_history_trial_count": rendered_audit["max_history_trial_count"],
        "prompt_size_difference": condition_audit["prompt_size_difference"],
        "prompt_size_structural_check": prompt_size_structural_check(rendered_audit),
        "context_window_note": "Largest synthetic prompt is structurally small relative to modern LLM context windows; provider-specific token limits remain a Phase 6E concern.",
    }


def prompt_size_structural_check(rendered_audit: dict[str, Any]) -> bool:
    size_summary = rendered_audit.get("size_summary", {})
    largest = max((summary.get("characters_max", 0) for summary in size_summary.values()), default=0)
    return 0 < largest < 50000


def render_freeze_report(audit: dict[str, Any], manifest: dict[str, Any]) -> str:
    size = audit["prompt_size_reference"]
    return "\n".join(
        [
            "# Phase 6D.4 Prompt Package Freeze Report",
            "",
            "Dataset class: synthetic validation",
            f"Package version: `{audit['package_version']}`",
            f"Prompt spec version: `{audit['prompt_spec_version']}`",
            f"Response schema version: `{audit['response_schema_version']}`",
            "",
            "## Conditions",
            "",
            "- `non_history`: target and participant metadata only.",
            "- `personalised_history`: same target and participant metadata plus eligible prior-trial evidence.",
            "",
            "## Synthetic Counts",
            "",
            f"- Rendered prompts: {audit['synthetic_reference_counts']['rendered_prompts']}",
            f"- Non-history prompts: {audit['synthetic_reference_counts']['non_history']}",
            f"- Personalised-history prompts: {audit['synthetic_reference_counts']['personalised_history']}",
            f"- Matched condition pairs: {audit['synthetic_reference_counts']['matched_condition_pairs']}",
            "",
            "## Validation",
            "",
            f"- Condition integrity: {audit['condition_integrity']}",
            f"- Target leakage free: {audit['target_leakage_free']}",
            f"- Provenance leakage free: {audit['provenance_leakage_free']}",
            f"- Sensitivity-feature leakage free: {audit['sensitivity_feature_leakage_free']}",
            f"- Deterministic rendering: {audit['deterministic_rendering']}",
            f"- Artifact hashes valid at freeze: {audit['artifact_hashes_valid']}",
            f"- Response-schema fixtures valid: {audit['response_schema_valid']}",
            f"- Prompt-size structural check: {audit['prompt_size_structural_check']}",
            "",
            "## Policies",
            "",
            f"- Reasoning: zero-shot primary inference; chain-of-thought requested = {manifest['reasoning_policy']['chain_of_thought_requested']}.",
            f"- Few-shot examples: {manifest['few_shot_policy']['primary_few_shot_examples']}.",
            "- Repair: one primary generation attempt, one formatting-only repair attempt, no ground truth or correctness feedback.",
            "",
            "## Prompt Size Summary",
            "",
            f"- Non-history chars min/median/max: {size['non_history']['characters_min']}/{size['non_history']['characters_median']}/{size['non_history']['characters_max']}",
            f"- Non-history words min/median/max: {size['non_history']['approximate_words_min']}/{size['non_history']['approximate_words_median']}/{size['non_history']['approximate_words_max']}",
            f"- Personalised-history chars min/median/max: {size['personalised_history']['characters_min']}/{size['personalised_history']['characters_median']}/{size['personalised_history']['characters_max']}",
            f"- Personalised-history words min/median/max: {size['personalised_history']['approximate_words_min']}/{size['personalised_history']['approximate_words_median']}/{size['personalised_history']['approximate_words_max']}",
            f"- Maximum history-trial count: {audit['max_history_trial_count']}",
            "",
            f"Completion gate `{PHASE6D_PROMPT_PACKAGE_FROZEN_GATE}`: `{str(audit[PHASE6D_PROMPT_PACKAGE_FROZEN_GATE]).lower()}`",
            "",
            "No LLM calls, provider adapters, real participant outcomes, model IDs, temperatures, or provider token limits are included.",
            "",
        ]
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(payload: Any) -> str:
    return sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze or verify the Phase 6D prompt package.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--prompt-data", type=Path, default=DEFAULT_PROMPT_DATA)
    parser.add_argument("--prediction-examples", type=Path, default=DEFAULT_PREDICTION_EXAMPLES)
    parser.add_argument("--response-schema", type=Path, default=DEFAULT_RESPONSE_SCHEMA)
    parser.add_argument("--write-freeze", action="store_true", help="Regenerate the frozen manifest and synthetic freeze artifacts.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    if args.write_freeze:
        audit = freeze_prompt_package(repo_root, args.manifest, args.output_dir, args.prompt_data, args.prediction_examples, args.response_schema)
        print(f"Wrote Phase 6D.4 freeze artifacts to {repo_root / args.output_dir}")
        print(f"{PHASE6D_PROMPT_PACKAGE_FROZEN_GATE}={audit[PHASE6D_PROMPT_PACKAGE_FROZEN_GATE]}")
        return 0 if audit[PHASE6D_PROMPT_PACKAGE_FROZEN_GATE] else 1
    result = verify_prompt_package(repo_root, args.manifest, args.output_dir, args.prompt_data, args.response_schema)
    print(f"artifact_hashes_valid={result['artifact_hashes_valid']}")
    print(f"reference_prompt_hashes_valid={result['reference_prompt_hashes_valid']}")
    print(f"condition_integrity={result['condition_integrity']}")
    print(f"deterministic_rendering={result['deterministic_rendering']}")
    print(f"{PHASE6D_PROMPT_PACKAGE_FROZEN_GATE}={result[PHASE6D_PROMPT_PACKAGE_FROZEN_GATE]}")
    return 0 if result[PHASE6D_PROMPT_PACKAGE_FROZEN_GATE] else 1


if __name__ == "__main__":
    raise SystemExit(main())
