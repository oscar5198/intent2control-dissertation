import csv
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.data.integration import (  # noqa: E402
    EXPECTED_STRUCTURAL_COUNTS,
    READY_GATE_NAME,
    run_phase6b_synthetic_pipeline,
)


def run_pipeline(tmp_path):
    return run_phase6b_synthetic_pipeline(REPO_ROOT, output_dir=tmp_path / "phase6b5")


def test_phase6b5_runner_executes_all_stages_and_freezes_expected_counts(tmp_path):
    report = run_pipeline(tmp_path)
    assert report["stages_executed"] == ["6B.1", "6B.2", "6B.3", "6B.4"]
    assert report["observed_structural_counts"] == EXPECTED_STRUCTURAL_COUNTS
    assert report["phase6b_complete"] is True
    assert report[READY_GATE_NAME]["ready"] is True


def test_phase6b5_integration_fixture_contains_controlled_ties_and_missing_comment(tmp_path):
    report = run_pipeline(tmp_path)
    fixture_path = REPO_ROOT / report["synthetic_fixture"]
    with fixture_path.open("r", encoding="utf-8-sig", newline="") as handle:
        p1 = next(row for row in csv.DictReader(handle) if row["study_id"] == "SYNTHETIC_PHASE6B1_P001")
    responses = json.loads(p1["responses_json"])
    trial1 = {row["display_label"]: row["rating"] for row in responses if row["trial_index"] == 1}
    trial2 = {row["display_label"]: row["rating"] for row in responses if row["trial_index"] == 2}
    trial4_comments = {row["comparative_comment"] for row in responses if row["trial_index"] == 4}
    assert trial1["D"] == trial1["E"] == 43
    assert trial2["C"] == trial2["D"] == 44
    assert trial2["E"] == 46
    assert trial4_comments == {""}


def test_phase6b5_audits_pass_for_leakage_provenance_equivalence_and_determinism(tmp_path):
    report = run_pipeline(tmp_path)
    audits = report["audits"]
    assert audits["leakage"]["passed"] is True
    assert audits["provenance_leakage"]["passed"] is True
    assert audits["condition_equivalence"]["passed"] is True
    assert audits["determinism"]["passed"] is True
    assert audits["hidden_ground_truth_separation"]["passed"] is True


def test_phase6b5_identifier_acoustic_metadata_and_context_audits_pass(tmp_path):
    report = run_pipeline(tmp_path)
    audits = report["audits"]
    assert audits["identifier_integrity"]["passed"] is True
    assert audits["history_rotation"]["passed"] is True
    assert audits["acoustic_mapping"]["passed"] is True
    assert audits["metadata"]["passed"] is True
    assert audits["context"]["passed"] is True


def test_phase6b5_final_prompt_data_contains_no_hidden_answers_or_provenance(tmp_path):
    report = run_pipeline(tmp_path)
    prompt_path = tmp_path / "phase6b5" / "final_prompt_data_objects.jsonl"
    model_payload = ""
    with prompt_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            model_payload += json.dumps(json.loads(line)["model_input"], sort_keys=True)
    forbidden = [
        "ground_truth",
        "observed_preferred_set",
        "observed_preferred_mix",
        "observed_rank",
        "stimulus_id",
        "actual_mix_id",
        "audio_path",
        "z_SI",
        ".wav",
    ]
    assert not any(token in model_payload for token in forbidden)
    assert report["audits"]["hidden_ground_truth_separation"]["checks"]["authoritative_scoring_source"] == "phase6b3_prediction_examples_jsonl"


def test_phase6b5_writes_machine_and_human_readable_reports(tmp_path):
    run_pipeline(tmp_path)
    output_dir = tmp_path / "phase6b5"
    assert (output_dir / "phase6b_integration_audit.json").exists()
    assert (output_dir / "expected_structural_counts.json").exists()
    assert (output_dir / "leakage_audit.json").exists()
    assert (output_dir / "determinism_report.json").exists()
    report_md = output_dir / "phase6b_validation_report.md"
    assert report_md.exists()
    assert "not dissertation experiment results" in report_md.read_text(encoding="utf-8")
