"use strict";

window.StudyApp = window.StudyApp || {};

window.StudyApp.netlifySubmission = (function () {
  var STUDY_VERSION = "five_mix_frontend_v1_2026-08-06";
  var SCHEMA_VERSION = "five_mix_netlify_forms_v1";
  var FORM_NAME = "listening-study-5mix";
  var SOURCE_VERSION = "frontend-5mix-netlify-forms-2026-08-06";
  var SUBMISSION_TIMEOUT_MS = 15000;
  var JSON_FIELDS = [
    "consent_json",
    "listening_setup_json",
    "pre_study_json",
    "practice_json",
    "demographics_json",
    "post_task_json",
    "assigned_song_ids_json",
    "scenario_order_json",
    "episode_order_json",
    "song_order_json",
    "trial_order_json",
    "mix_mapping_json",
    "presentation_order_json",
    "trial_records_json",
    "responses_json",
    "derived_preferences_json",
    "timing_json",
    "device_browser_json",
    "final_payload_json",
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
      return Promise.resolve().then(function () {
        validatePayload(payload);
        return submitPayload(payload);
      }).then(function () {
        return payload;
      }).catch(function (error) {
        error.payload = payload;
        throw error;
      });
    });
  }

  function buildSubmissionPayload() {
    return Promise.all([
      fetchJson("../config/stimuli.json"),
      fetchJson("../config/study-config.json")
    ]).then(function (configs) {
      var config = configs[0];
      var studyConfig = configs[1];
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
      var responses = buildResponses(trialRows);
      var trialRecords = buildTrialRecords(trialRows);
      var comments = trialRecords.filter(function (trial) {
        return typeof trial.comparative_comment === "string" && trial.comparative_comment.trim().length > 0;
      });
      var payload = {
        study_id: storage.getOrCreateStudyId(),
        study_version: STUDY_VERSION,
        schema_version: SCHEMA_VERSION,
        stimulus_configuration_version: config.stimulusConfigurationVersion || "",
        source_version: SOURCE_VERSION,
        submission_status: "completed",
        study_group: groupAssignment.groupId || "",
        group_id: groupAssignment.groupId || "",
        started_at: startedAt || "",
        completed_at: completedAt,
        duration_seconds: deriveDurationSeconds(startedAt, completedAt),
        trial_count: trialRows.length,
        version_count: getExpectedMixesPerTrial(config),
        rating_count: responses.length,
        comment_count: comments.length,
        consent_confirmed: isConsentConfirmed(storage),
        consent_json: buildConsentData(storage),
        listening_setup_json: buildListeningSetupData(storage),
        pre_study_json: buildPreStudyData(storage),
        practice_json: buildPracticeData(storage),
        demographics_json: storage.getItem("demographics.responses") || {},
        post_task_json: storage.getItem("postTask.responses") || {},
        assigned_song_ids_json: assignedSongIds,
        scenario_order_json: buildEpisodeOrder(trialOrder),
        episode_order_json: buildEpisodeOrder(trialOrder),
        song_order_json: buildSongOrder(trialRows),
        trial_order_json: buildTrialOrderData(trialOrder),
        mix_mapping_json: buildMixMapping(trialRows),
        presentation_order_json: buildPresentationOrder(trialRows),
        trial_records_json: trialRecords,
        responses_json: responses,
        derived_preferences_json: buildDerivedPreferences(trialRows),
        timing_json: buildTimingData(storage),
        device_browser_json: buildDeviceBrowserData(),
        client_validation_json: clientValidation
      };

      payload.final_payload_json = buildFinalPayloadSnapshot(payload, studyConfig);
      return payload;
    });
  }

  function submitPayload(payload) {
    if (isLocalPreviewHost()) {
      var localSubmissionUrl = getSubmissionUrl();
      logSubmissionDiagnostic("Local preview cannot submit to Netlify Forms.", null, localSubmissionUrl);
      return Promise.reject(createLocalPreviewSubmissionError(payload));
    }

    var controller = window.AbortController ? new AbortController() : null;
    var timeoutId = null;
    var body = toUrlEncodedBody(payload);
    var submissionUrl = getSubmissionUrl();

    if (controller) {
      timeoutId = window.setTimeout(function () {
        controller.abort();
      }, SUBMISSION_TIMEOUT_MS);
    }

    logSubmissionDiagnostic("Submitting Netlify form.", null, submissionUrl);

    return fetch(submissionUrl, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body,
      signal: controller ? controller.signal : undefined
    }).then(function (response) {
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
      if (!response.ok) {
        logSubmissionDiagnostic("Netlify form submission failed.", response, submissionUrl);
        throw new Error("Submission request failed.");
      }
      logSubmissionDiagnostic("Netlify form submission succeeded.", response, submissionUrl);
      return response;
    }).catch(function (error) {
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
      logSubmissionDiagnostic("Netlify form submission error.", null, submissionUrl, error);
      throw error;
    });
  }

  function getSubmissionUrl() {
    var pathname = window.location && window.location.pathname ? window.location.pathname : "";
    if (!pathname || pathname === "/") {
      return "/index.html";
    }
    return pathname;
  }

  function logSubmissionDiagnostic(message, response, submissionUrl, error) {
    if (!isDevelopmentDiagnosticsEnabled() || !window.console || !window.console.info) {
      return;
    }
    window.console.info("[listening-study submission]", {
      message: message,
      requestUrl: submissionUrl,
      responseStatus: response ? response.status : null,
      responseStatusText: response ? response.statusText : null,
      errorName: error ? error.name : null
    });
  }

  function isDevelopmentDiagnosticsEnabled() {
    return isLocalPreviewHost();
  }

  function isLocalPreviewHost() {
    var hostname = window.location && window.location.hostname ? window.location.hostname : "";
    return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1" || hostname === "";
  }

  function createLocalPreviewSubmissionError(payload) {
    var error = new Error("Local preview cannot save to Netlify Forms.");
    error.code = "LOCAL_NETLIFY_FORMS_UNAVAILABLE";
    error.localPreviewSubmissionUnavailable = true;
    error.payload = payload;
    return error;
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
      if (window.console && window.console.error) {
        window.console.error("[listening-study-5mix submission] Validation failed.", {
          failedChecks: failed,
          validation: validation
        });
      }
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
          scenario_id: trial.scenarioId,
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
          rating_set: response ? typeof response.rating === "number" && Number.isFinite(response.rating) : false,
          audio_played: response ? response.audioPlayed === true : false,
          first_play_timestamp: response ? response.firstPlayTimestamp || "" : "",
          comparative_comment: responseRecord ? responseRecord.comparative_comment || responseRecord.comparativeComment || "" : "",
          response_time_ms: response ? response.derivedTrialDurationMs : null,
          audio_path: mapping.audioPath || (response && response.audioPath) || "",
          expected_stimulus_id: mix ? mix.stimulusId : ""
        };
      });

      return {
        episode_id: trial.scenarioId,
        scenario_id: trial.scenarioId,
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
          scenario_id: mapping.scenario_id,
          episode_position: mapping.episode_position,
          song_id: mapping.song_id,
          excerpt_id: mapping.excerpt_id,
          trial_index: mapping.trial_index,
          song_position: mapping.song_position,
          display_label: mapping.display_label,
          display_position: mapping.display_position,
          stimulus_id: mapping.stimulus_id,
          actual_mix_id: mapping.actual_mix_id,
          audio_path: mapping.audio_path,
          rating: mapping.rating,
          rating_set: mapping.rating_set,
          audio_played: mapping.audio_played,
          first_play_timestamp: mapping.first_play_timestamp,
          comparative_comment: mapping.comparative_comment,
          response_time_ms: mapping.response_time_ms
        });
      });
    });
    return responses;
  }

  function buildTrialRecords(trialRows) {
    return trialRows.map(function (trial) {
      return {
        episode_id: trial.episode_id,
        scenario_id: trial.scenario_id,
        episode_position: trial.episode_position,
        song_id: trial.song_id,
        excerpt_id: trial.excerpt_id,
        song_position: trial.song_position,
        trial_index: trial.trial_index,
        comparative_comment: trial.mappings.length > 0 ? trial.mappings[0].comparative_comment : "",
        version_records: trial.mappings.map(function (mapping) {
          return {
            display_label: mapping.display_label,
            display_position: mapping.display_position,
            actual_mix_id: mapping.actual_mix_id,
            stimulus_id: mapping.stimulus_id,
            audio_path: mapping.audio_path,
            rating: mapping.rating,
            rating_set: mapping.rating_set,
            audio_played: mapping.audio_played,
            first_play_timestamp: mapping.first_play_timestamp,
            response_time_ms: mapping.response_time_ms
          };
        })
      };
    });
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
    var expectedMixesPerTrial = getExpectedMixesPerTrial(config);
    var expectedResponseCount = expectedTrialCount * expectedMixesPerTrial;
    var responses = buildResponses(trialRows);
    var trialRecords = buildTrialRecords(trialRows);
    var episodeIds = unique(trialRows.map(function (trial) { return trial.episode_id; }));
    var expectedEpisodeIds = Array.isArray(config.scenarios) ? config.scenarios.map(function (scenario) { return scenario.id; }) : [];
    var songIds = unique(trialRows.map(function (trial) { return trial.song_id; }));
    var expectedVersionLabels = getExpectedVersionLabels(config);

    return {
      expected_response_count: expectedResponseCount,
      expected_trial_count: expectedTrialCount,
      actual_trial_count: trialRows.length,
      expected_comment_count: expectedTrialCount,
      actual_comment_count: trialRows.filter(function (trial) {
        var comment = trial.mappings.length > 0 ? trial.mappings[0].comparative_comment : "";
        return typeof comment === "string" && comment.trim().length > 0;
      }).length,
      actual_response_count: responses.length,
      study_id_present: Boolean(window.StudyApp.storage && window.StudyApp.storage.getOrCreateStudyId()),
      group_id_present: Boolean(trialOrder && trialOrder.groupId),
      schema_version_present: Boolean(SCHEMA_VERSION),
      stimulus_configuration_version_present: Boolean(config.stimulusConfigurationVersion),
      trial_count_matches_expected: trialRows.length === expectedTrialCount,
      version_count_matches_expected: responses.length === expectedResponseCount,
      comment_count_matches_expected: trialRecords.length === expectedTrialCount && trialRecords.every(function (trial) {
        return typeof trial.comparative_comment === "string" && trial.comparative_comment.trim().length > 0;
      }),
      all_stimulus_ids_present: responses.every(function (response) { return Boolean(response.stimulus_id); }),
      all_actual_mix_ids_present: responses.every(function (response) { return Boolean(response.actual_mix_id); }),
      all_ratings_numeric: responses.every(function (response) { return typeof response.rating === "number" && Number.isFinite(response.rating); }),
      all_ratings_integer_in_range: responses.every(function (response) { return Number.isInteger(response.rating) && response.rating >= 0 && response.rating <= 100; }),
      all_ratings_deliberately_set: responses.every(function (response) { return response.rating_set === true; }),
      all_required_audio_played: responses.every(function (response) { return response.audio_played === true; }),
      all_required_comparative_comments_present: responses.every(function (response) { return typeof response.comparative_comment === "string" && response.comparative_comment.trim().length > 0 && response.comparative_comment.length <= 1000; }),
      questionnaire_completion_present: Boolean(window.StudyApp.storage && window.StudyApp.storage.getItem("postTask.completed") === true && window.StudyApp.storage.getItem("demographics.completed") === true),
      all_expected_episodes_present: expectedEpisodeIds.length > 0 && episodeIds.length === expectedEpisodeIds.length && expectedEpisodeIds.every(function (episodeId) { return episodeIds.indexOf(episodeId) !== -1; }),
      two_songs_present: songIds.length === 2 && assignedSongIds.length === 2,
      expected_mixes_per_trial: trialRows.every(function (trial) { return trial.mappings.length === expectedMixesPerTrial; }),
      all_display_labels_present_once_per_trial: trialRows.every(function (trial) {
        var labels = trial.mappings.map(function (mapping) { return mapping.display_label; }).sort();
        return labels.join("|") === expectedVersionLabels.join("|");
      }),
      unique_physical_mixes_per_trial: trialRows.every(function (trial) {
        return unique(trial.mappings.map(function (mapping) { return mapping.actual_mix_id; })).length === expectedMixesPerTrial;
      }),
      display_labels_match_expected_stimuli: trialRows.every(function (trial) {
        return trial.mappings.every(function (mapping) {
          return mapping.stimulus_id && mapping.stimulus_id === mapping.expected_stimulus_id;
        });
      }),
      every_response_song_assigned: responses.every(function (response) { return assignedSongIds.indexOf(response.song_id) !== -1; }),
      every_response_episode_valid: responses.every(function (response) { return Boolean(findById(config.scenarios, response.episode_id)); }),
      each_trial_contains_expected_mixes: trialRows.every(function (trial) {
        var configured = getConfiguredStimulusIds(config, trial.excerpt_id);
        var actual = trial.mappings.map(function (mapping) { return mapping.stimulus_id; });
        return actual.length === expectedMixesPerTrial && unique(actual).length === expectedMixesPerTrial && actual.every(function (stimulusId) {
          return configured.indexOf(stimulusId) !== -1;
        });
      }),
      mapping_response_records_agree: trialRows.every(function (trial) {
        return trial.mappings.every(function (mapping) {
          return mapping.stimulus_id === mapping.expected_stimulus_id;
        });
      })
    };
  }

  function buildConsentData(storage) {
    return {
      pis_document_opened: storage.getItem("pis.documentOpened"),
      consent_document_opened: storage.getItem("consent.documentOpened"),
      pis_acknowledged: storage.getItem("pis.acknowledged"),
      consent_items: storage.getItem("consent.items"),
      consent_completion_timestamp: storage.getItem("timing.consentCompletion"),
      study_information_consent_completion_timestamp: storage.getItem("timing.studyInformationConsentCompletion")
    };
  }

  function buildListeningSetupData(storage) {
    return {
      test_audio_played: storage.getItem("listeningSetup.testAudioPlayed"),
      headphones: storage.getItem("listeningSetup.headphones"),
      quiet_environment: storage.getItem("listeningSetup.quietEnvironment"),
      comfortable_volume: storage.getItem("listeningSetup.comfortableVolume"),
      completed: storage.getItem("listeningSetup.completed"),
      completion_timestamp: storage.getItem("timing.listeningSetupCompletion")
    };
  }

  function buildPreStudyData(storage) {
    return {
      passed: storage.getItem("screening.passed"),
      failed: storage.getItem("screening.failed"),
      total_score: storage.getItem("screening.totalScore"),
      development_bypass_used: storage.getItem("screening.developmentBypassUsed"),
      attempt_records: storage.getItem("screening.attemptRecords") || []
    };
  }

  function buildPracticeData(storage) {
    return {
      completed: storage.getItem("practice.completed"),
      ratings: storage.getItem("practice.ratings") || {},
      rating_touched: storage.getItem("practice.ratingTouched") || {},
      comparative_comment: storage.getItem("practice.comparativeComment") || "",
      current_responses: storage.getItem("practice.currentResponses") || {},
      started_at: storage.getItem("timing.practiceStart"),
      submitted_at: storage.getItem("timing.practiceSubmission"),
      completed_at: storage.getItem("timing.practiceCompletion")
    };
  }

  function buildTimingData(storage) {
    var result = {};
    storage.getDocumentedDevelopmentKeys().forEach(function (key) {
      var value = storage.getItem(key);
      if (key.indexOf("timing.") === 0 && value !== null) {
        result[key] = value;
      }
    });
    return result;
  }

  function buildDeviceBrowserData() {
    var nav = window.navigator || {};
    var screenInfo = window.screen || {};
    return {
      user_agent: nav.userAgent || "",
      language: nav.language || "",
      languages: nav.languages || [],
      platform: nav.platform || "",
      vendor: nav.vendor || "",
      cookie_enabled: typeof nav.cookieEnabled === "boolean" ? nav.cookieEnabled : null,
      screen_width: screenInfo.width || null,
      screen_height: screenInfo.height || null,
      viewport_width: window.innerWidth || null,
      viewport_height: window.innerHeight || null,
      timezone: (window.Intl && Intl.DateTimeFormat) ? Intl.DateTimeFormat().resolvedOptions().timeZone || "" : ""
    };
  }

  function buildTrialOrderData(trialOrder) {
    if (!trialOrder || !Array.isArray(trialOrder.trials)) {
      return {};
    }
    return {
      group_id: trialOrder.groupId || "",
      generated_at: trialOrder.generatedAt || "",
      method: trialOrder.method || "",
      algorithm: trialOrder.algorithm || "",
      stimulus_configuration_version: trialOrder.stimulusConfigurationVersion || "",
      trials: trialOrder.trials.map(function (trial) {
        return {
          trial_index: trial.trialIndex,
          scenario_id: trial.scenarioId,
          excerpt_id: trial.excerptId,
          version_mappings: (trial.versionMappings || []).map(function (mapping) {
            return {
              display_label: normaliseDisplayLabel(mapping.neutralLabel),
              actual_mix_id: mapping.actualMixId || "",
              stimulus_id: mapping.stimulusId || "",
              audio_path: mapping.audioPath || ""
            };
          })
        };
      })
    };
  }

  function buildFinalPayloadSnapshot(payload, studyConfig) {
    var snapshot = {};
    Object.keys(payload).forEach(function (key) {
      if (key !== "final_payload_json") {
        snapshot[key] = payload[key];
      }
    });
    snapshot.study_config_summary = {
      trials_per_participant: studyConfig.trialsPerParticipant,
      mixes_per_trial: studyConfig.mixesPerTrial,
      ratings_per_participant: studyConfig.ratingsPerParticipant,
      required_comments_per_participant: studyConfig.requiredCommentsPerParticipant
    };
    return snapshot;
  }

  function getExpectedMixesPerTrial(config) {
    return config.trialGeneration ? config.trialGeneration.versionsPerTrial : 5;
  }

  function getExpectedVersionLabels(config) {
    if (Array.isArray(config.versionLabels) && config.versionLabels.length > 0) {
      return config.versionLabels.map(normaliseDisplayLabel).sort();
    }
    return ["A", "B", "C", "D", "E"];
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
    getSubmissionUrl: getSubmissionUrl,
    isLocalPreviewHost: isLocalPreviewHost,
    submitPayload: submitPayload,
    toUrlEncodedBody: toUrlEncodedBody,
    validatePayload: validatePayload
  };
}());
