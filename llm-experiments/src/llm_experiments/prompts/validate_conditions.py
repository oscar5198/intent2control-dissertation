"""Phase 6D.3 experimental-condition integrity validation."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from llm_experiments.prompts.prompt_spec import (
    CONDITIONS,
    EXPECTED_LABELS,
    FORMAT_REPAIR_INSTRUCTION,
    MISSING_VALUE,
    PROMPT_SPEC_VERSION,
    RESPONSE_SCHEMA_VERSION,
    SYSTEM_INSTRUCTION,
    load_jsonl,
    render_sections,
    write_json,
)
from llm_experiments.prompts.render import (
    RENDERED_PROMPT_SCHEMA_VERSION,
    render_format_repair,
)


INTEGRITY_SCHEMA_VERSION = "phase6d3_condition_integrity_v1"
PAIR_VALIDATION_COLUMNS = [
    "prediction_example_id",
    "pair_complete",
    "system_equal",
    "task_equal",
    "metadata_equal",
    "context_equal",
    "target_candidates_equal",
    "acoustic_guide_equal",
    "output_instructions_equal",
    "history_difference_only",
    "history_source_correct",
    "comment_boundary_valid",
    "target_leakage_detected",
    "identifier_leakage_detected",
    "sensitivity_feature_leakage_detected",
    "non_history_contamination_detected",
    "history_target_overlap_detected",
    "schema_version_valid",
    "repair_prompt_valid",
    "pair_valid",
    "non_history_characters",
    "personalised_history_characters",
    "character_difference",
    "non_history_words",
    "personalised_history_words",
    "word_difference",
    "history_trial_count",
    "failure_codes",
]

ERROR_CODES = {
    "PAIR_MISSING_NON_HISTORY",
    "PAIR_MISSING_PERSONALISED_HISTORY",
    "PAIR_DUPLICATE_CONDITION",
    "PAIR_UNEXPECTED_CONDITION",
    "PAIR_PREDICTION_EXAMPLE_MISMATCH",
    "VERSION_PROMPT_SPEC_MISMATCH",
    "VERSION_RESPONSE_SCHEMA_MISMATCH",
    "VERSION_RENDERED_SCHEMA_MISMATCH",
    "SYSTEM_MISMATCH",
    "TASK_MISMATCH",
    "METADATA_MISMATCH",
    "CONTEXT_MISMATCH",
    "TARGET_CANDIDATE_MISMATCH",
    "ACOUSTIC_GUIDE_MISMATCH",
    "OUTPUT_INSTRUCTION_MISMATCH",
    "UNEXPECTED_SECTION_DIFFERENCE",
    "TARGET_LEAKAGE",
    "IDENTIFIER_PROVENANCE_LEAKAGE",
    "SENSITIVITY_FEATURE_LEAKAGE",
    "NON_HISTORY_CONTAMINATION",
    "HISTORY_TARGET_OVERLAP",
    "HISTORY_SOURCE_MISMATCH",
    "COMMENT_BOUNDARY_FAILURE",
    "REPAIR_PROMPT_LEAKAGE",
}

DIRECT_TARGET_OUTCOME_TOKENS = [
    "Target rating",
    "Target human rating",
    "Target comparative comment",
    "human_rating",
    "observed_rank",
    "observed_ranks",
    "observed_preferred_set",
    "observed_preferred_mix",
    "observed_max_rating",
    "is_single_winner",
    "n_preferred_tied",
    "is_observed_preferred",
    "ground_truth",
]
IDENTIFIER_TOKENS = [
    "stimulus_id",
    "actual_mix_id",
    "audio_path",
    "acoustic_feature_table_used",
    ".wav",
]
SENSITIVITY_TOKENS = ["z_SI", "z_SI_role"]


def build_condition_integrity_report(
    rendered_prompts_jsonl: Path,
    prompt_data_jsonl: Path,
    output_dir: Path,
    prediction_examples_jsonl: Path | None = None,
) -> dict[str, Any]:
    rendered = load_jsonl(rendered_prompts_jsonl)
    prompt_data = load_jsonl(prompt_data_jsonl)
    prediction_examples = load_jsonl(prediction_examples_jsonl) if prediction_examples_jsonl else []
    records = validate_all_pairs(rendered, prompt_data, prediction_examples)
    audit = build_global_audit(records, rendered, prompt_data)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "condition_pair_validation.csv", records, PAIR_VALIDATION_COLUMNS)
    write_json(output_dir / "condition_pair_validation.json", {"schema_version": INTEGRITY_SCHEMA_VERSION, "records": records})
    write_json(output_dir / "condition_integrity_audit.json", audit)
    (output_dir / "condition_integrity_summary.md").write_text(render_summary(audit), encoding="utf-8")
    return audit


def validate_all_pairs(
    rendered_prompts: list[dict[str, Any]],
    prompt_data_objects: list[dict[str, Any]],
    prediction_examples: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rendered_by_example = group_by_example_condition(rendered_prompts)
    prompt_data_by_example = group_by_example_condition(prompt_data_objects)
    example_truth = {row["prediction_example_id"]: row for row in prediction_examples or []}
    records: list[dict[str, Any]] = []
    for prediction_example_id in sorted(prompt_data_by_example):
        source_pair = prompt_data_by_example[prediction_example_id]
        rendered_pair = rendered_by_example.get(prediction_example_id, {})
        history_available = any(
            bool(obj.get("pipeline_metadata", {}).get("personalised_history_available"))
            for rows in source_pair.values()
            for obj in rows
        )
        records.append(validate_pair(prediction_example_id, rendered_pair, source_pair, history_available, example_truth.get(prediction_example_id)))
    for prediction_example_id in sorted(set(rendered_by_example) - set(prompt_data_by_example)):
        records.append(make_empty_failure_record(prediction_example_id, ["PAIR_PREDICTION_EXAMPLE_MISMATCH"]))
    return records


def validate_pair(
    prediction_example_id: str,
    rendered_pair: dict[str, list[dict[str, Any]]],
    source_pair: dict[str, list[dict[str, Any]]],
    history_available: bool,
    prediction_example: dict[str, Any] | None = None,
) -> dict[str, Any]:
    codes: list[str] = []
    add_pair_completeness_codes(rendered_pair, source_pair, history_available, codes)
    non_rendered = first_or_none(rendered_pair.get("non_history", []))
    hist_rendered = first_or_none(rendered_pair.get("personalised_history", []))
    non_source = first_or_none(source_pair.get("non_history", []))
    hist_source = first_or_none(source_pair.get("personalised_history", []))

    if not history_available:
        return record_for_unavailable_history(prediction_example_id, non_rendered, non_source, codes)
    if not non_rendered or not hist_rendered or not non_source or not hist_source:
        return make_empty_failure_record(prediction_example_id, codes)

    non_sections = extract_user_sections(user_message(non_rendered))
    hist_sections = extract_user_sections(user_message(hist_rendered))
    expected_non_sections = section_map(non_source)
    expected_hist_sections = section_map(hist_source)

    if non_rendered.get("prediction_example_id") != hist_rendered.get("prediction_example_id"):
        codes.append("PAIR_PREDICTION_EXAMPLE_MISMATCH")
    schema_version_valid = validate_versions(non_rendered, codes) and validate_versions(hist_rendered, codes)
    system_equal = non_rendered["messages"][0]["content"] == hist_rendered["messages"][0]["content"] == SYSTEM_INSTRUCTION
    if not system_equal:
        codes.append("SYSTEM_MISMATCH")
    task_equal = sections_equal(non_sections, hist_sections, expected_non_sections, expected_hist_sections, "Task")
    metadata_equal = sections_equal(non_sections, hist_sections, expected_non_sections, expected_hist_sections, "Participant information")
    context_equal = sections_equal(non_sections, hist_sections, expected_non_sections, expected_hist_sections, "Target listening situation")
    candidates_equal = sections_equal(non_sections, hist_sections, expected_non_sections, expected_hist_sections, "Target candidate mixes") and target_candidates_match_source(hist_sections, hist_source)
    acoustic_equal = sections_equal(non_sections, hist_sections, expected_non_sections, expected_hist_sections, "Acoustic feature guide")
    output_equal = sections_equal(non_sections, hist_sections, expected_non_sections, expected_hist_sections, "Prediction/output instructions")
    section_checks = [
        (task_equal, "TASK_MISMATCH"),
        (metadata_equal, "METADATA_MISMATCH"),
        (context_equal, "CONTEXT_MISMATCH"),
        (candidates_equal, "TARGET_CANDIDATE_MISMATCH"),
        (acoustic_equal, "ACOUSTIC_GUIDE_MISMATCH"),
        (output_equal, "OUTPUT_INSTRUCTION_MISMATCH"),
    ]
    for passed, code in section_checks:
        if not passed:
            codes.append(code)
    history_difference_only = set(hist_sections) == set(non_sections) | {"Previous listening evidence from this participant"}
    if not history_difference_only:
        codes.append("UNEXPECTED_SECTION_DIFFERENCE")
    history_source_correct = hist_sections.get("Previous listening evidence from this participant") == expected_hist_sections.get("Previous listening evidence from this participant")
    if not history_source_correct:
        codes.append("HISTORY_SOURCE_MISMATCH")
    comment_boundary_valid = validate_comment_boundary(hist_sections, hist_source)
    if not comment_boundary_valid:
        codes.append("COMMENT_BOUNDARY_FAILURE")
    leakage = validate_prompt_leakage(non_rendered, hist_rendered, non_source, hist_source, prediction_example)
    codes.extend(leakage["codes"])
    repair_prompt_valid = validate_repair_prompt(render_format_repair('{"bad":true}', response_schema()), codes)
    sizes = pair_sizes(non_rendered, hist_rendered, hist_source)
    codes = sorted(set(codes))
    return {
        "prediction_example_id": prediction_example_id,
        "pair_complete": not any(code.startswith("PAIR_") for code in codes),
        "system_equal": system_equal,
        "task_equal": task_equal,
        "metadata_equal": metadata_equal,
        "context_equal": context_equal,
        "target_candidates_equal": candidates_equal,
        "acoustic_guide_equal": acoustic_equal,
        "output_instructions_equal": output_equal,
        "history_difference_only": history_difference_only,
        "history_source_correct": history_source_correct,
        "comment_boundary_valid": comment_boundary_valid,
        "target_leakage_detected": "TARGET_LEAKAGE" in codes,
        "identifier_leakage_detected": "IDENTIFIER_PROVENANCE_LEAKAGE" in codes,
        "sensitivity_feature_leakage_detected": "SENSITIVITY_FEATURE_LEAKAGE" in codes,
        "non_history_contamination_detected": "NON_HISTORY_CONTAMINATION" in codes,
        "history_target_overlap_detected": "HISTORY_TARGET_OVERLAP" in codes,
        "schema_version_valid": schema_version_valid,
        "repair_prompt_valid": repair_prompt_valid,
        "pair_valid": not codes,
        **sizes,
        "failure_codes": json.dumps(codes, separators=(",", ":")),
    }


def add_pair_completeness_codes(
    rendered_pair: dict[str, list[dict[str, Any]]],
    source_pair: dict[str, list[dict[str, Any]]],
    history_available: bool,
    codes: list[str],
) -> None:
    for condition in rendered_pair:
        if condition not in CONDITIONS:
            codes.append("PAIR_UNEXPECTED_CONDITION")
    if len(rendered_pair.get("non_history", [])) == 0:
        codes.append("PAIR_MISSING_NON_HISTORY")
    if len(rendered_pair.get("non_history", [])) > 1:
        codes.append("PAIR_DUPLICATE_CONDITION")
    if history_available and len(rendered_pair.get("personalised_history", [])) == 0:
        codes.append("PAIR_MISSING_PERSONALISED_HISTORY")
    if len(rendered_pair.get("personalised_history", [])) > 1:
        codes.append("PAIR_DUPLICATE_CONDITION")
    if "non_history" not in source_pair:
        codes.append("PAIR_MISSING_NON_HISTORY")
    if history_available and "personalised_history" not in source_pair:
        codes.append("PAIR_MISSING_PERSONALISED_HISTORY")


def record_for_unavailable_history(
    prediction_example_id: str,
    non_rendered: dict[str, Any] | None,
    non_source: dict[str, Any] | None,
    codes: list[str],
) -> dict[str, Any]:
    if non_rendered and validate_versions(non_rendered, codes) and non_source:
        non_sections = extract_user_sections(user_message(non_rendered))
        expected = section_map(non_source)
        if "Previous listening evidence from this participant" in non_sections:
            codes.append("NON_HISTORY_CONTAMINATION")
        for heading, body in expected.items():
            if non_sections.get(heading) != body:
                codes.append("UNEXPECTED_SECTION_DIFFERENCE")
    codes = sorted(set(codes))
    return {
        "prediction_example_id": prediction_example_id,
        "pair_complete": "PAIR_MISSING_NON_HISTORY" not in codes,
        "system_equal": True,
        "task_equal": True,
        "metadata_equal": True,
        "context_equal": True,
        "target_candidates_equal": True,
        "acoustic_guide_equal": True,
        "output_instructions_equal": True,
        "history_difference_only": True,
        "history_source_correct": True,
        "comment_boundary_valid": True,
        "target_leakage_detected": "TARGET_LEAKAGE" in codes,
        "identifier_leakage_detected": "IDENTIFIER_PROVENANCE_LEAKAGE" in codes,
        "sensitivity_feature_leakage_detected": "SENSITIVITY_FEATURE_LEAKAGE" in codes,
        "non_history_contamination_detected": "NON_HISTORY_CONTAMINATION" in codes,
        "history_target_overlap_detected": False,
        "schema_version_valid": not any(code.startswith("VERSION_") for code in codes),
        "repair_prompt_valid": True,
        "pair_valid": not codes,
        "non_history_characters": len(user_message(non_rendered)) if non_rendered else 0,
        "personalised_history_characters": 0,
        "character_difference": 0,
        "non_history_words": word_count(user_message(non_rendered)) if non_rendered else 0,
        "personalised_history_words": 0,
        "word_difference": 0,
        "history_trial_count": 0,
        "failure_codes": json.dumps(codes, separators=(",", ":")),
    }


def make_empty_failure_record(prediction_example_id: str, codes: list[str]) -> dict[str, Any]:
    codes = sorted(set(codes))
    return {
        "prediction_example_id": prediction_example_id,
        "pair_complete": False,
        "system_equal": False,
        "task_equal": False,
        "metadata_equal": False,
        "context_equal": False,
        "target_candidates_equal": False,
        "acoustic_guide_equal": False,
        "output_instructions_equal": False,
        "history_difference_only": False,
        "history_source_correct": False,
        "comment_boundary_valid": False,
        "target_leakage_detected": "TARGET_LEAKAGE" in codes,
        "identifier_leakage_detected": "IDENTIFIER_PROVENANCE_LEAKAGE" in codes,
        "sensitivity_feature_leakage_detected": "SENSITIVITY_FEATURE_LEAKAGE" in codes,
        "non_history_contamination_detected": "NON_HISTORY_CONTAMINATION" in codes,
        "history_target_overlap_detected": "HISTORY_TARGET_OVERLAP" in codes,
        "schema_version_valid": not any(code.startswith("VERSION_") for code in codes),
        "repair_prompt_valid": True,
        "pair_valid": False,
        "non_history_characters": 0,
        "personalised_history_characters": 0,
        "character_difference": 0,
        "non_history_words": 0,
        "personalised_history_words": 0,
        "word_difference": 0,
        "history_trial_count": 0,
        "failure_codes": json.dumps(codes, separators=(",", ":")),
    }


def validate_versions(rendered: dict[str, Any], codes: list[str]) -> bool:
    valid = True
    if rendered.get("schema_version") != RENDERED_PROMPT_SCHEMA_VERSION:
        codes.append("VERSION_RENDERED_SCHEMA_MISMATCH")
        valid = False
    if rendered.get("prompt_spec_version") != PROMPT_SPEC_VERSION:
        codes.append("VERSION_PROMPT_SPEC_MISMATCH")
        valid = False
    if rendered.get("response_schema_version") != RESPONSE_SCHEMA_VERSION:
        codes.append("VERSION_RESPONSE_SCHEMA_MISMATCH")
        valid = False
    return valid


def validate_prompt_leakage(
    non_rendered: dict[str, Any],
    hist_rendered: dict[str, Any],
    non_source: dict[str, Any],
    hist_source: dict[str, Any],
    prediction_example: dict[str, Any] | None,
) -> dict[str, Any]:
    codes: list[str] = []
    non_text = full_prompt_text(non_rendered)
    hist_text = full_prompt_text(hist_rendered)
    for text in [non_text, hist_text]:
        if any(token in text for token in DIRECT_TARGET_OUTCOME_TOKENS):
            codes.append("TARGET_LEAKAGE")
        if any(token in text for token in IDENTIFIER_TOKENS):
            codes.append("IDENTIFIER_PROVENANCE_LEAKAGE")
        if any(token in text for token in SENSITIVITY_TOKENS):
            codes.append("SENSITIVITY_FEATURE_LEAKAGE")
    if "Participant rating:" in non_text or "Participant comparative comment:" in non_text or "Previous listening evidence from this participant" in non_text:
        codes.append("NON_HISTORY_CONTAMINATION")
    target = non_source["model_input"]["target"]
    for value in collect_disallowed_source_identifiers(non_source, hist_source):
        if value and (str(value) in non_text or str(value) in hist_text):
            codes.append("IDENTIFIER_PROVENANCE_LEAKAGE")
    if prediction_example:
        ground_truth = prediction_example.get("ground_truth", {})
        for rating in ground_truth.get("human_ratings", {}).values():
            if f"Participant rating: {rating}" in hist_text and history_target_like_source(hist_source, target):
                codes.append("TARGET_LEAKAGE")
        target_comment = prediction_example.get("ground_truth", {}).get("comparative_comment")
        if target_comment and target_comment in hist_text:
            codes.append("TARGET_LEAKAGE")
    if history_target_like_source(hist_source, target):
        codes.append("HISTORY_TARGET_OVERLAP")
    return {"codes": sorted(set(codes))}


def collect_disallowed_source_identifiers(non_source: dict[str, Any], hist_source: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for trial in [non_source["model_input"]["target"], hist_source["model_input"]["target"], *hist_source.get("model_input", {}).get("history", [])]:
        song = trial.get("song", {})
        for key in ["song_title", "song_id", "excerpt_id"]:
            if song.get(key):
                values.append(str(song[key]))
    return sorted(set(values))


def history_target_like_source(hist_source: dict[str, Any], target: dict[str, Any]) -> bool:
    target_signature = comparable_trial_signature(target)
    return any(comparable_trial_signature(trial) == target_signature for trial in hist_source.get("model_input", {}).get("history", []))


def comparable_trial_signature(trial: dict[str, Any]) -> dict[str, Any]:
    return {
        "context": trial.get("context", {}),
        "song": {"participant_song_label": trial.get("song", {}).get("participant_song_label")},
        "candidates": [
            {
                "label": candidate.get("label"),
                "acoustic_features": candidate.get("acoustic_features"),
            }
            for candidate in sorted(trial.get("candidates", []), key=lambda row: EXPECTED_LABELS.index(str(row.get("label", "A"))))
        ],
    }


def validate_comment_boundary(hist_sections: dict[str, str], hist_source: dict[str, Any]) -> bool:
    history = hist_source.get("model_input", {}).get("history", [])
    section = hist_sections.get("Previous listening evidence from this participant", "")
    for trial in history:
        expected = f"Participant comparative comment: {render_value_for_validation(trial.get('comparative_comment'))}"
        if expected not in section:
            return False
    return "### System" not in section and '"role":"system"' not in section and '"role": "system"' not in section


def validate_repair_prompt(repair_prompt: dict[str, Any], codes: list[str]) -> bool:
    text = "\n".join(message.get("content", "") for message in repair_prompt.get("messages", []))
    prohibited = [
        "SYNTHETIC_PHASE6B1",
        "Target listening situation",
        "Previous listening evidence",
        "Participant rating:",
        "Participant comparative comment:",
        "ground_truth",
        "correct answer",
        "should choose",
    ]
    valid = FORMAT_REPAIR_INSTRUCTION in text and RESPONSE_SCHEMA_VERSION in text and not any(token in text for token in prohibited)
    if not valid:
        codes.append("REPAIR_PROMPT_LEAKAGE")
    return valid


def target_candidates_match_source(sections: dict[str, str], source: dict[str, Any]) -> bool:
    expected = section_map(source).get("Target candidate mixes", "")
    actual = sections.get("Target candidate mixes", "")
    return actual == expected


def sections_equal(
    non_sections: dict[str, str],
    hist_sections: dict[str, str],
    expected_non: dict[str, str],
    expected_hist: dict[str, str],
    heading: str,
) -> bool:
    return non_sections.get(heading) == hist_sections.get(heading) == expected_non.get(heading) == expected_hist.get(heading)


def section_map(source_obj: dict[str, Any]) -> dict[str, str]:
    return {section["heading"]: section["body"] for section in render_sections(source_obj["model_input"], source_obj["condition"])}


def extract_user_sections(user: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current: str | None = None
    lines: list[str] = []
    for line in user.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(lines).strip()
            current = line[3:].strip()
            lines = []
        elif current is not None:
            lines.append(line)
    if current is not None:
        sections[current] = "\n".join(lines).strip()
    return sections


def pair_sizes(non_rendered: dict[str, Any], hist_rendered: dict[str, Any], hist_source: dict[str, Any]) -> dict[str, int]:
    non_user = user_message(non_rendered)
    hist_user = user_message(hist_rendered)
    return {
        "non_history_characters": len(non_user),
        "personalised_history_characters": len(hist_user),
        "character_difference": len(hist_user) - len(non_user),
        "non_history_words": word_count(non_user),
        "personalised_history_words": word_count(hist_user),
        "word_difference": word_count(hist_user) - word_count(non_user),
        "history_trial_count": len(hist_source.get("model_input", {}).get("history", [])),
    }


def build_global_audit(records: list[dict[str, Any]], rendered: list[dict[str, Any]], prompt_data: list[dict[str, Any]]) -> dict[str, Any]:
    code_counts = Counter(code for record in records for code in json.loads(record["failure_codes"]))
    differences = [int(record["character_difference"]) for record in records if record["personalised_history_characters"]]
    word_differences = [int(record["word_difference"]) for record in records if record["personalised_history_words"]]
    audit = {
        "schema_version": INTEGRITY_SCHEMA_VERSION,
        "prompt_spec_version": PROMPT_SPEC_VERSION,
        "response_schema_version": RESPONSE_SCHEMA_VERSION,
        "rendered_schema_version": RENDERED_PROMPT_SCHEMA_VERSION,
        "prompt_data_objects_read": len(prompt_data),
        "rendered_prompts_read": len(rendered),
        "matched_pair_count": sum(1 for record in records if record["personalised_history_characters"]),
        "valid_pair_count": sum(1 for record in records if record["pair_valid"]),
        "non_history_prompt_count": sum(1 for row in rendered if row.get("condition") == "non_history"),
        "personalised_history_prompt_count": sum(1 for row in rendered if row.get("condition") == "personalised_history"),
        "pair_equivalence_failures": count_records_with_codes(records, ["SYSTEM_MISMATCH", "TASK_MISMATCH", "METADATA_MISMATCH", "CONTEXT_MISMATCH", "TARGET_CANDIDATE_MISMATCH", "ACOUSTIC_GUIDE_MISMATCH", "OUTPUT_INSTRUCTION_MISMATCH", "UNEXPECTED_SECTION_DIFFERENCE"]),
        "target_leakage_failures": count_records_with_codes(records, ["TARGET_LEAKAGE"]),
        "identifier_provenance_leakage_failures": count_records_with_codes(records, ["IDENTIFIER_PROVENANCE_LEAKAGE"]),
        "sensitivity_feature_leakage_failures": count_records_with_codes(records, ["SENSITIVITY_FEATURE_LEAKAGE"]),
        "non_history_contamination_failures": count_records_with_codes(records, ["NON_HISTORY_CONTAMINATION"]),
        "history_target_overlap_failures": count_records_with_codes(records, ["HISTORY_TARGET_OVERLAP"]),
        "history_source_correctness_failures": count_records_with_codes(records, ["HISTORY_SOURCE_MISMATCH"]),
        "comment_boundary_failures": count_records_with_codes(records, ["COMMENT_BOUNDARY_FAILURE"]),
        "repair_prompt_failures": count_records_with_codes(records, ["REPAIR_PROMPT_LEAKAGE"]),
        "schema_version_failures": count_records_with_prefix(records, "VERSION_"),
        "deterministic_audit_passed": records == validate_all_pairs(rendered, prompt_data, []),
        "prompt_size_difference": summarize_differences(differences, word_differences),
        "failure_code_counts": dict(sorted(code_counts.items())),
        "EXPERIMENTAL_CONDITION_INTEGRITY": False,
        "contains_llm_responses": False,
        "contains_ground_truth": False,
        "contains_provider_specific_transport": False,
        "length_balancing_policy": "No artificial length balancing; personalised-history prompts are longer because the manipulation adds prior participant evidence.",
    }
    audit["EXPERIMENTAL_CONDITION_INTEGRITY"] = (
        audit["matched_pair_count"] > 0
        and audit["valid_pair_count"] == audit["matched_pair_count"]
        and not audit["failure_code_counts"]
    )
    return audit


def summarize_differences(characters: list[int], words: list[int]) -> dict[str, Any]:
    if not characters:
        return {
            "character_difference_min": 0,
            "character_difference_median": 0,
            "character_difference_max": 0,
            "word_difference_min": 0,
            "word_difference_median": 0,
            "word_difference_max": 0,
        }
    return {
        "character_difference_min": min(characters),
        "character_difference_median": statistics.median(characters),
        "character_difference_max": max(characters),
        "word_difference_min": min(words),
        "word_difference_median": statistics.median(words),
        "word_difference_max": max(words),
    }


def render_summary(audit: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Phase 6D.3 Experimental Condition Integrity Summary",
            "",
            "Dataset class: synthetic/test",
            f"Prompt spec version: `{audit['prompt_spec_version']}`",
            f"Response schema version: `{audit['response_schema_version']}`",
            "",
            "## Counts",
            "",
            f"- Rendered prompts read: {audit['rendered_prompts_read']}",
            f"- Matched pairs: {audit['matched_pair_count']}",
            f"- Valid pairs: {audit['valid_pair_count']}",
            f"- Non-history prompts: {audit['non_history_prompt_count']}",
            f"- Personalised-history prompts: {audit['personalised_history_prompt_count']}",
            "",
            "## Validation",
            "",
            f"- Pair-equivalence failures: {audit['pair_equivalence_failures']}",
            f"- Target leakage failures: {audit['target_leakage_failures']}",
            f"- Identifier/provenance leakage failures: {audit['identifier_provenance_leakage_failures']}",
            f"- Sensitivity-feature leakage failures: {audit['sensitivity_feature_leakage_failures']}",
            f"- Non-history contamination failures: {audit['non_history_contamination_failures']}",
            f"- History target-overlap failures: {audit['history_target_overlap_failures']}",
            f"- History-source correctness failures: {audit['history_source_correctness_failures']}",
            f"- Comment-boundary failures: {audit['comment_boundary_failures']}",
            f"- Repair-prompt failures: {audit['repair_prompt_failures']}",
            f"- Deterministic audit passed: {audit['deterministic_audit_passed']}",
            f"- `EXPERIMENTAL_CONDITION_INTEGRITY`: `{str(audit['EXPERIMENTAL_CONDITION_INTEGRITY']).lower()}`",
            "",
            "No LLM calls, provider adapters, prompt alternatives, ground-truth scoring, or performance metrics are included.",
            "",
        ]
    )


def response_schema() -> dict[str, Any]:
    return {
        "$id": RESPONSE_SCHEMA_VERSION,
        "required": ["predicted_preferred_mix", "predicted_ratings", "predicted_ranking"],
    }


def group_by_example_condition(rows: list[dict[str, Any]]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[str(row.get("prediction_example_id", ""))][str(row.get("condition", ""))].append(row)
    return grouped


def first_or_none(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return rows[0] if rows else None


def user_message(rendered: dict[str, Any] | None) -> str:
    if not rendered:
        return ""
    return next((message["content"] for message in rendered.get("messages", []) if message.get("role") == "user"), "")


def full_prompt_text(rendered: dict[str, Any]) -> str:
    return "\n".join(message.get("content", "") for message in rendered.get("messages", []))


def word_count(text: str) -> int:
    return len([part for part in text.split() if part])


def render_value_for_validation(value: Any) -> str:
    return MISSING_VALUE if value is None or value == "" else str(value)


def count_records_with_codes(records: list[dict[str, Any]], codes: list[str]) -> int:
    wanted = set(codes)
    return sum(1 for record in records if wanted & set(json.loads(record["failure_codes"])))


def count_records_with_prefix(records: list[dict[str, Any]], prefix: str) -> int:
    return sum(1 for record in records if any(code.startswith(prefix) for code in json.loads(record["failure_codes"])))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Phase 6D.3 experimental-condition integrity.")
    parser.add_argument("--rendered-prompts", required=True, type=Path)
    parser.add_argument("--prompt-data", required=True, type=Path)
    parser.add_argument("--prediction-examples", type=Path, default=None)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit = build_condition_integrity_report(args.rendered_prompts, args.prompt_data, args.output_dir, args.prediction_examples)
    print(f"Wrote condition validation outputs to {args.output_dir}")
    print(f"matched_pair_count={audit['matched_pair_count']}")
    print(f"valid_pair_count={audit['valid_pair_count']}")
    print(f"pair_equivalence_failures={audit['pair_equivalence_failures']}")
    print(f"target_leakage_failures={audit['target_leakage_failures']}")
    print(f"identifier_provenance_leakage_failures={audit['identifier_provenance_leakage_failures']}")
    print(f"sensitivity_feature_leakage_failures={audit['sensitivity_feature_leakage_failures']}")
    print(f"EXPERIMENTAL_CONDITION_INTEGRITY={audit['EXPERIMENTAL_CONDITION_INTEGRITY']}")
    return 0 if audit["EXPERIMENTAL_CONDITION_INTEGRITY"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
