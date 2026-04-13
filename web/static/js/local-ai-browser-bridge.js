(function () {
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

  function rootConfig(root) {
    const dataset = root ? root.dataset : {};
    return {
      remoteHosted: dataset.aiMode === 'remote' || !isLocalHost(window.location.hostname),
      localSignerUrl: dataset.localSignerUrl || 'http://127.0.0.1:27272',
      signerDownloadPage: dataset.localSignerDownloadPage || '',
      signerSetupWindows: dataset.localSignerSetupWindows || '',
      signerSetupMacos: dataset.localSignerSetupMacos || '',
      signerSetupLinux: dataset.localSignerSetupLinux || '',
      runtimeStatusUrl: dataset.runtimeStatusUrl || '/api/local-ai/status',
      runtimeBootstrapUrl: dataset.runtimeBootstrapUrl || '/api/local-ai/bootstrap',
      serverAskUrl: dataset.serverAskUrl || '',
      serverContextUrl: dataset.serverContextUrl || '',
      serverReindexUrl: dataset.serverReindexUrl || '',
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

  function installerLink(config) {
    const platform = clientPlatform();
    if (platform === 'windows') {
      return config.signerSetupWindows || config.signerDownloadPage || '';
    }
    if (platform === 'macos') {
      return config.signerSetupMacos || config.signerDownloadPage || '';
    }
    if (platform === 'linux') {
      return config.signerSetupLinux || config.signerDownloadPage || '';
    }
    return config.signerDownloadPage || '';
  }

  function companionHelp(config, opts) {
    const actionUrl = installerLink(config);
    const installLabel = opts && opts.outdated
      ? 'Aggiorna il Local Signer su questo dispositivo.'
      : 'Installa o avvia il Local Signer su questo dispositivo.';
    const detail = actionUrl
      ? installLabel + ' Se necessario, usa il pacchetto ufficiale dedicato al tuo sistema.'
      : installLabel;
    return {
      title: opts && opts.outdated ? 'Aggiornamento del companion richiesto' : 'Companion locale non raggiungibile',
      body: detail,
      actionUrl: actionUrl,
      actionLabel: opts && opts.outdated ? 'Aggiorna il Local Signer' : 'Installa il Local Signer',
    };
  }

  function runtimeLabel(runtime) {
    const labels = {
      missing: 'non disponibile',
      installing: 'installazione',
      starting: 'avvio',
      ready: 'pronto',
      error: 'errore',
      disabled: 'disattivato',
    };
    return labels[runtime.status] || runtime.status || 'non disponibile';
  }

  async function fetchRuntimeStatus(config) {
    if (config.remoteHosted) {
      const response = await fetch(config.localSignerUrl + '/ai/status', {
        method: 'GET',
      });
      return readJsonResponse(response);
    }
    const response = await fetch(config.runtimeStatusUrl, {
      method: 'GET',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    });
    return readJsonResponse(response);
  }

  async function fetchCompanionPing(config) {
    const response = await fetch(config.localSignerUrl + '/ping', {
      method: 'GET',
    });
    return readJsonResponse(response);
  }

  async function fetchServerContext(config, payload) {
    const response = await fetch(config.serverContextUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: JSON.stringify(payload || {}),
    });
    return readJsonResponse(response);
  }

  async function fetchServerAnswer(config, payload) {
    const response = await fetch(config.serverAskUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: JSON.stringify(payload || {}),
    });
    return readJsonResponse(response);
  }

  async function runCompanionRagQuery(config, payload) {
    const response = await fetch(config.localSignerUrl + '/ai/rag/query', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload || {}),
    });
    return readJsonResponse(response);
  }

  async function runServerReindex(config, payload) {
    const response = await fetch(config.serverReindexUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: JSON.stringify(payload || {}),
    });
    return readJsonResponse(response);
  }

  window.HacsLocalAiBrowserBridge = {
    rootConfig,
    readJsonResponse,
    fetchRuntimeStatus,
    fetchCompanionPing,
    fetchServerContext,
    fetchServerAnswer,
    runCompanionRagQuery,
    runServerReindex,
    companionHelp,
    runtimeLabel,
  };
})();
