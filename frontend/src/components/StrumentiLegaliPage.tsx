import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Building2, Mail, MapPin, Phone } from 'lucide-react'
import {
  caricaStrumentiLegali,
  eseguiCalcolo,
  elencoTestuale,
  etichettaChiave,
  fontiRisultato,
  righeRisultato,
  tabelleRisultato,
  type CampoStrumento,
  type EsitoCalcolo,
  type StrumentiLegaliPayload,
  type StrumentoForense,
} from '../strumentiLegaliData'
import './StrumentiLegaliPage.css'

function toolDallUrl(): string {
  if (typeof window === 'undefined') return ''
  return new URLSearchParams(window.location.search).get('tool') ?? ''
}

function valoriIniziali(strumento: StrumentoForense | undefined): Record<string, string> {
  if (!strumento) return {}
  const stato: Record<string, string> = {}
  for (const campo of strumento.campi) {
    stato[campo.name] = campo.value ?? ''
  }
  return stato
}

function CampoModulo({
  campo,
  valore,
  onChange,
}: {
  campo: CampoStrumento
  valore: string
  onChange: (name: string, value: string) => void
}) {
  const id = `campo-${campo.name}`
  return (
    <div className="iu-field">
      <label className="iu-field__label" htmlFor={id}>
        {campo.label}
      </label>
      {campo.type === 'select' ? (
        <select
          id={id}
          className="iu-input"
          value={valore}
          onChange={(event) => onChange(campo.name, event.target.value)}
        >
          {(campo.options ?? []).map((opzione) => (
            <option key={opzione.value} value={opzione.value}>
              {opzione.label}
            </option>
          ))}
        </select>
      ) : (
        <input
          id={id}
          className="iu-input"
          type={campo.type === 'date' ? 'date' : campo.type === 'number' ? 'number' : 'text'}
          value={valore}
          min={campo.min}
          max={campo.max}
          step={campo.step}
          onChange={(event) => onChange(campo.name, event.target.value)}
        />
      )}
      {campo.help ? <p className="iu-field__help">{campo.help}</p> : null}
    </div>
  )
}

function testoUfficio(ufficio: Record<string, unknown>, ...chiavi: string[]): string {
  for (const chiave of chiavi) {
    const valore = ufficio[chiave]
    if (typeof valore === 'string' && valore.trim()) return valore.trim()
  }
  return ''
}

function RisultatoUffici({ result }: { result: Record<string, unknown> }) {
  const uffici = Array.isArray(result.offices)
    ? result.offices.filter((voce): voce is Record<string, unknown> => typeof voce === 'object' && voce !== null)
    : []
  const comune = typeof result.comune === 'string' ? result.comune : ''

  return (
    <section className="iu-tool-result iu-tool-result--offices" aria-live="polite">
      <header className="iu-office-results__header">
        <div>
          <h3 className="iu-tool-result__title">Uffici competenti</h3>
          <p>{comune ? `${comune} · ` : ''}{uffici.length} {uffici.length === 1 ? 'ufficio trovato' : 'uffici trovati'}</p>
        </div>
      </header>
      <div className="iu-office-results">
        {uffici.map((ufficio, indice) => {
          const nome = testoUfficio(ufficio, 'name', 'nome') || `Ufficio ${indice + 1}`
          const tipo = testoUfficio(ufficio, 'typeLabel', 'type_label', 'kind')
          const indirizzo = [
            testoUfficio(ufficio, 'address', 'indirizzo'),
            testoUfficio(ufficio, 'cap'),
            testoUfficio(ufficio, 'city', 'citta'),
          ].filter(Boolean).join(' · ')
          const pec = testoUfficio(ufficio, 'pec')
          const email = testoUfficio(ufficio, 'email')
          const telefono = testoUfficio(ufficio, 'phone', 'telefono')
          return (
            <article className="iu-office-result" key={`${nome}-${pec || indice}`}>
              <header>
                <span className="iu-office-result__icon"><Building2 size={17} aria-hidden="true" /></span>
                <div>
                  {tipo ? <span>{tipo}</span> : null}
                  <strong>{nome}</strong>
                </div>
              </header>
              {indirizzo ? <p><MapPin size={15} aria-hidden="true" />{indirizzo}</p> : null}
              <div className="iu-office-result__contacts">
                {pec ? <a href={`mailto:${pec}`}><Mail size={15} aria-hidden="true" /><span><b>PEC</b>{pec}</span></a> : null}
                {email ? <a href={`mailto:${email}`}><Mail size={15} aria-hidden="true" /><span><b>Email</b>{email}</span></a> : null}
                {telefono ? <span><Phone size={15} aria-hidden="true" /><span><b>Telefono</b>{telefono}</span></span> : null}
              </div>
            </article>
          )
        })}
      </div>
      {uffici.length ? (
        <p className="iu-office-results__note">Verifica materia, rito, valore e norme speciali prima di usare il risultato in un atto.</p>
      ) : (
        <div className="iu-alert iu-alert--warning">Nessun ufficio trovato per il Comune indicato.</div>
      )}
    </section>
  )
}

function Risultato({ esito }: { esito: EsitoCalcolo }) {
  if (!esito.ok) {
    return (
      <div className="iu-alert iu-alert--danger" role="alert">
        {esito.errore || 'Calcolo non riuscito.'}
      </div>
    )
  }
  if (esito.result && Array.isArray(esito.result.offices)) {
    return <RisultatoUffici result={esito.result} />
  }
  const righe = righeRisultato(esito.result)
  const note = elencoTestuale(esito.result, 'notes')
  const avvisi = elencoTestuale(esito.result, 'warnings')
  const fonti = fontiRisultato(esito.result)
  const tabelle = tabelleRisultato(esito.result)

  return (
    <section className="iu-tool-result" aria-live="polite">
      <h3 className="iu-tool-result__title">Esito del calcolo</h3>
      <dl className="iu-tool-result__grid">
        {righe.map((riga) => (
          <div className="iu-tool-result__item" key={riga.label}>
            <dt>{riga.label}</dt>
            <dd>{riga.value}</dd>
          </div>
        ))}
      </dl>

      {tabelle.map((tabella) => (
        <div className="iu-table-wrap" key={tabella.chiave}>
          <h4 className="iu-tool-result__subtitle">{tabella.titolo}</h4>
          <table className="iu-table">
            <thead>
              <tr>
                {tabella.colonne.map((colonna) => (
                  <th key={colonna}>{etichettaChiave(colonna)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tabella.righe.map((riga, indice) => (
                <tr key={`${tabella.chiave}-${indice}`}>
                  {tabella.colonne.map((colonna) => (
                    <td key={colonna}>{riga[colonna]}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}

      {avvisi.map((avviso) => (
        <div className="iu-alert iu-alert--warning" key={avviso}>
          {avviso}
        </div>
      ))}
      {note.length ? (
        <ul className="iu-tool-result__notes">
          {note.map((nota) => (
            <li key={nota}>{nota}</li>
          ))}
        </ul>
      ) : null}
      {fonti.length ? (
        <p className="iu-tool-result__sources">
          Fonti:{' '}
          {fonti.map((fonte, indice) => (
            <span key={fonte.url}>
              {indice > 0 ? ' · ' : ''}
              <a href={fonte.url} target="_blank" rel="noreferrer">
                {fonte.title || fonte.url}
              </a>
            </span>
          ))}
        </p>
      ) : null}
    </section>
  )
}

/**
 * Modulo dello strumento aperto, reso in linea sotto la voce selezionata.
 *
 * Sta in un componente proprio perché la pagina lo monta dentro l'elenco: la
 * voce cliccata resta il punto di riferimento visivo e il modulo non finisce
 * in fondo alla pagina, dove l'utente doveva cercarlo.
 */
function PannelloStrumento({
  strumento,
  valori,
  esito,
  inCorso,
  onCampo,
  onCalcola,
}: {
  strumento: StrumentoForense
  valori: Record<string, string>
  esito: EsitoCalcolo | null
  inCorso: boolean
  onCampo: (name: string, value: string) => void
  onCalcola: () => void
}) {
  if (!strumento.reso_in_react) {
    return (
      <section className="iu-strumenti__pannello" id={`pannello-${strumento.id}`}>
        <div className="iu-alert iu-alert--info">
          <p><strong>{strumento.title}</strong> non è momentaneamente disponibile.</p>
        </div>
      </section>
    )
  }

  return (
    <section className="iu-strumenti__pannello" id={`pannello-${strumento.id}`}>
      <form
        className="iu-strumenti__form"
        onSubmit={(event) => {
          event.preventDefault()
          onCalcola()
        }}
      >
        {strumento.campi.map((campo) => (
          <CampoModulo key={campo.name} campo={campo} valore={valori[campo.name] ?? ''} onChange={onCampo} />
        ))}
        <div className="iu-strumenti__azioni">
          <button className="iu-button iu-button--primary" type="submit" disabled={inCorso}>
            {inCorso ? 'Calcolo in corso...' : strumento.azione || 'Calcola'}
          </button>
        </div>
      </form>
      {esito ? <Risultato esito={esito} /> : null}
    </section>
  )
}

export default function StrumentiLegaliPage() {
  const [payload, setPayload] = useState<StrumentiLegaliPayload | null>(null)
  const [attivo, setAttivo] = useState<string>(toolDallUrl())
  const [valori, setValori] = useState<Record<string, string>>({})
  const [esito, setEsito] = useState<EsitoCalcolo | null>(null)
  const [inCorso, setInCorso] = useState(false)
  const [filtro, setFiltro] = useState('')
  const abort = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    caricaStrumentiLegali(toolDallUrl(), controller.signal)
      .then((dati) => {
        setPayload(dati)
        setAttivo((corrente) => corrente || dati.tool_attivo)
      })
      .catch(() => undefined)
    return () => controller.abort()
  }, [])

  const strumento = useMemo(
    () => payload?.strumenti.find((voce) => voce.id === attivo),
    [payload, attivo],
  )

  useEffect(() => {
    setValori(valoriIniziali(strumento))
    setEsito(null)
  }, [strumento])

  const visibili = useMemo(() => {
    const testo = filtro.trim().toLowerCase()
    const elenco = payload?.strumenti ?? []
    if (!testo) return elenco
    return elenco.filter(
      (voce) =>
        voce.title.toLowerCase().includes(testo) ||
        voce.subtitle.toLowerCase().includes(testo) ||
        voce.categoria.toLowerCase().includes(testo),
    )
  }, [payload, filtro])

  const cambiaCampo = useCallback((name: string, value: string) => {
    setValori((corrente) => ({ ...corrente, [name]: value }))
  }, [])

  const selezionaStrumento = useCallback((voce: StrumentoForense) => {
    // Un secondo clic sulla voce già aperta la richiude: l'elenco torna
    // scorrevole senza dover cercare un pulsante di chiusura.
    setAttivo((corrente) => (corrente === voce.id ? '' : voce.id))
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href)
      url.searchParams.set('tool', voce.id)
      window.history.replaceState(window.history.state, '', url.toString())
    }
  }, [])

  const calcola = useCallback(async () => {
    if (!strumento) return
    abort.current?.abort()
    const controller = new AbortController()
    abort.current = controller
    setInCorso(true)
    try {
      setEsito(await eseguiCalcolo(strumento.id, valori, controller.signal))
    } finally {
      setInCorso(false)
    }
  }, [strumento, valori])

  if (!payload) {
    return (
      <main className="iu-content">
        <p aria-live="polite">Caricamento degli strumenti forensi...</p>
      </main>
    )
  }

  return (
    <main className="iu-content iu-strumenti">
      <header className="iu-strumenti__header">
        <h1>Strumenti Forensi</h1>
        <p>
          {payload.totale} strumenti operativi, {payload.totale_in_react} compilabili in questa pagina.
        </p>
        {payload.warning ? (
          <div className="iu-alert iu-alert--warning" role="alert">
            {payload.warning}
          </div>
        ) : null}
        <label className="iu-field__label" htmlFor="filtro-strumenti">
          Cerca uno strumento
        </label>
        <input
          id="filtro-strumenti"
          className="iu-input"
          type="search"
          value={filtro}
          placeholder="Interessi, contributo unificato, prescrizione..."
          onChange={(event) => setFiltro(event.target.value)}
        />
      </header>

      <div className="iu-strumenti__elenco">
        {visibili.map((voce) => {
          const aperto = voce.id === attivo
          return (
            <div className={aperto ? 'iu-strumento iu-strumento--aperto' : 'iu-strumento'} key={voce.id}>
              <button
                type="button"
                className={aperto ? 'iu-strumento-card iu-strumento-card--attiva' : 'iu-strumento-card'}
                onClick={() => selezionaStrumento(voce)}
                aria-expanded={aperto}
                aria-controls={`pannello-${voce.id}`}
              >
                <span className="iu-strumento-card__categoria">{voce.categoria}</span>
                <span className="iu-strumento-card__titolo">{voce.title}</span>
                <span className="iu-strumento-card__sottotitolo">{voce.subtitle}</span>
              </button>
              {aperto && strumento ? (
                <PannelloStrumento
                  strumento={strumento}
                  valori={valori}
                  esito={esito}
                  inCorso={inCorso}
                  onCampo={cambiaCampo}
                  onCalcola={() => void calcola()}
                />
              ) : null}
            </div>
          )
        })}
        {!visibili.length ? <p>Nessuno strumento corrisponde alla ricerca.</p> : null}
      </div>
    </main>
  )
}
