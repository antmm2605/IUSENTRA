(() => {
  const form = document.getElementById("supportCreateForm");
  const resultBox = document.getElementById("supportCreateResult");
  const joinUrlInput = document.getElementById("supportJoinUrl");
  const copyJoinUrlBtn = document.getElementById("supportCopyJoinUrl");
  const openOperatorLink = document.getElementById("supportOpenOperator");
  const openSessionDetailLink = document.getElementById("supportOpenSessionDetail");
  const saveNotesBtn = document.getElementById("supportSaveNotes");
  const notesField = document.getElementById("supportNotes");
  const feedbackBox = document.getElementById("supportConsoleFeedback");

  function showFeedback(message, tone = "success") {
    if (!feedbackBox) return;
    feedbackBox.className = `alert alert-${tone} mb-3`;
    feedbackBox.textContent = message;
    feedbackBox.classList.remove("d-none");
  }

  function clearFeedback() {
    if (!feedbackBox) return;
    feedbackBox.className = "d-none mb-3";
    feedbackBox.textContent = "";
  }

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    const text = await response.text();
    let payload = {};
    try {
      payload = text ? JSON.parse(text) : {};
    } catch (_) {
      payload = {};
    }
    if (!response.ok) {
      throw new Error(payload.description || payload.error || text || `HTTP ${response.status}`);
    }
    return payload;
  }

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submitBtn = form.querySelector("button[type='submit']");
    const payload = Object.fromEntries(new FormData(form).entries());
    submitBtn.disabled = true;
    clearFeedback();
    try {
      const response = await fetchJson(form.action || "/support/api/session", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (joinUrlInput) joinUrlInput.value = response.join_url || "";
      if (openOperatorLink) openOperatorLink.href = response.operator_url || "#";
      if (openSessionDetailLink) openSessionDetailLink.href = `/admin/supporto-remoto?sessione=${encodeURIComponent((response.session || {}).public_id || "")}`;
      resultBox?.classList.remove("d-none");
      if (response.operator_url) {
        window.open(response.operator_url, "_blank", "noopener");
      }
      if (navigator.clipboard && response.join_url) {
        await navigator.clipboard.writeText(response.join_url);
      }
      showFeedback("Sessione creata. Link cliente pronto e stanza operatore aperta in una nuova scheda.");
    } catch (error) {
      showFeedback(`Impossibile creare la sessione: ${error.message}`, "danger");
    } finally {
      submitBtn.disabled = false;
    }
  });

  copyJoinUrlBtn?.addEventListener("click", async () => {
    if (!joinUrlInput?.value) return;
    try {
      await navigator.clipboard.writeText(joinUrlInput.value);
      showFeedback("Link cliente copiato negli appunti.");
    } catch (_) {
      showFeedback("Copia negli appunti non disponibile su questo browser.", "warning");
    }
  });

  saveNotesBtn?.addEventListener("click", async () => {
    const publicId = saveNotesBtn.dataset.publicId || "";
    if (!publicId) return;
    saveNotesBtn.disabled = true;
    try {
      await fetchJson(`/support/api/${encodeURIComponent(publicId)}/note?role=operator`, {
        method: "POST",
        body: JSON.stringify({ notes: notesField?.value || "" }),
      });
      showFeedback("Note sessione salvate correttamente.");
      window.location.reload();
    } catch (error) {
      showFeedback(`Salvataggio note non riuscito: ${error.message}`, "danger");
    } finally {
      saveNotesBtn.disabled = false;
    }
  });
})();
