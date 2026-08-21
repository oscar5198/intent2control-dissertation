from __future__ import annotations

import ast
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FINAL_REVIEW = ROOT / "experimental-design" / "stimulus-selection" / "final-selection" / "five-mix-selection-review-20260806"
SOURCE_EVIDENCE = ROOT / "experimental-design" / "stimulus-selection" / "final-selection" / "source-evidence"
AUDIO_ROOT = ROOT / "study-interface" / "frontend-5mix" / "assets" / "audio" / "study-stimuli" / "main-study"
FEATURE_TABLE = ROOT / "statistical-modeling" / "outputs" / "acoustic-features" / "final_20_stimulus_feature_table.csv"


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_final_generator_source_manifest_resolves() -> None:
    tree = ast.parse((FINAL_REVIEW / "generate_five_mix_review.py").read_text(encoding="utf-8"))
    sources = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "SOURCES":
                    sources = ast.literal_eval(node.value)
    assert sources
    missing = [path for path in sources.values() if not (ROOT / path).exists()]
    assert missing == []


def test_final_selection_tables_cover_four_songs_and_twenty_mixes() -> None:
    rows = _rows(FINAL_REVIEW / "recommended_five_mix_selections.csv")
    assert len(rows) == 20
    by_song: dict[str, list[str]] = {}
    for row in rows:
        by_song.setdefault(row["song"], []).append(row["original_mix_name"])
    assert by_song == {
        "Lead Me": ["DU-D", "DU-E", "PXL-L1", "PXL-L4", "McG-pro2"],
        "In The Meantime": ["QUT-B", "DU-H", "DU-I", "DU-K", "QUT-pro"],
        "Pouring Room": ["McG-R", "McG-T", "McG-X", "McG-pro1", "McG-V"],
        "I'd Like To Know": ["PXL-S3", "PXL-S5", "PXL-S1", "PXL-S2", "PXL-S7"],
    }


def test_final_audio_inventory_and_feature_table_are_complete() -> None:
    wavs = sorted(AUDIO_ROOT.rglob("*.wav"))
    assert len(wavs) == 20
    features = _rows(FEATURE_TABLE)
    assert len(features) == 20
    assert {row["song_title"] for row in features} == {"Lead Me", "In The Meantime", "Pouring Room", "I'd Like To Know"}


def test_source_evidence_is_compact() -> None:
    assert SOURCE_EVIDENCE.exists()
    assert not (ROOT / "experimental-design" / "stimulus-selection" / "supporting-analysis").exists()
