(function () {
  'use strict';

  var RecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition || null;
  var synth = window.speechSynthesis || null;
  var recognition = null;
  var listening = false;
  var recognitionSession = null;
  var FEMALE_HINTS = [
    'female',
    'elsa',
    'alice',
    'lucia',
    'sofia',
    'giulia',
    'bianca',
    'federica',
    'serena',
    'helena',
    'isabella',
    'microsoft elsa',
    'google italiano',
    'hortense',
    'aria',
    'emma',
    'sara',
  ];
  var MALE_HINTS = ['male', 'diego', 'luca', 'paolo', 'marco', 'microsoft cosimo'];
  var NATURAL_HINTS = ['natural', 'neural', 'premium', 'enhanced', 'online', 'desktop'];
  var DEFAULT_SILENCE_MS = 3000;
  var speechJobId = 0;

  function ttsRegistry() {
    return window.IusentraTtsEngineRegistry || null;
  }

  function legalNormalizer() {
    return window.IusentraLegalSpeechNormalizer || null;
  }

  function voiceProfiles() {
    return window.IusentraVoiceProfiles || null;
  }

  function resolveSpeechOptions(options) {
    var profiles = voiceProfiles();
    if (profiles && profiles.resolveSpeechOptions) {
      return profiles.resolveSpeechOptions(options || {});
    }
    return Object.assign({
      lang: 'it-IT',
      mode: 'summary',
      legalNormalization: true,
      preferFemale: true,
      maxAutoReadChars: 1800,
      maxChunkChars: 280,
    }, options || {});
  }

  function supportsRecognition() {
    return Boolean(RecognitionCtor);
  }

  function supportsSpeech() {
    var registry = ttsRegistry();
    if (registry && registry.getStatus) {
      var status = registry.getStatus() || {};
      if (status.supported || status.ready) {
        return true;
      }
    }
    return Boolean(synth);
  }

  function clearSilenceTimer() {
    if (recognitionSession && recognitionSession.silenceTimer) {
      window.clearTimeout(recognitionSession.silenceTimer);
      recognitionSession.silenceTimer = null;
    }
  }

  function scoreVoice(voice, preferFemale) {
    var haystack = (String(voice && voice.name || '') + ' ' + String(voice && voice.voiceURI || '')).toLowerCase();
    var score = 0;
    if (String(voice && voice.lang || '').toLowerCase().indexOf('it') === 0) {
      score += 60;
    }
    if (preferFemale) {
      FEMALE_HINTS.forEach(function (hint) {
        if (haystack.indexOf(hint) >= 0) {
          score += 22;
        }
      });
      MALE_HINTS.forEach(function (hint) {
        if (haystack.indexOf(hint) >= 0) {
          score -= 8;
        }
      });
    }
    NATURAL_HINTS.forEach(function (hint) {
      if (haystack.indexOf(hint) >= 0) {
        score += 8;
      }
    });
    return score;
  }

  function pickItalianVoice(options) {
    if (!synth || !supportsSpeech()) {
      return null;
    }
    var voices = synth.getVoices ? synth.getVoices() : [];
    if (!voices || !voices.length) {
      return null;
    }

    var preferFemale = !options || options.preferFemale !== false;
    return voices
      .slice()
      .sort(function (left, right) {
        return scoreVoice(right, preferFemale) - scoreVoice(left, preferFemale);
      })[0] || null;
  }

  function stopListening() {
    if (!recognitionSession) {
      return;
    }

    recognitionSession.manualStop = true;
    recognitionSession.stopRequested = true;
    clearSilenceTimer();

    if (recognition) {
      try {
        recognition.stop();
      } catch (error) {
        // no-op
      }
    }
  }

  function buildCombinedTranscript(session) {
    return ((session.finalText || '') + ' ' + (session.interimText || '')).trim();
  }

  function finishRecognition(session, resolve) {
    if (!session || session.completed) {
      return;
    }
    session.completed = true;
    listening = false;
    clearSilenceTimer();
    recognition = null;
    recognitionSession = null;
    resolve(buildCombinedTranscript(session));
  }

  function failRecognition(session, reject, error) {
    if (!session || session.completed) {
      return;
    }
    session.completed = true;
    listening = false;
    clearSilenceTimer();
    recognition = null;
    recognitionSession = null;
    reject(error);
  }

  function scheduleSilenceStop(session) {
    if (!session || session.completed) {
      return;
    }
    clearSilenceTimer();
    session.silenceTimer = window.setTimeout(function () {
      session.stopRequested = true;
      if (recognition) {
        try {
          recognition.stop();
        } catch (error) {
          // If the browser already stopped recognition, the onend handler will close the session.
        }
      }
    }, session.silenceMs);
  }

  function startListening(options) {
    if (!supportsRecognition()) {
      return Promise.reject(new Error('Dettatura vocale non supportata su questo browser.'));
    }
    if (listening) {
      stopListening();
    }

    listening = true;
    recognition = new RecognitionCtor();
    recognition.lang = (options && options.lang) || 'it-IT';
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    return new Promise(function (resolve, reject) {
      var session = {
        finalText: '',
        interimText: '',
        completed: false,
        manualStop: false,
        stopRequested: false,
        silenceTimer: null,
        silenceMs: Math.max(1500, Number(options && options.silenceMs || DEFAULT_SILENCE_MS)),
      };
      recognitionSession = session;

      recognition.onresult = function (event) {
        var interim = '';
        for (var i = event.resultIndex; i < event.results.length; i += 1) {
          var transcript = String(event.results[i][0].transcript || '').trim();
          if (!transcript) {
            continue;
          }
          if (event.results[i].isFinal) {
            session.finalText += (session.finalText ? ' ' : '') + transcript;
          } else {
            interim += (interim ? ' ' : '') + transcript;
          }
        }
        session.interimText = interim.trim();
        if (options && typeof options.onTranscript === 'function') {
          options.onTranscript(buildCombinedTranscript(session), Boolean(session.interimText));
        }
        if (buildCombinedTranscript(session)) {
          scheduleSilenceStop(session);
        }
      };

      recognition.onerror = function (event) {
        var code = String((event && event.error) || '').toLowerCase();
        if ((code === 'no-speech' || code === 'aborted') && buildCombinedTranscript(session)) {
          finishRecognition(session, resolve);
          return;
        }
        failRecognition(
          session,
          reject,
          new Error('Riconoscimento vocale non disponibile: ' + String((event && event.error) || 'errore sconosciuto'))
        );
      };

      recognition.onend = function () {
        if (session.completed) {
          return;
        }
        if (session.manualStop || session.stopRequested) {
          finishRecognition(session, resolve);
          return;
        }

        if (buildCombinedTranscript(session)) {
          try {
            recognition.start();
            scheduleSilenceStop(session);
            return;
          } catch (restartError) {
            finishRecognition(session, resolve);
            return;
          }
        }

        finishRecognition(session, resolve);
      };

      try {
        recognition.start();
        scheduleSilenceStop(session);
      } catch (startError) {
        failRecognition(session, reject, startError);
      }
    });
  }

  function cancelSpeech() {
    speechJobId += 1;
    var registry = ttsRegistry();
    if (registry && registry.cancel) {
      try {
        registry.cancel();
      } catch (error) {
        // no-op
      }
    }
    if (supportsSpeech()) {
      try {
        synth.cancel();
      } catch (error) {
        // no-op
      }
    }
  }

  function normalizeSpeechText(value, options) {
    var helper = legalNormalizer();
    if (helper && helper.normalizeLegalSpeechText && (!options || options.legalNormalization !== false)) {
      return helper.normalizeLegalSpeechText(value, options || {});
    }
    return String(value || '')
      .replace(/\s+/g, ' ')
      .replace(/\s+([,.;:!?])/g, '$1')
      .replace(/([,;:!?])([^\s])/g, '$1 $2')
      .trim();
  }

  function splitSpeechChunks(text, options) {
    var helper = legalNormalizer();
    if (helper && helper.splitLegalSpeechChunks) {
      return helper.splitLegalSpeechChunks(text, options || {});
    }
    var normalized = normalizeSpeechText(text, options);
    if (!normalized) {
      return [];
    }
    var sentences = normalized
      .split(/(?<=[.!?;:])\s+/)
      .map(function (item) { return item.trim(); })
      .filter(Boolean);

    if (!sentences.length) {
      return [normalized];
    }

    var chunks = [];
    var current = '';
    sentences.forEach(function (sentence) {
      if (!current) {
        current = sentence;
        return;
      }
      if ((current + ' ' + sentence).length <= 220) {
        current += ' ' + sentence;
        return;
      }
      chunks.push(current);
      current = sentence;
    });
    if (current) {
      chunks.push(current);
    }
    return chunks;
  }

  function speak(text, options) {
    if (!text) {
      return false;
    }
    cancelSpeech();
    var speechOptions = resolveSpeechOptions(options || {});
    var preparedText = normalizeSpeechText(String(text), speechOptions);
    if (!preparedText) {
      return false;
    }
    var registry = ttsRegistry();
    if (registry && registry.speak) {
      Promise.resolve(registry.speak(preparedText, Object.assign({}, speechOptions, { skipNormalization: true })))
        .catch(function () {
          // Il registro gestisce gia' il fallback browser; qui evitiamo errori non gestiti.
        });
      return true;
    }
    if (!supportsSpeech()) {
      return false;
    }
    var chunks = splitSpeechChunks(preparedText, speechOptions);
    if (!chunks.length) {
      return false;
    }
    var voice = pickItalianVoice(speechOptions || {});
    var jobId = speechJobId;
    var index = 0;

    function speakNext() {
      if (!supportsSpeech() || jobId !== speechJobId || index >= chunks.length) {
        return;
      }
      var item = chunks[index] || {};
      var utterance = new SpeechSynthesisUtterance(String(item.text || item || '').trim());
      utterance.lang = speechOptions.lang || 'it-IT';
      utterance.rate = Number(speechOptions.rate) || 0.93;
      utterance.pitch = Number(speechOptions.pitch) || 1.08;
      utterance.volume = Number(speechOptions.volume) || 0.98;
      if (voice) {
        utterance.voice = voice;
      }
      utterance.onend = function () {
        index += 1;
        if (index < chunks.length && jobId === speechJobId) {
          window.setTimeout(speakNext, Math.max(40, Number(item.pauseAfterMs) || 80));
        }
      };
      utterance.onerror = function () {
        index = chunks.length;
      };
      synth.speak(utterance);
    }

    speakNext();
    return true;
  }

  function supportsNeuralSpeech() {
    var registry = ttsRegistry();
    return Boolean(registry && registry.supportsNeuralSpeech && registry.supportsNeuralSpeech());
  }

  function preloadSpeechEngine(options) {
    var registry = ttsRegistry();
    if (!registry || !registry.preload) {
      return Promise.resolve(getSpeechEngineStatus());
    }
    return registry.preload(options || {});
  }

  function getSpeechEngineStatus(options) {
    var registry = ttsRegistry();
    var speechOptions = resolveSpeechOptions(options || {});
    var profileLabel = speechOptions.badgeLabel || speechOptions.profileLabel || '';
    if (registry && registry.getStatus) {
      var status = registry.getStatus();
      if (status && status.engine === 'browser' && status.ready && profileLabel) {
        status = Object.assign({}, status, { label: profileLabel, profileLabel: speechOptions.profileLabel });
      }
      return status;
    }
    return {
      engine: 'browser',
      label: supportsSpeech() ? (profileLabel || 'Voce browser') : 'Voce non supportata',
      supported: supportsSpeech(),
      ready: supportsSpeech(),
      backend: 'browser',
      profileLabel: speechOptions.profileLabel,
    };
  }

  if (synth && supportsSpeech() && synth.onvoiceschanged !== undefined) {
    synth.onvoiceschanged = function () {
      pickItalianVoice({ preferFemale: true });
    };
  }

  window.PctLexVoice = {
    cancelSpeech: cancelSpeech,
    speak: speak,
    startListening: startListening,
    stopListening: stopListening,
    supportsRecognition: supportsRecognition,
    supportsSpeech: supportsSpeech,
    supportsNeuralSpeech: supportsNeuralSpeech,
    preloadSpeechEngine: preloadSpeechEngine,
    getSpeechEngineStatus: getSpeechEngineStatus,
  };
})();
