import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.data.prompt_data import (  # noqa: E402
    build_condition_objects,
    build_condition_objects_from_jsonl,
    validate_condition_pair,
    validate_prompt_data_no_leakage,
    write_prompt_data_outputs,
)


PHASE6B3_JSONL = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6b3" / "prediction_examples.jsonl"
EDGE_PHASE6B3_JSONL = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6b3_edge_cases" / "prediction_examples.jsonl"


def build_main_objects():
    return build_condition_objects_from_jsonl(PHASE6B3_JSONL)


def load_examples(path=PHASE6B3_JSONL):
    examples = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                examples.append(json.loads(line))
    return examples


def grouped_by_example(objects):
    grouped = {}
    for obj in objects:
        grouped.setdefault(obj["prediction_example_id"], {})[obj["condition"]] = obj
    return grouped


def test_every_prediction_example_produces_non_history_and_available_history_condition():
    objects, summary = build_main_objects()
    grouped = grouped_by_example(objects)
    assert summary["prediction_examples_read"] == 11
    assert summary["non_history_object_count"] == 11
    assert summary["personalised_history_object_count"] == 11
    assert summary["condition_object_count"] == 22
    assert all("non_history" in pair for pair in grouped.values())
    assert all("personalised_history" in pair for pair in grouped.values())


def test_personalised_history_omitted_when_history_unavailable():
    examples = load_examples()
    no_history = json.loads(json.dumps(examples[0]))
    no_history["prediction_example_id"] = "SYNTHETIC_NO_HISTORY"
    no_history["input_data"]["history"] = []
    no_history["n_history_trials"] = 0
    no_history["personalised_history_available"] = False
    objects, summary = build_condition_objects([no_history])
    assert [obj["condition"] for obj in objects] == ["non_history"]
    assert summary["examples_lacking_personalised_history"] == 1


def test_paired_target_and_metadata_payloads_are_identical_across_conditions():
    objects, summary = build_main_objects()
    assert summary["paired_condition_equivalence_failures"] == 0
    for pair in grouped_by_example(objects).values():
        validate_condition_pair(pair["non_history"], pair["personalised_history"])
        assert pair["non_history"]["model_input"]["target"] == pair["personalised_history"]["model_input"]["target"]
        assert pair["non_history"]["model_input"]["participant_metadata"] == pair["personalised_history"]["model_input"]["participant_metadata"]


def test_target_candidates_are_a_to_e_and_use_primary_acoustic_features_only():
    objects, _ = build_main_objects()
    target_candidates = objects[0]["model_input"]["target"]["candidates"]
    assert [candidate["label"] for candidate in target_candidates] == ["A", "B", "C", "D", "E"]
    for candidate in target_candidates:
        assert set(candidate["acoustic_features"]) == {"z_RMS", "z_CF", "z_SW"}
        assert "z_SI" not in json.dumps(candidate)


def test_target_ratings_comments_preference_tie_fields_and_ground_truth_are_absent():
    objects, _ = build_main_objects()
    non_history = objects[0]
    payload = json.dumps(non_history["model_input"], sort_keys=True)
    forbidden_tokens = [
        "human_rating",
        "comparative_comment",
        "observed_rank",
        "observed_preferred_set",
        "observed_preferred_mix",
        "observed_max_rating",
        "is_single_winner",
        "n_preferred_tied",
        "ground_truth",
        "SYNTHETIC TEST COMMENT SYNTHETIC_PHASE6B1_P001 trial 1.",
    ]
    assert not any(token in payload for token in forbidden_tokens)
    assert "ground_truth" not in non_history


def test_history_absent_in_non_history_but_ratings_and_comments_present_in_personalised_history():
    objects, _ = build_main_objects()
    pair = grouped_by_example(objects)["SYNTHETIC_PHASE6B1_P001__heldout__SYNTHETIC_PHASE6B1_P001__trial_01"]
    assert "history" not in pair["non_history"]["model_input"]
    history = pair["personalised_history"]["model_input"]["history"]
    assert history[0]["comparative_comment"] == "SYNTHETIC TEST COMMENT SYNTHETIC_PHASE6B1_P001 trial 2."
    assert [candidate["human_rating"] for candidate in history[0]["candidates"]] == [42, 43, 44, 45, 46]


def test_missing_history_comment_remains_null():
    examples = load_examples()
    modified = json.loads(json.dumps(examples[0]))
    modified["prediction_example_id"] = "SYNTHETIC_MISSING_HISTORY_COMMENT"
    modified["input_data"]["history"][0]["comparative_comment"] = None
    objects, _ = build_condition_objects([modified])
    personalised = next(obj for obj in objects if obj["condition"] == "personalised_history")
    assert personalised["model_input"]["history"][0]["comparative_comment"] is None


def test_missing_participant_metadata_remains_null():
    objects, _ = build_main_objects()
    p2 = next(obj for obj in objects if obj["prediction_example_id"].startswith("SYNTHETIC_PHASE6B1_P002") and obj["condition"] == "non_history")
    assert p2["model_input"]["participant_metadata"]["hearing_difficulty"] is None


def test_target_tie_information_does_not_leak_into_prompt_data():
    objects, _ = build_condition_objects_from_jsonl(EDGE_PHASE6B3_JSONL)
    tied = next(
        obj
        for obj in objects
        if obj["prediction_example_id"].endswith("trial_02") and obj["condition"] == "personalised_history"
    )
    payload = json.dumps(tied["model_input"], sort_keys=True)
    assert "observed_preferred_set" not in payload
    assert "observed_preferred_mix" not in payload
    assert "n_preferred_tied" not in payload


def test_underlying_target_mix_ids_paths_and_stimulus_ids_are_not_model_facing():
    objects, _ = build_main_objects()
    payload = json.dumps(objects[0]["model_input"], sort_keys=True)
    forbidden = ["stimulus_id", "actual_mix_id", "audio_path", "acoustic_feature_table_used", "lead_me_du_e", "mix_271852ba8676", ".wav"]
    assert not any(token in payload for token in forbidden)


def test_acoustic_values_are_serialized_to_four_decimal_places():
    objects, _ = build_main_objects()
    first_features = objects[0]["model_input"]["target"]["candidates"][0]["acoustic_features"]
    assert first_features == {"z_RMS": -1.0251, "z_CF": 0.52, "z_SW": -0.8666}


def test_condition_ids_and_serialization_are_deterministic(tmp_path):
    first, _ = build_main_objects()
    second, _ = build_main_objects()
    assert first == second
    assert [obj["condition_object_id"] for obj in first] == [obj["condition_object_id"] for obj in second]

    first_path, first_summary, _ = write_prompt_data_outputs(PHASE6B3_JSONL, tmp_path / "first")
    second_path, second_summary, _ = write_prompt_data_outputs(PHASE6B3_JSONL, tmp_path / "second")
    assert first_path.read_text(encoding="utf-8") == second_path.read_text(encoding="utf-8")
    assert json.loads(first_summary.read_text(encoding="utf-8")) == json.loads(second_summary.read_text(encoding="utf-8"))


def test_pair_validation_catches_target_mismatch():
    objects, _ = build_main_objects()
    pair = grouped_by_example(objects)["SYNTHETIC_PHASE6B1_P001__heldout__SYNTHETIC_PHASE6B1_P001__trial_01"]
    altered = json.loads(json.dumps(pair["personalised_history"]))
    altered["model_input"]["target"]["candidates"][0]["acoustic_features"]["z_RMS"] = 123
    try:
        validate_condition_pair(pair["non_history"], altered)
    except ValueError as exc:
        assert "target payloads" in str(exc)
    else:
        raise AssertionError("Expected paired-condition validation to catch target mismatch.")


def test_leakage_validator_is_context_aware_for_history_ratings_but_rejects_target_rating():
    objects, _ = build_main_objects()
    personalised = next(obj for obj in objects if obj["condition"] == "personalised_history")
    validate_prompt_data_no_leakage(personalised)
    leaked = json.loads(json.dumps(personalised))
    leaked["model_input"]["target"]["candidates"][0]["human_rating"] = 99
    try:
        validate_prompt_data_no_leakage(leaked)
    except ValueError as exc:
        assert "human_rating" in str(exc)
    else:
        raise AssertionError("Expected leakage validator to reject target human_rating.")
