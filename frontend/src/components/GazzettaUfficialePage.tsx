import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight, ExternalLink, FileText, Landmark, RefreshCw, Search, X } from 'lucide-react'
import { Page } from '../ui/Page'
import { Modal } from '../ui/legalPrimitives'
import { Button, ButtonLink } from '../ui/Button'
import { CampoData } from '../ui/CampoData'
import { useBusyActivity } from '../ui/useBusyActivity'
import { sanitizeDisplayText } from '../displayText'
import { formatDateIt, formatDateTimeIt } from '../formatting'
import {
  GAZZETTA_QUERY_INIZIALE,
  estremiGazzetta,
  gazzettaQueryDaIndirizzo,
  gazzettaQueryString,
  gazzettaVuota,
  loadGazzetta,
  loadGazzettaTesto,
  loadGazzettaSommario,
  refreshGazzetta,
  type GazzettaAtto,
  type GazzettaPayload,
  type GazzettaQuery,
  type GazzettaStatoSerie,
  type GazzettaTesto,
} from '../gazzettaData'
import './GazzettaUfficialePage.css'

const SITO_UFFICIALE = 'https://www.gazzettaufficiale.it/'

function testo(valore: string, ripiego = ''): string {
  return sanitizeDisplayText(valore || ripiego)
}

function dataIt(valore: string): string {
  return formatDateIt(valore, 'data non indicata')
}

/** Solo collegamenti https:// verso il sito della Gazzetta Ufficiale. */
function collegamentoUfficiale(valore: string): string {
  try {
    const url = new URL((valore || '').trim())
    if (url.protocol !== 'https:' || url.username || url.password) return ''
    return ['www.gazzettaufficiale.it', 'gazzettaufficiale.it'].includes(url.hostname) ? url.href : ''
  } catch {
    return ''
  }
}

function StatoSerie({ stato }: { stato: GazzettaStatoSerie }) {
  const sommario = stato.latestIssue ? collegamentoUfficiale(stato.latestIssue.url) : ''
  const classe = !stato.checked ? 'is-pending' : stato.ok ? 'is-ok' : 'is-error'
  return (
    <li className={`iu-gazzetta-stato__voce ${classe}`}>
      <span className="iu-gazzetta-stato__icona" aria-hidden="true">{stato.checked && !stato.ok ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}</span>
      <span className="iu-gazzetta-stato__testo">
        <strong>{testo(stato.label)}</strong>
        {stato.latestIssue ? (
          sommario
            ? <a href={sommario} target="_blank" rel="noopener noreferrer" title="Apri il sommario ufficiale del fascicolo">Ultimo fascicolo n. {stato.latestIssue.number} del {dataIt(stato.latestIssue.date)}</a>
            : <span>Ultimo fascicolo n. {stato.latestIssue.number} del {dataIt(stato.latestIssue.date)}</span>
        ) : <span>Nessun fascicolo in archivio</span>}
        <span className="iu-gazzetta-stato__controllo">{stato.checked ? `Controllata il ${formatDateTimeIt(stato.lastAttemptAt)}` : 'Non ancora controllata'}</span>
        {stato.message ? <small>{testo(stato.message)}</small> : null}
      </span>
    </li>
  )
}

function TestoAtto({ id }: { id: string }) {
  const [testoAtto, setTestoAtto] = useState<GazzettaTesto | null>(null)
  const [errore, setErrore] = useState('')
  useEffect(() => {
    const controllo = new AbortController()
    loadGazzettaTesto(id, controllo.signal)
      .then(setTestoAtto)
      .catch((motivo: unknown) => { if (!controllo.signal.aborted) setErrore(motivo instanceof Error ? motivo.message : 'Testo non disponibile.') })
    return () => controllo.abort()
  }, [id])
  if (errore) return <p className="iu-gazzetta-atto__testo-stato" role="alert"><AlertTriangle size={14} /> {errore}</p>
  if (!testoAtto) return <p className="iu-gazzetta-atto__testo-stato" role="status"><RefreshCw className="iu-spin" size={14} /> Carico il testo dell’atto…</p>
  if (!testoAtto.available) return <p className="iu-gazzetta-atto__testo-stato">{testo(testoAtto.message)}</p>
  const fonte = collegamentoUfficiale(testoAtto.textUrl)
  return (
    <section className="iu-gazzetta-atto__testo" aria-label="Testo completo dell’atto">
      <pre>{testoAtto.text.split(/\r?\n/).map((riga) => riga.trim()).join('\n').replace(/\n{3,}/g, '\n\n').trim()}</pre>
      <p className="iu-gazzetta-atto__testo-fonte">
        Fonte del testo: {testo(testoAtto.source || 'Gazzetta Ufficiale, vista «originario»')}{testoAtto.articles ? `, ${testoAtto.articles} articoli` : ''}, acquisito il {formatDateTimeIt(testoAtto.readAt)}
        {fonte ? <> · <a href={fonte} target="_blank" rel="noopener noreferrer">fonte ufficiale</a></> : null}
      </p>
    </section>
  )
}

type Dettaglio = { vista: 'atto' | 'sommario'; atto: GazzettaAtto }

function SommarioFascicolo({ atto, apriAtto }: { atto: GazzettaAtto; apriAtto: (atto: GazzettaAtto) => void }) {
  const [atti, setAtti] = useState<GazzettaAtto[] | null>(null)
  const [errore, setErrore] = useState('')
  useEffect(() => {
    const controllo = new AbortController()
    loadGazzettaSommario(atto.id, controllo.signal)
      .then((dati) => { if (!controllo.signal.aborted) setAtti(dati.items) })
      .catch((motivo: unknown) => { if (!controllo.signal.aborted) setErrore(motivo instanceof Error ? motivo.message : 'Sommario non disponibile.') })
    return () => controllo.abort()
  }, [atto.id])

  if (errore) return <p role="alert">{errore}</p>
  if (!atti) return <p role="status">Caricamento del sommario…</p>
  if (!atti.length) return <p>Il sommario non contiene atti consultabili.</p>
  return (
    <ul className="iu-gazzetta-lettura__sommario">
      {atti.map((voce, indice) => (
        <li key={voce.id}>
          {voce.section && voce.section !== atti[indice - 1]?.section ? <h4>{testo(voce.section)}</h4> : null}
          <button type="button" onClick={() => apriAtto(voce)}>{testo(voce.title)}</button>
          {voce.description ? <p>{testo(voce.description)}</p> : null}
          {voce.authority || voce.page || voce.editorialCode ? <small>{[voce.authority, voce.page && `pag. ${voce.page}`, voce.editorialCode].filter(Boolean).map((valore) => testo(valore)).join(' · ')}</small> : null}
        </li>
      ))}
    </ul>
  )
}

function RigaAtto({ atto, apri }: { atto: GazzettaAtto; apri: (dettaglio: Dettaglio) => void }) {
  return (
    <li className="iu-gazzetta-atto">
      <span className={`iu-gazzetta-atto__serie is-${atto.series.toLowerCase()}`} title={testo(atto.seriesLabel)}>{testo(atto.seriesShort)}</span>
      <div className="iu-gazzetta-atto__corpo">
        <div className="iu-gazzetta-atto__etichette">
          <span className="iu-gazzetta-atto__tipo">{testo(atto.kindLabel)}</span>
          {atto.authority ? <span className="iu-gazzetta-atto__ente">{testo(atto.authority)}</span> : null}
        </div>
        <h3>{testo(atto.title)}</h3>
        {atto.description ? <p>{testo(atto.description)}</p> : null}
        <p className="iu-gazzetta-atto__estremi">
          {atto.actDate && atto.actDate <= atto.issueDate ? <>Data dell’atto <time dateTime={atto.actDate}>{dataIt(atto.actDate)}</time> · </> : null}
          {atto.actDate && atto.actDate > atto.issueDate ? <>Data nell’intestazione successiva alla pubblicazione · </> : null}
          {estremiGazzetta(atto, dataIt)}
          {atto.page ? ` · pag. ${atto.page}` : ''}
          {atto.section ? ` · ${testo(atto.section)}` : ''}
          {atto.editorialCode ? ` · codice redazionale ${atto.editorialCode}` : ''}
        </p>
      </div>
      <div className="iu-gazzetta-atto__azioni">
        <button type="button" className="iu-gazzetta-atto__leggi" onClick={() => apri({ vista: 'atto', atto })}><FileText size={14} /> Apri l’atto</button>
        <button type="button" className="iu-gazzetta-atto__leggi" onClick={() => apri({ vista: 'sommario', atto })}>Sommario del fascicolo</button>
      </div>
    </li>
  )
}

export function GazzettaUfficialePage() {
  const [query, setQuery] = useState<GazzettaQuery>(() => gazzettaQueryDaIndirizzo(window.location.search))
  const [cerca, setCerca] = useState(query.q)
  const [ente, setEnte] = useState(query.ente)
  const [numero, setNumero] = useState(query.numero)
  const [dati, setDati] = useState<GazzettaPayload>(gazzettaVuota)
  const [caricamento, setCaricamento] = useState(true)
  const [aggiornamento, setAggiornamento] = useState(false)
  const [errore, setErrore] = useState('')
  const [avviso, setAvviso] = useState('')
  const [dettaglio, setDettaglio] = useState<Dettaglio | null>(null)
  useBusyActivity(caricamento, 'Ricerca nella Gazzetta Ufficiale…')
  useBusyActivity(aggiornamento, 'Lettura dei sommari ufficiali…')

  const cambia = (patch: Partial<GazzettaQuery>) => setQuery((attuale) => ({ ...attuale, ...patch, pagina: patch.pagina ?? 1 }))

  // Ricerca, ente e numero partono dopo una breve pausa di digitazione.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery((attuale) => (attuale.q === cerca && attuale.ente === ente && attuale.numero === numero
        ? attuale
        : { ...attuale, q: cerca, ente, numero: numero.replace(/\D/g, ''), pagina: 1 }))
    }, 350)
    return () => window.clearTimeout(timer)
  }, [cerca, ente, numero])

  useEffect(() => {
    const controllo = new AbortController()
    setCaricamento(true)
    setErrore('')
    window.history.replaceState({}, '', `${window.location.pathname}${gazzettaQueryString(query)}`)
    loadGazzetta(query, controllo.signal)
      .then(setDati)
      .catch((motivo: unknown) => { if (!controllo.signal.aborted) setErrore(motivo instanceof Error ? motivo.message : 'Ricerca non disponibile.') })
      .finally(() => { if (!controllo.signal.aborted) setCaricamento(false) })
    return () => controllo.abort()
  }, [query])

  const aggiorna = () => {
    setAggiornamento(true)
    setErrore('')
    setAvviso('')
    refreshGazzetta(query)
      .then((nuovi) => {
        setDati(nuovi)
        setQuery((attuale) => ({ ...attuale, pagina: 1 }))
        if (nuovi.refresh && !nuovi.refresh.done && nuovi.refresh.reason) setAvviso(nuovi.refresh.reason)
      })
      .catch((motivo: unknown) => setErrore(motivo instanceof Error ? motivo.message : 'Aggiornamento non riuscito.'))
      .finally(() => setAggiornamento(false))
  }

  const azzera = () => {
    setCerca('')
    setEnte('')
    setNumero('')
    setQuery(GAZZETTA_QUERY_INIZIALE)
  }

  const pagine = Math.max(1, Math.ceil(dati.total / Math.max(1, dati.pageSize)))
  const serieInErrore = dati.sourceStates.filter((stato) => stato.checked && !stato.ok)
  const filtriAttivi = useMemo(
    () => Boolean(query.q || query.serie || query.tipo || query.rubrica || query.ente || query.dal || query.al || query.numero),
    [query],
  )
  const totaleSerie = dati.facets.series.reduce((somma, voce) => somma + voce.count, 0)

  return (
    <Page
      title="Gazzetta Ufficiale"
      subtitle="Cerca gli atti delle sei serie e consulta il testo originale o il sommario dell’edizione."
      className="iu-gazzetta"
      actions={(
        <>
          <Button tone="neutral" onClick={aggiorna} disabled={aggiornamento} aria-busy={aggiornamento} title="Legge subito i sommari dei fascicoli nuovi">
            <RefreshCw size={15} /> Aggiorna ora
          </Button>
          <ButtonLink tone="neutral" href={SITO_UFFICIALE} target="_blank" rel="noopener noreferrer"><Landmark size={15} /> Sito della Gazzetta Ufficiale</ButtonLink>
        </>
      )}
    >
      {dati.archiveMissing ? <div className="iu-gazzetta__messaggio is-info" role="status">{testo(dati.message)}</div> : null}
      {serieInErrore.length ? (
        <div className="iu-gazzetta__messaggio is-error" role="alert">
          <AlertTriangle size={16} />
          <span>
            {serieInErrore.length === 1 ? 'Aggiornamento in ritardo per una serie.' : `Aggiornamento in ritardo per ${serieInErrore.length} serie.`}
            {' '}{dati.archive.total ? 'Gli atti già acquisiti restano consultabili.' : 'Consulta il sito ufficiale per leggere le pubblicazioni.'}
            {' '}I dettagli sono nello stato delle serie.
          </span>
        </div>
      ) : null}
      {avviso ? <div className="iu-gazzetta__messaggio is-info" role="status">{testo(avviso)}</div> : null}
      {errore ? <div className="iu-gazzetta__messaggio is-error" role="alert">{testo(errore)}</div> : null}

      <section className="iu-gazzetta__filtri" aria-label="Ricerca e filtri">
        <label className="iu-gazzetta__cerca">
          <Search size={16} aria-hidden="true" />
          <span className="sr-only">Cerca nella Gazzetta Ufficiale</span>
          <input value={cerca} onChange={(evento) => setCerca(evento.currentTarget.value)} placeholder="Cerca nel titolo e nel testo del sommario: parole, numero dell’atto, codice redazionale" />
          {cerca ? <button type="button" onClick={() => setCerca('')} title="Cancella ricerca"><X size={14} /></button> : null}
        </label>
        <div className="iu-gazzetta__serie" role="group" aria-label="Serie">
          <button type="button" className={!query.serie ? 'is-active' : ''} aria-pressed={!query.serie} onClick={() => cambia({ serie: '' })}>
            Tutte le serie <span>{totaleSerie}</span>
          </button>
          {dati.facets.series.map((voce) => (
            <button type="button" key={voce.id} className={query.serie === voce.id ? 'is-active' : ''} aria-pressed={query.serie === voce.id} onClick={() => cambia({ serie: query.serie === voce.id ? '' : voce.id })}>
              {testo(voce.label)} <span>{voce.count}</span>
            </button>
          ))}
        </div>
        <div className="iu-gazzetta__campi">
          <label>
            <span>Tipo di atto</span>
            <select value={query.tipo} onChange={(evento) => cambia({ tipo: evento.currentTarget.value })}>
              <option value="">Tutti i tipi</option>
              {dati.facets.kinds.map((voce) => <option key={voce.id} value={voce.id}>{testo(voce.label)} ({voce.count})</option>)}
            </select>
          </label>
          <label>
            <span>Sezione del sommario</span>
            <select value={query.rubrica} onChange={(evento) => cambia({ rubrica: evento.currentTarget.value })}>
              <option value="">Tutte le sezioni</option>
              {dati.facets.sections.map((voce) => <option key={voce.id} value={voce.id}>{testo(voce.label)} ({voce.count})</option>)}
            </select>
          </label>
          <label className="iu-gazzetta__campo-ente">
            <span>Ente emanante</span>
            <input list="iu-gazzetta-enti" value={ente} onChange={(evento) => setEnte(evento.currentTarget.value)} placeholder="Scegli o scrivi l’ente" />
            <datalist id="iu-gazzetta-enti">
              {dati.facets.authorities.map((voce) => <option key={voce.id} value={voce.id}>{`${voce.count} atti`}</option>)}
            </datalist>
          </label>
          <label>
            <span>Pubblicata dal</span>
            <CampoData value={query.dal} max={query.al || undefined} onChange={(valore) => cambia({ dal: valore })} aria-label="Pubblicata dal giorno" />
          </label>
          <label>
            <span>al</span>
            <CampoData value={query.al} min={query.dal || undefined} onChange={(valore) => cambia({ al: valore })} aria-label="Pubblicata fino al giorno" />
          </label>
          <label className="iu-gazzetta__campo-numero">
            <span>N. Gazzetta</span>
            <input inputMode="numeric" value={numero} onChange={(evento) => setNumero(evento.currentTarget.value.replace(/\D/g, '').slice(0, 4))} placeholder="es. 261" />
          </label>
          <label>
            <span>Ordina</span>
            <select value={query.ordine || (query.q ? 'pertinenza' : 'data_atto_recenti')} onChange={(evento) => cambia({ ordine: evento.currentTarget.value })}>
              <option value="data_atto_recenti">Data dell’atto, più recente</option>
              <option value="data_atto_meno_recenti">Data dell’atto, meno recente</option>
              <option value="recenti">Pubblicazione, più recente</option>
              <option value="meno_recenti">Pubblicazione, meno recente</option>
              <option value="pertinenza">Pertinenza della ricerca</option>
            </select>
          </label>
          {filtriAttivi ? <button type="button" className="iu-gazzetta__azzera" onClick={azzera}><X size={14} /> Azzera filtri</button> : null}
        </div>
      </section>

      <div className="iu-gazzetta__corpo">
        <section className="iu-gazzetta__risultati" aria-label="Atti trovati">
          <header className="iu-gazzetta__intestazione-risultati">
            <strong>{dati.total.toLocaleString('it-IT')} {dati.total === 1 ? 'atto' : 'atti'}</strong>
            {dati.archive.total ? <span>Archivio: {dati.archive.total.toLocaleString('it-IT')} atti pubblicati dal {dataIt(dati.archive.from)} al {dataIt(dati.archive.to)}</span> : null}
          </header>
          {caricamento && !dati.items.length ? (
            <div className="iu-gazzetta__caricamento" role="status"><span /><span /><span /></div>
          ) : dati.items.length ? (
            <ul className={`iu-gazzetta__elenco ${caricamento ? 'is-loading' : ''}`}>
              {dati.items.map((atto) => <RigaAtto key={atto.id} atto={atto} apri={setDettaglio} />)}
            </ul>
          ) : (
            <div className="iu-gazzetta__vuoto">
              <FileText size={22} />
              <strong>{dati.archiveMissing ? 'Archivio non ancora disponibile' : 'Nessun atto con questi filtri'}</strong>
              <span>{dati.archiveMissing ? 'Usa «Aggiorna ora» per leggere subito i sommari ufficiali.' : 'Togli un filtro o cambia la ricerca.'}</span>
            </div>
          )}
          {pagine > 1 ? (
            <nav className="iu-gazzetta__pagine" aria-label="Pagine dei risultati">
              <button type="button" disabled={query.pagina <= 1 || caricamento} onClick={() => cambia({ pagina: query.pagina - 1 })}><ChevronLeft size={15} /> Precedente</button>
              <span>Pagina {dati.page} di {pagine}</span>
              <button type="button" disabled={!dati.hasMore || caricamento} onClick={() => cambia({ pagina: query.pagina + 1 })}>Successiva <ChevronRight size={15} /></button>
            </nav>
          ) : null}
        </section>
        <aside className="iu-gazzetta-stato" aria-label="Stato delle serie">
          <h2>Serie della Gazzetta Ufficiale</h2>
          <p>Ogni ora il software legge l’elenco ufficiale degli ultimi 30 giorni e archivia i sommari dei fascicoli nuovi; in sfondo recupera l’archivio dal 01/01/2022 con il testo completo degli atti.</p>
          <ul>{dati.sourceStates.map((stato) => <StatoSerie key={stato.id} stato={stato} />)}</ul>
        </aside>
      </div>
      <Modal open={Boolean(dettaglio)} title={dettaglio?.vista === 'sommario' ? 'Sommario del fascicolo' : 'Testo dell’atto'} onClose={() => setDettaglio(null)}>
        {dettaglio ? (
          <div className="iu-gazzetta-lettura" key={`${dettaglio.vista}-${dettaglio.atto.id}`}>
            <p className="iu-gazzetta-lettura__estremi">{estremiGazzetta(dettaglio.atto, dataIt)}</p>
            {dettaglio.vista === 'sommario' ? (
              <>
                {collegamentoUfficiale(dettaglio.atto.issueUrl) ? <a href={collegamentoUfficiale(dettaglio.atto.issueUrl)} target="_blank" rel="noopener noreferrer">Sommario sul sito ufficiale <ExternalLink size={14} /></a> : null}
                <SommarioFascicolo atto={dettaglio.atto} apriAtto={(atto) => setDettaglio({ vista: 'atto', atto })} />
              </>
            ) : (
              <>
                <h3>{testo(dettaglio.atto.title)}</h3>
                {dettaglio.atto.description ? <p>{testo(dettaglio.atto.description)}</p> : null}
                {dettaglio.atto.editorialCode ? <p className="iu-gazzetta-lettura__estremi">Codice redazionale {dettaglio.atto.editorialCode}</p> : null}
                <div className="iu-gazzetta-lettura__azioni">
                  {collegamentoUfficiale(dettaglio.atto.officialUrl) ? <a href={collegamentoUfficiale(dettaglio.atto.officialUrl)} target="_blank" rel="noopener noreferrer">Atto sul sito ufficiale <ExternalLink size={14} /></a> : null}
                  <button type="button" onClick={() => setDettaglio({ ...dettaglio, vista: 'sommario' })}>Sommario del fascicolo</button>
                </div>
                {dettaglio.atto.hasText ? <TestoAtto id={dettaglio.atto.id} /> : <p>Il testo originale è in acquisizione. Puoi consultare l’atto sul sito ufficiale.</p>}
              </>
            )}
          </div>
        ) : null}
      </Modal>
    </Page>
  )
}

export default GazzettaUfficialePage
