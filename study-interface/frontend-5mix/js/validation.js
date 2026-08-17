"use strict";

/*
  Validation responsibility placeholders.
  Responsibilities:
  - Common required-field validation.
  - Whitespace-only comment detection.
  - PIS acknowledgement and consent validation.
  - Page-level validation hooks.
  - Trial validation for configured ratings and one required comparative comment.
*/

window.StudyApp = window.StudyApp || {};

window.StudyApp.validation = (function () {
  function isBlank(value) {
    return typeof value !== "string" || value.trim().length === 0;
  }

  function validateRequiredField(value) {
    return !isBlank(value);
  }

  function validateRequiredComment(value) {
    return !isBlank(value);
  }

  function formatVersionList(labels) {
    var safeLabels = (labels || []).filter(Boolean);

    if (safeLabels.length === 0) {
      return "the required versions";
    }
    if (safeLabels.length === 1) {
      return "Version " + safeLabels[0];
    }
    if (safeLabels.length === 2) {
      return "Versions " + safeLabels[0] + " and " + safeLabels[1];
    }
    return "Versions " + safeLabels.slice(0, -1).join(", ") + ", and " + safeLabels[safeLabels.length - 1];
  }

  function buildCompletionFeedback(requirements) {
    var missingPlaybackLabels = requirements && Array.isArray(requirements.missingPlaybackLabels) ? requirements.missingPlaybackLabels : [];
    var missingRatingLabels = requirements && Array.isArray(requirements.missingRatingLabels) ? requirements.missingRatingLabels : [];
    var commentValid = Boolean(requirements && requirements.commentValid);
    var commentTooLong = Boolean(requirements && requirements.commentTooLong);
    var maxCommentLength = requirements && requirements.maxCommentLength ? Number(requirements.maxCommentLength) : 1000;
    var parts = [];

    if (missingPlaybackLabels.length > 0) {
      parts.push("listen to " + formatVersionList(missingPlaybackLabels));
    }
    if (missingRatingLabels.length > 0) {
      parts.push("rate " + formatVersionList(missingRatingLabels));
    }
    if (!commentValid) {
      parts.push(commentTooLong ? "shorten the comment to " + maxCommentLength + " characters or fewer" : "enter a comment explaining your ratings");
    }

    if (parts.length === 0) {
      return "";
    }
    if (parts.length === 1) {
      return "Before continuing, please " + parts[0] + ".";
    }
    if (parts.length === 2) {
      return "Before continuing, please " + parts[0] + " and " + parts[1] + ".";
    }
    return "Before continuing, please " + parts.slice(0, -1).join(", ") + ", and " + parts[parts.length - 1] + ".";
  }

  function validateConsent() {
    var requiredItems = Array.prototype.slice.call(document.querySelectorAll("[data-consent-required]"));
    return requiredItems.every(function (item) {
      return item.checked;
    });
  }

  function validateDocumentOpened(key) {
    if (!window.StudyApp.storage) {
      return false;
    }

    return window.StudyApp.storage.getItem(key) === true;
  }

  function validateRequiredCheckboxes(selector) {
    var requiredItems = Array.prototype.slice.call(document.querySelectorAll(selector));
    return requiredItems.every(function (item) {
      return item.checked;
    });
  }

  function validateRequiredAudioPlayed(audioIds) {
    if (!window.StudyApp.audio || !Array.isArray(audioIds)) {
      return false;
    }

    return audioIds.every(function (audioId) {
      return window.StudyApp.audio.hasAudioBeenPlayed(audioId);
    });
  }

  function validatePage(pageId) {
    void pageId;
    return false;
  }

  return {
    isBlank: isBlank,
    validateRequiredField: validateRequiredField,
    validateRequiredComment: validateRequiredComment,
    formatVersionList: formatVersionList,
    buildCompletionFeedback: buildCompletionFeedback,
    validateDocumentOpened: validateDocumentOpened,
    validateRequiredCheckboxes: validateRequiredCheckboxes,
    validateRequiredAudioPlayed: validateRequiredAudioPlayed,
    validateConsent: validateConsent,
    validatePage: validatePage
  };
}());
