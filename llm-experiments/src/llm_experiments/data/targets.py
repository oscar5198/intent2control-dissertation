"""Derive Phase 6B.2 human preference targets from canonical long rows.

This module consumes the Phase 6B.1 candidate-level table and creates
deterministic rating-derived ground truth. It does not create held-out examples,
prompt objects, or any LLM-facing data.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .processing import EXPECTED_LABELS, write_csv, write_json


TARGET_REASON_CODES = [
    "missing_candidate",
    "duplicate_presentation_label",
    "invalid_mapping",
    "missing_rating",
    "rating_out_of_range",
    "duplicate_candidate_mapping",
]

TARGET_INVALIDATING_6B1_ISSUES = {
    "incomplete_trial_row_count": "missing_candidate",
    "incomplete_or_invalid_labels": "missing_candidate",
    "duplicate_presentation_label": "duplicate_presentation_label",
    "missing_stimulus_id": "invalid_mapping",
    "missing_mix_mapping": "invalid_mapping",
    "missing_label_mapping": "invalid_mapping",
    "mapping_response_disagreement": "invalid_mapping",
    "presentation_order_disagreement": "invalid_mapping",
    "inactive_stimulus_id": "invalid_mapping",
    "duplicate_candidate_mapping": "duplicate_candidate_mapping",
    "missing_rating": "missing_rating",
}

CANDIDATE_TARGET_COLUMNS = [
    "target_eligible",
    "target_ineligibility_reasons",
    "history_eligible",
    "history_ineligibility_reasons",
    "history_comment_available",
    "observed_max_rating",
    "observed_preferred_set",
    "observed_preferred_mix",
    "is_single_winner",
    "n_preferred_tied",
    "is_observed_preferred",
    "observed_rank",
]

TRIAL_TARGET_COLUMNS = [
    "participant_id",
    "trial_id",
    "trial_order",
    "trial_index",
    "episode_id",
    "scenario_id",
    "song_id",
    "excerpt_id",
    "target_eligible",
    "target_ineligibility_reasons",
    "history_eligible",
    "history_ineligibility_reasons",
    "history_comment_available",
    "observed_max_rating",
    "observed_preferred_set",
    "observed_preferred_mix",
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
]


def load_canonical_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), reader.fieldnames or []


def group_by_trial(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("trial_id", ""))].append(row)
    return dict(grouped)


def stable_json_labels(labels: list[str]) -> str:
    ordered = [label for label in EXPECTED_LABELS if label in set(labels)]
    return json.dumps(ordered, separators=(",", ":"))


def parse_issue_codes(value: Any) -> set[str]:
    if value in (None, ""):
        return set()
    return {item for item in str(value).split("|") if item}


def parse_rating(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        rating = float(value)
    except (TypeError, ValueError):
        return None
    if rating < 0 or rating > 100:
        return None
    return rating


def is_rating_present(value: Any) -> bool:
    if value in (None, ""):
        return False
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def validate_target_trial(trial_rows: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    reasons: set[str] = set()
    labels = [str(row.get("presentation_label", "")) for row in trial_rows]
    stimulus_ids = [str(row.get("stimulus_id", "")) for row in trial_rows]

    if len(trial_rows) != 5:
        reasons.add("missing_candidate")
    if sorted(labels) != EXPECTED_LABELS:
        reasons.add("missing_candidate")
    if len(set(labels)) != len(labels):
        reasons.add("duplicate_presentation_label")
    if len(set(stimulus_ids)) != len(stimulus_ids):
        reasons.add("duplicate_candidate_mapping")
    if any(not stimulus_id for stimulus_id in stimulus_ids):
        reasons.add("invalid_mapping")

    for row in trial_rows:
        for issue in parse_issue_codes(row.get("validation_issues", "")):
            mapped = TARGET_INVALIDATING_6B1_ISSUES.get(issue)
            if mapped:
                reasons.add(mapped)
        rating = row.get("human_rating", "")
        if not is_rating_present(rating):
            reasons.add("missing_rating")
        elif parse_rating(rating) is None:
            reasons.add("rating_out_of_range")

    ordered = [code for code in TARGET_REASON_CODES if code in reasons]
    return not ordered, ordered


def validate_history_trial(trial_rows: list[dict[str, Any]]) -> tuple[bool, list[str], bool]:
    eligible, reasons = validate_target_trial(trial_rows)
    comments = {str(row.get("comparative_comment", "")).strip() for row in trial_rows}
    non_empty_comments = {comment for comment in comments if comment}
    history_comment_available = len(non_empty_comments) == 1
    return eligible, reasons, history_comment_available


def derive_preferred_set(ratings_by_label: dict[str, float]) -> tuple[float, list[str], str, bool, int]:
    observed_max = max(ratings_by_label.values())
    preferred_set = [label for label in EXPECTED_LABELS if ratings_by_label[label] == observed_max]
    is_single = len(preferred_set) == 1
    preferred_mix = preferred_set[0] if is_single else ""
    return observed_max, preferred_set, preferred_mix, is_single, len(preferred_set)


def derive_observed_ranks(ratings_by_label: dict[str, float]) -> dict[str, float]:
    """Return descending average ranks, where highest rating has rank 1.

    Equal ratings receive the average of the ranks they occupy. For example,
    ratings A=90, C=90, E=80, B=70, D=50 produce A=1.5, C=1.5, E=3, B=4,
    D=5.
    """

    sorted_items = sorted(ratings_by_label.items(), key=lambda item: (-item[1], EXPECTED_LABELS.index(item[0])))
    ranks: dict[str, float] = {}
    position = 1
    index = 0
    while index < len(sorted_items):
        rating = sorted_items[index][1]
        tied = [sorted_items[index][0]]
        next_index = index + 1
        while next_index < len(sorted_items) and sorted_items[next_index][1] == rating:
            tied.append(sorted_items[next_index][0])
            next_index += 1
        occupied = list(range(position, position + len(tied)))
        average_rank = sum(occupied) / len(occupied)
        for label in tied:
            ranks[label] = average_rank
        position += len(tied)
        index = next_index
    return ranks


def build_trial_ground_truth(trial_rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered_rows = sorted(trial_rows, key=lambda row: EXPECTED_LABELS.index(str(row.get("presentation_label", "Z"))) if str(row.get("presentation_label", "Z")) in EXPECTED_LABELS else 99)
    first = ordered_rows[0] if ordered_rows else {}
    target_eligible, target_reasons = validate_target_trial(ordered_rows)
    history_eligible, history_reasons, history_comment_available = validate_history_trial(ordered_rows)
    ratings_by_label = {
        str(row.get("presentation_label", "")): parse_rating(row.get("human_rating", ""))
        for row in ordered_rows
        if str(row.get("presentation_label", "")) in EXPECTED_LABELS
    }

    result: dict[str, Any] = {
        "participant_id": first.get("participant_id", ""),
        "trial_id": first.get("trial_id", ""),
        "trial_order": first.get("trial_order", ""),
        "trial_index": first.get("trial_index", ""),
        "episode_id": first.get("episode_id", ""),
        "scenario_id": first.get("scenario_id", ""),
        "song_id": first.get("song_id", ""),
        "excerpt_id": first.get("excerpt_id", ""),
        "target_eligible": target_eligible,
        "target_ineligibility_reasons": "|".join(target_reasons),
        "history_eligible": history_eligible,
        "history_ineligibility_reasons": "|".join(history_reasons),
        "history_comment_available": history_comment_available,
        "observed_max_rating": "",
        "observed_preferred_set": "",
        "observed_preferred_mix": "",
        "is_single_winner": "",
        "n_preferred_tied": "",
    }
    for label in EXPECTED_LABELS:
        result[f"human_rating_{label}"] = ""
        result[f"observed_rank_{label}"] = ""

    for label in EXPECTED_LABELS:
        if label in ratings_by_label and ratings_by_label[label] is not None:
            result[f"human_rating_{label}"] = format_number(ratings_by_label[label])

    if target_eligible:
        complete_ratings = {label: ratings_by_label[label] for label in EXPECTED_LABELS}
        observed_max, preferred_set, preferred_mix, is_single, n_tied = derive_preferred_set(complete_ratings)
        ranks = derive_observed_ranks(complete_ratings)
        result.update(
            {
                "observed_max_rating": format_number(observed_max),
                "observed_preferred_set": stable_json_labels(preferred_set),
                "observed_preferred_mix": preferred_mix,
                "is_single_winner": is_single,
                "n_preferred_tied": n_tied,
            }
        )
        for label in EXPECTED_LABELS:
            result[f"observed_rank_{label}"] = format_number(ranks[label])

    return result


def enrich_candidate_ground_truth(rows: list[dict[str, Any]], trial_targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    target_by_trial = {str(target["trial_id"]): target for target in trial_targets}
    enriched: list[dict[str, Any]] = []
    for row in rows:
        target = target_by_trial[str(row.get("trial_id", ""))]
        label = str(row.get("presentation_label", ""))
        preferred_set = json.loads(target["observed_preferred_set"]) if target.get("observed_preferred_set") else []
        enriched_row = dict(row)
        enriched_row.update(
            {
                "target_eligible": target["target_eligible"],
                "target_ineligibility_reasons": target["target_ineligibility_reasons"],
                "history_eligible": target["history_eligible"],
                "history_ineligibility_reasons": target["history_ineligibility_reasons"],
                "history_comment_available": target["history_comment_available"],
                "observed_max_rating": target["observed_max_rating"],
                "observed_preferred_set": target["observed_preferred_set"],
                "observed_preferred_mix": target["observed_preferred_mix"],
                "is_single_winner": target["is_single_winner"],
                "n_preferred_tied": target["n_preferred_tied"],
                "is_observed_preferred": bool(target["target_eligible"] and label in preferred_set),
                "observed_rank": target.get(f"observed_rank_{label}", ""),
            }
        )
        enriched.append(enriched_row)
    return sorted(enriched, key=lambda row: (str(row.get("participant_id", "")), sort_int(row.get("trial_order", "")), str(row.get("presentation_label", ""))))


def build_preference_targets(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    grouped = group_by_trial(rows)
    trial_targets = [build_trial_ground_truth(grouped[trial_id]) for trial_id in sorted(grouped, key=lambda trial_id: (str(grouped[trial_id][0].get("participant_id", "")), sort_int(grouped[trial_id][0].get("trial_order", ""))))]
    enriched = enrich_candidate_ground_truth(rows, trial_targets)
    summary = build_target_summary(enriched, trial_targets)
    return enriched, trial_targets, summary


def build_target_summary(enriched_rows: list[dict[str, Any]], trial_targets: list[dict[str, Any]]) -> dict[str, Any]:
    reason_counts = Counter()
    for target in trial_targets:
        for reason in str(target.get("target_ineligibility_reasons", "")).split("|"):
            if reason:
                reason_counts[reason] += 1
    return {
        "candidate_row_count": len(enriched_rows),
        "trial_target_count": len(trial_targets),
        "target_eligible_trial_count": sum(1 for target in trial_targets if boolish(target.get("target_eligible"))),
        "target_ineligible_trial_count": sum(1 for target in trial_targets if not boolish(target.get("target_eligible"))),
        "history_eligible_trial_count": sum(1 for target in trial_targets if boolish(target.get("history_eligible"))),
        "history_comment_missing_trial_count": sum(1 for target in trial_targets if not boolish(target.get("history_comment_available"))),
        "target_ineligibility_reason_counts": dict(sorted(reason_counts.items())),
        "contains_held_out_examples": False,
        "contains_llm_prompts": False,
    }


def build_preference_targets_from_csv(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[str]]:
    rows, input_columns = load_canonical_rows(path)
    enriched, trial_targets, summary = build_preference_targets(rows)
    return enriched, trial_targets, summary, input_columns


def write_preference_target_outputs(input_csv: Path, output_dir: Path) -> tuple[Path, Path, Path]:
    enriched, trial_targets, summary, input_columns = build_preference_targets_from_csv(input_csv)
    candidate_path = output_dir / "candidate_ground_truth_enriched.csv"
    trial_path = output_dir / "trial_ground_truth_targets.csv"
    summary_path = output_dir / "preference_target_summary.json"
    write_csv(candidate_path, enriched, input_columns + CANDIDATE_TARGET_COLUMNS)
    write_csv(trial_path, trial_targets, TRIAL_TARGET_COLUMNS)
    write_json(summary_path, {"input_csv": str(input_csv), **summary})
    return candidate_path, trial_path, summary_path


def format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.10g}"


def sort_int(value: Any) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 999999


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Phase 6B.2 deterministic human preference targets.")
    parser.add_argument("--input", required=True, type=Path, help="Phase 6B.1 analysis_ready_long.csv.")
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory for Phase 6B.2 target outputs.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidate_path, trial_path, summary_path = write_preference_target_outputs(args.input, args.output_dir)
    print(f"Wrote candidate-level ground truth to {candidate_path}")
    print(f"Wrote trial-level ground truth to {trial_path}")
    print(f"Wrote preference target summary to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
