import { useBusyActivity } from '../../ui/useBusyActivity'
import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, Check, FileText, Gavel, Receipt, X } from 'lucide-react'
import { Badge } from '../dashboard'

export type PropostaDefinizione = {
  id: string
  documentoId: string
  documento: string
  anteprima: string
  motivo: string
  numero: string
  anno: string
  data: string
  importoLabel: string
  capoSpese: string
  compensate: boolean
}

export type CreditoDaSentenza = {
  eventId: string
  tipo: string
  etichetta: string
  importoLabel: string
  stato: 'to_review' | 'confirmed'
  statoLabel: string
  parcella: string
}

export type ProposteSentenza = {
  stato: string
  definizione: PropostaDefinizione[]
  crediti: CreditoDaSentenza[]
  controlloEconomicoAttivo: boolean
}

function dataItaliana(iso: string): string {
  const parti = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '')
  return parti ? `${parti[3]}/${parti[2]}/${parti[1]}` : ''
}

function estremi(proposta: PropostaDefinizione): string {
  const numero = proposta.numero ? `n. ${proposta.numero}${proposta.anno ? `/${proposta.anno}` : ''}` : ''
  const data = dataItaliana(proposta.data)
  return [numero, data ? `del ${data}` : ''].filter(Boolean).join(' ')
}

async function inviaJson(url: string, body: Record<string, string>): Promise<Record<string, unknown>> {
  const response = await fetch(url, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  const payload = await response.json().catch(() => ({})) as Record<string, unknown>
  if (!response.ok || !payload.ok) throw new Error(String(payload.errore || payload.message || 'Operazione non completata.'))
  return payload
}

// Le proposte che nascono dalla sentenza letta nel fascicolo: la definizione del
// fascicolo e i crediti liquidati nel capo spese. Nulla cambia da solo:
// l'avvocato conferma o respinge, e solo un credito confermato diventa parcella.
// Legge /api/v1/ui/fascicoli/<id>/letture/sentenza.
export function SentenzaProposteSection({ fascicoloId, active = true, refreshKey = 0, onAggiornato }: { fascicoloId: string; active?: boolean; refreshKey?: number; onAggiornato?: () => void }) {
  const [proposte, setProposte] = useState<ProposteSentenza | null>(null)
  const [errore, setErrore] = useState('')
  const [messaggio, setMessaggio] = useState('')
  const [inCorso, setInCorso] = useState('')
  useBusyActivity(Boolean(inCorso), 'Registrazione della decisione…')

  const load = useCallback(async () => {
    if (!active || !fascicoloId) return
    try {
      const response = await fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/letture/sentenza`, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } })
      const payload = await response.json().catch(() => ({})) as { ok?: boolean; proposte?: ProposteSentenza; errore?: string }
      if (!response.ok || !payload.ok || !payload.proposte) throw new Error(payload.errore || 'Proposte dalla sentenza non disponibili.')
      setProposte(payload.proposte)
      setErrore('')
    } catch (requestError) {
      setErrore(requestError instanceof Error ? requestError.message : 'Proposte dalla sentenza non disponibili.')
    }
  }, [active, fascicoloId])

  useEffect(() => { void load() }, [load, refreshKey])

  const esegui = useCallback(async (chiave: string, azione: () => Promise<string>) => {
    setInCorso(chiave)
    setErrore('')
    try {
      setMessaggio(await azione())
      await load()
      onAggiornato?.()
    } catch (requestError) {
      setErrore(requestError instanceof Error ? requestError.message : 'Operazione non completata.')
    } finally {
      setInCorso('')
    }
  }, [load, onAggiornato])

  const decidiDefinizione = (proposta: PropostaDefinizione, esito: 'conferma' | 'respingi') => esegui(proposta.id, async () => {
    await inviaJson(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/letture/sentenza/definizione`, { propostaId: proposta.id, esito })
    return esito === 'conferma' ? 'Fascicolo definito: la sentenza è registrata come fonte nella cronologia.' : 'Proposta di definizione respinta.'
  })

  const decidiCredito = (credito: CreditoDaSentenza, decision: 'confirm' | 'reject') => esegui(credito.eventId, async () => {
    await inviaJson('/api/v1/ui/sentenza-economic/confirm', { eventId: credito.eventId, decision })
    return decision === 'confirm' ? 'Credito confermato: ora puoi generare la parcella.' : 'Credito respinto.'
  })

  const generaParcella = (credito: CreditoDaSentenza) => esegui(credito.eventId, async () => {
    await inviaJson('/api/v1/ui/sentenza-economic/parcella', { eventId: credito.eventId, fascicoloId })
    return 'Parcella generata dal credito confermato: la trovi in Fatturazione, da verificare prima dell’emissione.'
  })

  const definizione = proposte?.definizione ?? []
  const crediti = proposte?.crediti ?? []
  if (!definizione.length && !crediti.length && !errore && !messaggio) return null

  return (
    <div className="iu-fas-letture__anomalie iu-fas-letture__fatti" aria-label="Proposte dalla sentenza">
      <h5><Gavel size={14}/> Proposte dalla sentenza da confermare ({definizione.length + crediti.filter((voce) => voce.stato === 'to_review').length})</h5>
      {errore ? <p className="iu-fas-lettura__state iu-fas-lettura__state--error" role="alert"><AlertTriangle size={15}/> {errore}</p> : null}
      {messaggio ? <p className="iu-fas-lettura__nota" role="status">{messaggio}</p> : null}
      <ul>
        {definizione.map((proposta) => (
          <li className="is-warning" key={proposta.id}>
            <div className="iu-fas-letture__anomalia-testo">
              <Badge tone="warning">Definizione del fascicolo</Badge>
              <b>Sentenza {estremi(proposta)}</b>
              <span>in {proposta.documento}</span>
              <p>{proposta.motivo}</p>
              {proposta.importoLabel ? <small>Spese liquidate nel dispositivo: {proposta.importoLabel}{proposta.capoSpese ? ` — «${proposta.capoSpese}»` : ''}</small> : proposta.compensate ? <small>Spese di lite compensate nel dispositivo.</small> : null}
            </div>
            <div className="iu-fas-letture__anomalia-azioni">
              <a href={proposta.anteprima} target="_blank" rel="noreferrer"><FileText size={13}/> Apri la sentenza</a>
              <button type="button" disabled={Boolean(inCorso)} onClick={() => void decidiDefinizione(proposta, 'conferma')} title="Il fascicolo passa a «definito» con la sentenza come fonte"><Check size={13}/> Conferma definizione</button>
              <button type="button" disabled={Boolean(inCorso)} onClick={() => void decidiDefinizione(proposta, 'respingi')} title="La sentenza non definisce il fascicolo (impugnata, non definitiva o di altro grado)"><X size={13}/> Respingi</button>
            </div>
          </li>
        ))}
        {crediti.map((credito) => (
          <li className={credito.stato === 'confirmed' ? 'is-success' : 'is-warning'} key={credito.eventId}>
            <div className="iu-fas-letture__anomalia-testo">
              <Badge tone={credito.stato === 'confirmed' ? 'success' : 'warning'}>{credito.statoLabel}</Badge>
              <b>{credito.importoLabel || 'Importo da verificare nel capo spese'}</b>
              <span>{credito.etichetta}</span>
              {credito.parcella ? <small>Parcella generata: {credito.parcella}</small> : null}
            </div>
            <div className="iu-fas-letture__anomalia-azioni">
              {credito.stato === 'to_review' ? (
                <>
                  <button type="button" disabled={Boolean(inCorso)} onClick={() => void decidiCredito(credito, 'confirm')} title="Il credito letto nella sentenza è corretto"><Check size={13}/> Conferma credito</button>
                  <button type="button" disabled={Boolean(inCorso)} onClick={() => void decidiCredito(credito, 'reject')} title="Il credito non spetta o l'importo è errato"><X size={13}/> Respingi</button>
                </>
              ) : !credito.parcella && credito.importoLabel ? (
                <button type="button" disabled={Boolean(inCorso)} onClick={() => void generaParcella(credito)} title="Crea la parcella dal credito confermato"><Receipt size={13}/> Genera parcella</button>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default SentenzaProposteSection
