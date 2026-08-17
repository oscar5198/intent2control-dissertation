import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.inference.configuration import PRIMARY_INFERENCE_CONFIG_VERSION  # noqa: E402
from llm_experiments.inference.records import (  # noqa: E402
    ATTEMPT_SCHEMA_VERSION,
    EXECUTION_SUMMARY_SCHEMA_VERSION,
    PREDICTION_LOGGING_VERSION,
    PREDICTION_SCHEMA_VERSION,
    RUN_MANIFEST_SCHEMA_VERSION,
    JsonlAttemptLogger,
    contains_secret,
    create_run_manifest,
    finalize_prediction_record,
    hash_inference_config,
    hash_prompt_payload,
    load_resume_state,
    make_attempt_record,
    make_prediction_record_id,
    merge_run_logs,
    normalize_cost,
    normalize_usage,
    portable_artifact_path,
    read_jsonl,
    run_logged_synthetic_mock,
    sanitize_provider_metadata,
    write_execution_summary,
    write_json_atomic,
    write_jsonl,
    write_predictions,
)
from llm_experiments.inference.registry import load_model_registry, resolve_model  # noqa: E402
from llm_experiments.inference.requests import make_inference_request, make_inference_request_id  # noqa: E402
from llm_experiments.inference.responses import make_raw_result  # noqa: E402
from llm_experiments.inference.validation import validate_response_text  # noqa: E402
from llm_experiments.prompts.prompt_spec import load_jsonl  # noqa: E402


MODEL_REGISTRY = REPO_ROOT / "llm-experiments" / "config" / "phase6e1_model_registry.json"
RENDERED_PROMPTS = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6d2_rendered_prompts" / "rendered_prompts.jsonl"
RESPONSE_SCHEMA = REPO_ROOT / "llm-experiments" / "schema" / "preference_prediction_response_v1.json"
ATTEMPT_SCHEMA = REPO_ROOT / "llm-experiments" / "schema" / "phase6e_attempt_log_v1.json"
PREDICTION_SCHEMA = REPO_ROOT / "llm-experiments" / "schema" / "phase6e_prediction_record_v1.json"
MANIFEST_SCHEMA = REPO_ROOT / "llm-experiments" / "schema" / "phase6e_run_manifest_v1.json"
SUMMARY_SCHEMA = REPO_ROOT / "llm-experiments" / "schema" / "phase6e_execution_summary_v1.json"


VALID_TEXT = (
    '{"predicted_preferred_mix":"C","predicted_ratings":{"A":60,"B":45,'
    '"C":80,"D":70,"E":55},"predicted_ranking":["C","D","A","E","B"]}'
)
INVALID_TEXT = '{"predicted_preferred_mix":"F"}'


def test_logging_contract_versions_are_frozen():
    assert PREDICTION_LOGGING_VERSION == "phase6e_prediction_logging_v1"
    assert ATTEMPT_SCHEMA_VERSION == "phase6e_attempt_log_v1"
    assert PREDICTION_SCHEMA_VERSION == "phase6e_prediction_record_v1"
    assert RUN_MANIFEST_SCHEMA_VERSION == "phase6e_run_manifest_v1"
    assert EXECUTION_SUMMARY_SCHEMA_VERSION == "phase6e_execution_summary_v1"


def test_prediction_record_id_is_deterministic_and_scientific():
    first = make_prediction_record_id("ex1", "non_history", "gpt", PRIMARY_INFERENCE_CONFIG_VERSION)
    second = make_prediction_record_id("ex1", "non_history", "gpt", PRIMARY_INFERENCE_CONFIG_VERSION)
    other_condition = make_prediction_record_id("ex1", "personalised_history", "gpt", PRIMARY_INFERENCE_CONFIG_VERSION)
    assert first == second
    assert first != other_condition


def test_prompt_payload_hash_is_order_stable_for_canonical_payloads():
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    assert hash_prompt_payload(messages) == hash_prompt_payload(json.loads(json.dumps(messages)))


def test_inference_config_hash_ignores_operational_timestamps_and_urls():
    base = {
        "model_key": "gpt",
        "exact_model_id": "mock::gpt",
        "checkpoint_or_revision": "mock_v1",
        "inference_config_version": PRIMARY_INFERENCE_CONFIG_VERSION,
        "prompt_package_version": "phase6d_prompt_package_v1",
        "response_schema_version": "preference_prediction_response_v1",
        "temperature_requested": 0,
        "top_p_requested": None,
        "seed_requested": 20260814,
        "max_output_tokens": 256,
        "structured_output_strategy": "local_schema_validation",
        "started_at": "2026-08-14T00:00:00Z",
        "endpoint_url": "https://example.invalid",
    }
    changed = {**base, "started_at": "2026-08-15T00:00:00Z", "endpoint_url": "https://other.invalid"}
    assert hash_inference_config(base) == hash_inference_config(changed)


def test_inference_config_hash_changes_for_scientific_settings():
    base = sample_config()
    changed = {**base, "temperature_requested": 1}
    assert hash_inference_config(base) != hash_inference_config(changed)


def test_primary_valid_attempt_logs_core_provenance():
    attempt = sample_attempt()
    assert attempt["schema_version"] == ATTEMPT_SCHEMA_VERSION
    assert attempt["prediction_logging_version"] == PREDICTION_LOGGING_VERSION
    assert attempt["attempt_type"] == "primary"
    assert attempt["response_validation_status"] == "valid"
    assert attempt["prompt_payload_sha256"]
    assert attempt["inference_config_sha256"]


def test_repair_attempt_can_coexist_with_primary_attempt():
    primary = sample_attempt(raw_text=INVALID_TEXT)
    repair = sample_attempt(raw_text=VALID_TEXT, attempt_type="format_repair", attempt_number=2)
    assert primary["prediction_record_id"] == repair["prediction_record_id"]
    assert primary["inference_request_id"] != repair["inference_request_id"]


def test_final_record_references_successful_repair():
    prediction = finalize_prediction_record([
        sample_attempt(raw_text=INVALID_TEXT),
        sample_attempt(raw_text=VALID_TEXT, attempt_type="format_repair", attempt_number=2),
    ])
    assert prediction["final_status"] == "valid_after_repair"
    assert prediction["repair_attempt_id"] == make_repair_request()["inference_request_id"]
    assert prediction["predicted_preferred_mix"] == "C"


def test_invalid_after_repair_is_represented():
    prediction = finalize_prediction_record([
        sample_attempt(raw_text=INVALID_TEXT),
        sample_attempt(raw_text=INVALID_TEXT, attempt_type="format_repair", attempt_number=2),
    ])
    assert prediction["final_status"] == "invalid_after_repair"
    assert prediction["predicted_preferred_mix"] is None


def test_backend_failure_is_represented():
    prediction = finalize_prediction_record([sample_attempt(raw_text=None, request_status="error")])
    assert prediction["final_status"] == "backend_failed"
    assert prediction["raw_final_response_text"] is None


def test_raw_response_is_preserved_separately_from_parsed_prediction():
    attempt = sample_attempt(raw_text=VALID_TEXT)
    prediction = finalize_prediction_record([attempt])
    assert prediction["raw_final_response_text"] == VALID_TEXT
    assert prediction["predicted_rating_C"] == 80
    assert attempt["extracted_model_text"] == VALID_TEXT


def test_token_null_and_zero_are_distinct():
    assert normalize_usage(None) == {"input_tokens": None, "output_tokens": None, "total_tokens": None}
    assert normalize_usage({"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}) == {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


def test_cost_null_and_zero_are_distinct():
    assert normalize_cost(None)["total_cost"] is None
    assert normalize_cost({"total_cost": 0, "cost_source": "provider"})["total_cost"] == 0


def test_latency_numeric_or_nullable_in_attempts():
    no_latency = sample_attempt(latency=None)
    zero_latency = sample_attempt(latency={"total_seconds": 0.0, "source": "local_mock"})
    assert no_latency["latency_seconds"] is None
    assert zero_latency["latency_seconds"] == 0.0


def test_provider_metadata_sanitizes_credentials_but_preserves_token_usage():
    clean = sanitize_provider_metadata({"authorization": "Bearer sk-test", "nested": {"token_usage": 3}})
    assert clean["authorization"] == "[REDACTED]"
    assert clean["nested"]["token_usage"] == 3
    assert contains_secret(clean) is False


def test_logger_blocks_exact_duplicate_attempts(tmp_path):
    logger = JsonlAttemptLogger(tmp_path)
    attempt = sample_attempt()
    logger.log_attempt(attempt)
    try:
        logger.log_attempt(attempt)
    except ValueError as exc:
        assert "Duplicate completed attempt blocked" in str(exc)
    else:
        raise AssertionError("Expected exact duplicate attempt to be blocked.")


def test_logger_detects_conflicting_duplicate_attempts(tmp_path):
    logger = JsonlAttemptLogger(tmp_path)
    attempt = sample_attempt()
    logger.log_attempt(attempt)
    conflicting = {**attempt, "raw_response_text": "{}"}
    try:
        logger.log_attempt(conflicting)
    except ValueError as exc:
        assert "Conflicting duplicate attempt detected" in str(exc)
    else:
        raise AssertionError("Expected conflicting duplicate attempt to fail.")


def test_resume_state_reconstructs_completed_and_failed_predictions(tmp_path):
    attempt = sample_attempt()
    logger = JsonlAttemptLogger(tmp_path)
    logger.log_attempt(attempt)
    write_predictions(tmp_path, [attempt])
    state = load_resume_state(tmp_path)
    assert state["completed_primary_attempts"] == [attempt["inference_request_id"]]
    assert state["failed_predictions"] == []


def test_run_manifest_is_generated_with_repo_relative_dataset_path():
    manifest = create_run_manifest("run", "synthetic_mock", RENDERED_PROMPTS, 22, ["gpt"], 22)
    assert manifest["schema_version"] == RUN_MANIFEST_SCHEMA_VERSION
    assert manifest["rendered_prompt_dataset"]["path"].startswith("llm-experiments/")
    assert "C:\\Users\\oscar" not in json.dumps(manifest)


def test_execution_summary_counts_statuses(tmp_path):
    attempts = [sample_attempt()]
    predictions = write_predictions(tmp_path, attempts)
    manifest = create_run_manifest("run", "synthetic_mock", RENDERED_PROMPTS, 1, ["gpt"], 1)
    summary = write_execution_summary(tmp_path, manifest, attempts, predictions)
    assert summary["schema_version"] == EXECUTION_SUMMARY_SCHEMA_VERSION
    assert summary["valid_primary"] == 1
    assert summary["contains_ground_truth"] is False


def test_synthetic_logged_mock_run_creates_88_attempts_and_predictions(tmp_path):
    summary = run_logged_synthetic_mock(REPO_ROOT, output_root=tmp_path)
    run_dir = tmp_path / "phase6e3_synthetic_mock_run"
    assert summary["attempts_total"] == 88
    assert summary["predictions_attempted"] == 88
    assert len(read_jsonl(run_dir / "attempt_log.jsonl")) == 88
    assert len(read_jsonl(run_dir / "predictions.jsonl")) == 88
    assert (run_dir / "raw_responses").is_dir()


def test_logged_mock_run_never_requires_ground_truth(tmp_path):
    summary = run_logged_synthetic_mock(REPO_ROOT, output_root=tmp_path)
    assert summary["contains_ground_truth"] is False
    serialized = (tmp_path / "phase6e3_synthetic_mock_run" / "execution_summary.json").read_text(encoding="utf-8")
    assert "participant_outcome" not in serialized
    assert "true_preference" not in serialized
    assert "observed_preferred_mix" not in serialized


def test_controlled_multi_attempt_fixtures_are_written(tmp_path):
    run_logged_synthetic_mock(REPO_ROOT, output_root=tmp_path)
    fixture_dir = tmp_path / "controlled_multi_attempt_fixtures"
    assert sorted(path.name for path in fixture_dir.glob("*.json")) == [
        "backend_failure.json",
        "primary_invalid_repair_invalid.json",
        "primary_invalid_repair_valid.json",
        "primary_valid.json",
    ]


def test_distributed_merge_combines_non_conflicting_logs(tmp_path):
    left = make_run_dir(tmp_path / "left", [sample_attempt()])
    right = make_run_dir(tmp_path / "right", [sample_attempt(model_key="centaur")])
    result = merge_run_logs([left, right], tmp_path / "merged")
    assert result["attempt_count"] == 2
    assert result["prediction_count"] == 2


def test_merge_rejects_incompatible_prompt_package(tmp_path):
    bad = {**sample_attempt(), "prompt_package_version": "wrong"}
    run_dir = make_run_dir(tmp_path / "bad", [bad])
    expect_merge_error([run_dir], tmp_path / "merged", "incompatible prompt package")


def test_merge_rejects_incompatible_config_version(tmp_path):
    attempt = sample_attempt()
    run_dir = make_run_dir(tmp_path / "bad", [attempt])
    prediction = read_jsonl(run_dir / "predictions.jsonl")[0]
    prediction["inference_config_version"] = "wrong"
    write_jsonl(run_dir / "predictions.jsonl", [prediction])
    expect_merge_error([run_dir], tmp_path / "merged", "incompatible config version")


def test_merge_rejects_mixed_synthetic_and_production_run_types(tmp_path):
    left = make_run_dir(tmp_path / "left", [sample_attempt()], run_type="synthetic_mock")
    right = make_run_dir(tmp_path / "right", [sample_attempt(model_key="centaur")], run_type="production")
    expect_merge_error([left, right], tmp_path / "merged", "mixed real/synthetic run types")


def test_merge_rejects_missing_model_identity(tmp_path):
    bad = {**sample_attempt(), "exact_model_id": None}
    run_dir = make_run_dir(tmp_path / "bad", [bad])
    expect_merge_error([run_dir], tmp_path / "merged", "missing model identity")


def test_canonical_logs_do_not_contain_absolute_user_paths(tmp_path):
    run_logged_synthetic_mock(REPO_ROOT, output_root=tmp_path)
    run_dir = tmp_path / "phase6e3_synthetic_mock_run"
    text = "\n".join(
        [
            (run_dir / "run_manifest.json").read_text(encoding="utf-8"),
            (run_dir / "attempt_log.jsonl").read_text(encoding="utf-8"),
            (run_dir / "predictions.jsonl").read_text(encoding="utf-8"),
            (run_dir / "execution_summary.json").read_text(encoding="utf-8"),
        ]
    )
    assert "C:\\Users\\oscar" not in text
    assert "/Users/oscar" not in text


def test_phase6e3_schemas_accept_representative_outputs(tmp_path):
    attempt = sample_attempt()
    prediction = finalize_prediction_record([attempt])
    manifest = create_run_manifest("run", "synthetic_mock", RENDERED_PROMPTS, 1, ["gpt"], 1)
    summary = write_execution_summary(tmp_path, manifest, [attempt], [prediction])
    for payload, schema_path in [
        (attempt, ATTEMPT_SCHEMA),
        (prediction, PREDICTION_SCHEMA),
        (manifest, MANIFEST_SCHEMA),
        (summary, SUMMARY_SCHEMA),
    ]:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        assert list(Draft202012Validator(schema).iter_errors(payload)) == []


def test_portable_artifact_path_preserves_repo_artifact_segment():
    assert portable_artifact_path(RENDERED_PROMPTS).startswith("llm-experiments/")


def sample_config():
    return {
        "model_key": "gpt",
        "exact_model_id": "mock::gpt",
        "checkpoint_or_revision": "mock_v1",
        "inference_config_version": PRIMARY_INFERENCE_CONFIG_VERSION,
        "prompt_package_version": "phase6d_prompt_package_v1",
        "response_schema_version": "preference_prediction_response_v1",
        "temperature_requested": 0,
        "top_p_requested": None,
        "seed_requested": 20260814,
        "max_output_tokens": 256,
        "structured_output_strategy": "local_schema_validation",
    }


def sample_request(model_key="gpt", attempt_type="primary", attempt_number=1):
    rendered = load_jsonl(RENDERED_PROMPTS)[0]
    model = {**resolve_model(model_key, load_model_registry(MODEL_REGISTRY)), "default_backend_key": "mock"}
    request = make_inference_request(rendered, model, inference_config_version=PRIMARY_INFERENCE_CONFIG_VERSION)
    if attempt_type != "primary" or attempt_number != 1:
        request = {**request, "attempt_type": attempt_type, "attempt_number": attempt_number}
        request["inference_request_id"] = make_inference_request_id(
            request["rendered_prompt_id"],
            request["model_key"],
            request["inference_config_id"],
            attempt_type,
            attempt_number,
        )
    return request


def make_repair_request():
    return sample_request(attempt_type="format_repair", attempt_number=2)


def sample_attempt(raw_text=VALID_TEXT, request_status="completed", attempt_type="primary", attempt_number=1, model_key="gpt", latency=None):
    request = sample_request(model_key=model_key, attempt_type=attempt_type, attempt_number=attempt_number)
    schema = json.loads(RESPONSE_SCHEMA.read_text(encoding="utf-8"))
    raw_result = make_raw_result(
        request,
        "mock",
        request_status,
        raw_response_text=raw_text,
        provider_response_metadata={"finish_reason": "stop"},
        usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        latency=latency,
        error={"type": "connection_error", "message": "network unavailable"} if request_status == "error" else None,
    )
    validation = validate_response_text(raw_text, schema)
    return make_attempt_record(
        request,
        raw_result,
        validation,
        model_identity={"exact_model_id": f"mock::{model_key}", "checkpoint_or_revision": "mock_v1"},
        backend_provenance={"deployment_environment": "mock", "serving_mode": "deterministic_mock"},
        request_parameters=sample_config(),
        run_id="test_run",
    )


def make_run_dir_with_type(path: Path, attempts: list[dict], run_type: str):
    manifest = create_run_manifest("run", run_type, RENDERED_PROMPTS, len(attempts), sorted({row["model_key"] for row in attempts}), len(attempts))
    write_json_atomic(path / "run_manifest.json", manifest)
    write_jsonl(path / "attempt_log.jsonl", attempts)
    write_jsonl(path / "predictions.jsonl", [finalize_prediction_record([attempt]) for attempt in attempts])
    return path


def make_run_dir(path: Path, attempts: list[dict], run_type: str = "synthetic_mock"):
    return make_run_dir_with_type(path, attempts, run_type)


def expect_merge_error(source_run_dirs, output_dir, expected):
    try:
        merge_run_logs(source_run_dirs, output_dir)
    except ValueError as exc:
        assert expected in str(exc)
    else:
        raise AssertionError(f"Expected merge error containing {expected!r}.")
