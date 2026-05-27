(function () {
  const ROOT_ID = 'iusentra-local-signer-monitor';
  const STORAGE_KEY = 'iusentra-local-signer-installer-prompt';

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

  async function fetchJsonWithTimeout(url, timeoutMs) {
    const controller = new AbortController();
    const timer = window.setTimeout(function () {
      controller.abort();
    }, timeoutMs || 2500);
    try {
      const response = await fetch(url, {
        method: 'GET',
        signal: controller.signal,
      });
      return await response.json();
    } finally {
      window.clearTimeout(timer);
    }
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
    const iframe = document.createElement('iframe');
    iframe.className = 'd-none';
    iframe.setAttribute('aria-hidden', 'true');
    iframe.src = uri;
    document.body.appendChild(iframe);
    window.setTimeout(function () {
      iframe.remove();
    }, 2500);
  }

  function requestStart(cfg) {
    requestProtocol(cfg.restartProtocol);
  }

  function requestUpdate(cfg) {
    requestProtocol(cfg.updateProtocol);
  }

  function banner() {
    let el = document.getElementById('iusentra-local-signer-status');
    if (el) {
      return el;
    }
    el = document.createElement('div');
    el.id = 'iusentra-local-signer-status';
    el.className = 'alert alert-warning shadow position-fixed bottom-0 end-0 m-3 z-3 d-none';
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');
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

  function renderBanner(kind, title, body, actions) {
    const el = banner();
    el.className =
      'alert shadow position-fixed bottom-0 end-0 m-3 z-3 ' +
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
          '" target="_blank" rel="noopener" data-local-signer-action="' +
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
      document.body.appendChild(link);
      link.click();
      link.remove();
    }, 1200);
  }

  async function verifyAfterStart(cfg) {
    requestStart(cfg);
    for (let attempt = 0; attempt < 10; attempt += 1) {
      await sleep(900);
      const payload = await ping(cfg);
      if (payload) {
        return payload;
      }
    }
    return null;
  }

  async function verifyAfterUpdate(cfg) {
    try {
      await fetchJsonWithTimeout(cfg.baseUrl + '/update', 8000);
    } catch (error) {
      requestUpdate(cfg);
      window.setTimeout(function () {
        const installer = installerFor(cfg);
        const link = document.createElement('a');
        link.href = installer.url;
        link.target = '_blank';
        link.rel = 'noopener';
        document.body.appendChild(link);
        link.click();
        link.remove();
      }, 1500);
    }
    for (let attempt = 0; attempt < 70; attempt += 1) {
      await sleep(1200);
      const payload = await ping(cfg);
      if (payload && compareVersions(payload.versione || payload.version || '', cfg.latestVersion) >= 0) {
        return payload;
      }
    }
    return null;
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
        'Local Signer non rilevato',
        'Fase 1: provo ad avviare il servizio locale sul PC. Se non parte, preparo il pacchetto ufficiale per questo dispositivo.',
        [
          { type: 'button', name: 'retry', label: 'Verifica di nuovo', className: 'btn-outline-primary' },
          { type: 'link', name: 'installer', label: installer.label, url: installer.url, className: 'btn-primary' },
        ]
      );
      payload = await verifyAfterStart(cfg);
      if (!payload) {
        renderBanner(
          'warning',
          'Installazione Local Signer richiesta',
          'Fase 3: il servizio locale non risponde ancora. Installa il pacchetto proposto, poi usa “Verifica di nuovo” per la fase 4.',
          [
            { type: 'link', name: 'installer', label: installer.label, url: installer.url, className: 'btn-primary' },
            { type: 'button', name: 'retry', label: 'Verifica dopo installazione', className: 'btn-outline-primary' },
          ]
        );
        autoOpenInstallerOnce(cfg, 'missing');
        return { ok: false, reason: 'missing' };
      }
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
          '. Provo ad avviare automaticamente il pacchetto ufficiale e poi ricontrollo il servizio.',
        [
          { type: 'button', name: 'auto-update', label: 'Aggiorna automaticamente', className: 'btn-primary' },
          { type: 'link', name: 'installer', label: installer.label, url: installer.url, className: 'btn-primary' },
          { type: 'button', name: 'retry', label: 'Verifica dopo aggiornamento', className: 'btn-outline-primary' },
        ]
      );
      if (cfg.autoInstallerPrompt && !installerPromptAlreadyShown(cfg, 'outdated-auto')) {
        rememberInstallerPrompt(cfg, 'outdated-auto');
        const updated = await verifyAfterUpdate(cfg);
        if (updated) {
          hideBanner();
          return { ok: true, version: updated.versione || updated.version || '', payload: updated };
        }
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
