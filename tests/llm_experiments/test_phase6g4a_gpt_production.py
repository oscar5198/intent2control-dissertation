from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.inference.phase6g4a_gpt import OUTPUT_DIR, run_preflight  # noqa: E402
from llm_experiments.inference.registry import assert_no_secrets  # noqa: E402


OUT = REPO_ROOT / OUTPUT_DIR
RUN_MANIFEST = OUT / "run_manifest.json"
PREFLIGHT = OUT / "preflight_report.json"
SUMMARY = OUT / "execution_summary.json"
QC_REPORT = OUT / "gpt_production_qc_report.md"
GPT_SHARD = REPO_ROOT / "llm-experiments" / "outputs" / "real" / "phase6g3" / "phase6g3_qmul_gpt_shard_manifest.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_gpt_preflight_structural_checks_pass_except_runtime_dependencies(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    preflight = run_preflight(REPO_ROOT)

    assert preflight["checks"]["phase6d_prompt_package_frozen"] is True
    assert preflight["checks"]["phase6g1_real_data_ready"] is True
    assert preflight["checks"]["phase6g2d_production_ready"] is True
    assert preflight["checks"]["phase6g3_prompt_freeze_ready"] is True
    assert preflight["checks"]["gpt_shard_count_valid"] is True
    assert preflight["checks"]["prompt_hashes_valid"] is True
    assert preflight["checks"]["request_ids_deterministic_unique"] is True
    assert preflight["checks"]["output_directory_production_gpt_namespace"] is True
    assert preflight["checks"]["no_hidden_ground_truth_loaded"] is True
    assert preflight["checks"]["openai_api_key_present"] is False


def test_gpt_shard_is_gpt_only_and_has_expected_coverage() -> None:
    shard = load_json(GPT_SHARD)

    assert shard["request_count"] == 396
    assert set(row["model_key"] for row in shard["requests"]) == {"gpt"}
    assert sum(1 for row in shard["requests"] if row["condition"] == "non_history") == 198
    assert sum(1 for row in shard["requests"] if row["condition"] == "personalised_history") == 198
    assert len({row["request_id"] for row in shard["requests"]}) == 396


def test_blocked_outputs_do_not_contain_predictions_or_secrets() -> None:
    for path in [RUN_MANIFEST, PREFLIGHT, SUMMARY]:
        payload = load_json(path)
        assert_no_secrets(payload)
    summary = load_json(SUMMARY)

    assert summary["preflight_passed"] is False
    assert summary["attempted_prediction_count"] == 0
    assert summary["terminal_prediction_count"] == 0
    assert summary["total_api_calls"] == 0
    assert summary["GPT_PRODUCTION_INFERENCE_COMPLETE"] is False
    assert summary["ALL_GPT_PREDICTIONS_VALID"] is False
    assert not (OUT / "attempt_log.jsonl").exists()
    assert not (OUT / "predictions.jsonl").exists()


def test_run_manifest_freezes_gpt_request_settings() -> None:
    manifest = load_json(RUN_MANIFEST)

    assert manifest["exact_requested_model"] == "gpt-5.5"
    assert manifest["expected_returned_model"] == "gpt-5.5-2026-04-23"
    assert manifest["temperature_sent"] is False
    assert manifest["top_p_sent"] is False
    assert manifest["seed_sent"] is False
    assert manifest["max_output_tokens"] == 256
    assert manifest["expected_request_count"] == 396
    assert manifest["shard_request_count"] == 396
    assert manifest["contains_hidden_ground_truth"] is False


def test_qc_report_records_blocker_without_accuracy() -> None:
    text = QC_REPORT.read_text(encoding="utf-8")

    assert "Preflight passed: `false`" in text
    assert "OPENAI_API_KEY" not in text
    assert "accuracy:" not in text.lower()
    assert "score" not in text.lower()
    assert "Claude" in text
    assert "Llama" in text
    assert "Centaur" in text
