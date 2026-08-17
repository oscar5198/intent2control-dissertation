import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.inference.adapters import MockAdapter, QMULAdapter, RunPodAdapter  # noqa: E402
from llm_experiments.inference.base import ModelAdapter  # noqa: E402
from llm_experiments.inference.registry import (  # noqa: E402
    PLACEHOLDER_MODEL_ID,
    assert_no_secrets,
    backend_specs_by_key,
    load_backend_registry,
    load_model_registry,
    resolve_backend,
    resolve_model,
)
from llm_experiments.inference.requests import (  # noqa: E402
    DEFAULT_INFERENCE_CONFIG_VERSION,
    INFERENCE_INTERFACE_VERSION,
    make_inference_request,
    make_inference_request_id,
)
from llm_experiments.inference.responses import make_raw_result  # noqa: E402
from llm_experiments.inference.runner import (  # noqa: E402
    build_execution_manifest,
    duplicate_request_ids,
    model_condition_coverage,
    resolve_adapter,
    run_mock_inference,
)
from llm_experiments.inference.validation import load_response_schema, validate_response_text  # noqa: E402
from llm_experiments.prompts.prompt_spec import load_jsonl  # noqa: E402


MODEL_REGISTRY = REPO_ROOT / "llm-experiments" / "config" / "phase6e1_model_registry.json"
BACKEND_REGISTRY = REPO_ROOT / "llm-experiments" / "config" / "phase6e1_backend_registry.json"
RENDERED_PROMPTS = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6d2_rendered_prompts" / "rendered_prompts.jsonl"
RESPONSE_SCHEMA = REPO_ROOT / "llm-experiments" / "schema" / "preference_prediction_response_v1.json"
REQUEST_SCHEMA = REPO_ROOT / "llm-experiments" / "schema" / "phase6e_inference_request_v1.json"
RESULT_SCHEMA = REPO_ROOT / "llm-experiments" / "schema" / "phase6e_raw_inference_result_v1.json"
MANIFEST_SCHEMA = REPO_ROOT / "llm-experiments" / "schema" / "phase6e_execution_manifest_v1.json"


def test_all_four_planned_scientific_model_keys_exist():
    models = {row["model_key"]: row for row in load_model_registry(MODEL_REGISTRY)["models"]}
    assert set(models) == {"gpt", "claude_sonnet", "llama_3_1_70b_instruct", "centaur"}


def test_centaur_maps_to_runpod_and_other_models_map_to_qmul():
    models = {row["model_key"]: row for row in load_model_registry(MODEL_REGISTRY)["models"]}
    backends = backend_specs_by_key(load_backend_registry(BACKEND_REGISTRY))
    assert backends[models["centaur"]["default_backend_key"]]["backend_type"] == "runpod_http"
    for key in ["gpt", "claude_sonnet", "llama_3_1_70b_instruct"]:
        assert backends[models[key]["default_backend_key"]]["backend_type"].startswith("qmul")


def test_final_model_ids_remain_unfrozen_placeholders():
    for model in load_model_registry(MODEL_REGISTRY)["models"]:
        assert model["checkpoint_or_model_identifier"] == PLACEHOLDER_MODEL_ID


def test_adapters_implement_common_interface_and_accept_same_request():
    request = sample_request()
    for backend_key, cls in [("qmul_placeholder", QMULAdapter), ("runpod_centaur_placeholder", RunPodAdapter), ("mock", MockAdapter)]:
        adapter = cls(resolve_backend(backend_key, load_backend_registry(BACKEND_REGISTRY)))
        assert isinstance(adapter, ModelAdapter)
        prepared = adapter.prepare_request(request)
        assert prepared["messages"] == request["messages"]
        assert prepared["inference_request_id"] == request["inference_request_id"]


def test_deterministic_request_ids_and_distinct_model_condition_variants():
    rendered = load_jsonl(RENDERED_PROMPTS)
    first = rendered[0]
    same = make_inference_request_id(first["rendered_prompt_id"], "gpt", DEFAULT_INFERENCE_CONFIG_VERSION)
    again = make_inference_request_id(first["rendered_prompt_id"], "gpt", DEFAULT_INFERENCE_CONFIG_VERSION)
    other_model = make_inference_request_id(first["rendered_prompt_id"], "centaur", DEFAULT_INFERENCE_CONFIG_VERSION)
    other_condition_prompt = next(row for row in rendered if row["prediction_example_id"] == first["prediction_example_id"] and row["condition"] != first["condition"])
    other_condition = make_inference_request_id(other_condition_prompt["rendered_prompt_id"], "gpt", DEFAULT_INFERENCE_CONFIG_VERSION)
    assert same == again
    assert same != other_model
    assert same != other_condition


def test_prompt_package_preflight_required_and_drift_blocks_executable_mode(monkeypatch):
    def failed_preflight(_repo_root):
        return {"PHASE6D_PROMPT_PACKAGE_FROZEN": False, "artifact_hashes_valid": False}

    monkeypatch.setattr("llm_experiments.inference.runner.verify_prompt_package", failed_preflight)
    try:
        build_execution_manifest(REPO_ROOT)
    except RuntimeError as exc:
        assert "preflight failed" in str(exc)
    else:
        raise AssertionError("Expected prompt drift preflight to block request construction.")


def test_ground_truth_not_required_or_loaded(tmp_path):
    output_dir = tmp_path / "out"
    manifest = build_execution_manifest(REPO_ROOT, output_dir=output_dir)
    assert manifest["contains_ground_truth"] is False
    assert manifest["requests_created"] == 88


def test_rendered_prompt_messages_passed_unchanged_to_mock_adapter():
    request = sample_request()
    adapter = MockAdapter(resolve_backend("mock", load_backend_registry(BACKEND_REGISTRY)))
    prepared = adapter.prepare_request(request)
    assert prepared["messages"] == request["messages"]


def test_mock_valid_invalid_and_empty_responses_validate_by_schema():
    schema = load_response_schema(RESPONSE_SCHEMA)
    valid = MockAdapter({**resolve_backend("mock", load_backend_registry(BACKEND_REGISTRY)), "mock_mode": "valid_response"})
    invalid_json = MockAdapter({**resolve_backend("mock", load_backend_registry(BACKEND_REGISTRY)), "mock_mode": "invalid_json"})
    schema_invalid = MockAdapter({**resolve_backend("mock", load_backend_registry(BACKEND_REGISTRY)), "mock_mode": "schema_invalid"})
    empty = MockAdapter({**resolve_backend("mock", load_backend_registry(BACKEND_REGISTRY)), "mock_mode": "empty_response"})
    request = valid.prepare_request(sample_request())
    assert validate_response_text(valid.extract_raw_response(valid.invoke(request)), schema)["status"] == "valid"
    assert validate_response_text(invalid_json.extract_raw_response(invalid_json.invoke(request)), schema)["status"] == "invalid_json"
    assert validate_response_text(schema_invalid.extract_raw_response(schema_invalid.invoke(request)), schema)["status"] == "schema_invalid"
    assert validate_response_text(empty.extract_raw_response(empty.invoke(request)), schema)["status"] == "missing_response"


def test_timeout_and_connection_error_represented_canonically():
    request = sample_request()
    for mode, status in [("timeout", "timeout"), ("connection_error", "error")]:
        adapter = MockAdapter({**resolve_backend("mock", load_backend_registry(BACKEND_REGISTRY)), "mock_mode": mode})
        provider = adapter.invoke(adapter.prepare_request(request))
        result = make_raw_result(request, adapter.backend_type, provider["status"], provider.get("text"), provider.get("metadata"), error=provider.get("error"))
        assert result["request_status"] == status
        assert result["error"]["type"] in {"timeout", "connection_error"}


def test_unknown_model_and_backend_rejected():
    try:
        resolve_model("missing", load_model_registry(MODEL_REGISTRY))
    except KeyError as exc:
        assert "Unknown model key" in str(exc)
    else:
        raise AssertionError("Expected unknown model to fail.")
    try:
        resolve_backend("missing", load_backend_registry(BACKEND_REGISTRY))
    except KeyError as exc:
        assert "Unknown backend key" in str(exc)
    else:
        raise AssertionError("Expected unknown backend to fail.")


def test_duplicate_request_ids_detected():
    request = sample_request()
    assert duplicate_request_ids([request, dict(request)]) == [request["inference_request_id"]]


def test_backend_unavailable_and_unsupported_capability_are_clean_failures():
    adapter = QMULAdapter(resolve_backend("qmul_placeholder", load_backend_registry(BACKEND_REGISTRY)))
    assert adapter.healthcheck()["available"] is False
    try:
        adapter.require_capability("native_json_schema_enforcement")
    except RuntimeError as exc:
        assert "does not declare required capability" in str(exc)
    else:
        raise AssertionError("Expected unsupported capability to fail.")


def test_malformed_rendered_prompt_and_raw_provider_result_fail_cleanly():
    rendered = dict(load_jsonl(RENDERED_PROMPTS)[0])
    rendered["messages"] = []
    try:
        make_inference_request(rendered, resolve_model("gpt", load_model_registry(MODEL_REGISTRY)))
    except ValueError as exc:
        assert "messages" in str(exc)
    else:
        raise AssertionError("Expected malformed rendered prompt to fail.")
    adapter = MockAdapter(resolve_backend("mock", load_backend_registry(BACKEND_REGISTRY)))
    try:
        adapter.extract_raw_response({"status": "completed"})
    except ValueError as exc:
        assert "missing text" in str(exc)
    else:
        raise AssertionError("Expected malformed provider result to fail.")


def test_dry_run_performs_no_backend_invocation(monkeypatch, tmp_path):
    def forbidden_invoke(self, request):
        raise AssertionError("dry-run must not invoke adapters")

    monkeypatch.setattr(MockAdapter, "invoke", forbidden_invoke)
    monkeypatch.setattr(QMULAdapter, "invoke", forbidden_invoke)
    monkeypatch.setattr(RunPodAdapter, "invoke", forbidden_invoke)
    manifest = build_execution_manifest(REPO_ROOT, output_dir=tmp_path)
    assert manifest["execution_status"] == "dry_run_validated"


def test_synthetic_four_model_request_matrix_and_condition_coverage():
    manifest = build_execution_manifest(REPO_ROOT)
    assert manifest["rendered_prompts_read"] == 22
    assert manifest["selected_model_count"] == 4
    assert manifest["expected_request_count"] == 88
    assert manifest["requests_created"] == 88
    assert manifest["duplicate_request_ids"] == []
    assert manifest["model_condition_coverage"]["complete"] is True


def test_model_condition_coverage_detects_missing_condition():
    request = sample_request()
    coverage = model_condition_coverage([request], ["gpt"])
    assert coverage["complete"] is False
    assert request["condition"] not in coverage["missing_model_condition_combinations"]["gpt"]


def test_mock_integration_run_creates_88_valid_raw_results(tmp_path):
    audit = run_mock_inference(REPO_ROOT, output_dir=tmp_path)
    assert audit["rendered_prompts_read"] == 22
    assert audit["selected_model_count"] == 4
    assert audit["expected_request_count"] == 88
    assert audit["requests_created"] == 88
    assert audit["mock_requests_completed"] == 88
    assert audit["response_schema_valid_count"] == 88
    assert audit["model_condition_coverage"]["complete"] is True


def test_credentials_absent_and_absolute_user_paths_absent_from_configs():
    for registry in [load_model_registry(MODEL_REGISTRY), load_backend_registry(BACKEND_REGISTRY)]:
        assert_no_secrets(registry)
        text = json.dumps(registry)
        assert "C:\\Users\\oscar" not in text
        assert "/Users/oscar" not in text


def test_cross_platform_path_handling_accepts_relative_paths(tmp_path):
    manifest = build_execution_manifest(REPO_ROOT, output_dir=Path("llm-experiments/outputs/synthetic/phase6e1"))
    assert manifest["schema_version"] == "phase6e_execution_manifest_v1"


def test_canonical_request_result_and_manifest_schemas_accept_outputs():
    request = sample_request()
    result = make_raw_result(request, "mock", "completed", raw_response_text="{}")
    manifest = build_execution_manifest(REPO_ROOT)
    for payload, schema_path in [(request, REQUEST_SCHEMA), (result, RESULT_SCHEMA), (manifest, MANIFEST_SCHEMA)]:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(schema).iter_errors(payload))
        assert errors == []


def test_phase6d_preflight_remains_passing():
    from llm_experiments.prompts.freeze_package import verify_prompt_package

    result = verify_prompt_package(REPO_ROOT)
    assert result["PHASE6D_PROMPT_PACKAGE_FROZEN"] is True


def sample_request():
    rendered = load_jsonl(RENDERED_PROMPTS)[0]
    model = resolve_model("gpt", load_model_registry(MODEL_REGISTRY))
    return make_inference_request(rendered, model)
