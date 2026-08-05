"use strict";

/*
  Response-time responsibility placeholders.
  Confirmed timing points:
  - Study start timestamp.
  - Page entry timestamp.
  - Page completion timestamp.
  - Trial start timestamp.
  - Trial submission timestamp.
  - Final submission timestamp.
  - Duration derivation from timestamp pairs.
*/

window.StudyApp = window.StudyApp || {};

window.StudyApp.timing = (function () {
  function nowIsoString() {
    return new Date().toISOString();
  }

  function recordStudyStart() {
    var timestamp = nowIsoString();
    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("timing.studyStart", timestamp);
    }
    return timestamp;
  }

  function recordPageEntry(pageId) {
    var timestamp = nowIsoString();
    if (window.StudyApp.storage && pageId) {
      window.StudyApp.storage.setItem("timing.pageEntry." + pageId, timestamp);
    }
    return timestamp;
  }

  function recordPageCompletion(pageId) {
    var timestamp = nowIsoString();
    if (window.StudyApp.storage && pageId) {
      window.StudyApp.storage.setItem("timing.pageCompletion." + pageId, timestamp);
    }
    return timestamp;
  }

  function recordTrialStart(trialId) {
    var timestamp = nowIsoString();
    if (window.StudyApp.storage && trialId) {
      window.StudyApp.storage.setItem("timing.trialStart." + trialId, timestamp);
    }
    return timestamp;
  }

  function recordTrialSubmission(trialId) {
    var timestamp = nowIsoString();
    if (window.StudyApp.storage && trialId) {
      window.StudyApp.storage.setItem("timing.trialSubmission." + trialId, timestamp);
    }
    return timestamp;
  }

  function recordFinalSubmission() {
    var timestamp = nowIsoString();
    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("timing.finalSubmission", timestamp);
    }
    return timestamp;
  }

  function recordConsentCompletion() {
    var timestamp = nowIsoString();
    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("timing.consentCompletion", timestamp);
    }
    return timestamp;
  }

  function recordStudyInformationConsentCompletion() {
    var timestamp = nowIsoString();
    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("timing.studyInformationConsentCompletion", timestamp);
    }
    return timestamp;
  }

  function recordListeningSetupCompletion() {
    var timestamp = nowIsoString();
    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("timing.listeningSetupCompletion", timestamp);
    }
    return timestamp;
  }

  function recordScreeningStart(attemptNumber) {
    var timestamp = nowIsoString();
    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("timing.screeningStart.attempt" + attemptNumber, timestamp);
    }
    return timestamp;
  }

  function recordScreeningItemStart(itemId, attemptNumber) {
    var timestamp = nowIsoString();
    if (window.StudyApp.storage && itemId) {
      window.StudyApp.storage.setItem("timing.screeningItemStart.attempt" + attemptNumber + "." + itemId, timestamp);
    }
    return timestamp;
  }

  function recordScreeningItemSubmission(itemId, attemptNumber) {
    var timestamp = nowIsoString();
    if (window.StudyApp.storage && itemId) {
      window.StudyApp.storage.setItem("timing.screeningItemSubmission.attempt" + attemptNumber + "." + itemId, timestamp);
    }
    return timestamp;
  }

  function recordScreeningCompletion(attemptNumber) {
    var timestamp = nowIsoString();
    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("timing.screeningCompletion.attempt" + attemptNumber, timestamp);
    }
    return timestamp;
  }

  function recordInstructionsCompletion() {
    var timestamp = nowIsoString();
    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("timing.instructionsCompletion", timestamp);
    }
    return timestamp;
  }

  function recordPracticeStart() {
    var timestamp = nowIsoString();
    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("timing.practiceStart", timestamp);
    }
    return timestamp;
  }

  function recordPracticeSubmission() {
    var timestamp = nowIsoString();
    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("timing.practiceSubmission", timestamp);
    }
    return timestamp;
  }

  function recordPracticeCompletion() {
    var timestamp = nowIsoString();
    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("timing.practiceCompletion", timestamp);
    }
    return timestamp;
  }

  function deriveDuration(startTimestamp, endTimestamp) {
    var start = Date.parse(startTimestamp);
    var end = Date.parse(endTimestamp);

    if (Number.isNaN(start) || Number.isNaN(end) || end < start) {
      return null;
    }

    return end - start;
  }

  return {
    nowIsoString: nowIsoString,
    recordStudyStart: recordStudyStart,
    recordPageEntry: recordPageEntry,
    recordPageCompletion: recordPageCompletion,
    recordTrialStart: recordTrialStart,
    recordTrialSubmission: recordTrialSubmission,
    recordFinalSubmission: recordFinalSubmission,
    recordConsentCompletion: recordConsentCompletion,
    recordStudyInformationConsentCompletion: recordStudyInformationConsentCompletion,
    recordListeningSetupCompletion: recordListeningSetupCompletion,
    recordScreeningStart: recordScreeningStart,
    recordScreeningItemStart: recordScreeningItemStart,
    recordScreeningItemSubmission: recordScreeningItemSubmission,
    recordScreeningCompletion: recordScreeningCompletion,
    recordInstructionsCompletion: recordInstructionsCompletion,
    recordPracticeStart: recordPracticeStart,
    recordPracticeSubmission: recordPracticeSubmission,
    recordPracticeCompletion: recordPracticeCompletion,
    deriveDuration: deriveDuration
  };
}());
