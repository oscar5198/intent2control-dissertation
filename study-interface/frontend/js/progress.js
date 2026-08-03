"use strict";

/*
  Progress responsibility placeholders.
  Responsibilities:
  - Calculate progress by study stage.
  - Render progress labels.
  - Render progress bar state later.
*/

window.StudyApp = window.StudyApp || {};

window.StudyApp.progress = (function () {
  var stages = {
    "landing": { label: "Welcome", index: 1, total: 12, value: 8 },
    "study-information-consent": { label: "Participant Information Sheet and Consent Form", index: 2, total: 12, value: 17 },
    "participant-information-deprecated": { label: "Redirecting", index: 2, total: 12, value: 17 },
    "consent-deprecated": { label: "Redirecting", index: 2, total: 12, value: 17 },
    "listening-setup": { label: "Listening setup", index: 3, total: 12, value: 25 },
    "screening": { label: "Pre-Study Listening Task", index: 4, total: 12, value: 33 },
    "instructions": { label: "Instructions", index: 5, total: 12, value: 42 },
    "practice": { label: "Practice trial", index: 6, total: 12, value: 50 },
    "main-study": { label: "Main Study", index: 7, total: 12, value: 58 },
    "trial": { label: "Main Study", index: 8, total: 12, value: 67 },
    "post-task": { label: "Post-task questionnaire", index: 9, total: 12, value: 75 },
    "demographics": { label: "Demographic questionnaire", index: 10, total: 12, value: 83 },
    "review": { label: "Review and final submission", index: 11, total: 12, value: 92 },
    "completion": { label: "Completion", index: 12, total: 12, value: 100 }
  };

  function calculateProgress(pageId, trialIndex) {
    var resolvedTrialIndex;

    if (pageId === "trial") {
      resolvedTrialIndex = resolveTrialIndex(trialIndex);
      return {
        label: "Main Study",
        detail: "Listening Task " + resolvedTrialIndex + " of 10",
        index: 8,
        total: 12,
        value: Math.min(74, 67 + Math.round((resolvedTrialIndex - 1) * (7 / 9)))
      };
    }

    return stages[pageId] || { label: "Study", index: 0, total: 12, value: 0 };
  }

  function getProgressLabel(pageId, trialIndex) {
    void trialIndex;
    return calculateProgress(pageId).label;
  }

  function prepareProgress(pageId) {
    var target = document.querySelector("[data-progress]");
    if (!target) {
      return false;
    }

    return renderProgress(target, calculateProgress(pageId));
  }

  function renderProgress(target, progressState) {
    if (!target || !progressState) {
      return false;
    }

    target.innerHTML = "";

    var label = document.createElement("div");
    label.className = "progress__label";
    label.innerHTML = "<span>" + progressState.label + (progressState.detail ? ": " + progressState.detail : "") + "</span><span>Step " + progressState.index + " of " + progressState.total + "</span>";

    var screenReaderText = document.createElement("span");
    screenReaderText.className = "visually-hidden";
    screenReaderText.textContent = "Current stage: " + progressState.label + (progressState.detail ? ", " + progressState.detail : "") + ", step " + progressState.index + " of " + progressState.total + ".";

    var track = document.createElement("div");
    track.className = "progress__track";
    track.setAttribute("aria-hidden", "true");

    var bar = document.createElement("div");
    bar.className = "progress__bar";
    bar.style.setProperty("--progress-value", progressState.value + "%");

    track.appendChild(bar);
    target.appendChild(label);
    target.appendChild(screenReaderText);
    target.appendChild(track);

    return true;
  }

  function resolveTrialIndex(trialIndex) {
    var stored;

    if (typeof trialIndex === "number" && trialIndex >= 1) {
      return Math.min(trialIndex, 10);
    }

    stored = window.StudyApp.storage && window.StudyApp.storage.getItem("experimental.currentTrialIndex");
    if (typeof stored === "number" && stored >= 1) {
      return Math.min(stored, 10);
    }

    return 1;
  }

  return {
    calculateProgress: calculateProgress,
    getProgressLabel: getProgressLabel,
    prepareProgress: prepareProgress,
    renderProgress: renderProgress
  };
}());
