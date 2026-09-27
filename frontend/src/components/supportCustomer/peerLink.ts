/**
 * Connessione WebRTC del cliente. Il cliente risponde alle offerte
 * dell'operatore (che crea l'offerta dopo `start_offer`), invia schermo e
 * microfono e riceve l'audio dell'operatore e la chat sul data channel.
 *
 * Porta ensurePeerConnection / flushPendingIceCandidates / addRemoteIceCandidate
 * dello script legacy. In più: una sola creazione concorrente (lo script legacy
 * poteva creare due RTCPeerConnection se offerta e ICE arrivavano insieme).
 */

const CONNECTION_STATE_LABELS: Record<RTCPeerConnectionState, string> = {
  new: 'in preparazione',
  connecting: 'in corso',
  connected: 'attiva',
  disconnected: 'interrotta',
  failed: 'non riuscita',
  closed: 'chiusa',
}

export function connectionStateLabel(state: RTCPeerConnectionState): string {
  return `Connessione ${CONNECTION_STATE_LABELS[state] || state}`
}

type PeerLinkOptions = {
  rtcConfiguration: () => Promise<RTCConfiguration>
  localStream: () => MediaStream | null
  sendSignal: (message: Record<string, unknown>) => void
  onRemoteStream: (stream: MediaStream) => void
  onChatMessage: (text: string) => void
  onConnectionState: (label: string) => void
}

export class SupportPeerLink {
  private pc: RTCPeerConnection | null = null
  private creating: Promise<RTCPeerConnection> | null = null
  private dataChannel: RTCDataChannel | null = null
  private generation = 0
  private readonly pendingIceCandidates: RTCIceCandidateInit[] = []
  private readonly options: PeerLinkOptions

  constructor(options: PeerLinkOptions) {
    this.options = options
  }

  get active(): boolean {
    return Boolean(this.pc)
  }

  ensure(): Promise<RTCPeerConnection> {
    if (this.pc) return Promise.resolve(this.pc)
    if (this.creating) return this.creating
    const creating: Promise<RTCPeerConnection> = this.create().finally(() => {
      if (this.creating === creating) this.creating = null
    })
    this.creating = creating
    return creating
  }

  private async create(): Promise<RTCPeerConnection> {
    const generation = this.generation
    const configuration = await this.options.rtcConfiguration()
    // Chiusura arrivata durante l'attesa della configurazione: niente connessioni orfane.
    if (generation !== this.generation) throw new Error('Connessione assistenza annullata.')
    if (this.pc) return this.pc
    const pc = new RTCPeerConnection(configuration)
    const stream = this.options.localStream()
    if (stream) {
      stream.getTracks().forEach((track) => pc.addTrack(track, stream))
    }
    pc.onicecandidate = (event) => {
      if (event.candidate) this.options.sendSignal({ type: 'ice', candidate: event.candidate.toJSON() })
    }
    pc.ontrack = (event) => {
      const [remote] = event.streams
      if (remote) this.options.onRemoteStream(remote)
    }
    pc.ondatachannel = (event) => this.setupDataChannel(event.channel)
    pc.onconnectionstatechange = () => {
      if (this.pc === pc) this.options.onConnectionState(connectionStateLabel(pc.connectionState))
    }
    this.pc = pc
    return pc
  }

  private setupDataChannel(channel: RTCDataChannel): void {
    this.dataChannel = channel
    channel.onmessage = (event: MessageEvent) => this.options.onChatMessage(String(event.data ?? ''))
  }

  private async flushPendingIceCandidates(pc: RTCPeerConnection): Promise<void> {
    if (!pc.remoteDescription || !this.pendingIceCandidates.length) return
    const candidates = this.pendingIceCandidates.splice(0, this.pendingIceCandidates.length)
    for (const candidate of candidates) {
      try {
        await pc.addIceCandidate(candidate)
      } catch (error) {
        console.warn('Candidato ICE scartato dopo descrizione remota.', error)
      }
    }
  }

  /** Offerta dell'operatore: descrizione remota, candidati in coda, risposta. */
  async handleOffer(sdp: RTCSessionDescriptionInit): Promise<void> {
    const pc = await this.ensure()
    await pc.setRemoteDescription(sdp)
    await this.flushPendingIceCandidates(pc)
    const answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    this.options.sendSignal({ type: 'answer', sdp: pc.localDescription?.toJSON() ?? answer })
  }

  async handleAnswer(sdp: RTCSessionDescriptionInit): Promise<void> {
    const pc = await this.ensure()
    await pc.setRemoteDescription(sdp)
    await this.flushPendingIceCandidates(pc)
  }

  async addRemoteIceCandidate(candidate: RTCIceCandidateInit): Promise<void> {
    const pc = await this.ensure()
    if (!pc.remoteDescription) {
      this.pendingIceCandidates.push(candidate)
      return
    }
    try {
      await pc.addIceCandidate(candidate)
    } catch (error) {
      console.warn('Candidato ICE remoto non applicato.', error)
    }
  }

  /** Chat sul data channel, se aperto. */
  sendChat(text: string): boolean {
    if (!this.dataChannel || this.dataChannel.readyState !== 'open') return false
    this.dataChannel.send(text)
    return true
  }

  close(): void {
    this.generation += 1
    this.creating = null
    if (this.dataChannel) {
      try {
        this.dataChannel.close()
      } catch {
        // Già chiuso.
      }
      this.dataChannel = null
    }
    if (this.pc) {
      try {
        this.pc.close()
      } catch {
        // Già chiusa.
      }
      this.pc = null
    }
    this.pendingIceCandidates.length = 0
  }
}
