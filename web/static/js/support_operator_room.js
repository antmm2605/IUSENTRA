(() => {
  const boot = window.SUPPORT_BOOTSTRAP || {};
  const $ = (id) => document.getElementById(id);

  const statusBadge = $("statusBadge");
  const peerBadge = $("peerBadge");
  const remoteControlBadge = $("remoteControlBadge");
  const remoteScreen = $("remoteScreen");
  const remoteVideo = $("remoteVideo");
  const remoteVideoFallback = $("remoteVideoFallback");
  const operatorMic = $("operatorMic");
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

  let ws = null;
  let pc = null;
  let dataChannel = null;
  let localStream = null;
  let stateTimer = null;
  let pingTimer = null;
  let makingOffer = false;
  let controlRequested = false;
  let controlApproved = false;
  let sessionClosed = Boolean(boot.closed || boot.status === "closed");

  function setStatus(text) {
    if (statusBadge) statusBadge.textContent = text;
  }

  function setPeer(connected) {
    if (!peerBadge) return;
    peerBadge.textContent = connected ? "Cliente collegato" : "Cliente non collegato";
    peerBadge.className = `badge ${connected ? "bg-success" : "bg-secondary"}`;
  }

  function apiUrl(path) {
    return `${boot.apiPrefix}${path}?role=${encodeURIComponent(boot.role)}&token=${encodeURIComponent(boot.authToken)}`;
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
    const active = Boolean(controlApproved && !sessionClosed);
    remoteScreen?.classList.toggle("support-room__screen--control-enabled", active);
    remoteControls().forEach((item) => {
      item.disabled = !active;
    });
    if (remoteControlBadge) {
      if (active) {
        remoteControlBadge.textContent = "Controllo PC attivo";
        remoteControlBadge.className = "badge bg-success";
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
      requestAdvancedBtn.textContent = controlApproved ? "Controllo PC attivo" : "Richiedi controllo PC";
    }
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
    controlApproved = false;
    updateControlUi();
    if (remoteVideoFallback) {
      remoteVideoFallback.textContent = "Sessione conclusa: crea una nuova sessione per riprendere l'assistenza.";
    }
  }

  async function syncState() {
    try {
      const payload = await fetchJson(apiUrl("/state"));
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
    dataChannel = pc.createDataChannel("support-chat", { ordered: true });
    setupDataChannel(dataChannel);

    pc.onicecandidate = (event) => {
      if (event.candidate && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ice", candidate: event.candidate }));
      }
    };
    pc.ontrack = (event) => {
      const [stream] = event.streams;
      if (stream) {
        remoteVideo.srcObject = stream;
        remoteVideoFallback?.classList.add("d-none");
      }
    };
    pc.onconnectionstatechange = () => {
      if (pc) setStatus(`Connessione ${pc.connectionState}`);
    };
    return pc;
  }

  async function connectWs() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return;
    }
    ws = new WebSocket(wsUrl());
    ws.onopen = () => {
      setStatus("Canale realtime attivo");
      pingTimer = window.setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping" }));
        }
      }, 20000);
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
        } else {
          setStatus(`Errore controllo PC: ${message.error || "comando non riuscito"}`);
        }
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
      setStatus("Canale realtime chiuso");
      setPeer(false);
    };
  }

  async function acquireOperatorAudio() {
    if (!operatorMic?.checked) return;
    localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
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
      await fetchJson(apiUrl("/start"), { method: "POST", body: JSON.stringify({}) });
      if (!stateTimer) {
        stateTimer = window.setInterval(syncState, 4000);
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
      try { ws.close(); } catch (_) {}
      ws = null;
    }
    if (localStream) {
      localStream.getTracks().forEach((track) => track.stop());
      localStream = null;
    }
    if (remoteVideo) {
      remoteVideo.srcObject = null;
      remoteVideoFallback?.classList.remove("d-none");
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
    if (!remoteScreen) return;
    if (document.fullscreenElement) {
      await document.exitFullscreen();
      return;
    }
    await remoteScreen.requestFullscreen();
  }

  joinBtn?.addEventListener("click", joinSession);
  requestAdvancedBtn?.addEventListener("click", requestAdvanced);
  closeBtn?.addEventListener("click", closeSession);
  sendBtn?.addEventListener("click", sendChat);
  copyLinkBtn?.addEventListener("click", copyLink);
  fullscreenBtn?.addEventListener("click", toggleFullscreen);
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
  if (sessionClosed) {
    markSessionClosed();
  } else {
    syncState();
  }
})();
