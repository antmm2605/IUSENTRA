/** Scanner WIA già esposto dal Local Signer. Nessun PIN o invio cloud. */
type LocalRequest = RequestInit & { targetAddressSpace: 'loopback' }
type Scan = { ok?: boolean; filename?: string; content_base64?: string }
const bases = ['http://127.0.0.1:27272', 'http://localhost:27272']
let acquiring = false

export function scannerFileFromPayload(payload: Scan): File {
  const encoded = String(payload.content_base64 || '').trim()
  if (!encoded || encoded.length > 84 * 1024 * 1024) throw new Error('La pagina acquisita è vuota o supera 60 MB.')
  let binary: string
  try { binary = atob(encoded) } catch { throw new Error('La pagina acquisita non è leggibile.') }
  if (!binary.length || binary.length > 60 * 1024 * 1024) throw new Error('La pagina acquisita è vuota o supera 60 MB.')
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0))
  if (bytes[0] !== 0xff || bytes[1] !== 0xd8) throw new Error('Lo scanner non ha restituito una pagina JPEG valida.')
  const name = String(payload.filename || 'scansione.jpg').replace(/[\\/:*?"<>|\x00-\x1f]/g, ' ').trim()
  return new File([bytes], name || 'scansione.jpg', { type: 'image/jpeg' })
}

export async function acquireFromLocalScanner(): Promise<File> {
  if (acquiring) throw new Error('È già in corso un’acquisizione dallo scanner.')
  acquiring = true
  try {
    let base = ''
    // Si possono ripetere solo letture di disponibilità, mai il comando WIA.
    for (const candidate of bases) {
      try {
        const response = await fetch(`${candidate}/ping?light=1`, { signal: AbortSignal.timeout(2500), mode: 'cors', targetAddressSpace: 'loopback' } as LocalRequest)
        const status = await response.json()
        if (response.ok && status.ok) { base = candidate; break }
      } catch { /* Prova l'altro nome loopback, senza avviare lo scanner. */ }
    }
    if (!base) throw new Error('Avvia IUSENTRA Local Signer sul PC collegato allo scanner e riprova.')
    let response: Response
    try {
      response = await fetch(`${base}/scanner/acquire`, {
        method: 'POST', mode: 'cors', targetAddressSpace: 'loopback',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ timeout: 120 }), signal: AbortSignal.timeout(130_000),
      } as LocalRequest)
    } catch {
      throw new Error('Risposta dello scanner non ricevuta. Controlla la finestra di acquisizione sul PC prima di riprovare: il comando non è stato ripetuto.')
    }
    if (response.status === 404) throw new Error('Aggiorna IUSENTRA Local Signer dalle impostazioni per usare lo scanner.')
    const payload = await response.json().catch(() => null) as Scan | null
    if (!response.ok || !payload?.ok) throw new Error('Acquisizione annullata o scanner non disponibile. Controlla collegamento, driver e finestra dello scanner sul PC.')
    return scannerFileFromPayload(payload)
  } finally { acquiring = false }
}
