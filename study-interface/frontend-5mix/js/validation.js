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
    validateDocumentOpened: validateDocumentOpened,
    validateRequiredCheckboxes: validateRequiredCheckboxes,
    validateRequiredAudioPlayed: validateRequiredAudioPlayed,
    validateConsent: validateConsent,
    validatePage: validatePage
  };
}());
