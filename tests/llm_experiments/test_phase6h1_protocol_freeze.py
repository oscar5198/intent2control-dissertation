from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.evaluation import phase6h1_protocol_freeze as phase6h1  # noqa: E402


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_tmp(tmp_path: Path) -> dict:
    return phase6h1.build_phase6h1_protocol_freeze(REPO_ROOT, output_dir=tmp_path / "phase6h1")


def test_ground_truth_reconstruction_and_candidate_mapping() -> None:
    examples = phase6h1.read_jsonl(REPO_ROOT / phase6h1.PREDICTION_EXAMPLES)
    prompt_objects = phase6h1.read_jsonl(REPO_ROOT / phase6h1.PROMPT_DATA_OBJECTS)
    rows = phase6h1.build_ground_truth_rows(examples, prompt_objects)

    assert len(rows) == 396
    assert len({row["paired_example_id"] for row in rows}) == 198
    assert all(sorted(row["candidate_mapping"]) == list(phase6h1.LABELS) for row in rows)
    first = next(row for row in rows if row["canonical_request_key"] == "P001__heldout__P001__trial_01__non_history__phase6d_prompt_spec_v1")
    assert first["actual_rating_A"] == 19
    assert first["actual_rating_E"] == 53
    assert first["candidate_mapping"]["E"]["stimulus_id"] == "lead_me_pxl_l4"


def test_actual_winner_tie_detection_and_average_ranks() -> None:
    assert phase6h1.rank_with_ties({"A": 100, "B": 100, "C": 50, "D": 25, "E": 25}) == {
        "A": 1.5,
        "B": 1.5,
        "C": 3.0,
        "D": 4.5,
        "E": 4.5,
    }
    result = build_tmp(Path("build_tmp_phase6h1"))
    try:
        tie_policy = result["tie_policy"]
        assert tie_policy["unique_highest_rated_mix_trials"] == 182
        assert tie_policy["top_rating_tie_trials"] == 16
        assert tie_policy["non_top_rating_tie_trials"] == 12
        assert tie_policy["top1_policy"] == "set_based_credit_for_top_ties"
    finally:
        shutil.rmtree(REPO_ROOT / "build_tmp_phase6h1", ignore_errors=True)


def test_joined_predictions_have_expected_shape_and_preserve_prediction_hashes(tmp_path: Path) -> None:
    result = build_tmp(tmp_path)
    joined = result["joined"]
    manifest = result["freeze_manifest"]
    g5_manifest = load_json(REPO_ROOT / phase6h1.PHASE6G5_FREEZE)

    assert len(joined) == 1584
    assert result["qc"]["rows_per_model"] == {model: 396 for model in phase6h1.MODELS}
    assert result["qc"]["duplicate_model_request_keys"] == 0
    assert result["qc"]["prediction_hashes_preserved"] is True
    assert manifest["phase6g5_prediction_hashes"]["final_jsonl_hash"] == g5_manifest["final_jsonl_hash"]
    assert manifest["final_metrics_computed"] is False


def test_personalisation_pairing_is_exact(tmp_path: Path) -> None:
    result = build_tmp(tmp_path)
    pairs = result["pair_manifest"]

    assert pairs["underlying_heldout_examples"] == 198
    assert pairs["request_condition_targets"] == 396
    assert pairs["PERSONALISATION_PAIRING_VALID"] is True
    assert pairs["failures"] == []
    assert all(pair["conditions"] == ["non_history", "personalised_history"] for pair in pairs["pairs"])
    assert all(pair["same_target_human_outcome"] for pair in pairs["pairs"])


def test_metric_applicability_and_centaur_rating_exclusion(tmp_path: Path) -> None:
    result = build_tmp(tmp_path)
    protocol = result["metric_protocol"]
    centaur_rows = [row for row in result["joined"] if row["model_key"] == "centaur"]

    assert protocol["primary_prediction_metric"]["name"] == "preferred_mix_top1_accuracy"
    assert protocol["primary_prediction_metric"]["chance_level"] == 0.20
    assert protocol["rating_prediction_metrics"]["excluded_models"]["centaur"]
    assert all(row["predicted_ratings_supported"] is False for row in centaur_rows)
    assert all(row["predicted_ratings"] is None for row in centaur_rows)


def test_mixed_effects_fairness_audit_uses_final_n33_baseline(tmp_path: Path) -> None:
    result = build_tmp(tmp_path)
    audit = result["fairness_audit"]

    assert audit["training_test_alignment"]["llm_frozen_underlying_examples"] == 198
    assert audit["training_test_alignment"]["existing_heldout_baseline_underlying_examples"] == 198
    assert audit["same_heldout_examples_as_llm"] is True
    assert audit["mixed_effects_refit_required_before_final_comparison"] is False
    assert audit["information_alignment"]["information_parity_claimed"] is False


def test_no_target_leakage_and_no_final_metrics(tmp_path: Path) -> None:
    result = build_tmp(tmp_path)
    qc = result["qc"]
    manifest = result["freeze_manifest"]

    assert qc["no_target_leakage_in_inference_artifacts"] is True
    assert qc["final_metrics_computed"] is False
    assert manifest["ground_truth_join_performed"] is True
    assert manifest["evaluation_protocol_frozen"] is True
    forbidden = {"top1_correct", "accuracy", "mae", "rmse", "spearman"}
    assert not any(forbidden & set(row) for row in result["joined"])


def test_phase6h1_build_is_reproducible(tmp_path: Path) -> None:
    out = tmp_path / "phase6h1"
    first = phase6h1.build_phase6h1_protocol_freeze(REPO_ROOT, output_dir=out)
    first_manifest = first["freeze_manifest"]
    second = phase6h1.build_phase6h1_protocol_freeze(REPO_ROOT, output_dir=out)
    second_manifest = second["freeze_manifest"]

    assert second_manifest["created_at_utc"] == first_manifest["created_at_utc"]
    assert second_manifest["artifact_hashes"] == first_manifest["artifact_hashes"]
    assert second_manifest["source_hashes"] == first_manifest["source_hashes"]
    assert second_manifest["gates"] == first_manifest["gates"]


def test_output_files_are_written_with_frozen_protocol_gates(tmp_path: Path) -> None:
    result = build_tmp(tmp_path)
    paths = {key: REPO_ROOT / value for key, value in result["paths"].items()}

    for path in paths.values():
        assert path.exists(), path
    ground_truth = load_jsonl(paths["ground_truth_jsonl"])
    joined = load_jsonl(paths["joined_jsonl"])
    manifest = load_json(paths["freeze_manifest"])
    assert len(ground_truth) == 396
    assert len(joined) == 1584
    assert all(manifest["gates"].values())
