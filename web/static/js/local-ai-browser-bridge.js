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
      serverAttachmentsUrl: dataset.serverAttachmentsUrl || '',
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

  function isCompanionTransportError(error) {
    const message = String((error && error.message) || '').toLowerCase();
    const status = Number((error && error.httpStatus) || 0);
    if (!status) {
      return true;
    }
    return (
      message.includes('failed to fetch') ||
      message.includes('networkerror') ||
      message.includes('load failed') ||
      message.includes('network request failed')
    );
  }

  function companionRuntimeHelp(error) {
    return {
      title: 'Companion locale raggiunto, ma la richiesta non e\' andata a buon fine',
      body: 'Il Local Signer risponde correttamente su questo dispositivo, ma il modulo AI locale ha restituito un errore operativo.',
      detail: String((error && error.message) || 'Errore operativo del modulo AI locale.'),
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

  async function parseServerAttachments(config, payload) {
    const response = await fetch(config.serverAttachmentsUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: JSON.stringify(payload || {}),
    });
    return readJsonResponse(response);
  }

  async function parseCompanionAttachments(config, payload) {
    const response = await fetch(config.localSignerUrl + '/ai/attachments/parse', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload || {}),
    });
    return readJsonResponse(response);
  }

  async function streamCompanionSse(config, path, payload, handlers) {
    const response = await fetch(config.localSignerUrl + path, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload || {}),
    });
    if (!response.ok) {
      await readJsonResponse(response);
    }
    if (!response.body) {
      throw new Error('Il browser non supporta lo streaming della risposta locale.');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalPayload = null;

    while (true) {
      const result = await reader.read();
      if (result.done) {
        return finalPayload || {};
      }

      buffer += decoder.decode(result.value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.indexOf('data: ') !== 0) {
          continue;
        }
        const raw = line.slice(6).trim();
        if (!raw) {
          continue;
        }
        if (raw === '[DONE]') {
          if (handlers && typeof handlers.onDone === 'function') {
            handlers.onDone(finalPayload || {});
          }
          return finalPayload || {};
        }

        let data = {};
        try {
          data = JSON.parse(raw);
        } catch (error) {
          throw new Error('Risposta non leggibile ricevuta dal companion locale.');
        }

        if (data.errore) {
          const err = new Error(data.errore);
          err.payload = data;
          throw err;
        }

        if (data.token && handlers && typeof handlers.onToken === 'function') {
          handlers.onToken(String(data.token || ''), data);
        }

        if (data.done) {
          finalPayload = data;
        }
      }
    }
  }

  async function streamCompanionChat(config, payload, handlers) {
    return streamCompanionSse(config, '/ai/chat/stream', payload, handlers);
  }

  async function streamCompanionRagQuery(config, payload, handlers) {
    return streamCompanionSse(config, '/ai/rag/query/stream', payload, handlers);
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

  window.IusentraLocalAiBrowserBridge = {
    rootConfig,
    readJsonResponse,
    fetchRuntimeStatus,
    fetchCompanionPing,
    fetchServerContext,
    parseServerAttachments,
    parseCompanionAttachments,
    fetchServerAnswer,
    runCompanionRagQuery,
    streamCompanionChat,
    streamCompanionRagQuery,
    runServerReindex,
    companionHelp,
    isCompanionTransportError,
    companionRuntimeHelp,
    runtimeLabel,
  };
})();
