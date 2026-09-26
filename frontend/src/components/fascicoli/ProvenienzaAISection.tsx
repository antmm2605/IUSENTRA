import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, ChevronDown, ChevronUp, ShieldCheck } from 'lucide-react'
import { Badge } from '../dashboard'

type Controllo = { campo: string; valore: string; esito: string; motivo: string }

export type UscitaAI = {
  sigillo: string
  azioneEtichetta: string
  modelloEtichetta: string
  versioneRegole: string
  impronta: string
  citazione: string
  creatoIl: string
  oggetto: string
  proposta: string
  attuale: string
  esito: string
  cancello: { stato: 'ammesso' | 'bloccato' | 'non_applicabile'; etichetta: string; controlli: Controllo[] }
  approvazione: 'da_approvare' | 'confermata' | 'corretta' | 'respinta'
  approvazioneEtichetta: string
  integro: boolean
  catena: { registrato: boolean; rivisto: boolean; evento: string }
}

type Riepilogo = { totale: number; daApprovare: number; bloccate: number; nonIntegre: number; modelli: string[] }

const TONO_APPROVAZIONE: Record<UscitaAI['approvazione'], 'success' | 'warning' | 'info' | 'danger'> = {
  da_approvare: 'warning',
  confermata: 'success',
  corretta: 'info',
  respinta: 'danger',
}

function quando(iso: string): string {
  const data = new Date(iso)
  return Number.isNaN(data.getTime()) ? iso : data.toLocaleString('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

// La vista «Provenienza»: ogni uscita di un modello usata nel fascicolo (seconda
// lettura del catalogo, bozze dell'editor) con il modello, l'esito del cancello,
// chi l'ha approvata, il sigillo che ne prova l'integrità e l'evento della
// catena probatoria. Legge /api/v1/ui/fascicoli/<id>/provenienza-ai.
export function ProvenienzaAISection({ fascicoloId, active = true, refreshKey = 0 }: { fascicoloId: string; active?: boolean; refreshKey?: number }) {
  const [voci, setVoci] = useState<UscitaAI[]>([])
  const [riepilogo, setRiepilogo] = useState<Riepilogo | null>(null)
  const [catena, setCatena] = useState<{ attiva: boolean; messaggio: string }>({ attiva: false, messaggio: '' })
  const [errore, setErrore] = useState('')
  const [aperta, setAperta] = useState('')
  const [tutte, setTutte] = useState(false)

  const load = useCallback(async () => {
    if (!active || !fascicoloId) return
    try {
      const response = await fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/provenienza-ai`, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } })
      const payload = await response.json()
      if (!payload.ok) throw new Error(payload.errore || 'Provenienza delle uscite AI non disponibile.')
      setVoci(Array.isArray(payload.voci) ? payload.voci : [])
      setRiepilogo(payload.riepilogo ?? null)
      setCatena(payload.catena ?? { attiva: false, messaggio: '' })
      setErrore('')
    } catch (requestError) {
      setErrore(requestError instanceof Error ? requestError.message : 'Provenienza delle uscite AI non disponibile.')
    }
  }, [active, fascicoloId])

  useEffect(() => { void load() }, [load, refreshKey])

  if (!voci.length && !errore) return null
  const visibili = tutte ? voci : voci.slice(0, 5)
  return (
    <div className="iu-fas-letture__parti iu-fas-letture__provenienza" aria-label="Provenienza delle uscite AI">
      <h5><ShieldCheck size={14}/> Provenienza delle uscite AI ({voci.length})</h5>
      {riepilogo ? (
        <p className="iu-fas-letture__provenienza-riepilogo">
          {riepilogo.daApprovare ? <Badge tone="warning">{riepilogo.daApprovare} da approvare</Badge> : <Badge tone="success">Tutte rivedute</Badge>}
          {riepilogo.bloccate ? <Badge tone="danger">{riepilogo.bloccate} con valori bloccati</Badge> : null}
          {riepilogo.nonIntegre ? <Badge tone="danger">{riepilogo.nonIntegre} sigilli non integri</Badge> : null}
          <small>Modelli: {riepilogo.modelli.join(', ') || '—'}</small>
        </p>
      ) : null}
      {catena.messaggio ? <small className="iu-fas-letture__parte-citazione">{catena.messaggio}</small> : null}
      {errore ? <p className="iu-fas-lettura__state iu-fas-lettura__state--error" role="alert"><AlertTriangle size={15}/> {errore}</p> : null}
      <ul>
        {visibili.map((voce) => {
          const dettaglio = aperta === voce.sigillo
          return (
            <li key={voce.sigillo} className={voce.approvazione === 'da_approvare' || voce.cancello.stato === 'bloccato' || !voce.integro ? 'is-warning' : ''}>
              <div className="iu-fas-letture__parte-testo">
                <span>
                  <Badge tone={TONO_APPROVAZIONE[voce.approvazione] ?? 'warning'}>{voce.approvazioneEtichetta}</Badge>{' '}
                  <Badge tone={voce.cancello.stato === 'bloccato' ? 'danger' : voce.cancello.stato === 'ammesso' ? 'success' : 'neutral'}>{voce.cancello.etichetta}</Badge>
                </span>
                <b>{voce.azioneEtichetta} · {voce.oggetto}</b>
                <small>{voce.modelloEtichetta} · {quando(voce.creatoIl)}{voce.proposta ? ` · proposta: ${voce.proposta}` : ''}{voce.attuale && voce.attuale !== voce.proposta ? ` · ora: ${voce.attuale}` : ''}</small>
                {voce.esito ? <small>{voce.esito}</small> : null}
                <small>
                  Sigillo {voce.sigillo.slice(0, 12)}… {voce.integro ? 'integro' : 'NON integro: il record è stato modificato dopo la registrazione'}
                  {catena.attiva ? (voce.catena.registrato ? ` · nella catena probatoria${voce.catena.rivisto ? ', con la revisione' : ''}` : ' · non ancora nella catena probatoria') : ''}
                </small>
                {dettaglio ? (
                  <>
                    {voce.citazione ? <small className="iu-fas-letture__parte-citazione">«{voce.citazione}»</small> : null}
                    <small>Regole: {voce.versioneRegole || '—'} · impronta del testo letto {voce.impronta || '—'}</small>
                    {voce.cancello.controlli.map((controllo) => (
                      <small key={`${controllo.campo}-${controllo.valore}`} className={controllo.esito === 'bloccato' ? 'is-danger' : ''}>
                        {controllo.campo}: {controllo.valore || '—'} — {controllo.motivo}
                      </small>
                    ))}
                  </>
                ) : null}
              </div>
              <button type="button" className="iu-button iu-button--ghost" onClick={() => setAperta(dettaglio ? '' : voce.sigillo)} aria-expanded={dettaglio}>
                {dettaglio ? <ChevronUp size={14}/> : <ChevronDown size={14}/>} {dettaglio ? 'Chiudi' : 'Controlli'}
              </button>
            </li>
          )
        })}
      </ul>
      {voci.length > 5 ? (
        <button type="button" className="iu-button iu-button--ghost" onClick={() => setTutte(!tutte)}>
          {tutte ? 'Mostra le ultime 5' : `Mostra tutte (${voci.length})`}
        </button>
      ) : null}
    </div>
  )
}

export default ProvenienzaAISection
