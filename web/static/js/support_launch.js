(() => {
  const modalId = "supportLaunchModal";
  let modalInstance = null;

  function ensureModal() {
    let modal = document.getElementById(modalId);
    if (!modal) {
      modal = document.createElement("div");
      modal.className = "modal fade";
      modal.id = modalId;
      modal.tabIndex = -1;
      modal.setAttribute("aria-hidden", "true");
      modal.innerHTML = `
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">Assistenza remota pronta</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Chiudi"></button>
            </div>
            <div class="modal-body">
              <div id="supportLaunchFeedback" class="alert alert-success mb-3">
                Sessione creata correttamente. Invia il link al cliente e apri la stanza operatore.
              </div>
              <label class="form-label">Link cliente</label>
              <div class="input-group mb-3">
                <input type="text" class="form-control" id="supportLaunchJoinUrl" readonly>
                <button type="button" class="btn btn-outline-secondary" id="supportLaunchCopyBtn">Copia</button>
              </div>
              <div class="d-flex gap-2 flex-wrap">
                <a href="#" class="btn btn-primary" id="supportLaunchOpenOperator" target="_blank" rel="noopener">Apri stanza operatore</a>
                <a href="#" class="btn btn-outline-secondary" id="supportLaunchOpenConsole">Apri in console</a>
              </div>
            </div>
          </div>
        </div>
      `;
      document.body.appendChild(modal);
    }
    if (!modalInstance && window.bootstrap?.Modal) {
      modalInstance = new window.bootstrap.Modal(modal);
    }
    return modal;
  }

  function setFeedback(message, tone = "success") {
    const feedback = document.getElementById("supportLaunchFeedback");
    if (!feedback) return;
    feedback.className = `alert alert-${tone} mb-3`;
    feedback.textContent = message;
  }

  function showModal(payload) {
    ensureModal();
    const joinInput = document.getElementById("supportLaunchJoinUrl");
    const copyBtn = document.getElementById("supportLaunchCopyBtn");
    const openOperator = document.getElementById("supportLaunchOpenOperator");
    const openConsole = document.getElementById("supportLaunchOpenConsole");

    if (joinInput) joinInput.value = payload.join_url || "";
    if (openOperator) openOperator.href = payload.operator_url || "#";
    if (openConsole) {
      openConsole.href = `/admin/supporto-remoto?sessione=${encodeURIComponent((payload.session || {}).public_id || "")}`;
    }

    if (copyBtn) {
      copyBtn.onclick = async () => {
        try {
          if (joinInput?.value) {
            await navigator.clipboard.writeText(joinInput.value);
            setFeedback("Link cliente copiato negli appunti.");
          }
        } catch (_) {
          setFeedback("Copia negli appunti non disponibile su questo browser.", "warning");
        }
      };
    }

    modalInstance?.show();
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

  async function createSupportSession(button) {
    const originalHtml = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i>Apro assistenza...';

    const payload = {
      customer_name: button.dataset.supportCustomerName || "",
      customer_email: button.dataset.supportCustomerEmail || "",
      studio_slug: button.dataset.supportStudioSlug || "",
      studio_nome: button.dataset.supportStudioName || "",
      client_id: button.dataset.supportClientId || "",
      practice_id: button.dataset.supportPracticeId || "",
      practice_label: button.dataset.supportPracticeLabel || button.dataset.supportContextLabel || "",
      notes: button.dataset.supportContextLabel || "",
    };

    try {
      const result = await fetchJson("/support/api/session", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      ensureModal();
      if (result.operator_url) {
        window.open(result.operator_url, "_blank", "noopener");
      }
      try {
        if (navigator.clipboard && result.join_url) {
          await navigator.clipboard.writeText(result.join_url);
          setFeedback("Sessione creata. Link cliente copiato e stanza operatore aperta in una nuova scheda.");
        } else {
          setFeedback("Sessione creata correttamente. Invia il link al cliente e apri la stanza operatore.");
        }
      } catch (_) {
        setFeedback("Sessione creata correttamente. Copia manualmente il link cliente dalla finestra che si apre.", "warning");
      }
      showModal(result);
    } catch (error) {
      ensureModal();
      setFeedback(`Impossibile aprire l'assistenza remota: ${error.message}`, "danger");
      modalInstance?.show();
    } finally {
      button.disabled = false;
      button.innerHTML = originalHtml;
    }
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-support-launch]");
    if (!button) return;
    event.preventDefault();
    createSupportSession(button);
  });
})();
