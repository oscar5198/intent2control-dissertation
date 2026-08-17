import csv
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.data.processing import (  # noqa: E402
    CANONICAL_COLUMNS,
    build_analysis_ready_dataset,
    write_analysis_ready_outputs,
)


FIXTURE = REPO_ROOT / "llm-experiments" / "fixtures" / "synthetic" / "phase6b1_five_mix_netlify_export.csv"
STIMULI = REPO_ROOT / "study-interface" / "frontend-5mix" / "config" / "stimuli.json"
FEATURES = REPO_ROOT / "statistical-baseline" / "outputs" / "feature_exploration" / "final_20_stimulus_feature_table.csv"


def build_rows():
    rows, issues, summary, feature_audit = build_analysis_ready_dataset(FIXTURE, STIMULI, FEATURES)
    return rows, issues, summary, feature_audit


def test_canonical_output_contains_one_row_per_participant_trial_candidate():
    rows, _, summary, _ = build_rows()
    assert summary["canonical_row_unit"] == "participant x trial x candidate_mix"
    assert summary["participant_count"] == 2
    assert summary["candidate_row_count"] == len(rows)
    assert len(rows) == 59
    assert set(CANONICAL_COLUMNS).issuperset(rows[0].keys())


def test_complete_synthetic_participant_produces_30_candidate_rows():
    rows, _, _, _ = build_rows()
    p1_rows = [row for row in rows if row["participant_id"] == "SYNTHETIC_PHASE6B1_P001"]
    assert len(p1_rows) == 30
    assert len({row["trial_id"] for row in p1_rows}) == 6


def test_complete_trial_has_five_unique_a_to_e_rows_and_valid_mapping():
    rows, _, _, _ = build_rows()
    trial_rows = [
        row
        for row in rows
        if row["participant_id"] == "SYNTHETIC_PHASE6B1_P001" and row["trial_order"] == 1
    ]
    assert len(trial_rows) == 5
    assert [row["presentation_label"] for row in trial_rows] == ["A", "B", "C", "D", "E"]
    assert len({row["stimulus_id"] for row in trial_rows}) == 5
    assert {row["trial_validation_status"] for row in trial_rows} == {"complete"}


def test_underlying_stimulus_mapping_is_reconstructed_from_raw_mapping_metadata():
    rows, _, _, _ = build_rows()
    with FIXTURE.open("r", encoding="utf-8", newline="") as handle:
        raw_p1 = next(row for row in csv.DictReader(handle) if row["study_id"] == "SYNTHETIC_PHASE6B1_P001")
    mapping = json.loads(raw_p1["mix_mapping_json"])
    trial_row = next(
        row
        for row in rows
        if row["participant_id"] == "SYNTHETIC_PHASE6B1_P001"
        and row["episode_id"] == "EDR-1"
        and row["song_id"] == "lead_me"
        and row["presentation_label"] == "A"
    )
    assert trial_row["stimulus_id"] == mapping["EDR-1"]["lead_me"]["A"]
    assert trial_row["active_stimulus_match"] is True


def test_ratings_remain_attached_to_presented_candidate_and_comments_repeat_across_trial():
    rows, _, _, _ = build_rows()
    trial_rows = [
        row
        for row in rows
        if row["participant_id"] == "SYNTHETIC_PHASE6B1_P001" and row["trial_order"] == 2
    ]
    ratings_by_label = {row["presentation_label"]: row["human_rating"] for row in trial_rows}
    assert ratings_by_label == {"A": 42, "B": 43, "C": 44, "D": 45, "E": 46}
    assert {row["comparative_comment"] for row in trial_rows} == {
        "SYNTHETIC TEST COMMENT SYNTHETIC_PHASE6B1_P001 trial 2."
    }


def test_participant_metadata_are_consistent_and_missingness_is_preserved():
    rows, _, _, _ = build_rows()
    p1_values = {row["music_listening_habits"] for row in rows if row["participant_id"] == "SYNTHETIC_PHASE6B1_P001"}
    p2_missing = {
        row["participant_metadata_missing_fields"]
        for row in rows
        if row["participant_id"] == "SYNTHETIC_PHASE6B1_P002"
    }
    assert p1_values == {"daily"}
    assert p2_missing == {"hearing_difficulty"}


def test_acoustic_features_join_to_correct_stimulus_and_primary_features_are_available():
    rows, _, _, _ = build_rows()
    feature_rows = {}
    with FEATURES.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            feature_rows[row["stimulus_id"]] = row
    row = next(row for row in rows if row["stimulus_id"] == "lead_me_du_e")
    assert row["z_RMS"] == feature_rows["lead_me_du_e"]["z_RMS"]
    assert row["z_CF"] != ""
    assert row["z_SW"] != ""
    assert row["z_SI"] != ""
    assert row["z_SI_role"] == "optional_qc_sensitivity_predictor"
    assert row["feature_join_status"] == "matched"


def test_trial_ids_are_unique_at_participant_trial_level_and_deterministic():
    rows_a, _, _, _ = build_rows()
    rows_b, _, _, _ = build_rows()
    ids_a = [row["trial_id"] for row in rows_a]
    ids_b = [row["trial_id"] for row in rows_b]
    assert ids_a == ids_b
    assert len({(row["participant_id"], row["trial_order"], row["trial_id"]) for row in rows_a}) == 12
    assert "SYNTHETIC_PHASE6B1_P001__trial_01" in ids_a


def test_malformed_or_incomplete_trials_are_flagged_not_repaired():
    rows, issues, summary, _ = build_rows()
    incomplete_rows = [
        row
        for row in rows
        if row["participant_id"] == "SYNTHETIC_PHASE6B1_P002" and row["trial_order"] == 6
    ]
    assert len(incomplete_rows) == 4
    assert {row["trial_validation_status"] for row in incomplete_rows} == {"incomplete"}
    assert any(issue["code"] == "incomplete_trial_row_count" for issue in issues)
    assert summary["incomplete_or_malformed_trial_count"] == 1


def test_no_preference_or_winner_labels_are_constructed_in_phase6b1():
    rows, _, summary, _ = build_rows()
    forbidden = ("preferred", "winner", "winning", "observed_ranking", "preference_label")
    assert summary["contains_preference_labels"] is False
    assert not any(any(token in column.lower() for token in forbidden) for column in rows[0].keys())


def test_write_outputs_creates_stable_analysis_ready_files(tmp_path):
    analysis_path, issues_path, summary_path, feature_audit_path = write_analysis_ready_outputs(
        FIXTURE,
        STIMULI,
        FEATURES,
        tmp_path,
    )
    assert analysis_path.exists()
    assert issues_path.exists()
    assert summary_path.exists()
    assert feature_audit_path.exists()
    with analysis_path.open("r", encoding="utf-8", newline="") as handle:
        written_rows = list(csv.DictReader(handle))
    assert written_rows[0]["participant_id"] == "SYNTHETIC_PHASE6B1_P001"
    assert written_rows[0]["trial_order"] == "1"
    assert written_rows[0]["presentation_label"] == "A"
