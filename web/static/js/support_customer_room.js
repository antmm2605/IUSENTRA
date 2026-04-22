(() => {
  const boot = window.SUPPORT_BOOTSTRAP || {};
  const $ = (id) => document.getElementById(id);

  const statusBadge = $("statusBadge");
  const peerBadge = $("peerBadge");
  const localPreview = $("localPreview");
  const localPreviewFallback = $("localPreviewFallback");
  const remoteAudio = $("remoteAudio");
  const consentScreen = $("consentScreen");
  const consentAudio = $("consentAudio");
  const consentChat = $("consentChat");
  const startBtn = $("startBtn");
  const stopBtn = $("stopBtn");
  const advancedBanner = $("advancedBanner");
  const approveAdvancedBtn = $("approveAdvancedBtn");
  const rejectAdvancedBtn = $("rejectAdvancedBtn");
  const chatLog = $("chatLog");
  const chatInput = $("chatInput");
  const sendBtn = $("sendBtn");

  let ws = null;
  let pc = null;
  let dataChannel = null;
  let localStream = null;
  let micStream = null;
  let stateTimer = null;
  let pingTimer = null;

  function setStatus(text) {
    if (statusBadge) statusBadge.textContent = text;
  }

  function setPeer(connected) {
    if (!peerBadge) return;
    peerBadge.textContent = connected ? "Operatore collegato" : "Operatore non collegato";
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

  async function syncState() {
    try {
      const payload = await fetchJson(apiUrl("/state"));
      const session = payload.session || {};
      setStatus(session.status_label || "Sessione aggiornata");
      setPeer(Boolean(session.presence && session.presence.operator));
      advancedBanner?.classList.toggle("d-none", !(session.advanced_control_requested && !session.advanced_control_approved));
      if (session.status === "closed") {
        cleanup(false);
        startBtn.disabled = true;
        stopBtn.disabled = true;
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
        appendChat(`Operatore: ${message.text}`, "other");
      }
    };
    ws.onclose = () => {
      if (pingTimer) window.clearInterval(pingTimer);
      pingTimer = null;
      setStatus("Canale realtime chiuso");
      setPeer(false);
    };
  }

  async function acquireMedia() {
    if (!consentScreen?.checked) {
      throw new Error("Per continuare devi autorizzare la condivisione schermo.");
    }

    const screenStream = await navigator.mediaDevices.getDisplayMedia({
      video: { frameRate: { ideal: 12, max: 15 } },
      audio: false,
    });
    const tracks = [...screenStream.getVideoTracks()];

    if (consentAudio?.checked) {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      tracks.push(...micStream.getAudioTracks());
    }

    localStream = new MediaStream(tracks);
    localPreview.srcObject = localStream;
    localPreviewFallback?.classList.add("d-none");

    const videoTrack = screenStream.getVideoTracks()[0];
    if (videoTrack) {
      videoTrack.onended = () => stopSession();
    }
  }

  async function startSession() {
    try {
      startBtn.disabled = true;
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
      await ensurePeerConnection();
      await fetchJson(apiUrl("/start"), { method: "POST", body: JSON.stringify({}) });
      stopBtn.disabled = false;
      setStatus("Sessione avviata");
      if (!stateTimer) {
        stateTimer = window.setInterval(syncState, 4000);
      }
      await syncState();
    } catch (error) {
      console.error(error);
      setStatus(`Errore: ${error.message}`);
      startBtn.disabled = false;
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
      startBtn.disabled = true;
      setStatus("Sessione chiusa");
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
    if (micStream) {
      micStream.getTracks().forEach((track) => track.stop());
      micStream = null;
    }
    localPreview.srcObject = null;
    localPreviewFallback?.classList.remove("d-none");
    if (enableRestart) {
      startBtn.disabled = false;
    }
  }

  async function approveAdvanced() {
    try {
      await fetchJson(apiUrl("/escalation"), { method: "POST", body: JSON.stringify({ action: "approve" }) });
      advancedBanner?.classList.add("d-none");
      appendChat("Hai approvato il controllo remoto avanzato.", "me");
    } catch (error) {
      setStatus(`Errore: ${error.message}`);
    }
  }

  async function rejectAdvanced() {
    try {
      await fetchJson(apiUrl("/escalation"), { method: "POST", body: JSON.stringify({ action: "reject" }) });
      advancedBanner?.classList.add("d-none");
      appendChat("Hai rifiutato il controllo remoto avanzato.", "me");
    } catch (error) {
      setStatus(`Errore: ${error.message}`);
    }
  }

  function sendChat() {
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
  approveAdvancedBtn?.addEventListener("click", approveAdvanced);
  rejectAdvancedBtn?.addEventListener("click", rejectAdvanced);
  sendBtn?.addEventListener("click", sendChat);
  chatInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") sendChat();
  });

  syncState();
})();
