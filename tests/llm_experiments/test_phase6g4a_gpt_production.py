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
DIAGNOSTIC_256 = REPO_ROOT / gpt4a.DIAGNOSTIC_256_RUN_DIR
DIAGNOSTIC_1024 = REPO_ROOT / gpt4a.DIAGNOSTIC_1024_RUN_DIR
CONFIG_CORRECTION = REPO_ROOT / gpt4a.CONFIGURATION_CORRECTION_MANIFEST
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


def test_final_gpt_max_output_tokens_4096_and_config_correction_manifest() -> None:
    correction = load_json(CONFIG_CORRECTION)
    manifest = load_json(RUN_MANIFEST)

    assert gpt4a.MAX_OUTPUT_TOKENS == 4096
    assert manifest["max_output_tokens"] == 4096
    assert correction["initial_max_output_tokens"] == 256
    assert correction["prior_max_output_tokens"] == 1024
    assert correction["new_max_output_tokens"] == 4096
    assert correction["correction_type"] == "execution_compatibility_correction"
    assert correction["scope"] == "gpt_only"
    assert correction["guarded_validation_evidence"]["diagnostic_256_to_1024"]["incomplete_at_exact_prior_budget_count"] == 2
    assert correction["guarded_validation_evidence"]["diagnostic_1024_to_4096"]["valid_primary_count"] == 2
    assert correction["guarded_validation_evidence"]["diagnostic_1024_to_4096"]["output_budget_exhausted_count"] == 1
    assert correction["guarded_validation_evidence"]["diagnostic_1024_to_4096"]["transport_failure_count"] == 0
    assert correction["guarded_validation_evidence"]["diagnostic_1024_to_4096"]["formatting_repair_count"] == 0
    assert correction["scientific_policy"]["no_human_ground_truth_inspected"] is True
    assert correction["scientific_policy"]["no_prediction_accuracy_used"] is True
    assert correction["scientific_policy"]["provider_native_reasoning_preserved"] is True
    assert correction["scientific_policy"]["reasoning_effort_set"] is False
    assert correction["inference_config_hash_prior"] != correction["inference_config_hash_new"]
    assert_no_secrets(correction)


def test_prompt_schema_and_model_identity_unchanged_by_budget_correction() -> None:
    manifest = load_json(RUN_MANIFEST)

    assert manifest["exact_requested_model"] == "gpt-5.5"
    assert manifest["expected_returned_model"] == "gpt-5.5-2026-04-23"
    assert manifest["temperature_sent"] is False
    assert manifest["top_p_sent"] is False
    assert manifest["seed_sent"] is False
    assert manifest["reasoning_effort_sent"] is False
    assert manifest["rendered_prompt_dataset"].endswith("phase6g3_real_rendered_prompts.jsonl")
    assert gpt4a.RESPONSE_SCHEMA.name == "preference_prediction_response_v1.json"
    assert load_json(CONFIG_CORRECTION)["scientific_policy"]["rendered_prompts_changed"] is False
    assert load_json(CONFIG_CORRECTION)["scientific_policy"]["response_schema_changed"] is False
    assert load_json(CONFIG_CORRECTION)["scientific_policy"]["model_identity_changed"] is False
    assert load_json(CONFIG_CORRECTION)["scientific_policy"]["decoding_policy_changed"] is False


def test_corrected_run_03_namespace_records_authoritative_completed_run() -> None:
    summary = load_json(SUMMARY)
    manifest = load_json(RUN_MANIFEST)

    assert manifest["run_id"] == "phase6g4a_gpt_corrected_run_03"
    assert manifest["output_dir"].endswith("phase6g4/gpt/corrected_run_03")
    assert summary["preflight_passed"] is True
    assert summary["attempted_prediction_count"] == 396
    assert summary["terminal_prediction_count"] == 396
    assert summary["valid_primary_count"] == 264
    assert summary["backend_failure_count"] == 126
    assert summary["output_budget_exhausted_count"] == 6
    assert summary["remaining_predictions"] == 0
    assert (OUT / "attempt_log.jsonl").exists()
    assert (OUT / "predictions.jsonl").exists()


def test_prior_diagnostic_runs_preserved_as_non_scientific_evidence() -> None:
    assert DIAGNOSTIC_256.exists()
    assert DIAGNOSTIC_1024.exists()
    run01_manifest_path = DIAGNOSTIC_256 / "run_manifest.json"
    run02_manifest_path = DIAGNOSTIC_1024 / "run_manifest.json"
    if run01_manifest_path.exists():
        run01 = load_json(run01_manifest_path)
        assert run01["run_id"] == "phase6g4a_gpt_corrected_run_01"
        assert run01["output_dir"].endswith("phase6g4/gpt/corrected_run_01")
        assert run01["max_output_tokens"] == 256
    if run02_manifest_path.exists():
        run02 = load_json(run02_manifest_path)
        assert run02["run_id"] == "phase6g4a_gpt_corrected_run_02"
        assert run02["output_dir"].endswith("phase6g4/gpt/corrected_run_02")
        assert run02["max_output_tokens"] == 1024
    correction = load_json(CONFIG_CORRECTION)
    assert correction["initial_diagnostic_run_namespace"].endswith("phase6g4/gpt/corrected_run_01")
    assert correction["prior_run_namespace"].endswith("phase6g4/gpt/corrected_run_02")
    assert correction["scientific_policy"]["diagnostic_256_token_run_is_final_scientific_gpt_run"] is False
    assert correction["scientific_policy"]["diagnostic_1024_token_run_is_final_scientific_gpt_run"] is False


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
    out = tmp_path / "phase6g4" / "gpt" / "corrected_run_03"

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


def test_incomplete_max_output_tokens_classified_without_repair(monkeypatch, tmp_path) -> None:
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
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "output_text": '{"predicted_preferred_mix":"C","predicted_ratings":{"A":58,"B":72,"C":80,"D":',
            "metadata": {"model": "gpt-5.5-2026-04-23", "request_api": "OpenAI.responses.create"},
            "usage": {"input_tokens": 10, "output_tokens": 1024, "total_tokens": 1034, "output_tokens_details": {"reasoning_tokens": 900}},
        }

    monkeypatch.setattr(gpt4a, "run_preflight", fake_preflight)
    monkeypatch.setattr(gpt4a, "invoke_openai", fake_invoke)
    out = tmp_path / "phase6g4" / "gpt" / "corrected_run_03"

    summary = gpt4a.run_gpt_production(REPO_ROOT, guarded_batch_size=1, output_dir=out, run_id="test_corrected_run_03")

    attempts = load_jsonl(out / "attempt_log.jsonl")
    predictions = load_jsonl(out / "predictions.jsonl")
    assert calls["count"] == 1
    assert len(attempts) == 1
    assert attempts[0]["request_status"] == "incomplete"
    assert attempts[0]["failure_code"] == "output_budget_exhausted"
    assert attempts[0]["failure_category"] == "output_budget"
    assert attempts[0]["retryable"] is False
    assert attempts[0]["output_budget_exhausted"] is True
    assert attempts[0]["incomplete_details"]["reason"] == "max_output_tokens"
    assert predictions[0]["final_status"] == "output_budget_exhausted"
    assert predictions[0]["formatting_repair_count"] == 0
    assert summary["output_budget_exhausted_count"] == 1


def test_provider_native_reasoning_and_sampling_controls_omitted(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                status="completed",
                output_text='{"predicted_preferred_mix":"A","predicted_ratings":{"A":80,"B":60,"C":55,"D":50,"E":45},"predicted_ranking":["A","B","C","D","E"]}',
                model="gpt-5.5-2026-04-23",
                usage={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
                incomplete_details=None,
            )

    class FakeClient:
        def __init__(self):
            self.responses = FakeResponses()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeClient))

    result = gpt4a.invoke_openai([{"role": "system", "content": "s"}, {"role": "user", "content": "u"}], "primary")

    assert result["status"] == "completed"
    assert captured["model"] == "gpt-5.5"
    assert captured["max_output_tokens"] == 4096
    assert captured["instructions"] == "s"
    assert captured["input"] == "u"
    assert "reasoning" not in captured
    assert "reasoning_effort" not in captured
    assert "temperature" not in captured
    assert "top_p" not in captured
    assert "seed" not in captured


def test_gpt_shard_is_gpt_only_and_has_expected_coverage() -> None:
    shard = load_json(GPT_SHARD)

    assert shard["request_count"] == 396
    assert set(row["model_key"] for row in shard["requests"]) == {"gpt"}
    assert sum(1 for row in shard["requests"] if row["condition"] == "non_history") == 198
    assert sum(1 for row in shard["requests"] if row["condition"] == "personalised_history") == 198
    assert len({row["request_id"] for row in shard["requests"]}) == 396


def test_no_ground_truth_or_secrets_are_serialized() -> None:
    for path in [RUN_MANIFEST, PREFLIGHT, SUMMARY, ARCHIVE / "recovery_manifest.json", CONFIG_CORRECTION]:
        payload = load_json(path)
        assert_no_secrets(payload)
        text = json.dumps(payload).lower()
        assert "final_trial_ground_truth" not in text
        assert "final_candidate_ground_truth" not in text
    assert "OPENAI_API_KEY" not in QC_REPORT.read_text(encoding="utf-8")


def test_qc_report_records_recovery_guardrails() -> None:
    text = QC_REPORT.read_text(encoding="utf-8")

    assert "Preflight passed: `true`" in text
    assert "Attempted predictions: `396`" in text
    assert "Output-budget exhausted: `6`" in text
    assert "accuracy:" not in text.lower()
