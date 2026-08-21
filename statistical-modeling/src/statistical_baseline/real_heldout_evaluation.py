"""Held-out predictive evaluation for the final real statistical models."""

from __future__ import annotations

import hashlib
import json
import math
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from statistical_baseline.heldout import diagnostic_status, extract_arviz_diagnostics, posterior_winning_probabilities


REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_DATA_PATH = REPO_ROOT / "data/processed/ratings_final.csv"
REAL_TRIAL_PREFS_PATH = REPO_ROOT / "data/processed/trial_preferences_final.csv"
REAL_CLEANING_MANIFEST_PATH = REPO_ROOT / "statistical-modeling/data/real/real_cleaning_manifest.json"
PROTOCOL_SOURCE = REPO_ROOT / "llm-experiments/llm_evaluation_protocol.md"
OUTPUT_ROOT = REPO_ROOT / "statistical-modeling/outputs/heldout-evaluation"
OUTPUT_DIR = OUTPUT_ROOT / "mcmc-evaluation"
ENTRYPOINT_PATH = REPO_ROOT / "statistical-modeling/scripts/evaluate_heldout_predictions.py"
PHASE6_EXAMPLES_SOURCE = REPO_ROOT / "llm-experiments/src/llm_experiments/data/examples.py"
PHASE6_TARGETS_SOURCE = REPO_ROOT / "llm-experiments/src/llm_experiments/data/targets.py"
PHASE6_PROMPT_DATA_SOURCE = REPO_ROOT / "llm-experiments/src/llm_experiments/data/prompt_data.py"

INTERVAL_LEVEL = 0.94
BASE_SEED = 20260817
CHECKPOINT_COMPATIBILITY_VERSION = "real_heldout_mcmc_checkpoint_v2_strict_n33"
EXPECTED_N33_COUNTS = {
    "participants": 33,
    "rating_rows": 990,
    "target_trials": 198,
    "fold_model_pairs": 396,
    "target_candidate_rows": 5,
    "participant_history_rows": 25,
}
REQUIRED_N33_PARTICIPANTS = {"P031", "P032", "P033"}
MODEL_DEFINITIONS = [
    {
        "model_id": "categorical_design",
        "model_label": "Stimulus baseline",
        "role": "primary",
        "formula": "rating ~ episode + group + (1 | participant_id) + (1 | stimulus_id)",
        "seed_offset": 0,
    },
    {
        "model_id": "primary_acoustic",
        "model_label": "Primary acoustic feature baseline",
        "role": "primary",
        "formula": "rating ~ episode + group + z_RMS + z_CF + z_SW + (1 | participant_id) + (1 | stimulus_id)",
        "seed_offset": 10000,
    },
]
HELDOUT_IMPLEMENTATION_NOTE = {
    "full_data_inference": "Bambi/PyMC",
    "heldout_repeated_evaluation": "explicit PyMC",
    "equivalence": "The explicit PyMC held-out models implement the same additive fixed-effect and random-intercept structures as the full-data Bambi formulas.",
    "stimulus_formula": "rating ~ episode + group + (1 | participant_id) + (1 | stimulus_id)",
    "feature_formula": "rating ~ episode + group + z_RMS + z_CF + z_SW + (1 | participant_id) + (1 | stimulus_id)",
    "treatment_coding": "Reference levels are the first sorted levels present in the training/target union; for the canonical N=33 data this matches Bambi reference coding with EDR-1 and group_01 as references.",
    "random_effects": "Participant and stimulus effects are normal varying intercepts with shared HalfNormal scale parameters; no random slopes, interactions, song random effect, or group random effect are included.",
}
SAMPLER_SETTINGS = {
    "draws": 500,
    "tune": 500,
    "chains": 2,
    "cores": None,
    "target_accept": 0.95,
    "inference_method": "nutpie",
}
APPROXIMATION_SETTINGS = {
    "posterior_draws": 1000,
    "method": "empirical_bayes_gaussian_linear_posterior",
    "fixed_slope_prior_sd": 20.0,
    "intercept_prior_mean": 50.0,
    "intercept_prior_sd": 30.0,
    "participant_prior_sd": 15.0,
    "stimulus_prior_sd": 15.0,
}
DIAGNOSTIC_THRESHOLDS = {
    "fit_ok_max_divergences": 0,
    "fit_ok_max_rhat": 1.01,
    "fit_ok_min_bulk_ess": 100,
    "fit_ok_min_tail_ess": 100,
}


@dataclass(frozen=True)
class EvaluationPaths:
    output_dir: Path = OUTPUT_DIR

    @property
    def checkpoint_dir(self) -> Path:
        return self.output_dir / "checkpoints"

    @property
    def figures_dir(self) -> Path:
        return self.output_dir / "figures"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataframe_sha256(df: pd.DataFrame) -> str:
    payload = df.to_csv(index=False, lineterminator="\n")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def relpath(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def cleaning_manifest() -> dict[str, Any]:
    return json.loads(REAL_CLEANING_MANIFEST_PATH.read_text(encoding="utf-8"))


def cleaned_dataset_metadata(df: pd.DataFrame) -> dict[str, Any]:
    manifest = cleaning_manifest()
    participants = sorted(df["participant_id"].astype(str).unique().tolist())
    group_split = (
        df[["participant_id", "group"]]
        .drop_duplicates()
        .groupby("group", observed=True)
        .size()
        .astype(int)
        .to_dict()
    )
    feature_info = manifest.get("configuration_inputs", {}).get("feature_table", {})
    raw_info = manifest.get("raw_provenance", {})
    return {
        "cleaned_ratings_path": relpath(REAL_DATA_PATH),
        "cleaned_ratings_sha256": file_sha256(REAL_DATA_PATH),
        "cleaning_manifest_path": relpath(REAL_CLEANING_MANIFEST_PATH),
        "cleaning_manifest_sha256": file_sha256(REAL_CLEANING_MANIFEST_PATH),
        "cleaning_created_at_utc": manifest.get("created_at_utc"),
        "cleaning_dataset_version": raw_info.get("stored_path"),
        "raw_filename": raw_info.get("original_filename"),
        "raw_path": raw_info.get("stored_path"),
        "raw_sha256": raw_info.get("sha256"),
        "analysable_n": int(len(participants)),
        "participants": participants,
        "group_split": group_split,
        "rating_count": int(len(df)),
        "feature_table_path": feature_info.get("path"),
        "feature_table_sha256": feature_info.get("sha256"),
    }


def load_real_ratings(path: Path = REAL_DATA_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {
        "participant_id",
        "trial_id",
        "group",
        "episode",
        "song_id",
        "presentation_label",
        "presentation_order",
        "stimulus_id",
        "mix_id",
        "rating",
        "z_RMS",
        "z_CF",
        "z_SW",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Clean real ratings are missing required columns: {missing}")
    df = df.copy()
    for col in ["participant_id", "trial_id", "group", "episode", "song_id", "presentation_label", "stimulus_id", "mix_id"]:
        df[col] = df[col].astype(str)
    for col in ["rating", "z_RMS", "z_CF", "z_SW"]:
        df[col] = pd.to_numeric(df[col], errors="raise")
    return df.sort_values(["participant_id", "trial_id", "presentation_order"]).reset_index(drop=True)


def validate_real_dataset(df: pd.DataFrame) -> pd.DataFrame:
    trial_counts = df.groupby(["participant_id", "trial_id"], observed=True).size().rename("candidate_count").reset_index()
    failures: list[dict[str, Any]] = []
    if not (trial_counts["candidate_count"] == 5).all():
        failures.append({"check": "every_participant_trial_has_five_candidates", "passed": False})
    trial_per_participant = df[["participant_id", "trial_id"]].drop_duplicates().groupby("participant_id").size()
    if not (trial_per_participant == 6).all():
        failures.append({"check": "every_participant_has_six_trials", "passed": False})
    if df[["participant_id", "song_id", "episode"]].drop_duplicates().duplicated(["participant_id", "song_id", "episode"]).any():
        failures.append({"check": "participant_song_episode_unique_trial", "passed": False})
    if not failures:
        failures.append({"check": "real_dataset_structure", "passed": True})
    return pd.DataFrame(failures)


def build_split_manifest(df: pd.DataFrame) -> pd.DataFrame:
    trial_cols = ["participant_id", "group", "trial_id", "trial_index", "song_id", "episode"]
    manifest = (
        df[trial_cols]
        .drop_duplicates()
        .sort_values(["participant_id", "trial_id"])
        .reset_index(drop=True)
    )
    manifest.insert(0, "fold_id", np.arange(1, len(manifest) + 1))
    manifest["prediction_example_id"] = manifest["trial_id"].map(lambda value: f"real_loto__{value}")
    manifest["heldout_unit"] = "participant_id_x_trial_id"
    manifest["phase6_split_source"] = str(PROTOCOL_SOURCE.relative_to(REPO_ROOT)).replace("\\", "/")
    manifest["phase6_split_rule"] = "leave-one-trial-out participant-trial; all five candidate rows excluded together"
    manifest["candidate_count"] = manifest["trial_id"].map(df.groupby("trial_id").size())
    return manifest


def official_n33_target_validation(df: pd.DataFrame, split_manifest: pd.DataFrame) -> pd.DataFrame:
    participants = set(df["participant_id"].astype(str).unique())
    target_counts = split_manifest["trial_id"].map(df.groupby("trial_id").size())
    history_counts = []
    for _, split in split_manifest.iterrows():
        training, _ = target_training_split(df, str(split["trial_id"]))
        history_counts.append(int(training["participant_id"].eq(str(split["participant_id"])).sum()))
    rows = [
        {
            "check": "exactly_33_participants",
            "passed": int(df["participant_id"].nunique()) == EXPECTED_N33_COUNTS["participants"],
            "value": int(df["participant_id"].nunique()),
        },
        {
            "check": "exactly_990_rating_rows",
            "passed": len(df) == EXPECTED_N33_COUNTS["rating_rows"],
            "value": len(df),
        },
        {
            "check": "exactly_198_target_trials",
            "passed": len(split_manifest) == EXPECTED_N33_COUNTS["target_trials"],
            "value": len(split_manifest),
        },
        {
            "check": "exactly_396_target_model_units",
            "passed": len(split_manifest) * len(MODEL_DEFINITIONS) == EXPECTED_N33_COUNTS["fold_model_pairs"],
            "value": len(split_manifest) * len(MODEL_DEFINITIONS),
        },
        {
            "check": "new_participants_p031_p033_present",
            "passed": REQUIRED_N33_PARTICIPANTS.issubset(participants),
            "value": "|".join(sorted(REQUIRED_N33_PARTICIPANTS & participants)),
        },
        {
            "check": "each_target_has_five_heldout_rows",
            "passed": bool((target_counts == EXPECTED_N33_COUNTS["target_candidate_rows"]).all()),
            "value": str(target_counts.value_counts().to_dict()),
        },
        {
            "check": "each_target_participant_retains_25_history_rows",
            "passed": bool(all(count == EXPECTED_N33_COUNTS["participant_history_rows"] for count in history_counts)),
            "value": str(pd.Series(history_counts).value_counts().to_dict()),
        },
    ]
    return pd.DataFrame(rows)


def audit_phase6_split_source(df: pd.DataFrame, split_manifest: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    source_rows = [
        {
            "source_path": str(PROTOCOL_SOURCE.relative_to(REPO_ROOT)).replace("\\", "/"),
            "source_type": "protocol_document",
            "finding": "States leave-one-trial-out participant-trial evaluation with up to six target predictions per participant.",
            "sha256": file_sha256(PROTOCOL_SOURCE),
        },
        {
            "source_path": str(PHASE6_EXAMPLES_SOURCE.relative_to(REPO_ROOT)).replace("\\", "/"),
            "source_type": "implementation",
            "finding": "build_prediction_examples iterates over sorted trial_targets and emits an example for every target_eligible trial.",
            "sha256": file_sha256(PHASE6_EXAMPLES_SOURCE),
        },
        {
            "source_path": str(PHASE6_TARGETS_SOURCE.relative_to(REPO_ROOT)).replace("\\", "/"),
            "source_type": "implementation",
            "finding": "build_trial_ground_truth marks structurally valid five-candidate rated trials as target_eligible; no one-target-per-participant selector is present.",
            "sha256": file_sha256(PHASE6_TARGETS_SOURCE),
        },
        {
            "source_path": str(PHASE6_PROMPT_DATA_SOURCE.relative_to(REPO_ROOT)).replace("\\", "/"),
            "source_type": "implementation",
            "finding": "Prompt-data objects consume all trusted prediction examples and do not subsample target trials.",
            "sha256": file_sha256(PHASE6_PROMPT_DATA_SOURCE),
        },
    ]
    participant_counts = split_manifest.groupby("participant_id")["trial_id"].nunique()
    concrete_real_manifest_candidates = sorted(
        path
        for path in (REPO_ROOT / "llm-experiments").glob("outputs/**/*")
        if path.is_file()
        and "synthetic" not in {part.lower() for part in path.parts}
        and path.name in {"prediction_examples.jsonl", "prompt_data_objects.jsonl", "trial_ground_truth_targets.csv"}
    )
    audit = {
        "analysable_participant_count": int(df["participant_id"].nunique()),
        "expected_heldout_target_trials_according_to_phase6": int(len(split_manifest)),
        "source_paths_containing_frozen_split_logic": [row["source_path"] for row in source_rows],
        "concrete_real_phase6_manifest_found": bool(concrete_real_manifest_candidates),
        "concrete_real_phase6_manifest_paths": [str(path.relative_to(REPO_ROOT)).replace("\\", "/") for path in concrete_real_manifest_candidates],
        "every_real_participant_has_exactly_one_heldout_target": bool((participant_counts == 1).all()),
        "target_trials_per_participant_min": int(participant_counts.min()),
        "target_trials_per_participant_max": int(participant_counts.max()),
        "previous_180_trial_evaluation_differs_from_frozen_phase6": False,
        "previous_180_trial_evaluation_assessment": "Matches the frozen Phase 6 implementation because the authoritative builder emits every eligible participant-trial target; no concrete real one-target-per-participant manifest was found.",
        "exact_participant_target_trial_ids": split_manifest.groupby("participant_id")["trial_id"].apply(list).to_dict(),
    }
    return pd.DataFrame(source_rows), audit


def human_winner_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for trial_id, trial in df.groupby("trial_id", sort=True):
        max_rating = trial["rating"].max()
        winners = trial.loc[trial["rating"] == max_rating].sort_values("presentation_label")
        rows.append(
            {
                "trial_id": trial_id,
                "observed_max_rating": float(max_rating),
                "observed_winner_count": int(len(winners)),
                "observed_tie": bool(len(winners) > 1),
                "observed_winner_labels": "|".join(winners["presentation_label"].tolist()),
                "observed_winner_stimulus_ids": "|".join(winners["stimulus_id"].tolist()),
            }
        )
    return pd.DataFrame(rows)


def sampler_name(sampler_settings: dict[str, Any]) -> str:
    if sampler_settings.get("inference_method") == "nutpie":
        return "nutpie"
    return str(sampler_settings.get("nuts_sampler", sampler_settings.get("inference_method", "pymc")))


def run_metadata(df: pd.DataFrame, split_manifest: pd.DataFrame, fit_method: str, sampler_settings: dict[str, Any] | None = None) -> dict[str, Any]:
    sampler_settings = sampler_settings or SAMPLER_SETTINGS
    dataset = cleaned_dataset_metadata(df)
    target_manifest_sha256 = dataframe_sha256(split_manifest)
    return {
        "checkpoint_compatibility_version": CHECKPOINT_COMPATIBILITY_VERSION,
        "cleaned_ratings_sha256": dataset["cleaned_ratings_sha256"],
        "cleaning_manifest_sha256": dataset["cleaning_manifest_sha256"],
        "cleaning_dataset_version": dataset["cleaning_dataset_version"],
        "raw_sha256": dataset["raw_sha256"],
        "analysable_n": dataset["analysable_n"],
        "group_split": dataset["group_split"],
        "rating_count": dataset["rating_count"],
        "target_count": int(len(split_manifest)),
        "model_fit_count": int(len(split_manifest) * len(MODEL_DEFINITIONS)),
        "target_manifest_sha256": target_manifest_sha256,
        "target_manifest_version": "phase6_leave_one_trial_out_n33_v1",
        "model_definitions": MODEL_DEFINITIONS,
        "fit_method": fit_method,
        "inference_method": fit_method,
        "sampler": sampler_name(sampler_settings),
        "chains": int(sampler_settings["chains"]),
        "tune": int(sampler_settings["tune"]),
        "draws": int(sampler_settings["draws"]),
        "target_accept": float(sampler_settings["target_accept"]),
        "feature_table_sha256": dataset["feature_table_sha256"],
        "feature_table_path": dataset["feature_table_path"],
    }


def compatible_hash(fit_method: str, sampler_settings: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None) -> str:
    sampler_settings = sampler_settings or SAMPLER_SETTINGS
    payload = {
        "models": MODEL_DEFINITIONS,
        "sampler": sampler_settings,
        "approximation": APPROXIMATION_SETTINGS,
        "candidate_schema_version": "real_heldout_candidate_predictions_v2_ci_columns",
        "fit_method": fit_method,
        "interval": INTERVAL_LEVEL,
        "real_data_sha256": file_sha256(REAL_DATA_PATH),
        "cleaning_manifest_sha256": file_sha256(REAL_CLEANING_MANIFEST_PATH),
        "protocol_sha256": file_sha256(PROTOCOL_SOURCE),
        "checkpoint_compatibility_version": CHECKPOINT_COMPATIBILITY_VERSION,
        "strict_metadata": metadata,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def checkpoint_paths(paths: EvaluationPaths, prediction_example_id: str, model_id: str) -> tuple[Path, Path, Path]:
    digest = hashlib.sha1(f"{prediction_example_id}__{model_id}".encode("utf-8")).hexdigest()[:14]
    participant = prediction_example_id.split("__heldout__")[0].replace("real_loto__", "")
    trial = prediction_example_id.rsplit("__", 1)[-1]
    stem = f"{participant}_{trial}_{model_id}_{digest}"
    return (
        paths.checkpoint_dir / "cp" / f"{stem}.csv",
        paths.checkpoint_dir / "tp" / f"{stem}.csv",
        paths.checkpoint_dir / "fd" / f"{stem}.json",
    )


def checkpoint_metadata(run_meta: dict[str, Any], split_row: pd.Series, model_def: dict[str, Any], run_hash: str) -> dict[str, Any]:
    formula_sha256 = hashlib.sha256(model_def["formula"].encode("utf-8")).hexdigest()
    return {
        **run_meta,
        "compatible_hash": run_hash,
        "participant_id": str(split_row["participant_id"]),
        "target_trial_id": str(split_row["trial_id"]),
        "trial_id": str(split_row["trial_id"]),
        "prediction_example_id": str(split_row["prediction_example_id"]),
        "fold_id": int(split_row["fold_id"]),
        "model_name": model_def["model_id"],
        "baseline_model": model_def["model_id"],
        "model_formula": model_def["formula"],
        "model_formula_sha256": formula_sha256,
        "formula": model_def["formula"],
    }


def metadata_equal(actual: Any, expected: Any) -> bool:
    if isinstance(expected, float):
        try:
            return math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=1e-12)
        except (TypeError, ValueError):
            return False
    return actual == expected


def checkpoint_status(candidate_path: Path, trial_path: Path, diag_path: Path, expected_metadata: dict[str, Any]) -> tuple[bool, str]:
    if not (candidate_path.exists() and trial_path.exists() and diag_path.exists()):
        return False, "missing_checkpoint_files"
    try:
        diag = json.loads(diag_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False, "invalid_checkpoint_json"
    for key, expected_value in expected_metadata.items():
        if key not in diag:
            return False, f"missing_metadata:{key}"
        if not metadata_equal(diag.get(key), expected_value):
            return False, f"metadata_mismatch:{key}"
    if diag.get("fit_status") not in {"fit_ok", "convergence_warning"}:
        return False, "fit_status_not_completed"
    if len(pd.read_csv(candidate_path)) != EXPECTED_N33_COUNTS["target_candidate_rows"]:
        return False, "candidate_row_count_mismatch"
    if len(pd.read_csv(trial_path)) != 1:
        return False, "trial_row_count_mismatch"
    return True, "compatible"


def checkpoint_valid(candidate_path: Path, trial_path: Path, diag_path: Path, expected_metadata: dict[str, Any]) -> bool:
    return checkpoint_status(candidate_path, trial_path, diag_path, expected_metadata)[0]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def target_training_split(df: pd.DataFrame, trial_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    target = df.loc[df["trial_id"] == trial_id].copy()
    training = df.loc[df["trial_id"] != trial_id].copy()
    if len(target) != 5:
        raise ValueError(f"Held-out trial {trial_id} has {len(target)} rows; expected 5.")
    if training["trial_id"].eq(trial_id).any():
        raise ValueError(f"Held-out trial {trial_id} leaked into training data.")
    return training, target


def fit_pymc_expected_draws(training: pd.DataFrame, target: pd.DataFrame, model_def: dict[str, Any], settings: dict[str, Any]) -> tuple[Any, dict[str, list[float]]]:
    import pymc as pm

    # Treatment-coded fixed effects mirror the full-data Bambi formulas:
    # EDR-1 and group_01 are the canonical reference levels for the real data.
    participants = sorted(set(training["participant_id"]) | set(target["participant_id"]))
    stimuli = sorted(set(training["stimulus_id"]) | set(target["stimulus_id"]))
    episodes = sorted(set(training["episode"]) | set(target["episode"]))
    groups = sorted(set(training["group"]) | set(target["group"]))
    episode_contrasts = episodes[1:]
    group_contrasts = groups[1:]
    feature_cols = [feature for feature in ["z_RMS", "z_CF", "z_SW"] if feature in model_def["formula"]]

    participant_index = {value: idx for idx, value in enumerate(participants)}
    stimulus_index = {value: idx for idx, value in enumerate(stimuli)}
    episode_index = {value: idx for idx, value in enumerate(episode_contrasts)}
    group_index = {value: idx for idx, value in enumerate(group_contrasts)}

    y = training["rating"].to_numpy(dtype=float)
    participant_idx = training["participant_id"].map(participant_index).to_numpy(dtype=int)
    stimulus_idx = training["stimulus_id"].map(stimulus_index).to_numpy(dtype=int)
    episode_x = np.column_stack([(training["episode"] == level).astype(float).to_numpy() for level in episode_contrasts]) if episode_contrasts else np.zeros((len(training), 0))
    group_x = np.column_stack([(training["group"] == level).astype(float).to_numpy() for level in group_contrasts]) if group_contrasts else np.zeros((len(training), 0))
    feature_x = training[feature_cols].to_numpy(dtype=float) if feature_cols else np.zeros((len(training), 0))

    coords = {
        "participant": participants,
        "stimulus": stimuli,
        "episode_contrast": episode_contrasts,
        "group_contrast": group_contrasts,
        "feature": feature_cols,
        "obs_id": np.arange(len(training)),
    }
    with pm.Model(coords=coords) as model:
        intercept = pm.Normal("Intercept", mu=50, sigma=30)
        beta_episode = pm.Normal("beta_episode", mu=0, sigma=20, dims="episode_contrast") if episode_contrasts else 0
        beta_group = pm.Normal("beta_group", mu=0, sigma=20, dims="group_contrast") if group_contrasts else 0
        beta_feature = pm.Normal("beta_feature", mu=0, sigma=20, dims="feature") if feature_cols else 0
        sigma_participant = pm.HalfNormal("sigma_participant", sigma=30)
        sigma_stimulus = pm.HalfNormal("sigma_stimulus", sigma=30)
        z_participant = pm.Normal("z_participant", mu=0, sigma=1, dims="participant")
        z_stimulus = pm.Normal("z_stimulus", mu=0, sigma=1, dims="stimulus")
        participant_effect = pm.Deterministic("participant_effect", z_participant * sigma_participant, dims="participant")
        stimulus_effect = pm.Deterministic("stimulus_effect", z_stimulus * sigma_stimulus, dims="stimulus")
        sigma = pm.HalfNormal("sigma", sigma=30)
        mu = intercept + participant_effect[participant_idx] + stimulus_effect[stimulus_idx]
        if episode_contrasts:
            mu = mu + pm.math.dot(episode_x, beta_episode)
        if group_contrasts:
            mu = mu + pm.math.dot(group_x, beta_group)
        if feature_cols:
            mu = mu + pm.math.dot(feature_x, beta_feature)
        pm.Normal("rating", mu=mu, sigma=sigma, observed=y, dims="obs_id")
        sample_kwargs = {
            "draws": settings["draws"],
            "tune": settings["tune"],
            "chains": settings["chains"],
            "target_accept": settings["target_accept"],
            "random_seed": settings["random_seed"],
            "progressbar": False,
        }
        if settings.get("cores") is not None:
            sample_kwargs["cores"] = settings["cores"]
        if settings.get("inference_method") == "nutpie":
            sample_kwargs["nuts_sampler"] = "nutpie"
        idata = pm.sample(**sample_kwargs)

    posterior = idata.posterior
    base = posterior["Intercept"].values.reshape(-1)
    participant_effects = posterior["participant_effect"].values.reshape(-1, len(participants))
    stimulus_effects = posterior["stimulus_effect"].values.reshape(-1, len(stimuli))
    episode_betas = posterior["beta_episode"].values.reshape(-1, len(episode_contrasts)) if episode_contrasts else np.zeros((len(base), 0))
    group_betas = posterior["beta_group"].values.reshape(-1, len(group_contrasts)) if group_contrasts else np.zeros((len(base), 0))
    feature_betas = posterior["beta_feature"].values.reshape(-1, len(feature_cols)) if feature_cols else np.zeros((len(base), 0))

    draws_by_label: dict[str, list[float]] = {}
    for _, row in target.sort_values("presentation_label").iterrows():
        draws = base.copy()
        ep = str(row["episode"])
        grp = str(row["group"])
        if ep in episode_index:
            draws = draws + episode_betas[:, episode_index[ep]]
        if grp in group_index:
            draws = draws + group_betas[:, group_index[grp]]
        for feature_pos, feature in enumerate(feature_cols):
            draws = draws + feature_betas[:, feature_pos] * float(row[feature])
        draws = draws + participant_effects[:, participant_index[str(row["participant_id"])]]
        draws = draws + stimulus_effects[:, stimulus_index[str(row["stimulus_id"])]]
        draws_by_label[str(row["presentation_label"])] = draws.astype(float).tolist()
    return idata, draws_by_label


def fit_gaussian_approx_expected_draws(training: pd.DataFrame, target: pd.DataFrame, model_def: dict[str, Any], seed: int) -> tuple[dict[str, Any], dict[str, list[float]]]:
    participants = sorted(set(training["participant_id"]) | set(target["participant_id"]))
    stimuli = sorted(set(training["stimulus_id"]) | set(target["stimulus_id"]))
    episodes = sorted(set(training["episode"]) | set(target["episode"]))
    groups = sorted(set(training["group"]) | set(target["group"]))
    episode_contrasts = episodes[1:]
    group_contrasts = groups[1:]
    feature_cols = [feature for feature in ["z_RMS", "z_CF", "z_SW"] if feature in model_def["formula"]]
    terms = ["Intercept"]
    prior_means = [APPROXIMATION_SETTINGS["intercept_prior_mean"]]
    prior_sds = [APPROXIMATION_SETTINGS["intercept_prior_sd"]]
    for level in episode_contrasts:
        terms.append(f"episode[{level}]")
        prior_means.append(0.0)
        prior_sds.append(APPROXIMATION_SETTINGS["fixed_slope_prior_sd"])
    for level in group_contrasts:
        terms.append(f"group[{level}]")
        prior_means.append(0.0)
        prior_sds.append(APPROXIMATION_SETTINGS["fixed_slope_prior_sd"])
    for feature in feature_cols:
        terms.append(feature)
        prior_means.append(0.0)
        prior_sds.append(APPROXIMATION_SETTINGS["fixed_slope_prior_sd"])
    for participant in participants:
        terms.append(f"participant[{participant}]")
        prior_means.append(0.0)
        prior_sds.append(APPROXIMATION_SETTINGS["participant_prior_sd"])
    for stimulus in stimuli:
        terms.append(f"stimulus[{stimulus}]")
        prior_means.append(0.0)
        prior_sds.append(APPROXIMATION_SETTINGS["stimulus_prior_sd"])

    X = design_matrix(training, participants, stimuli, episode_contrasts, group_contrasts, feature_cols)
    y = training["rating"].to_numpy(dtype=float)
    prior_mean = np.array(prior_means, dtype=float)
    prior_sd = np.array(prior_sds, dtype=float)
    ridge_prec = np.diag(1.0 / (prior_sd**2))
    # Estimate residual scale with a ridge posterior mode, then condition on it for fast Gaussian draws.
    beta_mode = np.linalg.solve(X.T @ X + ridge_prec, X.T @ y + ridge_prec @ prior_mean)
    residual = y - X @ beta_mode
    sigma = float(max(np.sqrt(np.mean(residual**2)), 1e-6))
    posterior_prec = (X.T @ X) / (sigma**2) + ridge_prec
    posterior_cov = np.linalg.inv(posterior_prec)
    posterior_mean = posterior_cov @ ((X.T @ y) / (sigma**2) + ridge_prec @ prior_mean)
    rng = np.random.default_rng(seed)
    draws = rng.multivariate_normal(posterior_mean, posterior_cov, size=APPROXIMATION_SETTINGS["posterior_draws"], check_valid="ignore")
    target_X = design_matrix(target.sort_values("presentation_label"), participants, stimuli, episode_contrasts, group_contrasts, feature_cols)
    target_draws = target_X @ draws.T
    draws_by_label = {
        str(label): target_draws[position, :].astype(float).tolist()
        for position, label in enumerate(target.sort_values("presentation_label")["presentation_label"].tolist())
    }
    diag = {
        "terms": terms,
        "approximate_residual_sigma": sigma,
        "posterior_draw_count": APPROXIMATION_SETTINGS["posterior_draws"],
        "approximation_method": APPROXIMATION_SETTINGS["method"],
    }
    return diag, draws_by_label


def design_matrix(df: pd.DataFrame, participants: list[str], stimuli: list[str], episode_contrasts: list[str], group_contrasts: list[str], feature_cols: list[str]) -> np.ndarray:
    columns = [np.ones(len(df), dtype=float)]
    columns.extend((df["episode"].to_numpy(dtype=str) == level).astype(float) for level in episode_contrasts)
    columns.extend((df["group"].to_numpy(dtype=str) == level).astype(float) for level in group_contrasts)
    columns.extend(df[feature].to_numpy(dtype=float) for feature in feature_cols)
    columns.extend((df["participant_id"].to_numpy(dtype=str) == participant).astype(float) for participant in participants)
    columns.extend((df["stimulus_id"].to_numpy(dtype=str) == stimulus).astype(float) for stimulus in stimuli)
    return np.column_stack(columns)


def fit_one_fold(
    df: pd.DataFrame,
    split_row: pd.Series,
    model_def: dict[str, Any],
    paths: EvaluationPaths,
    run_hash: str,
    run_meta: dict[str, Any],
    fit_method: str,
    sampler_settings: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    candidate_path, trial_path, diag_path = checkpoint_paths(paths, split_row["prediction_example_id"], model_def["model_id"])
    expected_metadata = checkpoint_metadata(run_meta, split_row, model_def, run_hash)
    if checkpoint_valid(candidate_path, trial_path, diag_path, expected_metadata):
        return pd.read_csv(candidate_path), pd.read_csv(trial_path), json.loads(diag_path.read_text(encoding="utf-8"))

    training, target = target_training_split(df, str(split_row["trial_id"]))
    seed = BASE_SEED + int(split_row["fold_id"]) + int(model_def["seed_offset"])
    settings = {**(sampler_settings or SAMPLER_SETTINGS), "random_seed": seed}

    started = time.perf_counter()
    fit_status = "fit_ok"
    message = ""
    try:
        if fit_method == "mcmc":
            idata, draws_by_label = fit_pymc_expected_draws(training, target, model_def, settings)
            diagnostics = extract_arviz_diagnostics(idata)
            fit_status = diagnostic_status(
                diagnostics["divergences"],
                diagnostics["max_rhat"],
                diagnostics["min_bulk_ess"],
                diagnostics["min_tail_ess"],
                DIAGNOSTIC_THRESHOLDS,
            )
        elif fit_method == "laplace":
            approx_diag, draws_by_label = fit_gaussian_approx_expected_draws(training, target, model_def, seed)
            diagnostics = {
                "divergences": None,
                "max_rhat": None,
                "min_bulk_ess": None,
                "min_tail_ess": None,
                **approx_diag,
            }
            fit_status = "fit_ok"
            message = "Fast empirical-Bayes Gaussian posterior approximation; MCMC diagnostics not applicable."
        else:
            raise ValueError(f"Unknown fit_method: {fit_method}")
    except Exception as exc:
        runtime_seconds = time.perf_counter() - started
        diag = {
            "prediction_example_id": split_row["prediction_example_id"],
            "trial_id": split_row["trial_id"],
            "participant_id": split_row["participant_id"],
            "baseline_model": model_def["model_id"],
            "fit_status": "fit_failed",
            "message": repr(exc),
            "runtime_seconds": runtime_seconds,
            "random_seed": settings["random_seed"],
            "cores": settings.get("cores"),
            "sampler_settings": settings,
            **expected_metadata,
        }
        write_json(diag_path, diag)
        raise

    runtime_seconds = time.perf_counter() - started
    candidate_rows, trial_row = summarise_fold_predictions(split_row, model_def, target, draws_by_label, fit_method)
    diag = {
        "prediction_example_id": split_row["prediction_example_id"],
        "trial_id": split_row["trial_id"],
        "participant_id": split_row["participant_id"],
        "baseline_model": model_def["model_id"],
        "model_label": model_def["model_label"],
        "formula": model_def["formula"],
        "fit_status": fit_status,
        "message": message,
        "fit_method": fit_method,
        "runtime_seconds": runtime_seconds,
        "training_row_count": int(len(training)),
        "target_candidate_count": int(len(target)),
        "target_rows_excluded": int(len(target)),
        "target_trial_training_rows": int(training["trial_id"].eq(split_row["trial_id"]).sum()),
        "participant_other_trial_rows_retained": int(training["participant_id"].eq(split_row["participant_id"]).sum()),
        "same_stimulus_other_participant_rows_retained": int(training["stimulus_id"].isin(target["stimulus_id"]).sum()),
        "target_exclusion_validated": True,
        "random_seed": settings["random_seed"],
        "cores": settings.get("cores"),
        "sampler_settings": settings,
        **expected_metadata,
        **diagnostics,
    }

    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    trial_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(candidate_rows).to_csv(candidate_path, index=False)
    pd.DataFrame([trial_row]).to_csv(trial_path, index=False)
    write_json(diag_path, diag)
    return pd.DataFrame(candidate_rows), pd.DataFrame([trial_row]), diag


def fit_fold_task(task: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    return fit_one_fold(
        task["df"],
        task["split_row"],
        task["model_def"],
        task["paths"],
        task["run_hash"],
        task["run_meta"],
        task["fit_method"],
        task["sampler_settings"],
    )


def summarise_fold_predictions(split_row: pd.Series, model_def: dict[str, Any], target: pd.DataFrame, draws_by_label: dict[str, list[float]], fit_method: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    probs_by_label = posterior_winning_probabilities(draws_by_label)
    alpha = (1.0 - INTERVAL_LEVEL) / 2.0
    target = target.sort_values("presentation_label").copy()
    max_prob = max(probs_by_label.values())
    prob_winners = sorted([label for label, prob in probs_by_label.items() if np.isclose(prob, max_prob, atol=1e-12)])
    predicted_tie = len(prob_winners) > 1
    predicted_label = "" if predicted_tie else prob_winners[0]
    candidate_rows: list[dict[str, Any]] = []
    draw_array = np.column_stack([np.array(draws_by_label[label], dtype=float) for label in target["presentation_label"].tolist()])
    outside_draw_prop = float(((draw_array < 0) | (draw_array > 100)).mean())
    draw_tie_count = int((np.isclose(draw_array, draw_array.max(axis=1, keepdims=True), atol=1e-12).sum(axis=1) > 1).sum())
    for _, row in target.iterrows():
        label = str(row["presentation_label"])
        draws = np.array(draws_by_label[label], dtype=float)
        candidate_rows.append(
            {
                "prediction_example_id": split_row["prediction_example_id"],
                "fold_id": int(split_row["fold_id"]),
                "participant_id": split_row["participant_id"],
                "group": split_row["group"],
                "trial_id": split_row["trial_id"],
                "target_trial_id": split_row["trial_id"],
                "song_id": split_row["song_id"],
                "episode": split_row["episode"],
                "presentation_label": label,
                "stimulus_id": row["stimulus_id"],
                "mix_id": row["mix_id"],
                "baseline_model": model_def["model_id"],
                "model_label": model_def["model_label"],
                "formula": model_def["formula"],
                "observed_rating": float(row["rating"]),
                "posterior_mean_expected_rating": float(draws.mean()),
                "posterior_expected_sd": float(draws.std(ddof=1)),
                "posterior_expected_hdi_lower": hdi(draws, INTERVAL_LEVEL)[0],
                "posterior_expected_hdi_upper": hdi(draws, INTERVAL_LEVEL)[1],
                "posterior_probability_highest": float(probs_by_label[label]),
                "is_predicted_winner": bool((not predicted_tie) and label == predicted_label),
                "is_final_predicted_winner": bool((not predicted_tie) and label == predicted_label),
                "is_exact_predicted_tie": bool(label in prob_winners and predicted_tie),
                "fit_method": fit_method,
                "posterior_expected_draws_outside_0_100_prop": float(((draws < 0) | (draws > 100)).mean()),
            }
        )
    sorted_probs = sorted(probs_by_label.items(), key=lambda item: (-item[1], item[0]))
    observed_max = float(target["rating"].max())
    observed_winners = sorted(target.loc[target["rating"] == observed_max, "presentation_label"].astype(str).tolist())
    trial_row = {
        "prediction_example_id": split_row["prediction_example_id"],
        "fold_id": int(split_row["fold_id"]),
        "participant_id": split_row["participant_id"],
        "group": split_row["group"],
        "trial_id": split_row["trial_id"],
        "target_trial_id": split_row["trial_id"],
        "song_id": split_row["song_id"],
        "episode": split_row["episode"],
        "baseline_model": model_def["model_id"],
        "model_label": model_def["model_label"],
        "fit_method": fit_method,
        "predicted_winner_label": predicted_label,
        "predicted_tie": bool(predicted_tie),
        "predicted_tied_labels": "|".join(prob_winners) if predicted_tie else "",
        "predicted_winner_probability": float(sorted_probs[0][1]),
        "top2_margin": float(sorted_probs[0][1] - sorted_probs[1][1]),
        "winner_probability_entropy": entropy([prob for _, prob in sorted_probs]),
        "observed_winner_labels": "|".join(observed_winners),
        "observed_winner_count": int(len(observed_winners)),
        "observed_tie": bool(len(observed_winners) > 1),
        "observed_max_rating": observed_max,
        "observed_winner_probability_mass": float(sum(probs_by_label[label] for label in observed_winners)),
        "strict_unique_winner_correct": bool((len(observed_winners) == 1) and (not predicted_tie) and predicted_label == observed_winners[0]),
        "tie_compatible_correct": bool((not predicted_tie) and predicted_label in observed_winners),
        "top2_hit": bool(any(label in observed_winners for label, _ in sorted_probs[:2])),
        "spearman_rating": spearman(target["rating"].to_numpy(dtype=float), target["presentation_label"].map(lambda label: np.mean(draws_by_label[str(label)])).to_numpy(dtype=float)),
        "ndcg": ndcg(target["rating"].to_numpy(dtype=float), target["presentation_label"].map(lambda label: np.mean(draws_by_label[str(label)])).to_numpy(dtype=float)),
        "mae": float(np.abs(target["rating"].to_numpy(dtype=float) - np.array([np.mean(draws_by_label[str(label)]) for label in target["presentation_label"]])).mean()),
        "rmse": float(np.sqrt(((target["rating"].to_numpy(dtype=float) - np.array([np.mean(draws_by_label[str(label)]) for label in target["presentation_label"]])) ** 2).mean())),
        "posterior_expected_draws_outside_0_100_prop": outside_draw_prop,
        "posterior_draw_tie_count": draw_tie_count,
        "posterior_draw_tie_probability": float(draw_tie_count / draw_array.shape[0]),
        "winning_probability_sum": float(sum(probs_by_label.values())),
    }
    return candidate_rows, trial_row


def hdi(draws: np.ndarray, interval_level: float) -> tuple[float, float]:
    values = np.sort(np.asarray(draws, dtype=float))
    if len(values) == 0:
        return float("nan"), float("nan")
    interval_idx_inc = int(np.floor(interval_level * len(values)))
    if interval_idx_inc < 1 or interval_idx_inc >= len(values):
        return float(values[0]), float(values[-1])
    widths = values[interval_idx_inc:] - values[: len(values) - interval_idx_inc]
    min_idx = int(np.argmin(widths))
    return float(values[min_idx]), float(values[min_idx + interval_idx_inc])


def entropy(probs: list[float]) -> float:
    arr = np.array(probs, dtype=float)
    arr = arr[arr > 0]
    return float(-(arr * np.log(arr)).sum())


def spearman(observed: np.ndarray, predicted: np.ndarray) -> float:
    if len(np.unique(observed)) < 2 or len(np.unique(predicted)) < 2:
        return float("nan")
    return float(pd.Series(observed).corr(pd.Series(predicted), method="spearman"))


def ndcg(observed: np.ndarray, predicted: np.ndarray) -> float:
    order = np.argsort(-predicted)
    ideal = np.argsort(-observed)
    discounts = 1.0 / np.log2(np.arange(2, len(observed) + 2))
    dcg = float(np.sum(observed[order] * discounts))
    idcg = float(np.sum(observed[ideal] * discounts))
    return float("nan") if idcg == 0 else float(dcg / idcg)


def leakage_audit(df: pd.DataFrame, split_manifest: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, split in split_manifest.iterrows():
        training, target = target_training_split(df, split["trial_id"])
        rows.append(
            {
                "prediction_example_id": split["prediction_example_id"],
                "participant_id": split["participant_id"],
                "trial_id": split["trial_id"],
                "target_candidate_count": len(target),
                "training_row_count": len(training),
                "target_rows_in_training": int(training["trial_id"].eq(split["trial_id"]).sum()),
                "participant_history_rows_retained": int(training["participant_id"].eq(split["participant_id"]).sum()),
                "same_stimulus_other_participant_rows_retained": int(training["stimulus_id"].isin(target["stimulus_id"]).sum()),
                "leakage_passed": bool(len(target) == 5 and not training["trial_id"].eq(split["trial_id"]).any()),
            }
        )
    return pd.DataFrame(rows)


def aggregate_metric_rows(trials: pd.DataFrame, candidates: pd.DataFrame, by: list[str] | None = None) -> pd.DataFrame:
    group_cols = ["baseline_model"] + (by or [])
    rows = []
    for keys, trial_group in trials.groupby(group_cols, dropna=False, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        key_payload = dict(zip(group_cols, keys))
        candidate_group = candidates.merge(trial_group[["prediction_example_id", "baseline_model"]], on=["prediction_example_id", "baseline_model"])
        unique_trials = trial_group.loc[~trial_group["observed_tie"]]
        rows.append(
            {
                **key_payload,
                "n_trials": int(len(trial_group)),
                "n_unique_winner_trials": int(len(unique_trials)),
                "n_tied_human_trials": int(trial_group["observed_tie"].sum()),
                "strict_unique_winner_accuracy": mean_or_nan(unique_trials["strict_unique_winner_correct"]) if len(unique_trials) else float("nan"),
                "tie_compatible_accuracy": mean_or_nan(trial_group["tie_compatible_correct"]),
                "top2_hit_rate": mean_or_nan(trial_group["top2_hit"]),
                "mean_spearman": mean_or_nan(trial_group["spearman_rating"]),
                "mean_ndcg": mean_or_nan(trial_group["ndcg"]),
                "mae": float(np.abs(candidate_group["observed_rating"] - candidate_group["posterior_mean_expected_rating"]).mean()),
                "rmse": float(np.sqrt(((candidate_group["observed_rating"] - candidate_group["posterior_mean_expected_rating"]) ** 2).mean())),
                "mean_predicted_winner_probability": mean_or_nan(trial_group["predicted_winner_probability"]),
                "mean_observed_winner_probability_mass": mean_or_nan(trial_group["observed_winner_probability_mass"]),
                "mean_entropy": mean_or_nan(trial_group["winner_probability_entropy"]),
                "mean_top2_margin": mean_or_nan(trial_group["top2_margin"]),
                "mean_expected_draws_outside_0_100_prop": mean_or_nan(trial_group["posterior_expected_draws_outside_0_100_prop"]),
                "predicted_exact_tie_count": int(trial_group["predicted_tie"].sum()),
            }
        )
    return pd.DataFrame(rows)


def mean_or_nan(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.mean()) if values.notna().any() else float("nan")


def participant_metrics(trials: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    return aggregate_metric_rows(trials, candidates, by=["participant_id", "group"])


def model_comparison(metrics: pd.DataFrame) -> pd.DataFrame:
    wide = metrics.set_index("baseline_model")
    rows = []
    for metric in [
        "strict_unique_winner_accuracy",
        "tie_compatible_accuracy",
        "top2_hit_rate",
        "mean_spearman",
        "mean_ndcg",
        "mae",
        "rmse",
        "mean_predicted_winner_probability",
        "mean_observed_winner_probability_mass",
        "mean_entropy",
        "mean_top2_margin",
    ]:
        rows.append(
            {
                "metric": metric,
                "categorical_design": float(wide.loc["categorical_design", metric]),
                "primary_acoustic": float(wide.loc["primary_acoustic", metric]),
                "primary_acoustic_minus_categorical_design": float(wide.loc["primary_acoustic", metric] - wide.loc["categorical_design", metric]),
            }
        )
    return pd.DataFrame(rows)


def bootstrap_model_comparison(participant_level: pd.DataFrame, n_bootstrap: int = 2000, seed: int = BASE_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    participants = sorted(participant_level["participant_id"].unique())
    metrics = [
        "strict_unique_winner_accuracy",
        "tie_compatible_accuracy",
        "top2_hit_rate",
        "mean_spearman",
        "mean_ndcg",
        "mae",
        "rmse",
        "mean_observed_winner_probability_mass",
    ]
    draws: dict[str, list[float]] = {metric: [] for metric in metrics}
    for _ in range(n_bootstrap):
        sample = rng.choice(participants, size=len(participants), replace=True)
        sampled = pd.concat([participant_level.loc[participant_level["participant_id"] == pid] for pid in sample], ignore_index=True)
        means = sampled.groupby("baseline_model")[metrics].mean(numeric_only=True)
        if {"categorical_design", "primary_acoustic"}.issubset(means.index):
            diff = means.loc["primary_acoustic"] - means.loc["categorical_design"]
            for metric in metrics:
                draws[metric].append(float(diff[metric]))
    rows = []
    for metric, values in draws.items():
        arr = np.array(values, dtype=float)
        rows.append(
            {
                "metric": metric,
                "difference_direction": "primary_acoustic_minus_categorical_design",
                "bootstrap_replicates": int(len(arr)),
                "mean_difference": float(np.nanmean(arr)),
                "ci_lower": float(np.nanquantile(arr, 0.025)),
                "ci_upper": float(np.nanquantile(arr, 0.975)),
                "probability_difference_gt_0": float(np.nanmean(arr > 0)),
            }
        )
    return pd.DataFrame(rows)


def validate_outputs(split_manifest: pd.DataFrame, candidates: pd.DataFrame, trials: pd.DataFrame) -> pd.DataFrame:
    rows = []
    candidate_counts = candidates.groupby(["prediction_example_id", "baseline_model"]).size()
    rows.append({"check": "every_fold_model_has_five_candidates", "passed": bool((candidate_counts == 5).all()), "value": str(candidate_counts.value_counts().to_dict())})
    prob_between = candidates["posterior_probability_highest"].between(0, 1).all()
    rows.append({"check": "posterior_probabilities_between_0_and_1", "passed": bool(prob_between), "value": ""})
    prob_sums = candidates.groupby(["prediction_example_id", "baseline_model"])["posterior_probability_highest"].sum()
    rows.append({"check": "posterior_probabilities_sum_to_one", "passed": bool(np.allclose(prob_sums.to_numpy(), 1.0, atol=1e-8)), "value": f"min={prob_sums.min():.12f}; max={prob_sums.max():.12f}"})
    winner_counts = candidates.groupby(["prediction_example_id", "baseline_model"])["is_final_predicted_winner"].sum()
    exact_ties = trials["predicted_tie"].sum()
    rows.append({"check": "one_final_winner_unless_exact_tie", "passed": bool(((winner_counts == 1) | trials.set_index(["prediction_example_id", "baseline_model"])["predicted_tie"]).all()), "value": f"exact_predicted_ties={int(exact_ties)}"})
    complete_pairs = len(split_manifest) * len(MODEL_DEFINITIONS)
    rows.append({"check": "all_fold_model_pairs_completed", "passed": bool(len(candidate_counts) == complete_pairs), "value": f"{len(candidate_counts)}/{complete_pairs}"})
    return pd.DataFrame(rows)


def completion_status(split_manifest: pd.DataFrame, diagnostics: pd.DataFrame, fit_method: str, require_full_n33: bool = True) -> dict[str, Any]:
    expected_pairs = len(split_manifest) * len(MODEL_DEFINITIONS)
    participants = set(diagnostics.get("participant_id", pd.Series(dtype=str)).astype(str))
    pair_counts = diagnostics.groupby(["prediction_example_id", "baseline_model"], dropna=False).size() if len(diagnostics) else pd.Series(dtype=int)
    target_model_counts = diagnostics.groupby("prediction_example_id", dropna=False)["baseline_model"].nunique() if len(diagnostics) else pd.Series(dtype=int)
    completed_status = diagnostics.get("fit_status", pd.Series(dtype=str)).isin(["fit_ok", "convergence_warning"])
    method_ok = diagnostics.get("fit_method", pd.Series(dtype=str)).eq(fit_method)
    leakage_ok = diagnostics.get("target_exclusion_validated", pd.Series(dtype=bool)).eq(True)
    missing_new_participants = sorted(REQUIRED_N33_PARTICIPANTS - participants)
    full_n33_ok = bool(
        int(diagnostics.get("participant_id", pd.Series(dtype=str)).nunique()) == EXPECTED_N33_COUNTS["participants"]
        and not missing_new_participants
    )
    complete = bool(
        len(diagnostics) == expected_pairs
        and len(pair_counts) == expected_pairs
        and bool((pair_counts == 1).all())
        and int(diagnostics.get("trial_id", pd.Series(dtype=str)).nunique()) == len(split_manifest)
        and bool((target_model_counts == len(MODEL_DEFINITIONS)).all())
        and bool(completed_status.all())
        and bool(method_ok.all())
        and bool(leakage_ok.all())
        and (full_n33_ok if require_full_n33 else True)
    )
    return {
        "complete": complete,
        "expected_fold_model_pairs": int(expected_pairs),
        "compatible_completed_fold_model_pairs": int(len(diagnostics)),
        "target_count": int(diagnostics.get("trial_id", pd.Series(dtype=str)).nunique()),
        "participant_count": int(diagnostics.get("participant_id", pd.Series(dtype=str)).nunique()),
        "missing_required_new_participants": missing_new_participants,
        "require_full_n33": bool(require_full_n33),
        "both_models_for_every_target": bool((target_model_counts == len(MODEL_DEFINITIONS)).all()) if len(target_model_counts) else False,
        "all_fit_status_complete": bool(completed_status.all()) if len(completed_status) else False,
        "all_fit_method_matches": bool(method_ok.all()) if len(method_ok) else False,
        "all_leakage_checks_pass": bool(leakage_ok.all()) if len(leakage_ok) else False,
    }


def heldout_checkpoint_status(
    output_dir: Path = OUTPUT_DIR,
    fit_method: str = "mcmc",
    sampler_settings: dict[str, Any] | None = None,
    max_folds: int | None = None,
    fold_ids: list[int] | None = None,
) -> dict[str, Any]:
    sampler_settings = sampler_settings or SAMPLER_SETTINGS
    paths = EvaluationPaths(output_dir=Path(output_dir).resolve())
    df = load_real_ratings()
    dataset_validation = validate_real_dataset(df)
    split_manifest = build_split_manifest(df)
    official_validation = official_n33_target_validation(df, split_manifest)
    if fold_ids is not None:
        requested_folds = set(fold_ids)
        split_manifest = split_manifest.loc[split_manifest["fold_id"].isin(requested_folds)].copy()
    if max_folds is not None:
        split_manifest = split_manifest.head(max_folds).copy()
    run_meta = run_metadata(df, split_manifest, fit_method, sampler_settings)
    run_hash = compatible_hash(fit_method, sampler_settings, run_meta)
    compatible_rows: list[dict[str, Any]] = []
    incompatible_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    for _, split_row in split_manifest.iterrows():
        for model_def in MODEL_DEFINITIONS:
            candidate_path, trial_path, diag_path = checkpoint_paths(paths, split_row["prediction_example_id"], model_def["model_id"])
            expected_metadata = checkpoint_metadata(run_meta, split_row, model_def, run_hash)
            compatible, reason = checkpoint_status(candidate_path, trial_path, diag_path, expected_metadata)
            row = {
                "fold_id": int(split_row["fold_id"]),
                "participant_id": str(split_row["participant_id"]),
                "trial_id": str(split_row["trial_id"]),
                "prediction_example_id": str(split_row["prediction_example_id"]),
                "baseline_model": model_def["model_id"],
                "reason": reason,
            }
            if compatible:
                compatible_rows.append(row)
            elif reason == "missing_checkpoint_files":
                missing_rows.append(row)
            else:
                incompatible_rows.append(row)
    compatible_df = pd.DataFrame(compatible_rows)
    participants_represented = sorted(compatible_df["participant_id"].unique().tolist()) if len(compatible_df) else []
    required_outputs = [
        "heldout_split_manifest.csv",
        "frozen_target_manifest.csv",
        "candidate_predictions.csv",
        "trial_predictions.csv",
        "fold_diagnostics.csv",
        "leakage_audit.csv",
        "feature_model_metrics.csv",
        "stimulus_model_metrics.csv",
        "participant_level_metrics.csv",
        "bootstrap_model_comparison.csv",
        "runtime_summary.csv",
        "mcmc_vs_laplace_sensitivity.csv",
        "evaluation_manifest.json",
    ]
    return {
        "output_dir": relpath(paths.output_dir) if paths.output_dir.is_relative_to(REPO_ROOT) else str(paths.output_dir),
        "checkpoint_dir": relpath(paths.checkpoint_dir) if paths.checkpoint_dir.is_relative_to(REPO_ROOT) else str(paths.checkpoint_dir),
        "checkpoint_compatibility_version": CHECKPOINT_COMPATIBILITY_VERSION,
        "expected_folds": int(len(split_manifest)),
        "expected_fold_model_pairs": int(len(split_manifest) * len(MODEL_DEFINITIONS)),
        "compatible_completed_folds": int(len(compatible_rows)),
        "stale_or_incompatible_folds": int(len(incompatible_rows)),
        "missing_folds": int(len(missing_rows)),
        "participants_represented": participants_represented,
        "participant_count_represented": int(len(participants_represented)),
        "p031_p033_present": REQUIRED_N33_PARTICIPANTS.issubset(set(participants_represented)),
        "dataset_validation_passed": bool(dataset_validation["passed"].all()),
        "official_n33_validation_passed": bool(official_validation["passed"].all()),
        "official_n33_validation": official_validation.to_dict(orient="records"),
        "final_consolidation_complete": bool(all((paths.output_dir / name).exists() for name in required_outputs)),
        "required_outputs_missing": [name for name in required_outputs if not (paths.output_dir / name).exists()],
        "sample_incompatible_reasons": pd.Series([row["reason"] for row in incompatible_rows]).value_counts().head(10).to_dict() if incompatible_rows else {},
    }


def make_figures(metrics: pd.DataFrame, comparison: pd.DataFrame, diagnostics: pd.DataFrame, paths: EvaluationPaths) -> None:
    import matplotlib.pyplot as plt

    paths.figures_dir.mkdir(parents=True, exist_ok=True)
    metric_subset = metrics.set_index("baseline_model")[["strict_unique_winner_accuracy", "tie_compatible_accuracy", "top2_hit_rate", "mean_ndcg"]]
    ax = metric_subset.T.plot(kind="bar", figsize=(8, 4), rot=25)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Score")
    ax.set_title("Held-out preference metrics")
    plt.tight_layout()
    plt.savefig(paths.figures_dir / "heldout_preference_metrics.png", dpi=160)
    plt.close()

    error_subset = metrics.set_index("baseline_model")[["mae", "rmse"]]
    ax = error_subset.T.plot(kind="bar", figsize=(6, 4), rot=0)
    ax.set_ylabel("Rating points")
    ax.set_title("Held-out rating error")
    plt.tight_layout()
    plt.savefig(paths.figures_dir / "heldout_rating_error.png", dpi=160)
    plt.close()

    ax = diagnostics.boxplot(column="runtime_seconds", by="baseline_model", figsize=(7, 4))
    ax.set_title("Fold runtime")
    ax.set_xlabel("")
    ax.set_ylabel("Seconds")
    plt.suptitle("")
    plt.tight_layout()
    plt.savefig(paths.figures_dir / "fold_runtime_distribution.png", dpi=160)
    plt.close()


def run_real_heldout_evaluation(
    output_dir: Path = OUTPUT_DIR,
    resume: bool = True,
    max_folds: int | None = None,
    fit_method: str = "mcmc",
    sampler_settings: dict[str, Any] | None = None,
    parallel_folds: int = 1,
    fold_ids: list[int] | None = None,
) -> dict[str, Any]:
    sampler_settings = sampler_settings or SAMPLER_SETTINGS
    if parallel_folds < 1:
        raise ValueError("parallel_folds must be >= 1.")
    paths = EvaluationPaths(output_dir=Path(output_dir).resolve())
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    paths.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    df = load_real_ratings()
    dataset_validation = validate_real_dataset(df)
    if not dataset_validation["passed"].all():
        raise ValueError("Real cleaned data failed held-out structure validation.")

    split_manifest = build_split_manifest(df)
    official_validation = official_n33_target_validation(df, split_manifest)
    if not official_validation["passed"].all():
        raise ValueError("Official N=33 held-out target validation failed.")
    if fold_ids is not None:
        requested_folds = set(fold_ids)
        available_folds = set(split_manifest["fold_id"].astype(int))
        missing_folds = sorted(requested_folds - available_folds)
        if missing_folds:
            raise ValueError(f"Requested fold_id values are not available: {missing_folds}")
        split_manifest = split_manifest.loc[split_manifest["fold_id"].isin(requested_folds)].copy()
    if max_folds is not None:
        split_manifest = split_manifest.head(max_folds).copy()
    split_manifest.to_csv(paths.output_dir / "heldout_split_manifest.csv", index=False)
    split_manifest.to_csv(paths.output_dir / "frozen_target_manifest.csv", index=False)
    split_source_audit, split_audit = audit_phase6_split_source(df, split_manifest)
    split_source_audit.to_csv(paths.output_dir / "phase6_split_source_audit.csv", index=False)
    write_json(paths.output_dir / "phase6_frozen_split_audit.json", split_audit)
    leakage = leakage_audit(df, split_manifest)
    leakage.to_csv(paths.output_dir / "leakage_audit.csv", index=False)
    if not leakage["leakage_passed"].all():
        raise ValueError("Leakage audit failed before fitting.")

    run_meta = run_metadata(df, split_manifest, fit_method, sampler_settings)
    run_hash = compatible_hash(fit_method, sampler_settings, run_meta)
    all_candidates: list[pd.DataFrame] = []
    all_trials: list[pd.DataFrame] = []
    diagnostics: list[dict[str, Any]] = []
    total_started = time.perf_counter()
    pending_tasks: list[dict[str, Any]] = []
    for _, split_row in split_manifest.iterrows():
        for model_def in MODEL_DEFINITIONS:
            candidate_path, trial_path, diag_path = checkpoint_paths(paths, split_row["prediction_example_id"], model_def["model_id"])
            expected_metadata = checkpoint_metadata(run_meta, split_row, model_def, run_hash)
            if resume and checkpoint_valid(candidate_path, trial_path, diag_path, expected_metadata):
                cand, trial, diag = pd.read_csv(candidate_path), pd.read_csv(trial_path), json.loads(diag_path.read_text(encoding="utf-8"))
                all_candidates.append(cand)
                all_trials.append(trial)
                diagnostics.append(diag)
            else:
                pending_tasks.append(
                    {
                        "df": df,
                        "split_row": split_row,
                        "model_def": model_def,
                        "paths": paths,
                        "run_hash": run_hash,
                        "run_meta": run_meta,
                        "fit_method": fit_method,
                        "sampler_settings": sampler_settings,
                    }
                )

    if parallel_folds == 1:
        for task in pending_tasks:
            cand, trial, diag = fit_fold_task(task)
            all_candidates.append(cand)
            all_trials.append(trial)
            diagnostics.append(diag)
    else:
        with ProcessPoolExecutor(max_workers=parallel_folds) as executor:
            for cand, trial, diag in executor.map(fit_fold_task, pending_tasks):
                all_candidates.append(cand)
                all_trials.append(trial)
                diagnostics.append(diag)

    candidates = pd.concat(all_candidates, ignore_index=True)
    trials = pd.concat(all_trials, ignore_index=True)
    diagnostics_df = pd.DataFrame(diagnostics)
    completion = completion_status(split_manifest, diagnostics_df, fit_method, require_full_n33=fold_ids is None and max_folds is None)
    if not completion["complete"]:
        raise ValueError(f"Held-out evaluation did not produce a complete compatible run: {completion}")
    human_winners = human_winner_table(df)
    trials = trials.drop(columns=[col for col in human_winners.columns if col in trials.columns and col != "trial_id"], errors="ignore").merge(human_winners, on="trial_id", how="left", suffixes=("", "_from_preferences"))
    candidates.to_csv(paths.output_dir / "candidate_predictions.csv", index=False)
    trials.to_csv(paths.output_dir / "trial_predictions.csv", index=False)
    diagnostics_df.to_csv(paths.output_dir / "fold_diagnostics.csv", index=False)
    fit_method_audit = (
        diagnostics_df.groupby(["baseline_model", "fit_method", "fit_status"], dropna=False)
        .size()
        .reset_index(name="fold_count")
    )
    fit_method_audit.to_csv(paths.output_dir / "fit_method_audit.csv", index=False)

    validation = validate_outputs(split_manifest, candidates, trials)
    official_validation.to_csv(paths.output_dir / "official_n33_target_validation.csv", index=False)
    validation.to_csv(paths.output_dir / "output_validation.csv", index=False)
    metrics = aggregate_metric_rows(trials, candidates)
    metrics.loc[metrics["baseline_model"] == "categorical_design"].to_csv(paths.output_dir / "stimulus_model_metrics.csv", index=False)
    metrics.loc[metrics["baseline_model"] == "primary_acoustic"].to_csv(paths.output_dir / "feature_model_metrics.csv", index=False)
    comparison = model_comparison(metrics)
    comparison.to_csv(paths.output_dir / "model_comparison.csv", index=False)
    aggregate_metric_rows(trials, candidates, by=["episode"]).to_csv(paths.output_dir / "metrics_by_episode.csv", index=False)
    aggregate_metric_rows(trials, candidates, by=["song_id"]).to_csv(paths.output_dir / "metrics_by_song.csv", index=False)
    aggregate_metric_rows(trials, candidates, by=["group"]).to_csv(paths.output_dir / "metrics_by_group.csv", index=False)
    participant_level = participant_metrics(trials, candidates)
    participant_level.to_csv(paths.output_dir / "participant_level_metrics.csv", index=False)
    bootstrap = bootstrap_model_comparison(participant_level)
    bootstrap.to_csv(paths.output_dir / "bootstrap_model_comparison.csv", index=False)
    mcmc_completed = int((diagnostics_df.get("fit_method", pd.Series(dtype=str)) == "mcmc").sum())
    laplace_completed = int((diagnostics_df.get("fit_method", pd.Series(dtype=str)) == "laplace").sum())
    if fit_method == "mcmc":
        comparison_status = "official_mcmc_executed"
        comparison_reason = "Official held-out evaluation executed with MCMC; Laplace outputs are not part of this run."
    else:
        comparison_status = "legacy_laplace_sensitivity_only"
        comparison_reason = "Laplace approximation executed only as a legacy/sensitivity path and must not be mixed with official MCMC predictions."
    mcmc_laplace = pd.DataFrame(
        [
            {
                "comparison": "mcmc_vs_laplace_identical_fold_subset",
                "status": comparison_status,
                "reason": comparison_reason,
                "mcmc_completed_fold_model_pairs": mcmc_completed,
                "laplace_completed_fold_model_pairs": laplace_completed,
            }
        ]
    )
    mcmc_laplace.to_csv(paths.output_dir / "mcmc_vs_laplace_sensitivity.csv", index=False)

    runtime = pd.DataFrame(
        [
            {
                "model": "all",
                "fold_model_fits": int(len(diagnostics_df)),
                "total_runtime_seconds_this_run": float(time.perf_counter() - total_started),
                "sum_fit_runtime_seconds": float(pd.to_numeric(diagnostics_df["runtime_seconds"], errors="coerce").sum()),
            },
            *[
                {
                    "model": model_id,
                    "fold_model_fits": int(len(group)),
                    "total_runtime_seconds_this_run": float("nan"),
                    "sum_fit_runtime_seconds": float(pd.to_numeric(group["runtime_seconds"], errors="coerce").sum()),
                }
                for model_id, group in diagnostics_df.groupby("baseline_model")
            ],
        ]
    )
    runtime.to_csv(paths.output_dir / "runtime_summary.csv", index=False)
    make_figures(metrics, comparison, diagnostics_df, paths)
    manifest = {
        "schema_version": "real_heldout_evaluation_v1",
        "entrypoint": str(ENTRYPOINT_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "output_dir": str(paths.output_dir.relative_to(REPO_ROOT)).replace("\\", "/"),
        "phase6_split_source": str(PROTOCOL_SOURCE.relative_to(REPO_ROOT)).replace("\\", "/"),
        "phase6_split_source_sha256": file_sha256(PROTOCOL_SOURCE),
        "real_data_source": str(REAL_DATA_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "real_data_sha256": file_sha256(REAL_DATA_PATH),
        "cleaning_manifest_sha256": file_sha256(REAL_CLEANING_MANIFEST_PATH),
        "raw_sha256": cleaned_dataset_metadata(df)["raw_sha256"],
        "split_rule": "leave-one-trial-out participant-trial; all five candidate rows excluded together",
        "phase6_split_audit": split_audit,
        "checkpoint_compatibility_version": CHECKPOINT_COMPATIBILITY_VERSION,
        "target_manifest_sha256": run_meta["target_manifest_sha256"],
        "n_participants": int(df["participant_id"].nunique()),
        "n_trials": int(split_manifest["trial_id"].nunique()),
        "n_candidate_rows": int(len(df)),
        "model_fit_count": int(len(diagnostics_df)),
        "group_split": run_meta["group_split"],
        "n_tied_human_trials": int(human_winners["observed_tie"].sum()),
        "models": MODEL_DEFINITIONS,
        "implementation_note": HELDOUT_IMPLEMENTATION_NOTE,
        "sampler_settings": sampler_settings,
        "inference_method": fit_method,
        "sampler": run_meta["sampler"],
        "chains": run_meta["chains"],
        "tune": run_meta["tune"],
        "draws": run_meta["draws"],
        "target_accept": run_meta["target_accept"],
        "parallel_folds": parallel_folds,
        "requested_fold_ids": fold_ids,
        "executed_fit_method": fit_method,
        "approximation_settings": APPROXIMATION_SETTINGS if fit_method == "laplace" else None,
        "compatible_hash": run_hash,
        "completion_status": completion,
        "validation_passed": bool(validation["passed"].all()),
        "fit_status_counts": diagnostics_df["fit_status"].value_counts().to_dict(),
        "fit_method_counts": diagnostics_df["fit_method"].value_counts().to_dict() if "fit_method" in diagnostics_df else {},
        "mcmc_vs_laplace_sensitivity": mcmc_laplace.iloc[0].to_dict(),
        "draw_level_winner_tie_rule": "split posterior winning probability equally across candidates tied for maximum expected rating in a draw",
        "final_winner_rule": "largest posterior winning probability; exact equal maximum probabilities flagged as predicted_tie",
        "outputs": sorted(path.name for path in paths.output_dir.glob("*") if path.is_file()),
    }
    write_json(paths.output_dir / "evaluation_manifest.json", manifest)
    write_findings(paths.output_dir / "heldout_statistical_baseline_findings.md", metrics, comparison, bootstrap, validation, diagnostics_df, manifest)
    return {
        "manifest": manifest,
        "metrics": metrics,
        "comparison": comparison,
        "bootstrap": bootstrap,
        "validation": validation,
        "diagnostics": diagnostics_df,
        "runtime": runtime,
    }


def write_findings(path: Path, metrics: pd.DataFrame, comparison: pd.DataFrame, bootstrap: pd.DataFrame, validation: pd.DataFrame, diagnostics: pd.DataFrame, manifest: dict[str, Any]) -> None:
    lines = [
        "# Held-Out Statistical Baseline Findings",
        "",
        f"Phase 6 split source: `{manifest['phase6_split_source']}`.",
        f"Evaluation used {manifest['n_trials']} leave-one-trial-out participant-trial targets from {manifest['n_participants']} participants; {manifest['n_tied_human_trials']} targets had tied observed winners.",
        "",
        "## Overall metrics",
        markdown_table(metrics),
        "",
        "## Feature-minus-stimulus comparison",
        markdown_table(comparison),
        "",
        "## Participant bootstrap comparison",
        markdown_table(bootstrap),
        "",
        "## Validation",
        markdown_table(validation),
        "",
        "## Fold diagnostics",
        markdown_table(diagnostics["fit_status"].value_counts().rename_axis("fit_status").reset_index(name="count")),
        "",
        "Winner probabilities were derived draw by draw from posterior expected ratings, not from posterior predictive residual noise and not from posterior means alone.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    display = df.copy()
    for col in display.columns:
        if pd.api.types.is_float_dtype(display[col]):
            display[col] = display[col].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    headers = [str(col) for col in display.columns]
    rows = [[str(value) for value in row] for row in display.to_numpy()]
    return "\n".join(
        [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
            *["| " + " | ".join(row) + " |" for row in rows],
        ]
    )


if __name__ == "__main__":
    run_real_heldout_evaluation()
