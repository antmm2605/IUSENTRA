(function () {
  'use strict';

  var STORAGE_FALLBACK = 'hacs-pct-ai-layout-v1';
  var DESKTOP_MEDIA = '(min-width: 992px)';
  var DRAG_MARGIN = 12;
  var MIN_WIDGET_WIDTH = 368;
  var MIN_WIDGET_HEIGHT = 520;
  var MAX_WIDGET_WIDTH = 720;
  var MAX_WIDGET_HEIGHT = 860;
  var state = {
    open: false,
    streaming: false,
    history: [],
    attachments: [],
    fascId: null,
    currentBubble: null,
    drag: null,
    resize: null,
    listening: false,
    voiceReplyEnabled: true,
  };

  var widget;
  var panel;
  var fab;
  var input;
  var sendButton;
  var statusBar;
  var messages;
  var ctx;
  var ctxLabel;
  var badge;
  var voiceBadge;
  var uploadInput;
  var attachmentsShelf;
  var exportButton;
  var micButton;
  var voiceToggleButton;
  var resizeHandle;
  var storageKey = STORAGE_FALLBACK;
  var dragHandle;
  var bridgeConfig = null;

  function query(id) {
    return document.getElementById(id);
  }

  function isDesktop() {
    return window.matchMedia(DESKTOP_MEDIA).matches;
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function renderMarkdown(text) {
    if (!text) {
      return '';
    }

    var html = String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    html = html.replace(/`([^`\n]+)`/g, '<code>$1</code>');
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/^([*\-]\s.+)$/gm, '<li>$1</li>');
    html = html.replace(/^(\d+\.\s.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>[\s\S]*?<\/li>)(\s*<li>[\s\S]*?<\/li>)*/g, '<ul>$&</ul>');

    return html
      .split(/\n\n+/)
      .map(function (part) {
        var trimmed = part.trim();
        if (!trimmed) {
          return '';
        }
        if (trimmed.indexOf('<ul>') === 0 || trimmed.indexOf('<pre>') === 0) {
          return trimmed;
        }
        return '<p>' + trimmed.replace(/\n/g, '<br>') + '</p>';
      })
      .join('');
  }

  function setStatus(message) {
    if (statusBar) {
      statusBar.textContent = message || '';
    }
  }

  function browserBridge() {
    return window.HacsLocalAiBrowserBridge || null;
  }

  function documentsHelper() {
    return window.PctLexDocuments || null;
  }

  function voiceHelper() {
    return window.PctLexVoice || null;
  }

  function scrollBottom() {
    if (messages) {
      messages.scrollTop = messages.scrollHeight;
    }
  }

  function appendMessage(role, content) {
    if (!messages) {
      return null;
    }

    var wrap = document.createElement('div');
    var avatarIcon = role === 'user' ? 'person-fill' : 'stars';
    var avatarClass = role === 'user' ? 'pct-ai-avatar--user' : 'pct-ai-avatar--ai';
    wrap.className = 'pct-ai-msg pct-ai-msg--' + role;
    wrap.innerHTML =
      '<div class="pct-ai-avatar ' + avatarClass + '"><i class="bi bi-' + avatarIcon + '"></i></div>' +
      '<div class="pct-ai-bubble">' + (content ? renderMarkdown(content) : '<span class="pct-ai-cursor">...</span>') + '</div>';

    messages.appendChild(wrap);
    scrollBottom();
    return wrap.querySelector('.pct-ai-bubble');
  }

  function setBubbleContent(element, content) {
    if (element) {
      element.innerHTML = content ? renderMarkdown(content) : '<span class="pct-ai-cursor">...</span>';
    }
  }

  function setBubbleHtml(element, html) {
    if (element) {
      element.innerHTML = html || '';
    }
  }

  function renderSources(payload) {
    var citations = Array.isArray(payload && payload.citations) ? payload.citations.filter(Boolean) : [];
    if (!citations.length) {
      return '';
    }
    return (
      '<div class="pct-ai-sources mt-3">' +
        '<div class="fw-semibold small mb-1">Fonti</div>' +
        '<ul class="small mb-0">' +
          citations.map(function (item) { return '<li>' + escapeHtml(item) + '</li>'; }).join('') +
        '</ul>' +
      '</div>'
    );
  }

  function voicePreferenceKey() {
    return storageKey + ':prefs';
  }

  function loadVoicePreference() {
    try {
      var raw = window.localStorage.getItem(voicePreferenceKey());
      if (!raw) {
        return null;
      }
      return JSON.parse(raw);
    } catch (error) {
      return null;
    }
  }

  function saveVoicePreference() {
    try {
      window.localStorage.setItem(
        voicePreferenceKey(),
        JSON.stringify({ voiceReplyEnabled: state.voiceReplyEnabled })
      );
    } catch (error) {
      return;
    }
  }

  function updateVoiceUi() {
    var voice = voiceHelper();
    var speechSupported = Boolean(voice && voice.supportsSpeech && voice.supportsSpeech());
    var recognitionSupported = Boolean(voice && voice.supportsRecognition && voice.supportsRecognition());

    if (voiceToggleButton) {
      voiceToggleButton.classList.toggle('is-active', state.voiceReplyEnabled && speechSupported);
      voiceToggleButton.disabled = !speechSupported;
      voiceToggleButton.innerHTML = '<i class="bi bi-' + (state.voiceReplyEnabled ? 'volume-up-fill' : 'volume-mute-fill') + '"></i>';
    }

    if (micButton) {
      micButton.disabled = !recognitionSupported;
      micButton.classList.toggle('is-active', state.listening);
      micButton.innerHTML =
        '<i class="bi bi-' + (state.listening ? 'mic-mute-fill' : 'mic-fill') + '"></i>' +
        '<span>' + (state.listening ? 'Ascolto…' : 'Detta') + '</span>';
    }

    if (voiceBadge) {
      if (state.listening && recognitionSupported) {
        voiceBadge.textContent = 'Ascolto attivo';
        voiceBadge.classList.add('is-online');
        voiceBadge.classList.remove('is-offline');
      } else if (speechSupported || recognitionSupported) {
        voiceBadge.textContent = state.voiceReplyEnabled ? 'Voce attiva' : 'Voce pronta';
        voiceBadge.classList.toggle('is-online', state.voiceReplyEnabled);
        voiceBadge.classList.toggle('is-offline', !state.voiceReplyEnabled);
      } else {
        voiceBadge.textContent = 'Voce non supportata';
        voiceBadge.classList.add('is-offline');
        voiceBadge.classList.remove('is-online');
      }
    }
  }

  function sanitizeSpeechText(value) {
    return String(value || '')
      .replace(/```[\s\S]*?```/g, ' ')
      .replace(/`([^`]+)`/g, '$1')
      .replace(/\*\*(.*?)\*\*/g, '$1')
      .replace(/[_#>*-]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function speakAnswer(value) {
    var voice = voiceHelper();
    if (!state.voiceReplyEnabled || !voice || !voice.supportsSpeech || !voice.supportsSpeech()) {
      return;
    }
    var clean = sanitizeSpeechText(value);
    if (!clean) {
      return;
    }
    voice.speak(clean, { lang: 'it-IT', rate: 1 });
  }

  function renderCompanionHelp(outdated) {
    if (!browserBridge() || !bridgeConfig) {
      return '<div class="text-danger">Companion locale non raggiungibile su questo dispositivo.</div>';
    }
    var help = browserBridge().companionHelp(bridgeConfig, { outdated: outdated });
    return (
      '<div class="text-danger fw-semibold mb-2">' + escapeHtml(help.title || 'Companion locale non disponibile') + '</div>' +
      '<div class="small text-muted">' + escapeHtml(help.body || '') + '</div>' +
      (help.actionUrl
        ? '<div class="mt-3"><a class="btn btn-sm btn-outline-primary" href="' + escapeHtml(help.actionUrl) + '" target="_blank" rel="noreferrer">' +
            '<i class="bi bi-box-arrow-up-right me-2"></i>' + escapeHtml(help.actionLabel || 'Apri istruzioni') +
          '</a></div>'
        : '')
    );
  }

  function isCompanionTransportError(error) {
    var message = String((error && error.message) || '').toLowerCase();
    var status = Number(error && error.httpStatus || 0);
    if (!status) {
      return true;
    }
    return (
      message.indexOf('failed to fetch') >= 0 ||
      message.indexOf('networkerror') >= 0 ||
      message.indexOf('load failed') >= 0 ||
      message.indexOf('network request failed') >= 0
    );
  }

  function renderCompanionRuntimeHelp(error) {
    var message = escapeHtml((error && error.message) || 'Il companion locale ha rifiutato la richiesta AI.');
    return (
      '<div class="text-warning fw-semibold mb-2">Companion locale raggiunto, ma la richiesta non e\' andata a buon fine</div>' +
      '<div class="small text-muted">Lex e\' riuscito a contattare il Local Signer su questo dispositivo, ma il modulo AI locale ha restituito un errore operativo.</div>' +
      '<div class="small mt-2"><code>' + message + '</code></div>'
    );
  }

  function renderServerPreparationHelp(error) {
    var authProblem = Number(error && error.httpStatus || 0) === 401 || Number(error && error.httpStatus || 0) === 403;
    var message = escapeHtml((error && error.message) || 'Il server HACS non e\' riuscito a preparare il contesto della richiesta.');
    return (
      '<div class="text-danger fw-semibold mb-2">' + (authProblem ? 'Sessione scaduta o non autorizzata' : 'Preparazione richiesta non riuscita') + '</div>' +
      '<div class="small text-muted">' + (
        authProblem
          ? 'Ricarica la pagina ed effettua nuovamente l\'accesso a HACS prima di chiedere una risposta a Lex.'
          : 'Lex non e\' riuscito a preparare il contesto sul server HACS prima di interrogare il companion locale.'
      ) + '</div>' +
      '<div class="small mt-2"><code>' + message + '</code></div>'
    );
  }

  function setAnswerPayload(element, payload) {
    var answer = payload && payload.answer ? renderMarkdown(payload.answer) : '<p>Nessuna risposta disponibile.</p>';
    setBubbleHtml(element, answer + renderSources(payload || {}));
  }

  function defaultIntroMarkup() {
    return (
      '<div class="pct-ai-msg pct-ai-msg--assistant">' +
        '<div class="pct-ai-avatar pct-ai-avatar--ai"><i class="bi bi-stars"></i></div>' +
        '<div class="pct-ai-bubble">' +
          '<p>Ciao, sono <strong>Lex</strong>. Ti supporto su fascicoli, clienti, agenda, scadenziario, deposito telematico, firma digitale, PEC e moduli operativi dello studio.</p>' +
          '<ul>' +
            '<li>Suggerimenti su PCT, PDP, PAT, firma digitale, PEC e PDF/A</li>' +
            '<li>Supporto consultivo su clienti, agenda, scadenziario, soggetti e fascicoli</li>' +
            '<li>Contesto operativo su template atti, tariffario, preventivi, fatturazione e applicazioni</li>' +
            '<li>Piste di ricerca legale con archivio sentenze e fonti ufficiali web</li>' +
          '</ul>' +
          '<p>Lex resta sempre consultivo: suggerisce controlli, rischi e prossimi passi, ma non prende decisioni al posto del professionista.</p>' +
          '<p>Se HACS e\' online, Lex usa il companion locale di questo dispositivo per parlare con Ollama in modo sicuro e non bloccante.</p>' +
          '<p>Puoi caricare documenti, dettare la richiesta con la voce e scaricare il riepilogo operativo della conversazione.</p>' +
          '<p class="mb-0">Se il pannello ti intralcia, trascinalo o ridimensionalo: posizione e dimensioni restano salvate su questo browser.</p>' +
        '</div>' +
      '</div>'
    );
  }

  function clearHistory() {
    state.history = [];
    state.currentBubble = null;
    state.attachments = [];
    if (messages) {
      messages.innerHTML = defaultIntroMarkup();
    }
    renderAttachments();
    setStatus('Conversazione pronta.');
  }

  function renderAttachments() {
    var docs = documentsHelper();
    if (!docs || !attachmentsShelf) {
      return;
    }
    docs.renderAttachmentShelf(attachmentsShelf, state.attachments);
  }

  function removeAttachment(attachmentId) {
    state.attachments = state.attachments.filter(function (item) {
      return String(item.id || '') !== String(attachmentId || '');
    });
    renderAttachments();
    setStatus(state.attachments.length ? 'Documento rimosso dal contesto di Lex.' : 'Nessun documento caricato al momento.');
  }

  function handleAttachmentParseResult(payload) {
    var parsed = Array.isArray(payload && payload.attachments) ? payload.attachments : [];
    var errors = Array.isArray(payload && payload.errors) ? payload.errors : [];
    state.attachments = state.attachments.concat(parsed).slice(0, 4);
    renderAttachments();
    if (errors.length && parsed.length) {
      setStatus(parsed.length + ' documenti pronti, con ' + errors.length + ' file da verificare.');
    } else if (errors.length) {
      setStatus('Lex non ha potuto leggere ' + errors.length + ' documento/i.');
    } else {
      setStatus(parsed.length + ' documento/i pronti nel contesto di Lex.');
    }
  }

  function handleUpload(event) {
    var docs = documentsHelper();
    var bridge = browserBridge();
    if (!docs || !bridge || !bridgeConfig) {
      setStatus('Parser documentale non disponibile in questo momento.');
      return;
    }

    var slots = Math.max(0, 4 - state.attachments.length);
    var files = Array.prototype.slice.call((event && event.target && event.target.files) || []).slice(0, slots);
    if (!files.length) {
      if (slots <= 0) {
        setStatus('Puoi tenere al massimo 4 documenti contemporaneamente nel contesto di Lex.');
      }
      return;
    }

    setStatus('Lex sta leggendo i documenti caricati...');
    docs.parseAttachments({
      files: files,
      remoteHosted: Boolean(bridgeConfig && bridgeConfig.remoteHosted),
      bridge: bridge,
      config: bridgeConfig,
    })
      .then(handleAttachmentParseResult)
      .catch(function (error) {
        setStatus('Caricamento documenti non riuscito: ' + String((error && error.message) || 'errore sconosciuto'));
      })
      .finally(function () {
        if (uploadInput) {
          uploadInput.value = '';
        }
      });
  }

  function autoResize() {
    if (!input) {
      return;
    }
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 132) + 'px';
  }

  function setOpen(nextOpen) {
    state.open = Boolean(nextOpen);
    if (!panel || !fab || !widget) {
      return;
    }

    panel.hidden = !state.open;
    fab.classList.toggle('pct-ai-fab--active', state.open);
    widget.classList.toggle('pct-ai-widget--open', state.open);

    if (state.open) {
      window.requestAnimationFrame(function () {
        if (input) {
          input.focus();
          autoResize();
        }
        scrollBottom();
      });
    }
  }

  function toggle() {
    setOpen(!state.open);
  }

  function finalizeRequest(message) {
    state.streaming = false;
    if (sendButton) {
      sendButton.disabled = false;
    }
    setStatus(message || 'Assistente pronto.');
    scrollBottom();
  }

  function payloadBase() {
    return {
      messages: state.history.slice(-20),
      fascicolo_id: state.fascId || '',
    };
  }

  function sendLocal(text) {
    fetch(widget.dataset.chatUrl || '/api/assistente/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: state.history.slice(-20),
        fascicolo_id: state.fascId || '',
        attachments: state.attachments.slice(),
      }),
    }).then(function (response) {
      if (!response.body) {
        throw new Error('Il browser non supporta lo streaming della risposta.');
      }

      var reader = response.body.getReader();
      var decoder = new TextDecoder();
      var buffer = '';
      var full = '';

      function readChunk() {
        return reader.read().then(function (result) {
          if (result.done) {
            state.history.push({ role: 'assistant', content: full });
            speakAnswer(full);
            finalizeRequest();
            return;
          }

          buffer += decoder.decode(result.value, { stream: true });
          var lines = buffer.split('\n');
          buffer = lines.pop();

          lines.forEach(function (line) {
            if (line.indexOf('data: ') !== 0) {
              return;
            }

            var raw = line.slice(6).trim();
              if (raw === '[DONE]') {
                state.history.push({ role: 'assistant', content: full });
                speakAnswer(full);
                finalizeRequest();
                return;
              }

            try {
              var data = JSON.parse(raw);
              if (data.errore) {
                setBubbleContent(state.currentBubble, 'Attenzione: ' + data.errore);
                state.history.push({ role: 'assistant', content: data.errore });
                finalizeRequest();
                return;
              }
              if (data.token) {
                full += data.token;
                setBubbleContent(state.currentBubble, full);
                scrollBottom();
              }
            } catch (error) {
              setBubbleContent(state.currentBubble, 'Risposta non leggibile ricevuta dal servizio.');
              finalizeRequest('Assistente momentaneamente non disponibile.');
            }
          });

          if (state.streaming) {
            return readChunk();
          }

          return null;
        });
      }

      return readChunk();
    }).catch(function (error) {
      setBubbleContent(state.currentBubble, 'Errore di connessione: ' + escapeHtml(error.message));
      finalizeRequest('Connessione al runtime non riuscita.');
    });
  }

  function sendViaCompanion(text) {
    if (!browserBridge() || !bridgeConfig) {
      setBubbleContent(state.currentBubble, 'Il bridge AI locale non e\' disponibile su questo browser.');
      finalizeRequest('Bridge AI locale non disponibile.');
      return;
    }

    setStatus('Lex sta interrogando il companion locale del dispositivo...');
    browserBridge()
      .fetchServerContext(bridgeConfig, {
        question: text,
        messages: state.history.slice(-20),
        fascicolo_id: state.fascId || '',
      })
      .then(function (prepared) {
        var docs = documentsHelper();
        var docsBlock = docs ? docs.buildPromptBlock(state.attachments) : '';
        if (docsBlock) {
          prepared.prompt = String(prepared.prompt || '').trim() + '\n\n' + docsBlock;
        }
        var partial = '';
        return browserBridge()
          .streamCompanionRagQuery(bridgeConfig, prepared, {
            onToken: function (token) {
              partial += String(token || '');
              setStatus('Lex sta scrivendo dal dispositivo locale...');
              setBubbleContent(state.currentBubble, partial);
              scrollBottom();
            },
          })
          .catch(function (error) {
            error = error || new Error('Companion locale non raggiungibile.');
            error.__companionStage = true;
            error.__partialAnswer = partial;
            throw error;
          });
      })
      .then(function (payload) {
        if (!payload.answer && state.currentBubble) {
          payload.answer = state.currentBubble.textContent || '';
        }
        setAnswerPayload(state.currentBubble, payload);
        state.history.push({ role: 'assistant', content: String(payload.answer || '').trim() });
        speakAnswer(payload.answer || '');
        checkStatus();
        finalizeRequest('Risposta generata sul dispositivo locale.');
      })
      .catch(function (error) {
        if (!error || !error.__companionStage) {
          setBubbleHtml(state.currentBubble, renderServerPreparationHelp(error));
          finalizeRequest(
            Number(error && error.httpStatus || 0) === 401 || Number(error && error.httpStatus || 0) === 403
              ? 'Sessione HACS da rinnovare.'
              : 'Preparazione della richiesta non riuscita.'
          );
          return;
        }
        var outdated = Number(error && error.httpStatus || 0) === 404;
        if (outdated) {
          setBubbleHtml(state.currentBubble, renderCompanionHelp(true));
          finalizeRequest('Aggiornamento del companion locale richiesto.');
          return;
        }
        if (isCompanionTransportError(error)) {
          if (!bridgeConfig.remoteHosted) {
            setStatus('Companion locale non raggiungibile, attivo fallback sul runtime locale di HACS...');
            sendLocal(text);
            return;
          }
          setBubbleHtml(state.currentBubble, renderCompanionHelp(false));
          finalizeRequest('Companion locale non raggiungibile.');
          return;
        }
        if (error && error.__partialAnswer) {
          setBubbleHtml(
            state.currentBubble,
            renderMarkdown(error.__partialAnswer) +
              '<div class="small text-warning mt-3">La risposta si e\' interrotta prima del completamento.</div>' +
              '<div class="small mt-2"><code>' + escapeHtml((error && error.message) || 'Errore operativo del modulo AI locale.') + '</code></div>'
          );
          state.history.push({ role: 'assistant', content: String(error.__partialAnswer || '').trim() });
          finalizeRequest('Risposta interrotta dal companion locale.');
          return;
        }
        setBubbleHtml(state.currentBubble, renderCompanionRuntimeHelp(error));
        finalizeRequest('Companion locale raggiunto, ma la richiesta non e\' andata a buon fine.');
      });
  }

  function send() {
    if (state.streaming || !input) {
      return;
    }

    var text = String(input.value || '').trim();
    if (!text) {
      return;
    }

    input.value = '';
    autoResize();
    if (voiceHelper()) {
      voiceHelper().cancelSpeech();
    }

    state.history.push({ role: 'user', content: text });
    appendMessage('user', text);

    state.streaming = true;
    if (sendButton) {
      sendButton.disabled = true;
    }

    state.currentBubble = appendMessage('assistant', '');

    if (bridgeConfig) {
      sendViaCompanion(text);
      return;
    }

    setStatus('Lex sta preparando la risposta...');
    sendLocal(text);
  }

  function updateBadge(ok, label) {
    if (!badge) {
      return;
    }

    badge.textContent = label;
    badge.classList.toggle('is-offline', !ok);
    badge.classList.toggle('is-online', ok);
  }

  function checkRemoteStatus() {
    if (!browserBridge() || !bridgeConfig) {
      updateBadge(false, 'Bridge assente');
      setStatus('Bridge AI locale non disponibile sul browser corrente.');
      return;
    }

    browserBridge()
      .fetchRuntimeStatus(bridgeConfig)
      .then(function (data) {
        var runtime = data.runtime || {};
        var ready = Boolean(data.runtime_online || runtime.status === 'ready');
        var modelLabel = (data.resolved_models && data.resolved_models.chat) || 'Companion locale';
        updateBadge(ready, ready ? modelLabel : 'Companion offline');
        setStatus(
          ready
            ? 'Lex e\' collegato al companion locale di questo dispositivo.'
            : 'Il companion locale non e\' ancora operativo su questo dispositivo.'
        );
      })
      .catch(function () {
        browserBridge()
          .fetchCompanionPing(bridgeConfig)
          .then(function () {
            updateBadge(false, 'AI locale non pronta');
            setStatus('Local Signer raggiungibile, ma il modulo AI locale non e\' operativo su questo dispositivo.');
          })
          .catch(function () {
            updateBadge(false, 'Companion offline');
            setStatus('Il browser non riesce a raggiungere il companion locale su questo dispositivo.');
          });
      });
  }

  function checkStatus() {
    bridgeConfig = browserBridge() && widget ? browserBridge().rootConfig(widget) : null;
    if (bridgeConfig && bridgeConfig.remoteHosted) {
      checkRemoteStatus();
      return;
    }

    fetch(widget.dataset.statusUrl || '/api/assistente/stato')
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (data.ok) {
          updateBadge(true, data.modello_attivo || 'Operativo');
          setStatus('Lex e\' pronto sul runtime locale di HACS.');
        } else {
          updateBadge(false, 'Offline');
          setStatus('Runtime locale non disponibile su questa installazione.');
        }
      })
      .catch(function () {
        updateBadge(false, 'Offline');
        setStatus('Stato del runtime non disponibile in questo momento.');
      });
  }

  function getSavedLayout() {
    try {
      var raw = window.localStorage.getItem(storageKey);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      return null;
    }
  }

  function saveLayout(layoutPatch) {
    try {
      var current = getSavedLayout() || {};
      window.localStorage.setItem(storageKey, JSON.stringify(Object.assign({}, current, layoutPatch || {})));
    } catch (error) {
      return;
    }
  }

  function clearSavedPosition() {
    try {
      window.localStorage.removeItem(storageKey);
    } catch (error) {
      return;
    }
  }

  function applyCustomLayout(layout) {
    if (!widget || !layout || !isDesktop()) {
      return;
    }

    var targetWidth = clamp(Number(layout.width || widget.offsetWidth || 392), MIN_WIDGET_WIDTH, Math.min(MAX_WIDGET_WIDTH, window.innerWidth - DRAG_MARGIN * 2));
    var targetHeight = clamp(Number(layout.height || widget.offsetHeight || 640), MIN_WIDGET_HEIGHT, Math.min(MAX_WIDGET_HEIGHT, window.innerHeight - DRAG_MARGIN * 2));
    widget.style.width = targetWidth + 'px';
    widget.style.height = targetHeight + 'px';

    var width = targetWidth;
    var height = targetHeight;
    var maxLeft = Math.max(DRAG_MARGIN, window.innerWidth - width - DRAG_MARGIN);
    var maxTop = Math.max(DRAG_MARGIN, window.innerHeight - height - DRAG_MARGIN);
    var left = clamp(Number(layout.left || 0), DRAG_MARGIN, maxLeft);
    var top = clamp(Number(layout.top || 0), DRAG_MARGIN, maxTop);

    widget.classList.add('pct-ai-widget--custom');
    widget.style.left = left + 'px';
    widget.style.top = top + 'px';
    widget.style.right = 'auto';
    widget.style.bottom = 'auto';
  }

  function resetPosition() {
    if (!widget) {
      return;
    }

    clearSavedPosition();
    widget.classList.remove('pct-ai-widget--custom');
    widget.style.left = '';
    widget.style.top = '';
    widget.style.right = '';
    widget.style.bottom = '';
    widget.style.width = '';
    widget.style.height = '';
    setStatus('Posizione e dimensioni ripristinate in basso a destra.');
  }

  function restorePosition() {
    if (!widget) {
      return;
    }

    if (!isDesktop()) {
      resetPosition();
      return;
    }

    var saved = getSavedLayout();
    if (saved) {
      applyCustomLayout(saved);
    }
  }

  function handlePointerMove(event) {
    if (!state.drag || !widget) {
      return;
    }

    var width = widget.offsetWidth || 392;
    var height = widget.offsetHeight || 640;
    var nextLeft = clamp(event.clientX - state.drag.offsetX, DRAG_MARGIN, Math.max(DRAG_MARGIN, window.innerWidth - width - DRAG_MARGIN));
    var nextTop = clamp(event.clientY - state.drag.offsetY, DRAG_MARGIN, Math.max(DRAG_MARGIN, window.innerHeight - height - DRAG_MARGIN));

    widget.classList.add('pct-ai-widget--custom', 'pct-ai-widget--dragging');
    widget.style.left = nextLeft + 'px';
    widget.style.top = nextTop + 'px';
    widget.style.right = 'auto';
    widget.style.bottom = 'auto';
    state.drag.moved = true;
  }

  function endDrag() {
    if (!state.drag || !widget) {
      return;
    }

    widget.classList.remove('pct-ai-widget--dragging');
    if (state.drag.moved) {
      saveLayout({
        left: parseFloat(widget.style.left || '0'),
        top: parseFloat(widget.style.top || '0'),
      });
      setStatus('Posizione aggiornata sul browser corrente.');
    }

    window.removeEventListener('pointermove', handlePointerMove);
    window.removeEventListener('pointerup', endDrag);
    window.removeEventListener('pointercancel', endDrag);
    document.body.classList.remove('pct-ai-no-select');
    state.drag = null;
  }

  function startDrag(event) {
    if (!isDesktop() || !widget || event.button !== 0) {
      return;
    }

    var interactiveTarget = event.target.closest('button, textarea, a, input');
    if (interactiveTarget && !interactiveTarget.hasAttribute('data-pct-ai-drag-handle')) {
      return;
    }

    var rect = widget.getBoundingClientRect();
    widget.classList.add('pct-ai-widget--custom');
    widget.style.left = rect.left + 'px';
    widget.style.top = rect.top + 'px';
    widget.style.right = 'auto';
    widget.style.bottom = 'auto';

    state.drag = {
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
      moved: false,
    };

    document.body.classList.add('pct-ai-no-select');
    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', endDrag);
    window.addEventListener('pointercancel', endDrag);
  }

  function handleResizeMove(event) {
    if (!state.resize || !widget) {
      return;
    }
    var nextWidth = clamp(
      state.resize.startWidth + (event.clientX - state.resize.startX),
      MIN_WIDGET_WIDTH,
      Math.min(MAX_WIDGET_WIDTH, window.innerWidth - DRAG_MARGIN * 2)
    );
    var nextHeight = clamp(
      state.resize.startHeight + (event.clientY - state.resize.startY),
      MIN_WIDGET_HEIGHT,
      Math.min(MAX_WIDGET_HEIGHT, window.innerHeight - DRAG_MARGIN * 2)
    );
    widget.classList.add('pct-ai-widget--custom', 'pct-ai-widget--dragging');
    widget.style.width = nextWidth + 'px';
    widget.style.height = nextHeight + 'px';
    state.resize.moved = true;
  }

  function endResize() {
    if (!state.resize || !widget) {
      return;
    }
    widget.classList.remove('pct-ai-widget--dragging');
    if (state.resize.moved) {
      saveLayout({
        width: parseFloat(widget.style.width || '0'),
        height: parseFloat(widget.style.height || '0'),
        left: parseFloat(widget.style.left || '0') || undefined,
        top: parseFloat(widget.style.top || '0') || undefined,
      });
      setStatus('Dimensioni di Lex aggiornate sul browser corrente.');
    }
    window.removeEventListener('pointermove', handleResizeMove);
    window.removeEventListener('pointerup', endResize);
    window.removeEventListener('pointercancel', endResize);
    document.body.classList.remove('pct-ai-no-select');
    state.resize = null;
  }

  function startResize(event) {
    if (!isDesktop() || !widget || event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    var rect = widget.getBoundingClientRect();
    widget.classList.add('pct-ai-widget--custom');
    widget.style.left = rect.left + 'px';
    widget.style.top = rect.top + 'px';
    widget.style.right = 'auto';
    widget.style.bottom = 'auto';
    state.resize = {
      startX: event.clientX,
      startY: event.clientY,
      startWidth: widget.offsetWidth || MIN_WIDGET_WIDTH,
      startHeight: widget.offsetHeight || MIN_WIDGET_HEIGHT,
      moved: false,
    };
    document.body.classList.add('pct-ai-no-select');
    window.addEventListener('pointermove', handleResizeMove);
    window.addEventListener('pointerup', endResize);
    window.addEventListener('pointercancel', endResize);
  }

  function bindEvents() {
    fab.addEventListener('click', toggle);
    sendButton.addEventListener('click', send);
    query('pct-ai-close').addEventListener('click', function () { setOpen(false); });
    query('pct-ai-clear').addEventListener('click', clearHistory);
    query('pct-ai-reset-position').addEventListener('click', resetPosition);
    if (exportButton) {
      exportButton.addEventListener('click', function () {
        var docs = documentsHelper();
        if (!docs) {
          return;
        }
        docs.triggerDownload({
          history: state.history,
          attachments: state.attachments,
          contextLabel: ctx && !ctx.hidden && ctxLabel ? ctxLabel.textContent : '',
        });
        setStatus('Riepilogo conversazione scaricato.');
      });
    }
    if (uploadInput) {
      uploadInput.addEventListener('change', handleUpload);
    }
    if (attachmentsShelf && documentsHelper()) {
      documentsHelper().bindShelfRemoval(attachmentsShelf, removeAttachment);
    }
    if (voiceToggleButton) {
      voiceToggleButton.addEventListener('click', function () {
        state.voiceReplyEnabled = !state.voiceReplyEnabled;
        if (!state.voiceReplyEnabled && voiceHelper()) {
          voiceHelper().cancelSpeech();
        }
        saveVoicePreference();
        updateVoiceUi();
        setStatus(state.voiceReplyEnabled ? 'Risposta vocale attivata.' : 'Risposta vocale disattivata.');
      });
    }
    if (micButton) {
      micButton.addEventListener('click', function () {
        var voice = voiceHelper();
        if (!voice || !voice.supportsRecognition || !voice.supportsRecognition()) {
          setStatus('Dettatura vocale non disponibile su questo browser.');
          return;
        }
        if (state.listening) {
          voice.stopListening();
          state.listening = false;
          updateVoiceUi();
          setStatus('Dettatura interrotta.');
          return;
        }
        state.listening = true;
        updateVoiceUi();
        setStatus('Lex sta ascoltando la tua richiesta...');
        voice.startListening({
          lang: 'it-IT',
          onTranscript: function (transcript) {
            if (input) {
              input.value = transcript || '';
              autoResize();
            }
          },
        }).then(function (finalText) {
          state.listening = false;
          updateVoiceUi();
          if (finalText && input) {
            input.value = finalText;
            autoResize();
            send();
          } else {
            setStatus('Nessun testo vocale rilevato.');
          }
        }).catch(function (error) {
          state.listening = false;
          updateVoiceUi();
          setStatus(String((error && error.message) || 'Riconoscimento vocale non disponibile.'));
        });
      });
    }

    input.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        send();
      }
    });
    input.addEventListener('input', autoResize);

    if (dragHandle) {
      dragHandle.addEventListener('pointerdown', startDrag);
    }
    if (resizeHandle) {
      resizeHandle.addEventListener('pointerdown', startResize);
    }

    window.addEventListener('resize', function () {
      if (isDesktop()) {
        restorePosition();
      } else {
        resetPosition();
      }
    });
  }

  function initContext() {
    var match = window.location.pathname.match(/\/fascicoli\/([^/]+)/);
    state.fascId = (match && match[1]) || window.pctAiFascicoloId || null;
    if (state.fascId && ctx && ctxLabel) {
      ctx.hidden = false;
      ctxLabel.textContent = 'Contesto fascicolo attivo';
    }
  }

  function init() {
    widget = query('pct-ai-widget');
    panel = query('pct-ai-panel');
    fab = query('pct-ai-fab');
    input = query('pct-ai-input');
    sendButton = query('pct-ai-send');
    statusBar = query('pct-ai-status');
    messages = query('pct-ai-messages');
    ctx = query('pct-ai-ctx');
    ctxLabel = query('pct-ai-ctx-label');
    badge = query('pct-ai-model-badge');
    voiceBadge = query('pct-ai-voice-badge');
    uploadInput = query('pct-ai-upload');
    attachmentsShelf = query('pct-ai-attachments');
    exportButton = query('pct-ai-export');
    micButton = query('pct-ai-mic');
    voiceToggleButton = query('pct-ai-voice-toggle');
    resizeHandle = query('pct-ai-resize-handle');
    dragHandle = query('pct-ai-header');

    if (!widget || !panel || !fab || !input || !sendButton) {
      return;
    }

    storageKey = widget.dataset.storageKey || STORAGE_FALLBACK;
    bridgeConfig = browserBridge() ? browserBridge().rootConfig(widget) : null;
    var prefs = loadVoicePreference();
    if (prefs && typeof prefs.voiceReplyEnabled === 'boolean') {
      state.voiceReplyEnabled = prefs.voiceReplyEnabled;
    }

    bindEvents();
    initContext();
    restorePosition();
    clearHistory();
    updateVoiceUi();
    checkStatus();
  }

  window.pctAI = {
    init: init,
    toggle: toggle,
    send: send,
    clearHistory: clearHistory,
    resetPosition: resetPosition,
  };

  document.addEventListener('DOMContentLoaded', init);
})();
