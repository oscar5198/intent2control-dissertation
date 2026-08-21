"""Real participant data cleaning for the five-mix listening study.

The functions in this module keep the raw Netlify/Excel export immutable and
derive auditable, long-format analysis tables from the structured JSON payloads
submitted by the frontend.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_SOURCE = PROJECT_ROOT / "statistical-modeling/data/real/raw/listening_preference_responses_33_immutable.xlsx"
DOWNLOAD_SOURCE = Path(os.environ["REAL_DATA_DOWNLOAD_SOURCE"]) if os.environ.get("REAL_DATA_DOWNLOAD_SOURCE") else RAW_SOURCE
OUTPUT_DIR = PROJECT_ROOT / "statistical-modeling/data/real"
NOTEBOOK_PATH = PROJECT_ROOT / "statistical-modeling/notebooks/_06_real_data_cleaning.ipynb"
STIMULI_CONFIG = PROJECT_ROOT / "study-interface/frontend-5mix/config/stimuli.json"
STUDY_CONFIG = PROJECT_ROOT / "study-interface/frontend-5mix/config/study-config.json"
FEATURE_TABLE = PROJECT_ROOT / "statistical-modeling/outputs/acoustic-features/final_20_stimulus_feature_table.csv"

JSON_COLUMNS = [
    "consent_json",
    "listening_setup_json",
    "pre_study_json",
    "practice_json",
    "demographics_json",
    "post_task_json",
    "assigned_song_ids_json",
    "scenario_order_json",
    "episode_order_json",
    "song_order_json",
    "trial_order_json",
    "mix_mapping_json",
    "presentation_order_json",
    "trial_records_json",
    "responses_json",
    "derived_preferences_json",
    "timing_json",
    "device_browser_json",
    "client_validation_json",
    "final_payload_json",
]

PRIMARY_FEATURE_COLUMNS = [
    "rms_mean",
    "crest_factor_mean",
    "stereo_width",
    "stereo_imbalance",
    "z_RMS",
    "z_CF",
    "z_SW",
    "z_SI",
]

TECHNICAL_PLACEHOLDERS = {"test", "testing", "n/a", "na", "none", "null", ".", "-", "--"}


@dataclass(frozen=True)
class Design:
    expected_groups: list[str]
    expected_episodes: list[str]
    expected_mixes_per_trial: int
    expected_trials_per_participant: int
    expected_ratings_per_participant: int
    expected_comments_per_participant: int
    group_to_songs: dict[str, list[str]]
    stimulus_to_config: dict[str, dict[str, Any]]
    mix_to_config: dict[str, dict[str, Any]]
    config_summary: dict[str, Any]


def ensure_raw_copy() -> dict[str, Any]:
    """Copy the supplied workbook into the immutable raw-data location if needed."""
    RAW_SOURCE.parent.mkdir(parents=True, exist_ok=True)
    copied = False
    if not RAW_SOURCE.exists():
        if not DOWNLOAD_SOURCE.exists():
            raise FileNotFoundError(f"Raw workbook is missing: {DOWNLOAD_SOURCE}")
        shutil.copy2(DOWNLOAD_SOURCE, RAW_SOURCE)
        copied = True
    elif DOWNLOAD_SOURCE.exists() and file_sha256(DOWNLOAD_SOURCE) != file_sha256(RAW_SOURCE):
        raise ValueError(f"Immutable raw workbook already exists with a different SHA-256: {RAW_SOURCE}")
    return {
        "original_filename": DOWNLOAD_SOURCE.name,
        "stored_path": str(RAW_SOURCE.relative_to(PROJECT_ROOT)),
        "copied_this_run": copied,
        "sha256": file_sha256(RAW_SOURCE),
        "bytes": RAW_SOURCE.stat().st_size,
    }


CANONICAL_OUTPUT_NAMES = [
    "real_ratings_clean.csv",
    "real_participants_clean.csv",
    "real_trial_preferences.csv",
    "real_trial_ties_long.csv",
    "real_submission_audit.csv",
    "real_exclusion_log.csv",
    "real_data_validation.csv",
    "real_data_summary.csv",
    "real_schema_audit.csv",
    "real_participant_metadata_audit.csv",
    "real_downstream_stale_outputs.csv",
    "real_cleaning_manifest.json",
]


def archive_existing_canonical_outputs(new_raw_sha256: str) -> dict[str, Any]:
    """Move old canonical real-data outputs aside when the raw source changes."""
    manifest_path = OUTPUT_DIR / "real_cleaning_manifest.json"
    if not manifest_path.exists():
        return {"archived_this_run": False, "reason": "no_previous_manifest"}

    try:
        previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        previous_sha = previous_manifest.get("raw_provenance", {}).get("sha256", "")
        previous_rows = previous_manifest.get("raw_shape", {}).get("rows", "unknown")
    except Exception as exc:  # noqa: BLE001 - archive audit should preserve reason.
        previous_manifest = {}
        previous_sha = ""
        previous_rows = "unknown"
        parse_error = f"{type(exc).__name__}: {exc}"
    else:
        parse_error = ""

    if previous_sha == new_raw_sha256:
        return {
            "archived_this_run": False,
            "reason": "existing_canonical_outputs_already_match_current_raw_sha256",
            "previous_raw_sha256": previous_sha,
        }

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_dir = OUTPUT_DIR / f"superseded_{previous_rows}responses_{timestamp}"
    archive_dir.mkdir(parents=True, exist_ok=False)
    archived_files = []
    for name in CANONICAL_OUTPUT_NAMES:
        source = OUTPUT_DIR / name
        if source.exists():
            destination = archive_dir / name
            shutil.move(str(source), str(destination))
            archived_files.append(str(destination.relative_to(PROJECT_ROOT)))

    archive_manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "reason": "canonical real-data outputs superseded by a new immutable participant-response workbook",
        "previous_raw_sha256": previous_sha,
        "new_raw_sha256": new_raw_sha256,
        "previous_manifest_parse_error": parse_error,
        "archived_files": archived_files,
        "previous_manifest": previous_manifest,
    }
    (archive_dir / "supersession_manifest.json").write_text(
        json.dumps(archive_manifest, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return {
        "archived_this_run": True,
        "archive_dir": str(archive_dir.relative_to(PROJECT_ROOT)),
        "archived_files": archived_files,
        "previous_raw_sha256": previous_sha,
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_json_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, (dict, list)):
        return value
    text = str(value)
    if not text.strip():
        return None
    return json.loads(text)


def safe_parse_json(value: Any) -> tuple[Any, str]:
    try:
        return parse_json_value(value), ""
    except Exception as exc:  # noqa: BLE001 - audit needs the parse reason.
        return None, f"{type(exc).__name__}: {exc}"


def load_design() -> Design:
    stimuli_config = load_json(STIMULI_CONFIG)
    study_config = load_json(STUDY_CONFIG)
    group_to_songs: dict[str, list[str]] = {}
    stimulus_to_config: dict[str, dict[str, Any]] = {}
    mix_to_config: dict[str, dict[str, Any]] = {}

    excerpts_by_id = {excerpt["id"]: excerpt for excerpt in stimuli_config["excerpts"]}
    for group in stimuli_config["groups"]:
        songs: list[str] = []
        for excerpt_id in group["excerptIds"]:
            excerpt = excerpts_by_id[excerpt_id]
            song_id = excerpt["sourceSongId"]
            songs.append(song_id)
            for mix in excerpt["mixes"]:
                row = {
                    "group": group["id"],
                    "group_label": group.get("sourceAllocationLabel", ""),
                    "excerpt_id": excerpt_id,
                    "song_id": song_id,
                    "song_title": excerpt.get("finalExcerptName", ""),
                    "participant_song_label": excerpt.get("participantLabel", ""),
                    "mix_slot": mix.get("slot", ""),
                    "mix_id": mix.get("actualMixId", ""),
                    "stimulus_id": mix.get("stimulusId", ""),
                    "original_mix_name": mix.get("originalMixName", ""),
                    "frontend_audio_path": mix.get("audioPath", ""),
                }
                stimulus_to_config[row["stimulus_id"]] = row
                mix_to_config[row["mix_id"]] = row
        group_to_songs[group["id"]] = songs

    config_summary = {
        "stimulus_configuration_version": stimuli_config.get("stimulusConfigurationVersion"),
        "study_version_expected": "five_mix_frontend_v1_2026-08-06",
        "schema_version_expected": "five_mix_netlify_forms_v1",
        "group_count": study_config["groupCount"],
        "songs_total": len({row["song_id"] for row in stimulus_to_config.values()}),
        "stimuli_total": len(stimulus_to_config),
        "episodes": [scenario["id"] for scenario in stimuli_config["scenarios"]],
        "ratings_per_participant": study_config["ratingsPerParticipant"],
        "comments_per_participant": study_config["requiredCommentsPerParticipant"],
        "comment_unit": "one comparative comment per participant x song x episode trial, repeated on each of that trial's five rating rows",
    }
    return Design(
        expected_groups=[group["id"] for group in stimuli_config["groups"]],
        expected_episodes=[scenario["id"] for scenario in stimuli_config["scenarios"]],
        expected_mixes_per_trial=study_config["mixesPerTrial"],
        expected_trials_per_participant=study_config["trialsPerParticipant"],
        expected_ratings_per_participant=study_config["ratingsPerParticipant"],
        expected_comments_per_participant=study_config["requiredCommentsPerParticipant"],
        group_to_songs=group_to_songs,
        stimulus_to_config=stimulus_to_config,
        mix_to_config=mix_to_config,
        config_summary=config_summary,
    )


def load_raw_workbook() -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    workbook = pd.ExcelFile(RAW_SOURCE)
    sheet_audit = []
    main_df: pd.DataFrame | None = None
    for sheet in workbook.sheet_names:
        sheet_df = pd.read_excel(RAW_SOURCE, sheet_name=sheet)
        sheet_audit.append({"sheet_name": sheet, "row_count": len(sheet_df), "column_count": len(sheet_df.columns)})
        if main_df is None and len(sheet_df.columns) > 0:
            main_df = sheet_df
    if main_df is None:
        raise ValueError("No populated sheet found in raw workbook.")
    return main_df, sheet_audit


def build_schema_audit(raw_df: pd.DataFrame, sheet_audit: list[dict[str, Any]]) -> pd.DataFrame:
    duplicate_flags = pd.Index(raw_df.columns).duplicated(keep=False)
    rows = []
    for column, duplicate in zip(raw_df.columns, duplicate_flags):
        series = raw_df[column]
        non_missing = series.dropna()
        parse_errors = 0
        if column in JSON_COLUMNS:
            parse_errors = sum(1 for value in non_missing if safe_parse_json(value)[1])
        rows.append(
            {
                "column_name": column,
                "dtype": str(series.dtype),
                "missing_count": int(series.isna().sum()),
                "missing_fraction": float(series.isna().mean()),
                "non_missing_count": int(series.notna().sum()),
                "unique_non_missing": int(non_missing.astype(str).nunique()) if len(non_missing) else 0,
                "duplicate_column_name": bool(duplicate),
                "obviously_empty": bool(series.isna().all()),
                "column_role": classify_column(column),
                "json_parse_errors": parse_errors,
                "workbook_sheets": json.dumps(sheet_audit),
            }
        )
    return pd.DataFrame(rows)


def classify_column(column: str) -> str:
    lower = column.lower()
    if lower in {"study_id", "study_group", "group_id"}:
        return "participant_or_group_identifier"
    if lower in {"started_at", "completed_at", "created_at"} or "timestamp" in lower:
        return "timestamp"
    if lower in {"trial_count", "version_count", "rating_count", "comment_count"}:
        return "completion_count"
    if lower in {"ip", "user_agent", "referrer"}:
        return "backend_or_browser_metadata"
    if lower.endswith("_json"):
        if "response" in lower or "trial" in lower or "mapping" in lower or "order" in lower:
            return "trial_randomisation_or_response_json"
        if "demographics" in lower or "post_task" in lower or "setup" in lower or "consent" in lower or "pre_study" in lower:
            return "participant_metadata_json"
        return "structured_json"
    return "form_or_backend_metadata"


def make_participant_ids(raw_df: pd.DataFrame) -> dict[int, str]:
    ordering = raw_df.assign(_source_row=range(1, len(raw_df) + 1)).sort_values(
        by=["created_at", "completed_at", "study_id", "_source_row"],
        kind="mergesort",
    )
    return {int(row["_source_row"]): f"P{idx:03d}" for idx, (_, row) in enumerate(ordering.iterrows(), start=1)}


def participant_base(row: pd.Series, source_row: int, participant_id: str) -> dict[str, Any]:
    return {
        "source_row": source_row,
        "participant_id": participant_id,
        "source_study_id": row.get("study_id", ""),
        "study_version": row.get("study_version", ""),
        "schema_version": row.get("schema_version", ""),
        "stimulus_configuration_version": row.get("stimulus_configuration_version", ""),
        "submission_status": row.get("submission_status", ""),
        "group": row.get("group_id") or row.get("study_group", ""),
        "study_group": row.get("study_group", ""),
        "started_at": row.get("started_at", ""),
        "completed_at": row.get("completed_at", ""),
        "created_at": row.get("created_at", ""),
        "duration_seconds": row.get("duration_seconds", pd.NA),
        "trial_count_raw": row.get("trial_count", pd.NA),
        "version_count_raw": row.get("version_count", pd.NA),
        "rating_count_raw": row.get("rating_count", pd.NA),
        "comment_count_raw": row.get("comment_count", pd.NA),
        "consent_confirmed": row.get("consent_confirmed", pd.NA),
    }


def build_long_ratings(raw_df: pd.DataFrame, design: Design) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    participant_ids = make_participant_ids(raw_df)
    long_rows: list[dict[str, Any]] = []
    submission_rows: list[dict[str, Any]] = []
    parse_audit_rows: list[dict[str, Any]] = []

    for zero_index, raw_row in raw_df.reset_index(drop=True).iterrows():
        source_row = zero_index + 1
        participant_id = participant_ids[source_row]
        base = participant_base(raw_row, source_row, participant_id)
        parsed = {}
        parse_errors = {}
        for column in JSON_COLUMNS:
            value, error = safe_parse_json(raw_row.get(column, pd.NA))
            parsed[column] = value
            parse_errors[column] = error
            if error:
                parse_audit_rows.append(
                    {
                        "source_row": source_row,
                        "participant_id": participant_id,
                        "column_name": column,
                        "parse_error": error,
                    }
                )

        responses = parsed.get("responses_json")
        if not isinstance(responses, list):
            responses = []
        trial_order = parsed.get("trial_order_json") if isinstance(parsed.get("trial_order_json"), dict) else {}
        configured_trial_mappings = {
            int(trial.get("trial_index") or trial.get("trialIndex")): trial
            for trial in trial_order.get("trials", [])
            if isinstance(trial, dict) and (trial.get("trial_index") or trial.get("trialIndex"))
        }
        assigned_song_ids = parsed.get("assigned_song_ids_json") if isinstance(parsed.get("assigned_song_ids_json"), list) else []
        client_validation = parsed.get("client_validation_json") if isinstance(parsed.get("client_validation_json"), dict) else {}
        demographics = parsed.get("demographics_json") if isinstance(parsed.get("demographics_json"), dict) else {}
        post_task = parsed.get("post_task_json") if isinstance(parsed.get("post_task_json"), dict) else {}
        listening_setup = parsed.get("listening_setup_json") if isinstance(parsed.get("listening_setup_json"), dict) else {}
        pre_study = parsed.get("pre_study_json") if isinstance(parsed.get("pre_study_json"), dict) else {}

        submission_rows.append(
            {
                **base,
                "assigned_song_ids": "|".join(map(str, assigned_song_ids)),
                "json_parse_error_count": sum(1 for value in parse_errors.values() if value),
                "responses_json_count": len(responses),
                "client_expected_response_count": client_validation.get("expected_response_count"),
                "client_actual_response_count": client_validation.get("actual_response_count"),
                "client_validation_all_passed": all(value is True or not isinstance(value, bool) for value in client_validation.values()) if client_validation else False,
                "demographics_present": bool(demographics),
                "post_task_present": bool(post_task),
                "listening_setup_completed": listening_setup.get("completed"),
                "pre_study_passed": pre_study.get("passed"),
                "response_pattern_hash": stable_hash(responses),
                "ip_user_agent_hash": stable_hash({"ip": raw_row.get("ip", ""), "user_agent": raw_row.get("user_agent", "")}),
            }
        )

        for response_index, response in enumerate(responses, start=1):
            if not isinstance(response, dict):
                continue
            trial_index = as_int(response.get("trial_index"))
            label = normalise_label(response.get("display_label"))
            trial_mapping = configured_trial_mappings.get(trial_index, {})
            expected_for_label = find_version_mapping(trial_mapping, label)
            response_stimulus = str(response.get("stimulus_id", "") or "")
            response_mix = str(response.get("actual_mix_id", "") or "")
            expected_stimulus = str(expected_for_label.get("stimulus_id", "") or expected_for_label.get("stimulusId", "") or "")
            expected_mix = str(expected_for_label.get("actual_mix_id", "") or expected_for_label.get("actualMixId", "") or "")
            config_from_stimulus = design.stimulus_to_config.get(response_stimulus, {})
            rating = pd.to_numeric(response.get("rating"), errors="coerce")
            comment = str(response.get("comparative_comment", "") or response.get("comment", "") or "")
            long_rows.append(
                {
                    **base,
                    "response_index": response_index,
                    "trial_id": f"{participant_id}__trial_{trial_index:02d}" if trial_index is not None else f"{participant_id}__trial_unknown_{response_index:02d}",
                    "trial_index": trial_index,
                    "episode": response.get("episode_id") or response.get("scenario_id"),
                    "scenario_id": response.get("scenario_id") or response.get("episode_id"),
                    "episode_position": as_int(response.get("episode_position")),
                    "song_id": response.get("song_id"),
                    "excerpt_id": response.get("excerpt_id"),
                    "song_position": as_int(response.get("song_position")),
                    "participant_song_label": config_from_stimulus.get("participant_song_label", ""),
                    "presentation_label": label,
                    "presentation_order": as_int(response.get("display_position")),
                    "mix_id": response_mix,
                    "stimulus_id": response_stimulus,
                    "expected_mix_id_from_trial_order": expected_mix,
                    "expected_stimulus_id_from_trial_order": expected_stimulus,
                    "mapping_reconstructed": bool(response_stimulus and response_stimulus == expected_stimulus and response_mix == expected_mix),
                    "rating": rating,
                    "rating_set": response.get("rating_set"),
                    "audio_played": response.get("audio_played"),
                    "first_play_timestamp": response.get("first_play_timestamp", ""),
                    "comment": comment,
                    "comment_trimmed": comment.strip(),
                    "response_time_ms": response.get("response_time_ms"),
                    "audio_path": response.get("audio_path", ""),
                }
            )

    return pd.DataFrame(long_rows), pd.DataFrame(submission_rows), pd.DataFrame(parse_audit_rows)


def normalise_label(value: Any) -> str:
    text = str(value or "").strip()
    return re.sub(r"^Version\s+", "", text, flags=re.IGNORECASE)


def find_version_mapping(trial_mapping: dict[str, Any], label: str) -> dict[str, Any]:
    mappings = trial_mapping.get("version_mappings") or trial_mapping.get("versionMappings") or []
    for mapping in mappings:
        display_label = normalise_label(mapping.get("display_label") or mapping.get("neutralLabel"))
        if display_label == label:
            return mapping
    return {}


def as_int(value: Any) -> int | None:
    try:
        if pd.isna(value):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def stable_hash(payload: Any) -> str:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def attach_features(ratings: pd.DataFrame) -> pd.DataFrame:
    feature_table = pd.read_csv(FEATURE_TABLE)
    columns = [
        "stimulus_id",
        "mix_id",
        "rms_mean",
        "crest_factor_mean",
        "stereo_width",
        "stereo_imbalance",
        "z_RMS",
        "z_CF",
        "z_SW",
        "z_SI",
    ]
    merged = ratings.merge(
        feature_table[columns],
        on=["stimulus_id", "mix_id"],
        how="left",
        validate="many_to_one",
    )
    return merged


def build_trial_table(ratings: pd.DataFrame, design: Design) -> pd.DataFrame:
    if ratings.empty:
        return pd.DataFrame()
    grouped = ratings.groupby(["participant_id", "song_id", "episode"], dropna=False)
    rows = []
    for key, frame in grouped:
        participant_id, song_id, episode = key
        valid_rating = frame["rating"].notna() & frame["rating"].between(0, 100)
        candidate_frame = frame.loc[valid_rating].copy()
        max_rating = candidate_frame["rating"].max() if not candidate_frame.empty else pd.NA
        winners = candidate_frame[candidate_frame["rating"] == max_rating] if pd.notna(max_rating) else candidate_frame.iloc[0:0]
        rows.append(
            {
                "participant_id": participant_id,
                "group": frame["group"].iloc[0],
                "song_id": song_id,
                "episode": episode,
                "trial_id": frame["trial_id"].iloc[0],
                "trial_index": frame["trial_index"].iloc[0],
                "candidate_count": len(frame),
                "unique_candidate_count": frame["stimulus_id"].nunique(dropna=True),
                "rating_count": int(valid_rating.sum()),
                "comment_count": int(frame["comment_trimmed"].astype(bool).sum()),
                "distinct_comment_count": int(frame.loc[frame["comment_trimmed"].astype(bool), "comment_trimmed"].nunique()),
                "max_rating": max_rating,
                "n_tied_winners": len(winners),
                "tie_flag": len(winners) > 1,
                "preferred_mix_id": "|".join(winners["mix_id"].astype(str).tolist()),
                "preferred_stimulus_id": "|".join(winners["stimulus_id"].astype(str).tolist()),
                "preferred_presentation_label": "|".join(winners["presentation_label"].astype(str).tolist()),
                "expected_five_candidates": len(frame) == design.expected_mixes_per_trial and frame["stimulus_id"].nunique(dropna=True) == design.expected_mixes_per_trial,
                "comments_present": int(frame["comment_trimmed"].astype(bool).sum()) == len(frame),
            }
        )
    return pd.DataFrame(rows)


def build_tie_table(ratings: pd.DataFrame) -> pd.DataFrame:
    if ratings.empty:
        return pd.DataFrame(columns=["participant_id", "song_id", "episode", "trial_id", "mix_id", "stimulus_id", "rating"])
    rows = []
    for _, frame in ratings.groupby(["participant_id", "song_id", "episode"], dropna=False):
        valid = frame[frame["rating"].notna()]
        if valid.empty:
            continue
        max_rating = valid["rating"].max()
        winners = valid[valid["rating"] == max_rating]
        if len(winners) <= 1:
            continue
        rows.extend(
            winners[
                [
                    "participant_id",
                    "group",
                    "song_id",
                    "episode",
                    "trial_id",
                    "presentation_label",
                    "mix_id",
                    "stimulus_id",
                    "rating",
                ]
            ].to_dict("records")
        )
    return pd.DataFrame(rows)


def build_participants(
    submissions: pd.DataFrame,
    ratings: pd.DataFrame,
    trial_preferences: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    metadata_rows = []
    metadata_audit = []
    for _, submission in submissions.iterrows():
        raw_row = submission["source_row"]
        participant_id = submission["participant_id"]
        source = pd.read_excel(RAW_SOURCE).iloc[int(raw_row) - 1]
        demographics = safe_parse_json(source.get("demographics_json"))[0] or {}
        post_task = safe_parse_json(source.get("post_task_json"))[0] or {}
        listening_setup = safe_parse_json(source.get("listening_setup_json"))[0] or {}
        pre_study = safe_parse_json(source.get("pre_study_json"))[0] or {}
        participant_trials = trial_preferences[trial_preferences["participant_id"] == participant_id]
        participant_ratings = ratings[ratings["participant_id"] == participant_id]
        row = {
            "participant_id": participant_id,
            "source_study_id": submission["source_study_id"],
            "group": submission["group"],
            "started_at": submission["started_at"],
            "completed_at": submission["completed_at"],
            "created_at": submission["created_at"],
            "duration_seconds": submission["duration_seconds"],
            "age_range": clean_text(demographics.get("age_range")),
            "gender": clean_text(demographics.get("gender")),
            "cultural_influence_country": clean_text(demographics.get("cultural_influence_country")),
            "music_listening_habits": clean_text(demographics.get("music_listening_habits")),
            "music_production_or_audio_engineering_experience": clean_text(demographics.get("music_production_or_audio_engineering_experience")),
            "hearing_difficulty": clean_text(demographics.get("hearing_difficulty")),
            "scenario_immersion": post_task.get("scenario_immersion"),
            "task_difficulty": post_task.get("task_difficulty"),
            "prior_excerpt_familiarity": clean_text(post_task.get("prior_excerpt_familiarity")),
            "headphones_or_earphones_used": clean_text(post_task.get("headphones_or_earphones_used")),
            "completion_location_or_environment": clean_text(post_task.get("completion_location_or_environment")),
            "listening_setup_completed": listening_setup.get("completed"),
            "pre_study_passed": pre_study.get("passed"),
            "n_ratings": len(participant_ratings),
            "n_trials": len(participant_trials),
            "n_songs": participant_ratings["song_id"].nunique(dropna=True),
            "n_episodes": participant_ratings["episode"].nunique(dropna=True),
        }
        metadata_rows.append(row)

    participants = pd.DataFrame(metadata_rows)
    for column in [
        "age_range",
        "gender",
        "cultural_influence_country",
        "music_listening_habits",
        "music_production_or_audio_engineering_experience",
        "hearing_difficulty",
        "scenario_immersion",
        "task_difficulty",
        "prior_excerpt_familiarity",
        "headphones_or_earphones_used",
        "completion_location_or_environment",
    ]:
        if column not in participants:
            continue
        counts = participants[column].fillna("").astype(str).replace("", "<missing>").value_counts(dropna=False)
        for value, count in counts.items():
            metadata_audit.append(
                {
                    "metadata_variable": column,
                    "raw_representation": value,
                    "count": int(count),
                    "missing_count": int(participants[column].isna().sum() + (participants[column].astype(str).str.strip() == "").sum()),
                    "unique_values": int(participants[column].fillna("").astype(str).nunique()),
                    "proposed_analysis_representation": "preserve as collected; trimmed whitespace only",
                }
            )
    return participants, pd.DataFrame(metadata_audit)


def clean_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def build_validation_tables(
    raw_df: pd.DataFrame,
    ratings: pd.DataFrame,
    submissions: pd.DataFrame,
    trial_preferences: pd.DataFrame,
    design: Design,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    checks = []
    expected_songs = set(sum(design.group_to_songs.values(), []))
    all_featured = ratings[PRIMARY_FEATURE_COLUMNS].notna().all(axis=1) if not ratings.empty else pd.Series(dtype=bool)
    trial_candidate_ok = trial_preferences["expected_five_candidates"].all() if not trial_preferences.empty else False
    validations = {
        "raw_workbook_has_rows": len(raw_df) > 0,
        "one_wide_row_per_submission": "responses_json" in raw_df.columns and len(raw_df) == raw_df["study_id"].nunique(),
        "all_groups_valid": set(ratings["group"].dropna()).issubset(set(design.expected_groups)),
        "all_group_song_combinations_valid": all(
            row.song_id in design.group_to_songs.get(row.group, []) for row in ratings[["group", "song_id"]].drop_duplicates().itertuples()
        ),
        "all_episodes_valid": set(ratings["episode"].dropna()).issubset(set(design.expected_episodes)),
        "all_songs_expected": set(ratings["song_id"].dropna()).issubset(expected_songs),
        "all_stimuli_expected": set(ratings["stimulus_id"].dropna()).issubset(set(design.stimulus_to_config)),
        "all_randomisation_mappings_reconstructed": bool(ratings["mapping_reconstructed"].all()),
        "no_invalid_ratings": bool(ratings["rating"].notna().all() and ratings["rating"].between(0, 100).all()),
        "no_missing_comments_on_rating_rows": bool(ratings["comment_trimmed"].astype(bool).all()),
        "all_trials_have_five_unique_candidates": bool(trial_candidate_ok),
        "complete_participants_have_expected_trials": bool((trial_preferences.groupby("participant_id").size() == design.expected_trials_per_participant).all()),
        "complete_participants_have_expected_episodes": bool((ratings.groupby("participant_id")["episode"].nunique() == len(design.expected_episodes)).all()),
        "all_features_mapped": bool(all_featured.all()) if len(all_featured) else False,
        "no_accidental_duplicate_rating_rows": not ratings.duplicated(["participant_id", "episode", "song_id", "presentation_label"]).any(),
        "exclusion_log_accounts_for_every_submission": len(submissions) == len(raw_df),
    }
    for check, passed in validations.items():
        checks.append({"check": check, "passed": bool(passed), "details": ""})

    participant_audit_rows = []
    duplicate_study_ids = set(submissions.loc[submissions["source_study_id"].duplicated(keep=False), "source_study_id"])
    duplicate_patterns = set(submissions.loc[submissions["response_pattern_hash"].duplicated(keep=False), "response_pattern_hash"])
    for _, submission in submissions.iterrows():
        pid = submission["participant_id"]
        frame = ratings[ratings["participant_id"] == pid]
        trial_frame = trial_preferences[trial_preferences["participant_id"] == pid]
        missing_ratings = int(design.expected_ratings_per_participant - frame["rating"].notna().sum())
        invalid_ratings = int((frame["rating"].isna() | ~frame["rating"].between(0, 100)).sum())
        missing_comments = int((~frame["comment_trimmed"].astype(bool)).sum())
        duplicate_trial_rows = int(frame.duplicated(["episode", "song_id", "presentation_label"]).sum())
        unexpected_songs = sorted(set(frame["song_id"].dropna()) - set(design.group_to_songs.get(submission["group"], [])))
        unexpected_mixes = sorted(set(frame["stimulus_id"].dropna()) - set(design.stimulus_to_config))
        unexpected_contexts = sorted(set(frame["episode"].dropna()) - set(design.expected_episodes))
        duplicate_class = "no duplicate concern"
        duplicate_evidence = ""
        if submission["source_study_id"] in duplicate_study_ids:
            duplicate_class = "probable duplicate"
            duplicate_evidence = "source_study_id appears more than once"
        elif submission["response_pattern_hash"] in duplicate_patterns and len(duplicate_patterns) > 0:
            duplicate_class = "possible duplicate"
            duplicate_evidence = "exact duplicated response pattern hash"
        complete = (
            frame["song_id"].nunique(dropna=True) == 2
            and frame["episode"].nunique(dropna=True) == len(design.expected_episodes)
            and len(trial_frame) == design.expected_trials_per_participant
            and frame["rating"].notna().sum() == design.expected_ratings_per_participant
            and missing_comments == 0
            and invalid_ratings == 0
            and duplicate_trial_rows == 0
            and not unexpected_songs
            and not unexpected_mixes
            and not unexpected_contexts
        )
        exclusion_reasons = []
        if not complete:
            exclusion_reasons.append("incomplete_or_structurally_invalid_submission")
        if duplicate_class == "probable duplicate":
            exclusion_reasons.append("probable_duplicate")
        if invalid_ratings:
            exclusion_reasons.append("invalid_rating_values")
        participant_audit_rows.append(
            {
                "source_row": submission["source_row"],
                "participant_id": pid,
                "source_study_id": submission["source_study_id"],
                "group": submission["group"],
                "assigned_songs": submission["assigned_song_ids"],
                "n_episodes_completed": int(frame["episode"].nunique(dropna=True)),
                "n_song_episode_trials_completed": int(len(trial_frame)),
                "n_ratings": int(frame["rating"].notna().sum()),
                "n_comments": int(frame["comment_trimmed"].astype(bool).sum()),
                "missing_ratings": missing_ratings,
                "missing_comments": missing_comments,
                "malformed_ratings": invalid_ratings,
                "duplicated_trial_rating_combinations": duplicate_trial_rows,
                "unexpected_songs": "|".join(unexpected_songs),
                "unexpected_mixes": "|".join(unexpected_mixes),
                "unexpected_contexts": "|".join(unexpected_contexts),
                "duplicate_classification": duplicate_class,
                "duplicate_evidence": duplicate_evidence,
                "complete_submission": complete,
                "include_recommended": complete and duplicate_class != "probable duplicate",
                "exclusion_reason": "|".join(exclusion_reasons),
                "requires_manual_review": duplicate_class != "no duplicate concern",
                "recommended_action": "retain" if complete and duplicate_class == "no duplicate concern" else "review" if duplicate_class != "no duplicate concern" else "exclude",
            }
        )
    return pd.DataFrame(checks), pd.DataFrame(participant_audit_rows)


def write_outputs(outputs: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs["ratings"].to_csv(OUTPUT_DIR / "real_ratings_clean.csv", index=False)
    outputs["participants"].to_csv(OUTPUT_DIR / "real_participants_clean.csv", index=False)
    outputs["trial_preferences"].to_csv(OUTPUT_DIR / "real_trial_preferences.csv", index=False)
    outputs["ties"].to_csv(OUTPUT_DIR / "real_trial_ties_long.csv", index=False)
    outputs["submission_audit"].to_csv(OUTPUT_DIR / "real_submission_audit.csv", index=False)
    outputs["exclusion_log"].to_csv(OUTPUT_DIR / "real_exclusion_log.csv", index=False)
    outputs["validation"].to_csv(OUTPUT_DIR / "real_data_validation.csv", index=False)
    outputs["summary"].to_csv(OUTPUT_DIR / "real_data_summary.csv", index=False)
    outputs["schema_audit"].to_csv(OUTPUT_DIR / "real_schema_audit.csv", index=False)
    outputs["metadata_audit"].to_csv(OUTPUT_DIR / "real_participant_metadata_audit.csv", index=False)
    manifest_path = OUTPUT_DIR / "real_cleaning_manifest.json"
    manifest_path.write_text(json.dumps(outputs["manifest"], indent=2, default=str) + "\n", encoding="utf-8")
    outputs["downstream_stale"].to_csv(OUTPUT_DIR / "real_downstream_stale_outputs.csv", index=False)


def build_summary(
    raw_df: pd.DataFrame,
    ratings: pd.DataFrame,
    participants: pd.DataFrame,
    trial_preferences: pd.DataFrame,
    ties: pd.DataFrame,
    exclusion_log: pd.DataFrame,
    validation: pd.DataFrame,
    design: Design,
) -> pd.DataFrame:
    include = exclusion_log[exclusion_log["include_recommended"]]
    ready = bool(validation["passed"].all()) and int((~exclusion_log["include_recommended"]).sum()) == 0
    final_ratings = ratings[ratings["participant_id"].isin(include["participant_id"])]
    summary = {
        "raw_submissions": len(raw_df),
        "raw_columns": len(raw_df.columns),
        "unit_of_observation_raw": "one row per participant/submission with trial-level JSON payloads",
        "group_01_submissions": int((participants["group"] == "group_01").sum()),
        "group_02_submissions": int((participants["group"] == "group_02").sum()),
        "complete_participants": int(exclusion_log["complete_submission"].sum()),
        "incomplete_participants": int((~exclusion_log["complete_submission"]).sum()),
        "possible_duplicates": int((exclusion_log["duplicate_classification"] == "possible duplicate").sum()),
        "probable_duplicates": int((exclusion_log["duplicate_classification"] == "probable duplicate").sum()),
        "manual_review_cases": int(exclusion_log["requires_manual_review"].sum()),
        "recommended_exclusions": int((~exclusion_log["include_recommended"]).sum()),
        "final_recommended_analysable_n": int(include["participant_id"].nunique()),
        "final_group_01_n": int((include["group"] == "group_01").sum()),
        "final_group_02_n": int((include["group"] == "group_02").sum()),
        "expected_ratings_if_all_valid": int(len(raw_df) * design.expected_ratings_per_participant),
        "actual_rating_rows": int(len(ratings)),
        "final_analysable_rating_rows": int(len(final_ratings)),
        "missing_ratings": int(ratings["rating"].isna().sum()),
        "invalid_ratings": int((ratings["rating"].isna() | ~ratings["rating"].between(0, 100)).sum()),
        "rating_min": float(ratings["rating"].min()),
        "rating_max": float(ratings["rating"].max()),
        "expected_comments_if_all_valid": int(len(raw_df) * design.expected_comments_per_participant),
        "actual_trial_comments": int(trial_preferences[["participant_id", "song_id", "episode"]].drop_duplicates().shape[0]),
        "missing_blank_rating_row_comments": int((~ratings["comment_trimmed"].astype(bool)).sum()),
        "episodes_found": "|".join(sorted(ratings["episode"].dropna().unique())),
        "songs_found": "|".join(sorted(ratings["song_id"].dropna().unique())),
        "stimuli_found": int(ratings["stimulus_id"].nunique(dropna=True)),
        "all_randomisation_mappings_reconstructed": bool(ratings["mapping_reconstructed"].all()),
        "participant_song_episode_trials": int(len(trial_preferences)),
        "trials_with_rating_ties": int(trial_preferences["tie_flag"].sum()),
        "trial_tie_proportion": float(trial_preferences["tie_flag"].mean()) if len(trial_preferences) else 0.0,
        "all_stimuli_mapped_to_features": bool(ratings[PRIMARY_FEATURE_COLUMNS].notna().all(axis=1).all()),
        "z_features_from_frozen_phase3_table": True,
        "final_gate": "REAL DATA READY FOR STATISTICAL MODELLING" if ready else "REAL DATA REQUIRES MANUAL REVIEW BEFORE MODELLING",
    }
    return pd.DataFrame([summary])


def build_downstream_stale_outputs(raw_provenance: dict[str, Any]) -> pd.DataFrame:
    rows = []
    stale_targets = [
        {
            "phase": "Phase 3B final stimulus model",
            "notebook": "statistical-modeling/notebooks/_07_real_stimulus_model.ipynb",
            "output_path": "statistical-modeling/outputs/stimulus-model",
        },
        {
            "phase": "Phase 3B final acoustic feature model",
            "notebook": "statistical-modeling/notebooks/_08_real_feature_model.ipynb",
            "output_path": "statistical-modeling/outputs/feature-model",
        },
        {
            "phase": "Phase 3 held-out statistical evaluation",
            "notebook": "statistical-modeling/notebooks/_09_real_heldout_evaluation.ipynb",
            "output_path": "statistical-modeling/outputs/heldout-evaluation",
        },
    ]
    for target in stale_targets:
        path = PROJECT_ROOT / target["output_path"]
        rows.append(
            {
                **target,
                "status": "superseded_by_new_real_dataset_until_rerun",
                "new_raw_source": raw_provenance["stored_path"],
                "new_raw_sha256": raw_provenance["sha256"],
                "path_exists": path.exists(),
                "action_required": "rerun_notebook_against_current_canonical_real_data",
            }
        )
    return pd.DataFrame(rows)


def run_cleaning() -> dict[str, Any]:
    raw_provenance = ensure_raw_copy()
    archive_audit = archive_existing_canonical_outputs(raw_provenance["sha256"])
    design = load_design()
    raw_df, sheet_audit = load_raw_workbook()
    schema_audit = build_schema_audit(raw_df, sheet_audit)
    ratings, submissions, parse_audit = build_long_ratings(raw_df, design)
    ratings = attach_features(ratings)
    trial_preferences = build_trial_table(ratings, design)
    ties = build_tie_table(ratings)
    participants, metadata_audit = build_participants(submissions, ratings, trial_preferences)
    validation, exclusion_log = build_validation_tables(raw_df, ratings, submissions, trial_preferences, design)
    summary = build_summary(raw_df, ratings, participants, trial_preferences, ties, exclusion_log, validation, design)
    downstream_stale = build_downstream_stale_outputs(raw_provenance)
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "notebook_path": str(NOTEBOOK_PATH.relative_to(PROJECT_ROOT)),
        "raw_provenance": raw_provenance,
        "raw_shape": {"rows": len(raw_df), "columns": len(raw_df.columns)},
        "submission_count": int(len(raw_df)),
        "canonical_versioning": {
            "strategy": "canonical real_*.csv files updated for the current empirical dataset; previous canonical files moved into a clearly labelled superseded folder when their raw SHA-256 differs",
            "archive_audit": archive_audit,
        },
        "sheet_audit": sheet_audit,
        "design": design.config_summary,
        "configuration_inputs": {
            "stimuli_config": {"path": str(STIMULI_CONFIG.relative_to(PROJECT_ROOT)), "sha256": file_sha256(STIMULI_CONFIG)},
            "study_config": {"path": str(STUDY_CONFIG.relative_to(PROJECT_ROOT)), "sha256": file_sha256(STUDY_CONFIG)},
            "feature_table": {"path": str(FEATURE_TABLE.relative_to(PROJECT_ROOT)), "sha256": file_sha256(FEATURE_TABLE)},
        },
        "outputs": {
            "ratings": "statistical-modeling/data/real/real_ratings_clean.csv",
            "participants": "statistical-modeling/data/real/real_participants_clean.csv",
            "trial_preferences": "statistical-modeling/data/real/real_trial_preferences.csv",
            "ties": "statistical-modeling/data/real/real_trial_ties_long.csv",
            "submission_audit": "statistical-modeling/data/real/real_submission_audit.csv",
            "exclusion_log": "statistical-modeling/data/real/real_exclusion_log.csv",
            "validation": "statistical-modeling/data/real/real_data_validation.csv",
            "summary": "statistical-modeling/data/real/real_data_summary.csv",
            "schema_audit": "statistical-modeling/data/real/real_schema_audit.csv",
            "metadata_audit": "statistical-modeling/data/real/real_participant_metadata_audit.csv",
            "downstream_stale": "statistical-modeling/data/real/real_downstream_stale_outputs.csv",
            "manifest": "statistical-modeling/data/real/real_cleaning_manifest.json",
        },
        "privacy_note": "Raw IP/user-agent/referrer fields remain only in the immutable raw workbook. Clean analysis outputs use source_study_id and deterministic participant_id only.",
        "transformations": [
            "Copied immutable raw workbook into statistical-modeling/data/real/raw if absent.",
            "Parsed structured Netlify JSON payloads from the participant-level wide export.",
            "Created deterministic participant_id values P001... by created_at, completed_at, source_study_id, source row.",
            "Expanded responses_json to one rating row per participant x song x episode x presented mix.",
            "Reconstructed A-E presentation labels using the submitted trial_order_json and checked agreement with response stimulus/mix IDs.",
            "Repeated each trial's comparative comment on its five rating rows because the frontend collected one mandatory comparative comment per trial.",
            "Attached frozen Phase 3 RMS/CF/SW/SI acoustic features by stimulus_id and mix_id.",
            "Derived preferred mix per participant x song x episode without breaking rating ties.",
            "Generated participant, submission, exclusion, schema, validation, preference, and tie audit tables.",
        ],
    }
    outputs = {
        "raw": raw_df,
        "schema_audit": schema_audit,
        "ratings": ratings,
        "participants": participants,
        "trial_preferences": trial_preferences,
        "ties": ties,
        "submission_audit": submissions,
        "exclusion_log": exclusion_log,
        "validation": validation,
        "summary": summary,
        "metadata_audit": metadata_audit,
        "parse_audit": parse_audit,
        "manifest": manifest,
        "downstream_stale": downstream_stale,
    }
    write_outputs(outputs)
    return outputs
