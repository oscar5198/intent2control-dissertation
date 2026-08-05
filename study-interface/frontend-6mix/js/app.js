"use strict";

/*
  Shared application initialisation.
  Responsibilities:
  - Detect the current page.
  - Start shared setup safely.
  - Coordinate page-level hooks.
  - Avoid assuming a backend or final persistence layer.
*/

window.StudyApp = window.StudyApp || {};

window.StudyApp.app = (function () {
  var screeningState = {
    config: null,
    studyConfig: null,
    currentIndex: 0,
    responses: [],
    scores: [],
    attemptNumber: 1,
    complete: false,
    selectedAnswers: {},
    presentationOrder: []
  };

  function getCurrentPage() {
    return document.body ? document.body.getAttribute("data-page") : null;
  }

  function initialisePage() {
    var currentPage = getCurrentPage();

    if (!currentPage) {
      return;
    }

    initialiseActions(currentPage);

    if (window.StudyApp.navigation && !window.StudyApp.navigation.isRouteAllowed(currentPage)) {
      window.location.replace(window.StudyApp.navigation.getRouteFallback(currentPage));
      return;
    }

    if (window.StudyApp.timing) {
      window.StudyApp.timing.recordPageEntry(currentPage);
    }

    if (window.StudyApp.progress) {
      window.StudyApp.progress.prepareProgress(currentPage);
    }

    if (currentPage === "listening-setup") {
      initialiseListeningSetup(currentPage);
    }

    if (currentPage === "screening") {
      initialiseScreening(currentPage);
    }

    if (currentPage === "instructions") {
      initialiseInstructions(currentPage);
    }

    if (currentPage === "practice") {
      initialisePractice(currentPage);
    }

    if (currentPage === "trial" && window.StudyApp.trial) {
      window.StudyApp.trial.initialiseExperimentalTrial(currentPage);
    }

    if (currentPage === "demographics") {
      initialiseQuestionnaire(currentPage, "demographic", "demographics.responses", "demographics.completed", "review.html");
    }

    if (currentPage === "post-task") {
      initialiseQuestionnaire(currentPage, "postTask", "postTask.responses", "postTask.completed", "demographics.html");
    }

    if (currentPage === "review") {
      initialiseReview(currentPage);
    }

    if (currentPage === "completion") {
      initialiseCompletion();
    }
  }

  function setError(errorElement, show) {
    if (!errorElement) {
      return;
    }

    errorElement.classList.toggle("is-hidden", !show);
  }

  function setDisabled(element, disabled) {
    if (!element) {
      return;
    }

    element.disabled = disabled;
    element.setAttribute("aria-disabled", String(disabled));
  }

  function initialiseActions(currentPage) {
    var startButton = document.querySelector("[data-action='start-study']");
    var printButton = document.querySelector("[data-action='print-page']");
    var backButtons = Array.prototype.slice.call(document.querySelectorAll("[data-action='back']"));
    var beginMainStudyButton = document.querySelector("[data-action='begin-main-study']");
    var documentLinks = Array.prototype.slice.call(document.querySelectorAll("[data-document-link]"));
    var pisForm = document.querySelector("[data-form='participant-information']");
    var consentForm = document.querySelector("[data-form='consent']");
    var combinedForm = document.querySelector("[data-form='study-information-consent']");

    if (startButton) {
      if (startButton.getAttribute("data-start-listener-attached") === "true") {
        return;
      }
      startButton.setAttribute("data-start-listener-attached", "true");
      startButton.addEventListener("click", function () {
        var navigated;

        if (startButton.getAttribute("data-start-study-running") === "true") {
          return;
        }

        startButton.setAttribute("data-start-study-running", "true");
        setDisabled(startButton, true);

        try {
          if (window.StudyApp.storage) {
            window.StudyApp.storage.resetStudyState();
          }
          if (window.StudyApp.timing) {
            window.StudyApp.timing.recordStudyStart();
          }
          if (window.StudyApp.storage) {
            window.StudyApp.storage.getOrCreateStudyId();
          }
          if (window.StudyApp.navigation) {
            navigated = window.StudyApp.navigation.navigateTo("study-information-consent.html");
          }

          if (!navigated) {
            throw new Error("Navigation target study-information-consent.html is not available.");
          }
        } catch (error) {
          console.error("Start study action failed.", error);
          startButton.removeAttribute("data-start-study-running");
          setDisabled(startButton, false);
          showPageInitialisationError("The study could not be started. Please refresh the page and try again.");
        }
      });
    }

    if (printButton) {
      printButton.addEventListener("click", function () {
        window.print();
      });
    }

    backButtons.forEach(function (button) {
      button.addEventListener("click", function () {
        if (currentPage === "screening" && hasActiveScreeningAttempt() && button.getAttribute("data-back-confirmed") !== "true") {
          showScreeningBackWarning(button);
          return;
        }

        var target = button.getAttribute("data-target");
        if (window.StudyApp.navigation) {
          window.StudyApp.navigation.navigateTo(target);
        }
      });
    });

    if (beginMainStudyButton && beginMainStudyButton.getAttribute("data-begin-listener-attached") !== "true") {
      beginMainStudyButton.setAttribute("data-begin-listener-attached", "true");
      beginMainStudyButton.addEventListener("click", function () {
        if (window.StudyApp.timing) {
          window.StudyApp.timing.recordPageCompletion(currentPage);
        }
        if (window.StudyApp.navigation) {
          window.location.href = "trial.html?v=scale-active-summary-20260804";
        }
      });
    }

    documentLinks.forEach(function (link) {
      link.addEventListener("click", function () {
        var documentType = link.getAttribute("data-document-link");
        if (window.StudyApp.storage && documentType) {
          window.StudyApp.storage.setItem(documentType + ".documentOpened", true);
        }
      });
    });

    if (pisForm) {
      pisForm.addEventListener("submit", function (event) {
        event.preventDefault();
        handlePisSubmit(currentPage);
      });
    }

    if (consentForm) {
      consentForm.addEventListener("submit", function (event) {
        event.preventDefault();
        handleConsentSubmit(currentPage);
      });
    }

    if (combinedForm) {
      combinedForm.addEventListener("submit", function (event) {
        event.preventDefault();
        handleStudyInformationConsentSubmit(currentPage);
      });
    }
  }

  function handlePisSubmit(currentPage) {
    var checkbox = document.getElementById("pis-acknowledgement");
    var error = document.getElementById("pis-acknowledgement-error");
    var isValid = checkbox && checkbox.checked;

    setError(error, !isValid);
    if (checkbox) {
      checkbox.setAttribute("aria-invalid", String(!isValid));
    }

    if (!isValid) {
      if (checkbox) {
        checkbox.focus();
      }
      return false;
    }

    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("pis.acknowledged", true);
    }
    if (window.StudyApp.timing) {
      window.StudyApp.timing.recordPageCompletion(currentPage);
    }
    if (window.StudyApp.navigation) {
      window.StudyApp.navigation.navigateTo("consent.html");
    }

    return true;
  }

  function handleConsentSubmit(currentPage) {
    var requiredItems = Array.prototype.slice.call(document.querySelectorAll("[data-consent-required]"));
    var summary = document.querySelector("[data-validation-summary]");
    var firstInvalid = null;

    requiredItems.forEach(function (item) {
      var isValid = item.checked;
      var error = document.getElementById(item.getAttribute("aria-describedby"));

      setError(error, !isValid);
      item.setAttribute("aria-invalid", String(!isValid));

      if (!isValid && !firstInvalid) {
        firstInvalid = item;
      }
    });

    setError(summary, Boolean(firstInvalid));

    if (firstInvalid) {
      if (summary) {
        summary.focus();
      }
      firstInvalid.focus();
      return false;
    }

    if (window.StudyApp.storage) {
      var consentState = {};
      requiredItems.forEach(function (item) {
        consentState[item.name] = item.checked;
      });
      window.StudyApp.storage.setItem("consent.items", consentState);
    }
    if (window.StudyApp.timing) {
      window.StudyApp.timing.recordConsentCompletion();
      window.StudyApp.timing.recordPageCompletion(currentPage);
    }
    if (window.StudyApp.navigation) {
      window.StudyApp.navigation.navigateTo("listening-setup.html");
    }

    return true;
  }

  function handleStudyInformationConsentSubmit(currentPage) {
    var pisOpened = window.StudyApp.storage && window.StudyApp.storage.getItem("pis.documentOpened") === true;
    var consentOpened = window.StudyApp.storage && window.StudyApp.storage.getItem("consent.documentOpened") === true;
    var pisCheckbox = document.getElementById("pis-acknowledgement");
    var requiredItems = Array.prototype.slice.call(document.querySelectorAll("[data-consent-required]"));
    var summary = document.querySelector("[data-validation-summary]");
    var firstInvalid = null;

    firstInvalid = firstInvalid || validateBooleanRequirement("pis-opened-error", pisOpened, document.querySelector("[data-document-link='pis']"));
    firstInvalid = firstInvalid || validateCheckboxRequirement(pisCheckbox, "pis-acknowledgement-error");
    firstInvalid = firstInvalid || validateBooleanRequirement("consent-opened-error", consentOpened, document.querySelector("[data-document-link='consent']"));

    requiredItems.forEach(function (item) {
      firstInvalid = firstInvalid || validateCheckboxRequirement(item, item.getAttribute("aria-describedby"));
    });

    setError(summary, Boolean(firstInvalid));

    if (firstInvalid) {
      if (summary) {
        summary.focus();
      }
      firstInvalid.focus();
      return false;
    }

    if (window.StudyApp.storage) {
      var consentState = {};
      requiredItems.forEach(function (item) {
        consentState[item.name] = item.checked;
      });
      window.StudyApp.storage.setItem("pis.acknowledged", true);
      window.StudyApp.storage.setItem("consent.items", consentState);
    }
    if (window.StudyApp.timing) {
      window.StudyApp.timing.recordStudyInformationConsentCompletion();
      window.StudyApp.timing.recordConsentCompletion();
      window.StudyApp.timing.recordPageCompletion(currentPage);
    }
    if (window.StudyApp.navigation) {
      window.StudyApp.navigation.navigateTo("listening-setup.html");
    }

    return true;
  }

  function validateBooleanRequirement(errorId, isValid, focusTarget) {
    var error = document.getElementById(errorId);
    setError(error, !isValid);
    if (focusTarget) {
      focusTarget.setAttribute("aria-invalid", String(!isValid));
    }
    return isValid ? null : focusTarget;
  }

  function validateCheckboxRequirement(checkbox, errorId) {
    var isValid = checkbox && checkbox.checked;
    var error = document.getElementById(errorId);
    setError(error, !isValid);
    if (checkbox) {
      checkbox.setAttribute("aria-invalid", String(!isValid));
    }
    return isValid ? null : checkbox;
  }

  function initialiseInstructions(currentPage) {
    var form = document.querySelector("[data-form='instructions']");
    var checkbox = document.getElementById("instructions-acknowledgement");
    var continueButton = document.querySelector("[data-instructions-continue]");

    if (checkbox) {
      checkbox.checked = Boolean(window.StudyApp.storage && window.StudyApp.storage.getItem("instructions.acknowledged") === true);
      updateInstructionsContinue();
      checkbox.addEventListener("change", function () {
        if (window.StudyApp.storage) {
          window.StudyApp.storage.setItem("instructions.acknowledged", checkbox.checked);
        }
        updateInstructionsContinue();
      });
    }

    if (form) {
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        handleInstructionsSubmit(currentPage);
      });
    }

    function updateInstructionsContinue() {
      setDisabled(continueButton, !(checkbox && checkbox.checked));
    }
  }

  function handleInstructionsSubmit(currentPage) {
    var checkbox = document.getElementById("instructions-acknowledgement");
    var summary = document.querySelector("[data-validation-summary]");
    var firstInvalid = validateCheckboxRequirement(checkbox, "instructions-acknowledgement-error");

    setError(summary, Boolean(firstInvalid));
    if (firstInvalid) {
      if (summary) {
        summary.focus();
      }
      firstInvalid.focus();
      return false;
    }

    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("instructions.acknowledged", true);
    }
    if (window.StudyApp.timing) {
      window.StudyApp.timing.recordInstructionsCompletion();
      window.StudyApp.timing.recordPageCompletion(currentPage);
    }
    if (window.StudyApp.navigation) {
      window.location.href = "practice.html?v=scale-active-summary-20260804";
    }
    return true;
  }

  function initialisePractice(currentPage) {
    var form = document.querySelector("[data-form='practice']");

    if (window.StudyApp.timing) {
      window.StudyApp.timing.recordPracticeStart();
      window.StudyApp.timing.recordTrialStart("practice_trial");
    }

    fetchJson("../config/practice.json").then(function (config) {
      renderPractice(config);
      restorePracticeResponses(config);
      updatePracticeCompletionState(config);

      if (form) {
        form.addEventListener("submit", function (event) {
          event.preventDefault();
          handlePracticeSubmit(currentPage, config);
        });
      }
    }).catch(function () {
      var summary = document.querySelector("[data-validation-summary]");
      if (summary) {
        summary.textContent = "Practice materials could not be loaded. Practice cannot be completed until the study materials are available.";
      }
      setError(summary, true);
    });
  }

  function renderPractice(config) {
    var title = document.querySelector("[data-practice-scenario-title]");
    var text = document.querySelector("[data-practice-scenario-text]");
    var instruction = document.querySelector("[data-practice-scenario-instruction]");
    var notice = document.querySelector("[data-practice-development-notice]");
    var container = document.querySelector("[data-practice-versions]");

    if (title) {
      title.textContent = config.practiceScenario.title;
    }
    if (text) {
      text.textContent = config.practiceScenario.text;
    }
    if (instruction) {
      instruction.textContent = config.practiceScenario.instruction || "";
      instruction.classList.toggle("is-hidden", !config.practiceScenario.instruction);
    }
    if (notice) {
      notice.textContent = config.developmentLabel || "Practice trial";
      notice.classList.toggle("is-hidden", config.developmentOnly !== true);
    }
    if (!container) {
      return false;
    }

    container.innerHTML = "";
    container.appendChild(createPracticeSharedRatingSection(config));
    container.appendChild(createPracticeCommentSection(config));

    if (window.StudyApp.audio) {
      window.StudyApp.audio.setupAudioControls(container);
    }
    return true;
  }

  function createPracticeSharedRatingSection(config) {
    var section = document.createElement("section");
    var header = document.createElement("div");
    var heading = document.createElement("h2");
    var intro = document.createElement("p");
    var scale = createPracticePreferenceScale(config);
    var audioBank = createPracticeAudioBank(config);

    section.className = "trial-task-section shared-rating-section";
    header.className = "shared-rating-section__header";
    heading.textContent = "Place the versions on the preference scale";
    intro.className = "trial-section-intro";
    intro.appendChild(document.createTextNode("Drag each marker to set its preference rating. "));
    intro.appendChild(createStrongText("Click or tap a marker to play that version."));
    header.appendChild(heading);
    header.appendChild(createSharedStopAudioControl("practice"));
    section.appendChild(header);
    section.appendChild(intro);
    section.appendChild(audioBank);
    section.appendChild(scale);
    return section;
  }

  function createPracticeCommentSection(config) {
    var section = document.createElement("section");
    var heading = document.createElement("h2");
    var intro = document.createElement("p");
    var field = createPracticeComparativeCommentField(config);

    section.className = "trial-task-section";
    section.classList.add("is-hidden");
    section.setAttribute("data-practice-comparative-comment-section", "");
    heading.textContent = "Explain your ratings";
    intro.className = "trial-section-intro";
    intro.textContent = getComparativeCommentPrompt(config.versions);
    section.appendChild(heading);
    section.appendChild(intro);
    section.appendChild(field);
    return section;
  }

  function createPracticePreferenceScale(config) {
    var scale = document.createElement("div");
    var track = document.createElement("div");
    var markerLayer = document.createElement("div");
    var anchorRow = createRatingAnchorScale();

    scale.className = "shared-preference-scale";
    track.className = "shared-preference-scale__track";
    markerLayer.className = "shared-preference-scale__markers";
    markerLayer.setAttribute("data-marker-count", String(config.versions.length));

    config.versions.forEach(function (version, index) {
      markerLayer.appendChild(createPracticePreferenceMarker(config, version, index, track));
    });

    track.appendChild(markerLayer);
    scale.appendChild(track);
    scale.appendChild(anchorRow);
    return scale;
  }

  function createPracticePreferenceMarker(config, version, index, track) {
    var marker = document.createElement("button");
    var initialValue = getInitialPreferencePlaceholderValue(config.ratingScale, index, config.versions.length);

    marker.type = "button";
    marker.id = version.id + "-rating";
    marker.name = version.id + "Rating";
    marker.className = "preference-marker preference-marker--" + (index + 1) + " preference-marker--unset";
    marker.tabIndex = -1;
    marker.textContent = version.label.replace("Version ", "");
    marker.setAttribute("aria-label", version.label + " audio marker. Drag to set the rating. Click or tap to play.");
    marker.setAttribute("data-version-display-label", version.label);
    marker.setAttribute("data-practice-rating", version.id);
    marker.setAttribute("data-audio-id-target", "practice." + version.id);
    setPreferenceMarkerPosition(marker, initialValue);

    attachPreferenceMarkerPointerHandlers(marker, track, function () {
      playPracticeMarkerAudio(version.id);
    }, function (event) {
      setPracticeMarkerFromPointer(config, marker, track, event, true);
    });
    return marker;
  }

  function getInitialPreferencePlaceholderValue(ratingScale, index, markerCount) {
    var minimum = Number(ratingScale.minimum);
    var maximum = Number(ratingScale.maximum);
    var midpoint = Math.round((minimum + maximum) / 2);
    var spacing = Math.max(4, Math.round((maximum - minimum) / 12.5));
    var count = Number(markerCount) || 1;
    var offset = (index - ((count - 1) / 2)) * spacing;

    if (count <= 1) {
      return midpoint;
    }

    return Math.max(minimum, Math.min(maximum, Math.round(midpoint + offset)));
  }

  function setPracticeMarkerFromPointer(config, marker, track, event, touched) {
    var rect = track.getBoundingClientRect();
    var value = getPreferenceValueFromPointer(rect, event);
    var versionId = marker.getAttribute("data-practice-rating");
    setPracticeMarkerRating(config, marker, versionId, value, touched);
  }

  function setPracticeMarkerRating(config, marker, versionId, value, touched) {
    var boundedValue = Math.max(config.ratingScale.minimum, Math.min(config.ratingScale.maximum, Number(value)));
    setPreferenceMarkerPosition(marker, boundedValue);
    marker.classList.toggle("preference-marker--unset", touched !== true);
    marker.classList.toggle("preference-marker--rated", touched === true);
    marker.setAttribute("aria-invalid", "false");
    storePracticeRating(versionId, boundedValue, touched);
    updatePracticeCompletionState(config);
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

  function playPracticeMarkerAudio(versionId) {
    setActivePreferenceMarker("practice." + versionId);
    if (window.StudyApp.audio) {
      window.StudyApp.audio.playAudioFromBeginning("practice." + versionId);
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
      setDisabled(button, !hasPlayingAudio);
    });
  }

  function createPracticeAudioBank(config) {
    var bank = document.createElement("div");
    bank.className = "marker-audio-bank";
    bank.setAttribute("aria-hidden", "true");
    config.versions.forEach(function (version) {
      bank.appendChild(createPracticeAudioElement(config, version));
    });
    return bank;
  }

  function createPracticeSection(headingText, introText, gridClassName, cards) {
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

  function createPracticeAudioElement(config, version) {
    var audio = document.createElement("audio");
    var source = document.createElement("source");
    var audioError = document.createElement("p");

    audio.className = "audio-control";
    audio.controls = false;
    audio.preload = "none";
    audio.setAttribute("aria-label", "Practice " + version.label + " audio");
    audio.setAttribute("data-audio-id", "practice." + version.id);
    audio.setAttribute("data-marker-controlled-audio", "true");
    source.src = "../" + version.audioPath;
    source.type = getAudioMimeType(version.audioPath);
    audio.appendChild(source);
    audioError.id = version.id + "-audio-error";
    audioError.className = "validation-message is-hidden";
    audioError.textContent = version.label + " audio could not be loaded.";
    audio.addEventListener("playing", function () {
      if (window.StudyApp.audio) {
        window.StudyApp.audio.markAudioPlayed("practice." + version.id);
      }
      setActivePreferenceMarker("practice." + version.id);
      updatePracticeCompletionState(config);
    });
    audio.addEventListener("error", function () {
      setError(audioError, true);
      updatePracticeCompletionState(config);
    });
    audio.addEventListener("ended", function () {
      setActivePreferenceMarker(null);
    });

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

  function createPracticeComparativeCommentField(config) {
    var wrapper = document.createElement("div");
    var commentLabel = document.createElement("label");
    var comment = document.createElement("textarea");
    var commentError = document.createElement("p");

    wrapper.className = "question-panel trial-comparative-comment";
    commentLabel.className = "field__label";
    commentLabel.setAttribute("for", "practice-comparative-comment");
    commentLabel.textContent = "Required comment";
    comment.id = "practice-comparative-comment";
    comment.name = "comparative_comment";
    comment.className = "textarea";
    comment.maxLength = config.commentMaxLength || 1000;
    comment.setAttribute("data-practice-comparative-comment", "");
    comment.setAttribute("aria-describedby", "practice-comparative-comment-error");
    comment.addEventListener("input", function () {
      storePracticeComparativeComment(comment.value);
      updatePracticeCompletionState(config);
    });
    commentError.id = "practice-comparative-comment-error";
    commentError.className = "validation-message is-hidden";
    commentError.textContent = "Provide a comment comparing the versions.";

    wrapper.appendChild(commentLabel);
    wrapper.appendChild(comment);
    wrapper.appendChild(commentError);
    return wrapper;
  }

  function restorePracticeResponses(config) {
    var ratings = window.StudyApp.storage && window.StudyApp.storage.getItem("practice.ratings") || {};
    var touched = window.StudyApp.storage && window.StudyApp.storage.getItem("practice.ratingTouched") || {};
    var comparativeComment = window.StudyApp.storage && window.StudyApp.storage.getItem("practice.comparativeComment");
    var comparativeCommentInput = document.querySelector("[data-practice-comparative-comment]");

    config.versions.forEach(function (version) {
      var ratingControl = document.querySelector("[data-practice-rating='" + version.id + "']");
      if (ratingControl && touched[version.id] === true && typeof ratings[version.id] !== "undefined") {
        setPreferenceMarkerPosition(ratingControl, ratings[version.id]);
        ratingControl.classList.remove("preference-marker--unset");
        ratingControl.classList.add("preference-marker--rated");
      }
    });

    if (comparativeCommentInput && typeof comparativeComment === "string") {
      comparativeCommentInput.value = comparativeComment;
    }
  }

  function storePracticeRating(versionId, value, touched) {
    var ratings = window.StudyApp.storage && window.StudyApp.storage.getItem("practice.ratings") || {};
    var touchedState = window.StudyApp.storage && window.StudyApp.storage.getItem("practice.ratingTouched") || {};
    if (!window.StudyApp.storage) {
      return false;
    }
    ratings[versionId] = Number(value);
    touchedState[versionId] = touched === true;
    window.StudyApp.storage.setItem("practice.ratings", ratings);
    window.StudyApp.storage.setItem("practice.ratingTouched", touchedState);
    window.StudyApp.storage.setItem("practice.currentResponses", {
      ratings: ratings,
      ratingTouched: touchedState,
      comparative_comment: window.StudyApp.storage.getItem("practice.comparativeComment") || ""
    });
    return true;
  }

  function storePracticeComparativeComment(value) {
    if (!window.StudyApp.storage) {
      return false;
    }
    window.StudyApp.storage.setItem("practice.comparativeComment", value);
    window.StudyApp.storage.setItem("practice.currentResponses", {
      ratings: window.StudyApp.storage.getItem("practice.ratings") || {},
      ratingTouched: window.StudyApp.storage.getItem("practice.ratingTouched") || {},
      comparative_comment: value
    });
    return true;
  }

  function updatePracticeCompletionState(config) {
    var completeButton = document.querySelector("[data-practice-complete]");
    var commentSection = document.querySelector("[data-practice-comparative-comment-section]");
    var ratingsReady = arePracticeRatingsComplete(config);

    if (commentSection) {
      commentSection.classList.toggle("is-hidden", !ratingsReady);
    }
    setDisabled(completeButton, !isPracticeComplete(config, false).valid);
  }

  function arePracticeRatingsComplete(config) {
    var ratings = window.StudyApp.storage && window.StudyApp.storage.getItem("practice.ratings") || {};
    var touched = window.StudyApp.storage && window.StudyApp.storage.getItem("practice.ratingTouched") || {};

    return (config.versions || []).every(function (version) {
      return touched[version.id] === true && typeof ratings[version.id] === "number";
    });
  }

  function isPracticeComplete(config, showErrors) {
    var ratings = window.StudyApp.storage && window.StudyApp.storage.getItem("practice.ratings") || {};
    var touched = window.StudyApp.storage && window.StudyApp.storage.getItem("practice.ratingTouched") || {};
    var comparativeComment = window.StudyApp.storage && window.StudyApp.storage.getItem("practice.comparativeComment");
    var commentInput = document.querySelector("[data-practice-comparative-comment]");
    var commentError = document.getElementById("practice-comparative-comment-error");
    var commentValid = !window.StudyApp.validation || (window.StudyApp.validation.validateRequiredComment(comparativeComment) && String(comparativeComment || "").length <= (config.commentMaxLength || 1000));
    var firstInvalid = null;

    config.versions.forEach(function (version) {
      var ratingControl = document.querySelector("[data-practice-rating='" + version.id + "']");
      var audioRequired = config.audioPlaybackRequired === true;
      var audioPlayed = !audioRequired || hasPracticeAudioPlayed(version.id);
      var audioElement = document.querySelector("[data-audio-id='practice." + version.id + "']");
      var ratingValid = touched[version.id] === true && typeof ratings[version.id] === "number";

      if (showErrors) {
        if (ratingControl) {
          ratingControl.setAttribute("aria-invalid", String(!ratingValid));
        }
      }
      if (!audioPlayed && !firstInvalid) {
        firstInvalid = ratingControl || audioElement;
      }
      if (!ratingValid && !firstInvalid) {
        firstInvalid = ratingControl;
      }
    });

    if (showErrors) {
      if (commentError) {
        commentError.textContent = String(comparativeComment || "").length > (config.commentMaxLength || 1000) ? "Keep this comment under " + (config.commentMaxLength || 1000) + " characters." : "Provide a comment comparing the versions.";
      }
      setError(commentError, !commentValid);
      if (commentInput) {
        commentInput.setAttribute("aria-invalid", String(!commentValid));
      }
    }
    if (!commentValid && !firstInvalid) {
      firstInvalid = commentInput;
    }

    return {
      valid: !firstInvalid,
      firstInvalid: firstInvalid
    };
  }

  function getComparativeCommentPrompt(versions) {
    return "Write one short comment comparing the versions. Briefly explain which differences influenced your ratings and why you preferred some mixes over others.";
  }

  function createStrongText(text) {
    var strong = document.createElement("strong");
    strong.textContent = text;
    return strong;
  }

  function getVersionRangeLabel(versions) {
    var labels = (versions || []).map(function (version) {
      return (version.label || "").replace(/^Version\s+/i, "").trim();
    }).filter(Boolean);
    if (labels.length === 0) {
      return "the versions";
    }
    if (labels.length === 1) {
      return "Version " + labels[0];
    }
    return "Versions " + labels[0] + "–" + labels[labels.length - 1];
  }

  function hasPracticeAudioPlayed(versionId) {
    return Boolean(window.StudyApp.audio && window.StudyApp.audio.hasAudioBeenPlayed("practice." + versionId));
  }

  function handlePracticeSubmit(currentPage, config) {
    var summary = document.querySelector("[data-validation-summary]");
    var validation = isPracticeComplete(config, true);

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

    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("practice.completed", true);
    }
    if (window.StudyApp.timing) {
      window.StudyApp.timing.recordTrialSubmission("practice_trial");
      window.StudyApp.timing.recordPracticeSubmission();
      window.StudyApp.timing.recordPracticeCompletion();
      window.StudyApp.timing.recordPageCompletion(currentPage);
    }
    if (window.StudyApp.navigation) {
      window.location.href = "main-study.html?v=scale-active-summary-20260804";
    }
    return true;
  }

  function initialiseListeningSetup(currentPage) {
    var form = document.querySelector("[data-form='listening-setup']");
    var audioElement = document.getElementById("setup-test-audio");
    var continueButton = document.querySelector("[data-listening-setup-continue]");
    var warning = document.querySelector("[data-setup-audio-warning]");
    var developmentNotice = document.querySelector("[data-setup-development-notice]");
    var requiredItems = Array.prototype.slice.call(document.querySelectorAll("[data-setup-required]"));
    var audioAvailable = false;
    var setupAudioPath = "../assets/audio/study-stimuli/listening-setup/setup_test_audio.wav";

    if (window.StudyApp.audio) {
      window.StudyApp.audio.setupAudioControls(document);
    }

    requiredItems.forEach(function (item) {
      var stored = window.StudyApp.storage && window.StudyApp.storage.getItem("listeningSetup." + item.name) === true;
      item.checked = stored;
      item.addEventListener("change", function () {
        if (window.StudyApp.storage) {
          window.StudyApp.storage.setItem("listeningSetup." + item.name, item.checked);
        }
        updateListeningSetupContinue(audioAvailable);
      });
    });

    if (audioElement) {
      audioElement.addEventListener("playing", function () {
        if (window.StudyApp.storage) {
          window.StudyApp.storage.setItem("listeningSetup.testAudioPlayed", true);
        }
        updateListeningSetupContinue(audioAvailable);
      });
      audioElement.addEventListener("error", function () {
        audioAvailable = false;
        setError(warning, true);
        updateListeningSetupContinue(false);
      });
    }

    fetchJson("../config/study-config.json").then(function (config) {
      var setupConfig = config.setupTestAudio || {};
      if (setupConfig.audioPath) {
        setupAudioPath = "../" + setupConfig.audioPath;
        updateSetupAudioSource(audioElement, setupAudioPath);
      }
      if (developmentNotice && config.appEnvironment === "development" && setupConfig.status === "temporary-development") {
        developmentNotice.textContent = setupConfig.developmentNotice || "Playback test";
        developmentNotice.classList.remove("is-hidden");
      }
      return checkRelativeAsset(setupAudioPath);
    }).catch(function () {
      return checkRelativeAsset(setupAudioPath);
    }).then(function (exists) {
      audioAvailable = exists;
      setError(warning, !exists);
      updateListeningSetupContinue(exists);
    });

    if (form) {
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        handleListeningSetupSubmit(currentPage, audioAvailable);
      });
    }

    function updateListeningSetupContinue(isAudioAvailable) {
      var canContinue = isAudioAvailable && hasSetupAudioPlayed() && requiredItems.every(function (item) {
        return item.checked;
      });
      setDisabled(continueButton, !canContinue);
    }
  }

  function updateSetupAudioSource(audioElement, audioPath) {
    var source;
    if (!audioElement || !audioPath) {
      return false;
    }

    source = audioElement.querySelector("source");
    if (!source) {
      source = document.createElement("source");
      audioElement.appendChild(source);
    }

    if (source.getAttribute("src") !== audioPath) {
      source.setAttribute("src", audioPath);
      source.setAttribute("type", getAudioMimeType(audioPath));
      audioElement.load();
    }

    return true;
  }

  function getAudioMimeType(audioPath) {
    var lowerPath = String(audioPath).toLowerCase();
    if (lowerPath.indexOf(".mp3") !== -1) {
      return "audio/mpeg";
    }
    if (lowerPath.indexOf(".wav") !== -1) {
      return "audio/wav";
    }
    if (lowerPath.indexOf(".ogg") !== -1) {
      return "audio/ogg";
    }
    return "audio/mpeg";
  }

  function hasSetupAudioPlayed() {
    return Boolean(window.StudyApp.audio && window.StudyApp.audio.hasAudioBeenPlayed("setup-test-audio"));
  }

  function handleListeningSetupSubmit(currentPage, audioAvailable) {
    var summary = document.querySelector("[data-validation-summary]");
    var audioError = document.getElementById("setup-audio-error");
    var requiredItems = Array.prototype.slice.call(document.querySelectorAll("[data-setup-required]"));
    var firstInvalid = null;
    var audioValid = audioAvailable && hasSetupAudioPlayed();

    setError(audioError, !audioValid);
    if (!audioValid) {
      firstInvalid = document.getElementById("setup-test-audio");
    }

    requiredItems.forEach(function (item) {
      firstInvalid = firstInvalid || validateCheckboxRequirement(item, item.getAttribute("aria-describedby"));
    });

    setError(summary, Boolean(firstInvalid));

    if (firstInvalid) {
      if (summary) {
        summary.focus();
      }
      firstInvalid.focus();
      return false;
    }

    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("listeningSetup.completed", true);
    }
    if (window.StudyApp.timing) {
      window.StudyApp.timing.recordListeningSetupCompletion();
      window.StudyApp.timing.recordPageCompletion(currentPage);
    }
    window.location.href = "screening.html?v=reference-ab-v4";

    return true;
  }

  function initialiseScreening(currentPage) {
    var routeWarning = document.querySelector("[data-screening-route-warning]");
    if (window.StudyApp.storage && window.StudyApp.storage.getItem("listeningSetup.completed") !== true) {
      setError(routeWarning, true);
    }

    Promise.all([
      fetchJson("../config/screening.json"),
      fetchJson("../config/study-config.json")
    ]).then(function (configs) {
      screeningState.config = configs[0];
      screeningState.studyConfig = configs[1];
      screeningState.attemptNumber = getStoredAttemptNumber();
      screeningState.currentIndex = getStoredScreeningItemIndex();
      screeningState.responses = getStoredScreeningResponses();
      screeningState.scores = getStoredScreeningScores();
      screeningState.selectedAnswers = getStoredScreeningSelectedAnswers();
      screeningState.complete = window.StudyApp.storage && window.StudyApp.storage.getItem("screening.activeAttempt") === false;
      screeningState.presentationOrder = prepareScreeningPresentations(screeningState.config, screeningState.attemptNumber);
      sanitizeScreeningSelectedAnswers();

      if (window.StudyApp.storage && !screeningState.complete) {
        window.StudyApp.storage.setItem("screening.activeAttempt", true);
        window.StudyApp.storage.setItem("screening.attemptNumber", screeningState.attemptNumber);
        window.StudyApp.storage.setItem("screening.currentItemIndex", screeningState.currentIndex);
      }
      if (window.StudyApp.timing && !screeningState.complete) {
        window.StudyApp.timing.recordScreeningStart(screeningState.attemptNumber);
      }

      renderScreening();
      attachScreeningActions(currentPage);
      if (screeningState.complete) {
        restoreCompletedScreeningResult();
      }
    }).catch(function (error) {
      var warning = document.querySelector("[data-screening-development-warning]");
      var instructions = document.querySelector("[data-screening-instructions]");
      console.error("Pre-Study Listening Task failed to initialise.", error);
      if (instructions) {
        instructions.textContent = "We were unable to load this listening task. Please refresh the page once. If the problem continues, please contact the researcher.";
      }
      if (warning) {
        warning.textContent = "We were unable to load this listening task. Please refresh the page once. If the problem continues, please contact the researcher.";
      }
      setError(warning, true);
    });
  }

  function renderScreening() {
    var config = screeningState.config;
    var items = getActiveScreeningItems();
    if (!config || !items.length) {
      return;
    }

    var warning = document.querySelector("[data-screening-development-warning]");
    var instructions = document.querySelector("[data-screening-instructions]");

    if (instructions) {
      instructions.innerHTML = formatScreeningInstructions(config.screeningInstructions);
    }

    if (warning) {
      warning.textContent = config.developmentLabel || "Pre-Study Listening Task";
    }
    setError(warning, hasUnresolvedScreeningValues(config));
    renderScreeningItems();
  }

  function getActiveScreeningItems() {
    if (Array.isArray(screeningState.presentationOrder) && screeningState.presentationOrder.length > 0) {
      return screeningState.presentationOrder;
    }
    return screeningState.config && Array.isArray(screeningState.config.items) ? screeningState.config.items : [];
  }

  function prepareScreeningPresentations(config, attemptNumber) {
    var storedOrder = window.StudyApp.storage && window.StudyApp.storage.getItem("screening.presentationOrder.attempt" + attemptNumber);
    var order;

    if (isValidScreeningPresentationOrder(storedOrder, config)) {
      config.items = storedOrder;
      return storedOrder;
    }

    if (storedOrder !== null) {
      resetIncompatibleScreeningAttemptState(attemptNumber);
      screeningState.selectedAnswers = {};
      screeningState.responses = [];
      screeningState.scores = [];
    }

    if (!config || !Array.isArray(config.segments) || !config.segments.length) {
      return config && Array.isArray(config.items) ? config.items : [];
    }

    order = buildScreeningPresentationOrder(config);
    config.items = order;
    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("screening.presentationOrder.attempt" + attemptNumber, order);
    }
    return order;
  }

  function buildScreeningPresentationOrder(config) {
    var structure = config.presentationStructure || {};
    var repetitions = typeof structure.repetitionsPerSegment === "number" ? structure.repetitionsPerSegment : 1;
    var presentations = [];

    config.segments.forEach(function (segment) {
      var repetition;
      for (repetition = 1; repetition <= repetitions; repetition += 1) {
        presentations.push(createScreeningPresentation(segment, repetition));
      }
    });

    if (structure.randomisePresentationOrder === true && window.StudyApp.randomisation) {
      presentations = shuffleScreeningPresentations(presentations, structure);
    }

    return presentations.map(function (presentation, index) {
      presentation.presentationOrder = index + 1;
      presentation.id = presentation.segmentId + "_rep" + presentation.repetitionNumber + "_order" + presentation.presentationOrder;
      return presentation;
    });
  }

  function shuffleScreeningPresentations(presentations, structure) {
    var attempts = 0;
    var shuffled = presentations;

    while (attempts < 20) {
      shuffled = window.StudyApp.randomisation.shuffle(presentations);
      if (!isGroupedScreeningSegmentOrder(shuffled, structure)) {
        return shuffled;
      }
      attempts += 1;
    }

    return buildInterleavedScreeningFallback(presentations);
  }

  function isGroupedScreeningSegmentOrder(presentations, structure) {
    var repetitions = typeof structure.repetitionsPerSegment === "number" ? structure.repetitionsPerSegment : 1;
    var segmentOrder;

    if (!Array.isArray(presentations) || presentations.length !== repetitions * 2) {
      return false;
    }

    segmentOrder = presentations.map(function (presentation) {
      return presentation.segmentId;
    });

    return segmentOrder.slice(0, repetitions).every(function (segmentId) {
      return segmentId === segmentOrder[0];
    }) && segmentOrder.slice(repetitions).every(function (segmentId) {
      return segmentId === segmentOrder[repetitions];
    }) && segmentOrder[0] !== segmentOrder[repetitions];
  }

  function buildInterleavedScreeningFallback(presentations) {
    var groups = {};
    var segmentIds = [];
    var interleaved = [];

    presentations.forEach(function (presentation) {
      if (!groups[presentation.segmentId]) {
        groups[presentation.segmentId] = [];
        segmentIds.push(presentation.segmentId);
      }
      groups[presentation.segmentId].push(presentation);
    });

    if (segmentIds.length !== 2) {
      return presentations;
    }

    segmentIds = window.StudyApp.randomisation.shuffle(segmentIds);
    groups[segmentIds[0]] = window.StudyApp.randomisation.shuffle(groups[segmentIds[0]]);
    groups[segmentIds[1]] = window.StudyApp.randomisation.shuffle(groups[segmentIds[1]]);

    [segmentIds[0], segmentIds[1], segmentIds[0], segmentIds[1], segmentIds[0], segmentIds[1]].forEach(function (segmentId) {
      interleaved.push(groups[segmentId].shift());
    });

    return interleaved;
  }

  function createScreeningPresentation(segment, repetitionNumber) {
    var matchAnswerOptions = window.StudyApp.randomisation ? window.StudyApp.randomisation.shuffle(["version_a", "version_b"]) : ["version_a", "version_b"];
    var matchAnswer = matchAnswerOptions[0];
    var nonMatchAnswer = matchAnswer === "version_a" ? "version_b" : "version_a";
    var audioChoices = [
      {
        id: "reference",
        label: "Reference",
        audioPath: segment.matchAudioPath,
        internalRole: "reference_match"
      },
      {
        id: matchAnswer,
        label: matchAnswer === "version_a" ? "Version A" : "Version B",
        audioPath: segment.matchDuplicateAudioPath || segment.matchAudioPath,
        internalRole: "matching_answer"
      },
      {
        id: nonMatchAnswer,
        label: nonMatchAnswer === "version_a" ? "Version A" : "Version B",
        audioPath: segment.nonMatchAudioPath,
        internalRole: "non_matching_answer"
      }
    ];

    audioChoices.sort(function (first, second) {
      return getVersionSortIndex(first.id) - getVersionSortIndex(second.id);
    });

    return {
      id: segment.id + "_rep" + repetitionNumber,
      segmentId: segment.id,
      stimulusVersion: screeningState.config ? screeningState.config.preStudyStimulusVersion : null,
      repetitionNumber: repetitionNumber,
      sourceSong: segment.sourceSong || null,
      referenceMixId: segment.referenceMixId || null,
      comparisonMixId: segment.comparisonMixId || null,
      excerptStartSeconds: segment.excerptStartSeconds,
      excerptEndSeconds: segment.excerptEndSeconds,
      comparisonOffsetSecondsRelativeToReference: segment.comparisonOffsetSecondsRelativeToReference,
      questionType: segment.questionType || "abx",
      prompt: segment.prompt || "Which of A or B matches the Reference?",
      audioChoices: audioChoices,
      answerOptions: [
        { value: "version_a", label: "Version A" },
        { value: "version_b", label: "Version B" },
      ],
      correctAnswer: matchAnswer,
      requiredAudioChoices: segment.requiredAudioChoices || ["reference", "version_a", "version_b"],
      versionMapping: {
        reference: "matching_reference",
        version_a: matchAnswer === "version_a" ? "matching_answer" : "non_matching_answer",
        version_b: matchAnswer === "version_b" ? "matching_answer" : "non_matching_answer"
      },
      developmentLogic: segment.developmentLogic
    };
  }

  function getVersionSortIndex(versionId) {
    if (versionId === "reference") {
      return 1;
    }
    if (versionId === "version_a") {
      return 2;
    }
    if (versionId === "version_b") {
      return 3;
    }
    return 99;
  }

  function getScreeningChoiceDisplayLabel(choiceId) {
    if (choiceId === "reference") {
      return "Reference";
    }
    if (choiceId === "version_a") {
      return "Version A";
    }
    if (choiceId === "version_b") {
      return "Version B";
    }
    return "";
  }

  function isValidScreeningPresentationOrder(order, config) {
    var structure = config && config.presentationStructure ? config.presentationStructure : {};
    var expectedCount = typeof structure.presentationCount === "number" ? structure.presentationCount : null;
    var expectedSegmentCount = typeof structure.segmentCount === "number" ? structure.segmentCount : null;
    var expectedRepetitions = typeof structure.repetitionsPerSegment === "number" ? structure.repetitionsPerSegment : null;
    var segmentCounts = {};
    var validSegmentIds = Array.isArray(config && config.segments) ? config.segments.map(function (segment) {
      return segment.id;
    }) : [];

    if (!Array.isArray(order) || !expectedCount || order.length !== expectedCount) {
      return false;
    }

    if (!order.every(function (item) {
      return isValidScreeningPresentationItem(item, config);
    })) {
      return false;
    }

    if (isGroupedScreeningSegmentOrder(order, structure)) {
      return false;
    }

    order.forEach(function (item) {
      segmentCounts[item.segmentId] = (segmentCounts[item.segmentId] || 0) + 1;
    });

    if (expectedSegmentCount && Object.keys(segmentCounts).length !== expectedSegmentCount) {
      return false;
    }

    return validSegmentIds.every(function (segmentId) {
      return segmentCounts[segmentId] === expectedRepetitions;
    });
  }

  function isValidScreeningPresentationItem(item, config) {
    var choiceIds;
    var stimulusVersion = config ? config.preStudyStimulusVersion : null;
    if (!item || typeof item !== "object") {
      return false;
    }
    if (stimulusVersion && item.stimulusVersion !== stimulusVersion) {
      return false;
    }
    if (!item.id || !item.segmentId || typeof item.repetitionNumber !== "number" || typeof item.presentationOrder !== "number") {
      return false;
    }
    if (["version_a", "version_b"].indexOf(item.correctAnswer) === -1) {
      return false;
    }
    if (!Array.isArray(item.audioChoices) || item.audioChoices.length !== 3 || !Array.isArray(item.answerOptions) || item.answerOptions.length !== 2) {
      return false;
    }
    choiceIds = item.audioChoices.map(function (choice) {
      return choice && choice.id;
    }).sort();
    if (choiceIds.join("|") !== "reference|version_a|version_b") {
      return false;
    }
    return item.audioChoices.every(function (choice) {
      return choice.label === getScreeningChoiceDisplayLabel(choice.id) && choice.audioPath && choice.audioPath.indexOf("assets/audio/") === 0;
    }) && item.answerOptions.every(function (option) {
      return option && option.label === getScreeningChoiceDisplayLabel(option.value);
    });
  }

  function resetIncompatibleScreeningAttemptState(attemptNumber) {
    if (!window.StudyApp.storage) {
      return false;
    }

    [
      "screening.presentationOrder.attempt" + attemptNumber,
      "screening.playedStates.attempt" + attemptNumber,
      "screening.attemptScore.attempt" + attemptNumber,
      "screening.selectedAnswers",
      "screening.itemResponses",
      "screening.itemScores",
      "screening.totalScore",
      "screening.currentItemIndex",
      "screening.passed",
      "screening.failed",
      "screening.activeAttempt"
    ].forEach(function (key) {
      window.StudyApp.storage.removeItem(key);
    });

    console.info("Incompatible pre-study listening task state was reset for the current attempt.");
    return true;
  }

  function renderScreeningItems() {
    var items = getActiveScreeningItems();
    var container = document.querySelector("[data-screening-items]");

    if (!items.length || !container) {
      return;
    }

    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("screening.currentItemIndex", 0);
    }

    container.innerHTML = "";
    items.forEach(function (item, index) {
      var itemSection = document.createElement("article");
      var itemProgress = document.createElement("p");
      var heading = document.createElement("h3");
      var prompt = document.createElement("p");
      var audioContainer = document.createElement("div");
      var answerContainer = document.createElement("fieldset");
      var legend = document.createElement("legend");
      var error = document.createElement("p");

      if (window.StudyApp.timing) {
        window.StudyApp.timing.recordScreeningItemStart(item.id, screeningState.attemptNumber);
      }

      itemSection.id = item.id;
      itemSection.className = "screening-item-card";
      itemSection.tabIndex = -1;
      itemSection.setAttribute("data-screening-item", item.id);
      itemProgress.className = "progress__label";
      itemProgress.textContent = "Listening item " + (index + 1) + " of " + items.length;
      heading.textContent = "Listening item " + (index + 1);
      prompt.innerHTML = item.prompt === "TBC" ? "Listen to the versions and choose the match." : "<strong>" + escapeHtml(item.prompt) + "</strong>";
      audioContainer.className = "screening-audio-grid";
      audioContainer.setAttribute("data-screening-audio", item.id);
      answerContainer.className = "field";
      answerContainer.setAttribute("data-screening-answers", item.id);
      legend.className = "field__label";
      legend.textContent = "Answer for listening item " + (index + 1);
      error.id = item.id + "-error";
      error.className = "validation-message is-hidden";
      error.textContent = "Play the Reference, Version A, and Version B, then select an answer for this item.";

      answerContainer.appendChild(legend);
      itemSection.appendChild(itemProgress);
      itemSection.appendChild(heading);
      itemSection.appendChild(prompt);
      itemSection.appendChild(audioContainer);
      itemSection.appendChild(answerContainer);
      itemSection.appendChild(error);
      container.appendChild(itemSection);

      renderScreeningAudio(item, audioContainer);
      renderScreeningAnswers(item, answerContainer);
    });
    updateScreeningSubmitState();
  }

  function renderScreeningAudio(item, container) {
    if (!container) {
      return;
    }

    container.innerHTML = "";
    item.audioChoices.forEach(function (choice) {
      var card = document.createElement("div");
      card.className = "audio-choice-card";

      var label = document.createElement("h3");
      label.textContent = getScreeningChoiceDisplayLabel(choice.id);

      var audio = document.createElement("audio");
      audio.className = "audio-control";
      audio.controls = true;
      audio.preload = "none";
      audio.setAttribute("aria-label", getScreeningChoiceDisplayLabel(choice.id));
      audio.setAttribute("data-audio-id", getScreeningAudioId(item.id, choice.id));

      var source = document.createElement("source");
      source.src = "../" + choice.audioPath;
      source.type = getAudioMimeType(choice.audioPath);
      audio.appendChild(source);

      var warning = document.createElement("p");
      warning.className = "validation-message is-hidden";
      warning.textContent = getScreeningChoiceDisplayLabel(choice.id) + " could not be loaded.";
      audio.addEventListener("playing", function () {
        storeScreeningPlayedState(item.id, choice.id);
        updateScreeningSubmitState();
      });
      audio.addEventListener("error", function () {
        setError(warning, true);
        updateScreeningSubmitState();
      });

      card.appendChild(label);
      card.appendChild(audio);
      card.appendChild(warning);
      container.appendChild(card);
    });

    if (window.StudyApp.audio) {
      window.StudyApp.audio.setupAudioControls(container);
    }
  }

  function renderScreeningAnswers(item, container) {
    if (!container) {
      return;
    }

    Array.prototype.slice.call(container.querySelectorAll(".radio-option")).forEach(function (option) {
      option.remove();
    });

    item.answerOptions.forEach(function (option) {
      var wrapper = document.createElement("div");
      var displayLabel = getScreeningChoiceDisplayLabel(option.value);

      if (!displayLabel) {
        return;
      }

      wrapper.className = "radio-option";

      var input = document.createElement("input");
      input.type = "radio";
      input.name = "screeningAnswer-" + item.id;
      input.id = "screening-answer-" + item.id + "-" + option.value;
      input.value = option.value;
      input.checked = screeningState.selectedAnswers[item.id] === option.value;
      input.addEventListener("change", function () {
        screeningState.selectedAnswers[item.id] = input.value;
        if (window.StudyApp.storage) {
          window.StudyApp.storage.setItem("screening.selectedAnswers", screeningState.selectedAnswers);
        }
        updateScreeningSubmitState();
      });

      var label = document.createElement("label");
      label.setAttribute("for", input.id);
      label.textContent = displayLabel;

      wrapper.appendChild(input);
      wrapper.appendChild(label);
      container.appendChild(wrapper);
    });
  }

  function attachScreeningActions(currentPage) {
    var submitButton = document.querySelector("[data-action='submit-screening-answer']");
    var retryButton = document.querySelector("[data-action='retry-screening']");
    var continueButton = document.querySelector("[data-action='continue-after-screening']");
    var bypassButton = document.querySelector("[data-action='development-bypass']");

    if (submitButton) {
      submitButton.addEventListener("click", function () {
        handleScreeningSubmit();
      });
    }

    setDisabled(continueButton, true);

    if (retryButton) {
      retryButton.addEventListener("click", function () {
        retryScreening(currentPage);
      });
    }

    if (continueButton) {
      continueButton.addEventListener("click", function () {
        if (window.StudyApp.storage && window.StudyApp.storage.getItem("screening.passed") === true && window.StudyApp.navigation) {
          window.StudyApp.navigation.navigateTo("instructions.html");
        }
      });
    }

    if (bypassButton) {
      var bypassAllowed = isDevelopmentBypassAllowed();
      bypassButton.classList.toggle("is-hidden", !bypassAllowed);
      bypassButton.addEventListener("click", function () {
        if (!isDevelopmentBypassAllowed()) {
          return;
        }
        storeScreeningResult(true, true);
        showScreeningResult("Pre-Study Listening Task completed.", true);
      });
    }
  }

  function handleScreeningSubmit() {
    var items = getActiveScreeningItems();
    var error = document.getElementById("screening-answer-error");
    var summary = document.querySelector("[data-validation-summary]");
    var validation = validateAllScreeningItems(true);
    var responses;

    setError(error, !validation.valid);
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

    responses = items.map(function (item) {
      var answer = screeningState.selectedAnswers[item.id];
      var score = scoreScreeningItem(item, answer);
      if (window.StudyApp.timing) {
        window.StudyApp.timing.recordScreeningItemSubmission(item.id, screeningState.attemptNumber);
      }
      return {
        itemId: item.id,
        segmentId: item.segmentId || null,
        repetitionNumber: item.repetitionNumber || null,
        presentationOrder: item.presentationOrder || null,
        sourceSong: item.sourceSong || null,
        referenceMixId: item.referenceMixId || null,
        comparisonMixId: item.comparisonMixId || null,
        excerptStartSeconds: item.excerptStartSeconds,
        excerptEndSeconds: item.excerptEndSeconds,
        versionMapping: item.versionMapping || null,
        answer: answer,
        correctAnswer: item.correctAnswer,
        score: score,
        correct: score === 1
      };
    });

    screeningState.responses = responses;
    screeningState.scores = responses.map(function (response) {
      return response.score;
    });

    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("screening.itemResponses", screeningState.responses);
      window.StudyApp.storage.setItem("screening.itemScores", screeningState.scores);
    }

    completeScreening();
    return true;
  }

  function validateAllScreeningItems(showErrors) {
    var items = getActiveScreeningItems();
    var firstInvalid = null;
    var allValid = true;

    if (!items.length) {
      return {
        valid: false,
        firstInvalid: null
      };
    }

    items.forEach(function (item) {
      var requiredAudioPlayed = item.requiredAudioChoices.every(function (choiceId) {
        return hasScreeningAudioPlayed(item.id, choiceId);
      });
      var selected = screeningState.selectedAnswers[item.id];
      var answered = Boolean(selected);
      var itemError = document.getElementById(item.id + "-error");
      var itemValid = requiredAudioPlayed && answered;
      var missingAudioLabels = getMissingScreeningAudioLabels(item);

      updateScreeningItemFeedback(itemError, missingAudioLabels, answered, showErrors);

      allValid = allValid && itemValid;
      if (!requiredAudioPlayed && !firstInvalid) {
        firstInvalid = findFirstUnplayedScreeningAudio(item) || document.querySelector("[data-screening-item='" + item.id + "']");
      }
      if (requiredAudioPlayed && !answered && !firstInvalid) {
        firstInvalid = document.querySelector("input[name='screeningAnswer-" + item.id + "']") || document.querySelector("[data-screening-item='" + item.id + "']");
      }
    });

    return {
      valid: allValid,
      firstInvalid: firstInvalid
    };
  }

  function updateScreeningItemFeedback(itemError, missingAudioLabels, answered, showErrors) {
    if (!itemError) {
      return;
    }

    if (missingAudioLabels.length > 0) {
      itemError.textContent = "Please listen to the Reference, Version A, and Version B before answering. Still needed: " + missingAudioLabels.join(", ") + ".";
      setError(itemError, true);
      return;
    }

    if (showErrors && !answered) {
      itemError.textContent = "Select whether Version A or Version B matches the Reference.";
      setError(itemError, true);
      return;
    }

    setError(itemError, false);
  }

  function scoreScreeningItem(item, answer) {
    if (!item.correctAnswer || item.correctAnswer === "TBC") {
      return null;
    }

    return item.correctAnswer === answer ? 1 : 0;
  }

  function completeScreening() {
    var config = screeningState.config;
    var items = getActiveScreeningItems();
    var total = screeningState.scores.reduce(function (sum, score) {
      return sum + (typeof score === "number" ? score : 0);
    }, 0);
    var passed = typeof config.minimumScore === "number" && total >= config.minimumScore;

    screeningState.complete = true;
    storeScreeningResult(passed, false, total);

    if (window.StudyApp.timing) {
      window.StudyApp.timing.recordScreeningCompletion(screeningState.attemptNumber);
    }

    if (passed) {
      showScreeningResult("Pre-Study Listening Task completed.", true);
      return;
    }

    if (canRetryScreening()) {
      showScreeningResult("Please repeat the Pre-Study Listening Task before continuing.", false);
      return;
    }

    showScreeningResult("The Pre-Study Listening Task is complete. The next step for this situation remains TBC.", false);
  }

  function storeScreeningResult(passed, bypassUsed, total) {
    var attempts;
    if (!window.StudyApp.storage) {
      return;
    }

    window.StudyApp.storage.setItem("screening.totalScore", typeof total === "number" ? total : null);
    window.StudyApp.storage.setItem("screening.passed", passed === true);
    window.StudyApp.storage.setItem("screening.failed", passed !== true);
    window.StudyApp.storage.setItem("screening.developmentBypassUsed", bypassUsed === true);
    window.StudyApp.storage.setItem("screening.activeAttempt", false);
    window.StudyApp.storage.setItem("screening.attemptScore.attempt" + screeningState.attemptNumber, typeof total === "number" ? total : null);

    attempts = window.StudyApp.storage.getItem("screening.attemptRecords") || [];
    attempts = attempts.filter(function (attempt) {
      return attempt.attemptNumber !== screeningState.attemptNumber;
    });
    attempts.push({
      attemptNumber: screeningState.attemptNumber,
      score: typeof total === "number" ? total : null,
      passed: passed === true,
      presentationOrder: getActiveScreeningItems().map(function (item) {
        return {
          itemId: item.id,
          segmentId: item.segmentId || null,
          repetitionNumber: item.repetitionNumber || null,
          presentationOrder: item.presentationOrder || null,
          sourceSong: item.sourceSong || null,
          referenceMixId: item.referenceMixId || null,
          comparisonMixId: item.comparisonMixId || null,
          excerptStartSeconds: item.excerptStartSeconds,
          excerptEndSeconds: item.excerptEndSeconds,
          correctAnswer: item.correctAnswer,
          versionMapping: item.versionMapping || null
        };
      }),
      responses: screeningState.responses.slice()
    });
    attempts.sort(function (first, second) {
      return first.attemptNumber - second.attemptNumber;
    });
    window.StudyApp.storage.setItem("screening.attemptRecords", attempts);
  }

  function showScreeningResult(message, passed) {
    var result = document.querySelector("[data-screening-result]");
    var feedback = document.querySelector("[data-screening-feedback]");
    var retryButton = document.querySelector("[data-action='retry-screening']");
    var continueButton = document.querySelector("[data-action='continue-after-screening']");
    var itemSection = document.querySelector("[data-screening-item-section]");
    var instructionsSection = document.querySelector("[data-screening-instructions-section]");

    if (result) {
      result.classList.remove("is-hidden");
    }
    if (itemSection) {
      itemSection.classList.add("is-hidden");
    }
    if (instructionsSection) {
      instructionsSection.classList.add("is-hidden");
    }
    if (feedback) {
      feedback.textContent = message;
    }
    if (retryButton) {
      retryButton.classList.toggle("is-hidden", passed || !canRetryScreening());
    }
    setDisabled(continueButton, !passed);
  }

  function restoreCompletedScreeningResult() {
    var passed = Boolean(window.StudyApp.storage && window.StudyApp.storage.getItem("screening.passed") === true);
    var failed = Boolean(window.StudyApp.storage && window.StudyApp.storage.getItem("screening.failed") === true);

    if (passed) {
      showScreeningResult("Pre-Study Listening Task completed.", true);
      return true;
    }

    if (failed && canRetryScreening()) {
      showScreeningResult("Please repeat the Pre-Study Listening Task before continuing.", false);
      return true;
    }

    if (failed) {
      showScreeningResult("The Pre-Study Listening Task is complete. The next step for this situation remains TBC.", false);
      return true;
    }

    return false;
  }

  function retryScreening(currentPage) {
    void currentPage;
    var nextAttempt = getStoredAttemptNumber() + 1;
    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("screening.attemptNumber", nextAttempt);
      window.StudyApp.storage.setItem("screening.itemResponses", []);
      window.StudyApp.storage.setItem("screening.itemScores", []);
      window.StudyApp.storage.setItem("screening.selectedAnswers", {});
      window.StudyApp.storage.setItem("screening.currentItemIndex", 0);
      window.StudyApp.storage.setItem("screening.playedStates.attempt" + nextAttempt, {});
      window.StudyApp.storage.removeItem("screening.presentationOrder.attempt" + nextAttempt);
      window.StudyApp.storage.setItem("screening.activeAttempt", true);
      window.StudyApp.storage.setItem("screening.passed", false);
      window.StudyApp.storage.setItem("screening.failed", false);
    }

    screeningState.attemptNumber = nextAttempt;
    screeningState.currentIndex = 0;
    screeningState.responses = [];
    screeningState.scores = [];
    screeningState.selectedAnswers = {};
    screeningState.complete = false;
    screeningState.presentationOrder = prepareScreeningPresentations(screeningState.config, screeningState.attemptNumber);

    var result = document.querySelector("[data-screening-result]");
    var itemSection = document.querySelector("[data-screening-item-section]");
    var instructionsSection = document.querySelector("[data-screening-instructions-section]");
    if (result) {
      result.classList.add("is-hidden");
    }
    if (itemSection) {
      itemSection.classList.remove("is-hidden");
    }
    if (instructionsSection) {
      instructionsSection.classList.remove("is-hidden");
    }

    if (window.StudyApp.timing) {
      window.StudyApp.timing.recordScreeningStart(screeningState.attemptNumber);
    }

    renderScreening();
  }

  function canRetryScreening() {
    var config = screeningState.config;
    if (!config || config.retryEnabled !== true) {
      return false;
    }
    if (typeof config.maximumAttempts !== "number") {
      return false;
    }

    return getStoredAttemptNumber() < config.maximumAttempts;
  }

  function getStoredAttemptNumber() {
    var stored = window.StudyApp.storage && window.StudyApp.storage.getItem("screening.attemptNumber");
    return typeof stored === "number" && stored > 0 ? stored : 1;
  }

  function getStoredScreeningItemIndex() {
    var stored = window.StudyApp.storage && window.StudyApp.storage.getItem("screening.currentItemIndex");
    return typeof stored === "number" && stored >= 0 ? stored : 0;
  }

  function getStoredScreeningResponses() {
    var stored = window.StudyApp.storage && window.StudyApp.storage.getItem("screening.itemResponses");
    return Array.isArray(stored) ? stored : [];
  }

  function getStoredScreeningScores() {
    var stored = window.StudyApp.storage && window.StudyApp.storage.getItem("screening.itemScores");
    return Array.isArray(stored) ? stored : [];
  }

  function getStoredScreeningSelectedAnswers() {
    var stored = window.StudyApp.storage && window.StudyApp.storage.getItem("screening.selectedAnswers");
    return stored && typeof stored === "object" && !Array.isArray(stored) ? stored : {};
  }

  function sanitizeScreeningSelectedAnswers() {
    var changed = false;
    Object.keys(screeningState.selectedAnswers || {}).forEach(function (itemId) {
      if (["version_a", "version_b"].indexOf(screeningState.selectedAnswers[itemId]) === -1) {
        delete screeningState.selectedAnswers[itemId];
        changed = true;
      }
    });
    if (changed && window.StudyApp.storage) {
      screeningState.responses = [];
      screeningState.scores = [];
      window.StudyApp.storage.setItem("screening.selectedAnswers", screeningState.selectedAnswers);
      window.StudyApp.storage.setItem("screening.itemResponses", []);
      window.StudyApp.storage.setItem("screening.itemScores", []);
    }
  }

  function getScreeningAudioId(itemId, choiceId) {
    return "screening.attempt" + screeningState.attemptNumber + "." + itemId + "." + choiceId;
  }

  function formatScreeningInstructions(text) {
    return escapeHtml(text || "").split(/\n\s*\n/).map(function (paragraph) {
      var trimmed = paragraph.trim();
      if (trimmed === "Which of A or B matches the Reference?") {
        return '<p class="prestudy-key-question"><strong>Which of A or B matches the Reference?</strong></p>';
      }
      return "<p>" + trimmed + "</p>";
    }).join("");
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function storeScreeningPlayedState(itemId, choiceId) {
    var playedState;
    if (!window.StudyApp.storage) {
      return false;
    }

    playedState = window.StudyApp.storage.getItem("screening.playedStates.attempt" + screeningState.attemptNumber) || {};
    if (!playedState[itemId]) {
      playedState[itemId] = {};
    }
    playedState[itemId][choiceId] = true;
    window.StudyApp.storage.setItem("screening.playedStates.attempt" + screeningState.attemptNumber, playedState);
    return true;
  }

  function hasScreeningAudioPlayed(itemId, choiceId) {
    var audioId = getScreeningAudioId(itemId, choiceId);
    var playedState = window.StudyApp.storage && window.StudyApp.storage.getItem("screening.playedStates.attempt" + screeningState.attemptNumber);
    var screeningPlayed = Boolean(playedState && playedState[itemId] && playedState[itemId][choiceId]);
    var audioPlayed = Boolean(window.StudyApp.audio && window.StudyApp.audio.hasAudioBeenPlayed(audioId));
    return screeningPlayed || audioPlayed;
  }

  function findFirstUnplayedScreeningAudio(item) {
    var firstUnplayed = null;
    if (!item || !Array.isArray(item.requiredAudioChoices)) {
      return null;
    }

    item.requiredAudioChoices.some(function (choiceId) {
      if (!hasScreeningAudioPlayed(item.id, choiceId)) {
        firstUnplayed = document.querySelector("[data-audio-id='" + getScreeningAudioId(item.id, choiceId) + "']");
        return true;
      }
      return false;
    });

    return firstUnplayed;
  }

  function getMissingScreeningAudioLabels(item) {
    if (!item || !Array.isArray(item.requiredAudioChoices)) {
      return [];
    }

    return item.requiredAudioChoices.filter(function (choiceId) {
      return !hasScreeningAudioPlayed(item.id, choiceId);
    }).map(function (choiceId) {
      var choice = Array.isArray(item.audioChoices) && item.audioChoices.find(function (audioChoice) {
        return audioChoice.id === choiceId;
      });
      return getScreeningChoiceDisplayLabel(choiceId) || (choice ? choice.label : choiceId);
    });
  }

  function updateScreeningSubmitState() {
    var items = getActiveScreeningItems();
    var submitButton = document.querySelector("[data-action='submit-screening-answer']");
    var error = document.getElementById("screening-answer-error");
    var validation;

    if (!items.length || !submitButton) {
      return false;
    }

    validation = validateAllScreeningItems(false);

    submitButton.textContent = "Submit listening task";
    setDisabled(submitButton, !validation.valid);
    setError(error, false);
    return validation.valid;
  }

  function hasUnresolvedScreeningValues(config) {
    var items = getActiveScreeningItems();
    return !config || config.screeningInstructions === "TBC" || typeof config.minimumScore !== "number" || !items.length || items.some(function (item) {
      return item.prompt === "TBC" || item.correctAnswer === "TBC" || item.audioChoices.some(function (choice) {
        return choice.audioPath.indexOf("placeholder") !== -1;
      });
    });
  }

  function isDevelopmentBypassAllowed() {
    var config = screeningState.config;
    var studyConfig = screeningState.studyConfig;
    return Boolean(config && studyConfig && config.developmentBypass && config.developmentBypass.enabled === true && studyConfig.frontendDevelopmentMode === true && studyConfig.appEnvironment === "development");
  }

  function hasActiveScreeningAttempt() {
    return Boolean(window.StudyApp.storage && window.StudyApp.storage.getItem("screening.activeAttempt") === true);
  }

  function showScreeningBackWarning(button) {
    var warning = document.querySelector("[data-screening-route-warning]");
    if (warning) {
      warning.textContent = "A listening task attempt is active. Selecting Back again will leave the attempt and return to Listening Setup.";
      setError(warning, true);
      warning.focus();
    }
    button.setAttribute("data-back-confirmed", "true");
  }

  function initialiseQuestionnaire(currentPage, sectionKey, storageKey, completionKey, nextPage) {
    fetchJson("../config/questionnaires.json").then(function (config) {
      var fields = config[sectionKey] || [];
      var form = document.querySelector("[data-form='" + currentPage + "']");
      var container = document.querySelector("[data-questionnaire-fields='" + sectionKey + "']");

      renderQuestionnaireFields(container, fields, storageKey);
      restoreQuestionnaireResponses(fields, storageKey);

      if (form) {
        form.addEventListener("submit", function (event) {
          event.preventDefault();
          handleQuestionnaireSubmit(currentPage, fields, storageKey, completionKey, nextPage);
        });
      }
    }).catch(function () {
      var summary = document.querySelector("[data-validation-summary]");
      if (summary) {
        summary.textContent = "Questionnaire questions could not be loaded.";
      }
      setError(summary, true);
    });
  }

  function renderQuestionnaireFields(container, fields, storageKey) {
    if (!container) {
      return false;
    }

    container.innerHTML = "";
    fields.forEach(function (field) {
      var wrapper = document.createElement("fieldset");
      var legend = document.createElement("legend");
      var helper = document.createElement("p");
      var status = document.createElement("span");
      var error = document.createElement("p");

      wrapper.className = "question-panel";
      wrapper.setAttribute("data-question-id", field.id);
      legend.className = "field__label";
      legend.textContent = field.label;
      status.className = "question-status";
      status.textContent = field.required ? "Required" : "Optional";
      legend.appendChild(status);
      wrapper.appendChild(legend);
      if (field.helperText) {
        helper.id = field.id + "-helper";
        helper.className = "field-help";
        helper.textContent = field.helperText;
        wrapper.appendChild(helper);
      }

      if (field.type === "textarea") {
        wrapper.appendChild(createTextareaQuestion(field, storageKey));
      } else if (field.type === "text") {
        wrapper.appendChild(createTextQuestion(field, storageKey));
      } else {
        wrapper.appendChild(createChoiceQuestion(field, storageKey));
      }

      error.id = field.id + "-error";
      error.className = "validation-message is-hidden";
      error.textContent = "Please answer this required question.";
      wrapper.appendChild(error);
      container.appendChild(wrapper);
    });

    return true;
  }

  function createChoiceQuestion(field, storageKey) {
    var group = document.createElement("div");
    group.className = "radio-group" + (isAgreementScale(field) ? " radio-group--likert" : "");
    if (isAgreementScale(field)) {
      group.setAttribute("aria-label", "Agreement scale from strongly disagree to strongly agree");
    }
    (field.responseOptions || []).forEach(function (option) {
      var optionWrapper = document.createElement("div");
      var input = document.createElement("input");
      var label = document.createElement("label");
      var inputId = field.id + "-" + option.value;

      optionWrapper.className = "radio-option";
      input.type = "radio";
      input.id = inputId;
      input.name = field.id;
      input.value = option.value;
      input.setAttribute("data-question-input", field.id);
      input.setAttribute("aria-describedby", field.id + "-error");
      input.addEventListener("change", function () {
        storeQuestionnaireValue(storageKey, field.id, input.value);
        updateOtherDetailVisibility(field, storageKey, true);
        clearQuestionError(field.id);
      });
      label.setAttribute("for", inputId);
      label.textContent = option.label;
      optionWrapper.appendChild(input);
      optionWrapper.appendChild(label);
      group.appendChild(optionWrapper);
    });
    if (hasOtherDetail(field)) {
      group.appendChild(createOtherDetailField(field, storageKey));
      updateOtherDetailVisibility(field, storageKey, false);
    }
    return group;
  }

  function createOtherDetailField(field, storageKey) {
    var wrapper = document.createElement("div");
    var label = document.createElement("label");
    var input = document.createElement("input");
    var detail = field.otherDetail;

    wrapper.className = "other-detail-field is-hidden";
    wrapper.setAttribute("data-other-detail-wrapper", field.id);

    label.className = "field__label";
    label.setAttribute("for", detail.id);
    label.textContent = detail.label || "Please specify.";

    input.type = "text";
    input.id = detail.id;
    input.name = detail.id;
    input.className = "input";
    input.maxLength = detail.maxLength || 120;
    input.placeholder = detail.placeholder || "Please specify...";
    input.setAttribute("data-question-input", detail.id);
    input.setAttribute("data-other-detail-input", field.id);
    input.setAttribute("aria-describedby", field.id + "-error");
    input.setAttribute("aria-required", "false");
    input.disabled = true;
    input.addEventListener("input", function () {
      storeQuestionnaireValue(storageKey, detail.id, input.value);
      clearQuestionError(field.id);
    });

    wrapper.appendChild(label);
    wrapper.appendChild(input);
    return wrapper;
  }

  function isAgreementScale(field) {
    var labels = (field.responseOptions || []).map(function (option) {
      return option.label;
    });
    return field.type === "scale_choice" && labels.indexOf("Strongly disagree") !== -1 && labels.indexOf("Strongly agree") !== -1;
  }

  function hasOtherDetail(field) {
    return Boolean(field.otherDetail && field.otherDetail.enabled === true && field.otherDetail.id);
  }

  function createTextQuestion(field, storageKey) {
    var wrapper = document.createElement("div");
    var input = document.createElement("input");
    input.type = "text";
    input.id = field.id;
    input.name = field.id;
    input.className = "input";
    input.maxLength = field.maxLength || 120;
    input.setAttribute("data-question-input", field.id);
    input.setAttribute("aria-describedby", getQuestionDescribedBy(field));
    input.addEventListener("input", function () {
      storeQuestionnaireValue(storageKey, field.id, input.value);
      clearQuestionError(field.id);
    });
    wrapper.appendChild(input);
    return wrapper;
  }

  function createTextareaQuestion(field, storageKey) {
    var textarea = document.createElement("textarea");
    textarea.id = field.id;
    textarea.name = field.id;
    textarea.className = "textarea";
    textarea.maxLength = field.maxLength || 1000;
    textarea.setAttribute("data-question-input", field.id);
    textarea.setAttribute("aria-describedby", getQuestionDescribedBy(field));
    textarea.addEventListener("input", function () {
      storeQuestionnaireValue(storageKey, field.id, textarea.value);
      clearQuestionError(field.id);
    });
    return textarea;
  }

  function restoreQuestionnaireResponses(fields, storageKey) {
    var responses = window.StudyApp.storage && window.StudyApp.storage.getItem(storageKey) || {};
    fields.forEach(function (field) {
      var value = responses[field.id];
      var input;

      if (typeof value === "undefined" || value === null) {
        return;
      }

      if (field.type === "single_choice" || field.type === "scale_choice") {
        input = document.querySelector("input[name='" + field.id + "'][value='" + value + "']");
        if (input) {
          input.checked = true;
        }
        if (hasOtherDetail(field)) {
          restoreOtherDetail(field, responses);
          updateOtherDetailVisibility(field, storageKey, false);
        }
        return;
      }

      input = document.querySelector("[data-question-input='" + field.id + "']");
      if (input) {
        input.value = value;
      }
    });
  }

  function getQuestionDescribedBy(field) {
    return (field.helperText ? field.id + "-helper " : "") + field.id + "-error";
  }

  function restoreOtherDetail(field, responses) {
    var input;
    if (!hasOtherDetail(field)) {
      return false;
    }
    input = document.querySelector("[data-other-detail-input='" + field.id + "']");
    if (input && typeof responses[field.otherDetail.id] === "string") {
      input.value = responses[field.otherDetail.id];
      return true;
    }
    return false;
  }

  function updateOtherDetailVisibility(field, storageKey, focusWhenShown) {
    var selected = document.querySelector("input[name='" + field.id + "']:checked");
    var wrapper = document.querySelector("[data-other-detail-wrapper='" + field.id + "']");
    var input = document.querySelector("[data-other-detail-input='" + field.id + "']");
    var show = Boolean(selected && selected.value === "other" && hasOtherDetail(field));

    if (!wrapper || !input) {
      return false;
    }

    wrapper.classList.toggle("is-hidden", !show);
    input.required = show;
    input.setAttribute("aria-required", String(show));
    input.disabled = !show;
    if (!show) {
      input.value = "";
      removeQuestionnaireValue(storageKey, field.otherDetail.id);
      input.setAttribute("aria-invalid", "false");
    } else if (focusWhenShown) {
      input.focus();
    }
    return true;
  }

  function handleQuestionnaireSubmit(currentPage, fields, storageKey, completionKey, nextPage) {
    var validation = validateQuestionnaire(fields, storageKey, true);
    var summary = document.querySelector("[data-validation-summary]");

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

    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem(completionKey, true);
    }
    if (window.StudyApp.timing) {
      window.StudyApp.timing.recordPageCompletion(currentPage);
    }
    if (window.StudyApp.navigation) {
      window.StudyApp.navigation.navigateTo(nextPage);
    }
    return true;
  }

  function validateQuestionnaire(fields, storageKey, showErrors) {
    var responses = window.StudyApp.storage && window.StudyApp.storage.getItem(storageKey) || {};
    var firstInvalid = null;

    fields.forEach(function (field) {
      var valid = !field.required || !window.StudyApp.validation.isBlank(responses[field.id]);
      var error = document.getElementById(field.id + "-error");
      var input = getQuestionInput(field);
      var otherDetailInput = hasOtherDetail(field) ? document.querySelector("[data-other-detail-input='" + field.id + "']") : null;

      if (valid && hasOtherDetail(field) && responses[field.id] === "other") {
        valid = !window.StudyApp.validation.isBlank(responses[field.otherDetail.id]);
        input = otherDetailInput || input;
      }

      if (showErrors) {
        if (error && hasOtherDetail(field) && responses[field.id] === "other" && !valid) {
          error.textContent = "Please provide details for Other.";
        } else if (error) {
          error.textContent = "Please answer this required question.";
        }
        setError(error, !valid);
        setQuestionInvalid(field, !valid);
        if (otherDetailInput) {
          otherDetailInput.setAttribute("aria-invalid", String(!valid && responses[field.id] === "other"));
        }
      }
      if (!valid && !firstInvalid) {
        firstInvalid = input;
      }
    });

    return {
      valid: firstInvalid === null,
      firstInvalid: firstInvalid
    };
  }

  function getQuestionInput(field) {
    if (field.type === "single_choice" || field.type === "scale_choice") {
      return document.querySelector("input[name='" + field.id + "']:checked") || document.querySelector("input[name='" + field.id + "']");
    }
    return document.querySelector("[data-question-input='" + field.id + "']");
  }

  function setQuestionInvalid(field, invalid) {
    var inputs = Array.prototype.slice.call(document.querySelectorAll("[data-question-input='" + field.id + "']"));
    inputs.forEach(function (input) {
      input.setAttribute("aria-invalid", String(invalid));
    });
  }

  function clearQuestionError(fieldId) {
    var error = document.getElementById(fieldId + "-error");
    setError(error, false);
    Array.prototype.slice.call(document.querySelectorAll("[data-question-input='" + fieldId + "']")).forEach(function (input) {
      input.setAttribute("aria-invalid", "false");
    });
    Array.prototype.slice.call(document.querySelectorAll("[data-other-detail-input='" + fieldId + "']")).forEach(function (input) {
      input.setAttribute("aria-invalid", "false");
    });
  }

  function storeQuestionnaireValue(storageKey, questionId, value) {
    var responses = window.StudyApp.storage && window.StudyApp.storage.getItem(storageKey) || {};
    if (!window.StudyApp.storage) {
      return false;
    }
    responses[questionId] = value;
    window.StudyApp.storage.setItem(storageKey, responses);
    return true;
  }

  function removeQuestionnaireValue(storageKey, questionId) {
    var responses = window.StudyApp.storage && window.StudyApp.storage.getItem(storageKey) || {};
    if (!window.StudyApp.storage) {
      return false;
    }
    if (Object.prototype.hasOwnProperty.call(responses, questionId)) {
      delete responses[questionId];
      window.StudyApp.storage.setItem(storageKey, responses);
    }
    return true;
  }

  function initialiseReview(currentPage) {
    var form = document.querySelector("[data-form='review']");
    var inspectButton = document.querySelector("[data-action='inspect-payload']");
    var downloadButton = document.querySelector("[data-action='download-payload']");

    renderCompletionSummary();
    initialiseDevelopmentPayloadPanel();

    if (form) {
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        handleFinalSubmit(currentPage);
      });
    }
    if (inspectButton) {
      inspectButton.addEventListener("click", inspectPayload);
    }
    if (downloadButton) {
      downloadButton.addEventListener("click", downloadPayload);
    }
  }

  function renderCompletionSummary() {
    var list = document.querySelector("[data-completion-summary]");
    var checks = getCompletionChecks();

    if (!list) {
      return false;
    }
    list.innerHTML = "";
    checks.forEach(function (check) {
      var item = document.createElement("li");
      item.className = check.complete ? "completion-list__item completion-list__item--complete" : "completion-list__item";
      item.textContent = (check.complete ? "Complete: " : "Incomplete: ") + check.label;
      list.appendChild(item);
    });
    return true;
  }

  function getCompletionChecks() {
    var submittedTrials = window.StudyApp.storage && window.StudyApp.storage.getItem("experimental.submittedTrials");
    var trialCount = Array.isArray(submittedTrials) ? submittedTrials.length : 0;
    var expectedTrialCount = getExpectedExperimentalTrialCount();

    return [
      { id: "consent", label: "Consent completed", complete: Boolean(window.StudyApp.storage && window.StudyApp.storage.getItem("consent.items")) },
      { id: "listeningSetup", label: "Listening setup completed", complete: window.StudyApp.storage && window.StudyApp.storage.getItem("listeningSetup.completed") === true },
      { id: "screening", label: "Pre-study listening task completed", complete: window.StudyApp.storage && window.StudyApp.storage.getItem("screening.passed") === true },
      { id: "instructions", label: "Instructions acknowledged", complete: window.StudyApp.storage && window.StudyApp.storage.getItem("instructions.acknowledged") === true },
      { id: "practice", label: "Practice completed", complete: window.StudyApp.storage && window.StudyApp.storage.getItem("practice.completed") === true },
      { id: "trials", label: trialCount + " of " + expectedTrialCount + " listening tasks completed", complete: trialCount === expectedTrialCount },
      { id: "demographics", label: "Demographics completed", complete: window.StudyApp.storage && window.StudyApp.storage.getItem("demographics.completed") === true },
      { id: "postTask", label: "Post-task questionnaire completed", complete: window.StudyApp.storage && window.StudyApp.storage.getItem("postTask.completed") === true }
    ];
  }

  function getExpectedExperimentalTrialCount() {
    var trialOrder = window.StudyApp.storage && window.StudyApp.storage.getItem("experimental.trialOrder");
    if (trialOrder && Array.isArray(trialOrder.trials) && trialOrder.trials.length > 0) {
      return trialOrder.trials.length;
    }
    return 6;
  }

  function areRequiredStagesComplete() {
    return getCompletionChecks().every(function (check) {
      return check.complete;
    });
  }

  function handleFinalSubmit(currentPage) {
    var summary = document.querySelector("[data-validation-summary]");
    var button = document.querySelector("[data-final-submit]");

    if (window.StudyApp.storage && window.StudyApp.storage.getItem("final.submissionCompleted") === true) {
      setError(summary, true);
      if (summary) {
        summary.textContent = "This study session has already been submitted.";
        summary.focus();
      }
      window.StudyApp.navigation.navigateTo("completion.html");
      return false;
    }

    if (window.StudyApp.storage && window.StudyApp.storage.getItem("final.submissionInProgress") === true) {
      return false;
    }

    if (!areRequiredStagesComplete()) {
      setError(summary, true);
      if (summary) {
        summary.textContent = "Final submission is blocked until all required study stages are complete.";
        summary.focus();
      }
      renderCompletionSummary();
      return false;
    }

    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("final.submissionInProgress", true);
    }
    setDisabled(button, true);
    setError(summary, true);
    if (summary) {
      summary.textContent = "Saving your responses...";
      summary.focus();
    }

    window.StudyApp.netlifySubmission.buildAndSubmit().then(function (payload) {
      if (window.StudyApp.storage) {
        window.StudyApp.storage.setItem("final.payload", payload);
        window.StudyApp.storage.setItem("final.submissionInProgress", false);
        window.StudyApp.storage.setItem("final.submissionCompleted", true);
        window.StudyApp.storage.setItem("final.submitted", true);
        window.StudyApp.storage.setItem("final.submissionResult", {
          submittedAt: payload.completed_at,
          studyId: payload.study_id,
          formName: window.StudyApp.netlifySubmission.getFormName()
        });
      }
      if (window.StudyApp.timing) {
        window.StudyApp.timing.recordFinalSubmission();
        window.StudyApp.timing.recordPageCompletion(currentPage);
      }
      window.StudyApp.navigation.navigateTo("completion.html");
    }).catch(function () {
      if (window.StudyApp.storage) {
        window.StudyApp.storage.setItem("final.submissionInProgress", false);
      }
      setDisabled(button, false);
      setError(summary, true);
      if (summary) {
        summary.textContent = "Your responses could not be saved. Please check your connection and try Final Submit again. Your answers have not been cleared.";
        summary.focus();
      }
    });

    return true;
  }

  function buildFinalPayload() {
    if (window.StudyApp.netlifySubmission) {
      return {
        status: "available_asynchronously",
        formName: window.StudyApp.netlifySubmission.getFormName(),
        studyVersion: window.StudyApp.netlifySubmission.getStudyVersion(),
        studyId: window.StudyApp.storage.getOrCreateStudyId()
      };
    }

    var finalTimestamp = window.StudyApp.timing ? window.StudyApp.timing.nowIsoString() : new Date().toISOString();

    return {
      developmentOnly: true,
      productionSafe: false,
      warning: "Study session data for review.",
      study_id: window.StudyApp.storage.getOrCreateStudyId(),
      studyVersion: "phase_2b_development",
      timestamps: collectTimingValues(),
      consent: {
        pisDocumentOpened: window.StudyApp.storage.getItem("pis.documentOpened"),
        consentDocumentOpened: window.StudyApp.storage.getItem("consent.documentOpened"),
        pisAcknowledged: window.StudyApp.storage.getItem("pis.acknowledged"),
        consentItems: window.StudyApp.storage.getItem("consent.items")
      },
      listeningSetup: {
        testAudioPlayed: window.StudyApp.storage.getItem("listeningSetup.testAudioPlayed"),
        headphones: window.StudyApp.storage.getItem("listeningSetup.headphones"),
        quietEnvironment: window.StudyApp.storage.getItem("listeningSetup.quietEnvironment"),
        comfortableVolume: window.StudyApp.storage.getItem("listeningSetup.comfortableVolume"),
        completed: window.StudyApp.storage.getItem("listeningSetup.completed")
      },
      screening: {
        passed: window.StudyApp.storage.getItem("screening.passed"),
        failed: window.StudyApp.storage.getItem("screening.failed"),
        totalScore: window.StudyApp.storage.getItem("screening.totalScore"),
        attemptRecords: window.StudyApp.storage.getItem("screening.attemptRecords")
      },
      instructions: {
        acknowledged: window.StudyApp.storage.getItem("instructions.acknowledged")
      },
      practice: {
        completed: window.StudyApp.storage.getItem("practice.completed"),
        completionTimestamp: window.StudyApp.storage.getItem("timing.practiceCompletion")
      },
      groupAssignment: window.StudyApp.storage.getItem("experimental.groupAssignment"),
      trialOrder: window.StudyApp.storage.getItem("experimental.trialOrder"),
      experimentalResponses: window.StudyApp.storage.getItem("experimental.submittedTrials"),
      demographics: window.StudyApp.storage.getItem("demographics.responses"),
      postTask: window.StudyApp.storage.getItem("postTask.responses"),
      finalSubmissionTimestamp: finalTimestamp
    };
  }

  function collectTimingValues() {
    var keys = window.StudyApp.storage.getDocumentedDevelopmentKeys().filter(function (key) {
      return key.indexOf("timing.") === 0;
    });
    var result = {};
    keys.forEach(function (key) {
      var value = window.StudyApp.storage.getItem(key);
      if (value !== null) {
        result[key] = value;
      }
    });
    return result;
  }

  function initialiseDevelopmentPayloadPanel() {
    var panel = document.querySelector("[data-development-payload-panel]");

    fetchJson("../config/study-config.json").then(function (config) {
      var enabled = Boolean(config.frontendDevelopmentMode === true && config.appEnvironment === "development");
      if (panel) {
        panel.classList.toggle("is-hidden", !enabled);
      }
    }).catch(function () {
      if (panel) {
        panel.classList.add("is-hidden");
      }
    });
  }

  function inspectPayload() {
    var preview = document.querySelector("[data-payload-preview]");
    var storedPayload = window.StudyApp.storage && window.StudyApp.storage.getItem("final.payload");
    if (window.StudyApp.netlifySubmission && !storedPayload) {
      window.StudyApp.netlifySubmission.buildSubmissionPayload().then(function (payload) {
        if (preview) {
          preview.textContent = JSON.stringify(payload, null, 2);
          preview.classList.remove("is-hidden");
          preview.focus();
        }
      }).catch(function () {
        if (preview) {
          preview.textContent = "Submission payload could not be prepared. Please complete all required study stages first.";
          preview.classList.remove("is-hidden");
          preview.focus();
        }
      });
      return;
    }
    var payload = storedPayload || buildFinalPayload();
    if (preview) {
      preview.textContent = JSON.stringify(payload, null, 2);
      preview.classList.remove("is-hidden");
      preview.focus();
    }
  }

  function downloadPayload() {
    var storedPayload = window.StudyApp.storage && window.StudyApp.storage.getItem("final.payload");
    if (window.StudyApp.netlifySubmission && !storedPayload) {
      window.StudyApp.netlifySubmission.buildSubmissionPayload().then(triggerPayloadDownload).catch(function () {
        inspectPayload();
      });
      return;
    }
    triggerPayloadDownload(storedPayload || buildFinalPayload());
  }

  function triggerPayloadDownload(payload) {
    var blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    var link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "intent2control-study-session-data.json";
    document.body.appendChild(link);
    link.click();
    URL.revokeObjectURL(link.href);
    link.remove();
  }

  function initialiseCompletion() {
    var studyId = document.querySelector("[data-session-id]");
    if (studyId && window.StudyApp.storage) {
      studyId.textContent = window.StudyApp.storage.getOrCreateStudyId();
    }
  }

  function fetchJson(path) {
    return fetch(path, { cache: "no-store" }).then(function (response) {
      if (!response.ok) {
        throw new Error("Could not load " + path);
      }
      return response.json();
    });
  }

  function checkRelativeAsset(path) {
    return fetch(path, { method: "HEAD", cache: "no-store" }).then(function (response) {
      return response.ok;
    }).catch(function () {
      return false;
    });
  }

  function safeStartup() {
    function start() {
      try {
        initialisePage();
      } catch (error) {
        console.error("Study page initialisation failed.", error);
        showPageInitialisationError("This page could not be fully prepared. Please refresh the page and try again.");
      }
    }

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", start);
      return;
    }

    start();
  }

  function showPageInitialisationError(message) {
    var card = document.querySelector(".main-card");
    var existing = document.querySelector("[data-page-initialisation-error]");
    var errorElement = existing || document.createElement("div");

    if (!card) {
      return;
    }

    errorElement.className = "validation-summary";
    errorElement.setAttribute("data-page-initialisation-error", "");
    errorElement.setAttribute("role", "status");
    errorElement.setAttribute("tabindex", "-1");
    errorElement.textContent = message;

    if (!existing) {
      card.insertBefore(errorElement, card.firstElementChild ? card.firstElementChild.nextSibling : null);
    }

    errorElement.focus();
  }

  safeStartup();

  return {
    getCurrentPage: getCurrentPage,
    initialisePage: initialisePage
  };
}());
