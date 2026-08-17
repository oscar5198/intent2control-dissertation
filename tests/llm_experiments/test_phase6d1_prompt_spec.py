import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.prompts.prompt_spec import (  # noqa: E402
    CONDITIONS,
    EXPECTED_LABELS,
    FORMAT_REPAIR_INSTRUCTION,
    MISSING_VALUE,
    OUTPUT_INSTRUCTIONS,
    PROMPT_ACOUSTIC_DECIMALS,
    PROMPT_SPEC_VERSION,
    RESPONSE_SCHEMA_VERSION,
    SYSTEM_INSTRUCTION,
    TASK_WORDING,
    build_matched_synthetic_examples,
    load_jsonl,
    render_condition_prompt,
    render_number,
    validate_prompt_equivalence,
    validate_rendered_prompt_no_leakage,
)


PROMPT_DATA = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6b5" / "final_prompt_data_objects.jsonl"
RESPONSE_SCHEMA = REPO_ROOT / "llm-experiments" / "schema" / "preference_prediction_response_v1.json"
TEMPLATE = REPO_ROOT / "llm-experiments" / "prompts" / "phase6d_prompt_template_v1.json"
SPEC = REPO_ROOT / "llm-experiments" / "prompts" / "prompt_specification.md"
EXAMPLE_AUDIT = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6d1_prompt_spec" / "phase6d1_prompt_audit.json"
EXAMPLES_JSON = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6d1_prompt_spec" / "phase6d1_matched_synthetic_prompt_examples.json"


def test_prompt_spec_version_and_exact_system_instruction_are_frozen():
    assert PROMPT_SPEC_VERSION == "phase6d_prompt_spec_v1"
    assert SYSTEM_INSTRUCTION == (
        "You are predicting individual listener preference in a music listening study. "
        "Infer this participant's likely 0-100 ratings and most preferred anonymous mix for the supplied target situation. "
        "Use only the supplied participant, context, acoustic-feature, and history information. "
        "Do not assume anything about underlying mixes beyond the supplied anonymous labels and feature values. "
        "Return only the specified JSON object, with no explanatory prose outside the JSON."
    )
    assert TASK_WORDING == "Predict which anonymous mix A-E this specific participant is most likely to rate highest for the target listening situation."


def test_response_schema_is_strict_and_prediction_only():
    schema = json.loads(RESPONSE_SCHEMA.read_text(encoding="utf-8"))
    assert schema["$id"] == RESPONSE_SCHEMA_VERSION
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["predicted_preferred_mix", "predicted_ratings", "predicted_ranking"]
    assert schema["properties"]["predicted_preferred_mix"]["enum"] == EXPECTED_LABELS
    ratings = schema["properties"]["predicted_ratings"]
    assert ratings["additionalProperties"] is False
    assert ratings["required"] == EXPECTED_LABELS
    assert all(ratings["properties"][label]["type"] == "number" for label in EXPECTED_LABELS)
    assert all(ratings["properties"][label]["minimum"] == 0 for label in EXPECTED_LABELS)
    assert all(ratings["properties"][label]["maximum"] == 100 for label in EXPECTED_LABELS)
    ranking = schema["properties"]["predicted_ranking"]
    assert ranking["minItems"] == 5
    assert ranking["maxItems"] == 5
    assert ranking["uniqueItems"] is True


def test_template_matches_frozen_constants():
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    assert template["prompt_spec_version"] == PROMPT_SPEC_VERSION
    assert template["response_schema_version"] == RESPONSE_SCHEMA_VERSION
    assert template["system_instruction"] == SYSTEM_INSTRUCTION
    assert template["task_wording"] == TASK_WORDING
    assert template["acoustic_numeric_precision_decimal_places"] == PROMPT_ACOUSTIC_DECIMALS
    assert template["format_repair_instruction"] == FORMAT_REPAIR_INSTRUCTION
    assert template["section_order"]["non_history"] == [
        "Task",
        "Target listening situation",
        "Participant information",
        "Acoustic feature guide",
        "Target candidate mixes",
        "Prediction/output instructions",
    ]
    assert template["section_order"]["personalised_history"][-2] == "Previous listening evidence from this participant"


def test_non_history_prompt_structure_contains_no_history_section():
    pair = matched_pair()
    prompt = render_condition_prompt(pair["non_history"])
    assert prompt["section_headings"] == [
        "Task",
        "Target listening situation",
        "Participant information",
        "Acoustic feature guide",
        "Target candidate mixes",
        "Prediction/output instructions",
    ]
    assert "Previous listening evidence" not in prompt["user_message"]
    assert "Participant rating:" not in prompt["user_message"]


def test_personalised_history_prompt_structure_adds_only_history_section():
    pair = matched_pair()
    prompt = render_condition_prompt(pair["personalised_history"])
    assert prompt["section_headings"] == [
        "Task",
        "Target listening situation",
        "Participant information",
        "Acoustic feature guide",
        "Target candidate mixes",
        "Previous listening evidence from this participant",
        "Prediction/output instructions",
    ]
    assert prompt["history_trial_count"] == 5
    assert "The 0-100 values below are ratings previously given by this same participant." in prompt["user_message"]


def test_participant_metadata_missing_values_render_as_not_provided():
    p2_non_history = next(
        obj
        for obj in load_jsonl(PROMPT_DATA)
        if obj["prediction_example_id"].startswith("SYNTHETIC_PHASE6B1_P002") and obj["condition"] == "non_history"
    )
    rendered = render_condition_prompt(p2_non_history)["user_message"]
    assert f"- Hearing difficulty: {MISSING_VALUE}" in rendered


def test_acoustic_values_render_to_two_decimals_without_negative_zero():
    assert PROMPT_ACOUSTIC_DECIMALS == 2
    assert render_number(-0.0024) == "0.00"
    rendered = render_condition_prompt(matched_pair()["non_history"])["user_message"]
    assert "RMS z-score: -1.03" in rendered
    assert "RMS z-score: -0.0024" not in rendered
    assert "RMS z-score: -0.00" not in rendered


def test_song_identity_uses_participant_label_not_title_or_ids():
    pair = matched_pair()
    rendered = render_condition_prompt(pair["personalised_history"])["user_message"]
    assert "Study song: Song A" in rendered
    assert "Study song: Song B" in rendered
    assert "Lead Me" not in rendered
    assert "I'd Like To Know" not in rendered
    assert "lead_me" not in rendered
    assert "group_01_song_a_lead_me" not in rendered


def test_output_instructions_have_three_fields_and_no_reasoning_field():
    assert "predicted_preferred_mix" in OUTPUT_INSTRUCTIONS
    assert "predicted_ratings" in OUTPUT_INSTRUCTIONS
    assert "predicted_ranking" in OUTPUT_INSTRUCTIONS
    assert "Do not include a rationale, explanation, reasoning trace" in OUTPUT_INSTRUCTIONS
    assert "confidence" not in json.loads(RESPONSE_SCHEMA.read_text(encoding="utf-8"))["properties"]


def test_format_repair_instruction_is_format_only():
    assert "Repair formatting only" in FORMAT_REPAIR_INSTRUCTION
    assert "Do not add new participant information" in FORMAT_REPAIR_INSTRUCTION
    assert "do not hint which candidate should win" in FORMAT_REPAIR_INSTRUCTION


def test_matched_prompt_equivalence_passes():
    pair = matched_pair()
    rendered = {
        "non_history": render_condition_prompt(pair["non_history"]),
        "personalised_history": render_condition_prompt(pair["personalised_history"]),
    }
    report = validate_prompt_equivalence(pair["non_history"], pair["personalised_history"], rendered)
    assert report["passed"] is True
    assert all(report["checks"].values())


def test_leakage_audit_passes_for_matched_pair():
    pair = matched_pair()
    rendered = {
        "non_history": render_condition_prompt(pair["non_history"]),
        "personalised_history": render_condition_prompt(pair["personalised_history"]),
    }
    report = validate_rendered_prompt_no_leakage(pair["non_history"], pair["personalised_history"], rendered)
    assert report == {"passed": True, "failures": []}


def test_leakage_audit_catches_song_title_and_forbidden_identifier():
    pair = matched_pair()
    rendered = {
        "non_history": render_condition_prompt(pair["non_history"]),
        "personalised_history": render_condition_prompt(pair["personalised_history"]),
    }
    rendered["non_history"]["user_message"] += "\nLead Me\nstimulus_id"
    report = validate_rendered_prompt_no_leakage(pair["non_history"], pair["personalised_history"], rendered)
    assert report["passed"] is False
    assert len(report["failures"]) >= 2


def test_static_synthetic_prompt_examples_and_audit_are_written():
    payload = json.loads(EXAMPLES_JSON.read_text(encoding="utf-8"))
    audit = json.loads(EXAMPLE_AUDIT.read_text(encoding="utf-8"))
    assert payload["prompt_spec_version"] == PROMPT_SPEC_VERSION
    assert set(payload["examples"]) == set(CONDITIONS)
    assert audit["equivalence_validation"]["passed"] is True
    assert audit["leakage_validation"]["passed"] is True
    assert audit["non_history_history_trials"] == 0
    assert audit["personalised_history_history_trials"] == 5
    assert audit["target_candidate_count"] == 5
    assert audit["non_history_size"]["characters"] > 0
    assert audit["personalised_history_size"]["characters"] > audit["non_history_size"]["characters"]


def test_prompt_spec_document_references_version_schema_and_provider_neutrality():
    text = SPEC.read_text(encoding="utf-8")
    assert PROMPT_SPEC_VERSION in text
    assert RESPONSE_SCHEMA_VERSION in text
    assert SYSTEM_INSTRUCTION in text
    assert "Provider adapters may change only technical transport mechanisms" in text
    assert "few-shot demonstrations" in text


def test_build_matched_synthetic_examples_is_deterministic():
    first = build_matched_synthetic_examples(PROMPT_DATA)
    second = build_matched_synthetic_examples(PROMPT_DATA)
    assert first == second


def matched_pair():
    objects = load_jsonl(PROMPT_DATA)
    prediction_example_id = "SYNTHETIC_PHASE6B1_P001__heldout__SYNTHETIC_PHASE6B1_P001__trial_01"
    return {
        obj["condition"]: obj
        for obj in objects
        if obj["prediction_example_id"] == prediction_example_id
    }
