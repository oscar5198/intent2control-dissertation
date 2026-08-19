"""Phase 6H.3 dissertation-ready results synthesis.

This stage compiles frozen Phase 6H.1, 6H.2A, and 6H.2B artifacts into a
results pack. It does not run inference, refit models, or rescore trials.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
OUTPUT_DIR = Path("llm-experiments/outputs/real/phase6h3")
PHASE6H1_DIR = Path("llm-experiments/outputs/real/phase6h1")
PHASE6H2B_DIR = Path("llm-experiments/outputs/real/phase6h2b")
PHASE6H2A_EMPIRICAL_DIR = Path("statistical-baseline/outputs/final_n33_empirical")


def run_phase6h3_results_synthesis(repo_root: Path, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    out = repo_root / output_dir
    out.mkdir(parents=True, exist_ok=True)

    sources = load_sources(repo_root)
    tables = write_tables(out, sources)
    figures = write_figure_recommendations(repo_root, out)
    markdown = write_markdown_outputs(out, sources, figures)
    qc = build_qc(repo_root, output_dir, tables, figures, markdown, sources)
    inventory = build_inventory(repo_root, output_dir, tables, figures, markdown, qc)

    write_json(out / "phase6h3_final_results_inventory.json", inventory)
    write_qc_report(out / "phase6h3_qc_report.md", qc, inventory)
    return {
        "output_dir": str(out),
        "tables": tables,
        "figures": figures,
        "markdown": markdown,
        "qc": qc,
        "inventory": inventory,
    }


def load_sources(repo_root: Path) -> dict[str, Any]:
    return {
        "h1_summary": read_json(repo_root / PHASE6H1_DIR / "phase6h1_data_collection_summary.json"),
        "h1_protocol": read_json(repo_root / PHASE6H1_DIR / "phase6h1_metric_protocol.json"),
        "h1_tie_policy": read_json(repo_root / PHASE6H1_DIR / "phase6h1_tie_policy.json"),
        "h2a_inventory": read_json(repo_root / PHASE6H2A_EMPIRICAL_DIR / "n33_empirical_results_inventory.json"),
        "mixed_effects": read_csv(repo_root / PHASE6H2B_DIR / "phase6h2b_table_a_central_mixed_effects.csv"),
        "prediction": read_csv(repo_root / PHASE6H2B_DIR / "phase6h2b_table_b_prediction_results.csv"),
        "personalisation": read_csv(repo_root / PHASE6H2B_DIR / "phase6h2b_table_c_personalisation_effects.csv"),
        "personalisation_full": read_csv(repo_root / PHASE6H2B_DIR / "phase6h2b_personalisation_effects.csv"),
        "chance": read_csv(repo_root / PHASE6H2B_DIR / "phase6h2b_chance_tests.csv"),
        "comparison": read_csv(repo_root / PHASE6H2B_DIR / "phase6h2b_mixed_effects_llm_comparison.csv"),
        "h2b_manifest": read_json(repo_root / PHASE6H2B_DIR / "phase6h2b_provenance_manifest.json"),
        "h2b_qc": read_json(repo_root / PHASE6H2B_DIR / "phase6h2b_qc_summary.json"),
    }


def write_tables(out: Path, sources: dict[str, Any]) -> dict[str, str]:
    table1 = build_main_table_1(sources)
    table2 = build_main_table_2(sources)
    table3 = build_optional_table_3(sources)

    paths = {
        "main_table_1_csv": out / "phase6h3_main_table_1_mixed_effects.csv",
        "main_table_1_md": out / "phase6h3_main_table_1_mixed_effects.md",
        "main_table_2_csv": out / "phase6h3_main_table_2_prediction_results.csv",
        "main_table_2_md": out / "phase6h3_main_table_2_prediction_results.md",
        "optional_table_3_csv": out / "phase6h3_optional_table_3_personalisation.csv",
    }

    write_csv(paths["main_table_1_csv"], table1)
    write_markdown_table(paths["main_table_1_md"], "# Main Table 1: Empirical Mixed-Effects Results", table1)
    write_csv(paths["main_table_2_csv"], table2)
    write_markdown_table(paths["main_table_2_md"], "# Main Table 2: Held-Out Preference Prediction", table2)
    write_csv(paths["optional_table_3_csv"], table3)
    return {key: path.name for key, path in paths.items()}


def build_main_table_1(sources: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    keep_terms = {
        "Intercept",
        "episode[EDR-2]",
        "episode[FM-1]",
        "group[group_02]",
        "z_RMS",
        "z_CF",
        "z_SW",
        "1|participant_id_sigma",
        "1|stimulus_id_sigma",
        "sigma",
        "participant_ICC",
        "stimulus_ICC",
        "residual_share",
    }
    label_map = {
        "episode[EDR-2]": "Episode: EDR-2 vs EDR-1",
        "episode[FM-1]": "Episode: FM-1 vs EDR-1",
        "group[group_02]": "Participant group: group_02 vs group_01",
        "z_RMS": "Acoustic feature: RMS (z)",
        "z_CF": "Acoustic feature: crest factor (z)",
        "z_SW": "Acoustic feature: spectral width (z)",
        "1|participant_id_sigma": "Participant random-effect SD",
        "1|stimulus_id_sigma": "Stimulus random-effect SD",
        "sigma": "Residual SD",
        "participant_ICC": "Participant ICC",
        "stimulus_ICC": "Stimulus ICC",
        "residual_share": "Residual variance share",
    }
    for row in sources["mixed_effects"]:
        if row["term"] not in keep_terms:
            continue
        rows.append(
            {
                "Section": row["section"],
                "Model": row["model"],
                "Quantity": label_map.get(row["term"], row["term"]),
                "Estimate": fmt_num(row["estimate"], 3),
                "95% CrI": f"[{fmt_num(row['ci_low'], 3)}, {fmt_num(row['ci_high'], 3)}]",
                "Dissertation role": role_for_mixed_effect(row),
            }
        )
    return rows


def role_for_mixed_effect(row: dict[str, str]) -> str:
    if row["section"] == "fixed" and row["model"] == "primary_feature_model":
        return "Primary empirical fixed effect"
    if row["section"] == "fixed":
        return "Stimulus/context reference model"
    if row["section"] == "variance":
        return "Model uncertainty and residual variation"
    return "Preference-variation partition"


def build_main_table_2(sources: dict[str, Any]) -> list[dict[str, str]]:
    chance_by_label = {(row["model_label"], row["condition"]): row for row in sources["chance"]}
    rows = []
    for row in sources["prediction"]:
        chance = chance_by_label.get((row["Model"], row["Condition"]), {})
        rows.append(
            {
                "Model": row["Model"],
                "Condition": row["Condition"],
                "Top-1 %": fmt_percent(row["Top-1 Accuracy"]),
                "95% CI": row["95% CI"],
                "Chance p (BH)": fmt_p(chance.get("p_value_bh_adjusted", "")),
                "Mean Spearman": fmt_num(row["Mean Spearman"], 3),
                "MAE": fmt_optional(row["MAE"], 2),
                "RMSE": fmt_optional(row["RMSE"], 2),
                "Primary role": prediction_role(row),
            }
        )
    return rows


def prediction_role(row: dict[str, str]) -> str:
    if row["Model"].startswith("Mixed-effects"):
        return "Matched empirical predictive baseline"
    if row["Condition"] == "personalised_history":
        return "LLM with participant history"
    return "LLM without participant history"


def build_optional_table_3(sources: dict[str, Any]) -> list[dict[str, str]]:
    p_by_model = {row["model_label"]: row for row in sources["personalisation_full"]}
    rows = []
    for row in sources["personalisation"]:
        p_row = p_by_model[row["Model"]]
        rows.append(
            {
                "Model": row["Model"],
                "Delta Top-1 pp": fmt_num(row["Delta Top-1 pp"], 1),
                "History helps": row["History Helps"],
                "History hurts": row["History Hurts"],
                "McNemar p": fmt_p(p_row["mcnemar_exact_p"]),
                "Delta Spearman": fmt_num(row["Delta Spearman"], 3),
                "Delta MAE": fmt_optional(row["Delta MAE"], 2),
            }
        )
    return rows


def write_figure_recommendations(repo_root: Path, out: Path) -> list[dict[str, str]]:
    figure_specs = [
        {
            "figure_id": "Figure 1",
            "recommended_placement": "Main Results, Listening Study and Preference Variation",
            "source": PHASE6H2A_EMPIRICAL_DIR / "n33_primary_feature_coefficient_plot.png",
            "output": out / "phase6h3_figure1_mixed_effects_coefficients.png",
            "caption": "Posterior estimates for the primary feature mixed-effects model, showing episode, participant-group, and acoustic-feature associations with listener ratings.",
            "role": "main",
        },
        {
            "figure_id": "Figure 2",
            "recommended_placement": "Main Results, Held-Out Mix Preference Prediction",
            "source": PHASE6H2B_DIR / "phase6h2b_figure2_top1_accuracy.png",
            "output": out / "phase6h3_figure2_top1_accuracy.png",
            "caption": "Held-out preferred-mix Top-1 accuracy with Wilson 95% intervals for LLM conditions and the matched mixed-effects predictive baseline.",
            "role": "main",
        },
        {
            "figure_id": "Supplementary Figure S1",
            "recommended_placement": "Appendix or supplementary results",
            "source": PHASE6H2B_DIR / "phase6h2b_figure3_personalisation_top1.png",
            "output": out / "phase6h3_supplementary_figure_personalisation_top1.png",
            "caption": "Within-model change in Top-1 accuracy when participant history is supplied.",
            "role": "appendix",
        },
    ]
    recommendations = []
    for spec in figure_specs:
        src = repo_root / spec["source"]
        shutil.copy2(src, spec["output"])
        recommendations.append(
            {
                "figure_id": spec["figure_id"],
                "role": spec["role"],
                "recommended_placement": spec["recommended_placement"],
                "source_path": str(spec["source"]).replace("\\", "/"),
                "phase6h3_path": spec["output"].name,
                "caption": spec["caption"],
            }
        )
    write_json(out / "phase6h3_main_figure_recommendations.json", recommendations)
    return recommendations


def write_markdown_outputs(out: Path, sources: dict[str, Any], figures: list[dict[str, str]]) -> dict[str, str]:
    paths = {
        "rq_answer_matrix": out / "phase6h3_rq_answer_matrix.md",
        "appendix_recommendations": out / "phase6h3_appendix_recommendations.md",
        "results_ready_text": out / "phase6h3_results_ready_text.md",
        "interpretation_limitations": out / "phase6h3_interpretation_limitations_notes.md",
        "dissertation_results_plan": out / "phase6h3_dissertation_results_plan.md",
    }
    paths["rq_answer_matrix"].write_text(build_rq_answer_matrix(sources), encoding="utf-8")
    paths["appendix_recommendations"].write_text(build_appendix_recommendations(figures), encoding="utf-8")
    paths["results_ready_text"].write_text(build_results_ready_text(sources), encoding="utf-8")
    paths["interpretation_limitations"].write_text(build_interpretation_limitations(), encoding="utf-8")
    paths["dissertation_results_plan"].write_text(build_results_plan(), encoding="utf-8")
    return {key: path.name for key, path in paths.items()}


def build_rq_answer_matrix(sources: dict[str, Any]) -> str:
    best_personalised = max(
        (row for row in sources["prediction"] if row["Condition"] == "personalised_history"),
        key=lambda row: float(row["Top-1 Accuracy"]),
    )
    mixed = next(row for row in sources["prediction"] if row["Model"].startswith("Mixed-effects"))
    return "\n".join(
        [
            "# Phase 6H.3 Research Question Answer Matrix",
            "",
            "| RQ | Evidence base | Dissertation-ready answer |",
            "| --- | --- | --- |",
            "| RQ1: How do listener/context and acoustic variables explain mix ratings? | N=33 mixed-effects models; 990 ratings; participant and stimulus random effects; primary feature model. | Ratings vary materially by episode, group, participant, stimulus, and acoustic descriptors. FM-1 is lower than EDR-1 in both models; crest factor is negatively associated with ratings in the primary feature model, while participant and stimulus variance remain substantial. |",
            f"| RQ2: Can models predict held-out preferred mixes? | Frozen 198-trial held-out target set with set-based Top-1 tie credit. Best personalised LLM: {best_personalised['Model']} at {fmt_percent(best_personalised['Top-1 Accuracy'])}; mixed-effects baseline: {fmt_percent(mixed['Top-1 Accuracy'])}. | Prediction is possible above the 20% chance reference for selected personalised conditions and the matched mixed-effects baseline, but performance remains modest in absolute terms. |",
            "| RQ3: Does participant history help LLM prediction? | Paired history vs non-history comparisons across 198 examples per LLM. | Participant history substantially improves GPT-5.5 and Claude Sonnet 5, with smaller and not clearly reliable gains for Llama 3.1 70B and Centaur. |",
            "| RQ4: How do LLMs compare with the empirical mixed-effects predictor? | Same 198 held-out examples, identical Top-1 tie policy, paired McNemar comparisons. | The mixed-effects baseline is the strongest ranking model. Personalised GPT-5.5 matches its Top-1 point estimate and personalised Claude is slightly higher numerically, but neither differs detectably from the mixed-effects baseline on Top-1. |",
            "",
        ]
    )


def build_appendix_recommendations(figures: list[dict[str, str]]) -> str:
    return "\n".join(
        [
            "# Phase 6H.3 Appendix Recommendations",
            "",
            "- Include the full Phase 6H.1 protocol freeze artifacts as reproducibility appendices: metric protocol, tie policy, prediction/ground-truth join manifest, and QC report.",
            "- Include Phase 6H.2B trial-level and candidate-level score CSVs as machine-readable supplementary material rather than main-body tables.",
            "- Place `phase6h3_optional_table_3_personalisation.csv` in an appendix if the main results chapter is space-constrained.",
            "- Use `phase6h3_supplementary_figure_personalisation_top1.png` as Supplementary Figure S1 unless the personalisation subsection needs a visual summary in the main text.",
            "- Report Centaur rating-error metrics as not applicable because this condition uses native likelihood outputs rather than calibrated 0-100 ratings.",
            "- Keep stale incomplete-marker notes from Phase 6H.2A in provenance/QC appendices only; the final N=33 diagnostics are the authoritative empirical outputs.",
            "",
            "Recommended figure files:",
            *(f"- {figure['figure_id']}: `{figure['phase6h3_path']}` ({figure['role']})" for figure in figures),
            "",
        ]
    )


def build_results_ready_text(sources: dict[str, Any]) -> str:
    summary = sources["h1_summary"]
    return "\n\n".join(
        [
            "# Phase 6H.3 Results-Ready Text",
            "## A. Listening Study and Preference Variation",
            (
                f"The final listening-study dataset contained {summary['participant_count']} analysable participants "
                f"({summary['group_counts']['group_01']} in group_01 and {summary['group_counts']['group_02']} in group_02), "
                f"{summary['total_trials']} participant-song-episode trials, and {summary['total_individual_mix_ratings']} individual mix ratings. "
                "Each trial presented five randomized candidate mixes, with A-E labels reconstructed from the frozen candidate mappings. "
                "All expected trial-level comments were present, and no post-freeze additional responses were detected. "
                "This dataset therefore provides the empirical basis for both preference-variation modelling and held-out prediction."
            ),
            "## B. Mixed-Effects Empirical Model",
            (
                "The mixed-effects analysis used two N=33 models: a stimulus/context model and a primary acoustic-feature model. "
                "Both included participant and stimulus random intercepts and converged satisfactorily, with four chains, 1,000 posterior draws per chain, "
                "zero divergences, and maximum R-hat of 1.01. In the primary feature model, FM-1 was rated lower than EDR-1 "
                "(estimate -6.641, 95% CrI [-10.627, -2.677]), while group_02 was higher than group_01 "
                "(16.766, [2.029, 32.145]). Crest factor was negatively associated with ratings (-6.265, [-12.443, -0.369]); "
                "RMS was positive but crossed zero, and spectral width was negative but also crossed zero. Participant and stimulus ICCs remained non-trivial, "
                "supporting the claim that listener and stimulus differences shape mix preference."
            ),
            "## C. Held-Out Mix Preference Prediction",
            (
                "Held-out prediction used the frozen 198-trial target set and the Phase 6H.1 set-based Top-1 tie policy. "
                "Without participant history, LLM Top-1 accuracy ranged from 20.7% to 24.7%, close to the 20% chance reference. "
                "With participant history, GPT-5.5 reached 34.3% Top-1 accuracy and Claude Sonnet 5 reached 35.9%; both were above chance after BH adjustment. "
                "Llama 3.1 70B and Centaur improved only slightly with history. Mean Spearman correlations followed the same pattern, with the largest LLM ranking gains for GPT-5.5 and Claude Sonnet 5."
            ),
            "## D. Effect of Participant History",
            (
                "Participant history had model-dependent value. GPT-5.5 improved by 11.6 percentage points in Top-1 accuracy, helping 48 examples and hurting 25, "
                "while Claude Sonnet 5 improved by 15.2 percentage points, helping 52 and hurting 22. These paired changes were supported by exact McNemar tests. "
                "Llama 3.1 70B and Centaur showed much smaller Top-1 gains of 1.0 and 1.5 percentage points, respectively. "
                "For models with numeric ratings, history also reduced MAE, most strongly for GPT-5.5."
            ),
            "## E. Comparison with the Mixed-Effects Predictive Model",
            (
                "The matched mixed-effects predictive baseline achieved 34.3% Top-1 accuracy, a mean Spearman correlation of 0.347, MAE of 23.00, and RMSE of 27.59. "
                "Personalised GPT-5.5 matched the mixed-effects Top-1 point estimate, and personalised Claude Sonnet 5 was numerically higher by 1.5 percentage points, "
                "but neither difference was detectable in paired Top-1 testing. The mixed-effects model remained the strongest ranking model, and it had lower RMSE than GPT-5.5 despite GPT-5.5 having a slightly lower MAE."
            ),
            "",
        ]
    )


def build_interpretation_limitations() -> str:
    return "\n".join(
        [
            "# Phase 6H.3 Interpretation and Limitations Notes",
            "",
            "- Treat the mixed-effects models as the central empirical analysis and the LLMs as held-out predictive probes, not as an overall model leaderboard.",
            "- Describe Top-1 accuracy as set-based preferred-mix credit under the frozen tie policy, because tied observed winners were retained rather than discarded.",
            "- Emphasise absolute performance as modest: even the strongest methods select the observed top mix on roughly one third of held-out trials.",
            "- Avoid claiming that participant history universally improves LLM prediction; the improvement is substantial for GPT-5.5 and Claude Sonnet 5, but small for Llama 3.1 70B and Centaur.",
            "- Report Centaur MAE/RMSE as not applicable because its outputs are native likelihood scores, not calibrated 0-100 ratings.",
            "- State that N=33 is the final usable dataset for this dissertation, while avoiding claims that it is conventionally powered for all effects.",
            "- Keep causal language out of the Results chapter; phrase model coefficients as associations with ratings.",
            "",
        ]
    )


def build_results_plan() -> str:
    return "\n".join(
        [
            "# Phase 6H.3 Dissertation Results Plan",
            "",
            "## VI. Results",
            "",
            "### A. Listening Study and Preference Variation",
            "Use the dataset paragraph, Main Table 1, and Figure 1. Lead with N=33, 990 ratings, 198 trials, the randomized five-mix design, and the empirical mixed-effects results.",
            "",
            "### B. Held-Out Mix Preference Prediction",
            "Use Main Table 2 and Figure 2. Present Top-1 accuracy first, then ranking and rating-error diagnostics. Mention the 20% chance reference and BH-adjusted chance tests.",
            "",
            "### C. Effect of Participant History",
            "Use Optional Table 3 in the main text if space permits; otherwise place it in the appendix and summarise the key paired effects in prose.",
            "",
            "### D. Comparison with Mixed-Effects Predictive Model",
            "Use the paired mixed-effects comparison results from Phase 6H.2B. Emphasise matched target examples, no baseline refit during scoring, and the distinction between Top-1, ranking, MAE, and RMSE.",
            "",
            "### Recommended Main Outputs",
            "- Main Table 1: `phase6h3_main_table_1_mixed_effects.md`",
            "- Main Table 2: `phase6h3_main_table_2_prediction_results.md`",
            "- Figure 1: `phase6h3_figure1_mixed_effects_coefficients.png`",
            "- Figure 2: `phase6h3_figure2_top1_accuracy.png`",
            "",
        ]
    )


def build_qc(repo_root: Path, output_dir: Path, tables: dict[str, str], figures: list[dict[str, str]], markdown: dict[str, str], sources: dict[str, Any]) -> dict[str, Any]:
    out = repo_root / output_dir
    required = [*tables.values(), *(figure["phase6h3_path"] for figure in figures), *markdown.values()]
    source_paths = [
        PHASE6H1_DIR / "phase6h1_data_collection_summary.json",
        PHASE6H1_DIR / "phase6h1_metric_protocol.json",
        PHASE6H1_DIR / "phase6h1_tie_policy.json",
        PHASE6H2B_DIR / "phase6h2b_table_a_central_mixed_effects.csv",
        PHASE6H2B_DIR / "phase6h2b_table_b_prediction_results.csv",
        PHASE6H2B_DIR / "phase6h2b_table_c_personalisation_effects.csv",
        PHASE6H2B_DIR / "phase6h2b_personalisation_effects.csv",
        PHASE6H2B_DIR / "phase6h2b_chance_tests.csv",
        PHASE6H2B_DIR / "phase6h2b_mixed_effects_llm_comparison.csv",
        PHASE6H2B_DIR / "phase6h2b_provenance_manifest.json",
        PHASE6H2B_DIR / "phase6h2b_qc_summary.json",
        PHASE6H2A_EMPIRICAL_DIR / "n33_empirical_results_inventory.json",
        PHASE6H2A_EMPIRICAL_DIR / "n33_primary_feature_coefficient_plot.png",
        PHASE6H2B_DIR / "phase6h2b_figure2_top1_accuracy.png",
        PHASE6H2B_DIR / "phase6h2b_figure3_personalisation_top1.png",
    ]
    gates = {
        "PHASE6H3_RESULTS_SYNTHESIS_COMPLETE": True,
        "NO_MODEL_INFERENCE_RERUN": sources["h2b_manifest"].get("prediction_rerun") is False,
        "NO_MIXED_EFFECTS_REFIT": sources["h2b_manifest"].get("mixed_effects_refit") is False,
        "FROZEN_TIE_POLICY_USED": sources["h1_tie_policy"].get("top1_policy") == "set_based_credit_for_top_ties",
        "DATASET_COUNTS_MATCH_FINAL_N33": sources["h1_summary"].get("participant_count") == 33
        and sources["h1_summary"].get("total_individual_mix_ratings") == 990
        and sources["h1_summary"].get("total_trials") == 198,
        "H2B_QC_COMPLETE": all(bool(value) for value in sources["h2b_qc"].get("gates", {}).values()),
        "ALL_DECLARED_OUTPUTS_EXIST": all((out / name).exists() and (out / name).stat().st_size > 0 for name in required),
    }
    return {
        "schema_version": "phase6h3_qc_summary_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_hashes": {str(path).replace("\\", "/"): sha256_file(repo_root / path) for path in source_paths},
        "output_files": required,
        "gates": gates,
        "passed": all(gates.values()),
        "notes": [
            "Phase 6H.3 formats frozen Phase 6H.1, 6H.2A, and 6H.2B artifacts only.",
            "No prompt generation, model inference, mixed-effects fitting, metric scoring, or dissertation document editing is performed.",
        ],
    }


def build_inventory(repo_root: Path, output_dir: Path, tables: dict[str, str], figures: list[dict[str, str]], markdown: dict[str, str], qc: dict[str, Any]) -> dict[str, Any]:
    out = repo_root / output_dir
    output_files = [*tables.values(), *(figure["phase6h3_path"] for figure in figures), *markdown.values(), "phase6h3_qc_report.md"]
    return {
        "schema_version": "phase6h3_final_results_inventory_v1",
        "created_at_utc": qc["created_at_utc"],
        "output_dir": str(output_dir).replace("\\", "/"),
        "purpose": "Dissertation-ready Results chapter synthesis from frozen Phase 6H artifacts.",
        "inputs": {
            "protocol": str(PHASE6H1_DIR).replace("\\", "/"),
            "empirical_mixed_effects": str(PHASE6H2A_EMPIRICAL_DIR).replace("\\", "/"),
            "final_scoring": str(PHASE6H2B_DIR).replace("\\", "/"),
        },
        "tables": tables,
        "figures": figures,
        "markdown_outputs": markdown,
        "output_hashes": {name: sha256_file(out / name) for name in output_files if (out / name).exists()},
        "qc": {"passed": qc["passed"], "gates": qc["gates"]},
    }


def write_qc_report(path: Path, qc: dict[str, Any], inventory: dict[str, Any]) -> None:
    lines = [
        "# Phase 6H.3 QC Report",
        "",
        f"- Output directory: `{inventory['output_dir']}`",
        f"- QC passed: `{str(qc['passed']).lower()}`",
        "",
        "## Gates",
    ]
    lines.extend(f"- {key}: `{str(value).lower()}`" for key, value in qc["gates"].items())
    lines.extend(["", "## Notes"])
    lines.extend(f"- {note}" for note in qc["notes"])
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty CSV: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown_table(path: Path, title: str, rows: list[dict[str, str]]) -> None:
    headers = list(rows[0].keys())
    lines = [title, "", "| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(escape_md(row[header]) for header in headers) + " |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def escape_md(value: str) -> str:
    return str(value).replace("|", "\\|")


def fmt_num(value: str, digits: int) -> str:
    if value in {"", "N/A", None}:
        return "N/A"
    return f"{float(value):.{digits}f}"


def fmt_optional(value: str, digits: int) -> str:
    return "N/A" if value in {"", "N/A", None} else fmt_num(value, digits)


def fmt_percent(value: str) -> str:
    return f"{100 * float(value):.1f}%"


def fmt_p(value: str) -> str:
    if value in {"", None}:
        return "N/A"
    p = float(value)
    if p < 0.001:
        return f"{p:.2e}"
    return f"{p:.3f}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    run_phase6h3_results_synthesis(REPO_ROOT)
