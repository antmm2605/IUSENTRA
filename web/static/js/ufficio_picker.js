/**
 * ufficio_picker.js — Autocomplete riutilizzabile per gli uffici giudiziari.
 *
 * Utilizzo (Jinja2):
 *   {% from "includes/_ufficio_picker.html" import ufficio_picker %}
 *   {{ ufficio_picker("tribunale", current_value=fascicolo.tribunale or "", usa_nome=true) }}
 *
 * Il picker manda al server:
 *   - usa_nome=true  → <input name="..."> riceve u.nome  (es. "Tribunale di Milano")
 *   - usa_nome=false → <input name="..."> riceve u.codice (es. "0580010")
 */

(function (global) {
  'use strict';

  const TIPO_ICONS = {
    TRIBUNALE: 'bi-building', CORTE_APPELLO: 'bi-bank2',
    PROCURA: 'bi-shield-exclamation', PROCURA_GENERALE: 'bi-shield-fill',
    CORTE_CASSAZIONE: 'bi-star-fill', TM: 'bi-people-fill',
    SORVEGLIANZA: 'bi-eye-fill', CORTE_ASSISE: 'bi-hammer',
    GDP: 'bi-person-badge', TAR: 'bi-building-check', CDS: 'bi-columns-gap',
  };
  const TIPO_LABEL = {
    TRIBUNALE: 'Tribunale', CORTE_APPELLO: "Corte d'Appello",
    PROCURA: 'Procura della Repubblica', PROCURA_GENERALE: 'Procura Generale',
    CORTE_CASSAZIONE: 'Cassazione', TM: 'Trib. Minorenni',
    SORVEGLIANZA: 'Trib. Sorveglianza', CORTE_ASSISE: "Corte d'Assise",
    GDP: 'Giudice di Pace', TAR: 'TAR', CDS: 'Consiglio di Stato',
  };
  const TIPO_PLACEHOLDER = {
    TRIBUNALE: 'tribunale per città (es. Milano)…',
    CORTE_APPELLO: "corte d'appello (es. Roma)…",
    PROCURA: 'procura per città (es. Napoli)…',
    PROCURA_GENERALE: 'procura generale (es. Torino)…',
    CORTE_ASSISE: "corte d'assise per città…",
    GDP: 'giudice di pace per città…',
    TM: 'tribunale minorenni per città…',
    SORVEGLIANZA: 'tribunale sorveglianza per città…',
    TAR: 'TAR per regione (es. Lombardia)…',
  };
  const GRUPPI_ORDER = ['CORTE_CASSAZIONE','CDS','CORTE_APPELLO','PROCURA_GENERALE',
                        'TRIBUNALE','PROCURA','CORTE_ASSISE','GDP','TM','SORVEGLIANZA','TAR'];

  /**
   * Inizializza un picker su un elemento root.
   * @param {string} uid — id univoco del root element (senza #)
   */
  function initUfficioPicker(uid) {
    const root     = document.getElementById(uid);
    if (!root) return;

    const usaNome  = root.dataset.uffpUsaNome === 'true';
    const required = root.dataset.uffpRequired === 'true';

    const input    = root.querySelector('[data-uffp-input]');
    const hidden   = root.querySelector('[data-uffp-value]');
    const dropdown = root.querySelector('[data-uffp-dropdown]');
    const clearBtn = root.querySelector('[data-uffp-clear]');
    const badge    = root.querySelector('[data-uffp-badge]');
    const badgeLbl = root.querySelector('[data-uffp-badge-label]');
    const tabs     = root.querySelector('[data-uffp-tabs]');
    const tipoIcon = root.querySelector('[data-uffp-icon]');

    if (!input || !hidden || !dropdown) return;

    let tipoFiltro = '';
    let items      = [];
    let focusIdx   = -1;
    let timer      = null;

    // ── Posiziona dropdown fixed sotto l'input ───────────────────
    function posiziona() {
      const rect = input.getBoundingClientRect();
      dropdown.style.top      = (rect.bottom + 4) + 'px';
      dropdown.style.left     = rect.left + 'px';
      dropdown.style.width    = rect.width + 'px';
      const spazio = window.innerHeight - rect.bottom - 8;
      dropdown.style.maxHeight = Math.min(340, spazio) + 'px';
    }

    // ── Tab tipo ─────────────────────────────────────────────────
    tabs && tabs.querySelectorAll('.uff-tab').forEach(tab => {
      tab.addEventListener('click', e => {
        e.stopPropagation();
        tabs.querySelectorAll('.uff-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        tipoFiltro = tab.dataset.tipo;
        if (tipoIcon) {
          const ic = tipoFiltro ? (TIPO_ICONS[tipoFiltro] || 'bi-search') : 'bi-search';
          tipoIcon.innerHTML = `<i class="bi ${ic} text-muted"></i>`;
        }
        if (input) {
          input.placeholder = tipoFiltro
            ? 'Cerca ' + (TIPO_PLACEHOLDER[tipoFiltro] || tipoFiltro.toLowerCase() + '…')
            : 'Cerca per città o nome…';
          if (input.value.trim().length >= 2) cerca(input.value.trim());
          else chiudi();
          input.focus();
        }
      });
    });

    // ── Rendering dropdown ────────────────────────────────────────
    function render(data) {
      focusIdx = -1; items = [];
      posiziona();
      if (!data.length) {
        dropdown.innerHTML = `<div class="uff-empty"><i class="bi bi-search me-1"></i>Nessun ufficio trovato<div class="mt-1 small">Prova con un nome di città diverso</div></div>`;
        dropdown.classList.add('show');
        return;
      }
      const gruppi = {};
      data.forEach(u => { const t = u.tipo || 'TRIBUNALE'; (gruppi[t] = gruppi[t] || []).push(u); });
      const tipiPresenti = GRUPPI_ORDER.filter(t => gruppi[t]);
      Object.keys(gruppi).forEach(t => { if (!tipiPresenti.includes(t)) tipiPresenti.push(t); });
      const multi = tipiPresenti.length > 1;
      let html = '';
      tipiPresenti.forEach(tipo => {
        if (multi) {
          const ic = TIPO_ICONS[tipo] || 'bi-building';
          html += `<div class="uff-group-header"><i class="bi ${ic}"></i>${TIPO_LABEL[tipo] || tipo}</div>`;
        }
        gruppi[tipo].forEach(u => {
          const idx = items.length; items.push(u);
          html += `<div class="uff-item" data-idx="${idx}" tabindex="-1">
            <i class="bi ${TIPO_ICONS[u.tipo] || 'bi-building'} uff-icon"></i>
            <div class="uff-body">
              <div class="uff-nome">${u.nome}</div>
              <div class="uff-sub">${u.distretto}${u.pec ? ' · <span class="font-monospace small">' + u.pec + '</span>' : ''}</div>
            </div>
            ${multi ? '' : `<span class="uff-tipo-badge uff-tipo-${u.tipo}">${TIPO_LABEL[u.tipo] || u.tipo}</span>`}
          </div>`;
        });
      });
      dropdown.innerHTML = html;
      dropdown.classList.add('show');
      dropdown.querySelectorAll('.uff-item').forEach(el => {
        el.addEventListener('mousedown', e => { e.preventDefault(); seleziona(items[+el.dataset.idx]); });
      });
    }

    function seleziona(u) {
      input.value  = u.nome;
      hidden.value = usaNome ? u.nome : u.codice;
      if (badgeLbl) badgeLbl.innerHTML = `<i class="bi ${TIPO_ICONS[u.tipo] || 'bi-building'} me-1"></i><strong>${u.nome}</strong> <span class="opacity-75">(${u.distretto})</span>`;
      if (badge)    badge.style.display = 'block';
      if (clearBtn) clearBtn.style.display = 'inline-flex';
      input.setCustomValidity('');
      chiudi();
    }

    function chiudi() { dropdown.classList.remove('show'); focusIdx = -1; }

    function muoviFocus(dir) {
      const els = dropdown.querySelectorAll('.uff-item');
      if (!els.length) return;
      els[focusIdx]?.classList.remove('focused');
      focusIdx = (focusIdx + dir + els.length) % els.length;
      els[focusIdx]?.classList.add('focused');
      els[focusIdx]?.scrollIntoView({ block: 'nearest' });
    }

    function cerca(q) {
      const url = `/api/uffici?q=${encodeURIComponent(q)}${tipoFiltro ? '&tipo=' + tipoFiltro : ''}`;
      fetch(url).then(r => r.json()).then(render).catch(() => chiudi());
    }

    input.addEventListener('input', function () {
      clearTimeout(timer);
      const q = this.value.trim();
      hidden.value = '';
      if (badge)    badge.style.display = 'none';
      if (clearBtn) clearBtn.style.display = q ? 'inline-flex' : 'none';
      if (q.length < 2) { chiudi(); return; }
      timer = setTimeout(() => cerca(q), 180);
    });

    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown')  { e.preventDefault(); muoviFocus(+1); return; }
      if (e.key === 'ArrowUp')    { e.preventDefault(); muoviFocus(-1); return; }
      if (e.key === 'Enter') {
        const els = dropdown.querySelectorAll('.uff-item');
        if (focusIdx >= 0 && els[focusIdx]) { e.preventDefault(); seleziona(items[focusIdx]); }
        return;
      }
      if (e.key === 'Escape') chiudi();
    });

    // Validazione al submit (solo se required)
    const form = input.closest('form');
    if (form && required) {
      form.addEventListener('submit', function (e) {
        if (!hidden.value && input.value.trim()) {
          fetch(`/api/uffici?q=${encodeURIComponent(input.value.trim())}${tipoFiltro ? '&tipo=' + tipoFiltro : ''}`)
            .then(r => r.json())
            .then(data => {
              if (data.length) { seleziona(data[0]); form.submit(); }
              else { input.setCustomValidity('Seleziona un ufficio dalla lista'); input.reportValidity(); }
            });
          e.preventDefault();
        } else if (!hidden.value) {
          input.setCustomValidity('Seleziona un ufficio dalla lista');
          input.reportValidity();
          e.preventDefault();
        }
      }, { once: false });
    }
    input.addEventListener('input', () => input.setCustomValidity(''));

    clearBtn && clearBtn.addEventListener('click', () => {
      input.value = ''; hidden.value = '';
      if (badge)    badge.style.display = 'none';
      if (clearBtn) clearBtn.style.display = 'none';
      chiudi(); input.focus();
    });

    document.addEventListener('click', e => {
      if (!root.contains(e.target)) chiudi();
    });

    window.addEventListener('scroll',  () => { if (dropdown.classList.contains('show')) posiziona(); }, { passive: true });
    window.addEventListener('resize',  () => { if (dropdown.classList.contains('show')) posiziona(); }, { passive: true });

    // ── Se c'è già un valore corrente, mostra il badge ───────────
    const initText  = root.dataset.uffpCurrentText  || '';
    const initValue = root.dataset.uffpCurrentValue || '';
    if (initText && initValue) {
      input.value  = initText;
      hidden.value = initValue;
      if (clearBtn) clearBtn.style.display = 'inline-flex';
      if (badge && badgeLbl) {
        badgeLbl.innerHTML = `<strong>${initText}</strong>`;
        badge.style.display = 'block';
      }
    }
  }

  // ── Auto-init su DOMContentLoaded ────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.uffp-root').forEach(el => initUfficioPicker(el.id));
  });

  global.initUfficioPicker = initUfficioPicker;
})(window);
