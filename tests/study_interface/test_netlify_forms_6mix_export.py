import csv
import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "study-interface" / "scripts" / "netlify_forms_6mix_to_long_csv.py"


def load_converter():
    spec = importlib.util.spec_from_file_location("netlify_forms_6mix_to_long_csv", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_raw_netlify_export_writes_response_metadata_and_validation_report(tmp_path):
    converter = load_converter()
    input_csv = tmp_path / "listening-study-6mix.csv"
    output_dir = tmp_path / "out"
    responses = []
    mix_mapping = {"E1": {"song_a": {}}}
    presentation_order = {"E1": {"song_a": []}}

    for position, label in enumerate(["A", "B", "C", "D"], start=1):
        stimulus_id = f"song_a_mix_{label.lower()}"
        mix_mapping["E1"]["song_a"][label] = stimulus_id
        presentation_order["E1"]["song_a"].append(label)
        responses.append(
            {
                "trial_index": 1,
                "scenario_id": "E1",
                "episode_id": "E1",
                "episode_position": 1,
                "song_id": "song_a",
                "excerpt_id": "excerpt_a",
                "song_position": 1,
                "display_label": label,
                "display_position": position,
                "actual_mix_id": f"mix_{label.lower()}",
                "stimulus_id": stimulus_id,
                "audio_path": f"assets/{label}.wav",
                "rating": 50 + position,
                "rating_set": True,
                "audio_played": True,
                "first_play_timestamp": "2026-08-06T00:00:00Z",
                "comparative_comment": "Unicode check: clearer, warmer - cafe.",
                "response_time_ms": 1234,
            }
        )

    write_csv(
        input_csv,
        [
            {
                "study_id": "synthetic_study",
                "study_version": "synthetic_v1",
                "schema_version": "six_mix_netlify_forms_v1",
                "stimulus_configuration_version": "synthetic_config_v1",
                "submission_status": "completed",
                "group_id": "group_synthetic",
                "study_group": "group_synthetic",
                "started_at": "2026-08-06T00:00:00Z",
                "completed_at": "2026-08-06T00:10:00Z",
                "duration_seconds": "600",
                "assigned_song_ids_json": json.dumps(["song_a"]),
                "episode_order_json": json.dumps(["E1"]),
                "song_order_json": json.dumps({"E1": ["song_a"]}),
                "mix_mapping_json": json.dumps(mix_mapping),
                "presentation_order_json": json.dumps(presentation_order),
                "responses_json": json.dumps(responses),
                "client_validation_json": json.dumps({"expected_response_count": 4, "actual_response_count": 4}),
            }
        ],
    )

    rows, fieldnames, column_map = converter.load_rows(input_csv)
    long_rows, metadata_rows, issues, report, labels = converter.convert_export(rows, fieldnames, column_map, input_csv)

    assert len(long_rows) == 4
    assert len(metadata_rows) == 1
    assert issues == []
    assert report["overall_status"] == "pass"
    assert labels == ["A", "B", "C", "D"]
    assert metadata_rows[0]["label_D_stimulus_id"] == "song_a_mix_d"

    converter.write_csv(output_dir / "responses_long.csv", long_rows, converter.BASE_LONG_FIELDS + converter.RESPONSE_FIELDS)
    converter.write_csv(
        output_dir / "experiment_metadata.csv",
        metadata_rows,
        converter.BASE_METADATA_FIELDS + ["label_A_stimulus_id", "label_D_stimulus_id"],
    )
    converter.write_json(output_dir / "export_validation_report.json", report)

    assert len(read_csv(output_dir / "responses_long.csv")) == 4
    assert read_csv(output_dir / "experiment_metadata.csv")[0]["display_order"] == "A | B | C | D"
    assert json.loads((output_dir / "export_validation_report.json").read_text(encoding="utf-8"))["overall_status"] == "pass"


def test_long_format_fallback_flags_missing_raw_netlify_json(tmp_path):
    converter = load_converter()
    input_csv = tmp_path / "responses_long.csv"
    write_csv(
        input_csv,
        [
            {
                "study_id": "synthetic_study",
                "study_version": "synthetic_v1",
                "schema_version": "six_mix_netlify_forms_v1",
                "stimulus_configuration_version": "synthetic_config_v1",
                "group_id": "group_synthetic",
                "started_at": "2026-08-06T00:00:00Z",
                "completed_at": "2026-08-06T00:10:00Z",
                "duration_seconds": "600",
                "trial_index": "1",
                "scenario_id": "E1",
                "episode_id": "E1",
                "episode_position": "1",
                "song_id": "song_a",
                "excerpt_id": "excerpt_a",
                "song_position": "1",
                "display_label": "A",
                "display_position": "1",
                "actual_mix_id": "mix_a",
                "stimulus_id": "song_a_mix_a",
                "audio_path": "assets/A.wav",
                "rating": "50",
                "rating_set": "True",
                "audio_played": "True",
                "first_play_timestamp": "2026-08-06T00:00:00Z",
                "comparative_comment": "Fallback comment.",
                "response_time_ms": "1234",
            }
        ],
    )

    rows, fieldnames, column_map = converter.load_rows(input_csv)
    long_rows, metadata_rows, issues, report, labels = converter.convert_long_export(rows, fieldnames, column_map, input_csv)

    assert len(long_rows) == 1
    assert len(metadata_rows) == 1
    assert labels == ["A"]
    assert report["overall_status"] == "fail"
    assert issues[0]["code"] == "raw_netlify_json_unavailable"
