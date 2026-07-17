(function () {
  const ROOT_ID = 'iusentra-local-signer-monitor';
  const STORAGE_KEY = 'iusentra-local-signer-installer-prompt';
  let updatePromise = null;

  function root() {
    return document.getElementById(ROOT_ID);
  }

  function config() {
    const el = root();
    const data = el ? el.dataset : {};
    return {
      enabled: data.enabled !== '0',
      baseUrl: data.localSignerUrl || 'http://127.0.0.1:27272',
      latestVersion: data.latestVersion || '',
      downloadPage: data.downloadPage || '/impostazioni?tab=firma',
      setupWindows: data.setupWindows || '/polisWeb/local-signer/setup/windows',
      setupMacos: data.setupMacos || '/polisWeb/local-signer/setup/macos',
      setupLinux: data.setupLinux || '/polisWeb/local-signer/setup/linux',
      updateProtocol: data.updateProtocol || 'iusentra-local-signer://update',
      restartProtocol: data.restartProtocol || 'iusentra-local-signer://restart',
      autoInstallerPrompt: data.autoInstallerPrompt === '1',
    };
  }

  function escapeHtml(value) {
    return String(value || '').replace(/[&<>"']/g, function (char) {
      return {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      }[char];
    });
  }

  function sleep(ms) {
    return new Promise(function (resolve) {
      window.setTimeout(resolve, ms);
    });
  }

  function platform() {
    const ua = String(window.navigator.userAgent || window.navigator.platform || '').toLowerCase();
    if (ua.includes('mac')) {
      return 'macos';
    }
    if (ua.includes('linux') && !ua.includes('android')) {
      return 'linux';
    }
    return 'windows';
  }

  function isDesktopLocalSignerHost() {
    const ua = String(window.navigator.userAgent || '').toLowerCase();
    const platformName = String(window.navigator.platform || '').toLowerCase();
    const isMobileOrTablet = /android|iphone|ipad|ipod|mobile|tablet|silk|kindle/.test(ua);
    const isIpadDesktopMode = platformName.includes('mac') && Number(window.navigator.maxTouchPoints || 0) > 1;
    return !isMobileOrTablet && !isIpadDesktopMode;
  }

  function installerFor(cfg) {
    const current = platform();
    if (current === 'macos') {
      return { url: cfg.setupMacos, label: 'Installa o aggiorna Local Signer per macOS' };
    }
    if (current === 'linux') {
      return { url: cfg.setupLinux, label: 'Installa o aggiorna Local Signer per Linux' };
    }
    return { url: cfg.setupWindows, label: 'Installa o aggiorna Local Signer per Windows' };
  }

  function versionParts(value) {
    return String(value || '')
      .replace(/^v/i, '')
      .split(/[^\d]+/)
      .filter(Boolean)
      .map(function (part) {
        return parseInt(part, 10) || 0;
      });
  }

  function compareVersions(a, b) {
    const left = versionParts(a);
    const right = versionParts(b);
    const max = Math.max(left.length, right.length);
    for (let i = 0; i < max; i += 1) {
      const av = left[i] || 0;
      const bv = right[i] || 0;
      if (av > bv) return 1;
      if (av < bv) return -1;
    }
    return 0;
  }

  async function fetchJsonWithTimeout(url, timeoutMs, requestOptions) {
    const controller = new AbortController();
    const timer = window.setTimeout(function () {
      controller.abort();
    }, timeoutMs || 2500);
    try {
      const response = await fetch(url, {
        method: 'GET',
        cache: 'no-store',
        mode: 'cors',
        ...(requestOptions || {}),
        signal: controller.signal,
      });
      return await response.json();
    } finally {
      window.clearTimeout(timer);
    }
  }

  function triggerHiddenLink(url, options) {
    const link = document.createElement('a');
    link.href = url;
    link.style.display = 'none';
    if (options && options.download) {
      link.download = '';
    }
    if (options && options.blank) {
      link.target = '_blank';
      link.rel = 'noopener';
    }
    document.body.appendChild(link);
    link.click();
    window.setTimeout(function () {
      link.remove();
    }, 2500);
  }

  function openInstallerDownload(cfg) {
    const installer = installerFor(cfg);
    triggerHiddenLink(installer.url, { download: true, blank: true });
  }

  async function ping(cfg) {
    try {
      const payload = await fetchJsonWithTimeout(cfg.baseUrl + '/ping?light=1', 2500);
      if (!payload || payload.ok !== true) {
        return null;
      }
      return payload;
    } catch (error) {
      return null;
    }
  }

  function requestProtocol(uri) {
    triggerHiddenLink(uri, {});
  }

  function requestStart(cfg) {
    requestProtocol(cfg.restartProtocol);
  }

  function requestUpdate(cfg) {
    requestProtocol(cfg.updateProtocol);
  }

  function layoutBanner(el) {
    const narrow = window.matchMedia('(max-width: 767px)').matches;
    el.style.left = narrow ? '12px' : 'auto';
    el.style.right = narrow ? '12px' : '88px';
    el.style.bottom = narrow ? '88px' : '16px';
    el.style.margin = '0';
    el.style.maxWidth = narrow ? 'calc(100vw - 24px)' : 'min(680px, calc(100vw - 120px))';
    el.style.zIndex = '1080';
  }

  function bindBannerLayout(el) {
    layoutBanner(el);
    if (el.dataset.localSignerLayoutBound === '1') {
      return;
    }
    el.dataset.localSignerLayoutBound = '1';
    window.addEventListener('resize', function () {
      layoutBanner(el);
    });
  }

  function banner() {
    let el = document.getElementById('iusentra-local-signer-status');
    if (el) {
      bindBannerLayout(el);
      return el;
    }
    el = document.createElement('div');
    el.id = 'iusentra-local-signer-status';
    el.className = 'alert alert-warning shadow position-fixed d-none';
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');
    bindBannerLayout(el);
    document.body.appendChild(el);
    return el;
  }

  function hideBanner() {
    const el = document.getElementById('iusentra-local-signer-status');
    if (el) {
      el.classList.add('d-none');
      el.innerHTML = '';
    }
  }

  function renderInstallRequired(cfg, installer) {
    renderBanner(
      'warning',
      'Installazione Local Signer richiesta',
      'Il servizio locale non risponde: se Local Signer è già installato, avvialo dal pulsante dedicato; altrimenti usa il pacchetto ufficiale.',
      [
        { type: 'button', name: 'start', label: 'Avvia Local Signer', className: 'btn-primary' },
        { type: 'link', name: 'installer', label: 'Scarica installer ufficiale', url: installer.url, className: 'btn-outline-primary' },
        { type: 'button', name: 'retry', label: 'Verifica dopo installazione', className: 'btn-outline-secondary' },
      ]
    );
    autoOpenInstallerOnce(cfg, 'missing');
  }

  function renderBanner(kind, title, body, actions) {
    if (title === 'Installazione Local Signer richiesta') {
      title = 'Local Signer da installare su questo PC';
      body = 'IUSENTRA ha già provato ad avviare il servizio locale. Apri l’installer ufficiale; al termine premi Verifica dopo installazione.';
    } else if (title === 'Aggiornamento Local Signer richiesto') {
      body = 'Ho tentato l’aggiornamento automatico. Se Windows non ha autorizzato l’avvio, apri il pacchetto ufficiale qui sotto e poi verifica di nuovo.';
    }
    const el = banner();
    bindBannerLayout(el);
    el.className =
      'alert shadow position-fixed ' +
      (kind === 'success' ? 'alert-success' : kind === 'danger' ? 'alert-danger' : 'alert-warning');
    const actionHtml = (actions || [])
      .map(function (action) {
        if (action.type === 'button') {
          return (
            '<button type="button" class="btn btn-sm ' +
            escapeHtml(action.className || 'btn-primary') +
            '" data-local-signer-action="' +
            escapeHtml(action.name) +
            '">' +
            escapeHtml(action.label) +
            '</button>'
          );
        }
        return (
          '<a class="btn btn-sm ' +
          escapeHtml(action.className || 'btn-primary') +
          '" href="' +
          escapeHtml(action.url) +
          '" target="_blank" rel="noopener" download data-local-signer-action="' +
          escapeHtml(action.name || 'installer') +
          '">' +
          escapeHtml(action.label) +
          '</a>'
        );
      })
      .join(' ');
    el.innerHTML =
      '<div class="fw-semibold mb-1">' +
      escapeHtml(title) +
      '</div><div class="small mb-2">' +
      escapeHtml(body) +
      '</div><div class="d-flex gap-2 flex-wrap">' +
      actionHtml +
      '<button type="button" class="btn btn-sm btn-outline-secondary" data-local-signer-action="close">Chiudi</button>' +
      '</div>';
    el.classList.remove('d-none');
  }

  function installerPromptAlreadyShown(cfg, reason) {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      const current = raw ? JSON.parse(raw) : {};
      const ageMs = Date.now() - Number(current.at || 0);
      return current.version === cfg.latestVersion && current.reason === reason && ageMs < 24 * 60 * 60 * 1000;
    } catch (error) {
      return false;
    }
  }

  function rememberInstallerPrompt(cfg, reason) {
    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ version: cfg.latestVersion, reason: reason, at: Date.now() })
      );
    } catch (error) {
      // localStorage non disponibile: il banner resta comunque operativo.
    }
  }

  function autoOpenInstallerOnce(cfg, reason) {
    if (!cfg.autoInstallerPrompt || installerPromptAlreadyShown(cfg, reason)) {
      return;
    }
    rememberInstallerPrompt(cfg, reason);
    const installer = installerFor(cfg);
    window.setTimeout(function () {
      const link = document.createElement('a');
      link.href = installer.url;
      link.target = '_blank';
      link.rel = 'noopener';
      link.download = '';
      document.body.appendChild(link);
      link.click();
      link.remove();
    }, 1200);
  }

  async function verifyAfterStart(cfg, attempts, delayMs) {
    requestStart(cfg);
    const maxAttempts = attempts || 4;
    const delay = delayMs || 700;
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      await sleep(delay);
      const payload = await ping(cfg);
      if (payload) {
        return payload;
      }
    }
    return null;
  }

  async function verifyAfterUpdate(cfg) {
    if (updatePromise) {
      return updatePromise;
    }
    updatePromise = (async function () {
    try {
      const updatePayload = await fetchJsonWithTimeout(cfg.baseUrl + '/update', 60000, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ base_url: window.location.origin }),
      });
      if (!updatePayload || updatePayload.ok !== true) {
        throw new Error('Aggiornamento locale non avviato');
      }
    } catch (error) {
      requestUpdate(cfg);
    }
    const updateDeadline = Date.now() + 360000;
    for (let attempt = 0; attempt < 240 && Date.now() < updateDeadline; attempt += 1) {
      await sleep(1500);
      const payload = await ping(cfg);
      if (payload && compareVersions(payload.versione || payload.version || '', cfg.latestVersion) >= 0) {
        return payload;
      }
    }
    return null;
    })();
    try {
      return await updatePromise;
    } finally {
      updatePromise = null;
    }
  }

  async function run(options) {
    const cfg = config();
    if (!cfg.enabled || !cfg.latestVersion) {
      return { ok: false, reason: 'disabled' };
    }
    if (!isDesktopLocalSignerHost()) {
      hideBanner();
      return { ok: false, reason: 'unsupported_mobile_tablet' };
    }

    const installer = installerFor(cfg);
    let payload = await ping(cfg);
    if (!payload) {
      renderBanner(
        'warning',
        'Avvio Local Signer in corso',
        'Il servizio locale non sta rispondendo. IUSENTRA prova ad avviarlo automaticamente e poi ricontrolla questo PC.',
        [
          { type: 'button', name: 'retry', label: 'Verifica di nuovo', className: 'btn-outline-secondary' },
        ]
      );
      const started = await verifyAfterStart(cfg, 8, 900);
      if (!started) {
        renderInstallRequired(cfg, installer);
        return { ok: false, reason: 'missing' };
      }
      payload = started;
    }

    const installedVersion = payload.versione || payload.version || '';
    if (compareVersions(installedVersion, cfg.latestVersion) < 0) {
      renderBanner(
        'warning',
        'Aggiornamento Local Signer in corso',
        'Fase 2: versione rilevata ' +
          installedVersion +
          ', versione richiesta ' +
          cfg.latestVersion +
          '. Avvio automaticamente l’aggiornamento locale e poi ricontrollo il servizio.',
        [
          { type: 'button', name: 'auto-update', label: 'Aggiorna automaticamente', className: 'btn-primary' },
          { type: 'link', name: 'installer', label: installer.label, url: installer.url, className: 'btn-primary' },
          { type: 'button', name: 'retry', label: 'Verifica dopo aggiornamento', className: 'btn-outline-primary' },
        ]
      );
      const updated = await verifyAfterUpdate(cfg);
      if (updated) {
        hideBanner();
        return { ok: true, version: updated.versione || updated.version || '', payload: updated };
      }
      renderBanner(
        'warning',
        'Aggiornamento Local Signer richiesto',
        'Se Windows non ha autorizzato l’avvio automatico, usa il pacchetto ufficiale qui sotto e poi verifica di nuovo.',
        [
          { type: 'button', name: 'auto-update', label: 'Riprova aggiornamento automatico', className: 'btn-primary' },
          { type: 'link', name: 'installer', label: installer.label, url: installer.url, className: 'btn-outline-primary' },
          { type: 'button', name: 'retry', label: 'Verifica dopo aggiornamento', className: 'btn-outline-secondary' },
        ]
      );
      return { ok: false, reason: 'outdated', installedVersion: installedVersion };
    }

    hideBanner();
    if (options && options.showOk) {
      renderBanner(
        'success',
        'Local Signer aggiornato',
        'Fase 4 completata: il servizio locale risponde ed espone la versione ' + installedVersion + '.',
        [{ type: 'button', name: 'close', label: 'Chiudi', className: 'btn-outline-success' }]
      );
    }
    return { ok: true, version: installedVersion, payload: payload };
  }

  document.addEventListener('click', function (event) {
    const target = event.target && event.target.closest('[data-local-signer-action]');
    if (!target) {
      return;
    }
    const action = target.getAttribute('data-local-signer-action');
    if (action === 'retry') {
      event.preventDefault();
      run({ showOk: true });
    } else if (action === 'start') {
      event.preventDefault();
      (async function () {
        const cfg = config();
        const installer = installerFor(cfg);
        renderBanner(
          'warning',
          'Avvio Local Signer',
          'Apro il collegamento locale sul PC e ricontrollo il servizio. Se Windows chiede conferma, autorizza IUSENTRA Local Signer.',
          [{ type: 'button', name: 'retry', label: 'Verifica', className: 'btn-outline-primary' }]
        );
        const started = await verifyAfterStart(cfg, 10, 900);
        if (started) {
          renderBanner(
            'success',
            'Local Signer attivo',
            'Il servizio locale risponde con la versione ' + (started.versione || started.version || cfg.latestVersion) + '.',
            [{ type: 'button', name: 'close', label: 'Chiudi', className: 'btn-outline-success' }]
          );
          return;
        }
        renderInstallRequired(cfg, installer);
      })();
    } else if (action === 'auto-update') {
      event.preventDefault();
      (async function () {
        const cfg = config();
        renderBanner(
          'warning',
          'Aggiornamento automatico avviato',
          'Sto aprendo il pacchetto ufficiale IUSENTRA sul PC e ricontrollo il servizio locale.',
          [{ type: 'button', name: 'retry', label: 'Verifica', className: 'btn-outline-primary' }]
        );
        const updated = await verifyAfterUpdate(cfg);
        if (updated) {
          renderBanner(
            'success',
            'Local Signer aggiornato',
            'Il servizio locale risponde con la versione ' + (updated.versione || updated.version || cfg.latestVersion) + '.',
            [{ type: 'button', name: 'close', label: 'Chiudi', className: 'btn-outline-success' }]
          );
        }
      })();
    } else if (action === 'close') {
      event.preventDefault();
      hideBanner();
    }
  });

  window.IusentraLocalSignerMonitor = {
    run: run,
    compareVersions: compareVersions,
    installerFor: installerFor,
    isDesktopLocalSignerHost: isDesktopLocalSignerHost,
  };

  document.addEventListener('DOMContentLoaded', function () {
    run({ showOk: false });
  });
})();
