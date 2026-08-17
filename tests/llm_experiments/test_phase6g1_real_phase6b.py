from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.data.examples import validate_no_target_leakage  # noqa: E402

OUTPUT_DIR = REPO_ROOT / "llm-experiments" / "outputs" / "real" / "phase6b"
MANIFEST_PATH = OUTPUT_DIR / "phase6g1_real_phase6b_manifest.json"
LOCKED_XLSX = REPO_ROOT / "statistical-baseline" / "data" / "real" / "raw" / "listening_preference_responses_33_immutable.xlsx"
LOCKED_SHA256 = "5bab388fbf564e0caf5c1ca8a5a722bf8d517e23c018e48375d076e75dba0bdd"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_locked_source_hash_and_manifest_counts() -> None:
    manifest = load_json(MANIFEST_PATH)
    counts = manifest["counts"]

    assert sha256_file(LOCKED_XLSX) == LOCKED_SHA256
    assert manifest["locked_dataset_sha256"] == LOCKED_SHA256
    assert counts["participant_count"] == 33
    assert counts["candidate_row_count"] == 990
    assert counts["trial_count"] == 198
    assert counts["target_eligible_trial_count"] == 198
    assert counts["target_ineligible_trial_count"] == 0
    assert counts["phase3_target_count"] == 198
    assert counts["prediction_example_count"] == 198
    assert counts["non_history_object_count"] == 198
    assert counts["personalised_history_object_count"] == 198
    assert counts["condition_object_count"] == 396
    assert counts["expected_four_model_primary_inference_count"] == 1584


def test_phase3_alignment_and_ae_mapping_reports_pass() -> None:
    manifest = load_json(MANIFEST_PATH)
    alignment_rows = read_csv(OUTPUT_DIR / "phase3_target_alignment_report.csv")
    mapping_rows = read_csv(OUTPUT_DIR / "ae_mapping_alignment_report.csv")

    assert manifest["phase3_alignment"]["passed"] is True
    assert manifest["phase3_alignment"]["aligned_target_count"] == 198
    assert len(alignment_rows) == 198
    assert all(row["aligned"] == "True" for row in alignment_rows)
    assert len({row["phase6b_prediction_example_id"] for row in alignment_rows}) == 198

    assert manifest["ae_mapping_alignment"]["passed"] is True
    assert manifest["ae_mapping_alignment"]["candidate_alignment_count"] == 990
    assert len(mapping_rows) == 990
    assert all(row["aligned"] == "True" for row in mapping_rows)


def test_prediction_examples_are_unique_and_hide_target_outcomes_from_input() -> None:
    examples = load_jsonl(OUTPUT_DIR / "final_prediction_examples.jsonl")
    example_ids = [example["prediction_example_id"] for example in examples]

    assert len(example_ids) == len(set(example_ids)) == 198
    assert {example["n_history_trials"] for example in examples} == {5}
    for example in examples:
        target = example["input_data"]["target"]
        target_payload = json.dumps(target, sort_keys=True)
        assert target["trial_id"] not in [trial["trial_id"] for trial in example["input_data"]["history"]]
        assert "human_rating" not in target_payload
        assert "comparative_comment" not in target_payload
        assert "ground_truth" not in json.dumps(example["input_data"], sort_keys=True)
        assert set(example["ground_truth"]) >= {"human_ratings", "observed_ranks", "observed_preferred_set"}


def test_prompt_data_model_input_has_no_ground_truth_sensitivity_or_provenance() -> None:
    objects = load_jsonl(OUTPUT_DIR / "final_prompt_data_objects.jsonl")
    forbidden = {"ground_truth", "z_SI", "stimulus_id", "actual_mix_id", "audio_path", "source_study_id"}

    assert len(objects) == 396
    for obj in objects:
        payload = json.dumps(obj["model_input"], sort_keys=True)
        for token in forbidden:
            assert token not in payload
        assert obj["condition"] in {"non_history", "personalised_history"}


def test_paired_conditions_identical_except_history() -> None:
    objects = load_jsonl(OUTPUT_DIR / "final_prompt_data_objects.jsonl")
    by_example: dict[str, dict[str, dict]] = {}
    for obj in objects:
        by_example.setdefault(obj["prediction_example_id"], {})[obj["condition"]] = obj

    assert len(by_example) == 198
    for pair in by_example.values():
        assert set(pair) == {"non_history", "personalised_history"}
        assert pair["non_history"]["model_input"]["participant_metadata"] == pair["personalised_history"]["model_input"]["participant_metadata"]
        assert pair["non_history"]["model_input"]["target"] == pair["personalised_history"]["model_input"]["target"]
        assert "history" not in pair["non_history"]["model_input"]
        assert len(pair["personalised_history"]["model_input"]["history"]) == 5


def test_leakage_determinism_and_readiness_gates_pass() -> None:
    manifest = load_json(MANIFEST_PATH)
    leakage = load_json(OUTPUT_DIR / "leakage_audit.json")
    determinism = load_json(OUTPUT_DIR / "deterministic_rebuild_audit.json")
    readiness = load_json(OUTPUT_DIR / "production_readiness_gate.json")

    assert leakage["passed"] is True
    assert determinism["passed"] is True
    assert readiness["REAL_PHASE6B_READY"] is True
    assert readiness["PRODUCTION_INFERENCE_READY"] is False
    assert manifest["REAL_PHASE6B_READY"] is True
    assert manifest["PRODUCTION_INFERENCE_READY"] is False


def test_repeated_or_trivial_comments_do_not_create_false_target_leakage() -> None:
    example = {
        "input_data": {
            "target": {
                "trial_id": "PTEST__trial_01",
                "candidates": [{"presentation_label": "A"}],
            },
            "history": [
                {
                    "trial_id": "PTEST__trial_02",
                    "comparative_comment": ".",
                    "candidates": [{"presentation_label": "A", "human_rating": 50}],
                }
            ],
        },
        "ground_truth": {
            "human_ratings": {"A": 10},
            "observed_ranks": {"A": 1},
            "observed_preferred_set": ["A"],
            "observed_preferred_mix": "A",
            "is_single_winner": True,
            "n_preferred_tied": 1,
        },
    }
    target_rows = [{"comparative_comment": "."}]

    validate_no_target_leakage(example, target_rows)
