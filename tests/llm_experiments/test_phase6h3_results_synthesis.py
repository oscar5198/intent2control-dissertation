from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_SRC = REPO_ROOT / "llm-experiments" / "src"
if str(LLM_SRC) not in sys.path:
    sys.path.insert(0, str(LLM_SRC))

from llm_experiments.evaluation import phase6h3_results_synthesis as phase6h3  # noqa: E402


@pytest.fixture(scope="module")
def synthesized(tmp_path_factory: pytest.TempPathFactory) -> dict:
    out = tmp_path_factory.mktemp("phase6h3")
    return phase6h3.run_phase6h3_results_synthesis(REPO_ROOT, output_dir=out)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_qc_gates_confirm_synthesis_only(synthesized: dict) -> None:
    gates = synthesized["qc"]["gates"]

    assert synthesized["qc"]["passed"] is True
    assert gates["NO_MODEL_INFERENCE_RERUN"] is True
    assert gates["NO_MIXED_EFFECTS_REFIT"] is True
    assert gates["FROZEN_TIE_POLICY_USED"] is True
    assert gates["DATASET_COUNTS_MATCH_FINAL_N33"] is True


def test_main_table_1_contains_empirical_effects_and_variance(synthesized: dict) -> None:
    out = Path(synthesized["output_dir"])
    rows = read_csv(out / "phase6h3_main_table_1_mixed_effects.csv")
    quantities = {row["Quantity"] for row in rows}

    assert "Episode: FM-1 vs EDR-1" in quantities
    assert "Acoustic feature: crest factor (z)" in quantities
    assert "Participant ICC" in quantities
    assert "Residual variance share" in quantities
    assert any(row["Dissertation role"] == "Primary empirical fixed effect" for row in rows)


def test_main_table_2_preserves_final_prediction_metrics(synthesized: dict) -> None:
    out = Path(synthesized["output_dir"])
    rows = read_csv(out / "phase6h3_main_table_2_prediction_results.csv")
    gpt_history = next(row for row in rows if row["Model"] == "GPT-5.5" and row["Condition"] == "personalised_history")
    mixed = next(row for row in rows if row["Model"] == "Mixed-effects primary acoustic")

    assert gpt_history["Top-1 %"] == "34.3%"
    assert gpt_history["MAE"] == "21.75"
    assert mixed["Top-1 %"] == "34.3%"
    assert mixed["Primary role"] == "Matched empirical predictive baseline"
    assert len(rows) == 9


def test_optional_personalisation_table_includes_paired_counts(synthesized: dict) -> None:
    out = Path(synthesized["output_dir"])
    rows = read_csv(out / "phase6h3_optional_table_3_personalisation.csv")
    claude = next(row for row in rows if row["Model"] == "Claude Sonnet 5")

    assert claude["Delta Top-1 pp"] == "15.2"
    assert claude["History helps"] == "52"
    assert claude["History hurts"] == "22"
    assert claude["McNemar p"] == "6.43e-04"


def test_rq_matrix_and_results_text_are_dissertation_ready(synthesized: dict) -> None:
    out = Path(synthesized["output_dir"])
    rq = (out / "phase6h3_rq_answer_matrix.md").read_text(encoding="utf-8")
    text = (out / "phase6h3_results_ready_text.md").read_text(encoding="utf-8")

    assert "RQ1" in rq and "RQ4" in rq
    assert "not as an overall model leaderboard" not in text
    assert "## A. Listening Study and Preference Variation" in text
    assert "## E. Comparison with the Mixed-Effects Predictive Model" in text
    assert "198-trial target set" in text


def test_figure_recommendations_copy_existing_pngs(synthesized: dict) -> None:
    out = Path(synthesized["output_dir"])
    recommendations = json.loads((out / "phase6h3_main_figure_recommendations.json").read_text(encoding="utf-8"))

    assert [row["role"] for row in recommendations] == ["main", "main", "appendix"]
    for row in recommendations:
        figure = out / row["phase6h3_path"]
        assert figure.exists()
        assert figure.stat().st_size > 0


def test_inventory_records_hashes_and_outputs(synthesized: dict) -> None:
    out = Path(synthesized["output_dir"])
    inventory = json.loads((out / "phase6h3_final_results_inventory.json").read_text(encoding="utf-8"))

    assert inventory["schema_version"] == "phase6h3_final_results_inventory_v1"
    assert inventory["qc"]["passed"] is True
    assert "phase6h3_main_table_1_mixed_effects.md" in inventory["output_hashes"]
    assert "phase6h3_figure2_top1_accuracy.png" in inventory["output_hashes"]


def test_qc_report_lists_all_gates(synthesized: dict) -> None:
    out = Path(synthesized["output_dir"])
    report = (out / "phase6h3_qc_report.md").read_text(encoding="utf-8")

    assert "PHASE6H3_RESULTS_SYNTHESIS_COMPLETE" in report
    assert "ALL_DECLARED_OUTPUTS_EXIST" in report
    assert "No prompt generation" in report
