let currentDraftId = null;
let cachedDrafts = [];
let reviewToast = null;

const reviewTenantSlug = String(window.REVIEW_TENANT_SLUG || '').trim();
const actionableButtonIds = ['btn-save', 'btn-approve', 'btn-reject', 'btn-open-sql', 'btn-publish'];
const dateFormatter = new Intl.DateTimeFormat('it-IT', {
  dateStyle: 'short',
  timeStyle: 'short'
});

function escapeHtml(str) {
  return String(str ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

function formatDate(value) {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return dateFormatter.format(parsed);
}

function badge(label, cls = '') {
  return `<span class="review-badge ${cls}">${escapeHtml(label)}</span>`;
}

function showToast(message) {
  const body = document.getElementById('review-toast-body');
  body.textContent = message;
  if (!reviewToast) {
    reviewToast = new bootstrap.Toast(document.getElementById('review-toast'));
  }
  reviewToast.show();
}

function reviewUrl(path) {
  const url = new URL(`${window.location.origin}${window.REVIEW_API_BASE}${path}`);
  if (reviewTenantSlug) {
    url.searchParams.set('tenant_slug', reviewTenantSlug);
  }
  return `${url.pathname}${url.search}`;
}

function setActionState(enabled) {
  actionableButtonIds.forEach((id) => {
    const node = document.getElementById(id);
    if (node) {
      node.disabled = !enabled;
    }
  });
}

function resetDraftPanel(message) {
  currentDraftId = null;
  setActionState(false);
  document.getElementById('draft-empty').classList.remove('d-none');
  document.getElementById('draft-empty').textContent = message;
  document.getElementById('draft-meta').classList.add('d-none');
  document.getElementById('spec-editor').value = '';
  document.getElementById('validation-view').textContent = '';
  document.getElementById('sql-view').textContent = '';
  document.getElementById('retrieval-list').innerHTML = '';
  document.getElementById('retrieval-empty').classList.remove('d-none');
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  let payload = {};
  try {
    payload = await response.json();
  } catch (error) {
    payload = {};
  }
  if (!response.ok || payload.ok === false) {
    const message = payload.errore || 'Operazione non riuscita.';
    throw new Error(message);
  }
  return payload;
}

function renderRetrievalExamples(examples) {
  const list = document.getElementById('retrieval-list');
  const empty = document.getElementById('retrieval-empty');
  const rows = Array.isArray(examples) ? examples : [];
  if (!rows.length) {
    list.innerHTML = '';
    empty.classList.remove('d-none');
    return;
  }

  empty.classList.add('d-none');
  list.innerHTML = rows.map((row) => {
    const label = escapeHtml(row.name || row.procedure_code || row.subbranch_code || 'Esempio correlato');
    const channel = escapeHtml(row.channel_code || '-');
    const level = escapeHtml(row.complexity_level || row.risk_level || '-');
    return `
      <div class="review-retrieval-item">
        <div class="review-retrieval-title">${label}</div>
        <div class="review-retrieval-meta">
          ${badge(`Canale ${channel}`)}
          ${badge(`Profilo ${level}`)}
        </div>
      </div>
    `;
  }).join('');
}

function renderDraftList(data) {
  const filter = (document.getElementById('filter-text').value || '').toLowerCase().trim();
  const list = document.getElementById('draft-list');
  const filtered = data.filter((draft) => {
    const haystack = `${draft.subbranch_code || ''} ${draft.procedure_code || ''} ${draft.status || ''}`.toLowerCase();
    return haystack.includes(filter);
  });

  document.getElementById('draft-count').textContent = filtered.length;
  if (!filtered.length) {
    list.innerHTML = `
      <div class="review-list-empty">
        ${filter
          ? 'Nessuna bozza corrisponde al filtro inserito.'
          : 'Nessuna bozza disponibile. Torna alla dashboard e genera prima auditor, gap queue e draft AI.'}
      </div>
    `;
    return filtered;
  }

  list.innerHTML = filtered.map((draft) => `
    <button class="review-draft-item ${currentDraftId === draft.id ? 'is-active' : ''}" data-id="${draft.id}">
      <div class="review-draft-top">
        <div class="review-draft-title">${escapeHtml(draft.subbranch_code)}</div>
        ${badge(draft.status, `status-${String(draft.status).toLowerCase()}`)}
      </div>
      <div class="review-draft-meta">
        ${badge(draft.risk_level || 'MEDIUM', `risk-${String(draft.risk_level || '').toLowerCase()}`)}
        ${badge(draft.auto_publish_eligible ? 'Auto si' : 'Auto no', draft.auto_publish_eligible ? 'auto-yes' : '')}
        <span>${escapeHtml(draft.procedure_code || '-')}</span>
      </div>
    </button>
  `).join('');

  document.querySelectorAll('.review-draft-item').forEach((button) => {
    button.addEventListener('click', () => loadDraft(Number(button.dataset.id)));
  });
  return filtered;
}

async function fetchDrafts() {
  try {
    const data = await fetchJson(reviewUrl('/drafts'));
    cachedDrafts = Array.isArray(data) ? data : [];
    const visibleDrafts = renderDraftList(cachedDrafts);

    if (!cachedDrafts.length) {
      resetDraftPanel('Nessuna bozza disponibile. Per popolare questa schermata esegui auditor, gap queue e generazione AI dalla dashboard.');
      return;
    }

    if (!visibleDrafts.length) {
      resetDraftPanel('Il filtro non restituisce alcuna bozza. Modifica o svuota il filtro per continuare.');
      return;
    }

    const stillVisible = visibleDrafts.some((draft) => draft.id === currentDraftId);
    if (!stillVisible) {
      await loadDraft(Number(visibleDrafts[0].id));
      return;
    }
    renderDraftList(cachedDrafts);
  } catch (error) {
    cachedDrafts = [];
    renderDraftList([]);
    resetDraftPanel(`Impossibile caricare la coda di revisione: ${error.message}`);
    showToast(error.message);
  }
}

async function loadDraft(id) {
  try {
    currentDraftId = id;
    setActionState(true);
    renderDraftList(cachedDrafts);
    const data = await fetchJson(reviewUrl(`/drafts/${id}`));

    document.getElementById('draft-empty').classList.add('d-none');
    document.getElementById('draft-meta').classList.remove('d-none');
    document.getElementById('meta-subbranch').textContent = data.subbranch_code || '-';
    document.getElementById('meta-procedure').textContent = data.procedure_code || '-';
    document.getElementById('meta-status').textContent = data.status || '-';
    document.getElementById('meta-risk').textContent = data.risk_level || '-';
    document.getElementById('meta-score').textContent = data.validation_report_json?.score ?? 0;
    document.getElementById('meta-warnings-count').textContent =
      `${(data.validation_report_json?.warnings || []).length} warning`;
    document.getElementById('chip-auto-publish').textContent =
      `Auto publish: ${data.auto_publish_eligible ? 'si' : 'no'}`;
    document.getElementById('chip-created-at').textContent = `Creato: ${formatDate(data.created_at)}`;
    document.getElementById('chip-reviewed-at').textContent = `Review: ${formatDate(data.reviewed_at)}`;
    document.getElementById('spec-editor').value = JSON.stringify(data.spec_json || {}, null, 2);
    document.getElementById('validation-view').textContent = JSON.stringify(data.validation_report_json || {}, null, 2);
    document.getElementById('sql-view').textContent = data.sql_preview || '';
    renderRetrievalExamples(data.retrieval_examples_json || []);
  } catch (error) {
    resetDraftPanel(`Impossibile caricare la bozza selezionata: ${error.message}`);
    showToast(error.message);
  }
}

async function saveDraft() {
  if (!currentDraftId) return;
  let spec;
  try {
    spec = JSON.parse(document.getElementById('spec-editor').value);
  } catch (error) {
    showToast('JSON non valido. Correggi il contenuto prima di salvare.');
    return;
  }

  try {
    const data = await fetchJson(reviewUrl(`/drafts/${currentDraftId}/save`), {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({spec_json: spec, tenant_slug: reviewTenantSlug})
    });
    document.getElementById('validation-view').textContent = JSON.stringify(data.validation || {}, null, 2);
    showToast('Bozza salvata correttamente.');
    await fetchDrafts();
  } catch (error) {
    showToast(error.message);
  }
}

async function approveDraft() {
  if (!currentDraftId) return;
  try {
    await fetchJson(reviewUrl(`/drafts/${currentDraftId}/approve`), {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({reviewer: 'review-ui', tenant_slug: reviewTenantSlug})
    });
    showToast('Bozza approvata.');
    await fetchDrafts();
  } catch (error) {
    showToast(error.message);
  }
}

async function rejectDraft() {
  if (!currentDraftId) return;
  try {
    await fetchJson(reviewUrl(`/drafts/${currentDraftId}/reject`), {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({reviewer: 'review-ui', tenant_slug: reviewTenantSlug})
    });
    showToast('Bozza rifiutata.');
    await fetchDrafts();
  } catch (error) {
    showToast(error.message);
  }
}

async function previewSql() {
  if (!currentDraftId) return;
  try {
    const data = await fetchJson(reviewUrl(`/drafts/${currentDraftId}/sql`));
    document.getElementById('sql-view').textContent = data.sql || '';
    showToast('Anteprima SQL aggiornata.');
  } catch (error) {
    showToast(error.message);
  }
}

async function publishDraft() {
  if (!currentDraftId) return;
  try {
    await fetchJson(reviewUrl(`/drafts/${currentDraftId}/publish`), {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({tenant_slug: reviewTenantSlug})
    });
    showToast('Bozza pubblicata e database aggiornato.');
    await fetchDrafts();
  } catch (error) {
    showToast(error.message);
  }
}

document.getElementById('btn-refresh').addEventListener('click', fetchDrafts);
document.getElementById('btn-save').addEventListener('click', saveDraft);
document.getElementById('btn-approve').addEventListener('click', approveDraft);
document.getElementById('btn-reject').addEventListener('click', rejectDraft);
document.getElementById('btn-open-sql').addEventListener('click', previewSql);
document.getElementById('btn-publish').addEventListener('click', publishDraft);
document.getElementById('filter-text').addEventListener('input', () => {
  const visibleDrafts = renderDraftList(cachedDrafts);
  if (!visibleDrafts.length) {
    resetDraftPanel('Il filtro non restituisce alcuna bozza. Modifica o svuota il filtro per continuare.');
    return;
  }
  if (!visibleDrafts.some((draft) => draft.id === currentDraftId)) {
    loadDraft(Number(visibleDrafts[0].id));
  }
});

setActionState(false);
resetDraftPanel('Caricamento della coda revisioni in corso...');
fetchDrafts();
