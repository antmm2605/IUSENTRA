(function () {
  'use strict';

  var STORAGE_FALLBACK = 'hacs-pct-ai-layout-v1';
  var DESKTOP_MEDIA = '(min-width: 992px)';
  var DRAG_MARGIN = 12;
  var state = {
    open: false,
    streaming: false,
    history: [],
    fascId: null,
    currentBubble: null,
    drag: null,
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
          '<p>Ciao, sono <strong>Lex</strong>. Ti aiuto con deposito telematico, firma digitale, PEC e stati del fascicolo.</p>' +
          '<ul>' +
            '<li>Preparazione buste e invio depositi PCT, PDP e PAT</li>' +
            '<li>Lettura errori, esiti controlli e stati di cancelleria</li>' +
            '<li>Verifiche operative su firma digitale, PEC e PDF/A</li>' +
            '<li>Richiami rapidi alla normativa del deposito telematico</li>' +
          '</ul>' +
          '<p>Se HACS e\' online, Lex usa il companion locale di questo dispositivo per parlare con Ollama in modo sicuro e non bloccante.</p>' +
          '<p class="mb-0">Se il pannello ti intralcia, trascinalo dove preferisci: la posizione resta salvata su questo browser.</p>' +
        '</div>' +
      '</div>'
    );
  }

  function clearHistory() {
    state.history = [];
    state.currentBubble = null;
    if (messages) {
      messages.innerHTML = defaultIntroMarkup();
    }
    setStatus('Conversazione pronta.');
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
      body: JSON.stringify(payloadBase()),
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

  function sendRemote(text) {
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
        return browserBridge()
          .runCompanionRagQuery(bridgeConfig, prepared)
          .catch(function (error) {
            error = error || new Error('Companion locale non raggiungibile.');
            error.__companionStage = true;
            throw error;
          });
      })
      .then(function (payload) {
        setAnswerPayload(state.currentBubble, payload);
        state.history.push({ role: 'assistant', content: String(payload.answer || '').trim() });
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
        setBubbleHtml(state.currentBubble, renderCompanionHelp(outdated));
        finalizeRequest('Companion locale non raggiungibile.');
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

    state.history.push({ role: 'user', content: text });
    appendMessage('user', text);

    state.streaming = true;
    if (sendButton) {
      sendButton.disabled = true;
    }

    state.currentBubble = appendMessage('assistant', '');

    if (bridgeConfig && bridgeConfig.remoteHosted) {
      sendRemote(text);
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
        updateBadge(false, 'Companion offline');
        setStatus('Il browser non riesce a raggiungere il companion locale su questo dispositivo.');
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

  function getSavedPosition() {
    try {
      var raw = window.localStorage.getItem(storageKey);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      return null;
    }
  }

  function savePosition(position) {
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(position));
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

  function applyCustomPosition(position) {
    if (!widget || !position || !isDesktop()) {
      return;
    }

    var width = widget.offsetWidth || 392;
    var height = widget.offsetHeight || 640;
    var maxLeft = Math.max(DRAG_MARGIN, window.innerWidth - width - DRAG_MARGIN);
    var maxTop = Math.max(DRAG_MARGIN, window.innerHeight - height - DRAG_MARGIN);
    var left = clamp(Number(position.left || 0), DRAG_MARGIN, maxLeft);
    var top = clamp(Number(position.top || 0), DRAG_MARGIN, maxTop);

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
    setStatus('Posizione ripristinata in basso a destra.');
  }

  function restorePosition() {
    if (!widget) {
      return;
    }

    if (!isDesktop()) {
      resetPosition();
      return;
    }

    var saved = getSavedPosition();
    if (saved) {
      applyCustomPosition(saved);
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
      savePosition({
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

  function bindEvents() {
    fab.addEventListener('click', toggle);
    sendButton.addEventListener('click', send);
    query('pct-ai-close').addEventListener('click', function () { setOpen(false); });
    query('pct-ai-clear').addEventListener('click', clearHistory);
    query('pct-ai-reset-position').addEventListener('click', resetPosition);

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
    dragHandle = query('pct-ai-header');

    if (!widget || !panel || !fab || !input || !sendButton) {
      return;
    }

    storageKey = widget.dataset.storageKey || STORAGE_FALLBACK;
    bridgeConfig = browserBridge() ? browserBridge().rootConfig(widget) : null;

    bindEvents();
    initContext();
    restorePosition();
    clearHistory();
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
