let currentDraftId = null;
let cachedDrafts = [];
let reviewToast = null;
const reviewTenantSlug = String(window.REVIEW_TENANT_SLUG || '').trim();

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

async function fetchDrafts() {
  const res = await fetch(reviewUrl('/drafts'));
  const data = await res.json();
  cachedDrafts = Array.isArray(data) ? data : [];
  renderDraftList(cachedDrafts);
}

function renderDraftList(data) {
  const filter = (document.getElementById('filter-text').value || '').toLowerCase().trim();
  const list = document.getElementById('draft-list');
  const filtered = data.filter((draft) => {
    const haystack = `${draft.subbranch_code || ''} ${draft.procedure_code || ''} ${draft.status || ''}`.toLowerCase();
    return haystack.includes(filter);
  });

  document.getElementById('draft-count').textContent = filtered.length;
  list.innerHTML = filtered.map((draft) => `
    <button class="review-draft-item ${currentDraftId === draft.id ? 'is-active' : ''}" data-id="${draft.id}">
      <div class="review-draft-top">
        <div class="review-draft-title">${escapeHtml(draft.subbranch_code)}</div>
        ${badge(draft.status, `status-${String(draft.status).toLowerCase()}`)}
      </div>
      <div class="review-draft-meta">
        ${badge(draft.risk_level || 'MEDIUM', `risk-${String(draft.risk_level || '').toLowerCase()}`)}
        ${badge(draft.auto_publish_eligible ? 'Auto sì' : 'Auto no', draft.auto_publish_eligible ? 'auto-yes' : '')}
        <span>${escapeHtml(draft.procedure_code || '-')}</span>
      </div>
    </button>
  `).join('');

  document.querySelectorAll('.review-draft-item').forEach((button) => {
    button.addEventListener('click', () => loadDraft(Number(button.dataset.id)));
  });
}

async function loadDraft(id) {
  currentDraftId = id;
  renderDraftList(cachedDrafts);
  const res = await fetch(reviewUrl(`/drafts/${id}`));
  const data = await res.json();

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
    `Auto publish: ${data.auto_publish_eligible ? 'sì' : 'no'}`;
  document.getElementById('chip-created-at').textContent = `Creato: ${formatDate(data.created_at)}`;
  document.getElementById('chip-reviewed-at').textContent = `Review: ${formatDate(data.reviewed_at)}`;
  document.getElementById('spec-editor').value = JSON.stringify(data.spec_json || {}, null, 2);
  document.getElementById('validation-view').textContent = JSON.stringify(data.validation_report_json || {}, null, 2);
  document.getElementById('sql-view').textContent = data.sql_preview || '';
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

  const res = await fetch(reviewUrl(`/drafts/${currentDraftId}/save`), {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({spec_json: spec, tenant_slug: reviewTenantSlug})
  });
  const data = await res.json();
  if (!res.ok || data.ok === false) {
    showToast(data.errore || 'Errore durante il salvataggio.');
    return;
  }
  document.getElementById('validation-view').textContent = JSON.stringify(data.validation || {}, null, 2);
  showToast('Draft salvato correttamente.');
  await fetchDrafts();
  await loadDraft(currentDraftId);
}

async function approveDraft() {
  if (!currentDraftId) return;
  await fetch(reviewUrl(`/drafts/${currentDraftId}/approve`), {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({reviewer: 'review-ui', tenant_slug: reviewTenantSlug})
  });
  showToast('Draft approvato.');
  await fetchDrafts();
  await loadDraft(currentDraftId);
}

async function rejectDraft() {
  if (!currentDraftId) return;
  await fetch(reviewUrl(`/drafts/${currentDraftId}/reject`), {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({reviewer: 'review-ui', tenant_slug: reviewTenantSlug})
  });
  showToast('Draft rifiutato.');
  await fetchDrafts();
  await loadDraft(currentDraftId);
}

async function previewSql() {
  if (!currentDraftId) return;
  const res = await fetch(reviewUrl(`/drafts/${currentDraftId}/sql`));
  const data = await res.json();
  document.getElementById('sql-view').textContent = data.sql || '';
  showToast('SQL aggiornato.');
}

async function publishDraft() {
  if (!currentDraftId) return;
  const res = await fetch(reviewUrl(`/drafts/${currentDraftId}/publish`), {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({tenant_slug: reviewTenantSlug})
  });
  const data = await res.json();
  if (!res.ok || data.ok === false) {
    showToast(data.errore || 'Errore durante la pubblicazione.');
    return;
  }
  showToast('Draft pubblicato e database aggiornato.');
  await fetchDrafts();
  await loadDraft(currentDraftId);
}

document.getElementById('btn-refresh').addEventListener('click', fetchDrafts);
document.getElementById('btn-save').addEventListener('click', saveDraft);
document.getElementById('btn-approve').addEventListener('click', approveDraft);
document.getElementById('btn-reject').addEventListener('click', rejectDraft);
document.getElementById('btn-open-sql').addEventListener('click', previewSql);
document.getElementById('btn-publish').addEventListener('click', publishDraft);
document.getElementById('filter-text').addEventListener('input', () => renderDraftList(cachedDrafts));

fetchDrafts();
