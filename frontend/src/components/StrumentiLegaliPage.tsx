import { useOperationalRefresh } from '../hooks/useOperationalRefresh'
import { NormativeArticleLink } from './NormativeArticleLink'
import { useBusyActivity } from '../ui/useBusyActivity'
import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Building2, CalendarPlus, Mail, MapPin, Phone } from 'lucide-react'
import {
  aggiungiScadenza,
  campoVisibile,
  caricaStrumentiLegali,
  scadenzeProposte,
  eseguiCalcolo,
  elencoTestuale,
  etichettaChiave,
  fontiRisultato,
  righeRisultato,
  tabelleRisultato,
  type CampoStrumento,
  type EsitoCalcolo,
  type EsitoScadenza,
  type StrumentiLegaliPayload,
  type StrumentoForense,
} from '../strumentiLegaliData'
import { getContestoStrumento, type ContestoStrumento } from '../applicazioniData'
import './StrumentiLegaliPage.css'
import { applicaPrecompilatoUtility, catalogoUtility, destinazioneUtility } from '../utilityCatalog'
import { LoadingState } from '../ui/LoadingState'

const OcrDocumentoTool = lazy(() => import('./strumenti/OcrDocumentoTool'))
const DocumentChecksTool = lazy(() => import('./strumenti/DocumentChecksTool'))

function parametroUrl(nome: string): string {
  if (typeof window === 'undefined') return ''
  return (new URLSearchParams(window.location.search).get(nome) ?? '').trim()
}

function categoriaVisibile(valore: string): string {
  return /^(utility|utilita|utilità)$/i.test(valore.trim()) ? 'Utilità' : valore.trim()
}

function toolDallUrl(): string {
  return parametroUrl('tool')
}

/**
 * Valori iniziali del modulo: default dello strumento, poi i campi ricavati
 * dalla pratica (`?id_fascicolo=`) e, solo per lo strumento della voce del
 * catalogo (`?app=`), il preset della voce.
 */
function valoriIniziali(strumento: StrumentoForense | undefined, contesto: ContestoStrumento | null): Record<string, string> {
  if (!strumento) return {}
  const stato: Record<string, string> = {}
  for (const campo of strumento.campi) {
    stato[campo.name] = campo.value ?? ''
  }
  const extra = { ...(contesto?.prefill ?? {}), ...(contesto && contesto.toolId === strumento.id ? contesto.preset : {}) }
  for (const [nome, valore] of Object.entries(extra)) {
    if (nome in stato) stato[nome] = valore
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

function ScadenzeProposte({ esito, tool, dati }: { esito: EsitoCalcolo; tool: string; dati: Record<string, string> }) {
  const proposte = scadenzeProposte(esito.result)
  const [esiti, setEsiti] = useState<Record<number, EsitoScadenza>>({})
  const [inCorso, setInCorso] = useState<number | null>(null)
  if (!proposte.length) return null
  const idFascicolo = parametroUrl('id_fascicolo')
  const aggiungi = async (indice: number) => {
    setInCorso(indice)
    const risposta = await aggiungiScadenza(tool, dati, indice, idFascicolo).catch(() => ({ ok: false, errore: 'Scadenza non creata.' }))
    setInCorso(null)
    setEsiti((correnti) => ({ ...correnti, [indice]: risposta }))
  }
  return (
    <div className="iu-tool-deadlines">
      <h4 className="iu-tool-result__subtitle">Scadenze da riportare{idFascicolo ? ' nel fascicolo' : ''}</h4>
      <ul>
        {proposte.map((voce, indice) => {
          const risposta = esiti[indice]
          return (
            <li key={`${voce.titolo}-${voce.data}`}>
              <div>
                <strong>{voce.titolo}</strong>
                <span>{voce.data.split('-').reverse().join('/')} · {voce.norma}</span>
                {risposta ? (
                  <span role={risposta.ok ? 'status' : 'alert'} className={risposta.ok ? 'is-ok' : 'is-error'}>
                    {risposta.ok ? risposta.messaggio : risposta.errore}
                    {risposta.ok && risposta.href ? <> <a href={risposta.href}>Apri</a></> : null}
                  </span>
                ) : null}
              </div>
              <button className="iu-button iu-button--secondary" type="button" disabled={inCorso !== null || Boolean(risposta?.ok)}
                onClick={() => void aggiungi(indice)}>
                <CalendarPlus size={15} aria-hidden="true" />
                {inCorso === indice ? 'Aggiunta…' : 'Aggiungi allo scadenziario'}
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function Risultato({ esito, tool, dati }: { esito: EsitoCalcolo; tool: string; dati: Record<string, string> }) {
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
  const righe = righeRisultato(esito.result, tool)
  const note = elencoTestuale(esito.result, 'notes')
  const avvisi = elencoTestuale(esito.result, 'warnings')
  const fonti = fontiRisultato(esito.result)
  const tabelle = tabelleRisultato(esito.result, tool)

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

      <ScadenzeProposte key={JSON.stringify(esito.result?.scadenze_proposte ?? '')} esito={esito} tool={tool} dati={dati} />

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
              <NormativeArticleLink url={fonte.url} article={fonte.title}>
                {fonte.title || fonte.url}
              </NormativeArticleLink>
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
  datiCalcolo,
  inCorso,
  onCampo,
  onCalcola,
}: {
  strumento: StrumentoForense
  valori: Record<string, string>
  esito: EsitoCalcolo | null
  datiCalcolo: Record<string, string>
  inCorso: boolean
  onCampo: (name: string, value: string) => void
  onCalcola: () => void
}) {
  if (strumento.componente === 'impronta-documenti' || strumento.componente === 'confronta-testi') {
    return (
      <section className="iu-strumenti__pannello" id={`pannello-${strumento.id}`}>
        <Suspense fallback={<p aria-live="polite">Caricamento dello strumento…</p>}>
          <DocumentChecksTool key={strumento.id} mode={strumento.componente === 'impronta-documenti' ? 'hash' : 'text'} />
        </Suspense>
      </section>
    )
  }
  if (strumento.componente === 'ocr-documento') {
    return (
      <section className="iu-strumenti__pannello" id={`pannello-${strumento.id}`}>
        <Suspense fallback={<p aria-live="polite">Caricamento dello strumento…</p>}>
          <OcrDocumentoTool />
        </Suspense>
      </section>
    )
  }
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
        {strumento.campi.filter((campo) => campoVisibile(campo, strumento.campi, valori)).map((campo) => (
          <CampoModulo key={campo.name} campo={campo} valore={valori[campo.name] ?? ''} onChange={onCampo} />
        ))}
        <div className="iu-strumenti__azioni">
          <button className="iu-button iu-button--primary" type="submit" disabled={inCorso}>
            {inCorso ? 'Calcolo in corso...' : strumento.azione || 'Calcola'}
          </button>
        </div>
      </form>
      {esito ? <Risultato esito={esito} tool={strumento.id} dati={datiCalcolo} /> : null}
    </section>
  )
}

export default function StrumentiLegaliPage() {
  const [payload, setPayload] = useState<StrumentiLegaliPayload | null>(null)
  const [caricamento, setCaricamento] = useState(0)
  const [attivo, setAttivo] = useState<string>(toolDallUrl())
  const [valori, setValori] = useState<Record<string, string>>({})
  const [esito, setEsito] = useState<EsitoCalcolo | null>(null)
  const [datiCalcolo, setDatiCalcolo] = useState<Record<string, string>>({})
  const [inCorso, setInCorso] = useState(false)
  useBusyActivity(inCorso, 'Calcolo in corso…')
  const [filtro, setFiltro] = useState('')
  const [categoria, setCategoria] = useState('')
  const [limiteVoci, setLimiteVoci] = useState(24)
  const [contesto, setContesto] = useState<ContestoStrumento | null>(null)
  const abort = useRef<AbortController | null>(null)
  const toolIniziale = useRef(toolDallUrl())
  const strumentoValori = useRef('')
  const campiModificati = useRef(new Set<string>())

  useEffect(() => {
    const controller = new AbortController()
    caricaStrumentiLegali(toolDallUrl(), controller.signal)
      .then((dati) => {
        setPayload(dati)
        setAttivo((corrente) => corrente || dati.tool_attivo)
      })
      .catch(() => { if (!controller.signal.aborted) setPayload({ strumenti: [], categorie: [], tool_attivo: '', totale: 0, totale_in_react: 0, endpoint_calcolo: '', warning: 'Utility non disponibile. Riprova il caricamento.' }) })
    return () => controller.abort()
  }, [caricamento])

  useOperationalRefresh(['normativa'], async () => {
    const data = await caricaStrumentiLegali(toolDallUrl())
    if (!data.strumenti.length && !data.endpoint_calcolo) throw new Error('Catalogo Utility non confermato.')
    setPayload(data)
  })

  // Voce del catalogo (`?app=`) e pratica (`?id_fascicolo=`): preset e precompilato dall'API applicazioni.
  useEffect(() => {
    const app = parametroUrl('app')
    const idFascicolo = parametroUrl('id_fascicolo')
    if (!app && !idFascicolo) return undefined
    const controller = new AbortController()
    getContestoStrumento(app, idFascicolo, controller.signal)
      .then((dati) => {
        setContesto(dati)
        if (dati.toolId && !toolDallUrl()) setAttivo(dati.toolId)
      })
      .catch(() => undefined)
    return () => controller.abort()
  }, [])

  const strumento = useMemo(
    () => payload?.strumenti.find((voce) => voce.id === attivo),
    [payload, attivo],
  )

  useEffect(() => {
    const cambioStrumento = strumentoValori.current !== (strumento?.id ?? '')
    if (cambioStrumento) campiModificati.current.clear()
    const modificati = new Set(campiModificati.current)
    setValori(corrente => applicaPrecompilatoUtility(valoriIniziali(strumento, contesto), corrente, modificati))
    if (cambioStrumento) setEsito(null)
    strumentoValori.current = strumento?.id ?? ''
  }, [strumento, contesto])

  const catalogo = useMemo(() => catalogoUtility(payload?.strumenti ?? [], payload?.funzioni ?? []), [payload])
  const catalogoOrdinato = useMemo(() => {
    const iniziale = catalogo.find(voce => voce.strumento?.id === toolIniziale.current)
    return iniziale ? [iniziale, ...catalogo.filter(voce => voce !== iniziale)] : catalogo
  }, [catalogo])
  const categorie = useMemo(() => {
    const conteggi = new Map<string, number>()
    for (const voce of catalogo) {
      const nome = categoriaVisibile(voce.categoria)
      conteggi.set(nome, (conteggi.get(nome) ?? 0) + 1)
    }
    return Array.from(conteggi, ([nome, totale]) => ({ nome, totale }))
      .sort((a, b) => a.nome.localeCompare(b.nome, 'it'))
  }, [catalogo])

  const visibili = useMemo(() => {
    const testo = filtro.trim().toLocaleLowerCase('it')
    return catalogoOrdinato.filter((voce) =>
      (!categoria || categoriaVisibile(voce.categoria) === categoria) &&
      (!testo || [voce.title, voce.subtitle, categoriaVisibile(voce.categoria)]
        .some((valore) => valore.toLocaleLowerCase('it').includes(testo))),
    )
  }, [catalogoOrdinato, filtro, categoria])
  const visibiliIds = useMemo(() => new Set(visibili.map((voce) => voce.id)), [visibili])
  const mostrateIds = useMemo(() => new Set(visibili.slice(0, limiteVoci).map((voce) => voce.id)), [visibili, limiteVoci])
  useEffect(() => { setLimiteVoci(24) }, [filtro, categoria])

  const cambiaCampo = useCallback((name: string, value: string) => {
    campiModificati.current.add(name)
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
      setDatiCalcolo(valori)
      setEsito(await eseguiCalcolo(strumento.id, valori, controller.signal))
    } finally {
      setInCorso(false)
    }
  }, [strumento, valori])

  if (!payload) {
    return (
      <main className="iu-content">
        <LoadingState title="Caricamento Utility" message="Recupero dei calcoli e delle funzioni dello studio." />
      </main>
    )
  }

  return (
    <main className="iu-content iu-strumenti">
      <header className="iu-strumenti__header">
        <h1>Utility</h1>
        <p>Calcoli forensi, documenti e funzioni operative: cerca per nome o argomento.</p>
        {payload.warning ? (
          <div className="iu-alert iu-alert--warning" role="alert">
            {payload.warning}
            <button type="button" className="iu-button iu-button--secondary" onClick={() => { setPayload(null); setCaricamento(value => value + 1) }}>Riprova caricamento</button>
          </div>
        ) : null}
        {contesto?.fascicolo ? (
          <div className="iu-alert iu-alert--info" role="status">
            Campi precompilati dalla pratica {contesto.fascicolo.label || contesto.fascicolo.id}: verificali prima di calcolare.
          </div>
        ) : null}
        {(contesto?.warnings ?? []).map((avviso) => (
          <div className="iu-alert iu-alert--warning" role="status" key={avviso}>
            {avviso}
          </div>
        ))}
        <div className="iu-utility-filters">
        <div className="iu-field">
        <label className="iu-field__label" htmlFor="filtro-strumenti">
          Cerca uno strumento
        </label>
        <input
          id="filtro-strumenti"
          className="iu-input"
          type="search"
          value={filtro}
          placeholder="Interessi, documenti, codice fiscale, termini…"
          onChange={(event) => setFiltro(event.target.value)}
        />
        </div>
        <div className="iu-field">
          <label className="iu-field__label" htmlFor="categoria-utility">Argomento</label>
          <select className="iu-input" id="categoria-utility" value={categoria} onChange={event => setCategoria(event.target.value)}>
            <option value="">Tutti gli argomenti ({catalogo.length})</option>
            {categorie.map(voce => <option key={voce.nome} value={voce.nome}>{voce.nome} ({voce.totale})</option>)}
          </select>
        </div>
        </div>
      </header>

      <div className="iu-strumenti__riepilogo">
        <span role="status">{visibili.length} {visibili.length === 1 ? 'strumento trovato' : 'strumenti trovati'}{categoria ? ` · ${categoria}` : ''}</span>
        {filtro || categoria ? <button type="button" onClick={() => { setFiltro(''); setCategoria('') }}>Azzera filtri</button> : null}
      </div>
      <div className="iu-strumenti__elenco">
        {catalogoOrdinato.map((voce) => {
          const aperto = voce.strumento?.id === attivo
          if (!mostrateIds.has(voce.id) && !aperto) return null
          if (voce.funzione) {
            const href = destinazioneUtility(voce.funzione.href, parametroUrl('id_fascicolo'))
            return <div className="iu-strumento" key={voce.id} hidden={!visibiliIds.has(voce.id)}>
              {href ? <a className="iu-strumento-card iu-utility-link" href={href} aria-label={`Apri ${voce.title}`}>
                <span className="iu-strumento-card__categoria">{categoriaVisibile(voce.categoria)}</span>
                <span className="iu-strumento-card__titolo">{voce.title}</span>
                <span className="iu-strumento-card__sottotitolo">{voce.subtitle}</span>
                {voce.funzione.unavailable ? <span>{voce.funzione.unavailable.reason}</span> : null}
              </a> : <p role="alert">{voce.title}: percorso non disponibile.</p>}
            </div>
          }
          return (
            <div className={aperto ? 'iu-strumento iu-strumento--aperto' : 'iu-strumento'} key={voce.id} hidden={!visibiliIds.has(voce.id)}>
              <button
                type="button"
                className={aperto ? 'iu-strumento-card iu-strumento-card--attiva' : 'iu-strumento-card'}
                onClick={() => { if (voce.strumento) selezionaStrumento(voce.strumento) }}
                aria-expanded={aperto}
                aria-controls={`pannello-${voce.strumento?.id}`}
              >
                <span className="iu-strumento-card__categoria">{categoriaVisibile(voce.categoria)}</span>
                <span className="iu-strumento-card__titolo">{voce.title}</span>
                <span className="iu-strumento-card__sottotitolo">{voce.subtitle}</span>
              </button>
              {aperto && strumento ? (
                <PannelloStrumento
                  strumento={strumento}
                  valori={valori}
                  esito={esito}
                  datiCalcolo={datiCalcolo}
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
      {visibili.length > limiteVoci ? <button type="button" className="iu-button iu-button--secondary" onClick={() => setLimiteVoci(value => value + 24)}>Mostra altre funzioni ({Math.min(limiteVoci, visibili.length)} di {visibili.length})</button> : null}
    </main>
  )
}
