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
  var activeAudioElement = null;
  var lastSelectedAudioElement = null;

  function setupAudioControls(container) {
    var root = container || document;
    var audioElements = Array.prototype.slice.call(root.querySelectorAll("audio[data-audio-id]"));

    audioElements.forEach(function (audioElement) {
      applyControlledListeningAttributes(audioElement);
      enforceFixedVolume(audioElement);
      enforceSeekPrevention(audioElement);
      if (audioElement.getAttribute("data-marker-controlled-audio") === "true") {
        audioElement.controls = false;
        audioElement.classList.add("audio-control--hidden-native");
      } else {
        createCustomAudioControls(audioElement);
      }
      audioElement.addEventListener("play", function () {
        handleAudioPlay(audioElement);
      });
      audioElement.addEventListener("playing", function () {
        markAudioPlayed(audioElement.getAttribute("data-audio-id"));
      });
      audioElement.addEventListener("ended", function () {
        resetAudioElement(audioElement);
        if (activeAudioElement === audioElement) {
          activeAudioElement = null;
        }
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

  function createCustomAudioControls(audioElement) {
    var audioLabel;
    var isSetupControl;
    var controls;
    var playButton;
    var restartButton;
    var progress;
    var timeDisplay;

    if (!audioElement || audioElement.getAttribute("data-custom-audio-attached") === "true") {
      return false;
    }

    audioElement.controls = false;
    audioLabel = audioElement.getAttribute("aria-label") || "Audio";
    isSetupControl = audioElement.getAttribute("data-audio-id") === "setup-test-audio";

    controls = document.createElement("div");
    controls.className = "custom-audio-control " + (isSetupControl ? "custom-audio-control--setup" : "custom-audio-control--compact");
    controls.setAttribute("data-custom-audio-control", audioElement.getAttribute("data-audio-id") || "");

    playButton = document.createElement("button");
    playButton.type = "button";
    playButton.className = "custom-audio-control__button" + (isSetupControl ? "" : " custom-audio-control__button--icon");
    playButton.setAttribute("aria-label", "Play " + audioLabel);

    progress = document.createElement("progress");
    progress.className = "custom-audio-control__progress";
    progress.max = 1000;
    progress.value = 0;
    progress.tabIndex = -1;
    progress.setAttribute("aria-label", audioLabel + " playback progress");

    timeDisplay = document.createElement("span");
    timeDisplay.className = "custom-audio-control__time";
    timeDisplay.textContent = "0:00 / 0:00";
    timeDisplay.setAttribute("aria-live", "off");

    playButton.addEventListener("click", function () {
      var playAttempt;
      if (audioElement.paused) {
        if (!isSetupControl || audioElement.ended || (Number.isFinite(audioElement.duration) && audioElement.currentTime >= audioElement.duration)) {
          setAudioCurrentTime(audioElement, 0);
        }
        playAttempt = audioElement.play();
        handlePlayAttempt(playAttempt, audioElement, playButton, progress, timeDisplay);
      } else {
        audioElement.pause();
      }
    });

    if (isSetupControl) {
      restartButton = document.createElement("button");
      restartButton.type = "button";
      restartButton.className = "custom-audio-control__button custom-audio-control__button--secondary";
      restartButton.textContent = "Restart";
      restartButton.setAttribute("aria-label", audioLabel + ": restart from the beginning");
      restartButton.addEventListener("click", function () {
        var playAttempt;
        setAudioCurrentTime(audioElement, 0);
        playAttempt = audioElement.play();
        handlePlayAttempt(playAttempt, audioElement, playButton, progress, timeDisplay);
      });
    }

    audioElement.addEventListener("loadedmetadata", function () {
      updateCustomAudioControl(audioElement, playButton, progress, timeDisplay);
    });
    audioElement.addEventListener("timeupdate", function () {
      updateCustomAudioControl(audioElement, playButton, progress, timeDisplay);
    });
    audioElement.addEventListener("play", function () {
      updateCustomAudioControl(audioElement, playButton, progress, timeDisplay);
    });
    audioElement.addEventListener("pause", function () {
      updateCustomAudioControl(audioElement, playButton, progress, timeDisplay);
    });
    audioElement.addEventListener("ended", function () {
      updateCustomAudioControl(audioElement, playButton, progress, timeDisplay);
    });
    audioElement.addEventListener("error", function () {
      resetCustomAudioControlAfterLoadFailure(audioElement, playButton, progress, timeDisplay);
    });
    audioElement.addEventListener("emptied", function () {
      resetCustomAudioControlAfterLoadFailure(audioElement, playButton, progress, timeDisplay);
    });
    audioElement.addEventListener("abort", function () {
      resetCustomAudioControlAfterLoadFailure(audioElement, playButton, progress, timeDisplay);
    });

    controls.appendChild(playButton);
    if (restartButton) {
      controls.appendChild(restartButton);
    }
    controls.appendChild(timeDisplay);
    controls.appendChild(progress);
    audioElement.insertAdjacentElement("afterend", controls);
    audioElement.classList.add("audio-control--hidden-native");
    audioElement.setAttribute("data-custom-audio-attached", "true");
    updateCustomAudioControl(audioElement, playButton, progress, timeDisplay);
    return true;
  }

  function handlePlayAttempt(playAttempt, audioElement, playButton, progress, timeDisplay) {
    if (playAttempt && typeof playAttempt.catch === "function") {
      playAttempt.catch(function (error) {
        console.error("Audio playback could not start.", error);
        resetCustomAudioControlAfterLoadFailure(audioElement, playButton, progress, timeDisplay);
      });
    }
  }

  function resetCustomAudioControlAfterLoadFailure(audioElement, playButton, progress, timeDisplay) {
    if (!audioElement) {
      return false;
    }

    if (!audioElement.paused) {
      audioElement.pause();
    }
    setAudioCurrentTime(audioElement, 0);
    if (activeAudioElement === audioElement) {
      activeAudioElement = null;
    }
    updateCustomAudioControl(audioElement, playButton, progress, timeDisplay);
    return true;
  }

  function updateCustomAudioControl(audioElement, playButton, progress, timeDisplay) {
    var duration = Number.isFinite(audioElement.duration) ? audioElement.duration : 0;
    var currentTime = Number.isFinite(audioElement.currentTime) ? audioElement.currentTime : 0;
    var audioLabel = audioElement.getAttribute("aria-label") || "Audio";
    var isIconButton = playButton.classList.contains("custom-audio-control__button--icon");
    var isPaused = audioElement.paused;

    playButton.textContent = isIconButton ? (isPaused ? "▶" : "❚❚") : (isPaused ? "Play" : "Pause");
    playButton.setAttribute("aria-label", (isPaused ? "Play " : "Pause ") + audioLabel);
    progress.value = duration > 0 ? Math.round((currentTime / duration) * progress.max) : 0;
    progress.setAttribute("value", String(progress.value));
    progress.setAttribute("aria-valuetext", formatTime(currentTime) + " of " + formatTime(duration));
    timeDisplay.textContent = formatTime(currentTime) + " / " + formatTime(duration);
  }

  function formatTime(seconds) {
    var safeSeconds = Number.isFinite(seconds) ? Math.max(0, seconds) : 0;
    var minutes = Math.floor(safeSeconds / 60);
    var remainingSeconds = Math.floor(safeSeconds % 60);
    return minutes + ":" + String(remainingSeconds).padStart(2, "0");
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

  function handleAudioPlay(audioElement) {
    if (!audioElement) {
      return false;
    }

    if (activeAudioElement && activeAudioElement !== audioElement) {
      resetAudioElement(activeAudioElement);
    }

    if (lastSelectedAudioElement !== audioElement) {
      setAudioCurrentTime(audioElement, 0);
    }

    activeAudioElement = audioElement;
    lastSelectedAudioElement = audioElement;
    enforceFixedVolume(audioElement);
    return true;
  }

  function pauseOtherAudio(activeElement) {
    Array.prototype.slice.call(document.querySelectorAll("audio")).forEach(function (audioElement) {
      if (audioElement !== activeElement && !audioElement.paused) {
        resetAudioElement(audioElement);
      }
    });
    return true;
  }

  function playAudioFromBeginning(audioId) {
    var audioElement = audioId ? document.querySelector("audio[data-audio-id='" + audioId + "']") : null;
    if (!audioElement) {
      return false;
    }

    if (activeAudioElement && activeAudioElement !== audioElement) {
      resetAudioElement(activeAudioElement);
    }
    pauseOtherAudio(audioElement);
    setAudioCurrentTime(audioElement, 0);
    var playAttempt = audioElement.play();
    if (playAttempt && typeof playAttempt.catch === "function") {
      playAttempt.catch(function (error) {
        console.error("Audio playback could not start.", error);
      });
    }
    return true;
  }

  function stopActiveAudio() {
    if (activeAudioElement) {
      resetAudioElement(activeAudioElement);
      activeAudioElement = null;
      return true;
    }

    pauseOtherAudio(null);
    return false;
  }

  function resetAudioElement(audioElement) {
    if (!audioElement) {
      return false;
    }

    audioElement.pause();
    setAudioCurrentTime(audioElement, 0);
    return true;
  }

  function setAudioCurrentTime(audioElement, value) {
    try {
      audioElement.setAttribute("data-allow-programmatic-seek", "true");
      audioElement.currentTime = value;
      audioElement.setAttribute("data-last-allowed-time", String(value));
    } catch (error) {
      return false;
    } finally {
      window.setTimeout(function () {
        audioElement.removeAttribute("data-allow-programmatic-seek");
      }, 0);
    }
    return true;
  }

  function enforceSeekPrevention(audioElement) {
    if (!audioElement || audioElement.getAttribute("data-seek-prevention-attached") === "true") {
      return false;
    }

    audioElement.setAttribute("data-seek-prevention-attached", "true");
    audioElement.setAttribute("data-last-allowed-time", "0");

    audioElement.addEventListener("timeupdate", function () {
      if (audioElement.getAttribute("data-allow-programmatic-seek") === "true") {
        return;
      }
      audioElement.setAttribute("data-last-allowed-time", String(audioElement.currentTime || 0));
    });

    audioElement.addEventListener("seeking", function () {
      var lastAllowedTime = parseFloat(audioElement.getAttribute("data-last-allowed-time") || "0");
      if (audioElement.getAttribute("data-allow-programmatic-seek") === "true") {
        return;
      }
      if (Math.abs((audioElement.currentTime || 0) - lastAllowedTime) > 0.35) {
        setAudioCurrentTime(audioElement, lastAllowedTime);
      }
    });

    audioElement.addEventListener("ratechange", function () {
      if (audioElement.playbackRate !== 1) {
        audioElement.playbackRate = 1;
      }
    });

    return true;
  }

  function enforceFixedVolume(audioElement) {
    if (!audioElement) {
      return false;
    }

    if (audioElement.volume !== 1) {
      audioElement.volume = 1;
    }
    if (audioElement.muted) {
      audioElement.muted = false;
    }

    if (audioElement.getAttribute("data-fixed-volume-attached") !== "true") {
      audioElement.setAttribute("data-fixed-volume-attached", "true");
      audioElement.addEventListener("volumechange", function () {
        if (audioElement.volume !== 1 || audioElement.muted) {
          enforceFixedVolume(audioElement);
        }
      });
    }

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
    playAudioFromBeginning: playAudioFromBeginning,
    stopActiveAudio: stopActiveAudio,
    pauseOtherAudio: pauseOtherAudio,
    resetAudioElement: resetAudioElement,
    createCustomAudioControls: createCustomAudioControls,
    shouldRecordPlaybackEvents: shouldRecordPlaybackEvents
  };
}());
