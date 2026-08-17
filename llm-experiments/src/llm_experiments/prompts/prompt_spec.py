"""Phase 6D.1 model-agnostic prompt specification and synthetic rendering."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


PROMPT_SPEC_VERSION = "phase6d_prompt_spec_v1"
RESPONSE_SCHEMA_VERSION = "preference_prediction_response_v1"
MISSING_VALUE = "Not provided"
PROMPT_ACOUSTIC_DECIMALS = 2
CONDITIONS = ["non_history", "personalised_history"]
EXPECTED_LABELS = ["A", "B", "C", "D", "E"]

SYSTEM_INSTRUCTION = (
    "You are predicting individual listener preference in a music listening study. "
    "Infer this participant's likely 0-100 ratings and most preferred anonymous mix for the supplied target situation. "
    "Use only the supplied participant, context, acoustic-feature, and history information. "
    "Do not assume anything about underlying mixes beyond the supplied anonymous labels and feature values. "
    "Return only the specified JSON object, with no explanatory prose outside the JSON."
)

TASK_WORDING = (
    "Predict which anonymous mix A-E this specific participant is most likely to rate highest for the target listening situation."
)

RATING_INTERPRETATION = (
    "Predicted ratings are the participant's expected 0-100 suitability/preference ratings for the five mixes in this target listening situation. "
    "They are not probabilities, confidence percentages, or objective audio-quality scores."
)

ZSCORE_EXPLANATION = (
    "The acoustic values are z-scores standardized across the study stimulus set: 0 is approximately the study-stimulus average, "
    "positive values are above that average, and negative values are below that average. Positive or negative values are not inherently better."
)

FEATURE_DEFINITIONS = {
    "z_RMS": ("RMS level z-score", "Standardized measure of average signal energy/level."),
    "z_CF": ("Crest factor z-score", "Standardized measure of peak-to-average contrast/dynamic character."),
    "z_SW": ("Stereo width z-score", "Standardized measure of stereo spatial spread."),
}

PARTICIPANT_METADATA_LABELS = {
    "age_range": "Age range",
    "gender": "Gender",
    "cultural_influence_country": "Cultural influence country",
    "music_listening_habits": "Music listening habits",
    "music_production_or_audio_engineering_experience": "Music production/audio engineering experience",
    "hearing_difficulty": "Hearing difficulty",
}

OUTPUT_INSTRUCTIONS = """Return exactly one JSON object and no prose outside the JSON.

Use this exact top-level structure:

```json
{
  "predicted_preferred_mix": "C",
  "predicted_ratings": {
    "A": 62,
    "B": 48,
    "C": 81,
    "D": 70,
    "E": 55
  },
  "predicted_ranking": ["C", "D", "A", "E", "B"]
}
```

Rules:
- `predicted_preferred_mix` must be one of `A`, `B`, `C`, `D`, or `E`.
- `predicted_ratings` must contain exactly A-E as JSON numbers from 0 to 100. Decimals are allowed.
- `predicted_ranking` must contain exactly A-E once each, ordered from most preferred to least preferred.
- Ideally, `predicted_preferred_mix`, the highest predicted rating, and the first ranking entry should agree.
- Do not include a rationale, explanation, reasoning trace, confidence field, or any extra top-level field."""

FORMAT_REPAIR_INSTRUCTION = (
    "Your previous response did not match the required JSON format. Repair formatting only and return exactly one JSON object that conforms to "
    "the supplied schema. Do not add new participant information, do not include ground truth or correctness feedback, and do not hint which "
    "candidate should win."
)

FORBIDDEN_RENDERED_SUBSTRINGS = [
    "ground_truth",
    "observed_preferred",
    "observed_rank",
    "observed_max_rating",
    "is_single_winner",
    "n_preferred_tied",
    "stimulus_id",
    "actual_mix_id",
    "audio_path",
    "z_SI",
    ".wav",
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def render_condition_prompt(condition_object: dict[str, Any]) -> dict[str, Any]:
    condition = str(condition_object["condition"])
    model_input = condition_object["model_input"]
    sections = render_sections(model_input, condition)
    user_message = "\n\n".join(f"## {section['heading']}\n\n{section['body']}" for section in sections)
    return {
        "prompt_spec_version": PROMPT_SPEC_VERSION,
        "response_schema_version": RESPONSE_SCHEMA_VERSION,
        "condition_object_id": condition_object["condition_object_id"],
        "prediction_example_id": condition_object["prediction_example_id"],
        "condition": condition,
        "system_instruction": SYSTEM_INSTRUCTION,
        "user_message": user_message,
        "section_headings": [section["heading"] for section in sections],
        "history_trial_count": len(model_input.get("history", [])),
        "target_candidate_count": len(model_input["target"]["candidates"]),
        "size_audit": prompt_size(user_message),
    }


def render_sections(model_input: dict[str, Any], condition: str) -> list[dict[str, str]]:
    sections = [
        {"heading": "Task", "body": f"{TASK_WORDING}\n\n{RATING_INTERPRETATION}"},
        {"heading": "Target listening situation", "body": render_target_context(model_input["target"])},
        {"heading": "Participant information", "body": render_participant_metadata(model_input["participant_metadata"])},
        {"heading": "Acoustic feature guide", "body": render_feature_guide()},
        {"heading": "Target candidate mixes", "body": render_candidates(model_input["target"]["candidates"], include_rating=False)},
    ]
    if condition == "personalised_history":
        sections.append({"heading": "Previous listening evidence from this participant", "body": render_history(model_input.get("history", []))})
    sections.append({"heading": "Prediction/output instructions", "body": OUTPUT_INSTRUCTIONS})
    return sections


def render_target_context(target: dict[str, Any]) -> str:
    context = target["context"]
    return "\n".join(
        [
            f"Context: {render_value(context.get('context_text'))}",
            f"Study song: {render_song_label(target.get('song', {}))}",
        ]
    )


def render_participant_metadata(metadata: dict[str, Any]) -> str:
    return "\n".join(
        f"- {label}: {render_value(metadata.get(field))}"
        for field, label in PARTICIPANT_METADATA_LABELS.items()
    )


def render_feature_guide() -> str:
    lines = [ZSCORE_EXPLANATION]
    for _, (label, description) in FEATURE_DEFINITIONS.items():
        lines.append(f"- {label}: {description}")
    return "\n".join(lines)


def render_candidates(candidates: list[dict[str, Any]], include_rating: bool) -> str:
    blocks = []
    ordered = sorted(candidates, key=lambda row: EXPECTED_LABELS.index(str(row["label"])))
    for candidate in ordered:
        features = candidate["acoustic_features"]
        lines = [
            f"Candidate {candidate['label']}",
            f"- RMS z-score: {render_number(features.get('z_RMS'))}",
            f"- Crest factor z-score: {render_number(features.get('z_CF'))}",
            f"- Stereo width z-score: {render_number(features.get('z_SW'))}",
        ]
        if include_rating:
            lines.append(f"- Participant rating: {render_rating(candidate.get('human_rating'))}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def render_history(history: list[dict[str, Any]]) -> str:
    lines = ["The 0-100 values below are ratings previously given by this same participant. They are not confidence values."]
    for trial in sorted(history, key=lambda row: (row.get("trial_order") is None, row.get("trial_order") or 0)):
        lines.extend(
            [
                "",
                f"Previous trial {render_value(trial.get('trial_order'))}",
                f"Listening situation: {render_value(trial.get('context', {}).get('context_text'))}",
                f"Study song: {render_song_label(trial.get('song', {}))}",
                "",
                render_candidates(trial.get("candidates", []), include_rating=True),
                "",
                f"Participant comparative comment: {render_value(trial.get('comparative_comment'))}",
            ]
        )
    return "\n".join(lines)


def render_song_label(song: dict[str, Any]) -> str:
    return render_value(song.get("participant_song_label"))


def render_value(value: Any) -> str:
    if value is None or value == "":
        return MISSING_VALUE
    return str(value)


def render_number(value: Any) -> str:
    if value is None or value == "":
        return MISSING_VALUE
    rounded = round(float(value), PROMPT_ACOUSTIC_DECIMALS)
    if rounded == 0:
        rounded = 0.0
    return f"{rounded:.{PROMPT_ACOUSTIC_DECIMALS}f}"


def render_rating(value: Any) -> str:
    if value is None or value == "":
        return MISSING_VALUE
    return str(value)


def prompt_size(text: str) -> dict[str, int]:
    return {
        "characters": len(text),
        "approximate_word_count": len(re.findall(r"\b\S+\b", text)),
    }


def build_matched_synthetic_examples(prompt_data_jsonl: Path) -> dict[str, Any]:
    objects = load_jsonl(prompt_data_jsonl)
    by_example: dict[str, dict[str, dict[str, Any]]] = {}
    for obj in objects:
        by_example.setdefault(str(obj["prediction_example_id"]), {})[str(obj["condition"])] = obj
    for prediction_example_id in sorted(by_example):
        pair = by_example[prediction_example_id]
        if set(pair) >= {"non_history", "personalised_history"}:
            rendered = {
                "non_history": render_condition_prompt(pair["non_history"]),
                "personalised_history": render_condition_prompt(pair["personalised_history"]),
            }
            audit = audit_matched_pair(pair["non_history"], pair["personalised_history"], rendered)
            return {
                "schema_version": "phase6d1_synthetic_prompt_examples_v1",
                "prompt_spec_version": PROMPT_SPEC_VERSION,
                "response_schema_version": RESPONSE_SCHEMA_VERSION,
                "prediction_example_id": prediction_example_id,
                "examples": rendered,
                "audit": audit,
            }
    raise ValueError("No matched non_history/personalised_history prompt-data pair found.")


def audit_matched_pair(
    non_history: dict[str, Any],
    personalised_history: dict[str, Any],
    rendered: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    equivalence = validate_prompt_equivalence(non_history, personalised_history, rendered)
    leakage = validate_rendered_prompt_no_leakage(non_history, personalised_history, rendered)
    return {
        "non_history_size": rendered["non_history"]["size_audit"],
        "personalised_history_size": rendered["personalised_history"]["size_audit"],
        "non_history_history_trials": rendered["non_history"]["history_trial_count"],
        "personalised_history_history_trials": rendered["personalised_history"]["history_trial_count"],
        "target_candidate_count": rendered["non_history"]["target_candidate_count"],
        "equivalence_validation": equivalence,
        "leakage_validation": leakage,
    }


def validate_prompt_equivalence(
    non_history: dict[str, Any],
    personalised_history: dict[str, Any],
    rendered: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    checks = {
        "same_system_instruction": rendered["non_history"]["system_instruction"] == rendered["personalised_history"]["system_instruction"],
        "same_target": non_history["model_input"]["target"] == personalised_history["model_input"]["target"],
        "same_participant_metadata": non_history["model_input"]["participant_metadata"] == personalised_history["model_input"]["participant_metadata"],
        "same_feature_definitions": render_feature_guide() in rendered["non_history"]["user_message"]
        and render_feature_guide() in rendered["personalised_history"]["user_message"],
        "same_output_instructions": OUTPUT_INSTRUCTIONS in rendered["non_history"]["user_message"]
        and OUTPUT_INSTRUCTIONS in rendered["personalised_history"]["user_message"],
        "history_only_in_personalised_history": "Previous listening evidence from this participant"
        not in rendered["non_history"]["section_headings"]
        and "Previous listening evidence from this participant" in rendered["personalised_history"]["section_headings"],
    }
    return {"passed": all(checks.values()), "checks": checks}


def validate_rendered_prompt_no_leakage(
    non_history: dict[str, Any],
    personalised_history: dict[str, Any],
    rendered: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    failures: list[str] = []
    for condition, prompt in rendered.items():
        text = prompt["user_message"]
        for token in FORBIDDEN_RENDERED_SUBSTRINGS:
            if token in text:
                failures.append(f"{condition} contains forbidden token {token!r}.")
    target_song_title = non_history["model_input"]["target"].get("song", {}).get("song_title")
    target_song_id = non_history["model_input"]["target"].get("song", {}).get("song_id")
    target_excerpt_id = non_history["model_input"]["target"].get("song", {}).get("excerpt_id")
    for token in [target_song_title, target_song_id, target_excerpt_id]:
        if token and token in rendered["non_history"]["user_message"]:
            failures.append(f"non_history reveals non-rendered target song identifier {token!r}.")
        if token and token in rendered["personalised_history"]["user_message"]:
            failures.append(f"personalised_history reveals non-rendered target song identifier {token!r}.")
    if "Participant rating:" in rendered["non_history"]["user_message"]:
        failures.append("non_history contains participant history ratings.")
    target_comment = non_history["model_input"]["target"].get("comparative_comment")
    if target_comment:
        for condition, prompt in rendered.items():
            if target_comment in prompt["user_message"]:
                failures.append(f"{condition} contains target comparative comment.")
    return {"passed": not failures, "failures": failures}


def write_synthetic_prompt_examples(prompt_data_jsonl: Path, output_dir: Path) -> tuple[Path, Path, Path]:
    payload = build_matched_synthetic_examples(prompt_data_jsonl)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "phase6d1_matched_synthetic_prompt_examples.json"
    audit_path = output_dir / "phase6d1_prompt_audit.json"
    non_history_path = output_dir / "phase6d1_non_history_prompt_example.md"
    personalised_path = output_dir / "phase6d1_personalised_history_prompt_example.md"
    write_json(json_path, payload)
    write_json(audit_path, payload["audit"])
    non_history_path.write_text(render_example_markdown(payload["examples"]["non_history"]), encoding="utf-8")
    personalised_path.write_text(render_example_markdown(payload["examples"]["personalised_history"]), encoding="utf-8")
    return json_path, audit_path, non_history_path


def render_example_markdown(prompt: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Synthetic {prompt['condition']} Prompt Example",
            "",
            f"Prompt spec version: `{prompt['prompt_spec_version']}`",
            f"Response schema version: `{prompt['response_schema_version']}`",
            f"Prediction example ID: `{prompt['prediction_example_id']}`",
            "",
            "## System Instruction",
            "",
            prompt["system_instruction"],
            "",
            "## User Message",
            "",
            prompt["user_message"],
            "",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render Phase 6D.1 matched synthetic prompt examples.")
    parser.add_argument("--prompt-data", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    json_path, audit_path, non_history_path = write_synthetic_prompt_examples(args.prompt_data, args.output_dir)
    print(f"Wrote matched synthetic prompts to {json_path}")
    print(f"Wrote prompt audit to {audit_path}")
    print(f"Wrote non-history markdown example to {non_history_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
