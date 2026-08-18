from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

import llm_experiments.inference.phase6g4a_gpt as gpt4a  # noqa: E402
from llm_experiments.inference.registry import assert_no_secrets  # noqa: E402


OUT = REPO_ROOT / gpt4a.OUTPUT_DIR
ARCHIVE = REPO_ROOT / gpt4a.FAILED_INFRA_ARCHIVE_DIR
RUN_MANIFEST = OUT / "run_manifest.json"
PREFLIGHT = OUT / "preflight_report.json"
SUMMARY = OUT / "execution_summary.json"
QC_REPORT = OUT / "gpt_production_qc_report.md"
GPT_SHARD = REPO_ROOT / "llm-experiments" / "outputs" / "real" / "phase6g3" / "phase6g3_qmul_gpt_shard_manifest.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_malformed_key_with_trailing_newline_blocks_before_requests(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test\n")
    monkeypatch.setattr(gpt4a.util, "find_spec", lambda name: object() if name == "openai" else None)

    preflight = gpt4a.run_preflight(REPO_ROOT)

    assert preflight["checks"]["openai_api_key_present"] is True
    assert preflight["checks"]["openai_api_key_has_no_leading_or_trailing_whitespace"] is False
    assert preflight["checks"]["openai_api_key_contains_no_cr_or_lf"] is False
    assert preflight["passed"] is False
    assert "sk-test" not in json.dumps(preflight)


def test_recovery_manifest_preserves_failed_infrastructure_run_provenance() -> None:
    recovery = load_json(ARCHIVE / "recovery_manifest.json")

    assert recovery["old_run_id"] == "phase6g4a_gpt_failed_infrastructure_run_01"
    assert recovery["new_corrected_run_id"] == "phase6g4a_gpt_corrected_run_01"
    assert recovery["failure_classification"]["affected_prediction_count"] == 396
    assert recovery["failure_classification"]["failed_transport_attempt_count"] == 1188
    assert recovery["failure_classification"]["successful_provider_generation_count"] == 0
    assert recovery["failure_classification"]["returned_model_identity_count"] == 0
    assert recovery["failure_classification"]["token_usage_count"] == 0
    assert len(recovery["affected_prediction_ids"]) == 396
    assert "trailing newline" in recovery["confirmed_root_cause"]
    assert_no_secrets(recovery)


def test_corrected_run_preflight_namespace_is_distinct_and_blocked_locally() -> None:
    summary = load_json(SUMMARY)
    manifest = load_json(RUN_MANIFEST)

    assert manifest["run_id"] == "phase6g4a_gpt_corrected_run_01"
    assert manifest["output_dir"].endswith("phase6g4/gpt/corrected_run_01")
    assert summary["preflight_passed"] is False
    assert summary["attempted_prediction_count"] == 0
    assert summary["total_api_calls"] == 0
    assert summary["guarded_batch_limit"] == 3
    assert summary["predictions_executed_this_invocation"] == 0
    assert summary["remaining_predictions"] == 396
    assert not (OUT / "attempt_log.jsonl").exists()
    assert not (OUT / "predictions.jsonl").exists()


def test_guarded_batch_size_3_executes_exactly_3_prediction_units_and_resume(monkeypatch, tmp_path) -> None:
    calls = {"count": 0}

    def fake_preflight(repo_root: Path, output_dir: Path = gpt4a.OUTPUT_DIR) -> dict:
        return {
            "schema_version": "phase6g4a_gpt_preflight_v1",
            "passed": True,
            "checks": {},
            "failures": [],
            "gpt_shard_request_count": 396,
            "condition_counts": {"non_history": 198, "personalised_history": 198},
            "prompt_hash_mismatches": [],
            "duplicate_request_ids": [],
        }

    def fake_invoke(messages: list[dict[str, str]], attempt_type: str) -> dict:
        calls["count"] += 1
        return {
            "status": "completed",
            "output_text": '{"predicted_preferred_mix":"A","predicted_ratings":{"A":80,"B":60,"C":55,"D":50,"E":45},"predicted_ranking":["A","B","C","D","E"]}',
            "metadata": {"model": "gpt-5.5-2026-04-23", "request_api": "OpenAI.responses.create"},
            "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
        }

    monkeypatch.setattr(gpt4a, "run_preflight", fake_preflight)
    monkeypatch.setattr(gpt4a, "invoke_openai", fake_invoke)
    out = tmp_path / "phase6g4" / "gpt" / "corrected_run_01"

    first = gpt4a.run_gpt_production(REPO_ROOT, guarded_batch_size=3, output_dir=out, run_id="test_corrected_run")
    second = gpt4a.run_gpt_production(REPO_ROOT, guarded_batch_size=3, output_dir=out, run_id="test_corrected_run")

    assert first["predictions_executed_this_invocation"] == 3
    assert first["attempted_prediction_count"] == 3
    assert first["remaining_predictions"] == 393
    assert first["stopped_after_guarded_batch"] is True
    assert second["predictions_executed_this_invocation"] == 3
    assert second["attempted_prediction_count"] == 6
    assert second["remaining_predictions"] == 390
    assert calls["count"] == 6
    predictions = load_jsonl(out / "predictions.jsonl")
    assert len(predictions) == 6
    assert len({row["prediction_id"] for row in predictions}) == 6
    assert all(row["run_id"] == "test_corrected_run" for row in predictions)


def test_gpt_shard_is_gpt_only_and_has_expected_coverage() -> None:
    shard = load_json(GPT_SHARD)

    assert shard["request_count"] == 396
    assert set(row["model_key"] for row in shard["requests"]) == {"gpt"}
    assert sum(1 for row in shard["requests"] if row["condition"] == "non_history") == 198
    assert sum(1 for row in shard["requests"] if row["condition"] == "personalised_history") == 198
    assert len({row["request_id"] for row in shard["requests"]}) == 396


def test_no_ground_truth_or_secrets_are_serialized() -> None:
    for path in [RUN_MANIFEST, PREFLIGHT, SUMMARY, ARCHIVE / "recovery_manifest.json"]:
        payload = load_json(path)
        assert_no_secrets(payload)
        text = json.dumps(payload).lower()
        assert "final_trial_ground_truth" not in text
        assert "final_candidate_ground_truth" not in text
    assert "OPENAI_API_KEY" not in QC_REPORT.read_text(encoding="utf-8")


def test_qc_report_records_recovery_guardrails() -> None:
    text = QC_REPORT.read_text(encoding="utf-8")

    assert "Preflight passed: `false`" in text
    assert "Guarded batch limit: `3`" in text
    assert "Predictions executed this invocation: `0`" in text
    assert "accuracy:" not in text.lower()
