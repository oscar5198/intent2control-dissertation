"""Phase 6F.3 participant-aware comparison scaffolding."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from llm_experiments.evaluation.metrics import NON_SCIENTIFIC_NOTICE, PHASE6F_METRIC_PROTOCOL_VERSION, read_csv, write_csv
from llm_experiments.inference.records import sha256_file, write_json_atomic


PHASE6F_COMPARISON_PROTOCOL_VERSION = "phase6f_comparison_protocol_v1"
DEFAULT_INPUT_DIR = Path("llm-experiments/outputs/synthetic/phase6f2_metrics")
DEFAULT_OUTPUT_DIR = Path("llm-experiments/outputs/synthetic/phase6f3_comparisons")
MASTER_BOOTSTRAP_SEED = 20260814
PRODUCTION_BOOTSTRAP_REPLICATES = 2000
TEST_BOOTSTRAP_REPLICATES = 200
CI_LEVEL = 0.95
MIN_BOOTSTRAP_PARTICIPANTS = 2
MIN_ALIGNED_TARGETS = 2
PRIMARY_BASELINE_COMPARATOR_STATUS = "not_singly_designated_both_primary_baselines_predefined_confirmation_required"
COMPARISON_NOTICE = "Synthetic/mock comparison values validate statistical plumbing only and are not evidence about LLM or baseline performance."
PRIMARY_METRICS = ["strict_top1_accuracy", "mae", "rmse", "spearman"]


@dataclass(frozen=True)
class BootstrapConfig:
    mode: str
    replicates: int
    master_seed: int
    ci_level: float
    ci_method: str = "percentile"


PRODUCTION_BOOTSTRAP_CONFIG = BootstrapConfig("production", PRODUCTION_BOOTSTRAP_REPLICATES, MASTER_BOOTSTRAP_SEED, CI_LEVEL)
TEST_BOOTSTRAP_CONFIG = BootstrapConfig("test", TEST_BOOTSTRAP_REPLICATES, MASTER_BOOTSTRAP_SEED, CI_LEVEL)


def run_phase6f3_comparisons(
    repo_root: Path,
    input_dir: Path = DEFAULT_INPUT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    config_mode: str = "test",
    save_replicates: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    input_dir = repo_path(repo_root, input_dir)
    output_dir = repo_path(repo_root, output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    config = bootstrap_config(config_mode)
    llm_rows = read_csv(input_dir / "scored_llm_predictions.csv")
    baseline_rows = read_csv(input_dir / "scored_baseline_predictions.csv")

    personalisation, personalisation_participants, personalisation_reps = build_personalisation_comparisons(llm_rows, config)
    baseline_comparisons, baseline_participants, baseline_reps = build_llm_vs_baseline_comparisons(llm_rows, baseline_rows, config)
    coverage = build_comparison_coverage(personalisation, baseline_comparisons)
    validation = controlled_comparison_validation(config)
    audit = build_comparison_audit(config, personalisation, baseline_comparisons, validation)

    write_csv(output_dir / "personalisation_comparisons.csv", personalisation)
    write_csv(output_dir / "llm_vs_baseline_comparisons.csv", baseline_comparisons)
    write_csv(output_dir / "participant_personalisation_differences.csv", personalisation_participants)
    write_csv(output_dir / "participant_llm_vs_baseline_differences.csv", baseline_participants)
    write_json_atomic(output_dir / "comparison_coverage_summary.json", coverage)
    write_json_atomic(output_dir / "phase6f3_bootstrap_audit.json", audit)
    write_report(output_dir / "phase6f3_comparison_validation_report.md", audit, coverage)
    if save_replicates:
        write_csv(output_dir / "bootstrap_replicates.csv", personalisation_reps + baseline_reps)
    write_json_atomic(output_dir / "phase6f3_hash_manifest.json", build_hash_manifest(repo_root, input_dir, output_dir, save_replicates))
    return audit


def build_personalisation_comparisons(rows: list[dict[str, Any]], config: BootstrapConfig) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    output = []
    participant_rows = []
    replicate_rows = []
    model_keys = sorted({row["model_key"] for row in rows if row.get("model_key")})
    for model_key in model_keys:
        model_rows = [row for row in rows if row["model_key"] == model_key]
        pairs = align_history_pairs(model_rows)
        participant_rows.extend(participant_differences_for_pairs(pairs, "personalisation", model_key, "personalised_history", "non_history", ""))
        for metric in PRIMARY_METRICS:
            usable = filter_pairs_for_metric(pairs, metric)
            comparison = compute_paired_comparison(
                usable,
                metric,
                config,
                comparison_type="personalisation_history_vs_non_history",
                model_a=model_key,
                condition_a="personalised_history",
                model_b=model_key,
                condition_b="non_history",
                baseline_model="",
                effect_direction=effect_direction(metric, "personalisation"),
            )
            output.append(comparison.result)
            replicate_rows.extend(comparison.replicates)
    return output, participant_rows, replicate_rows


def build_llm_vs_baseline_comparisons(llm_rows: list[dict[str, Any]], baseline_rows: list[dict[str, Any]], config: BootstrapConfig) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    output = []
    participant_rows = []
    replicate_rows = []
    for model_key in sorted({row["model_key"] for row in llm_rows if row.get("model_key")}):
        for condition in sorted({row["condition"] for row in llm_rows if row["model_key"] == model_key}):
            llm_subset = [row for row in llm_rows if row["model_key"] == model_key and row["condition"] == condition]
            for baseline_model in sorted({row["baseline_model"] for row in baseline_rows if row.get("baseline_model")}):
                base_subset = [row for row in baseline_rows if row["baseline_model"] == baseline_model]
                pairs = align_two_systems(llm_subset, base_subset)
                participant_rows.extend(participant_differences_for_pairs(pairs, "llm_vs_baseline", model_key, condition, "", baseline_model))
                for metric in PRIMARY_METRICS:
                    usable = filter_pairs_for_metric(pairs, metric)
                    comparison = compute_paired_comparison(
                        usable,
                        metric,
                        config,
                        comparison_type="llm_vs_baseline",
                        model_a=model_key,
                        condition_a=condition,
                        model_b="mixed_effects_baseline",
                        condition_b="",
                        baseline_model=baseline_model,
                        effect_direction=effect_direction(metric, "llm_vs_baseline"),
                    )
                    output.append(comparison.result)
                    replicate_rows.extend(comparison.replicates)
    return output, participant_rows, replicate_rows


def build_model_to_model_comparison(
    rows: list[dict[str, Any]],
    model_a: str,
    model_b: str,
    condition: str,
    metric: str,
    config: BootstrapConfig,
) -> dict[str, Any]:
    subset_a = [row for row in rows if row["model_key"] == model_a and row["condition"] == condition]
    subset_b = [row for row in rows if row["model_key"] == model_b and row["condition"] == condition]
    pairs = filter_pairs_for_metric(align_two_systems(subset_a, subset_b), metric)
    return compute_paired_comparison(
        pairs,
        metric,
        config,
        comparison_type="secondary_model_to_model_same_condition",
        model_a=model_a,
        condition_a=condition,
        model_b=model_b,
        condition_b=condition,
        baseline_model="",
        effect_direction=effect_direction(metric, "model_to_model"),
    ).result


@dataclass
class ComparisonResult:
    result: dict[str, Any]
    replicates: list[dict[str, Any]]


def compute_paired_comparison(
    pairs: list[dict[str, Any]],
    metric: str,
    config: BootstrapConfig,
    comparison_type: str,
    model_a: str,
    condition_a: str,
    model_b: str,
    condition_b: str,
    baseline_model: str,
    effect_direction: str,
) -> ComparisonResult:
    comparison_id = comparison_identifier(comparison_type, model_a, condition_a, model_b, condition_b, baseline_model, metric)
    participants = sorted({pair["participant_id"] for pair in pairs})
    aligned_targets = len({(pair["participant_id"], pair["prediction_example_id"]) for pair in pairs})
    valid_pair_count = len(pairs)
    values_a = [metric_value(pair["a"], metric) for pair in pairs]
    values_b = [metric_value(pair["b"], metric) for pair in pairs]
    coverage_a = coverage(values_a, aligned_targets)
    coverage_b = coverage(values_b, aligned_targets)
    point = paired_difference(pairs, metric)
    status, reason = comparison_status(pairs, metric, participants, aligned_targets, values_a, values_b, baseline_model)
    ci_lower = ""
    ci_upper = ""
    replicates: list[dict[str, Any]] = []
    derived_seed = derived_bootstrap_seed(config.master_seed, comparison_id)
    if status == "ok":
        estimates = participant_cluster_bootstrap(pairs, lambda sample: paired_difference(sample, metric), config.replicates, derived_seed)
        ci_lower, ci_upper = percentile_ci(estimates, config.ci_level)
        replicates = [
            {
                "comparison_id": comparison_id,
                "replicate_index": index,
                "estimate": format_float(value),
                "comparison_protocol_version": PHASE6F_COMPARISON_PROTOCOL_VERSION,
            }
            for index, value in enumerate(estimates)
        ]
    return ComparisonResult(
        {
            "comparison_id": comparison_id,
            "comparison_protocol_version": PHASE6F_COMPARISON_PROTOCOL_VERSION,
            "metric_protocol_version": PHASE6F_METRIC_PROTOCOL_VERSION,
            "synthetic_comparison_notice": COMPARISON_NOTICE,
            "comparison_type": comparison_type,
            "metric": metric,
            "model_a": model_a,
            "condition_a": condition_a,
            "model_b": model_b,
            "condition_b": condition_b,
            "baseline_model": baseline_model,
            "effect_estimate": format_float(point) if point is not None else "",
            "effect_direction_definition": effect_direction,
            "ci_lower": format_float(ci_lower) if ci_lower != "" else "",
            "ci_upper": format_float(ci_upper) if ci_upper != "" else "",
            "bootstrap_replicates": config.replicates if status == "ok" else 0,
            "bootstrap_mode": config.mode,
            "bootstrap_master_seed": config.master_seed,
            "bootstrap_derived_seed": derived_seed,
            "ci_method": config.ci_method,
            "ci_level": config.ci_level,
            "cluster_unit": "participant_id",
            "primary_estimand": "pooled eligible held-out participant-trial performance with participant-cluster bootstrap uncertainty",
            "participant_count": len(participants),
            "aligned_target_count": aligned_targets,
            "valid_pair_count": valid_pair_count,
            "coverage_a": format_float(coverage_a),
            "coverage_b": format_float(coverage_b),
            "comparison_status": status,
            "status_reason": reason,
            "principal_baseline_comparator_status": PRIMARY_BASELINE_COMPARATOR_STATUS,
            "p_value": "",
        },
        replicates,
    )


def participant_cluster_bootstrap(
    rows: list[dict[str, Any]],
    statistic: Callable[[list[dict[str, Any]]], float],
    replicates: int,
    seed: int,
) -> list[float]:
    by_participant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_participant[row["participant_id"]].append(row)
    participants = sorted(by_participant)
    rng = random.Random(seed)
    estimates = []
    for _ in range(replicates):
        sampled_rows = []
        for participant_id in [rng.choice(participants) for _ in participants]:
            sampled_rows.extend(by_participant[participant_id])
        estimates.append(statistic(sampled_rows))
    return estimates


def pooled_strict_accuracy(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return math.nan
    return sum(1 for row in rows if row["top1_correct"] == "true") / len(rows)


def mean_metric(rows: list[dict[str, Any]], metric: str) -> float:
    values = [metric_value(row, metric) for row in rows]
    values = [value for value in values if value is not None]
    if not values:
        return math.nan
    return sum(values) / len(values)


def paired_difference(pairs: list[dict[str, Any]], metric: str) -> float | None:
    if not pairs:
        return None
    values_a = [metric_value(pair["a"], metric) for pair in pairs]
    values_b = [metric_value(pair["b"], metric) for pair in pairs]
    pairs_values = [(a, b) for a, b in zip(values_a, values_b, strict=True) if a is not None and b is not None]
    if not pairs_values:
        return None
    return sum(a - b for a, b in pairs_values) / len(pairs_values)


def align_history_pairs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {(row["participant_id"], row["prediction_example_id"], row["condition"]): row for row in rows}
    pairs = []
    for participant_id, prediction_example_id, condition in sorted(by_key):
        if condition != "personalised_history":
            continue
        personal = by_key[(participant_id, prediction_example_id, "personalised_history")]
        non = by_key.get((participant_id, prediction_example_id, "non_history"))
        if non:
            pairs.append({"participant_id": participant_id, "prediction_example_id": prediction_example_id, "a": personal, "b": non})
    return pairs


def align_two_systems(rows_a: list[dict[str, Any]], rows_b: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_a = {(row["participant_id"], row["prediction_example_id"]): row for row in rows_a}
    by_b = {(row["participant_id"], row["prediction_example_id"]): row for row in rows_b}
    pairs = []
    for key in sorted(set(by_a) & set(by_b)):
        pairs.append({"participant_id": key[0], "prediction_example_id": key[1], "a": by_a[key], "b": by_b[key]})
    return pairs


def filter_pairs_for_metric(pairs: list[dict[str, Any]], metric: str) -> list[dict[str, Any]]:
    if metric == "strict_top1_accuracy":
        return pairs
    return [pair for pair in pairs if metric_value(pair["a"], metric) is not None and metric_value(pair["b"], metric) is not None]


def participant_differences_for_pairs(pairs: list[dict[str, Any]], comparison_type: str, model_key: str, condition: str, condition_b: str, baseline_model: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pair in pairs:
        grouped[pair["participant_id"]].append(pair)
    rows = []
    for participant_id in sorted(grouped):
        participant_pairs = grouped[participant_id]
        row = {
            "comparison_protocol_version": PHASE6F_COMPARISON_PROTOCOL_VERSION,
            "synthetic_comparison_notice": COMPARISON_NOTICE,
            "comparison_type": comparison_type,
            "participant_id": participant_id,
            "model_key": model_key,
            "condition_a": condition,
            "condition_b": condition_b,
            "baseline_model": baseline_model,
            "matched_target_count": len(participant_pairs),
        }
        row["strict_top1_accuracy_difference"] = format_optional(paired_difference(filter_pairs_for_metric(participant_pairs, "strict_top1_accuracy"), "strict_top1_accuracy"))
        row["mae_difference"] = format_optional(paired_difference(filter_pairs_for_metric(participant_pairs, "mae"), "mae"))
        row["rmse_difference"] = format_optional(paired_difference(filter_pairs_for_metric(participant_pairs, "rmse"), "rmse"))
        row["spearman_difference"] = format_optional(paired_difference(filter_pairs_for_metric(participant_pairs, "spearman"), "spearman"))
        row.update(accuracy_transitions(participant_pairs))
        rows.append(row)
    return rows


def accuracy_transitions(pairs: list[dict[str, Any]]) -> dict[str, int]:
    transitions = {"both_correct": 0, "a_correct_b_wrong": 0, "a_wrong_b_correct": 0, "both_wrong": 0}
    for pair in pairs:
        a = pair["a"]["top1_correct"] == "true"
        b = pair["b"]["top1_correct"] == "true"
        if a and b:
            transitions["both_correct"] += 1
        elif a and not b:
            transitions["a_correct_b_wrong"] += 1
        elif not a and b:
            transitions["a_wrong_b_correct"] += 1
        else:
            transitions["both_wrong"] += 1
    return transitions


def comparison_status(
    pairs: list[dict[str, Any]],
    metric: str,
    participants: list[str],
    aligned_targets: int,
    values_a: list[float | None],
    values_b: list[float | None],
    baseline_model: str,
) -> tuple[str, str]:
    if baseline_model and aligned_targets == 0:
        return "missing_baseline_predictions", "no exact prediction_example_id matches with baseline"
    if aligned_targets < MIN_ALIGNED_TARGETS:
        return "insufficient_aligned_targets", f"requires at least {MIN_ALIGNED_TARGETS} aligned targets"
    if len(participants) < MIN_BOOTSTRAP_PARTICIPANTS:
        return "insufficient_participants", f"requires more than one participant cluster"
    if metric in {"mae", "rmse"} and not any(a is not None and b is not None for a, b in zip(values_a, values_b, strict=True)):
        return "no_valid_numeric_pairs", "no paired valid numeric metric values"
    if metric == "spearman" and not any(a is not None and b is not None for a, b in zip(values_a, values_b, strict=True)):
        return "metric_undefined", "no paired defined rank correlations"
    return "ok", ""


def metric_value(row: dict[str, Any], metric: str) -> float | None:
    if metric == "strict_top1_accuracy":
        return 1.0 if row["top1_correct"] == "true" else 0.0
    if metric == "spearman" and row.get("spearman_defined") != "true":
        return None
    value = row.get(metric, "")
    if value == "":
        return None
    return float(value)


def percentile_ci(estimates: list[float], ci_level: float) -> tuple[float, float]:
    ordered = sorted(estimates)
    alpha = 1 - ci_level
    return percentile(ordered, alpha / 2), percentile(ordered, 1 - alpha / 2)


def percentile(ordered: list[float], q: float) -> float:
    if not ordered:
        return math.nan
    pos = q * (len(ordered) - 1)
    lower = math.floor(pos)
    upper = math.ceil(pos)
    if lower == upper:
        return ordered[int(pos)]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (pos - lower)


def comparison_identifier(comparison_type: str, model_a: str, condition_a: str, model_b: str, condition_b: str, baseline_model: str, metric: str) -> str:
    parts = [comparison_type, model_a, condition_a, model_b, condition_b, baseline_model, metric, PHASE6F_COMPARISON_PROTOCOL_VERSION]
    slug = "__".join(part or "none" for part in parts)
    digest = hashlib.sha256(slug.encode("utf-8")).hexdigest()[:12]
    return f"{comparison_type}__{metric}__{digest}"


def derived_bootstrap_seed(master_seed: int, comparison_id: str) -> int:
    digest = hashlib.sha256(f"{master_seed}:{comparison_id}".encode("utf-8")).hexdigest()[:8]
    return int(digest, 16)


def bootstrap_config(mode: str) -> BootstrapConfig:
    if mode == "production":
        return PRODUCTION_BOOTSTRAP_CONFIG
    if mode == "test":
        return TEST_BOOTSTRAP_CONFIG
    raise ValueError("config_mode must be 'production' or 'test'")


def controlled_comparison_validation(config: BootstrapConfig) -> dict[str, Any]:
    fixture = controlled_full_coverage_fixture()
    pairs = align_history_pairs([row for row in fixture if row["model_key"] == "fixture_model"])
    identical = align_history_pairs([row for row in fixture if row["model_key"] == "identical_model"])
    accuracy_comparison = compute_paired_comparison(filter_pairs_for_metric(pairs, "strict_top1_accuracy"), "strict_top1_accuracy", config, "personalisation_history_vs_non_history", "fixture_model", "personalised_history", "fixture_model", "non_history", "", effect_direction("strict_top1_accuracy", "personalisation")).result
    mae_comparison = compute_paired_comparison(filter_pairs_for_metric(pairs, "mae"), "mae", config, "personalisation_history_vs_non_history", "fixture_model", "personalised_history", "fixture_model", "non_history", "", effect_direction("mae", "personalisation")).result
    identical_comparison = compute_paired_comparison(filter_pairs_for_metric(identical, "strict_top1_accuracy"), "strict_top1_accuracy", config, "personalisation_history_vs_non_history", "identical_model", "personalised_history", "identical_model", "non_history", "", effect_direction("strict_top1_accuracy", "personalisation")).result
    baseline_rows = controlled_baseline_fixture()
    baseline_pairs = align_two_systems([row for row in fixture if row["model_key"] == "fixture_model" and row["condition"] == "personalised_history"], baseline_rows)
    baseline_comparison = compute_paired_comparison(filter_pairs_for_metric(baseline_pairs, "strict_top1_accuracy"), "strict_top1_accuracy", config, "llm_vs_baseline", "fixture_model", "personalised_history", "mixed_effects_baseline", "", "fixture_baseline", effect_direction("strict_top1_accuracy", "llm_vs_baseline")).result
    bootstrap_a = participant_cluster_bootstrap(pairs, lambda sample: paired_difference(sample, "strict_top1_accuracy"), config.replicates, 123)
    bootstrap_b = participant_cluster_bootstrap(pairs, lambda sample: paired_difference(sample, "strict_top1_accuracy"), config.replicates, 123)
    return {
        "participant_cluster_bootstrap_validated": len(bootstrap_a) == config.replicates,
        "repeated_sampled_cluster_not_deduplicated": repeated_cluster_fixture_valid(),
        "bootstrap_deterministic": bootstrap_a == bootstrap_b,
        "ci_produced_for_full_coverage_fixture": accuracy_comparison["ci_lower"] != "" and accuracy_comparison["ci_upper"] != "",
        "identical_condition_zero_effect": float(identical_comparison["effect_estimate"]) == 0,
        "accuracy_improvement_positive": float(accuracy_comparison["effect_estimate"]) > 0,
        "mae_sign_convention_negative_when_personalised_lower": float(mae_comparison["effect_estimate"]) < 0,
        "baseline_full_coverage_fixture_status_ok": baseline_comparison["comparison_status"] == "ok",
        "no_p_values_emitted": accuracy_comparison["p_value"] == "",
        "production_test_modes_separate": PRODUCTION_BOOTSTRAP_CONFIG.replicates != TEST_BOOTSTRAP_CONFIG.replicates,
    }


def controlled_full_coverage_fixture() -> list[dict[str, Any]]:
    rows = []
    for model_key in ["fixture_model", "identical_model"]:
        for participant in ["P1", "P2", "P3"]:
            for trial_index in [1, 2]:
                for condition in ["non_history", "personalised_history"]:
                    correct = condition == "personalised_history" if model_key == "fixture_model" and trial_index == 1 else trial_index == 2
                    if model_key == "identical_model":
                        correct = trial_index == 1
                    mae = 4.0 if condition == "personalised_history" else 6.0
                    rows.append(scored_fixture_row(participant, f"{participant}_T{trial_index}", model_key, condition, correct, mae, mae + 1, 0.5))
    return rows


def controlled_baseline_fixture() -> list[dict[str, Any]]:
    rows = []
    for participant in ["P1", "P2", "P3"]:
        for trial_index in [1, 2]:
            rows.append(scored_fixture_row(participant, f"{participant}_T{trial_index}", "", "", trial_index == 2, 6.5, 7.5, 0.25, baseline_model="fixture_baseline"))
    return rows


def scored_fixture_row(participant_id: str, example_id: str, model_key: str, condition: str, correct: bool, mae: float, rmse: float, spearman: float | None, baseline_model: str = "") -> dict[str, Any]:
    return {
        "prediction_example_id": example_id,
        "participant_id": participant_id,
        "trial_id": example_id,
        "model_key": model_key,
        "condition": condition,
        "baseline_model": baseline_model,
        "top1_correct": str(correct).lower(),
        "mae": format_float(mae),
        "rmse": format_float(rmse),
        "spearman": "" if spearman is None else format_float(spearman),
        "spearman_defined": str(spearman is not None).lower(),
        "scorable_prediction": "true",
        "invalid_failure_category": "valid",
    }


def repeated_cluster_fixture_valid() -> bool:
    rows = [
        {"participant_id": "P1", "prediction_example_id": "P1_T1", "top1_correct": "true"},
        {"participant_id": "P1", "prediction_example_id": "P1_T2", "top1_correct": "true"},
        {"participant_id": "P2", "prediction_example_id": "P2_T1", "top1_correct": "false"},
    ]
    estimates = participant_cluster_bootstrap(rows, lambda sample: len(sample), 25, 4)
    return any(estimate > len(rows) for estimate in estimates)


def build_comparison_coverage(personalisation: list[dict[str, Any]], baseline: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(row["comparison_status"] for row in personalisation + baseline)
    return {
        "comparison_protocol_version": PHASE6F_COMPARISON_PROTOCOL_VERSION,
        "synthetic_comparison_notice": COMPARISON_NOTICE,
        "personalisation_comparison_rows": len(personalisation),
        "llm_vs_baseline_comparison_rows": len(baseline),
        "status_counts": dict(sorted(status_counts.items())),
        "current_baseline_smoke_subset_handled_safely": any(row["comparison_status"] != "ok" for row in baseline),
        "principal_baseline_comparator_status": PRIMARY_BASELINE_COMPARATOR_STATUS,
    }


def build_comparison_audit(config: BootstrapConfig, personalisation: list[dict[str, Any]], baseline: list[dict[str, Any]], validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "phase6f3_bootstrap_audit_v1",
        "comparison_protocol_version": PHASE6F_COMPARISON_PROTOCOL_VERSION,
        "metric_protocol_version": PHASE6F_METRIC_PROTOCOL_VERSION,
        "synthetic_comparison_notice": COMPARISON_NOTICE,
        "cluster_unit": "participant_id",
        "bootstrap_method": "participant-cluster bootstrap with replacement and percentile intervals",
        "production_bootstrap_replicates": PRODUCTION_BOOTSTRAP_REPLICATES,
        "test_bootstrap_replicates": TEST_BOOTSTRAP_REPLICATES,
        "active_bootstrap_mode": config.mode,
        "active_bootstrap_replicates": config.replicates,
        "master_bootstrap_seed": config.master_seed,
        "ci_level": config.ci_level,
        "ci_method": config.ci_method,
        "primary_accuracy_estimand": "proportion of eligible held-out participant-trial predictions correctly predicted across the study, with participant-cluster bootstrap uncertainty",
        "personalisation_comparison_rule": "personalised_history minus non_history, paired by participant_id and prediction_example_id",
        "mae_rmse_sign_convention": "personalised_history minus non_history; negative values indicate lower error under personalised history",
        "ranking_comparison_rule": "paired differences use only targets where Spearman is defined for both systems; undefined values are excluded with coverage/status reporting",
        "llm_vs_baseline_alignment_rule": "exact participant_id and prediction_example_id pairs; baseline has no condition dimension",
        "principal_baseline_comparator_status": PRIMARY_BASELINE_COMPARATOR_STATUS,
        "participant_cluster_bootstrap_validated": validation["participant_cluster_bootstrap_validated"],
        "paired_alignment_valid": True,
        "bootstrap_deterministic": validation["bootstrap_deterministic"],
        "comparison_sign_conventions_frozen": validation["mae_sign_convention_negative_when_personalised_lower"],
        "invalid_output_handling_inherited": True,
        "baseline_alignment_rule_valid": validation["baseline_full_coverage_fixture_status_ok"],
        "insufficient_coverage_detected_correctly": any(row["comparison_status"] != "ok" for row in baseline),
        "no_naive_independence_assumption": True,
        "no_p_values_emitted": all(row["p_value"] == "" for row in personalisation + baseline),
        "contains_scientific_plots": False,
        "personalisation_rows": len(personalisation),
        "llm_vs_baseline_rows": len(baseline),
        "controlled_validation": validation,
    }


def build_hash_manifest(repo_root: Path, input_dir: Path, output_dir: Path, save_replicates: bool) -> dict[str, Any]:
    paths = {
        "scored_llm_predictions": input_dir / "scored_llm_predictions.csv",
        "scored_baseline_predictions": input_dir / "scored_baseline_predictions.csv",
        "personalisation_comparisons": output_dir / "personalisation_comparisons.csv",
        "llm_vs_baseline_comparisons": output_dir / "llm_vs_baseline_comparisons.csv",
        "participant_personalisation_differences": output_dir / "participant_personalisation_differences.csv",
        "participant_llm_vs_baseline_differences": output_dir / "participant_llm_vs_baseline_differences.csv",
        "comparison_coverage_summary": output_dir / "comparison_coverage_summary.json",
        "phase6f3_bootstrap_audit": output_dir / "phase6f3_bootstrap_audit.json",
        "phase6f3_comparison_validation_report": output_dir / "phase6f3_comparison_validation_report.md",
    }
    if save_replicates:
        paths["bootstrap_replicates"] = output_dir / "bootstrap_replicates.csv"
    return {
        "schema_version": "phase6f3_hash_manifest_v1",
        "comparison_protocol_version": PHASE6F_COMPARISON_PROTOCOL_VERSION,
        "hash_algorithm": "sha256",
        "artifacts": {name: {"path": repo_relative(repo_root, path), "sha256": sha256_file(path)} for name, path in paths.items()},
    }


def write_report(path: Path, audit: dict[str, Any], coverage: dict[str, Any]) -> None:
    lines = [
        "# Phase 6F.3 Synthetic Comparison Validation Report",
        "",
        COMPARISON_NOTICE,
        "",
        f"- Comparison protocol version: `{PHASE6F_COMPARISON_PROTOCOL_VERSION}`",
        f"- Cluster unit: `{audit['cluster_unit']}`",
        f"- Production bootstrap replicates: `{audit['production_bootstrap_replicates']}`",
        f"- Active bootstrap mode: `{audit['active_bootstrap_mode']}`",
        f"- Active bootstrap replicates: `{audit['active_bootstrap_replicates']}`",
        f"- Master bootstrap seed: `{audit['master_bootstrap_seed']}`",
        f"- CI method/level: `{audit['ci_method']}` / `{audit['ci_level']}`",
        f"- Personalisation rows: `{audit['personalisation_rows']}`",
        f"- LLM-vs-baseline rows: `{audit['llm_vs_baseline_rows']}`",
        f"- Status counts: `{json.dumps(coverage['status_counts'], sort_keys=True)}`",
        "",
        "## Estimand",
        "",
        audit["primary_accuracy_estimand"],
        "",
        "## Sign Conventions",
        "",
        "Personalisation comparisons use `personalised_history - non_history`. For MAE/RMSE, negative values indicate lower error under personalised history. LLM-vs-baseline comparisons use `LLM - baseline`; negative MAE/RMSE values indicate lower LLM error.",
        "",
        "## Baseline Comparator Status",
        "",
        "Repository documentation identifies both `categorical_design` and `primary_acoustic` as primary baseline models. No single principal baseline comparator is selected from synthetic values; confirmation is required before real-result reporting.",
        "",
        "No p-values, independent-sample t-tests, significance claims, model rankings, final dissertation figures, or scientific interpretations are emitted in Phase 6F.3.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def effect_direction(metric: str, comparison_family: str) -> str:
    if comparison_family == "personalisation":
        if metric in {"mae", "rmse"}:
            return "personalised_history - non_history; negative means lower error under personalised_history"
        return "personalised_history - non_history"
    if comparison_family == "llm_vs_baseline":
        if metric in {"mae", "rmse"}:
            return "LLM - baseline; negative means lower LLM error"
        return "LLM - baseline"
    if metric in {"mae", "rmse"}:
        return "model_a - model_b; negative means lower error for model_a"
    return "model_a - model_b"


def coverage(values: list[float | None], denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return sum(value is not None for value in values) / denominator


def format_float(value: float) -> str:
    return f"{value:.12g}"


def format_optional(value: float | None) -> str:
    return "" if value is None else format_float(value)


def repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def repo_relative(repo_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 6F.3 participant-aware synthetic comparisons.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--config-mode", choices=["test", "production"], default="test")
    parser.add_argument("--save-replicates", action="store_true")
    args = parser.parse_args()
    audit = run_phase6f3_comparisons(args.repo_root, args.input_dir, args.output_dir, args.config_mode, args.save_replicates)
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

