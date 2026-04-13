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

  function toggleBrevoGuide(host) {
    const guide = document.getElementById('brevo-guide');
    if (guide) {
      guide.style.display = host === 'smtp-relay.brevo.com' ? '' : 'none';
    }
  }

  function fillSMTP(host, port, tls) {
    setFieldValue('smtp_host', host);
    setFieldValue('smtp_port', port);
    setCheckboxValue('smtp_use_tls', tls === '1');
    toggleBrevoGuide(host);
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
      message;
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

  document.addEventListener('DOMContentLoaded', function () {
    const smtpHost = document.getElementById('smtp_host');
    if (!smtpHost) {
      return;
    }

    toggleBrevoGuide(smtpHost.value);
    smtpHost.addEventListener('input', function () {
      toggleBrevoGuide(smtpHost.value);
    });
  });

  window.togglePwd = togglePwd;
  window.fillPEC = fillPEC;
  window.fillSMTP = fillSMTP;
  window.testConn = testConn;
})();
