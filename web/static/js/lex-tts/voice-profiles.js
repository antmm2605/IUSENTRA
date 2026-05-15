(function (root) {
  'use strict';

  var DEFAULT_PROFILE_ID = 'lex-it-professional';

  var VOICE_PROFILES = {
    'lex-it-professional': {
      id: 'lex-it-professional',
      label: 'Lex Professionale',
      badgeLabel: 'Voce professionale',
      lang: 'it-IT',
      genderHint: 'female',
      rate: 0.92,
      pitch: 1.04,
      volume: 0.98,
      maxAutoReadChars: 1800,
      maxChunkChars: 280,
      pauseMs: { sentence: 180, paragraph: 420, section: 650 },
      enginePreference: ['supertonic', 'browser'],
      qualityPreset: 'balanced',
      mode: 'summary',
    },
    'lex-it-reading': {
      id: 'lex-it-reading',
      label: 'Lettura atti',
      badgeLabel: 'Lettura atti',
      lang: 'it-IT',
      genderHint: 'female',
      rate: 0.84,
      pitch: 1.0,
      volume: 0.98,
      maxAutoReadChars: 4200,
      maxChunkChars: 300,
      pauseMs: { sentence: 260, paragraph: 560, section: 780 },
      enginePreference: ['supertonic', 'browser'],
      qualityPreset: 'balanced',
      mode: 'document_reading',
    },
    'lex-it-brief': {
      id: 'lex-it-brief',
      label: 'Sintesi breve',
      badgeLabel: 'Voce breve',
      lang: 'it-IT',
      genderHint: 'female',
      rate: 0.96,
      pitch: 1.03,
      volume: 0.98,
      maxAutoReadChars: 900,
      maxChunkChars: 240,
      pauseMs: { sentence: 150, paragraph: 320, section: 520 },
      enginePreference: ['supertonic', 'browser'],
      qualityPreset: 'fast',
      mode: 'summary',
    },
    'lex-it-accessibility': {
      id: 'lex-it-accessibility',
      label: 'Accessibilita',
      badgeLabel: 'Accessibilita',
      lang: 'it-IT',
      genderHint: 'female',
      rate: 0.78,
      pitch: 1.02,
      volume: 1.0,
      maxAutoReadChars: 2400,
      maxChunkChars: 240,
      pauseMs: { sentence: 320, paragraph: 680, section: 900 },
      enginePreference: ['supertonic', 'browser'],
      qualityPreset: 'balanced',
      mode: 'accessibility',
    },
  };

  function qualityApi() {
    return root.IusentraTtsQualityPresets || null;
  }

  function getProfile(id) {
    var key = String(id || DEFAULT_PROFILE_ID).trim();
    return Object.assign({}, VOICE_PROFILES[key] || VOICE_PROFILES[DEFAULT_PROFILE_ID]);
  }

  function resolveSpeechOptions(options) {
    options = options || {};
    var profile = getProfile(options.profileId);
    var qualityId = options.quality || options.qualityPreset || profile.qualityPreset || 'balanced';
    var preset = qualityApi() && qualityApi().getQualityPreset ? qualityApi().getQualityPreset(qualityId) : { id: qualityId };
    var pauseMs = Object.assign({}, profile.pauseMs || {}, options.pauseMs || {});
    var rate = Number(options.rate || 0) || profile.rate || 0.93;
    var multiplier = Number(preset.browserRateMultiplier || 0) || 1;
    return Object.assign({}, profile, preset, options, {
      profileId: profile.id,
      profileLabel: profile.label,
      badgeLabel: profile.badgeLabel,
      quality: preset.id || qualityId,
      qualityPreset: preset.id || qualityId,
      lang: options.lang || profile.lang || 'it-IT',
      rate: rate * multiplier,
      pitch: Number(options.pitch || 0) || profile.pitch || 1.0,
      volume: Number(options.volume || 0) || profile.volume || 1.0,
      maxAutoReadChars: Number(options.maxAutoReadChars || 0) || profile.maxAutoReadChars || 1800,
      maxChunkChars: Number(options.maxChunkChars || 0) || preset.maxChunkChars || profile.maxChunkChars || 280,
      pauseMs: pauseMs,
      mode: options.mode || profile.mode || 'summary',
      enginePreference: options.enginePreference || profile.enginePreference || ['supertonic', 'browser'],
      preferFemale: options.preferFemale !== false && profile.genderHint !== 'male',
    });
  }

  root.IusentraVoiceProfiles = {
    DEFAULT_PROFILE_ID: DEFAULT_PROFILE_ID,
    VOICE_PROFILES: VOICE_PROFILES,
    getProfile: getProfile,
    resolveSpeechOptions: resolveSpeechOptions,
  };
})(typeof window !== 'undefined' ? window : globalThis);
