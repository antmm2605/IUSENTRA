(function () {
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
      windows: meta?.dataset.windowsUrl || '/polisWeb/local-signer/setup/windows',
      macos: meta?.dataset.macosUrl || '/polisWeb/local-signer/setup/macos',
      linux: meta?.dataset.linuxUrl || '/polisWeb/local-signer/setup/linux',
    };
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
      return Boolean(data && data.ok);
    } catch (error) {
      return false;
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
    if (await pingLocalSigner()) {
      return true;
    }
    result.className = 'test-result test-spin';
    result.innerHTML = '<i class="bi bi-arrow-repeat spin me-1"></i>Avvio Local Signer...';
    requestLocalSignerStart();
    for (let attempt = 0; attempt < 10; attempt += 1) {
      await sleep(900);
      if (await pingLocalSigner()) {
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
      password: collectValue('pec_password', ''),
      smtp_host: collectValue('pec_smtp_host', ''),
      smtp_port: parseInt(collectValue('pec_smtp_port', '465'), 10) || 465,
      use_ssl: document.getElementById('pec_use_ssl')?.checked ?? true,
    };
  }

  async function testPecSmtpLocale(btnId, resId) {
    const button = document.getElementById(btnId);
    const result = document.getElementById(resId);
    if (!button || !result) {
      return;
    }

    const payload = collectPecPayload();
    if (!payload.password) {
      renderTestResult(
        result,
        false,
        'Inserisci la password PEC per il test locale: resta sul PC e non viene salvata dal server.'
      );
      return;
    }

    button.disabled = true;
    result.className = 'test-result test-spin';
    result.innerHTML = '<i class="bi bi-arrow-repeat spin me-1"></i>Verifica Local Signer...';

    try {
      if (!(await ensureLocalSignerReady(result))) {
        return;
      }
      const meta = localSignerMeta();
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
      renderTestResult(result, Boolean(data.ok), data.messaggio || 'Verifica locale completata.');
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
})();
