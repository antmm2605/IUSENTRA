import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, Send } from 'lucide-react'
import { Badge } from '../dashboard'

type Destinatario = { nome: string; ruolo: string; presso: string; fonte: string }

export type ObbligoNotifica = {
  chiave: string
  documento: string
  etichetta: string
  atti: string
  stato: 'da_notificare' | 'da_verificare' | 'facoltativo' | 'notificato'
  motivo: string
  scadenza: string
  natura: string
  formula: string
  destinatari: Destinatario[]
  fonti: string[]
  dopo: string
  avvertenze: string
}

const STATI: Record<ObbligoNotifica['stato'], { testo: string; tono: 'danger' | 'warning' | 'info' | 'success' }> = {
  da_notificare: { testo: 'Da notificare', tono: 'danger' },
  da_verificare: { testo: 'Da verificare', tono: 'warning' },
  facoltativo: { testo: 'Facoltativa', tono: 'info' },
  notificato: { testo: 'Notificato', tono: 'success' },
}

function dataItaliana(iso: string): string {
  const [anno, mese, giorno] = iso.split('-')
  return anno && mese && giorno ? `${giorno}/${mese}/${anno}` : iso
}

// Il presidio notifiche che legge i documenti: per ogni atto del fascicolo che
// la legge obbliga a notificare, i destinatari (con la norma che dice dove) e
// il termine calcolato dalle date lette. Legge /api/v1/ui/fascicoli/<id>/obblighi-notifica.
export function ObblighiNotificaSection({ fascicoloId, active = true, refreshKey = 0 }: { fascicoloId: string; active?: boolean; refreshKey?: number }) {
  const [obblighi, setObblighi] = useState<ObbligoNotifica[]>([])
  const [errore, setErrore] = useState('')

  const load = useCallback(async () => {
    if (!active || !fascicoloId) return
    try {
      const response = await fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/obblighi-notifica`, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } })
      const payload = await response.json()
      if (!payload.ok) throw new Error(payload.errore || 'Obblighi di notifica non disponibili.')
      setObblighi(Array.isArray(payload.obblighi) ? payload.obblighi : [])
      setErrore('')
    } catch (requestError) {
      setErrore(requestError instanceof Error ? requestError.message : 'Obblighi di notifica non disponibili.')
    }
  }, [active, fascicoloId])

  useEffect(() => { void load() }, [load, refreshKey])

  if (!obblighi.length && !errore) return null
  return (
    <div className="iu-fas-letture__parti iu-fas-letture__obblighi" aria-label="Notifiche richieste dagli atti">
      <h5><Send size={14}/> Notifiche richieste dagli atti ({obblighi.length})</h5>
      {errore ? <p className="iu-fas-lettura__state iu-fas-lettura__state--error" role="alert"><AlertTriangle size={15}/> {errore}</p> : null}
      <ul>
        {obblighi.map((obbligo) => {
          const stato = STATI[obbligo.stato] ?? STATI.da_verificare
          return (
            <li key={obbligo.chiave} className={`is-${stato.tono === 'danger' ? 'warning' : stato.tono}`}>
              <div className="iu-fas-letture__parte-testo">
                <Badge tone={stato.tono}>{stato.testo}</Badge>
                <b>Notificare {obbligo.atti}</b>
                <span>{obbligo.etichetta} · {obbligo.documento}</span>
                {obbligo.scadenza ? <small><strong>Entro il {dataItaliana(obbligo.scadenza)}</strong> — {obbligo.formula}</small> : obbligo.formula ? <small>{obbligo.formula}</small> : null}
                {obbligo.destinatari.length ? (
                  <small>A: {obbligo.destinatari.map((d) => `${d.nome} ${d.presso} (${d.fonte})`).join('; ')}</small>
                ) : null}
                {obbligo.motivo ? <small>{obbligo.motivo}</small> : null}
                {obbligo.dopo ? <small>Dopo: {obbligo.dopo}</small> : null}
                {obbligo.avvertenze ? <small className="iu-fas-letture__parte-citazione">{obbligo.avvertenze}</small> : null}
                <small>Fonti: {obbligo.fonti.join(', ')}</small>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export default ObblighiNotificaSection
