"""Phase 6E.1 dry-run and mock inference runner."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from llm_experiments.inference.adapters import MockAdapter, QMULAdapter, RunPodAdapter
from llm_experiments.inference.base import ModelAdapter
from llm_experiments.inference.configuration import production_preflight
from llm_experiments.inference.registry import (
    DEFAULT_BACKEND_REGISTRY_PATH,
    DEFAULT_MODEL_REGISTRY_PATH,
    assert_no_secrets,
    load_backend_registry,
    load_model_registry,
    resolve_backend,
    resolve_model,
)
from llm_experiments.inference.requests import (
    DEFAULT_INFERENCE_CONFIG_VERSION,
    DEFAULT_PROMPT_PACKAGE_VERSION,
    INFERENCE_INTERFACE_VERSION,
    make_inference_request,
)
from llm_experiments.inference.responses import make_raw_result
from llm_experiments.inference.state_machine import run_synthetic_failure_matrix
from llm_experiments.inference.validation import load_response_schema, validate_response_text
from llm_experiments.prompts.freeze_package import (
    DEFAULT_MANIFEST,
    PHASE6D_PROMPT_PACKAGE_FROZEN_GATE,
    verify_prompt_package,
)
from llm_experiments.prompts.prompt_spec import load_jsonl, write_json


DEFAULT_RENDERED_PROMPTS = Path("llm-experiments/outputs/synthetic/phase6d2_rendered_prompts/rendered_prompts.jsonl")
DEFAULT_RESPONSE_SCHEMA = Path("llm-experiments/schema/preference_prediction_response_v1.json")
DEFAULT_RENDERED_SCHEMA = Path("llm-experiments/schema/rendered_prompt_v1.json")
DEFAULT_OUTPUT_DIR = Path("llm-experiments/outputs/synthetic/phase6e1")
DEFAULT_SELECTED_MODELS = ["gpt", "claude_sonnet", "llama_3_1_70b_instruct", "centaur"]

ADAPTER_CLASSES = {
    "mock": MockAdapter,
    "qmul_local": QMULAdapter,
    "qmul_http": QMULAdapter,
    "openai_compatible": QMULAdapter,
    "runpod_http": RunPodAdapter,
}


def build_execution_manifest(
    repo_root: Path,
    rendered_prompts_path: Path = DEFAULT_RENDERED_PROMPTS,
    model_registry_path: Path = DEFAULT_MODEL_REGISTRY_PATH,
    backend_registry_path: Path = DEFAULT_BACKEND_REGISTRY_PATH,
    response_schema_path: Path = DEFAULT_RESPONSE_SCHEMA,
    rendered_schema_path: Path = DEFAULT_RENDERED_SCHEMA,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    selected_models: list[str] | None = None,
    dry_run: bool = True,
    allow_real_backends: bool = False,
    require_preflight: bool = True,
) -> dict[str, Any]:
    selected_models = selected_models or DEFAULT_SELECTED_MODELS
    preflight = verify_prompt_package(repo_root) if require_preflight else {PHASE6D_PROMPT_PACKAGE_FROZEN_GATE: False}
    if not preflight.get(PHASE6D_PROMPT_PACKAGE_FROZEN_GATE):
        if not dry_run or require_preflight:
            raise RuntimeError("Phase 6D prompt-package preflight failed; inference request construction blocked.")
    primary_preflight = production_preflight(repo_root) if allow_real_backends else None
    if allow_real_backends and not primary_preflight.get("production_inference_allowed"):
        raise RuntimeError("Phase 6E.2 production preflight failed; real inference is blocked.")

    rendered_prompts = load_jsonl(repo_root / rendered_prompts_path)
    rendered_schema = json.loads((repo_root / rendered_schema_path).read_text(encoding="utf-8"))
    rendered_validator = Draft202012Validator(rendered_schema)
    rendered_errors = {
        row.get("rendered_prompt_id", "<missing>"): [error.message for error in rendered_validator.iter_errors(row)]
        for row in rendered_prompts
    }
    rendered_errors = {key: value for key, value in rendered_errors.items() if value}
    if rendered_errors:
        raise ValueError(f"Malformed rendered prompts: {rendered_errors}")

    model_registry = load_model_registry(repo_root / model_registry_path)
    backend_registry = load_backend_registry(repo_root / backend_registry_path)
    assert_no_secrets(model_registry)
    assert_no_secrets(backend_registry)
    response_schema = load_response_schema(repo_root / response_schema_path)
    requests = []
    for model_key in selected_models:
        model_spec = resolve_model(model_key, model_registry)
        backend_spec = resolve_backend(model_spec["default_backend_key"], backend_registry)
        adapter = resolve_adapter(backend_spec)
        if not dry_run and backend_spec["backend_type"] != "mock" and not allow_real_backends:
            raise RuntimeError(f"Real backend {backend_spec['backend_key']} is not enabled in Phase 6E.1.")
        adapter.describe_backend()
        for rendered_prompt in rendered_prompts:
            requests.append(make_inference_request(rendered_prompt, model_spec, model_spec["inference_config_version"]))

    duplicate_ids = duplicate_request_ids(requests)
    coverage = model_condition_coverage(requests, selected_models)
    manifest = {
        "schema_version": "phase6e_execution_manifest_v1",
        "inference_interface_version": INFERENCE_INTERFACE_VERSION,
        "prompt_package_version": DEFAULT_PROMPT_PACKAGE_VERSION,
        "response_schema_version": response_schema["$id"],
        "inference_config_version": DEFAULT_INFERENCE_CONFIG_VERSION,
        "mode": "dry_run" if dry_run else "mock",
        "prompt_package_preflight": preflight,
        "primary_inference_preflight": primary_preflight,
        "rendered_prompts_read": len(rendered_prompts),
        "selected_model_keys": selected_models,
        "selected_model_count": len(selected_models),
        "expected_request_count": len(rendered_prompts) * len(selected_models),
        "requests_created": len(requests),
        "duplicate_request_ids": duplicate_ids,
        "model_condition_coverage": coverage,
        "execution_status": "dry_run_validated" if dry_run else "pending_mock_execution",
        "requests": [
            {
                "inference_request_id": request["inference_request_id"],
                "rendered_prompt_id": request["rendered_prompt_id"],
                "prediction_example_id": request["prediction_example_id"],
                "condition": request["condition"],
                "model_key": request["model_key"],
                "backend_key": request["backend_key"],
                "prompt_package_version": request["prompt_package_version"],
                "response_schema_version": request["response_schema_version"],
                "inference_config_id": request["inference_config_id"],
                "attempt_type": request["attempt_type"],
                "execution_status": "dry_run_validated" if dry_run else "pending",
            }
            for request in requests
        ],
        "contains_ground_truth": False,
        "contains_credentials": False,
        "real_backend_invocation_enabled": allow_real_backends,
    }
    out = repo_root / output_dir
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "phase6e1_execution_manifest.json", manifest)
    return manifest


def run_mock_inference(
    repo_root: Path,
    rendered_prompts_path: Path = DEFAULT_RENDERED_PROMPTS,
    model_registry_path: Path = DEFAULT_MODEL_REGISTRY_PATH,
    backend_registry_path: Path = DEFAULT_BACKEND_REGISTRY_PATH,
    response_schema_path: Path = DEFAULT_RESPONSE_SCHEMA,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    selected_models: list[str] | None = None,
    mock_mode: str = "valid_response",
) -> dict[str, Any]:
    selected_models = selected_models or DEFAULT_SELECTED_MODELS
    model_registry = load_model_registry(repo_root / model_registry_path)
    backend_registry = load_backend_registry(repo_root / backend_registry_path)
    mock_backend = resolve_backend("mock", backend_registry)
    mock_backend = {**mock_backend, "mock_mode": mock_mode}
    adapter = MockAdapter(mock_backend)
    rendered_prompts = load_jsonl(repo_root / rendered_prompts_path)
    response_schema = load_response_schema(repo_root / response_schema_path)
    requests = [
        make_inference_request(rendered_prompt, {**resolve_model(model_key, model_registry), "default_backend_key": "mock"})
        for model_key in selected_models
        for rendered_prompt in rendered_prompts
    ]
    duplicate_ids = duplicate_request_ids(requests)
    if duplicate_ids:
        raise ValueError(f"Duplicate inference request IDs: {duplicate_ids}")
    results = []
    validations = []
    for request in requests:
        prepared = adapter.prepare_request(request)
        provider_response = adapter.invoke(prepared)
        raw_text = adapter.extract_raw_response(provider_response)
        status = provider_response.get("status", "completed")
        error = provider_response.get("error")
        result = make_raw_result(
            request,
            backend_type=adapter.backend_type,
            request_status=status,
            raw_response_text=raw_text,
            provider_response_metadata=provider_response.get("metadata"),
            usage=adapter.extract_usage(provider_response),
            latency=None,
            error=error,
        )
        validation = validate_response_text(raw_text, response_schema)
        validations.append({"inference_request_id": request["inference_request_id"], **validation})
        results.append(result)
    audit = {
        "schema_version": "phase6e1_synthetic_mock_audit_v1",
        "inference_interface_version": INFERENCE_INTERFACE_VERSION,
        "prompt_package_preflight": verify_prompt_package(repo_root),
        "rendered_prompts_read": len(rendered_prompts),
        "selected_model_keys": selected_models,
        "selected_model_count": len(selected_models),
        "expected_request_count": len(rendered_prompts) * len(selected_models),
        "requests_created": len(requests),
        "mock_requests_completed": sum(1 for row in results if row["request_status"] == "completed"),
        "response_schema_valid_count": sum(1 for row in validations if row["valid"]),
        "response_schema_invalid_count": sum(1 for row in validations if not row["valid"]),
        "duplicate_request_ids": duplicate_ids,
        "model_condition_coverage": model_condition_coverage(requests, selected_models),
        "mock_mode": mock_mode,
        "contains_ground_truth": False,
        "contains_real_model_responses": False,
    }
    out = repo_root / output_dir
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "phase6e1_mock_raw_results.jsonl", results)
    write_jsonl(out / "phase6e1_mock_response_validations.jsonl", validations)
    write_json(out / "phase6e1_synthetic_mock_audit.json", audit)
    return audit


def resolve_adapter(backend_spec: dict[str, Any]) -> ModelAdapter:
    backend_type = backend_spec["backend_type"]
    if backend_type not in ADAPTER_CLASSES:
        raise KeyError(f"Unknown backend type: {backend_type}")
    return ADAPTER_CLASSES[backend_type](backend_spec)


def duplicate_request_ids(requests: list[dict[str, Any]]) -> list[str]:
    counts = Counter(request["inference_request_id"] for request in requests)
    return sorted(request_id for request_id, count in counts.items() if count > 1)


def model_condition_coverage(requests: list[dict[str, Any]], selected_models: list[str]) -> dict[str, Any]:
    by_model: dict[str, set[str]] = defaultdict(set)
    for request in requests:
        by_model[request["model_key"]].add(request["condition"])
    expected = {"non_history", "personalised_history"}
    missing = {model: sorted(expected - by_model.get(model, set())) for model in selected_models}
    missing = {model: conditions for model, conditions in missing.items() if conditions}
    return {
        "expected_conditions": sorted(expected),
        "conditions_by_model": {model: sorted(by_model.get(model, set())) for model in selected_models},
        "missing_model_condition_combinations": missing,
        "complete": not missing,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 6E.1 inference dry-run/mock runner.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--rendered-prompts", type=Path, default=DEFAULT_RENDERED_PROMPTS)
    parser.add_argument("--model-registry", type=Path, default=DEFAULT_MODEL_REGISTRY_PATH)
    parser.add_argument("--backend-registry", type=Path, default=DEFAULT_BACKEND_REGISTRY_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--models", nargs="*", default=DEFAULT_SELECTED_MODELS)
    parser.add_argument("--mode", choices=["dry_run", "mock", "mock_failure_matrix"], default="dry_run")
    parser.add_argument("--mock-mode", default="valid_response")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    if args.mode == "dry_run":
        manifest = build_execution_manifest(
            repo_root,
            rendered_prompts_path=args.rendered_prompts,
            model_registry_path=args.model_registry,
            backend_registry_path=args.backend_registry,
            output_dir=args.output_dir,
            selected_models=args.models,
            dry_run=True,
        )
        print(f"rendered_prompts_read={manifest['rendered_prompts_read']}")
        print(f"selected_model_count={manifest['selected_model_count']}")
        print(f"expected_request_count={manifest['expected_request_count']}")
        print(f"requests_created={manifest['requests_created']}")
        print(f"model_condition_coverage_complete={manifest['model_condition_coverage']['complete']}")
        return 0
    if args.mode == "mock_failure_matrix":
        summary = run_synthetic_failure_matrix(repo_root)
        print(f"run_id={summary['run_id']}")
        print(f"attempts_total={summary['attempts_total']}")
        print(f"predictions_attempted={summary['predictions_attempted']}")
        print(f"INFERENCE_RUN_COMPLETE={summary['INFERENCE_RUN_COMPLETE']}")
        print(f"ALL_EXPECTED_PREDICTIONS_VALID={summary['ALL_EXPECTED_PREDICTIONS_VALID']}")
        return 0
    audit = run_mock_inference(
        repo_root,
        rendered_prompts_path=args.rendered_prompts,
        model_registry_path=args.model_registry,
        backend_registry_path=args.backend_registry,
        output_dir=args.output_dir,
        selected_models=args.models,
        mock_mode=args.mock_mode,
    )
    print(f"rendered_prompts_read={audit['rendered_prompts_read']}")
    print(f"selected_model_count={audit['selected_model_count']}")
    print(f"expected_request_count={audit['expected_request_count']}")
    print(f"requests_created={audit['requests_created']}")
    print(f"mock_requests_completed={audit['mock_requests_completed']}")
    print(f"response_schema_valid_count={audit['response_schema_valid_count']}")
    print(f"model_condition_coverage_complete={audit['model_condition_coverage']['complete']}")
    return 0 if audit["response_schema_invalid_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
