(function () {
  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatDateTimeIt(value) {
    if (!value) {
      return 'n.d.';
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return escapeHtml(value);
    }

    return new Intl.DateTimeFormat('it-IT', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(date);
  }

  function formatNumberIt(value, options) {
    if (value === null || value === undefined || value === '') {
      return 'n.d.';
    }

    const numeric = Number(value);
    if (Number.isNaN(numeric)) {
      return escapeHtml(value);
    }

    return new Intl.NumberFormat('it-IT', options || {}).format(numeric);
  }

  function formatBytes(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric) || numeric <= 0) {
      return 'n.d.';
    }

    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let size = numeric;
    let unitIndex = 0;

    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex += 1;
    }

    return formatNumberIt(size, { maximumFractionDigits: size >= 100 ? 0 : 1 }) + ' ' + units[unitIndex];
  }

  function aiStatusMeta(status) {
    const labels = {
      ready: { label: 'Operativo', tone: 'success', icon: 'bi-check-circle-fill' },
      missing: { label: 'Runtime non disponibile', tone: 'warning', icon: 'bi-exclamation-triangle-fill' },
      starting: { label: 'Avvio in corso', tone: 'info', icon: 'bi-arrow-repeat' },
      installing: { label: 'Installazione in corso', tone: 'info', icon: 'bi-box-arrow-in-down' },
      error: { label: 'Errore operativo', tone: 'danger', icon: 'bi-x-octagon-fill' },
      disabled: { label: 'Disattivato', tone: 'secondary', icon: 'bi-pause-circle-fill' },
    };
    return labels[status] || {
      label: escapeHtml(status || 'Stato sconosciuto'),
      tone: 'secondary',
      icon: 'bi-question-circle',
    };
  }

  function aiRoleLabel(role) {
    if (role === 'chat') {
      return 'Conversazione';
    }
    if (role === 'embed') {
      return 'Embeddings';
    }
    return escapeHtml(role || 'Modello');
  }

  function aiInstallStateLabel(state) {
    const labels = {
      ready: 'Pronto',
      missing: 'Assente',
      pulling: 'Download in corso',
      error: 'Errore',
    };
    return labels[state] || escapeHtml(state || 'n.d.');
  }

  function setAiBadge(label, tone) {
    const badge = document.getElementById('ai-runtime-badge');
    if (!badge) {
      return;
    }
    badge.className = 'badge text-bg-' + (tone || 'secondary');
    badge.textContent = label;
  }

  function showAiFeedback(kind, title, body) {
    const stack = document.getElementById('ai-action-feedback');
    if (!stack) {
      return;
    }

    const icon = kind === 'success'
      ? 'bi-check-circle-fill'
      : kind === 'warning'
        ? 'bi-exclamation-triangle-fill'
        : 'bi-info-circle-fill';

    stack.classList.remove('d-none');
    stack.innerHTML =
      '<div class="ui-feedback ui-feedback--' + escapeHtml(kind) + '">' +
      '<div class="ui-feedback__icon"><i class="bi ' + icon + '"></i></div>' +
      '<div class="ui-feedback__content">' +
      '<div class="ui-feedback__title">' + escapeHtml(title) + '</div>' +
      '<div class="ui-feedback__body">' + escapeHtml(body) + '</div>' +
      '</div>' +
      '</div>';
  }

  function getAiRoot() {
    return document.getElementById('ai-panel-root');
  }

  function isLocalHost(hostname) {
    return ['localhost', '127.0.0.1', '::1'].includes(String(hostname || '').toLowerCase());
  }

  function clientPlatform() {
    const source = String(navigator.userAgent || navigator.platform || '').toLowerCase();
    if (source.includes('win')) {
      return 'windows';
    }
    if (source.includes('mac')) {
      return 'macos';
    }
    if (source.includes('linux')) {
      return 'linux';
    }
    return 'unknown';
  }

  function aiUiConfig() {
    const root = getAiRoot();
    const dataset = root ? root.dataset : {};
    const remoteHosted = dataset.aiMode === 'remote' || !isLocalHost(window.location.hostname);
    return {
      remoteHosted,
      localSignerUrl: dataset.localSignerUrl || 'http://127.0.0.1:27272',
      signerDownloadPage: dataset.localSignerDownloadPage || '',
      signerSetupWindows: dataset.localSignerSetupWindows || '',
      signerSetupMacos: dataset.localSignerSetupMacos || '',
      signerSetupLinux: dataset.localSignerSetupLinux || '',
      runtimeStatusUrl: dataset.runtimeStatusUrl || '/api/local-ai/status',
      runtimeBootstrapUrl: dataset.runtimeBootstrapUrl || '/api/local-ai/bootstrap',
    };
  }

  function currentAiSettings() {
    const baseUrlField = document.getElementById('ai_base_url');
    const config = aiUiConfig();
    let baseUrl = baseUrlField ? String(baseUrlField.value || '').trim() : '';
    if (!baseUrl) {
      baseUrl = 'http://127.0.0.1:11434/api';
    }
    if (config.remoteHosted && baseUrl.includes('host.docker.internal')) {
      baseUrl = 'http://127.0.0.1:11434/api';
    }
    return {
      enabled: Boolean(document.getElementById('ai_enabled')?.checked),
      auto_bootstrap: Boolean(document.getElementById('ai_auto_bootstrap')?.checked),
      base_url: baseUrl,
      chat_model: String(document.getElementById('ai_chat_model')?.value || '').trim(),
      embed_model: String(document.getElementById('ai_embed_model')?.value || '').trim(),
      keep_alive: String(document.querySelector('input[name="ai_keep_alive"]')?.value || '10m').trim() || '10m',
      auto_index_documents: Boolean(document.getElementById('ai_auto_index_documents')?.checked),
    };
  }

  async function readJsonResponse(response) {
    let payload = {};
    try {
      payload = await response.json();
    } catch (error) {
      payload = {};
    }

    if (!response.ok || payload.errore) {
      const err = new Error(payload.errore || 'Risposta non valida del servizio AI locale.');
      err.httpStatus = response.status;
      err.payload = payload;
      throw err;
    }

    return payload;
  }

  function installerActionsHtml(installActions) {
    if (!Array.isArray(installActions) || !installActions.length) {
      return '';
    }
    return (
      '<div class="d-flex flex-wrap gap-2 mt-3">' +
      installActions.map(function (action) {
        const tone = action.tone || 'outline-primary';
        return (
          '<a class="btn btn-sm btn-' + escapeHtml(tone) + '" href="' + escapeHtml(action.href || '#') + '" target="_blank" rel="noreferrer">' +
          (action.icon ? '<i class="bi ' + escapeHtml(action.icon) + ' me-2"></i>' : '') +
          escapeHtml(action.label || 'Apri') +
          '</a>'
        );
      }).join('') +
      '</div>'
    );
  }

  function renderLocalAiStatus(payload) {
    const summary = document.getElementById('ai-runtime-summary');
    const installer = document.getElementById('ai-installer-summary');
    const models = document.getElementById('ai-models-summary');
    if (!summary || !installer || !models) {
      return;
    }

    const runtime = payload?.runtime || {};
    const counts = payload?.counts || {};
    const installerData = payload?.installer || {};
    const preferredModels = payload?.preferred_models || {};
    const resolvedModels = payload?.resolved_models || {};
    const runtimeStatus = runtime.status || 'missing';
    const runtimeLive = Boolean(payload?.runtime_online);
    const effectiveBaseUrl = payload?.runtime_base_url_live || payload?.settings?.base_url || 'n.d.';
    const hostPlatform = installerData.host_platform || installerData.platform || 'n.d.';
    const executionPlatform = installerData.execution_platform || installerData.platform || 'n.d.';
    const executionLabel = installerData.containerized ? 'container ' + executionPlatform : executionPlatform;
    const detectedExecutable = installerData.detected_executable || 'Non ancora rilevato';
    const statusMeta = aiStatusMeta(runtimeStatus);
    const chatModelValue = resolvedModels.chat || 'n.d.';
    const embedModelValue = resolvedModels.embed || 'n.d.';
    const preferredChatValue = preferredModels.chat || '';
    const preferredEmbedValue = preferredModels.embed || '';
    const modelMeta = [];
    if (preferredChatValue && preferredChatValue !== chatModelValue) {
      modelMeta.push('Policy preferita ' + escapeHtml(preferredChatValue));
    }
    modelMeta.push(
      preferredEmbedValue && preferredEmbedValue !== embedModelValue
        ? 'Embeddings ' + escapeHtml(embedModelValue) + ' Â· policy ' + escapeHtml(preferredEmbedValue)
        : 'Embeddings ' + escapeHtml(embedModelValue)
    );

    setAiBadge(statusMeta.label, statusMeta.tone);

    summary.innerHTML =
      '<article class="settings-ai-stat settings-ai-stat--' + statusMeta.tone + '">' +
      '<div class="settings-ai-stat__label">Stato operativo</div>' +
      '<div class="settings-ai-stat__value"><i class="bi ' + statusMeta.icon + ' me-2"></i>' + statusMeta.label + '</div>' +
      '<div class="settings-ai-stat__meta">Runtime online: ' + (runtimeLive ? 'si' : 'no') + '</div>' +
      '</article>' +
      '<article class="settings-ai-stat">' +
      '<div class="settings-ai-stat__label">Versione live</div>' +
      '<div class="settings-ai-stat__value">' + escapeHtml(payload?.runtime_version_live || 'n.d.') + '</div>' +
      '<div class="settings-ai-stat__meta">Ultimo controllo: ' + formatDateTimeIt(runtime.last_health_check_at) + '</div>' +
      '</article>' +
      '<article class="settings-ai-stat">' +
      '<div class="settings-ai-stat__label">Profilo hardware</div>' +
      '<div class="settings-ai-stat__value">' + escapeHtml(runtime.hardware_profile || 'n.d.') + '</div>' +
      '<div class="settings-ai-stat__meta">RAM ' + formatNumberIt(runtime.ram_gb, { maximumFractionDigits: 1 }) + ' GB Â· Disco libero ' + formatNumberIt(runtime.disk_free_gb, { maximumFractionDigits: 1 }) + ' GB</div>' +
      '</article>' +
      '<article class="settings-ai-stat">' +
      '<div class="settings-ai-stat__label">Documenti indicizzati</div>' +
      '<div class="settings-ai-stat__value">' + formatNumberIt(counts.documents_total ?? 0) + '</div>' +
      '<div class="settings-ai-stat__meta">Chunk totali ' + formatNumberIt(counts.chunks_total ?? 0) + '</div>' +
      '</article>' +
      '<article class="settings-ai-stat">' +
      '<div class="settings-ai-stat__label">Embeddings pronti</div>' +
      '<div class="settings-ai-stat__value">' + formatNumberIt(counts.chunks_embedded ?? 0) + '</div>' +
      '<div class="settings-ai-stat__meta">Chunk in coda ' + formatNumberIt(counts.chunks_pending ?? 0) + '</div>' +
      '</article>' +
      '<article class="settings-ai-stat">' +
      '<div class="settings-ai-stat__label">Modello operativo</div>' +
      '<div class="settings-ai-stat__value">' + escapeHtml(chatModelValue) + '</div>' +
      '<div class="settings-ai-stat__meta">' + modelMeta.join(' Â· ') + '</div>' +
      '</article>' +
      '<article class="settings-ai-stat">' +
      '<div class="settings-ai-stat__label">Runtime collegato</div>' +
      '<div class="settings-ai-stat__value settings-ai-installer__value--mono">' + escapeHtml(effectiveBaseUrl) + '</div>' +
      '<div class="settings-ai-stat__meta">Host reale ' + escapeHtml(hostPlatform) + ' Â· Ambiente IUSENTRA ' + escapeHtml(executionLabel) + '</div>' +
      '</article>' +
      (runtime.last_error
        ? '<article class="settings-ai-stat settings-ai-stat--danger settings-ai-stat--full">' +
          '<div class="settings-ai-stat__label">Ultimo errore</div>' +
          '<div class="settings-ai-stat__meta">' + escapeHtml(runtime.last_error) + '</div>' +
          '</article>'
        : '');

    installer.innerHTML =
      '<div class="settings-ai-installer__hero">' +
      '<div class="settings-ai-installer__title">' + escapeHtml(installerData.summary_title || 'Provisioning locale') + '</div>' +
      '<div class="settings-ai-installer__body">' + escapeHtml(installerData.summary_body || 'Informazioni di provisioning non disponibili.') + '</div>' +
      '</div>' +
      '<div class="settings-ai-installer__grid">' +
      '<div class="settings-ai-installer__item"><div class="settings-ai-installer__label">Strategia</div><div class="settings-ai-installer__value">' + escapeHtml(installerData.strategy_label || 'n.d.') + '</div></div>' +
      '<div class="settings-ai-installer__item"><div class="settings-ai-installer__label">Versione ufficiale rilevata</div><div class="settings-ai-installer__value">' + escapeHtml(installerData.latest_version || 'n.d.') + '</div><div class="settings-ai-installer__meta">' + formatDateTimeIt(installerData.latest_published_at) + '</div></div>' +
      '<div class="settings-ai-installer__item"><div class="settings-ai-installer__label">' + escapeHtml(installerData.asset_label || 'Pacchetto consigliato') + '</div><div class="settings-ai-installer__value">' + escapeHtml(installerData.asset_name || 'n.d.') + '</div><div class="settings-ai-installer__meta">' + formatBytes(installerData.asset_size_bytes) + '</div></div>' +
      '<div class="settings-ai-installer__item"><div class="settings-ai-installer__label">Percorso gestito</div><div class="settings-ai-installer__value settings-ai-installer__value--mono">' + escapeHtml(installerData.managed_runtime_dir || 'n.d.') + '</div></div>' +
      '<div class="settings-ai-installer__item"><div class="settings-ai-installer__label">Host reale</div><div class="settings-ai-installer__value">' + escapeHtml(hostPlatform) + '</div><div class="settings-ai-installer__meta">Architettura ' + escapeHtml(installerData.host_machine || installerData.machine || 'n.d.') + '</div></div>' +
      '<div class="settings-ai-installer__item"><div class="settings-ai-installer__label">Ambiente IUSENTRA</div><div class="settings-ai-installer__value">' + escapeHtml(executionLabel) + '</div><div class="settings-ai-installer__meta">' + (installerData.containerized ? 'Runtime applicativo in container' : 'Runtime applicativo nativo') + '</div></div>' +
      '<div class="settings-ai-installer__item settings-ai-installer__item--full"><div class="settings-ai-installer__label">Eseguibile rilevato</div><div class="settings-ai-installer__value settings-ai-installer__value--mono">' + escapeHtml(detectedExecutable) + '</div></div>' +
      '<div class="settings-ai-installer__item settings-ai-installer__item--full"><div class="settings-ai-installer__label">Ambito di distribuzione</div><div class="settings-ai-installer__body">' + escapeHtml(installerData.distribution_scope || '') + '</div></div>' +
      (installerData.post_install_note
        ? '<div class="settings-ai-installer__item settings-ai-installer__item--full"><div class="settings-ai-installer__label">Dopo l\'installazione</div><div class="settings-ai-installer__body">' + escapeHtml(installerData.post_install_note) + '</div></div>'
        : '') +
      '</div>' +
      (installerData.asset_download_url
        ? '<a class="btn btn-sm btn-outline-primary mt-3" href="' + escapeHtml(installerData.asset_download_url) + '" target="_blank" rel="noreferrer"><i class="bi bi-box-arrow-up-right me-2"></i>' + escapeHtml(installerData.asset_cta_label || 'Apri il download ufficiale') + '</a>'
        : '') +
      installerActionsHtml(installerData.install_actions);

    const rows = (payload?.models || []).map(function (row) {
      return '<article class="settings-ai-model">' +
        '<div class="settings-ai-model__title">' + escapeHtml(row.model_name) + '</div>' +
        '<div class="settings-ai-model__meta">' + aiRoleLabel(row.role) + ' Â· ' + aiInstallStateLabel(row.install_state) + (row.is_active ? ' Â· attivo' : '') + '</div>' +
        (row.last_verified_at ? '<div class="settings-ai-model__foot">Ultima verifica ' + formatDateTimeIt(row.last_verified_at) + '</div>' : '') +
        '</article>';
    });

    models.innerHTML = rows.length ? rows.join('') : '<div class="settings-ai-empty">Nessun modello registrato al momento.</div>';
  }

  function companionUnavailablePayload(reason, outdated) {
    const config = aiUiConfig();
    const platformKey = clientPlatform();
    const preferredHref = platformKey === 'windows'
      ? config.signerSetupWindows
      : platformKey === 'macos'
        ? config.signerSetupMacos
        : config.signerSetupLinux;

    return {
      settings: currentAiSettings(),
      runtime: {
        status: 'missing',
        hardware_profile: 'n.d.',
        ram_gb: null,
        disk_free_gb: null,
        last_health_check_at: new Date().toISOString(),
        last_error: outdated
          ? 'Il Local Signer e\' installato ma va aggiornato per supportare il bridge AI locale.'
          : 'Il browser non riesce a raggiungere il Local Signer su questo dispositivo.',
      },
      runtime_online: false,
      runtime_version_live: '',
      runtime_base_url_live: '',
      counts: {
        documents_total: 0,
        chunks_total: 0,
        chunks_embedded: 0,
        chunks_pending: 0,
      },
      resolved_models: {
        chat: currentAiSettings().chat_model || 'gemma3:1b',
        embed: currentAiSettings().embed_model || 'embeddinggemma:300m',
      },
      models: [],
      installer: {
        strategy_label: 'Companion locale sul dispositivo cliente',
        summary_title: outdated ? 'Aggiornamento Local Signer richiesto' : 'Companion locale non rilevato',
        summary_body: outdated
          ? 'La web app online ha trovato un Local Signer raggiungibile, ma la versione installata non espone ancora il bridge AI locale. Aggiornalo dal pacchetto ufficiale e poi ripeti il controllo.'
          : 'Quando IUSENTRA e\' online, il browser deve parlare con il Local Signer sul dispositivo cliente. Installa o avvia il companion locale su questa macchina e poi ripeti il controllo.',
        distribution_scope: reason || 'Il runtime AI resta sul dispositivo cliente e non viene eseguito dal browser.',
        host_platform: platformKey,
        host_machine: 'n.d.',
        execution_platform: platformKey,
        containerized: false,
        managed_runtime_dir: 'Companion locale richiesto sul dispositivo cliente',
        install_actions: [
          preferredHref ? {
            label: outdated ? 'Aggiorna Local Signer su questo dispositivo' : 'Installa Local Signer su questo dispositivo',
            href: preferredHref,
            icon: platformKey === 'windows' ? 'bi-windows' : platformKey === 'macos' ? 'bi-apple' : 'bi-terminal',
            tone: 'primary',
          } : null,
          config.signerDownloadPage ? {
            label: 'Apri la pagina ufficiale dei pacchetti',
            href: config.signerDownloadPage,
            icon: 'bi-box-arrow-up-right',
            tone: 'outline-secondary',
          } : null,
        ].filter(Boolean),
      },
    };
  }

  async function fetchCompanionStatus() {
    const config = aiUiConfig();
    const params = new URLSearchParams(currentAiSettings());
    const response = await fetch(config.localSignerUrl + '/ai/status?' + params.toString(), {
      method: 'GET',
    });
    return readJsonResponse(response);
  }

  async function fetchServerStatus() {
    const config = aiUiConfig();
    const response = await fetch(config.runtimeStatusUrl, {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    });
    return readJsonResponse(response);
  }

  async function refreshLocalAiStatus(showMessage) {
    if (!document.getElementById('ai-runtime-summary')) {
      return;
    }

    const config = aiUiConfig();
    setAiBadge('Verifica in corso', 'secondary');

    try {
      const payload = config.remoteHosted ? await fetchCompanionStatus() : await fetchServerStatus();
      renderLocalAiStatus(payload);
      if (showMessage) {
        showAiFeedback(
          'success',
          'Stato aggiornato',
          config.remoteHosted
            ? 'Il pannello AI locale e\' stato aggiornato leggendo il companion sul dispositivo cliente.'
            : 'Il pannello AI locale e\' stato aggiornato con lo stato reale del runtime e dell\'indice documentale.'
        );
      }
    } catch (error) {
      if (config.remoteHosted) {
        const payload = companionUnavailablePayload(
          'Companion locale non raggiungibile dal browser su http://127.0.0.1:27272.',
          Number(error.httpStatus || 0) === 404
        );
        renderLocalAiStatus(payload);
        showAiFeedback(
          'warning',
          Number(error.httpStatus || 0) === 404 ? 'Aggiornamento richiesto' : 'Companion locale non raggiungibile',
          Number(error.httpStatus || 0) === 404
            ? 'Il Local Signer risponde ma non supporta ancora il bridge AI locale. Aggiornalo da questo dispositivo e poi ripeti il controllo.'
            : 'La web app online non puo\' leggere Ollama direttamente dal server. Installa o avvia il Local Signer su questo dispositivo e poi ripeti il controllo.'
        );
        return;
      }

      setAiBadge('Errore runtime', 'danger');
      const summary = document.getElementById('ai-runtime-summary');
      if (summary) {
        summary.innerHTML = '<div class="settings-ai-empty text-danger">Non e\' stato possibile leggere lo stato dell\'AI locale.</div>';
      }
      showAiFeedback(
        'danger',
        'Controllo non riuscito',
        'Non sono riuscito a leggere lo stato del runtime locale. Verifica il servizio Ollama sulla stessa macchina di IUSENTRA oppure riprova tra pochi istanti.'
      );
    }
  }

  async function runLocalAiBootstrap() {
    const button = document.getElementById('ai-bootstrap-btn');
    if (button) {
      button.disabled = true;
    }

    const config = aiUiConfig();
    setAiBadge('Preparazione in corso', 'info');
    showAiFeedback(
      'warning',
      'Preparazione runtime in corso',
      config.remoteHosted
        ? 'Sto chiedendo al companion locale di verificare Ollama e i modelli su questo dispositivo, senza coinvolgere il server Railway.'
        : 'Sto verificando la strategia corretta per questa macchina e la disponibilita\' dei modelli locali.'
    );

    try {
      let payload;
      if (config.remoteHosted) {
        const response = await fetch(config.localSignerUrl + '/ai/bootstrap', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(Object.assign({}, currentAiSettings(), { force: true })),
        });
        payload = await readJsonResponse(response);
      } else {
        const response = await fetch(config.runtimeBootstrapUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify({ force: true }),
        });
        payload = await readJsonResponse(response);
      }

      renderLocalAiStatus(payload.status_payload || payload);
      const result = payload?.result || {};
      const meta = aiStatusMeta(result.status || 'ready');
      showAiFeedback(
        meta.tone === 'danger' ? 'danger' : meta.tone === 'warning' ? 'warning' : 'success',
        meta.label,
        result.status === 'ready'
          ? 'Il runtime locale e i modelli richiesti risultano pronti sul dispositivo corrente.'
          : (result.error || 'La procedura e\' terminata ma il runtime richiede ancora una verifica operativa.')
      );
    } catch (error) {
      if (config.remoteHosted) {
        const payload = companionUnavailablePayload(
          'Il browser non riesce a raggiungere il Local Signer su questo dispositivo.',
          Number(error.httpStatus || 0) === 404
        );
        renderLocalAiStatus(payload);
        showAiFeedback(
          'warning',
          'Companion locale necessario',
          'Per la versione online di IUSENTRA il bootstrap AI deve passare dal Local Signer sul dispositivo cliente. Installa o aggiorna il companion locale e poi ripeti la procedura.'
        );
      } else {
        setAiBadge('Preparazione fallita', 'danger');
        showAiFeedback(
          'danger',
          'Preparazione non riuscita',
          'Non sono riuscito a completare la preparazione del runtime locale. Il gestionale resta operativo e puoi riprovare senza interrompere il lavoro.'
        );
      }
    } finally {
      if (button) {
        button.disabled = false;
      }
      await refreshLocalAiStatus(false);
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (document.getElementById('ai-runtime-summary')) {
      refreshLocalAiStatus(false);
    }
  });

  window.refreshLocalAiStatus = refreshLocalAiStatus;
  window.runLocalAiBootstrap = runLocalAiBootstrap;
})();

