(() => {
  const root = document.querySelector(".sigp-shell");
  const API_BASE = (root?.dataset.apiBase || "/sigp-sync").replace(/\/$/, "");
  const state = { localCases: [], filteredCases: [], currentSnapshot: null, currentCaseId: null, activeTab: "documenti", documentFilter: "" };
  const $ = (id) => document.getElementById(id);
  const qsa = (selector, scope = document) => [...scope.querySelectorAll(selector)];

  function escapeHtml(value) {
    return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }
  function compact(value, fallback = "-") {
    const text = String(value ?? "").trim();
    return text || fallback;
  }
  function formatDate(value) {
    if (!value) return "-";
    const raw = String(value);
    const parsed = new Date(raw);
    if (Number.isNaN(parsed.getTime())) return raw;
    return parsed.toLocaleString("it-IT", { year: "numeric", month: "2-digit", day: "2-digit", hour: raw.includes("T") || raw.includes(":") ? "2-digit" : undefined, minute: raw.includes("T") || raw.includes(":") ? "2-digit" : undefined });
  }
  function formatBytes(bytes) {
    const value = Number(bytes || 0);
    if (!value) return "-";
    const units = ["B", "KB", "MB", "GB"];
    let size = value;
    let i = 0;
    while (size >= 1024 && i < units.length - 1) { size /= 1024; i += 1; }
    return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
  }
  function setBusy(el, busy = true) {
    if (!el) return;
    el.disabled = busy;
  }
  async function withBusy(el, fn) {
    setBusy(el, true);
    try { return await fn(); } finally { setBusy(el, false); }
  }
  function toast(title, message = "", type = "ok") {
    const host = $("toastHost");
    if (!host) return;
    const div = document.createElement("div");
    div.className = `sigp-toast sigp-toast--${type}`;
    div.innerHTML = `<strong>${escapeHtml(title)}</strong>${message ? `<p>${escapeHtml(message)}</p>` : ""}`;
    host.appendChild(div);
    window.setTimeout(() => div.remove(), 5200);
  }
  async function api(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
    let json = null;
    try { json = await response.json(); } catch (_) { json = { ok: false, message: "Risposta non JSON dal server." }; }
    if (!response.ok || json.ok === false) throw new Error(json.message || json.errore || `Errore HTTP ${response.status}`);
    return json;
  }
  function setAdapterStatus(result) {
    const el = $("sigpAdapterStatus");
    if (!el) return;
    el.classList.remove("sigp-status--idle", "sigp-status--ok", "sigp-status--warn");
    el.classList.add(result?.ok ? "sigp-status--ok" : "sigp-status--warn");
    el.textContent = result?.ok ? "Sync autorizzata pronta" : "Verifica richiesta";
  }
  async function health() {
    const result = await api("/api/health");
    setAdapterStatus(result);
    toast("Modulo SIGP attivo", result.messaggio || "Health check completato.");
  }
  async function ensureSchema() {
    const result = await api("/api/schema/ensure", { method: "POST" });
    toast("Database pronto", result.message || "Schema verificato.");
    await refreshLocalCases();
  }
  async function preflight() {
    const result = await api("/api/preflight", { method: "POST" });
    setAdapterStatus(result);
    toast("Preflight completato", result.message || "Controllo locale richiesto.");
  }
  async function importPayload() {
    const rawText = $("payloadJson")?.value?.trim();
    if (!rawText) {
      toast("Payload mancante", "Incolla il JSON reale ricevuto dal canale autorizzato.", "warn");
      return;
    }
    let payload;
    try { payload = JSON.parse(rawText); } catch (error) {
      toast("JSON non valido", error.message, "error");
      return;
    }
    const result = await api("/api/fascicoli/importa-payload", {
      method: "POST",
      body: JSON.stringify({ payload, fascicolo_locale_id: $("fascicoloLocaleId")?.value?.trim() || null }),
    });
    toast("Payload importato", `${result.conteggi?.documenti || 0} documenti normalizzati.`);
    await refreshLocalCases();
    if (result.sigp_fascicolo_id) await openSnapshot(result.sigp_fascicolo_id);
  }
  async function refreshLocalCases() {
    const result = await api("/api/fascicoli?limit=100");
    state.localCases = result.items || [];
    applyLocalFilter();
  }
  function applyLocalFilter() {
    const term = ($("localFilter")?.value || "").trim().toLowerCase();
    state.filteredCases = state.localCases.filter((item) => !term || [item.ufficio, item.registro, item.numero_rg, item.anno_rg, item.giudice, item.oggetto, item.stato].join(" ").toLowerCase().includes(term));
    renderLocalCases();
  }
  function renderLocalCases() {
    const box = $("fascicoliList");
    const count = $("localCount");
    if (!box) return;
    if (count) count.textContent = `${state.filteredCases.length} di ${state.localCases.length} fascicolo/i`;
    if (!state.filteredCases.length) {
      box.innerHTML = `<div class="sigp-empty-row">Nessun fascicolo importato.</div>`;
      return;
    }
    box.innerHTML = state.filteredCases.map((f) => `
      <article class="sigp-case-card${Number(f.id) === Number(state.currentCaseId) ? " is-active" : ""}">
        <span class="sigp-pill">${escapeHtml(compact(f.registro, "GDP"))} ${escapeHtml(compact(f.numero_rg))}/${escapeHtml(compact(f.anno_rg))}</span>
        <strong class="sigp-card-title">${escapeHtml(compact(f.ufficio))}</strong>
        <div class="sigp-card-small">${escapeHtml(compact(f.oggetto, "Oggetto non disponibile"))}</div>
        <div class="sigp-card-meta">Ultima sync: ${escapeHtml(formatDate(f.updated_at))}</div>
        <button class="sigp-btn sigp-btn--ghost js-open-case" type="button" data-id="${escapeHtml(f.id)}">Apri</button>
      </article>
    `).join("");
    qsa(".js-open-case", box).forEach((button) => button.addEventListener("click", () => withBusy(button, async () => openSnapshot(button.dataset.id)).catch(showError)));
  }
  async function openSnapshot(id) {
    const result = await api(`/api/fascicoli/${encodeURIComponent(id)}`);
    state.currentSnapshot = result.snapshot;
    state.currentCaseId = Number(id);
    renderLocalCases();
    renderSnapshot();
  }
  function renderSnapshot() {
    const snapshot = state.currentSnapshot;
    if (!snapshot) return;
    const f = snapshot.fascicolo || {};
    $("emptyState").hidden = true;
    $("caseDetail").hidden = false;
    const rg = `${compact(f.registro, "GDP")} ${compact(f.numero_rg)}/${compact(f.anno_rg)}`;
    $("detailTitle").textContent = compact(f.ufficio);
    $("detailSubtitle").textContent = `${rg} - ${compact(f.oggetto, "Oggetto non disponibile")}`;
    $("sumRg").textContent = rg;
    $("sumStato").textContent = compact(f.stato);
    $("sumGiudice").textContent = compact(f.giudice);
    $("sumSync").textContent = formatDate(f.updated_at);
    setCount("countDocumenti", snapshot.documenti?.length || 0);
    setCount("countEventi", snapshot.eventi?.length || 0);
    setCount("countUdienze", snapshot.udienze?.length || 0);
    setCount("countParti", snapshot.parti?.length || 0);
    setCount("countComunicazioni", snapshot.comunicazioni?.length || 0);
    setCount("countLog", snapshot.log?.length || 0);
    renderActiveTab();
  }
  function setCount(id, value) { const el = $(id); if (el) el.textContent = String(value); }
  function renderActiveTab() {
    qsa(".sigp-tab").forEach((tab) => tab.classList.toggle("is-active", tab.dataset.tab === state.activeTab));
    qsa(".sigp-tab-panel").forEach((panel) => { panel.hidden = panel.id !== `tab-${state.activeTab}`; });
    if (state.activeTab === "documenti") renderDocuments();
    if (state.activeTab === "eventi") renderTimeline("eventsTimeline", state.currentSnapshot?.eventi || [], "tipo_evento", "descrizione", "data_evento");
    if (state.activeTab === "udienze") renderTimeline("udienzeTimeline", state.currentSnapshot?.udienze || [], "tipo", "descrizione", "data_udienza");
    if (state.activeTab === "parti") renderParti();
    if (state.activeTab === "comunicazioni") renderComunicazioni();
    if (state.activeTab === "log") renderLog();
  }
  function renderDocuments() {
    const box = $("documentsTable");
    if (!box) return;
    const term = state.documentFilter.trim().toLowerCase();
    const docs = (state.currentSnapshot?.documenti || []).filter((d) => !term || [d.tipo_atto, d.nome_file, d.classificazione, d.depositante, d.documento_uid].join(" ").toLowerCase().includes(term));
    if (!docs.length) { box.innerHTML = `<div class="sigp-empty-row">Nessun documento da mostrare.</div>`; return; }
    box.innerHTML = `<table class="sigp-table"><thead><tr><th>Documento</th><th>Classificazione</th><th>Data</th><th>Depositante</th><th>Sezione</th><th>Dimensione</th></tr></thead><tbody>${docs.map((d) => `<tr><td><strong>${escapeHtml(compact(d.nome_file, "Documento senza nome"))}</strong><br><code>${escapeHtml(compact(d.documento_uid, "UID non disponibile"))}</code></td><td>${escapeHtml(compact(d.classificazione || d.tipo_atto))}</td><td>${escapeHtml(formatDate(d.data_deposito || d.data_documento))}</td><td>${escapeHtml(compact(d.depositante))}</td><td>${escapeHtml(compact(d.sezione))}</td><td>${escapeHtml(formatBytes(d.dimensione_bytes))}</td></tr>`).join("")}</tbody></table>`;
  }
  function renderTimeline(id, rows, titleKey, bodyKey, dateKey) {
    const box = $(id);
    if (!box) return;
    if (!rows.length) { box.innerHTML = `<div class="sigp-empty-row">Nessun elemento importato.</div>`; return; }
    box.innerHTML = rows.map((e) => `<article class="sigp-timeline-item"><h4>${escapeHtml(compact(e[titleKey], "Evento"))}</h4><p>${escapeHtml(compact(e[bodyKey], "Nessuna descrizione"))}</p><div class="sigp-card-meta">${escapeHtml(formatDate(e[dateKey]))}</div></article>`).join("");
  }
  function renderParti() {
    const box = $("partiTable");
    const rows = state.currentSnapshot?.parti || [];
    if (!rows.length) { box.innerHTML = `<div class="sigp-empty-row">Nessuna parte importata.</div>`; return; }
    box.innerHTML = `<table class="sigp-table"><thead><tr><th>Ruolo</th><th>Nominativo</th><th>CF / P.IVA</th><th>Difensore</th></tr></thead><tbody>${rows.map((p) => `<tr><td>${escapeHtml(compact(p.ruolo))}</td><td><strong>${escapeHtml(compact([p.nome, p.cognome].filter(Boolean).join(" ") || p.denominazione, "Nominativo non disponibile"))}</strong></td><td>${escapeHtml(compact([p.codice_fiscale, p.partita_iva].filter(Boolean).join(" - ")))}</td><td>${escapeHtml(compact(p.difensore))}</td></tr>`).join("")}</tbody></table>`;
  }
  function renderComunicazioni() {
    const box = $("comunicazioniTable");
    const rows = state.currentSnapshot?.comunicazioni || [];
    if (!rows.length) { box.innerHTML = `<div class="sigp-empty-row">Nessuna comunicazione importata.</div>`; return; }
    box.innerHTML = `<table class="sigp-table"><thead><tr><th>Data</th><th>Tipo</th><th>Oggetto</th><th>Mittente</th></tr></thead><tbody>${rows.map((c) => `<tr><td>${escapeHtml(formatDate(c.data_comunicazione))}</td><td>${escapeHtml(compact(c.tipo))}</td><td><strong>${escapeHtml(compact(c.oggetto))}</strong></td><td>${escapeHtml(compact(c.mittente))}</td></tr>`).join("")}</tbody></table>`;
  }
  function renderLog() {
    const box = $("syncLogTable");
    const rows = state.currentSnapshot?.log || [];
    if (!rows.length) { box.innerHTML = `<div class="sigp-empty-row">Nessun log disponibile.</div>`; return; }
    box.innerHTML = `<table class="sigp-table"><thead><tr><th>Data</th><th>Azione</th><th>Esito</th><th>Messaggio</th></tr></thead><tbody>${rows.map((l) => `<tr><td>${escapeHtml(formatDate(l.created_at))}</td><td>${escapeHtml(compact(l.azione))}</td><td>${escapeHtml(compact(l.esito))}</td><td>${escapeHtml(compact(l.messaggio))}</td></tr>`).join("")}</tbody></table>`;
  }
  async function downloadDocuments() {
    if (!state.currentCaseId) return;
    await api(`/api/fascicoli/${encodeURIComponent(state.currentCaseId)}/download`, { method: "POST", body: JSON.stringify({ mode: "new_only" }) });
  }
  function showError(error) {
    console.error(error);
    toast("Errore", error.message || String(error), "error");
  }
  function bindEvents() {
    $("btnHealth")?.addEventListener("click", (event) => withBusy(event.currentTarget, health).catch(showError));
    $("btnEnsureSchema")?.addEventListener("click", (event) => withBusy(event.currentTarget, ensureSchema).catch(showError));
    $("btnPreflight")?.addEventListener("click", (event) => withBusy(event.currentTarget, preflight).catch(showError));
    $("btnImportPayload")?.addEventListener("click", (event) => withBusy(event.currentTarget, importPayload).catch(showError));
    $("btnRefresh")?.addEventListener("click", (event) => withBusy(event.currentTarget, refreshLocalCases).catch(showError));
    $("btnDownloadNew")?.addEventListener("click", (event) => withBusy(event.currentTarget, downloadDocuments).catch(showError));
    $("localFilter")?.addEventListener("input", applyLocalFilter);
    $("documentFilter")?.addEventListener("input", (event) => { state.documentFilter = event.target.value || ""; renderDocuments(); });
    qsa(".sigp-tab").forEach((tab) => tab.addEventListener("click", () => { state.activeTab = tab.dataset.tab; renderActiveTab(); }));
  }
  document.addEventListener("DOMContentLoaded", () => {
    bindEvents();
    health().catch(() => {});
    refreshLocalCases().catch(() => {});
  });
})();
