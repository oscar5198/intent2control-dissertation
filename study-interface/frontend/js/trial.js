"use strict";

/*
  Experimental trial controller.
  Development-only responsibilities:
  - Assign a temporary frontend group.
  - Generate and persist the ten-trial order.
  - Render the current unsubmitted trial.
  - Require playback, deliberate ratings, and non-whitespace comments.
  - Store submitted experimental responses separately from practice data.
*/

window.StudyApp = window.StudyApp || {};

window.StudyApp.trial = (function () {
  var currentConfig = null;
  var currentTrialOrder = null;
  var currentTrial = null;
  var currentTrialStartTimestamp = null;

  function initialiseExperimentalTrial(currentPage) {
    fetchJson("../config/stimuli.json").then(function (config) {
      var groupAssignment;
      var completedCount;

      currentConfig = config;
      groupAssignment = window.StudyApp.randomisation.assignGroup(config.groups);
      currentTrialOrder = window.StudyApp.randomisation.buildTrialOrder(config, groupAssignment);

      if (!groupAssignment || !currentTrialOrder) {
        showSummary("Study materials could not be prepared.");
        return;
      }

      completedCount = countCompletedTrials();
      if (completedCount >= config.trialGeneration.trialsPerParticipant) {
        if (window.StudyApp.navigation) {
          window.StudyApp.navigation.navigateTo("post-task.html");
        }
        return;
      }

      currentTrial = currentTrialOrder.trials[completedCount];
      window.StudyApp.storage.setItem("experimental.currentTrialIndex", currentTrial.trialIndex);
      currentTrialStartTimestamp = getStoredTrialStart(currentTrial.trialIndex) || recordTrialStart(currentTrial.trialIndex);
      renderCurrentTrial(currentPage, groupAssignment);
      initialiseDevelopmentTrialHelper(groupAssignment);
    }).catch(function () {
      showSummary("Study materials could not be loaded.");
    });
  }

  function renderCurrentTrial(currentPage, groupAssignment) {
    var scenario = findById(currentConfig.scenarios, currentTrial.scenarioId);
    var excerpt = findById(currentConfig.excerpts, currentTrial.excerptId);
    var trialCount = currentConfig.trialGeneration.trialsPerParticipant;
    var title = document.querySelector("[data-trial-title]");
    var scenarioTitle = document.querySelector("[data-trial-scenario-title]");
    var scenarioText = document.querySelector("[data-trial-scenario-text]");
    var excerptTitle = document.querySelector("[data-trial-excerpt-title]");
    var developmentNotice = document.querySelector("[data-trial-development-notice]");
    var versionContainer = document.querySelector("[data-trial-versions]");
    var backButton = document.querySelector("[data-trial-back]");
    var form = document.querySelector("[data-form='experimental-trial']");

    if (title) {
      title.textContent = "Listening Task " + currentTrial.trialIndex + " of " + trialCount;
    }
    if (scenarioTitle) {
      scenarioTitle.textContent = scenario ? getParticipantScenarioTitle(scenario) : "Scenario";
    }
    if (scenarioText) {
      scenarioText.textContent = scenario ? scenario.text : "";
    }
    if (excerptTitle) {
      excerptTitle.textContent = excerpt ? getParticipantExcerptTitle(excerpt.id) : "Music excerpt: Song";
    }
    if (developmentNotice) {
      developmentNotice.textContent = currentConfig.developmentLabel || "Experimental trial";
      if (currentTrialOrder.developmentCompatibilityWarning) {
        developmentNotice.textContent = developmentNotice.textContent + " " + currentTrialOrder.developmentCompatibilityWarning;
      }
      developmentNotice.classList.toggle("is-hidden", currentConfig.developmentOnly !== true);
    }
    if (backButton) {
      backButton.classList.toggle("is-hidden", currentTrial.trialIndex !== 1);
      backButton.disabled = currentTrial.trialIndex !== 1;
      backButton.setAttribute("aria-disabled", String(currentTrial.trialIndex !== 1));
    }

    if (versionContainer) {
      versionContainer.innerHTML = "";
      versionContainer.appendChild(createTrialAudioSection());
      versionContainer.appendChild(createTrialSharedRatingSection());
      versionContainer.appendChild(createTrialCommentSection());
      if (window.StudyApp.audio) {
        window.StudyApp.audio.setupAudioControls(versionContainer);
      }
    }

    restoreUnsavedResponses();
    updateCompletionState(false);
    updateProgress();

    if (form && form.getAttribute("data-trial-listener-attached") !== "true") {
      form.setAttribute("data-trial-listener-attached", "true");
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        handleSubmit(currentPage, groupAssignment);
      });
    }
  }

  function createTrialSection(headingText, introText, gridClassName, cards) {
    var section = document.createElement("section");
    var heading = document.createElement("h2");
    var grid = document.createElement("div");

    section.className = "trial-task-section";
    heading.textContent = headingText;
    section.appendChild(heading);

    if (introText) {
      var intro = document.createElement("p");
      intro.className = "trial-section-intro";
      intro.textContent = introText;
      section.appendChild(intro);
    }

    grid.className = "trial-control-grid " + gridClassName;
    cards.forEach(function (card) {
      grid.appendChild(card);
    });
    section.appendChild(grid);
    return section;
  }

  function createTrialAudioSection() {
    return createTrialSection("Listen to Version A, B, and C", "You may replay the versions and compare them in any order.", "trial-audio-grid", currentTrial.versionMappings.map(createAudioCard));
  }

  function createTrialSharedRatingSection() {
    var section = document.createElement("section");
    var heading = document.createElement("h2");
    var intro = document.createElement("p");
    var scale = createTrialPreferenceScale();

    section.className = "trial-task-section shared-rating-section";
    heading.textContent = "Place the versions on the preference scale";
    intro.className = "trial-section-intro";
    intro.textContent = "Drag, click, or use the keyboard to position Version A, Version B, and Version C on one shared 0-100 preference scale.";
    section.appendChild(heading);
    section.appendChild(intro);
    section.appendChild(scale);
    return section;
  }

  function createTrialCommentSection() {
    return createTrialSection("Explain your ratings", "Please briefly explain what influenced your preference for each mix.", "trial-comment-grid", currentTrial.versionMappings.map(createCommentCard));
  }

  function createTrialPreferenceScale() {
    var scale = document.createElement("div");
    var track = document.createElement("div");
    var markerLayer = document.createElement("div");
    var anchorRow = createRatingAnchorScale();
    var valueList = document.createElement("div");

    scale.className = "shared-preference-scale";
    track.className = "shared-preference-scale__track";
    markerLayer.className = "shared-preference-scale__markers";
    valueList.className = "shared-preference-scale__values";

    currentTrial.versionMappings.forEach(function (mapping, index) {
      markerLayer.appendChild(createTrialPreferenceMarker(mapping, index, track));
      valueList.appendChild(createTrialPreferenceValue(mapping));
    });

    track.addEventListener("click", function (event) {
      var selectedMarker = getSelectedPreferenceMarker(scale);
      if (event.target.closest && event.target.closest(".preference-marker")) {
        return;
      }
      if (!selectedMarker) {
        return;
      }
      playTrialMarkerAudio(selectedMarker.getAttribute("data-audio-id-target"));
      setTrialMarkerFromPointer(selectedMarker, track, event, true);
      selectedMarker.focus({ preventScroll: true });
    });

    track.appendChild(markerLayer);
    scale.appendChild(track);
    scale.appendChild(anchorRow);
    scale.appendChild(valueList);
    return scale;
  }

  function createTrialPreferenceMarker(mapping, index, track) {
    var marker = document.createElement("button");
    var versionId = getVersionId(mapping.neutralLabel);
    var audioId = getAudioId(currentTrial.trialIndex, versionId);
    var initialValue = getInitialPreferencePlaceholderValue(currentConfig.ratingScale, index);

    marker.type = "button";
    marker.id = versionId + "-rating";
    marker.name = versionId + "Rating";
    marker.className = "preference-marker preference-marker--" + (index + 1) + " preference-marker--unset";
    marker.tabIndex = 0;
    marker.textContent = mapping.neutralLabel.replace("Version ", "");
    marker.setAttribute("role", "slider");
    marker.setAttribute("data-trial-rating", versionId);
    marker.setAttribute("data-audio-id-target", audioId);
    marker.setAttribute("aria-label", "Preference rating for " + mapping.neutralLabel);
    marker.setAttribute("aria-valuemin", String(currentConfig.ratingScale.minimum));
    marker.setAttribute("aria-valuemax", String(currentConfig.ratingScale.maximum));
    marker.setAttribute("aria-valuenow", String(initialValue));
    marker.setAttribute("aria-valuetext", mapping.neutralLabel + " not set");
    marker.setAttribute("aria-describedby", versionId + "-rating-value " + versionId + "-rating-error");
    setPreferenceMarkerPosition(marker, initialValue);

    marker.addEventListener("pointerdown", function (event) {
      event.preventDefault();
      selectPreferenceMarker(marker);
      marker.focus({ preventScroll: true });
      playTrialMarkerAudio(audioId);
      setTrialMarkerFromPointer(marker, track, event, true);
      marker.setPointerCapture(event.pointerId);
    });
    marker.addEventListener("pointermove", function (event) {
      if (marker.hasPointerCapture && marker.hasPointerCapture(event.pointerId)) {
        setTrialMarkerFromPointer(marker, track, event, true);
      }
    });
    marker.addEventListener("pointerup", function (event) {
      if (marker.releasePointerCapture && marker.hasPointerCapture && marker.hasPointerCapture(event.pointerId)) {
        marker.releasePointerCapture(event.pointerId);
      }
    });
    marker.addEventListener("keydown", function (event) {
      selectPreferenceMarker(marker);
      handleTrialMarkerKeydown(marker, versionId, audioId, event);
    });
    marker.addEventListener("focus", function () {
      selectPreferenceMarker(marker);
    });

    return marker;
  }

  function getInitialPreferencePlaceholderValue(ratingScale, index) {
    var minimum = Number(ratingScale.minimum);
    var maximum = Number(ratingScale.maximum);
    var midpoint = Math.round((minimum + maximum) / 2);
    var spacing = Math.round((maximum - minimum) / 10);
    var offsets = [-spacing, 0, spacing];

    return Math.max(minimum, Math.min(maximum, midpoint + (offsets[index] || 0)));
  }

  function createTrialPreferenceValue(mapping) {
    var versionId = getVersionId(mapping.neutralLabel);
    var item = document.createElement("p");
    item.id = versionId + "-rating-value";
    item.className = "rating-value shared-preference-scale__value";
    item.textContent = mapping.neutralLabel + ": Not set";
    item.setAttribute("aria-live", "polite");
    return item;
  }

  function setTrialMarkerFromPointer(marker, track, event, touched) {
    var rect = track.getBoundingClientRect();
    var value = getPreferenceValueFromPointer(rect, event);
    var versionId = marker.getAttribute("data-trial-rating");
    setTrialMarkerRating(marker, versionId, value, touched);
  }

  function handleTrialMarkerKeydown(marker, versionId, audioId, event) {
    var handled = true;
    var currentValue = Number(marker.getAttribute("aria-valuenow") || 50);
    var nextValue = currentValue;

    if (event.key === "ArrowLeft" || event.key === "ArrowDown") {
      nextValue = currentValue - 1;
    } else if (event.key === "ArrowRight" || event.key === "ArrowUp") {
      nextValue = currentValue + 1;
    } else if (event.key === "PageDown") {
      nextValue = currentValue - 10;
    } else if (event.key === "PageUp") {
      nextValue = currentValue + 10;
    } else if (event.key === "Home") {
      nextValue = 0;
    } else if (event.key === "End") {
      nextValue = 100;
    } else if (event.key === " " || event.key === "Spacebar" || event.key === "Enter") {
      playTrialMarkerAudio(audioId);
      setTrialMarkerRating(marker, versionId, currentValue, true);
    } else {
      handled = false;
    }

    if (!handled) {
      return;
    }

    event.preventDefault();
    if (nextValue !== currentValue) {
      playTrialMarkerAudio(audioId);
      setTrialMarkerRating(marker, versionId, nextValue, true);
    }
  }

  function setTrialMarkerRating(marker, versionId, value, touched) {
    var boundedValue = Math.max(currentConfig.ratingScale.minimum, Math.min(currentConfig.ratingScale.maximum, Number(value)));
    setPreferenceMarkerPosition(marker, boundedValue);
    marker.classList.toggle("preference-marker--unset", touched !== true);
    marker.setAttribute("aria-valuenow", String(boundedValue));
    marker.setAttribute("aria-valuetext", touched ? String(boundedValue) : "Not set");
    marker.setAttribute("aria-invalid", "false");
    storeUnsavedRating(versionId, boundedValue, touched);
    updateRatingValue(versionId, boundedValue, touched);
    updateCompletionState(false);
  }

  function setPreferenceMarkerPosition(marker, value) {
    var boundedValue = Math.max(0, Math.min(100, Number(value)));
    marker.style.left = String(boundedValue) + "%";
    marker.style.bottom = String(boundedValue) + "%";
  }

  function getSelectedPreferenceMarker(scale) {
    return scale.querySelector(".preference-marker.is-selected");
  }

  function selectPreferenceMarker(marker) {
    var scale = marker.closest(".shared-preference-scale");
    if (!scale) {
      return false;
    }
    Array.prototype.slice.call(scale.querySelectorAll(".preference-marker")).forEach(function (item) {
      item.classList.toggle("is-selected", item === marker);
    });
    return true;
  }

  function getPreferenceValueFromPointer(rect, event) {
    if (rect.height > rect.width * 1.5) {
      return Math.round(((rect.bottom - event.clientY) / rect.height) * 100);
    }
    return rect.width > 0 ? Math.round(((event.clientX - rect.left) / rect.width) * 100) : 50;
  }

  function playTrialMarkerAudio(audioId) {
    setActivePreferenceMarker(audioId);
    if (window.StudyApp.audio) {
      window.StudyApp.audio.playAudioFromBeginning(audioId);
    }
  }

  function setActivePreferenceMarker(audioId) {
    Array.prototype.slice.call(document.querySelectorAll(".preference-marker, .version-card--audio")).forEach(function (element) {
      element.classList.toggle("is-playing", element.getAttribute("data-audio-id-target") === audioId || element.getAttribute("data-audio-card-id") === audioId);
    });
  }

  function createAudioCard(mapping) {
    var card = document.createElement("article");
    var heading = document.createElement("h3");
    var audio = document.createElement("audio");
    var source = document.createElement("source");
    var audioError = document.createElement("p");
    var playedStatus = document.createElement("p");
    var versionId = getVersionId(mapping.neutralLabel);
    var audioId = getAudioId(currentTrial.trialIndex, versionId);

    card.className = "version-card version-card--audio";
    card.setAttribute("data-audio-card-id", audioId);
    heading.textContent = mapping.neutralLabel;
    audio.className = "audio-control";
    audio.controls = true;
    audio.preload = "none";
    audio.setAttribute("aria-label", mapping.neutralLabel + " audio");
    audio.setAttribute("data-audio-id", audioId);
    source.src = "../" + mapping.audioPath;
    source.type = getAudioMimeType(mapping.audioPath);
    audio.appendChild(source);
    audio.addEventListener("playing", function () {
      if (window.StudyApp.audio) {
        window.StudyApp.audio.markAudioPlayed(audioId);
      }
      setActivePreferenceMarker(audioId);
      storeFirstPlayTimestamp(versionId);
      updateCompletionState(false);
    });
    audio.addEventListener("error", function () {
      setError(audioError, true);
      updateCompletionState(false);
    });
    audio.addEventListener("ended", function () {
      setActivePreferenceMarker(null);
    });

    audioError.id = versionId + "-audio-error";
    audioError.className = "validation-message is-hidden";
    audioError.textContent = "The audio for " + mapping.neutralLabel + " could not be loaded.";
    playedStatus.id = versionId + "-played-status";
    playedStatus.className = "field-help field-help--flush trial-played-status";
    playedStatus.textContent = "Required: play this version before submitting.";
    playedStatus.setAttribute("aria-live", "polite");

    card.appendChild(heading);
    card.appendChild(audio);
    card.appendChild(audioError);
    card.appendChild(playedStatus);
    return card;
  }

  function createRatingAnchorScale() {
    var scale = document.createElement("div");
    var numbers = ["0", "25", "50", "75", "100"];
    var labels = ["Bad", "Poor", "Fair", "Good", "Excellent"];

    scale.className = "rating-anchor-scale";
    scale.setAttribute("aria-hidden", "true");

    numbers.forEach(function (number, index) {
      var anchor = document.createElement("span");
      anchor.innerHTML = "<span class=\"rating-anchor-scale__number\">" + number + "</span><br>" + labels[index];
      scale.appendChild(anchor);
    });

    return scale;
  }

  function createCommentCard(mapping) {
    var card = document.createElement("article");
    var heading = document.createElement("h3");
    var commentLabel = document.createElement("label");
    var comment = document.createElement("textarea");
    var commentError = document.createElement("p");
    var versionId = getVersionId(mapping.neutralLabel);

    card.className = "version-card version-card--comment";
    heading.textContent = mapping.neutralLabel;
    commentLabel.className = "field__label";
    commentLabel.setAttribute("for", versionId + "-comment");
    commentLabel.textContent = "Required comment";
    comment.id = versionId + "-comment";
    comment.name = versionId + "Comment";
    comment.className = "textarea";
    comment.setAttribute("data-trial-comment", versionId);
    comment.setAttribute("aria-describedby", versionId + "-comment-error");
    comment.addEventListener("input", function () {
      storeUnsavedComment(versionId, comment.value);
      updateCompletionState(false);
    });
    commentError.id = versionId + "-comment-error";
    commentError.className = "validation-message is-hidden";
    commentError.textContent = "Provide a comment for " + mapping.neutralLabel + ".";

    card.appendChild(heading);
    card.appendChild(commentLabel);
    card.appendChild(comment);
    card.appendChild(commentError);
    return card;
  }

  function restoreUnsavedResponses() {
    var state = getUnsavedState();
    currentTrial.versionMappings.forEach(function (mapping) {
      var versionId = getVersionId(mapping.neutralLabel);
      var ratingControl = document.querySelector("[data-trial-rating='" + versionId + "']");
      var comment = document.querySelector("[data-trial-comment='" + versionId + "']");

      if (ratingControl && state.ratingTouched[versionId] === true && typeof state.ratings[versionId] !== "undefined") {
        setPreferenceMarkerPosition(ratingControl, state.ratings[versionId]);
        ratingControl.classList.remove("preference-marker--unset");
        ratingControl.setAttribute("aria-valuenow", String(state.ratings[versionId]));
        ratingControl.setAttribute("aria-valuetext", String(state.ratings[versionId]));
        updateRatingValue(versionId, state.ratings[versionId], true);
      }
      if (comment && typeof state.comments[versionId] === "string") {
        comment.value = state.comments[versionId];
      }
      updatePlayedStatus(versionId);
    });
  }

  function handleSubmit(currentPage, groupAssignment) {
    var validation = validateCurrentTrial(true);
    var summary = document.querySelector("[data-validation-summary]");
    var submissionTimestamp;
    var record;

    setError(summary, !validation.valid);
    if (!validation.valid) {
      if (summary) {
        summary.focus();
      }
      if (validation.firstInvalid) {
        validation.firstInvalid.focus();
      }
      return false;
    }

    submissionTimestamp = recordTrialSubmission(currentTrial.trialIndex);
    record = buildResponseRecord(groupAssignment, submissionTimestamp);
    saveSubmittedTrial(record);
    removeUnsavedState(currentTrial.trialIndex);

    if (window.StudyApp.timing) {
      window.StudyApp.timing.recordPageCompletion(currentPage);
    }

    if (countCompletedTrials() >= currentConfig.trialGeneration.trialsPerParticipant) {
      window.StudyApp.navigation.navigateTo("post-task.html");
      return true;
    }

    window.location.reload();
    return true;
  }

  function validateCurrentTrial(showErrors) {
    var state = getUnsavedState();
    var firstInvalid = null;

    currentTrial.versionMappings.forEach(function (mapping) {
      var versionId = getVersionId(mapping.neutralLabel);
      var audioPlayed = hasAudioPlayed(versionId);
      var ratingSet = state.ratingTouched[versionId] === true && typeof state.ratings[versionId] === "number";
      var commentValid = window.StudyApp.validation.validateRequiredComment(state.comments[versionId]);
      var audioError = document.getElementById(versionId + "-audio-required-error") || document.getElementById(versionId + "-played-status");
      var ratingInput = document.querySelector("[data-trial-rating='" + versionId + "']");
      var ratingError = document.getElementById(versionId + "-rating-error");
      var commentInput = document.querySelector("[data-trial-comment='" + versionId + "']");
      var commentError = document.getElementById(versionId + "-comment-error");
      var audioElement = document.querySelector("[data-audio-id='" + getAudioId(currentTrial.trialIndex, versionId) + "']");

      if (showErrors) {
        if (audioError) {
          audioError.textContent = audioPlayed ? "Played." : "Play " + mapping.neutralLabel + " before continuing.";
          audioError.classList.toggle("validation-message", !audioPlayed);
        }
        if (ratingInput) {
          ratingInput.setAttribute("aria-invalid", String(!ratingSet));
        }
        if (commentInput) {
          commentInput.setAttribute("aria-invalid", String(!commentValid));
        }
        setError(ratingError, !ratingSet);
        setError(commentError, !commentValid);
      }

      if (!audioPlayed && !firstInvalid) {
        firstInvalid = audioElement;
      }
      if (!ratingSet && !firstInvalid) {
        firstInvalid = ratingInput;
      }
      if (!commentValid && !firstInvalid) {
        firstInvalid = commentInput;
      }
    });

    return {
      valid: firstInvalid === null,
      firstInvalid: firstInvalid
    };
  }

  function updateCompletionState(showErrors) {
    var button = document.querySelector("[data-submit-trial]");
    var validation = currentTrial ? validateCurrentTrial(showErrors) : { valid: false };

    if (button) {
      button.disabled = false;
      button.setAttribute("aria-disabled", "false");
      button.setAttribute("data-ready-to-submit", String(validation.valid));
    }

    currentTrial.versionMappings.forEach(function (mapping) {
      updatePlayedStatus(getVersionId(mapping.neutralLabel));
    });

    return validation.valid;
  }

  function buildResponseRecord(groupAssignment, submissionTimestamp) {
    var scenario = findById(currentConfig.scenarios, currentTrial.scenarioId);
    var excerpt = findById(currentConfig.excerpts, currentTrial.excerptId);
    var state = getUnsavedState();
    var duration = window.StudyApp.timing.deriveDuration(currentTrialStartTimestamp, submissionTimestamp);

    return {
      groupId: groupAssignment.groupId,
      trialIndex: currentTrial.trialIndex,
      scenarioId: currentTrial.scenarioId,
      excerptId: currentTrial.excerptId,
      scenarioTitle: scenario ? getParticipantScenarioTitle(scenario) : null,
      neutralExcerptTitle: excerpt ? getParticipantExcerptTitle(excerpt.id) : null,
      trialStartTimestamp: currentTrialStartTimestamp,
      trialSubmissionTimestamp: submissionTimestamp,
      derivedTrialDurationMs: duration,
      versionResponses: currentTrial.versionMappings.map(function (mapping) {
        var versionId = getVersionId(mapping.neutralLabel);
        return {
          groupId: groupAssignment.groupId,
          trialIndex: currentTrial.trialIndex,
          scenarioId: currentTrial.scenarioId,
          excerptId: currentTrial.excerptId,
          neutralDisplayLabel: mapping.neutralLabel,
          actualMixId: mapping.actualMixId,
          audioPath: mapping.audioPath,
          rating: state.ratings[versionId],
          comment: state.comments[versionId],
          audioPlayed: hasAudioPlayed(versionId),
          firstPlayTimestamp: getFirstPlayTimestamp(versionId),
          trialStartTimestamp: currentTrialStartTimestamp,
          trialSubmissionTimestamp: submissionTimestamp,
          derivedTrialDurationMs: duration
        };
      })
    };
  }

  function saveSubmittedTrial(record) {
    var records = getSubmittedTrials();
    var existingIndex = records.findIndex(function (item) {
      return item.trialIndex === record.trialIndex;
    });

    if (existingIndex === -1) {
      records.push(record);
    } else {
      records[existingIndex] = record;
    }

    records.sort(function (first, second) {
      return first.trialIndex - second.trialIndex;
    });

    window.StudyApp.storage.setItem("experimental.submittedTrials", records);
    window.StudyApp.storage.setItem("experimental.completedTrialIndices", records.map(function (item) {
      return item.trialIndex;
    }));
  }

  function getSubmittedTrials() {
    var records = window.StudyApp.storage && window.StudyApp.storage.getItem("experimental.submittedTrials");
    return Array.isArray(records) ? records : [];
  }

  function initialiseDevelopmentTrialHelper(groupAssignment) {
    var panel = document.querySelector("[data-trial-development-helper]");
    var button = document.querySelector("[data-action='complete-development-trials']");
    var feedback = document.querySelector("[data-development-helper-feedback]");

    fetchJson("../config/study-config.json").then(function (studyConfig) {
      var enabled = Boolean(studyConfig.frontendDevelopmentMode === true && studyConfig.appEnvironment === "development");

      if (panel) {
        panel.classList.toggle("is-hidden", !enabled);
      }
      if (!enabled || !button) {
        return;
      }

      button.addEventListener("click", function () {
        if (button.getAttribute("data-confirmed") !== "true") {
          button.setAttribute("data-confirmed", "true");
          if (feedback) {
            feedback.textContent = "Select the button again to confirm creation of sample trial records.";
            setError(feedback, true);
          }
          return;
        }

        completeRemainingTrialsForDevelopment(groupAssignment);
        if (feedback) {
          feedback.textContent = "Sample trial records were created. Moving to the post-task questionnaire.";
          setError(feedback, true);
        }
        window.StudyApp.navigation.navigateTo("post-task.html");
      });
    }).catch(function () {
      if (panel) {
        panel.classList.add("is-hidden");
      }
    });
  }

  function completeRemainingTrialsForDevelopment(groupAssignment) {
    var records = getSubmittedTrials();
    var completedIndices = records.map(function (record) {
      return record.trialIndex;
    });
    var baseTime = Date.now();

    currentTrialOrder.trials.forEach(function (trial, index) {
      var startTimestamp;
      var submissionTimestamp;
      var scenario;
      var excerpt;
      var duration;
      var record;

      if (completedIndices.indexOf(trial.trialIndex) !== -1) {
        return;
      }

      startTimestamp = new Date(baseTime + index * 60000).toISOString();
      submissionTimestamp = new Date(baseTime + index * 60000 + 45000).toISOString();
      scenario = findById(currentConfig.scenarios, trial.scenarioId);
      excerpt = findById(currentConfig.excerpts, trial.excerptId);
      duration = window.StudyApp.timing.deriveDuration(startTimestamp, submissionTimestamp);

      record = {
        groupId: groupAssignment.groupId,
        trialIndex: trial.trialIndex,
        scenarioId: trial.scenarioId,
        excerptId: trial.excerptId,
        scenarioTitle: scenario ? getParticipantScenarioTitle(scenario) : null,
        neutralExcerptTitle: excerpt ? getParticipantExcerptTitle(excerpt.id) : null,
        trialStartTimestamp: startTimestamp,
        trialSubmissionTimestamp: submissionTimestamp,
        derivedTrialDurationMs: duration,
        developmentHelperGenerated: true,
        versionResponses: trial.versionMappings.map(function (mapping, mappingIndex) {
          var versionId = getVersionId(mapping.neutralLabel);
          var firstPlayTimestamp = new Date(Date.parse(startTimestamp) + mappingIndex * 3000).toISOString();
          window.StudyApp.storage.setItem(getFirstPlayKey(trial.trialIndex, versionId), firstPlayTimestamp);
          window.StudyApp.storage.setItem("audio.played." + getAudioId(trial.trialIndex, versionId), true);
          return {
            groupId: groupAssignment.groupId,
            trialIndex: trial.trialIndex,
            scenarioId: trial.scenarioId,
            excerptId: trial.excerptId,
            neutralDisplayLabel: mapping.neutralLabel,
            actualMixId: mapping.actualMixId,
            audioPath: mapping.audioPath,
            rating: 50 + mappingIndex,
            comment: "Sample comment for " + mapping.neutralLabel + ".",
            audioPlayed: true,
            firstPlayTimestamp: firstPlayTimestamp,
            trialStartTimestamp: startTimestamp,
            trialSubmissionTimestamp: submissionTimestamp,
            derivedTrialDurationMs: duration
          };
        })
      };

      records.push(record);
      window.StudyApp.storage.setItem("timing.trialStart." + getTrialId(trial.trialIndex), startTimestamp);
      window.StudyApp.storage.setItem("timing.trialSubmission." + getTrialId(trial.trialIndex), submissionTimestamp);
      removeUnsavedState(trial.trialIndex);
    });

    records.sort(function (first, second) {
      return first.trialIndex - second.trialIndex;
    });
    window.StudyApp.storage.setItem("experimental.submittedTrials", records);
    window.StudyApp.storage.setItem("experimental.completedTrialIndices", records.map(function (record) {
      return record.trialIndex;
    }));
  }

  function countCompletedTrials() {
    return getSubmittedTrials().length;
  }

  function hasCompletedAllTrials() {
    var trialOrder = window.StudyApp.storage && window.StudyApp.storage.getItem("experimental.trialOrder");
    var expectedCount = trialOrder && Array.isArray(trialOrder.trials) ? trialOrder.trials.length : 10;
    return countCompletedTrials() >= expectedCount;
  }

  function getUnsavedState() {
    var key = getUnsavedStateKey(currentTrial.trialIndex);
    var state = window.StudyApp.storage && window.StudyApp.storage.getItem(key);

    if (!state) {
      state = {
        ratings: {},
        ratingTouched: {},
        comments: {}
      };
    }

    return state;
  }

  function storeUnsavedRating(versionId, value, touched) {
    var state = getUnsavedState();
    state.ratings[versionId] = Number(value);
    state.ratingTouched[versionId] = touched === true;
    window.StudyApp.storage.setItem(getUnsavedStateKey(currentTrial.trialIndex), state);
    window.StudyApp.storage.setItem("experimental.currentResponses", state);
  }

  function storeUnsavedComment(versionId, value) {
    var state = getUnsavedState();
    state.comments[versionId] = value;
    window.StudyApp.storage.setItem(getUnsavedStateKey(currentTrial.trialIndex), state);
    window.StudyApp.storage.setItem("experimental.currentResponses", state);
  }

  function removeUnsavedState(trialIndex) {
    window.StudyApp.storage.removeItem(getUnsavedStateKey(trialIndex));
    window.StudyApp.storage.setItem("experimental.currentResponses", {});
  }

  function storeFirstPlayTimestamp(versionId) {
    var key = getFirstPlayKey(currentTrial.trialIndex, versionId);
    if (!window.StudyApp.storage.getItem(key)) {
      window.StudyApp.storage.setItem(key, window.StudyApp.timing.nowIsoString());
    }
    updatePlayedStatus(versionId);
  }

  function getFirstPlayTimestamp(versionId) {
    return window.StudyApp.storage.getItem(getFirstPlayKey(currentTrial.trialIndex, versionId));
  }

  function hasAudioPlayed(versionId) {
    return Boolean(window.StudyApp.audio && window.StudyApp.audio.hasAudioBeenPlayed(getAudioId(currentTrial.trialIndex, versionId)));
  }

  function updatePlayedStatus(versionId) {
    var status = document.getElementById(versionId + "-played-status");
    if (status) {
      status.textContent = hasAudioPlayed(versionId) ? "Played." : "Required: play this version before submitting.";
      status.classList.toggle("validation-message", !hasAudioPlayed(versionId));
    }
  }

  function updateRatingValue(versionId, value, touched) {
    var valueLabel = document.getElementById(versionId + "-rating-value");
    var label = getTrialVersionLabel(versionId);
    if (valueLabel) {
      valueLabel.textContent = label + ": " + (touched ? value : "Not set");
    }
  }

  function getTrialVersionLabel(versionId) {
    var marker = document.querySelector("[data-trial-rating='" + versionId + "']");
    return marker ? marker.getAttribute("aria-label").replace("Preference rating for ", "") : versionId;
  }

  function updateProgress() {
    var target = document.querySelector("[data-progress]");
    if (window.StudyApp.progress && target) {
      window.StudyApp.progress.renderProgress(target, window.StudyApp.progress.calculateProgress("trial", currentTrial.trialIndex));
    }
  }

  function showSummary(message) {
    var summary = document.querySelector("[data-validation-summary]");
    if (summary) {
      summary.textContent = message;
      setError(summary, true);
      summary.focus();
    }
  }

  function recordTrialStart(trialIndex) {
    if (window.StudyApp.timing) {
      return window.StudyApp.timing.recordTrialStart(getTrialId(trialIndex));
    }
    return null;
  }

  function recordTrialSubmission(trialIndex) {
    if (window.StudyApp.timing) {
      return window.StudyApp.timing.recordTrialSubmission(getTrialId(trialIndex));
    }
    return null;
  }

  function getStoredTrialStart(trialIndex) {
    return window.StudyApp.storage.getItem("timing.trialStart." + getTrialId(trialIndex));
  }

  function getTrialId(trialIndex) {
    return "experimental_trial_" + String(trialIndex).padStart(2, "0");
  }

  function getVersionId(label) {
    return label.toLowerCase().replace(/\s+/g, "_");
  }

  function getAudioId(trialIndex, versionId) {
    return "experimental.trial" + trialIndex + "." + versionId;
  }

  function getFirstPlayKey(trialIndex, versionId) {
    return "experimental.firstPlay.trial" + trialIndex + "." + versionId;
  }

  function getUnsavedStateKey(trialIndex) {
    return "experimental.unsavedTrial." + trialIndex;
  }

  function findById(items, id) {
    return items.find(function (item) {
      return item.id === id;
    });
  }

  function getParticipantScenarioTitle(scenario) {
    if (!scenario || !scenario.title) {
      return "Scenario";
    }

    return scenario.title.replace(/^(EDR|FM)-\d+\s*(?:-|Ã¢â‚¬â€œ|Ã¢â‚¬â€|ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â)\s*/i, "").trim();
  }

  function getParticipantExcerptTitle(excerptId) {
    var mapping = window.StudyApp.storage && window.StudyApp.storage.getItem("experimental.excerptLabelMapping");
    var label = mapping && mapping.labelsByExcerptId ? mapping.labelsByExcerptId[excerptId] : null;
    return "Music excerpt: " + (label || "Song");
  }

  function setError(errorElement, show) {
    if (!errorElement) {
      return;
    }

    errorElement.classList.toggle("is-hidden", !show);
  }

  function fetchJson(path) {
    return fetch(path, { cache: "no-store" }).then(function (response) {
      if (!response.ok) {
        throw new Error("Could not load " + path);
      }
      return response.json();
    });
  }

  function getAudioMimeType(path) {
    if (path.indexOf(".wav") !== -1) {
      return "audio/wav";
    }
    if (path.indexOf(".ogg") !== -1) {
      return "audio/ogg";
    }
    return "audio/mpeg";
  }

  return {
    initialiseExperimentalTrial: initialiseExperimentalTrial,
    countCompletedTrials: countCompletedTrials,
    hasCompletedAllTrials: hasCompletedAllTrials,
    getSubmittedTrials: getSubmittedTrials,
    completeRemainingTrialsForDevelopment: completeRemainingTrialsForDevelopment
  };
}());
