from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.inference import phase6g5_final_predictions as phase6g5  # noqa: E402
from llm_experiments.inference import phase6g4a_gpt_recovery as gpt_recovery  # noqa: E402


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_final_source_selection_points_to_authoritative_phase6g4_artifacts() -> None:
    assert phase6g5.FINAL_SOURCES["gpt"]["prediction_file"].as_posix().endswith("source/gpt-5-5/predictions.jsonl")
    assert phase6g5.FINAL_SOURCES["claude_sonnet"]["prediction_file"].as_posix().endswith("source/claude-sonnet-5/predictions.jsonl")
    assert phase6g5.FINAL_SOURCES["llama_3_1_70b_instruct"]["prediction_file"].as_posix().endswith("source/llama-3-1-70b-instruct/predictions.jsonl")
    assert phase6g5.FINAL_SOURCES["centaur"]["prediction_file"].as_posix().endswith("source/centaur/predictions.jsonl")


def test_source_counts_are_396_each_with_expected_condition_balance() -> None:
    for model_key, source in phase6g5.FINAL_SOURCES.items():
        rows = phase6g5.read_jsonl(REPO_ROOT / source["prediction_file"])
        assert len(rows) == 396, model_key
        counts = {}
        for row in rows:
            counts[row["condition"]] = counts.get(row["condition"], 0) + 1
        assert counts == {"non_history": 198, "personalised_history": 198}


def test_build_outputs_merge_1584_rows_and_detect_current_gpt_unresolved_blocker(tmp_path: Path) -> None:
    result = phase6g5.build_phase6g5_final_predictions(REPO_ROOT, output_dir=tmp_path / "phase6g5")
    qc = result["qc_summary"]

    assert qc["actual_total_rows"] == 1584
    assert qc["model_counts"] == {model: 396 for model in phase6g5.EXPECTED_MODELS}
    assert all(counts == {"non_history": 198, "personalised_history": 198} for counts in qc["condition_counts_by_model"].values())
    assert qc["cross_model_request_alignment"] is True
    assert qc["duplicate_model_canonical_request_key_count"] == 0
    assert qc["GROUND_TRUTH_NOT_LOADED_FOR_PHASE6G5"] is True
    assert qc["evaluation_metrics_computed"] is False
    assert qc["FINAL_LLM_PREDICTIONS_QC_PASSED"] is True
    assert result["freeze_manifest"]["gates"]["FINAL_LLM_PREDICTIONS_FROZEN"] is True
    assert result["freeze_manifest"]["gates"]["FINAL_LLM_PREDICTIONS_MERGED"] is True


def test_builded_prediction_rows_have_valid_capability_flags_except_known_gpt_blocker(tmp_path: Path) -> None:
    result = phase6g5.build_phase6g5_final_predictions(REPO_ROOT, output_dir=tmp_path / "phase6g5")
    rows = load_jsonl(REPO_ROOT / result["paths"]["predictions_jsonl"]) if Path(result["paths"]["predictions_jsonl"]).is_absolute() else load_jsonl(REPO_ROOT / result["paths"]["predictions_jsonl"])
    valid_mixes = set("ABCDE")

    for row in rows:
        assert row["predicted_preferred_mix"] in valid_mixes
        assert sorted(row["predicted_ranking"]) == sorted(valid_mixes)
        if row["model_key"] == "centaur":
            assert row["predicted_ratings_supported"] is False
            assert row["predicted_ratings"] is None
            assert sorted(row["centaur_candidate_log_likelihoods"]) == sorted(valid_mixes)
            assert sorted(row["centaur_candidate_probabilities"]) == sorted(valid_mixes)
            assert abs(sum(row["centaur_candidate_probabilities"].values()) - 1.0) <= phase6g5.PROBABILITY_TOLERANCE
        else:
            assert row["predicted_ratings_supported"] is True
            assert sorted(row["predicted_ratings"]) == sorted(valid_mixes)
            assert all(0 <= value <= 100 for value in row["predicted_ratings"].values())


def test_prompt_hashes_match_phase6g3_manifest_for_all_rows(tmp_path: Path) -> None:
    result = phase6g5.build_phase6g5_final_predictions(REPO_ROOT, output_dir=tmp_path / "phase6g5")
    rows = load_jsonl(REPO_ROOT / result["paths"]["predictions_jsonl"])
    prompt_manifest = load_json(REPO_ROOT / phase6g5.PROMPT_HASH_MANIFEST)
    hashes = {row["rendered_prompt_id"]: row["message_payload_sha256"] for row in prompt_manifest["records"]}

    assert all(row["prompt_hash"] == hashes[row["canonical_request_key"]] for row in rows)


def test_capability_matrix_excludes_centaur_from_rating_error_without_ground_truth(tmp_path: Path) -> None:
    result = phase6g5.build_phase6g5_final_predictions(REPO_ROOT, output_dir=tmp_path / "phase6g5")
    matrix = load_json(REPO_ROOT / result["paths"]["capability_matrix"])

    assert matrix["capabilities"]["centaur"]["winner"] == "supported_native_likelihood"
    assert matrix["capabilities"]["centaur"]["ranking"] == "supported_native_likelihood"
    assert matrix["capabilities"]["centaur"]["rating_0_100"] == "unsupported"
    assert matrix["evaluation_policy"]["rating_error_metrics"] == ["gpt", "claude_sonnet", "llama_3_1_70b_instruct"]
    assert matrix["evaluation_policy"]["ground_truth_consulted_for_capability_decision"] is False


def test_repeated_build_keeps_prediction_and_manifest_hashes_deterministic(tmp_path: Path) -> None:
    out = tmp_path / "phase6g5"
    first = phase6g5.build_phase6g5_final_predictions(REPO_ROOT, output_dir=out)
    first_manifest = first["freeze_manifest"]
    first_hashes = {
        "jsonl": first_manifest["final_jsonl_hash"],
        "csv": first_manifest["final_csv_hash"],
        "capability": first_manifest["capability_matrix_hash"],
        "inventory": first_manifest["inventory_hash"],
        "qc": first_manifest["qc_summary_hash"],
    }
    second = phase6g5.build_phase6g5_final_predictions(REPO_ROOT, output_dir=out)
    second_manifest = second["freeze_manifest"]

    assert second_manifest["created_at_utc"] == first_manifest["created_at_utc"]
    assert {
        "jsonl": second_manifest["final_jsonl_hash"],
        "csv": second_manifest["final_csv_hash"],
        "capability": second_manifest["capability_matrix_hash"],
        "inventory": second_manifest["inventory_hash"],
        "qc": second_manifest["qc_summary_hash"],
    } == first_hashes


def test_historical_artifacts_are_not_modified_by_build(tmp_path: Path) -> None:
    tracked_sources = [REPO_ROOT / source["prediction_file"] for source in phase6g5.FINAL_SOURCES.values()]
    before = {path: phase6g5.sha256_file(path) for path in tracked_sources}

    phase6g5.build_phase6g5_final_predictions(REPO_ROOT, output_dir=tmp_path / "phase6g5")

    assert {path: phase6g5.sha256_file(path) for path in tracked_sources} == before


def test_no_ground_truth_files_are_copied_into_phase6g5_outputs(tmp_path: Path) -> None:
    result = phase6g5.build_phase6g5_final_predictions(REPO_ROOT, output_dir=tmp_path / "phase6g5")
    output_root = REPO_ROOT / result["paths"]["predictions_jsonl"]
    package_dir = output_root.parent
    names = [path.name.lower() for path in package_dir.iterdir()]

    assert all("ground_truth" not in name for name in names)
    assert all("human_outcome" not in name for name in names)


def test_jsonl_can_be_rebuilt_in_clean_copy_without_hidden_inputs(tmp_path: Path) -> None:
    out = tmp_path / "phase6g5"
    result = phase6g5.build_phase6g5_final_predictions(REPO_ROOT, output_dir=out)
    package_dir = REPO_ROOT / result["paths"]["predictions_jsonl"]

    assert package_dir.exists()
    assert not any("truth" in str(path).lower() for path in package_dir.parent.rglob("*"))


def test_phase6g5_passes_with_simulated_run05_corrected_gpt_source(monkeypatch, tmp_path: Path) -> None:
    if (REPO_ROOT / phase6g5.GPT_TARGETED_RUN05_SOURCE["prediction_file"]).exists():
        pytest.skip("Real GPT recovery_run_05 artifact exists; duplicate simulated recovery is intentionally blocked.")
    out = tmp_path / "phase6g4" / "gpt" / "recovery_run_05"

    def fake_preflight(repo_root, output_dir=gpt_recovery.TARGETED_OUTPUT_DIR, require_openai_key=True):
        return {
            "schema_version": "phase6g4a_gpt_targeted_recovery_preflight_v1",
            "passed": True,
            "checks": {},
            "failures": [],
            "target_request_id": gpt_recovery.TARGETED_FAILED_REQUEST_ID,
            "target_rendered_prompt_id": gpt_recovery.TARGETED_FAILED_RENDERED_PROMPT_ID,
            "ground_truth_dependency": False,
        }

    def fake_invoke(messages, attempt_type, max_output_tokens):
        return {
            "status": "completed",
            "output_text": '{"predicted_preferred_mix":"A","predicted_ratings":{"A":80,"B":60,"C":55,"D":50,"E":45},"predicted_ranking":["A","B","C","D","E"]}',
            "metadata": {"model": "gpt-5.5-2026-04-23", "request_api": "OpenAI.responses.create"},
            "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30, "output_tokens_details": {"reasoning_tokens": 5}},
        }

    monkeypatch.setattr(gpt_recovery, "run_targeted_preflight", fake_preflight)
    monkeypatch.setattr(gpt_recovery, "invoke_openai", fake_invoke)
    gpt_recovery.run_gpt_targeted_final_slot_recovery(REPO_ROOT, guarded_batch_size=1, output_dir=out)
    simulated_gpt_source = dict(phase6g5.GPT_TARGETED_RUN05_SOURCE)
    simulated_gpt_source["prediction_file"] = out / "final_gpt_predictions.jsonl"
    simulated_gpt_source["summary_file"] = out / "final_gpt_completion_summary.json"

    def fake_sources(repo_root):
        sources = {model_key: dict(source) for model_key, source in phase6g5.FINAL_SOURCES.items()}
        sources["gpt"] = simulated_gpt_source
        return sources

    monkeypatch.setattr(phase6g5, "resolve_final_sources", fake_sources)
    result = phase6g5.build_phase6g5_final_predictions(REPO_ROOT, output_dir=tmp_path / "phase6g5")

    assert result["qc_summary"]["actual_total_rows"] == 1584
    assert result["qc_summary"]["FINAL_LLM_PREDICTIONS_QC_PASSED"] is True
    assert result["freeze_manifest"]["gates"]["FINAL_LLM_PREDICTIONS_FROZEN"] is True
    assert result["qc_summary"]["GROUND_TRUTH_NOT_LOADED_FOR_PHASE6G5"] is True
