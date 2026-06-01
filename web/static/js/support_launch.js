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
              <label class="form-label" id="supportLaunchJoinLabel">Link cliente</label>
              <div class="input-group mb-3">
                <input type="text" class="form-control" id="supportLaunchJoinUrl" readonly>
                <button type="button" class="btn btn-outline-secondary" id="supportLaunchCopyBtn">Copia</button>
              </div>
              <div class="d-flex gap-2 flex-wrap">
                <a href="#" class="btn btn-primary" id="supportLaunchOpenOperator" target="_blank" rel="noopener">Apri stanza operatore</a>
        <a href="#" class="btn btn-outline-secondary" id="supportLaunchOpenConsole">Apri in cabina</a>
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

  function hideSupportModal() {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    if (modalInstance?.hide) {
      modalInstance.hide();
      return;
    }
    modal.classList.remove("show");
    modal.style.display = "none";
    modal.setAttribute("aria-hidden", "true");
    modal.removeAttribute("aria-modal");
    document.body.classList.remove("modal-open");
    const fallbackBackdrop = document.getElementById(`${modalId}Backdrop`);
    fallbackBackdrop?.remove();
  }

  function showSupportModal() {
    const modal = ensureModal();
    modal.querySelectorAll("[data-bs-dismiss='modal']").forEach((element) => {
      element.addEventListener("click", hideSupportModal, { once: true });
    });
    if (modalInstance?.show) {
      modalInstance.show();
      return;
    }
    let backdrop = document.getElementById(`${modalId}Backdrop`);
    if (!backdrop) {
      backdrop = document.createElement("div");
      backdrop.id = `${modalId}Backdrop`;
      backdrop.className = "modal-backdrop fade show";
      backdrop.addEventListener("click", hideSupportModal);
      document.body.appendChild(backdrop);
    }
    modal.classList.add("show");
    modal.style.display = "block";
    modal.removeAttribute("aria-hidden");
    modal.setAttribute("aria-modal", "true");
    modal.setAttribute("role", "dialog");
    document.body.classList.add("modal-open");
  }

  function showModal(payload) {
    ensureModal();
    const customerEntry = Boolean(payload.customer_entry);
    const joinInput = document.getElementById("supportLaunchJoinUrl");
    const copyBtn = document.getElementById("supportLaunchCopyBtn");
    const openOperator = document.getElementById("supportLaunchOpenOperator");
    const openConsole = document.getElementById("supportLaunchOpenConsole");
    const title = document.querySelector(`#${modalId} .modal-title`);
    const joinLabel = document.getElementById("supportLaunchJoinLabel");

    if (title) {
      title.textContent = customerEntry ? "Richiesta inviata al supporto" : "Assistenza remota pronta";
    }
    if (joinLabel) {
      joinLabel.textContent = customerEntry ? "Link stanza cliente" : "Link cliente";
    }

    if (joinInput) joinInput.value = payload.join_url || "";
    if (openOperator) {
      openOperator.href = customerEntry ? payload.join_url || "#" : payload.operator_url || "#";
      openOperator.textContent = customerEntry ? "Apri stanza cliente" : "Apri stanza operatore";
    }
    if (openConsole) {
      openConsole.classList.toggle("d-none", customerEntry);
      openConsole.href = customerEntry
        ? "#"
        : `/admin/supporto-remoto?sessione=${encodeURIComponent((payload.session || {}).public_id || "")}`;
    }

    if (copyBtn) {
      copyBtn.classList.toggle("d-none", customerEntry);
      copyBtn.onclick = async () => {
        try {
          if (joinInput?.value) {
            await navigator.clipboard.writeText(joinInput.value);
            setFeedback(customerEntry ? "Link stanza cliente copiato negli appunti." : "Link cliente copiato negli appunti.");
          }
        } catch (_) {
          setFeedback("Copia negli appunti non disponibile su questo browser.", "warning");
        }
      };
    }

    showSupportModal();
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
      context_label: button.dataset.supportContextLabel || "",
      notes: button.dataset.supportContextLabel || "",
    };
    const endpoint = button.dataset.supportEndpoint || "/support/api/session";

    try {
      const result = await fetchJson(endpoint, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      ensureModal();
      if (result.customer_entry && result.join_url) {
        window.open(result.join_url, "_blank", "noopener");
        setFeedback("Richiesta inviata al SUPERADMIN. Resta nella stanza cliente, conferma i consensi richiesti e attendi che l'operatore prenda in carico la sessione.");
      } else if (result.operator_url) {
        window.open(result.operator_url, "_blank", "noopener");
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
      }
      showModal(result);
    } catch (error) {
      ensureModal();
      setFeedback(`Impossibile aprire l'assistenza remota: ${error.message}`, "danger");
      showSupportModal();
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
