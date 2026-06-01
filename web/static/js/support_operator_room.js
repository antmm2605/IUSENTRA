(() => {
  if (window.__iusentraSupportOperatorRoomLoaded) return;
  window.__iusentraSupportOperatorRoomLoaded = true;

  const $ = (id) => document.getElementById(id);

  function readBootstrap() {
    if (window.SUPPORT_BOOTSTRAP) return window.SUPPORT_BOOTSTRAP;
    const element = $("support-operator-bootstrap");
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
  const remoteControlBadge = $("remoteControlBadge");
  const remoteScreen = $("remoteScreen");
  const remoteVideo = $("remoteVideo");
  const remoteAudio = $("remoteAudio");
  const remoteAgentFrame = $("remoteAgentFrame");
  const remoteVideoFallback = $("remoteVideoFallback");
  const operatorMic = $("operatorMic");
  const operatorMuteMicBtn = $("operatorMuteMicBtn");
  const joinBtn = $("joinBtn");
  const requestAdvancedBtn = $("requestAdvancedBtn");
  const closeBtn = $("closeBtn");
  const copyLinkBtn = $("copyLinkBtn");
  const fullscreenBtn = $("fullscreenBtn");
  const joinUrlField = $("joinUrlField");
  const chatLog = $("chatLog");
  const chatInput = $("chatInput");
  const sendBtn = $("sendBtn");
  const remoteControlText = $("remoteControlText");
  const sendRemoteTextBtn = $("sendRemoteTextBtn");
  const remoteKeyButtons = Array.from(document.querySelectorAll("[data-remote-key]"));
  const supportShell = $("supportOperatorShell") || document.querySelector("[data-support-operator-react='true']");

  let ws = null;
  let wsOpenPromise = null;
  let pc = null;
  let dataChannel = null;
  let localStream = null;
  let stateTimer = null;
  let pingTimer = null;
  let makingOffer = false;
  let controlRequested = false;
  let controlApproved = false;
  let clientConnected = false;
  let pageFullscreen = false;
  let operatorMicMuted = false;
  let closingWsIntentionally = false;
  let stateSyncInFlight = false;
  let sessionClosed = Boolean(boot.closed || boot.status === "closed");
  const statePollDelayMs = 12000;

  function setStatus(text) {
    if (statusBadge) statusBadge.textContent = text;
  }

  function setPeer(connected) {
    clientConnected = Boolean(connected);
    if (!peerBadge) return;
    peerBadge.textContent = clientConnected ? "Cliente collegato" : "Cliente non collegato";
    peerBadge.className = `badge ${clientConnected ? "bg-success" : "bg-secondary"}`;
    updateControlUi();
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

  function appendChat(text, who = "other") {
    if (!chatLog) return;
    const item = document.createElement("div");
    item.className = `support-chat-log__message support-chat-log__message--${who}`;
    item.textContent = text;
    chatLog.appendChild(item);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  function remoteControls() {
    return [remoteControlText, sendRemoteTextBtn, ...remoteKeyButtons].filter(Boolean);
  }

  function updateControlUi() {
    const active = Boolean(controlApproved && clientConnected && !sessionClosed);
    remoteScreen?.classList.toggle("support-room__screen--control-enabled", active);
    remoteControls().forEach((item) => {
      item.disabled = !active;
    });
    if (remoteControlBadge) {
      if (active) {
        remoteControlBadge.textContent = "Controllo PC attivo";
        remoteControlBadge.className = "badge bg-success";
      } else if (controlApproved) {
        remoteControlBadge.textContent = "In attesa cliente";
        remoteControlBadge.className = "badge bg-warning text-dark";
      } else if (controlRequested) {
        remoteControlBadge.textContent = "In attesa consenso cliente";
        remoteControlBadge.className = "badge bg-warning text-dark";
      } else {
        remoteControlBadge.textContent = "Controllo PC non attivo";
        remoteControlBadge.className = "badge bg-secondary";
      }
    }
    if (requestAdvancedBtn) {
      requestAdvancedBtn.disabled = sessionClosed || controlApproved || controlRequested;
      requestAdvancedBtn.textContent = controlApproved
        ? (clientConnected ? "Controllo PC attivo" : "In attesa cliente")
        : "Richiedi controllo PC";
    }
  }

  function operatorAudioTracks() {
    return localStream ? localStream.getAudioTracks().filter((track) => track.readyState !== "ended") : [];
  }

  function syncOperatorMicUi() {
    if (!operatorMuteMicBtn) return;
    const tracks = operatorAudioTracks();
    const canToggle = !sessionClosed && (tracks.length > 0 || Boolean(operatorMic?.checked));
    operatorMuteMicBtn.disabled = !canToggle;
    operatorMuteMicBtn.setAttribute("aria-pressed", operatorMicMuted ? "true" : "false");
    operatorMuteMicBtn.classList.toggle("iu-support-button--active", operatorMicMuted);
    const label = operatorMuteMicBtn.querySelector("span:last-child");
    if (label) {
      label.textContent = operatorMicMuted ? "Riattiva microfono" : "Muta microfono";
    }
  }

  function toggleOperatorMicrophone() {
    if (sessionClosed) return;
    const tracks = operatorAudioTracks();
    if (!tracks.length && !operatorMic?.checked) {
      syncOperatorMicUi();
      return;
    }
    operatorMicMuted = !operatorMicMuted;
    tracks.forEach((track) => {
      track.enabled = !operatorMicMuted;
    });
    setStatus(
      tracks.length
        ? (operatorMicMuted ? "Microfono operatore disattivato" : "Microfono operatore attivo")
        : (operatorMicMuted ? "Microfono operatore disattivato all'avvio" : "Microfono operatore attivo all'avvio")
    );
    syncOperatorMicUi();
  }

  function markSessionClosed() {
    sessionClosed = true;
    cleanup(false);
    setStatus("Sessione chiusa");
    setPeer(false);
    joinBtn.disabled = true;
    requestAdvancedBtn.disabled = true;
    closeBtn.disabled = true;
    sendBtn.disabled = true;
    chatInput.disabled = true;
    operatorMic.disabled = true;
    operatorMuteMicBtn.disabled = true;
    controlApproved = false;
    updateControlUi();
    if (remoteVideoFallback) {
      remoteVideoFallback.textContent = "Sessione conclusa: crea una nuova sessione per riprendere l'assistenza.";
    }
  }

  async function syncState() {
    if (stateSyncInFlight || sessionClosed) return;
    stateSyncInFlight = true;
    try {
      const payload = await fetchJson(stateUrl());
      const session = payload.session || {};
      setStatus(session.status_label || "Sessione aggiornata");
      setPeer(Boolean(session.presence && session.presence.client));
      controlRequested = Boolean(session.advanced_control_requested);
      controlApproved = Boolean(session.advanced_control_approved);
      updateControlUi();
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
    dataChannel.onmessage = (event) => appendChat(`Cliente: ${event.data}`, "other");
  }

  async function ensurePeerConnection() {
    if (pc) return pc;

    pc = new RTCPeerConnection(await getRtcConfiguration());
    if (localStream) {
      localStream.getTracks().forEach((track) => pc.addTrack(track, localStream));
    }
    if (!pc.getTransceivers().some((transceiver) => transceiver.receiver?.track?.kind === "video")) {
      pc.addTransceiver("video", { direction: "recvonly" });
    }
    if (!pc.getTransceivers().some((transceiver) => transceiver.receiver?.track?.kind === "audio")) {
      pc.addTransceiver("audio", { direction: "recvonly" });
    }
    dataChannel = pc.createDataChannel("support-chat", { ordered: true });
    setupDataChannel(dataChannel);

    pc.onicecandidate = (event) => {
      if (event.candidate && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ice", candidate: event.candidate }));
      }
    };
    pc.ontrack = (event) => {
      const [stream] = event.streams;
      if (!stream) return;
      if (event.track?.kind === "audio" && remoteAudio) {
        remoteAudio.srcObject = stream;
        remoteAudio.play?.().catch(() => {});
        setStatus("Audio cliente attivo");
        return;
      }
      if (event.track?.kind === "video") {
        remoteVideo.srcObject = stream;
        remoteVideo.classList.remove("d-none");
        remoteAgentFrame?.classList.add("d-none");
        remoteVideoFallback?.classList.add("d-none");
      }
    };
    pc.onconnectionstatechange = () => {
      if (pc) setStatus(`Connessione ${pc.connectionState}`);
    };
    return pc;
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
      if (message.type === "remote_control_ack") {
        if (message.ok) {
          setStatus("Comando PC eseguito");
          const result = message.result || {};
          const detail = result.key || result.text || result.action || "";
          appendChat(`PC cliente: comando eseguito${detail ? ` (${detail})` : ""}.`, "other");
        } else {
          const errorText = message.error || "comando non riuscito";
          setStatus(`Errore controllo PC: ${errorText}`);
          appendChat(`PC cliente: comando non riuscito: ${errorText}.`, "other");
        }
        return;
      }
      if (message.type === "screen_frame" && message.image) {
        if (remoteAgentFrame) {
          remoteAgentFrame.src = message.image;
          remoteAgentFrame.classList.remove("d-none");
        }
        if (remoteVideo) {
          remoteVideo.classList.add("d-none");
          remoteVideo.srcObject = null;
        }
        remoteVideoFallback?.classList.add("d-none");
        setStatus("Schermo cliente visibile");
        return;
      }
      if (message.type === "start_offer") {
        await createAndSendOffer();
        return;
      }
      if (message.type === "offer") {
        const peer = await ensurePeerConnection();
        await peer.setRemoteDescription(new RTCSessionDescription(message.sdp));
        const answer = await peer.createAnswer();
        await peer.setLocalDescription(answer);
        ws.send(JSON.stringify({ type: "answer", sdp: peer.localDescription }));
        if (remoteVideo) remoteVideo.classList.remove("d-none");
        remoteAgentFrame?.classList.add("d-none");
        return;
      }
      if (message.type === "answer") {
        const peer = await ensurePeerConnection();
        await peer.setRemoteDescription(new RTCSessionDescription(message.sdp));
        return;
      }
      if (message.type === "ice" && message.candidate) {
        const peer = await ensurePeerConnection();
        try {
          await peer.addIceCandidate(new RTCIceCandidate(message.candidate));
        } catch (error) {
          console.error(error);
        }
        return;
      }
      if (message.type === "chat") {
        appendChat(`Cliente: ${message.text}`, "other");
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

  async function acquireOperatorAudio() {
    if (!operatorMic?.checked) {
      operatorMicMuted = false;
      syncOperatorMicUi();
      return;
    }
    try {
      localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      operatorAudioTracks().forEach((track) => {
        track.enabled = !operatorMicMuted;
      });
      syncOperatorMicUi();
    } catch (error) {
      if (localStream) {
        localStream.getTracks().forEach((track) => track.stop());
        localStream = null;
      }
      operatorMicMuted = true;
      syncOperatorMicUi();
      console.warn("Microfono operatore non autorizzato o non disponibile: assistenza avviata senza audio.", error);
      setStatus("Microfono operatore non disponibile: assistenza avviata senza audio");
    }
  }

  async function createAndSendOffer() {
    if (!ws || ws.readyState !== WebSocket.OPEN || makingOffer) return;
    makingOffer = true;
    try {
      const peer = await ensurePeerConnection();
      const offer = await peer.createOffer();
      await peer.setLocalDescription(offer);
      ws.send(JSON.stringify({ type: "offer", sdp: peer.localDescription }));
    } finally {
      makingOffer = false;
    }
  }

  async function joinSession() {
    if (sessionClosed) {
      markSessionClosed();
      return;
    }
    try {
      joinBtn.disabled = true;
      await acquireOperatorAudio();
      await connectWs();
      await ensurePeerConnection();
      if (!stateTimer) {
        stateTimer = window.setInterval(syncState, statePollDelayMs);
      }
      setStatus("Operatore collegato");
      await syncState();
    } catch (error) {
      console.error(error);
      setStatus(`Errore: ${error.message}`);
      joinBtn.disabled = false;
    }
  }

  async function requestAdvanced() {
    if (sessionClosed || controlApproved || controlRequested) return;
    try {
      await fetchJson(apiUrl("/escalation"), { method: "POST", body: JSON.stringify({ action: "request" }) });
      controlRequested = true;
      updateControlUi();
      appendChat("Hai richiesto il controllo remoto del PC.", "me");
      await syncState();
    } catch (error) {
      setStatus(`Errore: ${error.message}`);
    }
  }

  async function closeSession() {
    try {
      await fetchJson(apiUrl("/close"), { method: "POST", body: JSON.stringify({}) });
    } catch (error) {
      console.error(error);
    } finally {
      cleanup(false);
      joinBtn.disabled = true;
      sessionClosed = true;
      setStatus("Sessione chiusa");
      updateControlUi();
    }
  }

  function cleanup(enableRestart) {
    if (stateTimer) window.clearInterval(stateTimer);
    if (pingTimer) window.clearInterval(pingTimer);
    stateTimer = null;
    pingTimer = null;
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
    operatorMicMuted = false;
    syncOperatorMicUi();
    if (remoteVideo) {
      remoteVideo.srcObject = null;
      remoteVideo.classList.remove("d-none");
      remoteVideoFallback?.classList.remove("d-none");
    }
    if (remoteAgentFrame) {
      remoteAgentFrame.classList.add("d-none");
      remoteAgentFrame.src = "";
    }
    if (enableRestart) {
      joinBtn.disabled = false;
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

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(joinUrlField?.value || "");
      setStatus("Link cliente copiato negli appunti");
    } catch (error) {
      setStatus("Copia del link non riuscita");
    }
  }

  function sendRemoteCommand(command) {
    if (sessionClosed || !controlApproved) {
      setStatus("Controllo PC non ancora approvato dal cliente");
      return;
    }
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setStatus("Canale realtime non attivo");
      return;
    }
    ws.send(JSON.stringify({
      type: "remote_control",
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      command,
    }));
  }

  function sendRemoteText() {
    const text = remoteControlText?.value || "";
    if (!text) return;
    sendRemoteCommand({ action: "text", text });
    remoteControlText.value = "";
  }

  function sendRemoteClick(event, action, button) {
    if (!remoteScreen) return;
    event.preventDefault();
    const rect = remoteScreen.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const xRatio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
    const yRatio = Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height));
    sendRemoteCommand({
      action,
      button,
      x_ratio: xRatio,
      y_ratio: yRatio,
    });
  }

  async function toggleFullscreen() {
    const fullscreenTarget = supportShell || remoteScreen;
    if (!fullscreenTarget) return;
    if (document.fullscreenElement || pageFullscreen) {
      pageFullscreen = false;
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      }
      syncFullscreenUi();
      return;
    }
    try {
      if (fullscreenTarget.requestFullscreen && document.fullscreenEnabled !== false) {
        await fullscreenTarget.requestFullscreen();
      }
    } catch (error) {
      pageFullscreen = true;
      setStatus("Schermo intero attivo nella pagina");
    }
    if (!document.fullscreenElement) {
      pageFullscreen = true;
    }
    syncFullscreenUi();
  }

  function syncFullscreenUi() {
    const active = Boolean(document.fullscreenElement || pageFullscreen);
    supportShell?.classList.toggle("iu-support-operator--fullscreen", active);
    fullscreenBtn?.classList.toggle("iu-support-button--active", active);
    const label = fullscreenBtn?.querySelector("span:last-child");
    if (label) {
      label.textContent = active ? "Esci schermo intero" : "Schermo intero";
    }
  }

  joinBtn?.addEventListener("click", joinSession);
  operatorMuteMicBtn?.addEventListener("click", toggleOperatorMicrophone);
  operatorMic?.addEventListener("change", () => {
    if (!operatorMic.checked) {
      operatorMicMuted = false;
    }
    syncOperatorMicUi();
  });
  requestAdvancedBtn?.addEventListener("click", requestAdvanced);
  closeBtn?.addEventListener("click", closeSession);
  sendBtn?.addEventListener("click", sendChat);
  copyLinkBtn?.addEventListener("click", copyLink);
  fullscreenBtn?.addEventListener("click", toggleFullscreen);
  document.addEventListener("fullscreenchange", syncFullscreenUi);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      syncState();
    }
  });
  sendRemoteTextBtn?.addEventListener("click", sendRemoteText);
  remoteControlText?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") sendRemoteText();
  });
  remoteKeyButtons.forEach((button) => {
    button.addEventListener("click", () => sendRemoteCommand({ action: "key", key: button.dataset.remoteKey }));
  });
  remoteScreen?.addEventListener("click", (event) => sendRemoteClick(event, "click", "left"));
  remoteScreen?.addEventListener("dblclick", (event) => sendRemoteClick(event, "double_click", "left"));
  remoteScreen?.addEventListener("contextmenu", (event) => sendRemoteClick(event, "click", "right"));
  chatInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") sendChat();
  });

  updateControlUi();
  syncOperatorMicUi();
  if (sessionClosed) {
    markSessionClosed();
  } else {
    syncState();
    if (!stateTimer) {
      stateTimer = window.setInterval(syncState, statePollDelayMs);
    }
  }
  window.addEventListener("beforeunload", () => cleanup(false));
})();
