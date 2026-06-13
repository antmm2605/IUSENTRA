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
  var microphonePermissionState = 'unknown';
  var microphonePreflightGranted = false;
  var lastVoiceInputTarget = null;

  function isMicrophonePermissionError(error) {
    var name = String(error && error.name || '').toLowerCase();
    var message = String(error && error.message || '').toLowerCase();
    return name === 'notallowederror' ||
      name === 'permissiondeniederror' ||
      name === 'securityerror' ||
      message.indexOf('permission') >= 0 ||
      message.indexOf('denied') >= 0 ||
      message.indexOf('not allowed') >= 0;
  }

  function microphoneDeniedMessage() {
    return 'Dettatura vocale non autorizzata dal browser. Consenti il microfono per questa pagina e riprova.';
  }

  function microphoneGrantedButBlockedMessage() {
    return 'Chrome indica il microfono come consentito, ma la dettatura non è partita. Controlla il microfono scelto da Chrome, chiudi eventuali registrazioni aperte e riprova.';
  }

  function microphoneDeviceUnavailableMessage(error) {
    var name = String(error && error.name || '').toLowerCase();
    if (name === 'notfounderror' || name === 'devicesnotfounderror') {
      return 'Nessun microfono disponibile. Collega o abilita un microfono e riprova.';
    }
    if (name === 'notreadableerror' || name === 'trackstarterror') {
      return 'Il microfono risulta occupato da un altro programma. Chiudi le altre registrazioni e riprova.';
    }
    return 'Microfono non disponibile in questa sessione. Controlla il dispositivo audio e riprova.';
  }

  function stopMediaStream(stream) {
    if (!stream || !stream.getTracks) {
      return;
    }
    stream.getTracks().forEach(function (track) {
      try {
        track.stop();
      } catch (error) {
        // no-op
      }
    });
  }

  function readMicrophonePermission() {
    var nav = window.navigator || {};
    if (!nav.permissions || !nav.permissions.query) {
      microphonePermissionState = 'unknown';
      return Promise.resolve(microphonePermissionState);
    }
    return nav.permissions.query({ name: 'microphone' }).then(function (status) {
      microphonePermissionState = String(status && status.state || 'unknown');
      return microphonePermissionState;
    }).catch(function () {
      microphonePermissionState = 'unknown';
      return microphonePermissionState;
    });
  }

  function hasNamedAudioInputDevice() {
    var nav = window.navigator || {};
    if (!nav.mediaDevices || !nav.mediaDevices.enumerateDevices) {
      return Promise.resolve(false);
    }
    return nav.mediaDevices.enumerateDevices().then(function (devices) {
      return (devices || []).some(function (device) {
        return device && device.kind === 'audioinput' && String(device.label || '').trim();
      });
    }).catch(function () {
      return false;
    });
  }

  function requestMicrophoneStream() {
    var nav = window.navigator || {};
    if (!nav.mediaDevices || !nav.mediaDevices.getUserMedia) {
      return Promise.resolve(null);
    }
    return nav.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      var tracks = stream && stream.getAudioTracks ? stream.getAudioTracks() : [];
      return Promise.all(tracks.map(function (track) {
        if (!track || !track.applyConstraints) {
          return Promise.resolve();
        }
        return track.applyConstraints({
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        }).catch(function () {
          return undefined;
        });
      })).then(function () {
        return stream;
      });
    });
  }

  function verifyMicrophoneAccess() {
    return readMicrophonePermission().then(function () {
      return requestMicrophoneStream().then(function (stream) {
        if (stream) {
          stopMediaStream(stream);
          microphonePreflightGranted = true;
          microphonePermissionState = 'granted';
        }
        return hasNamedAudioInputDevice().then(function (hasDeviceLabel) {
          return {
            ok: true,
            state: microphonePermissionState,
            granted: microphonePreflightGranted || microphonePermissionState === 'granted',
            hasNamedAudioInput: hasDeviceLabel,
          };
        });
      }).catch(function (error) {
        microphonePreflightGranted = false;
        if (isMicrophonePermissionError(error)) {
          microphonePermissionState = 'denied';
          throw new Error(microphoneDeniedMessage());
        }
        throw new Error(microphoneDeviceUnavailableMessage(error));
      });
    });
  }

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

  function commandPattern(command) {
    var escaped = String(command || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+');
    return new RegExp('(^|\\s)' + escaped + '(?=\\s|$)', 'gi');
  }

  function replaceDictationCommand(text, commands, replacement) {
    var next = String(text || '');
    commands.forEach(function (command) {
      next = next.replace(commandPattern(command), function (_match, prefix) {
        return prefix + replacement;
      });
    });
    return next;
  }

  function restoreCompactEmailText(value) {
    return String(value || '').replace(
      /([a-z0-9._%+-]+)\s*@\s*([a-z0-9.-]+)\s*\.\s*([a-z]{2,})(?=\b)/gi,
      function (_match, local, domain, tld) {
        return (local + '@' + domain + '.' + tld).toLowerCase();
      }
    )
      .replace(/\b([a-z0-9._%+-]+)\.\s+([a-z0-9._%+-]+)@/gi, '$1.$2@')
      .replace(/@([a-z0-9.-]+)\.\s+([a-z]{2,})(?=\b)/gi, '@$1.$2');
  }

  function normalizeEmailDictationText(value) {
    var text = restoreCompactEmailText(value).toLowerCase();
    text = text
      .replace(/\s+/g, '')
      .replace(/\s*@\s*/g, '@')
      .replace(/\s*\.\s*/g, '.')
      .replace(/gmail\.com$/i, 'gmail.com')
      .replace(/pec\.it$/i, 'pec.it');
    if (/^[a-z]{2,}-[a-z]{1,5}\d+@/.test(text)) {
      text = text.replace(/^([a-z]{2,})-([a-z]{1,5}\d+@)/, '$1$2');
    }
    if (/^[a-z]{2,}-[a-z]{1,5}\d+gmail\.com$/.test(text)) {
      text = text.replace(/^([a-z]{2,})-([a-z]{1,5}\d+gmail\.com)$/, '$1$2');
    }
    return text;
  }

  function normalizeUrlDictationText(value) {
    return String(value || '')
      .replace(/\s+/g, '')
      .replace(/\s*\.\s*/g, '.')
      .replace(/\s*\/\s*/g, '/')
      .replace(/\s*:\s*/g, ':')
      .replace(/^Www\./i, 'www.')
      .toLowerCase();
  }

  function capitalizeDictationSentences(value) {
    return String(value || '').replace(/(^|[.!?]\s+|\n+)([a-zàèéìòù])/g, function (_match, prefix, letter) {
      return prefix + letter.toUpperCase();
    });
  }

  function formatDictationText(value) {
    var text = String(value || '').replace(/\s+/g, ' ').trim();
    if (!text) {
      return '';
    }

    text = ' ' + text + ' ';
    text = replaceDictationCommand(text, ['nuovo paragrafo', 'nuovo capoverso'], '\n\n');
    text = replaceDictationCommand(text, ['a capo', 'nuova riga', 'vai a capo'], '\n');
    text = replaceDictationCommand(text, ['punto e virgola', 'punto virgola'], ';');
    text = replaceDictationCommand(text, ['punto interrogativo', 'punto di domanda', 'punto domanda'], '?');
    text = replaceDictationCommand(text, ['punto esclamativo', 'punto escamativo', 'punto esclamazione'], '!');
    text = replaceDictationCommand(text, ['due punti'], ':');
    text = replaceDictationCommand(text, ['virgola'], ',');
    text = replaceDictationCommand(text, ['punto fermo', 'punto'], '.');
    text = replaceDictationCommand(text, ['apri parentesi'], '(');
    text = replaceDictationCommand(text, ['chiudi parentesi'], ')');
    text = replaceDictationCommand(text, ['apri virgolette', 'virgolette aperte'], '"');
    text = replaceDictationCommand(text, ['chiudi virgolette', 'virgolette chiuse'], '"');
    text = replaceDictationCommand(text, ['apostrofo'], "'");
    text = replaceDictationCommand(text, ['chiocciola', 'chiocciolina', 'ciocciola'], '@');
    text = replaceDictationCommand(text, ['underscore', 'under score', 'ancscore', 'and score', 'trattino basso'], '_');
    text = replaceDictationCommand(text, ['asterisco', 'aterisco'], '*');
    text = replaceDictationCommand(text, ['spazio meno spazio'], ' - ');
    text = replaceDictationCommand(text, ['spazio più spazio', 'spazio piu spazio'], ' + ');
    text = replaceDictationCommand(text, ['spazio per spazio'], ' * ');
    text = replaceDictationCommand(text, ['spazio diviso spazio'], ' / ');
    text = replaceDictationCommand(text, ['segno meno'], '-');
    text = replaceDictationCommand(text, ['segno più', 'segno piu'], '+');
    text = replaceDictationCommand(text, ['segno uguale'], '=');
    text = replaceDictationCommand(text, ['segno diviso'], '/');
    text = replaceDictationCommand(text, ['segno per'], '*');
    text = replaceDictationCommand(text, ['barra'], '/');
    text = replaceDictationCommand(text, ['trattino'], '-');
    text = replaceDictationCommand(text, ['spazio'], ' ');

    text = text
      .replace(/(\d)\s+meno\s+(\d)/gi, '$1 - $2')
      .replace(/(\d)\s+(?:più|piu)\s+(\d)/gi, '$1 + $2')
      .replace(/(\d)\s+per\s+(\d)/gi, '$1 * $2')
      .replace(/(\d)\s+diviso\s+(\d)/gi, '$1 / $2')
      .replace(/\s+([,.;:!?])/g, '$1')
      .replace(/([,;:!?])(?=[^\s\n])/g, '$1 ')
      .replace(/\(\s+/g, '(')
      .replace(/\s+\)/g, ')')
      .replace(/\s*'\s*/g, "'")
      .replace(/\s*@\s*/g, '@')
      .replace(/\s*_\s*/g, '_')
      .replace(/\s*\*\s*/g, '*')
      .replace(/\s*\/\s*/g, '/')
      .replace(/\s*=\s*/g, '=')
      .replace(/\s{2,}/g, ' ')
      .replace(/\n[ \t]+/g, '\n')
      .replace(/[ \t]+\n/g, '\n')
      .trim();

    text = restoreCompactEmailText(text);
    if (/^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$/i.test(text)) {
      return text.toLowerCase();
    }
    return capitalizeDictationSentences(text);
  }

  function buildCombinedTranscript(session) {
    return formatDictationText(((session.finalText || '') + ' ' + (session.interimText || '')).trim());
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

    return verifyMicrophoneAccess().then(function () {
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
          started: false,
          silenceTimer: null,
          silenceMs: Math.max(1500, Number(options && options.silenceMs || DEFAULT_SILENCE_MS)),
        };
        recognitionSession = session;

        recognition.onstart = function () {
          session.started = true;
          listening = true;
          if (options && typeof options.onStart === 'function') {
            options.onStart();
          }
        };

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
          if (code === 'no-speech' || code === 'aborted') {
            finishRecognition(session, resolve);
            return;
          }
          if (code === 'not-allowed' || code === 'service-not-allowed') {
            failRecognition(
              session,
              reject,
              new Error(microphonePreflightGranted || microphonePermissionState === 'granted'
                ? microphoneGrantedButBlockedMessage()
                : microphoneDeniedMessage())
            );
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

          if (!session.started && (microphonePreflightGranted || microphonePermissionState === 'granted')) {
            failRecognition(session, reject, new Error(microphoneGrantedButBlockedMessage()));
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
        } catch (startError) {
          failRecognition(session, reject, startError);
        }
      });
    });
  }

  function dispatchVoiceInputStatus(detail) {
    try {
      window.dispatchEvent(new CustomEvent('iusentra:voice-input-status', { detail: detail || {} }));
    } catch (error) {
      // no-op
    }
  }

  function isTextInputElement(element) {
    if (!element || !element.tagName) {
      return false;
    }
    var tagName = String(element.tagName || '').toLowerCase();
    if (tagName === 'textarea') {
      return true;
    }
    if (tagName !== 'input') {
      return false;
    }
    var type = String(element.getAttribute('type') || 'text').toLowerCase();
    return [
      'text',
      'search',
      'email',
      'tel',
      'url',
      'number',
      'date',
      'time',
      'datetime-local',
    ].indexOf(type) >= 0;
  }

  function isForbiddenVoiceTarget(element) {
    if (!element) {
      return true;
    }
    var type = String(element.getAttribute && element.getAttribute('type') || '').toLowerCase();
    var name = String(element.getAttribute && (element.getAttribute('name') || element.getAttribute('id') || element.getAttribute('aria-label') || '') || '').toLowerCase();
    if (element.disabled || element.readOnly || element.getAttribute('aria-disabled') === 'true') {
      return true;
    }
    if (['password', 'hidden', 'file', 'checkbox', 'radio', 'range', 'color'].indexOf(type) >= 0) {
      return true;
    }
    return /(csrf|token|pin|password|pass|segreto|secret|private|chiave)/i.test(name);
  }

  function canAttachVoiceInput(element) {
    if (!element || isForbiddenVoiceTarget(element)) {
      return false;
    }
    return isTextInputElement(element) || isSelectVoiceElement(element) || Boolean(element.isContentEditable || element.closest && element.closest('[contenteditable="true"]'));
  }

  function resolveEditableTarget(element) {
    if (!element) {
      return null;
    }
    if (element.isContentEditable) {
      return element;
    }
    if (element.closest) {
      var editable = element.closest('[contenteditable="true"]');
      if (editable) {
        return editable;
      }
    }
    return element;
  }

  function resolveActiveTextTarget(explicitTarget) {
    var target = resolveEditableTarget(explicitTarget || document.activeElement);
    if (canAttachVoiceInput(target)) {
      return target;
    }
    if (lastVoiceInputTarget && document.contains(lastVoiceInputTarget) && canAttachVoiceInput(lastVoiceInputTarget)) {
      return lastVoiceInputTarget;
    }
    return null;
  }

  function rememberVoiceInputTarget(event) {
    var target = resolveEditableTarget(event && event.target);
    if (canAttachVoiceInput(target)) {
      lastVoiceInputTarget = target;
    }
  }

  function dispatchInputEvents(element) {
    if (!element) {
      return;
    }
    ['input', 'change'].forEach(function (eventName) {
      try {
        element.dispatchEvent(new Event(eventName, { bubbles: true }));
      } catch (error) {
        // no-op
      }
    });
  }

  function textForTarget(target, text) {
    var output = formatDictationText(text);
    if (!output) {
      return '';
    }
    if (target && target.tagName && String(target.tagName).toLowerCase() === 'input') {
      var type = String(target.getAttribute('type') || 'text').toLowerCase();
      var descriptor = targetDescriptor(target);
      if (isDateVoiceField(target)) {
        return parseItalianVoiceDate(output) || parseItalianVoiceDate(text);
      }
      if (type === 'email' || /email|pec|mail/i.test(descriptor)) {
        return normalizeEmailDictationText(output);
      }
      if (type === 'url' || /url|link|sito|web/i.test(descriptor)) {
        return normalizeUrlDictationText(output);
      }
      if (/codice[_\s-]*fiscale|codicefiscale|fiscal/i.test(descriptor)) {
        return output.replace(/\s+/g, '').toUpperCase();
      }
      if (isDocumentNumberVoiceField(target)) {
        return compactDocumentCodeFieldText(output);
      }
      if (isCompactNumericVoiceField(target)) {
        return compactNumericFieldText(output);
      }
    }
    return output;
  }

  function isSelectVoiceElement(element) {
    return Boolean(element && element.tagName && String(element.tagName).toLowerCase() === 'select');
  }

  function normalizedOptionText(value) {
    return String(value || '')
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^\w]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function selectOptionFromVoiceText(element, text) {
    if (!isSelectVoiceElement(element)) {
      return '';
    }
    var wanted = normalizedOptionText(text);
    if (!wanted) {
      return '';
    }
    var descriptor = targetDescriptor(element);
    var aliases = [wanted];
    if (/sesso|genere/i.test(descriptor)) {
      if (/^(m|maschio|maschile|uomo)$/.test(wanted)) aliases.push('maschile', 'm');
      if (/^(f|femmina|femminile|donna)$/.test(wanted)) aliases.push('femminile', 'f');
    }
    for (var index = 0; index < element.options.length; index += 1) {
      var option = element.options[index];
      var optionLabel = normalizedOptionText(option.text || option.label || option.value);
      var optionValue = normalizedOptionText(option.value);
      if (aliases.indexOf(optionLabel) >= 0 || aliases.indexOf(optionValue) >= 0) {
        element.value = option.value;
        dispatchInputEvents(element);
        return option.text || option.value;
      }
    }
    return '';
  }

  function targetDescriptor(element) {
    return String(
      element && (
        element.name ||
        element.id ||
        element.getAttribute('aria-label') ||
        element.getAttribute('placeholder') ||
        ''
      ) || ''
    ).toLowerCase();
  }

  function uppercaseFirstFieldLetter(value) {
    return String(value || '').replace(/^(\s*)([a-zàèéìòù])/i, function (_match, prefix, letter) {
      return prefix + letter.toUpperCase();
    });
  }

  function italianSmallNumberWord(value) {
    var key = String(value || '').toLowerCase().replace(/[\s-]+/g, '');
    var numbers = {
      primo: 1, uno: 1, una: 1, due: 2, tre: 3, quattro: 4, cinque: 5, sei: 6, sette: 7, otto: 8, nove: 9,
      dieci: 10, undici: 11, dodici: 12, tredici: 13, quattordici: 14, quindici: 15, sedici: 16,
      diciassette: 17, diciotto: 18, diciannove: 19, venti: 20, ventuno: 21, ventidue: 22, ventitre: 23,
      ventitré: 23, ventiquattro: 24, venticinque: 25, ventisei: 26, ventisette: 27, ventotto: 28,
      ventinove: 29, trenta: 30, trentuno: 31,
    };
    return Object.prototype.hasOwnProperty.call(numbers, key) ? numbers[key] : null;
  }

  function replaceItalianDateNumberWords(value) {
    var text = String(value || '').toLowerCase();
    text = text.replace(/\bduemila\s*([a-zàèéìòù]+)?\b/gi, function (_match, rest) {
      var parsed = italianSmallNumberWord(rest || '');
      return String(2000 + (parsed || 0));
    });
    [
      'trentuno', 'trenta', 'ventinove', 'ventotto', 'ventisette', 'ventisei', 'venticinque', 'ventiquattro',
      'ventitré', 'ventitre', 'ventidue', 'ventuno', 'venti', 'diciannove', 'diciotto', 'diciassette',
      'sedici', 'quindici', 'quattordici', 'tredici', 'dodici', 'undici', 'dieci', 'nove', 'otto',
      'sette', 'sei', 'cinque', 'quattro', 'tre', 'due', 'una', 'uno', 'primo',
    ].forEach(function (word) {
      var parsed = italianSmallNumberWord(word);
      if (parsed !== null) {
        text = replaceDictationCommand(' ' + text + ' ', [word], String(parsed)).trim();
      }
    });
    return text;
  }

  function normalizeYear(yearText) {
    var year = Number(String(yearText || '').replace(/\D/g, ''));
    if (!year) {
      return null;
    }
    if (year < 100) {
      return year >= 50 ? 1900 + year : 2000 + year;
    }
    return year;
  }

  function validItalianDateParts(day, month, year) {
    if (!day || !month || !year || month < 1 || month > 12 || day < 1) {
      return false;
    }
    var maxDay = new Date(year, month, 0).getDate();
    return day <= maxDay;
  }

  function isoDateValue(day, month, year) {
    if (!validItalianDateParts(day, month, year)) {
      return '';
    }
    return [
      String(year).padStart(4, '0'),
      String(month).padStart(2, '0'),
      String(day).padStart(2, '0'),
    ].join('-');
  }

  function relativeItalianDateValue(offsetDays) {
    var date = new Date();
    date.setHours(12, 0, 0, 0);
    date.setDate(date.getDate() + offsetDays);
    return isoDateValue(date.getDate(), date.getMonth() + 1, date.getFullYear());
  }

  function parseItalianVoiceDate(value) {
    var months = {
      gennaio: 1, febbraio: 2, marzo: 3, aprile: 4, maggio: 5, giugno: 6,
      luglio: 7, agosto: 8, settembre: 9, ottobre: 10, novembre: 11, dicembre: 12,
    };
    var text = replaceItalianDateNumberWords(value)
      .replace(/\bdel\b|\bdi\b|\bdell[' ]\b|\bil\b|\bla\b/gi, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .toLowerCase();
    if (!text) return '';
    if (/\boggi\b/.test(text)) return relativeItalianDateValue(0);
    if (/\bdopodomani\b/.test(text)) return relativeItalianDateValue(2);
    if (/\bdomani\b/.test(text)) return relativeItalianDateValue(1);

    var namedMonth = text.match(/\b(\d{1,2})\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+(\d{2,4})\b/i);
    if (namedMonth) {
      return isoDateValue(Number(namedMonth[1]), months[namedMonth[2]], normalizeYear(namedMonth[3]));
    }

    var numeric = text.match(/\b(\d{1,2})[\/.\-\s]+(\d{1,2})[\/.\-\s]+(\d{2,4})\b/);
    if (numeric) {
      return isoDateValue(Number(numeric[1]), Number(numeric[2]), normalizeYear(numeric[3]));
    }

    var compact = text.match(/\b(\d{2})(\d{2})(\d{4})\b/);
    if (compact) {
      return isoDateValue(Number(compact[1]), Number(compact[2]), normalizeYear(compact[3]));
    }
    return '';
  }

  function replaceSpokenNumberWords(value) {
    var text = String(value || '');
    [
      [['triplo zero'], '000'],
      [['doppio zero'], '00'],
      [['zero', 'zeri'], '0'],
      [['uno', 'una'], '1'],
      [['due'], '2'],
      [['tre'], '3'],
      [['quattro'], '4'],
      [['cinque'], '5'],
      [['sei'], '6'],
      [['sette'], '7'],
      [['otto'], '8'],
      [['nove'], '9'],
      [['dieci'], '10'],
      [['undici'], '11'],
      [['dodici'], '12'],
      [['tredici'], '13'],
      [['quattordici'], '14'],
      [['quindici'], '15'],
      [['sedici'], '16'],
      [['diciassette'], '17'],
      [['diciotto'], '18'],
      [['diciannove'], '19'],
      [['venti'], '20'],
      [['trenta'], '30'],
      [['quaranta'], '40'],
      [['cinquanta'], '50'],
      [['sessanta'], '60'],
      [['settanta'], '70'],
      [['ottanta'], '80'],
      [['novanta'], '90'],
      [['cento'], '100'],
    ].forEach(function (entry) {
      text = replaceDictationCommand(' ' + text + ' ', entry[0], entry[1]).trim();
    });
    return text;
  }

  function compactNumericFieldText(value) {
    return replaceSpokenNumberWords(value)
      .replace(/\s*([+])\s*/g, '$1')
      .replace(/(?<=\d)\s+(?=\d)/g, '')
      .replace(/\s*([./-])\s*(?=\d)/g, '$1')
      .replace(/(?<=\d)\s*([./-])\s*/g, '$1');
  }

  function compactDocumentCodeFieldText(value) {
    return compactNumericFieldText(value).replace(/\s+/g, '').toUpperCase();
  }

  function isDocumentNumberVoiceField(element) {
    var descriptor = targetDescriptor(element);
    return /numero[_\s-]*documento|documento[_\s-]*numero|doc[_\s-]*numero|numero[_\s-]*doc|documento/i.test(descriptor);
  }

  function isCompactNumericVoiceField(element) {
    var descriptor = targetDescriptor(element);
    var type = String(element && element.getAttribute && element.getAttribute('type') || 'text').toLowerCase();
    return type === 'tel' ||
      type === 'number' ||
      /telefono|cellulare|fax|whatsapp|mobile|cap|civico|numero[_\s-]*documento|documento[_\s-]*numero|doc[_\s-]*numero|numero[_\s-]*doc|documento|recapito/i.test(descriptor);
  }

  function normalizeFieldValueAfterDictation(element) {
    if (!element || !isTextInputElement(element)) {
      return '';
    }
    var descriptor = targetDescriptor(element);
    var type = String(element.getAttribute('type') || 'text').toLowerCase();
    if (isDateVoiceField(element)) {
      element.value = parseItalianVoiceDate(element.value) || element.value;
      return String(element.value || '');
    }
    if (type === 'email' || type === 'url' || /email|pec|mail|url|link|sito|web/i.test(descriptor)) {
      if (type === 'email' || /email|pec|mail/i.test(descriptor)) {
        element.value = normalizeEmailDictationText(element.value);
      } else if (type === 'url' || /url|link|sito|web/i.test(descriptor)) {
        element.value = normalizeUrlDictationText(element.value);
      }
      return String(element.value || '');
    }
    if (isCompactNumericVoiceField(element)) {
      element.value = isDocumentNumberVoiceField(element)
        ? compactDocumentCodeFieldText(element.value)
        : compactNumericFieldText(element.value);
      return String(element.value || '');
    }
    if (/codice[_\s-]*fiscale|codicefiscale|fiscal/i.test(descriptor)) {
      element.value = String(element.value || '').replace(/\s+/g, '').toUpperCase();
      return String(element.value || '');
    }
    element.value = uppercaseFirstFieldLetter(element.value);
    return String(element.value || '');
  }

  function isDateVoiceField(element) {
    if (!element) {
      return false;
    }
    var type = String(element.getAttribute && element.getAttribute('type') || 'text').toLowerCase();
    if (type === 'date') {
      return true;
    }
    return /\bdata\b|nascita|rilascio|scadenza|decorrenza|udienza|termine/i.test(targetDescriptor(element));
  }

  function buildTextInsertionParts(before, after, formatted) {
    var needsSpaceBefore = before && !/[\s\n([{/"']$/.test(before) && !/^[,.;:!?)]/.test(formatted);
    var needsSpaceAfter = after && !/^[\s\n,.;:!?)]/.test(after) && !/[\s\n([{/"']$/.test(formatted);
    var insertion = (needsSpaceBefore ? ' ' : '') + formatted + (needsSpaceAfter ? ' ' : '');
    var textStart = before.length + (needsSpaceBefore ? 1 : 0);
    return {
      insertion: insertion,
      cursor: before.length + insertion.length,
      textStart: textStart,
      textEnd: textStart + formatted.length,
    };
  }

  function selectInsertedText(element, start, end) {
    if (!element || !element.setSelectionRange) {
      return;
    }
    try {
      element.setSelectionRange(start, end);
    } catch (error) {
      return;
    }
    window.setTimeout(function () {
      if (document.activeElement !== element || !element.setSelectionRange) {
        return;
      }
      if (element.selectionStart === start && element.selectionEnd === end) {
        try {
          element.setSelectionRange(end, end);
        } catch (error) {
          // no-op
        }
      }
    }, 1800);
  }

  function createInlineDictationPreview(target) {
    var element = resolveActiveTextTarget(target);
    if (!element || !isTextInputElement(element) || isDateVoiceField(element)) {
      return null;
    }
    element.focus();
    var originalValue = String(element.value || '');
    var start = typeof element.selectionStart === 'number' ? element.selectionStart : originalValue.length;
    var end = typeof element.selectionEnd === 'number' ? element.selectionEnd : start;
    var before = originalValue.slice(0, start);
    var after = originalValue.slice(end);
    var active = false;

    function writePreview(text, final) {
      var formatted = textForTarget(element, text);
      if (!formatted) {
        return '';
      }
      var parts = buildTextInsertionParts(before, after, formatted);
      element.value = before + parts.insertion + after;
      normalizeFieldValueAfterDictation(element);
      element.setAttribute('data-iusentra-voice-preview', final ? 'finale' : 'ascolto');
      try {
        element.setSelectionRange(parts.textStart, parts.textEnd);
      } catch (error) {
        // no-op
      }
      dispatchInputEvents(element);
      active = true;
      return formatted;
    }

    return {
      update: function (text) {
        return writePreview(text, false);
      },
      commit: function (text) {
        var formatted = writePreview(text, true);
        element.removeAttribute('data-iusentra-voice-preview');
        if (!formatted) {
          this.clear();
          return '';
        }
        var parts = buildTextInsertionParts(before, after, formatted);
        selectInsertedText(element, parts.textStart, parts.textEnd);
        active = false;
        return formatted;
      },
      clear: function () {
        if (!active) {
          return;
        }
        element.value = originalValue;
        element.removeAttribute('data-iusentra-voice-preview');
        try {
          element.setSelectionRange(start, end);
        } catch (error) {
          // no-op
        }
        dispatchInputEvents(element);
        active = false;
      },
    };
  }

  function insertTextIntoTarget(target, text, options) {
    var element = resolveActiveTextTarget(target);
    if (isSelectVoiceElement(element)) {
      var selected = selectOptionFromVoiceText(element, text);
      if (!selected) {
        throw new Error('Non ho trovato un’opzione compatibile nel campo selezionato.');
      }
      return selected;
    }
    var formatted = textForTarget(element, text);
    if (!element) {
      throw new Error('Seleziona prima il campo in cui vuoi dettare.');
    }
    if (!formatted) {
      return '';
    }
    if (element.isContentEditable) {
      element.focus();
      try {
        document.execCommand('insertText', false, formatted);
      } catch (error) {
        element.textContent = (element.textContent || '') + formatted;
      }
      dispatchInputEvents(element);
      return formatted;
    }
    if (isTextInputElement(element)) {
      element.focus();
      if (isDateVoiceField(element)) {
        element.value = formatted;
        dispatchInputEvents(element);
        return formatted;
      }
      var start = typeof element.selectionStart === 'number' ? element.selectionStart : String(element.value || '').length;
      var end = typeof element.selectionEnd === 'number' ? element.selectionEnd : start;
      var before = String(element.value || '').slice(0, start);
      var after = String(element.value || '').slice(end);
      var parts = buildTextInsertionParts(before, after, formatted);
      var insertion = parts.insertion;
      element.value = before + insertion + after;
      normalizeFieldValueAfterDictation(element);
      if (element.setSelectionRange) {
        if (options && options.selectInserted) {
          selectInsertedText(element, parts.textStart, parts.textEnd);
        } else {
          try {
            element.setSelectionRange(parts.cursor, parts.cursor);
          } catch (error) {
            // no-op
          }
        }
      }
      dispatchInputEvents(element);
      return formatted;
    }
    throw new Error('Il campo selezionato non accetta dettatura vocale.');
  }

  function startDictationForTarget(target, options) {
    var element = resolveActiveTextTarget(target);
    var context = options || {};
    var inlinePreview = null;
    if (!element) {
      return Promise.reject(new Error('Seleziona prima il campo in cui vuoi dettare.'));
    }
    dispatchVoiceInputStatus({ state: 'checking', message: 'Controllo microfono in corso.' });
    return startListening({
      lang: context.lang || 'it-IT',
      silenceMs: context.silenceMs || 3000,
      onStart: function () {
        dispatchVoiceInputStatus({ state: 'listening', message: 'Dettatura attiva nel campo selezionato.' });
        inlinePreview = context.inlinePreview === false ? null : createInlineDictationPreview(element);
        if (typeof context.onStart === 'function') {
          context.onStart();
        }
      },
      onTranscript: function (transcript, interim) {
        if (inlinePreview && transcript) {
          inlinePreview.update(transcript);
        }
        dispatchVoiceInputStatus({
          state: interim ? 'listening' : 'captured',
          message: transcript ? 'Sto ascoltando: ' + transcript : 'Sto ascoltando.',
          transcript: transcript,
          interim: Boolean(interim),
        });
        if (typeof context.onTranscript === 'function') {
          context.onTranscript(transcript, interim);
        }
      },
    }).then(function (finalText) {
      var inserted = inlinePreview ? inlinePreview.commit(finalText) : insertTextIntoTarget(element, finalText, { selectInserted: true });
      dispatchVoiceInputStatus({
        state: inserted ? 'inserted' : 'empty',
        message: inserted ? 'Testo inserito nel campo selezionato.' : 'Nessun testo vocale rilevato.',
        transcript: inserted,
      });
      if (typeof context.onInserted === 'function') {
        context.onInserted(inserted);
      }
      return inserted;
    }).catch(function (error) {
      if (inlinePreview) {
        inlinePreview.clear();
      }
      dispatchVoiceInputStatus({
        state: 'error',
        message: String((error && error.message) || 'Dettatura non disponibile.'),
      });
      throw error;
    });
  }

  function startDictationForActiveField(options) {
    return startDictationForTarget(document.activeElement, options || {});
  }

  function getMicrophoneStatus() {
    return {
      state: microphonePermissionState,
      granted: microphonePreflightGranted || microphonePermissionState === 'granted',
      supportsRecognition: supportsRecognition(),
    };
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

  if (window.document && window.document.addEventListener) {
    window.document.addEventListener('focusin', rememberVoiceInputTarget, true);
    window.document.addEventListener('pointerdown', rememberVoiceInputTarget, true);
    window.document.addEventListener('keyup', rememberVoiceInputTarget, true);
  }

  window.PctLexVoice = {
    cancelSpeech: cancelSpeech,
    canAttachVoiceInput: canAttachVoiceInput,
    formatDictationText: formatDictationText,
    getMicrophoneStatus: getMicrophoneStatus,
    insertTextIntoTarget: insertTextIntoTarget,
    speak: speak,
    startDictationForActiveField: startDictationForActiveField,
    startDictationForTarget: startDictationForTarget,
    startListening: startListening,
    stopListening: stopListening,
    supportsRecognition: supportsRecognition,
    supportsSpeech: supportsSpeech,
    supportsNeuralSpeech: supportsNeuralSpeech,
    preloadSpeechEngine: preloadSpeechEngine,
    verifyMicrophoneAccess: verifyMicrophoneAccess,
    getSpeechEngineStatus: getSpeechEngineStatus,
  };
  window.IusentraVoiceInput = {
    canAttach: canAttachVoiceInput,
    formatDictationText: formatDictationText,
    getMicrophoneStatus: getMicrophoneStatus,
    insertTextIntoTarget: insertTextIntoTarget,
    startForActiveField: startDictationForActiveField,
    startForTarget: startDictationForTarget,
    stop: stopListening,
    verifyMicrophoneAccess: verifyMicrophoneAccess,
  };
})();
