(function () {
  function root() {
    return document.getElementById('workspace-ai-root');
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

  function renderSources(payload) {
    const citations = (payload.citations || []).map(function (item) {
      return '<li>' + escapeHtml(item) + '</li>';
    }).join('');
    return citations
      ? '<div class="mt-3"><div class="fw-semibold mb-1">Fonti</div><ul class="small mb-0">' + citations + '</ul></div>'
      : '';
  }

  function renderCompanionHelp(config, outdated) {
    const help = bridge().companionHelp(config, { outdated: outdated });
    return (
      '<div class="wi-answer-muted text-danger fw-semibold mb-2">' + escapeHtml(help.title) + '</div>' +
      '<div class="wi-answer-muted">' + escapeHtml(help.body) + '</div>' +
      (help.actionUrl
        ? '<div class="mt-3"><a class="btn btn-sm btn-outline-primary" href="' + escapeHtml(help.actionUrl) + '" target="_blank" rel="noreferrer">' +
          '<i class="bi bi-box-arrow-up-right me-2"></i>' + escapeHtml(help.actionLabel) +
          '</a></div>'
        : '')
    );
  }

  async function refreshWorkspaceAiRuntime() {
    const currentRoot = root();
    const status = document.getElementById('workspace-ai-status');
    if (!currentRoot || !status || !bridge()) {
      return;
    }
    const config = bridge().rootConfig(currentRoot);
    status.textContent = 'Verifica del runtime locale in corso...';
    try {
      const payload = await bridge().fetchRuntimeStatus(config);
      const runtime = payload.runtime || {};
      status.textContent = 'Runtime locale: ' + bridge().runtimeLabel(runtime) + ' · profilo ' + (runtime.hardware_profile || 'n.d.');
    } catch (error) {
      status.textContent = config.remoteHosted
        ? 'Companion locale non raggiungibile su questo dispositivo'
        : 'Runtime locale non disponibile';
    }
  }

  async function askWorkspaceAi() {
    const currentRoot = root();
    const questionField = document.getElementById('workspace-ai-question');
    const answer = document.getElementById('workspace-ai-answer');
    const button = document.getElementById('workspace-ai-ask-btn');
    if (!currentRoot || !questionField || !answer || !button || !bridge()) {
      return;
    }
    const question = String(questionField.value || '').trim();
    if (!question) {
      answer.innerHTML = '<div class="wi-answer-muted text-danger">Inserisci una domanda operativa per ottenere una risposta contestuale.</div>';
      return;
    }

    const config = bridge().rootConfig(currentRoot);
    button.disabled = true;
    answer.innerHTML = '<div class="wi-answer-muted">Analisi della cabina intelligente in corso...</div>';

    try {
      let payload;
      if (config.remoteHosted) {
        const prepared = await bridge().fetchServerContext(config, {
          question: question,
          giorni: Number(currentRoot.dataset.horizonDays || 14),
        });
        payload = await bridge().runCompanionRagQuery(config, prepared);
      } else {
        payload = await bridge().fetchServerAnswer(config, {
          question: question,
          giorni: Number(currentRoot.dataset.horizonDays || 14),
        });
      }

      answer.innerHTML =
        '<div class="wi-answer-text">' + escapeHtml(payload.answer || '') + '</div>' +
        renderSources(payload);
      refreshWorkspaceAiRuntime();
    } catch (error) {
      const outdated = Number(error.httpStatus || 0) === 404;
      answer.innerHTML = config.remoteHosted
        ? renderCompanionHelp(config, outdated)
        : '<div class="wi-answer-muted text-danger">Errore durante l\'analisi AI della cabina intelligente.</div>';
    } finally {
      button.disabled = false;
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (!root() || !bridge()) {
      return;
    }
    refreshWorkspaceAiRuntime();
  });

  window.askWorkspaceAi = askWorkspaceAi;
  window.refreshWorkspaceAiRuntime = refreshWorkspaceAiRuntime;
})();
