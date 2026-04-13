(function () {
  function showFeedback(kind, title, body) {
    const container = document.getElementById('wa-action-feedback');
    if (!container) {
      return;
    }

    const icon = kind === 'success'
      ? 'bi-check-circle-fill'
      : kind === 'warning'
        ? 'bi-exclamation-triangle-fill'
        : 'bi-info-circle-fill';

    container.classList.remove('d-none');
    container.innerHTML =
      '<div class="ui-feedback ' + (kind !== 'info' ? 'ui-feedback--' + kind : '') + '">' +
      '<div class="ui-feedback__icon"><i class="bi ' + icon + '"></i></div>' +
      '<div class="ui-feedback__content">' +
      '<div class="ui-feedback__title">' + escapeHtml(title) + '</div>' +
      '<div class="ui-feedback__body">' + escapeHtml(body) + '</div>' +
      '</div>' +
      '</div>';
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function updateCharCount(textarea, counter) {
    if (textarea && counter) {
      counter.textContent = String(textarea.value.length);
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    const root = document.querySelector('.wa-page');
    if (!root) {
      return;
    }

    const linkUrl = root.dataset.waLinkUrl || '';
    const selectCliente = document.getElementById('sel-cliente');
    const testoMsg = document.getElementById('testo-msg');
    const charCount = document.getElementById('char-count');
    const waPreview = document.getElementById('wa-link-preview');
    const waButton = document.getElementById('wa-link-btn');
    const btnGeneraLink = document.getElementById('btn-genera-link');
    const promemoriaForm = document.getElementById('wa-promemoria-form');

    updateCharCount(testoMsg, charCount);

    if (testoMsg) {
      testoMsg.addEventListener('input', function () {
        updateCharCount(testoMsg, charCount);
      });
    }

    document.querySelectorAll('[data-template-text]').forEach(function (button) {
      button.addEventListener('click', function () {
        if (!testoMsg) {
          return;
        }
        testoMsg.value = button.dataset.templateText || '';
        updateCharCount(testoMsg, charCount);
        testoMsg.focus();
        showFeedback(
          'success',
          'Template applicato',
          'Il testo e\' stato inserito nel messaggio. Puoi completarlo oppure inviarlo subito.'
        );
      });
    });

    if (btnGeneraLink) {
      btnGeneraLink.addEventListener('click', async function () {
        const numero = selectCliente?.options?.[selectCliente.selectedIndex]?.dataset?.numero || '';
        const testo = testoMsg?.value.trim() || '';

        if (!numero || !testo) {
          showFeedback(
            'warning',
            'Dati mancanti',
            'Seleziona un cliente con numero WhatsApp e scrivi il testo del messaggio prima di generare il link.'
          );
          return;
        }

        btnGeneraLink.disabled = true;

        try {
          const response = await fetch(linkUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ numero, testo }),
          });
          const data = await response.json();

          if (!response.ok || data.errore || !data.link) {
            throw new Error(data.errore || 'Non sono riuscito a preparare il link WhatsApp.');
          }

          if (waButton) {
            waButton.href = data.link;
          }
          if (waPreview) {
            waPreview.classList.remove('d-none');
            waPreview.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }

          showFeedback(
            'success',
            'Link WhatsApp pronto',
            'Il link e\' stato generato correttamente. Puoi aprirlo e completare l\'invio manualmente.'
          );
        } catch (error) {
          showFeedback(
            'danger',
            'Generazione non riuscita',
            error instanceof Error ? error.message : 'Non sono riuscito a generare il link WhatsApp.'
          );
        } finally {
          btnGeneraLink.disabled = false;
        }
      });
    }

    if (promemoriaForm) {
      promemoriaForm.addEventListener('submit', function (event) {
        const count = Number(promemoriaForm.dataset.promemoriaCount || '0');
        const conferma = window.confirm(
          'Vuoi inviare ora i promemoria WhatsApp per ' + count + ' appuntamenti previsti domani?'
        );
        if (!conferma) {
          event.preventDefault();
        }
      });
    }
  });
})();
