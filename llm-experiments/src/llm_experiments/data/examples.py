"""Build Phase 6B.3 leave-one-trial-out prediction examples.

The canonical output is deterministic JSONL with one object per participant x
held-out target trial. The model-facing payload is kept under ``input_data``;
target outcome-derived values are retained only in ``ground_truth``.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .processing import EXPECTED_LABELS, write_json
from .targets import boolish, sort_int


PREDICTION_EXAMPLE_SCHEMA_VERSION = "phase6b3_prediction_examples_v1"
PREDICTION_EXAMPLE_BUILDER_VERSION = "phase6b3_builder_v1"
PROTOCOL_REFERENCE = "Phase 6A frozen LLM evaluation protocol"

PARTICIPANT_METADATA_FIELDS = [
    "age_range",
    "gender",
    "cultural_influence_country",
    "music_listening_habits",
    "music_production_or_audio_engineering_experience",
    "hearing_difficulty",
]

TARGET_OUTCOME_KEYS = {
    "human_rating",
    "comparative_comment",
    "observed_rank",
    "observed_preferred_set",
    "observed_preferred_mix",
    "observed_max_rating",
    "is_observed_preferred",
    "is_single_winner",
    "n_preferred_tied",
}

TRIAL_TARGET_OUTCOME_KEYS = {
    "observed_preferred_set",
    "observed_preferred_mix",
    "observed_max_rating",
    "is_single_winner",
    "n_preferred_tied",
    "human_rating_A",
    "human_rating_B",
    "human_rating_C",
    "human_rating_D",
    "human_rating_E",
    "observed_rank_A",
    "observed_rank_B",
    "observed_rank_C",
    "observed_rank_D",
    "observed_rank_E",
}


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def group_by_trial(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("trial_id", ""))].append(row)
    return dict(grouped)


def build_prediction_examples_from_csv(
    candidate_ground_truth_csv: Path,
    trial_ground_truth_csv: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidate_rows = load_csv_rows(candidate_ground_truth_csv)
    trial_targets = load_csv_rows(trial_ground_truth_csv)
    return build_prediction_examples(candidate_rows, trial_targets)


def build_prediction_examples(
    candidate_rows: list[dict[str, Any]],
    trial_targets: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows_by_trial = group_by_trial(candidate_rows)
    trials_by_participant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for target in trial_targets:
        trials_by_participant[str(target.get("participant_id", ""))].append(target)
    for participant_id in trials_by_participant:
        trials_by_participant[participant_id].sort(key=trial_sort_key)

    examples: list[dict[str, Any]] = []
    for target in sorted(trial_targets, key=trial_sort_key):
        if not boolish(target.get("target_eligible")):
            continue
        trial_id = str(target.get("trial_id", ""))
        target_rows = rows_by_trial.get(trial_id, [])
        history_trials = build_history_trials(
            target_trial=target,
            participant_trials=trials_by_participant[str(target.get("participant_id", ""))],
            rows_by_trial=rows_by_trial,
        )
        example = {
            "prediction_example_id": make_prediction_example_id(str(target.get("participant_id", "")), trial_id),
            "participant_id": str(target.get("participant_id", "")),
            "schema_version": PREDICTION_EXAMPLE_SCHEMA_VERSION,
            "example_builder_version": PREDICTION_EXAMPLE_BUILDER_VERSION,
            "protocol_reference": PROTOCOL_REFERENCE,
            "input_data": {
                "participant_metadata": build_participant_metadata(target_rows),
                "target": build_target_input(target, target_rows),
                "history": history_trials,
            },
            "n_history_trials": len(history_trials),
            "personalised_history_available": len(history_trials) > 0,
            "ground_truth": build_hidden_ground_truth(target),
        }
        validate_no_target_leakage(example, target_rows)
        examples.append(example)

    summary = build_prediction_summary(examples, trial_targets, rows_by_trial)
    return examples, summary


def make_prediction_example_id(participant_id: str, target_trial_id: str) -> str:
    return f"{participant_id}__heldout__{target_trial_id}"


def build_target_input(target: dict[str, Any], target_rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered_rows = sort_candidate_rows(target_rows)
    return {
        "trial_id": str(target.get("trial_id", "")),
        "trial_order": parse_number(target.get("trial_order", "")),
        "trial_index": parse_number(target.get("trial_index", "")),
        "episode": build_episode_object(first_or_empty(ordered_rows)),
        "song": build_song_object(first_or_empty(ordered_rows), target),
        "candidates": [build_target_candidate(row) for row in ordered_rows],
    }


def build_history_trials(
    target_trial: dict[str, Any],
    participant_trials: list[dict[str, Any]],
    rows_by_trial: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    target_trial_id = str(target_trial.get("trial_id", ""))
    history: list[dict[str, Any]] = []
    for trial in sorted(participant_trials, key=trial_sort_key):
        trial_id = str(trial.get("trial_id", ""))
        if trial_id == target_trial_id:
            continue
        if not boolish(trial.get("history_eligible")):
            continue
        history.append(build_history_trial(trial, rows_by_trial.get(trial_id, [])))
    return history


def build_history_trial(trial: dict[str, Any], trial_rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered_rows = sort_candidate_rows(trial_rows)
    first = first_or_empty(ordered_rows)
    return {
        "trial_id": str(trial.get("trial_id", "")),
        "trial_order": parse_number(trial.get("trial_order", "")),
        "trial_index": parse_number(trial.get("trial_index", "")),
        "episode": build_episode_object(first),
        "song": build_song_object(first, trial),
        "candidates": [build_history_candidate(row) for row in ordered_rows],
        "comparative_comment": comment_or_none(first.get("comparative_comment", "")),
        "history_comment_available": boolish(trial.get("history_comment_available")),
    }


def build_participant_metadata(trial_rows: list[dict[str, Any]]) -> dict[str, Any]:
    first = first_or_empty(trial_rows)
    return {field: value_or_none(first.get(field, "")) for field in PARTICIPANT_METADATA_FIELDS}


def build_episode_object(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "episode_id": value_or_none(row.get("episode_id", "")),
        "scenario_id": value_or_none(row.get("scenario_id", "")),
        "context_title": value_or_none(row.get("context_title", "")),
        "context_label": value_or_none(row.get("context_label", "")),
        "context_text": value_or_none(row.get("context_text", "")),
        "context_dominant_function": value_or_none(row.get("context_dominant_function", "")),
        "episode_position": parse_number(row.get("episode_position", "")),
    }


def build_song_object(row: dict[str, Any], trial: dict[str, Any]) -> dict[str, Any]:
    return {
        "song_id": value_or_none(trial.get("song_id", row.get("song_id", ""))),
        "excerpt_id": value_or_none(trial.get("excerpt_id", row.get("excerpt_id", ""))),
        "song_position": parse_number(row.get("song_position", "")),
        "participant_song_label": value_or_none(row.get("participant_song_label", "")),
        "song_title": value_or_none(row.get("song_title", "")),
    }


def build_target_candidate(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "presentation_label": str(row.get("presentation_label", "")),
        "stimulus_id": value_or_none(row.get("stimulus_id", "")),
        "actual_mix_id": value_or_none(row.get("actual_mix_id", "")),
        "audio_path": value_or_none(row.get("audio_path", "")),
        "z_RMS": parse_number(row.get("z_RMS", "")),
        "z_CF": parse_number(row.get("z_CF", "")),
        "z_SW": parse_number(row.get("z_SW", "")),
        "z_SI": parse_number(row.get("z_SI", "")),
        "z_SI_role": value_or_none(row.get("z_SI_role", "")),
        "acoustic_feature_table_used": value_or_none(row.get("acoustic_feature_table_used", "")),
    }


def build_history_candidate(row: dict[str, Any]) -> dict[str, Any]:
    candidate = build_target_candidate(row)
    candidate["human_rating"] = parse_number(row.get("human_rating", ""))
    return candidate


def build_hidden_ground_truth(target: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_trial_id": str(target.get("trial_id", "")),
        "human_ratings": {label: parse_number(target.get(f"human_rating_{label}", "")) for label in EXPECTED_LABELS},
        "observed_ranks": {label: parse_number(target.get(f"observed_rank_{label}", "")) for label in EXPECTED_LABELS},
        "observed_preferred_set": parse_json_list(target.get("observed_preferred_set", "")),
        "observed_preferred_mix": value_or_none(target.get("observed_preferred_mix", "")),
        "is_single_winner": boolish(target.get("is_single_winner")),
        "n_preferred_tied": parse_number(target.get("n_preferred_tied", "")),
    }


def validate_no_target_leakage(example: dict[str, Any], target_rows: list[dict[str, Any]]) -> None:
    target_input = example["input_data"]["target"]
    target_comment = comment_or_none(first_or_empty(target_rows).get("comparative_comment", ""))
    for candidate in target_input["candidates"]:
        leaked = TARGET_OUTCOME_KEYS.intersection(candidate)
        if leaked:
            raise ValueError(f"Target candidate leaks outcome fields: {sorted(leaked)}")

    leaked_target_keys = keys_matching(target_input, TARGET_OUTCOME_KEYS)
    if leaked_target_keys:
        raise ValueError(f"Target input leaks outcome fields: {sorted(leaked_target_keys)}")

    if target_comment:
        input_payload = json.dumps(example["input_data"], ensure_ascii=False, sort_keys=True)
        if target_comment in input_payload:
            raise ValueError("Target comparative comment appears in model-facing input_data.")

    target_trial_id = target_input["trial_id"]
    history_ids = [trial["trial_id"] for trial in example["input_data"]["history"]]
    if target_trial_id in history_ids:
        raise ValueError("Target trial appears in its own history.")

    ground_truth_keys = set(example["ground_truth"])
    required_ground_truth = {
        "human_ratings",
        "observed_ranks",
        "observed_preferred_set",
        "observed_preferred_mix",
        "is_single_winner",
        "n_preferred_tied",
    }
    missing = required_ground_truth - ground_truth_keys
    if missing:
        raise ValueError(f"Hidden ground truth missing required fields: {sorted(missing)}")


def validate_prediction_examples(examples: list[dict[str, Any]], rows_by_trial: dict[str, list[dict[str, Any]]] | None = None) -> None:
    seen: set[str] = set()
    for example in examples:
        example_id = str(example.get("prediction_example_id", ""))
        if not example_id:
            raise ValueError("Prediction example is missing prediction_example_id.")
        if example_id in seen:
            raise ValueError(f"Duplicate prediction_example_id: {example_id}")
        seen.add(example_id)
        target_id = str(example["input_data"]["target"]["trial_id"])
        target_rows = rows_by_trial.get(target_id, []) if rows_by_trial else []
        validate_no_target_leakage(example, target_rows)


def build_prediction_summary(
    examples: list[dict[str, Any]],
    trial_targets: list[dict[str, Any]],
    rows_by_trial: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    reason_counts = Counter()
    for target in trial_targets:
        if not boolish(target.get("target_eligible")):
            for reason in str(target.get("target_ineligibility_reasons", "")).split("|"):
                if reason:
                    reason_counts[reason] += 1
    validate_prediction_examples(examples, rows_by_trial)
    return {
        "schema_version": PREDICTION_EXAMPLE_SCHEMA_VERSION,
        "example_builder_version": PREDICTION_EXAMPLE_BUILDER_VERSION,
        "canonical_row_unit": "participant x held_out_target_trial",
        "participant_count": len({str(target.get("participant_id", "")) for target in trial_targets}),
        "trial_target_count": len(trial_targets),
        "target_eligible_trial_count": sum(1 for target in trial_targets if boolish(target.get("target_eligible"))),
        "target_ineligible_trial_count": sum(1 for target in trial_targets if not boolish(target.get("target_eligible"))),
        "prediction_example_count": len(examples),
        "examples_with_5_history_trials": sum(1 for example in examples if example["n_history_trials"] == 5),
        "examples_with_fewer_history_trials": sum(1 for example in examples if example["n_history_trials"] < 5),
        "examples_without_personalised_history_available": sum(
            1 for example in examples if not example["personalised_history_available"]
        ),
        "target_ineligibility_reason_counts": dict(sorted(reason_counts.items())),
        "contains_llm_prompts": False,
        "contains_llm_predictions": False,
        "contains_model_performance": False,
        "input_data_contains_target_outcomes": False,
    }


def write_prediction_example_outputs(
    candidate_ground_truth_csv: Path,
    trial_ground_truth_csv: Path,
    output_dir: Path,
) -> tuple[Path, Path, Path]:
    examples, summary = build_prediction_examples_from_csv(candidate_ground_truth_csv, trial_ground_truth_csv)
    examples_path = output_dir / "prediction_examples.jsonl"
    summary_path = output_dir / "prediction_example_summary.json"
    sample_path = output_dir / "prediction_example_sample.json"
    write_jsonl(examples_path, examples)
    write_json(summary_path, summary)
    sample_payload = {
        "note": "Synthetic inspection sample. input_data is model-facing; ground_truth is evaluation-only and must never be passed to the LLM.",
        "example": examples[0] if examples else None,
    }
    write_json(sample_path, sample_payload)
    return examples_path, summary_path, sample_path


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=False) + "\n")


def trial_sort_key(row: dict[str, Any]) -> tuple[str, int, str]:
    return (str(row.get("participant_id", "")), sort_int(row.get("trial_order", "")), str(row.get("trial_id", "")))


def sort_candidate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: EXPECTED_LABELS.index(str(row.get("presentation_label", "Z"))) if str(row.get("presentation_label", "Z")) in EXPECTED_LABELS else 99)


def first_or_empty(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return rows[0] if rows else {}


def value_or_none(value: Any) -> Any:
    if value in (None, ""):
        return None
    return value


def comment_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    comment = str(value).strip()
    return comment if comment else None


def parse_number(value: Any) -> int | float | None:
    if value in (None, ""):
        return None
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return None
    if number.is_integer():
        return int(number)
    return number


def parse_json_list(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    parsed = json.loads(str(value))
    if not isinstance(parsed, list):
        raise ValueError("Expected JSON list.")
    return parsed


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
    parser = argparse.ArgumentParser(description="Build Phase 6B.3 deterministic leave-one-trial-out prediction examples.")
    parser.add_argument("--candidates", required=True, type=Path, help="Phase 6B.2 candidate_ground_truth_enriched.csv.")
    parser.add_argument("--targets", required=True, type=Path, help="Phase 6B.2 trial_ground_truth_targets.csv.")
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory for Phase 6B.3 prediction example outputs.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    examples_path, summary_path, sample_path = write_prediction_example_outputs(args.candidates, args.targets, args.output_dir)
    print(f"Wrote prediction examples to {examples_path}")
    print(f"Wrote prediction example summary to {summary_path}")
    print(f"Wrote synthetic inspection sample to {sample_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
