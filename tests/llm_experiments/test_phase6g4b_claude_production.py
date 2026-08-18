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

import llm_experiments.inference.phase6g4b_claude as claude  # noqa: E402
from llm_experiments.inference.failures import classify_failure  # noqa: E402
from llm_experiments.inference.registry import assert_no_secrets  # noqa: E402


OUT = REPO_ROOT / claude.OUTPUT_DIR
RUN_MANIFEST = OUT / "run_manifest.json"
PREFLIGHT = OUT / "preflight_report.json"
SUMMARY = OUT / "execution_summary.json"
QC_REPORT = OUT / "claude_production_qc_report.md"
CLAUDE_SHARD = REPO_ROOT / claude.CLAUDE_SHARD


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fake_preflight() -> dict:
    return {
        "schema_version": "phase6g4b_claude_preflight_v1",
        "passed": True,
        "checks": {},
        "failures": [],
        "claude_shard_request_count": 396,
        "condition_counts": {"non_history": 198, "personalised_history": 198},
        "prompt_hash_mismatches": [],
        "duplicate_request_ids": [],
        "ground_truth_dependency": False,
    }


def valid_response() -> dict:
    return {
        "status": "completed",
        "output_text": '{"predicted_preferred_mix":"A","predicted_ratings":{"A":80,"B":60,"C":55,"D":50,"E":45},"predicted_ranking":["A","B","C","D","E"]}',
        "metadata": {"model": "claude-sonnet-5", "request_api": "Anthropic.messages.create", "stop_reason": "end_turn"},
        "usage": {"input_tokens": 10, "output_tokens": 20},
    }


def test_claude_preflight_blocks_malformed_key_before_requests(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test\n")
    monkeypatch.setattr(claude.util, "find_spec", lambda name: object() if name == "anthropic" else None)

    preflight = claude.run_preflight(REPO_ROOT)

    assert preflight["checks"]["anthropic_api_key_present"] is True
    assert preflight["checks"]["anthropic_api_key_has_no_leading_or_trailing_whitespace"] is False
    assert preflight["checks"]["anthropic_api_key_contains_no_cr_or_lf"] is False
    assert preflight["passed"] is False
    assert "sk-ant-test" not in json.dumps(preflight)


def test_claude_shard_cardinality_condition_counts_and_model() -> None:
    shard = load_json(CLAUDE_SHARD)
    requests = shard["requests"]
    counts = Counter(row["condition"] for row in requests)

    assert shard["request_count"] == 396
    assert len(requests) == 396
    assert counts == {"non_history": 198, "personalised_history": 198}
    assert {row["model_key"] for row in requests} == {"claude_sonnet"}
    assert {row["exact_model_id"] for row in requests} == {"claude-sonnet-5"}
    assert len({row["request_id"] for row in requests}) == 396


def test_blocked_local_artifacts_and_policy_fields() -> None:
    manifest = load_json(RUN_MANIFEST)
    summary = load_json(SUMMARY)

    assert manifest["run_id"] == "phase6g4b_claude_production_run_01"
    assert manifest["output_dir"].endswith("phase6g4/claude")
    assert manifest["exact_requested_model"] == "claude-sonnet-5"
    assert manifest["backend"] == "Anthropic Messages API"
    assert manifest["max_tokens"] == 1024
    assert manifest["thinking_disabled_sent"] is True
    assert manifest["temperature_sent"] is False
    assert manifest["top_p_sent"] is False
    assert manifest["top_k_sent"] is False
    assert manifest["seed_sent"] is False
    assert manifest["assistant_prefill_sent"] is False
    assert summary["preflight_passed"] is False
    assert summary["attempted_prediction_count"] == 0
    assert summary["remaining_predictions"] == 396


def test_provider_call_uses_anthropic_messages_with_thinking_disabled(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                id="msg_test",
                model="claude-sonnet-5",
                stop_reason="end_turn",
                content=[SimpleNamespace(type="text", text=valid_response()["output_text"])],
                usage=SimpleNamespace(input_tokens=1, output_tokens=2),
            )

    class FakeClient:
        def __init__(self):
            self.messages = FakeMessages()

    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=FakeClient))

    result = claude.invoke_anthropic([{"role": "system", "content": "s"}, {"role": "user", "content": "u"}], "primary")

    assert result["status"] == "completed"
    assert captured["model"] == "claude-sonnet-5"
    assert captured["max_tokens"] == 1024
    assert captured["thinking"] == {"type": "disabled"}
    assert captured["system"] == "s"
    assert captured["messages"] == [{"role": "user", "content": "u"}]
    assert "temperature" not in captured
    assert "top_p" not in captured
    assert "top_k" not in captured
    assert "seed" not in captured


def test_guarded_batch_resume_and_duplicate_prevention(monkeypatch, tmp_path) -> None:
    calls = {"count": 0}

    def fake_invoke(messages: list[dict[str, str]], attempt_type: str) -> dict:
        calls["count"] += 1
        return valid_response()

    out = tmp_path / "phase6g4" / "claude"
    monkeypatch.setattr(claude, "run_preflight", lambda repo_root, output_dir=claude.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(claude, "invoke_anthropic", fake_invoke)

    first = claude.run_claude_production(REPO_ROOT, guarded_batch_size=5, output_dir=out)
    second = claude.run_claude_production(REPO_ROOT, guarded_batch_size=5, output_dir=out)

    predictions = load_jsonl(out / "predictions.jsonl")
    assert first["predictions_executed_this_invocation"] == 5
    assert first["remaining_predictions"] == 391
    assert second["predictions_executed_this_invocation"] == 5
    assert second["remaining_predictions"] == 386
    assert calls["count"] == 10
    assert len(predictions) == 10
    assert len({row["request_id"] for row in predictions}) == 10
    assert len({row["prediction_id"] for row in predictions}) == 10


def test_malformed_completed_response_gets_one_format_repair(monkeypatch, tmp_path) -> None:
    calls = {"count": 0}

    def fake_invoke(messages: list[dict[str, str]], attempt_type: str) -> dict:
        calls["count"] += 1
        if attempt_type == "primary":
            return {"status": "completed", "output_text": "{bad json", "metadata": {"model": "claude-sonnet-5"}, "usage": {"input_tokens": 1, "output_tokens": 2}}
        return valid_response()

    out = tmp_path / "phase6g4" / "claude"
    monkeypatch.setattr(claude, "run_preflight", lambda repo_root, output_dir=claude.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(claude, "invoke_anthropic", fake_invoke)

    summary = claude.run_claude_production(REPO_ROOT, guarded_batch_size=1, output_dir=out)
    predictions = load_jsonl(out / "predictions.jsonl")

    assert calls["count"] == 2
    assert predictions[0]["final_status"] == "valid_after_repair"
    assert predictions[0]["formatting_repair_count"] == 1
    assert summary["valid_after_repair_count"] == 1


def test_max_tokens_stop_is_output_budget_and_not_repaired(monkeypatch, tmp_path) -> None:
    calls = {"count": 0}

    def fake_invoke(messages: list[dict[str, str]], attempt_type: str) -> dict:
        calls["count"] += 1
        return {
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens", "stop_reason": "max_tokens"},
            "output_text": '{"predicted_preferred_mix":"C"',
            "metadata": {"model": "claude-sonnet-5", "stop_reason": "max_tokens"},
            "usage": {"input_tokens": 1, "output_tokens": 1024},
        }

    out = tmp_path / "phase6g4" / "claude"
    monkeypatch.setattr(claude, "run_preflight", lambda repo_root, output_dir=claude.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(claude, "invoke_anthropic", fake_invoke)

    summary = claude.run_claude_production(REPO_ROOT, guarded_batch_size=1, output_dir=out)
    attempts = load_jsonl(out / "attempt_log.jsonl")
    predictions = load_jsonl(out / "predictions.jsonl")

    assert calls["count"] == 1
    assert attempts[0]["failure_code"] == "output_budget_exhausted"
    assert attempts[0]["retryable"] is False
    assert predictions[0]["final_status"] == "output_budget_exhausted"
    assert predictions[0]["formatting_repair_count"] == 0
    assert summary["output_budget_exhausted_count"] == 1


def test_failure_classification_rate_limit_quota_and_refusal_distinct() -> None:
    rate = classify_failure({"status": "error", "error": {"http_status_code": 429, "type": "rate_limit_error"}}, {})
    quota = classify_failure({"status": "error", "error": {"http_status_code": 429, "type": "insufficient_quota", "code": "credit_balance_exhausted"}}, {})
    refusal = classify_failure({"status": "completed", "error": {"type": "refusal"}}, {"status": "missing_response"})

    assert rate["failure_code"] == "rate_limited"
    assert rate["retryable"] is True
    assert quota["failure_code"] == "quota_exhausted"
    assert quota["retryable"] is False
    assert refusal["failure_code"] == "refusal"
    assert refusal["failure_category"] == "refusal"


def test_quota_exhaustion_halts_invocation_without_retries(monkeypatch, tmp_path) -> None:
    calls = {"count": 0}

    def fake_invoke(messages: list[dict[str, str]], attempt_type: str) -> dict:
        calls["count"] += 1
        return {
            "status": "error",
            "output_text": None,
            "metadata": {},
            "usage": None,
            "error": {"http_status_code": 429, "type": "insufficient_quota", "code": "credit_balance_exhausted"},
        }

    out = tmp_path / "phase6g4" / "claude"
    monkeypatch.setattr(claude, "run_preflight", lambda repo_root, output_dir=claude.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(claude, "invoke_anthropic", fake_invoke)

    summary = claude.run_claude_production(REPO_ROOT, guarded_batch_size=5, output_dir=out)
    attempts = load_jsonl(out / "attempt_log.jsonl")

    assert calls["count"] == 1
    assert len(attempts) == 1
    assert attempts[0]["failure_code"] == "quota_exhausted"
    assert attempts[0]["retryable"] is False
    assert summary["halted_due_quota_exhaustion"] is True
    assert summary["predictions_executed_this_invocation"] == 1
    assert summary["remaining_predictions"] == 395


def test_prompt_hashes_and_no_ground_truth_or_secrets() -> None:
    preflight = load_json(PREFLIGHT)
    manifest = load_json(RUN_MANIFEST)
    summary = load_json(SUMMARY)

    assert preflight["prompt_hash_mismatches"] == []
    assert preflight["checks"]["no_hidden_ground_truth_loaded"] is True
    assert manifest["contains_hidden_ground_truth"] is False
    assert summary["ground_truth_dependency"] is False
    for payload in [preflight, manifest, summary]:
        assert_no_secrets(payload)
        text = json.dumps(payload).lower()
        assert "final_trial_ground_truth" not in text
        assert "final_candidate_ground_truth" not in text
    assert "ANTHROPIC_API_KEY" not in QC_REPORT.read_text(encoding="utf-8")
