"""Final empirical acoustic feature-based Bayesian multilevel model."""

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
import xarray as xr


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "statistical-baseline/data/real"
STIMULUS_OUTPUT_DIR = PROJECT_ROOT / "statistical-baseline/outputs/real_stimulus_model"
OUTPUT_DIR = PROJECT_ROOT / "statistical-baseline/outputs/real_feature_model"
FIGURE_DIR = OUTPUT_DIR / "figures"
RATINGS_PATH = DATA_DIR / "real_ratings_clean.csv"
PREFERENCES_PATH = DATA_DIR / "real_trial_preferences.csv"
MANIFEST_PATH = DATA_DIR / "real_cleaning_manifest.json"
SUMMARY_PATH = DATA_DIR / "real_data_summary.csv"
PARTICIPANTS_PATH = DATA_DIR / "real_participants_clean.csv"
FEATURE_TABLE_PATH = PROJECT_ROOT / "statistical-baseline/outputs/feature_exploration/final_20_stimulus_feature_table.csv"

PRIMARY_FORMULA = "rating ~ episode + group + z_RMS + z_CF + z_SW + (1 | participant_id) + (1 | stimulus_id)"
SI_FORMULA = "rating ~ episode + group + z_RMS + z_CF + z_SW + z_SI + (1 | participant_id) + (1 | stimulus_id)"
BOUNDED_FORMULA = "rating_01 ~ episode + group + z_RMS + z_CF + z_SW + (1 | participant_id) + (1 | stimulus_id)"
SEED = 20260817
SAMPLING = {"draws": 1000, "tune": 1000, "chains": 4, "target_accept": 0.95}
PRIMARY_FEATURES = ["z_RMS", "z_CF", "z_SW"]
SI_FEATURES = PRIMARY_FEATURES + ["z_SI"]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cleaned_dataset_metadata() -> dict[str, Any]:
    summary = pd.read_csv(SUMMARY_PATH).iloc[0]
    participants = pd.read_csv(PARTICIPANTS_PATH)
    cleaning_manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {
        "cleaned_ratings_path": str(RATINGS_PATH.relative_to(PROJECT_ROOT)),
        "cleaned_ratings_sha256": file_sha256(RATINGS_PATH),
        "cleaning_manifest_path": str(MANIFEST_PATH.relative_to(PROJECT_ROOT)),
        "cleaning_manifest_sha256": file_sha256(MANIFEST_PATH),
        "raw_source_path": cleaning_manifest["raw_provenance"]["stored_path"],
        "raw_source_sha256": cleaning_manifest["raw_provenance"]["sha256"],
        "analysable_n": int(summary["final_recommended_analysable_n"]),
        "group_split": participants["group"].value_counts().sort_index().to_dict(),
        "rating_count": int(summary["final_analysable_rating_rows"]),
        "trial_count": int(summary["participant_song_episode_trials"]),
    }


def load_stimulus_icc_summary() -> pd.DataFrame:
    final_icc_path = STIMULUS_OUTPUT_DIR / "final_model_icc_summary.csv"
    if final_icc_path.exists():
        return pd.read_csv(final_icc_path)
    return pd.read_csv(STIMULUS_OUTPUT_DIR / "icc_posterior_summary.csv")


def load_inputs() -> dict[str, pd.DataFrame]:
    return {
        "ratings": pd.read_csv(RATINGS_PATH),
        "preferences": pd.read_csv(PREFERENCES_PATH),
        "feature_table": pd.read_csv(FEATURE_TABLE_PATH),
        "stimulus_icc": load_stimulus_icc_summary(),
        "stimulus_diag": pd.read_csv(STIMULUS_OUTPUT_DIR / "convergence_diagnostics.csv"),
        "stimulus_ppc": pd.read_csv(STIMULUS_OUTPUT_DIR / "posterior_predictive_summary.csv"),
        "stimulus_fixed": pd.read_csv(STIMULUS_OUTPUT_DIR / "fixed_effect_posterior_summary.csv"),
        "stimulus_runtime": pd.read_csv(STIMULUS_OUTPUT_DIR / "runtime_execution_summary.csv"),
    }


def prepare_model_data(ratings: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "rating",
        "episode",
        "group",
        "participant_id",
        "stimulus_id",
        "song_id",
        "mix_id",
        "z_RMS",
        "z_CF",
        "z_SW",
        "z_SI",
    ]
    data = ratings[columns].copy()
    data["rating"] = pd.to_numeric(data["rating"], errors="coerce")
    n = len(data)
    data["rating_01"] = ((data["rating"] / 100.0) * (n - 1) + 0.5) / n
    for column in ["episode", "group", "participant_id", "stimulus_id", "song_id", "mix_id"]:
        data[column] = data[column].astype(str)
    data["episode"] = pd.Categorical(data["episode"], categories=["EDR-1", "EDR-2", "FM-1"], ordered=False)
    data["group"] = pd.Categorical(data["group"], categories=["group_01", "group_02"], ordered=False)
    data["participant_id"] = pd.Categorical(data["participant_id"], ordered=False)
    data["stimulus_id"] = pd.Categorical(data["stimulus_id"], ordered=False)
    return data


def validate_model_data(data: pd.DataFrame, feature_table: pd.DataFrame) -> pd.DataFrame:
    summary = pd.read_csv(SUMMARY_PATH).iloc[0]
    participants = pd.read_csv(PARTICIPANTS_PATH)
    expected_n = int(summary["final_recommended_analysable_n"])
    expected_group_counts = participants["group"].value_counts().sort_index().to_dict()
    expected_ratings = int(summary["final_analysable_rating_rows"])
    profile_cols = ["stimulus_id", "z_RMS", "z_CF", "z_SW", "z_SI"]
    actual_profiles = data[profile_cols].drop_duplicates().sort_values("stimulus_id").reset_index(drop=True)
    frozen_profiles = feature_table[profile_cols].drop_duplicates().sort_values("stimulus_id").reset_index(drop=True)
    merged = actual_profiles.merge(frozen_profiles, on="stimulus_id", suffixes=("_data", "_frozen"), how="outer", indicator=True)
    feature_match = (merged["_merge"].eq("both").all() and all(np.allclose(merged[f"{col}_data"], merged[f"{col}_frozen"]) for col in ["z_RMS", "z_CF", "z_SW", "z_SI"]))
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
        "complete_z_RMS": data["z_RMS"].notna().all(),
        "complete_z_CF": data["z_CF"].notna().all(),
        "complete_z_SW": data["z_SW"].notna().all(),
        "complete_z_SI": data["z_SI"].notna().all(),
        "exactly_20_unique_feature_profiles": len(actual_profiles) == 20,
        "z_features_match_frozen_phase3_table": bool(feature_match),
    }
    return pd.DataFrame(
        [{"check": check, "passed": bool(passed), "actual_value": actual_value(check, data, actual_profiles)} for check, passed in checks.items()]
    )


def actual_value(check: str, data: pd.DataFrame, profiles: pd.DataFrame) -> Any:
    mapping = {
        "final_analysable_n_matches_cleaning_summary": data["participant_id"].nunique(),
        "group_01_n_matches_cleaning_summary": data.drop_duplicates("participant_id").query("group == 'group_01'").shape[0],
        "group_02_n_matches_cleaning_summary": data.drop_duplicates("participant_id").query("group == 'group_02'").shape[0],
        "rating_observations_match_cleaning_summary": len(data),
        "stimuli_20": data["stimulus_id"].nunique(),
        "songs_4": data["song_id"].nunique(),
        "episodes_3": data["episode"].nunique(),
        "ratings_per_participant_30": json.dumps(data.groupby("participant_id", observed=True).size().describe().to_dict()),
        "no_missing_outcome": int(data["rating"].isna().sum()),
        "no_invalid_ratings": int((~data["rating"].between(0, 100)).sum()),
        "no_missing_identifiers": int(data[["participant_id", "group", "stimulus_id"]].isna().sum().sum()),
        "exactly_20_unique_feature_profiles": len(profiles),
    }
    if check.startswith("complete_"):
        return int(data[check.replace("complete_", "")].isna().sum())
    return mapping.get(check, "")


def feature_descriptives(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for feature in SI_FEATURES:
        quartile = pd.qcut(data[feature], q=4, labels=["Q1", "Q2", "Q3", "Q4"], duplicates="drop")
        for level, frame in data.groupby(quartile, observed=True):
            values = frame["rating"]
            rows.append(
                {
                    "feature": feature,
                    "quartile": str(level),
                    "n": int(values.count()),
                    "rating_mean": float(values.mean()),
                    "rating_median": float(values.median()),
                    "rating_sd": float(values.std(ddof=1)),
                    "rating_min": float(values.min()),
                    "rating_max": float(values.max()),
                    "unique_stimuli": int(frame["stimulus_id"].nunique()),
                    "interpretation_note": "descriptive only; acoustic predictors vary at 20 stimulus levels, not 900 independent observations",
                }
            )
    boundary = {
        "feature": "outcome_boundary_distribution",
        "quartile": "all",
        "n": len(data),
        "rating_mean": float(data["rating"].mean()),
        "rating_median": float(data["rating"].median()),
        "rating_sd": float(data["rating"].std(ddof=1)),
        "rating_min": float(data["rating"].min()),
        "rating_max": float(data["rating"].max()),
        "unique_stimuli": int(data["stimulus_id"].nunique()),
        "interpretation_note": f"exact_zeros={(data['rating'] == 0).sum()}; exact_hundreds={(data['rating'] == 100).sum()}; <=5={(data['rating'] <= 5).sum()}; >=95={(data['rating'] >= 95).sum()}; transformed Beta sensitivity uses Smithson-Verkuilen adjustment",
    }
    rows.append(boundary)
    return pd.DataFrame(rows)


def fit_bambi_model(formula: str, data: pd.DataFrame, model_name: str) -> tuple[bmb.Model, az.InferenceData, dict[str, Any]]:
    model = bmb.Model(formula, data, family="gaussian")
    start = time.perf_counter()
    idata = model.fit(
        draws=SAMPLING["draws"],
        tune=SAMPLING["tune"],
        chains=SAMPLING["chains"],
        target_accept=SAMPLING["target_accept"],
        random_seed=SEED,
        nuts_sampler="nutpie",
        idata_kwargs={"log_likelihood": True},
    )
    runtime = time.perf_counter() - start
    idata = add_gaussian_log_likelihood(idata, data, formula)
    return model, idata, runtime_row(model_name, formula, runtime, "bambi_pymc_nutpie")


def runtime_row(model_name: str, formula: str, runtime: float, sampler: str) -> dict[str, Any]:
    return {
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


def stack_draws(array: Any) -> np.ndarray:
    return np.asarray(array.stack(sample=("chain", "draw")).values)


def coefficient_draws(idata: az.InferenceData, feature_names: list[str]) -> dict[str, np.ndarray]:
    posterior = idata.posterior
    draws = {"Intercept": stack_draws(posterior["Intercept"])}
    for coord in posterior.coords.get("episode_dim", []):
        label = str(coord.values if hasattr(coord, "values") else coord)
        draws[f"episode[{label}]"] = stack_draws(posterior["episode"].sel(episode_dim=label))
    for coord in posterior.coords.get("group_dim", []):
        label = str(coord.values if hasattr(coord, "values") else coord)
        draws[f"group[{label}]"] = stack_draws(posterior["group"].sel(group_dim=label))
    for feature in feature_names:
        draws[feature] = stack_draws(posterior[feature])
    return draws


def posterior_mu_for_observations(idata: az.InferenceData, data: pd.DataFrame, feature_names: list[str]) -> np.ndarray:
    coeffs = coefficient_draws(idata, feature_names)
    participant_effects = idata.posterior["1|participant_id"].stack(sample=("chain", "draw"))
    stimulus_effects = idata.posterior["1|stimulus_id"].stack(sample=("chain", "draw"))
    result = np.empty((len(data), len(coeffs["Intercept"])), dtype=float)
    for obs_index, row in enumerate(data.itertuples(index=False)):
        mu = coeffs["Intercept"].copy()
        episode = str(row.episode)
        group = str(row.group)
        if episode != "EDR-1":
            mu = mu + coeffs.get(f"episode[{episode}]", 0)
        if group == "group_02":
            mu = mu + coeffs.get("group[group_02]", 0)
        for feature in feature_names:
            mu = mu + coeffs[feature] * float(getattr(row, feature))
        mu = mu + np.asarray(participant_effects.sel(participant_id__factor_dim=str(row.participant_id)).values)
        mu = mu + np.asarray(stimulus_effects.sel(stimulus_id__factor_dim=str(row.stimulus_id)).values)
        result[obs_index, :] = mu
    return result


def add_gaussian_log_likelihood(idata: az.InferenceData, data: pd.DataFrame, formula: str) -> az.InferenceData:
    feature_names = feature_names_for_formula(formula)
    mu = posterior_mu_for_observations(idata, data, feature_names)
    sigma = stack_draws(idata.posterior["sigma"])
    y = data["rating"].to_numpy()[:, None]
    loglik = -0.5 * np.log(2 * np.pi * sigma[None, :] ** 2) - 0.5 * ((y - mu) / sigma[None, :]) ** 2
    n_chains = idata.posterior.sizes["chain"]
    n_draws = idata.posterior.sizes["draw"]
    ll = xr.Dataset(
        {"rating": (("chain", "draw", "observation"), loglik.T.reshape(n_chains, n_draws, len(data)))},
        coords={"chain": idata.posterior.coords["chain"], "draw": idata.posterior.coords["draw"], "observation": np.arange(len(data))},
    )
    if "log_likelihood" in idata.groups():
        del idata.log_likelihood
    idata.add_groups({"log_likelihood": ll})
    return idata


def feature_names_for_formula(formula: str) -> list[str]:
    if "z_SI" in formula:
        return SI_FEATURES
    if "z_RMS" in formula:
        return PRIMARY_FEATURES
    return []


def diagnostics_table(idatas: dict[str, az.InferenceData], runtimes: list[dict[str, Any]]) -> pd.DataFrame:
    runtime_by_name = {row["model_name"]: row for row in runtimes}
    rows = []
    for name, idata in idatas.items():
        summary = az.summary(idata, hdi_prob=0.94, round_to=None)
        sample_stats = idata.sample_stats
        divergences = int(sample_stats["diverging"].sum()) if "diverging" in sample_stats else 0
        max_tree_depth = int(sample_stats["tree_depth"].max()) if "tree_depth" in sample_stats else np.nan
        tree_depth_warnings = int((sample_stats["tree_depth"] >= 10).sum()) if "tree_depth" in sample_stats else 0
        energy_warnings = int(np.isnan(sample_stats["energy"].values).sum()) if "energy" in sample_stats else 0
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


def summarize_posterior(idata: az.InferenceData, var_names: list[str], model_name: str) -> pd.DataFrame:
    summary = az.summary(idata, var_names=var_names, hdi_prob=0.94, round_to=None).reset_index(names="term")
    summary = summary.rename(columns={"hdi_3%": "hdi_3", "hdi_97%": "hdi_97", "mcse_mean": "mcse"})
    summary.insert(0, "model_name", model_name)
    return summary


def variance_and_icc(idatas: dict[str, az.InferenceData]) -> tuple[pd.DataFrame, pd.DataFrame]:
    variance_rows = []
    icc_rows = []
    for model_name, idata in idatas.items():
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
        icc = az.summary(icc_idata, var_names=list(dataset), hdi_prob=0.94, round_to=None).reset_index(names="term")
        icc = icc.rename(columns={"hdi_3%": "hdi_3", "hdi_97%": "hdi_97", "mcse_mean": "mcse"})
        icc.insert(0, "model_name", model_name)
        icc_rows.append(icc)
        variance_rows.append(summarize_posterior(idata, ["1|participant_id_sigma", "1|stimulus_id_sigma", "sigma"], model_name))
    return pd.concat(variance_rows, ignore_index=True), pd.concat(icc_rows, ignore_index=True)


def posterior_predictive_summary(idatas: dict[str, az.InferenceData], data: pd.DataFrame, formulas: dict[str, str]) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    rows = []
    ppc_draws = {}
    observed = data["rating"].to_numpy()
    for model_name, idata in idatas.items():
        feature_names = SI_FEATURES if "z_SI" in formulas[model_name] else PRIMARY_FEATURES
        mu = posterior_mu_for_observations(idata, data, feature_names)
        sigma = stack_draws(idata.posterior["sigma"])
        rng = np.random.default_rng(SEED + len(ppc_draws))
        draws = rng.normal(mu, sigma[None, :])
        ppc_draws[model_name] = draws
        n_chains = idata.posterior.sizes["chain"]
        n_draws = idata.posterior.sizes["draw"]
        idata.extend(
            az.from_dict(
                posterior_predictive={"rating": draws.T.reshape(n_chains, n_draws, len(data))},
                coords={"observation": np.arange(len(data))},
                dims={"rating": ["observation"]},
            )
        )
        model_rows = [
            ("observed_mean", observed.mean()),
            ("observed_sd", observed.std(ddof=1)),
            ("posterior_predictive_mean_mean", draws.mean(axis=0).mean()),
            ("posterior_predictive_sd_mean", draws.std(axis=0, ddof=1).mean()),
            ("posterior_predictive_below_0", (draws < 0).mean()),
            ("posterior_predictive_above_100", (draws > 100).mean()),
            ("posterior_predictive_outside_0_100", ((draws < 0) | (draws > 100)).mean()),
        ]
        for metric, value in model_rows:
            rows.append({"model_name": model_name, "metric": metric, "value": float(value)})
        for episode in data["episode"].cat.categories:
            mask = data["episode"].astype(str).to_numpy() == episode
            rows.append({"model_name": model_name, "metric": f"observed_episode_mean_{episode}", "value": float(observed[mask].mean())})
            rows.append({"model_name": model_name, "metric": f"ppc_episode_mean_{episode}", "value": float(draws[mask].mean(axis=0).mean())})
        for group in data["group"].cat.categories:
            mask = data["group"].astype(str).to_numpy() == group
            rows.append({"model_name": model_name, "metric": f"observed_group_mean_{group}", "value": float(observed[mask].mean())})
            rows.append({"model_name": model_name, "metric": f"ppc_group_mean_{group}", "value": float(draws[mask].mean(axis=0).mean())})
        observed_stim = data.groupby("stimulus_id", observed=True)["rating"].mean()
        ppc_stim = []
        for stimulus in observed_stim.index:
            mask = data["stimulus_id"].astype(str).to_numpy() == str(stimulus)
            ppc_stim.append(draws[mask].mean(axis=0).mean())
        rows.append({"model_name": model_name, "metric": "observed_stimulus_mean_sd", "value": float(observed_stim.std(ddof=1))})
        rows.append({"model_name": model_name, "metric": "ppc_stimulus_mean_sd", "value": float(np.std(ppc_stim, ddof=1))})
    return pd.DataFrame(rows), ppc_draws


def fit_bounded_beta_sensitivity(data: pd.DataFrame) -> tuple[pm.Model, az.InferenceData, dict[str, Any], pd.DataFrame]:
    model = build_beta_model(data)
    start = time.perf_counter()
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
        idata.extend(pm.sample_posterior_predictive(idata, var_names=["rating_01"], random_seed=SEED))
    runtime = time.perf_counter() - start
    summary = summarize_posterior(idata, ["Intercept", "episode", "group", "z_RMS", "z_CF", "z_SW", "1|participant_id_sigma", "1|stimulus_id_sigma", "phi"], "bounded_beta_primary_sensitivity")
    return model, idata, runtime_row("bounded_beta_primary_sensitivity", BOUNDED_FORMULA, runtime, "explicit_pymc_beta_nutpie"), summary


def build_beta_model(data: pd.DataFrame) -> pm.Model:
    participant_codes = data["participant_id"].cat.codes.to_numpy()
    stimulus_codes = data["stimulus_id"].cat.codes.to_numpy()
    episode_codes = data["episode"].cat.codes.to_numpy()
    group_codes = data["group"].cat.codes.to_numpy()
    y = data["rating_01"].to_numpy(dtype=float)
    coords = {
        "observation": np.arange(len(data)),
        "episode_dim": ["EDR-2", "FM-1"],
        "group_dim": ["group_02"],
        "participant_id__factor_dim": list(data["participant_id"].cat.categories.astype(str)),
        "stimulus_id__factor_dim": list(data["stimulus_id"].cat.categories.astype(str)),
    }
    with pm.Model(coords=coords) as model:
        intercept = pm.Normal("Intercept", mu=0, sigma=2)
        episode = pm.Normal("episode", mu=0, sigma=1, dims="episode_dim")
        group = pm.Normal("group", mu=0, sigma=1, dims="group_dim")
        z_rms = pm.Normal("z_RMS", mu=0, sigma=1)
        z_cf = pm.Normal("z_CF", mu=0, sigma=1)
        z_sw = pm.Normal("z_SW", mu=0, sigma=1)
        sigma_participant = pm.HalfNormal("1|participant_id_sigma", sigma=1)
        sigma_stimulus = pm.HalfNormal("1|stimulus_id_sigma", sigma=1)
        participant_z = pm.Normal("participant_z", mu=0, sigma=1, dims="participant_id__factor_dim")
        stimulus_z = pm.Normal("stimulus_z", mu=0, sigma=1, dims="stimulus_id__factor_dim")
        participant_effect = pm.Deterministic("1|participant_id", participant_z * sigma_participant, dims="participant_id__factor_dim")
        stimulus_effect = pm.Deterministic("1|stimulus_id", stimulus_z * sigma_stimulus, dims="stimulus_id__factor_dim")
        eta = (
            intercept
            + episode[0] * (episode_codes == 1)
            + episode[1] * (episode_codes == 2)
            + group[0] * (group_codes == 1)
            + z_rms * data["z_RMS"].to_numpy()
            + z_cf * data["z_CF"].to_numpy()
            + z_sw * data["z_SW"].to_numpy()
            + participant_effect[participant_codes]
            + stimulus_effect[stimulus_codes]
        )
        mu = pm.Deterministic("mu", pm.math.sigmoid(eta), dims="observation")
        phi = pm.Exponential("phi", 1)
        alpha = pm.Deterministic("alpha", mu * phi, dims="observation")
        beta = pm.Deterministic("beta", (1 - mu) * phi, dims="observation")
        pm.Beta("rating_01", alpha=alpha, beta=beta, observed=y, dims="observation")
    return model


def beta_ppc_summary(idata: az.InferenceData, data: pd.DataFrame) -> pd.DataFrame:
    draws = idata.posterior_predictive["rating_01"].stack(sample=("chain", "draw")).values
    if draws.shape[0] != len(data):
        draws = draws.T
    draws_100 = draws * 100
    observed = data["rating"].to_numpy()
    return pd.DataFrame(
        [
            {"model_name": "bounded_beta_primary_sensitivity", "metric": "observed_mean", "value": float(observed.mean())},
            {"model_name": "bounded_beta_primary_sensitivity", "metric": "observed_sd", "value": float(observed.std(ddof=1))},
            {"model_name": "bounded_beta_primary_sensitivity", "metric": "posterior_predictive_mean_mean", "value": float(draws_100.mean(axis=0).mean())},
            {"model_name": "bounded_beta_primary_sensitivity", "metric": "posterior_predictive_sd_mean", "value": float(draws_100.std(axis=0, ddof=1).mean())},
            {"model_name": "bounded_beta_primary_sensitivity", "metric": "posterior_predictive_below_0", "value": 0.0},
            {"model_name": "bounded_beta_primary_sensitivity", "metric": "posterior_predictive_above_100", "value": 0.0},
            {"model_name": "bounded_beta_primary_sensitivity", "metric": "posterior_predictive_outside_0_100", "value": 0.0},
            {"model_name": "bounded_beta_primary_sensitivity", "metric": "exact_zero_note", "value": float((data["rating"] == 0).sum())},
            {"model_name": "bounded_beta_primary_sensitivity", "metric": "exact_hundred_note", "value": float((data["rating"] == 100).sum())},
        ]
    )


def loo_table(idatas: dict[str, az.InferenceData]) -> pd.DataFrame:
    rows = []
    loo_results = {}
    for model_name, idata in idatas.items():
        try:
            result = az.loo(idata, pointwise=True)
            loo_results[model_name] = result
            pareto = result.pareto_k.values
            rows.append(
                {
                    "model_name": model_name,
                    "elpd_loo": float(result.elpd_loo),
                    "se": float(result.se),
                    "p_loo": float(result.p_loo),
                    "pareto_k_gt_0_7": int((pareto > 0.7).sum()),
                    "pareto_k_max": float(np.max(pareto)),
                    "loo_valid": bool((pareto <= 0.7).all()),
                }
            )
        except Exception as exc:  # noqa: BLE001
            rows.append({"model_name": model_name, "elpd_loo": np.nan, "se": np.nan, "p_loo": np.nan, "pareto_k_gt_0_7": np.nan, "pareto_k_max": np.nan, "loo_valid": False, "error": f"{type(exc).__name__}: {exc}"})
    table = pd.DataFrame(rows)
    if len(table.dropna(subset=["elpd_loo"])) >= 2:
        best = table["elpd_loo"].max()
        table["elpd_diff_from_best"] = table["elpd_loo"] - best
    return table


def draw_summary(level: str, values: np.ndarray) -> dict[str, Any]:
    hdi = az.hdi(values, hdi_prob=0.94)
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "sd": float(np.std(values, ddof=1)),
        "hdi_3": float(hdi[0]),
        "hdi_97": float(hdi[1]),
        "probability_above_zero": float(np.mean(values > 0)),
        "probability_below_zero": float(np.mean(values < 0)),
        "level": level,
    }


def posterior_expected_ratings(idata: az.InferenceData, data: pd.DataFrame, formula: str) -> pd.DataFrame:
    feature_names = SI_FEATURES if "z_SI" in formula else PRIMARY_FEATURES
    combos = data[["group", "episode", "song_id", "stimulus_id", "mix_id"] + feature_names].drop_duplicates().sort_values(["group", "episode", "song_id", "stimulus_id"])
    rows = []
    for _, row in combos.iterrows():
        values = expected_rating_draws(idata, row, feature_names)
        rows.append(
            {
                "model_name": "primary_feature",
                "group": row["group"],
                "episode": row["episode"],
                "song_id": row["song_id"],
                "stimulus_id": row["stimulus_id"],
                "mix_id": row["mix_id"],
                **{feature: row[feature] for feature in feature_names},
                **{key: value for key, value in draw_summary("expected_rating", values).items() if key != "level"},
            }
        )
    return pd.DataFrame(rows)


def expected_rating_draws(idata: az.InferenceData, row: pd.Series, feature_names: list[str]) -> np.ndarray:
    coeffs = coefficient_draws(idata, feature_names)
    values = coeffs["Intercept"].copy()
    episode = str(row["episode"])
    group = str(row["group"])
    if episode != "EDR-1":
        values = values + coeffs.get(f"episode[{episode}]", 0)
    if group == "group_02":
        values = values + coeffs.get("group[group_02]", 0)
    for feature in feature_names:
        values = values + coeffs[feature] * float(row[feature])
    values = values + stack_draws(idata.posterior["1|stimulus_id"].sel(stimulus_id__factor_dim=str(row["stimulus_id"])))
    return values


def winner_probabilities(expected: pd.DataFrame, idata: az.InferenceData, formula: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    feature_names = SI_FEATURES if "z_SI" in formula else PRIMARY_FEATURES
    rows = []
    validations = []
    for (song_id, episode), frame in expected.groupby(["song_id", "episode"], sort=True):
        matrices = [expected_rating_draws(idata, row, feature_names) for _, row in frame.iterrows()]
        matrix = np.vstack(matrices)
        max_per_draw = matrix.max(axis=0)
        is_winner = np.isclose(matrix, max_per_draw[None, :], rtol=0, atol=1e-12)
        tie_counts = is_winner.sum(axis=0)
        probabilities = (is_winner / tie_counts[None, :]).mean(axis=1)
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
        validations.append(
            {
                "song_id": song_id,
                "episode": episode,
                "candidate_count": len(frame),
                "probability_sum": float(probabilities.sum()),
                "probabilities_between_0_and_1": bool(((probabilities >= 0) & (probabilities <= 1)).all()),
                "n_final_winners": int(final_tie.sum() == 1),
                "draw_level_tie_probability": draw_tie_probability,
                "final_probability_tie_flag": bool(final_tie.sum() > 1),
                "validation_passed": len(frame) == 5 and np.isclose(probabilities.sum(), 1.0) and ((probabilities >= 0) & (probabilities <= 1)).all() and final_tie.sum() == 1,
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(validations)


def observed_vs_model_preferences(preferences: pd.DataFrame, winners: pd.DataFrame) -> pd.DataFrame:
    observed_rows = []
    for _, pref in preferences.iterrows():
        stimuli = str(pref.get("preferred_stimulus_id", "")).split("|")
        credit = 1 / len(stimuli) if stimuli and stimuli != [""] else np.nan
        for stimulus_id in stimuli:
            observed_rows.append({"song_id": pref["song_id"], "episode": pref["episode"], "stimulus_id": stimulus_id, "observed_credit": credit, "tie_flag": bool(pref["tie_flag"])})
    observed = pd.DataFrame(observed_rows)
    observed_summary = observed.groupby(["song_id", "episode", "stimulus_id"], dropna=False).agg(observed_credit=("observed_credit", "sum"), observed_winner_rows=("observed_credit", "count"), observed_tie_rows=("tie_flag", "sum")).reset_index()
    totals = preferences.groupby(["song_id", "episode"], dropna=False).size().reset_index(name="human_trials")
    observed_summary = observed_summary.merge(totals, on=["song_id", "episode"], how="left")
    observed_summary["observed_share_fractional_ties"] = observed_summary["observed_credit"] / observed_summary["human_trials"]
    model = winners[["song_id", "episode", "stimulus_id", "posterior_probability_highest", "is_final_predicted_winner"]].copy()
    merged = observed_summary.merge(model, on=["song_id", "episode", "stimulus_id"], how="outer").fillna({"observed_credit": 0, "observed_winner_rows": 0, "observed_tie_rows": 0, "observed_share_fractional_ties": 0})
    predicted = model[model["is_final_predicted_winner"]][["song_id", "episode", "stimulus_id"]].rename(columns={"stimulus_id": "model_winner_stimulus_id"})
    observed_top = observed_summary.sort_values(["song_id", "episode", "observed_share_fractional_ties"], ascending=[True, True, False]).groupby(["song_id", "episode"], as_index=False).first()[["song_id", "episode", "stimulus_id"]].rename(columns={"stimulus_id": "observed_top_stimulus_id"})
    agreement = predicted.merge(observed_top, on=["song_id", "episode"], how="outer")
    agreement["in_sample_descriptive_agreement"] = agreement["model_winner_stimulus_id"] == agreement["observed_top_stimulus_id"]
    merged = merged.merge(agreement, on=["song_id", "episode"], how="left")
    merged["comparison_scope"] = "in-sample descriptive agreement; not out-of-sample predictive accuracy"
    return merged.sort_values(["song_id", "episode", "posterior_probability_highest"], ascending=[True, True, False])


def stimulus_vs_feature_comparison(inputs: dict[str, pd.DataFrame], diagnostics: pd.DataFrame, icc: pd.DataFrame, ppc: pd.DataFrame, loo: pd.DataFrame, primary_fixed: pd.DataFrame) -> pd.DataFrame:
    stimulus_diag = inputs["stimulus_diag"].query("model_name == 'final_stimulus'").iloc[0]
    feature_diag = diagnostics.query("model_name == 'primary_feature'").iloc[0]
    stimulus_icc = inputs["stimulus_icc"]
    rows = [
        {"aspect": "formula", "stimulus_model": "rating ~ episode + group + (1 | participant_id) + (1 | stimulus_id)", "feature_model": PRIMARY_FORMULA},
        {"aspect": "icc_scope", "stimulus_model": "conditional / final-model ICC", "feature_model": "conditional / final-model ICC"},
        {"aspect": "runtime_seconds", "stimulus_model": float(stimulus_diag["runtime_seconds"]), "feature_model": float(feature_diag["runtime_seconds"])},
        {"aspect": "participant_ICC_mean", "stimulus_model": float(stimulus_icc.query("term == 'participant_ICC'")["mean"].iloc[0]), "feature_model": float(icc.query("model_name == 'primary_feature' and term == 'participant_ICC'")["mean"].iloc[0])},
        {"aspect": "stimulus_ICC_mean", "stimulus_model": float(stimulus_icc.query("term == 'stimulus_ICC'")["mean"].iloc[0]), "feature_model": float(icc.query("model_name == 'primary_feature' and term == 'stimulus_ICC'")["mean"].iloc[0])},
        {"aspect": "ppc_outside_0_100", "stimulus_model": float(inputs["stimulus_ppc"].query("metric == 'posterior_predictive_outside_0_100'")["value"].iloc[0]), "feature_model": float(ppc.query("model_name == 'primary_feature' and metric == 'posterior_predictive_outside_0_100'")["value"].iloc[0])},
        {"aspect": "episode_EDR_2_mean", "stimulus_model": float(inputs["stimulus_fixed"].query("term == 'episode[EDR-2]'")["mean"].iloc[0]), "feature_model": float(primary_fixed.query("term == 'episode[EDR-2]'")["mean"].iloc[0])},
        {"aspect": "episode_FM_1_mean", "stimulus_model": float(inputs["stimulus_fixed"].query("term == 'episode[FM-1]'")["mean"].iloc[0]), "feature_model": float(primary_fixed.query("term == 'episode[FM-1]'")["mean"].iloc[0])},
        {"aspect": "group_group_02_mean", "stimulus_model": float(inputs["stimulus_fixed"].query("term == 'group[group_02]'")["mean"].iloc[0]), "feature_model": float(primary_fixed.query("term == 'group[group_02]'")["mean"].iloc[0])},
        {"aspect": "interpretability", "stimulus_model": "direct stimulus-level baseline; does not explain acoustic drivers", "feature_model": "native rating-point acoustic associations for RMS/CF/SW"},
        {"aspect": "main_limitation", "stimulus_model": "additive; no Episode x Stimulus interaction", "feature_model": "features vary across only 20 stimuli; additive; no Episode x Feature interaction"},
    ]
    return pd.DataFrame(rows)


def make_figures(data: pd.DataFrame, idatas: dict[str, az.InferenceData], ppc: pd.DataFrame) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    for feature in SI_FEATURES:
        plt.figure(figsize=(6, 4))
        plt.scatter(data[feature], data["rating"], alpha=0.25, s=16)
        means = data.groupby("stimulus_id", observed=True).agg({feature: "first", "rating": "mean"})
        plt.scatter(means[feature], means["rating"], color="#d62728", s=35, label="Stimulus means")
        plt.xlabel(feature)
        plt.ylabel("Rating")
        plt.title(f"Real Ratings by {feature}")
        plt.legend()
        plt.tight_layout()
        plt.savefig(FIGURE_DIR / f"ratings_by_{feature}.png", dpi=150)
        plt.close()
    for name, idata in idatas.items():
        var_names = ["z_RMS", "z_CF", "z_SW", "1|participant_id_sigma", "1|stimulus_id_sigma", "sigma"]
        if name == "si_sensitivity":
            var_names.insert(3, "z_SI")
        az.plot_trace(idata, var_names=var_names, compact=True)
        plt.tight_layout()
        plt.savefig(FIGURE_DIR / f"{name}_trace_selected.png", dpi=150)
        plt.close("all")


def findings_text(outputs: dict[str, Any]) -> str:
    primary = outputs["primary_fixed"]
    si = outputs["si_fixed"]
    icc = outputs["icc"]
    diag = outputs["diagnostics"].query("model_name == 'primary_feature'").iloc[0]
    ppc = outputs["ppc"].query("model_name == 'primary_feature' and metric == 'posterior_predictive_outside_0_100'")["value"].iloc[0]
    beta_status = outputs["bounded_status"]

    def coeff(table: pd.DataFrame, term: str) -> pd.Series:
        return table.query("term == @term").iloc[0]

    rms = coeff(primary, "z_RMS")
    cf = coeff(primary, "z_CF")
    sw = coeff(primary, "z_SW")
    si_term = coeff(si, "z_SI")
    picc = icc.query("model_name == 'primary_feature' and term == 'participant_ICC'").iloc[0]
    sicc = icc.query("model_name == 'primary_feature' and term == 'stimulus_ICC'").iloc[0]
    lines = [
        "# Empirical Feature-Model Findings",
        "",
        f"The achieved analysable sample was N={cleaned_dataset_metadata()['analysable_n']}, with group_01={cleaned_dataset_metadata()['group_split'].get('group_01', 0)} and group_02={cleaned_dataset_metadata()['group_split'].get('group_02', 0)}. The planned preferred analysable sample was N=50.",
        f"RMS: posterior mean {rms['mean']:.2f} rating points per one-SD increase, 94% HDI [{rms['hdi_3']:.2f}, {rms['hdi_97']:.2f}].",
        f"Crest factor: posterior mean {cf['mean']:.2f} rating points per one-SD increase, 94% HDI [{cf['hdi_3']:.2f}, {cf['hdi_97']:.2f}].",
        f"Stereo width: posterior mean {sw['mean']:.2f} rating points per one-SD increase, 94% HDI [{sw['hdi_3']:.2f}, {sw['hdi_97']:.2f}].",
        f"SI sensitivity: posterior mean {si_term['mean']:.2f}, 94% HDI [{si_term['hdi_3']:.2f}, {si_term['hdi_97']:.2f}]. SI remains sensitivity-only.",
        "Acoustic coefficients are conditional associations in native rating points for the Gaussian models and should not be read causally.",
        f"Primary participant ICC mean {picc['mean']:.3f}, 94% HDI [{picc['hdi_3']:.3f}, {picc['hdi_97']:.3f}]. Primary stimulus ICC mean {sicc['mean']:.3f}, 94% HDI [{sicc['hdi_3']:.3f}, {sicc['hdi_97']:.3f}].",
        f"Primary model diagnostics: divergences={int(diag['divergences'])}, max R-hat={diag['max_rhat']:.3f}, min bulk ESS={diag['min_bulk_ess']:.1f}, min tail ESS={diag['min_tail_ess']:.1f}.",
        f"Gaussian PPC outside 0-100 was {ppc:.4f}; predictions were not clipped.",
        f"Bounded sensitivity status: {beta_status}.",
        "The primary model is additive. It contains no Episode x Feature interaction, so relative feature contributions do not change by context in this model.",
        "Group remains confounded with assigned song set, so the group coefficient should not be interpreted as a causal participant-group effect.",
        "Acoustic predictors vary across only 20 unique stimulus profiles, reducing precision and limiting claims about general acoustic preference laws.",
    ]
    return "\n".join(lines) + "\n"


def write_outputs(outputs: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for key, filename in [
        ("descriptive", "descriptive_feature_summary.csv"),
        ("primary_fixed", "primary_fixed_effect_posterior_summary.csv"),
        ("si_fixed", "si_sensitivity_posterior_summary.csv"),
        ("loo", "primary_vs_si_loo.csv"),
        ("icc", "icc_posterior_summary.csv"),
        ("diagnostics", "convergence_diagnostics.csv"),
        ("ppc", "posterior_predictive_summary.csv"),
        ("comparison", "stimulus_vs_feature_comparison.csv"),
        ("expected", "posterior_expected_ratings.csv"),
        ("winners", "predicted_highest_rated_mixes.csv"),
        ("winner_validation", "posterior_winner_validation.csv"),
        ("observed_vs_model", "observed_vs_model_preference_summary.csv"),
        ("runtimes", "runtime_execution_summary.csv"),
        ("validation", "model_dataset_validation.csv"),
        ("variance", "variance_components.csv"),
        ("bounded_summary", "bounded_sensitivity_posterior_summary.csv"),
        ("bounded_ppc", "bounded_sensitivity_ppc_summary.csv"),
        ("stimulus_feature_loo", "stimulus_vs_feature_loo.csv"),
    ]:
        outputs[key].to_csv(OUTPUT_DIR / filename, index=False)
    (OUTPUT_DIR / "empirical_feature_model_findings.md").write_text(outputs["findings"], encoding="utf-8")
    outputs["primary_idata"].to_netcdf(OUTPUT_DIR / "primary_real_feature_model_idata.nc")
    outputs["si_idata"].to_netcdf(OUTPUT_DIR / "si_sensitivity_real_feature_model_idata.nc")
    if outputs.get("bounded_idata") is not None:
        outputs["bounded_idata"].to_netcdf(OUTPUT_DIR / "bounded_beta_primary_sensitivity_idata.nc")
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "primary_formula": PRIMARY_FORMULA,
        "si_formula": SI_FORMULA,
        "bounded_sensitivity_formula": BOUNDED_FORMULA,
        "icc_outputs": {
            "primary_feature": "conditional / final-model ICC from the primary feature model posterior",
            "si_sensitivity": "conditional / final-model ICC from the SI sensitivity posterior",
            "unconditional_feature_icc": "not fitted or exported by this module",
        },
        "cleaned_dataset": cleaned_dataset_metadata(),
        "sampling": SAMPLING | {"seed": SEED},
        "bounded_sensitivity_status": outputs["bounded_status"],
        "planned_preferred_analysable_sample": 50,
        "achieved_analysable_sample": cleaned_dataset_metadata()["analysable_n"],
        "final_gate": "REAL FEATURE MODEL READY FOR DISSERTATION RESULTS SECTION" if outputs["diagnostics"]["divergences"].sum() == 0 else "REAL FEATURE MODEL REQUIRES DIAGNOSTIC REVIEW",
    }
    (OUTPUT_DIR / "real_feature_model_manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")


def run_real_feature_model() -> dict[str, Any]:
    inputs = load_inputs()
    data = prepare_model_data(inputs["ratings"])
    validation = validate_model_data(data, inputs["feature_table"])
    if not validation["passed"].all():
        raise ValueError("Feature model dataset validation failed.")
    descriptive = feature_descriptives(data)
    primary_model, primary_idata, primary_runtime = fit_bambi_model(PRIMARY_FORMULA, data, "primary_feature")
    si_model, si_idata, si_runtime = fit_bambi_model(SI_FORMULA, data, "si_sensitivity")
    idatas = {"primary_feature": primary_idata, "si_sensitivity": si_idata}
    formulas = {"primary_feature": PRIMARY_FORMULA, "si_sensitivity": SI_FORMULA}
    primary_fixed = summarize_posterior(primary_idata, ["Intercept", "episode", "group", "z_RMS", "z_CF", "z_SW"], "primary_feature")
    si_fixed = summarize_posterior(si_idata, ["Intercept", "episode", "group", "z_RMS", "z_CF", "z_SW", "z_SI"], "si_sensitivity")
    variance, icc = variance_and_icc(idatas)
    ppc, _ = posterior_predictive_summary(idatas, data, formulas)
    bounded_model, bounded_idata, bounded_runtime, bounded_summary = fit_bounded_beta_sensitivity(data)
    bounded_ppc = beta_ppc_summary(bounded_idata, data)
    bounded_status = "fitted transformed-Beta sensitivity model after Smithson-Verkuilen adjustment for exact 0/100 ratings; coefficients are on logit/proportion scale, not native rating points"
    runtimes = pd.DataFrame([primary_runtime, si_runtime, bounded_runtime])
    diagnostics = diagnostics_table(idatas | {"bounded_beta_primary_sensitivity": bounded_idata}, runtimes.to_dict("records"))
    loo = loo_table(idatas)
    stimulus_idata = add_gaussian_log_likelihood(
        az.from_netcdf(STIMULUS_OUTPUT_DIR / "final_real_stimulus_model_idata.nc"),
        data,
        "rating ~ episode + group + (1 | participant_id) + (1 | stimulus_id)",
    )
    stimulus_feature_loo = loo_table({"stimulus_model": stimulus_idata, "primary_feature": primary_idata})
    expected = posterior_expected_ratings(primary_idata, data, PRIMARY_FORMULA)
    winners, winner_validation = winner_probabilities(expected, primary_idata, PRIMARY_FORMULA)
    observed_vs_model = observed_vs_model_preferences(inputs["preferences"], winners)
    comparison = stimulus_vs_feature_comparison(inputs, diagnostics, icc, ppc, loo, primary_fixed)
    make_figures(data, idatas, ppc)
    outputs = {
        "validation": validation,
        "descriptive": descriptive,
        "primary_idata": primary_idata,
        "si_idata": si_idata,
        "bounded_idata": bounded_idata,
        "primary_fixed": primary_fixed,
        "si_fixed": si_fixed,
        "bounded_summary": bounded_summary,
        "variance": variance,
        "icc": icc,
        "ppc": pd.concat([ppc, bounded_ppc], ignore_index=True),
        "bounded_ppc": bounded_ppc,
        "diagnostics": diagnostics,
        "loo": loo,
        "stimulus_feature_loo": stimulus_feature_loo,
        "expected": expected,
        "winners": winners,
        "winner_validation": winner_validation,
        "observed_vs_model": observed_vs_model,
        "comparison": comparison,
        "runtimes": runtimes,
        "bounded_status": bounded_status,
    }
    outputs["findings"] = findings_text(outputs)
    write_outputs(outputs)
    return outputs
