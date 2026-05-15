(function (root) {
  'use strict';

  var DEFAULT_MANIFEST_PATH = '/static/vendor/supertonic/manifest.json';
  var manifest = null;
  var status = {
    engine: 'supertonic',
    label: 'Supertonic non disponibile',
    supported: false,
    ready: false,
    enabled: false,
    backend: 'none',
    reason: 'not_loaded',
  };

  function emitStatus() {
    try {
      root.dispatchEvent(new CustomEvent('iusentra:lex-voice-status', { detail: getStatus() }));
    } catch (_error) {}
  }

  function sameOriginPath(value) {
    var raw = String(value || '').trim();
    if (!raw) {
      return '';
    }
    try {
      var url = new URL(raw, root.location && root.location.origin ? root.location.origin : 'http://localhost');
      if (root.location && url.origin !== root.location.origin) {
        return '';
      }
      return url.pathname + url.search;
    } catch (_error) {
      return raw.charAt(0) === '/' ? raw : '';
    }
  }

  function loadManifest(path) {
    var manifestPath = sameOriginPath(path || DEFAULT_MANIFEST_PATH);
    if (!manifestPath || !root.fetch) {
      return Promise.resolve(null);
    }
    return root.fetch(manifestPath, { credentials: 'same-origin', cache: 'no-store' })
      .then(function (response) {
        if (!response.ok) {
          return null;
        }
        return response.json();
      })
      .catch(function () { return null; });
  }

  function isSupported() {
    return Boolean(manifest && manifest.enabled && (root.ort || root.IusentraSupertonicRuntime));
  }

  function preload(options) {
    options = options || {};
    if (status.loading) {
      return status.loading;
    }
    status.label = 'Supertonic in caricamento';
    status.reason = 'loading_manifest';
    emitStatus();
    status.loading = loadManifest(options.manifestPath).then(function (loaded) {
      manifest = loaded;
      if (!manifest || !manifest.enabled) {
        status = {
          engine: 'supertonic',
          label: 'Supertonic non disponibile',
          supported: false,
          ready: false,
          enabled: false,
          backend: 'none',
          reason: manifest ? 'disabled' : 'manifest_missing',
        };
        emitStatus();
        return status;
      }
      status = {
        engine: 'supertonic',
        label: 'Supertonic non disponibile',
        supported: isSupported(),
        ready: false,
        enabled: true,
        backend: 'none',
        reason: root.ort || root.IusentraSupertonicRuntime ? 'runtime_ready_for_phase_3' : 'onnx_runtime_missing',
      };
      emitStatus();
      return status;
    }).finally(function () {
      status.loading = null;
    });
    return status.loading;
  }

  function speak() {
    return Promise.resolve({ ok: false, engine: 'supertonic', reason: status.reason || 'not_ready' });
  }

  function cancel() {
    return true;
  }

  function getStatus() {
    return Object.assign({}, status);
  }

  root.IusentraSupertonicEngine = {
    init: preload,
    preload: preload,
    isSupported: isSupported,
    isReady: function () { return Boolean(status.ready); },
    speak: speak,
    cancel: cancel,
    getStatus: getStatus,
    getBackendLabel: function () { return getStatus().label; },
  };
})(typeof window !== 'undefined' ? window : globalThis);
