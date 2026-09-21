/* Precompila solo campi vuoti. Nessun invio, pagamento o polling del PST. */
(() => {
  'use strict';
  const script = document.currentScript;
  const fascicolo = script && script.dataset.fascicolo;
  if (!fascicolo) return;
  fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicolo)}/pagopa/avvisi`, {
    credentials: 'same-origin',
  }).then(response => {
    if (!response.ok) throw new Error('Dati non disponibili');
    return response.json();
  }).then(async data => {
    if (document.readyState !== 'complete') {
      await new Promise(resolve => window.addEventListener('load', resolve, { once: true }));
    }
    const values = data.prefill || {};
    Object.entries(values).forEach(([name, value]) => {
      const field = document.getElementById(name) || document.getElementsByName(name)[0];
      if (!value || !field || field.disabled || field.readOnly || field.value) return;
      if (!['INPUT', 'TEXTAREA'].includes(field.tagName) || field.type === 'hidden') return;
      field.value = value;
      ['input', 'change'].forEach(type => {
        const event = document.createEvent('HTMLEvents');
        event.initEvent(type, true, false);
        field.dispatchEvent(event);
      });
    });
  }).catch(() => {
    const message = document.createElement('p');
    message.setAttribute('role', 'status');
    message.textContent = 'Precompilazione non disponibile. Verifica i dati del debitore prima di proseguire.';
    (document.querySelector('form') || document.body).prepend(message);
  });
})();
