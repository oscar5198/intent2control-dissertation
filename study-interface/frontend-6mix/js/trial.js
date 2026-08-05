"use strict";

/*
  Experimental trial controller.
  Development-only responsibilities:
  - Assign a temporary frontend group.
  - Generate and persist the configured trial order.
  - Render the current unsubmitted trial.
  - Require playback, deliberate ratings, and one non-whitespace comparative comment.
  - Store submitted experimental responses separately from practice data.
*/

window.StudyApp = window.StudyApp || {};

window.StudyApp.trial = (function () {
  var maxTrialCommentLength = 1000;
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

      if (currentTrialOrder.developmentCompatibilityWarning) {
        showSummary(currentTrialOrder.developmentCompatibilityWarning);
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

  function createTrialSharedRatingSection() {
    var section = document.createElement("section");
    var header = document.createElement("div");
    var heading = document.createElement("h2");
    var intro = document.createElement("p");
    var scale = createTrialPreferenceScale();
    var audioBank = createTrialAudioBank();

    section.className = "trial-task-section shared-rating-section";
    header.className = "shared-rating-section__header";
    heading.textContent = "Place the versions on the preference scale";
    intro.className = "trial-section-intro";
    intro.appendChild(document.createTextNode("Drag each marker to set its preference rating. "));
    intro.appendChild(createStrongText("Click or tap a marker to play that version."));
    header.appendChild(heading);
    header.appendChild(createSharedStopAudioControl("trial"));
    section.appendChild(header);
    section.appendChild(intro);
    section.appendChild(audioBank);
    section.appendChild(scale);
    return section;
  }

  function createTrialCommentSection() {
    var section = document.createElement("section");
    var heading = document.createElement("h2");
    var intro = document.createElement("p");
    var field = createComparativeCommentField();

    section.className = "trial-task-section";
    section.classList.add("is-hidden");
    section.setAttribute("data-trial-comparative-comment-section", "");
    heading.textContent = "Explain your ratings";
    intro.className = "trial-section-intro";
    intro.textContent = getComparativeCommentPrompt(currentTrial.versionMappings);
    section.appendChild(heading);
    section.appendChild(intro);
    section.appendChild(field);
    return section;
  }

  function createTrialPreferenceScale() {
    var scale = document.createElement("div");
    var track = document.createElement("div");
    var markerLayer = document.createElement("div");
    var anchorRow = createRatingAnchorScale();

    scale.className = "shared-preference-scale";
    track.className = "shared-preference-scale__track";
    markerLayer.className = "shared-preference-scale__markers";
    markerLayer.setAttribute("data-marker-count", String(currentTrial.versionMappings.length));

    currentTrial.versionMappings.forEach(function (mapping, index) {
      markerLayer.appendChild(createTrialPreferenceMarker(mapping, index, track));
    });

    track.appendChild(markerLayer);
    scale.appendChild(track);
    scale.appendChild(anchorRow);
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
    marker.tabIndex = -1;
    marker.textContent = mapping.neutralLabel.replace("Version ", "");
    marker.setAttribute("aria-label", mapping.neutralLabel + " audio marker. Drag to set the rating. Click or tap to play.");
    marker.setAttribute("data-version-display-label", mapping.neutralLabel);
    marker.setAttribute("data-trial-rating", versionId);
    marker.setAttribute("data-audio-id-target", audioId);
    setPreferenceMarkerPosition(marker, initialValue);

    attachPreferenceMarkerPointerHandlers(marker, track, function () {
      playTrialMarkerAudio(audioId);
    }, function (event) {
      setTrialMarkerFromPointer(marker, track, event, true);
    });
    return marker;
  }

  function getInitialPreferencePlaceholderValue(ratingScale, index) {
    var minimum = Number(ratingScale.minimum);
    var maximum = Number(ratingScale.maximum);
    var midpoint = Math.round((minimum + maximum) / 2);
    var markerCount = currentTrial && Array.isArray(currentTrial.versionMappings) ? currentTrial.versionMappings.length : 1;
    var spacing = Math.max(4, Math.round((maximum - minimum) / 12.5));
    var offset = (index - ((markerCount - 1) / 2)) * spacing;

    if (markerCount <= 1) {
      return midpoint;
    }

    return Math.max(minimum, Math.min(maximum, Math.round(midpoint + offset)));
  }

  function setTrialMarkerFromPointer(marker, track, event, touched) {
    var rect = track.getBoundingClientRect();
    var value = getPreferenceValueFromPointer(rect, event);
    var versionId = marker.getAttribute("data-trial-rating");
    setTrialMarkerRating(marker, versionId, value, touched);
  }

  function setTrialMarkerRating(marker, versionId, value, touched) {
    var boundedValue = Math.max(currentConfig.ratingScale.minimum, Math.min(currentConfig.ratingScale.maximum, Number(value)));
    setPreferenceMarkerPosition(marker, boundedValue);
    marker.classList.toggle("preference-marker--unset", touched !== true);
    marker.classList.toggle("preference-marker--rated", touched === true);
    marker.setAttribute("aria-invalid", "false");
    storeUnsavedRating(versionId, boundedValue, touched);
    updateCompletionState(false);
  }

  function setPreferenceMarkerPosition(marker, value) {
    var boundedValue = Math.max(0, Math.min(100, Number(value)));
    marker.style.left = String(boundedValue) + "%";
    marker.style.setProperty("--marker-rating-position", String(boundedValue) + "%");
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

  function attachPreferenceMarkerPointerHandlers(marker, track, playCallback, dragCallback) {
    var dragThresholdPixels = 8;
    var pointerState = null;

    marker.addEventListener("pointerdown", function (event) {
      event.preventDefault();
      selectPreferenceMarker(marker);
      pointerState = {
        id: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        dragging: false
      };
      if (marker.setPointerCapture) {
        marker.setPointerCapture(event.pointerId);
      }
    });

    marker.addEventListener("pointermove", function (event) {
      var deltaX;
      var deltaY;
      if (!pointerState || pointerState.id !== event.pointerId) {
        return;
      }
      deltaX = event.clientX - pointerState.startX;
      deltaY = event.clientY - pointerState.startY;
      if (!pointerState.dragging && Math.sqrt(deltaX * deltaX + deltaY * deltaY) >= dragThresholdPixels) {
        pointerState.dragging = true;
        if (typeof playCallback === "function") {
          playCallback();
        }
      }
      if (pointerState.dragging && typeof dragCallback === "function") {
        dragCallback(event);
      }
    });

    marker.addEventListener("pointerup", function (event) {
      if (marker.releasePointerCapture && marker.hasPointerCapture && marker.hasPointerCapture(event.pointerId)) {
        marker.releasePointerCapture(event.pointerId);
      }
      if (pointerState && pointerState.id === event.pointerId && !pointerState.dragging && typeof playCallback === "function") {
        playCallback();
      }
      pointerState = null;
    });

    marker.addEventListener("pointercancel", function (event) {
      if (marker.releasePointerCapture && marker.hasPointerCapture && marker.hasPointerCapture(event.pointerId)) {
        marker.releasePointerCapture(event.pointerId);
      }
      pointerState = null;
    });
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
    updateSharedStopAudioControls();
  }

  function setActivePreferenceMarker(audioId) {
    Array.prototype.slice.call(document.querySelectorAll(".preference-marker, .version-card--audio")).forEach(function (element) {
      element.classList.toggle("is-playing", Boolean(audioId) && (element.getAttribute("data-audio-id-target") === audioId || element.getAttribute("data-audio-card-id") === audioId));
    });
    updateSharedStopAudioControls();
  }

  function createSharedStopAudioControl(context) {
    var wrapper = document.createElement("div");
    var button = document.createElement("button");

    wrapper.className = "shared-audio-control-row";
    button.type = "button";
    button.className = "button button--secondary";
    button.textContent = "Stop audio";
    button.disabled = true;
    button.setAttribute("aria-disabled", "true");
    button.setAttribute("data-stop-shared-audio", context || "");
    button.addEventListener("click", function () {
      if (window.StudyApp.audio) {
        window.StudyApp.audio.stopActiveAudio();
      }
      setActivePreferenceMarker(null);
    });
    wrapper.appendChild(button);
    return wrapper;
  }

  function updateSharedStopAudioControls() {
    var hasPlayingAudio = Array.prototype.slice.call(document.querySelectorAll("audio[data-audio-id]")).some(function (audioElement) {
      return !audioElement.paused && !audioElement.ended;
    });
    Array.prototype.slice.call(document.querySelectorAll("[data-stop-shared-audio]")).forEach(function (button) {
      button.disabled = !hasPlayingAudio;
      button.setAttribute("aria-disabled", String(!hasPlayingAudio));
    });
  }

  function createTrialAudioBank() {
    var bank = document.createElement("div");
    bank.className = "marker-audio-bank";
    bank.setAttribute("aria-hidden", "true");
    currentTrial.versionMappings.forEach(function (mapping) {
      bank.appendChild(createAudioElement(mapping));
    });
    return bank;
  }

  function createAudioElement(mapping) {
    var audio = document.createElement("audio");
    var source = document.createElement("source");
    var audioError = document.createElement("p");
    var versionId = getVersionId(mapping.neutralLabel);
    var audioId = getAudioId(currentTrial.trialIndex, versionId);

    audio.className = "audio-control";
    audio.controls = false;
    audio.preload = "none";
    audio.setAttribute("aria-label", mapping.neutralLabel + " audio");
    audio.setAttribute("data-audio-id", audioId);
    audio.setAttribute("data-marker-controlled-audio", "true");
    source.src = buildMainStudyAudioUrl(mapping.audioPath);
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
    var wrapper = document.createElement("div");
    wrapper.appendChild(audio);
    wrapper.appendChild(audioError);
    return wrapper;
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

  function createComparativeCommentField() {
    var wrapper = document.createElement("div");
    var commentLabel = document.createElement("label");
    var comment = document.createElement("textarea");
    var commentError = document.createElement("p");

    wrapper.className = "question-panel trial-comparative-comment";
    commentLabel.className = "field__label";
    commentLabel.setAttribute("for", "trial-comparative-comment");
    commentLabel.textContent = "Required comment";
    comment.id = "trial-comparative-comment";
    comment.name = "comparative_comment";
    comment.className = "textarea";
    comment.maxLength = maxTrialCommentLength;
    comment.setAttribute("data-trial-comparative-comment", "");
    comment.setAttribute("aria-describedby", "trial-comparative-comment-error");
    comment.addEventListener("input", function () {
      storeUnsavedComparativeComment(comment.value);
      updateCompletionState(false);
    });
    commentError.id = "trial-comparative-comment-error";
    commentError.className = "validation-message is-hidden";
    commentError.textContent = "Provide a comment comparing the versions.";

    wrapper.appendChild(commentLabel);
    wrapper.appendChild(comment);
    wrapper.appendChild(commentError);
    return wrapper;
  }

  function restoreUnsavedResponses() {
    var state = getUnsavedState();
    var comment = document.querySelector("[data-trial-comparative-comment]");
    currentTrial.versionMappings.forEach(function (mapping) {
      var versionId = getVersionId(mapping.neutralLabel);
      var ratingControl = document.querySelector("[data-trial-rating='" + versionId + "']");

      if (ratingControl && state.ratingTouched[versionId] === true && typeof state.ratings[versionId] !== "undefined") {
        setPreferenceMarkerPosition(ratingControl, state.ratings[versionId]);
        ratingControl.classList.remove("preference-marker--unset");
        ratingControl.classList.add("preference-marker--rated");
      }
    });

    if (comment && typeof state.comparativeComment === "string") {
      comment.value = state.comparativeComment;
    }
  }

  function handleSubmit(currentPage, groupAssignment) {
    var validation = validateCurrentTrial(true);
    var summary = document.querySelector("[data-validation-summary]");
    var submissionTimestamp;
    var record;

    setError(summary, !validation.valid);
    if (!validation.valid) {
      if (summary) {
        summary.textContent = validation.message || "Please complete the listening task requirements before continuing.";
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
    var missingPlaybackLabels = [];
    var missingRatingLabels = [];
    var commentText = typeof state.comparativeComment === "string" ? state.comparativeComment : "";
    var commentValid = window.StudyApp.validation.validateRequiredComment(commentText) && commentText.length <= maxTrialCommentLength;
    var commentInput = document.querySelector("[data-trial-comparative-comment]");
    var commentError = document.getElementById("trial-comparative-comment-error");

    currentTrial.versionMappings.forEach(function (mapping) {
      var versionId = getVersionId(mapping.neutralLabel);
      var audioPlayed = hasAudioPlayed(versionId);
      var ratingSet = state.ratingTouched[versionId] === true && typeof state.ratings[versionId] === "number";
      var ratingInput = document.querySelector("[data-trial-rating='" + versionId + "']");
      var audioElement = document.querySelector("[data-audio-id='" + getAudioId(currentTrial.trialIndex, versionId) + "']");
      var shortLabel = getShortVersionLabel(mapping.neutralLabel);

      if (showErrors) {
        if (ratingInput) {
          ratingInput.setAttribute("aria-invalid", String(!ratingSet));
        }
      }

      if (!audioPlayed && !firstInvalid) {
        firstInvalid = ratingInput || audioElement;
      }
      if (!audioPlayed) {
        missingPlaybackLabels.push(shortLabel);
      }
      if (!ratingSet && !firstInvalid) {
        firstInvalid = ratingInput;
      }
      if (!ratingSet) {
        missingRatingLabels.push(shortLabel);
      }
    });

    if (showErrors) {
      if (commentError) {
        commentError.textContent = commentText.length > maxTrialCommentLength ? "Keep this comment under " + maxTrialCommentLength + " characters." : "Provide a comment comparing the versions.";
      }
      if (commentInput) {
        commentInput.setAttribute("aria-invalid", String(!commentValid));
      }
      setError(commentError, !commentValid);
    }
    if (!commentValid && !firstInvalid) {
      firstInvalid = commentInput;
    }

    return {
      valid: firstInvalid === null,
      firstInvalid: firstInvalid,
      message: buildTrialValidationMessage(missingPlaybackLabels, missingRatingLabels, commentValid, commentText)
    };
  }

  function buildTrialValidationMessage(missingPlaybackLabels, missingRatingLabels, commentValid, commentText) {
    var messages = [];

    if (missingPlaybackLabels.length > 0) {
      messages.push("Please listen to " + formatVersionList(missingPlaybackLabels) + " before continuing.");
    }

    if (missingRatingLabels.length === 1) {
      messages.push("Set a preference rating for " + formatVersionList(missingRatingLabels) + ".");
    } else if (missingRatingLabels.length > 1) {
      messages.push("Set preference ratings for " + formatVersionList(missingRatingLabels) + ".");
    }

    if (!commentValid) {
      messages.push(commentText.length > maxTrialCommentLength ? "Keep the comment under " + maxTrialCommentLength + " characters." : "Provide a comment comparing the versions.");
    }

    return messages.join(" ");
  }

  function formatVersionList(labels) {
    if (labels.length === 0) {
      return "the required versions";
    }
    if (labels.length === 1) {
      return "Version " + labels[0];
    }
    if (labels.length === 2) {
      return "Versions " + labels[0] + " and " + labels[1];
    }
    return "Versions " + labels.slice(0, -1).join(", ") + ", and " + labels[labels.length - 1];
  }

  function getShortVersionLabel(label) {
    return String(label || "").replace(/^Version\s+/i, "").trim();
  }

  function updateCompletionState(showErrors) {
    var button = document.querySelector("[data-submit-trial]");
    var validation = currentTrial ? validateCurrentTrial(showErrors) : { valid: false };
    var commentSection = document.querySelector("[data-trial-comparative-comment-section]");

    if (commentSection) {
      commentSection.classList.toggle("is-hidden", !areCurrentTrialRatingsComplete());
    }

    if (button) {
      button.disabled = false;
      button.setAttribute("aria-disabled", "false");
      button.setAttribute("data-ready-to-submit", String(validation.valid));
    }

    return validation.valid;
  }

  function areCurrentTrialRatingsComplete() {
    var state = getUnsavedState();
    return currentTrial.versionMappings.every(function (mapping) {
      var versionId = getVersionId(mapping.neutralLabel);
      return state.ratingTouched[versionId] === true && typeof state.ratings[versionId] === "number";
    });
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
      stimulusConfigurationVersion: currentConfig.stimulusConfigurationVersion || null,
      scenarioTitle: scenario ? getParticipantScenarioTitle(scenario) : null,
      neutralExcerptTitle: excerpt ? getParticipantExcerptTitle(excerpt.id) : null,
      trialStartTimestamp: currentTrialStartTimestamp,
      trialSubmissionTimestamp: submissionTimestamp,
      derivedTrialDurationMs: duration,
      comparative_comment: state.comparativeComment,
      versionResponses: currentTrial.versionMappings.map(function (mapping) {
        var versionId = getVersionId(mapping.neutralLabel);
        return {
          groupId: groupAssignment.groupId,
          trialIndex: currentTrial.trialIndex,
          scenarioId: currentTrial.scenarioId,
          excerptId: currentTrial.excerptId,
          stimulusConfigurationVersion: currentConfig.stimulusConfigurationVersion || null,
          neutralDisplayLabel: mapping.neutralLabel,
          actualMixId: mapping.actualMixId,
          stimulusId: mapping.stimulusId || null,
          audioPath: mapping.audioPath,
          rating: state.ratings[versionId],
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
        stimulusConfigurationVersion: currentConfig.stimulusConfigurationVersion || null,
        scenarioTitle: scenario ? getParticipantScenarioTitle(scenario) : null,
        neutralExcerptTitle: excerpt ? getParticipantExcerptTitle(excerpt.id) : null,
        trialStartTimestamp: startTimestamp,
        trialSubmissionTimestamp: submissionTimestamp,
        derivedTrialDurationMs: duration,
        comparative_comment: "Sample comparative comment for the displayed versions.",
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
            stimulusConfigurationVersion: currentConfig.stimulusConfigurationVersion || null,
            neutralDisplayLabel: mapping.neutralLabel,
            actualMixId: mapping.actualMixId,
            stimulusId: mapping.stimulusId || null,
            audioPath: mapping.audioPath,
            rating: 50 + mappingIndex,
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
    var expectedCount = trialOrder && Array.isArray(trialOrder.trials) ? trialOrder.trials.length : 6;
    return countCompletedTrials() >= expectedCount;
  }

  function getUnsavedState() {
    var key = getUnsavedStateKey(currentTrial.trialIndex);
    var state = window.StudyApp.storage && window.StudyApp.storage.getItem(key);

    if (!state) {
      state = {
        ratings: {},
        ratingTouched: {},
        comparativeComment: ""
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

  function storeUnsavedComparativeComment(value) {
    var state = getUnsavedState();
    state.comparativeComment = value;
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
  }

  function getFirstPlayTimestamp(versionId) {
    return window.StudyApp.storage.getItem(getFirstPlayKey(currentTrial.trialIndex, versionId));
  }

  function hasAudioPlayed(versionId) {
    return Boolean(window.StudyApp.audio && window.StudyApp.audio.hasAudioBeenPlayed(getAudioId(currentTrial.trialIndex, versionId)));
  }

  function getComparativeCommentPrompt(versionMappings) {
    return "Write one short comment comparing the versions. Briefly explain which differences influenced your ratings and why you preferred some mixes over others.";
  }

  function createStrongText(text) {
    var strong = document.createElement("strong");
    strong.textContent = text;
    return strong;
  }

  function getVersionRangeLabel(versionMappings) {
    var labels = (versionMappings || []).map(function (mapping) {
      return getShortVersionLabel(mapping.neutralLabel);
    }).filter(Boolean);
    if (labels.length === 0) {
      return "the versions";
    }
    if (labels.length === 1) {
      return "Version " + labels[0];
    }
    return "Versions " + labels[0] + "–" + labels[labels.length - 1];
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

  function buildMainStudyAudioUrl(audioPath) {
    var version = currentConfig && currentConfig.stimulusConfigurationVersion;
    var path = "../" + audioPath;
    if (!version) {
      return path;
    }
    return path + (path.indexOf("?") === -1 ? "?" : "&") + "v=" + encodeURIComponent(version);
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
