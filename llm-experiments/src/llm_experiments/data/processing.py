"""Build the Phase 6B.1 LLM analysis-ready long-format dataset.

The pipeline accepts raw Netlify participant-level CSV exports from the active
five-mix frontend and emits one row per participant x trial x candidate mix.
It intentionally preserves ratings/comments but does not derive preference
labels, winners, rankings, or held-out examples.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


EXPECTED_LABELS = ["A", "B", "C", "D", "E"]
PRIMARY_FEATURES = ["z_RMS", "z_CF", "z_SW"]
SENSITIVITY_FEATURES = ["z_SI"]
PARTICIPANT_METADATA_FIELDS = [
    "age_range",
    "gender",
    "cultural_influence_country",
    "music_listening_habits",
    "music_production_or_audio_engineering_experience",
    "hearing_difficulty",
]

CANONICAL_COLUMNS = [
    "participant_id",
    "study_id",
    "study_version",
    "schema_version",
    "stimulus_configuration_version",
    "source_version",
    "submission_status",
    "group_id",
    "study_group",
    "started_at",
    "completed_at",
    "duration_seconds",
    *PARTICIPANT_METADATA_FIELDS,
    "participant_metadata_missing_fields",
    "trial_id",
    "trial_order",
    "trial_index",
    "episode_id",
    "scenario_id",
    "episode_position",
    "context_title",
    "context_label",
    "context_text",
    "context_dominant_function",
    "song_id",
    "excerpt_id",
    "song_position",
    "participant_song_label",
    "song_title",
    "presentation_label",
    "display_position",
    "stimulus_id",
    "actual_mix_id",
    "audio_path",
    "human_rating",
    "rating_set",
    "audio_played",
    "first_play_timestamp",
    "comparative_comment",
    "response_time_ms",
    "z_RMS",
    "z_CF",
    "z_SW",
    "z_SI",
    "z_SI_role",
    "acoustic_feature_source_file",
    "acoustic_feature_table_used",
    "active_stimulus_match",
    "feature_join_status",
    "trial_row_count",
    "trial_labels",
    "trial_stimulus_ids",
    "trial_validation_status",
    "candidate_validation_status",
    "validation_issues",
]

ISSUE_COLUMNS = ["participant_id", "trial_id", "presentation_label", "code", "message"]
FEATURE_AUDIT_COLUMNS = ["status", "stimulus_id", "count", "message"]


def normalise_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def column_map(fieldnames: list[str]) -> dict[str, str]:
    return {normalise_header(name): name for name in fieldnames}


def get_value(row: dict[str, str], columns: dict[str, str], name: str, default: str = "") -> str:
    column = columns.get(normalise_header(name))
    if not column:
        return default
    value = row.get(column)
    return default if value is None else value


def parse_json_field(
    row: dict[str, str],
    columns: dict[str, str],
    field: str,
    participant_id: str,
    issues: list[dict[str, str]],
    default: Any,
) -> Any:
    value = get_value(row, columns, field)
    if value == "":
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        add_issue(issues, participant_id, "", "", f"malformed_{field}", str(exc))
        return default


def add_issue(
    issues: list[dict[str, str]],
    participant_id: str,
    trial_id: str,
    label: str,
    code: str,
    message: str,
) -> None:
    issues.append(
        {
            "participant_id": participant_id,
            "trial_id": trial_id,
            "presentation_label": label,
            "code": code,
            "message": message,
        }
    )


def load_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str], dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    return rows, fieldnames, column_map(fieldnames)


def load_stimulus_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_active_stimuli(config: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    scenarios = {scenario["id"]: scenario for scenario in config.get("scenarios", [])}
    excerpts = {excerpt["id"]: excerpt for excerpt in config.get("excerpts", [])}
    stimuli: dict[str, dict[str, Any]] = {}
    for excerpt in config.get("excerpts", []):
        for mix in excerpt.get("mixes", []):
            stimulus_id = str(mix.get("stimulusId", ""))
            if stimulus_id:
                stimuli[stimulus_id] = {
                    **mix,
                    "excerpt_id": excerpt.get("id", ""),
                    "song_id": excerpt.get("sourceSongId", excerpt.get("id", "")),
                    "song_title": excerpt.get("finalExcerptName", ""),
                    "participant_song_label": excerpt.get("participantLabel", ""),
                }
    return scenarios, excerpts, stimuli


def load_feature_table(path: Path) -> tuple[dict[str, dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    rows, _, _ = load_csv_rows(path)
    counts = Counter(row.get("stimulus_id", "") for row in rows if row.get("stimulus_id"))
    features: dict[str, dict[str, str]] = {}
    audit: list[dict[str, str]] = []
    for row in rows:
        stimulus_id = row.get("stimulus_id", "")
        if not stimulus_id:
            continue
        if counts[stimulus_id] == 1:
            features[stimulus_id] = row
        else:
            audit.append(
                {
                    "status": "duplicate_feature_match",
                    "stimulus_id": stimulus_id,
                    "count": str(counts[stimulus_id]),
                    "message": "Feature table contains duplicate rows for this stimulus_id.",
                }
            )
    return features, rows, audit


def build_analysis_ready_dataset(
    raw_export_csv: Path,
    stimulus_config_json: Path,
    feature_table_csv: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, Any], list[dict[str, str]]]:
    raw_rows, _, columns = load_csv_rows(raw_export_csv)
    config = load_stimulus_config(stimulus_config_json)
    scenarios, excerpts, active_stimuli = load_active_stimuli(config)
    feature_map, feature_rows, feature_audit = load_feature_table(feature_table_csv)
    active_ids = set(active_stimuli)
    feature_ids = {row.get("stimulus_id", "") for row in feature_rows if row.get("stimulus_id")}

    for stimulus_id in sorted(active_ids - set(feature_map)):
        feature_audit.append(
            {
                "status": "unmatched_active_stimulus",
                "stimulus_id": stimulus_id,
                "count": "0",
                "message": "Active five-mix stimulus has no unique acoustic-feature match.",
            }
        )
    for stimulus_id in sorted(feature_ids - active_ids):
        feature_audit.append(
            {
                "status": "obsolete_feature_row",
                "stimulus_id": stimulus_id,
                "count": "1",
                "message": "Feature row is not part of the active five-mix study config.",
            }
        )

    canonical_rows: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []

    for raw_row in raw_rows:
        participant_id = get_value(raw_row, columns, "study_id")
        participant_values = extract_participant_values(raw_row, columns)
        demographics = parse_json_field(raw_row, columns, "demographics_json", participant_id, issues, {})
        metadata = extract_participant_metadata(demographics)
        missing_metadata = [field for field in PARTICIPANT_METADATA_FIELDS if metadata.get(field, "") == ""]
        responses = parse_json_field(raw_row, columns, "responses_json", participant_id, issues, [])
        mix_mapping = parse_json_field(raw_row, columns, "mix_mapping_json", participant_id, issues, {})
        presentation_order = parse_json_field(raw_row, columns, "presentation_order_json", participant_id, issues, {})
        trial_order = parse_json_field(raw_row, columns, "trial_order_json", participant_id, issues, {})
        trial_order_lookup = build_trial_order_lookup(trial_order)

        if not participant_id:
            add_issue(issues, participant_id, "", "", "missing_participant_id", "Raw export row is missing study_id.")
        if not isinstance(responses, list):
            add_issue(issues, participant_id, "", "", "responses_not_list", "responses_json did not parse to a list.")
            continue

        normalised_responses = [normalise_response(response) for response in responses if isinstance(response, dict)]
        trial_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for response in normalised_responses:
            trial_key = (
                str(response.get("trial_index", "")),
                str(response.get("episode_id", "")),
                str(response.get("song_id", "")),
            )
            trial_groups[trial_key].append(response)

        for trial_key, trial_responses in sorted(trial_groups.items(), key=trial_group_sort_key):
            trial_index, episode_id, song_id = trial_key
            trial_id = make_trial_id(participant_id, trial_index, episode_id, song_id)
            trial_issues = validate_trial(
                participant_id,
                trial_id,
                episode_id,
                song_id,
                trial_responses,
                mix_mapping,
                presentation_order,
                active_stimuli,
                issues,
            )
            labels = sorted(str(response.get("display_label", "")) for response in trial_responses if response.get("display_label"))
            stimulus_ids = sorted(str(response.get("stimulus_id", "")) for response in trial_responses if response.get("stimulus_id"))
            trial_status = "complete" if not trial_issues else ("incomplete" if any(code.startswith("incomplete") or code in {"missing_label", "missing_rating"} for code in trial_issues) else "malformed")

            for response in sorted(trial_responses, key=response_sort_key):
                label = str(response.get("display_label", ""))
                stimulus_id = str(response.get("stimulus_id", ""))
                feature = feature_map.get(stimulus_id)
                active = active_stimuli.get(stimulus_id, {})
                scenario = scenarios.get(episode_id, {})
                excerpt_id = str(response.get("excerpt_id", "")) or str(active.get("excerpt_id", ""))
                excerpt = excerpts.get(excerpt_id, {})
                candidate_issues = validate_candidate(
                    participant_id,
                    trial_id,
                    response,
                    feature,
                    active_stimuli,
                    issues,
                )
                row_issues = sorted(set(trial_issues + candidate_issues))

                canonical_rows.append(
                    {
                        **participant_values,
                        **metadata,
                        "participant_metadata_missing_fields": "|".join(missing_metadata),
                        "trial_id": trial_id,
                        "trial_order": to_int_or_empty(trial_index),
                        "trial_index": to_int_or_empty(trial_index),
                        "episode_id": episode_id,
                        "scenario_id": str(response.get("scenario_id", episode_id) or episode_id),
                        "episode_position": to_int_or_empty(response.get("episode_position", "")),
                        "context_title": scenario.get("title", ""),
                        "context_label": scenario.get("id", episode_id),
                        "context_text": scenario.get("text", ""),
                        "context_dominant_function": scenario.get("dominantFunction", ""),
                        "song_id": song_id,
                        "excerpt_id": excerpt_id,
                        "song_position": to_int_or_empty(response.get("song_position", "")),
                        "participant_song_label": active.get("participant_song_label", excerpt.get("participantLabel", "")),
                        "song_title": active.get("song_title", excerpt.get("finalExcerptName", "")),
                        "presentation_label": label,
                        "display_position": to_int_or_empty(response.get("display_position", "")),
                        "stimulus_id": stimulus_id,
                        "actual_mix_id": str(response.get("actual_mix_id", "")) or str(active.get("actualMixId", "")),
                        "audio_path": str(response.get("audio_path", "")) or str(active.get("audioPath", "")),
                        "human_rating": response.get("rating", ""),
                        "rating_set": bool(response.get("rating_set", False)),
                        "audio_played": bool(response.get("audio_played", False)),
                        "first_play_timestamp": str(response.get("first_play_timestamp", "")),
                        "comparative_comment": str(response.get("comparative_comment", "")),
                        "response_time_ms": response.get("response_time_ms", ""),
                        "z_RMS": feature_value(feature, "z_RMS"),
                        "z_CF": feature_value(feature, "z_CF"),
                        "z_SW": feature_value(feature, "z_SW"),
                        "z_SI": feature_value(feature, "z_SI"),
                        "z_SI_role": feature_value(feature, "z_SI_role"),
                        "acoustic_feature_source_file": feature_value(feature, "feature_source_file"),
                        "acoustic_feature_table_used": feature_value(feature, "feature_table_used"),
                        "active_stimulus_match": stimulus_id in active_stimuli,
                        "feature_join_status": "matched" if feature else "missing",
                        "trial_row_count": len(trial_responses),
                        "trial_labels": "|".join(labels),
                        "trial_stimulus_ids": "|".join(stimulus_ids),
                        "trial_validation_status": trial_status,
                        "candidate_validation_status": "valid" if not candidate_issues else "invalid",
                        "validation_issues": "|".join(row_issues),
                    }
                )

        missing_order_trials = set(trial_order_lookup) - {
            str(key[0]) for key in trial_groups.keys()
        }
        for missing_trial_index in sorted(missing_order_trials, key=sort_maybe_int):
            order_item = trial_order_lookup[missing_trial_index]
            missing_trial_id = make_trial_id(
                participant_id,
                missing_trial_index,
                str(order_item.get("scenario_id", "")),
                "",
            )
            add_issue(
                issues,
                participant_id,
                missing_trial_id,
                "",
                "incomplete_missing_trial_responses",
                "Trial appears in trial_order_json but has no response rows.",
            )

    canonical_rows = sorted(canonical_rows, key=canonical_sort_key)
    summary = build_summary(raw_export_csv, stimulus_config_json, feature_table_csv, canonical_rows, issues, feature_audit)
    return canonical_rows, issues, summary, feature_audit


def extract_participant_values(row: dict[str, str], columns: dict[str, str]) -> dict[str, Any]:
    study_id = get_value(row, columns, "study_id")
    return {
        "participant_id": study_id,
        "study_id": study_id,
        "study_version": get_value(row, columns, "study_version"),
        "schema_version": get_value(row, columns, "schema_version"),
        "stimulus_configuration_version": get_value(row, columns, "stimulus_configuration_version"),
        "source_version": get_value(row, columns, "source_version"),
        "submission_status": get_value(row, columns, "submission_status"),
        "group_id": get_value(row, columns, "group_id") or get_value(row, columns, "study_group"),
        "study_group": get_value(row, columns, "study_group") or get_value(row, columns, "group_id"),
        "started_at": get_value(row, columns, "started_at"),
        "completed_at": get_value(row, columns, "completed_at"),
        "duration_seconds": get_value(row, columns, "duration_seconds"),
    }


def extract_participant_metadata(demographics: Any) -> dict[str, str]:
    source = demographics if isinstance(demographics, dict) else {}
    return {field: normalise_metadata_value(source.get(field, "")) for field in PARTICIPANT_METADATA_FIELDS}


def normalise_metadata_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return str(value).strip()


def build_trial_order_lookup(trial_order: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(trial_order, dict):
        return {}
    trials = trial_order.get("trials")
    if not isinstance(trials, list):
        return {}
    result = {}
    for trial in trials:
        if isinstance(trial, dict) and trial.get("trial_index") not in (None, ""):
            result[str(trial.get("trial_index"))] = trial
    return result


def normalise_response(response: dict[str, Any]) -> dict[str, Any]:
    result = dict(response)
    if not result.get("episode_id") and result.get("scenario_id"):
        result["episode_id"] = result.get("scenario_id")
    if not result.get("scenario_id") and result.get("episode_id"):
        result["scenario_id"] = result.get("episode_id")
    if "comparative_comment" not in result:
        result["comparative_comment"] = result.get("comment", "")
    if "display_label" in result:
        result["display_label"] = normalise_display_label(result.get("display_label"))
    return result


def normalise_display_label(label: Any) -> str:
    return str(label or "").strip().replace("Version ", "")


def make_trial_id(participant_id: str, trial_index: Any, episode_id: str, song_id: str) -> str:
    trial_part = str(trial_index).strip()
    try:
        trial_part = f"{int(float(trial_part)):02d}"
    except (TypeError, ValueError):
        trial_part = re.sub(r"[^A-Za-z0-9]+", "_", trial_part).strip("_") or "unknown"
    return f"{participant_id}__trial_{trial_part}"


def validate_trial(
    participant_id: str,
    trial_id: str,
    episode_id: str,
    song_id: str,
    trial_responses: list[dict[str, Any]],
    mix_mapping: Any,
    presentation_order: Any,
    active_stimuli: dict[str, dict[str, Any]],
    issues: list[dict[str, str]],
) -> list[str]:
    codes: list[str] = []
    labels = [str(response.get("display_label", "")) for response in trial_responses]
    stimulus_ids = [str(response.get("stimulus_id", "")) for response in trial_responses]
    comments = {str(response.get("comparative_comment", "")).strip() for response in trial_responses if str(response.get("comparative_comment", "")).strip()}
    expected_mapping = get_trial_mapping(mix_mapping, episode_id, song_id)
    expected_order = get_trial_order(presentation_order, episode_id, song_id)

    def record(code: str, message: str) -> None:
        codes.append(code)
        add_issue(issues, participant_id, trial_id, "", code, message)

    if len(trial_responses) != 5:
        record("incomplete_trial_row_count", f"Expected 5 candidate rows, found {len(trial_responses)}.")
    if sorted(labels) != EXPECTED_LABELS:
        record("incomplete_or_invalid_labels", f"Expected labels A-E once each, found {sorted(labels)!r}.")
    if len(set(labels)) != len(labels):
        record("duplicate_presentation_label", "Duplicate presentation labels found within trial.")
    if any(not stimulus_id for stimulus_id in stimulus_ids):
        record("missing_stimulus_id", "At least one candidate row is missing stimulus_id.")
    if len(set(stimulus_ids)) != len(stimulus_ids):
        record("duplicate_candidate_mapping", "Duplicate stimulus_id values found within trial.")
    if len(comments) != 1:
        record("missing_or_inconsistent_comment", f"Expected one repeated trial comment, found {len(comments)} distinct non-empty comments.")
    if not isinstance(expected_mapping, dict) or not expected_mapping:
        record("missing_mix_mapping", "No mix_mapping_json entry exists for this episode/song trial.")
    else:
        for response in trial_responses:
            label = str(response.get("display_label", ""))
            expected_stimulus = str(expected_mapping.get(label, ""))
            observed_stimulus = str(response.get("stimulus_id", ""))
            if not expected_stimulus:
                record("missing_label_mapping", f"No mapping for presentation label {label}.")
            elif expected_stimulus != observed_stimulus:
                record("mapping_response_disagreement", f"Label {label} maps to {expected_stimulus}, response has {observed_stimulus}.")
    if expected_order and labels != expected_order:
        record("presentation_order_disagreement", f"Response label order {labels!r} differs from presentation_order_json {expected_order!r}.")
    for stimulus_id in stimulus_ids:
        if stimulus_id and stimulus_id not in active_stimuli:
            record("inactive_stimulus_id", f"Stimulus {stimulus_id} is not part of the active five-mix config.")
    return sorted(set(codes))


def validate_candidate(
    participant_id: str,
    trial_id: str,
    response: dict[str, Any],
    feature: dict[str, str] | None,
    active_stimuli: dict[str, dict[str, Any]],
    issues: list[dict[str, str]],
) -> list[str]:
    codes: list[str] = []
    label = str(response.get("display_label", ""))
    stimulus_id = str(response.get("stimulus_id", ""))

    def record(code: str, message: str) -> None:
        codes.append(code)
        add_issue(issues, participant_id, trial_id, label, code, message)

    if label not in EXPECTED_LABELS:
        record("invalid_presentation_label", f"Presentation label must be A-E, found {label!r}.")
    rating = response.get("rating")
    if not is_valid_rating(rating):
        record("missing_rating", f"Rating is not numeric in 0-100: {rating!r}.")
    if stimulus_id not in active_stimuli:
        record("inactive_stimulus_id", f"Stimulus {stimulus_id!r} is not active.")
    if feature is None:
        record("missing_acoustic_features", f"No acoustic feature row matched stimulus {stimulus_id!r}.")
    else:
        for field in PRIMARY_FEATURES:
            if feature_value(feature, field) == "":
                record("missing_primary_acoustic_feature", f"Missing {field} for stimulus {stimulus_id!r}.")
        if feature_value(feature, "z_SI") == "":
            record("missing_sensitivity_acoustic_feature", f"Missing z_SI for stimulus {stimulus_id!r}.")
    return sorted(set(codes))


def get_trial_mapping(mapping: Any, episode_id: str, song_id: str) -> dict[str, Any]:
    if not isinstance(mapping, dict):
        return {}
    episode = mapping.get(episode_id)
    if not isinstance(episode, dict):
        return {}
    song = episode.get(song_id)
    return song if isinstance(song, dict) else {}


def get_trial_order(order: Any, episode_id: str, song_id: str) -> list[str]:
    if not isinstance(order, dict):
        return []
    episode = order.get(episode_id)
    if not isinstance(episode, dict):
        return []
    labels = episode.get(song_id)
    return [normalise_display_label(label) for label in labels] if isinstance(labels, list) else []


def is_valid_rating(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 100


def feature_value(feature: dict[str, str] | None, field: str) -> str:
    if not feature:
        return ""
    return feature.get(field, "")


def to_int_or_empty(value: Any) -> int | str:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return ""


def trial_group_sort_key(item: tuple[tuple[str, str, str], list[dict[str, Any]]]) -> tuple[int, str, str]:
    trial_index, episode_id, song_id = item[0]
    return (sort_maybe_int(trial_index), episode_id, song_id)


def response_sort_key(response: dict[str, Any]) -> tuple[int, str]:
    return (sort_maybe_int(response.get("display_position", "")), str(response.get("display_label", "")))


def canonical_sort_key(row: dict[str, Any]) -> tuple[str, int, str]:
    return (
        str(row.get("participant_id", "")),
        sort_maybe_int(row.get("trial_order", "")),
        str(row.get("presentation_label", "")),
    )


def sort_maybe_int(value: Any) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 999999


def build_summary(
    raw_export_csv: Path,
    stimulus_config_json: Path,
    feature_table_csv: Path,
    rows: list[dict[str, Any]],
    issues: list[dict[str, str]],
    feature_audit: list[dict[str, str]],
) -> dict[str, Any]:
    participants = sorted({str(row.get("participant_id", "")) for row in rows if row.get("participant_id")})
    trial_ids = sorted({str(row.get("trial_id", "")) for row in rows if row.get("trial_id")})
    issue_counts = Counter(issue["code"] for issue in issues)
    feature_counts = Counter(item["status"] for item in feature_audit)
    return {
        "input_csv": str(raw_export_csv),
        "stimulus_config_json": str(stimulus_config_json),
        "feature_table_csv": str(feature_table_csv),
        "canonical_row_unit": "participant x trial x candidate_mix",
        "participant_count": len(participants),
        "trial_count": len(trial_ids),
        "candidate_row_count": len(rows),
        "complete_trial_count": len({row["trial_id"] for row in rows if row.get("trial_validation_status") == "complete"}),
        "incomplete_or_malformed_trial_count": len({row["trial_id"] for row in rows if row.get("trial_validation_status") != "complete"}),
        "issue_counts": dict(sorted(issue_counts.items())),
        "feature_audit_counts": dict(sorted(feature_counts.items())),
        "contains_preference_labels": any(
            any(forbidden in column.lower() for forbidden in ["winner", "preferred", "preference_label", "observed_ranking"])
            for column in CANONICAL_COLUMNS
        ),
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_analysis_ready_outputs(
    raw_export_csv: Path,
    stimulus_config_json: Path,
    feature_table_csv: Path,
    output_dir: Path,
) -> tuple[Path, Path, Path, Path]:
    rows, issues, summary, feature_audit = build_analysis_ready_dataset(raw_export_csv, stimulus_config_json, feature_table_csv)
    analysis_path = output_dir / "analysis_ready_long.csv"
    issues_path = output_dir / "analysis_ready_validation_issues.csv"
    summary_path = output_dir / "analysis_ready_validation_summary.json"
    feature_audit_path = output_dir / "acoustic_feature_join_audit.csv"
    write_csv(analysis_path, rows, CANONICAL_COLUMNS)
    write_csv(issues_path, issues, ISSUE_COLUMNS)
    write_json(summary_path, summary)
    write_csv(feature_audit_path, feature_audit, FEATURE_AUDIT_COLUMNS)
    return analysis_path, issues_path, summary_path, feature_audit_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Phase 6B.1 LLM analysis-ready long-format data.")
    parser.add_argument("--input", required=True, type=Path, help="Raw Netlify participant-level CSV export.")
    parser.add_argument(
        "--stimuli",
        type=Path,
        default=Path("study-interface/frontend-5mix/config/stimuli.json"),
        help="Active five-mix stimuli config.",
    )
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("statistical-baseline/outputs/feature_exploration/final_20_stimulus_feature_table.csv"),
        help="Canonical final-20 acoustic feature table.",
    )
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory for generated analysis-ready outputs.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    analysis_path, issues_path, summary_path, feature_audit_path = write_analysis_ready_outputs(
        args.input,
        args.stimuli,
        args.features,
        args.output_dir,
    )
    print(f"Wrote analysis-ready rows to {analysis_path}")
    print(f"Wrote validation issues to {issues_path}")
    print(f"Wrote validation summary to {summary_path}")
    print(f"Wrote acoustic feature audit to {feature_audit_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
