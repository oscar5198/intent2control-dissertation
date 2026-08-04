"use strict";

window.StudyApp = window.StudyApp || {};

window.StudyApp.netlifySubmission = (function () {
  var STUDY_VERSION = "2026-08-04-v1";
  var FORM_NAME = "listening-study";
  var SUBMISSION_TIMEOUT_MS = 15000;
  var JSON_FIELDS = [
    "demographics_json",
    "assigned_song_ids_json",
    "episode_order_json",
    "song_order_json",
    "mix_mapping_json",
    "presentation_order_json",
    "responses_json",
    "derived_preferences_json",
    "client_validation_json"
  ];

  function getStudyVersion() {
    return STUDY_VERSION;
  }

  function getFormName() {
    return FORM_NAME;
  }

  function buildAndSubmit() {
    return buildSubmissionPayload().then(function (payload) {
      validatePayload(payload);
      return submitPayload(payload).then(function () {
        return payload;
      });
    });
  }

  function buildSubmissionPayload() {
    return fetchJson("../config/stimuli.json").then(function (config) {
      var storage = window.StudyApp.storage;
      var trialOrder = storage.getItem("experimental.trialOrder");
      var submittedTrials = storage.getItem("experimental.submittedTrials");
      var completedAt = getNowIso();
      var startedAt = storage.getItem("timing.studyStart");
      var groupAssignment = storage.getItem("experimental.groupAssignment") || {};
      var group = findById(config.groups, groupAssignment.groupId);
      var assignedExcerptIds = group && Array.isArray(group.excerptIds) ? group.excerptIds.slice() : [];
      var assignedSongIds = assignedExcerptIds.map(function (excerptId) {
        return getSongIdForExcerpt(config, excerptId);
      });
      var trialRows = normaliseTrials(config, trialOrder, submittedTrials);
      var clientValidation = buildClientValidation(config, trialOrder, trialRows, assignedSongIds);

      return {
        study_id: storage.getOrCreateStudyId(),
        study_version: STUDY_VERSION,
        submission_status: "completed",
        study_group: groupAssignment.groupId || "",
        started_at: startedAt || "",
        completed_at: completedAt,
        duration_seconds: deriveDurationSeconds(startedAt, completedAt),
        consent_confirmed: isConsentConfirmed(storage),
        demographics_json: storage.getItem("demographics.responses") || {},
        assigned_song_ids_json: assignedSongIds,
        episode_order_json: buildEpisodeOrder(trialOrder),
        song_order_json: buildSongOrder(trialRows),
        mix_mapping_json: buildMixMapping(trialRows),
        presentation_order_json: buildPresentationOrder(trialRows),
        responses_json: buildResponses(trialRows),
        derived_preferences_json: buildDerivedPreferences(trialRows),
        client_validation_json: clientValidation
      };
    });
  }

  function submitPayload(payload) {
    var controller = window.AbortController ? new AbortController() : null;
    var timeoutId = null;
    var body = toUrlEncodedBody(payload);

    if (controller) {
      timeoutId = window.setTimeout(function () {
        controller.abort();
      }, SUBMISSION_TIMEOUT_MS);
    }

    return fetch("/", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body,
      signal: controller ? controller.signal : undefined
    }).then(function (response) {
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
      if (!response.ok) {
        throw new Error("Submission request failed.");
      }
      return response;
    }).catch(function (error) {
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
      throw error;
    });
  }

  function toUrlEncodedBody(payload) {
    var params = new URLSearchParams();
    params.append("form-name", FORM_NAME);
    Object.keys(payload).forEach(function (key) {
      params.append(key, JSON_FIELDS.indexOf(key) !== -1 ? JSON.stringify(payload[key]) : String(payload[key]));
    });
    return params.toString();
  }

  function validatePayload(payload) {
    var validation = payload.client_validation_json || {};
    var failed = Object.keys(validation).filter(function (key) {
      return validation[key] === false;
    });
    if (failed.length > 0 || validation.actual_response_count !== validation.expected_response_count) {
      throw new Error("Submission validation failed: " + failed.join(", "));
    }
    return true;
  }

  function normaliseTrials(config, trialOrder, submittedTrials) {
    var orderTrials = trialOrder && Array.isArray(trialOrder.trials) ? trialOrder.trials : [];
    var responseTrials = Array.isArray(submittedTrials) ? submittedTrials : [];
    return orderTrials.map(function (trial, trialIndex) {
      var responseRecord = responseTrials.find(function (record) {
        return record.trialIndex === trial.trialIndex;
      });
      var episodePosition = getEpisodePosition(orderTrials, trial.scenarioId);
      var songPosition = getSongPositionWithinEpisode(orderTrials, trial);
      var mappings = (trial.versionMappings || []).map(function (mapping, mappingIndex) {
        var mix = findConfiguredMix(config, trial.excerptId, mapping);
        var label = normaliseDisplayLabel(mapping.neutralLabel);
        var response = responseRecord && Array.isArray(responseRecord.versionResponses) ? responseRecord.versionResponses.find(function (item) {
          return normaliseDisplayLabel(item.neutralDisplayLabel) === label;
        }) : null;

        return {
          episode_id: trial.scenarioId,
          episode_position: episodePosition,
          song_id: getSongIdForExcerpt(config, trial.excerptId),
          excerpt_id: trial.excerptId,
          song_position: songPosition,
          trial_index: trial.trialIndex || trialIndex + 1,
          display_label: label,
          display_position: mappingIndex + 1,
          stimulus_id: mapping.stimulusId || (response && response.stimulusId) || (mix && mix.stimulusId) || "",
          actual_mix_id: mapping.actualMixId || (response && response.actualMixId) || (mix && mix.actualMixId) || "",
          rating: response ? response.rating : null,
          comment: response ? response.comment : "",
          response_time_ms: response ? response.derivedTrialDurationMs : null,
          audio_path: mapping.audioPath || (response && response.audioPath) || "",
          expected_stimulus_id: mix ? mix.stimulusId : ""
        };
      });

      return {
        episode_id: trial.scenarioId,
        episode_position: episodePosition,
        song_id: getSongIdForExcerpt(config, trial.excerptId),
        excerpt_id: trial.excerptId,
        song_position: songPosition,
        trial_index: trial.trialIndex || trialIndex + 1,
        mappings: mappings
      };
    });
  }

  function buildResponses(trialRows) {
    var responses = [];
    trialRows.forEach(function (trial) {
      trial.mappings.forEach(function (mapping) {
        responses.push({
          episode_id: mapping.episode_id,
          episode_position: mapping.episode_position,
          song_id: mapping.song_id,
          song_position: mapping.song_position,
          display_label: mapping.display_label,
          display_position: mapping.display_position,
          stimulus_id: mapping.stimulus_id,
          rating: mapping.rating,
          comment: mapping.comment,
          response_time_ms: mapping.response_time_ms
        });
      });
    });
    return responses;
  }

  function buildEpisodeOrder(trialOrder) {
    var seen = {};
    var order = [];
    ((trialOrder && trialOrder.trials) || []).forEach(function (trial) {
      if (!seen[trial.scenarioId]) {
        seen[trial.scenarioId] = true;
        order.push(trial.scenarioId);
      }
    });
    return order;
  }

  function buildSongOrder(trialRows) {
    var result = {};
    trialRows.forEach(function (trial) {
      if (!result[trial.episode_id]) {
        result[trial.episode_id] = [];
      }
      result[trial.episode_id].push(trial.song_id);
    });
    return result;
  }

  function buildMixMapping(trialRows) {
    var result = {};
    trialRows.forEach(function (trial) {
      if (!result[trial.episode_id]) {
        result[trial.episode_id] = {};
      }
      result[trial.episode_id][trial.song_id] = {};
      trial.mappings.forEach(function (mapping) {
        result[trial.episode_id][trial.song_id][mapping.display_label] = mapping.stimulus_id;
      });
    });
    return result;
  }

  function buildPresentationOrder(trialRows) {
    var result = {};
    trialRows.forEach(function (trial) {
      if (!result[trial.episode_id]) {
        result[trial.episode_id] = {};
      }
      result[trial.episode_id][trial.song_id] = trial.mappings.map(function (mapping) {
        return mapping.display_label;
      });
    });
    return result;
  }

  function buildDerivedPreferences(trialRows) {
    return trialRows.map(function (trial) {
      var ratings = trial.mappings.map(function (mapping) {
        return {
          display_label: mapping.display_label,
          stimulus_id: mapping.stimulus_id,
          rating: Number(mapping.rating)
        };
      });
      var maxRating = Math.max.apply(null, ratings.map(function (item) { return item.rating; }));
      var winners = ratings.filter(function (item) {
        return item.rating === maxRating;
      });
      return {
        episode_id: trial.episode_id,
        song_id: trial.song_id,
        winning_display_label: winners.length === 1 ? winners[0].display_label : null,
        winning_stimulus_id: winners.length === 1 ? winners[0].stimulus_id : null,
        winning_rating: Number.isFinite(maxRating) ? maxRating : null,
        tie: winners.length > 1,
        tied_stimulus_ids: winners.length > 1 ? winners.map(function (item) { return item.stimulus_id; }) : []
      };
    });
  }

  function buildClientValidation(config, trialOrder, trialRows, assignedSongIds) {
    var expectedTrialCount = config.trialGeneration ? config.trialGeneration.trialsPerParticipant : trialRows.length;
    var expectedMixesPerTrial = config.trialGeneration ? config.trialGeneration.versionsPerTrial : 3;
    var expectedResponseCount = expectedTrialCount * expectedMixesPerTrial;
    var responses = buildResponses(trialRows);
    var episodeIds = unique(trialRows.map(function (trial) { return trial.episode_id; }));
    var songIds = unique(trialRows.map(function (trial) { return trial.song_id; }));

    return {
      expected_response_count: expectedResponseCount,
      actual_response_count: responses.length,
      all_stimulus_ids_present: responses.every(function (response) { return Boolean(response.stimulus_id); }),
      all_ratings_numeric: responses.every(function (response) { return typeof response.rating === "number" && Number.isFinite(response.rating); }),
      all_required_comments_present: responses.every(function (response) { return typeof response.comment === "string" && response.comment.trim().length > 0 && response.comment.length <= 1000; }),
      all_five_episodes_present: episodeIds.length === 5,
      two_songs_present: songIds.length === 2 && assignedSongIds.length === 2,
      three_mixes_per_trial: trialRows.every(function (trial) { return trial.mappings.length === expectedMixesPerTrial; }),
      display_labels_match_expected_stimuli: trialRows.every(function (trial) {
        return trial.mappings.every(function (mapping) {
          return mapping.stimulus_id && mapping.stimulus_id === mapping.expected_stimulus_id;
        });
      }),
      every_response_song_assigned: responses.every(function (response) { return assignedSongIds.indexOf(response.song_id) !== -1; }),
      every_response_episode_valid: responses.every(function (response) { return Boolean(findById(config.scenarios, response.episode_id)); }),
      each_trial_contains_expected_mixes: trialRows.every(function (trial) {
        var expected = getConfiguredStimulusIds(config, trial.excerpt_id).sort().join("|");
        var actual = trial.mappings.map(function (mapping) { return mapping.stimulus_id; }).sort().join("|");
        return expected === actual;
      }),
      mapping_response_records_agree: trialRows.every(function (trial) {
        return trial.mappings.every(function (mapping) {
          return mapping.stimulus_id === mapping.expected_stimulus_id;
        });
      })
    };
  }

  function findConfiguredMix(config, excerptId, mapping) {
    var excerpt = findById(config.excerpts, excerptId);
    if (!excerpt || !Array.isArray(excerpt.mixes)) {
      return null;
    }
    return excerpt.mixes.find(function (mix) {
      return (mapping.stimulusId && mix.stimulusId === mapping.stimulusId) ||
        (mapping.actualMixId && mix.actualMixId === mapping.actualMixId) ||
        (mapping.audioPath && mix.audioPath === mapping.audioPath);
    }) || null;
  }

  function getConfiguredStimulusIds(config, excerptId) {
    var excerpt = findById(config.excerpts, excerptId);
    return excerpt && Array.isArray(excerpt.mixes) ? excerpt.mixes.map(function (mix) {
      return mix.stimulusId;
    }) : [];
  }

  function getSongIdForExcerpt(config, excerptId) {
    var excerpt = findById(config.excerpts, excerptId);
    return excerpt ? excerpt.sourceSongId || excerpt.id : excerptId;
  }

  function getEpisodePosition(orderTrials, scenarioId) {
    return buildEpisodeOrder({ trials: orderTrials }).indexOf(scenarioId) + 1;
  }

  function getSongPositionWithinEpisode(orderTrials, trial) {
    return orderTrials.filter(function (item) {
      return item.scenarioId === trial.scenarioId;
    }).findIndex(function (item) {
      return item.trialIndex === trial.trialIndex;
    }) + 1;
  }

  function normaliseDisplayLabel(label) {
    var value = String(label || "").trim();
    return value.replace(/^Version\s+/i, "");
  }

  function isConsentConfirmed(storage) {
    var consentItems = storage.getItem("consent.items");
    return Boolean(consentItems && Object.keys(consentItems).length > 0 && Object.keys(consentItems).every(function (key) {
      return consentItems[key] === true;
    }));
  }

  function deriveDurationSeconds(startedAt, completedAt) {
    var ms = window.StudyApp.timing ? window.StudyApp.timing.deriveDuration(startedAt, completedAt) : null;
    return ms === null ? "" : Math.round(ms / 1000);
  }

  function getNowIso() {
    return window.StudyApp.timing ? window.StudyApp.timing.nowIsoString() : new Date().toISOString();
  }

  function unique(items) {
    var seen = {};
    return items.filter(function (item) {
      if (!item || seen[item]) {
        return false;
      }
      seen[item] = true;
      return true;
    });
  }

  function findById(items, id) {
    return Array.isArray(items) ? items.find(function (item) { return item.id === id; }) : null;
  }

  function fetchJson(path) {
    return fetch(path, { cache: "no-store" }).then(function (response) {
      if (!response.ok) {
        throw new Error("Could not load " + path);
      }
      return response.json();
    });
  }

  return {
    getStudyVersion: getStudyVersion,
    getFormName: getFormName,
    buildSubmissionPayload: buildSubmissionPayload,
    buildAndSubmit: buildAndSubmit,
    submitPayload: submitPayload,
    toUrlEncodedBody: toUrlEncodedBody,
    validatePayload: validatePayload
  };
}());
