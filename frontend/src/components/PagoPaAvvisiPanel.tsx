import { useCallback, useEffect, useRef, useState } from 'react'
import './PagoPaAvvisiPanel.css'

type Avviso = {
  numero_avviso: string; importo: string; tipologia: string; stato: string
  checkout_url: string; documento_id?: string
}

export function PagoPaAvvisiPanel({ fascicoloId, refreshKey, onHasAvvisi, onNuovo, onRicevute }: {
  fascicoloId: string; refreshKey: number; onHasAvvisi: (value: boolean) => void
  onNuovo: () => void; onRicevute: () => void
}) {
  const [avvisi, setAvvisi] = useState<Avviso[]>([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [recover, setRecover] = useState(false)
  const [numero, setNumero] = useState('')
  const [importo, setImporto] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const base = `/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/pagopa`
  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const response = await fetch(`${base}/avvisi`, { signal })
      const data = await response.json()
      if (!response.ok || !data.ok) throw new Error(data.message || 'Avvisi non disponibili.')
      if (signal?.aborted) return
      setAvvisi(data.avvisi); onHasAvvisi(data.avvisi.length > 0)
    } catch (error) {
      if (!signal?.aborted) setMessage(error instanceof Error ? error.message : 'Avvisi non disponibili.')
    }
  }, [base, onHasAvvisi])
  useEffect(() => {
    const abort = new AbortController()
    void load(abort.signal)
    return () => abort.abort()
  }, [load, refreshKey])
  const registra = async () => {
    setBusy(true); setMessage('Conservazione dell’avviso…')
    try {
      const response = await fetch(`${base}/avvisi`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ numero_avviso: numero, importo: importo.replace(',', '.') }),
      })
      const data = await response.json()
      if (!response.ok || !data.ok) throw new Error(data.message || 'Avviso non conservato.')
      setRecover(false); setMessage('Avviso conservato. Lo stato del pagamento viene verificato sul portale ufficiale.')
      await load()
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Avviso non conservato.') }
    finally { setBusy(false) }
  }
  const carica = async (file: File) => {
    setBusy(true); setMessage('Verifica della ricevuta…')
    try {
      const body = new FormData(); body.append('ricevuta', file)
      const response = await fetch(`${base}/ricevuta`, { method: 'POST', body })
      const data = await response.json()
      if (!response.ok || !data.ok) throw new Error(data.message || 'Ricevuta non acquisita.')
      setMessage(data.message); await load()
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Ricevuta non acquisita.') }
    finally { setBusy(false) }
  }
  return <section className="iu-pagopa-avvisi" aria-label="Avvisi PagoPA del fascicolo">
    <header><strong>Avvisi conservati nel fascicolo</strong>
      <button type="button" onClick={() => setRecover(!recover)} disabled={busy}>Collega avviso esistente</button>
    </header>
    {recover && <form onSubmit={(event) => { event.preventDefault(); void registra() }}>
      <label>Numero avviso<input value={numero} onChange={(event) => setNumero(event.target.value)} inputMode="numeric" pattern="[0-9]{18}" maxLength={18} required /></label>
      <label>Importo dell’avviso (€)<input value={importo} onChange={(event) => setImporto(event.target.value)} inputMode="decimal" required /></label>
      <button type="submit" disabled={busy}>Conserva avviso</button>
    </form>}
    {avvisi.map((avviso) => <article key={avviso.numero_avviso}>
      <div><strong>Avviso {avviso.numero_avviso}</strong>
        <p>{avviso.tipologia} · € {new Intl.NumberFormat('it-IT', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(avviso.importo))}</p>
        <p>{avviso.documento_id ? 'Ricevuta verificata e acquisita' : 'Ricevuta da acquisire · verifica l’esito sul portale ufficiale'}</p>
      </div>
      {!avviso.documento_id && /^https:\/\/checkout\.pagopa\.it\/\d{29}$/.test(avviso.checkout_url) &&
        <a href={avviso.checkout_url} target="_blank" rel="noopener noreferrer">Verifica avviso / prosegui su pagoPA</a>}
      {avviso.documento_id && <a href={`/fascicoli/${encodeURIComponent(fascicoloId)}#documenti`}>Documenti del fascicolo</a>}
    </article>)}
    {avvisi.length > 0 && <>
      <p>Il pagamento si completa sul sito ufficiale pagoPA. I dati della carta restano su quel sito. Conservare l’avviso non significa registrarlo come pagato.</p>
      <div className="iu-pagopa-avvisi__actions">
        <button type="button" onClick={onRicevute}>Cerca ricevuta sul PST</button>
        <button type="button" disabled={busy} onClick={() => fileRef.current?.click()}>Acquisisci ricevuta RT</button>
        <button type="button" onClick={onNuovo} disabled={busy}>Nuovo pagamento</button>
      </div>
      <input ref={fileRef} type="file" accept=".xml,.p7m" hidden onChange={(event) => {
        const file = event.target.files?.[0]; if (file) void carica(file); event.target.value = ''
      }} />
    </>}
    {message && <p role="status">{message}</p>}
  </section>
}
