"""Phase 6B.5 synthetic end-to-end integration runner and audits."""

from __future__ import annotations

import argparse
import csv
import filecmp
import json
import shutil
from pathlib import Path
from typing import Any

from .examples import write_prediction_example_outputs
from .processing import (
    CANONICAL_COLUMNS,
    EXPECTED_LABELS,
    PARTICIPANT_METADATA_FIELDS,
    build_analysis_ready_dataset,
    write_analysis_ready_outputs,
    write_csv,
    write_json,
)
from .prompt_data import (
    PRIMARY_ACOUSTIC_FEATURES,
    build_condition_objects_from_jsonl,
    load_prediction_examples_jsonl,
    validate_condition_pair,
    validate_prompt_data_no_leakage,
    write_prompt_data_outputs,
)
from .targets import build_preference_targets_from_csv, boolish, write_preference_target_outputs


READY_GATE_NAME = "READY_FOR_LLM_INFERENCE"
INTEGRATION_SCHEMA_VERSION = "phase6b5_synthetic_integration_v1"
DEFAULT_SOURCE_FIXTURE = Path("llm-experiments/fixtures/synthetic/phase6b1_five_mix_netlify_export.csv")
DEFAULT_STIMULI = Path("study-interface/frontend-5mix/config/stimuli.json")
DEFAULT_FEATURES = Path("statistical-baseline/outputs/feature_exploration/final_20_stimulus_feature_table.csv")
DEFAULT_OUTPUT_DIR = Path("llm-experiments/outputs/synthetic/phase6b5")

EXPECTED_STRUCTURAL_COUNTS = {
    "participant_count": 2,
    "trial_count": 12,
    "analysis_ready_candidate_rows": 59,
    "complete_participant_candidate_rows": 30,
    "complete_trial_count": 10,
    "incomplete_or_malformed_trial_count": 2,
    "target_eligible_trial_count": 11,
    "target_ineligible_trial_count": 1,
    "history_eligible_trial_count": 11,
    "prediction_example_count": 11,
    "non_history_object_count": 11,
    "personalised_history_object_count": 11,
    "condition_object_count": 22,
    "examples_lacking_personalised_history": 0,
}


def run_phase6b_synthetic_pipeline(
    repo_root: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    source_fixture: Path = DEFAULT_SOURCE_FIXTURE,
    stimulus_config: Path = DEFAULT_STIMULI,
    feature_table: Path = DEFAULT_FEATURES,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    output_dir = resolve_repo_path(repo_root, output_dir)
    source_fixture = resolve_repo_path(repo_root, source_fixture)
    stimulus_config = resolve_repo_path(repo_root, stimulus_config)
    feature_table = resolve_repo_path(repo_root, feature_table)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fixture_path = output_dir / "phase6b5_integration_synthetic_raw_export.csv"
    prepare_integration_fixture(source_fixture, fixture_path)

    first_run_dir = output_dir / "run_1"
    second_run_dir = output_dir / "run_2"
    first = run_pipeline_once(fixture_path, stimulus_config, feature_table, first_run_dir)
    second = run_pipeline_once(fixture_path, stimulus_config, feature_table, second_run_dir)

    audits = run_all_audits(first, stimulus_config)
    determinism = build_determinism_report(first, second)
    audits["determinism"] = determinism
    gate = build_ready_gate(audits)

    report = {
        "schema_version": INTEGRATION_SCHEMA_VERSION,
        "synthetic_fixture": repo_relative(repo_root, fixture_path),
        "source_fixture": repo_relative(repo_root, source_fixture),
        "stages_executed": ["6B.1", "6B.2", "6B.3", "6B.4"],
        "expected_structural_counts": EXPECTED_STRUCTURAL_COUNTS,
        "observed_structural_counts": audits["structural_counts"]["observed"],
        "audits": audits,
        READY_GATE_NAME: gate,
        "contains_real_participant_data": False,
        "contains_llm_prompts": False,
        "contains_llm_predictions": False,
        "contains_model_performance": False,
        "phase6b_complete": bool(gate["ready"]),
    }
    write_json(output_dir / "phase6b_integration_audit.json", report)
    write_json(output_dir / "expected_structural_counts.json", EXPECTED_STRUCTURAL_COUNTS)
    write_json(output_dir / "leakage_audit.json", audits["leakage"])
    write_json(output_dir / "determinism_report.json", determinism)
    write_validation_report(output_dir / "phase6b_validation_report.md", report)
    copy_final_artifacts(first, output_dir)
    return report


def prepare_integration_fixture(source_fixture: Path, output_fixture: Path) -> Path:
    with source_fixture.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    for row in rows:
        participant_id = row["study_id"]
        responses = json.loads(row["responses_json"])
        records = json.loads(row["trial_records_json"])
        if participant_id == "SYNTHETIC_PHASE6B1_P001":
            mutate_trial_ratings(responses, trial_index=1, ratings_by_label={"D": 43, "E": 43})
            mutate_trial_ratings(records_to_responses(records), trial_index=1, ratings_by_label={"D": 43, "E": 43})
            mutate_trial_ratings(responses, trial_index=2, ratings_by_label={"C": 44, "D": 44, "E": 46})
            mutate_trial_ratings(records_to_responses(records), trial_index=2, ratings_by_label={"C": 44, "D": 44, "E": 46})
            mutate_trial_comment(responses, trial_index=4, comment="")
            mutate_trial_comment(records_to_responses(records), trial_index=4, comment="")
            row["rating_count"] = str(sum(1 for item in responses if item.get("rating") is not None))
            row["comment_count"] = "5"
        row["responses_json"] = json.dumps(responses, separators=(",", ":"), ensure_ascii=False)
        row["trial_records_json"] = json.dumps(records, separators=(",", ":"), ensure_ascii=False)

    write_csv(output_fixture, rows, fieldnames)
    return output_fixture


def records_to_responses(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    response_refs: list[dict[str, Any]] = []
    for record in records:
        response_refs.extend(record.get("version_records", []))
    return response_refs


def mutate_trial_ratings(responses: list[dict[str, Any]], trial_index: int, ratings_by_label: dict[str, int]) -> None:
    for response in responses:
        if int(response.get("trial_index", -1)) == trial_index and response.get("display_label") in ratings_by_label:
            response["rating"] = ratings_by_label[str(response["display_label"])]


def mutate_trial_comment(responses: list[dict[str, Any]], trial_index: int, comment: str) -> None:
    for response in responses:
        if int(response.get("trial_index", -1)) == trial_index:
            response["comparative_comment"] = comment


def run_pipeline_once(
    fixture_path: Path,
    stimulus_config: Path,
    feature_table: Path,
    run_dir: Path,
) -> dict[str, Any]:
    phase6b1_dir = run_dir / "phase6b1"
    phase6b2_dir = run_dir / "phase6b2"
    phase6b3_dir = run_dir / "phase6b3"
    phase6b4_dir = run_dir / "phase6b4"

    analysis_path, issues_path, analysis_summary_path, feature_audit_path = write_analysis_ready_outputs(
        fixture_path,
        stimulus_config,
        feature_table,
        phase6b1_dir,
    )
    candidate_path, trial_path, target_summary_path = write_preference_target_outputs(analysis_path, phase6b2_dir)
    examples_path, example_summary_path, example_sample_path = write_prediction_example_outputs(
        candidate_path,
        trial_path,
        phase6b3_dir,
    )
    prompt_path, prompt_summary_path, prompt_sample_path = write_prompt_data_outputs(examples_path, phase6b4_dir)

    analysis_rows, _, analysis_summary, feature_audit = build_analysis_ready_dataset(fixture_path, stimulus_config, feature_table)
    enriched, trial_targets, target_summary, _ = build_preference_targets_from_csv(analysis_path)
    examples = load_prediction_examples_jsonl(examples_path)
    condition_objects, prompt_summary = build_condition_objects_from_jsonl(examples_path)

    return {
        "run_dir": run_dir,
        "paths": {
            "analysis_ready": analysis_path,
            "analysis_issues": issues_path,
            "analysis_summary": analysis_summary_path,
            "feature_audit": feature_audit_path,
            "candidate_ground_truth": candidate_path,
            "trial_ground_truth": trial_path,
            "target_summary": target_summary_path,
            "prediction_examples": examples_path,
            "prediction_summary": example_summary_path,
            "prediction_sample": example_sample_path,
            "prompt_data": prompt_path,
            "prompt_summary": prompt_summary_path,
            "prompt_sample": prompt_sample_path,
        },
        "analysis_rows": analysis_rows,
        "analysis_summary": analysis_summary,
        "feature_audit": feature_audit,
        "candidate_rows": enriched,
        "trial_targets": trial_targets,
        "target_summary": target_summary,
        "prediction_examples": examples,
        "condition_objects": condition_objects,
        "prompt_summary": prompt_summary,
    }


def run_all_audits(run: dict[str, Any], stimulus_config: Path) -> dict[str, Any]:
    return {
        "structural_counts": audit_structural_counts(run),
        "phase6b1": audit_phase6b1(run),
        "phase6b2": audit_phase6b2(run),
        "phase6b3": audit_phase6b3(run),
        "phase6b4": audit_phase6b4(run),
        "leakage": audit_leakage(run),
        "provenance_leakage": audit_provenance_leakage(run),
        "condition_equivalence": audit_condition_equivalence(run),
        "schema": audit_schema(run),
        "identifier_integrity": audit_identifier_integrity(run),
        "history_rotation": audit_history_rotation(run),
        "acoustic_mapping": audit_acoustic_mapping(run),
        "metadata": audit_metadata(run),
        "context": audit_context(run, stimulus_config),
        "hidden_ground_truth_separation": audit_hidden_ground_truth_separation(run),
    }


def audit_structural_counts(run: dict[str, Any]) -> dict[str, Any]:
    rows = run["analysis_rows"]
    trial_targets = run["trial_targets"]
    examples = run["prediction_examples"]
    objects = run["condition_objects"]
    observed = {
        "participant_count": len({row["participant_id"] for row in rows}),
        "trial_count": len({row["trial_id"] for row in rows}),
        "analysis_ready_candidate_rows": len(rows),
        "complete_participant_candidate_rows": sum(1 for row in rows if row["participant_id"] == "SYNTHETIC_PHASE6B1_P001"),
        "complete_trial_count": run["analysis_summary"]["complete_trial_count"],
        "incomplete_or_malformed_trial_count": run["analysis_summary"]["incomplete_or_malformed_trial_count"],
        "target_eligible_trial_count": sum(1 for target in trial_targets if boolish(target["target_eligible"])),
        "target_ineligible_trial_count": sum(1 for target in trial_targets if not boolish(target["target_eligible"])),
        "history_eligible_trial_count": sum(1 for target in trial_targets if boolish(target["history_eligible"])),
        "prediction_example_count": len(examples),
        "non_history_object_count": sum(1 for obj in objects if obj["condition"] == "non_history"),
        "personalised_history_object_count": sum(1 for obj in objects if obj["condition"] == "personalised_history"),
        "condition_object_count": len(objects),
        "examples_lacking_personalised_history": sum(1 for example in examples if not example["personalised_history_available"]),
    }
    return {"passed": observed == EXPECTED_STRUCTURAL_COUNTS, "expected": EXPECTED_STRUCTURAL_COUNTS, "observed": observed}


def audit_phase6b1(run: dict[str, Any]) -> dict[str, Any]:
    rows = run["analysis_rows"]
    p1_rows = [row for row in rows if row["participant_id"] == "SYNTHETIC_PHASE6B1_P001"]
    trial_groups = group_by(rows, "trial_id")
    checks = {
        "one_row_per_candidate": all(row["presentation_label"] in EXPECTED_LABELS for row in rows),
        "complete_participant_has_30_rows": len(p1_rows) == 30,
        "complete_trials_have_five_rows": all(len(group) == 5 for group in trial_groups.values() if group[0]["trial_validation_status"] == "complete"),
        "ratings_attached_to_labels": rating_by_label(rows, "SYNTHETIC_PHASE6B1_P001__trial_01")["D"] == 43,
        "comments_preserved_or_missing_as_fixture_controls": all("SYNTHETIC" in row["comparative_comment"] for row in rows if row["trial_id"] == "SYNTHETIC_PHASE6B1_P001__trial_01"),
        "metadata_mapped": next(row for row in rows if row["participant_id"] == "SYNTHETIC_PHASE6B1_P001")["music_listening_habits"] == "daily",
        "primary_acoustic_features_attached": all(row["z_RMS"] != "" and row["z_CF"] != "" and row["z_SW"] != "" for row in rows),
        "trial_ids_deterministic": "SYNTHETIC_PHASE6B1_P001__trial_01" in trial_groups,
        "malformed_or_incomplete_flagged": run["analysis_summary"]["incomplete_or_malformed_trial_count"] == 2,
    }
    return {"passed": all(checks.values()), "checks": checks}


def audit_phase6b2(run: dict[str, Any]) -> dict[str, Any]:
    targets = {target["trial_id"]: target for target in run["trial_targets"]}
    trial1 = targets["SYNTHETIC_PHASE6B1_P001__trial_01"]
    trial2 = targets["SYNTHETIC_PHASE6B1_P001__trial_02"]
    invalid = targets["SYNTHETIC_PHASE6B1_P002__trial_06"]
    checks = {
        "eligible_trials_have_ground_truth": bool(trial1["observed_preferred_set"]),
        "ineligible_trial_has_no_fabricated_target": invalid["target_eligible"] is False and invalid["observed_preferred_set"] == "",
        "maximum_tie_retained": json.loads(trial1["observed_preferred_set"]) == ["D", "E"],
        "no_arbitrary_tie_breaking": trial1["observed_preferred_mix"] == "",
        "non_maximum_tie_ranked_with_average_rank": trial2["observed_rank_C"] == "2.5" and trial2["observed_rank_D"] == "2.5",
        "target_history_eligibility_consistent": run["target_summary"]["target_eligible_trial_count"] == run["target_summary"]["history_eligible_trial_count"],
    }
    return {"passed": all(checks.values()), "checks": checks}


def audit_phase6b3(run: dict[str, Any]) -> dict[str, Any]:
    targets = {target["trial_id"]: target for target in run["trial_targets"]}
    checks = {
        "complete_participant_has_six_examples": sum(1 for ex in run["prediction_examples"] if ex["participant_id"] == "SYNTHETIC_PHASE6B1_P001") == 6,
        "ineligible_trial_not_target": all(ex["input_data"]["target"]["trial_id"] != "SYNTHETIC_PHASE6B1_P002__trial_06" for ex in run["prediction_examples"]),
        "targets_are_eligible": all(boolish(targets[ex["input_data"]["target"]["trial_id"]]["target_eligible"]) for ex in run["prediction_examples"]),
        "target_excluded_from_history": all(ex["input_data"]["target"]["trial_id"] not in [trial["trial_id"] for trial in ex["input_data"]["history"]] for ex in run["prediction_examples"]),
        "history_ordered": all([trial["trial_order"] for trial in ex["input_data"]["history"]] == sorted(trial["trial_order"] for trial in ex["input_data"]["history"]) for ex in run["prediction_examples"]),
        "target_candidates_a_to_e": all([candidate["presentation_label"] for candidate in ex["input_data"]["target"]["candidates"]] == EXPECTED_LABELS for ex in run["prediction_examples"]),
        "ground_truth_complete": all(set(ex["ground_truth"]) >= {"human_ratings", "observed_ranks", "observed_preferred_set"} for ex in run["prediction_examples"]),
    }
    return {"passed": all(checks.values()), "checks": checks}


def audit_phase6b4(run: dict[str, Any]) -> dict[str, Any]:
    objects = run["condition_objects"]
    checks = {
        "non_history_has_no_history": all("history" not in obj["model_input"] for obj in objects if obj["condition"] == "non_history"),
        "personalised_history_has_history": all(obj["model_input"].get("history") for obj in objects if obj["condition"] == "personalised_history"),
        "target_candidates_a_to_e": all([candidate["label"] for candidate in obj["model_input"]["target"]["candidates"]] == EXPECTED_LABELS for obj in objects),
        "target_uses_primary_features": all(set(candidate["acoustic_features"]) == set(PRIMARY_ACOUSTIC_FEATURES) for obj in objects for candidate in obj["model_input"]["target"]["candidates"]),
    }
    return {"passed": all(checks.values()), "checks": checks}


def audit_leakage(run: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    example_by_id = {example["prediction_example_id"]: example for example in run["prediction_examples"]}
    for obj in run["condition_objects"]:
        try:
            validate_prompt_data_no_leakage(obj)
        except ValueError as exc:
            failures.append(f"{obj.get('condition_object_id')}: {exc}")
        target_comment = target_comment_for_example(example_by_id[obj["prediction_example_id"]])
        model_input_text = json.dumps(obj["model_input"], sort_keys=True, ensure_ascii=False)
        if target_comment and target_comment in model_input_text:
            failures.append(f"{obj['condition_object_id']}: target comparative comment leaked")
        forbidden = ["observed_rank", "observed_preferred_set", "observed_preferred_mix", "observed_max_rating", "is_single_winner", "n_preferred_tied"]
        if any(token in model_input_text for token in forbidden):
            failures.append(f"{obj['condition_object_id']}: target outcome token leaked")
    return {"passed": not failures, "failure_count": len(failures), "failures": failures}


def audit_provenance_leakage(run: dict[str, Any]) -> dict[str, Any]:
    forbidden = ["stimulus_id", "actual_mix_id", "audio_path", "acoustic_feature_table_used", ".wav", "mix_", "_du_", "_mcg_", "_pxl_", "_qut_"]
    failures = []
    for obj in run["condition_objects"]:
        payload = json.dumps(obj["model_input"], sort_keys=True, ensure_ascii=False)
        leaked = [token for token in forbidden if token in payload]
        if leaked:
            failures.append({"condition_object_id": obj["condition_object_id"], "tokens": leaked})
    return {"passed": not failures, "failure_count": len(failures), "failures": failures}


def audit_condition_equivalence(run: dict[str, Any]) -> dict[str, Any]:
    failures = []
    for pair in pairs_by_example(run["condition_objects"]).values():
        if {"non_history", "personalised_history"} <= set(pair):
            try:
                validate_condition_pair(pair["non_history"], pair["personalised_history"])
            except ValueError as exc:
                failures.append(str(exc))
    return {"passed": not failures, "paired_condition_count": len(pairs_by_example(run["condition_objects"])), "failures": failures}


def audit_schema(run: dict[str, Any]) -> dict[str, Any]:
    failures = []
    for row in run["analysis_rows"]:
        missing = [field for field in CANONICAL_COLUMNS if field not in row]
        if missing:
            failures.append(f"analysis row missing {missing}")
        if row["presentation_label"] not in EXPECTED_LABELS:
            failures.append("invalid presentation label")
    for target in run["trial_targets"]:
        if target["target_eligible"] and not target["observed_preferred_set"]:
            failures.append(f"eligible target missing preferred set: {target['trial_id']}")
    for example in run["prediction_examples"]:
        if len(example["input_data"]["target"]["candidates"]) != 5:
            failures.append(f"prediction example target not five candidates: {example['prediction_example_id']}")
    for obj in run["condition_objects"]:
        if obj["condition"] not in {"non_history", "personalised_history"}:
            failures.append(f"invalid condition: {obj['condition']}")
    return {"passed": not failures, "failure_count": len(failures), "failures": failures[:20]}


def audit_identifier_integrity(run: dict[str, Any]) -> dict[str, Any]:
    condition_ids = [obj["condition_object_id"] for obj in run["condition_objects"]]
    prediction_ids = [ex["prediction_example_id"] for ex in run["prediction_examples"]]
    ground_truth_trial_ids = {target["trial_id"] for target in run["trial_targets"] if boolish(target["target_eligible"])}
    failures = []
    if len(condition_ids) != len(set(condition_ids)):
        failures.append("duplicate condition_object_id")
    if len(prediction_ids) != len(set(prediction_ids)):
        failures.append("duplicate prediction_example_id")
    prediction_set = set(prediction_ids)
    for obj in run["condition_objects"]:
        if obj["prediction_example_id"] not in prediction_set:
            failures.append(f"condition lacks valid prediction link: {obj['condition_object_id']}")
    for example in run["prediction_examples"]:
        if example["ground_truth"]["target_trial_id"] not in ground_truth_trial_ids:
            failures.append(f"prediction lacks hidden target link: {example['prediction_example_id']}")
    return {"passed": not failures, "failure_count": len(failures), "failures": failures}


def audit_history_rotation(run: dict[str, Any]) -> dict[str, Any]:
    examples = {ex["input_data"]["target"]["trial_id"]: ex for ex in run["prediction_examples"]}
    target_trial = examples["SYNTHETIC_PHASE6B1_P001__trial_02"]
    other_target = examples["SYNTHETIC_PHASE6B1_P001__trial_01"]
    other_history_ids = [trial["trial_id"] for trial in other_target["input_data"]["history"]]
    target_input_text = json.dumps(target_trial["input_data"]["target"], sort_keys=True)
    checks = {
        "trial_02_can_be_history_for_trial_01": "SYNTHETIC_PHASE6B1_P001__trial_02" in other_history_ids,
        "trial_02_ratings_absent_when_trial_02_is_target": "human_rating" not in target_input_text,
        "trial_02_comment_absent_when_trial_02_is_target": "SYNTHETIC TEST COMMENT SYNTHETIC_PHASE6B1_P001 trial 2." not in json.dumps(target_trial["input_data"], sort_keys=True),
    }
    return {"passed": all(checks.values()), "checks": checks}


def audit_acoustic_mapping(run: dict[str, Any]) -> dict[str, Any]:
    rows_by_trial_label = {(row["trial_id"], row["presentation_label"]): row for row in run["analysis_rows"]}
    failures = []
    for example in run["prediction_examples"]:
        target_id = example["input_data"]["target"]["trial_id"]
        prompt_pair = pairs_by_example(run["condition_objects"])[example["prediction_example_id"]]["non_history"]
        for candidate in prompt_pair["model_input"]["target"]["candidates"]:
            source = rows_by_trial_label[(target_id, candidate["label"])]
            expected = {field: round(float(source[field]), 4) for field in PRIMARY_ACOUSTIC_FEATURES}
            if candidate["acoustic_features"] != expected:
                failures.append(f"feature mismatch {target_id} {candidate['label']}")
            if "z_SI" in candidate["acoustic_features"]:
                failures.append(f"z_SI leaked {target_id} {candidate['label']}")
    return {"passed": not failures, "failure_count": len(failures), "failures": failures[:20]}


def audit_metadata(run: dict[str, Any]) -> dict[str, Any]:
    failures = []
    for pair in pairs_by_example(run["condition_objects"]).values():
        for obj in pair.values():
            metadata = obj["model_input"]["participant_metadata"]
            if set(metadata) != set(PARTICIPANT_METADATA_FIELDS):
                failures.append(f"metadata fields mismatch {obj['condition_object_id']}")
        if {"non_history", "personalised_history"} <= set(pair):
            if pair["non_history"]["model_input"]["participant_metadata"] != pair["personalised_history"]["model_input"]["participant_metadata"]:
                failures.append("paired metadata mismatch")
    missing_preserved = any(
        obj["model_input"]["participant_metadata"]["hearing_difficulty"] is None
        for obj in run["condition_objects"]
        if obj["prediction_example_id"].startswith("SYNTHETIC_PHASE6B1_P002")
    )
    if not missing_preserved:
        failures.append("missing metadata not preserved")
    return {"passed": not failures, "failure_count": len(failures), "failures": failures}


def audit_context(run: dict[str, Any], stimulus_config: Path) -> dict[str, Any]:
    config = json.loads(stimulus_config.read_text(encoding="utf-8"))
    contexts = {scenario["id"]: scenario["text"] for scenario in config.get("scenarios", [])}
    failures = []
    for pair in pairs_by_example(run["condition_objects"]).values():
        for obj in pair.values():
            context = obj["model_input"]["target"]["context"]
            if context["context_text"] != contexts.get(context["episode_id"]):
                failures.append(f"context text mismatch {obj['condition_object_id']}")
            if "SYNTHETIC TEST COMMENT" in context["context_text"]:
                failures.append(f"comment confused with context {obj['condition_object_id']}")
        if {"non_history", "personalised_history"} <= set(pair):
            if pair["non_history"]["model_input"]["target"]["context"] != pair["personalised_history"]["model_input"]["target"]["context"]:
                failures.append("paired context mismatch")
    return {"passed": not failures, "failure_count": len(failures), "failures": failures}


def audit_hidden_ground_truth_separation(run: dict[str, Any]) -> dict[str, Any]:
    prompt_text = run["paths"]["prompt_data"].read_text(encoding="utf-8")
    prediction_text = run["paths"]["prediction_examples"].read_text(encoding="utf-8")
    checks = {
        "prompt_data_has_no_ground_truth_key": "ground_truth" not in prompt_text,
        "prediction_examples_retain_ground_truth": "ground_truth" in prediction_text,
        "authoritative_scoring_source": "phase6b3_prediction_examples_jsonl",
    }
    return {"passed": checks["prompt_data_has_no_ground_truth_key"] and checks["prediction_examples_retain_ground_truth"], "checks": checks}


def build_determinism_report(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    comparisons = {
        "analysis_ready_csv": same_file(first, second, "analysis_ready"),
        "analysis_issues_csv": same_file(first, second, "analysis_issues"),
        "candidate_ground_truth_csv": same_file(first, second, "candidate_ground_truth"),
        "trial_ground_truth_csv": same_file(first, second, "trial_ground_truth"),
        "prediction_examples_jsonl": same_file(first, second, "prediction_examples"),
        "prompt_data_jsonl": same_file(first, second, "prompt_data"),
        "prediction_example_ids": [ex["prediction_example_id"] for ex in first["prediction_examples"]] == [ex["prediction_example_id"] for ex in second["prediction_examples"]],
        "condition_object_ids": [obj["condition_object_id"] for obj in first["condition_objects"]] == [obj["condition_object_id"] for obj in second["condition_objects"]],
        "structural_counts": audit_structural_counts(first)["observed"] == audit_structural_counts(second)["observed"],
    }
    return {"passed": all(comparisons.values()), "comparisons": comparisons}


def build_ready_gate(audits: dict[str, Any]) -> dict[str, Any]:
    required = [
        "structural_counts",
        "phase6b1",
        "phase6b2",
        "phase6b3",
        "phase6b4",
        "leakage",
        "provenance_leakage",
        "condition_equivalence",
        "schema",
        "identifier_integrity",
        "history_rotation",
        "acoustic_mapping",
        "metadata",
        "context",
        "hidden_ground_truth_separation",
        "determinism",
    ]
    failed = [name for name in required if not audits[name]["passed"]]
    return {
        "ready": not failed,
        "failed_checks": failed,
        "note": "Synthetic Phase 6B gate only; does not authorize LLM inference on real data without final export validation.",
    }


def copy_final_artifacts(run: dict[str, Any], output_dir: Path) -> None:
    copies = {
        "final_analysis_ready_long.csv": run["paths"]["analysis_ready"],
        "final_candidate_ground_truth_enriched.csv": run["paths"]["candidate_ground_truth"],
        "final_trial_ground_truth_targets.csv": run["paths"]["trial_ground_truth"],
        "final_prediction_examples.jsonl": run["paths"]["prediction_examples"],
        "final_prompt_data_objects.jsonl": run["paths"]["prompt_data"],
    }
    for name, source in copies.items():
        shutil.copyfile(source, output_dir / name)


def write_validation_report(path: Path, report: dict[str, Any]) -> None:
    counts = report["observed_structural_counts"]
    gate = report[READY_GATE_NAME]
    lines = [
        "# Phase 6B Synthetic Validation Report",
        "",
        "These are synthetic structural validation results only. They are not dissertation experiment results.",
        "",
        "## Purpose",
        "",
        "Validate the Phase 6B data pipeline from synthetic raw export structure through final model-facing prompt-data objects without LLM calls.",
        "",
        "## Fixture",
        "",
        f"- Synthetic integration fixture: `{report['synthetic_fixture']}`",
        f"- Source fixture: `{report['source_fixture']}`",
        "",
        "## Stages Executed",
        "",
        "- 6B.1 raw export to analysis-ready long data",
        "- 6B.2 hidden human preference targets",
        "- 6B.3 leave-one-trial-out prediction examples",
        "- 6B.4 condition-specific structured prompt-data objects",
        "",
        "## Structural Counts",
        "",
        f"- Participants: {counts['participant_count']}",
        f"- Candidate rows: {counts['analysis_ready_candidate_rows']}",
        f"- Trials: {counts['trial_count']}",
        f"- Complete trials: {counts['complete_trial_count']}",
        f"- Incomplete/malformed trials: {counts['incomplete_or_malformed_trial_count']}",
        f"- Target-eligible trials: {counts['target_eligible_trial_count']}",
        f"- Prediction examples: {counts['prediction_example_count']}",
        f"- Non-history objects: {counts['non_history_object_count']}",
        f"- Personalised-history objects: {counts['personalised_history_object_count']}",
        "",
        "## Audit Results",
        "",
    ]
    for name, audit in report["audits"].items():
        lines.append(f"- {name}: {'PASS' if audit['passed'] else 'FAIL'}")
    lines.extend(
        [
            "",
            "## Pre-LLM Gate",
            "",
            f"- `{READY_GATE_NAME}`: {'true' if gate['ready'] else 'false'}",
            f"- Failed checks: {', '.join(gate['failed_checks']) if gate['failed_checks'] else 'none'}",
            "",
            "## Conclusion",
            "",
            "Phase 6B can be marked COMPLETE for the synthetic pipeline." if gate["ready"] else "Phase 6B is blocked by failed synthetic validation checks.",
            "",
            "The future real-data pathway must run the same staged pipeline on the final complete raw export only, write outputs to a non-committed real-data location, and pass this validation gate before any LLM inference begins.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def same_file(first: dict[str, Any], second: dict[str, Any], key: str) -> bool:
    return filecmp.cmp(first["paths"][key], second["paths"][key], shallow=False)


def group_by(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row[key]), []).append(row)
    return grouped


def rating_by_label(rows: list[dict[str, Any]], trial_id: str) -> dict[str, Any]:
    return {row["presentation_label"]: row["human_rating"] for row in rows if row["trial_id"] == trial_id}


def target_comment_for_example(example: dict[str, Any]) -> str | None:
    target_id = example["input_data"]["target"]["trial_id"]
    for trial in example["input_data"]["history"]:
        if trial["trial_id"] == target_id:
            return trial.get("comparative_comment")
    # The target comment is not stored in 6B.3 input_data by design. Synthetic
    # comments follow this deterministic pattern, so this is only an audit probe.
    participant = example["participant_id"]
    order = example["input_data"]["target"]["trial_order"]
    return f"SYNTHETIC TEST COMMENT {participant} trial {order}."


def pairs_by_example(objects: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    pairs: dict[str, dict[str, dict[str, Any]]] = {}
    for obj in objects:
        pairs.setdefault(obj["prediction_example_id"], {})[obj["condition"]] = obj
    return pairs


def resolve_repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def repo_relative(repo_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 6B.5 synthetic end-to-end integration validation.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Synthetic integration output directory.")
    parser.add_argument("--source-fixture", type=Path, default=DEFAULT_SOURCE_FIXTURE, help="Base synthetic raw export fixture.")
    parser.add_argument("--stimuli", type=Path, default=DEFAULT_STIMULI, help="Active five-mix stimuli config.")
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES, help="Canonical final-20 acoustic feature table.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path.cwd()
    report = run_phase6b_synthetic_pipeline(
        repo_root=repo_root,
        output_dir=args.output_dir,
        source_fixture=args.source_fixture,
        stimulus_config=args.stimuli,
        feature_table=args.features,
    )
    print(f"Wrote Phase 6B synthetic integration outputs to {args.output_dir}")
    print(f"{READY_GATE_NAME}={str(report[READY_GATE_NAME]['ready']).lower()}")
    if not report[READY_GATE_NAME]["ready"]:
        print(f"Failed checks: {', '.join(report[READY_GATE_NAME]['failed_checks'])}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
