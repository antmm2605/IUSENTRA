(function (root) {
  'use strict';

  var QUALITY_PRESETS = {
    fast: {
      id: 'fast',
      label: 'Rapida',
      totalStep: 8,
      speed: 1.0,
      silenceDuration: 0.24,
      maxChunkChars: 190,
      browserRateMultiplier: 1.0,
    },
    balanced: {
      id: 'balanced',
      label: 'Bilanciata',
      totalStep: 12,
      speed: 0.94,
      silenceDuration: 0.34,
      maxChunkChars: 220,
      browserRateMultiplier: 0.94,
    },
    high: {
      id: 'high',
      label: 'Alta qualita',
      totalStep: 18,
      speed: 0.9,
      silenceDuration: 0.42,
      maxChunkChars: 240,
      browserRateMultiplier: 0.9,
    },
  };

  function getQualityPreset(id) {
    var key = String(id || 'balanced').trim();
    return Object.assign({}, QUALITY_PRESETS[key] || QUALITY_PRESETS.balanced);
  }

  root.IusentraTtsQualityPresets = {
    QUALITY_PRESETS: QUALITY_PRESETS,
    getQualityPreset: getQualityPreset,
  };
})(typeof window !== 'undefined' ? window : globalThis);
