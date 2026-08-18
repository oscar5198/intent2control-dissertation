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

import llm_experiments.inference.phase6g4d_centaur as centaur  # noqa: E402
from llm_experiments.inference.registry import assert_no_secrets  # noqa: E402


CENTAUR_SHARD = REPO_ROOT / centaur.CENTAUR_SHARD


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fake_preflight() -> dict:
    return {
        "schema_version": "phase6g4d_centaur_preflight_v1",
        "passed": True,
        "checks": {},
        "failures": [],
        "centaur_shard_request_count": 396,
        "condition_counts": {"non_history": 198, "personalised_history": 198},
        "prompt_hash_mismatches": [],
        "duplicate_request_ids": [],
        "ground_truth_dependency": False,
    }


def valid_response() -> dict:
    return {
        "status": "completed",
        "decoded_text": '{"predicted_preferred_mix":"A","predicted_ratings":{"A":80,"B":60,"C":55,"D":50,"E":45},"predicted_ranking":["A","B","C","D","E"]}',
        "metadata": {"model": centaur.REQUEST_MODEL, "request_api": centaur.REQUEST_API, "backend_type": centaur.BACKEND_TYPE},
        "usage": {"output_tokens": 42},
    }


def fenced_response() -> str:
    return '''```json
{"predicted_preferred_mix":"B","predicted_ratings":{"A":58,"B":74,"C":65,"D":50,"E":68},"predicted_ranking":["B","E","C","A","D"]}
```'''


def test_centaur_shard_cardinality_condition_counts_and_identity() -> None:
    shard = load_json(CENTAUR_SHARD)
    requests = shard["requests"]
    counts = Counter(row["condition"] for row in requests)

    assert shard["request_count"] == 396
    assert len(requests) == 396
    assert counts == {"non_history": 198, "personalised_history": 198}
    assert {row["model_key"] for row in requests} == {"centaur"}
    assert {row["backend_key"] for row in requests} == {"runpod_centaur_adapter_verified"}
    assert {row["exact_model_id"] for row in requests} == {"marcelbinz/Llama-3.1-Centaur-70B-adapter"}
    assert {row["deployment_revision"] for row in requests} == {"159600db8be99dc183c289923148dfd96cbd8e07"}
    assert len({row["request_id"] for row in requests}) == 396


def test_frozen_centaur_model_backend_and_capability_records() -> None:
    model = centaur.centaur_model_record(REPO_ROOT)
    backend = centaur.centaur_backend_record(REPO_ROOT)
    capability = centaur.centaur_capability_record(REPO_ROOT)

    assert model["exact_model_id"] == "marcelbinz/Llama-3.1-Centaur-70B-adapter"
    assert model["revision"] == "159600db8be99dc183c289923148dfd96cbd8e07"
    assert model["adapter_snapshot"] == centaur.ADAPTER_SNAPSHOT.as_posix()
    assert model["base_model"] == "unsloth/Meta-Llama-3.1-70B-bnb-4bit"
    assert model["base_revision"] == "a009b8db2439814febe725486a5ed388f12a8744"
    assert backend["backend_type"] == "runpod_centaur_adapter"
    assert backend["request_api"] == "FastLanguageModel.generate"
    assert backend["health_check"]["loader"] == "unsloth.FastLanguageModel.from_pretrained"
    assert backend["health_check"]["max_seq_length"] == 32768
    assert backend["message_serialization"] == "deterministic_concatenation_of_frozen_phase6d_system_and_user_content_no_semantic_wording_changes"
    assert capability["do_sample"] is False
    assert capability["max_new_tokens"] == 256
    assert capability["context_limit_tokens"] == 32768


def test_centaur_preflight_blocks_local_workstation_before_generation() -> None:
    preflight = centaur.run_preflight(REPO_ROOT)

    assert preflight["passed"] is False
    assert preflight["checks"]["phase6d_prompt_package_frozen"] is True
    assert preflight["checks"]["centaur_shard_count_valid"] is True
    assert preflight["checks"]["prompt_hashes_valid"] is True
    assert preflight["checks"]["model_identity_frozen"] is True
    assert preflight["checks"]["backend_configuration_frozen"] is True
    assert preflight["checks"]["runpod_auth_contract_frozen"] is True
    assert preflight["checks"]["output_directory_production_centaur_namespace"] is True
    assert preflight["checks"]["no_hidden_ground_truth_loaded"] is True
    assert "local_adapter_snapshot_exists" in preflight["failures"]
    assert "local_base_snapshot_exists" in preflight["failures"]
    assert_no_secrets(preflight)


def test_centaur_serialization_preserves_frozen_message_content_without_chat_template() -> None:
    messages = [{"role": "system", "content": "system text"}, {"role": "user", "content": "user text"}]

    assert centaur.serialize_centaur_messages(messages) == "system text\n\nuser text"


def test_centaur_response_normalizer_accepts_only_outer_fences() -> None:
    assert centaur.normalize_centaur_response_text(fenced_response())["response_normalization"] == "markdown_json_fence_removed"
    assert centaur.normalize_centaur_response_text(fenced_response())["normalized_response_text"].startswith('{"predicted_preferred_mix"')
    prose = "Here:\n" + fenced_response()
    assert centaur.normalize_centaur_response_text(prose)["normalized_response_text"] == prose


def test_invoke_centaur_uses_frozen_unsloth_loader_and_named_generate(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}
    adapter = tmp_path / "adapter"
    base = tmp_path / "base"
    adapter.mkdir()
    base.mkdir()
    (adapter / "adapter_config.json").write_text(json.dumps({"base_model_name_or_path": "remote/base"}), encoding="utf-8")

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

        def __call__(self, prompt: str, **kwargs):
            captured["prompt"] = prompt
            captured["tokenizer_kwargs"] = kwargs
            return {"input_ids": FakeTensor("input_ids", [10, 11, 12]), "attention_mask": FakeTensor("attention_mask", [1, 1, 1])}

        def decode(self, generated, **kwargs):
            captured["decode_tokens"] = list(generated)
            captured["decode_kwargs"] = kwargs
            return valid_response()["decoded_text"]

    class FakeModel:
        def generate(self, *args, **kwargs):
            captured["generate_positional_args"] = args
            captured["generate_kwargs"] = kwargs
            return [[10, 11, 12, 13, 14]]

    class FakeInferenceMode:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeFastLanguageModel:
        @staticmethod
        def from_pretrained(**kwargs):
            captured["from_pretrained"] = kwargs
            cfg = json.loads((Path(kwargs["model_name"]) / "adapter_config.json").read_text(encoding="utf-8"))
            captured["temporary_base_model_name_or_path"] = cfg["base_model_name_or_path"]
            return FakeModel(), FakeTokenizer()

        @staticmethod
        def for_inference(model):
            captured["for_inference_called"] = True

    monkeypatch.setattr(centaur, "ADAPTER_SNAPSHOT", adapter)
    monkeypatch.setattr(centaur, "BASE_SNAPSHOT", base)
    monkeypatch.setattr(centaur, "_TOKENIZER", None)
    monkeypatch.setattr(centaur, "_MODEL", None)
    monkeypatch.setattr(centaur, "_TEMP_ADAPTER_DIR", None)
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(inference_mode=lambda: FakeInferenceMode()))
    monkeypatch.setitem(sys.modules, "unsloth", SimpleNamespace(FastLanguageModel=FakeFastLanguageModel))

    result = centaur.invoke_centaur([{"role": "system", "content": "s"}, {"role": "user", "content": "u"}], "primary")

    assert result["status"] == "completed"
    assert captured["from_pretrained"]["max_seq_length"] == 32768
    assert captured["from_pretrained"]["dtype"] is None
    assert captured["from_pretrained"]["load_in_4bit"] is True
    assert captured["temporary_base_model_name_or_path"] == base.as_posix()
    assert captured["for_inference_called"] is True
    assert captured["prompt"] == "s\n\nu"
    assert captured["tokenizer_kwargs"] == {"return_tensors": "pt"}
    assert captured["generate_positional_args"] == ()
    assert "input_ids" in captured["generate_kwargs"]
    assert "attention_mask" in captured["generate_kwargs"]
    assert captured["generate_kwargs"]["max_new_tokens"] == 256
    assert captured["generate_kwargs"]["do_sample"] is False
    assert "temperature" not in captured["generate_kwargs"]
    assert "top_p" not in captured["generate_kwargs"]
    assert captured["tensor_moves"] == [("input_ids", "cuda"), ("attention_mask", "cuda")]
    assert captured["decode_tokens"] == [13, 14]


def test_guarded_batch_resume_and_duplicate_prevention(monkeypatch, tmp_path) -> None:
    calls = {"count": 0}

    def fake_invoke(messages: list[dict[str, str]], attempt_type: str) -> dict:
        calls["count"] += 1
        return valid_response()

    out = tmp_path / "phase6g4" / "centaur"
    monkeypatch.setattr(centaur, "run_preflight", lambda repo_root, output_dir=centaur.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(centaur, "invoke_centaur", fake_invoke)

    first = centaur.run_centaur_production(REPO_ROOT, guarded_batch_size=5, output_dir=out)
    second = centaur.run_centaur_production(REPO_ROOT, guarded_batch_size=5, output_dir=out)
    predictions = load_jsonl(out / "predictions.jsonl")

    assert first["predictions_executed_this_invocation"] == 5
    assert first["remaining_predictions"] == 391
    assert second["predictions_executed_this_invocation"] == 5
    assert second["remaining_predictions"] == 386
    assert calls["count"] == 10
    assert len(predictions) == 10
    assert len({row["request_id"] for row in predictions}) == 10
    assert len({row["prediction_id"] for row in predictions}) == 10


def test_fenced_valid_primary_is_valid_without_repair(monkeypatch, tmp_path) -> None:
    out = tmp_path / "phase6g4" / "centaur"
    monkeypatch.setattr(centaur, "run_preflight", lambda repo_root, output_dir=centaur.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(centaur, "invoke_centaur", lambda messages, attempt_type: {"status": "completed", "decoded_text": fenced_response(), "metadata": {"model": centaur.REQUEST_MODEL}, "usage": {"output_tokens": 22}})

    summary = centaur.run_centaur_production(REPO_ROOT, guarded_batch_size=1, output_dir=out)
    attempts = load_jsonl(out / "attempt_log.jsonl")
    predictions = load_jsonl(out / "predictions.jsonl")

    assert attempts[0]["response_normalization"] == "markdown_json_fence_removed"
    assert predictions[0]["final_status"] == "valid_primary"
    assert predictions[0]["formatting_repair_count"] == 0
    assert summary["formatting_repair_count"] == 0


def test_malformed_completed_response_gets_one_format_repair(monkeypatch, tmp_path) -> None:
    calls = {"count": 0}

    def fake_invoke(messages: list[dict[str, str]], attempt_type: str) -> dict:
        calls["count"] += 1
        if attempt_type == "primary":
            return {"status": "completed", "decoded_text": '{"predicted_preferred_mix":"A"', "metadata": {"model": centaur.REQUEST_MODEL}, "usage": {"output_tokens": 7}}
        return valid_response()

    out = tmp_path / "phase6g4" / "centaur"
    monkeypatch.setattr(centaur, "run_preflight", lambda repo_root, output_dir=centaur.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(centaur, "invoke_centaur", fake_invoke)

    summary = centaur.run_centaur_production(REPO_ROOT, guarded_batch_size=1, output_dir=out)
    predictions = load_jsonl(out / "predictions.jsonl")

    assert calls["count"] == 2
    assert predictions[0]["final_status"] == "valid_after_repair"
    assert summary["valid_after_repair_count"] == 1


def test_output_budget_exhausted_is_not_format_repaired(monkeypatch, tmp_path) -> None:
    def fake_invoke(messages: list[dict[str, str]], attempt_type: str) -> dict:
        return {"status": "incomplete", "decoded_text": '{"predicted_preferred_mix":"A"', "metadata": {"model": centaur.REQUEST_MODEL}, "usage": {"output_tokens": 256}, "incomplete_details": {"reason": "max_output_tokens"}}

    out = tmp_path / "phase6g4" / "centaur"
    monkeypatch.setattr(centaur, "run_preflight", lambda repo_root, output_dir=centaur.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(centaur, "invoke_centaur", fake_invoke)

    summary = centaur.run_centaur_production(REPO_ROOT, guarded_batch_size=1, output_dir=out)
    attempts = load_jsonl(out / "attempt_log.jsonl")
    predictions = load_jsonl(out / "predictions.jsonl")

    assert attempts[0]["failure_code"] == "output_budget_exhausted"
    assert predictions[0]["final_status"] == "output_budget_exhausted"
    assert predictions[0]["formatting_repair_count"] == 0
    assert summary["output_budget_exhausted_count"] == 1


def test_runtime_exception_provenance_and_cuda_oom(monkeypatch, tmp_path) -> None:
    def fake_invoke(messages: list[dict[str, str]], attempt_type: str) -> dict:
        raise centaur.CentaurRuntimeError("generation", RuntimeError("CUDA out of memory. Tried to allocate 2 GiB"))

    out = tmp_path / "phase6g4" / "centaur"
    monkeypatch.setattr(centaur, "run_preflight", lambda repo_root, output_dir=centaur.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(centaur, "invoke_centaur", fake_invoke)

    centaur.run_centaur_production(REPO_ROOT, guarded_batch_size=1, output_dir=out)
    attempt = load_jsonl(out / "attempt_log.jsonl")[0]

    assert attempt["exception_type"] == "RuntimeError"
    assert attempt["backend_stage"] == "generation"
    assert attempt["runtime_error_category"] == "cuda_out_of_memory"
    assert attempt["failure_category"] == "local_backend"
    assert attempt["cuda_oom_detected"] is True


def test_diagnostic_mode_is_isolated_and_can_succeed_with_mock(monkeypatch, tmp_path) -> None:
    diagnostic_out = tmp_path / "centaur_runtime_diagnostics"
    monkeypatch.setattr(centaur, "run_preflight", lambda repo_root, output_dir=centaur.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(centaur, "invoke_centaur", lambda messages, attempt_type, max_new_tokens=8: valid_response())

    result = centaur.run_centaur_runtime_diagnostic(REPO_ROOT, output_dir=diagnostic_out, max_new_tokens=8)

    assert result["diagnostic_only"] is True
    assert result["runtime_success"] is True
    assert result["ground_truth_dependency"] is False
    assert (diagnostic_out / "runtime_diagnostic.json").exists()
    assert not (diagnostic_out / "predictions.jsonl").exists()
    assert not (diagnostic_out / "attempt_log.jsonl").exists()
    assert_no_secrets(load_json(diagnostic_out / "runtime_diagnostic.json"))


def test_diagnostic_failure_preserves_exception(monkeypatch, tmp_path) -> None:
    diagnostic_out = tmp_path / "centaur_runtime_diagnostics"

    def fake_invoke(messages: list[dict[str, str]], attempt_type: str, max_new_tokens: int = 8) -> dict:
        raise centaur.CentaurRuntimeError("model_load", RuntimeError("bitsandbytes adapter load failed"))

    monkeypatch.setattr(centaur, "run_preflight", lambda repo_root, output_dir=centaur.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(centaur, "invoke_centaur", fake_invoke)

    result = centaur.run_centaur_runtime_diagnostic(REPO_ROOT, output_dir=diagnostic_out, max_new_tokens=8)

    assert result["runtime_success"] is False
    assert result["runtime_diagnostic"]["exception_type"] == "RuntimeError"
    assert result["runtime_diagnostic"]["backend_stage"] == "model_load"
    assert result["runtime_diagnostic"]["runtime_error_category"] == "quantization_runtime_error"
    assert_no_secrets(load_json(diagnostic_out / "runtime_diagnostic.json"))


def test_artifacts_do_not_serialize_secrets_or_ground_truth(monkeypatch, tmp_path) -> None:
    out = tmp_path / "phase6g4" / "centaur"
    monkeypatch.setattr(centaur, "run_preflight", lambda repo_root, output_dir=centaur.OUTPUT_DIR: fake_preflight())
    monkeypatch.setattr(centaur, "invoke_centaur", lambda messages, attempt_type: valid_response())

    centaur.run_centaur_production(REPO_ROOT, guarded_batch_size=2, output_dir=out)

    for path in [out / "run_manifest.json", out / "execution_summary.json", out / "failure_summary.json"]:
        payload = load_json(path)
        assert payload.get("ground_truth_dependency") is not True
        assert_no_secrets(payload)
    for row in load_jsonl(out / "attempt_log.jsonl") + load_jsonl(out / "predictions.jsonl"):
        assert "true_preferred" not in json.dumps(row).lower()
        assert "ground_truth" not in json.dumps(row).lower()
        assert_no_secrets(row)
