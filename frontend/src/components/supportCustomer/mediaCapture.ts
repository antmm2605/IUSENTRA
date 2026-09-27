/**
 * Acquisizione dei flussi locali del cliente: microfono (getUserMedia) e
 * schermo (getDisplayMedia). Nessuno stato: il controller decide i fallback.
 */

/** Tracce audio vive e senza duplicati dei flussi indicati (microfono + flusso inviato). */
export function liveAudioTracks(...streams: Array<MediaStream | null>): MediaStreamTrack[] {
  const tracks = streams.flatMap((stream) => (stream ? stream.getAudioTracks() : []))
  return tracks.filter((track, index) => track && track.readyState !== 'ended' && tracks.indexOf(track) === index)
}

export function setTracksEnabled(tracks: MediaStreamTrack[], enabled: boolean): void {
  tracks.forEach((track) => {
    track.enabled = enabled
  })
}

export function stopStream(stream: MediaStream | null): void {
  stream?.getTracks().forEach((track) => track.stop())
}

export function requestMicrophoneStream(): Promise<MediaStream> {
  return navigator.mediaDevices.getUserMedia({ audio: true, video: false })
}

export function browserScreenShareSupported(): boolean {
  return typeof navigator.mediaDevices?.getDisplayMedia === 'function'
}

/**
 * Percorso primario: condivisione schermo nativa del browser. Funziona su
 * qualsiasi browser moderno SENZA agente locale: lo schermo viaggia come
 * traccia video WebRTC.
 */
export function requestScreenStream(): Promise<MediaStream> {
  return navigator.mediaDevices.getDisplayMedia({
    video: { frameRate: { ideal: 15, max: 30 } },
    audio: false,
  })
}

export function errorName(error: unknown): string {
  return (error as { name?: string } | null)?.name || ''
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  return String((error as { message?: string } | null)?.message || error || '')
}
