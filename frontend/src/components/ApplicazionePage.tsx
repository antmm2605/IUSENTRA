import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, Calculator, Info } from 'lucide-react'
import {
  applicazioneDaUrl,
  eseguiApplicazione,
  getApplicazione,
  type Applicazione,
  type CampoApplicazione,
  type EsitoApplicazione,
  type SchedaApplicazione,
} from '../applicazioniData'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import './ApplicazionePage.css'

const CATALOGO = '/strumenti-operativi'

function valoriIniziali(item: Applicazione | null): Record<string, string> {
  const valori: Record<string, string> = {}
  for (const campo of item?.form?.fields ?? []) valori[campo.name] = campo.value
  return valori
}

/** Le voci che la pagina non calcola aprono la loro destinazione (strumento forense o pagina collegata). */
function destinazioneEsterna(item: Applicazione | null): string {
  if (!item || !item.href || item.href.startsWith('/applicazioni')) return ''
  return item.type === 'tool' || item.type === 'collegamento' ? item.href : ''
}

function Campo({ campo, valore, onChange }: { campo: CampoApplicazione; valore: string; onChange: (name: string, value: string) => void }) {
  const id = `app-campo-${campo.name}`
  return (
    <label className="iu-app-field" htmlFor={id}>
      <span>{campo.label}{campo.required ? ' *' : ''}</span>
      {campo.kind === 'select' ? (
        <select id={id} value={valore} required={campo.required} onChange={(event) => { const value = event.currentTarget.value; onChange(campo.name, value) }}>
          {campo.options.map((opzione) => <option key={opzione.value} value={opzione.value}>{opzione.label}</option>)}
        </select>
      ) : (
        <input
          id={id}
          type={campo.kind}
          value={valore}
          step={campo.kind === 'number' ? campo.step || 'any' : undefined}
          required={campo.required}
          onChange={(event) => { const value = event.currentTarget.value; onChange(campo.name, value) }}
        />
      )}
    </label>
  )
}

function Risultato({ esito }: { esito: EsitoApplicazione }) {
  return (
    <div className="iu-app-result" aria-live="polite">
      <p className={esito.ok ? 'iu-app-result__msg' : 'iu-app-result__msg is-error'}>{esito.message}</p>
      {esito.rows.length ? (
        <dl className="iu-app-result__grid">
          {esito.rows.map((riga, indice) => (
            <div key={`${riga.label}-${indice}`} className="iu-app-result__item">
              <dt>{riga.label}</dt>
              <dd>{riga.value}</dd>
              {riga.note ? <small>{riga.note}</small> : null}
            </div>
          ))}
        </dl>
      ) : null}
      {esito.notes.length ? (
        <ul className="iu-app-result__notes">
          {esito.notes.map((nota) => <li key={nota}>{nota}</li>)}
        </ul>
      ) : null}
    </div>
  )
}

export function ApplicazionePage() {
  const appId = useMemo(() => applicazioneDaUrl(window.location.pathname, window.location.search), [])
  const idFascicolo = useMemo(() => (new URLSearchParams(window.location.search).get('id_fascicolo') || '').trim(), [])
  const [scheda, setScheda] = useState<SchedaApplicazione | null>(null)
  const [valori, setValori] = useState<Record<string, string>>({})
  const [esito, setEsito] = useState<EsitoApplicazione | null>(null)
  const [inCorso, setInCorso] = useState(false)
  const abort = useRef<AbortController | null>(null)

  useEffect(() => {
    // Senza una funzione indicata la pagina è il catalogo: vive in Strumenti operativi.
    if (!appId) {
      window.location.replace(CATALOGO)
      return undefined
    }
    const controller = new AbortController()
    getApplicazione(appId, idFascicolo, controller.signal)
      .then((risultato) => {
        const destinazione = destinazioneEsterna(risultato.item)
        if (destinazione) {
          window.location.replace(destinazione)
          return
        }
        setScheda(risultato)
        setValori(valoriIniziali(risultato.item))
      })
      .catch(() => undefined)
    return () => controller.abort()
  }, [appId, idFascicolo])

  useEffect(() => () => abort.current?.abort(), [])

  const cambia = useCallback((name: string, value: string) => {
    setValori((correnti) => ({ ...correnti, [name]: value }))
  }, [])

  const esegui = useCallback(async () => {
    const action = scheda?.item?.form?.action
    if (!action) return
    abort.current?.abort()
    const controller = new AbortController()
    abort.current = controller
    setInCorso(true)
    try {
      setEsito(await eseguiApplicazione(action, valori, controller.signal))
    } catch {
      // Richiesta sostituita da una più recente: nessun esito da mostrare.
    } finally {
      if (abort.current === controller) setInCorso(false)
    }
  }, [scheda, valori])

  if (!appId) return <LoadingState title="Apertura del catalogo" message="Ti portiamo al catalogo delle funzioni dello studio." />
  if (!scheda) return <LoadingState title="Caricamento della funzione" />
  const item = scheda.item
  if (!scheda.ok || !item) {
    return (
      <EmptyState
        title="Funzione non trovata"
        message={scheda.message || 'La funzione richiesta non è nel catalogo dello studio.'}
        action={<ButtonLink href={CATALOGO} tone="neutral">Catalogo delle funzioni</ButtonLink>}
      />
    )
  }

  const azioni = <ButtonLink href={CATALOGO} tone="neutral"><ArrowLeft size={15} aria-hidden="true" /> Catalogo</ButtonLink>
  const sottotitolo = [item.section, item.status].filter(Boolean).join(' · ')

  if (item.type === 'non_disponibile' || !item.form) {
    const motivo = item.unavailable?.reason || 'Questa funzione non ha un calcolo disponibile in pagina.'
    const destinazione = item.unavailable?.href || CATALOGO
    return (
      <Page title={item.title} subtitle={sottotitolo} actions={azioni}>
        <EmptyState
          title="Funzione non disponibile"
          message={motivo}
          action={<ButtonLink href={destinazione} tone="primary">{item.unavailable?.label || 'Catalogo delle funzioni'}</ButtonLink>}
        />
      </Page>
    )
  }

  const form = item.form
  return (
    <Page title={item.title} subtitle={sottotitolo} actions={azioni}>
      {scheda.warnings.map((avviso) => <p key={avviso} className="iu-app-warning" role="status">{avviso}</p>)}
      <div className="iu-app-layout">
        <Panel title="Dati" subtitle={item.description}>
          <form
            className="iu-app-form"
            onSubmit={(event) => {
              event.preventDefault()
              void esegui()
            }}
          >
            {form.fields.map((campo) => <Campo key={campo.name} campo={campo} valore={valori[campo.name] ?? ''} onChange={cambia} />)}
            <div className="iu-app-actions">
              <Button type="submit" tone="primary" disabled={inCorso}>
                <Calculator size={15} aria-hidden="true" /> {inCorso ? 'Elaborazione in corso…' : form.submitLabel}
              </Button>
            </div>
          </form>
          {item.basis ? (
            <p className="iu-app-basis"><Info size={14} aria-hidden="true" /> {item.basis}</p>
          ) : null}
        </Panel>
        <Panel title="Risultato" actions={item.type === 'lookup' ? <Badge tone="info">Verifica</Badge> : <Badge tone="neutral">Calcolo</Badge>}>
          {esito ? <Risultato esito={esito} /> : <p className="iu-app-empty">Compila i dati e premi «{form.submitLabel}».</p>}
        </Panel>
      </div>
    </Page>
  )
}

export default ApplicazionePage
