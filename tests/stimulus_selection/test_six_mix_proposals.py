from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path

import pyloudnorm as pyln
import soundfile as sf


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "stimulus_selection" / "09_six_mix_proposals"
EXPECTED_SONGS = {"Lead Me", "In The Meantime", "Red To Blue", "Pouring Room"}


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_six_mix_proposal_shape_and_membership() -> None:
    rows = _rows(OUT / "tables" / "six_mix_proposals.csv")
    assert len(rows) == 24
    assert {row["song"] for row in rows} == EXPECTED_SONGS
    for song in EXPECTED_SONGS:
        song_rows = [row for row in rows if row["song"] == song]
        assert len(song_rows) == 6
        similar = {row["original_mix_name"] for row in song_rows if row["rating_condition"] == "Similar Ratings"}
        wide = {row["original_mix_name"] for row in song_rows if row["rating_condition"] == "Wide Ratings"}
        assert len(similar) == 3
        assert len(wide) == 3
        assert not similar & wide
    assert not any(row["original_mix_name"] in {"A", "B", "C", "D", "E", "F"} for row in rows)


def test_methodology_and_qc_tables_complete() -> None:
    config_text = (ROOT / "configs" / "stimulus_selection.yaml").read_text(encoding="utf-8")
    assert "six_mix_proposals:" in config_text
    assert "stereo_imbalance" in config_text
    assert "qc_only:" in config_text
    proposal_rows = _rows(OUT / "tables" / "six_mix_proposals.csv")
    qc_rows = _rows(OUT / "qc" / "six_mix_technical_qc.csv")
    assert len(qc_rows) == 24
    assert all(row["rating_count"] and row["mean_previous_preference"] for row in proposal_rows)
    assert all(row["boundary_fade_in_ms"] == "5" and row["boundary_fade_out_ms"] == "5" for row in qc_rows)
    assert all(row["boundary_click_qc_flag"] == "PASS" for row in qc_rows)
    assert all(row["technical_qc_status"] in {"PASS", "REVIEW", "FAIL"} for row in qc_rows)


def test_review_audio_format_loudness_and_names() -> None:
    manifest = _rows(OUT / "tables" / "six_mix_audio_manifest.csv")
    assert len(manifest) == 24
    meter = pyln.Meter(44100)
    for row in manifest:
        path = Path(row["output_path"])
        info = sf.info(str(path))
        audio, sr = sf.read(str(path), always_2d=True, dtype="float32")
        assert sr == 44100
        assert info.subtype == "PCM_24"
        assert audio.shape == (1234800, 2)
        assert row["fade_in_ms"] == "5"
        assert row["fade_out_ms"] == "5"
        assert row["clipping"] == "false"
        assert "_28sec.wav" in path.name
        assert not any(path.name.startswith(label + "_") for label in "ABCDEF")
        lufs = meter.integrated_loudness(audio)
        if row["validation_status"] == "PASS":
            assert abs(lufs - (-20.8)) <= 0.1


def test_alignment_figures_rapid_switch_and_zip() -> None:
    for song in EXPECTED_SONGS:
        assert (OUT / "alignment_review" / f"{song}_six_mix_waveforms.png").exists()
        assert (OUT / "alignment_review" / f"{song}_six_mix_transient_zoom.png").exists()
        rapid = OUT / "alignment_review" / f"{song}_SixMix_RapidSwitch.wav"
        assert rapid.exists()
        info = sf.info(str(rapid))
        assert info.subtype == "PCM_24"
        assert info.frames == 1234800
    zip_path = ROOT / "outputs" / "stimulus_selection" / "09_six_mix_proposals.zip"
    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as zf:
        assert zf.testzip() is None


def test_protected_outputs_unchanged_and_windows_paths() -> None:
    validation = json.loads((OUT / "validation" / "protected_outputs_hashes.json").read_text(encoding="utf-8"))
    assert validation["protected_unchanged"] is True
    assert validation["frontend_files_modified_by_pipeline"] is False
    assert validation["final_stimuli_modified_by_pipeline"] is False
    manifest = _rows(OUT / "tables" / "six_mix_audio_manifest.csv")
    assert any("QMUL UNIVERSITY" in row["output_path"] for row in manifest)
