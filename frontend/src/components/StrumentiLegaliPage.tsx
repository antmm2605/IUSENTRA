import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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

function Risultato({ esito }: { esito: EsitoCalcolo }) {
  if (!esito.ok) {
    return (
      <div className="iu-alert iu-alert--danger" role="alert">
        {esito.errore || 'Calcolo non riuscito.'}
      </div>
    )
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
    setAttivo(voce.id)
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

      <div className="iu-strumenti__layout">
        <nav className="iu-strumenti__elenco" aria-label="Elenco strumenti">
          {visibili.map((voce) => (
            <button
              type="button"
              key={voce.id}
              className={voce.id === attivo ? 'iu-strumento-card iu-strumento-card--attiva' : 'iu-strumento-card'}
              onClick={() => selezionaStrumento(voce)}
              aria-current={voce.id === attivo}
            >
              <span className="iu-strumento-card__categoria">{voce.categoria}</span>
              <span className="iu-strumento-card__titolo">{voce.title}</span>
              <span className="iu-strumento-card__sottotitolo">{voce.subtitle}</span>
            </button>
          ))}
          {!visibili.length ? <p>Nessuno strumento corrisponde alla ricerca.</p> : null}
        </nav>

        <section className="iu-strumenti__pannello">
          {!strumento ? (
            <p>Seleziona uno strumento dall'elenco.</p>
          ) : !strumento.reso_in_react ? (
            <div className="iu-alert iu-alert--info">
              <p>
                <strong>{strumento.title}</strong> non è ancora compilabile in questa pagina.
              </p>
              <p>
                <a className="iu-button" href={strumento.href_vista_classica}>
                  Apri nella vista classica
                </a>
              </p>
            </div>
          ) : (
            <>
              <h2>{strumento.title}</h2>
              <p className="iu-strumenti__sottotitolo">{strumento.subtitle}</p>
              <form
                className="iu-strumenti__form"
                onSubmit={(event) => {
                  event.preventDefault()
                  void calcola()
                }}
              >
                {strumento.campi.map((campo) => (
                  <CampoModulo
                    key={campo.name}
                    campo={campo}
                    valore={valori[campo.name] ?? ''}
                    onChange={cambiaCampo}
                  />
                ))}
                <div className="iu-strumenti__azioni">
                  <button className="iu-button iu-button--primary" type="submit" disabled={inCorso}>
                    {inCorso ? 'Calcolo in corso...' : strumento.azione || 'Calcola'}
                  </button>
                  <a className="iu-button iu-button--ghost" href={strumento.href_vista_classica}>
                    Vista classica
                  </a>
                </div>
              </form>
              {esito ? <Risultato esito={esito} /> : null}
            </>
          )}
        </section>
      </div>
    </main>
  )
}
