import csv
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.data.examples import (  # noqa: E402
    build_prediction_examples_from_csv,
    validate_no_target_leakage,
    write_prediction_example_outputs,
)


PHASE6B2_DIR = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6b2"
EDGE_DIR = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6b2_edge_cases"
CANDIDATES = PHASE6B2_DIR / "candidate_ground_truth_enriched.csv"
TARGETS = PHASE6B2_DIR / "trial_ground_truth_targets.csv"
EDGE_CANDIDATES = EDGE_DIR / "candidate_ground_truth_enriched.csv"
EDGE_TARGETS = EDGE_DIR / "trial_ground_truth_targets.csv"


def build_main_examples():
    examples, summary = build_prediction_examples_from_csv(CANDIDATES, TARGETS)
    return examples, summary


def by_target_trial(examples):
    return {example["input_data"]["target"]["trial_id"]: example for example in examples}


def test_six_eligible_trials_produce_six_prediction_examples_for_complete_participant():
    examples, summary = build_main_examples()
    p1_examples = [example for example in examples if example["participant_id"] == "SYNTHETIC_PHASE6B1_P001"]
    assert len(p1_examples) == 6
    assert summary["canonical_row_unit"] == "participant x held_out_target_trial"
    assert summary["prediction_example_count"] == 11


def test_each_complete_example_has_five_history_trials_and_target_is_excluded():
    examples, _ = build_main_examples()
    p1_examples = [example for example in examples if example["participant_id"] == "SYNTHETIC_PHASE6B1_P001"]
    assert all(example["n_history_trials"] == 5 for example in p1_examples)
    for example in p1_examples:
        target_id = example["input_data"]["target"]["trial_id"]
        history_ids = [trial["trial_id"] for trial in example["input_data"]["history"]]
        assert target_id not in history_ids


def test_history_order_follows_original_trial_order_then_trial_id():
    examples, _ = build_main_examples()
    example = by_target_trial(examples)["SYNTHETIC_PHASE6B1_P001__trial_03"]
    assert [trial["trial_order"] for trial in example["input_data"]["history"]] == [1, 2, 4, 5, 6]


def test_target_candidates_appear_once_each_in_a_to_e_order_with_acoustic_features():
    examples, _ = build_main_examples()
    target_candidates = examples[0]["input_data"]["target"]["candidates"]
    assert [candidate["presentation_label"] for candidate in target_candidates] == ["A", "B", "C", "D", "E"]
    assert len({candidate["presentation_label"] for candidate in target_candidates}) == 5
    for candidate in target_candidates:
        assert candidate["z_RMS"] is not None
        assert candidate["z_CF"] is not None
        assert candidate["z_SW"] is not None
        assert candidate["z_SI"] is not None


def test_target_candidates_do_not_expose_target_ratings_comments_or_preference_fields():
    examples, _ = build_main_examples()
    example = examples[0]
    target_payload = json.dumps(example["input_data"]["target"], sort_keys=True)
    forbidden_tokens = [
        "human_rating",
        "comparative_comment",
        "observed_preferred_set",
        "observed_preferred_mix",
        "observed_rank",
        "is_observed_preferred",
        "observed_max_rating",
    ]
    assert not any(token in target_payload for token in forbidden_tokens)
    assert "SYNTHETIC TEST COMMENT SYNTHETIC_PHASE6B1_P001 trial 1." not in json.dumps(example["input_data"])


def test_participant_metadata_are_attached_and_missingness_is_preserved():
    examples, _ = build_main_examples()
    p1 = next(example for example in examples if example["participant_id"] == "SYNTHETIC_PHASE6B1_P001")
    p2 = next(example for example in examples if example["participant_id"] == "SYNTHETIC_PHASE6B1_P002")
    assert p1["input_data"]["participant_metadata"]["music_listening_habits"] == "daily"
    assert p2["input_data"]["participant_metadata"]["hearing_difficulty"] is None


def test_eligible_history_ratings_and_comments_are_preserved_for_history_only():
    examples, _ = build_main_examples()
    example = by_target_trial(examples)["SYNTHETIC_PHASE6B1_P001__trial_03"]
    first_history = example["input_data"]["history"][0]
    assert first_history["comparative_comment"] == "SYNTHETIC TEST COMMENT SYNTHETIC_PHASE6B1_P001 trial 1."
    assert [candidate["human_rating"] for candidate in first_history["candidates"]] == [39, 40, 41, 42, 43]


def test_ineligible_history_trial_is_excluded_and_ineligible_target_is_not_generated():
    examples, summary = build_main_examples()
    p2_examples = [example for example in examples if example["participant_id"] == "SYNTHETIC_PHASE6B1_P002"]
    assert len(p2_examples) == 5
    assert "SYNTHETIC_PHASE6B1_P002__trial_06" not in by_target_trial(examples)
    assert all(example["n_history_trials"] == 4 for example in p2_examples)
    assert summary["target_ineligible_trial_count"] == 1
    assert "missing_candidate" in summary["target_ineligibility_reason_counts"]


def test_missing_history_comment_remains_null_without_excluding_history_trial():
    candidate_rows = load_rows(CANDIDATES)
    target_rows = load_rows(TARGETS)
    for row in candidate_rows:
        if row["trial_id"] == "SYNTHETIC_PHASE6B1_P001__trial_02":
            row["comparative_comment"] = ""
    examples, _ = build_prediction_examples_from_rows(candidate_rows, target_rows)
    example = by_target_trial(examples)["SYNTHETIC_PHASE6B1_P001__trial_01"]
    history_trial_2 = next(trial for trial in example["input_data"]["history"] if trial["trial_id"].endswith("trial_02"))
    assert history_trial_2["comparative_comment"] is None
    assert history_trial_2["history_comment_available"] is True


def test_valid_target_with_missing_participant_metadata_remains_generated():
    examples, _ = build_main_examples()
    p2_trial = by_target_trial(examples)["SYNTHETIC_PHASE6B1_P002__trial_01"]
    assert p2_trial["input_data"]["participant_metadata"]["hearing_difficulty"] is None
    assert p2_trial["ground_truth"]["observed_preferred_set"] == ["E"]


def test_hidden_ground_truth_retains_tie_sets_but_target_input_does_not_reveal_them():
    examples, _ = build_prediction_examples_from_csv(EDGE_CANDIDATES, EDGE_TARGETS)
    tied = by_target_trial(examples)["SYNTHETIC_PHASE6B2_EDGE_P001__trial_02"]
    assert tied["ground_truth"]["observed_preferred_set"] == ["A", "C"]
    assert tied["ground_truth"]["observed_preferred_mix"] is None
    target_payload = json.dumps(tied["input_data"]["target"], sort_keys=True)
    assert "observed_preferred_set" not in target_payload
    assert "human_rating" not in target_payload


def test_personalised_history_availability_is_true_when_any_history_exists():
    examples, summary = build_main_examples()
    assert all(example["personalised_history_available"] is True for example in examples)
    assert summary["examples_without_personalised_history_available"] == 0


def test_prediction_example_id_and_jsonl_output_are_deterministic(tmp_path):
    first_examples, _ = build_main_examples()
    second_examples, _ = build_main_examples()
    assert [example["prediction_example_id"] for example in first_examples] == [
        example["prediction_example_id"] for example in second_examples
    ]
    assert first_examples == second_examples

    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_jsonl, first_summary, _ = write_prediction_example_outputs(CANDIDATES, TARGETS, first_dir)
    second_jsonl, second_summary, _ = write_prediction_example_outputs(CANDIDATES, TARGETS, second_dir)
    assert first_jsonl.read_text(encoding="utf-8") == second_jsonl.read_text(encoding="utf-8")
    assert json.loads(first_summary.read_text(encoding="utf-8")) == json.loads(second_summary.read_text(encoding="utf-8"))


def test_leakage_validator_rejects_target_rating_and_self_history():
    examples, _ = build_main_examples()
    rating_leak = json.loads(json.dumps(examples[0]))
    rating_leak["input_data"]["target"]["candidates"][0]["human_rating"] = 99
    try:
        validate_no_target_leakage(rating_leak, [])
    except ValueError as exc:
        assert "leaks outcome fields" in str(exc)
    else:
        raise AssertionError("Expected leakage validator to reject target human_rating.")

    self_history = json.loads(json.dumps(examples[0]))
    self_history["input_data"]["history"].append({"trial_id": self_history["input_data"]["target"]["trial_id"]})
    try:
        validate_no_target_leakage(self_history, [])
    except ValueError as exc:
        assert "own history" in str(exc)
    else:
        raise AssertionError("Expected leakage validator to reject target trial in history.")


def load_rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_prediction_examples_from_rows(candidate_rows, target_rows):
    from llm_experiments.data.examples import build_prediction_examples

    return build_prediction_examples(candidate_rows, target_rows)

