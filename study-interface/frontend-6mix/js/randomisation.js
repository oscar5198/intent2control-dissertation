"use strict";

/*
  Randomisation responsibilities.
  Responsibilities:
  - Temporary frontend group assignment for development.
  - Scenario order randomisation.
  - Excerpt order randomisation.
  - Neutral Version A-F mapping.
  - Use cryptographically secure randomness where possible.
  - No final balancing algorithm yet.
*/

window.StudyApp = window.StudyApp || {};

window.StudyApp.randomisation = (function () {
  var trialOrderAlgorithm = "scenario_pairs_v1";
  var excerptLabelMappingKey = "experimental.excerptLabelMapping";

  function getSecureRandomNumber() {
    if (window.crypto && window.crypto.getRandomValues) {
      var values = new Uint32Array(1);
      window.crypto.getRandomValues(values);
      return values[0] / 4294967296;
    }

    return Math.random();
  }

  function shuffle(items) {
    var result = items.slice();
    var index = result.length;
    var randomIndex;
    var temporaryValue;

    while (index > 0) {
      randomIndex = Math.floor(getSecureRandomNumber() * index);
      index -= 1;
      temporaryValue = result[index];
      result[index] = result[randomIndex];
      result[randomIndex] = temporaryValue;
    }

    return result;
  }

  function assignGroup(groups) {
    var stored = window.StudyApp.storage && window.StudyApp.storage.getItem("experimental.groupAssignment");
    var groupList = Array.isArray(groups) ? groups : [];
    var selectedGroup;

    if (stored && groupList.some(function (group) { return group.id === stored.groupId; })) {
      return stored;
    }

    if (groupList.length === 0) {
      return null;
    }

    selectedGroup = groupList[Math.floor(getSecureRandomNumber() * groupList.length)];
    stored = {
      groupId: selectedGroup.id,
      assignedAt: new Date().toISOString(),
      method: "temporary_frontend_secure_random_if_available",
      finalServerSideBalancing: "TBC"
    };

    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("experimental.groupAssignment", stored);
    }

    return stored;
  }

  function buildScenarioOrder(scenarios) {
    return shuffle(Array.isArray(scenarios) ? scenarios : []);
  }

  function buildExcerptOrder(excerptIds) {
    return shuffle(Array.isArray(excerptIds) ? excerptIds : []);
  }

  function assignExcerptLabels(group) {
    var stored = window.StudyApp.storage && window.StudyApp.storage.getItem(excerptLabelMappingKey);
    var excerptIds = group && Array.isArray(group.excerptIds) ? group.excerptIds : [];
    var mapping;

    if (stored && stored.groupId === group.id && stored.labelsByExcerptId) {
      return stored;
    }

    mapping = {
      groupId: group.id,
      generatedAt: new Date().toISOString(),
      method: "stable_participant_facing_song_labels",
      labelsByExcerptId: {}
    };

    excerptIds.forEach(function (excerptId, index) {
      mapping.labelsByExcerptId[excerptId] = "Song " + String.fromCharCode(65 + index);
    });

    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem(excerptLabelMappingKey, mapping);
    }

    return mapping;
  }

  function mapNeutralMixLabels(mixes, labels) {
    var mixList = shuffle(Array.isArray(mixes) ? mixes : []);
    var labelList = Array.isArray(labels) ? labels : ["Version A", "Version B", "Version C", "Version D", "Version E", "Version F"];

    if (mixList.length !== labelList.length) {
      return [];
    }

    return labelList.map(function (label, index) {
      var mix = mixList[index];
      return {
        neutralLabel: label,
        actualMixId: mix ? mix.actualMixId : "TBC",
        stimulusId: mix ? mix.stimulusId : "TBC",
        realMixIdentity: mix ? mix.realMixIdentity : "TBC",
        originalMixName: mix ? mix.originalMixName : "TBC",
        audioPath: mix ? mix.audioPath : "TBC"
      };
    });
  }

  function buildTrialOrder(config, groupAssignment) {
    var stored = window.StudyApp.storage && window.StudyApp.storage.getItem("experimental.trialOrder");
    var group = config.groups.find(function (item) {
      return item.id === groupAssignment.groupId;
    });
    var submittedTrials = window.StudyApp.storage && window.StudyApp.storage.getItem("experimental.submittedTrials");
    var scenarioOrder;
    var trials = [];
    var storedCompatible;

    if (!group) {
      return null;
    }

    assignExcerptLabels(group);

    if (stored && Array.isArray(stored.trials)) {
      storedCompatible = isCompatibleTrialOrder(stored, config, group);
      if (storedCompatible) {
        return stored;
      }

      if (Array.isArray(submittedTrials) && submittedTrials.length > 0) {
        stored.developmentCompatibilityWarning = "This study session contains submitted trials from an earlier stimulus configuration. The current order has been preserved; start a fresh session before continuing with the revised audio materials.";
        return stored;
      }

      clearUnsubmittedExperimentalTrialState();
    }

    scenarioOrder = buildScenarioOrder(config.scenarios);
    scenarioOrder.forEach(function (scenario) {
      buildExcerptOrder(group.excerptIds).forEach(function (excerptId) {
        var excerpt = config.excerpts.find(function (item) {
          return item.id === excerptId;
        });

        trials.push({
          trialIndex: trials.length + 1,
          scenarioId: scenario.id,
          excerptId: excerptId,
          versionMappings: mapNeutralMixLabels(excerpt ? excerpt.mixes : [], config.versionLabels)
        });
      });
    });

    stored = {
      groupId: group.id,
      generatedAt: new Date().toISOString(),
      method: "temporary_frontend_secure_random_if_available",
      algorithm: trialOrderAlgorithm,
      stimulusConfigurationVersion: getStimulusConfigurationVersion(config),
      trials: trials
    };

    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("experimental.trialOrder", stored);
    }

    return stored;
  }

  function isCompatibleTrialOrder(stored, config, group) {
    if (!stored || stored.groupId !== group.id || stored.algorithm !== trialOrderAlgorithm) {
      return false;
    }

    if (stored.stimulusConfigurationVersion !== getStimulusConfigurationVersion(config)) {
      return false;
    }

    return isGroupedScenarioPairOrder(stored.trials, config.trialGeneration.trialsPerParticipant, group.excerptIds) && usesConfiguredMixes(stored.trials, config);
  }

  function getStimulusConfigurationVersion(config) {
    return config && config.stimulusConfigurationVersion ? config.stimulusConfigurationVersion : "unversioned";
  }

  function usesConfiguredMixes(trials, config) {
    var mixIdsByExcerpt = {};
    var audioPathsByExcerpt = {};
    var expectedVersionsPerTrial = config && config.trialGeneration ? config.trialGeneration.versionsPerTrial : 0;

    if (!Array.isArray(config.excerpts)) {
      return false;
    }

    config.excerpts.forEach(function (excerpt) {
      mixIdsByExcerpt[excerpt.id] = Array.isArray(excerpt.mixes) ? excerpt.mixes.map(function (mix) {
        return mix.actualMixId;
      }) : [];
      audioPathsByExcerpt[excerpt.id] = Array.isArray(excerpt.mixes) ? excerpt.mixes.map(function (mix) {
        return mix.audioPath;
      }) : [];
    });

    return trials.every(function (trial) {
      var expectedMixIds = mixIdsByExcerpt[trial.excerptId] || [];
      var expectedAudioPathList = audioPathsByExcerpt[trial.excerptId] || [];
      var expectedAudioPaths = {};
      var mappedMixIds = Array.isArray(trial.versionMappings) ? trial.versionMappings.map(function (mapping) {
        return mapping.actualMixId;
      }) : [];
      var mappedAudioPaths = Array.isArray(trial.versionMappings) ? trial.versionMappings.map(function (mapping) {
        return mapping.audioPath;
      }) : [];
      var mappedLabels = Array.isArray(trial.versionMappings) ? trial.versionMappings.map(function (mapping) {
        return mapping.neutralLabel;
      }) : [];

      (config.excerpts.find(function (excerpt) {
        return excerpt.id === trial.excerptId;
      }) || { mixes: [] }).mixes.forEach(function (mix) {
        expectedAudioPaths[mix.actualMixId] = mix.audioPath;
      });

      return expectedMixIds.length === expectedVersionsPerTrial &&
        expectedAudioPathList.length === expectedVersionsPerTrial &&
        mappedMixIds.length === expectedVersionsPerTrial &&
        uniqueCount(mappedMixIds) === expectedVersionsPerTrial &&
        uniqueCount(mappedAudioPaths) === expectedVersionsPerTrial &&
        uniqueCount(mappedLabels) === expectedVersionsPerTrial &&
        mappedMixIds.every(function (mixId) {
        var mapping = (trial.versionMappings || []).find(function (item) {
          return item.actualMixId === mixId;
        });
        return mappedMixIds.indexOf(mixId) !== -1 && mapping && mapping.audioPath === expectedAudioPaths[mixId];
      });
    });
  }

  function clearUnsubmittedExperimentalTrialState() {
    var namespace;

    if (!window.StudyApp.storage) {
      return;
    }

    [
      "experimental.trialOrder",
      "experimental.currentTrialIndex",
      "experimental.currentResponses",
      "experimental.completedTrialIndices"
    ].forEach(function (key) {
      window.StudyApp.storage.removeItem(key);
    });

    if (!window.StudyApp.storage.isAvailable || !window.StudyApp.storage.isAvailable() || !window.StudyApp.storage.getNamespace) {
      return;
    }

    namespace = window.StudyApp.storage.getNamespace();
    Object.keys(window.localStorage).forEach(function (key) {
      if (key.indexOf(namespace + "experimental.unsavedTrial.") === 0 ||
          key.indexOf(namespace + "experimental.firstPlay.") === 0 ||
          key.indexOf(namespace + "audio.played.experimental.") === 0 ||
          key.indexOf(namespace + "timing.trialStart.experimental_trial_") === 0 ||
          key.indexOf(namespace + "timing.trialSubmission.experimental_trial_") === 0) {
        window.localStorage.removeItem(key);
      }
    });
  }

  function isGroupedScenarioPairOrder(trials, expectedTrialCount, excerptIds) {
    var scenarioCounts = {};
    var index;
    var first;
    var second;

    if (!Array.isArray(trials) || trials.length !== expectedTrialCount || trials.length % 2 !== 0) {
      return false;
    }

    for (index = 0; index < trials.length; index += 2) {
      first = trials[index];
      second = trials[index + 1];

      if (!first || !second || first.scenarioId !== second.scenarioId) {
        return false;
      }

      if (excerptIds.indexOf(first.excerptId) === -1 || excerptIds.indexOf(second.excerptId) === -1 || first.excerptId === second.excerptId) {
        return false;
      }

      scenarioCounts[first.scenarioId] = (scenarioCounts[first.scenarioId] || 0) + 2;
    }

    return Object.keys(scenarioCounts).every(function (scenarioId) {
      return scenarioCounts[scenarioId] === 2;
    });
  }

  function uniqueCount(items) {
    var seen = {};
    return (Array.isArray(items) ? items : []).filter(function (item) {
      if (!item || seen[item]) {
        return false;
      }
      seen[item] = true;
      return true;
    }).length;
  }

  return {
    getSecureRandomNumber: getSecureRandomNumber,
    shuffle: shuffle,
    assignGroup: assignGroup,
    buildScenarioOrder: buildScenarioOrder,
    buildExcerptOrder: buildExcerptOrder,
    assignExcerptLabels: assignExcerptLabels,
    isGroupedScenarioPairOrder: isGroupedScenarioPairOrder,
    mapNeutralMixLabels: mapNeutralMixLabels,
    buildTrialOrder: buildTrialOrder
  };
}());
