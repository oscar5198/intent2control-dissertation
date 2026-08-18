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

    class FakeInputs:
        shape = (1, 3)

        def to(self, device: str):
            captured["device"] = device
            return self

    class FakeTokenizer:
        eos_token_id = 2

        def apply_chat_template(self, messages, **kwargs):
            captured["messages"] = messages
            captured["chat_template_kwargs"] = kwargs
            return FakeInputs()

        def decode(self, generated, **kwargs):
            captured["decode_tokens"] = list(generated)
            captured["decode_kwargs"] = kwargs
            return valid_response()["decoded_text"]

    class FakeModel:
        hf_device_map = {"": 0}

        def eval(self):
            captured["eval_called"] = True

        def generate(self, inputs, **kwargs):
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
    assert captured["chat_template_kwargs"] == {"tokenize": True, "add_generation_prompt": True, "return_tensors": "pt"}
    assert captured["generate_kwargs"]["max_new_tokens"] == 256
    assert captured["generate_kwargs"]["do_sample"] is False
    assert "temperature" not in captured["generate_kwargs"]
    assert "top_p" not in captured["generate_kwargs"]
    assert "seed" not in captured["generate_kwargs"]
    assert captured["device"] == "cuda"


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
