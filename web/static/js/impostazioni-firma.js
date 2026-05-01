(function () {
  const LOCAL_SIGNER_BASE = 'http://127.0.0.1:27272';

  function fetchJsonWithTimeout(url, timeoutMs) {
    const controller = new AbortController();
    const timer = window.setTimeout(function () {
      controller.abort();
    }, timeoutMs);
    return fetch(url, {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      signal: controller.signal,
    }).finally(function () {
      window.clearTimeout(timer);
    });
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

  function isDesktopLocalSignerHost() {
    const userAgent = String(window.navigator.userAgent || '').toLowerCase();
    const platformName = String(window.navigator.platform || '').toLowerCase();
    const isMobileOrTablet = /android|iphone|ipad|ipod|mobile|tablet|silk|kindle/.test(userAgent);
    const isIpadDesktopMode = platformName.includes('mac') && Number(window.navigator.maxTouchPoints || 0) > 1;
    return !isMobileOrTablet && !isIpadDesktopMode;
  }

  function localSignerDownloadLink() {
    const userAgent = (navigator.userAgent || '').toLowerCase();
    let id = 'btn-local-signer-windows';
    let label = 'Scarica Local Signer per Windows';
    if (userAgent.includes('mac os') || userAgent.includes('macintosh')) {
      id = 'btn-local-signer-macos';
      label = 'Scarica Local Signer per macOS';
    } else if (userAgent.includes('linux') && !userAgent.includes('android')) {
      id = 'btn-local-signer-linux';
      label = 'Scarica Local Signer per Linux';
    }
    const link = document.getElementById(id);
    return {
      label,
      url: link?.getAttribute('href') || '/polisWeb/local-signer/setup/windows',
    };
  }

  function localSignerMissingMessage() {
    const download = localSignerDownloadLink();
    return (
      '<span class="text-danger"><i class="bi bi-x-circle me-1"></i>' +
      'Local Signer non rilevato. Ho provato ad avviarlo automaticamente. ' +
      '<a href="' +
      escapeHtml(download.url) +
      '" target="_blank" rel="noopener">' +
      escapeHtml(download.label) +
      '</a> e riprova.</span>'
    );
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

  async function pingLocalSigner() {
    try {
      const response = await fetchJsonWithTimeout(LOCAL_SIGNER_BASE + '/ping?light=1', 2500);
      const payload = await response.json();
      return Boolean(payload && payload.ok);
    } catch (error) {
      return false;
    }
  }

  async function ensureLocalSignerReady(risultato) {
    if (!isDesktopLocalSignerHost()) {
      risultato.innerHTML =
        '<span class="text-warning"><i class="bi bi-exclamation-triangle me-1"></i>' +
        'Local Signer disponibile solo su PC desktop Windows, macOS o Linux. Da mobile o tablet il controllo non viene eseguito.' +
        '</span>';
      return false;
    }
    if (await pingLocalSigner()) {
      return true;
    }
    risultato.innerHTML =
      '<span class="text-muted"><i class="bi bi-hourglass-split me-1"></i>Avvio Local Signer...</span>';
    requestLocalSignerStart();
    for (let attempt = 0; attempt < 10; attempt += 1) {
      await sleep(900);
      if (await pingLocalSigner()) {
        return true;
      }
    }
    risultato.innerHTML = localSignerMissingMessage();
    return false;
  }

  function scegliModalita(formato) {
    document.querySelectorAll('input[name="firma_formato"]').forEach(function (radio) {
      radio.checked = radio.value === formato;
    });

    ['pkcs11', 'p12', 'pem'].forEach(function (chiave) {
      const sezione = document.getElementById('sezione_' + chiave);
      if (sezione) {
        sezione.classList.toggle('d-none', chiave !== formato);
      }
    });

    document.querySelectorAll('.firma-card').forEach(function (card) {
      card.classList.remove('border-primary');
      card.classList.add('border');
      card.style.background = '';
    });

    const cardAttiva = document.getElementById('card_' + formato);
    if (cardAttiva) {
      cardAttiva.classList.remove('border');
      cardAttiva.classList.add('border-primary');
      cardAttiva.style.background = 'rgba(var(--bs-primary-rgb), .04)';
    }

    if (formato === 'pem') {
      const avanzate = document.getElementById('avanzate-firma');
      if (avanzate && !avanzate.classList.contains('show')) {
        new bootstrap.Collapse(avanzate, { toggle: true });
      }
    }
  }

  function evidenziaPacchettoHost() {
    const userAgent = (navigator.userAgent || '').toLowerCase();
    let piattaforma = '';
    if (userAgent.includes('windows')) {
      piattaforma = 'windows';
    } else if (userAgent.includes('mac os') || userAgent.includes('macintosh')) {
      piattaforma = 'macos';
    } else if (userAgent.includes('linux')) {
      piattaforma = 'linux';
    }

    if (!piattaforma) {
      return;
    }

    const mappa = {
      windows: 'btn-local-signer-windows',
      macos: 'btn-local-signer-macos',
      linux: 'btn-local-signer-linux',
    };

    Object.keys(mappa).forEach(function (chiave) {
      const bottone = document.getElementById(mappa[chiave]);
      if (!bottone) {
        return;
      }

      bottone.classList.remove('btn-primary', 'btn-outline-secondary');
      bottone.classList.add(chiave === piattaforma ? 'btn-primary' : 'btn-outline-secondary');
    });
  }

  async function testaPkcs11() {
    const bottone = document.getElementById('btnTestPkcs11');
    const risultato = document.getElementById('pkcs11TestResult');
    if (!bottone || !risultato) {
      return;
    }

    bottone.disabled = true;
    risultato.innerHTML = '<span class="text-muted"><i class="bi bi-hourglass-split me-1"></i>Verifica in corso...</span>';

    if (!(await ensureLocalSignerReady(risultato))) {
      bottone.disabled = false;
      return;
    }

    fetchJsonWithTimeout(LOCAL_SIGNER_BASE + '/ping', 4000)
      .then(function (response) {
        return response.json();
      })
      .then(function (payload) {
        if (payload.ok && Array.isArray(payload.token) && payload.token.length > 0) {
          const token = payload.token[0];
          risultato.innerHTML =
            '<span class="text-success"><i class="bi bi-check-circle-fill me-1"></i>Token rilevato: <strong>' +
            (token.label || token.manufacturer || 'Dispositivo PKCS#11') +
            '</strong></span>';
          return;
        }

        if (payload.ok) {
          const nota = payload.errore_token || payload.errore_libreria || payload.nota_riavvio_signer;
          risultato.innerHTML =
            '<span class="text-warning"><i class="bi bi-exclamation-triangle me-1"></i>' +
            (nota || 'Local Signer attivo ma token non ancora disponibile. Collega il dispositivo e riprova.') +
            '</span>';
          return;
        }

        risultato.innerHTML =
          '<span class="text-danger"><i class="bi bi-x-circle me-1"></i>' +
          (payload.errore_libreria || payload.messaggio || 'Local Signer non pronto su questo PC.') +
          '</span>';
      })
      .catch(function (errore) {
        const dettaglio = errore && errore.name === 'AbortError'
          ? 'Timeout di collegamento al Local Signer.'
          : 'Local Signer non raggiungibile su questo PC.';
        risultato.innerHTML =
          localSignerMissingMessage().replace('Local Signer non rilevato.', escapeHtml(dettaglio));
      })
      .finally(function () {
        bottone.disabled = false;
      });
  }

  document.addEventListener('DOMContentLoaded', function () {
    evidenziaPacchettoHost();
  });

  window.scegliModalita = scegliModalita;
  window.switchFirmaFmt = scegliModalita;
  window.testaPkcs11 = testaPkcs11;
})();
