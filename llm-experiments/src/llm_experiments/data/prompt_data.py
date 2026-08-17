"""Build Phase 6B.4 condition-specific structured prompt-data objects.

This module consumes trusted Phase 6B.3 prediction examples and emits
condition-specific model-input data. It deliberately does not render natural
language prompts and does not copy hidden ground truth.
"""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .examples import write_jsonl
from .processing import EXPECTED_LABELS, write_json


PROMPT_DATA_SCHEMA_VERSION = "phase6b4_prompt_data_objects_v1"
PROMPT_DATA_BUILDER_VERSION = "phase6b4_builder_v1"
ACOUSTIC_FEATURE_PRECISION = 4
CONDITIONS = ["non_history", "personalised_history"]
PRIMARY_ACOUSTIC_FEATURES = ["z_RMS", "z_CF", "z_SW"]
SENSITIVITY_ACOUSTIC_FEATURES = ["z_SI"]
PARTICIPANT_METADATA_FIELDS = [
    "age_range",
    "gender",
    "cultural_influence_country",
    "music_listening_habits",
    "music_production_or_audio_engineering_experience",
    "hearing_difficulty",
]

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

MODEL_FORBIDDEN_KEYS = {
    "ground_truth",
    "stimulus_id",
    "actual_mix_id",
    "audio_path",
    "acoustic_feature_table_used",
    "z_SI",
    "z_SI_role",
}


def load_prediction_examples_jsonl(path: Path) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                examples.append(json.loads(stripped))
    return examples


def build_condition_objects_from_jsonl(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return build_condition_objects(load_prediction_examples_jsonl(path))


def build_condition_objects(prediction_examples: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    condition_objects: list[dict[str, Any]] = []
    for example in prediction_examples:
        condition_objects.append(build_non_history_object(example))
        if bool(example.get("personalised_history_available")):
            condition_objects.append(build_personalised_history_object(example))

    validation_counts = validate_condition_objects(condition_objects)
    summary = build_prompt_data_summary(prediction_examples, condition_objects, validation_counts)
    return condition_objects, summary


def build_non_history_object(example: dict[str, Any]) -> dict[str, Any]:
    prediction_example_id = str(example["prediction_example_id"])
    model_input = {
        "participant_metadata": build_participant_metadata(example),
        "target": build_target_prompt_data(example["input_data"]["target"]),
    }
    return {
        "condition_object_id": make_condition_object_id(prediction_example_id, "non_history"),
        "prediction_example_id": prediction_example_id,
        "condition": "non_history",
        "schema_version": PROMPT_DATA_SCHEMA_VERSION,
        "prompt_data_builder_version": PROMPT_DATA_BUILDER_VERSION,
        "pipeline_metadata": build_pipeline_metadata(example, "non_history"),
        "model_input": model_input,
    }


def build_personalised_history_object(example: dict[str, Any]) -> dict[str, Any]:
    prediction_example_id = str(example["prediction_example_id"])
    model_input = {
        "participant_metadata": build_participant_metadata(example),
        "target": build_target_prompt_data(example["input_data"]["target"]),
        "history": [build_history_prompt_data(trial) for trial in example["input_data"].get("history", [])],
    }
    return {
        "condition_object_id": make_condition_object_id(prediction_example_id, "personalised_history"),
        "prediction_example_id": prediction_example_id,
        "condition": "personalised_history",
        "schema_version": PROMPT_DATA_SCHEMA_VERSION,
        "prompt_data_builder_version": PROMPT_DATA_BUILDER_VERSION,
        "pipeline_metadata": build_pipeline_metadata(example, "personalised_history"),
        "model_input": model_input,
    }


def make_condition_object_id(prediction_example_id: str, condition: str) -> str:
    return f"{prediction_example_id}__{condition}"


def build_pipeline_metadata(example: dict[str, Any], condition: str) -> dict[str, Any]:
    return {
        "source_prediction_schema_version": example.get("schema_version"),
        "source_example_builder_version": example.get("example_builder_version"),
        "protocol_reference": example.get("protocol_reference"),
        "target_trial_id": example["input_data"]["target"].get("trial_id"),
        "n_history_trials_available": example.get("n_history_trials"),
        "personalised_history_available": bool(example.get("personalised_history_available")),
        "condition_includes_history": condition == "personalised_history",
        "primary_acoustic_features": list(PRIMARY_ACOUSTIC_FEATURES),
        "sensitivity_acoustic_features_excluded_from_model_input": list(SENSITIVITY_ACOUSTIC_FEATURES),
        "acoustic_feature_precision_decimal_places": ACOUSTIC_FEATURE_PRECISION,
        "model_input_contains_hidden_answers": False,
        "model_input_contains_underlying_candidate_ids_or_paths": False,
    }


def build_participant_metadata(example: dict[str, Any]) -> dict[str, Any]:
    metadata = example["input_data"]["participant_metadata"]
    return {field: metadata.get(field) for field in PARTICIPANT_METADATA_FIELDS}


def build_target_prompt_data(target: dict[str, Any]) -> dict[str, Any]:
    return {
        "trial_order": target.get("trial_order"),
        "context": build_context_prompt_data(target.get("episode", {})),
        "song": build_song_prompt_data(target.get("song", {})),
        "candidates": [build_candidate_prompt_data(candidate, include_rating=False) for candidate in target.get("candidates", [])],
    }


def build_context_prompt_data(episode: dict[str, Any]) -> dict[str, Any]:
    return {
        "episode_id": episode.get("episode_id"),
        "context_title": episode.get("context_title"),
        "context_label": episode.get("context_label"),
        "context_text": episode.get("context_text"),
        "context_dominant_function": episode.get("context_dominant_function"),
    }


def build_song_prompt_data(song: dict[str, Any]) -> dict[str, Any]:
    return {
        "song_id": song.get("song_id"),
        "excerpt_id": song.get("excerpt_id"),
        "participant_song_label": song.get("participant_song_label"),
        "song_title": song.get("song_title"),
    }


def build_history_prompt_data(history_trial: dict[str, Any]) -> dict[str, Any]:
    return {
        "trial_order": history_trial.get("trial_order"),
        "context": build_context_prompt_data(history_trial.get("episode", {})),
        "song": build_song_prompt_data(history_trial.get("song", {})),
        "candidates": [
            build_candidate_prompt_data(candidate, include_rating=True)
            for candidate in history_trial.get("candidates", [])
        ],
        "comparative_comment": history_trial.get("comparative_comment"),
    }


def build_candidate_prompt_data(candidate: dict[str, Any], include_rating: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
        "label": candidate.get("presentation_label"),
        "acoustic_features": {
            feature: rounded_feature(candidate.get(feature))
            for feature in PRIMARY_ACOUSTIC_FEATURES
        },
    }
    if include_rating:
        result["human_rating"] = candidate.get("human_rating")
    return result


def rounded_feature(value: Any) -> float | None:
    if value is None:
        return None
    return round(float(value), ACOUSTIC_FEATURE_PRECISION)


def validate_condition_objects(condition_objects: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter()
    by_example: dict[str, dict[str, dict[str, Any]]] = {}
    seen_ids: set[str] = set()
    for obj in condition_objects:
        condition_id = str(obj.get("condition_object_id", ""))
        if not condition_id:
            raise ValueError("Condition object missing condition_object_id.")
        if condition_id in seen_ids:
            raise ValueError(f"Duplicate condition_object_id: {condition_id}")
        seen_ids.add(condition_id)
        validate_prompt_data_no_leakage(obj)
        counts["objects_validated"] += 1
        by_example.setdefault(str(obj["prediction_example_id"]), {})[str(obj["condition"])] = obj

    for paired in by_example.values():
        if "non_history" in paired and "personalised_history" in paired:
            validate_condition_pair(paired["non_history"], paired["personalised_history"])
            counts["paired_condition_equivalence_validated"] += 1
    return dict(counts)


def validate_condition_pair(non_history: dict[str, Any], personalised_history: dict[str, Any]) -> None:
    if non_history["prediction_example_id"] != personalised_history["prediction_example_id"]:
        raise ValueError("Cannot validate pair with different prediction_example_id values.")
    if non_history["schema_version"] != personalised_history["schema_version"]:
        raise ValueError("Paired conditions have different schema versions.")
    if non_history["model_input"]["participant_metadata"] != personalised_history["model_input"]["participant_metadata"]:
        raise ValueError("Paired conditions have different participant metadata.")
    if non_history["model_input"]["target"] != personalised_history["model_input"]["target"]:
        raise ValueError("Paired conditions have different target payloads.")


def validate_prompt_data_no_leakage(obj: dict[str, Any]) -> None:
    if "ground_truth" in obj:
        raise ValueError("Condition object contains ground_truth.")
    model_input = obj.get("model_input", {})
    if "ground_truth" in json.dumps(model_input, sort_keys=True):
        raise ValueError("Model input contains ground_truth text.")
    forbidden_model_keys = keys_matching(model_input, MODEL_FORBIDDEN_KEYS)
    if forbidden_model_keys:
        raise ValueError(f"Model input contains forbidden provenance/sensitivity keys: {sorted(forbidden_model_keys)}")

    target = model_input.get("target", {})
    target_forbidden = keys_matching(target, TARGET_FORBIDDEN_KEYS)
    if target_forbidden:
        raise ValueError(f"Target model input leaks forbidden target keys: {sorted(target_forbidden)}")
    for candidate in target.get("candidates", []):
        if "human_rating" in candidate:
            raise ValueError("Target candidate contains human_rating.")
    if "history" in model_input and obj.get("condition") == "non_history":
        raise ValueError("Non-history model input contains history.")
    if obj.get("condition") == "personalised_history":
        history = model_input.get("history", [])
        if not history:
            raise ValueError("Personalised-history object lacks history evidence.")
        for trial in history:
            for candidate in trial.get("candidates", []):
                if "human_rating" not in candidate:
                    raise ValueError("History candidate missing human_rating.")


def build_prompt_data_summary(
    prediction_examples: list[dict[str, Any]],
    condition_objects: list[dict[str, Any]],
    validation_counts: dict[str, int],
) -> dict[str, Any]:
    condition_counts = Counter(str(obj["condition"]) for obj in condition_objects)
    return {
        "schema_version": PROMPT_DATA_SCHEMA_VERSION,
        "prompt_data_builder_version": PROMPT_DATA_BUILDER_VERSION,
        "canonical_row_unit": "prediction_example x information_condition",
        "prediction_examples_read": len(prediction_examples),
        "condition_object_count": len(condition_objects),
        "non_history_object_count": condition_counts.get("non_history", 0),
        "personalised_history_object_count": condition_counts.get("personalised_history", 0),
        "examples_lacking_personalised_history": sum(
            1 for example in prediction_examples if not bool(example.get("personalised_history_available"))
        ),
        "invalid_object_count": 0,
        "paired_condition_equivalence_failures": 0,
        "leakage_validation_failures": 0,
        "validation_counts": validation_counts,
        "contains_natural_language_prompts": False,
        "contains_llm_predictions": False,
        "contains_ground_truth": False,
        "model_input_primary_acoustic_features": list(PRIMARY_ACOUSTIC_FEATURES),
        "model_input_excludes_sensitivity_features": list(SENSITIVITY_ACOUSTIC_FEATURES),
        "acoustic_feature_precision_decimal_places": ACOUSTIC_FEATURE_PRECISION,
    }


def write_prompt_data_outputs(prediction_examples_jsonl: Path, output_dir: Path) -> tuple[Path, Path, Path]:
    objects, summary = build_condition_objects_from_jsonl(prediction_examples_jsonl)
    objects_path = output_dir / "prompt_data_objects.jsonl"
    summary_path = output_dir / "prompt_data_summary.json"
    sample_path = output_dir / "prompt_data_sample_pair.json"
    write_jsonl(objects_path, objects)
    write_json(summary_path, summary)
    write_json(sample_path, build_sample_pair(objects))
    return objects_path, summary_path, sample_path


def build_sample_pair(objects: list[dict[str, Any]]) -> dict[str, Any]:
    by_example: dict[str, list[dict[str, Any]]] = {}
    for obj in objects:
        by_example.setdefault(str(obj["prediction_example_id"]), []).append(obj)
    for pair in by_example.values():
        pair.sort(key=lambda obj: CONDITIONS.index(str(obj["condition"])))
        if len(pair) == 2:
            return {
                "note": "Synthetic structured prompt-data sample. Contains model_input only; no hidden ground truth or final natural-language prompt prose.",
                "condition_objects": pair,
            }
    return {
        "note": "Synthetic structured prompt-data sample. Contains model_input only; no hidden ground truth or final natural-language prompt prose.",
        "condition_objects": objects[:1],
    }


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


def deep_copy(value: Any) -> Any:
    return copy.deepcopy(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Phase 6B.4 deterministic condition-specific prompt-data objects.")
    parser.add_argument("--examples", required=True, type=Path, help="Phase 6B.3 prediction_examples.jsonl.")
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory for Phase 6B.4 prompt-data outputs.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    objects_path, summary_path, sample_path = write_prompt_data_outputs(args.examples, args.output_dir)
    print(f"Wrote prompt-data objects to {objects_path}")
    print(f"Wrote prompt-data summary to {summary_path}")
    print(f"Wrote synthetic sample pair to {sample_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
