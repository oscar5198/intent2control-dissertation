"use strict";

/*
  Audio responsibility placeholders.
  Responsibilities:
  - Prepare audio controls.
  - Track whether required audio has been played.
  - Support a one-active-audio-at-a-time policy later.
  - Keep detailed playback-event logging configurable/TBC.
*/

window.StudyApp = window.StudyApp || {};

window.StudyApp.audio = (function () {
  var playedAudioIds = {};

  function setupAudioControls(container) {
    var root = container || document;
    var audioElements = Array.prototype.slice.call(root.querySelectorAll("audio[data-audio-id]"));

    audioElements.forEach(function (audioElement) {
      applyControlledListeningAttributes(audioElement);
      audioElement.addEventListener("playing", function () {
        pauseOtherAudio(audioElement);
        markAudioPlayed(audioElement.getAttribute("data-audio-id"));
      });
    });

    return audioElements.length > 0;
  }

  function applyControlledListeningAttributes(audioElement) {
    if (!audioElement) {
      return false;
    }

    if ("controlsList" in audioElement && audioElement.controlsList && typeof audioElement.controlsList.add === "function") {
      addControlsListToken(audioElement, "nodownload");
      addControlsListToken(audioElement, "noplaybackrate");
      addControlsListToken(audioElement, "noremoteplayback");
    } else {
      audioElement.setAttribute("controlsList", "nodownload noplaybackrate noremoteplayback");
    }

    if ("disablePictureInPicture" in audioElement) {
      audioElement.disablePictureInPicture = true;
    }

    if ("disableRemotePlayback" in audioElement) {
      audioElement.disableRemotePlayback = true;
    }

    return true;
  }

  function addControlsListToken(audioElement, token) {
    try {
      audioElement.controlsList.add(token);
    } catch (error) {
      var existing = audioElement.getAttribute("controlsList") || "";
      var tokens = existing ? existing.split(/\s+/) : [];
      if (tokens.indexOf(token) === -1) {
        tokens.push(token);
      }
      audioElement.setAttribute("controlsList", tokens.join(" ").trim());
    }
  }

  function markAudioPlayed(audioId) {
    if (!audioId) {
      return false;
    }

    playedAudioIds[audioId] = true;
    if (window.StudyApp.storage) {
      window.StudyApp.storage.setItem("audio.played." + audioId, true);
    }
    return true;
  }

  function hasAudioBeenPlayed(audioId) {
    if (!audioId) {
      return false;
    }

    if (playedAudioIds[audioId]) {
      return true;
    }

    return Boolean(window.StudyApp.storage && window.StudyApp.storage.getItem("audio.played." + audioId) === true);
  }

  function pauseOtherAudio(activeAudioElement) {
    Array.prototype.slice.call(document.querySelectorAll("audio")).forEach(function (audioElement) {
      if (audioElement !== activeAudioElement && !audioElement.paused) {
        audioElement.pause();
      }
    });
    return true;
  }

  function shouldRecordPlaybackEvents(config) {
    void config;
    return null;
  }

  return {
    setupAudioControls: setupAudioControls,
    applyControlledListeningAttributes: applyControlledListeningAttributes,
    markAudioPlayed: markAudioPlayed,
    hasAudioBeenPlayed: hasAudioBeenPlayed,
    pauseOtherAudio: pauseOtherAudio,
    shouldRecordPlaybackEvents: shouldRecordPlaybackEvents
  };
}());
