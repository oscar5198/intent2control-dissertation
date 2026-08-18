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


def fenced_response(choice: str = "B") -> str:
    return f'''```json
{{"predicted_preferred_mix":"{choice}","predicted_ratings":{{"A":58,"B":74,"C":65,"D":50,"E":68}},"predicted_ranking":["B","E","C","A","D"]}}
```'''


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


def test_claude_response_normalizer_accepts_only_outer_fences() -> None:
    bare = '{"predicted_preferred_mix":"B"}'
    json_fenced = '```json\n{"predicted_preferred_mix":"B"}\n```'
    generic_fenced = '```\n{"predicted_preferred_mix":"B"}\n```'

    assert claude.normalize_claude_response_text(bare)["normalized_response_text"] == bare
    assert claude.normalize_claude_response_text(f"  {json_fenced}\n")["normalized_response_text"] == '{"predicted_preferred_mix":"B"}'
    assert claude.normalize_claude_response_text(generic_fenced)["normalized_response_text"] == '{"predicted_preferred_mix":"B"}'
    assert claude.normalize_claude_response_text(json_fenced)["response_normalization"] == "markdown_json_fence_removed"
    assert claude.normalize_claude_response_text(generic_fenced)["response_normalization"] == "markdown_generic_fence_removed"


def test_claude_response_normalizer_rejects_prose_trailing_text_and_multiple_fences() -> None:
    prose = 'Here is JSON:\n```json\n{"predicted_preferred_mix":"B"}\n```'
    trailing = '```json\n{"predicted_preferred_mix":"B"}\n```\nextra'
    multiple = '```json\n{"a":1}\n```\n```json\n{"b":2}\n```'

    assert claude.normalize_claude_response_text(prose)["normalized_response_text"] == prose
    assert claude.normalize_claude_response_text(trailing)["normalized_response_text"] == trailing
    assert claude.normalize_claude_response_text(multiple)["normalized_response_text"] == multiple


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


def test_fenced_valid_primary_is_valid_primary_without_format_repair(monkeypatch, tmp_path) -> None:
    calls = {"count": 0}

    def fake_invoke(messages: list[dict[str, str]], attempt_type: str) -> dict:
        calls["count"] += 1
        return {"status": "completed", "output_text": fenced_response(), "metadata": {"model": "claude-sonnet-5"}, "usage": {"input_tokens": 1, "output_tokens": 2}}

    out = tmp_path / "phase6g4" / "claude"
    monkeypatch.setattr(claude, "run_preflight", lambda repo_root, output_dir=claude.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(claude, "invoke_anthropic", fake_invoke)

    summary = claude.run_claude_production(REPO_ROOT, guarded_batch_size=1, output_dir=out)
    attempts = load_jsonl(out / "attempt_log.jsonl")
    predictions = load_jsonl(out / "predictions.jsonl")

    assert calls["count"] == 1
    assert attempts[0]["raw_response_text"].startswith("```json")
    assert attempts[0]["normalized_response_text"].startswith('{"predicted_preferred_mix"')
    assert attempts[0]["response_normalization"] == "markdown_json_fence_removed"
    assert predictions[0]["final_status"] == "valid_primary"
    assert predictions[0]["formatting_repair_count"] == 0
    assert summary["formatting_repair_count"] == 0


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


def test_malformed_and_schema_invalid_fenced_json_rejected() -> None:
    schema = claude.load_response_schema(REPO_ROOT / claude.RESPONSE_SCHEMA)
    malformed = claude.normalize_claude_response_text("```json\n{bad json\n```")
    schema_invalid = claude.normalize_claude_response_text('```json\n{"predicted_preferred_mix":"B"}\n```')

    assert claude.validate_response_text(malformed["normalized_response_text"], schema)["valid"] is False
    assert claude.validate_response_text(malformed["normalized_response_text"], schema)["status"] == "invalid_json"
    assert claude.validate_response_text(schema_invalid["normalized_response_text"], schema)["valid"] is False
    assert claude.validate_response_text(schema_invalid["normalized_response_text"], schema)["status"] == "schema_invalid"


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


def test_offline_revalidation_chooses_earliest_valid_and_resume_skips(monkeypatch, tmp_path) -> None:
    out = tmp_path / "phase6g4" / "claude"
    out.mkdir(parents=True)
    shard = load_json(CLAUDE_SHARD)
    first = shard["requests"][0]
    second = shard["requests"][1]
    attempts = [
        make_attempt(first, "primary", fenced_response("B"), False, "invalid_json"),
        make_attempt(first, "format_repair", valid_response()["output_text"].replace('"A"', '"C"', 1), True, "valid"),
        make_attempt(second, "primary", "{bad json", False, "invalid_json"),
        make_attempt(second, "format_repair", valid_response()["output_text"], True, "valid"),
    ]
    write_jsonl_for_test(out / "attempt_log.jsonl", attempts)
    manifest = claude.build_run_manifest(REPO_ROOT, fake_preflight(), 5, out, claude.RUN_ID)
    claude.write_json(out / "run_manifest.json", manifest)
    claude.write_json(out / "preflight_report.json", fake_preflight())
    calls = {"count": 0}
    monkeypatch.setattr(claude, "run_preflight", lambda repo_root, output_dir=claude.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(claude, "invoke_anthropic", lambda messages, attempt_type: calls.__setitem__("count", calls["count"] + 1) or valid_response())

    revalidation = claude.revalidate_existing_claude_attempts(REPO_ROOT, output_dir=out)
    predictions = load_jsonl(out / "predictions.jsonl")
    resume = claude.run_claude_production(REPO_ROOT, guarded_batch_size=1, output_dir=out)

    assert revalidation["api_calls_during_offline_recovery"] == 0
    assert revalidation["requests_revalidated"] == 2
    assert revalidation["predictions_recovered_from_primary_attempts"] == 1
    assert revalidation["predictions_recovered_from_repair_attempts"] == 1
    assert revalidation["predictions_still_invalid"] == 0
    assert predictions[0]["final_status"] == "valid_primary"
    assert predictions[0]["formatting_repair_count"] == 0
    assert predictions[1]["final_status"] == "valid_after_repair"
    assert predictions[1]["formatting_repair_count"] == 1
    assert revalidation["records"][0]["primary_and_repair_predictions_differ"] is True
    assert resume["predictions_executed_this_invocation"] == 1
    assert calls["count"] == 1
    assert len(load_jsonl(out / "predictions.jsonl")) == 3
    assert len({row["request_id"] for row in load_jsonl(out / "predictions.jsonl")}) == 3


def test_offline_revalidation_preserves_historical_live_preflight_and_is_idempotent(monkeypatch, tmp_path) -> None:
    out = tmp_path / "phase6g4" / "claude"
    out.mkdir(parents=True)
    shard = load_json(CLAUDE_SHARD)
    first = shard["requests"][0]
    attempts = [make_attempt(first, "primary", fenced_response("B"), False, "invalid_json")]
    write_jsonl_for_test(out / "attempt_log.jsonl", attempts)
    live_preflight = fake_preflight()
    live_preflight["passed"] = True
    live_preflight["source_marker"] = "live_qmul_production_preflight"
    stale_offline_preflight = dict(live_preflight)
    stale_offline_preflight["passed"] = False
    stale_offline_preflight["failures"] = ["anthropic_api_key_present"]
    manifest = claude.build_run_manifest(REPO_ROOT, live_preflight, 5, out, claude.RUN_ID)
    claude.write_json(out / "run_manifest.json", manifest)
    claude.write_json(out / "preflight_report.json", stale_offline_preflight)
    monkeypatch.setattr(claude, "run_preflight", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("offline revalidation must not rerun preflight")))

    first_manifest = claude.revalidate_existing_claude_attempts(REPO_ROOT, output_dir=out)
    first_predictions = (out / "predictions.jsonl").read_text(encoding="utf-8")
    first_summary = load_json(out / "execution_summary.json")
    second_manifest = claude.revalidate_existing_claude_attempts(REPO_ROOT, output_dir=out)
    second_predictions = (out / "predictions.jsonl").read_text(encoding="utf-8")
    second_summary = load_json(out / "execution_summary.json")

    assert first_summary["preflight_passed"] is True
    assert first_summary["production_preflight_source"] == "run_manifest.preflight"
    assert first_summary["offline_revalidation_performed"] is True
    assert first_summary["offline_revalidation_api_calls"] == 0
    assert first_manifest["production_preflight_passed"] is True
    assert first_manifest["production_preflight_source"] == "run_manifest.preflight"
    assert first_manifest["api_calls_during_offline_recovery"] == 0
    assert second_summary["preflight_passed"] is True
    assert second_manifest["requests_revalidated"] == first_manifest["requests_revalidated"]
    assert second_predictions == first_predictions
    assert load_json(out / "preflight_report.json")["passed"] is False


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


def make_attempt(request: dict, attempt_type: str, raw_text: str, valid: bool, validation_status: str) -> dict:
    return {
        "schema_version": "phase6g4b_claude_attempt_v1",
        "run_id": claude.RUN_ID,
        "request_id": request["request_id"],
        "prediction_id": claude.prediction_id(request),
        "rendered_prompt_id": request["rendered_prompt_id"],
        "prediction_example_id": request["prediction_example_id"],
        "condition": request["condition"],
        "model_key": claude.MODEL_KEY,
        "shard_model_key": request["model_key"],
        "exact_requested_model": claude.REQUEST_MODEL,
        "actual_returned_model": "claude-sonnet-5",
        "prompt_hash": request["prompt_hash"],
        "attempt_type": attempt_type,
        "attempt_number": 1 if attempt_type == "primary" else 2,
        "transport_attempt_number": 1,
        "request_status": "completed",
        "raw_response_text": raw_text,
        "validation_status": validation_status,
        "response_schema_valid": valid,
        "validation_errors": [],
        "token_usage": {"input_tokens": 1, "output_tokens": 2, "reasoning_tokens": None, "total_tokens": 3},
        "latency_seconds": 0.1,
        "started_at": "2026-08-18T00:00:00+00:00",
        "ended_at": "2026-08-18T00:00:01+00:00",
        "provider_response_metadata": {"model": "claude-sonnet-5"},
        "failure_code": None if valid else validation_status,
        "failure_category": None if valid else "structural_validation",
        "retryable": False,
        "max_tokens": 1024,
        "thinking_disabled_sent": True,
        "temperature_sent": False,
        "top_p_sent": False,
        "top_k_sent": False,
        "seed_sent": False,
        "assistant_prefill_sent": False,
    }


def write_jsonl_for_test(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
