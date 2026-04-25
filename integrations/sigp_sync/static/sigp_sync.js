(() => {
  const root = document.querySelector('.sigp-shell');
  const API_BASE = (root?.dataset.apiBase || '/sigp-sync').replace(/\/$/, '');
  const state = {
    localCases: [],
    filteredCases: [],
    currentSnapshot: null,
    currentCaseId: null,
    activeTab: 'documenti',
    documentFilter: '',
    selectedDocs: new Set(),
  };

  const $ = (id) => document.getElementById(id);
  const qsa = (selector, scope = document) => Array.from(scope.querySelectorAll(selector));

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  }

  function compact(value, fallback = '-') {
    const text = String(value ?? '').trim();
    return text || fallback;
  }

  function formatDate(value) {
    if (!value) return '-';
    const raw = String(value);
    const parsed = new Date(raw);
    if (Number.isNaN(parsed.getTime())) return raw;
    return parsed.toLocaleString('it-IT', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: raw.includes('T') || raw.includes(':') ? '2-digit' : undefined,
      minute: raw.includes('T') || raw.includes(':') ? '2-digit' : undefined,
    });
  }

  function formatBytes(bytes) {
    const value = Number(bytes || 0);
    if (!value) return '-';
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = value;
    let i = 0;
    while (size >= 1024 && i < units.length - 1) {
      size /= 1024;
      i += 1;
    }
    return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
  }

  function setBusy(el, busy = true) {
    if (el) el.disabled = busy;
  }

  async function withBusy(el, fn) {
    setBusy(el, true);
    try {
      return await fn();
    } finally {
      setBusy(el, false);
    }
  }

  function toast(title, message = '', type = 'ok') {
    const host = $('toastHost');
    if (!host) return;
    const div = document.createElement('div');
    div.className = `sigp-toast sigp-toast--${type}`;
    div.innerHTML = `<strong>${escapeHtml(title)}</strong>${message ? `<div>${escapeHtml(message)}</div>` : ''}`;
    host.appendChild(div);
    window.setTimeout(() => div.remove(), 6500);
  }

  async function api(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: {
        ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
        ...(options.headers || {}),
      },
      ...options,
    });
    let json = null;
    try {
      json = await response.json();
    } catch (_) {
      json = { ok: false, message: 'Risposta non JSON dal server.' };
    }
    if (!response.ok || json.ok === false) {
      throw new Error(json.message || json.errore || `Errore HTTP ${response.status}`);
    }
    return json;
  }

  function setAdapterStatus(result) {
    const el = $('sigpAdapterStatus');
    if (!el) return;
    el.classList.remove('sigp-status--idle', 'sigp-status--ok', 'sigp-status--warn');
    el.classList.add(result?.ok ? 'sigp-status--ok' : 'sigp-status--warn');
    el.textContent = result?.adapter === 'local_connector' ? 'Local Connector raggiungibile' : 'Catalogo/payload autorizzato';
  }

  async function health() {
    const result = await api('/api/health');
    setAdapterStatus(result);
  }

  async function ensureSchema() {
    const result = await api('/api/schema/ensure', { method: 'POST' });
    toast('Database pronto', result.message || 'Schema verificato.');
    await refreshLocalCases();
  }

  async function preflight() {
    const result = await api('/api/preflight', { method: 'POST' });
    setAdapterStatus(result);
    toast('Preflight completato', result.message || 'Controllo locale completato.');
  }

  async function importPayload() {
    const rawText = $('payloadJson')?.value?.trim();
    if (!rawText) {
      toast('Payload mancante', 'Incolla il JSON reale ricevuto dal canale autorizzato.', 'warn');
      return;
    }
    let payload;
    try {
      payload = JSON.parse(rawText);
    } catch (error) {
      toast('JSON non valido', error.message, 'error');
      return;
    }
    const result = await api('/api/fascicoli/importa-payload', {
      method: 'POST',
      body: JSON.stringify({
        payload,
        fascicolo_locale_id: $('fascicoloLocaleId')?.value?.trim() || null,
      }),
    });
    toast('Payload importato', `${result.conteggi?.documenti || 0} documenti nel payload.`);
    await refreshLocalCases();
    if (result.sigp_fascicolo_id) await openSnapshot(result.sigp_fascicolo_id);
  }

  async function refreshLocalCases() {
    const result = await api('/api/fascicoli?limit=200');
    state.localCases = result.items || [];
    applyLocalFilter();
  }

  function applyLocalFilter() {
    const term = ($('localFilter')?.value || '').trim().toLowerCase();
    state.filteredCases = state.localCases.filter((item) => {
      const haystack = [item.ufficio, item.registro, item.numero_rg, item.anno_rg, item.giudice, item.oggetto, item.stato]
        .join(' ')
        .toLowerCase();
      return !term || haystack.includes(term);
    });
    renderLocalCases();
  }

  function renderLocalCases() {
    const box = $('fascicoliList');
    const count = $('localCount');
    if (!box) return;
    if (count) count.textContent = `${state.filteredCases.length} di ${state.localCases.length} fascicolo/i`;
    if (!state.filteredCases.length) {
      box.innerHTML = '<div class="sigp-list-item">Nessun fascicolo importato.</div>';
      return;
    }
    box.innerHTML = state.filteredCases.map((f) => {
      const rg = `${compact(f.registro, 'GDP')} ${compact(f.numero_rg)}/${compact(f.anno_rg)}`;
      return `
        <article class="sigp-list-item ${String(state.currentCaseId) === String(f.id) ? 'is-active' : ''}">
          <div class="sigp-list-title">${escapeHtml(rg)}</div>
          <div>${escapeHtml(compact(f.ufficio))}</div>
          <div class="sigp-list-meta">${escapeHtml(compact(f.oggetto, 'Oggetto non disponibile'))}</div>
          <div class="sigp-list-meta">Ultima sync: ${escapeHtml(formatDate(f.updated_at))}</div>
          <button class="btn btn-sm btn-outline-primary mt-2 js-open-case" data-id="${escapeHtml(f.id)}">Apri</button>
        </article>
      `;
    }).join('');
    qsa('.js-open-case', box).forEach((button) => {
      button.addEventListener('click', () => withBusy(button, async () => openSnapshot(button.dataset.id)).catch(showError));
    });
  }

  async function openSnapshot(id) {
    const result = await api(`/api/fascicoli/${encodeURIComponent(id)}`);
    state.currentSnapshot = result.snapshot;
    state.currentCaseId = Number(id);
    state.selectedDocs.clear();
    renderLocalCases();
    await refreshDocuments();
    renderSnapshot();
  }

  async function refreshDocuments() {
    if (!state.currentCaseId) return;
    try {
      const result = await api(`/api/fascicoli/${encodeURIComponent(state.currentCaseId)}/documenti`);
      if (state.currentSnapshot) state.currentSnapshot.documenti = result.items || [];
    } catch (error) {
      console.warn('Impossibile aggiornare documenti', error);
    }
  }

  function renderSnapshot() {
    const snapshot = state.currentSnapshot;
    if (!snapshot) return;
    const f = snapshot.fascicolo || {};
    $('emptyState').hidden = true;
    $('caseDetail').hidden = false;
    const rg = `${compact(f.registro, 'GDP')} ${compact(f.numero_rg)}/${compact(f.anno_rg)}`;
    $('detailTitle').textContent = compact(f.ufficio);
    $('detailSubtitle').textContent = `${rg} - ${compact(f.oggetto, 'Oggetto non disponibile')}`;
    $('sumRg').textContent = rg;
    $('sumStato').textContent = compact(f.stato);
    $('sumGiudice').textContent = compact(f.giudice);
    $('sumSync').textContent = formatDate(f.updated_at);
    setCount('countDocumenti', snapshot.documenti?.length || 0);
    setCount('countEventi', snapshot.eventi?.length || 0);
    setCount('countUdienze', snapshot.udienze?.length || 0);
    setCount('countParti', snapshot.parti?.length || 0);
    setCount('countComunicazioni', snapshot.comunicazioni?.length || 0);
    setCount('countLog', snapshot.log?.length || 0);
    renderActiveTab();
  }

  function setCount(id, value) {
    const el = $(id);
    if (el) el.textContent = String(value);
  }

  function renderActiveTab() {
    qsa('.sigp-tab').forEach((tab) => tab.classList.toggle('is-active', tab.dataset.tab === state.activeTab));
    qsa('.sigp-tab-panel').forEach((panel) => {
      panel.hidden = panel.id !== `tab-${state.activeTab}`;
    });
    if (state.activeTab === 'documenti') renderDocuments();
    if (state.activeTab === 'eventi') renderTimeline('eventsTimeline', state.currentSnapshot?.eventi || [], 'tipo_evento', 'descrizione', 'data_evento');
    if (state.activeTab === 'udienze') renderTimeline('udienzeTimeline', state.currentSnapshot?.udienze || [], 'tipo', 'descrizione', 'data_udienza');
    if (state.activeTab === 'parti') renderParti();
    if (state.activeTab === 'comunicazioni') renderComunicazioni();
    if (state.activeTab === 'log') renderLog();
  }

  function renderDocuments() {
    const box = $('documentsTable');
    if (!box) return;
    const term = state.documentFilter.trim().toLowerCase();
    const docs = (state.currentSnapshot?.documenti || []).filter((d) => {
      const haystack = [d.tipo_atto, d.nome_file, d.classificazione, d.depositante, d.documento_uid, d.sezione]
        .join(' ')
        .toLowerCase();
      return !term || haystack.includes(term);
    });
    setCount('countDocumenti', state.currentSnapshot?.documenti?.length || 0);
    if (!docs.length) {
      box.innerHTML = '<div class="p-3 sigp-muted">Nessun documento da mostrare. Usa "Anteprima documenti via Local Connector" o "Importa catalogo JSON".</div>';
      return;
    }
    box.innerHTML = `
      <table class="sigp-table">
        <thead>
          <tr>
            <th><input type="checkbox" id="selectAllDocs"></th>
            <th>Documento</th>
            <th>Classificazione</th>
            <th>Data</th>
            <th>Depositante</th>
            <th>Sezione</th>
            <th>Dimensione</th>
            <th>Stato</th>
            <th>Azioni</th>
          </tr>
        </thead>
        <tbody>
          ${docs.map((d) => {
            const checked = state.selectedDocs.has(Number(d.id)) ? 'checked' : '';
            const localUrl = `${API_BASE}/api/fascicoli/${encodeURIComponent(state.currentCaseId)}/documenti/${encodeURIComponent(d.id)}/file`;
            return `
              <tr>
                <td><input type="checkbox" class="js-doc-check" data-id="${escapeHtml(d.id)}" ${checked}></td>
                <td><div class="sigp-doc-name">${escapeHtml(compact(d.nome_file, 'Documento senza nome'))}</div><div class="sigp-doc-uid">${escapeHtml(compact(d.documento_uid, 'UID non disponibile'))}</div></td>
                <td>${escapeHtml(compact(d.classificazione || d.tipo_atto))}</td>
                <td>${escapeHtml(formatDate(d.data_deposito || d.data_documento))}</td>
                <td>${escapeHtml(compact(d.depositante))}</td>
                <td>${escapeHtml(compact(d.sezione))}</td>
                <td>${escapeHtml(formatBytes(d.dimensione_bytes))}</td>
                <td>${d.path_locale ? '<span class="sigp-badge sigp-badge--ok">Scaricato</span>' : '<span class="sigp-badge sigp-badge--todo">Da scaricare</span>'}</td>
                <td>
                  ${d.path_locale ? `<a class="btn btn-sm btn-outline-primary" href="${localUrl}" target="_blank" rel="noopener">Apri</a>` : ''}
                  <label class="btn btn-sm btn-outline-secondary mb-0">
                    Collega file
                    <input type="file" class="js-attach-file" data-id="${escapeHtml(d.id)}" hidden>
                  </label>
                </td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    `;
    $('selectAllDocs')?.addEventListener('change', (event) => {
      if (event.target.checked) docs.forEach((d) => state.selectedDocs.add(Number(d.id)));
      else docs.forEach((d) => state.selectedDocs.delete(Number(d.id)));
      renderDocuments();
    });
    qsa('.js-doc-check', box).forEach((input) => {
      input.addEventListener('change', () => {
        const id = Number(input.dataset.id);
        if (input.checked) state.selectedDocs.add(id);
        else state.selectedDocs.delete(id);
      });
    });
    qsa('.js-attach-file', box).forEach((input) => {
      input.addEventListener('change', () => attachLocalFile(input.dataset.id, input.files?.[0]).catch(showError));
    });
  }

  function renderTimeline(id, rows, titleKey, bodyKey, dateKey) {
    const box = $(id);
    if (!box) return;
    if (!rows.length) {
      box.innerHTML = '<div class="sigp-muted">Nessun elemento importato.</div>';
      return;
    }
    box.className = 'sigp-timeline';
    box.innerHTML = rows.map((e) => `
      <article class="sigp-timeline-item">
        <h4>${escapeHtml(compact(e[titleKey], 'Evento'))}</h4>
        <p>${escapeHtml(compact(e[bodyKey], 'Nessuna descrizione'))}</p>
        <small>${escapeHtml(formatDate(e[dateKey]))}</small>
      </article>
    `).join('');
  }

  function renderParti() {
    const box = $('partiTable');
    const rows = state.currentSnapshot?.parti || [];
    if (!rows.length) {
      box.innerHTML = '<div class="p-3 sigp-muted">Nessuna parte importata.</div>';
      return;
    }
    box.innerHTML = `
      <table class="sigp-table"><thead><tr><th>Ruolo</th><th>Nominativo</th><th>CF / P.IVA</th><th>Difensore</th></tr></thead><tbody>
        ${rows.map((p) => `
          <tr><td>${escapeHtml(compact(p.ruolo))}</td><td>${escapeHtml(compact([p.nome, p.cognome].filter(Boolean).join(' ') || p.denominazione, 'Nominativo non disponibile'))}</td><td>${escapeHtml(compact([p.codice_fiscale, p.partita_iva].filter(Boolean).join(' - ')))}</td><td>${escapeHtml(compact(p.difensore))}</td></tr>
        `).join('')}
      </tbody></table>`;
  }

  function renderComunicazioni() {
    const box = $('comunicazioniTable');
    const rows = state.currentSnapshot?.comunicazioni || [];
    if (!rows.length) {
      box.innerHTML = '<div class="sigp-muted">Nessuna comunicazione importata.</div>';
      return;
    }
    box.innerHTML = rows.map((c) => `
      <article class="sigp-timeline-item">
        <h4>${escapeHtml(compact(c.oggetto, 'Comunicazione'))}</h4>
        <p>${escapeHtml(compact(c.tipo))} - ${escapeHtml(compact(c.mittente))}</p>
        <small>${escapeHtml(formatDate(c.data_comunicazione))}</small>
      </article>
    `).join('');
  }

  function renderLog() {
    const box = $('syncLogTable');
    const rows = state.currentSnapshot?.log || [];
    if (!rows.length) {
      box.innerHTML = '<div class="p-3 sigp-muted">Nessun log disponibile.</div>';
      return;
    }
    box.innerHTML = `
      <table class="sigp-table"><thead><tr><th>Data</th><th>Azione</th><th>Esito</th><th>Messaggio</th></tr></thead><tbody>
        ${rows.map((l) => `<tr><td>${escapeHtml(formatDate(l.created_at))}</td><td>${escapeHtml(compact(l.azione))}</td><td>${escapeHtml(compact(l.esito))}</td><td>${escapeHtml(compact(l.messaggio))}</td></tr>`).join('')}
      </tbody></table>`;
  }

  async function previewDocumentsFromConnector() {
    if (!state.currentCaseId) return;
    const result = await api(`/api/fascicoli/${encodeURIComponent(state.currentCaseId)}/documenti/preview-local-connector`, {
      method: 'POST',
      body: JSON.stringify({}),
    });
    toast('Catalogo acquisito', result.message || `${result.total || 0} documenti.`);
    if (result.documents && state.currentSnapshot) state.currentSnapshot.documenti = result.documents;
    await refreshDocuments();
    renderSnapshot();
  }

  async function importDocumentCatalog() {
    if (!state.currentCaseId) return;
    const rawText = $('documentCatalogJson')?.value?.trim();
    if (!rawText) {
      toast('Catalogo mancante', "Incolla il JSON con l'elenco documenti.", 'warn');
      return;
    }
    let catalog;
    try {
      catalog = JSON.parse(rawText);
    } catch (error) {
      toast('JSON catalogo non valido', error.message, 'error');
      return;
    }
    const result = await api(`/api/fascicoli/${encodeURIComponent(state.currentCaseId)}/documenti/importa-catalogo`, {
      method: 'POST',
      body: JSON.stringify({ catalogo: catalog, source: 'ui_catalog_json' }),
    });
    toast('Catalogo documenti importato', `${result.inserted || 0} nuovi, ${result.updated || 0} aggiornati.`);
    if (result.documents && state.currentSnapshot) state.currentSnapshot.documenti = result.documents;
    renderSnapshot();
  }

  async function downloadDocuments(mode = 'selected') {
    if (!state.currentCaseId) return;
    const ids = mode === 'new_only' ? [] : Array.from(state.selectedDocs);
    if (mode !== 'new_only' && !ids.length) {
      toast('Nessun documento selezionato', 'Seleziona almeno un documento dal catalogo.', 'warn');
      return;
    }
    const result = await api(`/api/fascicoli/${encodeURIComponent(state.currentCaseId)}/documenti/download-local-connector`, {
      method: 'POST',
      body: JSON.stringify({ document_ids: mode === 'new_only' ? (state.currentSnapshot?.documenti || []).filter((d) => d.scaricabile && !d.path_locale).map((d) => d.id) : ids }),
    });
    toast('Download documenti', result.message || 'Operazione completata.', result.errors?.length ? 'warn' : 'ok');
    if (result.documents && state.currentSnapshot) state.currentSnapshot.documenti = result.documents;
    renderSnapshot();
  }

  async function attachLocalFile(documentId, file) {
    if (!state.currentCaseId || !documentId || !file) return;
    const form = new FormData();
    form.append('file', file);
    const result = await api(`/api/fascicoli/${encodeURIComponent(state.currentCaseId)}/documenti/${encodeURIComponent(documentId)}/allega-file`, {
      method: 'POST',
      body: form,
    });
    toast('File collegato', result.message || 'Documento aggiornato.');
    if (result.documents && state.currentSnapshot) state.currentSnapshot.documenti = result.documents;
    renderSnapshot();
  }

  function showError(error) {
    console.error(error);
    toast('Errore', error.message || String(error), 'error');
  }

  function bindEvents() {
    $('btnEnsureSchema')?.addEventListener('click', (event) => withBusy(event.currentTarget, ensureSchema).catch(showError));
    $('btnPreflight')?.addEventListener('click', (event) => withBusy(event.currentTarget, preflight).catch(showError));
    $('btnImportPayload')?.addEventListener('click', (event) => withBusy(event.currentTarget, importPayload).catch(showError));
    $('btnRefresh')?.addEventListener('click', (event) => withBusy(event.currentTarget, refreshLocalCases).catch(showError));
    $('btnPreviewDocs')?.addEventListener('click', (event) => withBusy(event.currentTarget, previewDocumentsFromConnector).catch(showError));
    $('btnImportDocumentCatalog')?.addEventListener('click', (event) => withBusy(event.currentTarget, importDocumentCatalog).catch(showError));
    $('btnDownloadSelected')?.addEventListener('click', (event) => withBusy(event.currentTarget, () => downloadDocuments('selected')).catch(showError));
    $('btnDownloadNew')?.addEventListener('click', (event) => withBusy(event.currentTarget, () => downloadDocuments('new_only')).catch(showError));
    $('btnToggleCatalogImport')?.addEventListener('click', () => {
      const box = $('catalogImportBox');
      if (box) box.hidden = !box.hidden;
    });
    $('localFilter')?.addEventListener('input', applyLocalFilter);
    $('documentFilter')?.addEventListener('input', (event) => {
      state.documentFilter = event.target.value || '';
      renderDocuments();
    });
    qsa('.sigp-tab').forEach((tab) => tab.addEventListener('click', () => {
      state.activeTab = tab.dataset.tab;
      renderActiveTab();
    }));
  }

  document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    health().catch(() => {});
    refreshLocalCases().catch(() => {});
  });
})();
