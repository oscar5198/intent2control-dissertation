"use strict";

/*
  Temporary local development state abstraction.
  localStorage may be useful during static prototyping only.
  It is not the final secure research-data store.
  Final persistence depends on the confirmed QMUL backend.
*/

window.StudyApp = window.StudyApp || {};

window.StudyApp.storage = (function () {
  var namespace = "intent2control.study.dev.";
  var documentedDevelopmentKeys = [
    "timing.studyStart",
    "timing.pageEntry.study-information-consent",
    "timing.pageCompletion.study-information-consent",
    "timing.studyInformationConsentCompletion",
    "timing.consentCompletion",
    "timing.pageEntry.listening-setup",
    "timing.pageCompletion.listening-setup",
    "timing.listeningSetupCompletion",
    "timing.pageEntry.screening",
    "timing.pageCompletion.screening",
    "timing.screeningStart.attempt1",
    "timing.screeningItemStart.attempt1.prestudy_segment_01_rep1_order1",
    "timing.screeningItemSubmission.attempt1.prestudy_segment_01_rep1_order1",
    "timing.screeningCompletion.attempt1",
    "timing.pageEntry.instructions",
    "timing.pageCompletion.instructions",
    "timing.instructionsCompletion",
    "timing.pageEntry.practice",
    "timing.pageCompletion.practice",
    "timing.pageEntry.main-study",
    "timing.pageCompletion.main-study",
    "timing.practiceStart",
    "timing.trialStart.practice_trial",
    "timing.trialSubmission.practice_trial",
    "timing.practiceSubmission",
    "timing.practiceCompletion",
    "pis.documentOpened",
    "consent.documentOpened",
    "pis.acknowledged",
    "consent.items",
    "audio.played.setup-test-audio",
    "audio.played.screening.attempt1.prestudy_segment_01_rep1_order1.reference",
    "audio.played.screening.attempt1.prestudy_segment_01_rep1_order1.version_a",
    "audio.played.screening.attempt1.prestudy_segment_01_rep1_order1.version_b",
    "listeningSetup.testAudioPlayed",
    "listeningSetup.headphones",
    "listeningSetup.quietEnvironment",
    "listeningSetup.comfortableVolume",
    "listeningSetup.completed",
    "screening.activeAttempt",
    "screening.attemptNumber",
    "screening.currentItemIndex",
    "screening.presentationOrder.attempt1",
    "screening.selectedAnswers",
    "screening.playedStates.attempt1",
    "screening.itemResponses",
    "screening.itemScores",
    "screening.totalScore",
    "screening.attemptScore.attempt1",
    "screening.attemptRecords",
    "screening.passed",
    "screening.failed",
    "screening.developmentBypassUsed",
    "instructions.acknowledged",
    "practice.currentResponses",
    "practice.ratings",
    "practice.ratingTouched",
    "practice.comparativeComment",
    "practice.completed",
    "audio.played.practice.practice_version_a",
    "audio.played.practice.practice_version_b",
    "audio.played.practice.practice_version_c",
    "experimental.groupAssignment",
    "experimental.excerptLabelMapping",
    "experimental.trialOrder",
    "experimental.currentTrialIndex",
    "experimental.currentResponses",
    "experimental.unsavedTrial.1",
    "experimental.submittedTrials",
    "experimental.completedTrialIndices",
    "experimental.firstPlay.trial1.version_a",
    "experimental.firstPlay.trial1.version_b",
    "experimental.firstPlay.trial1.version_c",
    "audio.played.experimental.trial1.version_a",
    "audio.played.experimental.trial1.version_b",
    "audio.played.experimental.trial1.version_c",
    "timing.trialStart.experimental_trial_01",
    "timing.trialSubmission.experimental_trial_01",
    "timing.pageEntry.demographics",
    "timing.pageCompletion.demographics",
    "timing.pageEntry.post-task",
    "timing.pageCompletion.post-task",
    "timing.pageEntry.review",
    "timing.pageCompletion.review",
    "timing.pageEntry.completion",
    "session.studyId",
    "demographics.responses",
    "demographics.completed",
    "postTask.responses",
    "postTask.completed",
    "final.payload",
    "final.submissionInProgress",
    "final.submissionCompleted",
    "final.submissionResult",
    "final.submitted",
    "timing.finalSubmission"
  ];

  function isAvailable() {
    try {
      var testKey = namespace + "storageTest";
      window.localStorage.setItem(testKey, "1");
      window.localStorage.removeItem(testKey);
      return true;
    } catch (error) {
      return false;
    }
  }

  function getItem(key) {
    if (!isAvailable()) {
      return null;
    }

    try {
      var value = window.localStorage.getItem(namespace + key);
      return value ? JSON.parse(value) : null;
    } catch (error) {
      return null;
    }
  }

  function setItem(key, value) {
    if (!isAvailable()) {
      return false;
    }

    try {
      window.localStorage.setItem(namespace + key, JSON.stringify(value));
      return true;
    } catch (error) {
      return false;
    }
  }

  function removeItem(key) {
    if (!isAvailable()) {
      return false;
    }

    try {
      window.localStorage.removeItem(namespace + key);
      return true;
    } catch (error) {
      return false;
    }
  }

  function resetStudyState() {
    if (!isAvailable()) {
      return false;
    }

    try {
      Object.keys(window.localStorage).forEach(function (key) {
        if (key.indexOf(namespace) === 0) {
          window.localStorage.removeItem(key);
        }
      });
      return true;
    } catch (error) {
      return false;
    }
  }

  function getNamespace() {
    return namespace;
  }

  function getDocumentedDevelopmentKeys() {
    return documentedDevelopmentKeys.slice();
  }

  function getOrCreateStudyId() {
    var existing = getItem("session.studyId");
    var generated;

    if (existing) {
      return existing;
    }

    if (window.crypto && window.crypto.randomUUID) {
      generated = window.crypto.randomUUID();
    } else if (window.crypto && window.crypto.getRandomValues) {
      var values = new Uint32Array(4);
      window.crypto.getRandomValues(values);
      generated = Array.prototype.map.call(values, function (value) {
        return value.toString(16).padStart(8, "0");
      }).join("");
    } else {
      generated = "study_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 12);
    }

    setItem("session.studyId", generated);
    return generated;
  }

  function getOrCreateDevelopmentSessionId() {
    return getOrCreateStudyId();
  }

  return {
    getNamespace: getNamespace,
    getDocumentedDevelopmentKeys: getDocumentedDevelopmentKeys,
    isAvailable: isAvailable,
    getItem: getItem,
    setItem: setItem,
    removeItem: removeItem,
    resetStudyState: resetStudyState
    ,
    getOrCreateStudyId: getOrCreateStudyId,
    getOrCreateDevelopmentSessionId: getOrCreateDevelopmentSessionId
  };
}());
