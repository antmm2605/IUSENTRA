(function () {
  const PEC_PASSWORD_CACHE_KEY = 'iusentra.pec.localSignerPassword.once';
  let pecPasswordMemory = '';

  function setFieldValue(id, value) {
    const field = document.getElementById(id);
    if (field) {
      field.value = value;
    }
  }

  function setCheckboxValue(id, checked) {
    const field = document.getElementById(id);
    if (field) {
      field.checked = checked;
    }
  }

  function togglePwd(id, button) {
    const input = document.getElementById(id);
    if (!input) {
      return;
    }

    const isPlainText = input.type === 'text';
    input.type = isPlainText ? 'password' : 'text';

    const icon = button ? button.querySelector('i') : null;
    if (icon) {
      icon.className = isPlainText ? 'bi bi-eye' : 'bi bi-eye-slash';
    }
  }

  function fillPEC(smtpHost, smtpPort, imapHost, imapPort) {
    setFieldValue('pec_smtp_host', smtpHost);
    setFieldValue('pec_smtp_port', smtpPort);
    setFieldValue('pec_imap_host', imapHost);
    setFieldValue('pec_imap_port', imapPort);
  }

  function fillSMTP(host, port, tls) {
    setFieldValue('smtp_host', host);
    setFieldValue('smtp_port', port);
    setCheckboxValue('smtp_use_tls', tls === '1');
  }

  function collectValue(id, fallback) {
    const field = document.getElementById(id);
    if (!field) {
      return fallback || '';
    }
    return field.value;
  }

  function collectNamedValue(name, fallback) {
    const fields = Array.from(document.querySelectorAll('[name="' + name + '"]'));
    for (const field of fields) {
      if (field && typeof field.value === 'string' && field.value.length > 0) {
        return field.value;
      }
    }
    return fallback || '';
  }

  function readCachedPecPassword() {
    try {
      const raw = window.sessionStorage.getItem(PEC_PASSWORD_CACHE_KEY);
      if (!raw) {
        return '';
      }
      const payload = JSON.parse(raw);
      if (!payload || Date.now() > Number(payload.expiresAt || 0)) {
        window.sessionStorage.removeItem(PEC_PASSWORD_CACHE_KEY);
        return '';
      }
      return String(payload.value || '');
    } catch (error) {
      return '';
    }
  }

  function rememberPecPassword(value, persistForReload) {
    const cleaned = String(value || '');
    if (!cleaned) {
      return;
    }
    pecPasswordMemory = cleaned;
    if (!persistForReload) {
      return;
    }
    try {
      window.sessionStorage.setItem(
        PEC_PASSWORD_CACHE_KEY,
        JSON.stringify({
          value: cleaned,
          expiresAt: Date.now() + 15 * 60 * 1000,
        })
      );
    } catch (error) {
      // Browser storage non disponibile: resta comunque la memoria JS della pagina corrente.
    }
  }

  function collectPecPasswordForLocalSigner() {
    const direct = collectValue('pec_password', '') || collectNamedValue('pec_password', '');
    if (direct) {
      rememberPecPassword(direct, false);
      return direct;
    }
    return pecPasswordMemory || readCachedPecPassword();
  }

  function bindPecPasswordBridge() {
    const passwordField = document.getElementById('pec_password');
    const form = document.getElementById('form-pec');
    if (!passwordField) {
      return;
    }
    ['input', 'change', 'keyup', 'paste'].forEach(function (eventName) {
      passwordField.addEventListener(eventName, function () {
        window.setTimeout(function () {
          rememberPecPassword(passwordField.value, false);
        }, 0);
      });
    });
    if (form) {
      form.addEventListener('submit', function () {
        rememberPecPassword(passwordField.value, true);
      });
    }
  }

  function renderTestResult(container, success, message) {
    container.className = success ? 'test-result test-ok' : 'test-result test-fail';
    container.innerHTML =
      '<i class="bi ' +
      (success ? 'bi-check-circle-fill' : 'bi-x-circle-fill') +
      ' me-1"></i>' +
      escapeHtml(message);
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

  function renderTestResultHtml(container, success, html) {
    container.className = success ? 'test-result test-ok' : 'test-result test-fail';
    container.innerHTML =
      '<i class="bi ' +
      (success ? 'bi-check-circle-fill' : 'bi-x-circle-fill') +
      ' me-1"></i>' +
      html;
  }

  function localSignerMeta() {
    const meta = document.getElementById('pec-local-signer-meta');
    return {
      base: meta?.dataset.localSignerBase || 'http://127.0.0.1:27272',
      latestVersion: meta?.dataset.latestVersion || '',
      hasSavedPassword: meta?.dataset.hasSavedPassword === '1',
      windows: meta?.dataset.windowsUrl || '/polisWeb/local-signer/setup/windows',
      macos: meta?.dataset.macosUrl || '/polisWeb/local-signer/setup/macos',
      linux: meta?.dataset.linuxUrl || '/polisWeb/local-signer/setup/linux',
    };
  }

  function isDesktopLocalSignerHost() {
    const userAgent = String(window.navigator.userAgent || '').toLowerCase();
    const platformName = String(window.navigator.platform || '').toLowerCase();
    const isMobileOrTablet = /android|iphone|ipad|ipod|mobile|tablet|silk|kindle/.test(userAgent);
    const isIpadDesktopMode = platformName.includes('mac') && Number(window.navigator.maxTouchPoints || 0) > 1;
    return !isMobileOrTablet && !isIpadDesktopMode;
  }

  function localSignerInstallUrl() {
    const meta = localSignerMeta();
    const ua = window.navigator.userAgent || '';
    if (/Macintosh|Mac OS X/i.test(ua)) {
      return { label: 'Scarica Local Signer per macOS', url: meta.macos };
    }
    if (/Linux/i.test(ua) && !/Android/i.test(ua)) {
      return { label: 'Scarica Local Signer per Linux', url: meta.linux };
    }
    return { label: 'Scarica Local Signer per Windows', url: meta.windows };
  }

  function localSignerMissingHtml() {
    const install = localSignerInstallUrl();
    return (
      'Local Signer non rilevato. Ho provato ad avviarlo automaticamente: ' +
      '<a href="' +
      escapeHtml(install.url) +
      '" target="_blank" rel="noopener">' +
      escapeHtml(install.label) +
      '</a>.'
    );
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

  function localSignerOutdatedHtml(payload) {
    const meta = localSignerMeta();
    const install = localSignerInstallUrl();
    const installed = payload?.versione || payload?.version || 'n.d.';
    return (
      'Local Signer da aggiornare: rilevata versione ' +
      escapeHtml(installed) +
      ', richiesta ' +
      escapeHtml(meta.latestVersion) +
      '. <a href="' +
      escapeHtml(install.url) +
      '" target="_blank" rel="noopener">' +
      escapeHtml(install.label.replace('Scarica', 'Aggiorna')) +
      '</a>. Dopo l\'installazione ripeti il test.'
    );
  }

  function isLocalSignerOutdated(payload) {
    const meta = localSignerMeta();
    if (!meta.latestVersion || !payload) {
      return false;
    }
    return compareVersions(payload.versione || payload.version || '', meta.latestVersion) < 0;
  }

  function sleep(ms) {
    return new Promise(function (resolve) {
      window.setTimeout(resolve, ms);
    });
  }

  async function fetchJsonWithTimeout(url, options, timeoutMs) {
    const controller = new AbortController();
    const timer = window.setTimeout(function () {
      controller.abort();
    }, timeoutMs || 4000);
    try {
      const response = await fetch(url, {
        ...(options || {}),
        signal: controller.signal,
      });
      return await response.json();
    } finally {
      window.clearTimeout(timer);
    }
  }

  async function pingLocalSigner() {
    try {
      const meta = localSignerMeta();
      const data = await fetchJsonWithTimeout(meta.base + '/ping?light=1', { method: 'GET' }, 2500);
      return data && data.ok ? data : null;
    } catch (error) {
      return null;
    }
  }

  function requestLocalSignerStart() {
    const iframe = document.createElement('iframe');
    iframe.style.display = 'none';
    iframe.src = 'hacs-local-signer://restart';
    document.body.appendChild(iframe);
    window.setTimeout(function () {
      iframe.remove();
    }, 2500);
  }

  async function ensureLocalSignerReady(result) {
    if (!isDesktopLocalSignerHost()) {
      renderTestResultHtml(
        result,
        false,
        'Local Signer disponibile solo su PC desktop Windows, macOS o Linux. Da mobile o tablet il controllo non viene eseguito.'
      );
      return false;
    }
    const firstPing = await pingLocalSigner();
    if (firstPing) {
      if (isLocalSignerOutdated(firstPing)) {
        renderTestResultHtml(result, false, localSignerOutdatedHtml(firstPing));
        return false;
      }
      return true;
    }
    result.className = 'test-result test-spin';
    result.innerHTML = '<i class="bi bi-arrow-repeat spin me-1"></i>Avvio Local Signer...';
    requestLocalSignerStart();
    for (let attempt = 0; attempt < 10; attempt += 1) {
      await sleep(900);
      const ping = await pingLocalSigner();
      if (ping) {
        if (isLocalSignerOutdated(ping)) {
          renderTestResultHtml(result, false, localSignerOutdatedHtml(ping));
          return false;
        }
        return true;
      }
    }
    renderTestResultHtml(result, false, localSignerMissingHtml());
    return false;
  }

  async function testConn(tipo, btnId, resId) {
    const button = document.getElementById(btnId);
    const result = document.getElementById(resId);
    if (!button || !result) {
      return;
    }

    button.disabled = true;
    result.className = 'test-result test-spin';
    result.innerHTML = '<i class="bi bi-arrow-repeat spin me-1"></i>Verifica in corso...';

    let payload = {};
    if (tipo === 'pec-smtp' || tipo === 'pec-imap') {
      payload = {
        indirizzo: collectValue('pec_indirizzo', ''),
        password: collectValue('pec_password', ''),
        smtp_host: collectValue('pec_smtp_host', ''),
        smtp_port: parseInt(collectValue('pec_smtp_port', '465'), 10) || 465,
        imap_host: collectValue('pec_imap_host', ''),
        imap_port: parseInt(collectValue('pec_imap_port', '993'), 10) || 993,
        use_ssl: document.getElementById('pec_use_ssl')?.checked ?? true,
      };
    } else if (tipo === 'smtp') {
      payload = {
        host: collectValue('smtp_host', ''),
        port: parseInt(collectValue('smtp_port', '587'), 10) || 587,
        username: collectValue('smtp_username', ''),
        password: collectValue('smtp_password', ''),
        use_tls: document.getElementById('smtp_use_tls')?.checked ?? true,
      };
    } else if (tipo === 'whatsapp') {
      payload = {
        twilio_sid: collectValue('twilio_sid', ''),
        twilio_token: collectValue('twilio_token', ''),
        twilio_numero: collectValue('twilio_numero', ''),
        callmebot_key: collectValue('callmebot_key', ''),
      };
    }

    try {
      const response = await fetch('/impostazioni/test/' + tipo, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      renderTestResult(result, Boolean(data.ok), data.messaggio || 'Verifica completata.');
    } catch (error) {
      renderTestResult(result, false, 'Errore di rete durante la verifica.');
    } finally {
      button.disabled = false;
    }
  }

  function collectPecPayload() {
    return {
      indirizzo: collectValue('pec_indirizzo', ''),
      username: collectValue('pec_indirizzo', ''),
      password: collectPecPasswordForLocalSigner(),
      smtp_host: collectValue('pec_smtp_host', ''),
      smtp_port: parseInt(collectValue('pec_smtp_port', '465'), 10) || 465,
      use_ssl: document.getElementById('pec_use_ssl')?.checked ?? true,
    };
  }

  async function collectPecPayloadForLocalSmtp() {
    const payload = collectPecPayload();
    if (payload.password) {
      return payload;
    }
    const meta = localSignerMeta();
    if (!meta.hasSavedPassword) {
      return payload;
    }
    try {
      const response = await fetch('/impostazioni/pec/local-smtp-payload', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({
          indirizzo: payload.indirizzo,
          smtp_host: payload.smtp_host,
          smtp_port: payload.smtp_port,
          use_ssl: payload.use_ssl,
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok || !data.payload) {
        return {
          ...payload,
          _errorePassword: data.errore || 'Password PEC salvata non disponibile per il test locale.',
        };
      }
      return {
        ...payload,
        ...data.payload,
        indirizzo: payload.indirizzo || data.payload.indirizzo || '',
        username: payload.indirizzo || data.payload.username || data.payload.indirizzo || '',
        smtp_host: payload.smtp_host || data.payload.smtp_host || '',
        smtp_port: payload.smtp_port || data.payload.smtp_port || 465,
        use_ssl: payload.use_ssl,
      };
    } catch (error) {
      return {
        ...payload,
        _errorePassword: 'Impossibile recuperare la configurazione PEC salvata per il test locale.',
      };
    }
  }

  async function testPecSmtpLocale(btnId, resId) {
    const button = document.getElementById(btnId);
    const result = document.getElementById(resId);
    if (!button || !result) {
      return;
    }

    const meta = localSignerMeta();
    button.disabled = true;
    result.className = 'test-result test-spin';
    result.innerHTML = '<i class="bi bi-arrow-repeat spin me-1"></i>Preparazione test SMTP locale...';

    const payload = await collectPecPayloadForLocalSmtp();
    if (!payload.password) {
      renderTestResult(
        result,
        false,
        payload._errorePassword ||
          'Password PEC non disponibile per il test locale. Inseriscila nel campo PEC: resta nel browser, viene inviata solo al Local Signer su questo dispositivo e non viene salvata dal server.'
      );
      button.disabled = false;
      return;
    }

    result.className = 'test-result test-spin';
    result.innerHTML = '<i class="bi bi-arrow-repeat spin me-1"></i>Verifica Local Signer...';

    try {
      if (!(await ensureLocalSignerReady(result))) {
        return;
      }
      result.className = 'test-result test-spin';
      result.innerHTML = '<i class="bi bi-arrow-repeat spin me-1"></i>Test SMTP locale in corso...';
      const data = await fetchJsonWithTimeout(
        meta.base + '/pec/smtp/test',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify(payload),
        },
        35000
      );
      renderTestResult(
        result,
        Boolean(data.ok),
        data.ok ? 'Connessione SMTP PEC riuscita.' : data.messaggio || 'Verifica locale completata.'
      );
    } catch (error) {
      renderTestResultHtml(result, false, localSignerMissingHtml());
    } finally {
      button.disabled = false;
    }
  }

  window.togglePwd = togglePwd;
  window.fillPEC = fillPEC;
  window.fillSMTP = fillSMTP;
  window.testConn = testConn;
  window.testPecSmtpLocale = testPecSmtpLocale;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindPecPasswordBridge);
  } else {
    bindPecPasswordBridge();
  }
})();
