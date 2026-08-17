import csv
import json
import sys
from types import SimpleNamespace
from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_SRC = REPO_ROOT / "statistical-baseline" / "src"
if str(BASELINE_SRC) not in sys.path:
    sys.path.insert(0, str(BASELINE_SRC))

from statistical_baseline.heldout import (  # noqa: E402
    CANDIDATE_PREDICTION_COLUMNS,
    FIT_DIAGNOSTIC_COLUMNS,
    PRIMARY_MODEL_IDS,
    TRIAL_SUMMARY_COLUMNS,
    build_fit_plan,
    build_target_candidate_manifest,
    build_training_data_for_target,
    build_trial_summary_from_candidate_predictions,
    completed_prediction_keys,
    credible_interval,
    derive_baseline_winner,
    deterministic_smoke_subset,
    diagnostic_status,
    extract_expected_rating_draws,
    inference_settings,
    load_csv,
    load_jsonl,
    load_model_config,
    make_fit_diagnostic,
    posterior_winning_probabilities,
    run_smoke_test,
    sampler_kwargs,
    run_dry_run,
    selected_models,
    summarize_expected_rating_draws,
    validate_alignment,
)


ANALYSIS_READY = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6b5" / "final_analysis_ready_long.csv"
PREDICTION_EXAMPLES = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6b5" / "final_prediction_examples.jsonl"
CONFIG = REPO_ROOT / "statistical-baseline" / "config" / "phase6c_baseline_models.json"


def analysis_rows():
    return load_csv(ANALYSIS_READY)


def prediction_examples():
    return load_jsonl(PREDICTION_EXAMPLES)


def test_one_phase6b_target_maps_to_exactly_five_candidate_rows():
    manifest = build_target_candidate_manifest(analysis_rows(), prediction_examples())
    first_id = prediction_examples()[0]["prediction_example_id"]
    first_rows = [row for row in manifest if row["prediction_example_id"] == first_id]
    assert len(first_rows) == 5
    assert [row["presentation_label"] for row in first_rows] == ["A", "B", "C", "D", "E"]


def test_target_trial_five_rating_rows_are_excluded_but_participant_history_remains():
    rows = analysis_rows()
    example = prediction_examples()[0]
    training, target_rows, diagnostics = build_training_data_for_target(rows, example)
    target_trial_id = example["input_data"]["target"]["trial_id"]
    participant_id = example["participant_id"]
    assert len(target_rows) == 5
    assert all(row["trial_id"] != target_trial_id for row in training)
    assert diagnostics["participant_other_trial_rows_retained"] == 25
    assert any(row["participant_id"] == participant_id for row in training)


def test_other_participants_same_stimulus_rows_may_remain_when_available():
    rows = analysis_rows()
    example = prediction_examples()[0]
    target_stimulus = example["input_data"]["target"]["candidates"][0]["stimulus_id"]
    duplicate = dict(rows[0])
    duplicate["participant_id"] = "SYNTHETIC_OTHER_PARTICIPANT"
    duplicate["trial_id"] = "SYNTHETIC_OTHER_PARTICIPANT__trial_99"
    duplicate["stimulus_id"] = target_stimulus
    rows.append(duplicate)
    _, _, diagnostics = build_training_data_for_target(rows, example)
    assert diagnostics["same_stimulus_other_participant_rows_retained"] == 1


def test_target_mapping_a_to_e_matches_phase6b_examples():
    rows = analysis_rows()
    examples = prediction_examples()
    manifest = build_target_candidate_manifest(rows, examples)
    report = validate_alignment(rows, examples, manifest)
    assert report["passed"] is True
    assert report["candidate_rows"] == len(examples) * 5


def test_target_ordering_and_training_slicing_are_deterministic():
    rows = analysis_rows()
    examples = prediction_examples()
    models = selected_models(load_model_config(CONFIG))
    first = build_fit_plan(rows, examples, models)
    second = build_fit_plan(rows, examples, models)
    assert first == second
    assert [row["prediction_example_id"] for row in first[::2]] == sorted({example["prediction_example_id"] for example in examples})


def test_model_formulas_match_frozen_phase3_specification():
    config = load_model_config(CONFIG)
    models = {model["model_id"]: model for model in config["models"]}
    assert models["categorical_design"]["formula"] == "rating ~ episode + group + (1 | participant_id) + (1 | stimulus_id)"
    assert models["primary_acoustic"]["formula"] == "rating ~ episode + group + z_RMS + z_CF + z_SW + (1 | participant_id) + (1 | stimulus_id)"
    assert models["si_sensitivity"]["formula"] == "rating ~ episode + group + z_RMS + z_CF + z_SW + z_SI + (1 | participant_id) + (1 | stimulus_id)"


def test_production_configuration_matches_frozen_phase3_settings():
    config = load_model_config(CONFIG)
    production = config["inference_modes"]["production"]
    assert production["draws"] == 1000
    assert production["tune"] == 1000
    assert production["chains"] == 4
    assert production["target_accept"] == 0.95
    assert production["inference_method"] == "nutpie"
    assert production["analytical"] is True
    models = {model["model_id"]: model for model in config["models"]}
    assert inference_settings(config, models["categorical_design"], "production")["random_seed"] == 42
    assert inference_settings(config, models["primary_acoustic"], "production")["random_seed"] == 44


def test_smoke_test_configuration_is_explicitly_non_analytical_and_distinct():
    config = load_model_config(CONFIG)
    smoke = config["inference_modes"]["smoke_test"]
    production = config["inference_modes"]["production"]
    assert smoke["analytical"] is False
    assert smoke["draws"] < production["draws"]
    assert smoke["tune"] < production["tune"]
    assert smoke["label"] == "smoke_test"
    assert inference_settings(config, config["models"][0], "smoke_test")["label"] == "smoke_test"


def test_primary_acoustic_and_sensitivity_predictors_are_distinct():
    models = {model["model_id"]: model for model in load_model_config(CONFIG)["models"]}
    assert {"z_RMS", "z_CF", "z_SW"} <= set(models["primary_acoustic"]["required_predictors"])
    assert "z_SI" not in models["primary_acoustic"]["required_predictors"]
    assert "z_SI" in models["si_sensitivity"]["required_predictors"]


def test_no_target_observed_ratings_enter_target_candidate_manifest():
    manifest = build_target_candidate_manifest(analysis_rows(), prediction_examples())
    assert "rating" not in manifest[0]
    assert "human_rating" not in manifest[0]


def test_baseline_trial_summary_derivation_is_deterministic_and_tie_safe():
    rows = [
        base_prediction_row("A", 70),
        base_prediction_row("B", 72),
        base_prediction_row("C", 72),
        base_prediction_row("D", 60),
        base_prediction_row("E", 55),
    ]
    summary = build_trial_summary_from_candidate_predictions(rows)
    assert summary["predicted_preferred_mix"] == ""
    assert summary["is_predicted_tie"] is True
    assert summary["predicted_tied_labels"] == '["B","C"]'
    assert summary == build_trial_summary_from_candidate_predictions(rows)


def test_posterior_winning_probability_splits_draw_level_ties():
    probabilities = posterior_winning_probabilities(
        {
            "A": [1, 5, 3],
            "B": [2, 5, 1],
            "C": [3, 2, 3],
            "D": [0, 1, 3],
            "E": [1, 0, 2],
        }
    )
    rounded = {label: round(value, 10) for label, value in probabilities.items()}
    assert rounded == {
        "A": round(5 / 18, 10),
        "B": round(1 / 6, 10),
        "C": round(4 / 9, 10),
        "D": round(1 / 9, 10),
        "E": 0.0,
    }


def test_posterior_expected_rating_summaries_and_95_ci_are_correct():
    draws = {
        "A": [1, 2, 3, 4, 5],
        "B": [2, 3, 4, 5, 6],
        "C": [3, 4, 5, 6, 7],
        "D": [4, 5, 6, 7, 8],
        "E": [5, 6, 7, 8, 9],
    }
    summaries = summarize_expected_rating_draws(draws, interval_level=0.95)
    first = summaries[0]
    assert first["presentation_label"] == "A"
    assert first["predicted_mean_rating"] == 3
    assert round(first["posterior_predictive_sd"], 6) == round(1.5811388300841898, 6)
    assert credible_interval([1, 2, 3, 4, 5], 0.95) == (1.1, 4.9)
    assert round(sum(row["posterior_winning_probability"] for row in summaries), 10) == 1.0


def test_expected_rating_draw_extraction_uses_available_terms_and_zero_for_reference_or_unseen_levels():
    posterior = FakePosterior(
        {
            "Intercept": FakeArray([[10, 20]]),
            "episode": FakeArray([[[1], [2]]], dim_name="episode_dim"),
            "group": FakeArray([[[7], [8]]], dim_name="group_dim"),
            "z_RMS": FakeArray([[0.5, 1.0]]),
            "1|participant_id": FakeArray([[[3], [4]]], dim_name="participant_id__factor_dim"),
            "1|stimulus_id": FakeArray([[[5], [6]]], dim_name="stimulus_id__factor_dim"),
        },
        {
            "episode_dim": ["EDR-2"],
            "group_dim": ["group_02"],
            "participant_id__factor_dim": ["participant_1"],
            "stimulus_id__factor_dim": ["stimulus_1"],
        },
    )
    idata = SimpleNamespace(posterior=posterior)
    rows = [
        target_row("A", "EDR-1", "group_01", "participant_1", "stimulus_1", z_rms=2),
        target_row("B", "EDR-2", "group_02", "participant_2", "stimulus_2", z_rms=1),
        target_row("C", "EDR-1", "group_01", "participant_2", "stimulus_2", z_rms=0),
        target_row("D", "EDR-1", "group_01", "participant_2", "stimulus_2", z_rms=0),
        target_row("E", "EDR-1", "group_01", "participant_2", "stimulus_2", z_rms=0),
    ]

    draws = extract_expected_rating_draws(None, idata, rows)

    assert draws["A"] == [19.0, 32.0]
    assert draws["B"] == [18.5, 31.0]
    assert draws["C"] == [10.0, 20.0]


def test_exact_mean_ties_do_not_use_ground_truth_access():
    winner = derive_baseline_winner({"A": 10, "B": 10, "C": 9, "D": 8, "E": 7})
    assert winner["predicted_preferred_mix"] == ""
    assert winner["is_predicted_tie"] is True
    assert winner["predicted_tied_labels"] == '["A","B"]'


def test_resume_detects_completed_fits_and_prevents_duplicate_planning(tmp_path):
    output = tmp_path / "candidate_predictions.csv"
    first_id = prediction_examples()[0]["prediction_example_id"]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANDIDATE_PREDICTION_COLUMNS)
        writer.writeheader()
        for label in ["A", "B", "C", "D", "E"]:
            row = {field: "" for field in CANDIDATE_PREDICTION_COLUMNS}
            row.update(
                {
                    "prediction_example_id": first_id,
                    "baseline_model": "categorical_design",
                    "presentation_label": label,
                    "fit_status": "fit_ok",
                }
            )
            writer.writerow(row)
    assert completed_prediction_keys(output) == {(first_id, "categorical_design")}
    plan = build_fit_plan(analysis_rows(), prediction_examples()[:1], selected_models(load_model_config(CONFIG), ["categorical_design"]), completed_prediction_keys(output))
    assert plan[0]["fit_status"] == "already_complete"


def test_fit_diagnostic_schema_retains_failed_and_warning_statuses():
    failed = make_fit_diagnostic("example_1", "primary_acoustic", "fit_failed", message="synthetic failure")
    warning = make_fit_diagnostic("example_1", "primary_acoustic", "convergence_warning", divergences=1)
    assert set(failed) == set(FIT_DIAGNOSTIC_COLUMNS)
    assert failed["fit_status"] == "fit_failed"
    assert warning["fit_status"] == "convergence_warning"
    assert failed["protocol_version"] == "phase6c_baseline_prediction_v1"


def test_diagnostic_status_uses_phase3_thresholds():
    thresholds = load_model_config(CONFIG)["convergence_thresholds"]
    assert diagnostic_status(0, 1.0, 200, 200, thresholds) == "fit_ok"
    assert diagnostic_status(1, 1.0, 200, 200, thresholds) == "convergence_warning"
    assert diagnostic_status(0, None, 200, 200, thresholds) == "convergence_warning"


def test_dry_run_produces_expected_fit_count_and_schema_templates(tmp_path):
    summary = run_dry_run(ANALYSIS_READY, PREDICTION_EXAMPLES, tmp_path, config_path=CONFIG)
    assert summary["dry_run_passed"] is True
    assert summary["selected_models"] == PRIMARY_MODEL_IDS
    assert summary["prediction_example_count"] == 11
    assert summary["target_candidate_row_count"] == 55
    assert summary["expected_fit_count"] == 22
    assert (tmp_path / "fit_plan.csv").exists()
    assert (tmp_path / "alignment_report.json").exists()
    assert csv_header(tmp_path / "candidate_predictions_schema_template.csv") == CANDIDATE_PREDICTION_COLUMNS
    assert csv_header(tmp_path / "trial_prediction_summary_schema_template.csv") == TRIAL_SUMMARY_COLUMNS
    assert csv_header(tmp_path / "fit_diagnostics_schema_template.csv") == FIT_DIAGNOSTIC_COLUMNS


def test_sampler_kwargs_maps_nutpie_only_for_production_mode():
    config = load_model_config(CONFIG)
    model = config["models"][0]
    production_kwargs = sampler_kwargs(inference_settings(config, model, "production"))
    smoke_kwargs = sampler_kwargs(inference_settings(config, model, "smoke_test"))
    assert production_kwargs["nuts_sampler"] == "nutpie"
    assert "nuts_sampler" not in smoke_kwargs


def test_smoke_subset_is_deterministic():
    examples = prediction_examples()
    first = deterministic_smoke_subset(examples, n_targets=2)
    second = deterministic_smoke_subset(list(reversed(examples)), n_targets=2)
    assert [item["prediction_example_id"] for item in first] == [item["prediction_example_id"] for item in second]


def test_smoke_test_dependency_gate_records_failed_fits_without_outputs_when_bambi_missing(tmp_path):
    import importlib.util

    if importlib.util.find_spec("bambi") is not None:
        return
    summary = run_smoke_test(ANALYSIS_READY, PREDICTION_EXAMPLES, tmp_path, config_path=CONFIG, n_targets=1)
    assert summary["expected_fit_count"] == 2
    assert summary["completed_fit_count"] == 0
    assert summary["failed_fit_count"] == 2
    diagnostics = load_csv(tmp_path / "fit_diagnostics.csv")
    assert {row["fit_status"] for row in diagnostics} == {"fit_failed"}
    assert all("Bambi" in row["message"] for row in diagnostics)


def test_include_sensitivity_adds_sensitivity_model_without_changing_primary_default(tmp_path):
    summary = run_dry_run(ANALYSIS_READY, PREDICTION_EXAMPLES, tmp_path, config_path=CONFIG, include_sensitivity=True)
    assert summary["selected_models"] == ["categorical_design", "primary_acoustic", "si_sensitivity"]
    assert summary["expected_fit_count"] == 33


def base_prediction_row(label, predicted):
    return {
        "prediction_example_id": "example_1",
        "participant_id": "participant_1",
        "trial_id": "trial_1",
        "baseline_model": "categorical_design",
        "presentation_label": label,
        "fit_status": "fit_ok",
        "predicted_mean_rating": predicted,
        "posterior_winning_probability": "",
    }


def target_row(label, episode, group, participant_id, stimulus_id, z_rms=0):
    return {
        "presentation_label": label,
        "episode": episode,
        "group": group,
        "participant_id": participant_id,
        "stimulus_id": stimulus_id,
        "z_RMS": z_rms,
    }


class FakePosterior(dict):
    def __init__(self, variables, coords):
        super().__init__(variables)
        self.coords = {key: SimpleNamespace(values=np.array(value)) for key, value in coords.items()}


class FakeArray:
    def __init__(self, values, dim_name=None):
        self.values = np.array(values)
        self.dim_name = dim_name

    def isel(self, selectors):
        if self.dim_name is None:
            return self
        index = selectors[self.dim_name]
        return FakeArray(self.values[:, :, index])


def csv_header(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return next(csv.reader(handle))
