(function () {
  'use strict';

  var STORAGE_FALLBACK = 'iusentra-pct-ai-layout-v1';
  var SESSION_STORAGE_SUFFIX = ':session';
  var HISTORY_LIMIT = 12;
  var DESKTOP_MEDIA = '(min-width: 1181px)';
  var DRAG_MARGIN = 12;
  var MIN_WIDGET_WIDTH = 368;
  var MIN_WIDGET_HEIGHT = 520;
  var MAX_WIDGET_WIDTH = 720;
  var MAX_WIDGET_HEIGHT = 860;
  var state = {
    open: false,
    streaming: false,
    fullscreen: false,
    history: [],
    attachments: [],
    sessionId: null,
    contextWarmStarted: false,
    fascId: null,
    currentBubble: null,
    drag: null,
    resize: null,
    listening: false,
    voiceReplyEnabled: true,
    thinking: null,
    pendingFocus: null,
    runtimeStatusChecked: false,
    runtimeStatusPromise: null,
    contextPrimed: false,
    pageContext: null,
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
  var presetsShelf;
  var exportButton;
  var fullscreenButton;
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

  function prependSocialPrefix(prefix, answer) {
    var cleanPrefix = String(prefix || '').trim();
    var cleanAnswer = String(answer || '').trim();
    if (!cleanPrefix) {
      return cleanAnswer;
    }
    if (!cleanAnswer) {
      return cleanPrefix;
    }
    if (cleanAnswer.toLowerCase().indexOf(cleanPrefix.toLowerCase()) === 0) {
      return cleanAnswer;
    }
    return (cleanPrefix + ' ' + cleanAnswer).trim();
  }

  function lexIconUrl() {
    return (widget && widget.dataset && widget.dataset.lexIconUrl) || '/static/img/lex-mark.png';
  }

  function assistantAvatarMarkup() {
    return (
      '<div class="pct-ai-avatar pct-ai-avatar--ai">' +
        '<img src="' + escapeHtml(lexIconUrl()) + '" alt="" aria-hidden="true" class="pct-ai-brand-mark pct-ai-brand-mark--avatar">' +
      '</div>'
    );
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
      statusBar.classList.remove('is-thinking', 'is-reflection');
      statusBar.textContent = message || '';
    }
  }

  function setStatusHtml(html, mode) {
    if (!statusBar) {
      return;
    }
    statusBar.classList.toggle('is-thinking', mode === 'thinking');
    statusBar.classList.toggle('is-reflection', mode === 'reflection');
    statusBar.innerHTML = html || '';
  }

  function browserBridge() {
    return window.IusentraLocalAiBrowserBridge || null;
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
    wrap.className = 'pct-ai-msg pct-ai-msg--' + role;
    wrap.innerHTML =
      (role === 'user'
        ? '<div class="pct-ai-avatar pct-ai-avatar--user"><i class="bi bi-person-fill"></i></div>'
        : assistantAvatarMarkup()) +
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

  var ACTION_PROMPTS = {
    summary: 'Fammi una sintesi operativa del fascicolo o del tema attivo, con fatti rilevanti, warning e prossimi passi.',
    criticita: 'Trova criticita, rischi aperti, punti mancanti e verifiche residue sul tema attivo.',
    bozza: 'Preparami una bozza operativa iniziale con struttura chiara, warning e dati ancora da completare.',
    fonti: 'Mostrami soltanto le fonti e spiegami quali sono davvero utilizzabili.',
  };

  var SURFACE_PRESETS = {
    fascicolo: {
      label: 'Lex Fascicolo',
      prompt: 'Fammi una sintesi del fascicolo attivo: documenti chiave, rischi aperti, cosa manca e prossimi passi.',
    },
    udienza: {
      label: 'Lex Udienza',
      prompt: 'Preparami la prossima udienza con timeline, allegati da vedere, punti critici e verifiche residue.',
    },
    telematico: {
      label: 'Lex Telematico',
      prompt: 'Spiegami errori, warning e stato di import o deposito telematico, con cosa verificare prima del prossimo passo.',
    },
    operativo: {
      label: 'Lex Operativo',
      prompt: 'Dammi la prossima azione giusta della giornata con priorita, scadenze che stanno diventando problemi e fascicoli da presidiare.',
    },
  };

  function renderWarnings(payload) {
    var warnings = Array.isArray(payload && payload.warnings) ? payload.warnings.filter(Boolean) : [];
    if (!warnings.length) {
      return '';
    }
    return (
      '<div class="pct-ai-callout pct-ai-callout--warning">' +
        '<div class="pct-ai-callout__title"><i class="bi bi-exclamation-triangle me-1"></i>Warning</div>' +
        '<ul class="pct-ai-callout__list">' +
          warnings.map(function (item) { return '<li>' + escapeHtml(item) + '</li>'; }).join('') +
        '</ul>' +
      '</div>'
    );
  }

  function renderConfidence(payload) {
    var label = String(payload && (payload.confidenceLabel || payload.confidence_label || '') || '').trim();
    var confidence = Number(payload && payload.confidence || 0);
    var reason = String(payload && (payload.confidenceReason || payload.confidence_reason || '') || '').trim();
    if (!label && !reason && !confidence) {
      return '';
    }
    var badgeClass = 'bg-secondary-subtle text-secondary-emphasis';
    if (label === 'alta') {
      badgeClass = 'bg-success-subtle text-success-emphasis';
    } else if (label === 'media') {
      badgeClass = 'bg-warning-subtle text-warning-emphasis';
    } else if (label === 'bassa') {
      badgeClass = 'bg-danger-subtle text-danger-emphasis';
    }
    return (
      '<div class="pct-ai-callout pct-ai-callout--confidence">' +
        '<div class="pct-ai-callout__title"><i class="bi bi-shield-check me-1"></i>Affidabilita</div>' +
        '<div class="d-flex align-items-center gap-2 flex-wrap">' +
          (label ? '<span class="badge rounded-pill ' + badgeClass + '">' + escapeHtml(label.toUpperCase()) + '</span>' : '') +
          (confidence ? '<span class="small text-muted">score ' + escapeHtml(confidence.toFixed(2)) + '</span>' : '') +
        '</div>' +
        (reason ? '<div class="small text-muted mt-2">' + escapeHtml(reason) + '</div>' : '') +
      '</div>'
    );
  }

  function renderSources(payload) {
    var citations = Array.isArray(payload && payload.citations) ? payload.citations.filter(Boolean) : [];
    var sources = Array.isArray(payload && payload.sources) ? payload.sources.slice(0, 5) : [];
    var items = citations.map(function (item) {
      return '<li>' + escapeHtml(item) + '</li>';
    });
    sources.forEach(function (item) {
      var title = String(item && (item.title || item.citation || item.id || '') || '').trim();
      var excerpt = String(item && (item.excerpt || item.text || '') || '').trim();
      var accessLabel = String(item && (item.source_access_label || item.access_label || '') || '').trim();
      var requiresCredentials = Boolean(item && item.source_requires_credentials);
      var restricted = Boolean(item && item.source_restricted);
      var badge = accessLabel
        ? '<span class="badge rounded-pill bg-secondary-subtle text-secondary-emphasis me-1">' + escapeHtml(accessLabel) + '</span>'
        : '';
      if (requiresCredentials) {
        badge += '<span class="badge rounded-pill bg-warning-subtle text-warning-emphasis me-1">Credenziali</span>';
      }
      if (restricted) {
        badge += '<span class="badge rounded-pill bg-danger-subtle text-danger-emphasis">Riservata</span>';
      }
      var note = '';
      if (restricted) {
        note = 'Questa fonte non e utilizzabile via web pubblico: serve il portale o il canale dedicato dello studio.';
      } else if (requiresCredentials) {
        note = 'Questa fonte richiede credenziali o abilitazioni dedicate prima della consultazione completa.';
      }
      if (!title && !excerpt) {
        return;
      }
      items.push(
        '<li>' +
          '<span class="fw-semibold">' + escapeHtml(title || 'Fonte') + '</span>' +
          (badge ? '<div class="mt-1">' + badge + '</div>' : '') +
          (excerpt ? '<div class="small text-muted">' + escapeHtml(excerpt.slice(0, 220)) + '</div>' : '') +
          (note ? '<div class="small text-muted mt-1">' + escapeHtml(note) + '</div>' : '') +
        '</li>'
      );
    });
    if (!items.length) {
      return '';
    }
    return (
      '<div class="pct-ai-callout pct-ai-callout--sources">' +
        '<div class="pct-ai-callout__title"><i class="bi bi-journal-text me-1"></i>Fonti</div>' +
        '<ul class="pct-ai-callout__list">' + items.join('') + '</ul>' +
      '</div>'
    );
  }

  function renderActionPills(payload) {
    var actions = Array.isArray(payload && payload.actions) ? payload.actions.filter(Boolean) : [];
    if (!actions.length) {
      return '';
    }
    return (
      '<div class="pct-ai-action-pills">' +
        actions.map(function (action) {
          var key = String(action.key || '').trim();
          var label = String(action.label || key || '').trim();
          var prompt = ACTION_PROMPTS[key] || label;
          return '<button type="button" class="pct-ai-action-pill" data-lex-action="' + escapeHtml(prompt) + '">' + escapeHtml(label) + '</button>';
        }).join('') +
      '</div>'
    );
  }

  function renderPresetPills() {
    if (!presetsShelf) {
      return;
    }
    presetsShelf.innerHTML = Object.keys(SURFACE_PRESETS).map(function (key) {
      var preset = SURFACE_PRESETS[key];
      return (
        '<button type="button" class="pct-ai-preset-pill" data-lex-preset="' + escapeHtml(key) + '">' +
          '<span class="pct-ai-preset-pill__label">' + escapeHtml(preset.label) + '</span>' +
        '</button>'
      );
    }).join('');
  }

  function runPreset(key) {
    var preset = SURFACE_PRESETS[String(key || '').trim()];
    if (!preset || !input) {
      return;
    }
    input.value = preset.prompt;
    autoResize();
    if (!state.open) {
      setOpen(true);
    }
    send();
  }

  function queryProfile(question) {
    var text = String(question || '').toLowerCase();
    return {
      liveWeb: /ultima|ultime|oggi|aggiornat|recente|sentenza|cassazione|tar|consiglio di stato|norma|normativa|decreto/.test(text),
      documents: /document|allegat|verbale|memoria|ricorso|atto|bozza/.test(text),
      deadlines: /scadenz|termine|udienza|agenda|calendario/.test(text),
    };
  }

  var QUICK_FOCUS_RULES = [
    { topic: 'overview_today', label: 'quadro operativo di oggi', keywords: ['oggi cosa dobbiamo fare', 'cosa dobbiamo fare oggi', 'da dove partiamo oggi', 'quadro di oggi', 'situazione di oggi', 'priorita di oggi', 'priorità di oggi'] },
    { topic: 'dashboard', label: 'quadro generale dello studio', keywords: ['panoramica', 'situazione studio', 'quadro generale', 'dashboard'] },
    { topic: 'udienze', label: 'udienze rilevanti', keywords: ['udienza', 'udienze'] },
    { topic: 'agenda', label: 'agenda studio', keywords: ['agenda', 'calendario', 'appuntamento', 'appuntamenti'] },
    { topic: 'scadenze', label: 'scadenze rilevanti', keywords: ['scadenza', 'scadenze', 'termine', 'termini'] },
    { topic: 'fascicoli', label: 'fascicoli rilevanti', keywords: ['fascicolo', 'fascicoli', 'procedimento', 'procedimenti', 'rg'] },
    { topic: 'clienti', label: 'clienti rilevanti', keywords: ['cliente', 'clienti', 'assistito', 'assistiti'] },
    { topic: 'soggetti', label: 'parti e soggetti', keywords: ['soggetto', 'soggetti', 'parte', 'parti', 'difensore', 'codifensore'] },
    { topic: 'documenti', label: 'documenti collegati', keywords: ['documento', 'documenti', 'allegato', 'allegati', 'verbale', 'memoria'] },
    { topic: 'preventivi', label: 'preventivi', keywords: ['preventivo', 'preventivi'] },
    { topic: 'fatture', label: 'fatture e pagamenti', keywords: ['fattura', 'fatture', 'fatturazione', 'parcella', 'parcelle'] },
    { topic: 'pec_firma', label: 'PEC e firma digitale', keywords: ['pec', 'firma', 'firmato', 'p7m', 'token', 'certificato'] },
    { topic: 'sentenze_web', label: 'ricerca legale aggiornata', keywords: ['sentenza', 'sentenze', 'giurisprudenza', 'cassazione', 'normativa', 'norma', 'legge', 'decreto'] }
  ];

  var FOLLOW_UP_MARKERS = [
    'quelli', 'quelle', 'quello', 'quella', 'quei', 'questi', 'queste',
    'quale dei due', 'quale delle due', 'quale dei tre', 'quale delle tre',
    'le 2 fasi', 'le due fasi',
    'quello prima', 'quella prima',
    'continua', 'vai avanti', 'scaricala', 'aprila', 'fammi vedere', 'mostramela',
    'quella sentenza', 'quel pdf', 'e oggi'
  ];
  var SMALL_TALK_PATTERNS = [
    /^come stai(?: oggi)?[?!.,]*$/,
    /^come va(?: oggi)?[?!.,]*$/,
    /^come procede[?!.,]*$/,
    /^tutto bene[?!.,]*$/,
    /^ci sei[?!.,]*$/
  ];
  var GENERIC_OPERATIONAL_FOLLOW_UP_PATTERNS = [
    /\bprossim[a-z']*\b/,
    /\battivit[a-z']*\b/,
    /\bazione\b/,
    /\bazioni\b/,
    /\badempiment[a-z']*\b/,
    /\bpasso successivo\b/,
    /\bcosa facciamo\b/,
    /\bda dove partiamo\b/
  ];

  function cleanIntentText(value) {
    return String(value || '').replace(/\s+/g, ' ').trim().toLowerCase();
  }

  function containsFocusKeyword(text, keyword) {
    var clean = cleanIntentText(text);
    var needle = cleanIntentText(keyword);
    if (!clean || !needle) {
      return false;
    }
    if (needle.indexOf(' ') >= 0) {
      return clean.indexOf(needle) >= 0;
    }
    return new RegExp('(^|[^a-z0-9])' + needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '([^a-z0-9]|$)').test(clean);
  }

  function countIntentWords(value) {
    var clean = cleanIntentText(value);
    return clean ? clean.split(' ').filter(Boolean).length : 0;
  }

  function matchFocusRule(text) {
    var clean = cleanIntentText(text);
    if (!clean) {
      return null;
    }
    for (var index = 0; index < QUICK_FOCUS_RULES.length; index += 1) {
      var rule = QUICK_FOCUS_RULES[index];
      for (var keywordIndex = 0; keywordIndex < rule.keywords.length; keywordIndex += 1) {
        if (containsFocusKeyword(clean, rule.keywords[keywordIndex])) {
          return rule;
        }
      }
    }
    return null;
  }

  function looksLikeSmallTalk(text) {
    var clean = cleanIntentText(text);
    if (!clean) {
      return false;
    }
    return SMALL_TALK_PATTERNS.some(function (pattern) {
      return pattern.test(clean);
    });
  }

  function looksLikeFollowUp(text) {
    var clean = cleanIntentText(text);
    if (!clean) {
      return false;
    }
    if (looksLikeSmallTalk(clean)) {
      return false;
    }
    for (var index = 0; index < FOLLOW_UP_MARKERS.length; index += 1) {
      if (clean.indexOf(FOLLOW_UP_MARKERS[index]) >= 0) {
        return true;
      }
    }
    return false;
  }

  function looksLikeGenericOperationalFollowUp(text) {
    var clean = cleanIntentText(text);
    if (!clean) {
      return false;
    }
    return GENERIC_OPERATIONAL_FOLLOW_UP_PATTERNS.some(function (pattern) {
      return pattern.test(clean);
    });
  }

  function recentFocusRule(history, currentText) {
    var currentClean = cleanIntentText(currentText);
    for (var index = (history || []).length - 1; index >= 0; index -= 1) {
      var entry = history[index] || {};
      var metaTopic = entry.meta && entry.meta.topic ? String(entry.meta.topic) : '';
      if (metaTopic) {
        for (var ruleIndex = 0; ruleIndex < QUICK_FOCUS_RULES.length; ruleIndex += 1) {
          if (QUICK_FOCUS_RULES[ruleIndex].topic === metaTopic) {
            return QUICK_FOCUS_RULES[ruleIndex];
          }
        }
      }
      var content = cleanIntentText(entry.content || '');
      if (!content || content === currentClean) {
        continue;
      }
      var rule = matchFocusRule(content);
      if (rule) {
        return rule;
      }
    }
    return null;
  }

  function buildFocusLabel(rule, question) {
    var clean = cleanIntentText(question);
    if (!rule) {
      return '';
    }
    if (rule.topic === 'overview_today') {
      return 'quadro operativo di oggi';
    }
    if ((rule.topic === 'udienze' || rule.topic === 'agenda') && clean.indexOf('oggi') >= 0) {
      return 'udienze di oggi';
    }
    if ((rule.topic === 'udienze' || rule.topic === 'fascicoli') && clean.indexOf('attiv') >= 0) {
      return 'procedimenti attivi';
    }
    if (rule.topic === 'scadenze' && clean.indexOf('oggi') >= 0) {
      return 'scadenze di oggi';
    }
    return rule.label;
  }

  function resolveConversationFocus(question, history) {
    if (looksLikeSmallTalk(question)) {
      return { topic: '', focusLabel: '', isFollowUp: false };
    }
    var rule = matchFocusRule(question);
    var previousRule = recentFocusRule(history, question);
    var followUp = looksLikeFollowUp(question);
    var resolved = rule;

    if (!resolved && followUp) {
      resolved = previousRule;
    }
    if (!resolved && previousRule && looksLikeGenericOperationalFollowUp(question)) {
      resolved = previousRule;
      followUp = true;
    }
    if (!resolved) {
      return { topic: '', focusLabel: '', isFollowUp: false };
    }
    return {
      topic: resolved.topic,
      focusLabel: buildFocusLabel(resolved, question),
      isFollowUp: followUp
    };
  }

  function thinkingElapsedMs() {
    if (!state.thinking || !state.thinking.startedAt) {
      return 0;
    }
    return Math.max(0, Date.now() - state.thinking.startedAt);
  }

  function formatReflectionDuration(durationMs) {
    var seconds = Math.max(0, Number(durationMs || 0)) / 1000;
    return seconds.toLocaleString('it-IT', {
      minimumFractionDigits: seconds < 10 ? 1 : 0,
      maximumFractionDigits: seconds < 10 ? 1 : 0,
    }) + ' s';
  }

  function buildThinkingNote(question, stage) {
    var profile = queryProfile(question);
    if (stage !== 1 && stage !== 2) {
      return '';
    }
    if (stage === 1) {
      if (profile.liveWeb) {
        return 'Cerco l’aggiornamento più recente su fonti ufficiali e ti porto una risposta concreta con data, giudice e principio.';
      }
      if (profile.documents) {
        return 'Sto leggendo il contesto utile tra fascicolo, documenti e moduli intelligenti per risponderti in modo concreto.';
      }
      if (profile.deadlines) {
        return 'Sto incrociando scadenze, agenda e stato operativo per darti un riepilogo davvero utilizzabile.';
      }
      return 'Sto preparando una risposta concreta, usando solo il contesto utile per non farti perdere tempo.';
    }

    if (profile.liveWeb) {
      return 'Sto verificando i riferimenti più recenti e li sto trasformando in una sintesi utile, con i dettagli che contano davvero.';
    }
    if (profile.documents) {
      return 'Sto selezionando solo i passaggi davvero rilevanti e li sto ordinando in una risposta chiara e pronta da usare.';
    }
    return 'Sto rifinendo la risposta per dartela già ordinata, leggibile e subito spendibile.';
  }

  function buildThinkingBubbleHtmlLegacy(question, stage, elapsed) {
    var suffix = elapsed >= 1400 ? ' · ' + formatReflectionDuration(elapsed) : '';
    var note = buildThinkingNote(question, stage);
    return (
      '<div class="pct-ai-thinking-box">' +
        '<span class="pct-ai-status-pill pct-ai-status-pill--inline">' +
          '<span class="pct-ai-status-pill__dot"></span>' +
          '<span>Sto pensando' + suffix + '</span>' +
        '</span>' +
        (note ? '<div class="pct-ai-thinking-copy">' + escapeHtml(note) + '</div>' : '') +
      '</div>'
    );
  }

  function renderReflectionStatusLegacy(durationMs) {
    setStatusHtml(
      '<span class="pct-ai-status-reflection">' +
        '<i class="bi bi-hourglass-split"></i>' +
        '<span>Riflessione · ' + formatReflectionDuration(durationMs) + '</span>' +
      '</span>',
      'reflection'
    );
  }

  function buildThinkingBubbleHtml(question, stage, elapsed) {
    var suffix = elapsed >= 1400 ? ' - ' + formatReflectionDuration(elapsed) : '';
    var note = buildThinkingNote(question, stage);
    return (
      '<div class="pct-ai-thinking-box">' +
        '<span class="pct-ai-status-pill pct-ai-status-pill--inline">' +
          '<span class="pct-ai-status-pill__dot"></span>' +
          '<span>Sto pensando' + suffix + '</span>' +
        '</span>' +
        (note ? '<div class="pct-ai-thinking-copy">' + escapeHtml(note) + '</div>' : '') +
      '</div>'
    );
  }

  function renderReflectionStatus(durationMs) {
    setStatusHtml(
      '<span class="pct-ai-status-reflection">' +
        '<i class="bi bi-hourglass-split"></i>' +
        '<span>Riflessione - ' + formatReflectionDuration(durationMs) + '</span>' +
      '</span>',
      'reflection'
    );
  }

  function renderThinkingStatusLegacy() {
    if (!state.thinking || !state.thinking.active || state.thinking.receivedFirstToken || !state.currentBubble) {
      return;
    }

    var elapsed = Number(state.thinking.reflectionDurationMs || thinkingElapsedMs() || 0);
    var suffix = elapsed >= 1400 ? ' · ' + formatReflectionDuration(elapsed) : '';
    setStatusHtml(
      '<span class="pct-ai-status-pill">' +
        '<span class="pct-ai-status-pill__dot"></span>' +
        '<span>Sto pensando' + suffix + '</span>' +
      '</span>',
      'thinking'
    );
  }

  function ensureThinkingNoteLegacy(stage) {
    if (!state.thinking || !state.thinking.active || state.thinking.receivedFirstToken) {
      return;
    }
    var text = buildThinkingNote(state.thinking.question, stage);
    if (!text || !state.currentBubble) {
      return;
    }
    setBubbleContent(state.currentBubble, text);
    scrollBottom();
  }

  function renderThinkingStatus() {
    if (!state.thinking || !state.thinking.active || state.thinking.receivedFirstToken || !state.currentBubble) {
      return;
    }

    setBubbleHtml(
      state.currentBubble,
      buildThinkingBubbleHtml(
        state.thinking.question,
        Number(state.thinking.stage || 0),
        thinkingElapsedMs()
      )
    );
    scrollBottom();
  }

  function ensureThinkingNote(stage) {
    if (!state.thinking || !state.thinking.active || state.thinking.receivedFirstToken) {
      return;
    }
    state.thinking.stage = Number(stage || 0);
    renderThinkingStatus();
  }

  function stopThinkingTimers() {
    if (!state.thinking) {
      return;
    }
    if (state.thinking.statusTimer) {
      window.clearInterval(state.thinking.statusTimer);
      state.thinking.statusTimer = null;
    }
    if (state.thinking.stageOneTimer) {
      window.clearTimeout(state.thinking.stageOneTimer);
      state.thinking.stageOneTimer = null;
    }
    if (state.thinking.stageTwoTimer) {
      window.clearTimeout(state.thinking.stageTwoTimer);
      state.thinking.stageTwoTimer = null;
    }
  }

  function startThinkingFeedback(question) {
    stopThinkingTimers();
    state.thinking = {
      active: true,
      question: String(question || '').trim(),
      startedAt: Date.now(),
      stage: 0,
      receivedFirstToken: false,
      reflectionDurationMs: 0,
      statusTimer: window.setInterval(renderThinkingStatus, 250),
      stageOneTimer: null,
      stageTwoTimer: null,
    };
    setStatus('');
    renderThinkingStatus();
    state.thinking.stageOneTimer = window.setTimeout(function () {
      ensureThinkingNote(1);
    }, 900);
    state.thinking.stageTwoTimer = window.setTimeout(function () {
      ensureThinkingNote(2);
    }, 3200);
  }

  function markThinkingTokenReceived() {
    if (!state.thinking || state.thinking.receivedFirstToken) {
      return;
    }
    var durationMs = thinkingElapsedMs();
    state.thinking.receivedFirstToken = true;
    state.thinking.reflectionDurationMs = durationMs;
    state.thinking.active = false;
    stopThinkingTimers();
    renderReflectionStatus(durationMs);
  }

  function finalizeThinkingFeedbackLegacy(success) {
    if (!state.thinking) {
      return;
    }
    var elapsed = Number(state.thinking.reflectionDurationMs || thinkingElapsedMs() || 0);
    stopThinkingTimers();
    if (success) {
      setStatusHtml(
        '<span class="pct-ai-status-reflection">' +
          '<i class="bi bi-hourglass-split"></i>' +
          '<span>Riflessione · ' + formatReflectionDuration(elapsed) + '</span>' +
        '</span>',
        'reflection'
      );
    }
    state.thinking.active = false;
  }

  function finalizeThinkingFeedback(success) {
    if (!state.thinking) {
      return;
    }
    var elapsed = Number(state.thinking.reflectionDurationMs || thinkingElapsedMs() || 0);
    stopThinkingTimers();
    if (success) {
      renderReflectionStatus(elapsed);
    } else if (statusBar && (statusBar.classList.contains('is-thinking') || statusBar.classList.contains('is-reflection'))) {
      setStatus('');
    }
    state.thinking.active = false;
  }

  function generatedDocumentPayload(payload) {
    if (!payload || !payload.answer) {
      return null;
    }
    var docs = documentsHelper();
    var suggestedTitle = docs && docs.suggestGeneratedTitle
      ? docs.suggestGeneratedTitle({
          title: payload.title || '',
          question: payload.question || '',
          answer: payload.answer || '',
        })
      : 'Documento generato da Lex';

    return {
      title: suggestedTitle,
      question: String(payload.question || '').trim(),
      answer: String(payload.answer || '').trim(),
      citations: Array.isArray(payload.citations) ? payload.citations.filter(Boolean) : [],
      contextLabel: ctx && !ctx.hidden && ctxLabel ? String(ctxLabel.textContent || '').trim() : '',
      exportUrl: widget && widget.dataset ? widget.dataset.exportDocumentUrl || '' : '',
    };
  }

  function renderGeneratedDocumentActions(payload) {
    var docs = documentsHelper();
    if (!docs || !docs.buildGeneratedDocumentActions) {
      return '';
    }
    var exportPayload = generatedDocumentPayload(payload);
    if (!exportPayload) {
      return '';
    }
    return docs.buildGeneratedDocumentActions(exportPayload);
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
    voice.speak(clean, {
      lang: 'it-IT',
      rate: 0.93,
      pitch: 1.08,
      volume: 0.98,
      preferFemale: true,
    });
  }

  function renderCompanionHelp(outdated) {
    if (!browserBridge() || !bridgeConfig) {
      return '<div class="text-danger">Servizio locale non raggiungibile su questo dispositivo.</div>';
    }
    var help = browserBridge().companionHelp(bridgeConfig, { outdated: outdated });
    return (
      '<div class="text-danger fw-semibold mb-2">' + escapeHtml(help.title || 'Servizio locale del dispositivo non disponibile') + '</div>' +
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
    var message = escapeHtml((error && error.message) || 'Il servizio locale del dispositivo ha rifiutato la richiesta AI.');
    return (
      '<div class="text-warning fw-semibold mb-2">Servizio locale del dispositivo raggiunto, ma la richiesta non e\' andata a buon fine</div>' +
      '<div class="small text-muted">Lex e\' riuscito a contattare il Local Signer su questo dispositivo, ma il motore locale ha restituito un errore operativo.</div>' +
      '<div class="small mt-2"><code>' + message + '</code></div>'
    );
  }

  function renderServerPreparationHelp(error) {
    var authProblem = Number(error && error.httpStatus || 0) === 401 || Number(error && error.httpStatus || 0) === 403;
    var message = escapeHtml((error && error.message) || 'Il server IUSENTRA non e\' riuscito a preparare il contesto della richiesta.');
    return (
      '<div class="text-danger fw-semibold mb-2">' + (authProblem ? 'Sessione scaduta o non autorizzata' : 'Preparazione richiesta non riuscita') + '</div>' +
      '<div class="small text-muted">' + (
        authProblem
          ? 'Ricarica la pagina ed effettua nuovamente l\'accesso a IUSENTRA prima di chiedere una risposta a Lex.'
          : 'Lex non e\' riuscito a preparare il contesto sul server IUSENTRA prima di interrogare il servizio locale del dispositivo.'
      ) + '</div>' +
      '<div class="small mt-2"><code>' + message + '</code></div>'
    );
  }

  function renderReferenceLabel(referenceLabel) {
    var text = String(referenceLabel || '').trim();
    if (!text) {
      return '';
    }
    return '<div class="pct-ai-reference">Riferimento: ' + escapeHtml(text) + '</div>';
  }

  function stripArtificialPlaceholders(answer) {
    return String(answer || '')
      .replace(/\[(?:inserisci|specifica(?:re)?|esempio|ambito di ricerca)[^\]]*\]/gi, ' ')
      .replace(/\s+\n/g, '\n')
      .replace(/\n\s+/g, '\n')
      .replace(/[ \t]{2,}/g, ' ');
  }

  function shouldStripGreetingForQuestion(question) {
    var clean = cleanIntentText(question);
    if (!clean) {
      return true;
    }
    return !/^(ciao|salve|buongiorno|buonasera|buon pomeriggio|grazie|grazie mille|ti ringrazio|ok|va bene|perfetto|ottimo|bene|a domani|a dopo|ci aggiorniamo|buona giornata|buona serata|buon lavoro|buona notte)\b/.test(clean);
  }

  function stripLexGreeting(answer, question) {
    var clean = String(answer || '').trim();
    if (!clean || !shouldStripGreetingForQuestion(question)) {
      return clean;
    }
    return clean.replace(/^(?:(?:ciao,\s*sono lex\.?)|(?:ciao\.?)|(?:buongiorno\.?)|(?:buonasera\.?)|(?:buon pomeriggio\.?)|(?:salve\.?))\s+/i, '').trim();
  }

  function collapseLeadingDuplicateSentence(answer, openingLine) {
    var clean = String(answer || '').trim();
    var expected = String(openingLine || '').trim();
    if (expected) {
      var duplicatedOpening = new RegExp('^' + expected.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\s+' + expected.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(\\s+|$)', 'i');
      clean = clean.replace(duplicatedOpening, expected + ' ').trim();
    }
    return clean.replace(/^([^.!?\n]{6,180}[.!?])\s+\1(\s+|$)/i, '$1 ').trim();
  }

  function stripMetaResponseScaffolding(answer) {
    var clean = String(answer || '').trim();
    if (!clean) {
      return '';
    }
    clean = clean
      .replace(/^ok,\s*ecco una risposta[^\n]*\n*/i, '')
      .replace(/^ok,\s*ho capito\.[^\n]*\n*/i, '')
      .replace(/^risposta:\s*/i, '')
      .replace(/^\(a questo punto,[\s\S]*?\)\s*/i, '')
      .replace(/^motivazione:\s*/i, '')
      .replace(/spero che questa risposta sia adatta[^\n]*$/i, '')
      .replace(/applica immediatamente l'input fornito[^\n]*$/i, '')
      .replace(/---\s*motivazione:[\s\S]*$/i, '')
      .trim();
    return clean;
  }

  function replaceUnverifiedCaseLawExamples(answer, options) {
    var clean = String(answer || '').trim();
    var question = cleanIntentText(options && options.question || '');
    var isCaseLawQuestion = /sentenz|giurisprudenza|pronunc|cassazione|tribunale|corte d['’]appello/.test(question);
    var looksSpecificReference = /(cassazione|tribunale|corte d['’]appello)[^.\n]{0,100}(sent\.?\s*n\.?\s*\d+\/\d{4}|n\.?\s*\d+\/\d{4})/i.test(clean);
    var admitsExamples = /\besempi\b|\besemplificativ[oi]\b/i.test(clean);
    if ((options && options.legalReferenceGuardActive) && looksSpecificReference) {
      return 'Non ho ancora una pronuncia verificata da citare con numero e PDF. Posso cercare una pronuncia reale e riportarti il link corretto.';
    }
    if (isCaseLawQuestion && looksSpecificReference && admitsExamples) {
      return 'Non ho ancora una pronuncia verificata da citare con numero e PDF. Posso cercare una pronuncia reale e riportarti il link corretto.';
    }
    return clean;
  }

  function isDirectGuardAnswer(answer) {
    var clean = String(answer || '').trim().toLowerCase();
    if (!clean) {
      return false;
    }
    return clean.indexOf("quel riferimento non e' ancora verificato") === 0 ||
      clean.indexOf("non vedo ancora un pdf ufficiale diretto") === 0 ||
      clean.indexOf("non ho ancora una pronuncia verificata") === 0;
  }

  function sanitizeLexAnswer(answer, options) {
    var original = String(answer || '').replace(/\r/g, '').trim();
    if (!original) {
      return '';
    }
    var clean = stripArtificialPlaceholders(original);
    clean = stripMetaResponseScaffolding(clean);
    clean = stripLexGreeting(clean, options && options.question || '');
    clean = collapseLeadingDuplicateSentence(clean, options && options.openingLine || '');
    clean = replaceUnverifiedCaseLawExamples(clean, options || {});
    clean = clean.replace(/\n{3,}/g, '\n\n').trim();
    return clean || original;
  }

  function normalizeAssistantPayload(payload, options) {
    var normalized = Object.assign({}, payload || {});
    normalized.disableExports = Boolean(normalized.disableExports || normalized.disable_exports);
    if (Object.prototype.hasOwnProperty.call(normalized, 'reference_label') && !Object.prototype.hasOwnProperty.call(normalized, 'referenceLabel')) {
      normalized.referenceLabel = normalized.reference_label;
    }
    if (Object.prototype.hasOwnProperty.call(normalized, 'confidence_label') && !Object.prototype.hasOwnProperty.call(normalized, 'confidenceLabel')) {
      normalized.confidenceLabel = normalized.confidence_label;
    }
    if (Object.prototype.hasOwnProperty.call(normalized, 'confidence_reason') && !Object.prototype.hasOwnProperty.call(normalized, 'confidenceReason')) {
      normalized.confidenceReason = normalized.confidence_reason;
    }
    normalized.answer = sanitizeLexAnswer(normalized.answer || '', options || {});
    if (isDirectGuardAnswer(normalized.answer)) {
      normalized.referenceLabel = '';
      normalized.disableExports = true;
    }
    return normalized;
  }

  function buildAnswerHtml(payload, options) {
    var answer = payload && payload.answer ? renderMarkdown(payload.answer) : '<p>Nessuna risposta disponibile.</p>';
    var includeExports = !(options && options.includeExports === false) && !(payload && payload.disableExports);
    return (
      renderReferenceLabel(payload && payload.referenceLabel) +
      answer +
      renderConfidence(payload) +
      renderWarnings(payload) +
      renderSources(payload) +
      renderActionPills(payload) +
      (includeExports ? renderGeneratedDocumentActions(payload || {}) : '')
    );
  }

  function setAnswerPayload(element, payload) {
    var safePayload = payload || {};
    var exportPayload = generatedDocumentPayload(safePayload);
    if (element) {
      element._generatedDocument = exportPayload;
    }
    setBubbleHtml(element, buildAnswerHtml(safePayload, { includeExports: true }));
  }

  function defaultIntroMarkup() {
    return (
      '<div class="pct-ai-msg pct-ai-msg--assistant">' +
        assistantAvatarMarkup() +
        '<div class="pct-ai-bubble">' +
          '<p class="mb-0">Ciao, sono Lex.</p>' +
        '</div>' +
      '</div>'
    );
  }

  function generateSessionId() {
    return 'lex-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);
  }

  function sessionStorageKey() {
    return storageKey + SESSION_STORAGE_SUFFIX;
  }

  function trimHistory() {
    if (state.history.length > HISTORY_LIMIT) {
      state.history = state.history.slice(-HISTORY_LIMIT);
    }
  }

  function conversationContextLabel() {
    return ctx && !ctx.hidden && ctxLabel ? String(ctxLabel.textContent || '').trim() : '';
  }

  function cleanRoutePath(path) {
    var route = String(path || '').replace(/\/+$/, '') || '/';
    route = route.toLowerCase();
    if (route === '/app-v2') {
      return '/';
    }
    if (route.indexOf('/app-v2/') === 0) {
      return route.slice('/app-v2'.length) || '/';
    }
    return route;
  }

  function contextLabelForKey(contextKey, path) {
    var key = String(contextKey || '').trim().toLowerCase();
    var route = cleanRoutePath(path || (widget && widget.dataset ? widget.dataset.pagePath : '') || window.location.pathname);
    var labels = {
      'panoramica': 'Contesto panoramica',
      'regia-operativa': 'Contesto regia operativa',
      'ricerca-studio': 'Contesto ricerca studio',
      'agenda': 'Contesto agenda',
      'agenda-appuntamento': 'Contesto appuntamento',
      'fascicoli': 'Contesto fascicoli',
      'fascicolo': 'Contesto fascicolo attivo',
      'fascicolo-dettaglio': 'Contesto fascicolo attivo',
      'fascicolo-form': 'Contesto fascicolo',
      'cartella-cliente': 'Contesto cartella cliente',
      'anagrafiche': 'Contesto anagrafiche',
      'clienti': 'Contesto clienti',
      'clienti-nuovo': 'Contesto anagrafiche',
      'soggetti': 'Contesto soggetti',
      'email-pec': 'Contesto PEC',
      'comunicazioni': 'Contesto comunicazioni',
      'messaggi': 'Contesto messaggi',
      'nuovo-messaggio': 'Contesto invio messaggio',
      'scadenziario': 'Contesto scadenziario',
      'scadenza-form': 'Contesto scadenza',
      'preparazione-udienza': 'Contesto preparazione udienza',
      'telematico': 'Contesto telematico',
      'telematico-polisweb': 'Contesto PolisWeb / PST',
      'telematico-pdp': 'Contesto PDP Penale',
      'telematico-pat': 'Contesto PAT Amministrativo',
      'telematico-ptt': 'Contesto PTT Tributario',
      'telematico-tribunali': 'Contesto Tribunali / PEC',
      'telematico-checklist': 'Contesto checklist deposito',
      'telematico-firma': 'Contesto firma digitale',
    };
    if (labels[key]) {
      return labels[key];
    }
    if (route.indexOf('/fascicoli') === 0) return 'Contesto fascicoli';
    if (route.indexOf('/clienti') === 0 || route.indexOf('/soggetti') === 0) return 'Contesto anagrafiche';
    if (route === '/email' || route.indexOf('/messaggi') === 0) return 'Contesto comunicazioni';
    if (route.indexOf('/agenda') === 0) return 'Contesto agenda';
    if (route.indexOf('/scadenziario') === 0) return 'Contesto scadenziario';
    if (route.indexOf('/wizard-pro') === 0) return 'Contesto preparazione udienza';
    if (route === '/telematico' || route === '/telematici' || route === '/polisweb' || route === '/pdp' || route === '/pat' || route === '/sigit' || route === '/ptt' || route === '/tribunali' || route === '/deposito/checklist' || route === '/guida/firma-digitale') {
      return 'Contesto telematico';
    }
    if (route === '/global-search' || route === '/ricerca-studio') return 'Contesto ricerca studio';
    if (route === '/workspace-intelligente' || route.indexOf('/regia-operativa') === 0) return 'Contesto regia operativa';
    return 'Contesto pagina corrente';
  }

  function readExternalLexContext() {
    var external = window.IUSENTRA_LEX_CONTEXT;
    if (external && typeof external === 'object') {
      return external;
    }
    return null;
  }

  function applyLexPageContext(config, options) {
    config = config && typeof config === 'object' ? config : {};
    options = options || {};
    var contextKey = String(config.context || '').trim();
    var pagePath = String(config.pagePath || (widget && widget.dataset ? widget.dataset.pagePath : '') || window.location.pathname || '').trim();
    var label = String(config.contextLabel || config.label || '').trim() || contextLabelForKey(contextKey, pagePath);
    var previous = state.pageContext && state.pageContext.context + '|' + state.pageContext.label + '|' + state.pageContext.pagePath;
    state.pageContext = {
      context: contextKey || cleanRoutePath(pagePath).replace(/^\//, '') || 'pagina',
      label: label,
      pagePath: pagePath,
    };
    if (widget && widget.dataset) {
      widget.dataset.lexContext = state.pageContext.context;
      widget.dataset.pagePath = state.pageContext.pagePath;
    }
    if (ctx && ctxLabel && label) {
      ctx.hidden = false;
      ctxLabel.textContent = label;
    }
    if (previous && previous !== state.pageContext.context + '|' + state.pageContext.label + '|' + state.pageContext.pagePath) {
      state.contextWarmStarted = false;
      state.contextPrimed = false;
    }
    saveConversationMemory();
    if (options.open) {
      setOpen(true);
    }
  }

  function currentPageContextPayload() {
    var context = state.pageContext || {};
    return {
      context_label: conversationContextLabel(),
      page_context: String(context.context || ''),
      page_path: String(context.pagePath || (widget && widget.dataset ? widget.dataset.pagePath : '') || window.location.pathname || ''),
    };
  }

  function saveConversationMemory() {
    try {
      if (!window.sessionStorage) {
        return;
      }
      trimHistory();
      if (!state.history.length && !state.attachments.length) {
        window.sessionStorage.removeItem(sessionStorageKey());
        return;
      }
      if (!state.sessionId) {
        state.sessionId = generateSessionId();
      }
      window.sessionStorage.setItem(
        sessionStorageKey(),
        JSON.stringify({
          sessionId: state.sessionId,
          fascId: state.fascId || '',
          contextLabel: conversationContextLabel(),
          pageContext: state.pageContext || null,
          history: state.history.slice(-HISTORY_LIMIT),
          attachments: state.attachments.slice(0, 4),
          savedAt: new Date().toISOString(),
        })
      );
    } catch (error) {
      return;
    }
  }

  function restoreConversationMemory() {
    try {
      if (!window.sessionStorage) {
        return false;
      }
      var raw = window.sessionStorage.getItem(sessionStorageKey());
      if (!raw) {
        return false;
      }
      var parsed = JSON.parse(raw);
      state.sessionId = parsed && parsed.sessionId ? String(parsed.sessionId) : generateSessionId();
      state.history = Array.isArray(parsed && parsed.history) ? parsed.history.slice(-HISTORY_LIMIT) : [];
      state.attachments = Array.isArray(parsed && parsed.attachments) ? parsed.attachments.slice(0, 4) : [];
      if (!state.fascId && parsed && parsed.fascId) {
        state.fascId = String(parsed.fascId);
      }
      if (!state.fascId && parsed && parsed.contextLabel && ctx && ctxLabel) {
        ctx.hidden = false;
        ctxLabel.textContent = String(parsed.contextLabel);
      }
      if (parsed && parsed.pageContext && typeof parsed.pageContext === 'object') {
        state.pageContext = parsed.pageContext;
      }
      return Boolean(state.history.length || state.attachments.length);
    } catch (error) {
      try {
        window.sessionStorage.removeItem(sessionStorageKey());
      } catch (_cleanupError) {
        return false;
      }
      return false;
    }
  }

  function renderConversation() {
    if (!messages) {
      return;
    }
    messages.innerHTML = '';
    if (!state.history.length) {
      messages.innerHTML = defaultIntroMarkup();
      scrollBottom();
      return;
    }
    state.history.forEach(function (entry) {
      var role = entry.role === 'user' ? 'user' : 'assistant';
      var bubble = appendMessage(role, entry.content || '');
      if (role === 'assistant' && bubble) {
        setBubbleHtml(
          bubble,
          buildAnswerHtml(
            {
              answer: entry.content || '',
              referenceLabel: entry.meta && entry.meta.referenceLabel ? entry.meta.referenceLabel : '',
            },
            { includeExports: false }
          )
        );
      }
    });
  }

  function clearHistory() {
    finalizeThinkingFeedback(false);
    state.sessionId = generateSessionId();
    state.history = [];
    state.currentBubble = null;
    state.pendingFocus = null;
    state.attachments = [];
    state.contextWarmStarted = false;
    state.contextPrimed = false;
    renderConversation();
    renderAttachments();
    saveConversationMemory();
    setStatus('Nuova sessione pronta.');
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
    saveConversationMemory();
    setStatus(state.attachments.length ? 'Documento rimosso dal contesto di Lex.' : 'Nessun documento caricato al momento.');
  }

  function handleAttachmentParseResult(payload) {
    var parsed = Array.isArray(payload && payload.attachments) ? payload.attachments : [];
    var errors = Array.isArray(payload && payload.errors) ? payload.errors : [];
    state.attachments = state.attachments.concat(parsed).slice(0, 4);
    renderAttachments();
    saveConversationMemory();
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

  function setOpen(nextOpen, options) {
    options = options || {};
    state.open = Boolean(nextOpen);
    if (!panel || !fab || !widget) {
      return;
    }

    if (!state.open && state.fullscreen && options.exitFullscreen !== false) {
      setFullscreen(false, { silent: true });
    }

    panel.hidden = !state.open;
    fab.classList.toggle('pct-ai-fab--active', state.open);
    widget.classList.toggle('pct-ai-widget--open', state.open);

    if (state.open) {
      ensureAssistantReady();
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

  function closeAssistant() {
    if (state.fullscreen) {
      setFullscreen(false, { silent: true });
    }
    setOpen(false, { exitFullscreen: false });
  }

  function finalizeRequest(message) {
    state.streaming = false;
    state.pendingFocus = null;
    if (sendButton) {
      sendButton.disabled = false;
    }
    if (!(statusBar && statusBar.classList.contains('is-reflection'))) {
      setStatus(message || 'Assistente pronto.');
    }
    scrollBottom();
  }

  function payloadBase() {
    trimHistory();
    var chatMessages = state.history.slice(-HISTORY_LIMIT).map(function (entry) {
      return {
        role: entry.role,
        content: entry.content,
      };
    });
    var pageContext = currentPageContextPayload();
    return {
      session_id: state.sessionId || generateSessionId(),
      messages: chatMessages,
      fascicolo_id: state.fascId || '',
      context_label: pageContext.context_label,
      page_context: pageContext.page_context,
      page_path: pageContext.page_path,
    };
  }

  function ensureAssistantReady(forceStatusRefresh) {
    if (forceStatusRefresh) {
      state.runtimeStatusChecked = false;
      state.runtimeStatusPromise = null;
    }
    if (!state.contextPrimed) {
      state.contextPrimed = true;
      primeAssistantContext();
    }
    return ensureStatusCheck(forceStatusRefresh);
  }

  function primeAssistantContext() {
    var warmupUrl = widget && widget.dataset ? widget.dataset.warmupUrl || '' : '';
    var warmQuestion = '';
    if (!warmupUrl || state.contextWarmStarted) {
      return;
    }

    state.contextWarmStarted = true;
    if (!state.sessionId) {
      state.sessionId = generateSessionId();
    }

    for (var idx = state.history.length - 1; idx >= 0; idx -= 1) {
      if (state.history[idx] && state.history[idx].role === 'user' && state.history[idx].content) {
        warmQuestion = String(state.history[idx].content);
        break;
      }
    }

    fetch(warmupUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: state.sessionId,
        question: warmQuestion,
        context_label: conversationContextLabel(),
        page_context: currentPageContextPayload().page_context,
        page_path: currentPageContextPayload().page_path,
      }),
      }).catch(function () {
      state.contextWarmStarted = false;
    });
  }

  function ensureStatusCheck(forceRefresh) {
    if (forceRefresh) {
      state.runtimeStatusChecked = false;
      state.runtimeStatusPromise = null;
    }
    if (state.runtimeStatusChecked && !state.runtimeStatusPromise) {
      return Promise.resolve();
    }
    if (state.runtimeStatusPromise) {
      return state.runtimeStatusPromise;
    }
    state.runtimeStatusPromise = Promise.resolve(checkStatus()).finally(function () {
      state.runtimeStatusChecked = true;
      state.runtimeStatusPromise = null;
    });
    return state.runtimeStatusPromise;
  }

  function sendLocal(text) {
    var payload = payloadBase();
    var referenceLabel = state.pendingFocus && state.pendingFocus.focusLabel ? String(state.pendingFocus.focusLabel) : '';
    fetch(widget.dataset.chatUrl || '/api/assistente/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: payload.session_id,
        messages: payload.messages,
        fascicolo_id: payload.fascicolo_id,
        context_label: payload.context_label,
        page_context: payload.page_context,
        page_path: payload.page_path,
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
            var finalPayload = normalizeAssistantPayload(
              { answer: full, citations: [], question: text, referenceLabel: referenceLabel },
              { question: text }
            );
            setAnswerPayload(state.currentBubble, finalPayload);
            state.history.push({ role: 'assistant', content: finalPayload.answer, meta: { topic: state.pendingFocus && state.pendingFocus.topic || '', referenceLabel: referenceLabel } });
            saveConversationMemory();
            speakAnswer(finalPayload.answer);
            finalizeThinkingFeedback(true);
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
                var donePayload = normalizeAssistantPayload(
                  { answer: full, citations: [], question: text, referenceLabel: referenceLabel },
                  { question: text }
                );
                setAnswerPayload(state.currentBubble, donePayload);
                state.history.push({ role: 'assistant', content: donePayload.answer, meta: { topic: state.pendingFocus && state.pendingFocus.topic || '', referenceLabel: referenceLabel } });
                saveConversationMemory();
                speakAnswer(donePayload.answer);
                finalizeThinkingFeedback(true);
                finalizeRequest();
                return;
              }

            try {
              var data = JSON.parse(raw);
              if (data.errore) {
                setBubbleContent(state.currentBubble, 'Attenzione: ' + data.errore);
                state.history.push({ role: 'assistant', content: data.errore, meta: { topic: state.pendingFocus && state.pendingFocus.topic || '' } });
                saveConversationMemory();
                finalizeThinkingFeedback(false);
                finalizeRequest();
                return;
              }
              if (data.token) {
                markThinkingTokenReceived();
                full += data.token;
                setBubbleContent(state.currentBubble, full);
                scrollBottom();
              }
            } catch (error) {
              setBubbleContent(state.currentBubble, 'Risposta non leggibile ricevuta dal servizio.');
              finalizeThinkingFeedback(false);
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
      finalizeThinkingFeedback(false);
      finalizeRequest('Connessione al motore locale non riuscita.');
    });
  }

  function sendViaCompanion(text) {
    if (!browserBridge() || !bridgeConfig) {
      setBubbleContent(state.currentBubble, 'Il bridge AI locale non e\' disponibile su questo browser.');
      finalizeRequest('Bridge AI locale non disponibile.');
      return;
    }

    var preparedFocusLabel = state.pendingFocus && state.pendingFocus.focusLabel ? String(state.pendingFocus.focusLabel) : '';
    var preparedOpeningLine = '';
    var preparedLegalReferenceGuardActive = false;
    var preparedConfidenceLabel = '';
    var preparedConfidenceReason = '';
    var preparedConfidenceValue = 0;
    var preparedSources = [];
    var preparedCitations = [];
    browserBridge()
      .fetchServerContext(bridgeConfig, {
        question: text,
        messages: state.history.slice(-HISTORY_LIMIT).map(function (entry) {
          return {
            role: entry.role,
            content: entry.content,
          };
        }),
        fascicolo_id: state.fascId || '',
        session_id: state.sessionId || generateSessionId(),
        context_label: currentPageContextPayload().context_label,
        page_context: currentPageContextPayload().page_context,
        page_path: currentPageContextPayload().page_path,
        attachments: state.attachments.slice(),
      })
      .then(function (prepared) {
        if (prepared && Object.prototype.hasOwnProperty.call(prepared, 'focus_label')) {
          preparedFocusLabel = String(prepared.focus_label || '').trim();
        }
        preparedOpeningLine = String(prepared && prepared.opening_line || '').trim();
        preparedLegalReferenceGuardActive = Boolean(prepared && prepared.legal_reference_guard_active);
        preparedConfidenceLabel = String(prepared && (prepared.confidence_label || prepared.confidenceLabel || '') || '').trim();
        preparedConfidenceReason = String(prepared && (prepared.confidence_reason || prepared.confidenceReason || '') || '').trim();
        preparedConfidenceValue = Number(prepared && prepared.confidence || 0);
        preparedSources = Array.isArray(prepared && prepared.sources) ? prepared.sources.slice() : [];
        preparedCitations = Array.isArray(prepared && prepared.citations) ? prepared.citations.slice() : [];
        if ((String(prepared && prepared.query_type || '').trim() === 'social_only' || String(prepared && prepared.query_type || '').trim() === 'direct_answer' || String(prepared && prepared.query_type || '').trim() === 'workflow_answer' || String(prepared && prepared.query_type || '').trim() === 'governed_chat_blocked') && prepared && prepared.answer) {
          return {
            answer: String(prepared.answer || '').trim(),
            citations: preparedCitations,
            sources: preparedSources,
            confidence: prepared.confidence || preparedConfidenceValue,
            confidenceLabel: prepared.confidence_label || preparedConfidenceLabel,
            confidenceReason: prepared.confidence_reason || preparedConfidenceReason,
            question: text,
            referenceLabel: '',
            disableExports: Boolean(prepared.disable_exports),
            legalReferenceGuardActive: preparedLegalReferenceGuardActive,
          };
        }
        var partial = '';
        return browserBridge()
          .streamCompanionRagQuery(bridgeConfig, prepared, {
            onToken: function (token) {
              markThinkingTokenReceived();
              partial += String(token || '');
              setBubbleContent(state.currentBubble, partial);
              scrollBottom();
            },
          })
          .catch(function (error) {
            error = error || new Error('Servizio locale non raggiungibile.');
            error.__companionStage = true;
            error.__partialAnswer = partial;
            throw error;
          });
      })
      .then(function (payload) {
        if (!payload.answer && state.currentBubble) {
          payload.answer = state.currentBubble.textContent || '';
        }
        if (!Array.isArray(payload.sources) || !payload.sources.length) {
          payload.sources = Array.isArray(payload.sources) && payload.sources.length ? payload.sources : [];
          if (preparedSources.length) {
            payload.sources = preparedSources.slice();
          }
        }
        if (!Array.isArray(payload.citations) || !payload.citations.length) {
          payload.citations = Array.isArray(payload.citations) && payload.citations.length ? payload.citations : [];
          if (preparedCitations.length) {
            payload.citations = preparedCitations.slice();
          }
        }
        if (!Object.prototype.hasOwnProperty.call(payload, 'confidence') && preparedConfidenceValue) {
          payload.confidence = preparedConfidenceValue;
        }
        if (!payload.confidenceLabel && preparedConfidenceLabel) {
          payload.confidenceLabel = preparedConfidenceLabel;
        }
        if (!payload.confidenceReason && preparedConfidenceReason) {
          payload.confidenceReason = preparedConfidenceReason;
        }
        payload.question = text;
        if (Object.prototype.hasOwnProperty.call(payload, 'referenceLabel')) {
          payload.referenceLabel = String(payload.referenceLabel || '').trim();
        } else {
          payload.referenceLabel = String(preparedFocusLabel || '').trim();
        }
        payload = normalizeAssistantPayload(payload, {
          question: text,
          openingLine: preparedOpeningLine,
          legalReferenceGuardActive: Boolean(payload.legalReferenceGuardActive || preparedLegalReferenceGuardActive)
        });
        setAnswerPayload(state.currentBubble, payload);
        state.history.push({
          role: 'assistant',
          content: String(payload.answer || '').trim(),
          meta: {
            topic: state.pendingFocus && state.pendingFocus.topic || '',
            referenceLabel: payload.referenceLabel,
          },
        });
        saveConversationMemory();
        speakAnswer(payload.answer || '');
        finalizeThinkingFeedback(true);
        finalizeRequest('Risposta generata sul dispositivo locale.');
      })
      .catch(function (error) {
        if (!error || !error.__companionStage) {
          finalizeThinkingFeedback(false);
          setBubbleHtml(state.currentBubble, renderServerPreparationHelp(error));
          finalizeRequest(
            Number(error && error.httpStatus || 0) === 401 || Number(error && error.httpStatus || 0) === 403
              ? 'Sessione IUSENTRA da rinnovare.'
              : 'Preparazione della richiesta non riuscita.'
          );
          return;
        }
        var outdated = Number(error && error.httpStatus || 0) === 404;
        if (outdated) {
          finalizeThinkingFeedback(false);
          setBubbleHtml(state.currentBubble, renderCompanionHelp(true));
          finalizeRequest('Aggiornamento del servizio locale richiesto.');
          return;
        }
        if (isCompanionTransportError(error)) {
          if (!bridgeConfig.remoteHosted) {
            setStatus('Servizio locale del dispositivo non raggiungibile, attivo il percorso alternativo sul motore locale di IUSENTRA...');
            sendLocal(text);
            return;
          }
          finalizeThinkingFeedback(false);
          setBubbleHtml(state.currentBubble, renderCompanionHelp(false));
          finalizeRequest('Servizio locale non raggiungibile.');
          return;
        }
        if (error && error.__partialAnswer) {
          finalizeThinkingFeedback(false);
          setBubbleHtml(
            state.currentBubble,
            renderMarkdown(error.__partialAnswer) +
              '<div class="small text-warning mt-3">La risposta si e\' interrotta prima del completamento.</div>' +
              '<div class="small mt-2"><code>' + escapeHtml((error && error.message) || 'Errore operativo del modulo AI locale.') + '</code></div>'
          );
          state.history.push({
            role: 'assistant',
            content: String(error.__partialAnswer || '').trim(),
            meta: {
              topic: state.pendingFocus && state.pendingFocus.topic || '',
              referenceLabel: preparedFocusLabel,
            },
          });
          saveConversationMemory();
          finalizeRequest('Risposta interrotta dal servizio locale del dispositivo.');
          return;
        }
        finalizeThinkingFeedback(false);
        setBubbleHtml(state.currentBubble, renderCompanionRuntimeHelp(error));
        finalizeRequest('Servizio locale del dispositivo raggiunto, ma la richiesta non e\' andata a buon fine.');
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

    state.pendingFocus = resolveConversationFocus(text, state.history.slice(-HISTORY_LIMIT));
    state.history.push({
      role: 'user',
      content: text,
      meta: {
        topic: state.pendingFocus.topic || '',
        focusLabel: state.pendingFocus.focusLabel || '',
      },
    });
    saveConversationMemory();
    appendMessage('user', text);

    state.currentBubble = appendMessage('assistant', '');
    state.streaming = true;
    startThinkingFeedback(text);
    if (sendButton) {
      sendButton.disabled = true;
    }

    if (bridgeConfig) {
      sendViaCompanion(text);
      return;
    }

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
        var modelLabel = (data.resolved_models && data.resolved_models.chat) || 'Servizio locale';
        updateBadge(ready, ready ? modelLabel : 'Servizio locale offline');
        setStatus(
          ready
            ? 'Lex e\' collegato al servizio locale di questo dispositivo.'
            : 'Il servizio locale di questo dispositivo non e\' ancora operativo.'
        );
      })
      .catch(function () {
        browserBridge()
          .fetchCompanionPing(bridgeConfig)
          .then(function () {
            updateBadge(false, 'AI locale non pronta');
            setStatus('Local Signer raggiungibile, ma il motore locale non e\' operativo su questo dispositivo.');
          })
          .catch(function () {
            updateBadge(false, 'Servizio locale offline');
            setStatus('Il browser non riesce a raggiungere il servizio locale di questo dispositivo.');
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
          setStatus('Lex e\' pronto sul motore locale di IUSENTRA.');
        } else {
          updateBadge(false, 'Offline');
          setStatus('Motore locale non disponibile su questa installazione.');
        }
      })
      .catch(function () {
        updateBadge(false, 'Offline');
        setStatus('Stato del motore non disponibile in questo momento.');
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

  function clearInlineLayoutStyles() {
    if (!widget) {
      return;
    }
    widget.style.left = '';
    widget.style.top = '';
    widget.style.right = '';
    widget.style.bottom = '';
    widget.style.width = '';
    widget.style.height = '';
  }

  function applyFullscreenState() {
    if (!widget) {
      return;
    }
    widget.classList.toggle('pct-ai-widget--fullscreen', Boolean(state.fullscreen));
    if (fullscreenButton) {
      fullscreenButton.innerHTML = '<i class="bi bi-' + (state.fullscreen ? 'fullscreen-exit' : 'arrows-fullscreen') + '"></i>';
      fullscreenButton.title = state.fullscreen ? 'Esci da tutto schermo' : 'Apri Lex a tutto schermo';
      fullscreenButton.setAttribute('aria-label', fullscreenButton.title);
      fullscreenButton.classList.toggle('is-active', Boolean(state.fullscreen));
    }
  }

  function setFullscreen(nextFullscreen, options) {
    options = options || {};
    state.fullscreen = Boolean(nextFullscreen);
    if (state.fullscreen) {
      clearInlineLayoutStyles();
      if (widget) {
        widget.classList.remove('pct-ai-widget--custom');
      }
    }
    applyFullscreenState();
    if (options.persist !== false) {
      saveLayout({ fullscreen: state.fullscreen });
    }
    if (!state.fullscreen) {
      restorePosition();
    }
    if (!options.silent) {
      setStatus(state.fullscreen ? 'Lex aperta a tutto schermo.' : 'Lex tornata alla dimensione precedente.');
    }
  }

  function toggleFullscreen() {
    setFullscreen(!state.fullscreen);
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

  function resetPosition(options) {
    options = options || {};
    if (!widget) {
      return;
    }

    clearSavedPosition();
    state.fullscreen = false;
    applyFullscreenState();
    widget.classList.remove('pct-ai-widget--custom');
    clearInlineLayoutStyles();
    if (!options.silent) {
      setStatus('Posizione e dimensioni ripristinate in basso a destra.');
    }
  }

  function restorePosition() {
    if (!widget) {
      return;
    }

    var saved = getSavedLayout() || {};
    if (!state.open && saved.fullscreen) {
      saveLayout({ fullscreen: false });
      saved.fullscreen = false;
    }
    state.fullscreen = Boolean(saved.fullscreen && state.open);
    applyFullscreenState();

    if (state.fullscreen) {
      widget.classList.remove('pct-ai-widget--custom');
      clearInlineLayoutStyles();
      return;
    }

    if (!isDesktop()) {
      widget.classList.remove('pct-ai-widget--custom');
      clearInlineLayoutStyles();
      return;
    }

    if (saved && (saved.width || saved.height || saved.left || saved.top)) {
      applyCustomLayout(saved);
    } else {
      widget.classList.remove('pct-ai-widget--custom');
      clearInlineLayoutStyles();
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
    if (!isDesktop() || !widget || event.button !== 0 || state.fullscreen) {
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
    if (!isDesktop() || !widget || event.button !== 0 || state.fullscreen) {
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
    window.addEventListener('iusentra:lex-context', function (event) {
      applyLexPageContext(event && event.detail ? event.detail : {}, { open: false });
    });
    window.addEventListener('iusentra:open-floating-lex', function (event) {
      applyLexPageContext(event && event.detail ? event.detail : readExternalLexContext() || {}, { open: true });
    });
    sendButton.addEventListener('click', send);
    query('pct-ai-close').addEventListener('click', closeAssistant);
    query('pct-ai-clear').addEventListener('click', clearHistory);
    query('pct-ai-reset-position').addEventListener('click', resetPosition);
    if (fullscreenButton) {
      fullscreenButton.addEventListener('click', toggleFullscreen);
    }
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
    if (presetsShelf) {
      presetsShelf.addEventListener('click', function (event) {
        var presetButton = event.target.closest('[data-lex-preset]');
        if (!presetButton) {
          return;
        }
        runPreset(presetButton.getAttribute('data-lex-preset'));
      });
    }
    if (messages) {
      messages.addEventListener('click', function (event) {
        var actionButton = event.target.closest('[data-lex-action]');
        if (actionButton && input) {
          input.value = String(actionButton.getAttribute('data-lex-action') || '').trim();
          autoResize();
          send();
          return;
        }
        var button = event.target.closest('[data-generated-download]');
        var docs = documentsHelper();
        if (!button || !docs) {
          return;
        }
        var bubble = button.closest('.pct-ai-bubble');
        var payload = bubble && bubble._generatedDocument;
        if (!payload) {
          return;
        }
        var format = String(button.getAttribute('data-generated-download') || '');
        if (format === 'md' && docs.downloadGeneratedMarkdown) {
          docs.downloadGeneratedMarkdown(payload);
          setStatus('Documento Markdown generato da Lex scaricato.');
          return;
        }
        if (format === 'docx' && docs.downloadGeneratedDocx) {
          setStatus('Lex sta preparando il documento Word...');
          docs.downloadGeneratedDocx(payload)
            .then(function () {
              setStatus('Documento Word generato da Lex scaricato.');
            })
            .catch(function (error) {
              setStatus('Export Word non riuscito: ' + String((error && error.message) || 'errore sconosciuto'));
            });
        }
      });
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
          silenceMs: 3000,
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
        restorePosition();
      }
    });
    window.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && state.fullscreen) {
        setFullscreen(false, { silent: true });
      }
    });
  }

  function initContext() {
    var match = window.location.pathname.match(/\/fascicoli\/([^/]+)/);
    state.fascId = (match && match[1]) || window.pctAiFascicoloId || null;
    var externalContext = readExternalLexContext();
    applyLexPageContext(externalContext || {
      context: state.fascId ? 'fascicolo' : '',
      pagePath: window.location.pathname,
    }, { open: false });
    if (state.fascId && ctx && ctxLabel) {
      ctx.hidden = false;
      ctxLabel.textContent = 'Contesto fascicolo attivo';
      saveConversationMemory();
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
    presetsShelf = query('pct-ai-presets');
    exportButton = query('pct-ai-export');
    fullscreenButton = query('pct-ai-fullscreen');
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
    restorePosition();
    restoreConversationMemory();
    initContext();
    renderConversation();
    renderAttachments();
    renderPresetPills();
    if (!state.sessionId) {
      state.sessionId = generateSessionId();
    }
    if (!state.history.length && !state.attachments.length) {
      setStatus('Assistente pronto.');
    } else {
      setStatus('Sessione ripristinata.');
    }
    updateVoiceUi();
  }

  window.pctAI = {
    init: init,
    toggle: toggle,
    send: send,
    clearHistory: clearHistory,
    resetPosition: resetPosition,
    toggleFullscreen: toggleFullscreen,
  };

  document.addEventListener('DOMContentLoaded', init);
})();

