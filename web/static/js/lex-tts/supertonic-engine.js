(function (root) {
  'use strict';

  var DEFAULT_MANIFEST_PATH = '/static/vendor/supertonic/manifest.json';
  var MODEL_FILES = {
    duration: 'duration_predictor.onnx',
    textEncoder: 'text_encoder.onnx',
    vectorEstimator: 'vector_estimator.onnx',
    vocoder: 'vocoder.onnx',
    config: 'tts.json',
    unicodeIndexer: 'unicode_indexer.json',
  };
  var AVAILABLE_LANGS = {
    en: true, ko: true, ja: true, ar: true, bg: true, cs: true, da: true, de: true,
    el: true, es: true, et: true, fi: true, fr: true, hi: true, hr: true, hu: true,
    id: true, it: true, lt: true, lv: true, nl: true, pl: true, pt: true, ro: true,
    ru: true, sk: true, sl: true, sv: true, tr: true, uk: true, vi: true,
  };

  var manifest = null;
  var ortRuntime = null;
  var pipeline = null;
  var currentStyle = null;
  var currentStyleName = '';
  var activeAudio = null;
  var activeUrl = '';
  var activeJob = 0;
  var loadingPromise = null;
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

  function setStatus(next) {
    status = Object.assign({}, status, next || {});
    emitStatus();
    return status;
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

  function joinPath(base, name) {
    return String(base || '').replace(/\/+$/, '') + '/' + String(name || '').replace(/^\/+/, '');
  }

  function fetchJson(path) {
    var safePath = sameOriginPath(path);
    if (!safePath || !root.fetch) {
      return Promise.reject(new Error('Risorsa locale non valida.'));
    }
    return root.fetch(safePath, { credentials: 'same-origin', cache: 'no-store' }).then(function (response) {
      if (!response.ok) {
        throw new Error('Risorsa locale non disponibile.');
      }
      return response.json();
    });
  }

  function loadScript(path) {
    return new Promise(function (resolve, reject) {
      var safePath = sameOriginPath(path);
      if (!safePath || !root.document) {
        reject(new Error('Runtime locale non configurato.'));
        return;
      }
      var existing = root.document.querySelector('script[data-iusentra-supertonic-runtime="' + safePath + '"]');
      if (existing && root.ort) {
        resolve(root.ort);
        return;
      }
      var script = root.document.createElement('script');
      script.src = safePath;
      script.async = true;
      script.defer = true;
      script.dataset.iusentraSupertonicRuntime = safePath;
      script.onload = function () {
        root.ort ? resolve(root.ort) : reject(new Error('ONNX Runtime non esposto dal bundle locale.'));
      };
      script.onerror = function () { reject(new Error('ONNX Runtime locale non caricabile.')); };
      root.document.head.appendChild(script);
    });
  }

  function loadManifest(path) {
    return fetchJson(path || DEFAULT_MANIFEST_PATH).catch(function () { return null; });
  }

  function resolveLang(value) {
    var lang = String(value || 'it-IT').toLowerCase().split('-')[0];
    return AVAILABLE_LANGS[lang] ? lang : 'it';
  }

  function flatten(value, output) {
    output = output || [];
    if (Array.isArray(value)) {
      value.forEach(function (item) { flatten(item, output); });
    } else {
      output.push(Number(value) || 0);
    }
    return output;
  }

  function lengthToMask(lengths, maxLen) {
    var actualMax = maxLen || Math.max.apply(Math, lengths);
    return lengths.map(function (length) {
      var row = new Array(actualMax).fill(0);
      for (var index = 0; index < Math.min(length, actualMax); index += 1) {
        row[index] = 1;
      }
      return [row];
    });
  }

  function preprocessText(value, lang, indexer) {
    var clean = String(value || '').normalize('NFKD');
    clean = clean
      .replace(/[\u2013\u2011\u2014]/g, '-')
      .replace(/[\u201c\u201d]/g, '"')
      .replace(/[\u2018\u2019\u00b4`]/g, "'")
      .replace(/\u20ac/g, ' euro ')
      .replace(/[\u2665\u2606\u2661\u00a9\\]/g, '');
    clean = clean
      .replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]+/gu, '')
      .replace(/[–‑—]/g, '-')
      .replace(/[“”]/g, '"')
      .replace(/[‘’´`]/g, "'")
      .replace(/[\[\]#|]/g, ' ')
      .replace(/[♥☆♡©\\]/g, '')
      .replace(/\s+/g, ' ')
      .trim();
    if (clean && !/[.!?;:,'"')\]}]$/.test(clean)) {
      clean += '.';
    }
    clean = '<' + lang + '>' + clean + '</' + lang + '>';

    var ids = [];
    for (var offset = 0; offset < clean.length; offset += 1) {
      var codePoint = clean.codePointAt(offset);
      if (codePoint > 0xffff) {
        offset += 1;
      }
      ids.push(codePoint < indexer.length ? Number(indexer[codePoint]) : -1);
    }
    return ids;
  }

  function processText(textList, langList, indexer) {
    var rows = textList.map(function (value, index) {
      return preprocessText(value, langList[index], indexer);
    });
    var lengths = rows.map(function (row) { return row.length; });
    var maxLen = Math.max.apply(Math, lengths);
    var padded = rows.map(function (row) {
      var next = new Array(maxLen).fill(0);
      for (var index = 0; index < row.length; index += 1) {
        next[index] = row[index];
      }
      return next;
    });
    return {
      textIds: padded,
      textMask: lengthToMask(lengths, maxLen),
    };
  }

  function sampleNoisyLatent(duration, cfgs) {
    var sampleRate = Number(cfgs.ae && cfgs.ae.sample_rate) || 24000;
    var baseChunkSize = Number(cfgs.ae && cfgs.ae.base_chunk_size) || 512;
    var chunkCompress = Number(cfgs.ttl && cfgs.ttl.chunk_compress_factor) || 1;
    var latentDim = Number(cfgs.ttl && cfgs.ttl.latent_dim) || 64;
    var maxDur = Math.max.apply(Math, duration);
    var wavLengths = duration.map(function (item) { return Math.floor(item * sampleRate); });
    var chunkSize = baseChunkSize * chunkCompress;
    var latentLen = Math.max(1, Math.floor((Math.floor(maxDur * sampleRate) + chunkSize - 1) / chunkSize));
    var latentDimValue = latentDim * chunkCompress;
    var latentLengths = wavLengths.map(function (length) {
      return Math.max(1, Math.floor((length + chunkSize - 1) / chunkSize));
    });
    var mask = lengthToMask(latentLengths, latentLen);
    var xt = [];
    for (var batchIndex = 0; batchIndex < duration.length; batchIndex += 1) {
      var batch = [];
      for (var dim = 0; dim < latentDimValue; dim += 1) {
        var row = [];
        for (var time = 0; time < latentLen; time += 1) {
          var u1 = Math.max(0.0001, Math.random());
          var u2 = Math.random();
          var value = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
          row.push(value * mask[batchIndex][0][time]);
        }
        batch.push(row);
      }
      xt.push(batch);
    }
    return { xt: xt, latentMask: mask };
  }

  function makeTensor(type, values, dims) {
    return new ortRuntime.Tensor(type, values, dims);
  }

  function inferOne(textValue, lang, style, options) {
    var start = root.performance && root.performance.now ? root.performance.now() : Date.now();
    var textPack = processText([textValue], [lang], pipeline.indexer);
    var bsz = 1;
    var textIdsFlat = new BigInt64Array(flatten(textPack.textIds).map(function (item) { return BigInt(item); }));
    var textIdsShape = [bsz, textPack.textIds[0].length];
    var textMaskFlat = new Float32Array(flatten(textPack.textMask));
    var textMaskShape = [bsz, 1, textPack.textMask[0][0].length];
    var textIdsTensor = makeTensor('int64', textIdsFlat, textIdsShape);
    var textMaskTensor = makeTensor('float32', textMaskFlat, textMaskShape);
    var totalStep = Math.max(1, Number(options.totalStep) || 8);
    var speed = Math.max(0.5, Number(options.speed) || 1);

    return pipeline.duration.run({
      text_ids: textIdsTensor,
      style_dp: style.dp,
      text_mask: textMaskTensor,
    }).then(function (dpOutputs) {
      var duration = Array.from(dpOutputs.duration.data).map(function (item) { return Number(item) / speed; });
      return pipeline.textEncoder.run({
        text_ids: textIdsTensor,
        style_ttl: style.ttl,
        text_mask: textMaskTensor,
      }).then(function (textEncOutputs) {
        var sampled = sampleNoisyLatent(duration, pipeline.cfgs);
        var latentMaskFlat = new Float32Array(flatten(sampled.latentMask));
        var latentMaskTensor = makeTensor('float32', latentMaskFlat, [bsz, 1, sampled.latentMask[0][0].length]);
        var totalStepTensor = makeTensor('float32', new Float32Array([totalStep]), [bsz]);
        var xt = sampled.xt;
        var chain = Promise.resolve();
        for (var step = 0; step < totalStep; step += 1) {
          (function (currentStep) {
            chain = chain.then(function () {
              if (activeJob !== options.jobId) {
                throw new Error('Sintesi annullata.');
              }
              var xtFlat = new Float32Array(flatten(xt));
              var xtShape = [bsz, xt[0].length, xt[0][0].length];
              return pipeline.vectorEstimator.run({
                noisy_latent: makeTensor('float32', xtFlat, xtShape),
                text_emb: textEncOutputs.text_emb,
                style_ttl: style.ttl,
                latent_mask: latentMaskTensor,
                text_mask: textMaskTensor,
                current_step: makeTensor('float32', new Float32Array([currentStep]), [bsz]),
                total_step: totalStepTensor,
              }).then(function (vectorOutputs) {
                var data = Array.from(vectorOutputs.denoised_latent.data);
                var cursor = 0;
                xt = [];
                for (var b = 0; b < xtShape[0]; b += 1) {
                  var batch = [];
                  for (var dim = 0; dim < xtShape[1]; dim += 1) {
                    var row = [];
                    for (var time = 0; time < xtShape[2]; time += 1) {
                      row.push(data[cursor]);
                      cursor += 1;
                    }
                    batch.push(row);
                  }
                  xt.push(batch);
                }
              });
            });
          })(step);
        }
        return chain.then(function () {
          var finalXtFlat = new Float32Array(flatten(xt));
          return pipeline.vocoder.run({
            latent: makeTensor('float32', finalXtFlat, [bsz, xt[0].length, xt[0][0].length]),
          }).then(function (vocoderOutputs) {
            var wav = Array.from(vocoderOutputs.wav_tts.data);
            var elapsed = (root.performance && root.performance.now ? root.performance.now() : Date.now()) - start;
            status.lastSynthesisMs = Math.round(elapsed);
            return { wav: wav, duration: duration };
          });
        });
      });
    });
  }

  function writeWavFile(audioData, sampleRate) {
    var numChannels = 1;
    var bitsPerSample = 16;
    var bytesPerSample = bitsPerSample / 8;
    var blockAlign = numChannels * bytesPerSample;
    var byteRate = sampleRate * blockAlign;
    var dataSize = audioData.length * bytesPerSample;
    var buffer = new ArrayBuffer(44 + dataSize);
    var view = new DataView(buffer);
    function writeString(offset, value) {
      for (var index = 0; index < value.length; index += 1) {
        view.setUint8(offset + index, value.charCodeAt(index));
      }
    }
    writeString(0, 'RIFF');
    view.setUint32(4, 36 + dataSize, true);
    writeString(8, 'WAVE');
    writeString(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, bitsPerSample, true);
    writeString(36, 'data');
    view.setUint32(40, dataSize, true);
    var output = new Int16Array(audioData.length);
    for (var index = 0; index < audioData.length; index += 1) {
      var sample = Math.max(-1, Math.min(1, Number(audioData[index]) || 0));
      output[index] = Math.round(sample * 32767);
    }
    new Uint8Array(buffer, 44).set(new Uint8Array(output.buffer));
    return buffer;
  }

  function loadVoiceStyle(styleName) {
    var voiceStylesPath = sameOriginPath(manifest.voiceStylesPath || joinPath(manifest.basePath, 'voice_styles'));
    var stylePath = sameOriginPath(joinPath(voiceStylesPath, styleName));
    return fetchJson(stylePath).then(function (voiceStyle) {
      var ttlDims = voiceStyle.style_ttl && voiceStyle.style_ttl.dims;
      var dpDims = voiceStyle.style_dp && voiceStyle.style_dp.dims;
      var ttlData = flatten(voiceStyle.style_ttl && voiceStyle.style_ttl.data);
      var dpData = flatten(voiceStyle.style_dp && voiceStyle.style_dp.data);
      currentStyleName = styleName;
      return {
        ttl: makeTensor('float32', new Float32Array(ttlData), ttlDims),
        dp: makeTensor('float32', new Float32Array(dpData), dpDims),
      };
    });
  }

  function requestedVoiceStyle(options) {
    return String((options && options.voiceStyle) || (manifest && manifest.defaultVoiceStyle) || 'M1.json');
  }

  function loadRequestedVoiceStyle(options) {
    var styleName = requestedVoiceStyle(options);
    if (currentStyle && currentStyleName === styleName) {
      return Promise.resolve(currentStyle);
    }
    return loadVoiceStyle(styleName).catch(function () {
      var fallbackName = String((manifest && manifest.fallbackVoiceStyle) || 'M1.json');
      return loadVoiceStyle(fallbackName);
    }).then(function (style) {
      currentStyle = style;
      return currentStyle;
    });
  }

  function loadRuntime() {
    if (root.ort) {
      ortRuntime = root.ort;
      return Promise.resolve(ortRuntime);
    }
    if (root.IusentraSupertonicRuntime && root.IusentraSupertonicRuntime.ort) {
      ortRuntime = root.IusentraSupertonicRuntime.ort;
      return Promise.resolve(ortRuntime);
    }
    if (manifest && manifest.onnxRuntimeScript) {
      return loadScript(manifest.onnxRuntimeScript).then(function (ort) {
        ortRuntime = ort;
        return ortRuntime;
      });
    }
    return Promise.reject(new Error('ONNX Runtime locale non configurato.'));
  }

  function loadPipelineForBackend(backend) {
    var onnxPath = sameOriginPath(manifest.onnxPath || joinPath(manifest.basePath, 'onnx'));
    var sessionOptions = {
      executionProviders: [backend],
      graphOptimizationLevel: 'all',
    };
    if (ortRuntime && ortRuntime.env && ortRuntime.env.wasm && manifest.wasmPath) {
      ortRuntime.env.wasm.wasmPaths = sameOriginPath(manifest.wasmPath);
    }
    return Promise.all([
      fetchJson(joinPath(onnxPath, MODEL_FILES.config)),
      fetchJson(joinPath(onnxPath, MODEL_FILES.unicodeIndexer)),
      ortRuntime.InferenceSession.create(joinPath(onnxPath, MODEL_FILES.duration), sessionOptions),
      ortRuntime.InferenceSession.create(joinPath(onnxPath, MODEL_FILES.textEncoder), sessionOptions),
      ortRuntime.InferenceSession.create(joinPath(onnxPath, MODEL_FILES.vectorEstimator), sessionOptions),
      ortRuntime.InferenceSession.create(joinPath(onnxPath, MODEL_FILES.vocoder), sessionOptions),
    ]).then(function (items) {
      pipeline = {
        cfgs: items[0],
        indexer: items[1],
        duration: items[2],
        textEncoder: items[3],
        vectorEstimator: items[4],
        vocoder: items[5],
        sampleRate: Number(items[0].ae && items[0].ae.sample_rate) || 24000,
      };
      status.backend = backend;
      return pipeline;
    });
  }

  function preload(options) {
    options = options || {};
    if (pipeline && currentStyle) {
      return loadRequestedVoiceStyle(options).then(function () {
        setStatus({ reason: 'ready', voiceStyle: currentStyleName });
        return getStatus();
      });
    }
    if (loadingPromise) {
      return loadingPromise;
    }
    setStatus({
      label: 'Supertonic in caricamento',
      reason: 'loading_manifest',
      enabled: false,
      supported: false,
      ready: false,
      backend: 'none',
    });
    loadingPromise = loadManifest(options.manifestPath).then(function (loaded) {
      manifest = loaded;
      if (!manifest || !manifest.enabled) {
        return setStatus({
          label: 'Supertonic non disponibile',
          supported: false,
          ready: false,
          enabled: false,
          backend: 'none',
          reason: manifest ? 'disabled' : 'manifest_missing',
        });
      }
      return loadRuntime().then(function () {
        var preferWebGpu = Boolean(root.navigator && root.navigator.gpu);
        var firstBackend = preferWebGpu ? 'webgpu' : 'wasm';
        var secondBackend = firstBackend === 'webgpu' ? 'wasm' : '';
        return loadPipelineForBackend(firstBackend).catch(function () {
          if (!secondBackend) {
            throw new Error('Backend ONNX non disponibile.');
          }
          return loadPipelineForBackend(secondBackend);
        }).then(function () {
          return loadRequestedVoiceStyle(options);
        }).then(function () {
          return setStatus({
            label: status.backend === 'webgpu' ? 'Supertonic WebGPU' : 'Supertonic WASM',
            supported: true,
            ready: true,
            enabled: true,
            reason: 'ready',
            voiceStyle: currentStyleName,
          });
        });
      }).catch(function (error) {
        return setStatus({
          label: 'Supertonic non disponibile',
          supported: false,
          ready: false,
          enabled: true,
          backend: 'none',
          reason: String((error && error.message) || 'preload_failed'),
        });
      });
    }).finally(function () {
      loadingPromise = null;
    });
    return loadingPromise;
  }

  function isSupported() {
    return Boolean(status.enabled && (status.supported || root.ort || (manifest && manifest.onnxRuntimeScript)));
  }

  function isReady() {
    return Boolean(status.ready && pipeline && currentStyle);
  }

  function normalizeForSupertonic(value, options) {
    var profiles = root.IusentraVoiceProfiles || null;
    var resolved = profiles && profiles.resolveSpeechOptions ? profiles.resolveSpeechOptions(options || {}) : (options || {});
    var normalizer = root.IusentraLegalSpeechNormalizer || null;
    var clean = options && options.skipNormalization
      ? String(value || '').trim()
      : (normalizer && normalizer.normalizeLegalSpeechText
        ? normalizer.normalizeLegalSpeechText(value, resolved)
        : String(value || '').replace(/\s+/g, ' ').trim());
    var chunks = normalizer && normalizer.splitLegalSpeechChunks
      ? normalizer.splitLegalSpeechChunks(clean, resolved)
      : [{ text: clean, pauseAfterMs: 180 }];
    return { text: clean, chunks: chunks, options: resolved };
  }

  function playWavBuffer(buffer, jobId) {
    if (!root.Blob || !root.URL || !root.Audio) {
      return Promise.resolve({ ok: false, engine: 'supertonic', reason: 'audio_api_missing' });
    }
    cancel();
    activeJob = jobId;
    var blob = new Blob([buffer], { type: 'audio/wav' });
    activeUrl = root.URL.createObjectURL(blob);
    activeAudio = new Audio(activeUrl);
    return new Promise(function (resolve) {
      activeAudio.onended = function () {
        revokeAudioUrl();
        resolve({ ok: true, engine: 'supertonic', backend: status.backend });
      };
      activeAudio.onerror = function () {
        revokeAudioUrl();
        resolve({ ok: false, engine: 'supertonic', reason: 'playback_failed' });
      };
      activeAudio.play().catch(function () {
        revokeAudioUrl();
        resolve({ ok: false, engine: 'supertonic', reason: 'playback_blocked' });
      });
    });
  }

  function speak(value, options) {
    options = options || {};
    var prepared = normalizeForSupertonic(value, options);
    if (!prepared.text) {
      return Promise.resolve({ ok: false, engine: 'supertonic', reason: 'empty_text' });
    }
    var jobId = activeJob + 1;
    activeJob = jobId;
    return preload(prepared.options).then(function () {
      if (!isReady()) {
        return { ok: false, engine: 'supertonic', reason: status.reason || 'not_ready' };
      }
      setStatus({ label: status.backend === 'webgpu' ? 'Supertonic WebGPU' : 'Supertonic WASM', reason: 'synthesizing' });
      var lang = resolveLang(prepared.options.lang);
      var silenceDuration = Number(prepared.options.silenceDuration);
      if (!isFinite(silenceDuration)) {
        silenceDuration = 0.25;
      }
      var wavCat = [];
      var chain = Promise.resolve();
      var previousPauseMs = 0;
      prepared.chunks.forEach(function (chunk, index) {
        chain = chain.then(function () {
          if (jobId !== activeJob) {
            throw new Error('Sintesi annullata.');
          }
          return inferOne(String(chunk.text || chunk || ''), lang, currentStyle, Object.assign({}, prepared.options, { jobId: jobId }))
            .then(function (result) {
              if (index > 0) {
                var pauseMs = previousPauseMs || Math.round(silenceDuration * 1000);
                var silenceSamples = Math.floor((pauseMs / 1000) * pipeline.sampleRate);
                for (var i = 0; i < silenceSamples; i += 1) {
                  wavCat.push(0);
                }
              }
              var wavLen = Math.floor(pipeline.sampleRate * Number(result.duration[0] || 0));
              var segment = result.wav.slice(0, wavLen || result.wav.length);
              for (var sampleIndex = 0; sampleIndex < segment.length; sampleIndex += 1) {
                wavCat.push(segment[sampleIndex]);
              }
              previousPauseMs = Number(chunk.pauseAfterMs) || Math.round(silenceDuration * 1000);
            });
        });
      });
      return chain.then(function () {
        if (jobId !== activeJob) {
          return { ok: false, engine: 'supertonic', reason: 'cancelled' };
        }
        var buffer = writeWavFile(wavCat, pipeline.sampleRate);
        return playWavBuffer(buffer, jobId);
      }).finally(function () {
        if (status.ready) {
          setStatus({ label: status.backend === 'webgpu' ? 'Supertonic WebGPU' : 'Supertonic WASM', reason: 'ready' });
        }
      });
    }).catch(function (error) {
      setStatus({ reason: String((error && error.message) || 'synthesis_failed') });
      return { ok: false, engine: 'supertonic', reason: 'synthesis_failed' };
    });
  }

  function revokeAudioUrl() {
    if (activeUrl && root.URL && root.URL.revokeObjectURL) {
      try {
        root.URL.revokeObjectURL(activeUrl);
      } catch (_error) {}
    }
    activeUrl = '';
    activeAudio = null;
  }

  function cancel() {
    activeJob += 1;
    if (activeAudio) {
      try {
        activeAudio.pause();
        activeAudio.currentTime = 0;
      } catch (_error) {}
    }
    revokeAudioUrl();
    return true;
  }

  function getStatus() {
    return Object.assign({}, status);
  }

  root.IusentraSupertonicEngine = {
    init: preload,
    preload: preload,
    isSupported: isSupported,
    isReady: isReady,
    speak: speak,
    cancel: cancel,
    getStatus: getStatus,
    getBackendLabel: function () { return getStatus().label; },
  };
})(typeof window !== 'undefined' ? window : globalThis);
