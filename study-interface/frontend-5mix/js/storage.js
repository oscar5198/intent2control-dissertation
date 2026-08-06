"use strict";

/*
  Temporary local development state abstraction.
  localStorage may be useful during static prototyping only.
  It is not the final secure research-data store.
  Final persistence depends on the confirmed QMUL backend.
*/

window.StudyApp = window.StudyApp || {};

window.StudyApp.storage = (function () {
  var namespace = "intent2control.study.5mix.v1.";
  var stateSchemaVersion = "five_mix_state_v1_2026-08-06";
  var frontendVariant = "5mix";
  var mixCount = 5;
  var stimulusConfigurationVersion = "five_mix_frontend_v1_2026-08-06";
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
    "session.stateSchemaVersion",
    "session.frontendVariant",
    "session.mixCount",
    "session.startedAt",
    "session.lastConfigValidation",
    "practice.currentResponses",
    "practice.ratings",
    "practice.ratingTouched",
    "practice.comparativeComment",
    "practice.completed",
    "audio.played.practice.practice_version_a",
    "audio.played.practice.practice_version_b",
    "audio.played.practice.practice_version_c",
    "audio.played.practice.practice_version_d",
    "audio.played.practice.practice_version_e",
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
    "experimental.firstPlay.trial1.version_d",
    "experimental.firstPlay.trial1.version_e",
    "audio.played.experimental.trial1.version_a",
    "audio.played.experimental.trial1.version_b",
    "audio.played.experimental.trial1.version_c",
    "audio.played.experimental.trial1.version_d",
    "audio.played.experimental.trial1.version_e",
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
      var storageKey = namespace + key;
      var value = window.localStorage.getItem(storageKey);
      return value ? JSON.parse(value) : null;
    } catch (error) {
      try {
        window.localStorage.removeItem(namespace + key);
      } catch (removeError) {
        return null;
      }
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

  function clearKeysByPrefix(prefixes) {
    if (!isAvailable()) {
      return false;
    }

    try {
      Object.keys(window.localStorage).forEach(function (storageKey) {
        var localKey;
        if (storageKey.indexOf(namespace) !== 0) {
          return;
        }
        localKey = storageKey.slice(namespace.length);
        if (prefixes.some(function (prefix) { return localKey.indexOf(prefix) === 0; })) {
          window.localStorage.removeItem(storageKey);
        }
      });
      return true;
    } catch (error) {
      return false;
    }
  }

  function clearExperimentalAttemptState() {
    return clearKeysByPrefix([
      "experimental.",
      "audio.played.experimental.",
      "timing.trialStart.experimental_",
      "timing.trialSubmission.experimental_",
      "timing.pageEntry.main-study",
      "timing.pageCompletion.main-study",
      "timing.pageEntry.trial",
      "timing.pageCompletion.trial",
      "timing.pageEntry.post-task",
      "timing.pageCompletion.post-task",
      "timing.pageEntry.demographics",
      "timing.pageCompletion.demographics",
      "timing.pageEntry.review",
      "timing.pageCompletion.review",
      "postTask.",
      "demographics.",
      "final."
    ]);
  }

  function validateStoredStateAgainstConfig(config) {
    var trialOrder = getItem("experimental.trialOrder");
    var expectedVersion = config && config.stimulusConfigurationVersion;
    var expectedMixes = config && config.trialGeneration ? config.trialGeneration.versionsPerTrial : null;
    var configuredStimulusIds = {};
    var changed = false;

    if (!expectedVersion || !expectedMixes) {
      return { valid: true, changed: false, reason: "config_unavailable" };
    }

    (config.excerpts || []).forEach(function (excerpt) {
      configuredStimulusIds[excerpt.id] = (excerpt.mixes || []).map(function (mix) {
        return mix.stimulusId;
      });
    });

    if (getItem("session.stateSchemaVersion") !== stateSchemaVersion ||
        getItem("session.frontendVariant") !== frontendVariant ||
        getItem("session.mixCount") !== mixCount) {
      clearExperimentalAttemptState();
      setItem("session.stateSchemaVersion", stateSchemaVersion);
      setItem("session.frontendVariant", frontendVariant);
      setItem("session.mixCount", mixCount);
      changed = true;
    }

    if (!trialOrder) {
      setItem("session.lastConfigValidation", {
        stimulusConfigurationVersion: expectedVersion,
        validatedAt: new Date().toISOString()
      });
      return { valid: true, changed: changed, reason: changed ? "schema_updated" : "no_trial_order" };
    }

    if (trialOrder.stimulusConfigurationVersion !== expectedVersion ||
        !Array.isArray(trialOrder.trials) ||
        trialOrder.trials.some(function (trial) {
          var configured = configuredStimulusIds[trial.excerptId] || [];
          var mappings = Array.isArray(trial.versionMappings) ? trial.versionMappings : [];
          var seen = {};
          return mappings.length !== expectedMixes ||
            mappings.some(function (mapping) {
              if (!mapping.stimulusId || configured.indexOf(mapping.stimulusId) === -1 || seen[mapping.stimulusId]) {
                return true;
              }
              seen[mapping.stimulusId] = true;
              return false;
            });
        })) {
      clearExperimentalAttemptState();
      setItem("session.lastConfigValidation", {
        stimulusConfigurationVersion: expectedVersion,
        resetAt: new Date().toISOString(),
        reason: "incompatible_trial_order"
      });
      return { valid: false, changed: true, reason: "incompatible_trial_order" };
    }

    setItem("session.lastConfigValidation", {
      stimulusConfigurationVersion: expectedVersion,
      validatedAt: new Date().toISOString()
    });
    return { valid: true, changed: changed, reason: changed ? "schema_updated" : "ok" };
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
    setItem("session.stateSchemaVersion", stateSchemaVersion);
    setItem("session.frontendVariant", frontendVariant);
    setItem("session.mixCount", mixCount);
    if (!getItem("session.startedAt")) {
      setItem("session.startedAt", new Date().toISOString());
    }
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
    clearExperimentalAttemptState: clearExperimentalAttemptState,
    validateStoredStateAgainstConfig: validateStoredStateAgainstConfig,
    getStateSchemaVersion: function () { return stateSchemaVersion; },
    getFrontendVariant: function () { return frontendVariant; },
    getMixCount: function () { return mixCount; },
    getStimulusConfigurationVersion: function () { return stimulusConfigurationVersion; },
    getOrCreateStudyId: getOrCreateStudyId,
    getOrCreateDevelopmentSessionId: getOrCreateDevelopmentSessionId
  };
}());
