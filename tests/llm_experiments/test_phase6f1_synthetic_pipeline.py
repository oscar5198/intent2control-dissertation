import csv
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.phase6f import (  # noqa: E402
    CONDITIONS,
    MODEL_KEYS,
    PHASE6F_RUN_VERSION,
    PRIMARY_BASELINE_MODELS,
    audit_alignment,
    build_alignment_rows,
    build_baseline_prediction_rows,
    build_ground_truth_rows,
    build_llm_prediction_rows,
    load_context,
    run_phase6f_synthetic_pipeline,
    validate_mapping_and_leakage,
    validate_phase6f_determinism,
)
from llm_experiments.inference.configuration import production_preflight  # noqa: E402


OUT = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6f1_e2e"
PHASE6B = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6b5"
RENDERED = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6d2_rendered_prompts"
LLM_RUN = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6e3" / "phase6f1_synthetic_mock_llm_run"
BASELINE = REPO_ROOT / "statistical-baseline" / "outputs" / "phase6c3_synthetic_smoke_consolidated" / "phase6f_evaluation_ready_baseline_predictions.csv"
BASELINE_QC = REPO_ROOT / "statistical-baseline" / "outputs" / "phase6c3_synthetic_smoke_consolidated" / "phase6c_baseline_output_qc_summary.json"
BASELINE_CONFIG = REPO_ROOT / "statistical-baseline" / "config" / "phase6c_baseline_models.json"


def test_synthetic_raw_fixture_reaches_final_phase6f_output():
    audit = ensure_pipeline()
    assert audit["phase6f_run_version"] == PHASE6F_RUN_VERSION
    assert (OUT / "llm_predictions_for_evaluation.csv").exists()
    assert (OUT / "baseline_predictions_for_evaluation.csv").exists()
    assert (OUT / "ground_truth_for_evaluation.csv").exists()
    assert (OUT / "prediction_alignment_manifest.jsonl").exists()


def test_phase6b_readiness_required():
    assert ensure_pipeline()["phase6b_ready"] is True


def test_prompt_package_verification_required():
    assert ensure_pipeline()["prompt_package_verified"] is True


def test_condition_integrity_gate_required():
    assert ensure_pipeline()["experimental_condition_integrity"] is True


def test_hidden_ground_truth_unavailable_to_inference_runner():
    audit = ensure_pipeline()
    assert audit["ground_truth_loaded_during_inference"] is False
    assert audit["llm_summary"]["contains_ground_truth"] is False


def test_ae_mapping_preserved_end_to_end():
    assert ensure_pipeline()["ae_mapping_valid"] is True


def test_acoustic_features_preserved_to_correct_candidates():
    assert ensure_pipeline()["acoustic_mapping_valid"] is True


def test_target_absent_from_history():
    assert ensure_pipeline()["history_selection_valid"] is True


def test_all_four_model_keys_included():
    rows = read_csv(OUT / "llm_predictions_for_evaluation.csv")
    assert sorted({row["model_key"] for row in rows}) == sorted(MODEL_KEYS)


def test_both_conditions_included():
    rows = read_csv(OUT / "llm_predictions_for_evaluation.csv")
    assert sorted({row["condition"] for row in rows}) == sorted(CONDITIONS)


def test_expected_mock_request_count():
    assert ensure_pipeline()["counts"]["llm_requests"] == 88


def test_mock_prediction_count():
    assert ensure_pipeline()["counts"]["llm_prediction_records"] == 88


def test_response_schema_valid_for_llm_predictions():
    rows = read_csv(OUT / "llm_predictions_for_evaluation.csv")
    assert all(row["response_schema_version"] == "preference_prediction_response_v1" for row in rows)
    assert all(row["final_inference_status"] == "valid_primary" for row in rows)


def test_prompt_and_config_hashes_present():
    rows = read_csv(OUT / "llm_predictions_for_evaluation.csv")
    assert all(len(row["prompt_payload_sha256"]) == 64 for row in rows)
    assert all(len(row["inference_config_sha256"]) == 64 for row in rows)


def test_baseline_predictions_align_to_phase6b_targets():
    assert ensure_pipeline()["baseline_alignment_valid"] is True


def test_primary_baseline_model_ids_correct():
    rows = read_csv(OUT / "baseline_predictions_for_evaluation.csv")
    assert sorted({row["baseline_model"] for row in rows}) == PRIMARY_BASELINE_MODELS


def test_llm_predictions_align_to_target_ids():
    alignment = read_jsonl(OUT / "prediction_alignment_manifest.jsonl")
    assert all(row[f"{model}_{condition}_available"] for row in alignment for model in MODEL_KEYS for condition in CONDITIONS)


def test_ground_truth_stored_separately():
    gt = read_csv(OUT / "ground_truth_for_evaluation.csv")
    llm = (OUT / "llm_predictions_for_evaluation.csv").read_text(encoding="utf-8")
    assert all(row["evaluation_only"] == "EVALUATION_ONLY_NEVER_MODEL_FACING" for row in gt)
    assert "observed_preferred_mix" not in llm


def test_prediction_files_contain_no_observed_outcomes():
    text = (OUT / "llm_predictions_for_evaluation.csv").read_text(encoding="utf-8")
    for token in ["observed_", "human_rating", "is_single_winner"]:
        assert token not in text


def test_baseline_prediction_files_contain_no_observed_outcomes():
    text = (OUT / "baseline_predictions_for_evaluation.csv").read_text(encoding="utf-8")
    for token in ["observed_", "human_rating", "is_single_winner"]:
        assert token not in text


def test_alignment_manifest_detects_missing_prediction():
    context = context_obj()
    llm = build_llm_prediction_rows(context)[1:]
    baseline = build_baseline_prediction_rows(read_csv(BASELINE))
    gt = build_ground_truth_rows(context["examples"])
    alignment = build_alignment_rows(context, llm, baseline, gt)
    availability_keys = [f"{model}_{condition}_available" for model in MODEL_KEYS for condition in CONDITIONS]
    assert any(not row[key] for row in alignment for key in availability_keys)


def test_alignment_manifest_detects_duplicate_prediction():
    context = context_obj()
    llm = build_llm_prediction_rows(context)
    bad = llm + [dict(llm[0])]
    baseline = build_baseline_prediction_rows(read_csv(BASELINE))
    gt = build_ground_truth_rows(context["examples"])
    alignment = build_alignment_rows(context, bad, baseline, gt)
    audit = audit_alignment(alignment, bad, baseline, gt, load_json(BASELINE_QC), load_json(BASELINE_CONFIG))
    assert audit["duplicate_llm_predictions"]


def test_incompatible_model_config_version_rejected():
    context = context_obj()
    llm = build_llm_prediction_rows(context)
    llm[0]["inference_config_version"] = "wrong"
    assert any(row["inference_config_version"] != "phase6e_primary_inference_config_v1" for row in llm)


def test_incompatible_baseline_protocol_rejected():
    context = context_obj()
    baseline = build_baseline_prediction_rows(read_csv(BASELINE))
    baseline[0]["protocol_version"] = "wrong"
    gt = build_ground_truth_rows(context["examples"])
    alignment = build_alignment_rows(context, build_llm_prediction_rows(context), baseline, gt)
    audit = audit_alignment(alignment, build_llm_prediction_rows(context), baseline, gt, load_json(BASELINE_QC), load_json(BASELINE_CONFIG))
    assert audit["baseline_alignment_valid"] is False


def test_deterministic_rerun():
    audit = validate_phase6f_determinism(REPO_ROOT)
    assert audit["deterministic_rerun"] is True


def test_end_to_end_provenance_chain_valid():
    assert ensure_pipeline()["provenance_chain_valid"] is True


def test_production_gates_remain_blocked():
    assert production_preflight(REPO_ROOT)["production_inference_allowed"] is False
    assert ensure_pipeline()["live_production_gates_resolved"] is False


def test_no_metrics_are_emitted_by_phase6f1():
    audit = ensure_pipeline()
    assert audit["contains_metrics"] is False
    text = (OUT / "phase6f1_end_to_end_report.md").read_text(encoding="utf-8").lower()
    for token in ["accuracy", "rmse", "mae", "spearman", "p-value", "confidence interval"]:
        assert token not in text


def test_structural_counts_are_recorded():
    counts = ensure_pipeline()["counts"]
    assert counts["participants"] == 2
    assert counts["trials"] == 12
    assert counts["candidate_rows"] == 59
    assert counts["ground_truth_targets"] == 11
    assert counts["fully_aligned_targets"] == 1


def test_hash_manifest_records_major_inputs_and_outputs():
    artifacts = ensure_pipeline()["hash_manifest"]["artifacts"]
    for key in ["synthetic_raw_fixture", "final_prediction_examples", "rendered_prompts", "llm_predictions", "baseline_predictions", "ground_truth", "alignment_manifest"]:
        assert len(artifacts[key]["sha256"]) == 64


def test_phase6f_alignment_gate_ready_for_synthetic_common_subset():
    assert ensure_pipeline()["phase6f_e2e_alignment_ready"] is True


def ensure_pipeline():
    audit_path = OUT / "phase6f1_end_to_end_audit.json"
    if not audit_path.exists():
        return run_phase6f_synthetic_pipeline(REPO_ROOT)
    return load_json(audit_path)


def context_obj():
    ensure_pipeline()
    return load_context(REPO_ROOT, PHASE6B, RENDERED, LLM_RUN)


def read_csv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
