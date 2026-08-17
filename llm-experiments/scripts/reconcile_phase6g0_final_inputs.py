from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.prompts.freeze_package import verify_prompt_package  # noqa: E402
from llm_experiments.inference.configuration import production_preflight  # noqa: E402


OUTPUT_DIR = REPO_ROOT / "llm-experiments" / "outputs"
READINESS_JSON = OUTPUT_DIR / "phase6g0_final_execution_readiness.json"
REPORT_MD = OUTPUT_DIR / "phase6g0_reconciliation_report.md"
FINAL_BASELINE_DIR = REPO_ROOT / "statistical-baseline" / "outputs" / "real_heldout_evaluation" / "mcmc_phase6_split"
FINAL_DATA_DIR = REPO_ROOT / "statistical-baseline" / "data" / "real"
PHASE6F_SCHEMA = REPO_ROOT / "statistical-baseline" / "schema" / "phase6f_evaluation_ready_baseline_prediction_schema.csv"
PHASE6B_REAL_DIR = REPO_ROOT / "llm-experiments" / "outputs" / "real" / "phase6b"
PHASE6E2_SUMMARY = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6e2" / "phase6e2_summary.json"
PHASE6E_PRIMARY_CONFIG = REPO_ROOT / "llm-experiments" / "config" / "phase6e_primary_inference_config_v1.json"


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    state = build_state()
    write_json(READINESS_JSON, state)
    REPORT_MD.write_text(build_report(state), encoding="utf-8")
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0


def build_state() -> dict[str, Any]:
    manifest = load_json(FINAL_BASELINE_DIR / "evaluation_manifest.json")
    data_manifest = load_json(FINAL_DATA_DIR / "real_cleaning_manifest.json")
    data_summary = read_csv(FINAL_DATA_DIR / "real_data_summary.csv")[0]
    trial_predictions = read_csv(FINAL_BASELINE_DIR / "trial_predictions.csv")
    candidate_predictions = read_csv(FINAL_BASELINE_DIR / "candidate_predictions.csv")
    fold_diagnostics = read_csv(FINAL_BASELINE_DIR / "fold_diagnostics.csv")
    split_manifest = read_csv(FINAL_BASELINE_DIR / "heldout_split_manifest.csv")
    leakage_audit = read_csv(FINAL_BASELINE_DIR / "leakage_audit.csv")
    output_validation = read_csv(FINAL_BASELINE_DIR / "output_validation.csv")
    schema_columns = [row["column_name"] for row in read_csv(PHASE6F_SCHEMA)]
    prompt_preflight = verify_prompt_package(REPO_ROOT)
    production = production_preflight(REPO_ROOT)
    phase6e2 = load_json(PHASE6E2_SUMMARY) if PHASE6E2_SUMMARY.exists() else {}
    primary_config = load_json(PHASE6E_PRIMARY_CONFIG)

    final_dataset_locked = (
        data_summary.get("final_gate") == "REAL DATA READY FOR STATISTICAL MODELLING"
        and Path(data_manifest["raw_provenance"]["stored_path"]).name == "listening_preference_responses_33_immutable.xlsx"
        and data_summary.get("raw_submissions") == "33"
    )
    real_phase6b_outputs_ready = required_phase6b_real_outputs_exist()
    baseline_alignment = assess_baseline_alignment(manifest, trial_predictions, candidate_predictions, fold_diagnostics, leakage_audit, output_validation, schema_columns)
    freeze_gates = phase6e2.get("validation", {}).get("freeze_gates", {})
    config_freeze_gates = primary_config.get("freeze_gates", {})
    model_identities_frozen = bool(freeze_gates.get("MODEL_IDENTITIES_FROZEN", production.get("MODEL_IDENTITIES_FROZEN", False)))
    inference_backends_verified = bool(freeze_gates.get("INFERENCE_BACKENDS_VERIFIED", production.get("INFERENCE_BACKENDS_VERIFIED", False)))
    primary_inference_config_frozen = bool(freeze_gates.get("PRIMARY_INFERENCE_CONFIG_FROZEN", production.get("PRIMARY_INFERENCE_CONFIG_FROZEN", False)))
    if not freeze_gates:
        model_identities_frozen = bool(config_freeze_gates.get("MODEL_IDENTITIES_FROZEN", model_identities_frozen))
        inference_backends_verified = bool(config_freeze_gates.get("INFERENCE_BACKENDS_VERIFIED", inference_backends_verified))
        primary_inference_config_frozen = bool(config_freeze_gates.get("PRIMARY_INFERENCE_CONFIG_FROZEN", primary_inference_config_frozen))
    production_ready = bool(production.get("production_inference_allowed", False))
    unresolved_items = production.get("unresolved_items") or primary_config.get("unresolved_items", [])

    return {
        "schema_version": "phase6g0_final_execution_readiness_v1",
        "run_type": "repository_reconciliation_only",
        "phase3_final_models_complete": final_dataset_locked and (REPO_ROOT / "statistical-baseline" / "outputs" / "real_stimulus_model").exists() and (REPO_ROOT / "statistical-baseline" / "outputs" / "real_feature_model").exists(),
        "phase3_final_heldout_predictions_complete": bool(manifest["completion_status"]["complete"] and manifest["validation_passed"]),
        "authoritative_baseline_source": "statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split",
        "authoritative_baseline_source_type": "final_empirical_phase3_mcmc_leave_one_trial_out",
        "baseline_phase6_alignment_valid": baseline_alignment["valid"],
        "baseline_phase6f_ready_export_present": False,
        "baseline_phase6f_adapter_required": True,
        "baseline_phase6_alignment_details": baseline_alignment,
        "phase6c_production_rerun_needed": False,
        "phase6c_production_rerun_reason": "Final Phase 3 MCMC held-out predictions are complete and methodologically aligned; Phase 6 should consume/adapt these outputs rather than refit the old Phase 6C production path.",
        "principal_baseline_comparator": "both_predefined_primary",
        "principal_baseline_comparator_status": "both categorical_design and primary_acoustic are retained as primary/predefined; no single comparator selected from empirical performance.",
        "final_dataset_locked": final_dataset_locked,
        "final_dataset_source": "statistical-baseline/data/real/raw/listening_preference_responses_33_immutable.xlsx",
        "final_dataset_sha256": data_manifest["raw_provenance"]["sha256"],
        "final_dataset_participant_count": int(data_summary["final_recommended_analysable_n"]),
        "final_dataset_rating_rows": int(data_summary["final_analysable_rating_rows"]),
        "real_phase6b_outputs_ready": real_phase6b_outputs_ready,
        "real_phase6b_output_dir_checked": repo_rel(PHASE6B_REAL_DIR),
        "real_phase6b_next_input": "statistical-baseline/data/real/raw/listening_preference_responses_33_immutable.xlsx or an exact CSV export of its listening-study-5mix sheet",
        "real_phase6b_next_command": "If exported as CSV: python llm-experiments/scripts/build_analysis_ready_dataset.py --input <final_netlify_export.csv> --output-dir llm-experiments/outputs/real/phase6b/phase6b1 ; then run build_preference_targets.py, build_prediction_examples.py, and build_prompt_data_objects.py on those outputs.",
        "phase6d_prompt_package_verified": bool(prompt_preflight.get("PHASE6D_PROMPT_PACKAGE_FROZEN") and prompt_preflight.get("artifact_hashes_valid") and prompt_preflight.get("reference_prompt_hashes_valid")),
        "phase6d_prompt_package_version": prompt_preflight.get("package_version"),
        "model_identities_frozen": model_identities_frozen,
        "inference_backends_verified": inference_backends_verified,
        "primary_inference_config_frozen": primary_inference_config_frozen,
        "production_inference_ready": production_ready,
        "phase6e_unresolved_items": unresolved_items,
        "phase6e_primary_config_path": repo_rel(PHASE6E_PRIMARY_CONFIG),
        "ready_for_phase6g1": bool(final_dataset_locked and baseline_alignment["valid"] and prompt_preflight.get("PHASE6D_PROMPT_PACKAGE_FROZEN")),
        "ready_for_real_llm_inference": bool(real_phase6b_outputs_ready and model_identities_frozen and inference_backends_verified and primary_inference_config_frozen and production_ready),
        "identifier_reconciliation": {
            "phase3_prediction_example_pattern": "real_loto__{participant_id}__trial_##",
            "phase3_target_trial_pattern": "{participant_id}__trial_##",
            "phase6b_real_outputs_present": real_phase6b_outputs_ready,
            "expected_phase6b_prediction_example_mapping": "must preserve or map to Phase 3 prediction_example_id values before final LLM-vs-baseline scoring",
            "mapping_incompatibility": None if real_phase6b_outputs_ready else "Real Phase 6B prediction examples are not yet generated, so end-to-end ID equality cannot be verified today.",
        },
        "counts": {
            "heldout_participants": manifest["n_participants"],
            "heldout_targets": manifest["n_trials"],
            "heldout_candidate_rows": manifest["n_candidate_rows"],
            "heldout_trial_prediction_rows": len(trial_predictions),
            "heldout_candidate_prediction_rows": len(candidate_predictions),
            "heldout_model_fit_count": manifest["model_fit_count"],
            "fit_status_counts": dict(Counter(row["fit_status"] for row in fold_diagnostics)),
        },
        "remaining_phase6_sequence": [
            "6G.1 Generate final real Phase 6B outputs and verify identifier compatibility with Phase 3 baseline prediction_example_id values.",
            "6G.2 Freeze exact four model/checkpoint identities and live QMUL/RunPod backend contracts.",
            "6G.3 Render/freeze final real prompts from Phase 6B prompt-data objects.",
            "6G.4 Execute four-model production inference with Phase 6E logging/failure handling.",
            "6G.5 Merge/freeze LLM prediction records and adapt final Phase 3 baseline predictions into the Phase 6F-ready compact schema.",
            "6H Run real scoring, participant-aware comparisons, and reporting from frozen predictions only.",
        ],
        "inspected_files": inspected_files(),
    }


def assess_baseline_alignment(manifest: dict[str, Any], trial_rows: list[dict[str, str]], candidate_rows: list[dict[str, str]], diag_rows: list[dict[str, str]], leakage_rows: list[dict[str, str]], validation_rows: list[dict[str, str]], schema_columns: list[str]) -> dict[str, Any]:
    trial_keys = {(row["prediction_example_id"], row["baseline_model"]) for row in trial_rows}
    diag_keys = {(row["prediction_example_id"], row["baseline_model"]) for row in diag_rows}
    candidate_counts = Counter((row["prediction_example_id"], row["baseline_model"]) for row in candidate_rows)
    labels = sorted({row["presentation_label"] for row in candidate_rows})
    candidate_fields = set(candidate_rows[0]) if candidate_rows else set()
    trial_fields = set(trial_rows[0]) if trial_rows else set()
    available_or_constructable = {
        "prediction_example_id": "prediction_example_id" in trial_fields,
        "participant_id": "participant_id" in trial_fields,
        "trial_id": "trial_id" in trial_fields and "target_trial_id" in trial_fields,
        "baseline_model": "baseline_model" in trial_fields,
        "model_role": bool(manifest.get("models")),
        "predicted_preferred_mix": "predicted_winner_label" in trial_fields,
        "predicted_tie": "predicted_tie" in trial_fields,
        "predicted_ratings_A_E": {"presentation_label", "posterior_mean_expected_rating"} <= candidate_fields and labels == ["A", "B", "C", "D", "E"],
        "winning_probabilities_A_E": {"presentation_label", "posterior_probability_highest"} <= candidate_fields and labels == ["A", "B", "C", "D", "E"],
        "fit_status": "fit_status" in set(diag_rows[0]) if diag_rows else False,
        "protocol_version": True,
    }
    validation_passed = all(row["passed"] == "True" for row in validation_rows)
    return {
        "valid": bool(
            manifest["completion_status"]["complete"]
            and manifest["validation_passed"]
            and manifest["split_rule"].startswith("leave-one-trial-out participant-trial")
            and manifest["completion_status"]["all_leakage_checks_pass"]
            and trial_keys == diag_keys
            and set(candidate_counts.values()) == {5}
            and labels == ["A", "B", "C", "D", "E"]
            and all(row["leakage_passed"] == "True" for row in leakage_rows)
            and validation_passed
            and all(available_or_constructable.values())
        ),
        "methodologically_equivalent_to_phase6a_loto": manifest["split_rule"] == "leave-one-trial-out participant-trial; all five candidate rows excluded together",
        "target_outcome_excluded_from_fit": manifest["completion_status"]["all_leakage_checks_pass"] and all(row["leakage_passed"] == "True" for row in leakage_rows),
        "same_frozen_baseline_formulas": sorted(model["model_id"] for model in manifest["models"]) == ["categorical_design", "primary_acoustic"],
        "covers_all_final_eligible_targets": manifest["completion_status"]["target_count"] == 198 and manifest["completion_status"]["both_models_for_every_target"],
        "can_replace_old_phase6c_smoke_baseline": True,
        "phase6f_schema_columns": schema_columns,
        "source_fields_available_or_constructable": available_or_constructable,
        "exact_phase6f_file_present": False,
    }


def required_phase6b_real_outputs_exist() -> bool:
    required = [
        PHASE6B_REAL_DIR / "final_analysis_ready_long.csv",
        PHASE6B_REAL_DIR / "final_trial_ground_truth_targets.csv",
        PHASE6B_REAL_DIR / "final_candidate_ground_truth_enriched.csv",
        PHASE6B_REAL_DIR / "final_prediction_examples.jsonl",
        PHASE6B_REAL_DIR / "final_prompt_data_objects.jsonl",
    ]
    return all(path.exists() for path in required)


def build_report(state: dict[str, Any]) -> str:
    if state["real_phase6b_outputs_ready"]:
        blocker = "Phase 6E.2 live model/backend gates remain unresolved. Do not start production LLM inference until exact model identities, backend contracts, and the primary inference config are frozen."
    else:
        blocker = "Real Phase 6B outputs and real rendered prompts are not yet generated, and Phase 6E.2 live model/backend gates remain unresolved. Do not start production LLM inference until those are complete."
    lines = [
        "# Phase 6G.0 Final-Input Reconciliation Report",
        "",
        "Scope: repository reconciliation only. No LLMs were run, no statistical models were refit, prompt wording was not changed, and no new scientific comparisons were calculated.",
        "",
        "## Final Phase 3 Status",
        "",
        f"- Final dataset locked: `{str(state['final_dataset_locked']).lower()}`",
        f"- Final empirical held-out predictions complete: `{str(state['phase3_final_heldout_predictions_complete']).lower()}`",
        f"- Participants/targets/candidate rows: `{state['counts']['heldout_participants']}` / `{state['counts']['heldout_targets']}` / `{state['counts']['heldout_candidate_rows']}`",
        f"- Authoritative baseline source: `{state['authoritative_baseline_source']}`",
        "",
        "## Phase 3 To Phase 6 Alignment",
        "",
        f"- Baseline alignment valid: `{str(state['baseline_phase6_alignment_valid']).lower()}`",
        f"- Methodologically equivalent to Phase 6A LOTO: `{str(state['baseline_phase6_alignment_details']['methodologically_equivalent_to_phase6a_loto']).lower()}`",
        f"- Held-out target outcomes excluded from fit: `{str(state['baseline_phase6_alignment_details']['target_outcome_excluded_from_fit']).lower()}`",
        f"- Covers all final eligible targets: `{str(state['baseline_phase6_alignment_details']['covers_all_final_eligible_targets']).lower()}`",
        f"- Phase 6F-ready compact export present: `{str(state['baseline_phase6f_ready_export_present']).lower()}`",
        "",
        "The final Phase 3 MCMC held-out predictions can replace the old Phase 6C synthetic/smoke baseline for final Phase 6 comparisons. A small adapter/export step is still needed to materialize the compact Phase 6F schema.",
        "",
        "## Principal Baseline Comparator",
        "",
        f"`{state['principal_baseline_comparator']}`. {state['principal_baseline_comparator_status']}",
        "",
        "## Final Dataset And Phase 6B",
        "",
        f"- Final raw source: `{state['final_dataset_source']}`",
        f"- Raw SHA-256: `{state['final_dataset_sha256']}`",
        f"- Real Phase 6B outputs ready: `{str(state['real_phase6b_outputs_ready']).lower()}`",
        f"- Next input: `{state['real_phase6b_next_input']}`",
        f"- Next command: `{state['real_phase6b_next_command']}`",
        "",
        "## Phase 6D And 6E",
        "",
        f"- Prompt package verified: `{str(state['phase6d_prompt_package_verified']).lower()}`",
        f"- Model identities frozen: `{str(state['model_identities_frozen']).lower()}`",
        f"- Inference backends verified: `{str(state['inference_backends_verified']).lower()}`",
        f"- Primary inference config frozen: `{str(state['primary_inference_config_frozen']).lower()}`",
        f"- Production inference ready: `{str(state['production_inference_ready']).lower()}`",
        "- Unresolved live items:",
        *[f"  - {item}" for item in state["phase6e_unresolved_items"]],
        "",
        "## Remaining Execution Plan",
        "",
        *[f"- {step}" for step in state["remaining_phase6_sequence"]],
        "",
        "## Current Blocker To Real LLM Inference Today",
        "",
        blocker,
    ]
    return "\n".join(lines) + "\n"


def inspected_files() -> list[str]:
    paths = [
        "llm-experiments/llm_evaluation_protocol.md",
        "llm-experiments/src/llm_experiments/data/processing.py",
        "llm-experiments/src/llm_experiments/data/targets.py",
        "llm-experiments/src/llm_experiments/data/examples.py",
        "llm-experiments/src/llm_experiments/data/prompt_data.py",
        "llm-experiments/config/phase6e_model_registry_v1.json",
        "llm-experiments/config/phase6e_backend_registry_v1.json",
        "llm-experiments/config/phase6e_primary_inference_config_v1.json",
        "statistical-baseline/README.md",
        "statistical-baseline/data/real/real_cleaning_manifest.json",
        "statistical-baseline/data/real/real_data_summary.csv",
        "statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split/evaluation_manifest.json",
        "statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split/trial_predictions.csv",
        "statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split/candidate_predictions.csv",
        "statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split/fold_diagnostics.csv",
        "statistical-baseline/outputs/real_heldout_evaluation/mcmc_phase6_split/leakage_audit.csv",
        "statistical-baseline/schema/phase6f_evaluation_ready_baseline_prediction_schema.csv",
    ]
    return paths


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


if __name__ == "__main__":
    raise SystemExit(main())
