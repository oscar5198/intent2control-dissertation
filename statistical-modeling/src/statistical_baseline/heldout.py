"""Phase 6C held-out mixed-effects baseline preparation utilities.

Phase 6C.1 validates data slicing and output contracts without fitting final
real-data Bayesian models. Bambi/PyMC imports are intentionally lazy so dry-run
validation remains lightweight.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


EXPECTED_LABELS = ["A", "B", "C", "D", "E"]
PRIMARY_MODEL_IDS = ["categorical_design", "primary_acoustic"]
DEFAULT_CONFIG = Path("statistical-modeling/config/phase6c_baseline_models.json")
BASELINE_PROTOCOL_VERSION = "phase6c_baseline_prediction_v1"
DEFAULT_INTERVAL_LEVEL = 0.95

CANDIDATE_PREDICTION_COLUMNS = [
    "prediction_example_id",
    "participant_id",
    "trial_id",
    "presentation_label",
    "stimulus_id",
    "baseline_model",
    "fit_status",
    "predicted_mean_rating",
    "posterior_predictive_mean",
    "posterior_predictive_sd",
    "posterior_expected_ci_lower",
    "posterior_expected_ci_upper",
    "posterior_winning_probability",
]

TRIAL_SUMMARY_COLUMNS = [
    "prediction_example_id",
    "participant_id",
    "trial_id",
    "baseline_model",
    "fit_status",
    "predicted_rating_A",
    "predicted_rating_B",
    "predicted_rating_C",
    "predicted_rating_D",
    "predicted_rating_E",
    "predicted_preferred_mix",
    "is_predicted_tie",
    "predicted_tied_labels",
    "posterior_win_probability_A",
    "posterior_win_probability_B",
    "posterior_win_probability_C",
    "posterior_win_probability_D",
    "posterior_win_probability_E",
]

FIT_DIAGNOSTIC_COLUMNS = [
    "prediction_example_id",
    "baseline_model",
    "fit_status",
    "protocol_version",
    "inference_mode",
    "seed",
    "chains",
    "draws",
    "tune",
    "target_accept",
    "sampling_backend",
    "runtime_seconds",
    "target_exclusion_validated",
    "training_row_count",
    "divergences",
    "max_rhat",
    "min_bulk_ess",
    "min_tail_ess",
    "message",
]

FIT_PLAN_COLUMNS = [
    "prediction_example_id",
    "participant_id",
    "trial_id",
    "baseline_model",
    "role",
    "formula",
    "protocol_version",
    "inference_mode",
    "training_row_count",
    "target_candidate_count",
    "target_rows_excluded",
    "participant_other_trial_rows_retained",
    "same_stimulus_other_participant_rows_retained",
    "fit_status",
    "candidate_output_exists",
    "diagnostic_output_exists",
]

TARGET_CANDIDATE_COLUMNS = [
    "prediction_example_id",
    "participant_id",
    "trial_id",
    "presentation_label",
    "stimulus_id",
    "group",
    "episode",
    "z_RMS",
    "z_CF",
    "z_SW",
    "z_SI",
]


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_model_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def inference_settings(config: dict[str, Any], model: dict[str, Any], mode: str) -> dict[str, Any]:
    modes = config.get("inference_modes", {})
    if mode not in modes:
        raise ValueError(f"Unknown inference mode: {mode}")
    settings = dict(modes[mode])
    settings["random_seed"] = model["random_seed"]
    return settings


def assert_production_settings(config: dict[str, Any]) -> None:
    production = config["inference_modes"]["production"]
    expected = {
        "draws": 1000,
        "tune": 1000,
        "chains": 4,
        "cores": 1,
        "target_accept": 0.95,
        "inference_method": "nutpie",
        "analytical": True,
    }
    for key, expected_value in expected.items():
        if production.get(key) != expected_value:
            raise ValueError(f"Production inference setting {key}={production.get(key)!r}, expected {expected_value!r}.")


def assert_smoke_test_non_analytical(config: dict[str, Any]) -> None:
    smoke = config["inference_modes"]["smoke_test"]
    if smoke.get("analytical") is not False:
        raise ValueError("smoke_test mode must be explicitly marked non-analytical.")
    if smoke.get("draws", 0) >= config["inference_modes"]["production"].get("draws", 0):
        raise ValueError("smoke_test draws must remain clearly separate from production settings.")


def selected_models(config: dict[str, Any], model_ids: list[str] | None = None, include_sensitivity: bool = False) -> list[dict[str, Any]]:
    requested = set(model_ids or PRIMARY_MODEL_IDS)
    models = []
    for model in config["models"]:
        if model["model_id"] in requested or (include_sensitivity and model["role"] == "sensitivity"):
            models.append(model)
    missing = requested - {model["model_id"] for model in models}
    if missing:
        raise ValueError(f"Unknown baseline model IDs: {sorted(missing)}")
    return models


def normalise_analysis_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalised: list[dict[str, Any]] = []
    for row in rows:
        normalised.append(
            {
                **row,
                "rating": parse_number(row.get("human_rating", "")),
                "episode": row.get("episode_id", ""),
                "group": row.get("group_id", row.get("study_group", "")),
                "trial_order": parse_number(row.get("trial_order", "")),
                "z_RMS": parse_number(row.get("z_RMS", "")),
                "z_CF": parse_number(row.get("z_CF", "")),
                "z_SW": parse_number(row.get("z_SW", "")),
                "z_SI": parse_number(row.get("z_SI", "")),
            }
        )
    return normalised


def build_target_candidate_manifest(
    analysis_rows: list[dict[str, Any]],
    prediction_examples: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows_by_trial_label = {
        (str(row["trial_id"]), str(row["presentation_label"])): row
        for row in normalise_analysis_rows(analysis_rows)
    }
    manifest: list[dict[str, Any]] = []
    for example in sorted(prediction_examples, key=lambda item: item["prediction_example_id"]):
        target = example["input_data"]["target"]
        trial_id = str(target["trial_id"])
        for candidate in target["candidates"]:
            label = str(candidate["presentation_label"])
            source = rows_by_trial_label[(trial_id, label)]
            manifest.append(
                {
                    "prediction_example_id": example["prediction_example_id"],
                    "participant_id": example["participant_id"],
                    "trial_id": trial_id,
                    "presentation_label": label,
                    "stimulus_id": source["stimulus_id"],
                    "group": source["group"],
                    "episode": source["episode"],
                    "z_RMS": source["z_RMS"],
                    "z_CF": source["z_CF"],
                    "z_SW": source["z_SW"],
                    "z_SI": source["z_SI"],
                }
            )
    return manifest


def build_training_data_for_target(
    analysis_rows: list[dict[str, Any]],
    prediction_example: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rows = normalise_analysis_rows(analysis_rows)
    target_trial_id = str(prediction_example["input_data"]["target"]["trial_id"])
    participant_id = str(prediction_example["participant_id"])
    target_rows = [row for row in rows if str(row["trial_id"]) == target_trial_id]
    training_rows = [row for row in rows if str(row["trial_id"]) != target_trial_id]
    target_stimuli = {str(row["stimulus_id"]) for row in target_rows}
    diagnostics = {
        "target_rows_excluded": len(target_rows),
        "participant_other_trial_rows_retained": sum(
            1 for row in training_rows if str(row["participant_id"]) == participant_id
        ),
        "same_stimulus_other_participant_rows_retained": sum(
            1
            for row in training_rows
            if str(row["stimulus_id"]) in target_stimuli and str(row["participant_id"]) != participant_id
        ),
        "target_trial_in_training": any(str(row["trial_id"]) == target_trial_id for row in training_rows),
    }
    if diagnostics["target_rows_excluded"] != 5:
        raise ValueError(f"Target {target_trial_id} should exclude exactly five candidate rows.")
    if diagnostics["target_trial_in_training"]:
        raise ValueError(f"Target {target_trial_id} leaked into training rows.")
    return training_rows, target_rows, diagnostics


def build_fit_plan(
    analysis_rows: list[dict[str, Any]],
    prediction_examples: list[dict[str, Any]],
    models: list[dict[str, Any]],
    completed: set[tuple[str, str]] | None = None,
    inference_mode: str = "dry_run",
    output_dir: Path | None = None,
) -> list[dict[str, Any]]:
    completed = completed or set()
    fit_plan: list[dict[str, Any]] = []
    for example in sorted(prediction_examples, key=lambda item: item["prediction_example_id"]):
        training_rows, target_rows, diagnostics = build_training_data_for_target(analysis_rows, example)
        for model in models:
            key = (example["prediction_example_id"], model["model_id"])
            status = "already_complete" if key in completed else "pending"
            candidate_exists = bool(output_dir and (output_dir / "candidate_predictions.csv").exists())
            diagnostic_exists = bool(output_dir and (output_dir / "fit_diagnostics.csv").exists())
            fit_plan.append(
                {
                    "prediction_example_id": example["prediction_example_id"],
                    "participant_id": example["participant_id"],
                    "trial_id": example["input_data"]["target"]["trial_id"],
                    "baseline_model": model["model_id"],
                    "role": model["role"],
                    "formula": model["formula"],
                    "protocol_version": BASELINE_PROTOCOL_VERSION,
                    "inference_mode": inference_mode,
                    "training_row_count": len(training_rows),
                    "target_candidate_count": len(target_rows),
                    "target_rows_excluded": diagnostics["target_rows_excluded"],
                    "participant_other_trial_rows_retained": diagnostics["participant_other_trial_rows_retained"],
                    "same_stimulus_other_participant_rows_retained": diagnostics["same_stimulus_other_participant_rows_retained"],
                    "fit_status": status,
                    "candidate_output_exists": candidate_exists,
                    "diagnostic_output_exists": diagnostic_exists,
                }
            )
    return fit_plan


def validate_alignment(
    analysis_rows: list[dict[str, Any]],
    prediction_examples: list[dict[str, Any]],
    manifest: list[dict[str, Any]],
) -> dict[str, Any]:
    rows_by_trial_label = {
        (str(row["trial_id"]), str(row["presentation_label"])): str(row["stimulus_id"])
        for row in analysis_rows
    }
    failures: list[str] = []
    by_example = group_by(manifest, "prediction_example_id")
    for example in prediction_examples:
        example_id = example["prediction_example_id"]
        target = example["input_data"]["target"]
        manifest_rows = sorted(by_example.get(example_id, []), key=lambda row: EXPECTED_LABELS.index(row["presentation_label"]))
        if len(manifest_rows) != 5:
            failures.append(f"{example_id}: expected five candidate rows")
            continue
        if [row["presentation_label"] for row in manifest_rows] != EXPECTED_LABELS:
            failures.append(f"{example_id}: labels not A-E")
        expected_by_label = {
            candidate["presentation_label"]: candidate["stimulus_id"]
            for candidate in target["candidates"]
        }
        for row in manifest_rows:
            label = row["presentation_label"]
            if row["stimulus_id"] != expected_by_label[label]:
                failures.append(f"{example_id}: Phase 6B target mismatch for {label}")
            if row["stimulus_id"] != rows_by_trial_label[(row["trial_id"], label)]:
                failures.append(f"{example_id}: analysis row mismatch for {label}")
    return {
        "passed": not failures,
        "prediction_examples": len(prediction_examples),
        "candidate_rows": len(manifest),
        "failures": failures,
    }


def validate_fit_plan(fit_plan: list[dict[str, Any]]) -> dict[str, Any]:
    failures = []
    for row in fit_plan:
        if int(row["target_rows_excluded"]) != 5:
            failures.append(f"{row['prediction_example_id']} {row['baseline_model']}: target rows excluded != 5")
        if int(row["target_candidate_count"]) != 5:
            failures.append(f"{row['prediction_example_id']} {row['baseline_model']}: target candidates != 5")
        if int(row["participant_other_trial_rows_retained"]) <= 0:
            failures.append(f"{row['prediction_example_id']} {row['baseline_model']}: participant history not retained")
    return {"passed": not failures, "failures": failures}


def derive_baseline_winner(predicted_ratings_by_label: dict[str, float]) -> dict[str, Any]:
    max_rating = max(predicted_ratings_by_label.values())
    tied = [label for label in EXPECTED_LABELS if predicted_ratings_by_label[label] == max_rating]
    return {
        "predicted_preferred_mix": tied[0] if len(tied) == 1 else "",
        "is_predicted_tie": len(tied) > 1,
        "predicted_tied_labels": json.dumps(tied, separators=(",", ":")),
        "max_predicted_rating": max_rating,
    }


def posterior_winning_probabilities(draws_by_label: dict[str, list[float]]) -> dict[str, float]:
    lengths = {len(values) for values in draws_by_label.values()}
    if len(lengths) != 1:
        raise ValueError("All labels must have the same number of posterior draws.")
    n_draws = lengths.pop()
    wins = {label: 0.0 for label in EXPECTED_LABELS}
    for index in range(n_draws):
        draw_values = {label: draws_by_label[label][index] for label in EXPECTED_LABELS}
        max_value = max(draw_values.values())
        tied = [label for label in EXPECTED_LABELS if draw_values[label] == max_value]
        share = 1.0 / len(tied)
        for label in tied:
            wins[label] += share
    return {label: wins[label] / n_draws for label in EXPECTED_LABELS}


def credible_interval(values: list[float], interval_level: float = DEFAULT_INTERVAL_LEVEL) -> tuple[float, float]:
    if not values:
        raise ValueError("Cannot calculate credible interval for empty draws.")
    lower_q = (1 - interval_level) / 2
    upper_q = 1 - lower_q
    sorted_values = sorted(float(value) for value in values)
    return quantile(sorted_values, lower_q), quantile(sorted_values, upper_q)


def quantile(sorted_values: list[float], q: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = q * (len(sorted_values) - 1)
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return sorted_values[lower_index]
    lower = sorted_values[lower_index]
    upper = sorted_values[upper_index]
    return lower + (upper - lower) * (position - lower_index)


def summarize_expected_rating_draws(
    draws_by_label: dict[str, list[float]],
    interval_level: float = DEFAULT_INTERVAL_LEVEL,
) -> list[dict[str, Any]]:
    probabilities = posterior_winning_probabilities(draws_by_label)
    summaries: list[dict[str, Any]] = []
    for label in EXPECTED_LABELS:
        draws = [float(value) for value in draws_by_label[label]]
        lower, upper = credible_interval(draws, interval_level=interval_level)
        mean = sum(draws) / len(draws)
        variance = sum((value - mean) ** 2 for value in draws) / (len(draws) - 1) if len(draws) > 1 else 0.0
        summaries.append(
            {
                "presentation_label": label,
                "predicted_mean_rating": mean,
                "posterior_predictive_mean": mean,
                "posterior_predictive_sd": math.sqrt(variance),
                "posterior_expected_ci_lower": lower,
                "posterior_expected_ci_upper": upper,
                "posterior_winning_probability": probabilities[label],
            }
        )
    return summaries


def build_trial_summary_from_candidate_predictions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 5:
        raise ValueError("A trial summary requires exactly five candidate predictions.")
    first = rows[0]
    predicted = {row["presentation_label"]: float(row["predicted_mean_rating"]) for row in rows}
    winner = derive_baseline_winner(predicted)
    summary = {
        "prediction_example_id": first["prediction_example_id"],
        "participant_id": first["participant_id"],
        "trial_id": first["trial_id"],
        "baseline_model": first["baseline_model"],
        "fit_status": first.get("fit_status", "fit_ok"),
        "predicted_preferred_mix": winner["predicted_preferred_mix"],
        "is_predicted_tie": winner["is_predicted_tie"],
        "predicted_tied_labels": winner["predicted_tied_labels"],
    }
    for label in EXPECTED_LABELS:
        summary[f"predicted_rating_{label}"] = predicted[label]
        summary[f"posterior_win_probability_{label}"] = next(
            (row.get("posterior_winning_probability", "") for row in rows if row["presentation_label"] == label),
            "",
        )
    return summary


def make_fit_diagnostic(
    prediction_example_id: str,
    baseline_model: str,
    fit_status: str,
    message: str = "",
    protocol_version: str = BASELINE_PROTOCOL_VERSION,
    inference_mode: str = "",
    seed: int | str = "",
    chains: int | str = "",
    draws: int | str = "",
    tune: int | str = "",
    target_accept: float | str = "",
    sampling_backend: str = "",
    runtime_seconds: float | str = "",
    target_exclusion_validated: bool | str = "",
    training_row_count: int | str = "",
    divergences: int | str = "",
    max_rhat: float | str = "",
    min_bulk_ess: float | str = "",
    min_tail_ess: float | str = "",
) -> dict[str, Any]:
    return {
        "prediction_example_id": prediction_example_id,
        "baseline_model": baseline_model,
        "fit_status": fit_status,
        "protocol_version": protocol_version,
        "inference_mode": inference_mode,
        "seed": seed,
        "chains": chains,
        "draws": draws,
        "tune": tune,
        "target_accept": target_accept,
        "sampling_backend": sampling_backend,
        "runtime_seconds": runtime_seconds,
        "target_exclusion_validated": target_exclusion_validated,
        "training_row_count": training_row_count,
        "divergences": divergences,
        "max_rhat": max_rhat,
        "min_bulk_ess": min_bulk_ess,
        "min_tail_ess": min_tail_ess,
        "message": message,
    }


def completed_prediction_keys(candidate_prediction_csv: Path) -> set[tuple[str, str]]:
    if not candidate_prediction_csv.exists():
        return set()
    rows = load_csv(candidate_prediction_csv)
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        if row.get("fit_status") == "fit_ok":
            counts[(row["prediction_example_id"], row["baseline_model"])] += 1
    return {key for key, count in counts.items() if count == 5}


def fit_baseline_model(
    training_rows: list[dict[str, Any]],
    model_definition: dict[str, Any],
    settings: dict[str, Any],
    **overrides: Any,
) -> tuple[Any, Any]:
    """Construct and fit the frozen Bambi model.

    This is not invoked by Phase 6C.1 dry-run tests. It exists so Phase 6C.2 can
    use the same slicing/configuration path for final real-data fitting.
    """

    try:
        import bambi as bmb  # type: ignore
        import pandas as pd  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Bambi/Pandas are required for real baseline fitting, but dry-run mode does not need them.") from exc
    sampling = sampler_kwargs({**settings, **overrides})
    data = pd.DataFrame(training_rows)
    model = bmb.Model(model_definition["formula"], data)
    idata = model.fit(**sampling)
    return model, idata


def sampler_kwargs(settings: dict[str, Any]) -> dict[str, Any]:
    kwargs = {
        "draws": settings["draws"],
        "tune": settings["tune"],
        "chains": settings["chains"],
        "cores": settings["cores"],
        "target_accept": settings["target_accept"],
        "random_seed": settings["random_seed"],
    }
    method = settings.get("inference_method")
    if method == "nutpie":
        kwargs["nuts_sampler"] = "nutpie"
    return kwargs


def assert_fit_time_exclusion(training_rows: list[dict[str, Any]], target_rows: list[dict[str, Any]], prediction_example: dict[str, Any]) -> dict[str, Any]:
    target_trial_id = prediction_example["input_data"]["target"]["trial_id"]
    participant_id = prediction_example["participant_id"]
    leaked_rows = [row for row in training_rows if str(row["trial_id"]) == str(target_trial_id)]
    participant_rows = [row for row in training_rows if str(row["participant_id"]) == str(participant_id)]
    target_ratings = {(row["presentation_label"], row["rating"]) for row in target_rows}
    duplicate_target_rows = [
        row
        for row in training_rows
        if str(row["participant_id"]) == str(participant_id)
        and (row.get("presentation_label"), row.get("rating")) in target_ratings
        and str(row["trial_id"]) == str(target_trial_id)
    ]
    result = {
        "target_exclusion_validated": not leaked_rows and not duplicate_target_rows,
        "target_trial_training_rows": len(leaked_rows),
        "duplicate_target_outcome_rows": len(duplicate_target_rows),
        "participant_other_trial_rows_retained": len(participant_rows),
        "training_row_count": len(training_rows),
    }
    if not result["target_exclusion_validated"]:
        raise ValueError(f"Target trial {target_trial_id} leaked into fit-time training data.")
    if result["participant_other_trial_rows_retained"] <= 0:
        raise ValueError(f"Participant {participant_id} has no retained non-target rows for random-effect estimation.")
    return result


def extract_expected_rating_draws(model: Any, idata: Any, target_rows: list[dict[str, Any]]) -> dict[str, list[float]]:
    """Return posterior expected mean draws for target rows in A-E order.

    Bambi's public prediction helper is version-sensitive for crossed
    group-specific terms on new data. The Phase 6C models all use a Gaussian
    identity-link mean, so the frozen expected-rating quantity is computed
    explicitly from the fitted posterior terms.
    """

    if not hasattr(idata, "posterior"):
        raise RuntimeError("Fitted inference data does not contain a posterior group.")
    posterior = idata.posterior
    if "Intercept" not in posterior:
        raise RuntimeError("Fitted posterior does not contain an Intercept term.")

    sorted_targets = sorted(target_rows, key=lambda row: EXPECTED_LABELS.index(str(row["presentation_label"])))
    base = posterior_draw_vector(posterior, "Intercept")
    draws_by_label: dict[str, list[float]] = {}
    for row in sorted_targets:
        draws = list(base)
        draws = add_draw_vectors(draws, categorical_draw_vector(posterior, "episode", row.get("episode")))
        draws = add_draw_vectors(draws, categorical_draw_vector(posterior, "group", row.get("group")))
        for predictor in ["z_RMS", "z_CF", "z_SW", "z_SI"]:
            if predictor in posterior:
                draws = add_scaled_draw_vector(draws, posterior_draw_vector(posterior, predictor), parse_number(row.get(predictor, 0)) or 0)
        draws = add_draw_vectors(
            draws,
            factor_draw_vector(posterior, "1|participant_id", "participant_id__factor_dim", row.get("participant_id")),
        )
        draws = add_draw_vectors(
            draws,
            factor_draw_vector(posterior, "1|stimulus_id", "stimulus_id__factor_dim", row.get("stimulus_id")),
        )
        draws_by_label[str(row["presentation_label"])] = draws
    return draws_by_label


def posterior_draw_vector(posterior: Any, variable: str) -> list[float]:
    return [float(value) for value in posterior[variable].values.ravel().tolist()]


def categorical_draw_vector(posterior: Any, variable: str, level: Any) -> list[float]:
    if variable not in posterior:
        return zero_draw_vector(posterior)
    coord_name = f"{variable}_dim"
    return factor_draw_vector(posterior, variable, coord_name, level)


def factor_draw_vector(posterior: Any, variable: str, coord_name: str, level: Any) -> list[float]:
    if variable not in posterior or coord_name not in posterior.coords:
        return zero_draw_vector(posterior)
    levels = [str(value) for value in posterior.coords[coord_name].values.tolist()]
    level_text = str(level)
    if level_text not in levels:
        return zero_draw_vector(posterior)
    array = posterior[variable].isel({coord_name: levels.index(level_text)})
    return [float(value) for value in array.values.ravel().tolist()]


def zero_draw_vector(posterior: Any) -> list[float]:
    return [0.0 for _ in posterior_draw_vector(posterior, "Intercept")]


def add_draw_vectors(left: list[float], right: list[float]) -> list[float]:
    if len(left) != len(right):
        raise ValueError("Posterior draw vectors must have equal lengths.")
    return [left_value + right_value for left_value, right_value in zip(left, right)]


def add_scaled_draw_vector(left: list[float], right: list[float], scale: int | float) -> list[float]:
    if len(left) != len(right):
        raise ValueError("Posterior draw vectors must have equal lengths.")
    return [left_value + (right_value * float(scale)) for left_value, right_value in zip(left, right)]


def diagnostic_status(
    divergences: int | None,
    max_rhat: float | None,
    min_bulk_ess: float | None,
    min_tail_ess: float | None,
    thresholds: dict[str, Any],
) -> str:
    if divergences is None or max_rhat is None or min_bulk_ess is None or min_tail_ess is None:
        return "convergence_warning"
    if (
        divergences <= thresholds["fit_ok_max_divergences"]
        and max_rhat <= thresholds["fit_ok_max_rhat"]
        and min_bulk_ess >= thresholds["fit_ok_min_bulk_ess"]
        and min_tail_ess >= thresholds["fit_ok_min_tail_ess"]
    ):
        return "fit_ok"
    return "convergence_warning"


def run_dry_run(
    analysis_ready_csv: Path,
    prediction_examples_jsonl: Path,
    output_dir: Path,
    config_path: Path = DEFAULT_CONFIG,
    model_ids: list[str] | None = None,
    include_sensitivity: bool = False,
    resume: bool = True,
) -> dict[str, Any]:
    analysis_rows = load_csv(analysis_ready_csv)
    prediction_examples = load_jsonl(prediction_examples_jsonl)
    config = load_model_config(config_path)
    assert_production_settings(config)
    assert_smoke_test_non_analytical(config)
    models = selected_models(config, model_ids=model_ids, include_sensitivity=include_sensitivity)
    completed = completed_prediction_keys(output_dir / "candidate_predictions.csv") if resume else set()
    manifest = build_target_candidate_manifest(analysis_rows, prediction_examples)
    fit_plan = build_fit_plan(analysis_rows, prediction_examples, models, completed=completed, inference_mode="dry_run", output_dir=output_dir)
    alignment = validate_alignment(analysis_rows, prediction_examples, manifest)
    fit_validation = validate_fit_plan(fit_plan)
    expected_fit_count = sum(1 for row in fit_plan if row["fit_status"] == "pending")
    summary = {
        "schema_version": "phase6c2_heldout_baseline_dry_run_v1",
        "protocol_version": BASELINE_PROTOCOL_VERSION,
        "analysis_ready_csv": str(analysis_ready_csv),
        "prediction_examples_jsonl": str(prediction_examples_jsonl),
        "config_path": str(config_path),
        "selected_models": [model["model_id"] for model in models],
        "prediction_example_count": len(prediction_examples),
        "target_candidate_row_count": len(manifest),
        "fit_plan_row_count": len(fit_plan),
        "expected_fit_count": expected_fit_count,
        "resume_completed_fit_count": len(completed),
        "alignment": alignment,
        "fit_plan_validation": fit_validation,
        "dry_run_passed": alignment["passed"] and fit_validation["passed"],
        "contains_real_model_fits": False,
        "contains_final_performance": False,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "target_candidate_manifest.csv", manifest, TARGET_CANDIDATE_COLUMNS)
    write_csv(output_dir / "fit_plan.csv", fit_plan, FIT_PLAN_COLUMNS)
    write_json(output_dir / "alignment_report.json", alignment)
    write_json(output_dir / "dry_run_summary.json", summary)
    write_empty_output_templates(output_dir)
    return summary


def deterministic_smoke_subset(prediction_examples: list[dict[str, Any]], n_targets: int = 1) -> list[dict[str, Any]]:
    return sorted(prediction_examples, key=lambda item: item["prediction_example_id"])[:n_targets]


def run_single_heldout_fit(
    analysis_rows: list[dict[str, Any]],
    prediction_example: dict[str, Any],
    model_definition: dict[str, Any],
    config: dict[str, Any],
    inference_mode: str,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    if inference_mode not in {"smoke_test", "production"}:
        raise ValueError("Actual fitting requires smoke_test or production inference mode.")
    settings = inference_settings(config, model_definition, inference_mode)
    training_rows, target_rows, exclusion = build_training_data_for_target(analysis_rows, prediction_example)
    fit_check = assert_fit_time_exclusion(training_rows, target_rows, prediction_example)
    start = time.perf_counter()
    try:
        model, idata = fit_baseline_model(training_rows, model_definition, settings)
        draws_by_label = extract_expected_rating_draws(model, idata, target_rows)
        runtime = time.perf_counter() - start
        candidate_summaries = summarize_expected_rating_draws(
            draws_by_label,
            interval_level=float(config.get("credible_interval_level", DEFAULT_INTERVAL_LEVEL)),
        )
        rows_by_label = {row["presentation_label"]: row for row in sorted(target_rows, key=lambda row: EXPECTED_LABELS.index(str(row["presentation_label"])))}
        candidate_rows: list[dict[str, Any]] = []
        for summary in candidate_summaries:
            label = summary["presentation_label"]
            source = rows_by_label[label]
            candidate_rows.append(
                {
                    "prediction_example_id": prediction_example["prediction_example_id"],
                    "participant_id": prediction_example["participant_id"],
                    "trial_id": prediction_example["input_data"]["target"]["trial_id"],
                    "presentation_label": label,
                    "stimulus_id": source["stimulus_id"],
                    "baseline_model": model_definition["model_id"],
                    "fit_status": "fit_ok",
                    **{key: summary[key] for key in summary if key != "presentation_label"},
                }
            )
        diagnostics_raw = extract_arviz_diagnostics(idata)
        status = diagnostic_status(
            diagnostics_raw.get("divergences"),
            diagnostics_raw.get("max_rhat"),
            diagnostics_raw.get("min_bulk_ess"),
            diagnostics_raw.get("min_tail_ess"),
            config.get("convergence_thresholds", {}),
        )
        for row in candidate_rows:
            row["fit_status"] = status
        trial_summary = build_trial_summary_from_candidate_predictions(candidate_rows)
        diagnostic = make_fit_diagnostic(
            prediction_example_id=prediction_example["prediction_example_id"],
            baseline_model=model_definition["model_id"],
            fit_status=status,
            inference_mode=inference_mode,
            seed=settings["random_seed"],
            chains=settings["chains"],
            draws=settings["draws"],
            tune=settings["tune"],
            target_accept=settings["target_accept"],
            sampling_backend=settings["inference_method"],
            runtime_seconds=runtime,
            target_exclusion_validated=fit_check["target_exclusion_validated"],
            training_row_count=fit_check["training_row_count"],
            divergences=diagnostics_raw.get("divergences", ""),
            max_rhat=diagnostics_raw.get("max_rhat", ""),
            min_bulk_ess=diagnostics_raw.get("min_bulk_ess", ""),
            min_tail_ess=diagnostics_raw.get("min_tail_ess", ""),
        )
        return candidate_rows, trial_summary, diagnostic
    except Exception as exc:  # keep failed fit visible for resumable execution
        runtime = time.perf_counter() - start
        diagnostic = make_fit_diagnostic(
            prediction_example_id=prediction_example["prediction_example_id"],
            baseline_model=model_definition["model_id"],
            fit_status="fit_failed",
            message=str(exc),
            inference_mode=inference_mode,
            seed=settings["random_seed"],
            chains=settings["chains"],
            draws=settings["draws"],
            tune=settings["tune"],
            target_accept=settings["target_accept"],
            sampling_backend=settings["inference_method"],
            runtime_seconds=runtime,
            target_exclusion_validated=fit_check["target_exclusion_validated"],
            training_row_count=fit_check["training_row_count"],
        )
        return [], {}, diagnostic


def extract_arviz_diagnostics(idata: Any) -> dict[str, Any]:
    try:
        import arviz as az  # type: ignore
    except ImportError:
        return {"divergences": None, "max_rhat": None, "min_bulk_ess": None, "min_tail_ess": None}
    result: dict[str, Any] = {"divergences": 0, "max_rhat": None, "min_bulk_ess": None, "min_tail_ess": None}
    try:
        if hasattr(idata, "sample_stats") and "diverging" in idata.sample_stats:
            result["divergences"] = int(idata.sample_stats["diverging"].sum().values)
        rhat = az.rhat(idata)
        ess_bulk = az.ess(idata, method="bulk")
        ess_tail = az.ess(idata, method="tail")
        result["max_rhat"] = dataset_extreme(rhat, max)
        result["min_bulk_ess"] = dataset_extreme(ess_bulk, min)
        result["min_tail_ess"] = dataset_extreme(ess_tail, min)
    except Exception:
        pass
    return result


def dataset_extreme(dataset: Any, func: Any) -> float | None:
    values: list[float] = []
    for variable in dataset.data_vars:
        values.extend(float(value) for value in dataset[variable].values.ravel().tolist() if not math.isnan(float(value)))
    return func(values) if values else None


def run_smoke_test(
    analysis_ready_csv: Path,
    prediction_examples_jsonl: Path,
    output_dir: Path,
    config_path: Path = DEFAULT_CONFIG,
    model_ids: list[str] | None = None,
    n_targets: int = 1,
    resume: bool = True,
) -> dict[str, Any]:
    analysis_rows = load_csv(analysis_ready_csv)
    prediction_examples = deterministic_smoke_subset(load_jsonl(prediction_examples_jsonl), n_targets=n_targets)
    config = load_model_config(config_path)
    assert_production_settings(config)
    assert_smoke_test_non_analytical(config)
    models = selected_models(config, model_ids=model_ids or PRIMARY_MODEL_IDS)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "configuration_snapshot.json", config)
    completed = completed_prediction_keys(output_dir / "candidate_predictions.csv") if resume else set()
    fit_plan = build_fit_plan(analysis_rows, prediction_examples, models, completed=completed, inference_mode="smoke_test", output_dir=output_dir)
    candidate_rows: list[dict[str, Any]] = existing_rows(output_dir / "candidate_predictions.csv") if resume else []
    trial_rows: list[dict[str, Any]] = existing_rows(output_dir / "trial_prediction_summary.csv") if resume else []
    diagnostic_rows: list[dict[str, Any]] = existing_rows(output_dir / "fit_diagnostics.csv") if resume else []
    fitted: list[dict[str, str]] = []
    for plan_row in fit_plan:
        key = (plan_row["prediction_example_id"], plan_row["baseline_model"])
        if key in completed:
            continue
        example = next(item for item in prediction_examples if item["prediction_example_id"] == plan_row["prediction_example_id"])
        model_definition = next(item for item in models if item["model_id"] == plan_row["baseline_model"])
        candidates, trial_summary, diagnostic = run_single_heldout_fit(analysis_rows, example, model_definition, config, "smoke_test")
        diagnostic_rows.append(diagnostic)
        if candidates and trial_summary:
            candidate_rows.extend(candidates)
            trial_rows.append(trial_summary)
            fitted.append({"prediction_example_id": key[0], "baseline_model": key[1]})
        atomic_write_csv(output_dir / "candidate_predictions.csv", candidate_rows, CANDIDATE_PREDICTION_COLUMNS)
        atomic_write_csv(output_dir / "trial_prediction_summary.csv", trial_rows, TRIAL_SUMMARY_COLUMNS)
        atomic_write_csv(output_dir / "fit_diagnostics.csv", diagnostic_rows, FIT_DIAGNOSTIC_COLUMNS)
    manifest = build_execution_manifest(fit_plan, candidate_rows, diagnostic_rows)
    write_csv(output_dir / "fit_manifest.csv", manifest, FIT_PLAN_COLUMNS)
    summary = {
        "schema_version": "phase6c2_smoke_test_summary_v1",
        "protocol_version": BASELINE_PROTOCOL_VERSION,
        "inference_mode": "smoke_test",
        "analytical": False,
        "selected_prediction_examples": [item["prediction_example_id"] for item in prediction_examples],
        "selected_models": [model["model_id"] for model in models],
        "expected_fit_count": len(fit_plan),
        "completed_fit_count": len({(row["prediction_example_id"], row["baseline_model"]) for row in candidate_rows if row.get("fit_status") in {"fit_ok", "convergence_warning"}}),
        "failed_fit_count": sum(1 for row in diagnostic_rows if row.get("fit_status") == "fit_failed"),
        "candidate_prediction_row_count": len(candidate_rows),
        "trial_summary_row_count": len(trial_rows),
        "contains_final_performance": False,
    }
    write_json(output_dir / "execution_summary.json", summary)
    return summary


def build_execution_manifest(
    fit_plan: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    diagnostic_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    completed = {(row["prediction_example_id"], row["baseline_model"]) for row in candidate_rows if row.get("fit_status") in {"fit_ok", "convergence_warning"}}
    diagnostics = {(row["prediction_example_id"], row["baseline_model"]): row.get("fit_status", "") for row in diagnostic_rows}
    manifest = []
    for row in fit_plan:
        key = (row["prediction_example_id"], row["baseline_model"])
        manifest_row = dict(row)
        manifest_row["fit_status"] = "complete" if key in completed else diagnostics.get(key, row["fit_status"])
        manifest_row["candidate_output_exists"] = key in completed
        manifest_row["diagnostic_output_exists"] = key in diagnostics
        manifest.append(manifest_row)
    return manifest


def existing_rows(path: Path) -> list[dict[str, Any]]:
    return load_csv(path) if path.exists() else []


def atomic_write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    write_csv(tmp_path, rows, fieldnames)
    shutil.move(str(tmp_path), str(path))


def write_empty_output_templates(output_dir: Path) -> None:
    write_csv(output_dir / "candidate_predictions_schema_template.csv", [], CANDIDATE_PREDICTION_COLUMNS)
    write_csv(output_dir / "trial_prediction_summary_schema_template.csv", [], TRIAL_SUMMARY_COLUMNS)
    write_csv(output_dir / "fit_diagnostics_schema_template.csv", [], FIT_DIAGNOSTIC_COLUMNS)


def group_by(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[key])].append(row)
    return dict(grouped)


def parse_number(value: Any) -> int | float | None:
    if value in (None, ""):
        return None
    number = float(str(value))
    return int(number) if number.is_integer() else number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 6C held-out baseline dry-run, smoke-test, or explicit production mode.")
    parser.add_argument("--analysis-ready", required=True, type=Path, help="Phase 6B analysis_ready_long.csv.")
    parser.add_argument("--prediction-examples", required=True, type=Path, help="Phase 6B prediction_examples.jsonl.")
    parser.add_argument("--output-dir", required=True, type=Path, help="Output directory for plans/predictions/reports.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Phase 6C baseline model config.")
    parser.add_argument("--models", nargs="*", default=None, help="Baseline model IDs. Defaults to primary models.")
    parser.add_argument("--include-sensitivity", action="store_true", help="Also include sensitivity-only models.")
    parser.add_argument("--no-resume", action="store_true", help="Ignore existing candidate_predictions.csv when planning.")
    parser.add_argument("--dry-run", action="store_true", help="Validate slicing/mapping without sampling. This is the safe default.")
    parser.add_argument("--smoke-test", action="store_true", help="Run a small non-analytical synthetic Bayesian execution check.")
    parser.add_argument("--production", action="store_true", help="Explicitly request full production settings. Not implemented for unattended Phase 6C.2 use.")
    parser.add_argument("--smoke-targets", type=int, default=1, help="Number of deterministic synthetic targets for smoke-test mode.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    modes_requested = sum(bool(value) for value in [args.dry_run, args.smoke_test, args.production])
    if modes_requested > 1:
        raise SystemExit("Choose only one of --dry-run, --smoke-test, or --production.")
    if args.production:
        raise SystemExit("--production is intentionally explicit and reserved for final locked data; use --dry-run first and do not run it on partial data.")
    if args.smoke_test:
        summary = run_smoke_test(
            analysis_ready_csv=args.analysis_ready,
            prediction_examples_jsonl=args.prediction_examples,
            output_dir=args.output_dir,
            config_path=args.config,
            model_ids=args.models,
            n_targets=args.smoke_targets,
            resume=not args.no_resume,
        )
        print(f"Wrote Phase 6C.2 smoke-test outputs to {args.output_dir}")
        print(f"expected_fit_count={summary['expected_fit_count']}")
        print(f"completed_fit_count={summary['completed_fit_count']}")
        print(f"failed_fit_count={summary['failed_fit_count']}")
        return 0 if summary["failed_fit_count"] == 0 and summary["completed_fit_count"] == summary["expected_fit_count"] else 1
    summary = run_dry_run(
        analysis_ready_csv=args.analysis_ready,
        prediction_examples_jsonl=args.prediction_examples,
        output_dir=args.output_dir,
        config_path=args.config,
        model_ids=args.models,
        include_sensitivity=args.include_sensitivity,
        resume=not args.no_resume,
    )
    print(f"Wrote Phase 6C dry-run outputs to {args.output_dir}")
    print(f"expected_fit_count={summary['expected_fit_count']}")
    print(f"dry_run_passed={str(summary['dry_run_passed']).lower()}")
    return 0 if summary["dry_run_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
