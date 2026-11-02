import { useBusyActivity } from '../../ui/useBusyActivity'
import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, Check, FileText, Gavel, Receipt, Undo2, X } from 'lucide-react'
import { Badge } from '../dashboard'
import { SourceDocumentModal, type SourceDocument } from '../SourceDocumentModal'

type EstremiSentenza = { numero: string; anno: string; data: string }

export type PropostaDefinizione = EstremiSentenza & {
  id: string
  documentoId: string
  documento: string
  anteprima: string
  citazione: string
  motivo: string
  nonAutomatica: string[]
  importoLabel: string
  capoSpese: string
  compensate: boolean
}

export type CreditoDaSentenza = EstremiSentenza & {
  eventId: string
  tipo: string
  etichetta: string
  importoLabel: string
  stato: 'to_review' | 'confirmed'
  statoLabel: string
  parcella: string
  href: string
  documento: string
  citazione: string
}

export type RegistrazioneAutomatica = EstremiSentenza & {
  id: string
  documentoId: string
  documento: string
  href: string
  citazione: string
  etichetta: string
  importoLabel: string
  eventId: string
  parcella: string
  definito: boolean
  dataDefinizione: string
  normaDefinizione: string
  registrataIl: string
}

export type ProposteSentenza = {
  stato: string
  definizione: PropostaDefinizione[]
  crediti: CreditoDaSentenza[]
  automatiche: RegistrazioneAutomatica[]
  controlloEconomicoAttivo: boolean
}

function dataItaliana(iso: string): string {
  const parti = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '')
  return parti ? `${parti[3]}/${parti[2]}/${parti[1]}` : ''
}

function estremi(voce: EstremiSentenza): string {
  const numero = voce.numero ? `n. ${voce.numero}${voce.anno ? `/${voce.anno}` : ''}` : ''
  const data = dataItaliana(voce.data)
  return [numero, data ? `del ${data}` : ''].filter(Boolean).join(' ')
}

async function inviaJson(url: string, body: Record<string, string>): Promise<Record<string, unknown>> {
  const response = await fetch(url, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  const payload = await response.json().catch(() => ({})) as Record<string, unknown>
  if (!response.ok || !payload.ok) throw new Error(String(payload.errore || payload.message || 'Operazione non completata.'))
  return payload
}

function Citazione({ testo }: { testo: string }) {
  return testo ? <blockquote>«{testo}»</blockquote> : null
}

// Da dove viene ogni voce: la sentenza si apre nel visualizzatore del fascicolo.
function VisualizzaSentenza({ href, documento, contesto, onApri }: { href: string; documento: string; contesto: string; onApri: (fonte: SourceDocument) => void }) {
  if (!href) return null
  return (
    <button type="button" onClick={() => onApri({ href, label: documento || 'Sentenza', context: contesto })} title="Apre la sentenza da cui è stata letta la voce">
      <FileText size={13}/> Visualizza sentenza
    </button>
  )
}

// Le voci che nascono dalla sentenza letta nel fascicolo. Quando sentenza,
// identità del procedimento e credito sono certi il software registra da sé
// credito e definizione («Registrato automaticamente», annullabile); gli altri
// casi restano da confermare o respingere. Legge /api/v1/ui/fascicoli/<id>/letture/sentenza.
export function SentenzaProposteSection({ fascicoloId, active = true, refreshKey = 0, onAggiornato }: { fascicoloId: string; active?: boolean; refreshKey?: number; onAggiornato?: () => void }) {
  const [proposte, setProposte] = useState<ProposteSentenza | null>(null)
  const [errore, setErrore] = useState('')
  const [messaggio, setMessaggio] = useState('')
  const [inCorso, setInCorso] = useState('')
  const [fonte, setFonte] = useState<SourceDocument | null>(null)
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

  const urlDefinizione = `/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/letture/sentenza/definizione`

  const decidiDefinizione = (proposta: PropostaDefinizione, esito: 'conferma' | 'respingi') => esegui(proposta.id, async () => {
    await inviaJson(urlDefinizione, { propostaId: proposta.id, esito })
    return esito === 'conferma' ? 'Fascicolo definito: la sentenza è registrata come fonte nella cronologia.' : 'Proposta di definizione respinta.'
  })

  const annulla = (voce: RegistrazioneAutomatica) => esegui(voce.id, async () => {
    await inviaJson(urlDefinizione, { propostaId: voce.id, esito: 'annulla' })
    return 'Registrazione automatica annullata: stato del fascicolo ripristinato, credito di nuovo da confermare.'
  })

  const decidiCredito = (credito: CreditoDaSentenza, decision: 'confirm' | 'reject') => esegui(credito.eventId, async () => {
    await inviaJson('/api/v1/ui/sentenza-economic/confirm', { eventId: credito.eventId, decision })
    return decision === 'confirm' ? 'Credito confermato: ora puoi generare la parcella.' : 'Credito respinto.'
  })

  const generaParcella = (eventId: string) => esegui(eventId, async () => {
    await inviaJson('/api/v1/ui/sentenza-economic/parcella', { eventId, fascicoloId })
    return 'Parcella generata dal credito confermato: la trovi in Fatturazione, da verificare prima dell’emissione.'
  })

  const definizione = proposte?.definizione ?? []
  const crediti = proposte?.crediti ?? []
  const automatiche = proposte?.automatiche ?? []
  if (!definizione.length && !crediti.length && !automatiche.length && !errore && !messaggio) return null
  const daConfermare = definizione.length + crediti.filter((voce) => voce.stato === 'to_review').length

  return (
    <div className="iu-fas-letture__anomalie iu-fas-letture__fatti" aria-label="Dalla sentenza">
      <h5><Gavel size={14}/> {daConfermare ? `Proposte dalla sentenza da confermare (${daConfermare})` : 'Registrazioni dalla sentenza'}</h5>
      {errore ? <p className="iu-fas-lettura__state iu-fas-lettura__state--error" role="alert"><AlertTriangle size={15}/> {errore}</p> : null}
      {messaggio ? <p className="iu-fas-lettura__nota" role="status">{messaggio}</p> : null}
      <ul>
        {automatiche.map((voce) => (
          <li className="is-success" key={voce.id}>
            <div className="iu-fas-letture__anomalia-testo">
              <Badge tone="success">Registrato automaticamente</Badge>
              <b>dalla sentenza {estremi(voce)}</b>
              <span>in {voce.documento}</span>
              {voce.importoLabel ? <p>{voce.importoLabel} — {voce.etichetta}{voce.parcella ? ` · parcella ${voce.parcella}` : ''}</p> : null}
              {voce.definito ? <p>Fascicolo definito{voce.dataDefinizione ? ` dal ${dataItaliana(voce.dataDefinizione)}` : ''} ({voce.normaDefinizione}): la definizione non attesta il passaggio in giudicato.</p> : null}
              <Citazione testo={voce.citazione}/>
            </div>
            <div className="iu-fas-letture__anomalia-azioni">
              <VisualizzaSentenza href={voce.href} documento={voce.documento} contesto={voce.citazione} onApri={setFonte}/>
              {voce.importoLabel && !voce.parcella ? <button type="button" disabled={Boolean(inCorso)} onClick={() => void generaParcella(voce.eventId)} title="Crea la parcella dal credito registrato"><Receipt size={13}/> Genera parcella</button> : null}
              <button type="button" disabled={Boolean(inCorso)} onClick={() => void annulla(voce)} title="Ripristina lo stato precedente: il credito torna da confermare e la registrazione non si ripete"><Undo2 size={13}/> Annulla</button>
            </div>
          </li>
        ))}
        {definizione.map((proposta) => (
          <li className="is-warning" key={proposta.id}>
            <div className="iu-fas-letture__anomalia-testo">
              <Badge tone="warning">Definizione del fascicolo</Badge>
              <b>Sentenza {estremi(proposta)}</b>
              <span>in {proposta.documento}</span>
              <p>{proposta.motivo}</p>
              {proposta.importoLabel ? <small>Spese liquidate nel dispositivo: {proposta.importoLabel}</small> : proposta.compensate ? <small>Spese di lite compensate nel dispositivo.</small> : null}
              <Citazione testo={proposta.citazione}/>
              {proposta.nonAutomatica.length ? <small>Da confermare perché: {proposta.nonAutomatica.join(' ')}</small> : null}
            </div>
            <div className="iu-fas-letture__anomalia-azioni">
              <VisualizzaSentenza href={proposta.anteprima} documento={proposta.documento} contesto={proposta.citazione} onApri={setFonte}/>
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
              {credito.documento || credito.numero ? <small>Dalla sentenza {estremi(credito)}{credito.documento ? ` in ${credito.documento}` : ''}</small> : null}
              <Citazione testo={credito.citazione}/>
              {credito.parcella ? <small>Parcella generata: {credito.parcella}</small> : null}
            </div>
            <div className="iu-fas-letture__anomalia-azioni">
              <VisualizzaSentenza href={credito.href} documento={credito.documento} contesto={credito.citazione} onApri={setFonte}/>
              {credito.stato === 'to_review' ? (
                <>
                  <button type="button" disabled={Boolean(inCorso)} onClick={() => void decidiCredito(credito, 'confirm')} title="Il credito letto nella sentenza è corretto"><Check size={13}/> Conferma credito</button>
                  <button type="button" disabled={Boolean(inCorso)} onClick={() => void decidiCredito(credito, 'reject')} title="Il credito non spetta o l'importo è errato"><X size={13}/> Respingi</button>
                </>
              ) : !credito.parcella && credito.importoLabel ? (
                <button type="button" disabled={Boolean(inCorso)} onClick={() => void generaParcella(credito.eventId)} title="Crea la parcella dal credito confermato"><Receipt size={13}/> Genera parcella</button>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
      <SourceDocumentModal source={fonte} onClose={() => setFonte(null)}/>
    </div>
  )
}

export default SentenzaProposteSection
