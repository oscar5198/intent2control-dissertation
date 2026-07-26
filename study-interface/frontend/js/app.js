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
    selectedAnswers: {}
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
      initialiseQuestionnaire(currentPage, "demographic", "demographics.responses", "demographics.completed", "post-task.html");
    }

    if (currentPage === "post-task") {
      initialiseQuestionnaire(currentPage, "postTask", "postTask.responses", "postTask.completed", "review.html");
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
            window.StudyApp.storage.getOrCreateDevelopmentSessionId();
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
      window.StudyApp.navigation.navigateTo("practice.html");
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
    var excerpt = document.querySelector("[data-practice-excerpt-title]");
    var notice = document.querySelector("[data-practice-development-notice]");
    var container = document.querySelector("[data-practice-versions]");

    if (title) {
      title.textContent = config.practiceScenario.title;
    }
    if (text) {
      text.textContent = config.practiceScenario.text;
    }
    if (excerpt) {
      excerpt.textContent = config.practiceExcerpt.title;
    }
    if (notice) {
      notice.textContent = config.developmentLabel || "Practice trial";
      notice.classList.toggle("is-hidden", config.developmentOnly !== true);
    }
    if (!container) {
      return false;
    }

    container.innerHTML = "";
    container.appendChild(createPracticeSection("1. Listen to the versions", "Listen to all three versions before giving your ratings. You may replay them in any order and as many times as you wish.", "trial-audio-grid", config.versions.map(function (version) {
      return createPracticeAudioCard(version);
    })));
    container.appendChild(createPracticeSection("2. Rate the versions", "Use the preference scale from 0 — Least preferred to 100 — Most preferred.", "trial-rating-grid", config.versions.map(function (version) {
      return createPracticeRatingCard(config, version);
    })));
    container.appendChild(createPracticeSection("3. Explain your ratings", "Please briefly explain what influenced your preference for each mix.", "trial-comment-grid", config.versions.map(function (version) {
      return createPracticeCommentCard(config, version);
    })));

    if (window.StudyApp.audio) {
      window.StudyApp.audio.setupAudioControls(container);
    }
    return true;
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

  function createPracticeAudioCard(version) {
    var card = document.createElement("article");
    var heading = document.createElement("h3");
    var audio = document.createElement("audio");
    var source = document.createElement("source");
    var audioError = document.createElement("p");

    card.className = "version-card version-card--audio";
    heading.textContent = version.label;
    audio.className = "audio-control";
    audio.controls = true;
    audio.preload = "none";
    audio.setAttribute("aria-label", "Practice " + version.label + " audio");
    audio.setAttribute("data-audio-id", "practice." + version.id);
    source.src = "../" + version.audioPath;
    source.type = getAudioMimeType(version.audioPath);
    audio.appendChild(source);
    audioError.id = version.id + "-audio-error";
    audioError.className = "validation-message is-hidden";
    audioError.textContent = version.label + " audio could not be loaded.";
    audio.addEventListener("error", function () {
      setError(audioError, true);
    });

    card.appendChild(heading);
    card.appendChild(audio);
    card.appendChild(audioError);
    return card;
  }

  function createPracticeRatingCard(config, version) {
    var card = document.createElement("article");
    var heading = document.createElement("h3");
    var ratingLabel = document.createElement("label");
    var ratingRow = document.createElement("div");
    var ratingMin = document.createElement("span");
    var slider = document.createElement("input");
    var ratingMax = document.createElement("span");
    var ratingValue = document.createElement("p");
    var ratingError = document.createElement("p");

    card.className = "version-card version-card--rating";
    heading.textContent = version.label;
    ratingLabel.className = "field__label";
    ratingLabel.setAttribute("for", version.id + "-rating");
    ratingLabel.textContent = "Preference rating";

    ratingRow.className = "rating-row";
    ratingMin.textContent = String(config.ratingScale.minimum);
    ratingMax.textContent = String(config.ratingScale.maximum);
    ratingMin.className = "rating-endpoint";
    ratingMax.className = "rating-endpoint rating-endpoint--max";
    slider.id = version.id + "-rating";
    slider.name = version.id + "Rating";
    slider.className = "rating-slider";
    slider.type = "range";
    slider.min = String(config.ratingScale.minimum);
    slider.max = String(config.ratingScale.maximum);
    slider.step = String(config.ratingScale.step);
    slider.value = String(Math.round((config.ratingScale.minimum + config.ratingScale.maximum) / 2));
    slider.setAttribute("data-practice-rating", version.id);
    slider.setAttribute("aria-describedby", version.id + "-rating-value " + version.id + "-rating-error");
    slider.addEventListener("input", function () {
      storePracticeRating(version.id, slider.value, true);
      updatePracticeRatingValue(version.id, slider.value, true);
      updatePracticeCompletionState(config);
    });
    ratingRow.appendChild(ratingMin);
    ratingRow.appendChild(slider);
    ratingRow.appendChild(ratingMax);

    ratingValue.id = version.id + "-rating-value";
    ratingValue.className = "rating-value";
    ratingValue.textContent = "Current value: not set";
    ratingValue.setAttribute("aria-live", "polite");

    ratingError.id = version.id + "-rating-error";
    ratingError.className = "validation-message is-hidden";
    ratingError.textContent = "Provide a rating for " + version.label + ".";

    card.appendChild(heading);
    card.appendChild(ratingLabel);
    card.appendChild(ratingRow);
    card.appendChild(ratingValue);
    card.appendChild(ratingError);
    return card;
  }

  function createPracticeCommentCard(config, version) {
    var card = document.createElement("article");
    var heading = document.createElement("h3");
    var commentLabel = document.createElement("label");
    var comment = document.createElement("textarea");
    var commentError = document.createElement("p");

    card.className = "version-card version-card--comment";
    heading.textContent = version.label;
    commentLabel.className = "field__label";
    commentLabel.setAttribute("for", version.id + "-comment");
    commentLabel.textContent = "Required comment";
    comment.id = version.id + "-comment";
    comment.name = version.id + "Comment";
    comment.className = "textarea";
    comment.setAttribute("data-practice-comment", version.id);
    comment.setAttribute("aria-describedby", version.id + "-comment-error");
    comment.addEventListener("input", function () {
      storePracticeComment(version.id, comment.value);
      updatePracticeCompletionState(config);
    });
    commentError.id = version.id + "-comment-error";
    commentError.className = "validation-message is-hidden";
    commentError.textContent = "Provide a comment for " + version.label + ".";

    card.appendChild(heading);
    card.appendChild(commentLabel);
    card.appendChild(comment);
    card.appendChild(commentError);
    return card;
  }

  function restorePracticeResponses(config) {
    var ratings = window.StudyApp.storage && window.StudyApp.storage.getItem("practice.ratings") || {};
    var touched = window.StudyApp.storage && window.StudyApp.storage.getItem("practice.ratingTouched") || {};
    var comments = window.StudyApp.storage && window.StudyApp.storage.getItem("practice.comments") || {};

    config.versions.forEach(function (version) {
      var slider = document.querySelector("[data-practice-rating='" + version.id + "']");
      var comment = document.querySelector("[data-practice-comment='" + version.id + "']");
      if (slider && touched[version.id] === true && typeof ratings[version.id] !== "undefined") {
        slider.value = String(ratings[version.id]);
        updatePracticeRatingValue(version.id, slider.value, true);
      }
      if (comment && typeof comments[version.id] === "string") {
        comment.value = comments[version.id];
      }
    });
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
      comments: window.StudyApp.storage.getItem("practice.comments") || {}
    });
    return true;
  }

  function storePracticeComment(versionId, value) {
    var comments = window.StudyApp.storage && window.StudyApp.storage.getItem("practice.comments") || {};
    if (!window.StudyApp.storage) {
      return false;
    }
    comments[versionId] = value;
    window.StudyApp.storage.setItem("practice.comments", comments);
    window.StudyApp.storage.setItem("practice.currentResponses", {
      ratings: window.StudyApp.storage.getItem("practice.ratings") || {},
      ratingTouched: window.StudyApp.storage.getItem("practice.ratingTouched") || {},
      comments: comments
    });
    return true;
  }

  function updatePracticeRatingValue(versionId, value, touched) {
    var valueElement = document.getElementById(versionId + "-rating-value");
    if (valueElement) {
      valueElement.textContent = touched ? "Current value: " + value : "Current value: not set";
    }
  }

  function updatePracticeCompletionState(config) {
    var completeButton = document.querySelector("[data-practice-complete]");
    setDisabled(completeButton, !isPracticeComplete(config, false).valid);
  }

  function isPracticeComplete(config, showErrors) {
    var ratings = window.StudyApp.storage && window.StudyApp.storage.getItem("practice.ratings") || {};
    var touched = window.StudyApp.storage && window.StudyApp.storage.getItem("practice.ratingTouched") || {};
    var comments = window.StudyApp.storage && window.StudyApp.storage.getItem("practice.comments") || {};
    var firstInvalid = null;

    config.versions.forEach(function (version) {
      var slider = document.querySelector("[data-practice-rating='" + version.id + "']");
      var comment = document.querySelector("[data-practice-comment='" + version.id + "']");
      var ratingError = document.getElementById(version.id + "-rating-error");
      var commentError = document.getElementById(version.id + "-comment-error");
      var ratingValid = touched[version.id] === true && typeof ratings[version.id] === "number";
      var commentValid = !window.StudyApp.validation || window.StudyApp.validation.validateRequiredComment(comments[version.id]);

      if (showErrors) {
        setError(ratingError, !ratingValid);
        setError(commentError, !commentValid);
        if (slider) {
          slider.setAttribute("aria-invalid", String(!ratingValid));
        }
        if (comment) {
          comment.setAttribute("aria-invalid", String(!commentValid));
        }
      }
      if (!ratingValid && !firstInvalid) {
        firstInvalid = slider;
      }
      if (!commentValid && !firstInvalid) {
        firstInvalid = comment;
      }
    });

    return {
      valid: !firstInvalid,
      firstInvalid: firstInvalid
    };
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
      window.StudyApp.navigation.navigateTo("trial.html");
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
    var setupAudioPath = "../assets/audio/setup-test-development.mp3";

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
    if (window.StudyApp.navigation) {
      window.StudyApp.navigation.navigateTo("screening.html");
    }

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

      if (window.StudyApp.storage) {
        window.StudyApp.storage.setItem("screening.activeAttempt", true);
        window.StudyApp.storage.setItem("screening.attemptNumber", screeningState.attemptNumber);
        window.StudyApp.storage.setItem("screening.currentItemIndex", screeningState.currentIndex);
      }
      if (window.StudyApp.timing) {
        window.StudyApp.timing.recordScreeningStart(screeningState.attemptNumber);
      }

      renderScreening();
      attachScreeningActions(currentPage);
    }).catch(function () {
      var warning = document.querySelector("[data-screening-development-warning]");
      if (warning) {
        warning.textContent = "Screening materials could not be loaded. Continue is blocked until the study materials are available.";
      }
      setError(warning, true);
    });
  }

  function renderScreening() {
    var config = screeningState.config;
    if (!config || !config.items || !config.items.length) {
      return;
    }

    var warning = document.querySelector("[data-screening-development-warning]");
    var instructions = document.querySelector("[data-screening-instructions]");

    if (instructions) {
      instructions.textContent = config.screeningInstructions;
    }

    if (warning) {
      warning.textContent = config.developmentLabel || "Audio Screening";
    }
    setError(warning, config.developmentOnly === true || config.productionReady === false);
    renderScreeningItem();
  }

  function renderScreeningItem() {
    var config = screeningState.config;
    var item = config.items[screeningState.currentIndex];
    var progress = document.querySelector("[data-screening-item-progress]");
    var heading = document.querySelector("[data-screening-item-heading]");
    var prompt = document.querySelector("[data-screening-item-prompt]");
    var audioContainer = document.querySelector("[data-screening-audio]");
    var answerContainer = document.querySelector("[data-screening-answers]");

    if (!item) {
      return;
    }

    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("screening.currentItemIndex", screeningState.currentIndex);
    }

    if (window.StudyApp.timing) {
      window.StudyApp.timing.recordScreeningItemStart(item.id, screeningState.attemptNumber);
    }

    if (progress) {
      progress.textContent = "Question " + (screeningState.currentIndex + 1) + " of " + config.items.length;
    }
    if (heading) {
      heading.textContent = "Screening item";
    }
    if (prompt) {
      prompt.textContent = item.prompt === "TBC" ? "Final screening prompt is TBC." : item.prompt;
    }

    renderScreeningAudio(item, audioContainer);
    renderScreeningAnswers(item, answerContainer);
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
      label.textContent = choice.label;

      var audio = document.createElement("audio");
      audio.className = "audio-control";
      audio.controls = true;
      audio.preload = "none";
      audio.setAttribute("aria-label", choice.label);
      audio.setAttribute("data-audio-id", getScreeningAudioId(item.id, choice.id));

      var source = document.createElement("source");
      source.src = "../" + choice.audioPath;
      source.type = getAudioMimeType(choice.audioPath);
      audio.appendChild(source);

      var warning = document.createElement("p");
      warning.className = "validation-message is-hidden";
      warning.textContent = choice.label + " could not be loaded.";
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
      wrapper.className = "radio-option";

      var input = document.createElement("input");
      input.type = "radio";
      input.name = "screeningAnswer";
      input.id = "screening-answer-" + option.value;
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
      label.textContent = option.label;

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
        handleScreeningAnswerSubmit();
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
        showScreeningResult("Audio screening completed. You may continue.", true);
      });
    }
  }

  function handleScreeningAnswerSubmit() {
    var config = screeningState.config;
    var item = config.items[screeningState.currentIndex];
    var error = document.getElementById("screening-answer-error");
    var summary = document.querySelector("[data-validation-summary]");
    var selected = document.querySelector("input[name='screeningAnswer']:checked");
    var requiredAudioPlayed = item.requiredAudioChoices.every(function (choiceId) {
      return hasScreeningAudioPlayed(item.id, choiceId);
    });
    var isValid = selected && requiredAudioPlayed;

    setError(error, !isValid);
    setError(summary, !isValid);

    if (!isValid) {
      if (summary) {
        summary.focus();
      }
      if (!requiredAudioPlayed) {
        var firstAudio = document.querySelector("[data-screening-audio] audio");
        if (firstAudio) {
          firstAudio.focus();
        }
      } else if (document.querySelector("input[name='screeningAnswer']")) {
        document.querySelector("input[name='screeningAnswer']").focus();
      }
      return false;
    }

    if (window.StudyApp.timing) {
      window.StudyApp.timing.recordScreeningItemSubmission(item.id, screeningState.attemptNumber);
    }

    var score = scoreScreeningItem(item, selected.value);
    screeningState.responses[screeningState.currentIndex] = {
      itemId: item.id,
      answer: selected.value,
      correctAnswer: item.correctAnswer,
      score: score
    };
    screeningState.scores.push(score);

    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("screening.itemResponses", screeningState.responses);
      window.StudyApp.storage.setItem("screening.itemScores", screeningState.scores);
    }

    if (screeningState.currentIndex < config.items.length - 1) {
      screeningState.currentIndex += 1;
      if (window.StudyApp.storage) {
        window.StudyApp.storage.setItem("screening.currentItemIndex", screeningState.currentIndex);
      }
      renderScreeningItem();
      return true;
    }

    completeScreening();
    return true;
  }

  function scoreScreeningItem(item, answer) {
    if (!item.correctAnswer || item.correctAnswer === "TBC") {
      return null;
    }

    return item.correctAnswer === answer ? 1 : 0;
  }

  function completeScreening() {
    var config = screeningState.config;
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
      showScreeningResult("Screening passed. Your score was " + total + " out of " + config.items.length + ".", true);
      return;
    }

    if (canRetryScreening()) {
      showScreeningResult("Screening not passed. Your score was " + total + " out of " + config.items.length + ". You may retry the screening.", false);
      return;
    }

    showScreeningResult("Screening was not passed after the maximum number of attempts. Please contact the researcher if you need guidance.", false);
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
    attempts.push({
      attemptNumber: screeningState.attemptNumber,
      score: typeof total === "number" ? total : null,
      passed: passed === true,
      responses: screeningState.responses.slice()
    });
    window.StudyApp.storage.setItem("screening.attemptRecords", attempts);
  }

  function showScreeningResult(message, passed) {
    var result = document.querySelector("[data-screening-result]");
    var feedback = document.querySelector("[data-screening-feedback]");
    var retryButton = document.querySelector("[data-action='retry-screening']");
    var continueButton = document.querySelector("[data-action='continue-after-screening']");
    var itemSection = document.querySelector("[data-screening-item-section]");

    if (result) {
      result.classList.remove("is-hidden");
    }
    if (itemSection) {
      itemSection.classList.add("is-hidden");
    }
    if (feedback) {
      feedback.textContent = message;
    }
    if (retryButton) {
      retryButton.classList.toggle("is-hidden", passed || !canRetryScreening());
    }
    setDisabled(continueButton, !passed);
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

    var result = document.querySelector("[data-screening-result]");
    var itemSection = document.querySelector("[data-screening-item-section]");
    if (result) {
      result.classList.add("is-hidden");
    }
    if (itemSection) {
      itemSection.classList.remove("is-hidden");
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

  function getScreeningAudioId(itemId, choiceId) {
    return "screening.attempt" + screeningState.attemptNumber + "." + itemId + "." + choiceId;
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
    return Boolean(window.StudyApp.audio && window.StudyApp.audio.hasAudioBeenPlayed(audioId));
  }

  function updateScreeningSubmitState() {
    var config = screeningState.config;
    var item = config && config.items ? config.items[screeningState.currentIndex] : null;
    var submitButton = document.querySelector("[data-action='submit-screening-answer']");
    var error = document.getElementById("screening-answer-error");
    var selected = document.querySelector("input[name='screeningAnswer']:checked");
    var requiredAudioPlayed;
    var canSubmit;

    if (!item || !submitButton) {
      return false;
    }

    requiredAudioPlayed = item.requiredAudioChoices.every(function (choiceId) {
      return hasScreeningAudioPlayed(item.id, choiceId);
    });
    canSubmit = requiredAudioPlayed && Boolean(selected);

    submitButton.textContent = screeningState.currentIndex < config.items.length - 1 ? "Next" : "Submit screening";
    setDisabled(submitButton, !canSubmit);
    setError(error, false);
    return canSubmit;
  }

  function hasUnresolvedScreeningValues(config) {
    return !config || config.screeningInstructions === "TBC" || typeof config.minimumScore !== "number" || config.items.some(function (item) {
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
      warning.textContent = "A screening attempt is active. Selecting Back again will leave the attempt and return to Listening Setup.";
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
    group.className = "radio-group";
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
        clearQuestionError(field.id);
      });
      label.setAttribute("for", inputId);
      label.textContent = option.label;
      optionWrapper.appendChild(input);
      optionWrapper.appendChild(label);
      group.appendChild(optionWrapper);
    });
    return group;
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
    input.setAttribute("aria-describedby", field.id + "-error");
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
    textarea.setAttribute("aria-describedby", field.id + "-error");
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
        return;
      }

      input = document.querySelector("[data-question-input='" + field.id + "']");
      if (input) {
        input.value = value;
      }
    });
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

      if (showErrors) {
        setError(error, !valid);
        setQuestionInvalid(field, !valid);
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
      return document.querySelector("input[name='" + field.id + "']");
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

    return [
      { id: "consent", label: "Consent completed", complete: Boolean(window.StudyApp.storage && window.StudyApp.storage.getItem("consent.items")) },
      { id: "listeningSetup", label: "Listening setup completed", complete: window.StudyApp.storage && window.StudyApp.storage.getItem("listeningSetup.completed") === true },
      { id: "screening", label: "Screening passed", complete: window.StudyApp.storage && window.StudyApp.storage.getItem("screening.passed") === true },
      { id: "instructions", label: "Instructions acknowledged", complete: window.StudyApp.storage && window.StudyApp.storage.getItem("instructions.acknowledged") === true },
      { id: "practice", label: "Practice completed", complete: window.StudyApp.storage && window.StudyApp.storage.getItem("practice.completed") === true },
      { id: "trials", label: trialCount + " of 10 trials completed", complete: trialCount === 10 },
      { id: "demographics", label: "Demographics completed", complete: window.StudyApp.storage && window.StudyApp.storage.getItem("demographics.completed") === true },
      { id: "postTask", label: "Post-task questionnaire completed", complete: window.StudyApp.storage && window.StudyApp.storage.getItem("postTask.completed") === true }
    ];
  }

  function areRequiredStagesComplete() {
    return getCompletionChecks().every(function (check) {
      return check.complete;
    });
  }

  function handleFinalSubmit(currentPage) {
    var summary = document.querySelector("[data-validation-summary]");
    var payload;

    if (window.StudyApp.storage && window.StudyApp.storage.getItem("final.submitted") === true) {
      setError(summary, true);
      if (summary) {
        summary.textContent = "This study session has already been submitted.";
        summary.focus();
      }
      window.StudyApp.navigation.navigateTo("completion.html");
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

    payload = buildFinalPayload();
    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("final.payload", payload);
      window.StudyApp.storage.setItem("final.submitted", true);
    }
    if (window.StudyApp.timing) {
      window.StudyApp.timing.recordFinalSubmission();
      window.StudyApp.timing.recordPageCompletion(currentPage);
    }
    window.StudyApp.navigation.navigateTo("completion.html");
    return true;
  }

  function buildFinalPayload() {
    var finalTimestamp = window.StudyApp.timing ? window.StudyApp.timing.nowIsoString() : new Date().toISOString();

    return {
      developmentOnly: true,
      productionSafe: false,
      warning: "Study session data for review.",
      sessionId: window.StudyApp.storage.getOrCreateDevelopmentSessionId(),
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
    var payload = window.StudyApp.storage && (window.StudyApp.storage.getItem("final.payload") || buildFinalPayload());
    if (preview) {
      preview.textContent = JSON.stringify(payload, null, 2);
      preview.classList.remove("is-hidden");
      preview.focus();
    }
  }

  function downloadPayload() {
    var payload = window.StudyApp.storage && (window.StudyApp.storage.getItem("final.payload") || buildFinalPayload());
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
    var sessionId = document.querySelector("[data-session-id]");
    if (sessionId && window.StudyApp.storage) {
      sessionId.textContent = window.StudyApp.storage.getOrCreateDevelopmentSessionId();
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
