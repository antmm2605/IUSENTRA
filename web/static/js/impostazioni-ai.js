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

  async function readJsonResponse(response) {
    let payload = {};
    try {
      payload = await response.json();
    } catch (error) {
      payload = {};
    }

    if (!response.ok || payload.errore) {
      throw new Error(payload.errore || 'Risposta non valida del servizio AI locale.');
    }

    return payload;
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
    const resolvedModels = payload?.resolved_models || {};
    const runtimeStatus = runtime.status || 'missing';
    const runtimeLive = Boolean(payload?.runtime_online);
    const effectiveBaseUrl = payload?.runtime_base_url_live || payload?.settings?.base_url || 'n.d.';
    const hostPlatform = installerData.host_platform || installerData.platform || 'n.d.';
    const executionPlatform = installerData.execution_platform || installerData.platform || 'n.d.';
    const executionLabel = installerData.containerized ? 'container ' + executionPlatform : executionPlatform;
    const dockerStrategy = installerData.strategy_code === 'docker_service';
    const hostBridgeStrategy = ['host_bridge_windows', 'host_bridge_darwin'].includes(installerData.strategy_code || '');
    const detectedExecutable = installerData.detected_executable || (
      dockerStrategy
        ? 'Non richiesto: sidecar Docker opzionale'
        : hostBridgeStrategy
          ? 'Gestito sul sistema host Windows o macOS, non dentro il container'
          : 'Non ancora rilevato'
    );
    const installerAssetLabel = dockerStrategy
      ? 'Servizio consigliato'
      : hostBridgeStrategy
        ? 'Runtime host consigliato'
        : 'Pacchetto consigliato';
    const installerAssetMeta = installerData.asset_size_bytes
      ? formatBytes(installerData.asset_size_bytes)
      : dockerStrategy
        ? 'Immagine ufficiale'
        : hostBridgeStrategy
          ? 'Pacchetto host ufficiale'
          : 'n.d.';
    const statusMeta = aiStatusMeta(runtimeStatus);

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
      '<div class="settings-ai-stat__meta">RAM ' + formatNumberIt(runtime.ram_gb, { maximumFractionDigits: 1 }) + ' GB · Disco libero ' + formatNumberIt(runtime.disk_free_gb, { maximumFractionDigits: 1 }) + ' GB</div>' +
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
      '<div class="settings-ai-stat__label">Policy attiva</div>' +
      '<div class="settings-ai-stat__value">' + escapeHtml(resolvedModels.chat || 'n.d.') + '</div>' +
      '<div class="settings-ai-stat__meta">Embeddings ' + escapeHtml(resolvedModels.embed || 'n.d.') + '</div>' +
      '</article>' +
      '<article class="settings-ai-stat">' +
      '<div class="settings-ai-stat__label">Runtime collegato</div>' +
      '<div class="settings-ai-stat__value settings-ai-installer__value--mono">' + escapeHtml(effectiveBaseUrl) + '</div>' +
      '<div class="settings-ai-stat__meta">Host reale ' + escapeHtml(hostPlatform) + ' · Ambiente HACS ' + escapeHtml(executionLabel) + '</div>' +
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
      '<div class="settings-ai-installer__item">' +
      '<div class="settings-ai-installer__label">Strategia</div>' +
      '<div class="settings-ai-installer__value">' + escapeHtml(installerData.strategy_label || 'n.d.') + '</div>' +
      '</div>' +
      '<div class="settings-ai-installer__item">' +
      '<div class="settings-ai-installer__label">Versione ufficiale rilevata</div>' +
      '<div class="settings-ai-installer__value">' + escapeHtml(installerData.latest_version || 'n.d.') + '</div>' +
      '<div class="settings-ai-installer__meta">' + formatDateTimeIt(installerData.latest_published_at) + '</div>' +
      '</div>' +
      '<div class="settings-ai-installer__item">' +
      '<div class="settings-ai-installer__label">' + installerAssetLabel + '</div>' +
      '<div class="settings-ai-installer__value">' + escapeHtml(installerData.asset_name || 'n.d.') + '</div>' +
      '<div class="settings-ai-installer__meta">' + installerAssetMeta + '</div>' +
      '</div>' +
      '<div class="settings-ai-installer__item">' +
      '<div class="settings-ai-installer__label">Percorso gestito</div>' +
      '<div class="settings-ai-installer__value settings-ai-installer__value--mono">' + escapeHtml(installerData.managed_runtime_dir || 'n.d.') + '</div>' +
      '</div>' +
      '<div class="settings-ai-installer__item">' +
      '<div class="settings-ai-installer__label">Host reale</div>' +
      '<div class="settings-ai-installer__value">' + escapeHtml(hostPlatform) + '</div>' +
      '<div class="settings-ai-installer__meta">Architettura ' + escapeHtml(installerData.host_machine || installerData.machine || 'n.d.') + '</div>' +
      '</div>' +
      '<div class="settings-ai-installer__item">' +
      '<div class="settings-ai-installer__label">Ambiente HACS</div>' +
      '<div class="settings-ai-installer__value">' + escapeHtml(executionLabel) + '</div>' +
      '<div class="settings-ai-installer__meta">' + (installerData.containerized ? 'Runtime applicativo in container' : 'Runtime applicativo nativo') + '</div>' +
      '</div>' +
      '<div class="settings-ai-installer__item settings-ai-installer__item--full">' +
      '<div class="settings-ai-installer__label">Eseguibile rilevato</div>' +
      '<div class="settings-ai-installer__value settings-ai-installer__value--mono">' + escapeHtml(detectedExecutable) + '</div>' +
      '</div>' +
      '<div class="settings-ai-installer__item settings-ai-installer__item--full">' +
      '<div class="settings-ai-installer__label">Ambito di distribuzione</div>' +
      '<div class="settings-ai-installer__body">' + escapeHtml(installerData.distribution_scope || '') + '</div>' +
      '</div>' +
      '</div>' +
      (installerData.asset_download_url
        ? '<a class="btn btn-sm btn-outline-primary mt-3" href="' + escapeHtml(installerData.asset_download_url) + '" target="_blank" rel="noreferrer">' +
          '<i class="bi bi-box-arrow-up-right me-2"></i>' + (dockerStrategy ? 'Apri la pagina ufficiale del servizio' : 'Apri il download ufficiale') +
          '</a>'
        : '');

    const rows = (payload?.models || []).map(function (row) {
      return '<article class="settings-ai-model">' +
        '<div class="settings-ai-model__title">' + escapeHtml(row.model_name) + '</div>' +
        '<div class="settings-ai-model__meta">' + aiRoleLabel(row.role) + ' · ' + aiInstallStateLabel(row.install_state) + (row.is_active ? ' · attivo' : '') + '</div>' +
        (row.last_verified_at ? '<div class="settings-ai-model__foot">Ultima verifica ' + formatDateTimeIt(row.last_verified_at) + '</div>' : '') +
        '</article>';
    });

    models.innerHTML = rows.length ? rows.join('') : '<div class="settings-ai-empty">Nessun modello registrato al momento.</div>';
  }

  async function refreshLocalAiStatus(showMessage) {
    if (!document.getElementById('ai-runtime-summary')) {
      return;
    }

    setAiBadge('Verifica in corso', 'secondary');
    try {
      const response = await fetch('/api/local-ai/status', {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      const payload = await readJsonResponse(response);
      renderLocalAiStatus(payload);

      if (showMessage) {
        showAiFeedback(
          'success',
          'Stato aggiornato',
          'Il pannello AI locale e\' stato aggiornato con lo stato reale del runtime, dell\'ambiente host e dell\'indice documentale.'
        );
      }
    } catch (error) {
      setAiBadge('Errore runtime', 'danger');
      const summary = document.getElementById('ai-runtime-summary');
      if (summary) {
        summary.innerHTML = '<div class="settings-ai-empty text-danger">Non e\' stato possibile leggere lo stato dell\'AI locale.</div>';
      }
      showAiFeedback(
        'danger',
        'Controllo non riuscito',
        'Non sono riuscito a leggere lo stato del runtime locale. Verifica il servizio Ollama sulla stessa macchina di HACS oppure riprova tra pochi istanti.'
      );
    }
  }

  async function runLocalAiBootstrap() {
    const button = document.getElementById('ai-bootstrap-btn');
    if (button) {
      button.disabled = true;
    }

    setAiBadge('Preparazione in corso', 'info');
    showAiFeedback(
      'warning',
      'Preparazione runtime in corso',
      'Sto verificando la strategia corretta per questa macchina: runtime nativo sull\'host reale oppure sidecar Docker solo se davvero necessario, insieme ai modelli richiesti per il profilo hardware corrente.'
    );

    try {
      const response = await fetch('/api/local-ai/bootstrap', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({ force: true }),
      });
      const payload = await readJsonResponse(response);
      renderLocalAiStatus(payload.status_payload || payload);

      const result = payload?.result || {};
      const meta = aiStatusMeta(result.status || 'ready');
      const message = result.status === 'ready'
        ? 'Il runtime locale e\' stato preparato correttamente e i modelli richiesti risultano disponibili.'
        : (result.error || 'La procedura e\' terminata, ma il runtime richiede ancora un controllo operativo.');

      showAiFeedback(
        meta.tone === 'danger' ? 'danger' : meta.tone === 'warning' ? 'warning' : 'success',
        meta.label,
        message
      );
    } catch (error) {
      setAiBadge('Preparazione fallita', 'danger');
      showAiFeedback(
        'danger',
        'Preparazione non riuscita',
        'Non sono riuscito a completare la preparazione del runtime locale. Il gestionale resta operativo e puoi riprovare senza interrompere il lavoro.'
      );
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
