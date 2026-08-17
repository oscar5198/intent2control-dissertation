import csv
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.evaluation.reporting import (  # noqa: E402
    PHASE6F_REPORTING_VERSION,
    REPORT_NOTICE,
    DEFAULT_OUTPUT_DIR,
    run_phase6f4_reporting,
)
from llm_experiments.inference.records import sha256_file  # noqa: E402


OUT = REPO_ROOT / DEFAULT_OUTPUT_DIR
PLOTS = OUT / "plots"


def test_metric_summary_table_generated():
    run_phase6f4_reporting(REPO_ROOT)
    rows = read_csv(OUT / "llm_metric_summary_table.csv")
    assert rows
    assert {"model_key", "condition", "strict_top1_accuracy", "mean_per_trial_mae"} <= set(rows[0])


def test_baseline_table_generated():
    run_phase6f4_reporting(REPO_ROOT)
    rows = read_csv(OUT / "baseline_metric_summary_table.csv")
    assert sorted({row["baseline_model"] for row in rows}) == ["categorical_design", "primary_acoustic"]


def test_personalisation_comparison_table_generated():
    run_phase6f4_reporting(REPO_ROOT)
    rows = read_csv(OUT / "personalisation_comparison_table.csv")
    assert len(rows) == 16
    assert all(row["comparison_type"] == "personalisation_history_vs_non_history" for row in rows)


def test_llm_vs_baseline_table_generated():
    run_phase6f4_reporting(REPO_ROOT)
    rows = read_csv(OUT / "llm_vs_baseline_comparison_table.csv")
    assert len(rows) == 64
    assert all(row["baseline_model"] in {"categorical_design", "primary_acoustic"} for row in rows)


def test_participant_qc_table_generated():
    run_phase6f4_reporting(REPO_ROOT)
    rows = read_csv(OUT / "participant_qc_table.csv")
    assert rows
    assert {"participant_id", "eligible_target_count", "valid_llm_prediction_count", "baseline_available_count"} <= set(rows[0])


def test_context_song_coverage_table_generated():
    run_phase6f4_reporting(REPO_ROOT)
    rows = read_csv(OUT / "context_song_coverage_table.csv")
    assert rows
    assert {"context_label", "song_id", "target_count", "human_preference_tie_targets"} <= set(rows[0])


def test_inference_validity_table_generated():
    run_phase6f4_reporting(REPO_ROOT)
    rows = read_csv(OUT / "inference_validity_table.csv")
    assert len(rows) == 8
    assert all(row["valid_primary"] == "11" for row in rows)


def test_baseline_diagnostic_table_generated():
    run_phase6f4_reporting(REPO_ROOT)
    rows = read_csv(OUT / "baseline_diagnostic_table.csv")
    assert rows
    assert all(row["smoke_subset_mode"] == "partial" for row in rows)


def test_comparison_coverage_table_generated():
    run_phase6f4_reporting(REPO_ROOT)
    rows = read_csv(OUT / "comparison_coverage_table.csv")
    assert len(rows) == 80
    assert {"comparison_status", "aligned_target_count", "valid_numeric_pairs"} <= set(rows[0])


def test_accuracy_plot_generated():
    run_phase6f4_reporting(REPO_ROOT)
    assert (PLOTS / "strict_top1_accuracy_by_condition.png").stat().st_size > 0


def test_mae_rmse_plots_generated():
    run_phase6f4_reporting(REPO_ROOT)
    assert (PLOTS / "mae_by_condition.png").stat().st_size > 0
    assert (PLOTS / "rmse_by_condition.png").stat().st_size > 0


def test_personalisation_effect_plot_generated():
    run_phase6f4_reporting(REPO_ROOT)
    assert (PLOTS / "personalisation_effects.png").stat().st_size > 0


def test_baseline_effect_plot_handles_insufficient_coverage():
    run_phase6f4_reporting(REPO_ROOT)
    rows = read_csv(OUT / "llm_vs_baseline_comparison_table.csv")
    assert all(row["comparison_status"] == "insufficient_aligned_targets" for row in rows)
    assert (PLOTS / "llm_vs_baseline_effects.png").stat().st_size > 0


def test_validity_plot_generated():
    run_phase6f4_reporting(REPO_ROOT)
    assert (PLOTS / "inference_validity.png").stat().st_size > 0


def test_synthetic_labels_present_on_tables_and_report():
    run_phase6f4_reporting(REPO_ROOT)
    rows = read_csv(OUT / "llm_metric_summary_table.csv")
    assert all(row["synthetic_label"] == REPORT_NOTICE for row in rows)
    assert REPORT_NOTICE in (OUT / "phase6f4_predata_readiness_report.md").read_text(encoding="utf-8")


def test_no_scientific_interpretation_text_generated():
    run_phase6f4_reporting(REPO_ROOT)
    text = (OUT / "phase6f4_predata_readiness_report.md").read_text(encoding="utf-8").lower()
    for prohibited in ["significantly better", "superior", "outperforms", "best model", "history improves performance", "baseline underperforms"]:
        assert prohibited not in text


def test_readiness_audit_derives_phase6b_gate():
    audit = run_phase6f4_reporting(REPO_ROOT)
    assert audit["phase6b_pipeline_ready"] is True


def test_readiness_audit_derives_phase6c_status():
    audit = run_phase6f4_reporting(REPO_ROOT)
    assert audit["phase6c_baseline_infrastructure_ready"] is True


def test_readiness_audit_derives_phase6d_frozen_status():
    audit = run_phase6f4_reporting(REPO_ROOT)
    assert audit["phase6d_prompt_package_frozen"] is True


def test_readiness_audit_derives_phase6e_infrastructure_status():
    audit = run_phase6f4_reporting(REPO_ROOT)
    assert audit["phase6e_inference_infrastructure_ready"] is True


def test_unresolved_phase6e2_live_gates_remain_false():
    audit = run_phase6f4_reporting(REPO_ROOT)
    assert audit["phase6e_live_model_identities_frozen"] is False
    assert audit["phase6e_live_backends_verified"] is False


def test_phase6f1_gate_included():
    audit = run_phase6f4_reporting(REPO_ROOT)
    assert audit["phase6f_e2e_alignment_ready"] is True


def test_phase6f2_validation_included():
    audit = run_phase6f4_reporting(REPO_ROOT)
    assert audit["phase6f_metrics_validated"] is True


def test_phase6f3_validation_included():
    audit = run_phase6f4_reporting(REPO_ROOT)
    assert audit["phase6f_comparisons_validated"] is True


def test_real_data_pipeline_ready_evaluated_correctly():
    audit = run_phase6f4_reporting(REPO_ROOT)
    assert audit["real_data_pipeline_ready"] is True


def test_production_inference_ready_remains_false_when_live_config_unresolved():
    audit = run_phase6f4_reporting(REPO_ROOT)
    assert audit["production_inference_ready"] is False


def test_predata_analysis_ready_evaluated_correctly():
    audit = run_phase6f4_reporting(REPO_ROOT)
    assert audit["predata_analysis_ready"] is True


def test_phase6f_predata_dry_run_complete_evaluated_correctly():
    audit = run_phase6f4_reporting(REPO_ROOT)
    assert audit["phase6f_predata_dry_run_complete"] is True


def test_principal_baseline_comparator_unresolved_status_retained():
    audit = run_phase6f4_reporting(REPO_ROOT)
    assert audit["principal_baseline_comparator"] == "UNRESOLVED"


def test_deterministic_reporting_rerun():
    run_phase6f4_reporting(REPO_ROOT)
    first = {path.relative_to(OUT).as_posix(): sha256_file(path) for path in sorted(OUT.rglob("*")) if path.is_file()}
    run_phase6f4_reporting(REPO_ROOT)
    second = {path.relative_to(OUT).as_posix(): sha256_file(path) for path in sorted(OUT.rglob("*")) if path.is_file()}
    assert first == second


def test_no_metrics_recomputed_inconsistently():
    run_phase6f4_reporting(REPO_ROOT)
    source = read_csv(REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6f2_metrics" / "llm_metric_summary.csv")
    table = read_csv(OUT / "llm_metric_summary_table.csv")
    assert table[0]["strict_top1_accuracy"] == source[0]["strict_top1_accuracy"]
    assert table[0]["mean_per_trial_mae"] == source[0]["mean_per_trial_mae"]


def test_predata_checklist_generated():
    run_phase6f4_reporting(REPO_ROOT)
    rows = read_csv(OUT / "pre_real_data_checklist.csv")
    assert any(row["remaining_step"] == "verify exact four model/checkpoint identities" for row in rows)
    assert any(row["remaining_step"] == "execute LLM production" for row in rows)


def test_gate_checker_script_succeeds_for_predata_readiness():
    run_phase6f4_reporting(REPO_ROOT)
    result = subprocess.run([sys.executable, "llm-experiments/scripts/check_phase6_predata_readiness.py"], cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0


def test_reporting_protocol_version_recorded():
    audit = run_phase6f4_reporting(REPO_ROOT)
    assert audit["reporting_version"] == PHASE6F_REPORTING_VERSION


def test_hash_manifest_generated():
    run_phase6f4_reporting(REPO_ROOT)
    manifest = json.loads((OUT / "phase6f4_hash_manifest.json").read_text(encoding="utf-8"))
    assert manifest["reporting_version"] == PHASE6F_REPORTING_VERSION
    assert "strict_top1_accuracy_by_condition" in manifest["artifacts"]


def read_csv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))
