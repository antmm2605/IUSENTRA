let currentDraftId = null;
let cachedDrafts = [];
let currentDraftDetail = null;
let reviewToast = null;

const reviewTenantSlug = String(window.REVIEW_TENANT_SLUG || '').trim();
const actionableButtonIds = ['btn-save', 'btn-approve', 'btn-reject', 'btn-open-sql', 'btn-publish'];
const dateFormatter = new Intl.DateTimeFormat('it-IT', {
  timeZone: 'Europe/Rome',
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
  currentDraftDetail = null;
  setActionState(false);
  document.getElementById('draft-empty').classList.remove('d-none');
  document.getElementById('draft-empty').textContent = message;
  document.getElementById('draft-meta').classList.add('d-none');
  document.getElementById('spec-editor').value = '';
  document.getElementById('validation-view').textContent = '';
  document.getElementById('sql-view').textContent = '';
  document.getElementById('retrieval-list').innerHTML = '';
  document.getElementById('retrieval-empty').classList.remove('d-none');
  document.getElementById('diff-list').innerHTML = '';
  document.getElementById('diff-empty').classList.remove('d-none');
  document.getElementById('history-list').innerHTML = '';
  document.getElementById('history-empty').classList.remove('d-none');
  document.getElementById('approval-notes').value = '';
  document.getElementById('reject-notes').value = '';
  document.getElementById('review-signature').value = '';
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

function renderReviewDiff(diffPayload) {
  const list = document.getElementById('diff-list');
  const empty = document.getElementById('diff-empty');
  const sections = Array.isArray(diffPayload?.sections) ? diffPayload.sections : [];
  if (!sections.length) {
    list.innerHTML = '';
    empty.classList.remove('d-none');
    return;
  }

  empty.classList.add('d-none');
  list.innerHTML = sections.map((section) => {
    const fields = Array.isArray(section.fields) ? section.fields : [];
    const fieldHtml = fields.length
      ? `
        <div class="mt-2 small">
          ${fields.map((field) => `
            <div class="border rounded-2 px-2 py-1 mb-1 bg-light-subtle">
              <strong>${escapeHtml(field.field)}</strong>: ${escapeHtml(field.before)} -> ${escapeHtml(field.after)}
            </div>
          `).join('')}
        </div>
      `
      : '';
    return `
      <div class="border rounded-3 p-3">
        <div class="d-flex flex-wrap justify-content-between gap-2 mb-2">
          <div class="fw-semibold">${escapeHtml(section.section || 'Sezione')}</div>
          ${badge(section.change || 'updated', `status-${String(section.change || '').toLowerCase()}`)}
        </div>
        <div class="small text-muted">Prima: ${escapeHtml(section.before)}</div>
        <div class="small text-muted">Dopo: ${escapeHtml(section.after)}</div>
        ${fieldHtml}
      </div>
    `;
  }).join('');
}

function renderReviewHistory(historyRows) {
  const list = document.getElementById('history-list');
  const empty = document.getElementById('history-empty');
  const rows = Array.isArray(historyRows) ? historyRows : [];
  if (!rows.length) {
    list.innerHTML = '';
    empty.classList.remove('d-none');
    return;
  }

  empty.classList.add('d-none');
  list.innerHTML = rows.map((row) => `
    <div class="border rounded-3 p-3">
      <div class="d-flex flex-wrap justify-content-between gap-2 mb-2">
        <div class="fw-semibold">${escapeHtml(row.review_action || 'evento')}</div>
        <div class="small text-muted">${formatDate(row.created_at)}</div>
      </div>
      <div class="small mb-1"><strong>Reviewer:</strong> ${escapeHtml(row.reviewer || '-')}</div>
      <div class="small mb-1"><strong>Firma:</strong> ${escapeHtml(row.reviewer_signature || '-')}</div>
      <div class="small mb-2"><strong>Motivo:</strong> ${escapeHtml(row.review_reason || 'Nessuna motivazione registrata.')}</div>
      <div class="small text-muted">
        Diff sezioni: ${Number(row.diff_json?.summary?.changed_sections || 0)}
      </div>
    </div>
  `).join('');
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

function buildReviewRequestPayload(action) {
  const reviewSignature = String(document.getElementById('review-signature').value || '').trim();
  const approvalReason = String(document.getElementById('approval-notes').value || '').trim();
  const rejectReason = String(document.getElementById('reject-notes').value || '').trim();
  const reviewReason = action === 'reject' ? rejectReason : approvalReason;

  if (!reviewSignature) {
    showToast('Inserisci la firma del reviewer prima di proseguire.');
    return null;
  }
  if ((action === 'approve' || action === 'reject') && !reviewReason) {
    showToast('Inserisci il motivo della decisione prima di proseguire.');
    return null;
  }

  return {
    reviewer: 'review-ui',
    tenant_slug: reviewTenantSlug,
    review_signature: reviewSignature,
    review_reason: reviewReason
  };
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
    currentDraftDetail = data;

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
    document.getElementById('meta-reviewer').textContent = data.reviewer || '-';
    document.getElementById('meta-signature').textContent = data.review_signature || '-';
    document.getElementById('meta-last-action').textContent = data.last_review_action || '-';
    document.getElementById('meta-review-reason').textContent = data.review_reason || 'Nessuna motivazione registrata.';
    document.getElementById('spec-editor').value = JSON.stringify(data.spec_json || {}, null, 2);
    document.getElementById('validation-view').textContent = JSON.stringify(data.validation_report_json || {}, null, 2);
    document.getElementById('sql-view').textContent = data.sql_preview || '';
    document.getElementById('review-signature').value = data.review_signature || '';
    document.getElementById('approval-notes').value =
      ['approved', 'published'].includes(String(data.last_review_action || '')) ? (data.review_reason || '') : '';
    document.getElementById('reject-notes').value =
      String(data.last_review_action || '') === 'rejected' ? (data.review_reason || '') : '';
    renderRetrievalExamples(data.retrieval_examples_json || []);
    renderReviewDiff(data.review_diff_json || {});
    renderReviewHistory(data.review_history || []);
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
      body: JSON.stringify({
        spec_json: spec,
        tenant_slug: reviewTenantSlug,
        reviewer: 'review-ui',
        review_signature: String(document.getElementById('review-signature').value || '').trim()
      })
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
  const payload = buildReviewRequestPayload('approve');
  if (!payload) return;
  try {
    await fetchJson(reviewUrl(`/drafts/${currentDraftId}/approve`), {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    showToast('Bozza approvata con audit registrato.');
    await fetchDrafts();
  } catch (error) {
    showToast(error.message);
  }
}

async function rejectDraft() {
  if (!currentDraftId) return;
  const payload = buildReviewRequestPayload('reject');
  if (!payload) return;
  try {
    await fetchJson(reviewUrl(`/drafts/${currentDraftId}/reject`), {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    showToast('Bozza rifiutata con audit registrato.');
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
  const payload = buildReviewRequestPayload('publish');
  if (!payload) return;
  try {
    await fetchJson(reviewUrl(`/drafts/${currentDraftId}/publish`), {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
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
