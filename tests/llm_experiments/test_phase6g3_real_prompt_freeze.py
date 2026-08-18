from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.inference.phase6g3 import sha256_file, sha256_json  # noqa: E402
from llm_experiments.inference.registry import assert_no_secrets  # noqa: E402
from llm_experiments.prompts.freeze_package import verify_prompt_package  # noqa: E402
from llm_experiments.prompts.prompt_spec import EXPECTED_LABELS, PARTICIPANT_METADATA_LABELS, SYSTEM_INSTRUCTION, load_jsonl  # noqa: E402


OUT = REPO_ROOT / "llm-experiments" / "outputs" / "real" / "phase6g3"
PROMPT_DATA = REPO_ROOT / "llm-experiments" / "outputs" / "real" / "phase6b" / "final_prompt_data_objects.jsonl"
PHASE6G1_MANIFEST = REPO_ROOT / "llm-experiments" / "outputs" / "real" / "phase6b" / "phase6g1_real_phase6b_manifest.json"
FREEZE = OUT / "phase6g3_freeze_manifest.json"
RENDERED = OUT / "phase6g3_real_rendered_prompts.jsonl"
HASH_MANIFEST = OUT / "phase6g3_prompt_hash_manifest.json"
CONDITION_AUDIT = OUT / "phase6g3_condition_integrity_audit.json"
LEAKAGE_AUDIT = OUT / "phase6g3_leakage_audit.json"
SIZE_AUDIT = OUT / "phase6g3_prompt_size_audit.json"
CONTEXT_AUDIT = OUT / "phase6g3_context_compatibility_audit.json"
REQUESTS = OUT / "phase6g3_final_request_manifest.json"
READINESS_6G2D = REPO_ROOT / "llm-experiments" / "outputs" / "real" / "phase6g2d" / "phase6g2d_final_readiness.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def rendered_rows() -> list[dict]:
    return load_jsonl(RENDERED)


def source_rows() -> list[dict]:
    return load_jsonl(PROMPT_DATA)


def test_source_real_phase6b_hash_and_counts_verified() -> None:
    freeze = load_json(FREEZE)
    phase6g1 = load_json(PHASE6G1_MANIFEST)

    assert freeze["source_real_phase6b_prompt_data_sha256"] == sha256_file(PROMPT_DATA)
    assert freeze["source_real_phase6b_hash_verified"] is True
    assert phase6g1["REAL_PHASE6B_READY"] is True
    assert phase6g1["counts"]["prediction_example_count"] == 198
    assert phase6g1["counts"]["condition_object_count"] == 396
    assert phase6g1["counts"]["expected_four_model_primary_inference_count"] == 1584


def test_396_rendered_prompts_two_conditions_and_message_contract() -> None:
    rows = rendered_rows()
    counts = Counter(row["condition"] for row in rows)

    assert len(rows) == 396
    assert counts == {"non_history": 198, "personalised_history": 198}
    for row in rows:
        assert [message["role"] for message in row["messages"]] == ["system", "user"]
        assert row["messages"][0]["content"] == SYSTEM_INSTRUCTION
        assert row["prompt_spec_version"] == "phase6d_prompt_spec_v1"
        assert row["response_schema_version"] == "preference_prediction_response_v1"


def test_target_candidate_contract_and_acoustic_rendering() -> None:
    sources = source_rows()
    for row in sources:
        candidates = row["model_input"]["target"]["candidates"]
        assert [candidate["label"] for candidate in candidates] == EXPECTED_LABELS
        for candidate in candidates:
            assert set(candidate["acoustic_features"]) == {"z_RMS", "z_CF", "z_SW"}
            assert "human_rating" not in candidate
    first_user = rendered_rows()[0]["messages"][1]["content"]
    assert "RMS z-score:" in first_user
    assert re.search(r"RMS z-score: -?\d+\.\d{2}", first_user)
    assert "z_SI" not in "\n".join(row["messages"][1]["content"] for row in rendered_rows())


def test_participant_metadata_contract_is_exact() -> None:
    expected_labels = list(PARTICIPANT_METADATA_LABELS.values())
    for row in source_rows():
        assert set(row["model_input"]["participant_metadata"]) == set(PARTICIPANT_METADATA_LABELS)
    sample = rendered_rows()[0]["messages"][1]["content"]
    for label in expected_labels:
        assert f"- {label}:" in sample


def test_history_and_non_history_contracts() -> None:
    for row in source_rows():
        if row["condition"] == "personalised_history":
            history = row["model_input"]["history"]
            target_order = row["model_input"]["target"]["trial_order"]
            assert len(history) == 5
            assert all(trial["trial_order"] != target_order for trial in history)
            assert [trial["trial_order"] for trial in history] == sorted(trial["trial_order"] for trial in history)
        else:
            assert "history" not in row["model_input"]
    for row in rendered_rows():
        text = row["messages"][1]["content"]
        if row["condition"] == "non_history":
            assert "Previous listening evidence from this participant" not in text
            assert "Participant rating:" not in text
            assert "Participant comparative comment:" not in text
        else:
            assert text.count("Previous trial ") == 5


def test_condition_equivalence_and_leakage_audits_pass() -> None:
    condition = load_json(CONDITION_AUDIT)
    leakage = load_json(LEAKAGE_AUDIT)

    assert condition["matched_pair_count"] == 198
    assert condition["valid_pair_count"] == 198
    assert condition["pair_equivalence_failures"] == 0
    assert condition["comment_boundary_failures"] == 0
    assert condition["EXPERIMENTAL_CONDITION_INTEGRITY"] is True
    assert leakage["leakage_failures"] == 0
    assert leakage["target_leakage_failures"] == 0
    assert leakage["identifier_provenance_leakage_failures"] == 0
    assert leakage["sensitivity_feature_leakage_failures"] == 0
    assert leakage["history_target_overlap_failures"] == 0


def test_rendered_text_has_no_forbidden_provenance_or_target_outcome_tokens() -> None:
    text = "\n".join("\n".join(message["content"] for message in row["messages"]) for row in rendered_rows())
    forbidden = [
        "stimulus_id",
        "actual_mix_id",
        "audio_path",
        ".wav",
        "z_SI",
        "ground_truth",
        "observed_preferred",
        "observed_rank",
        "Target comparative comment",
    ]
    for token in forbidden:
        assert token not in text


def test_deterministic_rebuild_and_prompt_hashes_stable() -> None:
    freeze = load_json(FREEZE)
    hashes = load_json(HASH_MANIFEST)

    assert freeze["deterministic_rendering_status"]["deterministic_rendering_passed"] is True
    assert freeze["deterministic_rendering_status"]["ids_identical"] is True
    assert freeze["deterministic_rendering_status"]["prompt_hashes_identical"] is True
    assert hashes["rendered_prompt_count"] == 396
    assert len(hashes["records"]) == 396
    assert len({row["message_payload_sha256"] for row in hashes["records"]}) == 396
    first = rendered_rows()[0]
    first_hash = next(row for row in hashes["records"] if row["rendered_prompt_id"] == first["rendered_prompt_id"])
    assert first_hash["message_payload_sha256"] == sha256_json(first["messages"])


def test_size_and_context_compatibility_pass() -> None:
    size = load_json(SIZE_AUDIT)
    context = load_json(CONTEXT_AUDIT)
    context_rows = {row["model_key"]: row for row in context["models"]}

    assert size["history_trial_count_distribution"] == {"5": 198}
    assert size["maximum_history_trials"] == 5
    assert size["condition_size_summary"]["non_history"]["count"] == 198
    assert size["condition_size_summary"]["personalised_history"]["count"] == 198
    assert context["context_compatibility_passes"] is True
    assert context_rows["llama_3_1_70b_instruct"]["context_limit_tokens"] == 131072
    assert context_rows["centaur"]["context_limit_tokens"] == 32768
    assert context_rows["centaur"]["remaining_token_margin"] > 0


def test_centaur_serialization_and_choice_marker_decision() -> None:
    centaur = load_json(CONTEXT_AUDIT)["centaur_serialization"]

    assert centaur["chat_template"] == "absent"
    assert centaur["effective_context_limit"] == 32768
    assert centaur["preserves_semantic_text_exactly"] is True
    assert centaur["adds_model_specific_task_hints"] is False
    assert centaur["uses_double_angle_choice_markers"] is False
    assert centaur["choice_marker_decision"]["recommendation_exists"] is True
    assert centaur["choice_marker_decision"]["technically_required"] is False
    assert "<<" not in json.dumps(rendered_rows())
    assert ">>" not in json.dumps(rendered_rows())


def test_request_matrix_and_shards_complete_without_predictions() -> None:
    requests = load_json(REQUESTS)

    assert requests["request_count"] == 1584
    assert requests["contains_llm_predictions"] is False
    assert requests["contains_hidden_ground_truth"] is False
    assert requests["hidden_ground_truth_loaded"] is False
    for model_key, coverage in requests["model_condition_coverage"].items():
        assert coverage == {"non_history": 198, "personalised_history": 198, "total": 396}
    assert len({row["request_id"] for row in requests["requests"]}) == 1584
    assert load_json(OUT / "phase6g3_qmul_gpt_shard_manifest.json")["request_count"] == 396
    assert load_json(OUT / "phase6g3_qmul_claude_shard_manifest.json")["request_count"] == 396
    assert load_json(OUT / "phase6g3_qmul_llama_shard_manifest.json")["request_count"] == 396
    assert load_json(OUT / "phase6g3_qmul_all_shard_manifest.json")["request_count"] == 1188
    assert load_json(OUT / "phase6g3_runpod_centaur_shard_manifest.json")["request_count"] == 396


def test_ground_truth_isolation_and_no_secret_artifacts() -> None:
    for path in [FREEZE, HASH_MANIFEST, CONDITION_AUDIT, LEAKAGE_AUDIT, SIZE_AUDIT, CONTEXT_AUDIT, REQUESTS]:
        payload = load_json(path)
        assert_no_secrets(payload)
    request_text = REQUESTS.read_text(encoding="utf-8").lower()
    assert "final_trial_ground_truth" not in request_text
    assert "final_candidate_ground_truth" not in request_text
    assert "baseline" not in request_text
    assert "evaluation" not in request_text


def test_phase6d_and_phase6g2d_gates_remain_verified() -> None:
    freeze = load_json(FREEZE)
    readiness_6g2d = load_json(READINESS_6G2D)

    assert verify_prompt_package(REPO_ROOT)["PHASE6D_PROMPT_PACKAGE_FROZEN"] is True
    assert readiness_6g2d["PRODUCTION_INFERENCE_READY"] is True
    assert freeze["gate_inputs"]["phase6g2d_production_config_ready"] is True
    assert freeze["REAL_PRODUCTION_PROMPTS_FROZEN"] is True
    assert freeze["PHASE6G3_COMPLETE"] is True
    assert freeze["PHASE6G4_CAN_BEGIN_IMMEDIATELY"] is True
