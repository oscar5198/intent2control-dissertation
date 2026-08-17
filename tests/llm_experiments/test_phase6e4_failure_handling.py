import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.inference.adapters.mock import MockAdapter  # noqa: E402
from llm_experiments.inference.configuration import PRIMARY_INFERENCE_CONFIG_VERSION  # noqa: E402
from llm_experiments.inference.failures import (  # noqa: E402
    FAILURE_HANDLING_VERSION,
    classify_failure,
    is_retryable,
    should_repair,
)
from llm_experiments.inference.records import JsonlAttemptLogger, finalize_prediction_record, read_jsonl, write_predictions  # noqa: E402
from llm_experiments.inference.registry import load_backend_registry, load_model_registry, resolve_backend, resolve_model  # noqa: E402
from llm_experiments.inference.requests import make_inference_request  # noqa: E402
from llm_experiments.inference.retry import default_failure_policy, should_retry_transport  # noqa: E402
from llm_experiments.inference.runner import build_execution_manifest  # noqa: E402
from llm_experiments.inference.state_machine import (  # noqa: E402
    production_failure_handler_preflight,
    resume_prediction,
    run_synthetic_failure_matrix,
)
from llm_experiments.prompts.render import render_format_repair  # noqa: E402
from llm_experiments.prompts.prompt_spec import load_jsonl  # noqa: E402


MODEL_REGISTRY = REPO_ROOT / "llm-experiments" / "config" / "phase6e1_model_registry.json"
BACKEND_REGISTRY = REPO_ROOT / "llm-experiments" / "config" / "phase6e1_backend_registry.json"
RENDERED_PROMPTS = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6d2_rendered_prompts" / "rendered_prompts.jsonl"
RESPONSE_SCHEMA = REPO_ROOT / "llm-experiments" / "schema" / "preference_prediction_response_v1.json"


def test_valid_primary_reaches_terminal_valid_primary(tmp_path):
    prediction, attempts = execute_case(tmp_path, ["valid_response"])
    assert prediction["final_status"] == "valid_primary"
    assert len(attempts) == 1


def test_invalid_json_gets_one_repair_and_valid_after_repair(tmp_path):
    prediction, attempts = execute_case(tmp_path, ["invalid_json"], repair_mode="valid_response")
    assert prediction["final_status"] == "valid_after_repair"
    assert [row["attempt_type"] for row in attempts] == ["primary", "format_repair"]


def test_schema_invalid_gets_one_repair_and_valid_after_repair(tmp_path):
    prediction, attempts = execute_case(tmp_path, ["schema_invalid"], repair_mode="valid_response")
    assert prediction["final_status"] == "valid_after_repair"
    assert attempts[0]["response_validation_status"] == "schema_invalid"


def test_invalid_primary_and_invalid_repair_becomes_invalid_after_repair(tmp_path):
    prediction, attempts = execute_case(tmp_path, ["invalid_json"], repair_mode="invalid_json")
    assert prediction["final_status"] == "invalid_after_repair"
    assert prediction["predicted_preferred_mix"] is None
    assert len(attempts) == 2


def test_no_third_generation_after_failed_repair(tmp_path):
    prediction, attempts = execute_case(tmp_path, ["invalid_json"], repair_mode="invalid_json")
    rerun, rerun_attempts = execute_case(tmp_path, ["valid_response"], repair_mode="valid_response", resume=True)
    assert prediction["final_status"] == rerun["final_status"] == "invalid_after_repair"
    assert len(attempts) == len(rerun_attempts) == 2
    assert rerun["format_repair_attempt_count"] == 1


def test_timeout_retries_then_succeeds(tmp_path):
    prediction, attempts = execute_case(tmp_path, ["timeout", "valid_response"])
    assert prediction["final_status"] == "valid_primary"
    assert [row["attempt_status"] for row in attempts] == ["timeout", "valid"]


def test_timeout_retry_limit_enforced(tmp_path):
    prediction, attempts = execute_case(tmp_path, ["timeout", "timeout", "timeout", "valid_response"])
    assert prediction["final_status"] == "backend_failed"
    assert len(attempts) == 3
    assert prediction["transport_retry_count"] == 2


def test_http_5xx_is_retryable(tmp_path):
    prediction, attempts = execute_case(tmp_path, ["http_500", "valid_response"])
    assert prediction["final_status"] == "valid_primary"
    assert attempts[0]["failure_code"] == "http_server_error"


def test_http_429_rate_limit_is_retryable(tmp_path):
    prediction, attempts = execute_case(tmp_path, ["rate_limited", "valid_response"])
    assert prediction["final_status"] == "valid_primary"
    assert attempts[0]["failure_code"] == "rate_limited"
    assert attempts[0]["provider_response_metadata"]["retry_after_seconds"] == 1


def test_http_400_is_non_retryable(tmp_path):
    prediction, attempts = execute_case(tmp_path, ["http_400", "valid_response"])
    assert prediction["final_status"] == "backend_failed"
    assert len(attempts) == 1
    assert attempts[0]["failure_code"] == "http_client_error"


def test_auth_failure_is_non_retryable_and_sanitized(tmp_path):
    prediction, attempts = execute_case(tmp_path, ["auth_failure", "valid_response"])
    assert prediction["final_status"] == "backend_failed"
    assert len(attempts) == 1
    assert attempts[0]["failure_code"] == "bad_credentials"
    assert attempts[0]["safe_error_message"] == "[REDACTED]"


def test_empty_response_retries_without_repair(tmp_path):
    prediction, attempts = execute_case(tmp_path, ["empty_response", "valid_response"])
    assert prediction["final_status"] == "valid_primary"
    assert attempts[0]["failure_code"] == "empty_response"
    assert all(row["attempt_type"] == "primary" for row in attempts)


def test_connection_error_retry_behavior_exhausts(tmp_path):
    prediction, attempts = execute_case(tmp_path, ["connection_error", "connection_error", "connection_error"])
    assert prediction["final_status"] == "backend_failed"
    assert len(attempts) == 3


def test_transport_retry_does_not_count_as_repair(tmp_path):
    prediction, _attempts = execute_case(tmp_path, ["timeout", "valid_response"])
    assert prediction["scientific_generation_count"] == 1
    assert prediction["format_repair_attempt_count"] == 0


def test_repair_uses_same_model_backend_config(tmp_path):
    prediction, attempts = execute_case(tmp_path, ["invalid_json"], repair_mode="valid_response", model_key="centaur")
    primary, repair = attempts
    assert prediction["final_status"] == "valid_after_repair"
    assert primary["model_key"] == repair["model_key"] == "centaur"
    assert primary["backend_key"] == repair["backend_key"] == "mock"
    assert primary["inference_config_version"] == repair["inference_config_version"]


def test_repair_prompt_contains_no_participant_or_ground_truth_additions():
    schema = json.loads(RESPONSE_SCHEMA.read_text(encoding="utf-8"))
    prompt = render_format_repair("not json", schema)
    text = "\n".join(message["content"] for message in prompt["messages"])
    assert "Invalid response to repair:" in text
    assert "Required response schema:" in text
    assert "ground truth" in text
    assert "Participant rating:" not in text
    assert "Previous listening evidence" not in text
    assert "observed_preferred_mix" not in text


def test_raw_primary_and_repair_outputs_both_preserved(tmp_path):
    _prediction, attempts = execute_case(tmp_path, ["invalid_json"], repair_mode="valid_response")
    assert attempts[0]["raw_response_text"] == "This is not JSON"
    assert "predicted_preferred_mix" in attempts[1]["raw_response_text"]


def test_successful_attempt_linked_to_repair(tmp_path):
    prediction, attempts = execute_case(tmp_path, ["invalid_json"], repair_mode="valid_response")
    assert prediction["successful_attempt_id"] == attempts[1]["inference_request_id"]
    assert prediction["repair_attempt_id"] == attempts[1]["inference_request_id"]


def test_resume_valid_primary_does_nothing(tmp_path):
    first, attempts = execute_case(tmp_path, ["valid_response"])
    second, resumed = execute_case(tmp_path, ["timeout"], resume=True)
    assert first == second
    assert attempts == resumed


def test_resume_repair_pending_executes_one_repair(tmp_path):
    request = sample_request()
    policy = default_failure_policy(REPO_ROOT)
    schema = json.loads(RESPONSE_SCHEMA.read_text(encoding="utf-8"))
    logger = JsonlAttemptLogger(tmp_path, resume=True)
    adapter = MockAdapter({**resolve_backend("mock", load_backend_registry(BACKEND_REGISTRY)), "mock_sequence": ["invalid_json"]})
    resume_prediction(request, adapter, schema, {**policy, "max_format_repair_generations": 0}, logger, "test_run", model_identity("gpt"), backend_provenance(), request_parameters())
    repair_adapter = MockAdapter({**resolve_backend("mock", load_backend_registry(BACKEND_REGISTRY)), "mock_repair_mode": "valid_response"})
    prediction = resume_prediction(request, repair_adapter, schema, policy, logger, "test_run", model_identity("gpt"), backend_provenance(), request_parameters())
    assert prediction["final_status"] == "valid_after_repair"
    assert len(read_jsonl(tmp_path / "attempt_log.jsonl")) == 2


def test_resume_terminal_invalid_does_nothing(tmp_path):
    first, attempts = execute_case(tmp_path, ["invalid_json"], repair_mode="invalid_json")
    second, resumed = execute_case(tmp_path, ["valid_response"], repair_mode="valid_response", resume=True)
    assert first == second
    assert attempts == resumed


def test_crash_recovery_reconstructs_state_from_attempt_log(tmp_path):
    prediction, attempts = execute_case(tmp_path, ["invalid_json"], repair_mode="valid_response")
    predictions = write_predictions(tmp_path, attempts)
    assert predictions[0]["final_status"] == prediction["final_status"]


def test_idempotent_rerun_does_not_duplicate_attempts(tmp_path):
    execute_case(tmp_path, ["timeout", "valid_response"])
    _prediction, attempts = execute_case(tmp_path, ["timeout", "valid_response"], resume=True)
    assert len(attempts) == 2
    assert len({row["inference_request_id"] for row in attempts}) == 2


def test_distributed_merge_preserves_repair_relationships(tmp_path):
    from llm_experiments.inference.records import merge_run_logs, write_json_atomic, write_jsonl

    prediction, attempts = execute_case(tmp_path / "left", ["invalid_json"], repair_mode="valid_response")
    manifest = {"run_id": "left", "run_type": "synthetic_mock", "expected_request_count": 1}
    write_json_atomic(tmp_path / "left" / "run_manifest.json", manifest)
    write_jsonl(tmp_path / "left" / "predictions.jsonl", [prediction])
    result = merge_run_logs([tmp_path / "left"], tmp_path / "merged")
    merged_prediction = read_jsonl(tmp_path / "merged" / "predictions.jsonl")[0]
    assert result["attempt_count"] == 2
    assert merged_prediction["repair_attempt_id"] == attempts[1]["inference_request_id"]


def test_terminal_run_completion_gate_true_on_failure_matrix(tmp_path):
    summary = run_synthetic_failure_matrix(REPO_ROOT, output_root=tmp_path)
    assert summary["INFERENCE_RUN_COMPLETE"] is True


def test_valid_prediction_completeness_gate_false_when_failures_exist(tmp_path):
    summary = run_synthetic_failure_matrix(REPO_ROOT, output_root=tmp_path)
    assert summary["ALL_EXPECTED_PREDICTIONS_VALID"] is False


def test_blocked_production_gate_still_enforced():
    result = production_failure_handler_preflight(REPO_ROOT)
    assert result["production_inference_allowed"] is False
    assert result["blocked_by_preflight"] is True
    try:
        build_execution_manifest(REPO_ROOT, allow_real_backends=True)
    except RuntimeError as exc:
        assert "production preflight failed" in str(exc)
    else:
        raise AssertionError("Expected production preflight to block real inference.")


def test_credentials_sanitized_in_retry_error_classification(tmp_path):
    _prediction, attempts = execute_case(tmp_path, ["auth_failure"])
    assert attempts[0]["safe_error_message"] == "[REDACTED]"
    assert "sk-test" not in json.dumps(attempts[0])


def test_execution_summary_failure_counts_are_correct(tmp_path):
    summary = run_synthetic_failure_matrix(REPO_ROOT, output_root=tmp_path)
    assert summary["valid_primary"] == 5
    assert summary["valid_after_repair"] == 2
    assert summary["invalid"] == 1
    assert summary["backend_failures"] == 4
    assert summary["total_transport_retries"] == 8
    assert summary["total_formatting_repairs"] == 3


def test_failure_taxonomy_retryable_and_non_retryable_codes():
    assert is_retryable("timeout") is True
    assert is_retryable("rate_limited") is True
    assert is_retryable("http_client_error") is False
    assert classify_failure({"status": "error", "error": {"http_status_code": 500}}, {})["failure_code"] == "http_server_error"


def test_repair_eligibility_is_structural_only():
    assert should_repair("invalid_json", "completed", "bad") is True
    assert should_repair("schema_invalid", "completed", "{}") is True
    assert should_repair("missing_response", "completed", "") is False
    assert should_repair("valid", "completed", "{}") is False


def test_transport_retry_policy_is_bounded():
    policy = default_failure_policy(REPO_ROOT)
    assert should_retry_transport("timeout", 1, policy) is True
    assert should_retry_transport("timeout", 2, policy) is True
    assert should_retry_transport("timeout", 3, policy) is False
    assert should_retry_transport("http_client_error", 1, policy) is False


def execute_case(tmp_path, sequence, repair_mode=None, model_key="gpt", resume=False):
    request = sample_request(model_key)
    policy = default_failure_policy(REPO_ROOT)
    schema = json.loads(RESPONSE_SCHEMA.read_text(encoding="utf-8"))
    logger = JsonlAttemptLogger(tmp_path, resume=resume)
    adapter = MockAdapter({**resolve_backend("mock", load_backend_registry(BACKEND_REGISTRY)), "mock_sequence": sequence, "mock_repair_mode": repair_mode})
    prediction = resume_prediction(request, adapter, schema, policy, logger, "test_run", model_identity(model_key), backend_provenance(), request_parameters())
    attempts = [row for row in read_jsonl(tmp_path / "attempt_log.jsonl") if row["prediction_record_id"] == prediction["prediction_record_id"]]
    return prediction, attempts


def sample_request(model_key="gpt"):
    rendered = load_jsonl(RENDERED_PROMPTS)[0]
    model = {**resolve_model(model_key, load_model_registry(MODEL_REGISTRY)), "default_backend_key": "mock", "inference_config_version": PRIMARY_INFERENCE_CONFIG_VERSION}
    request = make_inference_request(rendered, model, inference_config_version=PRIMARY_INFERENCE_CONFIG_VERSION)
    request["failure_handling_version"] = FAILURE_HANDLING_VERSION
    return request


def model_identity(model_key):
    return {"exact_model_id": f"mock::{model_key}", "checkpoint_or_revision": "mock_v1"}


def backend_provenance():
    return {"deployment_environment": "mock", "serving_mode": "deterministic_failure_test"}


def request_parameters():
    return {
        "temperature_requested": 0,
        "top_p_requested": None,
        "seed_requested": 20260814,
        "max_output_tokens": 256,
        "structured_output_strategy": "local_schema_validation",
        "parameter_snapshot": {"failure_handling_version": FAILURE_HANDLING_VERSION},
    }
