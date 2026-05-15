(function (root) {
  'use strict';

  var lastStatus = null;

  function browserEngine() {
    return root.IusentraBrowserSpeechEngine || null;
  }

  function supertonicEngine() {
    return root.IusentraSupertonicEngine || null;
  }

  function emit(status) {
    lastStatus = status;
    try {
      root.dispatchEvent(new CustomEvent('iusentra:lex-voice-status', { detail: status }));
    } catch (_error) {}
  }

  function getPreferredEngine(options) {
    options = options || {};
    var preference = options.enginePreference || ['supertonic', 'browser'];
    for (var index = 0; index < preference.length; index += 1) {
      var name = preference[index];
      if (name === 'supertonic') {
        var supertonic = supertonicEngine();
        if (supertonic && supertonic.isSupported && supertonic.isSupported() && supertonic.isReady && supertonic.isReady()) {
          return supertonic;
        }
      }
      if (name === 'browser') {
        var browser = browserEngine();
        if (browser && browser.isSupported && browser.isSupported()) {
          return browser;
        }
      }
    }
    return null;
  }

  function preload(options) {
    var supertonic = supertonicEngine();
    if (!supertonic || !supertonic.preload) {
      return Promise.resolve(getStatus());
    }
    return supertonic.preload(options || {}).then(function () {
      emit(getStatus());
      return getStatus();
    }).catch(function () {
      emit(getStatus());
      return getStatus();
    });
  }

  function speak(text, options) {
    options = options || {};
    var engine = getPreferredEngine(options);
    if (!engine) {
      return Promise.resolve({ ok: false, reason: 'no_engine' });
    }
    emit(engine.getStatus ? engine.getStatus() : getStatus());
    return Promise.resolve(engine.speak(text, options)).then(function (result) {
      if (result && result.ok) {
        emit(engine.getStatus ? engine.getStatus() : getStatus());
        return result;
      }
      if (engine !== browserEngine() && browserEngine() && browserEngine().isSupported()) {
        emit(browserEngine().getStatus());
        return browserEngine().speak(text, Object.assign({}, options, { enginePreference: ['browser'] }));
      }
      return result || { ok: false, reason: 'speech_failed' };
    }).catch(function () {
      if (browserEngine() && browserEngine().isSupported()) {
        emit(browserEngine().getStatus());
        return browserEngine().speak(text, Object.assign({}, options, { enginePreference: ['browser'] }));
      }
      return { ok: false, reason: 'speech_failed' };
    });
  }

  function cancel() {
    [supertonicEngine(), browserEngine()].forEach(function (engine) {
      if (engine && engine.cancel) {
        try {
          engine.cancel();
        } catch (_error) {}
      }
    });
  }

  function getStatus() {
    var supertonic = supertonicEngine();
    var superStatus = supertonic && supertonic.getStatus ? supertonic.getStatus() : null;
    if (superStatus && superStatus.ready) {
      return superStatus;
    }
    var browser = browserEngine();
    if (browser && browser.getStatus) {
      return browser.getStatus();
    }
    return lastStatus || {
      engine: 'none',
      label: 'Voce non supportata',
      supported: false,
      ready: false,
      backend: 'none',
    };
  }

  root.IusentraTtsEngineRegistry = {
    init: preload,
    preload: preload,
    speak: speak,
    cancel: cancel,
    getStatus: getStatus,
    supportsNeuralSpeech: function () {
      var supertonic = supertonicEngine();
      return Boolean(supertonic && supertonic.isSupported && supertonic.isSupported());
    },
    getBackendLabel: function () { return getStatus().label; },
  };
})(typeof window !== 'undefined' ? window : globalThis);
