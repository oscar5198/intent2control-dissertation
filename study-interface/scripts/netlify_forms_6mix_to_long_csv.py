#!/usr/bin/env python3
"""Process six-mix Netlify exports into analysis-ready response and metadata files.

The utility keeps the raw Netlify participant-level CSV separate from the
analysis outputs. It parses the structured JSON fields, writes one long response
row per displayed mix, writes one metadata row per study trial, and reports any
data-integrity issues instead of silently dropping problematic records.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BASE_LONG_FIELDS = [
    "study_id",
    "study_version",
    "schema_version",
    "stimulus_configuration_version",
    "study_group",
    "group_id",
    "started_at",
    "completed_at",
    "duration_seconds",
]

RESPONSE_FIELDS = [
    "trial_index",
    "scenario_id",
    "episode_id",
    "episode_position",
    "song_id",
    "excerpt_id",
    "song_position",
    "display_label",
    "display_position",
    "actual_mix_id",
    "stimulus_id",
    "audio_path",
    "rating",
    "rating_set",
    "audio_played",
    "first_play_timestamp",
    "comment",
    "comparative_comment",
    "response_time_ms",
]

BASE_METADATA_FIELDS = [
    "study_id",
    "study_version",
    "schema_version",
    "stimulus_configuration_version",
    "study_group",
    "group_id",
    "started_at",
    "completed_at",
    "trial_index",
    "episode_id",
    "scenario_id",
    "episode_position",
    "song_id",
    "excerpt_id",
    "song_position",
    "displayed_mix_count",
    "display_order",
    "stimulus_ids_shown",
    "actual_mix_ids_shown",
    "trial_response_time_ms",
    "comment",
    "metadata_validation_status",
    "metadata_validation_notes",
]

ISSUE_FIELDS = ["source_row", "study_id", "field", "code", "message"]
JSON_FIELD_HINTS = {
    "assigned_song_ids_json",
    "episode_order_json",
    "scenario_order_json",
    "song_order_json",
    "mix_mapping_json",
    "presentation_order_json",
    "responses_json",
    "trial_records_json",
    "client_validation_json",
}
PRIVACY_FIELD_PATTERNS = ("ip", "user_agent", "useragent")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Process a Netlify listening-study-6mix CSV export into "
            "responses_long.csv, experiment_metadata.csv, and "
            "export_validation_report.json."
        )
    )
    parser.add_argument("input_csv_pos", nargs="?", type=Path, help="Netlify CSV export.")
    parser.add_argument(
        "output_csv_pos",
        nargs="?",
        type=Path,
        help="Legacy long-format output CSV path. Prefer --output-dir for new runs.",
    )
    parser.add_argument("--input", dest="input_csv", type=Path, help="Netlify CSV export.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for generated exports. Defaults to the input CSV directory.",
    )
    parser.add_argument("--responses-output", type=Path, default=None, help="Long response CSV path.")
    parser.add_argument("--metadata-output", type=Path, default=None, help="Experiment metadata CSV path.")
    parser.add_argument("--validation-report", type=Path, default=None, help="Validation JSON path.")
    parser.add_argument("--issues-csv", type=Path, default=None, help="Optional issue CSV path.")
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Backward-compatible alias for --issues-csv.",
    )
    return parser.parse_args()


def normalise_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def build_column_map(fieldnames: list[str]) -> dict[str, str]:
    return {normalise_header(name): name for name in fieldnames}


def get_value(row: dict[str, str], column_map: dict[str, str], name: str, default: str = "") -> str:
    column = column_map.get(normalise_header(name))
    if not column:
        return default
    value = row.get(column)
    return default if value is None else value


def add_issue(
    issues: list[dict[str, str]],
    row_number: int,
    study_id: str,
    field: str,
    code: str,
    message: str,
) -> None:
    issues.append(
        {
            "source_row": str(row_number),
            "study_id": study_id,
            "field": field,
            "code": code,
            "message": message,
        }
    )


def safe_json(
    row: dict[str, str],
    column_map: dict[str, str],
    row_number: int,
    study_id: str,
    field: str,
    issues: list[dict[str, str]],
    required: bool = False,
) -> Any:
    value = get_value(row, column_map, field)
    if value == "":
        if required:
            add_issue(issues, row_number, study_id, field, "missing_json", "JSON field is empty.")
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        add_issue(issues, row_number, study_id, field, "malformed_json", str(exc))
        return None


def load_rows(input_csv: Path) -> tuple[list[dict[str, str]], list[str], dict[str, str]]:
    with input_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    return rows, fieldnames, build_column_map(fieldnames)


def detect_json_columns(rows: list[dict[str, str]], fieldnames: list[str]) -> list[str]:
    result = []
    for name in fieldnames:
        normalised = normalise_header(name)
        values = [row.get(name, "") for row in rows if row.get(name, "")]
        if normalised in JSON_FIELD_HINTS or normalised.endswith("_json"):
            result.append(name)
        elif values and any(value.strip().startswith(("[", "{")) for value in values[:5]):
            result.append(name)
    return result


def participant_values(row: dict[str, str], column_map: dict[str, str]) -> dict[str, str]:
    group_id = get_value(row, column_map, "group_id") or get_value(row, column_map, "study_group")
    return {
        "study_id": get_value(row, column_map, "study_id"),
        "study_version": get_value(row, column_map, "study_version"),
        "schema_version": get_value(row, column_map, "schema_version"),
        "stimulus_configuration_version": get_value(row, column_map, "stimulus_configuration_version"),
        "study_group": get_value(row, column_map, "study_group") or group_id,
        "group_id": group_id,
        "started_at": get_value(row, column_map, "started_at"),
        "completed_at": get_value(row, column_map, "completed_at"),
        "duration_seconds": get_value(row, column_map, "duration_seconds"),
    }


def convert_export(
    rows: list[dict[str, str]],
    fieldnames: list[str],
    column_map: dict[str, str],
    input_csv: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]], dict[str, Any], list[str]]:
    issues: list[dict[str, str]] = []
    long_rows: list[dict[str, Any]] = []
    metadata_rows: list[dict[str, Any]] = []
    all_labels: set[str] = set()
    row_response_counts: dict[str, int] = {}
    trial_counts_by_study: dict[str, int] = {}
    study_id_counts = Counter(
        get_value(row, column_map, "study_id") for row in rows if get_value(row, column_map, "study_id")
    )
    duplicate_study_ids = sorted([study_id for study_id, count in study_id_counts.items() if count > 1])
    malformed_json_count_start = 0

    for row_number, row in enumerate(rows, start=2):
        participant = participant_values(row, column_map)
        study_id = participant["study_id"]
        if not study_id:
            add_issue(issues, row_number, study_id, "study_id", "missing_study_id", "Missing study_id.")
        if study_id and study_id_counts[study_id] > 1:
            add_issue(
                issues,
                row_number,
                study_id,
                "study_id",
                "duplicate_study_id",
                f"Study ID appears {study_id_counts[study_id]} times in this export.",
            )

        responses = safe_json(row, column_map, row_number, study_id, "responses_json", issues, required=True)
        client_validation = safe_json(row, column_map, row_number, study_id, "client_validation_json", issues)
        assigned_song_ids = safe_json(row, column_map, row_number, study_id, "assigned_song_ids_json", issues) or []
        episode_order = safe_json(row, column_map, row_number, study_id, "episode_order_json", issues)
        scenario_order = safe_json(row, column_map, row_number, study_id, "scenario_order_json", issues)
        song_order = safe_json(row, column_map, row_number, study_id, "song_order_json", issues) or {}
        mix_mapping = safe_json(row, column_map, row_number, study_id, "mix_mapping_json", issues) or {}
        presentation_order = safe_json(row, column_map, row_number, study_id, "presentation_order_json", issues) or {}

        if not isinstance(responses, list):
            add_issue(
                issues,
                row_number,
                study_id,
                "responses_json",
                "responses_not_list",
                "responses_json did not parse to a list.",
            )
            continue

        row_response_counts[study_id or f"row_{row_number}"] = len(responses)
        validate_client_counts(client_validation, len(responses), row, column_map, row_number, study_id, issues)

        valid_episode_ids = set()
        for order_source in (episode_order, scenario_order):
            if isinstance(order_source, list):
                valid_episode_ids.update(str(item) for item in order_source)
        if isinstance(song_order, dict):
            valid_episode_ids.update(str(key) for key in song_order.keys())
        if isinstance(mix_mapping, dict):
            valid_episode_ids.update(str(key) for key in mix_mapping.keys())

        trial_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        seen_response_keys: set[tuple[str, str, str, str]] = set()
        for response_index, response in enumerate(responses, start=1):
            if not isinstance(response, dict):
                add_issue(
                    issues,
                    row_number,
                    study_id,
                    f"responses_json[{response_index}]",
                    "response_not_object",
                    f"Response {response_index} is not an object.",
                )
                continue

            response = normalise_response(response)
            response_issues = validate_response(
                response,
                assigned_song_ids,
                valid_episode_ids,
                mix_mapping,
                row_number,
                study_id,
                response_index,
                issues,
            )
            key = (
                str(response.get("trial_index", "")),
                str(response.get("episode_id", "")),
                str(response.get("song_id", "")),
                str(response.get("display_label", "")),
            )
            if key in seen_response_keys:
                add_issue(
                    issues,
                    row_number,
                    study_id,
                    f"responses_json[{response_index}]",
                    "duplicate_response_within_trial",
                    f"Duplicate response key {key}.",
                )
                response_issues.append("duplicate response")
            seen_response_keys.add(key)

            trial_key = (
                str(response.get("trial_index", "")),
                str(response.get("episode_id", "")),
                str(response.get("song_id", "")),
            )
            trial_groups[trial_key].append(response)
            all_labels.add(str(response.get("display_label", "")))

            long_row = dict(participant)
            long_row.update(response)
            long_row["comment"] = response.get("comparative_comment", "")
            long_row["_validation_notes"] = " | ".join(response_issues)
            long_rows.append(long_row)

        trial_counts_by_study[study_id or f"row_{row_number}"] = len(trial_groups)
        for trial_key, trial_responses in sorted(trial_groups.items(), key=trial_sort_key):
            metadata_rows.append(
                build_metadata_row(
                    participant,
                    trial_responses,
                    mix_mapping,
                    presentation_order,
                    row_number,
                    study_id,
                    issues,
                )
            )

    json_columns = detect_json_columns(rows, fieldnames)
    malformed_json_count = sum(1 for issue in issues if issue["code"] == "malformed_json")
    missing_stimulus_ids = sum(1 for issue in issues if issue["code"] == "missing_stimulus_id")
    missing_mix_mappings = sum(1 for issue in issues if issue["code"] == "missing_mix_mapping")
    mapping_disagreements = sum(1 for issue in issues if issue["code"] == "mapping_response_disagreement")
    invalid_episode_ids = sum(1 for issue in issues if issue["code"] == "invalid_episode_id")
    unassigned_song_ids = sum(1 for issue in issues if issue["code"] == "unassigned_song_id")
    duplicate_responses = sum(1 for issue in issues if issue["code"] == "duplicate_response_within_trial")
    inconsistent_comments = sum(1 for issue in issues if issue["code"] == "inconsistent_trial_comments")
    unexpected_mix_counts = sum(1 for issue in issues if issue["code"] == "unexpected_mix_count")
    privacy_columns = detect_privacy_columns(fieldnames)

    report = {
        "input_csv": str(input_csv),
        "csv_columns": fieldnames,
        "structured_json_columns": json_columns,
        "submissions": len(rows),
        "unique_study_ids": len(study_id_counts),
        "duplicate_study_ids": duplicate_study_ids,
        "completed_submissions": sum(1 for row in rows if is_completed_submission(row, column_map)),
        "incomplete_submissions": sum(1 for row in rows if not is_completed_submission(row, column_map)),
        "one_row_per_completed_submission": len(rows) == len(study_id_counts) and not duplicate_study_ids,
        "response_counts_by_study_id": row_response_counts,
        "trial_counts_by_study_id": trial_counts_by_study,
        "total_long_format_response_rows": len(long_rows),
        "total_metadata_trial_rows": len(metadata_rows),
        "malformed_json_fields": malformed_json_count,
        "missing_stimulus_ids": missing_stimulus_ids,
        "missing_mix_mappings": missing_mix_mappings,
        "mapping_response_disagreements": mapping_disagreements,
        "invalid_episode_ids": invalid_episode_ids,
        "unassigned_song_ids": unassigned_song_ids,
        "unexpected_number_of_mixes_per_trial": unexpected_mix_counts,
        "duplicate_responses_within_trial": duplicate_responses,
        "inconsistent_comments_within_trial": inconsistent_comments,
        "every_trial_fully_reconstructable": all(
            row.get("metadata_validation_status") == "valid" for row in metadata_rows
        ),
        "privacy_columns_in_raw_export": privacy_columns,
        "analysis_outputs_exclude_privacy_columns": True,
        "overall_status": "pass" if not issues and metadata_rows else "fail",
        "issues": issues,
    }
    return long_rows, metadata_rows, issues, report, sorted(label for label in all_labels if label)


def normalise_response(response: dict[str, Any]) -> dict[str, Any]:
    result = dict(response)
    if not result.get("episode_id") and result.get("scenario_id"):
        result["episode_id"] = result.get("scenario_id")
    if not result.get("scenario_id") and result.get("episode_id"):
        result["scenario_id"] = result.get("episode_id")
    if "comment" not in result:
        result["comment"] = result.get("comparative_comment", "")
    if "comparative_comment" not in result:
        result["comparative_comment"] = result.get("comment", "")
    return result


def validate_client_counts(
    client_validation: Any,
    actual_response_count: int,
    row: dict[str, str],
    column_map: dict[str, str],
    row_number: int,
    study_id: str,
    issues: list[dict[str, str]],
) -> None:
    if isinstance(client_validation, dict):
        expected = client_validation.get("expected_response_count")
        actual = client_validation.get("actual_response_count")
        if isinstance(actual, int) and actual != actual_response_count:
            add_issue(
                issues,
                row_number,
                study_id,
                "client_validation_json",
                "expected_actual_mismatch",
                f"actual_response_count={actual}, parsed responses={actual_response_count}.",
            )
        if isinstance(expected, int) and isinstance(actual, int) and expected != actual:
            add_issue(
                issues,
                row_number,
                study_id,
                "client_validation_json",
                "expected_actual_mismatch",
                f"expected_response_count={expected}, actual_response_count={actual}.",
            )
    rating_count = get_value(row, column_map, "rating_count")
    if rating_count and rating_count.isdigit() and int(rating_count) != actual_response_count:
        add_issue(
            issues,
            row_number,
            study_id,
            "rating_count",
            "response_count_mismatch",
            f"rating_count={rating_count}, parsed responses={actual_response_count}.",
        )


def validate_response(
    response: dict[str, Any],
    assigned_song_ids: Any,
    valid_episode_ids: set[str],
    mix_mapping: Any,
    row_number: int,
    study_id: str,
    response_index: int,
    issues: list[dict[str, str]],
) -> list[str]:
    notes: list[str] = []
    episode_id = str(response.get("episode_id", "") or "")
    song_id = str(response.get("song_id", "") or "")
    display_label = str(response.get("display_label", "") or "")
    stimulus_id = str(response.get("stimulus_id", "") or "")

    for field in ["episode_id", "song_id", "display_label", "stimulus_id", "rating", "comparative_comment"]:
        if response.get(field) in (None, ""):
            code = "missing_stimulus_id" if field == "stimulus_id" else "missing_response_field"
            add_issue(
                issues,
                row_number,
                study_id,
                f"responses_json[{response_index}].{field}",
                code,
                f"Response {response_index} is missing {field}.",
            )
            notes.append(f"missing {field}")

    rating = response.get("rating")
    if not isinstance(rating, int) or rating < 0 or rating > 100:
        add_issue(
            issues,
            row_number,
            study_id,
            f"responses_json[{response_index}].rating",
            "rating_not_integer_0_100",
            f"Response {response_index} rating is not an integer in 0-100.",
        )
        notes.append("invalid rating")

    if isinstance(assigned_song_ids, list) and assigned_song_ids and song_id not in assigned_song_ids:
        add_issue(
            issues,
            row_number,
            study_id,
            f"responses_json[{response_index}].song_id",
            "unassigned_song_id",
            f"Response song_id {song_id!r} is not in assigned_song_ids_json.",
        )
        notes.append("unassigned song")

    if valid_episode_ids and episode_id not in valid_episode_ids:
        add_issue(
            issues,
            row_number,
            study_id,
            f"responses_json[{response_index}].episode_id",
            "invalid_episode_id",
            f"Response episode_id {episode_id!r} is not present in exported episode/order/mapping fields.",
        )
        notes.append("invalid episode")

    expected_stimulus = get_mapping_stimulus(mix_mapping, episode_id, song_id, display_label)
    if expected_stimulus is None:
        add_issue(
            issues,
            row_number,
            study_id,
            f"mix_mapping_json.{episode_id}.{song_id}.{display_label}",
            "missing_mix_mapping",
            "No exported mix mapping found for this response label.",
        )
        notes.append("missing mapping")
    elif stimulus_id and expected_stimulus != stimulus_id:
        add_issue(
            issues,
            row_number,
            study_id,
            f"responses_json[{response_index}].stimulus_id",
            "mapping_response_disagreement",
            f"Response stimulus_id={stimulus_id!r}, mapping stimulus_id={expected_stimulus!r}.",
        )
        notes.append("mapping disagreement")

    return notes


def get_mapping_stimulus(mix_mapping: Any, episode_id: str, song_id: str, display_label: str) -> str | None:
    if not isinstance(mix_mapping, dict):
        return None
    episode_mapping = mix_mapping.get(episode_id)
    if not isinstance(episode_mapping, dict):
        return None
    song_mapping = episode_mapping.get(song_id)
    if not isinstance(song_mapping, dict):
        return None
    value = song_mapping.get(display_label)
    return str(value) if value not in (None, "") else None


def trial_sort_key(item: tuple[tuple[str, str, str], list[dict[str, Any]]]) -> tuple[int, str, str]:
    trial_index = item[0][0]
    try:
        return (int(trial_index), item[0][1], item[0][2])
    except ValueError:
        return (999999, item[0][1], item[0][2])


def response_sort_key(response: dict[str, Any]) -> tuple[int, str]:
    display_position = response.get("display_position")
    try:
        return (int(display_position), str(response.get("display_label", "")))
    except (TypeError, ValueError):
        return (999999, str(response.get("display_label", "")))


def build_metadata_row(
    participant: dict[str, str],
    responses: list[dict[str, Any]],
    mix_mapping: Any,
    presentation_order: Any,
    row_number: int,
    study_id: str,
    issues: list[dict[str, str]],
) -> dict[str, Any]:
    ordered = sorted(responses, key=response_sort_key)
    first = ordered[0]
    labels = [str(response.get("display_label", "")) for response in ordered]
    stimulus_ids = [str(response.get("stimulus_id", "")) for response in ordered]
    actual_mix_ids = [str(response.get("actual_mix_id", "")) for response in ordered]
    comments = sorted(
        {
            str(response.get("comparative_comment", "") or "")
            for response in ordered
            if str(response.get("comparative_comment", "") or "").strip()
        }
    )
    notes: list[str] = []

    episode_id = str(first.get("episode_id", ""))
    song_id = str(first.get("song_id", ""))
    exported_order = get_presentation_order(presentation_order, episode_id, song_id)
    if exported_order and labels != exported_order:
        notes.append("display order differs from presentation_order_json")
        add_issue(
            issues,
            row_number,
            study_id,
            f"presentation_order_json.{episode_id}.{song_id}",
            "presentation_order_disagreement",
            f"responses order {labels!r}, presentation_order_json {exported_order!r}.",
        )

    mapping_labels = get_mapping_labels(mix_mapping, episode_id, song_id)
    if mapping_labels and set(mapping_labels) != set(labels):
        notes.append("mapping labels differ from response labels")
        add_issue(
            issues,
            row_number,
            study_id,
            f"mix_mapping_json.{episode_id}.{song_id}",
            "unexpected_mix_count",
            f"mapping labels {mapping_labels!r}, response labels {labels!r}.",
        )

    if len(set(labels)) != len(labels):
        notes.append("duplicate display label")
    if len(set(stimulus_ids)) != len(stimulus_ids):
        notes.append("duplicate stimulus_id")
    if any(not value for value in stimulus_ids):
        notes.append("missing stimulus_id")
    if len(comments) != 1:
        notes.append("inconsistent or missing trial comments")
        add_issue(
            issues,
            row_number,
            study_id,
            f"responses_json.trial_{first.get('trial_index', '')}.comparative_comment",
            "inconsistent_trial_comments",
            f"Found {len(comments)} distinct non-empty comments for this trial.",
        )

    row: dict[str, Any] = {
        **participant,
        "trial_index": first.get("trial_index", ""),
        "episode_id": episode_id,
        "scenario_id": first.get("scenario_id", episode_id),
        "episode_position": first.get("episode_position", ""),
        "song_id": song_id,
        "excerpt_id": first.get("excerpt_id", ""),
        "song_position": first.get("song_position", ""),
        "displayed_mix_count": len(ordered),
        "display_order": " | ".join(labels),
        "stimulus_ids_shown": " | ".join(stimulus_ids),
        "actual_mix_ids_shown": " | ".join(actual_mix_ids),
        "trial_response_time_ms": first.get("response_time_ms", ""),
        "comment": comments[0] if len(comments) == 1 else " | ".join(comments),
        "metadata_validation_status": "valid" if not notes else "invalid",
        "metadata_validation_notes": " | ".join(notes),
    }

    for response in ordered:
        label = str(response.get("display_label", ""))
        safe_label = safe_label_name(label)
        row[f"label_{safe_label}_stimulus_id"] = response.get("stimulus_id", "")
        row[f"label_{safe_label}_actual_mix_id"] = response.get("actual_mix_id", "")
    return row


def get_presentation_order(presentation_order: Any, episode_id: str, song_id: str) -> list[str]:
    if not isinstance(presentation_order, dict):
        return []
    episode = presentation_order.get(episode_id)
    if not isinstance(episode, dict):
        return []
    order = episode.get(song_id)
    return [str(item) for item in order] if isinstance(order, list) else []


def get_mapping_labels(mix_mapping: Any, episode_id: str, song_id: str) -> list[str]:
    if not isinstance(mix_mapping, dict):
        return []
    episode = mix_mapping.get(episode_id)
    if not isinstance(episode, dict):
        return []
    mapping = episode.get(song_id)
    return sorted(str(key) for key in mapping.keys()) if isinstance(mapping, dict) else []


def safe_label_name(label: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "_", label.strip()).strip("_")
    return value or "unknown"


def is_completed_submission(row: dict[str, str], column_map: dict[str, str]) -> bool:
    status = get_value(row, column_map, "submission_status").strip().lower()
    completed_at = get_value(row, column_map, "completed_at").strip()
    responses = get_value(row, column_map, "responses_json").strip()
    return status in ("completed", "local_only_completed") or bool(completed_at and responses)


def detect_privacy_columns(fieldnames: list[str]) -> list[str]:
    result = []
    for field in fieldnames:
        normalised = normalise_header(field)
        if any(pattern in normalised for pattern in PRIVACY_FIELD_PATTERNS):
            result.append(field)
    return result


def has_raw_responses_json(rows: list[dict[str, str]], column_map: dict[str, str]) -> bool:
    column = column_map.get("responses_json")
    return bool(column and any(row.get(column, "").strip() for row in rows))


def convert_long_export(
    rows: list[dict[str, str]],
    fieldnames: list[str],
    column_map: dict[str, str],
    input_csv: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]], dict[str, Any], list[str]]:
    issues: list[dict[str, str]] = []
    long_rows: list[dict[str, Any]] = []
    metadata_rows: list[dict[str, Any]] = []
    all_labels: set[str] = set()
    privacy_columns = detect_privacy_columns(fieldnames)

    study_ids = sorted({get_value(row, column_map, "study_id") for row in rows if get_value(row, column_map, "study_id")})
    for study_id in study_ids or [""]:
        add_issue(
            issues,
            1,
            study_id,
            "responses_json",
            "raw_netlify_json_unavailable",
            "Input appears to be a long-format response CSV, not the raw Netlify participant-level export.",
        )

    trial_groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    seen_response_keys: set[tuple[str, str, str, str, str]] = set()
    for row_number, row in enumerate(rows, start=2):
        participant = participant_values(row, column_map)
        response = {
            "trial_index": get_value(row, column_map, "trial_index"),
            "scenario_id": get_value(row, column_map, "scenario_id") or get_value(row, column_map, "episode_id"),
            "episode_id": get_value(row, column_map, "episode_id") or get_value(row, column_map, "scenario_id"),
            "episode_position": get_value(row, column_map, "episode_position"),
            "song_id": get_value(row, column_map, "song_id"),
            "excerpt_id": get_value(row, column_map, "excerpt_id"),
            "song_position": get_value(row, column_map, "song_position"),
            "display_label": get_value(row, column_map, "display_label"),
            "display_position": get_value(row, column_map, "display_position"),
            "actual_mix_id": get_value(row, column_map, "actual_mix_id"),
            "stimulus_id": get_value(row, column_map, "stimulus_id"),
            "audio_path": get_value(row, column_map, "audio_path"),
            "rating": get_value(row, column_map, "rating"),
            "rating_set": get_value(row, column_map, "rating_set"),
            "audio_played": get_value(row, column_map, "audio_played"),
            "first_play_timestamp": get_value(row, column_map, "first_play_timestamp"),
            "comment": get_value(row, column_map, "comment") or get_value(row, column_map, "comparative_comment"),
            "comparative_comment": get_value(row, column_map, "comparative_comment") or get_value(row, column_map, "comment"),
            "response_time_ms": get_value(row, column_map, "response_time_ms"),
        }
        notes: list[str] = []
        if not response["stimulus_id"]:
            add_issue(issues, row_number, participant["study_id"], "stimulus_id", "missing_stimulus_id", "Missing stimulus_id.")
            notes.append("missing stimulus_id")
        if not response["actual_mix_id"]:
            add_issue(issues, row_number, participant["study_id"], "actual_mix_id", "missing_actual_mix_id", "Missing actual_mix_id.")
            notes.append("missing actual_mix_id")
        if not response["comparative_comment"].strip():
            add_issue(issues, row_number, participant["study_id"], "comparative_comment", "missing_response_field", "Missing comment.")
            notes.append("missing comment")
        rating = response["rating"]
        if not str(rating).isdigit() or not 0 <= int(rating) <= 100:
            add_issue(issues, row_number, participant["study_id"], "rating", "rating_not_integer_0_100", "Rating is not an integer in 0-100.")
            notes.append("invalid rating")
        key = (
            participant["study_id"],
            str(response["trial_index"]),
            str(response["episode_id"]),
            str(response["song_id"]),
            str(response["display_label"]),
        )
        if key in seen_response_keys:
            add_issue(issues, row_number, participant["study_id"], "display_label", "duplicate_response_within_trial", f"Duplicate response key {key}.")
            notes.append("duplicate response")
        seen_response_keys.add(key)
        long_row = dict(participant)
        long_row.update(response)
        long_row["_validation_notes"] = " | ".join(notes)
        long_rows.append(long_row)
        all_labels.add(str(response["display_label"]))
        trial_groups[(participant["study_id"], str(response["trial_index"]), str(response["episode_id"]), str(response["song_id"]))].append(response | {"_participant": participant})

    for (_study_id, _trial_index, _episode_id, _song_id), trial_responses in sorted(trial_groups.items()):
        participant = trial_responses[0].pop("_participant")
        for response in trial_responses[1:]:
            response.pop("_participant", None)
        metadata_rows.append(build_metadata_row(participant, trial_responses, {}, {}, 1, participant["study_id"], issues))

    study_id_counts = Counter(row["study_id"] for row in long_rows if row.get("study_id"))
    report = {
        "input_csv": str(input_csv),
        "input_interpreted_as": "long_format_response_csv",
        "csv_columns": fieldnames,
        "structured_json_columns": [],
        "submissions": len(study_id_counts),
        "unique_study_ids": len(study_id_counts),
        "duplicate_study_ids": [],
        "completed_submissions": len(study_id_counts),
        "incomplete_submissions": 0,
        "one_row_per_completed_submission": False,
        "response_counts_by_study_id": dict(Counter(row["study_id"] for row in long_rows)),
        "trial_counts_by_study_id": dict(Counter(row["study_id"] for row in metadata_rows)),
        "total_long_format_response_rows": len(long_rows),
        "total_metadata_trial_rows": len(metadata_rows),
        "malformed_json_fields": 0,
        "missing_stimulus_ids": sum(1 for issue in issues if issue["code"] == "missing_stimulus_id"),
        "missing_mix_mappings": "not_checkable_without_raw_mix_mapping_json",
        "mapping_response_disagreements": "not_checkable_without_raw_mix_mapping_json",
        "invalid_episode_ids": "not_checkable_without_raw_order_json",
        "unassigned_song_ids": "not_checkable_without_raw_assigned_song_ids_json",
        "unexpected_number_of_mixes_per_trial": sum(1 for issue in issues if issue["code"] == "unexpected_mix_count"),
        "duplicate_responses_within_trial": sum(1 for issue in issues if issue["code"] == "duplicate_response_within_trial"),
        "inconsistent_comments_within_trial": sum(1 for issue in issues if issue["code"] == "inconsistent_trial_comments"),
        "every_trial_fully_reconstructable": all(row.get("metadata_validation_status") == "valid" for row in metadata_rows),
        "privacy_columns_in_raw_export": privacy_columns,
        "analysis_outputs_exclude_privacy_columns": True,
        "overall_status": "fail",
        "issues": issues,
    }
    return long_rows, metadata_rows, issues, report, sorted(label for label in all_labels if label)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, Path, Path, Path]:
    input_csv = args.input_csv or args.input_csv_pos
    if not input_csv:
        raise SystemExit("Provide an input CSV path with --input or as the first positional argument.")

    if args.output_dir:
        output_dir = args.output_dir
    elif args.output_csv_pos:
        output_dir = args.output_csv_pos.parent
    else:
        output_dir = input_csv.parent

    responses_output = args.responses_output or args.output_csv_pos or output_dir / "responses_long.csv"
    metadata_output = args.metadata_output or output_dir / "experiment_metadata.csv"
    validation_report = args.validation_report or output_dir / "export_validation_report.json"
    issues_csv = args.issues_csv or args.report or output_dir / "export_validation_issues.csv"
    return input_csv, responses_output, metadata_output, validation_report, issues_csv


def main() -> int:
    args = parse_args()
    input_csv, responses_output, metadata_output, validation_report, issues_csv = resolve_paths(args)
    rows, fieldnames, column_map = load_rows(input_csv)
    if has_raw_responses_json(rows, column_map):
        long_rows, metadata_rows, issues, report, labels = convert_export(rows, fieldnames, column_map, input_csv)
    else:
        long_rows, metadata_rows, issues, report, labels = convert_long_export(rows, fieldnames, column_map, input_csv)

    long_fields = BASE_LONG_FIELDS + RESPONSE_FIELDS
    label_fields = []
    for label in labels:
        safe_label = safe_label_name(label)
        label_fields.extend([f"label_{safe_label}_stimulus_id", f"label_{safe_label}_actual_mix_id"])
    metadata_fields = BASE_METADATA_FIELDS + label_fields

    write_csv(responses_output, long_rows, long_fields)
    write_csv(metadata_output, metadata_rows, metadata_fields)
    write_csv(issues_csv, issues, ISSUE_FIELDS)
    report.update(
        {
            "responses_long_csv": str(responses_output),
            "experiment_metadata_csv": str(metadata_output),
            "issues_csv": str(issues_csv),
        }
    )
    write_json(validation_report, report)

    print(f"Wrote {len(long_rows)} long-format rows to {responses_output}")
    print(f"Wrote {len(metadata_rows)} metadata trial rows to {metadata_output}")
    print(f"Wrote validation report to {validation_report}")
    print(f"Wrote {len(issues)} validation issues to {issues_csv}")
    return 0 if report["overall_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
