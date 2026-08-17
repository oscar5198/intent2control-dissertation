"""Phase 6F.4 synthetic reporting and pre-data readiness gates."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from llm_experiments.evaluation.comparisons import PHASE6F_COMPARISON_PROTOCOL_VERSION
from llm_experiments.evaluation.metrics import NON_SCIENTIFIC_NOTICE, PHASE6F_METRIC_PROTOCOL_VERSION, read_csv, read_jsonl, write_csv
from llm_experiments.inference.records import sha256_file, write_json_atomic
from llm_experiments.phase6f import PHASE6F_RUN_VERSION
from llm_experiments.prompts.freeze_package import PROMPT_PACKAGE_VERSION


PHASE6F_REPORTING_VERSION = "phase6f_reporting_v1"
DEFAULT_PHASE6F1_DIR = Path("llm-experiments/outputs/synthetic/phase6f1_e2e")
DEFAULT_PHASE6F2_DIR = Path("llm-experiments/outputs/synthetic/phase6f2_metrics")
DEFAULT_PHASE6F3_DIR = Path("llm-experiments/outputs/synthetic/phase6f3_comparisons")
DEFAULT_PHASE6B_DIR = Path("llm-experiments/outputs/synthetic/phase6b5")
DEFAULT_BASELINE_QC = Path("statistical-baseline/outputs/phase6c3_synthetic_smoke_consolidated/phase6c_baseline_output_qc_summary.json")
DEFAULT_OUTPUT_DIR = Path("llm-experiments/outputs/synthetic/phase6f4_predata_readiness")
REPORT_NOTICE = "SYNTHETIC / MOCK - NOT SCIENTIFIC RESULTS"
COMPARISON_NOTICE = "Synthetic/mock comparison values validate statistical plumbing only and are not evidence about LLM or baseline performance."
PROHIBITED_INTERPRETATION_TERMS = ["significantly better", "superior", "outperforms", "best model", "history improves performance", "baseline underperforms"]


def run_phase6f4_reporting(
    repo_root: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    phase6f1_dir: Path = DEFAULT_PHASE6F1_DIR,
    phase6f2_dir: Path = DEFAULT_PHASE6F2_DIR,
    phase6f3_dir: Path = DEFAULT_PHASE6F3_DIR,
    phase6b_dir: Path = DEFAULT_PHASE6B_DIR,
    baseline_qc_path: Path = DEFAULT_BASELINE_QC,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    output_dir = repo_path(repo_root, output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = output_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    phase6f1_dir = repo_path(repo_root, phase6f1_dir)
    phase6f2_dir = repo_path(repo_root, phase6f2_dir)
    phase6f3_dir = repo_path(repo_root, phase6f3_dir)
    phase6b_dir = repo_path(repo_root, phase6b_dir)
    baseline_qc_path = repo_path(repo_root, baseline_qc_path)

    phase6f1_audit = load_json(phase6f1_dir / "phase6f1_end_to_end_audit.json")
    phase6f2_audit = load_json(phase6f2_dir / "phase6f2_metric_audit.json")
    phase6f3_audit = load_json(phase6f3_dir / "phase6f3_bootstrap_audit.json")
    baseline_qc = load_json(baseline_qc_path)
    llm_metric = add_reporting_notice(read_csv(phase6f2_dir / "llm_metric_summary.csv"))
    baseline_metric = add_reporting_notice(read_csv(phase6f2_dir / "baseline_metric_summary.csv"))
    personalisation = add_reporting_notice(read_csv(phase6f3_dir / "personalisation_comparisons.csv"))
    llm_vs_baseline = add_reporting_notice(read_csv(phase6f3_dir / "llm_vs_baseline_comparisons.csv"))
    scored_llm = read_csv(phase6f2_dir / "scored_llm_predictions.csv")
    scored_baseline = read_csv(phase6f2_dir / "scored_baseline_predictions.csv")
    alignment = read_jsonl(phase6f1_dir / "prediction_alignment_manifest.jsonl")
    examples = read_jsonl(phase6b_dir / "final_prediction_examples.jsonl")

    participant_qc = build_participant_qc(scored_llm, scored_baseline)
    context_song = build_context_song_coverage(examples, alignment, scored_llm, scored_baseline)
    inference_validity = build_inference_validity(phase6f1_audit)
    baseline_diag = build_baseline_diagnostic(baseline_qc, scored_baseline)
    comparison_coverage = build_comparison_coverage(personalisation, llm_vs_baseline)
    checklist = build_checklist(phase6f1_audit)
    readiness = build_readiness_audit(phase6f1_audit, phase6f2_audit, phase6f3_audit, baseline_qc)

    tables = {
        "llm_metric_summary_table.csv": llm_metric,
        "baseline_metric_summary_table.csv": baseline_metric,
        "personalisation_comparison_table.csv": personalisation,
        "llm_vs_baseline_comparison_table.csv": llm_vs_baseline,
        "participant_qc_table.csv": participant_qc,
        "context_song_coverage_table.csv": context_song,
        "inference_validity_table.csv": inference_validity,
        "baseline_diagnostic_table.csv": baseline_diag,
        "comparison_coverage_table.csv": comparison_coverage,
        "pre_real_data_checklist.csv": checklist,
    }
    for filename, rows in tables.items():
        write_csv(output_dir / filename, rows)

    plot_sources = build_plot_sources(llm_metric, personalisation, llm_vs_baseline, inference_validity)
    for filename, rows in plot_sources.items():
        write_csv(output_dir / filename, rows)
    plot_paths = render_plots(plots_dir, plot_sources)
    readiness["reporting_tables_generated"] = all((output_dir / name).exists() for name in tables)
    readiness["reporting_plots_generated"] = all(path.exists() for path in plot_paths)
    readiness["phase6f4_reporting_generation_passed"] = readiness["reporting_tables_generated"] and readiness["reporting_plots_generated"]
    readiness["predata_analysis_ready"] = bool(
        readiness["real_data_pipeline_ready"]
        and not readiness["production_inference_ready"]
        and readiness["phase6f4_reporting_generation_passed"]
        and readiness["phase6f_comparisons_validated"]
    )
    readiness["phase6f_predata_dry_run_complete"] = bool(readiness["phase6f_e2e_alignment_ready"] and readiness["phase6f_metrics_validated"] and readiness["phase6f_comparisons_validated"] and readiness["phase6f4_reporting_generation_passed"])

    write_json_atomic(output_dir / "phase6f4_predata_readiness_audit.json", readiness)
    write_report(output_dir / "phase6f4_predata_readiness_report.md", readiness, tables, plot_paths)
    write_json_atomic(output_dir / "phase6f4_hash_manifest.json", build_hash_manifest(repo_root, output_dir, tables, plot_paths))
    return readiness


def build_readiness_audit(phase6f1: dict[str, Any], phase6f2: dict[str, Any], phase6f3: dict[str, Any], baseline_qc: dict[str, Any]) -> dict[str, Any]:
    phase6e_live = phase6f1.get("phase6e_live_preflight", {})
    live_missing = phase6e_live.get("missing_items") or [
        "exact GPT model ID unresolved",
        "exact Claude model ID unresolved",
        "exact Llama checkpoint unresolved",
        "exact Centaur checkpoint unresolved",
        "live QMUL serving contracts unresolved",
        "live RunPod serving contract unresolved",
    ]
    phase6b_ready = bool(phase6f1.get("phase6b_ready"))
    phase6c_ready = bool(baseline_qc.get("BASELINE_PRIMARY_OUTPUTS_COMPLETE") and baseline_qc.get("synthetic_structural_validation") == "PASS")
    phase6d_ready = bool(phase6f1.get("prompt_package_verified") and phase6f1.get("experimental_condition_integrity"))
    phase6e_infra = bool(phase6f1.get("mock_inference_complete") and phase6f1.get("llm_prediction_schema_valid"))
    live_ready = bool(phase6f1.get("live_production_gates_resolved"))
    metrics_ready = all(bool(phase6f2.get(key)) for key in ["ground_truth_join_valid", "mae_validated", "rmse_validated", "spearman_validated", "llm_scoring_complete"])
    comparisons_ready = all(bool(phase6f3.get(key)) for key in ["participant_cluster_bootstrap_validated", "paired_alignment_valid", "bootstrap_deterministic", "no_p_values_emitted"])
    return {
        "schema_version": "phase6f4_predata_readiness_audit_v1",
        "reporting_version": PHASE6F_REPORTING_VERSION,
        "synthetic_validation": True,
        "synthetic_label": REPORT_NOTICE,
        "metric_protocol_version": PHASE6F_METRIC_PROTOCOL_VERSION,
        "comparison_protocol_version": PHASE6F_COMPARISON_PROTOCOL_VERSION,
        "phase6f_run_version": phase6f1.get("phase6f_run_version", PHASE6F_RUN_VERSION),
        "prompt_package_version": PROMPT_PACKAGE_VERSION,
        "baseline_protocol_version": baseline_qc.get("protocol_version"),
        "phase6b_pipeline_ready": phase6b_ready,
        "phase6c_baseline_infrastructure_ready": phase6c_ready,
        "phase6d_prompt_package_frozen": phase6d_ready,
        "phase6e_inference_infrastructure_ready": phase6e_infra,
        "phase6e_live_model_identities_frozen": False,
        "phase6e_live_backends_verified": False,
        "phase6e_primary_inference_config_frozen": True,
        "phase6f_e2e_alignment_ready": bool(phase6f1.get("phase6f_e2e_alignment_ready")),
        "phase6f_metrics_validated": metrics_ready,
        "phase6f_comparisons_validated": comparisons_ready,
        "reporting_tables_generated": False,
        "reporting_plots_generated": False,
        "synthetic_determinism_passed": bool(phase6f1.get("deterministic_rerun") and phase6f3.get("bootstrap_deterministic")),
        "real_data_pipeline_ready": bool(phase6b_ready and phase6c_ready and phase6d_ready and phase6e_infra and metrics_ready and comparisons_ready),
        "production_inference_ready": live_ready,
        "predata_analysis_ready": False,
        "phase6f4_reporting_generation_passed": False,
        "phase6f_predata_dry_run_complete": False,
        "principal_baseline_comparator": "UNRESOLVED",
        "principal_baseline_comparator_status": phase6f3.get("principal_baseline_comparator_status"),
        "unresolved_live_deployment_items": live_missing,
        "final_milestone_assessment": "Yes for data processing, baseline analysis, prompt generation, scoring, comparison, and reporting; live LLM production execution still requires Phase 6E.2 model/backend verification.",
    }


def build_participant_qc(llm: list[dict[str, str]], baseline: list[dict[str, str]]) -> list[dict[str, Any]]:
    participants = sorted({row["participant_id"] for row in llm} | {row["participant_id"] for row in baseline})
    rows = []
    for participant in participants:
        llm_rows = [row for row in llm if row["participant_id"] == participant]
        base_rows = [row for row in baseline if row["participant_id"] == participant]
        row = {
            "synthetic_label": REPORT_NOTICE,
            "participant_id": participant,
            "eligible_target_count": len({row["prediction_example_id"] for row in llm_rows}),
            "valid_llm_prediction_count": sum(row["scorable_prediction"] == "true" for row in llm_rows),
            "invalid_llm_prediction_count": sum(row["scorable_prediction"] != "true" for row in llm_rows),
            "baseline_available_count": len(base_rows),
            "baseline_model_count": len({row["baseline_model"] for row in base_rows}),
            "mean_strict_accuracy": mean([1.0 if row["top1_correct"] == "true" else 0.0 for row in llm_rows]),
            "continuous_metric_coverage": coverage([row.get("mae") for row in llm_rows], len(llm_rows)),
        }
        for key in sorted({(row["model_key"], row["condition"]) for row in llm_rows}):
            subset = [row for row in llm_rows if (row["model_key"], row["condition"]) == key]
            row[f"{key[0]}__{key[1]}__valid_predictions"] = sum(item["scorable_prediction"] == "true" for item in subset)
        rows.append(row)
    return rows


def build_context_song_coverage(examples: list[dict[str, Any]], alignment: list[dict[str, Any]], llm: list[dict[str, str]], baseline: list[dict[str, str]]) -> list[dict[str, Any]]:
    alignment_by_id = {row["prediction_example_id"]: row for row in alignment}
    llm_ids = {row["prediction_example_id"] for row in llm}
    base_ids = {row["prediction_example_id"] for row in baseline}
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for example in examples:
        target = example["input_data"]["target"]
        key = (target["episode"]["context_label"], target["song"]["song_id"])
        groups[key].append(example)
    rows = []
    for key in sorted(groups):
        group = groups[key]
        ids = [example["prediction_example_id"] for example in group]
        rows.append(
            {
                "synthetic_label": REPORT_NOTICE,
                "context_label": key[0],
                "song_id": key[1],
                "target_count": len(ids),
                "llm_prediction_available_targets": sum(example_id in llm_ids for example_id in ids),
                "baseline_available_targets": sum(example_id in base_ids for example_id in ids),
                "alignment_complete_targets": sum(bool(alignment_by_id.get(example_id, {}).get("alignment_complete")) for example_id in ids),
                "human_preference_tie_targets": sum(example["ground_truth"]["n_preferred_tied"] > 1 for example in group),
            }
        )
    return rows


def build_inference_validity(audit: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key, value in sorted(audit["llm_summary"]["by_model_condition"].items()):
        model, condition = key.split("__", 1)
        rows.append(
            {
                "synthetic_label": REPORT_NOTICE,
                "model_key": model,
                "condition": condition,
                "expected_requests": value["predictions"],
                "valid_primary": value["valid_outputs"],
                "valid_after_repair": value["repairs_successful"],
                "invalid_after_repair": value["invalid_outputs"],
                "backend_failures": value["backend_failures"],
                "repairs_used": value["repairs_attempted"],
                "transport_retries": value["transport_retries"],
                "completion_coverage": value["primary_validity_rate"],
            }
        )
    return rows


def build_baseline_diagnostic(qc: dict[str, Any], scored_baseline: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows = []
    for model in sorted({row["baseline_model"] for row in scored_baseline}):
        subset = [row for row in scored_baseline if row["baseline_model"] == model]
        rows.append(
            {
                "synthetic_label": REPORT_NOTICE,
                "baseline_model": model,
                "expected_fits": qc.get("expected_primary_fits"),
                "completed_fits": qc.get("completed_primary_fits"),
                "convergence_warnings": sum(row["fit_status"] == "convergence_warning" for row in subset),
                "failed_fits": qc.get("failed_primary_fits"),
                "missing_fits": qc.get("missing_primary_fits"),
                "a_e_completeness_failures": qc.get("a_e_completeness_failures"),
                "probability_validation_failures": qc.get("probability_sum_failures"),
                "alignment_status": qc.get("synthetic_structural_validation"),
                "smoke_subset_mode": qc.get("mode"),
            }
        )
    return rows


def build_comparison_coverage(personalisation: list[dict[str, str]], baseline: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows = []
    for row in personalisation + baseline:
        rows.append(
            {
                "synthetic_label": REPORT_NOTICE,
                "comparison_id": row["comparison_id"],
                "comparison_type": row["comparison_type"],
                "metric": row["metric"],
                "expected_participant_count": row["participant_count"],
                "aligned_participant_count": row["participant_count"],
                "expected_target_count": row["aligned_target_count"],
                "aligned_target_count": row["aligned_target_count"],
                "valid_numeric_pairs": row["valid_pair_count"],
                "coverage_a": row["coverage_a"],
                "coverage_b": row["coverage_b"],
                "comparison_status": row["comparison_status"],
            }
        )
    return rows


def build_plot_sources(llm_metric: list[dict[str, str]], personalisation: list[dict[str, str]], llm_vs_baseline: list[dict[str, str]], inference_validity: list[dict[str, str]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "strict_top1_accuracy_by_condition_source.csv": [{"synthetic_label": REPORT_NOTICE, "model_key": row["model_key"], "condition": row["condition"], "strict_top1_accuracy": row["strict_top1_accuracy"]} for row in llm_metric],
        "mae_by_condition_source.csv": [{"synthetic_label": REPORT_NOTICE, "model_key": row["model_key"], "condition": row["condition"], "mean_per_trial_mae": row["mean_per_trial_mae"], "coverage": row["continuous_metric_coverage"]} for row in llm_metric],
        "rmse_by_condition_source.csv": [{"synthetic_label": REPORT_NOTICE, "model_key": row["model_key"], "condition": row["condition"], "mean_per_trial_rmse": row["mean_per_trial_rmse"], "coverage": row["continuous_metric_coverage"]} for row in llm_metric],
        "personalisation_effects_source.csv": [row for row in personalisation if row["metric"] in {"strict_top1_accuracy", "mae", "rmse"}],
        "llm_vs_baseline_effects_source.csv": [row for row in llm_vs_baseline if row["metric"] in {"strict_top1_accuracy", "mae", "rmse"}],
        "inference_validity_source.csv": inference_validity,
    }


def render_plots(plots_dir: Path, sources: dict[str, list[dict[str, Any]]]) -> list[Path]:
    paths = [
        plot_bar(plots_dir / "strict_top1_accuracy_by_condition.png", sources["strict_top1_accuracy_by_condition_source.csv"], "strict_top1_accuracy", "Strict Top-1 Accuracy"),
        plot_bar(plots_dir / "mae_by_condition.png", sources["mae_by_condition_source.csv"], "mean_per_trial_mae", "MAE"),
        plot_bar(plots_dir / "rmse_by_condition.png", sources["rmse_by_condition_source.csv"], "mean_per_trial_rmse", "RMSE"),
        plot_effects(plots_dir / "personalisation_effects.png", sources["personalisation_effects_source.csv"], "Personalisation Effects"),
        plot_effects(plots_dir / "llm_vs_baseline_effects.png", sources["llm_vs_baseline_effects_source.csv"], "LLM vs Baseline Effects"),
        plot_validity(plots_dir / "inference_validity.png", sources["inference_validity_source.csv"]),
    ]
    return paths


def plot_bar(path: Path, rows: list[dict[str, Any]], value_key: str, ylabel: str) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4.8))
    labels = [f"{row['model_key']}\n{row['condition']}" for row in rows]
    values = [float(row[value_key]) if row.get(value_key) not in {"", None} else 0.0 for row in rows]
    ax.bar(range(len(rows)), values, color="#4c78a8")
    if value_key == "strict_top1_accuracy":
        ax.axhline(0.2, color="#666666", linestyle="--", linewidth=1)
    ax.set_title(f"{REPORT_NOTICE}\n{ylabel}")
    ax.set_ylabel(ylabel)
    ax.set_xticks(range(len(rows)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=160, metadata={"Software": PHASE6F_REPORTING_VERSION})
    plt.close(fig)
    return path


def plot_effects(path: Path, rows: list[dict[str, Any]], title: str) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4.8))
    drawable = [row for row in rows if row.get("ci_lower") not in {"", None} and row.get("ci_upper") not in {"", None}]
    labels = [f"{row['model_a']}\n{row['metric']}" for row in drawable]
    estimates = [float(row["effect_estimate"]) for row in drawable]
    lows = [float(row["ci_lower"]) for row in drawable]
    highs = [float(row["ci_upper"]) for row in drawable]
    y = list(range(len(drawable)))
    if drawable:
        ax.errorbar(estimates, y, xerr=[[e - l for e, l in zip(estimates, lows)], [h - e for e, h in zip(estimates, highs)]], fmt="o", color="#4c78a8", ecolor="#333333")
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=8)
    else:
        ax.text(0.5, 0.5, "Insufficient comparison coverage", ha="center", va="center", transform=ax.transAxes)
        ax.set_yticks([])
    ax.axvline(0, color="#666666", linestyle="--", linewidth=1)
    ax.set_title(f"{REPORT_NOTICE}\n{title}")
    ax.set_xlabel("Paired effect estimate")
    fig.tight_layout()
    fig.savefig(path, dpi=160, metadata={"Software": PHASE6F_REPORTING_VERSION})
    plt.close(fig)
    return path


def plot_validity(path: Path, rows: list[dict[str, Any]]) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4.8))
    labels = [f"{row['model_key']}\n{row['condition']}" for row in rows]
    valid = [int(row["valid_primary"]) for row in rows]
    repaired = [int(row["valid_after_repair"]) for row in rows]
    invalid = [int(row["invalid_after_repair"]) for row in rows]
    backend = [int(row["backend_failures"]) for row in rows]
    x = list(range(len(rows)))
    ax.bar(x, valid, label="valid primary", color="#4c78a8")
    ax.bar(x, repaired, bottom=valid, label="valid after repair", color="#72b7b2")
    ax.bar(x, invalid, bottom=[a + b for a, b in zip(valid, repaired)], label="invalid", color="#f58518")
    ax.bar(x, backend, bottom=[a + b + c for a, b, c in zip(valid, repaired, invalid)], label="backend failed", color="#e45756")
    ax.set_title(f"{REPORT_NOTICE}\nInference Validity")
    ax.set_ylabel("Prediction records")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=160, metadata={"Software": PHASE6F_REPORTING_VERSION})
    plt.close(fig)
    return path


def write_report(path: Path, audit: dict[str, Any], tables: dict[str, list[dict[str, Any]]], plot_paths: list[Path]) -> None:
    lines = [
        "# Phase 6F.4 Pre-Data Readiness Report",
        "",
        REPORT_NOTICE,
        "",
        "## Purpose",
        "",
        "This report validates automatic Phase 6 analysis/reporting infrastructure using synthetic/mock outputs only. It does not contain dissertation results or model-performance conclusions.",
        "",
        "## Pipeline Versions",
        "",
        f"- Reporting: `{audit['reporting_version']}`",
        f"- Metric protocol: `{audit['metric_protocol_version']}`",
        f"- Comparison protocol: `{audit['comparison_protocol_version']}`",
        f"- Prompt package: `{audit['prompt_package_version']}`",
        f"- Baseline protocol: `{audit['baseline_protocol_version']}`",
        "",
        "## Readiness Gates",
        "",
        f"- `REAL_DATA_PIPELINE_READY`: `{str(audit['real_data_pipeline_ready']).lower()}`",
        f"- `PRODUCTION_INFERENCE_READY`: `{str(audit['production_inference_ready']).lower()}`",
        f"- `PREDATA_ANALYSIS_READY`: `{str(audit['predata_analysis_ready']).lower()}`",
        f"- `PHASE6F_PREDATA_DRY_RUN_COMPLETE`: `{str(audit['phase6f_predata_dry_run_complete']).lower()}`",
        "",
        "## Table/Plot Generation",
        "",
        f"- Tables generated: `{len(tables)}`",
        f"- Plots generated: `{len(plot_paths)}`",
        "",
        "## Outstanding Production Blockers",
        "",
        *[f"- {item}" for item in audit["unresolved_live_deployment_items"]],
        "",
        "## Baseline Comparator",
        "",
        "`principal_baseline_comparator = UNRESOLVED`. Both `categorical_design` and `primary_acoustic` remain in templates; this reporting decision must be settled before final dissertation interpretation.",
        "",
        "## Final Gate Assessment",
        "",
        audit["final_milestone_assessment"],
        "",
        "No p-values, significance claims, model rankings, subgroup fishing, final dissertation figures, or scientific interpretations were generated.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_checklist(phase6f1: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"step_order": 1, "remaining_step": "lock final survey export", "status": "pending"},
        {"step_order": 2, "remaining_step": "verify exact four model/checkpoint identities", "status": "pending"},
        {"step_order": 3, "remaining_step": "verify QMUL serving contracts", "status": "pending"},
        {"step_order": 4, "remaining_step": "verify RunPod Centaur contract", "status": "pending"},
        {"step_order": 5, "remaining_step": "freeze Phase 6E.2 production gates", "status": "pending"},
        {"step_order": 6, "remaining_step": "run final Phase 6B pipeline", "status": "pending"},
        {"step_order": 7, "remaining_step": "run Phase 6C baseline production", "status": "pending"},
        {"step_order": 8, "remaining_step": "render final real prompts", "status": "pending"},
        {"step_order": 9, "remaining_step": "execute LLM production", "status": "pending" if not phase6f1.get("live_production_gates_resolved") else "ready"},
        {"step_order": 10, "remaining_step": "run scoring/comparison/reporting", "status": "ready_after_real_inputs"},
    ]


def add_reporting_notice(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [{"synthetic_label": REPORT_NOTICE, **row} for row in rows]


def mean(values: list[float]) -> str:
    return "" if not values else f"{sum(values) / len(values):.12g}"


def coverage(values: list[Any], denominator: int) -> str:
    return "" if denominator == 0 else f"{sum(value not in {'', None} for value in values) / denominator:.12g}"


def build_hash_manifest(repo_root: Path, output_dir: Path, tables: dict[str, list[dict[str, Any]]], plot_paths: list[Path]) -> dict[str, Any]:
    paths = {name.removesuffix(".csv"): output_dir / name for name in tables}
    for plot_path in plot_paths:
        paths[plot_path.stem] = plot_path
    for name in ["phase6f4_predata_readiness_audit.json", "phase6f4_predata_readiness_report.md"]:
        paths[Path(name).stem] = output_dir / name
    return {
        "schema_version": "phase6f4_hash_manifest_v1",
        "reporting_version": PHASE6F_REPORTING_VERSION,
        "hash_algorithm": "sha256",
        "artifacts": {name: {"path": repo_relative(repo_root, path), "sha256": sha256_file(path)} for name, path in sorted(paths.items())},
    }


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def repo_relative(repo_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 6F.4 synthetic reporting and pre-data readiness.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    audit = run_phase6f4_reporting(args.repo_root, args.output_dir)
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

