import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "study-interface" / "frontend-5mix"


def run_validation_helper(cases):
    script = f"""
const fs = require("fs");
const vm = require("vm");
const sandbox = {{
  window: {{ StudyApp: {{}} }},
  document: {{}}
}};
sandbox.window.window = sandbox.window;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("study-interface/frontend-5mix/js/validation.js", "utf8"), sandbox);
const cases = {json.dumps(cases)};
const results = cases.map((item) => sandbox.window.StudyApp.validation.buildCompletionFeedback(item));
console.log(JSON.stringify(results));
"""
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


def test_practice_completion_feedback_cases():
    cases = [
        {"missingPlaybackLabels": [], "missingRatingLabels": [], "commentValid": True},
        {"missingPlaybackLabels": ["D"], "missingRatingLabels": [], "commentValid": True},
        {"missingPlaybackLabels": ["B", "E"], "missingRatingLabels": [], "commentValid": True},
        {"missingPlaybackLabels": [], "missingRatingLabels": ["C"], "commentValid": True},
        {"missingPlaybackLabels": [], "missingRatingLabels": ["A", "D"], "commentValid": True},
        {"missingPlaybackLabels": [], "missingRatingLabels": [], "commentValid": False},
        {"missingPlaybackLabels": ["E"], "missingRatingLabels": ["B", "E"], "commentValid": False},
    ]

    assert run_validation_helper(cases) == [
        "",
        "Before continuing, please listen to Version D.",
        "Before continuing, please listen to Versions B and E.",
        "Before continuing, please rate Version C.",
        "Before continuing, please rate Versions A and D.",
        "Before continuing, please enter a comment explaining your ratings.",
        "Before continuing, please listen to Version E, rate Versions B and E, and enter a comment explaining your ratings.",
    ]


def test_practice_is_configured_for_five_versions_not_three():
    practice = json.loads((FRONTEND / "config" / "practice.json").read_text(encoding="utf-8"))
    labels = [version["label"] for version in practice["versions"]]
    ids = [version["id"] for version in practice["versions"]]

    assert labels == ["Version A", "Version B", "Version C", "Version D", "Version E"]
    assert ids == [
        "practice_version_a",
        "practice_version_b",
        "practice_version_c",
        "practice_version_d",
        "practice_version_e",
    ]
    assert "Versions A-E" in practice["commentPrompt"]


def test_practice_and_main_pages_have_accessible_completion_feedback_regions():
    practice_html = (FRONTEND / "pages" / "practice.html").read_text(encoding="utf-8")
    trial_html = (FRONTEND / "pages" / "trial.html").read_text(encoding="utf-8")

    assert 'data-practice-completion-feedback' in practice_html
    assert 'data-trial-completion-feedback' in trial_html
    assert 'aria-live="polite"' in practice_html
    assert 'aria-live="polite"' in trial_html
    assert 'role="status"' in practice_html
    assert 'role="status"' in trial_html


def test_no_three_version_practice_completion_assumption_remains():
    app_js = (FRONTEND / "js" / "app.js").read_text(encoding="utf-8")
    storage_js = (FRONTEND / "js" / "storage.js").read_text(encoding="utf-8")

    assert "practice_version_d" in app_js or "config.versions.forEach" in app_js
    assert "practice_version_e" in app_js or "config.versions.forEach" in app_js
    assert "audio.played.practice.practice_version_d" in storage_js
    assert "audio.played.practice.practice_version_e" in storage_js
    assert "Versions A-C" not in app_js
    assert "Versions A-C" not in (FRONTEND / "config" / "practice.json").read_text(encoding="utf-8")


def test_main_study_feedback_uses_same_participant_facing_helper():
    trial_js = (FRONTEND / "js" / "trial.js").read_text(encoding="utf-8")

    assert "buildCompletionFeedback" in trial_js
    assert "data-trial-completion-feedback" in (FRONTEND / "pages" / "trial.html").read_text(encoding="utf-8")
    assert "actualMixId" not in trial_js[trial_js.find("function buildTrialValidationMessage"):trial_js.find("function formatVersionList")]
