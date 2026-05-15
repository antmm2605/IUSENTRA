(function (root) {
  'use strict';

  var synth = root.speechSynthesis || null;
  var activeJob = 0;
  var FEMALE_HINTS = ['female', 'elsa', 'alice', 'lucia', 'sofia', 'giulia', 'bianca', 'federica', 'serena', 'aria', 'emma', 'sara'];
  var MALE_HINTS = ['male', 'diego', 'luca', 'paolo', 'marco', 'cosimo'];
  var NATURAL_HINTS = ['natural', 'neural', 'premium', 'enhanced', 'online', 'desktop'];

  function normalizer() {
    return root.IusentraLegalSpeechNormalizer || null;
  }

  function isSupported() {
    return Boolean(synth && root.SpeechSynthesisUtterance);
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
    if (!isSupported() || !synth.getVoices) {
      return null;
    }
    var voices = synth.getVoices() || [];
    if (!voices.length) {
      return null;
    }
    var preferFemale = !options || options.preferFemale !== false;
    return voices.slice().sort(function (left, right) {
      return scoreVoice(right, preferFemale) - scoreVoice(left, preferFemale);
    })[0] || null;
  }

  function normalizeText(value, options) {
    var helper = normalizer();
    if (helper && helper.normalizeLegalSpeechText && (!options || options.legalNormalization !== false)) {
      return helper.normalizeLegalSpeechText(value, options || {});
    }
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function splitChunks(value, options) {
    var helper = normalizer();
    if (helper && helper.splitLegalSpeechChunks) {
      return helper.splitLegalSpeechChunks(value, options || {});
    }
    var clean = String(value || '').replace(/\s+/g, ' ').trim();
    return clean ? [{ text: clean, pauseAfterMs: 120, type: 'sentence' }] : [];
  }

  function cancel() {
    activeJob += 1;
    if (synth) {
      try {
        synth.cancel();
      } catch (_error) {}
    }
  }

  function speak(value, options) {
    options = options || {};
    if (!isSupported() || !value) {
      return Promise.resolve({ ok: false, engine: 'browser', reason: 'not_supported' });
    }
    cancel();
    var jobId = activeJob;
    var clean = options.skipNormalization ? String(value || '').trim() : normalizeText(value, options);
    var chunks = splitChunks(clean, options);
    var voice = pickItalianVoice(options);
    var index = 0;

    return new Promise(function (resolve) {
      function speakNext() {
        if (!isSupported() || jobId !== activeJob) {
          resolve({ ok: false, engine: 'browser', reason: 'cancelled' });
          return;
        }
        if (index >= chunks.length) {
          resolve({ ok: true, engine: 'browser' });
          return;
        }
        var item = chunks[index] || {};
        var utterance = new root.SpeechSynthesisUtterance(String(item.text || item || '').trim());
        if (!utterance.text) {
          index += 1;
          speakNext();
          return;
        }
        utterance.lang = options.lang || 'it-IT';
        utterance.rate = Number(options.rate) || 0.93;
        utterance.pitch = Number(options.pitch) || 1.08;
        utterance.volume = Number(options.volume) || 0.98;
        if (voice) {
          utterance.voice = voice;
        }
        utterance.onend = function () {
          index += 1;
          root.setTimeout(speakNext, Math.max(40, Number(item.pauseAfterMs) || 80));
        };
        utterance.onerror = function () {
          resolve({ ok: false, engine: 'browser', reason: 'speech_error' });
        };
        synth.speak(utterance);
      }
      speakNext();
    });
  }

  function getStatus() {
    return {
      engine: 'browser',
      label: isSupported() ? 'Voce browser' : 'Voce non supportata',
      supported: isSupported(),
      ready: isSupported(),
      backend: 'browser',
    };
  }

  if (isSupported() && synth.onvoiceschanged !== undefined) {
    synth.onvoiceschanged = function () {
      pickItalianVoice({ preferFemale: true });
    };
  }

  root.IusentraBrowserSpeechEngine = {
    init: function () { return Promise.resolve(getStatus()); },
    preload: function () { return Promise.resolve(getStatus()); },
    isSupported: isSupported,
    isReady: isSupported,
    speak: speak,
    cancel: cancel,
    getStatus: getStatus,
    getBackendLabel: function () { return getStatus().label; },
  };
})(typeof window !== 'undefined' ? window : globalThis);
