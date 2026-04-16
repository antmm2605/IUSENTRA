(function () {
  function root() {
    return document.getElementById('fascicolo-ai-root');
  }

  function bridge() {
    return window.HacsLocalAiBrowserBridge;
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, function (char) {
      return {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      }[char];
    });
  }

  function answerEl() {
    return document.getElementById('fascicolo-ai-answer');
  }

  function runtimeEl() {
    return document.getElementById('fascicolo-ai-runtime');
  }

  function showAnswerHtml(html) {
    const target = answerEl();
    if (target) {
      target.innerHTML = html;
    }
  }

  function renderSources(payload) {
    const citations = (payload.citations || []).map(function (item) {
      return '<li>' + escapeHtml(item) + '</li>';
    }).join('');
    return citations
      ? '<div class="mt-3"><div class="fw-semibold mb-1">Fonti</div><ul class="small mb-0">' + citations + '</ul></div>'
      : '';
  }

  function renderUnsupportedItems(items) {
    const rows = (items || []).slice(0, 6).map(function (item) {
      return (
        '<li>' +
          '<span class="fw-semibold">' + escapeHtml(item.nome || item.file_path || 'Documento') + '</span>' +
          '<div class="small text-muted">' + escapeHtml(item.reason || 'Formato non supportato') + '</div>' +
        '</li>'
      );
    }).join('');
    if (!rows) {
      return '';
    }
    return (
      '<div class="mt-3">' +
        '<div class="fw-semibold mb-1">Documenti da presidiare</div>' +
        '<ul class="small mb-0 ps-3">' + rows + '</ul>' +
      '</div>'
    );
  }

  function renderCompanionHelp(config, outdated) {
    const help = bridge().companionHelp(config, { outdated: outdated });
    return (
      '<div class="text-danger fw-semibold mb-2">' + escapeHtml(help.title) + '</div>' +
      '<div class="small text-muted">' + escapeHtml(help.body) + '</div>' +
      (help.actionUrl
        ? '<div class="mt-3"><a class="btn btn-sm btn-outline-primary" href="' + escapeHtml(help.actionUrl) + '" target="_blank" rel="noreferrer">' +
          '<i class="bi bi-box-arrow-up-right me-2"></i>' + escapeHtml(help.actionLabel) +
          '</a></div>'
        : '')
    );
  }

  function renderCompanionRuntimeHelp(error) {
    const issue = bridge() && typeof bridge().companionRuntimeHelp === 'function'
      ? bridge().companionRuntimeHelp(error)
      : {
          title: 'Companion locale raggiunto, ma la richiesta non e\' andata a buon fine',
          body: 'Il Local Signer e\' stato contattato correttamente, ma il modulo AI locale ha restituito un errore operativo.',
          detail: String((error && error.message) || 'Errore operativo del modulo AI locale.'),
        };
    return (
      '<div class="text-warning fw-semibold mb-2">' + escapeHtml(issue.title) + '</div>' +
      '<div class="small text-muted">' + escapeHtml(issue.body) + '</div>' +
      '<div class="small mt-2"><code>' + escapeHtml(issue.detail) + '</code></div>'
    );
  }

  async function refreshFascicoloAiRuntime() {
    const target = runtimeEl();
    const currentRoot = root();
    if (!target || !currentRoot || !bridge()) {
      return;
    }
    const config = bridge().rootConfig(currentRoot);
    target.textContent = 'Verifica del runtime AI in corso...';
    try {
      const payload = await bridge().fetchRuntimeStatus(config);
      const runtime = payload.runtime || {};
      target.textContent = 'Runtime locale: ' + bridge().runtimeLabel(runtime) + ' · profilo ' + (runtime.hardware_profile || 'n.d.');
    } catch (error) {
      target.textContent = config.remoteHosted
        ? 'Companion locale non raggiungibile su questo dispositivo'
        : 'Runtime locale non disponibile';
    }
  }

  async function askFascicoloAi(fascicoloId) {
    const currentRoot = root();
    const questionField = document.getElementById('fascicolo-ai-question');
    const button = document.getElementById('fascicolo-ai-ask-btn');
    if (!currentRoot || !questionField || !button || !bridge()) {
      return;
    }

    const question = String(questionField.value || '').trim();
    if (!question) {
      showAnswerHtml('<span class="text-danger">Inserisci una domanda sul fascicolo.</span>');
      return;
    }

    const config = bridge().rootConfig(currentRoot);
    button.disabled = true;
    showAnswerHtml('<div class="small text-muted">Analisi del fascicolo in corso...</div>');

    try {
      let payload;
      if (config.remoteHosted) {
        const prepared = await bridge().fetchServerContext(config, { question: question, fascicolo_id: fascicoloId });
        payload = await bridge().runCompanionRagQuery(config, prepared);
      } else {
        payload = await bridge().fetchServerAnswer(config, { question: question, fascicolo_id: fascicoloId });
      }

      showAnswerHtml(
        '<div class="small text-dark hacs-local-ai-answer-text">' + escapeHtml(payload.answer || '') + '</div>' +
        renderSources(payload)
      );
      refreshFascicoloAiRuntime();
    } catch (error) {
      const outdated = Number(error.httpStatus || 0) === 404;
      if (!config.remoteHosted) {
        showAnswerHtml('<span class="text-danger">Errore durante l\'analisi AI del fascicolo.</span>');
      } else if (outdated) {
        showAnswerHtml(renderCompanionHelp(config, true));
      } else if (bridge().isCompanionTransportError(error)) {
        showAnswerHtml(renderCompanionHelp(config, false));
      } else {
        showAnswerHtml(renderCompanionRuntimeHelp(error));
      }
    } finally {
      button.disabled = false;
    }
  }

  async function reindexFascicoloAi(fascicoloId) {
    const currentRoot = root();
    if (!currentRoot || !bridge()) {
      return;
    }
    const config = bridge().rootConfig(currentRoot);
    showAnswerHtml('<div class="small text-muted">Aggiorno l\'indice documentale del fascicolo...</div>');
    try {
      const payload = await bridge().runServerReindex(config, { fascicolo_id: fascicoloId, force: true });
      if (!payload.ok) {
        showAnswerHtml('<span class="text-danger">' + escapeHtml(payload.errore || 'Reindicizzazione non riuscita.') + '</span>');
        return;
      }
      const docs = payload.result && payload.result.documents ? payload.result.documents : {};
      const embeds = payload.result && payload.result.embeddings ? payload.result.embeddings : {};
      const embedLabel = config.remoteHosted
        ? 'Il testo e\' stato aggiornato sul server. La risposta finale usera\' il companion locale del dispositivo.'
        : 'Embedding pronti: ' + escapeHtml(String(embeds.embedded || 0));
      showAnswerHtml(
        '<div class="text-success">Indice fascicolo aggiornato correttamente.</div>' +
        '<div class="small mt-2">Documenti indicizzati: ' + escapeHtml(String(docs.indexed || 0)) +
        ' · documenti invariati: ' + escapeHtml(String(docs.skipped || 0)) +
        ' · non supportati: ' + escapeHtml(String(docs.unsupported || 0)) + '</div>' +
        '<div class="small mt-2 text-muted">' + embedLabel + '</div>' +
        renderUnsupportedItems(docs.unsupported_items || [])
      );
      refreshFascicoloAiRuntime();
    } catch (error) {
      showAnswerHtml('<span class="text-danger">Errore durante la reindicizzazione del fascicolo.</span>');
    }
  }

  window.askFascicoloAi = askFascicoloAi;
  window.reindexFascicoloAi = reindexFascicoloAi;
  window.refreshFascicoloAiRuntime = refreshFascicoloAiRuntime;
})();
