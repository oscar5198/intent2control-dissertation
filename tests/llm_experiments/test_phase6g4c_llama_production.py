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

import llm_experiments.inference.phase6g4c_llama as llama  # noqa: E402
from llm_experiments.inference.failures import classify_failure  # noqa: E402
from llm_experiments.inference.registry import assert_no_secrets  # noqa: E402


OUT = REPO_ROOT / llama.OUTPUT_DIR
RUN_MANIFEST = OUT / "run_manifest.json"
PREFLIGHT = OUT / "preflight_report.json"
SUMMARY = OUT / "execution_summary.json"
QC_REPORT = OUT / "llama_production_qc_report.md"
LLAMA_SHARD = REPO_ROOT / llama.LLAMA_SHARD


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fake_preflight() -> dict:
    return {
        "schema_version": "phase6g4c_llama_preflight_v1",
        "passed": True,
        "checks": {},
        "failures": [],
        "llama_shard_request_count": 396,
        "condition_counts": {"non_history": 198, "personalised_history": 198},
        "prompt_hash_mismatches": [],
        "duplicate_request_ids": [],
        "ground_truth_dependency": False,
    }


def valid_response() -> dict:
    return {
        "status": "completed",
        "decoded_text": '{"predicted_preferred_mix":"A","predicted_ratings":{"A":80,"B":60,"C":55,"D":50,"E":45},"predicted_ranking":["A","B","C","D","E"]}',
        "metadata": {"model": llama.REQUEST_MODEL, "request_api": llama.REQUEST_API, "backend_type": llama.BACKEND_TYPE},
        "usage": {"output_tokens": 42},
    }


def fenced_response(choice: str = "B") -> str:
    return f'''```json
{{"predicted_preferred_mix":"{choice}","predicted_ratings":{{"A":58,"B":74,"C":65,"D":50,"E":68}},"predicted_ranking":["B","E","C","A","D"]}}
```'''


def test_llama_shard_cardinality_condition_counts_and_model() -> None:
    shard = load_json(LLAMA_SHARD)
    requests = shard["requests"]
    counts = Counter(row["condition"] for row in requests)

    assert shard["request_count"] == 396
    assert len(requests) == 396
    assert counts == {"non_history": 198, "personalised_history": 198}
    assert {row["model_key"] for row in requests} == {"llama_3_1_70b_instruct"}
    assert {row["backend_key"] for row in requests} == {"qmul_llama_transformers_local_verified"}
    assert {row["exact_model_id"] for row in requests} == {"meta-llama/Llama-3.1-70B-Instruct"}
    assert {row["deployment_revision"] for row in requests} == {"1605565b47bb9346c5515c34102e054115b4f98b"}
    assert len({row["request_id"] for row in requests}) == 396


def test_llama_preflight_blocks_local_workstation_before_generation() -> None:
    preflight = llama.run_preflight(REPO_ROOT)

    assert preflight["passed"] is False
    assert "local_hf_cache_available" in preflight["failures"]
    assert "runtime_dependencies_available" in preflight["failures"]
    assert preflight["checks"]["authentication_configuration_valid"] is True
    assert preflight["checks"]["endpoint_configuration_available"] is True
    assert preflight["checks"]["frozen_decoding_policy_valid"] is True
    assert preflight["checks"]["no_hidden_ground_truth_loaded"] is True
    assert_no_secrets(preflight)


def test_blocked_local_artifacts_and_policy_fields() -> None:
    if not RUN_MANIFEST.exists() or not SUMMARY.exists():
        summary = llama.run_llama_production(REPO_ROOT, guarded_batch_size=5)
        assert summary["preflight_passed"] is False

    manifest = load_json(RUN_MANIFEST)
    summary = load_json(SUMMARY)

    assert manifest["run_id"] == "phase6g4c_llama_production_run_01"
    assert manifest["output_dir"].endswith("phase6g4/llama")
    assert manifest["exact_backend_model_id"] == "meta-llama/Llama-3.1-70B-Instruct"
    assert manifest["revision"] == "1605565b47bb9346c5515c34102e054115b4f98b"
    assert manifest["backend_type"] == "qmul_local_transformers"
    assert manifest["request_api"] == "AutoModelForCausalLM.generate"
    assert manifest["authentication_required"] is False
    assert manifest["inference_parameters"]["max_new_tokens"] == 256
    assert manifest["inference_parameters"]["do_sample"] is False
    assert manifest["inference_parameters"]["temperature_sent"] is False
    assert manifest["inference_parameters"]["top_p_sent"] is False
    assert manifest["inference_parameters"]["local_files_only"] is True
    assert summary["preflight_passed"] is False
    assert summary["attempted_prediction_count"] == 0
    assert summary["remaining_predictions"] == 396


def test_invoke_llama_uses_frozen_local_transformers_contract(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeTensor:
        def __init__(self, name: str, values: list[int]):
            self.name = name
            self.values = values
            self.shape = (1, len(values))

        def to(self, device: str):
            captured.setdefault("tensor_moves", []).append((self.name, device))
            return self

    class FakeTokenizer:
        eos_token_id = 2

        def apply_chat_template(self, messages, **kwargs):
            captured["messages"] = messages
            captured["chat_template_kwargs"] = kwargs
            return {
                "input_ids": FakeTensor("input_ids", [10, 11, 12]),
                "attention_mask": FakeTensor("attention_mask", [1, 1, 1]),
            }

        def decode(self, generated, **kwargs):
            captured["decode_tokens"] = list(generated)
            captured["decode_kwargs"] = kwargs
            return valid_response()["decoded_text"]

    class FakeModel:
        hf_device_map = {"": 0}

        def eval(self):
            captured["eval_called"] = True

        def get_input_embeddings(self):
            return SimpleNamespace(weight=SimpleNamespace(device="cuda:0"))

        def generate(self, *args, **kwargs):
            captured["generate_positional_args"] = args
            captured["generate_kwargs"] = kwargs
            return [[10, 11, 12, 13, 14]]

    class FakeInferenceMode:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeBitsAndBytesConfig:
        def __init__(self, **kwargs):
            captured["quantization_config"] = kwargs

    class FakeAutoTokenizer:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            captured["tokenizer_from_pretrained"] = {"args": args, "kwargs": kwargs}
            return FakeTokenizer()

    class FakeAutoModelForCausalLM:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            captured["model_from_pretrained"] = {"args": args, "kwargs": kwargs}
            return FakeModel()

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(bfloat16="bfloat16", inference_mode=lambda: FakeInferenceMode()))
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(AutoModelForCausalLM=FakeAutoModelForCausalLM, AutoTokenizer=FakeAutoTokenizer, BitsAndBytesConfig=FakeBitsAndBytesConfig))
    monkeypatch.setattr(llama, "_TOKENIZER", None)
    monkeypatch.setattr(llama, "_MODEL", None)

    result = llama.invoke_llama([{"role": "system", "content": "s"}, {"role": "user", "content": "u"}], "primary")

    assert result["status"] == "completed"
    assert result["decoded_text"].startswith('{"predicted_preferred_mix"')
    assert captured["tokenizer_from_pretrained"]["args"] == (llama.REQUEST_MODEL,)
    assert captured["tokenizer_from_pretrained"]["kwargs"] == {"revision": llama.REVISION, "local_files_only": True}
    assert captured["model_from_pretrained"]["args"] == (llama.REQUEST_MODEL,)
    assert captured["model_from_pretrained"]["kwargs"]["revision"] == llama.REVISION
    assert captured["model_from_pretrained"]["kwargs"]["local_files_only"] is True
    assert captured["model_from_pretrained"]["kwargs"]["device_map"] == "auto"
    assert captured["model_from_pretrained"]["kwargs"]["max_memory"] == {0: "43GiB"}
    assert captured["quantization_config"]["load_in_4bit"] is True
    assert captured["quantization_config"]["bnb_4bit_quant_type"] == "nf4"
    assert captured["chat_template_kwargs"] == {"tokenize": True, "add_generation_prompt": True, "return_tensors": "pt", "return_dict": True}
    assert captured["generate_positional_args"] == ()
    assert "input_ids" in captured["generate_kwargs"]
    assert "attention_mask" in captured["generate_kwargs"]
    assert captured["generate_kwargs"]["max_new_tokens"] == 256
    assert captured["generate_kwargs"]["do_sample"] is False
    assert "temperature" not in captured["generate_kwargs"]
    assert "top_p" not in captured["generate_kwargs"]
    assert "seed" not in captured["generate_kwargs"]
    assert captured["tensor_moves"] == [("input_ids", "cuda:0"), ("attention_mask", "cuda:0")]
    assert captured["decode_tokens"] == [13, 14]


def test_guarded_batch_resume_and_duplicate_prevention(monkeypatch, tmp_path) -> None:
    calls = {"count": 0}

    def fake_invoke(messages: list[dict[str, str]], attempt_type: str) -> dict:
        calls["count"] += 1
        return valid_response()

    out = tmp_path / "phase6g4" / "llama"
    monkeypatch.setattr(llama, "run_preflight", lambda repo_root, output_dir=llama.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(llama, "invoke_llama", fake_invoke)

    first = llama.run_llama_production(REPO_ROOT, guarded_batch_size=3, output_dir=out)
    second = llama.run_llama_production(REPO_ROOT, guarded_batch_size=3, output_dir=out)

    predictions = load_jsonl(out / "predictions.jsonl")
    assert first["predictions_executed_this_invocation"] == 3
    assert first["remaining_predictions"] == 393
    assert first["stopped_after_guarded_batch"] is True
    assert second["predictions_executed_this_invocation"] == 3
    assert second["remaining_predictions"] == 390
    assert calls["count"] == 6
    assert len(predictions) == 6
    assert len({row["request_id"] for row in predictions}) == 6
    assert len({row["prediction_id"] for row in predictions}) == 6
    assert {row["run_id"] for row in predictions} == {"phase6g4c_llama_production_run_01"}


def test_named_model_inputs_are_required_and_prompt_length_comes_from_input_ids() -> None:
    class FakeMapping:
        def __init__(self):
            self.store = {"input_ids": SimpleNamespace(shape=(1, 7)), "attention_mask": object()}

        def keys(self):
            return self.store.keys()

        def __getitem__(self, key):
            return self.store[key]

    named = llama.ensure_named_model_inputs(FakeMapping())

    assert named["input_ids"].shape[-1] == 7
    assert "attention_mask" in named
    try:
        llama.ensure_named_model_inputs(SimpleNamespace(shape=(1, 7)))
    except TypeError as exc:
        assert "mapping" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("non-mapping chat template output was accepted")


def test_input_device_comes_from_model_embeddings_and_only_tensors_move() -> None:
    moves: list[tuple[str, str]] = []

    class FakeTensor:
        def __init__(self, name: str):
            self.name = name

        def to(self, device: str):
            moves.append((self.name, device))
            return self

    model = SimpleNamespace(get_input_embeddings=lambda: SimpleNamespace(weight=SimpleNamespace(device="cuda:0")))
    inputs = {"input_ids": FakeTensor("input_ids"), "attention_mask": FakeTensor("attention_mask"), "metadata": "kept"}

    device = llama.model_input_device(model)
    moved = llama.move_model_inputs_to_device(inputs, device)

    assert device == "cuda:0"
    assert moves == [("input_ids", "cuda:0"), ("attention_mask", "cuda:0")]
    assert moved["metadata"] == "kept"


def test_fenced_valid_primary_is_valid_primary_without_format_repair(monkeypatch, tmp_path) -> None:
    def fake_invoke(messages: list[dict[str, str]], attempt_type: str) -> dict:
        return {"status": "completed", "decoded_text": fenced_response(), "metadata": {"model": llama.REQUEST_MODEL}, "usage": {"output_tokens": 22}}

    out = tmp_path / "phase6g4" / "llama"
    monkeypatch.setattr(llama, "run_preflight", lambda repo_root, output_dir=llama.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(llama, "invoke_llama", fake_invoke)

    summary = llama.run_llama_production(REPO_ROOT, guarded_batch_size=1, output_dir=out)
    attempts = load_jsonl(out / "attempt_log.jsonl")
    predictions = load_jsonl(out / "predictions.jsonl")

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
            return {"status": "completed", "decoded_text": '{"predicted_preferred_mix":"A"', "metadata": {"model": llama.REQUEST_MODEL}, "usage": {"output_tokens": 7}}
        return valid_response()

    out = tmp_path / "phase6g4" / "llama"
    monkeypatch.setattr(llama, "run_preflight", lambda repo_root, output_dir=llama.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(llama, "invoke_llama", fake_invoke)

    summary = llama.run_llama_production(REPO_ROOT, guarded_batch_size=1, output_dir=out)
    attempts = load_jsonl(out / "attempt_log.jsonl")
    predictions = load_jsonl(out / "predictions.jsonl")

    assert calls["count"] == 2
    assert [row["attempt_type"] for row in attempts] == ["primary", "format_repair"]
    assert predictions[0]["final_status"] == "valid_after_repair"
    assert predictions[0]["formatting_repair_count"] == 1
    assert summary["valid_after_repair_count"] == 1


def test_output_budget_exhausted_is_not_format_repaired(monkeypatch, tmp_path) -> None:
    calls = {"count": 0}

    def fake_invoke(messages: list[dict[str, str]], attempt_type: str) -> dict:
        calls["count"] += 1
        return {
            "status": "incomplete",
            "decoded_text": '{"predicted_preferred_mix":"A"',
            "metadata": {"model": llama.REQUEST_MODEL},
            "usage": {"output_tokens": 256},
            "incomplete_details": {"reason": "max_output_tokens"},
        }

    out = tmp_path / "phase6g4" / "llama"
    monkeypatch.setattr(llama, "run_preflight", lambda repo_root, output_dir=llama.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(llama, "invoke_llama", fake_invoke)

    summary = llama.run_llama_production(REPO_ROOT, guarded_batch_size=1, output_dir=out)
    attempts = load_jsonl(out / "attempt_log.jsonl")
    predictions = load_jsonl(out / "predictions.jsonl")

    assert classify_failure({"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}}, {"status": "invalid_json"})["failure_code"] == "output_budget_exhausted"
    assert calls["count"] == 1
    assert attempts[0]["failure_code"] == "output_budget_exhausted"
    assert attempts[0]["failure_category"] == "output_budget"
    assert predictions[0]["final_status"] == "output_budget_exhausted"
    assert predictions[0]["formatting_repair_count"] == 0
    assert summary["output_budget_exhausted_count"] == 1


def test_model_mismatch_is_terminal_and_stops_after_mismatching_prediction(monkeypatch, tmp_path) -> None:
    def fake_invoke(messages: list[dict[str, str]], attempt_type: str) -> dict:
        return {**valid_response(), "metadata": {"model": "wrong-local-model"}}

    out = tmp_path / "phase6g4" / "llama"
    monkeypatch.setattr(llama, "run_preflight", lambda repo_root, output_dir=llama.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(llama, "invoke_llama", fake_invoke)

    summary = llama.run_llama_production(REPO_ROOT, guarded_batch_size=3, output_dir=out)
    predictions = load_jsonl(out / "predictions.jsonl")

    assert summary["predictions_executed_this_invocation"] == 1
    assert summary["model_identity_mismatch_count"] == 1
    assert predictions[0]["final_status"] == "model_mismatch"
    assert predictions[0]["terminal"] is True


def test_artifacts_do_not_serialize_secrets_or_ground_truth(monkeypatch, tmp_path) -> None:
    out = tmp_path / "phase6g4" / "llama"
    monkeypatch.setattr(llama, "run_preflight", lambda repo_root, output_dir=llama.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(llama, "invoke_llama", lambda messages, attempt_type: valid_response())

    llama.run_llama_production(REPO_ROOT, guarded_batch_size=2, output_dir=out)

    for path in [out / "run_manifest.json", out / "execution_summary.json", out / "failure_summary.json"]:
        payload = load_json(path)
        assert payload.get("ground_truth_dependency") is not True
        assert_no_secrets(payload)
    for row in load_jsonl(out / "attempt_log.jsonl") + load_jsonl(out / "predictions.jsonl"):
        assert "true_preferred" not in json.dumps(row).lower()
        assert "ground_truth" not in json.dumps(row).lower()
        assert_no_secrets(row)


def test_local_exception_type_message_stage_and_category_are_preserved(monkeypatch, tmp_path) -> None:
    def fake_invoke(messages: list[dict[str, str]], attempt_type: str) -> dict:
        raise llama.LlamaRuntimeError("model_load", RuntimeError("bitsandbytes failed to load CUDA kernels"))

    out = tmp_path / "phase6g4" / "llama"
    monkeypatch.setattr(llama, "run_preflight", lambda repo_root, output_dir=llama.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(llama, "invoke_llama", fake_invoke)

    summary = llama.run_llama_production(REPO_ROOT, guarded_batch_size=1, output_dir=out)
    attempts = load_jsonl(out / "attempt_log.jsonl")

    assert summary["backend_failure_count"] == 1
    assert attempts[0]["request_status"] == "error"
    assert attempts[0]["exception_type"] == "RuntimeError"
    assert attempts[0]["exception_message"] == "bitsandbytes failed to load CUDA kernels"
    assert attempts[0]["backend_stage"] == "model_load"
    assert attempts[0]["runtime_error_category"] == "quantization_runtime_error"
    assert attempts[0]["failure_code"] == "quantization_runtime_error"
    assert attempts[0]["failure_category"] == "local_backend"
    assert attempts[0]["retryable"] is False


def test_cuda_oom_classification_is_explicit(monkeypatch, tmp_path) -> None:
    def fake_invoke(messages: list[dict[str, str]], attempt_type: str) -> dict:
        raise llama.LlamaRuntimeError("generation", RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB"))

    out = tmp_path / "phase6g4" / "llama"
    monkeypatch.setattr(llama, "run_preflight", lambda repo_root, output_dir=llama.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(llama, "invoke_llama", fake_invoke)

    llama.run_llama_production(REPO_ROOT, guarded_batch_size=1, output_dir=out)
    attempts = load_jsonl(out / "attempt_log.jsonl")

    assert attempts[0]["failure_code"] == "cuda_out_of_memory"
    assert attempts[0]["failure_category"] == "local_backend"
    assert attempts[0]["cuda_oom_detected"] is True
    assert attempts[0]["host_oom_detected"] is False


def test_generic_generation_error_is_not_connection_error(monkeypatch, tmp_path) -> None:
    def fake_invoke(messages: list[dict[str, str]], attempt_type: str) -> dict:
        raise llama.LlamaRuntimeError("generation", RuntimeError("shape mismatch during cache update"))

    out = tmp_path / "phase6g4" / "llama"
    monkeypatch.setattr(llama, "run_preflight", lambda repo_root, output_dir=llama.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(llama, "invoke_llama", fake_invoke)

    llama.run_llama_production(REPO_ROOT, guarded_batch_size=1, output_dir=out)
    attempts = load_jsonl(out / "attempt_log.jsonl")

    assert attempts[0]["failure_code"] == "generation_error"
    assert attempts[0]["failure_category"] == "local_backend"
    assert attempts[0]["failure_code"] != "connection_error"
    assert attempts[0]["backend_stage"] == "generation"


def test_diagnostic_mode_does_not_write_production_predictions(monkeypatch, tmp_path) -> None:
    diagnostic_out = tmp_path / "llama_runtime_diagnostics"
    monkeypatch.setattr(llama, "run_preflight", lambda repo_root, output_dir=llama.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(llama, "invoke_llama", lambda messages, attempt_type, max_new_tokens=8: valid_response())

    result = llama.run_llama_runtime_diagnostic(REPO_ROOT, output_dir=diagnostic_out, max_new_tokens=4)

    assert result["diagnostic_only"] is True
    assert result["ground_truth_dependency"] is False
    assert result["prompt_source"] == "synthetic_non_study_minimal_prompt"
    assert result["diagnostic_max_new_tokens"] == 4
    assert result["runtime_success"] is True
    assert (diagnostic_out / "runtime_diagnostic.json").exists()
    assert not (diagnostic_out / "predictions.jsonl").exists()
    assert not (diagnostic_out / "attempt_log.jsonl").exists()


def test_diagnostic_mode_writes_real_exception_information(monkeypatch, tmp_path) -> None:
    diagnostic_out = tmp_path / "llama_runtime_diagnostics"

    def fake_invoke(messages: list[dict[str, str]], attempt_type: str, max_new_tokens: int = 8) -> dict:
        raise llama.LlamaRuntimeError("device_transfer", RuntimeError("tensor on CPU cannot move to cuda"))

    monkeypatch.setattr(llama, "run_preflight", lambda repo_root, output_dir=llama.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(llama, "invoke_llama", fake_invoke)

    result = llama.run_llama_runtime_diagnostic(REPO_ROOT, output_dir=diagnostic_out, max_new_tokens=4)

    assert result["runtime_success"] is False
    assert result["runtime_diagnostic"]["exception_type"] == "RuntimeError"
    assert result["runtime_diagnostic"]["backend_stage"] == "device_transfer"
    assert result["runtime_diagnostic"]["runtime_error_category"] == "device_placement_error"
    assert_no_secrets(load_json(diagnostic_out / "runtime_diagnostic.json"))


def test_backend_failed_recovery_eligibility_excludes_valid_predictions() -> None:
    predictions = [
        {"request_id": "r1", "final_status": "backend_failed"},
        {"request_id": "r2", "final_status": "valid_primary"},
        {"request_id": "r3", "final_status": "valid_after_repair"},
        {"request_id": "r4", "final_status": "invalid_after_repair"},
    ]

    assert llama.backend_failed_recovery_eligible_request_ids(predictions) == ["r1"]


def test_prepare_recovery_preserves_historical_run01_artifacts_and_deduplicates(tmp_path) -> None:
    source = tmp_path / "phase6g4" / "llama"
    recovery = tmp_path / "phase6g4" / "llama_recovery_run_02"
    source.mkdir(parents=True)
    predictions = [
        {"request_id": "r1", "final_status": "backend_failed"},
        {"request_id": "r1", "final_status": "backend_failed"},
        {"request_id": "r2", "final_status": "valid_primary"},
    ]
    attempts = [{"request_id": "r1", "failure_code": "model_load_error"}]
    (source / "predictions.jsonl").write_text("\n".join(json.dumps(row) for row in predictions) + "\n", encoding="utf-8")
    (source / "attempt_log.jsonl").write_text("\n".join(json.dumps(row) for row in attempts) + "\n", encoding="utf-8")
    before_predictions = (source / "predictions.jsonl").read_text(encoding="utf-8")
    before_attempts = (source / "attempt_log.jsonl").read_text(encoding="utf-8")

    manifest = llama.prepare_backend_failed_recovery(REPO_ROOT, source_output_dir=source, recovery_output_dir=recovery)

    assert manifest["eligible_request_count"] == 1
    assert manifest["eligible_request_ids"] == ["r1"]
    assert manifest["historical_source_artifacts_preserved"] is True
    assert manifest["ground_truth_dependency"] is False
    assert (recovery / "backend_failed_recovery_manifest.json").exists()
    assert (source / "predictions.jsonl").read_text(encoding="utf-8") == before_predictions
    assert (source / "attempt_log.jsonl").read_text(encoding="utf-8") == before_attempts
    assert_no_secrets(manifest)


def test_backend_failed_recovery_run_uses_distinct_namespace_and_no_duplicate_targets(monkeypatch, tmp_path) -> None:
    source = tmp_path / "phase6g4" / "llama"
    recovery = tmp_path / "phase6g4" / "llama_recovery_run_02"
    source.mkdir(parents=True)
    shard = load_json(LLAMA_SHARD)
    eligible_ids = [shard["requests"][0]["request_id"], shard["requests"][1]["request_id"]]
    source_predictions = [{"request_id": eligible_ids[0], "final_status": "backend_failed"}, {"request_id": eligible_ids[1], "final_status": "backend_failed"}]
    (source / "predictions.jsonl").write_text("\n".join(json.dumps(row) for row in source_predictions) + "\n", encoding="utf-8")
    (source / "attempt_log.jsonl").write_text(json.dumps({"request_id": eligible_ids[0], "failure_code": "model_load_error"}) + "\n", encoding="utf-8")
    monkeypatch.setattr(llama, "run_preflight", lambda repo_root, output_dir=llama.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(llama, "invoke_llama", lambda messages, attempt_type: valid_response())

    first = llama.run_llama_backend_failed_recovery(REPO_ROOT, guarded_batch_size=1, source_output_dir=source, recovery_output_dir=recovery)
    second = llama.run_llama_backend_failed_recovery(REPO_ROOT, guarded_batch_size=2, source_output_dir=source, recovery_output_dir=recovery)
    recovered_predictions = load_jsonl(recovery / "predictions.jsonl")

    assert first["run_id"] == "phase6g4c_llama_backend_failed_recovery_run_02"
    assert first["expected_predictions"] == 2
    assert first["predictions_executed_this_invocation"] == 1
    assert second["predictions_executed_this_invocation"] == 1
    assert second["remaining_predictions"] == 0
    assert len(recovered_predictions) == 2
    assert len({row["request_id"] for row in recovered_predictions}) == 2
    assert {row["run_id"] for row in recovered_predictions} == {"phase6g4c_llama_backend_failed_recovery_run_02"}
