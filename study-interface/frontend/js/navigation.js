"use strict";

/*
  Navigation responsibility placeholders.
  Responsibilities:
  - Define the allowed page order.
  - Support next/back navigation later.
  - Prevent invalid transitions once validation is implemented.
  - Avoid hidden changes to randomisation or submitted trial state.
*/

window.StudyApp = window.StudyApp || {};

window.StudyApp.navigation = (function () {
  var pageSequence = [
    "index.html",
    "study-information-consent.html",
    "listening-setup.html",
    "screening.html",
    "instructions.html",
    "practice.html",
    "main-study.html",
    "trial.html",
    "post-task.html",
    "demographics.html",
    "review.html",
    "completion.html"
  ];

  var redirects = {
    "participant-information.html": "study-information-consent.html",
    "consent.html": "study-information-consent.html"
  };

  function getPageSequence() {
    return pageSequence.slice();
  }

  function canNavigateToPage(targetPage) {
    return pageSequence.indexOf(targetPage) !== -1 || Object.prototype.hasOwnProperty.call(redirects, targetPage);
  }

  function navigateTo(targetPage) {
    if (!canNavigateToPage(targetPage)) {
      return false;
    }

    window.location.href = redirects[targetPage] || targetPage;
    return true;
  }

  function isRouteAllowed(pageId) {
    normaliseQuestionnaireOrderState();

    if (hasFinalSubmission() && pageId !== "completion") {
      return false;
    }

    if (pageId === "instructions") {
      return Boolean(window.StudyApp.storage && window.StudyApp.storage.getItem("screening.passed") === true);
    }

    if (pageId === "practice") {
      return Boolean(window.StudyApp.storage && window.StudyApp.storage.getItem("instructions.acknowledged") === true);
    }

    if (pageId === "trial") {
      return Boolean(window.StudyApp.storage && window.StudyApp.storage.getItem("practice.completed") === true);
    }

    if (pageId === "main-study") {
      return Boolean(window.StudyApp.storage && window.StudyApp.storage.getItem("practice.completed") === true);
    }

    if (pageId === "demographics") {
      return Boolean(window.StudyApp.storage && window.StudyApp.storage.getItem("postTask.completed") === true);
    }

    if (pageId === "post-task") {
      return hasCompletedExperimentalTrials();
    }

    if (pageId === "review") {
      return Boolean(window.StudyApp.storage && window.StudyApp.storage.getItem("postTask.completed") === true && window.StudyApp.storage.getItem("demographics.completed") === true);
    }

    if (pageId === "completion") {
      return hasFinalSubmission();
    }

    return true;
  }

  function getRouteFallback(pageId) {
    if (pageId === "instructions") {
      return "screening.html";
    }
    if (pageId === "practice") {
      return "instructions.html";
    }
    if (pageId === "trial") {
      return "main-study.html";
    }
    if (pageId === "main-study") {
      return "practice.html";
    }
    if (pageId === "demographics") {
      return "post-task.html";
    }
    if (pageId === "post-task") {
      return window.StudyApp.storage && window.StudyApp.storage.getItem("practice.completed") === true ? "trial.html" : "practice.html";
    }
    if (pageId === "review") {
      return "demographics.html";
    }
    if (pageId === "completion") {
      return "review.html";
    }
    return "index.html";
  }

  function hasCompletedExperimentalTrials() {
    var records = window.StudyApp.storage && window.StudyApp.storage.getItem("experimental.submittedTrials");
    var expectedTrialCount = getExpectedExperimentalTrialCount();
    return Array.isArray(records) && records.length === expectedTrialCount;
  }

  function getExpectedExperimentalTrialCount() {
    var trialOrder = window.StudyApp.storage && window.StudyApp.storage.getItem("experimental.trialOrder");
    if (trialOrder && Array.isArray(trialOrder.trials) && trialOrder.trials.length > 0) {
      return trialOrder.trials.length;
    }
    return 6;
  }

  function normaliseQuestionnaireOrderState() {
    if (!window.StudyApp.storage || hasFinalSubmission()) {
      return false;
    }

    if (window.StudyApp.storage.getItem("demographics.completed") === true && window.StudyApp.storage.getItem("postTask.completed") !== true) {
      window.StudyApp.storage.removeItem("demographics.completed");
      window.StudyApp.storage.removeItem("timing.pageCompletion.demographics");
      return true;
    }

    return false;
  }

  function hasFinalSubmission() {
    return Boolean(window.StudyApp.storage && window.StudyApp.storage.getItem("final.submitted") === true);
  }

  function goToNextPage() {
    return false;
  }

  function goToPreviousPage() {
    return false;
  }

  return {
    getPageSequence: getPageSequence,
    canNavigateToPage: canNavigateToPage,
    navigateTo: navigateTo,
    isRouteAllowed: isRouteAllowed,
    getRouteFallback: getRouteFallback,
    hasCompletedExperimentalTrials: hasCompletedExperimentalTrials,
    hasFinalSubmission: hasFinalSubmission,
    goToNextPage: goToNextPage,
    goToPreviousPage: goToPreviousPage
  };
}());
