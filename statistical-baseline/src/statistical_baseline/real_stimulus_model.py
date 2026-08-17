"""Final empirical stimulus-based Bayesian multilevel model.

This module fits the pre-specified real-data stimulus model and writes
dissertation-ready tables without modifying raw data or cleaning decisions.
"""

from __future__ import annotations

import itertools
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import arviz as az
import bambi as bmb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pymc as pm


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "statistical-baseline/data/real"
OUTPUT_DIR = PROJECT_ROOT / "statistical-baseline/outputs/real_stimulus_model"
FIGURE_DIR = OUTPUT_DIR / "figures"
RATINGS_PATH = DATA_DIR / "real_ratings_clean.csv"
PARTICIPANTS_PATH = DATA_DIR / "real_participants_clean.csv"
PREFERENCES_PATH = DATA_DIR / "real_trial_preferences.csv"
TIES_PATH = DATA_DIR / "real_trial_ties_long.csv"
VALIDATION_PATH = DATA_DIR / "real_data_validation.csv"
MANIFEST_PATH = DATA_DIR / "real_cleaning_manifest.json"

INTERCEPT_FORMULA = "rating ~ 1 + (1 | participant_id) + (1 | stimulus_id)"
FINAL_FORMULA = "rating ~ episode + group + (1 | participant_id) + (1 | stimulus_id)"
SEED = 20260817
SAMPLING = {"draws": 1000, "tune": 1000, "chains": 4, "target_accept": 0.95}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cleaned_dataset_metadata(summary: pd.DataFrame) -> dict[str, Any]:
    row = summary.iloc[0]
    participants = pd.read_csv(PARTICIPANTS_PATH)
    return {
        "cleaned_ratings_path": str(RATINGS_PATH.relative_to(PROJECT_ROOT)),
        "cleaned_ratings_sha256": file_sha256(RATINGS_PATH),
        "cleaning_manifest_path": str(MANIFEST_PATH.relative_to(PROJECT_ROOT)),
        "cleaning_manifest_sha256": file_sha256(MANIFEST_PATH),
        "raw_source_path": json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["raw_provenance"]["stored_path"],
        "raw_source_sha256": json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["raw_provenance"]["sha256"],
        "analysable_n": int(row["final_recommended_analysable_n"]),
        "group_split": participants["group"].value_counts().sort_index().to_dict(),
        "rating_count": int(row["final_analysable_rating_rows"]),
        "trial_count": int(row["participant_song_episode_trials"]),
    }


def load_inputs() -> dict[str, Any]:
    ratings = pd.read_csv(RATINGS_PATH)
    participants = pd.read_csv(PARTICIPANTS_PATH)
    preferences = pd.read_csv(PREFERENCES_PATH)
    ties = pd.read_csv(TIES_PATH)
    validation = pd.read_csv(VALIDATION_PATH)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {
        "ratings": ratings,
        "participants": participants,
        "preferences": preferences,
        "ties": ties,
        "validation": validation,
        "manifest": manifest,
    }


def prepare_model_data(ratings: pd.DataFrame) -> pd.DataFrame:
    columns = ["rating", "episode", "group", "participant_id", "stimulus_id", "song_id", "mix_id"]
    data = ratings[columns].copy()
    data["rating"] = pd.to_numeric(data["rating"], errors="coerce")
    for column in ["episode", "group", "participant_id", "stimulus_id", "song_id", "mix_id"]:
        data[column] = data[column].astype(str)
    data["episode"] = pd.Categorical(data["episode"], categories=["EDR-1", "EDR-2", "FM-1"], ordered=False)
    data["group"] = pd.Categorical(data["group"], categories=["group_01", "group_02"], ordered=False)
    data["participant_id"] = pd.Categorical(data["participant_id"], ordered=False)
    data["stimulus_id"] = pd.Categorical(data["stimulus_id"], ordered=False)
    return data


def validate_model_data(data: pd.DataFrame) -> pd.DataFrame:
    summary = pd.read_csv(DATA_DIR / "real_data_summary.csv").iloc[0]
    participants = pd.read_csv(PARTICIPANTS_PATH)
    expected_n = int(summary["final_recommended_analysable_n"])
    expected_group_counts = participants["group"].value_counts().sort_index().to_dict()
    expected_ratings = int(summary["final_analysable_rating_rows"])
    checks = {
        "final_analysable_n_matches_cleaning_summary": data["participant_id"].nunique() == expected_n,
        "group_01_n_matches_cleaning_summary": data.drop_duplicates("participant_id").query("group == 'group_01'").shape[0] == expected_group_counts.get("group_01", 0),
        "group_02_n_matches_cleaning_summary": data.drop_duplicates("participant_id").query("group == 'group_02'").shape[0] == expected_group_counts.get("group_02", 0),
        "rating_observations_match_cleaning_summary": len(data) == expected_ratings,
        "stimuli_20": data["stimulus_id"].nunique() == 20,
        "songs_4": data["song_id"].nunique() == 4,
        "episodes_3": data["episode"].nunique() == 3,
        "ratings_per_participant_30": data.groupby("participant_id", observed=True).size().eq(30).all(),
        "no_missing_outcome": data["rating"].notna().all(),
        "no_invalid_ratings": data["rating"].between(0, 100).all(),
        "no_missing_identifiers": data[["participant_id", "group", "stimulus_id"]].notna().all().all(),
    }
    rows = []
    for check, passed in checks.items():
        rows.append({"check": check, "passed": bool(passed), "actual_value": actual_value_for_check(check, data)})
    return pd.DataFrame(rows)


def actual_value_for_check(check: str, data: pd.DataFrame) -> Any:
    if check == "final_analysable_n_matches_cleaning_summary":
        return data["participant_id"].nunique()
    if check == "group_01_n_matches_cleaning_summary":
        return data.drop_duplicates("participant_id").query("group == 'group_01'").shape[0]
    if check == "group_02_n_matches_cleaning_summary":
        return data.drop_duplicates("participant_id").query("group == 'group_02'").shape[0]
    if check == "rating_observations_match_cleaning_summary":
        return len(data)
    if check == "stimuli_20":
        return data["stimulus_id"].nunique()
    if check == "songs_4":
        return data["song_id"].nunique()
    if check == "episodes_3":
        return data["episode"].nunique()
    if check == "ratings_per_participant_30":
        return json.dumps(data.groupby("participant_id", observed=True).size().describe().to_dict())
    if check == "no_missing_outcome":
        return int(data["rating"].isna().sum())
    if check == "no_invalid_ratings":
        return int((~data["rating"].between(0, 100)).sum())
    if check == "no_missing_identifiers":
        return int(data[["participant_id", "group", "stimulus_id"]].isna().sum().sum())
    return ""


def descriptive_summaries(data: pd.DataFrame, preferences: pd.DataFrame) -> pd.DataFrame:
    rows = []
    rating = data["rating"]
    rows.append(metric_row("overall", "all", rating))
    for episode, frame in data.groupby("episode", observed=True):
        rows.append(metric_row("episode", episode, frame["rating"]))
    for group, frame in data.groupby("group", observed=True):
        rows.append(metric_row("group", group, frame["rating"]))
    for stimulus, frame in data.groupby("stimulus_id", observed=True):
        rows.append(metric_row("stimulus", stimulus, frame["rating"]))
    participant_means = data.groupby("participant_id", observed=True)["rating"].mean()
    rows.append(metric_row("participant_mean_distribution", "participant_means", participant_means))
    bins = pd.cut(data["rating"], bins=[-0.001, 20, 40, 60, 80, 100], labels=["0-20", "21-40", "41-60", "61-80", "81-100"])
    for label, count in bins.value_counts(sort=False).items():
        rows.append(
            {
                "summary_type": "rating_distribution_bin",
                "level": str(label),
                "n": int(count),
                "mean": np.nan,
                "median": np.nan,
                "sd": np.nan,
                "min": np.nan,
                "max": np.nan,
            }
        )
    rows.append({"summary_type": "observed_preference_trials", "level": "all", "n": len(preferences), "mean": np.nan, "median": np.nan, "sd": np.nan, "min": np.nan, "max": np.nan})
    return pd.DataFrame(rows)


def metric_row(summary_type: str, level: str, values: pd.Series) -> dict[str, Any]:
    return {
        "summary_type": summary_type,
        "level": level,
        "n": int(values.count()),
        "mean": float(values.mean()),
        "median": float(values.median()),
        "sd": float(values.std(ddof=1)),
        "min": float(values.min()),
        "max": float(values.max()),
    }


def fit_model(formula: str, data: pd.DataFrame, model_name: str) -> tuple[Any, az.InferenceData, dict[str, Any]]:
    model: Any = bmb.Model(formula, data, family="gaussian")
    start = time.perf_counter()
    try:
        idata = model.fit(
            draws=SAMPLING["draws"],
            tune=SAMPLING["tune"],
            chains=SAMPLING["chains"],
            target_accept=SAMPLING["target_accept"],
            random_seed=SEED,
            nuts_sampler="nutpie",
            idata_kwargs={"log_likelihood": True},
        )
        sampler = "bambi_pymc_nutpie"
    except Exception as exc:  # noqa: BLE001 - fallback is documented in outputs.
        fallback_reason = f"{type(exc).__name__}: {exc}"
        model = build_pymc_model(formula, data)
        with model:
            idata = pm.sample(
                draws=SAMPLING["draws"],
                tune=SAMPLING["tune"],
                chains=SAMPLING["chains"],
                target_accept=SAMPLING["target_accept"],
                random_seed=SEED,
                nuts_sampler="nutpie",
                return_inferencedata=True,
                idata_kwargs={"log_likelihood": True},
            )
        sampler = f"explicit_pymc_nutpie_fallback_after_bambi_error: {fallback_reason}"
    runtime = time.perf_counter() - start
    runtime_row = {
        "model_name": model_name,
        "formula": formula,
        "draws": SAMPLING["draws"],
        "tune": SAMPLING["tune"],
        "chains": SAMPLING["chains"],
        "target_accept": SAMPLING["target_accept"],
        "seed": SEED,
        "sampler": sampler,
        "runtime_seconds": runtime,
    }
    return model, idata, runtime_row


def build_pymc_model(formula: str, data: pd.DataFrame) -> pm.Model:
    participant_codes = data["participant_id"].cat.codes.to_numpy()
    stimulus_codes = data["stimulus_id"].cat.codes.to_numpy()
    episode_codes = data["episode"].cat.codes.to_numpy()
    group_codes = data["group"].cat.codes.to_numpy()
    y = data["rating"].to_numpy(dtype=float)
    coords = {
        "observation": np.arange(len(data)),
        "episode_dim": ["EDR-2", "FM-1"],
        "group_dim": ["group_02"],
        "participant_id__factor_dim": list(data["participant_id"].cat.categories.astype(str)),
        "stimulus_id__factor_dim": list(data["stimulus_id"].cat.categories.astype(str)),
    }
    include_fixed = formula == FINAL_FORMULA
    with pm.Model(coords=coords) as model:
        intercept = pm.Normal("Intercept", mu=50, sigma=30)
        sigma_participant = pm.HalfNormal("1|participant_id_sigma", sigma=20)
        sigma_stimulus = pm.HalfNormal("1|stimulus_id_sigma", sigma=20)
        sigma = pm.HalfNormal("sigma", sigma=30)
        participant_z = pm.Normal("participant_z", mu=0, sigma=1, dims="participant_id__factor_dim")
        stimulus_z = pm.Normal("stimulus_z", mu=0, sigma=1, dims="stimulus_id__factor_dim")
        participant_effect = pm.Deterministic(
            "1|participant_id",
            participant_z * sigma_participant,
            dims="participant_id__factor_dim",
        )
        stimulus_effect = pm.Deterministic(
            "1|stimulus_id",
            stimulus_z * sigma_stimulus,
            dims="stimulus_id__factor_dim",
        )
        mu = intercept + participant_effect[participant_codes] + stimulus_effect[stimulus_codes]
        if include_fixed:
            episode = pm.Normal("episode", mu=0, sigma=20, dims="episode_dim")
            group = pm.Normal("group", mu=0, sigma=20, dims="group_dim")
            edr2 = (episode_codes == 1).astype(float)
            fm1 = (episode_codes == 2).astype(float)
            group02 = (group_codes == 1).astype(float)
            mu = mu + episode[0] * edr2 + episode[1] * fm1 + group[0] * group02
        pm.Normal("rating", mu=mu, sigma=sigma, observed=y, dims="observation")
    return model


def diagnostics_table(idatas: dict[str, az.InferenceData], runtimes: list[dict[str, Any]]) -> pd.DataFrame:
    runtime_by_name = {row["model_name"]: row for row in runtimes}
    rows = []
    for name, idata in idatas.items():
        summary = az.summary(idata, hdi_prob=0.94, round_to=None)
        sample_stats = idata.sample_stats
        divergences = int(sample_stats["diverging"].sum()) if "diverging" in sample_stats else 0
        max_tree_depth = int(sample_stats["tree_depth"].max()) if "tree_depth" in sample_stats else np.nan
        tree_depth_warnings = int((sample_stats["tree_depth"] >= 10).sum()) if "tree_depth" in sample_stats else 0
        energy_warnings = 0
        if "energy" in sample_stats:
            energy = sample_stats["energy"].values.reshape(-1)
            energy_warnings = int(np.isnan(energy).sum())
        rows.append(
            {
                "model_name": name,
                "divergences": divergences,
                "max_rhat": float(summary["r_hat"].max()),
                "min_bulk_ess": float(summary["ess_bulk"].min()),
                "min_tail_ess": float(summary["ess_tail"].min()),
                "max_tree_depth": max_tree_depth,
                "tree_depth_warnings": tree_depth_warnings,
                "energy_warnings": energy_warnings,
                "runtime_seconds": runtime_by_name[name]["runtime_seconds"],
                "sampler": runtime_by_name[name]["sampler"],
            }
        )
    return pd.DataFrame(rows)


def summarize_posterior(idata: az.InferenceData, var_names: list[str]) -> pd.DataFrame:
    summary = az.summary(idata, var_names=var_names, hdi_prob=0.94, round_to=None)
    summary = summary.reset_index(names="term")
    return summary.rename(columns={"hdi_3%": "hdi_3", "hdi_97%": "hdi_97", "mcse_mean": "mcse"})


def variance_and_icc(
    idata: az.InferenceData,
    model_name: str,
    icc_scope: str,
    formula: str,
    primary_for_results: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    posterior = idata.posterior
    participant_var = posterior["1|participant_id_sigma"] ** 2
    stimulus_var = posterior["1|stimulus_id_sigma"] ** 2
    residual_var = posterior["sigma"] ** 2
    total = participant_var + stimulus_var + residual_var
    dataset = {
        "participant_variance": participant_var,
        "stimulus_variance": stimulus_var,
        "residual_variance": residual_var,
        "participant_ICC": participant_var / total,
        "stimulus_ICC": stimulus_var / total,
        "residual_share": residual_var / total,
    }
    icc_idata = az.from_dict(posterior={key: value.values for key, value in dataset.items()})
    summary = az.summary(icc_idata, var_names=list(dataset), hdi_prob=0.94, round_to=None).reset_index(names="term")
    summary = summary.rename(columns={"hdi_3%": "hdi_3", "hdi_97%": "hdi_97", "mcse_mean": "mcse"})
    summary.insert(0, "model_name", model_name)
    summary.insert(1, "icc_scope", icc_scope)
    summary.insert(2, "icc_label", icc_scope)
    summary.insert(3, "formula", formula)
    summary.insert(4, "primary_for_results", primary_for_results)
    sd_summary = summarize_posterior(idata, ["1|participant_id_sigma", "1|stimulus_id_sigma", "sigma"])
    sd_summary.insert(0, "model_name", model_name)
    sd_summary.insert(1, "icc_scope", icc_scope)
    sd_summary.insert(2, "icc_label", icc_scope)
    sd_summary.insert(3, "formula", formula)
    sd_summary.insert(4, "primary_for_results", primary_for_results)
    return sd_summary, summary


def stack_draws(array: Any) -> np.ndarray:
    return np.asarray(array.stack(sample=("chain", "draw")).values)


def coefficient_draws(idata: az.InferenceData) -> dict[str, np.ndarray]:
    posterior = idata.posterior
    draws = {"Intercept": stack_draws(posterior["Intercept"])}
    for coord in posterior.coords.get("episode_dim", []):
        label = str(coord.values if hasattr(coord, "values") else coord)
        draws[f"episode[{label}]"] = stack_draws(posterior["episode"].sel(episode_dim=label))
    for coord in posterior.coords.get("group_dim", []):
        label = str(coord.values if hasattr(coord, "values") else coord)
        draws[f"group[{label}]"] = stack_draws(posterior["group"].sel(group_dim=label))
    return draws


def episode_means_and_contrasts(idata: az.InferenceData, data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    draws = coefficient_draws(idata)
    group_02_weight = float((data.drop_duplicates("participant_id")["group"].astype(str) == "group_02").mean())
    group_effect = draws.get("group[group_02]", np.zeros_like(draws["Intercept"]))
    episode_draws = {
        "EDR-1": draws["Intercept"] + group_02_weight * group_effect,
        "EDR-2": draws["Intercept"] + draws.get("episode[EDR-2]", 0) + group_02_weight * group_effect,
        "FM-1": draws["Intercept"] + draws.get("episode[FM-1]", 0) + group_02_weight * group_effect,
    }
    episode_rows = [draw_summary("episode", episode, values) for episode, values in episode_draws.items()]
    contrast_rows = []
    for left, right in itertools.combinations(episode_draws, 2):
        values = episode_draws[right] - episode_draws[left]
        contrast_rows.append(draw_summary("episode_contrast", f"{right} minus {left}", values))
    return pd.DataFrame(episode_rows), pd.DataFrame(contrast_rows)


def draw_summary(summary_type: str, level: str, values: np.ndarray) -> dict[str, Any]:
    hdi = az.hdi(values, hdi_prob=0.94)
    return {
        "summary_type": summary_type,
        "level": level,
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "sd": float(np.std(values, ddof=1)),
        "hdi_3": float(hdi[0]),
        "hdi_97": float(hdi[1]),
        "probability_above_zero": float(np.mean(values > 0)),
        "probability_below_zero": float(np.mean(values < 0)),
    }


def stimulus_random_draws(idata: az.InferenceData, stimulus_id: str) -> np.ndarray:
    posterior = idata.posterior
    return stack_draws(posterior["1|stimulus_id"].sel(stimulus_id__factor_dim=stimulus_id))


def expected_rating_draws(idata: az.InferenceData, episode: str, group: str, stimulus_id: str) -> np.ndarray:
    draws = coefficient_draws(idata)
    values = draws["Intercept"].copy()
    if episode != "EDR-1":
        values = values + draws.get(f"episode[{episode}]", 0)
    if group == "group_02":
        values = values + draws.get("group[group_02]", 0)
    values = values + stimulus_random_draws(idata, stimulus_id)
    return values


def posterior_expected_ratings(idata: az.InferenceData, data: pd.DataFrame) -> pd.DataFrame:
    combos = data[["group", "episode", "song_id", "stimulus_id", "mix_id"]].drop_duplicates().sort_values(["group", "episode", "song_id", "stimulus_id"])
    rows = []
    for row in combos.itertuples(index=False):
        values = expected_rating_draws(idata, str(row.episode), str(row.group), str(row.stimulus_id))
        rows.append(
            {
                "group": row.group,
                "episode": row.episode,
                "song_id": row.song_id,
                "stimulus_id": row.stimulus_id,
                "mix_id": row.mix_id,
                **draw_summary("posterior_expected_rating", "expected_rating", values),
            }
        )
    return pd.DataFrame(rows).drop(columns=["summary_type", "level"])


def winner_probabilities(expected: pd.DataFrame, idata: az.InferenceData) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    validation_rows = []
    for (song_id, episode), frame in expected.groupby(["song_id", "episode"], sort=True):
        draw_matrix = []
        for _, row in frame.iterrows():
            draw_matrix.append(expected_rating_draws(idata, str(row["episode"]), str(row["group"]), str(row["stimulus_id"])))
        matrix = np.vstack(draw_matrix)
        max_per_draw = matrix.max(axis=0)
        is_winner = np.isclose(matrix, max_per_draw[None, :], rtol=0, atol=1e-12)
        tie_counts = is_winner.sum(axis=0)
        credit = is_winner / tie_counts[None, :]
        probabilities = credit.mean(axis=1)
        draw_tie_probability = float(np.mean(tie_counts > 1))
        max_probability = probabilities.max()
        final_tie = np.isclose(probabilities, max_probability, rtol=0, atol=1e-12)
        for idx, (_, row) in enumerate(frame.iterrows()):
            rows.append(
                {
                    "song_id": song_id,
                    "group": row["group"],
                    "episode": episode,
                    "stimulus_id": row["stimulus_id"],
                    "mix_id": row["mix_id"],
                    "posterior_mean_expected_rating": row["mean"],
                    "hdi_3": row["hdi_3"],
                    "hdi_97": row["hdi_97"],
                    "posterior_probability_highest": float(probabilities[idx]),
                    "is_final_predicted_winner": bool(final_tie[idx] and final_tie.sum() == 1),
                    "draw_level_tie_probability": draw_tie_probability,
                    "final_probability_tie_flag": bool(final_tie.sum() > 1),
                }
            )
        validation_rows.append(
            {
                "song_id": song_id,
                "episode": episode,
                "candidate_count": len(frame),
                "probability_sum": float(probabilities.sum()),
                "probabilities_between_0_and_1": bool(((probabilities >= 0) & (probabilities <= 1)).all()),
                "n_final_winners": int(sum(row["is_final_predicted_winner"] for row in rows if row["song_id"] == song_id and row["episode"] == episode)),
                "draw_level_tie_probability": draw_tie_probability,
                "final_probability_tie_flag": bool(final_tie.sum() > 1),
                "validation_passed": len(frame) == 5 and np.isclose(probabilities.sum(), 1.0) and ((probabilities >= 0) & (probabilities <= 1)).all() and final_tie.sum() == 1,
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(validation_rows)


def posterior_predictive_checks(model: Any, idata: az.InferenceData, data: pd.DataFrame) -> tuple[az.InferenceData, pd.DataFrame]:
    draws_by_observation = observed_posterior_predictive_draws(idata, data)
    n_chains = idata.posterior.sizes["chain"]
    n_draws = idata.posterior.sizes["draw"]
    ppc_group = az.from_dict(
        posterior_predictive={"rating": draws_by_observation.T.reshape(n_chains, n_draws, len(data))},
        coords={"observation": np.arange(len(data))},
        dims={"rating": ["observation"]},
    )
    idata.extend(ppc_group)
    observed = data["rating"].to_numpy()
    rows = [
        {"metric": "observed_mean", "value": float(observed.mean())},
        {"metric": "observed_sd", "value": float(observed.std(ddof=1))},
        {"metric": "posterior_predictive_mean_mean", "value": float(draws_by_observation.mean(axis=0).mean())},
        {"metric": "posterior_predictive_sd_mean", "value": float(draws_by_observation.std(axis=0, ddof=1).mean())},
        {"metric": "posterior_predictive_below_0", "value": float((draws_by_observation < 0).mean())},
        {"metric": "posterior_predictive_above_100", "value": float((draws_by_observation > 100).mean())},
        {"metric": "posterior_predictive_outside_0_100", "value": float(((draws_by_observation < 0) | (draws_by_observation > 100)).mean())},
    ]
    for episode in data["episode"].cat.categories:
        mask = data["episode"].astype(str).to_numpy() == episode
        rows.append({"metric": f"observed_episode_mean_{episode}", "value": float(observed[mask].mean())})
        rows.append({"metric": f"ppc_episode_mean_{episode}", "value": float(draws_by_observation[mask].mean(axis=0).mean())})
    for group in data["group"].cat.categories:
        mask = data["group"].astype(str).to_numpy() == group
        rows.append({"metric": f"observed_group_mean_{group}", "value": float(observed[mask].mean())})
        rows.append({"metric": f"ppc_group_mean_{group}", "value": float(draws_by_observation[mask].mean(axis=0).mean())})
    stimulus_observed = data.groupby("stimulus_id", observed=True)["rating"].mean()
    stimulus_ppc = []
    for stimulus in stimulus_observed.index:
        mask = data["stimulus_id"].astype(str).to_numpy() == str(stimulus)
        stimulus_ppc.append(draws_by_observation[mask].mean(axis=0).mean())
    rows.append({"metric": "observed_stimulus_mean_sd", "value": float(stimulus_observed.std(ddof=1))})
    rows.append({"metric": "ppc_stimulus_mean_sd", "value": float(np.std(stimulus_ppc, ddof=1))})
    return idata, pd.DataFrame(rows)


def observed_posterior_predictive_draws(idata: az.InferenceData, data: pd.DataFrame) -> np.ndarray:
    rng = np.random.default_rng(SEED)
    coeffs = coefficient_draws(idata)
    sigma = stack_draws(idata.posterior["sigma"])
    n_samples = len(sigma)
    result = np.empty((len(data), n_samples), dtype=float)
    participant_effects = idata.posterior["1|participant_id"].stack(sample=("chain", "draw"))
    stimulus_effects = idata.posterior["1|stimulus_id"].stack(sample=("chain", "draw"))
    for obs_index, row in enumerate(data.itertuples(index=False)):
        mu = coeffs["Intercept"].copy()
        episode = str(row.episode)
        group = str(row.group)
        if episode != "EDR-1":
            mu = mu + coeffs.get(f"episode[{episode}]", 0)
        if group == "group_02":
            mu = mu + coeffs.get("group[group_02]", 0)
        mu = mu + np.asarray(participant_effects.sel(participant_id__factor_dim=str(row.participant_id)).values)
        mu = mu + np.asarray(stimulus_effects.sel(stimulus_id__factor_dim=str(row.stimulus_id)).values)
        result[obs_index, :] = rng.normal(mu, sigma)
    return result


def observed_preference_summary(preferences: pd.DataFrame, ties: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, pref in preferences.iterrows():
        winners = str(pref.get("preferred_stimulus_id", "")).split("|")
        mix_ids = str(pref.get("preferred_mix_id", "")).split("|")
        credit = 1 / len(winners) if winners and winners != [""] else np.nan
        for stimulus_id, mix_id in zip(winners, mix_ids):
            rows.append(
                {
                    "song_id": pref["song_id"],
                    "group": pref["group"],
                    "episode": pref["episode"],
                    "stimulus_id": stimulus_id,
                    "mix_id": mix_id,
                    "winner_credit": credit,
                    "tie_flag": bool(pref["tie_flag"]),
                }
            )
    winners = pd.DataFrame(rows)
    summary = winners.groupby(["song_id", "group", "episode", "stimulus_id", "mix_id"], dropna=False).agg(
        observed_winner_credit=("winner_credit", "sum"),
        observed_winner_trials=("winner_credit", "count"),
        tied_winner_rows=("tie_flag", "sum"),
    ).reset_index()
    totals = preferences.groupby(["song_id", "episode"], dropna=False).size().reset_index(name="song_episode_trials")
    summary = summary.merge(totals, on=["song_id", "episode"], how="left")
    summary["observed_winner_share_fractional_ties"] = summary["observed_winner_credit"] / summary["song_episode_trials"]
    summary["comparison_scope"] = "in-sample descriptive fit only"
    return summary.sort_values(["song_id", "episode", "observed_winner_share_fractional_ties"], ascending=[True, True, False])


def make_figures(data: pd.DataFrame, idata: az.InferenceData, ppc_summary: pd.DataFrame) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(8, 5))
    plt.hist(data["rating"], bins=20, color="#4c78a8", edgecolor="white")
    plt.title("Observed Real Rating Distribution")
    plt.xlabel("Rating")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(FIGURE_DIR / "observed_rating_distribution.png", dpi=150)
    plt.close()

    az.plot_trace(idata, var_names=["Intercept", "episode", "group", "1|participant_id_sigma", "1|stimulus_id_sigma", "sigma"], compact=True)
    plt.tight_layout()
    plt.savefig(FIGURE_DIR / "real_stimulus_model_trace_selected.png", dpi=150)
    plt.close("all")

    observed = data.groupby("episode", observed=True)["rating"].mean()
    ppc_episode = {
        row.metric.replace("ppc_episode_mean_", ""): row.value
        for row in ppc_summary.itertuples(index=False)
        if row.metric.startswith("ppc_episode_mean_")
    }
    pd.DataFrame({"observed": observed, "posterior_predictive": pd.Series(ppc_episode)}).plot(kind="bar", figsize=(7, 4))
    plt.title("Observed vs Posterior Predictive Episode Means")
    plt.ylabel("Rating")
    plt.tight_layout()
    plt.savefig(FIGURE_DIR / "posterior_predictive_episode_means.png", dpi=150)
    plt.close()


def empirical_findings_text(
    summary: pd.DataFrame,
    null_icc: pd.DataFrame,
    final_icc: pd.DataFrame,
    fixed: pd.DataFrame,
    diagnostics: pd.DataFrame,
    ppc: pd.DataFrame,
) -> str:
    row = summary.iloc[0]
    participant_icc = final_icc.query("term == 'participant_ICC'").iloc[0]
    stimulus_icc = final_icc.query("term == 'stimulus_ICC'").iloc[0]
    residual = final_icc.query("term == 'residual_share'").iloc[0]
    null_participant_icc = null_icc.query("term == 'participant_ICC'").iloc[0]
    null_stimulus_icc = null_icc.query("term == 'stimulus_ICC'").iloc[0]
    null_residual = null_icc.query("term == 'residual_share'").iloc[0]
    final_diag = diagnostics.query("model_name == 'final_stimulus'").iloc[0]
    boundary = ppc.query("metric == 'posterior_predictive_outside_0_100'").iloc[0]["value"]
    lines = [
        "# Empirical Stimulus-Model Findings",
        "",
        f"The achieved analysable sample was N={int(row['final_recommended_analysable_n'])}, with {int(row['final_group_01_n'])} participants in group_01 and {int(row['final_group_02_n'])} in group_02.",
        "The primary dissertation ICCs are the conditional / final-model ICCs from the final stimulus model that includes episode and group fixed effects.",
        f"Conditional / final-model participant ICC posterior mean was {participant_icc['mean']:.3f} with 94% HDI [{participant_icc['hdi_3']:.3f}, {participant_icc['hdi_97']:.3f}], representing the proportion of remaining rating variance associated with stable between-listener differences after the fixed effects.",
        f"Conditional / final-model stimulus ICC posterior mean was {stimulus_icc['mean']:.3f} with 94% HDI [{stimulus_icc['hdi_3']:.3f}, {stimulus_icc['hdi_97']:.3f}], representing the remaining proportion associated with differences among the 20 mix stimuli. The conditional residual share posterior mean was {residual['mean']:.3f}.",
        f"Unconditional / null-model ICCs are also exported for variance-decomposition context only: participant ICC mean {null_participant_icc['mean']:.3f}, stimulus ICC mean {null_stimulus_icc['mean']:.3f}, residual share mean {null_residual['mean']:.3f}.",
        "Episode fixed effects are additive context shifts in native rating-point units, averaged across group and stimulus variability; they should be interpreted by magnitude, direction, and uncertainty rather than binary significance language.",
        "The group coefficient is structurally linked to song allocation, so it represents a systematic difference between the two assigned song sets / study groups rather than an independent causal effect of group membership.",
        f"The final model diagnostics recorded {int(final_diag['divergences'])} divergences, maximum R-hat {final_diag['max_rhat']:.3f}, minimum bulk ESS {final_diag['min_bulk_ess']:.1f}, and minimum tail ESS {final_diag['min_tail_ess']:.1f}.",
        f"The Gaussian posterior predictive outside-range proportion was {boundary:.4f}; samples were not clipped.",
        "Posterior highest-rated-mix probabilities were computed draw by draw using posterior expected ratings, with fractional credit for exact draw-level ties.",
        "Because the primary model has no Episode x Stimulus interaction or participant-specific episode slopes, it does not fully parameterise context-specific stimulus reversals or every form of within-listener heterogeneity.",
        f"Planned preferred analysable sample size was 50; achieved analysable N was {int(row['final_recommended_analysable_n'])}, so posterior estimates may be less precise than anticipated in the design simulations.",
    ]
    return "\n".join(lines) + "\n"


def write_outputs(outputs: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    outputs["descriptive"].to_csv(OUTPUT_DIR / "descriptive_summary.csv", index=False)
    outputs["fixed"].to_csv(OUTPUT_DIR / "fixed_effect_posterior_summary.csv", index=False)
    outputs["episode_means"].to_csv(OUTPUT_DIR / "episode_posterior_means.csv", index=False)
    outputs["episode_contrasts"].to_csv(OUTPUT_DIR / "episode_contrasts.csv", index=False)
    outputs["variance"].to_csv(OUTPUT_DIR / "variance_components.csv", index=False)
    outputs["null_variance"].to_csv(OUTPUT_DIR / "null_model_variance_components.csv", index=False)
    outputs["final_variance"].to_csv(OUTPUT_DIR / "final_model_variance_components.csv", index=False)
    outputs["icc"].to_csv(OUTPUT_DIR / "icc_posterior_summary.csv", index=False)
    outputs["null_icc"].to_csv(OUTPUT_DIR / "null_model_icc_summary.csv", index=False)
    outputs["final_icc"].to_csv(OUTPUT_DIR / "final_model_icc_summary.csv", index=False)
    outputs["diagnostics"].to_csv(OUTPUT_DIR / "convergence_diagnostics.csv", index=False)
    outputs["ppc"].to_csv(OUTPUT_DIR / "posterior_predictive_summary.csv", index=False)
    outputs["expected"].to_csv(OUTPUT_DIR / "posterior_expected_ratings.csv", index=False)
    outputs["winners"].to_csv(OUTPUT_DIR / "predicted_highest_rated_mixes.csv", index=False)
    outputs["winner_validation"].to_csv(OUTPUT_DIR / "posterior_winner_validation.csv", index=False)
    outputs["observed_preferences"].to_csv(OUTPUT_DIR / "observed_preference_summary.csv", index=False)
    pd.DataFrame(outputs["runtimes"]).to_csv(OUTPUT_DIR / "runtime_execution_summary.csv", index=False)
    outputs["validation"].to_csv(OUTPUT_DIR / "model_dataset_validation.csv", index=False)
    (OUTPUT_DIR / "empirical_stimulus_model_findings.md").write_text(outputs["findings_text"], encoding="utf-8")
    outputs["intercept_idata"].to_netcdf(OUTPUT_DIR / "intercept_only_real_stimulus_model_idata.nc")
    outputs["final_idata"].to_netcdf(OUTPUT_DIR / "final_real_stimulus_model_idata.nc")
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_ratings": str(RATINGS_PATH.relative_to(PROJECT_ROOT)),
        "input_cleaning_manifest": str(MANIFEST_PATH.relative_to(PROJECT_ROOT)),
        "cleaned_dataset": cleaned_dataset_metadata(outputs["summary"]),
        "intercept_formula": INTERCEPT_FORMULA,
        "final_formula": FINAL_FORMULA,
        "icc_outputs": {
            "unconditional_null_model": "null_model_icc_summary.csv",
            "conditional_final_model": "final_model_icc_summary.csv",
            "primary_for_dissertation_results": "conditional_final_model",
            "compatibility_alias": "icc_posterior_summary.csv contains conditional / final-model ICCs",
        },
        "sampling": SAMPLING | {"seed": SEED},
        "planned_preferred_analysable_sample": 50,
        "achieved_analysable_sample": int(outputs["summary"].iloc[0]["final_recommended_analysable_n"]),
        "final_gate": "REAL STIMULUS MODEL READY FOR DISSERTATION RESULTS SECTION" if outputs["diagnostics"]["divergences"].sum() == 0 else "REAL STIMULUS MODEL REQUIRES DIAGNOSTIC REVIEW",
    }
    (OUTPUT_DIR / "real_stimulus_model_manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")


def run_real_stimulus_model() -> dict[str, Any]:
    inputs = load_inputs()
    data = prepare_model_data(inputs["ratings"])
    validation = validate_model_data(data)
    if not validation["passed"].all():
        raise ValueError("Model dataset validation failed; inspect model_dataset_validation.csv.")
    descriptive = descriptive_summaries(data, inputs["preferences"])
    intercept_model, intercept_idata, intercept_runtime = fit_model(INTERCEPT_FORMULA, data, "intercept_only")
    final_model, final_idata, final_runtime = fit_model(FINAL_FORMULA, data, "final_stimulus")
    final_idata, ppc = posterior_predictive_checks(final_model, final_idata, data)
    idatas = {"intercept_only": intercept_idata, "final_stimulus": final_idata}
    runtimes = [intercept_runtime, final_runtime]
    diagnostics = diagnostics_table(idatas, runtimes)
    null_variance, null_icc = variance_and_icc(
        intercept_idata,
        "intercept_only",
        "unconditional / null-model ICC",
        INTERCEPT_FORMULA,
        False,
    )
    final_variance, final_icc = variance_and_icc(
        final_idata,
        "final_stimulus",
        "conditional / final-model ICC",
        FINAL_FORMULA,
        True,
    )
    variance = pd.concat([null_variance, final_variance], ignore_index=True)
    icc = final_icc.copy()
    fixed = summarize_posterior(final_idata, ["Intercept", "episode", "group"])
    episode_means, episode_contrasts = episode_means_and_contrasts(final_idata, data)
    expected = posterior_expected_ratings(final_idata, data)
    winners, winner_validation = winner_probabilities(expected, final_idata)
    observed_preferences = observed_preference_summary(inputs["preferences"], inputs["ties"])
    real_summary = pd.read_csv(DATA_DIR / "real_data_summary.csv")
    make_figures(data, final_idata, ppc)
    findings_text = empirical_findings_text(real_summary, null_icc, final_icc, fixed, diagnostics, ppc)
    outputs = {
        "summary": real_summary,
        "validation": validation,
        "descriptive": descriptive,
        "intercept_idata": intercept_idata,
        "final_idata": final_idata,
        "runtimes": runtimes,
        "diagnostics": diagnostics,
        "variance": variance,
        "null_variance": null_variance,
        "final_variance": final_variance,
        "icc": icc,
        "null_icc": null_icc,
        "final_icc": final_icc,
        "fixed": fixed,
        "episode_means": episode_means,
        "episode_contrasts": episode_contrasts,
        "ppc": ppc,
        "expected": expected,
        "winners": winners,
        "winner_validation": winner_validation,
        "observed_preferences": observed_preferences,
        "findings_text": findings_text,
    }
    write_outputs(outputs)
    return outputs
