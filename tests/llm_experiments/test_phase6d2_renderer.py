import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.prompts.prompt_spec import (  # noqa: E402
    EXPECTED_LABELS,
    FORMAT_REPAIR_INSTRUCTION,
    MISSING_VALUE,
    OUTPUT_INSTRUCTIONS,
    PROMPT_SPEC_VERSION,
    RESPONSE_SCHEMA_VERSION,
    SYSTEM_INSTRUCTION,
    load_jsonl,
)
from llm_experiments.prompts.render import (  # noqa: E402
    RENDERED_PROMPT_SCHEMA_VERSION,
    make_rendered_prompt_id,
    render_format_repair,
    render_prompt,
    render_prompt_dataset,
    render_prompt_sections,
    validate_condition_object_for_rendering,
    validate_condition_pair_equivalence,
)


PROMPT_DATA = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6b5" / "final_prompt_data_objects.jsonl"
RESPONSE_SCHEMA = REPO_ROOT / "llm-experiments" / "schema" / "preference_prediction_response_v1.json"
RENDERED_SCHEMA = REPO_ROOT / "llm-experiments" / "schema" / "rendered_prompt_v1.json"
RENDERED_OUTPUT = REPO_ROOT / "llm-experiments" / "outputs" / "synthetic" / "phase6d2_rendered_prompts"


def test_frozen_system_instruction_rendered_exactly():
    rendered = render_prompt(matched_pair()["non_history"])
    assert rendered["messages"][0] == {"role": "system", "content": SYSTEM_INSTRUCTION}


def test_metadata_order_fixed_and_missing_metadata_rendered():
    p2 = next(
        obj
        for obj in load_jsonl(PROMPT_DATA)
        if obj["prediction_example_id"].startswith("SYNTHETIC_PHASE6B1_P002") and obj["condition"] == "non_history"
    )
    text = render_prompt(p2)["messages"][1]["content"]
    expected = [
        "- Age range:",
        "- Gender:",
        "- Cultural influence country:",
        "- Music listening habits:",
        "- Music production/audio engineering experience:",
        "- Hearing difficulty:",
    ]
    assert [line.split(" ")[0] + " " + line.split(" ")[1] for line in section_lines(text, "Participant information")[:6]][0] == "- Age"
    positions = [text.index(label) for label in expected]
    assert positions == sorted(positions)
    assert f"- Hearing difficulty: {MISSING_VALUE}" in text


def test_active_context_text_preserved_without_target_comment():
    obj = matched_pair()["non_history"]
    text = render_prompt(obj)["messages"][1]["content"]
    context = obj["model_input"]["target"]["context"]["context_text"]
    assert context in text
    assert "SYNTHETIC TEST COMMENT SYNTHETIC_PHASE6B1_P001 trial 1." not in text


def test_song_title_ids_and_stable_mix_identifiers_not_exposed():
    text = render_prompt(matched_pair()["personalised_history"])["messages"][1]["content"]
    assert "Study song: Song A" in text
    assert "Study song: Song B" in text
    forbidden = ["Lead Me", "I'd Like To Know", "lead_me", "group_01_song_a_lead_me", "stimulus_id", "actual_mix_id", ".wav"]
    assert not any(token in text for token in forbidden)


def test_acoustic_values_are_two_decimals_and_z_si_absent():
    text = render_prompt(matched_pair()["non_history"])["messages"][1]["content"]
    assert "RMS z-score: -1.03" in text
    assert "RMS z-score: 0.00" in text
    assert "-1.0251" not in text
    assert "z_SI" not in text


def test_candidates_render_a_to_e_even_if_source_order_changes():
    obj = json.loads(json.dumps(matched_pair()["non_history"]))
    obj["model_input"]["target"]["candidates"] = list(reversed(obj["model_input"]["target"]["candidates"]))
    text = render_prompt(obj)["messages"][1]["content"]
    positions = [text.index(f"Candidate {label}") for label in EXPECTED_LABELS]
    assert positions == sorted(positions)


def test_non_history_contains_no_history_ratings_or_comments():
    text = render_prompt(matched_pair()["non_history"])["messages"][1]["content"]
    assert "Previous listening evidence" not in text
    assert "Participant rating:" not in text
    assert "Participant comparative comment:" not in text


def test_personalised_history_preserves_prior_ratings_comments_and_missing_comment():
    text = render_prompt(matched_pair()["personalised_history"])["messages"][1]["content"]
    assert "- Participant rating: 42" in text
    assert "Participant comparative comment: SYNTHETIC TEST COMMENT SYNTHETIC_PHASE6B1_P001 trial 2." in text
    assert f"Participant comparative comment: {MISSING_VALUE}" in text


def test_target_rating_comment_and_outcome_fields_absent():
    text = render_prompt(matched_pair()["personalised_history"])["messages"][1]["content"]
    forbidden = [
        "observed_rank",
        "observed_preferred_set",
        "observed_preferred_mix",
        "is_single_winner",
        "n_preferred_tied",
        "ground_truth",
    ]
    assert "SYNTHETIC TEST COMMENT SYNTHETIC_PHASE6B1_P001 trial 1." not in text
    assert not any(token in text for token in forbidden)


def test_output_instruction_matches_frozen_schema_and_requests_no_reasoning():
    text = render_prompt(matched_pair()["non_history"])["messages"][1]["content"]
    assert OUTPUT_INSTRUCTIONS in text
    assert "predicted_preferred_mix" in text
    assert "predicted_ratings" in text
    assert "predicted_ranking" in text
    assert "Do not include a rationale, explanation, reasoning trace" in text


def test_prompt_ids_and_serialization_are_deterministic():
    obj = matched_pair()["non_history"]
    first = render_prompt(obj)
    second = render_prompt(obj)
    assert first == second
    assert first["rendered_prompt_id"] == make_rendered_prompt_id(obj["condition_object_id"])
    assert json.dumps(first, sort_keys=True, separators=(",", ":")) == json.dumps(second, sort_keys=True, separators=(",", ":"))


def test_condition_pairs_identical_outside_history():
    pair = matched_pair()
    report = validate_condition_pair_equivalence(pair["non_history"], pair["personalised_history"])
    assert report["passed"] is True
    assert all(report["checks"].values())
    non_sections = render_prompt_sections(pair["non_history"])
    hist_sections = render_prompt_sections(pair["personalised_history"])
    assert non_sections["Target candidate mixes"] == hist_sections["Target candidate mixes"]
    assert "Previous listening evidence from this participant" not in non_sections
    assert "Previous listening evidence from this participant" in hist_sections


def test_repair_prompt_contains_invalid_output_schema_and_no_participant_evidence():
    schema = json.loads(RESPONSE_SCHEMA.read_text(encoding="utf-8"))
    repair = render_format_repair('{"bad": true}', schema)
    text = repair["messages"][0]["content"]
    assert FORMAT_REPAIR_INSTRUCTION in text
    assert '"$id": "preference_prediction_response_v1"' in text
    assert '{"bad": true}' in text
    assert "SYNTHETIC_PHASE6B1" not in text
    assert "correct answer" not in text.lower()
    assert "should choose" not in text.lower()


def test_malformed_input_fails_validation():
    obj = json.loads(json.dumps(matched_pair()["non_history"]))
    obj["model_input"]["target"]["candidates"].pop()
    try:
        validate_condition_object_for_rendering(obj)
    except ValueError as exc:
        assert "exactly A-E" in str(exc)
    else:
        raise AssertionError("Expected malformed candidate set to fail.")


def test_ground_truth_and_forbidden_model_input_rejected():
    obj = json.loads(json.dumps(matched_pair()["non_history"]))
    obj["ground_truth"] = {}
    try:
        validate_condition_object_for_rendering(obj)
    except ValueError as exc:
        assert "ground_truth" in str(exc)
    else:
        raise AssertionError("Expected top-level ground_truth to fail.")
    obj = json.loads(json.dumps(matched_pair()["non_history"]))
    obj["model_input"]["target"]["candidates"][0]["human_rating"] = 99
    try:
        validate_condition_object_for_rendering(obj)
    except ValueError as exc:
        assert "human_rating" in str(exc)
    else:
        raise AssertionError("Expected target human_rating to fail.")


def test_batch_rendered_dataset_audit_counts_and_sizes(tmp_path):
    audit = render_prompt_dataset(PROMPT_DATA, tmp_path, RESPONSE_SCHEMA)
    assert audit["prompt_data_objects_read"] == 22
    assert audit["rendered_prompts_written"] == 22
    assert audit["non_history_count"] == 11
    assert audit["personalised_history_count"] == 11
    assert audit["rendering_failures"] == 0
    assert audit["leakage_failures"] == 0
    assert audit["condition_pair_equivalence_failures"] == 0
    assert audit["deterministic_rerun_passed"] is True
    assert audit["size_summary"]["non_history"]["characters_min"] > 0
    assert audit["size_summary"]["personalised_history"]["characters_max"] > audit["size_summary"]["non_history"]["characters_max"]


def test_rendered_prompt_schema_artifact_matches_output_shape():
    schema = json.loads(RENDERED_SCHEMA.read_text(encoding="utf-8"))
    rendered = render_prompt(matched_pair()["non_history"])
    assert schema["$id"] == RENDERED_PROMPT_SCHEMA_VERSION
    assert set(schema["required"]) == set(rendered)
    assert rendered["messages"][0]["role"] == "system"
    assert rendered["messages"][1]["role"] == "user"
    assert rendered["response_schema_version"] == RESPONSE_SCHEMA_VERSION


def test_static_synthetic_rendered_dataset_exists_and_is_clean():
    audit = json.loads((RENDERED_OUTPUT / "rendered_prompt_audit.json").read_text(encoding="utf-8"))
    prompts = load_jsonl(RENDERED_OUTPUT / "rendered_prompts.jsonl")
    assert audit["rendered_prompts_written"] == 22
    assert audit["leakage_failures"] == 0
    assert audit["condition_pair_equivalence_failures"] == 0
    assert audit["deterministic_rerun_passed"] is True
    assert len(prompts) == 22
    assert prompts == sorted(prompts, key=lambda row: row["rendered_prompt_id"])


def matched_pair():
    prediction_example_id = "SYNTHETIC_PHASE6B1_P001__heldout__SYNTHETIC_PHASE6B1_P001__trial_01"
    return {
        obj["condition"]: obj
        for obj in load_jsonl(PROMPT_DATA)
        if obj["prediction_example_id"] == prediction_example_id
    }


def section_lines(text, heading):
    start = text.index(f"## {heading}")
    next_heading = text.find("\n\n## ", start + 1)
    body = text[start: next_heading if next_heading != -1 else len(text)]
    return [line for line in body.splitlines() if line.startswith("- ")]
