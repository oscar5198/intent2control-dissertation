import csv
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.data.targets import (  # noqa: E402
    build_preference_targets_from_csv,
    derive_observed_ranks,
    derive_preferred_set,
    write_preference_target_outputs,
)


EDGE_FIXTURE = REPO_ROOT / "llm-experiments" / "fixtures" / "synthetic" / "phase6b2_edge_cases_analysis_ready_long.csv"
PHASE6B1_OUTPUT = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6b1" / "analysis_ready_long.csv"


def build_edges():
    enriched, trial_targets, summary, _ = build_preference_targets_from_csv(EDGE_FIXTURE)
    targets = {int(target["trial_order"]): target for target in trial_targets}
    return enriched, targets, summary


def preferred_set(target):
    return json.loads(target["observed_preferred_set"]) if target["observed_preferred_set"] else []


def test_unique_maximum_produces_one_preferred_candidate():
    enriched, targets, _ = build_edges()
    target = targets[1]
    assert target["target_eligible"] is True
    assert preferred_set(target) == ["C"]
    assert target["observed_preferred_mix"] == "C"
    assert target["is_single_winner"] is True
    assert target["n_preferred_tied"] == 1
    preferred_rows = [row for row in enriched if int(row["trial_order"]) == 1 and row["is_observed_preferred"]]
    assert [row["presentation_label"] for row in preferred_rows] == ["C"]


def test_two_way_maximum_tie_produces_two_label_preferred_set_without_unique_winner():
    _, targets, _ = build_edges()
    target = targets[2]
    assert preferred_set(target) == ["A", "C"]
    assert target["observed_preferred_mix"] == ""
    assert target["is_single_winner"] is False
    assert target["n_preferred_tied"] == 2


def test_multi_way_and_all_five_ties_are_retained_without_arbitrary_tie_breaking():
    _, targets, _ = build_edges()
    assert preferred_set(targets[3]) == ["A", "B", "C"]
    assert targets[3]["observed_preferred_mix"] == ""
    assert targets[3]["n_preferred_tied"] == 3
    assert preferred_set(targets[4]) == ["A", "B", "C", "D", "E"]
    assert targets[4]["is_single_winner"] is False
    assert targets[4]["n_preferred_tied"] == 5


def test_non_maximum_rating_tie_affects_rank_but_not_preferred_set_size():
    _, targets, _ = build_edges()
    target = targets[5]
    assert preferred_set(target) == ["A"]
    assert target["n_preferred_tied"] == 1
    assert target["observed_rank_B"] == "2.5"
    assert target["observed_rank_C"] == "2.5"


def test_rank_convention_uses_descending_average_ranks():
    ranks = derive_observed_ranks({"A": 90, "B": 70, "C": 90, "D": 50, "E": 80})
    assert ranks == {"A": 1.5, "C": 1.5, "E": 3.0, "B": 4.0, "D": 5.0}


def test_preferred_set_serialization_is_deterministic_a_to_e_json():
    _, targets, _ = build_edges()
    assert targets[2]["observed_preferred_set"] == '["A","C"]'
    assert targets[4]["observed_preferred_set"] == '["A","B","C","D","E"]'


def test_missing_rating_makes_target_ineligible_with_reason_code():
    _, targets, _ = build_edges()
    target = targets[6]
    assert target["target_eligible"] is False
    assert target["target_ineligibility_reasons"] == "missing_rating"
    assert target["observed_preferred_set"] == ""


def test_out_of_range_rating_makes_target_ineligible_with_reason_code():
    _, targets, _ = build_edges()
    target = targets[7]
    assert target["target_eligible"] is False
    assert target["target_ineligibility_reasons"] == "rating_out_of_range"


def test_malformed_candidate_mapping_makes_target_ineligible():
    _, targets, _ = build_edges()
    target = targets[8]
    assert target["target_eligible"] is False
    assert target["target_ineligibility_reasons"] == "duplicate_candidate_mapping"


def test_participant_metadata_missingness_does_not_invalidate_target_ground_truth():
    _, targets, _ = build_edges()
    target = targets[9]
    assert target["target_eligible"] is True
    assert preferred_set(target) == ["A"]
    assert target["target_ineligibility_reasons"] == ""


def test_candidate_level_preferred_indicators_match_preferred_set_for_ties():
    enriched, _, _ = build_edges()
    preferred = [
        row["presentation_label"]
        for row in enriched
        if int(row["trial_order"]) == 2 and row["is_observed_preferred"]
    ]
    assert preferred == ["A", "C"]
    assert all(not row["is_observed_preferred"] for row in enriched if int(row["trial_order"]) == 7)


def test_history_eligibility_is_distinct_but_uses_rating_mapping_requirements():
    _, targets, _ = build_edges()
    assert targets[1]["history_eligible"] is True
    assert targets[6]["history_eligible"] is False
    assert targets[6]["history_ineligibility_reasons"] == "missing_rating"


def test_pure_preferred_set_derivation_handles_ties():
    observed_max, labels, preferred_mix, is_single, n_tied = derive_preferred_set(
        {"A": 90, "B": 70, "C": 90, "D": 50, "E": 80}
    )
    assert observed_max == 90
    assert labels == ["A", "C"]
    assert preferred_mix == ""
    assert is_single is False
    assert n_tied == 2


def test_rerunning_target_construction_produces_identical_outputs():
    first = build_preference_targets_from_csv(EDGE_FIXTURE)
    second = build_preference_targets_from_csv(EDGE_FIXTURE)
    assert first[0] == second[0]
    assert first[1] == second[1]
    assert first[2] == second[2]


def test_phase6b1_synthetic_output_can_be_target_enriched_without_breaking_compatibility():
    enriched, trial_targets, summary, _ = build_preference_targets_from_csv(PHASE6B1_OUTPUT)
    assert len(enriched) == 59
    assert len(trial_targets) == 12
    assert summary["target_eligible_trial_count"] == 11
    assert summary["target_ineligible_trial_count"] == 1
    assert "missing_candidate" in summary["target_ineligibility_reason_counts"]


def test_write_preference_target_outputs_creates_candidate_and_trial_tables(tmp_path):
    candidate_path, trial_path, summary_path = write_preference_target_outputs(EDGE_FIXTURE, tmp_path)
    assert candidate_path.exists()
    assert trial_path.exists()
    assert summary_path.exists()
    with trial_path.open("r", encoding="utf-8", newline="") as handle:
        trial_rows = list(csv.DictReader(handle))
    assert trial_rows[0]["observed_preferred_set"] == '["C"]'
    assert trial_rows[1]["observed_preferred_set"] == '["A","C"]'
    with candidate_path.open("r", encoding="utf-8", newline="") as handle:
        candidate_rows = list(csv.DictReader(handle))
    assert "is_observed_preferred" in candidate_rows[0]
    assert "observed_rank" in candidate_rows[0]
