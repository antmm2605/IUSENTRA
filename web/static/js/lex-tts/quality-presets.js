(function (root) {
  'use strict';

  var QUALITY_PRESETS = {
    fast: {
      id: 'fast',
      label: 'Rapida',
      totalStep: 4,
      speed: 1.08,
      silenceDuration: 0.18,
      maxChunkChars: 220,
      browserRateMultiplier: 1.04,
    },
    balanced: {
      id: 'balanced',
      label: 'Bilanciata',
      totalStep: 8,
      speed: 1.0,
      silenceDuration: 0.25,
      maxChunkChars: 280,
      browserRateMultiplier: 1.0,
    },
    high: {
      id: 'high',
      label: 'Alta qualita',
      totalStep: 12,
      speed: 0.96,
      silenceDuration: 0.32,
      maxChunkChars: 320,
      browserRateMultiplier: 0.96,
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
