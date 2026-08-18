from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

import llm_experiments.inference.phase6g4a_gpt_recovery as recovery  # noqa: E402
from llm_experiments.inference.failures import classify_failure  # noqa: E402
from llm_experiments.inference.registry import assert_no_secrets  # noqa: E402


OUT = REPO_ROOT / recovery.OUTPUT_DIR
RUN03 = REPO_ROOT / recovery.SOURCE_RUN03_DIR
MANIFEST = OUT / "recovery_manifest.json"
ELIGIBILITY = OUT / "recovery_eligibility.jsonl"
FINAL_PREDICTIONS = OUT / "final_gpt_predictions.jsonl"
FINAL_PROVENANCE = OUT / "final_gpt_prediction_provenance.jsonl"
FINAL_SUMMARY = OUT / "final_gpt_completion_summary.json"
GPT_SHARD = REPO_ROOT / "llm-experiments" / "outputs" / "real" / "phase6g3" / "phase6g3_qmul_gpt_shard_manifest.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def passing_preflight() -> dict:
    return {
        "schema_version": "phase6g4a_gpt_recovery_preflight_v1",
        "passed": True,
        "checks": {},
        "failures": [],
        "source_status_counts": {"valid_primary": 264, "backend_failed": 126, "output_budget_exhausted": 6},
        "prompt_hash_mismatches": [],
        "credential_policy": "no secret",
        "ground_truth_dependency": False,
    }


def valid_provider_response() -> dict:
    return {
        "status": "completed",
        "output_text": '{"predicted_preferred_mix":"A","predicted_ratings":{"A":80,"B":60,"C":55,"D":50,"E":45},"predicted_ranking":["A","B","C","D","E"]}',
        "metadata": {"model": "gpt-5.5-2026-04-23", "request_api": "OpenAI.responses.create"},
        "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30, "output_tokens_details": {"reasoning_tokens": 5}},
    }


def test_run03_authoritative_counts_and_recovery_eligibility() -> None:
    source_predictions = load_jsonl(RUN03 / "predictions.jsonl")
    counts = Counter(row["final_status"] for row in source_predictions)
    eligibility = recovery.build_recovery_eligibility(REPO_ROOT)
    reason_counts = Counter(row["recovery_eligibility_reason"] for row in eligibility)

    assert counts["valid_primary"] == 264
    assert counts["backend_failed"] == 126
    assert counts["output_budget_exhausted"] == 6
    assert len(eligibility) == 132
    assert reason_counts["quota_transport_recovery"] == 126
    assert reason_counts["output_budget_recovery"] == 6
    assert 264 + len(eligibility) == 396
    eligible_source_ids = {row["source_run03_prediction_id"] for row in eligibility}
    assert not any(row["final_status"] == "valid_primary" and row["prediction_id"] in eligible_source_ids for row in source_predictions)


def test_recovery_manifest_and_artifacts_record_policy() -> None:
    manifest = load_json(MANIFEST)
    eligibility = load_jsonl(ELIGIBILITY)

    assert manifest["run_id"] == "phase6g4a_gpt_recovery_run_04"
    assert manifest["source_run03_id"] == "phase6g4a_gpt_corrected_run_03"
    assert manifest["preserved_valid_count"] == 264
    assert manifest["transport_quota_recovery_count"] == 126
    assert manifest["output_budget_recovery_count"] == 6
    assert manifest["total_recovery_count"] == 132
    assert manifest["max_output_tokens_by_recovery_class"]["quota_transport_recovery"] == 4096
    assert manifest["max_output_tokens_by_recovery_class"]["output_budget_recovery"] == 8192
    assert manifest["exact_requested_model"] == "gpt-5.5"
    assert manifest["expected_returned_model"] == "gpt-5.5-2026-04-23"
    assert manifest["response_schema_version"] == "preference_prediction_response_v1"
    assert manifest["temperature_sent"] is False
    assert manifest["top_p_sent"] is False
    assert manifest["seed_sent"] is False
    assert "provider_native_reasoning" in manifest["reasoning_policy"]
    assert manifest["prompt_hash_verification"]["passed"] is True
    assert {row["max_output_tokens"] for row in eligibility if row["recovery_eligibility_reason"] == "quota_transport_recovery"} == {4096}
    assert {row["max_output_tokens"] for row in eligibility if row["recovery_eligibility_reason"] == "output_budget_recovery"} == {8192}
    assert_no_secrets(manifest)


def test_prompt_hashes_schema_model_and_deterministic_ids_unchanged() -> None:
    shard = load_json(GPT_SHARD)
    eligibility = recovery.build_recovery_eligibility(REPO_ROOT)
    first = eligibility[0]
    again = recovery.build_recovery_eligibility(REPO_ROOT)[0]
    shard_by_request = {row["request_id"]: row for row in shard["requests"]}

    assert first["recovery_unit_id"] == again["recovery_unit_id"]
    assert first["recovery_prediction_id"] == again["recovery_prediction_id"]
    for row in eligibility:
        source = shard_by_request[row["request_id"]]
        assert row["prompt_hash"] == source["prompt_hash"]
        assert row["rendered_prompt_id"] == source["rendered_prompt_id"]
        assert row["response_schema_version"] == "preference_prediction_response_v1"
        assert row["exact_requested_model"] == "gpt-5.5"


def test_quota_exhaustion_classified_non_retryable_and_rate_limit_distinct() -> None:
    quota = classify_failure({"status": "error", "error": {"http_status_code": 429, "type": "insufficient_quota", "code": "credit_balance_exhausted"}}, {})
    rate_limit = classify_failure({"status": "error", "error": {"http_status_code": 429, "type": "rate_limit_error", "code": "rate_limit_exceeded"}}, {})

    assert quota["failure_code"] == "quota_exhausted"
    assert quota["failure_category"] == "quota"
    assert quota["retryable"] is False
    assert rate_limit["failure_code"] == "rate_limited"
    assert rate_limit["failure_category"] == "transport"
    assert rate_limit["retryable"] is True


def test_quota_exhaustion_halts_invocation_without_retries(monkeypatch, tmp_path) -> None:
    calls = {"count": 0}

    def fake_invoke(messages: list[dict[str, str]], attempt_type: str, max_output_tokens: int) -> dict:
        calls["count"] += 1
        return {
            "status": "error",
            "output_text": None,
            "metadata": {},
            "usage": None,
            "error": {"http_status_code": 429, "type": "insufficient_quota", "code": "credit_balance_exhausted"},
        }

    monkeypatch.setattr(recovery, "run_preflight", lambda repo_root, output_dir=recovery.OUTPUT_DIR: passing_preflight())
    monkeypatch.setattr(recovery, "invoke_openai", fake_invoke)

    summary = recovery.run_gpt_recovery(REPO_ROOT, guarded_batch_size=6, output_dir=tmp_path / "phase6g4" / "gpt" / "recovery_run_04")

    attempts = load_jsonl(tmp_path / "phase6g4" / "gpt" / "recovery_run_04" / "attempt_log.jsonl")
    assert calls["count"] == 1
    assert len(attempts) == 1
    assert attempts[0]["failure_code"] == "quota_exhausted"
    assert attempts[0]["retryable"] is False
    assert summary["halted_due_quota_exhaustion"] is True
    assert summary["recovery_predictions_executed_this_invocation"] == 1
    assert summary["remaining_unresolved_recovery_predictions"] == 131


def test_guarded_batch_and_resume_skip_successful_recovery(monkeypatch, tmp_path) -> None:
    calls = {"count": 0}

    def fake_invoke(messages: list[dict[str, str]], attempt_type: str, max_output_tokens: int) -> dict:
        calls["count"] += 1
        return valid_provider_response()

    out = tmp_path / "phase6g4" / "gpt" / "recovery_run_04"
    monkeypatch.setattr(recovery, "run_preflight", lambda repo_root, output_dir=recovery.OUTPUT_DIR: passing_preflight())
    monkeypatch.setattr(recovery, "invoke_openai", fake_invoke)

    first = recovery.run_gpt_recovery(REPO_ROOT, guarded_batch_size=6, output_dir=out)
    second = recovery.run_gpt_recovery(REPO_ROOT, guarded_batch_size=6, output_dir=out)

    predictions = load_jsonl(out / "predictions.jsonl")
    assert first["recovery_predictions_executed_this_invocation"] == 6
    assert first["remaining_unresolved_recovery_predictions"] == 126
    assert second["recovery_predictions_executed_this_invocation"] == 6
    assert second["remaining_unresolved_recovery_predictions"] == 120
    assert calls["count"] == 12
    assert len(predictions) == 12
    assert len({row["source_run03_prediction_id"] for row in predictions}) == 12


def test_output_budget_truncation_does_not_format_repair(monkeypatch, tmp_path) -> None:
    calls = {"count": 0}

    def fake_invoke(messages: list[dict[str, str]], attempt_type: str, max_output_tokens: int) -> dict:
        calls["count"] += 1
        return {
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "output_text": '{"predicted_preferred_mix":"C","predicted_ratings":{"A":58',
            "metadata": {"model": "gpt-5.5-2026-04-23", "request_api": "OpenAI.responses.create"},
            "usage": {"input_tokens": 10, "output_tokens": max_output_tokens, "total_tokens": max_output_tokens + 10},
        }

    monkeypatch.setattr(recovery, "run_preflight", lambda repo_root, output_dir=recovery.OUTPUT_DIR: passing_preflight())
    monkeypatch.setattr(recovery, "invoke_openai", fake_invoke)
    out = tmp_path / "phase6g4" / "gpt" / "recovery_run_04"

    summary = recovery.run_gpt_recovery(REPO_ROOT, guarded_batch_size=1, output_dir=out)
    attempts = load_jsonl(out / "attempt_log.jsonl")
    predictions = load_jsonl(out / "predictions.jsonl")

    assert calls["count"] == 1
    assert attempts[0]["failure_code"] == "output_budget_exhausted"
    assert attempts[0]["attempt_type"] == "primary"
    assert predictions[0]["final_status"] == "output_budget_exhausted"
    assert predictions[0]["formatting_repair_count"] == 0
    assert summary["output_budget_exhausted_count"] == 1


def test_provider_native_reasoning_and_sampling_controls_omitted(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(status="completed", output_text=valid_provider_response()["output_text"], model="gpt-5.5-2026-04-23", usage={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}, incomplete_details=None)

    class FakeClient:
        def __init__(self):
            self.responses = FakeResponses()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeClient))

    result = recovery.invoke_openai([{"role": "system", "content": "s"}, {"role": "user", "content": "u"}], "primary", 8192)

    assert result["status"] == "completed"
    assert captured["model"] == "gpt-5.5"
    assert captured["max_output_tokens"] == 8192
    assert captured["instructions"] == "s"
    assert captured["input"] == "u"
    assert "reasoning" not in captured
    assert "reasoning_effort" not in captured
    assert "temperature" not in captured
    assert "top_p" not in captured
    assert "seed" not in captured


def test_final_merge_precedence_and_ground_truth_isolation(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(recovery, "run_preflight", lambda repo_root, output_dir=recovery.OUTPUT_DIR: passing_preflight())
    monkeypatch.setattr(recovery, "invoke_openai", lambda messages, attempt_type, max_output_tokens: valid_provider_response())
    out = tmp_path / "phase6g4" / "gpt" / "recovery_run_04"

    recovery.run_gpt_recovery(REPO_ROOT, guarded_batch_size=1, output_dir=out)

    final_rows = load_jsonl(out / "final_gpt_predictions.jsonl")
    provenance = load_jsonl(out / "final_gpt_prediction_provenance.jsonl")
    summary = load_json(out / "final_gpt_completion_summary.json")
    assert len(final_rows) == 396
    assert len({row["request_id"] for row in final_rows}) == 396
    assert Counter(row["source_type"] for row in provenance)["run03_original_valid_prediction"] == 264
    assert Counter(row["source_type"] for row in provenance)["run04_recovered_prediction"] == 1
    assert summary["ground_truth_dependency"] is False
    for path in [out / "recovery_manifest.json", out / "final_gpt_completion_summary.json"]:
        text = path.read_text(encoding="utf-8").lower()
        assert "final_trial_ground_truth" not in text
        assert "final_candidate_ground_truth" not in text
        assert_no_secrets(load_json(path))


def test_run03_artifacts_remain_immutable() -> None:
    manifest = load_json(MANIFEST)

    assert sha256_file(RUN03 / "predictions.jsonl") == manifest["source_run03_predictions_sha256"]
    assert sha256_file(RUN03 / "attempt_log.jsonl") == manifest["source_run03_attempt_log_sha256"]


def sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
