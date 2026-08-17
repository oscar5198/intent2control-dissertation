"""Phase 6D.2 deterministic model-agnostic prompt renderer."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from llm_experiments.prompts.prompt_spec import (
    CONDITIONS,
    EXPECTED_LABELS,
    FORMAT_REPAIR_INSTRUCTION,
    FORBIDDEN_RENDERED_SUBSTRINGS,
    OUTPUT_INSTRUCTIONS,
    PROMPT_SPEC_VERSION,
    RESPONSE_SCHEMA_VERSION,
    SYSTEM_INSTRUCTION,
    load_jsonl,
    prompt_size,
    render_condition_prompt,
    render_feature_guide,
    render_sections,
    render_value,
    validate_rendered_prompt_no_leakage,
    write_json,
)


RENDERED_PROMPT_SCHEMA_VERSION = "phase6d2_rendered_prompt_v1"
RENDERED_PROMPT_DATASET_VERSION = "phase6d2_rendered_prompt_dataset_v1"
RENDERED_PROMPT_ID_SEPARATOR = "__"
FORBIDDEN_MODEL_INPUT_KEYS = {
    "ground_truth",
    "stimulus_id",
    "actual_mix_id",
    "audio_path",
    "acoustic_feature_table_used",
    "z_SI",
    "z_SI_role",
    "observed_rank",
    "observed_ranks",
    "observed_preferred_set",
    "observed_preferred_mix",
    "observed_max_rating",
    "is_observed_preferred",
    "is_single_winner",
    "n_preferred_tied",
}
TARGET_FORBIDDEN_KEYS = {
    "human_rating",
    "comparative_comment",
    "observed_rank",
    "observed_ranks",
    "observed_preferred_set",
    "observed_preferred_mix",
    "observed_max_rating",
    "is_observed_preferred",
    "is_single_winner",
    "n_preferred_tied",
    "ground_truth",
}


def render_prompt(condition_object: dict[str, Any], response_schema: dict[str, Any] | None = None) -> dict[str, Any]:
    """Render one Phase 6B.4 condition object into model-agnostic messages."""

    validate_condition_object_for_rendering(condition_object)
    prompt = render_condition_prompt(condition_object)
    rendered = {
        "schema_version": RENDERED_PROMPT_SCHEMA_VERSION,
        "rendered_prompt_id": make_rendered_prompt_id(condition_object["condition_object_id"]),
        "condition_object_id": condition_object["condition_object_id"],
        "prediction_example_id": condition_object["prediction_example_id"],
        "condition": condition_object["condition"],
        "prompt_spec_version": PROMPT_SPEC_VERSION,
        "response_schema_version": RESPONSE_SCHEMA_VERSION,
        "source_prompt_data_schema_version": condition_object.get("schema_version", ""),
        "source_prompt_data_builder_version": condition_object.get("prompt_data_builder_version", ""),
        "messages": [
            render_system_message(),
            render_user_message(prompt["user_message"]),
        ],
    }
    validate_rendered_prompt(condition_object, rendered, response_schema=response_schema)
    return rendered


def make_rendered_prompt_id(condition_object_id: str) -> str:
    return f"{condition_object_id}{RENDERED_PROMPT_ID_SEPARATOR}{PROMPT_SPEC_VERSION}"


def render_system_message() -> dict[str, str]:
    return {"role": "system", "content": SYSTEM_INSTRUCTION}


def render_user_message(content: str) -> dict[str, str]:
    return {"role": "user", "content": content}


def render_format_repair(invalid_output: str, response_schema: dict[str, Any]) -> dict[str, Any]:
    """Render a model-agnostic structural repair prompt without participant evidence."""

    schema_version = str(response_schema.get("$id", RESPONSE_SCHEMA_VERSION))
    content = "\n\n".join(
        [
            FORMAT_REPAIR_INSTRUCTION,
            "Required response schema:",
            json.dumps(response_schema, sort_keys=True, indent=2, ensure_ascii=False),
            "Invalid response to repair:",
            str(invalid_output),
        ]
    )
    return {
        "schema_version": "phase6d2_format_repair_prompt_v1",
        "repair_prompt_id": f"format_repair{RENDERED_PROMPT_ID_SEPARATOR}{schema_version}",
        "response_schema_version": schema_version,
        "messages": [
            {"role": "user", "content": content},
        ],
    }


def validate_condition_object_for_rendering(condition_object: dict[str, Any]) -> None:
    required = ["condition_object_id", "prediction_example_id", "condition", "model_input"]
    missing = [field for field in required if field not in condition_object]
    if missing:
        raise ValueError(f"Condition object missing required renderer fields: {missing}")
    condition = condition_object["condition"]
    if condition not in CONDITIONS:
        raise ValueError(f"Unsupported condition: {condition}")
    if "ground_truth" in condition_object:
        raise ValueError("Renderer input must not contain ground_truth.")
    model_input = condition_object["model_input"]
    forbidden = keys_matching(model_input, FORBIDDEN_MODEL_INPUT_KEYS)
    if forbidden:
        raise ValueError(f"Model input contains forbidden provenance/outcome keys: {sorted(forbidden)}")
    target_forbidden = keys_matching(model_input.get("target", {}), TARGET_FORBIDDEN_KEYS)
    if target_forbidden:
        raise ValueError(f"Target model input contains forbidden target-outcome keys: {sorted(target_forbidden)}")
    validate_candidates(model_input.get("target", {}).get("candidates", []), include_rating=False, context="target")
    if condition == "non_history" and "history" in model_input:
        raise ValueError("non_history model input must not contain history.")
    if condition == "personalised_history":
        history = model_input.get("history")
        if not isinstance(history, list) or not history:
            raise ValueError("personalised_history model input must contain non-empty history.")
        for index, trial in enumerate(history):
            validate_candidates(trial.get("candidates", []), include_rating=True, context=f"history[{index}]")


def validate_candidates(candidates: list[dict[str, Any]], include_rating: bool, context: str) -> None:
    labels = [str(candidate.get("label", "")) for candidate in candidates]
    if sorted(labels) != EXPECTED_LABELS or len(labels) != len(EXPECTED_LABELS):
        raise ValueError(f"{context} candidates must contain exactly A-E.")
    for candidate in candidates:
        features = candidate.get("acoustic_features", {})
        if set(features) != {"z_RMS", "z_CF", "z_SW"}:
            raise ValueError(f"{context} candidate {candidate.get('label')} must contain exactly primary acoustic features.")
        if include_rating and "human_rating" not in candidate:
            raise ValueError(f"{context} candidate {candidate.get('label')} missing history human_rating.")
        if not include_rating and "human_rating" in candidate:
            raise ValueError(f"{context} candidate {candidate.get('label')} must not contain human_rating.")


def validate_rendered_prompt(
    condition_object: dict[str, Any],
    rendered_prompt: dict[str, Any],
    response_schema: dict[str, Any] | None = None,
) -> None:
    if rendered_prompt["prompt_spec_version"] != PROMPT_SPEC_VERSION:
        raise ValueError("Rendered prompt has wrong prompt_spec_version.")
    if rendered_prompt["response_schema_version"] != RESPONSE_SCHEMA_VERSION:
        raise ValueError("Rendered prompt has wrong response_schema_version.")
    if rendered_prompt["messages"] != [render_system_message(), render_user_message(rendered_prompt["messages"][1]["content"])]:
        raise ValueError("Rendered prompt messages must contain system then user roles only.")
    if rendered_prompt["messages"][0]["content"] != SYSTEM_INSTRUCTION:
        raise ValueError("Rendered system instruction does not match frozen specification.")
    text = rendered_prompt["messages"][1]["content"]
    for token in FORBIDDEN_RENDERED_SUBSTRINGS:
        if token in text:
            raise ValueError(f"Rendered prompt contains forbidden token {token!r}.")
    if condition_object["condition"] == "non_history" and ("Participant rating:" in text or "Participant comparative comment:" in text):
        raise ValueError("non_history rendered prompt contains history evidence.")
    if response_schema is not None and response_schema.get("$id") != rendered_prompt["response_schema_version"]:
        raise ValueError("Response schema version does not match rendered prompt linkage.")


def render_prompt_sections(condition_object: dict[str, Any]) -> dict[str, str]:
    validate_condition_object_for_rendering(condition_object)
    sections = render_sections(condition_object["model_input"], condition_object["condition"])
    return {section["heading"]: section["body"] for section in sections}


def validate_condition_pair_equivalence(non_history: dict[str, Any], personalised_history: dict[str, Any]) -> dict[str, Any]:
    non_rendered = render_prompt(non_history)
    hist_rendered = render_prompt(personalised_history)
    non_sections = render_prompt_sections(non_history)
    hist_sections = render_prompt_sections(personalised_history)
    checks = {
        "same_system_message": non_rendered["messages"][0] == hist_rendered["messages"][0],
        "same_target_section": non_sections.get("Target listening situation") == hist_sections.get("Target listening situation"),
        "same_participant_metadata_section": non_sections.get("Participant information") == hist_sections.get("Participant information"),
        "same_acoustic_guide": non_sections.get("Acoustic feature guide") == hist_sections.get("Acoustic feature guide") == render_feature_guide(),
        "same_target_candidates": non_sections.get("Target candidate mixes") == hist_sections.get("Target candidate mixes"),
        "same_output_instructions": non_sections.get("Prediction/output instructions") == hist_sections.get("Prediction/output instructions") == OUTPUT_INSTRUCTIONS,
        "history_section_only_in_personalised_history": "Previous listening evidence from this participant" not in non_sections
        and "Previous listening evidence from this participant" in hist_sections,
    }
    return {"passed": all(checks.values()), "checks": checks}


def render_prompt_dataset(prompt_data_jsonl: Path, output_dir: Path, response_schema_path: Path) -> dict[str, Any]:
    response_schema = json.loads(response_schema_path.read_text(encoding="utf-8"))
    objects = sorted(load_jsonl(prompt_data_jsonl), key=lambda row: str(row["condition_object_id"]))
    rendered: list[dict[str, Any]] = []
    failures: list[str] = []
    leakage_failures: list[str] = []
    for obj in objects:
        try:
            rendered_prompt = render_prompt(obj, response_schema=response_schema)
            rendered.append(rendered_prompt)
        except Exception as exc:
            failures.append(f"{obj.get('condition_object_id', '<missing>')}: {exc}")

    rendered = sorted(rendered, key=lambda row: row["rendered_prompt_id"])
    deterministic_rerun_passed = rendered == sorted(
        [render_prompt(obj, response_schema=response_schema) for obj in objects if obj.get("condition_object_id")],
        key=lambda row: row["rendered_prompt_id"],
    ) if not failures else False

    by_example: dict[str, dict[str, dict[str, Any]]] = {}
    for obj in objects:
        by_example.setdefault(str(obj["prediction_example_id"]), {})[str(obj["condition"])] = obj
    pair_reports = []
    for prediction_example_id, pair in sorted(by_example.items()):
        if "non_history" in pair and "personalised_history" in pair:
            try:
                report = validate_condition_pair_equivalence(pair["non_history"], pair["personalised_history"])
                if not report["passed"]:
                    failures.append(f"{prediction_example_id}: condition-pair equivalence failed.")
                rendered_pair = {
                    "non_history": render_condition_prompt(pair["non_history"]),
                    "personalised_history": render_condition_prompt(pair["personalised_history"]),
                }
                leakage = validate_rendered_prompt_no_leakage(pair["non_history"], pair["personalised_history"], rendered_pair)
                if not leakage["passed"]:
                    leakage_failures.extend(f"{prediction_example_id}: {failure}" for failure in leakage["failures"])
                pair_reports.append({"prediction_example_id": prediction_example_id, **report})
            except Exception as exc:
                failures.append(f"{prediction_example_id}: condition-pair validation failed: {exc}")

    output_dir.mkdir(parents=True, exist_ok=True)
    rendered_path = output_dir / "rendered_prompts.jsonl"
    write_jsonl(rendered_path, rendered)
    schema_version_mismatches = count_schema_version_mismatches(objects, rendered, response_schema)
    write_json(
        output_dir / "rendered_prompt_audit.json",
        build_audit(objects, rendered, failures, leakage_failures, pair_reports, deterministic_rerun_passed, schema_version_mismatches),
    )
    write_matched_pair_markdown(output_dir / "matched_rendered_prompt_pair.md", rendered)
    return json.loads((output_dir / "rendered_prompt_audit.json").read_text(encoding="utf-8"))


def build_audit(
    objects: list[dict[str, Any]],
    rendered: list[dict[str, Any]],
    failures: list[str],
    leakage_failures: list[str],
    pair_reports: list[dict[str, Any]],
    deterministic_rerun_passed: bool,
    schema_version_mismatches: int,
) -> dict[str, Any]:
    condition_counts = Counter(row["condition"] for row in rendered)
    sizes_by_condition: dict[str, list[dict[str, int]]] = {condition: [] for condition in CONDITIONS}
    max_history = 0
    for row in rendered:
        user = next(message["content"] for message in row["messages"] if message["role"] == "user")
        sizes_by_condition[row["condition"]].append(prompt_size(user))
    for obj in objects:
        max_history = max(max_history, len(obj.get("model_input", {}).get("history", [])))
    return {
        "schema_version": RENDERED_PROMPT_DATASET_VERSION,
        "prompt_spec_version": PROMPT_SPEC_VERSION,
        "response_schema_version": RESPONSE_SCHEMA_VERSION,
        "prompt_data_objects_read": len(objects),
        "rendered_prompts_written": len(rendered),
        "non_history_count": condition_counts.get("non_history", 0),
        "personalised_history_count": condition_counts.get("personalised_history", 0),
        "rendering_failures": len(failures),
        "leakage_failures": len(leakage_failures),
        "condition_pair_equivalence_failures": sum(1 for report in pair_reports if not report["passed"]),
        "schema_version_mismatches": schema_version_mismatches,
        "deterministic_rerun_passed": deterministic_rerun_passed,
        "max_history_trial_count": max_history,
        "size_summary": {
            condition: summarize_sizes(sizes)
            for condition, sizes in sizes_by_condition.items()
        },
        "failures": failures,
        "leakage_failure_messages": leakage_failures,
        "condition_pair_reports": pair_reports,
        "contains_llm_responses": False,
        "contains_provider_specific_transport": False,
        "contains_ground_truth": False,
    }


def count_schema_version_mismatches(
    objects: list[dict[str, Any]],
    rendered: list[dict[str, Any]],
    response_schema: dict[str, Any],
) -> int:
    mismatches = 0
    mismatches += sum(1 for obj in objects if obj.get("schema_version") != "phase6b4_prompt_data_objects_v1")
    mismatches += sum(1 for row in rendered if row.get("prompt_spec_version") != PROMPT_SPEC_VERSION)
    mismatches += sum(1 for row in rendered if row.get("response_schema_version") != response_schema.get("$id"))
    return mismatches


def summarize_sizes(sizes: list[dict[str, int]]) -> dict[str, Any]:
    if not sizes:
        return {
            "count": 0,
            "characters_min": 0,
            "characters_median": 0,
            "characters_max": 0,
            "approximate_words_min": 0,
            "approximate_words_median": 0,
            "approximate_words_max": 0,
        }
    characters = [row["characters"] for row in sizes]
    words = [row["approximate_word_count"] for row in sizes]
    return {
        "count": len(sizes),
        "characters_min": min(characters),
        "characters_median": statistics.median(characters),
        "characters_max": max(characters),
        "approximate_words_min": min(words),
        "approximate_words_median": statistics.median(words),
        "approximate_words_max": max(words),
    }


def write_matched_pair_markdown(path: Path, rendered: list[dict[str, Any]]) -> None:
    by_example: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rendered:
        by_example.setdefault(row["prediction_example_id"], {})[row["condition"]] = row
    for prediction_example_id in sorted(by_example):
        pair = by_example[prediction_example_id]
        if "non_history" in pair and "personalised_history" in pair:
            lines = [f"# Matched Rendered Prompt Pair", "", f"Prediction example ID: `{prediction_example_id}`", ""]
            for condition in CONDITIONS:
                prompt = pair[condition]
                lines.extend(
                    [
                        f"## {condition}",
                        "",
                        "### System",
                        "",
                        prompt["messages"][0]["content"],
                        "",
                        "### User",
                        "",
                        prompt["messages"][1]["content"],
                        "",
                    ]
                )
            path.write_text("\n".join(lines), encoding="utf-8")
            return
    path.write_text("# Matched Rendered Prompt Pair\n\nNo matched pair available.\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")


def keys_matching(value: Any, forbidden: set[str]) -> set[str]:
    matches: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in forbidden:
                matches.add(key)
            matches.update(keys_matching(nested, forbidden))
    elif isinstance(value, list):
        for item in value:
            matches.update(keys_matching(item, forbidden))
    return matches


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render Phase 6D.2 model-agnostic prompts from Phase 6B.4 prompt data.")
    parser.add_argument("--prompt-data", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--response-schema",
        type=Path,
        default=Path("llm-experiments/schema/preference_prediction_response_v1.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit = render_prompt_dataset(args.prompt_data, args.output_dir, args.response_schema)
    print(f"Wrote rendered prompts to {args.output_dir / 'rendered_prompts.jsonl'}")
    print(f"prompt_data_objects_read={audit['prompt_data_objects_read']}")
    print(f"rendered_prompts_written={audit['rendered_prompts_written']}")
    print(f"non_history_count={audit['non_history_count']}")
    print(f"personalised_history_count={audit['personalised_history_count']}")
    print(f"leakage_failures={audit['leakage_failures']}")
    print(f"condition_pair_equivalence_failures={audit['condition_pair_equivalence_failures']}")
    print(f"deterministic_rerun_passed={audit['deterministic_rerun_passed']}")
    return 0 if audit["rendering_failures"] == 0 and audit["leakage_failures"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
