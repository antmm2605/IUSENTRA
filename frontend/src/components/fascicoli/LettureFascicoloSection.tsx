import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, BookOpenCheck, Check, Pencil, RefreshCw, X } from 'lucide-react'
import { Badge } from '../dashboard'
import {
  anomalieOrdinate,
  etichettaCampo,
  fraseCollaudo,
  fraseLetturaAutomatica,
  fraseNovita,
  lettoriDaMostrare,
  oggettiInAttesa,
  riassuntoArchivio,
  riassuntoLetture,
  tonoGravita,
  type AnomaliaLettura,
  type EsitoAggiornamentoLetture,
  type FattoDaConfermare,
  type LettureFascicolo,
} from './lettureFascicolo'

const OGGETTI_VISIBILI = 6

// Il registro delle letture del fascicolo: che cosa il gestionale ha già letto
// (per lettore e per documento), le novità dall'ultima apertura e i dati
// letti che i controlli giudicano dubbi — le date prima di tutto — che
// l'avvocato conferma o corregge. Legge /api/v1/ui/fascicoli/<id>/letture,
// mai in cache: le novità sono personali.
export function LettureFascicoloSection({ fascicoloId, refreshKey = 0, onAggiornato }: { fascicoloId: string; refreshKey?: number; onAggiornato?: () => void }) {
  const [letture, setLetture] = useState<LettureFascicolo | null>(null)
  const [loading, setLoading] = useState(false)
  const [aggiornamento, setAggiornamento] = useState<EsitoAggiornamentoLetture | null>(null)
  const [error, setError] = useState('')
  const [correzione, setCorrezione] = useState<{ id: string; valore: string } | null>(null)
  const [correzioneFatto, setCorrezioneFatto] = useState<{ id: string; valore: string } | null>(null)
  const [tuttiGliOggetti, setTuttiGliOggetti] = useState(false)

  const corrente = useRef<LettureFascicolo | null>(null)
  const richiestaInCorso = useRef(false)
  const notificaAggiornamento = useRef(onAggiornato)
  notificaAggiornamento.current = onAggiornato

  const load = useCallback(async () => {
    if (!fascicoloId || richiestaInCorso.current) return
    richiestaInCorso.current = true
    if (!corrente.current) setLoading(true)
    setError('')
    try {
      const response = await fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/letture${corrente.current ? '?visto=0' : ''}`, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } })
      const payload = await response.json().catch(() => ({})) as { ok?: boolean; letture?: LettureFascicolo; errore?: string }
      if (!response.ok || !payload.ok || !payload.letture) throw new Error(payload.errore || 'Registro delle letture non disponibile.')
      const precedente = corrente.current
      const aggiornate = precedente ? { ...payload.letture, novita: precedente.novita } : payload.letture
      corrente.current = aggiornate
      setLetture(aggiornate)
      if (precedente && (precedente.impronta !== aggiornate.impronta || precedente.archivio?.lettura_automatica.ultima_lettura !== aggiornate.archivio?.lettura_automatica.ultima_lettura)) {
        notificaAggiornamento.current?.()
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Registro delle letture non disponibile.')
    } finally {
      richiestaInCorso.current = false
      setLoading(false)
    }
  }, [fascicoloId])

  useEffect(() => { void load() }, [load, refreshKey])
  useEffect(() => {
    const aggiornaSeVisibile = () => { if (document.visibilityState === 'visible') void load() }
    const timer = window.setInterval(aggiornaSeVisibile, 15000)
    window.addEventListener('focus', aggiornaSeVisibile)
    return () => { window.clearInterval(timer); window.removeEventListener('focus', aggiornaSeVisibile) }
  }, [load])

  const aggiorna = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const response = await fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/letture/aggiorna`, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: '{}' })
      const payload = await response.json().catch(() => ({})) as { ok?: boolean; letture?: LettureFascicolo; esito?: EsitoAggiornamentoLetture; errore?: string }
      if (!response.ok || !payload.ok || !payload.letture) throw new Error(payload.errore || 'Aggiornamento delle letture non completato.')
      corrente.current = payload.letture
      setLetture(payload.letture)
      setAggiornamento(payload.esito || null)
      onAggiornato?.()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Aggiornamento delle letture non completato.')
    } finally {
      setLoading(false)
    }
  }, [fascicoloId, onAggiornato])

  const risolvi = useCallback(async (anomalia: AnomaliaLettura, esito: 'confermata' | 'corretta' | 'ignorata', valore = '') => {
    setError('')
    try {
      const response = await fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/letture/anomalie/${encodeURIComponent(anomalia.id)}`, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: JSON.stringify({ esito, valore }) })
      const payload = await response.json().catch(() => ({})) as { ok?: boolean; errore?: string }
      if (!response.ok || !payload.ok) throw new Error(payload.errore || 'Anomalia non risolta.')
      setCorrezione(null)
      setLetture((current) => current ? { ...current, anomalie: current.anomalie.filter((voce) => voce.id !== anomalia.id), anomalie_aperte: Math.max(0, current.anomalie_aperte - 1) } : current)
      onAggiornato?.()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Anomalia non risolta.')
    }
  }, [fascicoloId, onAggiornato])

  const decidiFatto = useCallback(async (fatto: FattoDaConfermare, esito: 'confermata' | 'corretta' | 'ignorata', valore = '') => {
    setError('')
    try {
      const response = await fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/letture/fatti/${encodeURIComponent(fatto.id)}`, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: JSON.stringify({ esito, valore }) })
      const payload = await response.json().catch(() => ({})) as { ok?: boolean; errore?: string }
      if (!response.ok || !payload.ok) throw new Error(payload.errore || 'Decisione non registrata.')
      setCorrezioneFatto(null)
      setLetture((current) => current?.archivio ? { ...current, archivio: { ...current.archivio, da_confermare: current.archivio.da_confermare.filter((voce) => voce.id !== fatto.id), per_verifica: { ...current.archivio.per_verifica, plausibile: Math.max(0, current.archivio.per_verifica.plausibile - 1), [esito === 'ignorata' ? 'ignorata' : esito === 'corretta' ? 'corretta' : 'verificata']: current.archivio.per_verifica[esito === 'ignorata' ? 'ignorata' : esito === 'corretta' ? 'corretta' : 'verificata'] + 1 } } } : current)
      onAggiornato?.()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Decisione non registrata.')
    }
  }, [fascicoloId, onAggiornato])

  const riassunto = useMemo(() => (letture ? riassuntoLetture(letture) : null), [letture])
  const archivio = useMemo(() => (letture ? riassuntoArchivio(letture.archivio) : null), [letture])
  const collaudo = useMemo(() => (letture ? fraseCollaudo(letture.archivio?.collaudo_lettore) : null), [letture])
  const letturaAutomatica = useMemo(() => (letture ? fraseLetturaAutomatica(letture.archivio?.lettura_automatica) : ''), [letture])
  const lettoriVisibili = useMemo(() => (letture ? lettoriDaMostrare(letture) : []), [letture])
  const daConfermare = letture?.archivio?.da_confermare ?? []
  const novita = useMemo(() => (letture ? fraseNovita(letture.novita) : ''), [letture])
  const inAttesa = useMemo(() => (letture ? oggettiInAttesa(letture) : []), [letture])
  const anomalie = useMemo(() => (letture ? anomalieOrdinate(letture.anomalie) : []), [letture])
  const oggettiMostrati = tuttiGliOggetti ? inAttesa : inAttesa.slice(0, OGGETTI_VISIBILI)

  return (
    <section className="iu-fas-letture" aria-label="Registro delle letture del fascicolo" aria-busy={loading}>
      <div className="iu-fas-lettura__section-head">
        <h4><BookOpenCheck size={16}/> Letture e verifiche</h4>
        <span>{riassunto ? <Badge tone={riassunto.tono}>{riassunto.testo}</Badge> : loading ? 'in lettura…' : ''}</span>
      </div>
      {error ? <p className="iu-fas-lettura__state iu-fas-lettura__state--error" role="alert"><AlertTriangle size={15}/> {error}</p> : null}
      {novita ? <p className={`iu-fas-letture__novita${letture?.novita.nuovi.length || letture?.novita.cambiati.length ? ' is-nuove' : ''}`}>{novita}</p> : null}
      {archivio ? (
        <div className="iu-fas-letture__archivio" aria-label="Archivio delle letture">
          <p><Badge tone={archivio.tono}>Archivio</Badge> <span>{archivio.testo}</span></p>
          {letturaAutomatica ? <small>{letturaAutomatica}</small> : null}
          {collaudo ? <small className={`is-${collaudo.tono}`}>{collaudo.testo}</small> : null}
        </div>
      ) : null}
      {daConfermare.length ? (
        <div className="iu-fas-letture__anomalie iu-fas-letture__fatti">
          <h5><AlertTriangle size={14}/> Date lette dai documenti da confermare ({daConfermare.length})</h5>
          <ul>
            {daConfermare.map((fatto) => (
              <li className="is-warning" key={fatto.id}>
                <div className="iu-fas-letture__anomalia-testo">
                  <Badge tone="warning">{etichettaCampo(fatto.campo)}</Badge>
                  <b>{fatto.etichetta}</b>
                  <span>letto «{fatto.valore_letto}»</span>
                  <p>Data ben formata e ancorata al testo, ma nessun'altra fonte del fascicolo la conferma: agenda, scadenziario, PEC o portale non la conoscono.</p>
                  {fatto.contesto ? <small>{fatto.contesto}</small> : null}
                </div>
                {correzioneFatto?.id === fatto.id ? (
                  <form className="iu-fas-letture__correzione" onSubmit={(event) => { event.preventDefault(); void decidiFatto(fatto, 'corretta', correzioneFatto.valore) }}>
                    <label>Data giusta (gg/mm/aaaa)<input type="text" inputMode="numeric" placeholder="gg/mm/aaaa" value={correzioneFatto.valore} onChange={(event) => setCorrezioneFatto({ id: fatto.id, valore: event.target.value })} autoFocus/></label>
                    <button type="submit" disabled={!correzioneFatto.valore.trim()}><Check size={13}/> Salva</button>
                    <button type="button" onClick={() => setCorrezioneFatto(null)}><X size={13}/> Annulla</button>
                  </form>
                ) : (
                  <div className="iu-fas-letture__anomalia-azioni">
                    <button type="button" onClick={() => void decidiFatto(fatto, 'confermata')} title="La data letta è giusta"><Check size={13}/> È giusta</button>
                    <button type="button" onClick={() => setCorrezioneFatto({ id: fatto.id, valore: '' })}><Pencil size={13}/> Correggi</button>
                    <button type="button" onClick={() => void decidiFatto(fatto, 'ignorata')} title="Non è una data rilevante per il fascicolo"><X size={13}/> Ignora</button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {letture ? (
        <ul className="iu-fas-letture__lettori">
          {lettoriVisibili.map((voce) => (
            <li className={voce.errori ? 'is-danger' : voce.da_leggere ? 'is-warning' : voce.letti ? 'is-success' : ''} key={voce.lettore} title={voce.versione ? `Versione del lettore: ${voce.versione}` : undefined}>
              <b>{voce.etichetta}</b>
              <span>{voce.letti} lett{voce.letti === 1 ? 'o' : 'i'}{voce.da_leggere ? ` · ${voce.da_leggere} da leggere` : ''}{voce.errori ? ` · ${voce.errori} non leggibili` : ''}</span>
              {voce.ultima_lettura_it ? <small>ultima lettura {voce.ultima_lettura_it}</small> : null}
            </li>
          ))}
        </ul>
      ) : null}
      {inAttesa.length ? (
        <div className="iu-fas-letture__attesa">
          <ul>
            {oggettiMostrati.map((voce) => <li key={`${voce.oggetto.tipo}-${voce.oggetto.oggetto_id}`}><b>{voce.oggetto.etichetta}</b><span>aspetta: {voce.lettori.join(', ')}</span></li>)}
          </ul>
          {inAttesa.length > OGGETTI_VISIBILI ? <button type="button" className="iu-fas-lettura__link" onClick={() => setTuttiGliOggetti((current) => !current)}>{tuttiGliOggetti ? `Mostra i primi ${OGGETTI_VISIBILI}` : `Mostra tutti (${inAttesa.length})`}</button> : null}
        </div>
      ) : null}
      <div className="iu-fas-letture__azioni">
        <button type="button" disabled={loading} onClick={() => void aggiorna()} title="Legge solo i documenti nuovi o cambiati: quelli già letti non si rileggono"><RefreshCw className={loading ? 'iu-spin' : ''} size={14}/> Leggi i nuovi</button>
        {aggiornamento ? <span>{aggiornamento.messaggio}{aggiornamento.ocr_accodati ? ` · ${aggiornamento.ocr_accodati} in coda OCR` : ''}</span> : null}
      </div>
      {anomalie.length ? (
        <div className="iu-fas-letture__anomalie">
          <h5><AlertTriangle size={14}/> Dati letti da confermare ({anomalie.length})</h5>
          <ul>
            {anomalie.map((anomalia) => (
              <li className={`is-${tonoGravita(anomalia.gravita)}`} key={anomalia.id}>
                <div className="iu-fas-letture__anomalia-testo">
                  <Badge tone={tonoGravita(anomalia.gravita)}>{etichettaCampo(anomalia.campo)}</Badge>
                  <b>«{anomalia.valore_letto}»</b>
                  <span>in {anomalia.oggetto} · {anomalia.lettore_etichetta}</span>
                  <p>{anomalia.motivo}</p>
                  {anomalia.contesto ? <small>{anomalia.contesto}</small> : null}
                </div>
                {correzione?.id === anomalia.id ? (
                  <form className="iu-fas-letture__correzione" onSubmit={(event) => { event.preventDefault(); void risolvi(anomalia, 'corretta', correzione.valore) }}>
                    <label>Data giusta (gg/mm/aaaa)<input type="text" inputMode="numeric" placeholder="gg/mm/aaaa" value={correzione.valore} onChange={(event) => setCorrezione({ id: anomalia.id, valore: event.target.value })} autoFocus/></label>
                    <button type="submit" disabled={!correzione.valore.trim()}><Check size={13}/> Salva</button>
                    <button type="button" onClick={() => setCorrezione(null)}><X size={13}/> Annulla</button>
                  </form>
                ) : (
                  <div className="iu-fas-letture__anomalia-azioni">
                    {anomalia.valore_proposto ? <button type="button" onClick={() => void risolvi(anomalia, 'corretta', anomalia.valore_proposto)} title="Usa il valore proposto dal controllo"><Check size={13}/> Correggi in {anomalia.valore_proposto}</button> : null}
                    <button type="button" onClick={() => void risolvi(anomalia, 'confermata')} title="Il dato letto è giusto così"><Check size={13}/> È giusto</button>
                    <button type="button" onClick={() => setCorrezione({ id: anomalia.id, valore: anomalia.valore_proposto || '' })}><Pencil size={13}/> Correggi</button>
                    <button type="button" onClick={() => void risolvi(anomalia, 'ignorata')} title="Non è una data rilevante per il fascicolo"><X size={13}/> Ignora</button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      ) : letture && !loading ? <p className="iu-fas-lettura__nota">Nessun dato letto da confermare: date e riferimenti hanno superato i controlli.</p> : null}
    </section>
  )
}

export default LettureFascicoloSection
