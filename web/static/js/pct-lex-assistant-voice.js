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
  ];
  var MALE_HINTS = ['male', 'diego', 'luca', 'paolo', 'marco', 'microsoft cosimo'];
  var DEFAULT_SILENCE_MS = 3000;

  function supportsRecognition() {
    return Boolean(RecognitionCtor);
  }

  function supportsSpeech() {
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
          score += 18;
        }
      });
      MALE_HINTS.forEach(function (hint) {
        if (haystack.indexOf(hint) >= 0) {
          score -= 8;
        }
      });
    }
    if (haystack.indexOf('natural') >= 0 || haystack.indexOf('neural') >= 0) {
      score += 6;
    }
    if (haystack.indexOf('premium') >= 0 || haystack.indexOf('enhanced') >= 0) {
      score += 4;
    }
    return score;
  }

  function pickItalianVoice(options) {
    if (!supportsSpeech()) {
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
    if (supportsSpeech()) {
      synth.cancel();
    }
  }

  function speak(text, options) {
    if (!supportsSpeech() || !text) {
      return false;
    }
    cancelSpeech();
    var utterance = new SpeechSynthesisUtterance(String(text));
    utterance.lang = (options && options.lang) || 'it-IT';
    utterance.rate = (options && options.rate) || 0.96;
    utterance.pitch = (options && options.pitch) || 1.05;
    utterance.volume = (options && options.volume) || 1;
    var voice = pickItalianVoice(options || {});
    if (voice) {
      utterance.voice = voice;
    }
    synth.speak(utterance);
    return true;
  }

  if (supportsSpeech() && synth.onvoiceschanged !== undefined) {
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
  };
})();
