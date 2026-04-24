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

  function testaPkcs11() {
    const bottone = document.getElementById('btnTestPkcs11');
    const risultato = document.getElementById('pkcs11TestResult');
    if (!bottone || !risultato) {
      return;
    }

    bottone.disabled = true;
    risultato.innerHTML = '<span class="text-muted"><i class="bi bi-hourglass-split me-1"></i>Verifica in corso...</span>';

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
          '<span class="text-danger"><i class="bi bi-x-circle me-1"></i>' +
          dettaglio +
          ' Avvialo o installalo con il pacchetto qui sopra e riprova.</span>';
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
