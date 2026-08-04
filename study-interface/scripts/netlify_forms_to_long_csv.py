#!/usr/bin/env python3
"""Convert Netlify listening-study form exports into long-format ratings data."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


PARTICIPANT_FIELDS = [
    "study_id",
    "study_version",
    "study_group",
    "started_at",
    "completed_at",
    "duration_seconds",
]

RESPONSE_FIELDS = [
    "episode_id",
    "episode_position",
    "song_id",
    "song_position",
    "display_label",
    "display_position",
    "stimulus_id",
    "rating",
    "comment",
    "response_time_ms",
]

LONG_FIELDS = PARTICIPANT_FIELDS + RESPONSE_FIELDS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a Netlify listening-study CSV export to long-format CSV."
    )
    parser.add_argument("input_csv", type=Path, help="Netlify CSV export.")
    parser.add_argument("output_csv", type=Path, help="Long-format output CSV.")
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Validation report CSV path. Defaults to '<output>_validation_report.csv'.",
    )
    return parser.parse_args()


def safe_json(value: str, row_number: int, field: str, issues: list[dict[str, str]]) -> Any:
    if value is None or value == "":
        issues.append(issue(row_number, field, "missing_json", "JSON field is empty."))
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        issues.append(issue(row_number, field, "malformed_json", str(exc)))
        return None


def issue(row_number: int, field: str, code: str, message: str) -> dict[str, str]:
    return {
        "source_row": str(row_number),
        "study_id": "",
        "field": field,
        "code": code,
        "message": message,
    }


def add_issue(
    issues: list[dict[str, str]],
    row_number: int,
    study_id: str,
    field: str,
    code: str,
    message: str,
) -> None:
    item = issue(row_number, field, code, message)
    item["study_id"] = study_id
    issues.append(item)


def load_rows(input_csv: Path) -> list[dict[str, str]]:
    with input_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def convert(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    long_rows: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    study_id_counts = Counter(row.get("study_id", "") for row in rows if row.get("study_id"))

    for row_number, row in enumerate(rows, start=2):
        study_id = row.get("study_id", "")
        responses = safe_json(row.get("responses_json", ""), row_number, "responses_json", issues)
        client_validation = safe_json(
            row.get("client_validation_json", ""), row_number, "client_validation_json", issues
        )

        if study_id and study_id_counts[study_id] > 1:
            add_issue(
                issues,
                row_number,
                study_id,
                "study_id",
                "duplicate_study_id",
                f"Study ID appears {study_id_counts[study_id]} times in this export.",
            )
        if not study_id:
            add_issue(issues, row_number, study_id, "study_id", "missing_study_id", "Missing study_id.")

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

        expected = None
        if isinstance(client_validation, dict):
            expected = client_validation.get("expected_response_count")
            actual = client_validation.get("actual_response_count")
            if expected != actual:
                add_issue(
                    issues,
                    row_number,
                    study_id,
                    "client_validation_json",
                    "expected_actual_mismatch",
                    f"expected_response_count={expected}, actual_response_count={actual}.",
                )
        if isinstance(expected, int) and len(responses) != expected:
            add_issue(
                issues,
                row_number,
                study_id,
                "responses_json",
                "response_count_mismatch",
                f"Found {len(responses)} response objects, expected {expected}.",
            )

        for response_index, response in enumerate(responses, start=1):
            if not isinstance(response, dict):
                add_issue(
                    issues,
                    row_number,
                    study_id,
                    "responses_json",
                    "response_not_object",
                    f"Response {response_index} is not an object.",
                )
                continue
            validate_response(response, row_number, study_id, response_index, issues)
            long_row = {field: row.get(field, "") for field in PARTICIPANT_FIELDS}
            for field in RESPONSE_FIELDS:
                long_row[field] = response.get(field, "")
            long_rows.append(long_row)

    return long_rows, issues


def validate_response(
    response: dict[str, Any],
    row_number: int,
    study_id: str,
    response_index: int,
    issues: list[dict[str, str]],
) -> None:
    required = ["episode_id", "song_id", "display_label", "stimulus_id", "rating", "comment"]
    for field in required:
        value = response.get(field)
        if value is None or value == "":
            add_issue(
                issues,
                row_number,
                study_id,
                f"responses_json[{response_index}].{field}",
                "missing_response_field",
                f"Response {response_index} is missing {field}.",
            )
    rating = response.get("rating")
    if not isinstance(rating, (int, float)):
        add_issue(
            issues,
            row_number,
            study_id,
            f"responses_json[{response_index}].rating",
            "rating_not_numeric",
            f"Response {response_index} rating is not numeric.",
        )


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    report_path = args.report or args.output_csv.with_name(
        args.output_csv.stem + "_validation_report.csv"
    )
    rows = load_rows(args.input_csv)
    long_rows, issues = convert(rows)
    write_csv(args.output_csv, long_rows, LONG_FIELDS)
    write_csv(report_path, issues, ["source_row", "study_id", "field", "code", "message"])
    print(f"Wrote {len(long_rows)} long-format rows to {args.output_csv}")
    print(f"Wrote {len(issues)} validation issues to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
