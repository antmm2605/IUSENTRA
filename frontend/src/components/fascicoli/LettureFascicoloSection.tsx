import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, BookOpenCheck, Check, Pencil, RefreshCw, X } from 'lucide-react'
import { Badge } from '../dashboard'
import {
  anomalieOrdinate,
  etichettaCampo,
  fraseNovita,
  oggettiInAttesa,
  riassuntoLetture,
  tonoGravita,
  type AnomaliaLettura,
  type EsitoAggiornamentoLetture,
  type LettureFascicolo,
} from './lettureFascicolo'

const OGGETTI_VISIBILI = 6

// Il registro delle letture del fascicolo: che cosa il gestionale ha già letto
// (per lettore e per documento), le novità dall'ultima apertura e i dati
// letti che i controlli giudicano dubbi — le date prima di tutto — che
// l'avvocato conferma o corregge. Legge /api/v1/ui/fascicoli/<id>/letture,
// mai in cache: le novità sono personali.
export function LettureFascicoloSection({ fascicoloId, onAggiornato }: { fascicoloId: string; onAggiornato?: () => void }) {
  const [letture, setLetture] = useState<LettureFascicolo | null>(null)
  const [loading, setLoading] = useState(false)
  const [aggiornamento, setAggiornamento] = useState<EsitoAggiornamentoLetture | null>(null)
  const [error, setError] = useState('')
  const [correzione, setCorrezione] = useState<{ id: string; valore: string } | null>(null)
  const [tuttiGliOggetti, setTuttiGliOggetti] = useState(false)

  const load = useCallback(async () => {
    if (!fascicoloId) return
    setLoading(true)
    setError('')
    try {
      const response = await fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/letture`, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } })
      const payload = await response.json().catch(() => ({})) as { ok?: boolean; letture?: LettureFascicolo; errore?: string }
      if (!response.ok || !payload.ok || !payload.letture) throw new Error(payload.errore || 'Registro delle letture non disponibile.')
      setLetture(payload.letture)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Registro delle letture non disponibile.')
    } finally {
      setLoading(false)
    }
  }, [fascicoloId])

  useEffect(() => { void load() }, [load])

  const aggiorna = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const response = await fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/letture/aggiorna`, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: '{}' })
      const payload = await response.json().catch(() => ({})) as { ok?: boolean; letture?: LettureFascicolo; esito?: EsitoAggiornamentoLetture; errore?: string }
      if (!response.ok || !payload.ok || !payload.letture) throw new Error(payload.errore || 'Aggiornamento delle letture non completato.')
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

  const riassunto = useMemo(() => (letture ? riassuntoLetture(letture) : null), [letture])
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
      {letture ? (
        <ul className="iu-fas-letture__lettori">
          {letture.lettori.map((voce) => (
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
