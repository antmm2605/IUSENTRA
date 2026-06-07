(() => {
  if (window.__iusentraSupportCustomerRoomLoaded) return;
  window.__iusentraSupportCustomerRoomLoaded = true;

  const $ = (id) => document.getElementById(id);

  function readBootstrap() {
    if (window.SUPPORT_BOOTSTRAP) return window.SUPPORT_BOOTSTRAP;
    const element = $("support-customer-bootstrap");
    if (!element) return {};
    try {
      return JSON.parse(element.textContent || "{}");
    } catch (_) {
      return {};
    }
  }

  const boot = readBootstrap();

  const statusBadge = $("statusBadge");
  const peerBadge = $("peerBadge");
  const remoteAudio = $("remoteAudio");
  const takeChargeNotice = $("takeChargeNotice");
  const consentScreen = $("consentScreen");
  const consentAudio = $("consentAudio");
  const consentChat = $("consentChat");
  const startBtn = $("startBtn");
  const stopBtn = $("stopBtn");
  const customerMuteMicBtn = $("customerMuteMicBtn");
  const advancedBanner = $("advancedBanner");
  const approveAdvancedBtn = $("approveAdvancedBtn");
  const rejectAdvancedBtn = $("rejectAdvancedBtn");
  const customerFullscreenBtn = $("customerFullscreenBtn");
  const compactChatBtn = $("compactChatBtn");
  const customerShell = $("supportCustomerShell");
  const customerChatPanel = $("customerChatPanel");
  const chatLog = $("chatLog");
  const chatInput = $("chatInput");
  const sendBtn = $("sendBtn");

  let ws = null;
  let wsOpenPromise = null;
  let pc = null;
  let dataChannel = null;
  let localStream = null;
  let micStream = null;
  let stateTimer = null;
  let pingTimer = null;
  let wsReconnectTimer = null;
  let wsReconnectAttempts = 0;
  let agentScreenTimer = null;
  let agentScreenInFlight = false;
  let agentScreenArmed = false;
  let agentControlArmed = false;
  let customerFullscreen = false;
  let chatCompact = false;
  let customerMicMuted = false;
  let operatorReadyForStart = false;
  let supportStarted = false;
  let closingWsIntentionally = false;
  let stateSyncInFlight = false;
  let sessionClosed = Boolean(boot.closed || boot.status === "closed");
  const pendingIceCandidates = [];
  const statePollDelayMs = 12000;
  const wsPingIntervalMs = 15000;
  const wsReconnectBaseDelayMs = 800;
  const wsReconnectMaxDelayMs = 6000;

  function setStatus(text) {
    if (statusBadge) statusBadge.textContent = text;
  }

  function setPeer(connected) {
    if (!peerBadge) return;
    peerBadge.textContent = connected ? "Operatore collegato" : "Operatore non collegato";
    peerBadge.className = `badge ${connected ? "bg-success" : "bg-secondary"}`;
  }

  function customerAudioTracks() {
    return [
      ...(micStream ? micStream.getAudioTracks() : []),
      ...(localStream ? localStream.getAudioTracks() : []),
    ].filter((track, index, tracks) => track && track.readyState !== "ended" && tracks.indexOf(track) === index);
  }

  function syncCustomerMicUi() {
    if (!customerMuteMicBtn) return;
    const tracks = customerAudioTracks();
    const canToggle = !sessionClosed && (tracks.length > 0 || Boolean(consentAudio?.checked));
    customerMuteMicBtn.disabled = !canToggle;
    customerMuteMicBtn.setAttribute("aria-pressed", customerMicMuted ? "true" : "false");
    customerMuteMicBtn.classList.toggle("btn-secondary", customerMicMuted);
    customerMuteMicBtn.classList.toggle("btn-outline-secondary", !customerMicMuted);
    customerMuteMicBtn.innerHTML = customerMicMuted
      ? '<i class="bi bi-mic me-1"></i>Riattiva microfono'
      : '<i class="bi bi-mic-mute me-1"></i>Muta microfono';
  }

  function syncStartButtonUi() {
    if (!startBtn) return;
    const canStart = !sessionClosed && operatorReadyForStart && !supportStarted;
    startBtn.disabled = !canStart;
    startBtn.classList.toggle("btn-primary", canStart);
    startBtn.classList.toggle("btn-outline-secondary", !canStart && !supportStarted);
    startBtn.classList.toggle("btn-success", supportStarted);
    startBtn.setAttribute("aria-disabled", canStart ? "false" : "true");
    if (supportStarted) {
      startBtn.innerHTML = '<i class="bi bi-check-circle me-1"></i>Assistenza attiva';
      startBtn.title = "Assistenza avviata: puoi chiuderla con Termina sessione.";
      return;
    }
    if (canStart) {
      startBtn.innerHTML = '<i class="bi bi-play-circle me-1"></i>Avvia assistenza';
      startBtn.title = "Avvia la condivisione solo dopo la presa in carico del SUPERADMIN.";
      return;
    }
    startBtn.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>Attendi operatore';
    startBtn.title = "Il SUPERADMIN deve prima prendere in carico la richiesta dalla console.";
  }

  function toggleCustomerMicrophone() {
    if (sessionClosed) return;
    const tracks = customerAudioTracks();
    if (!tracks.length && !consentAudio?.checked) {
      syncCustomerMicUi();
      return;
    }
    customerMicMuted = !customerMicMuted;
    tracks.forEach((track) => {
      track.enabled = !customerMicMuted;
    });
    setStatus(
      tracks.length
        ? (customerMicMuted ? "Microfono cliente disattivato" : "Microfono cliente attivo")
        : (customerMicMuted ? "Microfono cliente disattivato all'avvio" : "Microfono cliente attivo all'avvio")
    );
    syncCustomerMicUi();
  }

  function setTakeChargeNotice(session) {
    if (!takeChargeNotice || sessionClosed) return;
    const status = String(session?.status || "").toLowerCase();
    const operatorPresent = Boolean(session?.presence && session.presence.operator);
    const taken =
      operatorPresent ||
      status === "waiting_client" ||
      status === "waiting_peer" ||
      status === "active";
    operatorReadyForStart = Boolean(taken);
    takeChargeNotice.classList.toggle("d-none", !taken);
    syncStartButtonUi();
  }

  function syncCustomerLayout() {
    document.body.classList.toggle("support-customer-page--fullscreen", customerFullscreen);
    customerShell?.classList.toggle("support-customer-shell--fullscreen", customerFullscreen);
    customerChatPanel?.classList.toggle("support-customer-chat--compact", chatCompact);
    if (customerChatPanel) {
      customerChatPanel.querySelectorAll(".card-header, .form-label, #chatLog").forEach((element) => {
        element.style.display = chatCompact ? "none" : "";
      });
      const body = customerChatPanel.querySelector(".card-body");
      if (body) {
        body.style.padding = chatCompact ? ".65rem" : "";
      }
    }
    if (customerFullscreenBtn) {
      customerFullscreenBtn.classList.toggle("btn-primary", customerFullscreen);
      customerFullscreenBtn.classList.toggle("btn-outline-primary", !customerFullscreen);
      customerFullscreenBtn.innerHTML = customerFullscreen
        ? '<i class="bi bi-fullscreen-exit me-1"></i>Esci schermo intero'
        : '<i class="bi bi-fullscreen me-1"></i>Schermo intero';
    }
    if (compactChatBtn) {
      compactChatBtn.classList.toggle("btn-primary", chatCompact);
      compactChatBtn.classList.toggle("btn-outline-primary", !chatCompact);
      compactChatBtn.innerHTML = chatCompact
        ? '<i class="bi bi-chat-square-text me-1"></i>Chat estesa'
        : '<i class="bi bi-chat-square me-1"></i>Chat compatta';
    }
  }

  async function toggleCustomerFullscreen() {
    if (sessionClosed) return;
    if (customerFullscreen) {
      customerFullscreen = false;
      if (document.fullscreenElement) {
        try { await document.exitFullscreen(); } catch (_) {}
      }
      syncCustomerLayout();
      return;
    }
    customerFullscreen = true;
    chatCompact = true;
    try {
      if (customerShell?.requestFullscreen && document.fullscreenEnabled !== false) {
        await customerShell.requestFullscreen();
      }
    } catch (_) {
      customerFullscreen = true;
    }
    syncCustomerLayout();
  }

  function toggleCompactChat() {
    chatCompact = !chatCompact;
    syncCustomerLayout();
  }

  function apiUrl(path) {
    return `${boot.apiPrefix}${path}?role=${encodeURIComponent(boot.role)}&token=${encodeURIComponent(boot.authToken)}`;
  }

  function stateUrl() {
    return `${apiUrl("/state")}&events=0`;
  }

  function wsUrl() {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${window.location.host}${boot.wsBase}/${boot.publicId}?role=${encodeURIComponent(boot.role)}&token=${encodeURIComponent(boot.authToken)}`;
  }

  function agentUrl(path) {
    const base = String(boot.localControlBase || "http://127.0.0.1:27273").replace(/\/+$/, "");
    return `${base}${path}`;
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

  async function fetchAgent(path, body = null) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 4500);
    try {
      const fetchOptions = {
        method: body ? "POST" : "GET",
        headers: body ? { "Content-Type": "application/json" } : { Accept: "application/json" },
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
        targetAddressSpace: "loopback",
      };
      const response = await fetch(agentUrl(path), fetchOptions);
      const text = await response.text();
      let payload = {};
      try {
        payload = text ? JSON.parse(text) : {};
      } catch (_) {
        payload = {};
      }
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || payload.description || text || `HTTP ${response.status}`);
      }
      return payload;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  function appendChat(text, who = "other") {
    if (!chatLog) return;
    const item = document.createElement("div");
    item.className = `support-chat-log__message support-chat-log__message--${who}`;
    item.textContent = text;
    chatLog.appendChild(item);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  function markScreenSharedForOperator() {
    setStatus("Schermo condiviso tramite agente locale");
  }

  async function captureAndRelayAgentScreen() {
    if (sessionClosed || !agentScreenArmed) return;
    try {
      const frame = await fetchAgent("/screenshot", {
        session_id: boot.publicId,
        token: boot.authToken,
        max_width: 1600,
        quality: 58,
      });
      markScreenSharedForOperator();
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: "screen_frame",
          image: frame.image,
          width: frame.width,
          height: frame.height,
          preview_width: frame.preview_width,
          preview_height: frame.preview_height,
          captured_at: frame.captured_at,
        }));
      }
    } catch (error) {
      console.error(error);
      setStatus(`Errore condivisione schermo: ${error.message}`);
    }
  }

  async function startAgentScreenShare(originalError) {
    await ensureLocalScreenShareAgent();
    await captureAndRelayAgentScreen();
    if (!agentScreenTimer) {
      agentScreenTimer = window.setInterval(captureAndRelayAgentScreen, 900);
    }
    setStatus("Schermo condiviso tramite agente locale");
    if (originalError?.name === "NotAllowedError") {
      appendChat("Il browser ha bloccato la condivisione schermo: sto usando l'agente locale autorizzato.", "me");
    }
  }

  function markSessionClosed() {
    sessionClosed = true;
    cleanup(false);
    setStatus("Sessione chiusa");
    setPeer(false);
    startBtn.disabled = true;
    stopBtn.disabled = true;
    sendBtn.disabled = true;
    chatInput.disabled = true;
    consentScreen.disabled = true;
    consentAudio.disabled = true;
    consentChat.disabled = true;
    customerMuteMicBtn.disabled = true;
    approveAdvancedBtn.disabled = true;
    rejectAdvancedBtn.disabled = true;
    takeChargeNotice?.classList.add("d-none");
    advancedBanner?.classList.add("d-none");
  }

  async function syncState() {
    if (stateSyncInFlight || sessionClosed) return;
    stateSyncInFlight = true;
    try {
      const payload = await fetchJson(stateUrl());
      const session = payload.session || {};
      setStatus(session.status_label || "Sessione aggiornata");
      setPeer(Boolean(session.presence && session.presence.operator));
      setTakeChargeNotice(session);
      advancedBanner?.classList.toggle("d-none", !(session.advanced_control_requested && !session.advanced_control_approved));
      if (session.status === "closed") {
        markSessionClosed();
      }
    } catch (error) {
      console.error(error);
    } finally {
      stateSyncInFlight = false;
    }
  }

  async function getRtcConfiguration() {
    const payload = await fetchJson(apiUrl("/webrtc-config"));
    return payload.rtcConfiguration;
  }

  function setupDataChannel(channel) {
    dataChannel = channel;
    dataChannel.onmessage = (event) => appendChat(`Operatore: ${event.data}`, "other");
  }

  async function ensurePeerConnection() {
    if (pc) return pc;
    pc = new RTCPeerConnection(await getRtcConfiguration());
    if (localStream) {
      localStream.getTracks().forEach((track) => pc.addTrack(track, localStream));
    }
    pc.onicecandidate = (event) => {
      if (event.candidate && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ice", candidate: event.candidate }));
      }
    };
    pc.ontrack = (event) => {
      const [stream] = event.streams;
      if (stream) {
        remoteAudio.srcObject = stream;
      }
    };
    pc.ondatachannel = (event) => setupDataChannel(event.channel);
    pc.onconnectionstatechange = () => {
      if (pc) setStatus(`Connessione ${pc.connectionState}`);
    };
    return pc;
  }

  async function flushPendingIceCandidates(peer) {
    if (!peer?.remoteDescription || !pendingIceCandidates.length) return;
    const candidates = pendingIceCandidates.splice(0, pendingIceCandidates.length);
    for (const candidate of candidates) {
      try {
        await peer.addIceCandidate(candidate);
      } catch (error) {
        console.warn("Candidato ICE scartato dopo descrizione remota.", error);
      }
    }
  }

  async function addRemoteIceCandidate(candidate) {
    const peer = await ensurePeerConnection();
    const iceCandidate = new RTCIceCandidate(candidate);
    if (!peer.remoteDescription) {
      pendingIceCandidates.push(iceCandidate);
      return;
    }
    try {
      await peer.addIceCandidate(iceCandidate);
    } catch (error) {
      console.warn("Candidato ICE remoto non applicato.", error);
    }
  }

  async function connectWs() {
    if (ws && ws.readyState === WebSocket.OPEN) {
      return;
    }
    if (ws && ws.readyState === WebSocket.CONNECTING && wsOpenPromise) {
      return wsOpenPromise;
    }
    ws = new WebSocket(wsUrl());
    closingWsIntentionally = false;
    wsOpenPromise = new Promise((resolve, reject) => {
      let settled = false;
      const settleOk = () => {
        if (settled) return;
        settled = true;
        resolve();
      };
      const settleKo = (message) => {
        if (settled) return;
        settled = true;
        reject(new Error(message));
      };

    ws.onopen = () => {
      setStatus("Canale realtime attivo");
      pingTimer = window.setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping" }));
        }
      }, 20000);
        settleOk();
    };
      ws.onerror = () => {
        settleKo("Canale realtime non disponibile.");
      };
    ws.onmessage = async (event) => {
      const message = JSON.parse(event.data || "{}");
      if (message.type === "peer_state") {
        setPeer(Boolean(message.connected));
        return;
      }
      if (message.type === "offer") {
        const peer = await ensurePeerConnection();
        await peer.setRemoteDescription(new RTCSessionDescription(message.sdp));
        await flushPendingIceCandidates(peer);
        const answer = await peer.createAnswer();
        await peer.setLocalDescription(answer);
        ws.send(JSON.stringify({ type: "answer", sdp: peer.localDescription }));
        return;
      }
      if (message.type === "answer") {
        const peer = await ensurePeerConnection();
        await peer.setRemoteDescription(new RTCSessionDescription(message.sdp));
        await flushPendingIceCandidates(peer);
        return;
      }
      if (message.type === "ice" && message.candidate) {
        await addRemoteIceCandidate(message.candidate);
        return;
      }
      if (message.type === "chat") {
        appendChat(`Operatore: ${message.text}`, "other");
        return;
      }
      if (message.type === "remote_control") {
        await executeRemoteCommand(message);
      }
    };
    ws.onclose = () => {
      if (pingTimer) window.clearInterval(pingTimer);
      pingTimer = null;
        wsOpenPromise = null;
        if (!closingWsIntentionally && !sessionClosed) {
          setStatus("Canale realtime chiuso");
          setPeer(false);
        }
        closingWsIntentionally = false;
        settleKo("Canale realtime chiuso prima della connessione.");
    };
    });
    return wsOpenPromise;
  }

  async function acquireMedia() {
    if (!consentScreen?.checked) {
      throw new Error("Per continuare devi autorizzare la condivisione schermo.");
    }

    const acquireMicrophoneTracks = async () => {
      if (!consentAudio?.checked) {
        customerMicMuted = false;
        syncCustomerMicUi();
        return [];
      }
      try {
        micStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        micStream.getAudioTracks().forEach((track) => {
          track.enabled = !customerMicMuted;
        });
        syncCustomerMicUi();
        return micStream.getAudioTracks();
      } catch (error) {
        if (micStream) {
          micStream.getTracks().forEach((track) => track.stop());
          micStream = null;
        }
        customerMicMuted = true;
        syncCustomerMicUi();
        console.warn("Microfono non autorizzato o non disponibile sul PC: assistenza avviata senza audio.", error);
        appendChat("Microfono non disponibile: assistenza avviata senza audio.", "me");
        setStatus("Microfono non disponibile: assistenza avviata senza audio");
        return [];
      }
    };

    const audioTracks = await acquireMicrophoneTracks();
    try {
      await startAgentScreenShare();
      localStream = audioTracks.length ? new MediaStream(audioTracks) : null;
      customerAudioTracks().forEach((track) => {
        track.enabled = !customerMicMuted;
      });
      syncCustomerMicUi();
      return;
    } catch (agentError) {
      console.error("Agente locale non raggiungibile per assistenza remota completa.", agentError);
      throw new Error(
        "Agente IUSENTRA Assistenza non raggiungibile: avvialo sul PC e consenti al browser l'accesso alla rete locale."
      );
    }
  }

  async function startSession() {
    if (sessionClosed) {
      markSessionClosed();
      return;
    }
    if (!operatorReadyForStart) {
      setStatus("Attendi che il SUPERADMIN prenda in carico la richiesta");
      syncStartButtonUi();
      return;
    }
    try {
      startBtn.disabled = true;
      startBtn.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i>Avvio assistenza...';
      await fetchJson(apiUrl("/consent"), {
        method: "POST",
        body: JSON.stringify({
          consent_screen: Boolean(consentScreen?.checked),
          consent_audio: Boolean(consentAudio?.checked),
          consent_chat: Boolean(consentChat?.checked),
        }),
      });
      await acquireMedia();
      await connectWs();
      if (localStream) {
        await ensurePeerConnection();
      }
      await fetchJson(apiUrl("/start"), { method: "POST", body: JSON.stringify({}) });
      supportStarted = true;
      stopBtn.disabled = false;
      setStatus("Sessione avviata");
      syncStartButtonUi();
      if (!stateTimer) {
        stateTimer = window.setInterval(syncState, statePollDelayMs);
      }
      await syncState();
    } catch (error) {
      console.error(error);
      cleanup(false);
      setStatus(`Errore: ${error.message}`);
      supportStarted = false;
      syncStartButtonUi();
    }
  }

  async function stopSession() {
    try {
      await fetchJson(apiUrl("/close"), { method: "POST", body: JSON.stringify({}) });
    } catch (error) {
      console.error(error);
    } finally {
      cleanup(false);
      stopBtn.disabled = true;
      supportStarted = false;
      operatorReadyForStart = false;
      syncStartButtonUi();
      setStatus("Sessione chiusa");
    }
  }

  function cleanup(enableRestart) {
    disarmLocalControlAgent();
    if (stateTimer) window.clearInterval(stateTimer);
    if (pingTimer) window.clearInterval(pingTimer);
    if (agentScreenTimer) window.clearInterval(agentScreenTimer);
    stateTimer = null;
    pingTimer = null;
    agentScreenTimer = null;
    if (dataChannel) {
      try { dataChannel.close(); } catch (_) {}
      dataChannel = null;
    }
    if (pc) {
      try { pc.close(); } catch (_) {}
      pc = null;
    }
    if (ws) {
      closingWsIntentionally = true;
      try { ws.close(); } catch (_) {}
      ws = null;
    }
    wsOpenPromise = null;
    if (localStream) {
      localStream.getTracks().forEach((track) => track.stop());
      localStream = null;
    }
    if (micStream) {
      micStream.getTracks().forEach((track) => track.stop());
      micStream = null;
    }
    customerMicMuted = false;
    supportStarted = false;
    syncCustomerMicUi();
    syncStartButtonUi();
    if (enableRestart) {
      syncStartButtonUi();
    }
  }

  async function approveAdvanced() {
    if (sessionClosed) return;
    try {
      await ensureLocalControlAgent();
      await connectWs();
      await fetchJson(apiUrl("/escalation"), { method: "POST", body: JSON.stringify({ action: "approve" }) });
      advancedBanner?.classList.add("d-none");
      appendChat("Hai approvato il controllo remoto del PC.", "me");
      if (!stateTimer) {
        stateTimer = window.setInterval(syncState, statePollDelayMs);
      }
      await syncState();
    } catch (error) {
      setStatus(`Errore: ${error.message}`);
    }
  }

  async function rejectAdvanced() {
    if (sessionClosed) return;
    try {
      await fetchJson(apiUrl("/escalation"), { method: "POST", body: JSON.stringify({ action: "reject" }) });
      await disarmLocalControlAgent();
      advancedBanner?.classList.add("d-none");
      appendChat("Hai rifiutato il controllo remoto del PC.", "me");
    } catch (error) {
      setStatus(`Errore: ${error.message}`);
    }
  }

  async function ensureLocalControlAgent() {
    setStatus("Verifico agente IUSENTRA Assistenza sul PC");
    const status = await fetchAgent("/status");
    if (!status.ok) {
      throw new Error("Agente IUSENTRA Assistenza non disponibile sul PC.");
    }
    await fetchAgent("/arm", {
      session_id: boot.publicId,
      token: boot.authToken,
      ttl_seconds: 3600,
      control: true,
    });
    agentControlArmed = true;
    setStatus("Controllo PC autorizzato su questo dispositivo");
  }

  async function ensureLocalScreenShareAgent() {
    setStatus("Verifico agente IUSENTRA Assistenza sul PC");
    const status = await fetchAgent("/status");
    if (!status.ok) {
      throw new Error("Agente IUSENTRA Assistenza non disponibile sul PC.");
    }
    await fetchAgent("/arm", {
      session_id: boot.publicId,
      token: boot.authToken,
      ttl_seconds: 3600,
      control: false,
    });
    agentScreenArmed = true;
  }

  async function disarmLocalControlAgent() {
    if (!agentScreenArmed && !agentControlArmed) return;
    agentScreenArmed = false;
    agentControlArmed = false;
    try {
      await fetchAgent("/disarm", {
        session_id: boot.publicId,
        token: boot.authToken,
      });
    } catch (error) {
      console.error(error);
    }
  }

  async function executeRemoteCommand(message) {
    const commandId = message.id || `${Date.now()}`;
    try {
      if (!agentControlArmed) {
        await ensureLocalControlAgent();
      }
      const result = await fetchAgent("/execute", {
        session_id: boot.publicId,
        token: boot.authToken,
        command: message.command || {},
      });
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "remote_control_ack", id: commandId, ok: true, result }));
      }
      setStatus("Comando PC eseguito");
    } catch (error) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: "remote_control_ack",
          id: commandId,
          ok: false,
          error: error.message,
        }));
      }
      setStatus(`Errore controllo PC: ${error.message}`);
    }
  }

  function sendChat() {
    if (sessionClosed) return;
    const text = (chatInput?.value || "").trim();
    if (!text) return;
    if (dataChannel && dataChannel.readyState === "open") {
      dataChannel.send(text);
    } else if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "chat", text }));
    }
    appendChat(`Tu: ${text}`, "me");
    chatInput.value = "";
  }

  startBtn?.addEventListener("click", startSession);
  stopBtn?.addEventListener("click", stopSession);
  customerMuteMicBtn?.addEventListener("click", toggleCustomerMicrophone);
  consentAudio?.addEventListener("change", () => {
    if (!consentAudio.checked) {
      customerMicMuted = false;
    }
    syncCustomerMicUi();
  });
  approveAdvancedBtn?.addEventListener("click", approveAdvanced);
  rejectAdvancedBtn?.addEventListener("click", rejectAdvanced);
  customerFullscreenBtn?.addEventListener("click", toggleCustomerFullscreen);
  compactChatBtn?.addEventListener("click", toggleCompactChat);
  document.addEventListener("fullscreenchange", () => {
    customerFullscreen = Boolean(document.fullscreenElement);
    syncCustomerLayout();
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      syncState();
    }
  });
  sendBtn?.addEventListener("click", sendChat);
  chatInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") sendChat();
  });

  if (sessionClosed) {
    markSessionClosed();
  } else {
    syncCustomerLayout();
    syncCustomerMicUi();
    syncStartButtonUi();
    syncState();
    if (!stateTimer) {
      stateTimer = window.setInterval(syncState, statePollDelayMs);
    }
  }
  window.addEventListener("beforeunload", () => {
    cleanup(false);
  });
})();
