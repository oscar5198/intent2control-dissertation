from __future__ import annotations

import csv
import filecmp
import hashlib
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.data.examples import write_prediction_example_outputs  # noqa: E402
from llm_experiments.data.integration import (  # noqa: E402
    audit_condition_equivalence,
    audit_hidden_ground_truth_separation,
    audit_identifier_integrity,
    audit_leakage,
    audit_provenance_leakage,
    build_determinism_report,
    run_pipeline_once,
)
from llm_experiments.data.processing import EXPECTED_LABELS, write_json  # noqa: E402
from llm_experiments.data.prompt_data import validate_prompt_data_no_leakage  # noqa: E402
from llm_experiments.data.targets import boolish  # noqa: E402


LOCKED_XLSX = REPO_ROOT / "statistical-baseline" / "data" / "real" / "raw" / "listening_preference_responses_33_immutable.xlsx"
LOCKED_SHA256 = "5bab388fbf564e0caf5c1ca8a5a722bf8d517e23c018e48375d076e75dba0bdd"
WORKBOOK_SHEET = "listening-study-5mix"
PARTICIPANT_MAP_CSV = REPO_ROOT / "statistical-baseline" / "data" / "real" / "real_participants_clean.csv"
PHASE3_BASELINE_DIR = REPO_ROOT / "statistical-baseline" / "outputs" / "real_heldout_evaluation" / "mcmc_phase6_split"
STIMULI = REPO_ROOT / "study-interface" / "frontend-5mix" / "config" / "stimuli.json"
FEATURES = REPO_ROOT / "statistical-baseline" / "outputs" / "feature_exploration" / "final_20_stimulus_feature_table.csv"
OUTPUT_DIR = REPO_ROOT / "llm-experiments" / "outputs" / "real" / "phase6b"
READINESS_UPDATE = REPO_ROOT / "llm-experiments" / "outputs" / "phase6g1_real_phase6b_readiness.json"

FINAL_COPIES = {
    "final_analysis_ready_long.csv": "analysis_ready",
    "final_candidate_ground_truth_enriched.csv": "candidate_ground_truth",
    "final_trial_ground_truth_targets.csv": "trial_ground_truth",
    "final_prediction_examples.jsonl": "prediction_examples",
    "final_prompt_data_objects.jsonl": "prompt_data",
}


def main() -> int:
    report = run_phase6g1_pipeline(REPO_ROOT, OUTPUT_DIR)
    print(f"REAL_PHASE6B_READY={str(report['REAL_PHASE6B_READY']).lower()}")
    print(f"prediction_examples={report['counts']['prediction_example_count']}")
    print(f"prompt_data_objects={report['counts']['condition_object_count']}")
    if not report["REAL_PHASE6B_READY"]:
        print(f"Failed checks: {', '.join(report['failed_checks'])}")
        return 1
    return 0


def run_phase6g1_pipeline(repo_root: Path = REPO_ROOT, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    locked_hash = sha256_file(LOCKED_XLSX)
    if locked_hash != LOCKED_SHA256:
        raise SystemExit(f"Dataset drift detected: {locked_hash} != {LOCKED_SHA256}")

    source_csv = export_locked_workbook_with_phase3_ids(output_dir / "phase6g1_locked_real_export_phase3_ids.csv")

    run_1_dir = output_dir / "run_1"
    run_2_dir = output_dir / "run_2"
    reset_dir(run_1_dir)
    reset_dir(run_2_dir)
    first = run_pipeline_once(source_csv, STIMULI, FEATURES, run_1_dir)
    second = run_pipeline_once(source_csv, STIMULI, FEATURES, run_2_dir)
    copy_final_artifacts(first, output_dir)

    phase3_targets = load_phase3_targets()
    alignment = build_phase3_alignment(first, phase3_targets)
    mapping_alignment = build_ae_mapping_alignment(first, phase3_targets)
    leakage = build_real_leakage_audit(first)
    determinism = build_determinism_report(first, second)
    structural = build_structural_counts(first, phase3_targets)
    readiness = build_readiness_gate(locked_hash, first, alignment, mapping_alignment, leakage, determinism, structural)
    hash_manifest = build_hash_manifest(output_dir)

    write_csv(output_dir / "phase3_target_alignment_report.csv", alignment["rows"], alignment["columns"])
    write_json(output_dir / "phase3_target_alignment_report.json", without_rows(alignment))
    write_csv(output_dir / "ae_mapping_alignment_report.csv", mapping_alignment["rows"], mapping_alignment["columns"])
    write_json(output_dir / "ae_mapping_alignment_report.json", without_rows(mapping_alignment))
    write_json(output_dir / "leakage_audit.json", leakage)
    write_json(output_dir / "deterministic_rebuild_audit.json", determinism)
    write_json(output_dir / "production_readiness_gate.json", readiness)
    hash_manifest = build_hash_manifest(output_dir)
    write_json(output_dir / "hash_manifest.json", hash_manifest)

    manifest = build_manifest(locked_hash, source_csv, first, structural, alignment, mapping_alignment, leakage, determinism, readiness, hash_manifest)
    write_json(output_dir / "phase6g1_real_phase6b_manifest.json", manifest)
    write_markdown_report(output_dir / "phase6g1_real_phase6b_report.md", manifest)
    write_json(READINESS_UPDATE, manifest)
    return manifest


def export_locked_workbook_with_phase3_ids(path: Path) -> Path:
    df = pd.read_excel(LOCKED_XLSX, sheet_name=WORKBOOK_SHEET, dtype=object)
    df = df.where(pd.notna(df), "")
    mapping = load_participant_id_mapping()
    missing = sorted(set(df["study_id"]) - set(mapping))
    if missing:
        raise ValueError(f"Locked workbook contains study_id values absent from Phase 3 participant map: {missing[:5]}")
    df["study_id"] = df["study_id"].map(mapping)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")
    return path


def load_participant_id_mapping() -> dict[str, str]:
    rows = read_csv(PARTICIPANT_MAP_CSV)
    return {row["source_study_id"]: row["participant_id"] for row in rows}


def load_phase3_targets() -> dict[tuple[str, str], dict[str, str]]:
    rows = read_csv(PHASE3_BASELINE_DIR / "candidate_predictions.csv")
    target_rows = [row for row in rows if row["baseline_model"] == "categorical_design"]
    return {
        (row["target_trial_id"], row["presentation_label"]): row
        for row in target_rows
    }


def build_phase3_alignment(run: dict[str, Any], phase3_targets: dict[tuple[str, str], dict[str, str]]) -> dict[str, Any]:
    phase3_trial_ids = sorted({trial_id for trial_id, _ in phase3_targets})
    phase6_trial_ids = sorted(example["input_data"]["target"]["trial_id"] for example in run["prediction_examples"])
    missing = sorted(set(phase3_trial_ids) - set(phase6_trial_ids))
    extra = sorted(set(phase6_trial_ids) - set(phase3_trial_ids))
    rows = []
    example_by_trial = {example["input_data"]["target"]["trial_id"]: example for example in run["prediction_examples"]}
    for trial_id in sorted(set(phase3_trial_ids) | set(phase6_trial_ids)):
        example = example_by_trial.get(trial_id)
        phase3_example_id = f"real_loto__{trial_id}" if trial_id in phase3_trial_ids else ""
        phase6_example_id = example["prediction_example_id"] if example else ""
        rows.append(
            {
                "trial_id": trial_id,
                "participant_id": trial_id.split("__trial_")[0],
                "phase3_prediction_example_id": phase3_example_id,
                "phase6b_prediction_example_id": phase6_example_id,
                "phase3_present": trial_id in phase3_trial_ids,
                "phase6b_present": trial_id in phase6_trial_ids,
                "aligned": trial_id in phase3_trial_ids and trial_id in phase6_trial_ids,
            }
        )
    return {
        "schema_version": "phase6g1_phase3_target_alignment_v1",
        "passed": not missing and not extra,
        "phase3_target_count": len(phase3_trial_ids),
        "phase6b_target_count": len(phase6_trial_ids),
        "aligned_target_count": sum(1 for row in rows if row["aligned"]),
        "missing_phase6b_targets": missing,
        "extra_phase6b_targets": extra,
        "columns": ["trial_id", "participant_id", "phase3_prediction_example_id", "phase6b_prediction_example_id", "phase3_present", "phase6b_present", "aligned"],
        "rows": rows,
    }


def build_ae_mapping_alignment(run: dict[str, Any], phase3_targets: dict[tuple[str, str], dict[str, str]]) -> dict[str, Any]:
    rows = []
    phase6_by_key = {}
    for row in run["analysis_rows"]:
        phase6_by_key[(row["trial_id"], row["presentation_label"])] = row
    keys = sorted(set(phase3_targets) | set(phase6_by_key))
    for trial_id, label in keys:
        phase3 = phase3_targets.get((trial_id, label), {})
        phase6 = phase6_by_key.get((trial_id, label), {})
        stimulus_match = str(phase3.get("stimulus_id", "")) == str(phase6.get("stimulus_id", ""))
        mix_match = str(phase3.get("mix_id", "")) == str(phase6.get("actual_mix_id", ""))
        rating_match = numbers_equal(phase3.get("observed_rating", ""), phase6.get("human_rating", ""))
        rows.append(
            {
                "trial_id": trial_id,
                "presentation_label": label,
                "phase3_stimulus_id": phase3.get("stimulus_id", ""),
                "phase6b_stimulus_id": phase6.get("stimulus_id", ""),
                "phase3_mix_id": phase3.get("mix_id", ""),
                "phase6b_mix_id": phase6.get("actual_mix_id", ""),
                "phase3_observed_rating": phase3.get("observed_rating", ""),
                "phase6b_human_rating": phase6.get("human_rating", ""),
                "stimulus_match": stimulus_match,
                "mix_match": mix_match,
                "rating_match": rating_match,
                "aligned": stimulus_match and mix_match and rating_match,
            }
        )
    failures = [row for row in rows if not row["aligned"]]
    return {
        "schema_version": "phase6g1_ae_mapping_alignment_v1",
        "passed": not failures,
        "candidate_alignment_count": sum(1 for row in rows if row["aligned"]),
        "candidate_row_count": len(rows),
        "failure_count": len(failures),
        "failures": failures[:25],
        "columns": [
            "trial_id",
            "presentation_label",
            "phase3_stimulus_id",
            "phase6b_stimulus_id",
            "phase3_mix_id",
            "phase6b_mix_id",
            "phase3_observed_rating",
            "phase6b_human_rating",
            "stimulus_match",
            "mix_match",
            "rating_match",
            "aligned",
        ],
        "rows": rows,
    }


def build_real_leakage_audit(run: dict[str, Any]) -> dict[str, Any]:
    base_audits = {
        "leakage": audit_leakage(run),
        "provenance_leakage": audit_provenance_leakage(run),
        "condition_equivalence": audit_condition_equivalence(run),
        "identifier_integrity": audit_identifier_integrity(run),
        "hidden_ground_truth_separation": audit_hidden_ground_truth_separation(run),
    }
    extra_failures = []
    for obj in run["condition_objects"]:
        try:
            validate_prompt_data_no_leakage(obj)
        except ValueError as exc:
            extra_failures.append(f"{obj['condition_object_id']}: {exc}")
        payload = json.dumps(obj["model_input"], sort_keys=True, ensure_ascii=False)
        if "z_SI" in payload:
            extra_failures.append(f"{obj['condition_object_id']}: z_SI leaked")
        if "source_study_id" in payload or "stimulus_id" in payload or "actual_mix_id" in payload or "audio_path" in payload:
            extra_failures.append(f"{obj['condition_object_id']}: provenance leaked")
    passed = all(audit["passed"] for audit in base_audits.values()) and not extra_failures
    return {
        "schema_version": "phase6g1_real_leakage_audit_v1",
        "passed": passed,
        "failure_count": len(extra_failures) + sum(audit.get("failure_count", 0) for audit in base_audits.values()),
        "base_audits": base_audits,
        "extra_failures": extra_failures[:50],
    }


def build_structural_counts(run: dict[str, Any], phase3_targets: dict[tuple[str, str], dict[str, str]]) -> dict[str, Any]:
    rows = run["analysis_rows"]
    targets = run["trial_targets"]
    examples = run["prediction_examples"]
    objects = run["condition_objects"]
    target_ineligible_reasons = Counter()
    for target in targets:
        if not boolish(target["target_eligible"]):
            reasons = str(target.get("target_ineligibility_reasons", "")).split("|")
            for reason in reasons:
                if reason:
                    target_ineligible_reasons[reason] += 1
    history_counts = Counter(example["n_history_trials"] for example in examples)
    return {
        "participant_count": len({row["participant_id"] for row in rows}),
        "candidate_row_count": len(rows),
        "trial_count": len({row["trial_id"] for row in rows}),
        "target_eligible_trial_count": sum(1 for target in targets if boolish(target["target_eligible"])),
        "target_ineligible_trial_count": sum(1 for target in targets if not boolish(target["target_eligible"])),
        "target_ineligibility_reason_counts": dict(sorted(target_ineligible_reasons.items())),
        "prediction_example_count": len(examples),
        "history_count_distribution": {str(key): value for key, value in sorted(history_counts.items())},
        "non_history_object_count": sum(1 for obj in objects if obj["condition"] == "non_history"),
        "personalised_history_object_count": sum(1 for obj in objects if obj["condition"] == "personalised_history"),
        "condition_object_count": len(objects),
        "phase3_candidate_rows": len(phase3_targets),
        "phase3_target_count": len({trial_id for trial_id, _ in phase3_targets}),
        "expected_rendered_prompt_count": len(objects),
        "expected_four_model_primary_inference_count": len(objects) * 4,
    }


def build_readiness_gate(
    locked_hash: str,
    run: dict[str, Any],
    alignment: dict[str, Any],
    mapping_alignment: dict[str, Any],
    leakage: dict[str, Any],
    determinism: dict[str, Any],
    structural: dict[str, Any],
) -> dict[str, Any]:
    checks = {
        "locked_dataset_hash_matches": locked_hash == LOCKED_SHA256,
        "canonical_transformation_passes": run["analysis_summary"]["candidate_row_count"] == 990 and not run["analysis_summary"]["issue_counts"],
        "participant_count_expected": structural["participant_count"] == 33,
        "candidate_row_count_expected": structural["candidate_row_count"] == 990,
        "target_count_matches_phase3": structural["target_eligible_trial_count"] == structural["phase3_target_count"] == 198,
        "phase3_target_alignment_passes": alignment["passed"],
        "ae_mapping_alignment_passes": mapping_alignment["passed"],
        "leakage_audit_passes": leakage["passed"],
        "prompt_data_construction_passes": structural["condition_object_count"] == structural["prediction_example_count"] * 2,
        "deterministic_rebuild_passes": determinism["passed"],
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "schema_version": "phase6g1_real_phase6b_readiness_gate_v1",
        "REAL_PHASE6B_READY": not failed,
        "failed_checks": failed,
        "checks": checks,
        "PRODUCTION_INFERENCE_READY": False,
        "production_inference_blocker": "Phase 6E.2 live model identities and backend contracts remain unresolved.",
    }


def build_hash_manifest(output_dir: Path) -> dict[str, Any]:
    self_updating = {
        "hash_manifest.json",
        "phase6g1_real_phase6b_manifest.json",
        "phase6g1_real_phase6b_report.md",
    }
    files = sorted(path for path in output_dir.iterdir() if path.is_file())
    return {
        "schema_version": "phase6g1_hash_manifest_v1",
        "files": [
            {
                "path": repo_rel(path),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for path in files
            if path.name not in self_updating
        ],
    }


def build_manifest(
    locked_hash: str,
    source_csv: Path,
    run: dict[str, Any],
    structural: dict[str, Any],
    alignment: dict[str, Any],
    mapping_alignment: dict[str, Any],
    leakage: dict[str, Any],
    determinism: dict[str, Any],
    readiness: dict[str, Any],
    hash_manifest: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "phase6g1_real_phase6b_manifest_v1",
        "run_type": "final_real_phase6b_dataset_freeze",
        "locked_dataset_path": repo_rel(LOCKED_XLSX),
        "locked_dataset_sheet": WORKBOOK_SHEET,
        "locked_dataset_sha256": locked_hash,
        "phase3_pseudonymized_source_csv": repo_rel(source_csv),
        "participant_map_source": repo_rel(PARTICIPANT_MAP_CSV),
        "phase3_baseline_source": repo_rel(PHASE3_BASELINE_DIR),
        "stages_executed": ["6B.1", "6B.2", "6B.3", "6B.4", "6B.5-style validation"],
        "counts": structural,
        "phase3_alignment": without_rows(alignment),
        "ae_mapping_alignment": without_rows(mapping_alignment),
        "leakage_audit": leakage,
        "deterministic_rebuild_audit": determinism,
        "hash_manifest": hash_manifest,
        "REAL_PHASE6B_READY": readiness["REAL_PHASE6B_READY"],
        "PRODUCTION_INFERENCE_READY": readiness["PRODUCTION_INFERENCE_READY"],
        "failed_checks": readiness["failed_checks"],
        "production_inference_blocker": readiness["production_inference_blocker"],
        "final_artifacts": {name: repo_rel(OUTPUT_DIR / name) for name in FINAL_COPIES},
        "alignment_join_note": "Phase 6B prediction_example_id values map one-to-one to Phase 3 prediction_example_id values through phase3_target_alignment_report.csv.",
    }


def write_markdown_report(path: Path, manifest: dict[str, Any]) -> None:
    counts = manifest["counts"]
    lines = [
        "# Phase 6G.1 Real Phase 6B Dataset Freeze",
        "",
        "Scope: final real Phase 6B data generation only. No LLM calls, prompt rendering, statistical refits, model-performance calculations, or prompt-specification changes were performed.",
        "",
        "## Locked Input",
        "",
        f"- Path: `{manifest['locked_dataset_path']}`",
        f"- Sheet: `{manifest['locked_dataset_sheet']}`",
        f"- SHA-256: `{manifest['locked_dataset_sha256']}`",
        "",
        "## Counts",
        "",
        f"- Participants: `{counts['participant_count']}`",
        f"- Candidate rows: `{counts['candidate_row_count']}`",
        f"- Trials: `{counts['trial_count']}`",
        f"- Target-eligible trials: `{counts['target_eligible_trial_count']}`",
        f"- Target-ineligible trials: `{counts['target_ineligible_trial_count']}`",
        f"- Prediction examples: `{counts['prediction_example_count']}`",
        f"- Non-history objects: `{counts['non_history_object_count']}`",
        f"- Personalised-history objects: `{counts['personalised_history_object_count']}`",
        f"- Prompt-data objects: `{counts['condition_object_count']}`",
        "",
        "## Alignment And Audits",
        "",
        f"- Phase 3 aligned targets: `{manifest['phase3_alignment']['aligned_target_count']}` / `{manifest['phase3_alignment']['phase3_target_count']}`",
        f"- A-E candidate mapping: `{'PASS' if manifest['ae_mapping_alignment']['passed'] else 'FAIL'}`",
        f"- Leakage audit: `{'PASS' if manifest['leakage_audit']['passed'] else 'FAIL'}`",
        f"- Deterministic rebuild: `{'PASS' if manifest['deterministic_rebuild_audit']['passed'] else 'FAIL'}`",
        "",
        "## Readiness",
        "",
        f"- `REAL_PHASE6B_READY`: `{str(manifest['REAL_PHASE6B_READY']).lower()}`",
        f"- `PRODUCTION_INFERENCE_READY`: `{str(manifest['PRODUCTION_INFERENCE_READY']).lower()}`",
        f"- Blocker: {manifest['production_inference_blocker']}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def copy_final_artifacts(run: dict[str, Any], output_dir: Path) -> None:
    for target_name, source_key in FINAL_COPIES.items():
        shutil.copyfile(run["paths"][source_key], output_dir / target_name)


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def numbers_equal(left: Any, right: Any) -> bool:
    try:
        return float(left) == float(right)
    except (TypeError, ValueError):
        return str(left) == str(right)


def without_rows(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key not in {"rows", "columns"}}


def repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
