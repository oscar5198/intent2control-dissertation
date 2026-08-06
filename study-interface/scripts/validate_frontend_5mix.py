import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "study-interface" / "frontend-5mix"


def fail(message):
    raise AssertionError(message)


def read_text(path):
    return path.read_text(encoding="utf-8")


def function_body(source, name):
    match = re.search(r"function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{", source)
    if not match:
        fail(f"Missing function {name}")
    start = match.end()
    depth = 1
    index = start
    while index < len(source) and depth:
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        index += 1
    return source[start:index - 1]


def main():
    stimuli = json.loads(read_text(FRONTEND / "config" / "stimuli.json"))
    study_config = json.loads(read_text(FRONTEND / "config" / "study-config.json"))
    practice = json.loads(read_text(FRONTEND / "config" / "practice.json"))
    screening = json.loads(read_text(FRONTEND / "config" / "screening.json"))
    labels = stimuli.get("versionLabels")
    required_audio = set()

    def add_required_audio(relative_path):
        if relative_path and relative_path.endswith(".wav"):
            required_audio.add(str((FRONTEND / relative_path).resolve()))

    if labels != ["Version A", "Version B", "Version C", "Version D", "Version E"]:
        fail(f"Unexpected main-study labels: {labels}")
    if stimuli["trialGeneration"]["versionsPerTrial"] != 5:
        fail("stimuli.json versionsPerTrial must be 5")
    if stimuli["trialGeneration"]["ratingsPerParticipant"] != 30:
        fail("stimuli.json ratingsPerParticipant must be 30")
    if study_config["mixesPerTrial"] != 5 or study_config["ratingsPerParticipant"] != 30:
        fail("study-config.json must declare 5 mixes and 30 ratings")
    practice_versions = practice.get("versions", [])
    if len(practice_versions) != 5:
        fail("practice.json must contain five practice versions")
    if [version.get("label") for version in practice_versions] != ["Version A", "Version B", "Version C", "Version D", "Version E"]:
        fail("practice versions must be labelled Version A-Version E")
    for version in practice_versions:
        add_required_audio(version["audioPath"])
        audio_path = FRONTEND / version["audioPath"]
        if not audio_path.exists() or audio_path.stat().st_size <= 0:
            fail(f"Missing or empty practice audio asset: {audio_path}")
    for segment in screening.get("segments", []):
        add_required_audio(segment.get("matchAudioPath"))
        add_required_audio(segment.get("matchDuplicateAudioPath"))
        add_required_audio(segment.get("nonMatchAudioPath"))
    add_required_audio(study_config.get("setupTestAudio", {}).get("audioPath"))

    excerpts = stimuli.get("excerpts", [])
    if len(excerpts) != 4:
        fail(f"Expected 4 excerpts, found {len(excerpts)}")
    if any(excerpt["finalExcerptName"] == "Red To Blue" for excerpt in excerpts):
        fail("Red To Blue must not be an active five-mix excerpt")
    if "I'd Like To Know" not in {excerpt["finalExcerptName"] for excerpt in excerpts}:
        fail("I'd Like To Know must be the active replacement song")

    for excerpt in excerpts:
        mixes = excerpt.get("mixes", [])
        if len(mixes) != 5:
            fail(f"{excerpt['id']} has {len(mixes)} mixes")
        seen_mix_ids = set()
        seen_stimulus_ids = set()
        for mix in mixes:
            add_required_audio(mix["audioPath"])
            seen_mix_ids.add(mix["actualMixId"])
            seen_stimulus_ids.add(mix["stimulusId"])
            audio_path = FRONTEND / mix["audioPath"]
            if not audio_path.exists():
                fail(f"Missing audio asset: {audio_path}")
        if len(seen_mix_ids) != 5 or len(seen_stimulus_ids) != 5:
            fail(f"{excerpt['id']} has duplicate mix or stimulus IDs")

    active_main_audio = {
        str((FRONTEND / mix["audioPath"]).resolve())
        for excerpt in excerpts
        for mix in excerpt.get("mixes", [])
    }
    actual_main_audio = {
        str(path.resolve())
        for path in (FRONTEND / "assets" / "audio" / "study-stimuli" / "main-study").rglob("*.wav")
    }
    if len(active_main_audio) != 20 or len(actual_main_audio) != 20 or active_main_audio != actual_main_audio:
        fail("Main-study audio folder must contain exactly the 20 active configured WAV files")

    actual_frontend_audio = {
        str(path.resolve())
        for path in (FRONTEND / "assets" / "audio").rglob("*.wav")
    }
    if len(required_audio) != 32 or required_audio != actual_frontend_audio:
        fail("frontend-5mix must contain exactly the 32 configured WAV files and no obsolete donor audio")

    index_html = read_text(FRONTEND / "index.html")
    submission_js = read_text(FRONTEND / "js" / "netlify-submission.js")
    storage_js = read_text(FRONTEND / "js" / "storage.js")
    app_js = read_text(FRONTEND / "js" / "app.js")
    trial_html = read_text(FRONTEND / "pages" / "trial.html")

    if "listening-study-5mix" not in index_html or "listening-study-6mix" in index_html:
        fail("index.html Netlify form must use listening-study-5mix only")
    if "five_mix_netlify_forms_v1" not in submission_js or "listening-study-6mix" in submission_js:
        fail("netlify-submission.js must use the five-mix form/schema")
    if "intent2control.study.5mix.v1." not in storage_js:
        fail("storage namespace must be five-mix-specific")
    if "audio.played.practice.practice_version_d" not in storage_js or "audio.played.practice.practice_version_e" not in storage_js:
        fail("storage documented keys must include practice Versions D and E")
    if "Version F" in trial_html or "all six" in trial_html.lower():
        fail("trial.html still contains six-version participant text")

    if 'localPreviewSubmissionUnavailable' not in submission_js or 'isLocalPreviewHost' not in submission_js:
        fail("netlify-submission.js must explicitly guard local preview submissions")
    if "This local preview cannot save to Netlify Forms" not in app_js:
        fail("final submit must show a clear local-preview Netlify Forms message")

    practice_comment_body = function_body(app_js, "createPracticeCommentSection")
    if 'classList.add("is-hidden")' in practice_comment_body:
        fail("practice comparative comment section must be visible immediately")
    practice_update_body = function_body(app_js, "updatePracticeCompletionState")
    if 'classList.toggle("is-hidden"' in practice_update_body:
        fail("practice completion update must not hide the comment section")
    trial_js = read_text(FRONTEND / "js" / "trial.js")
    trial_comment_body = function_body(trial_js, "createTrialCommentSection")
    if 'classList.add("is-hidden")' in trial_comment_body:
        fail("main-study comparative comment section must be visible immediately")

    print("frontend-5mix validation passed")


if __name__ == "__main__":
    main()
