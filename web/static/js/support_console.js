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
  const pushPanel = document.querySelector("[data-support-push-panel]");
  const pushBadge = document.getElementById("supportPushBadge");
  const pushMessage = document.getElementById("supportPushMessage");
  const pushDiagnostics = document.getElementById("supportPushDiagnostics");
  const pushActivateBtn = document.getElementById("supportPushActivate");
  const pushTestBtn = document.getElementById("supportPushTest");
  const pushDeactivateBtn = document.getElementById("supportPushDeactivate");
  let supportPushState = null;

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

  function browserSupportsPush() {
    return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  }

  function urlBase64ToArrayBuffer(value) {
    const padding = "=".repeat((4 - (value.length % 4)) % 4);
    const base64 = `${value}${padding}`.replace(/-/g, "+").replace(/_/g, "/");
    const raw = window.atob(base64);
    const buffer = new ArrayBuffer(raw.length);
    const output = new Uint8Array(buffer);
    for (let index = 0; index < raw.length; index += 1) {
      output[index] = raw.charCodeAt(index);
    }
    return buffer;
  }

  async function currentPushSubscription() {
    if (!browserSupportsPush()) return null;
    const registration = await navigator.serviceWorker.getRegistration("/");
    return registration ? registration.pushManager.getSubscription() : null;
  }

  async function ensurePushRegistration() {
    return navigator.serviceWorker.register("/sw.js?iusentra_sw=20260716_remote_hearing_v4", {
      scope: "/",
      updateViaCache: "none",
    }).then(function (registration) {
      return registration.update().catch(function () {}).then(function () {
        return registration;
      });
    });
  }

  function subscriptionPayload(subscription) {
    const payload = subscription.toJSON();
    return {
      endpoint: payload.endpoint,
      keys: payload.keys,
      deviceLabel: navigator.platform || "Dispositivo SUPERADMIN",
    };
  }

  function setPushBadge(text, tone) {
    if (!pushBadge) return;
    pushBadge.className = `badge bg-${tone}`;
    pushBadge.textContent = text;
  }

  function updatePushUi(status, subscription) {
    if (!pushPanel) return;
    const supported = browserSupportsPush();
    const configured = Boolean(status?.configured);
    const activeHere = Boolean(subscription);
    const activeCount = Number(status?.activeSubscriptions || 0);
    const permission = supported ? Notification.permission : "unsupported";

    if (!supported) {
      setPushBadge("Non supportato", "warning");
    } else if (!configured) {
      setPushBadge("Server da configurare", "warning");
    } else if (permission === "denied") {
      setPushBadge("Bloccato dal dispositivo", "warning");
    } else if (activeHere) {
      setPushBadge("Attivo su questo dispositivo", "success");
    } else if (activeCount > 0) {
      setPushBadge(`${activeCount} dispositivo attivo`, "info");
    } else {
      setPushBadge("Pronto", "primary");
    }

    if (pushMessage) {
      if (!supported) {
        pushMessage.textContent = "Questo browser o cellulare non supporta le notifiche Web Push.";
      } else if (permission === "denied") {
        pushMessage.textContent = "Le notifiche sono bloccate nelle impostazioni del browser o del sistema.";
      } else {
        pushMessage.textContent = status?.message || "Stato notifiche dispositivo letto.";
      }
    }
    if (pushDiagnostics) {
      const missing = Array.isArray(status?.diagnostics?.missing) ? status.diagnostics.missing : [];
      const devices = activeCount === 1 ? "1 dispositivo SUPERADMIN attivo." : `${activeCount} dispositivi SUPERADMIN attivi.`;
      pushDiagnostics.textContent = missing.length
        ? `Server incompleto: ${missing.join(", ")}.`
        : devices;
    }
    if (pushActivateBtn) {
      pushActivateBtn.disabled = !supported || !configured || activeHere || permission === "denied";
    }
    if (pushTestBtn) {
      pushTestBtn.disabled = !configured || activeCount < 1;
    }
    if (pushDeactivateBtn) {
      pushDeactivateBtn.disabled = !activeHere;
    }
  }

  async function refreshPushStatus() {
    if (!pushPanel) return;
    try {
      supportPushState = await fetchJson(pushPanel.dataset.statusUrl || "/admin/supporto-remoto/notifiche-dispositivo");
      updatePushUi(supportPushState, await currentPushSubscription());
    } catch (error) {
      setPushBadge("Errore", "danger");
      if (pushMessage) pushMessage.textContent = `Stato notifiche non disponibile: ${error.message}`;
      if (pushActivateBtn) pushActivateBtn.disabled = true;
      if (pushTestBtn) pushTestBtn.disabled = true;
      if (pushDeactivateBtn) pushDeactivateBtn.disabled = true;
    }
  }

  async function activatePushDevice() {
    if (!pushPanel || !browserSupportsPush()) return;
    pushActivateBtn.disabled = true;
    try {
      if (!supportPushState || !supportPushState.publicKey) {
        supportPushState = await fetchJson(pushPanel.dataset.statusUrl || "/admin/supporto-remoto/notifiche-dispositivo");
      }
      if (!supportPushState.publicKey) {
        throw new Error("Chiave pubblica Web Push non disponibile.");
      }
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        throw new Error("Autorizzazione notifiche non concessa.");
      }
      const registration = await ensurePushRegistration();
      let subscription = await registration.pushManager.getSubscription();
      if (!subscription) {
        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToArrayBuffer(supportPushState.publicKey),
        });
      }
      const response = await fetchJson(pushPanel.dataset.subscribeUrl || "/admin/supporto-remoto/notifiche-dispositivo/subscribe", {
        method: "POST",
        body: JSON.stringify(subscriptionPayload(subscription)),
      });
      supportPushState = response.status || supportPushState;
      if (pushMessage) pushMessage.textContent = response.message || "Notifiche assistenza attive.";
      await refreshPushStatus();
    } catch (error) {
      if (pushMessage) pushMessage.textContent = `Attivazione non completata: ${error.message}`;
      await refreshPushStatus();
    }
  }

  async function deactivatePushDevice() {
    if (!pushPanel || !browserSupportsPush()) return;
    pushDeactivateBtn.disabled = true;
    try {
      const subscription = await currentPushSubscription();
      const response = await fetchJson(pushPanel.dataset.subscribeUrl || "/admin/supporto-remoto/notifiche-dispositivo/subscribe", {
        method: "DELETE",
        body: JSON.stringify({ endpoint: subscription?.endpoint || "" }),
      });
      if (subscription) await subscription.unsubscribe();
      supportPushState = response.status || supportPushState;
      if (pushMessage) pushMessage.textContent = response.message || "Notifiche assistenza disattivate.";
      await refreshPushStatus();
    } catch (error) {
      if (pushMessage) pushMessage.textContent = `Disattivazione non completata: ${error.message}`;
      await refreshPushStatus();
    }
  }

  async function sendPushTest() {
    if (!pushPanel) return;
    pushTestBtn.disabled = true;
    try {
      const response = await fetchJson(pushPanel.dataset.testUrl || "/admin/supporto-remoto/notifiche-dispositivo/test", {
        method: "POST",
        body: JSON.stringify({}),
      });
      supportPushState = response.status || supportPushState;
      if (pushMessage) pushMessage.textContent = response.message || "Notifica di test inviata.";
      await refreshPushStatus();
    } catch (error) {
      if (pushMessage) pushMessage.textContent = `Test non completato: ${error.message}`;
      await refreshPushStatus();
    }
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
      let clipboardCopied = false;
      if (navigator.clipboard && response.join_url) {
        try {
          await navigator.clipboard.writeText(response.join_url);
          clipboardCopied = true;
        } catch (_) {
          clipboardCopied = false;
        }
      }
      if (response.operator_url) {
        window.open(response.operator_url, "_blank", "noopener");
      }
      showFeedback(
        clipboardCopied
          ? "Sessione creata. Link cliente copiato e stanza operatore aperta in una nuova scheda."
          : "Sessione creata. Link cliente pronto nel campo dedicato e stanza operatore aperta in una nuova scheda.",
      );
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

  pushActivateBtn?.addEventListener("click", () => {
    activatePushDevice();
  });

  pushDeactivateBtn?.addEventListener("click", () => {
    deactivatePushDevice();
  });

  pushTestBtn?.addEventListener("click", () => {
    sendPushTest();
  });

  if (pushPanel) {
    refreshPushStatus();
  }
})();
