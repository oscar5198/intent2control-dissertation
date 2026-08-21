from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

CURRENT_INPUTS = {
    "participants": REPO_ROOT / "data" / "processed" / "participants_final.csv",
    "ratings": REPO_ROOT / "data" / "processed" / "ratings_final.csv",
    "trial_preferences": REPO_ROOT / "data" / "processed" / "trial_preferences_final.csv",
    "features": REPO_ROOT / "statistical-modeling" / "outputs" / "acoustic-features" / "final_20_stimulus_feature_table.csv",
    "stimuli_config": REPO_ROOT / "study-interface" / "frontend-5mix" / "config" / "stimuli.json",
    "heldout_split": REPO_ROOT / "statistical-modeling" / "outputs" / "heldout-evaluation" / "mcmc-evaluation" / "heldout_split_manifest.csv",
}

PROMPT_DATA_DIR = REPO_ROOT / "llm-experiments" / "outputs" / "final" / "prompt-data"
FINAL_PROMPT_DATASET = PROMPT_DATA_DIR / "final_prompt_dataset.jsonl"
HELDOUT_EXAMPLES = PROMPT_DATA_DIR / "heldout_prediction_examples.jsonl"
HELDOUT_TARGETS = PROMPT_DATA_DIR / "heldout_targets.csv"
ANALYSIS_READY = PROMPT_DATA_DIR / "analysis_ready_ratings.csv"
LEAKAGE_AUDIT = PROMPT_DATA_DIR / "leakage_audit.json"
READINESS_GATE = PROMPT_DATA_DIR / "readiness_gate.json"
PROMPT_MANIFEST = PROMPT_DATA_DIR / "prompt_data_manifest.json"

EXPECTED = {
    "participant_count": 33,
    "rating_rows": 990,
    "trial_count": 198,
    "feature_rows": 20,
    "prompt_objects": 396,
    "prediction_examples": 198,
    "heldout_targets": 198,
    "condition_counts": {"non_history": 198, "personalised_history": 198},
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the retained final LLM prompt-data package against the "
            "current curated dissertation inputs. The default mode is "
            "non-destructive and does not call model APIs."
        )
    )
    parser.add_argument(
        "--write-manifest",
        action="store_true",
        help="Update prompt_data_manifest.json with current retained-source paths and validation hashes.",
    )
    args = parser.parse_args()

    report = validate_final_prompt_package(write_manifest=args.write_manifest)
    print(f"FINAL_PROMPT_DATA_READY={str(report['ready']).lower()}")
    if report["counts"]:
        print(f"participants={report['counts']['participants']}")
        print(f"ratings={report['counts']['ratings']}")
        print(f"trials={report['counts']['trial_preferences']}")
        print(f"prompt_objects={report['counts']['prompt_objects']}")
        print(f"prediction_examples={report['counts']['prediction_examples']}")
        print(f"heldout_targets={report['counts']['heldout_targets']}")
    if report["failures"]:
        print("Failures:")
        for failure in report["failures"]:
            print(f"- {failure}")
        return 1
    return 0


def validate_final_prompt_package(write_manifest: bool = False) -> dict[str, Any]:
    failures: list[str] = []
    required = [*CURRENT_INPUTS.values(), FINAL_PROMPT_DATASET, HELDOUT_EXAMPLES, HELDOUT_TARGETS, ANALYSIS_READY, LEAKAGE_AUDIT, READINESS_GATE]
    missing = [relpath(path) for path in required if not path.exists()]
    failures.extend(f"Missing required file: {path}" for path in missing)
    if missing:
        return {"ready": False, "failures": failures, "counts": {}}

    participants = read_csv(CURRENT_INPUTS["participants"])
    ratings = read_csv(CURRENT_INPUTS["ratings"])
    trial_preferences = read_csv(CURRENT_INPUTS["trial_preferences"])
    features = read_csv(CURRENT_INPUTS["features"])
    heldout_split = read_csv(CURRENT_INPUTS["heldout_split"])
    prompt_objects = read_jsonl(FINAL_PROMPT_DATASET)
    examples = read_jsonl(HELDOUT_EXAMPLES)
    heldout_targets = read_csv(HELDOUT_TARGETS)

    counts = {
        "participants": len(participants),
        "ratings": len(ratings),
        "trial_preferences": len(trial_preferences),
        "features": len(features),
        "heldout_split_rows": len(heldout_split),
        "prompt_objects": len(prompt_objects),
        "prediction_examples": len(examples),
        "heldout_targets": len(heldout_targets),
    }
    expected_pairs = {
        "participants": EXPECTED["participant_count"],
        "ratings": EXPECTED["rating_rows"],
        "trial_preferences": EXPECTED["trial_count"],
        "features": EXPECTED["feature_rows"],
        "heldout_split_rows": EXPECTED["trial_count"],
        "prompt_objects": EXPECTED["prompt_objects"],
        "prediction_examples": EXPECTED["prediction_examples"],
        "heldout_targets": EXPECTED["heldout_targets"],
    }
    for key, expected in expected_pairs.items():
        if counts[key] != expected:
            failures.append(f"{key} count {counts[key]} != expected {expected}")

    condition_counts = Counter(str(obj.get("condition")) for obj in prompt_objects)
    if dict(condition_counts) != EXPECTED["condition_counts"]:
        failures.append(f"condition counts {dict(condition_counts)} != expected {EXPECTED['condition_counts']}")

    target_ids = {row["trial_id"] for row in trial_preferences}
    example_target_ids = {extract_target_trial_id(example) for example in examples}
    prompt_target_ids = {obj.get("pipeline_metadata", {}).get("target_trial_id", "") for obj in prompt_objects}
    if example_target_ids != target_ids:
        failures.append("heldout prediction examples do not cover the same trial IDs as trial_preferences_final.csv")
    if prompt_target_ids != target_ids:
        failures.append("prompt data objects do not cover the same target trial IDs as trial_preferences_final.csv")

    for obj in prompt_objects:
        metadata = obj.get("pipeline_metadata", {})
        if metadata.get("model_input_contains_hidden_answers") is not False:
            failures.append(f"{obj.get('condition_object_id')}: hidden-answer audit is not false")
        if metadata.get("model_input_contains_underlying_candidate_ids_or_paths") is not False:
            failures.append(f"{obj.get('condition_object_id')}: provenance leakage audit is not false")
        payload = json.dumps(obj.get("model_input", {}), sort_keys=True, ensure_ascii=False)
        if '"z_SI"' in payload:
            failures.append(f"{obj.get('condition_object_id')}: z_SI appears in model_input")

    report = {
        "schema_version": "final_prompt_data_validation_v1",
        "ready": not failures,
        "counts": counts,
        "condition_counts": dict(condition_counts),
        "inputs": {key: artifact(path) for key, path in CURRENT_INPUTS.items()},
        "outputs": {
            "analysis_ready": artifact(ANALYSIS_READY),
            "heldout_prediction_examples": artifact(HELDOUT_EXAMPLES),
            "heldout_targets": artifact(HELDOUT_TARGETS),
            "final_prompt_dataset": artifact(FINAL_PROMPT_DATASET),
            "leakage_audit": artifact(LEAKAGE_AUDIT),
            "readiness_gate": artifact(READINESS_GATE),
        },
        "failures": failures,
        "note": "This validates the retained final prompt-data package from current curated repository inputs. It does not call APIs, regenerate predictions, or require the private raw Netlify workbook.",
    }
    if write_manifest and not failures:
        write_manifest_file(report)
    return report


def write_manifest_file(report: dict[str, Any]) -> None:
    existing = load_json(PROMPT_MANIFEST) if PROMPT_MANIFEST.exists() else {}
    existing["current_reproducibility_sources"] = {
        "schema_version": "current_prompt_data_sources_v1",
        "validation_entrypoint": relpath(Path(__file__)),
        "private_raw_workbook_required_for_current_reproducibility": False,
        "current_inputs": report["inputs"],
        "current_outputs": report["outputs"],
        "validation_counts": report["counts"],
        "condition_counts": report["condition_counts"],
    }
    PROMPT_MANIFEST.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def extract_target_trial_id(example: dict[str, Any]) -> str:
    if "input_data" in example:
        return str(example["input_data"]["target"]["trial_id"])
    if "target" in example:
        return str(example["target"]["trial_id"])
    truth = example.get("ground_truth", {})
    return str(truth.get("trial_id", ""))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact(path: Path) -> dict[str, Any]:
    return {
        "path": relpath(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def relpath(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


if __name__ == "__main__":
    raise SystemExit(main())
