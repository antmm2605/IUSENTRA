import { useOperationalRefresh } from '../hooks/useOperationalRefresh'
import { publishMutationRefresh } from '../operationalRefresh'
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle, Banknote, BellRing, CalendarClock, CheckCircle2, ChevronDown, FilePlus2, Gavel, Inbox, Mail,
  Plus, RefreshCw, Search, ShieldCheck, Wallet, X, ChevronLeft, ChevronRight,
} from 'lucide-react'
import { formatDateIt } from '../formatting'
import { ControlloStudioFiltri, FILTRI_VUOTI, filtraVoce } from './ControlloStudioFiltri'
import './ControlloStudioContext.css'
import './ControlloStudioPage.css'

const ControlloStudioDetail = lazy(() => import('./ControlloStudioDetail'))
export type Azione = { etichetta: string; href: string; endpoint: string; conferma: string; principale: boolean }
export type Voce = {
  id: string; area: string; area_etichetta: string; titolo: string; dettaglio: string; data: string; ora: string
  gravita: 'critica' | 'alta' | 'normale'; etichetta: string; fascicolo: { id?: string; etichetta?: string; href?: string }
  data_riferimento: string; tipo_data_riferimento: string; importo: number; azioni: Azione[]; fascia: string
}
type Area = { area: string; etichetta: string; totale: number; urgenti: number }
type Dati = {
  ok: boolean; message?: string; oggi?: string; voci?: Voce[]; aree?: Area[]; fasce?: Array<{ fascia: string; etichetta: string }>
  incassi?: { da_incassare: number; scaduto: number; parcelle_scadute: number; incassato_mese: number }
  fonti_non_disponibili?: string[]; riepilogo?: string; urgenti?: number; puo_completare_scadenze?: boolean
}

const ICONE: Record<string, typeof Gavel> = { scadenze: CalendarClock, agenda: Gavel, notifiche: ShieldCheck, comunicazioni: Mail, incassi: Banknote }
const FASCE_APERTE = new Set(['scaduto', 'oggi', 'domani', 'settimana'])
const GIORNI = ['domenica', 'lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato']
const MESI = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre']

const euro = (v: number | undefined) => {
  const [intero, decimali] = Math.abs(Number(v || 0)).toFixed(2).split('.')
  return `€ ${intero.replace(/\B(?=(\d{3})+(?!\d))/g, '.')},${decimali}`
}
const dataEstesa = (iso: string | undefined) => {
  if (!iso) return ''
  const [a, m, g] = iso.split('-').map(Number)
  const giorno = new Date(a, m - 1, g)
  const testo = `${GIORNI[giorno.getDay()]} ${g} ${MESI[m - 1]} ${a}`
  return testo[0].toUpperCase() + testo.slice(1)
}
const testoRicerca = (testo: string) => testo.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('it').trim()
const DIMENSIONE_PAGINA = 50

function ElencoVoci({ voci, onFatto, onApri, selezione, onSeleziona }: { voci: Voce[]; onFatto: (voce: Voce, azione: Azione) => void; onApri: (voce: Voce, azione?: Azione) => void; selezione: Set<string>; onSeleziona: (id: string) => void }) {
  const [pagina, setPagina] = useState(0)
  const elenco = useRef<HTMLUListElement>(null)
  const ultima = Math.max(0, Math.ceil(voci.length / DIMENSIONE_PAGINA) - 1)
  const attuale = Math.min(pagina, ultima)
  const da = attuale * DIMENSIONE_PAGINA
  const cambiaPagina = (numero: number) => {
    setPagina(numero)
    elenco.current?.scrollIntoView({ block: 'start', behavior: 'instant' })
  }
  return <>
    <ul ref={elenco}>{voci.slice(da, da + DIMENSIONE_PAGINA).map((v) => <RigaVoce voce={v} key={v.id} onFatto={onFatto} onApri={onApri} selezione={selezione} onSeleziona={onSeleziona}/>)}</ul>
    {ultima > 0 ? <nav className="iu-cs-paginazione" aria-label="Pagine dei risultati">
      <span>{da + 1}–{Math.min(da + DIMENSIONE_PAGINA, voci.length)} di {voci.length}</span>
      <button type="button" disabled={attuale === 0} onClick={() => cambiaPagina(attuale - 1)} aria-label="Pagina precedente"><ChevronLeft size={16}/></button>
      <span>Pagina {attuale + 1} di {ultima + 1}</span>
      <button type="button" disabled={attuale === ultima} onClick={() => cambiaPagina(attuale + 1)} aria-label="Pagina successiva"><ChevronRight size={16}/></button>
    </nav> : null}
  </>
}

async function esegui(endpoint: string, payload: object = {}): Promise<{ ok: boolean; message: string }> {
  const risposta = await fetch(endpoint, {
    method: 'POST', credentials: 'same-origin',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    body: JSON.stringify(payload),
  }).catch(() => null)
  if (!risposta) return { ok: false, message: 'Connessione non riuscita.' }
  const result = await risposta.json().catch(() => ({ ok: false, message: 'Operazione non riuscita.' })) as { ok: boolean; message: string }
  if (!risposta.ok) return { ok: false, message: result.message || 'Operazione non riuscita.' }
  if (result.ok) publishMutationRefresh(endpoint)
  return result
}

function RigaVoce({ voce, onFatto, onApri, selezione, onSeleziona }: { voce: Voce; onFatto: (voce: Voce, azione: Azione) => void; onApri: (voce: Voce, azione?: Azione) => void; selezione: Set<string>; onSeleziona: (id: string) => void }) {
  const Icona = ICONE[voce.area] || Inbox
  const principale = voce.azioni.find((a) => a.principale) || voce.azioni[0]
  const altre = voce.azioni.filter((a) => a !== principale)
  return (
    <li className={`iu-cs-voce is-${voce.gravita}${voce.id.startsWith('pec-') ? ' has-selection' : ''}`}>
      {voce.id.startsWith('pec-') ? <input className="iu-cs-select" type="checkbox" aria-label={`Seleziona ${voce.titolo}`} checked={selezione.has(voce.id)} onChange={() => onSeleziona(voce.id)}/> : null}
      <span className={`iu-cs-voce__icona is-${voce.area}`} aria-hidden="true"><Icona size={16}/></span>
      <div className="iu-cs-voce__testo">
        <div className="iu-cs-voce__riga1">
          <strong>{voce.titolo}</strong>
          {voce.etichetta ? <span className={`iu-cs-badge is-${voce.gravita}`}>{voce.etichetta}</span> : null}
        </div>
        <div className="iu-cs-voce__riga2">
          <span className="iu-cs-voce__area">{voce.area_etichetta}</span>
          {voce.dettaglio ? <span>{voce.dettaglio}</span> : null}
        </div>
        {voce.fascicolo?.href ? <a className="iu-cs-voce__fascicolo" href={voce.fascicolo.href}>{voce.fascicolo.etichetta}</a> : null}
      </div>
      <div className="iu-cs-voce__quando">
        {voce.ora ? <strong>{voce.ora}</strong> : null}
        <span>{voce.data ? formatDateIt(voce.data) : 'Termine da determinare'}</span>
        {voce.data_riferimento ? <small>{voce.tipo_data_riferimento}: {formatDateIt(voce.data_riferimento)}</small> : null}
      </div>
      <div className="iu-cs-voce__azioni">
        {principale ? (principale.endpoint
          ? <button type="button" className="is-primaria" onClick={() => onFatto(voce, principale)}>{principale.etichetta}</button>
          : ['scadenze', 'notifiche', 'agenda'].includes(voce.area) || voce.id.startsWith('pec-')
            ? <button type="button" className="is-primaria" onClick={() => onApri(voce, principale)}>{principale.etichetta}</button>
            : <a className="is-primaria" href={principale.href}>{principale.etichetta}</a>) : null}
        {altre.map((a) => a.endpoint
          ? <button type="button" key={a.etichetta} onClick={() => onFatto(voce, a)}><CheckCircle2 size={14}/> {a.etichetta}</button>
          : voce.area === 'agenda' ? <button type="button" key={a.etichetta} onClick={() => onApri(voce, a)}>{a.etichetta}</button>
          : <a key={a.etichetta} href={a.href}>{a.etichetta}</a>)}
      </div>
    </li>
  )
}

/** Controllo Studio: scadenze, udienze, notifiche, comunicazioni e incassi in un'unica coda ordinata per urgenza. */
export default function ControlloStudioPage() {
  const [dati, setDati] = useState<Dati | null>(null)
  const [selezionata, setSelezionata] = useState<Voce | null>(null)
  const [azioneSelezionata, setAzioneSelezionata] = useState<Azione | undefined>()
  const [filtri, setFiltri] = useState(FILTRI_VUOTI)
  const [selezione, setSelezione] = useState<Set<string>>(new Set())
  const [area, setArea] = useState('')
  const [periodo, setPeriodo] = useState('')
  const [ricerca, setRicerca] = useState('')
  const [resetCoda, setResetCoda] = useState(0)
  const [avviso, setAvviso] = useState('')
  const [erroreAzione, setErroreAzione] = useState(false)
  const [completamento, setCompletamento] = useState(false)
  const [confermaCollettiva, setConfermaCollettiva] = useState<{ ids: string[]; ricerca: string } | null>(null)
  const confermaPulsante = useRef<HTMLButtonElement>(null)
  const [aperte, setAperte] = useState<Set<string>>(new Set(FASCE_APERTE))
  const [caricamento, setCaricamento] = useState(false)
  const [erroreCaricamento, setErroreCaricamento] = useState('')

  const carica = useCallback(async () => {
    setCaricamento(true)
    const risposta = await fetch('/api/v1/ui/controllo-studio', { credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(20000), headers: { Accept: 'application/json' } }).catch(() => null)
    const valori = risposta ? await risposta.json().catch(() => null) as Dati | null : null
    const confermato = Boolean(risposta?.ok && valori?.ok)
    if (confermato) { setDati(valori); setErroreCaricamento('') }
    else {
      const message = valori?.message || 'Il quadro dello studio non si è aggiornato. I dati visualizzati sono conservati: riprova per verificare lo stato corrente.'
      setErroreCaricamento(message)
      setDati(current => current?.ok ? current : { ok: false, message })
    }
    setCaricamento(false)
    return confermato
  }, [])
  useOperationalRefresh(['agenda', 'scadenze', 'comunicazioni', 'fascicoli'], carica)
  useEffect(() => { void carica() }, [carica])
  useEffect(() => { setConfermaCollettiva(null) }, [area, periodo, ricerca, filtri])
  useEffect(() => {
    if (confermaCollettiva) { confermaPulsante.current?.focus(); confermaPulsante.current?.scrollIntoView({ block: 'nearest', behavior: 'instant' }) }
  }, [confermaCollettiva])

  const indice = useMemo(() => (dati?.voci || []).map((voce) => ({ voce, testo: testoRicerca([
    voce.titolo, voce.dettaglio, voce.fascicolo?.etichetta, voce.area_etichetta, formatDateIt(voce.data), voce.ora,
  ].join(' ')) })), [dati])
  const voci = useMemo(() => {
    const parole = testoRicerca(ricerca).split(/\s+/).filter(Boolean)
    return indice.filter(({ voce, testo }) => (!area || voce.area === area)
      && (!periodo || voce.fascia === periodo) && parole.every((p) => testo.includes(p))).map(({ voce }) => voce)
  }, [indice, area, periodo, ricerca])
  const vociFiltrate = useMemo(() => {
    const rows = voci.filter(v => filtraVoce(v, filtri))
    const giorno = (v: Voce) => filtri.dataFonte ? v.data_riferimento || v.data : v.data
    if (filtri.ordine === 'recenti') rows.sort((a, b) => giorno(b).localeCompare(giorno(a)))
    if (filtri.ordine === 'vecchie') rows.sort((a, b) => giorno(a).localeCompare(giorno(b)))
    if (filtri.ordine === 'titolo') rows.sort((a, b) => a.titolo.localeCompare(b.titolo, 'it'))
    return rows
  }, [voci, filtri])
  const pecFiltrate = vociFiltrate.filter(v => v.id.startsWith('pec-'))
  const selezionate = pecFiltrate.filter(v => selezione.has(v.id))
  const apri = (voce: Voce, azione?: Azione) => { setAzioneSelezionata(azione); setSelezionata(voce) }
  const segnaSelezionate = async () => {
    if (!selezionate.length || completamento) return
    setCompletamento(true)
    try {
      const result = await esegui('/api/v1/ui/controllo-studio/pec/lette', { ids: selezionate.map(v => v.id.replace(/^pec-/, '')) })
      setAvviso(result.message); setErroreAzione(!result.ok)
      if (result.ok) { setSelezione(new Set()); await carica() }
    } finally { setCompletamento(false) }
  }
  const gruppi = useMemo(() => (dati?.fasce || []).map((f) => ({ ...f, voci: vociFiltrate.filter((v) => v.fascia === f.fascia) })).filter((g) => g.voci.length), [dati, vociFiltrate])
  const scadute = (dati?.voci || []).filter((v) => v.area === 'scadenze' && v.fascia === 'scaduto').length
  const filtriAttivi = Boolean(area || periodo || ricerca.trim() || JSON.stringify(filtri) !== JSON.stringify(FILTRI_VUOTI))
  const tutteScadute = () => {
    setConfermaCollettiva(null)
    setArea('scadenze'); setPeriodo('scaduto'); setRicerca(''); setAperte(new Set(['scaduto'])); setResetCoda((n) => n + 1)
  }

  const preparaCompletamento = () => {
    const ids = vociFiltrate.filter((v) => v.area === 'scadenze' && v.fascia === 'scaduto').map((v) => v.id.replace(/^scadenza-/, ''))
    if (ids.length) setConfermaCollettiva({ ids, ricerca: ricerca.trim() })
  }
  const completaTutte = async () => {
    if (completamento || caricamento) return
    const ids = confermaCollettiva?.ids || []
    if (!ids.length) return
    setCompletamento(true); setAvviso(''); setErroreAzione(false)
    try {
      const esito = await esegui('/api/v1/ui/controllo-studio/scadenze/completa-scadute', { ids, conferma_adempimento: true })
      setAvviso(esito.message); setErroreAzione(!esito.ok)
      setConfermaCollettiva(null)
      await carica()
    } finally { setCompletamento(false) }
  }

  const fatto = async (voce: Voce, azione: Azione) => {
    if (completamento) return
    if (azione.conferma && !window.confirm(azione.conferma)) return
    const esito = await esegui(azione.endpoint)
    setAvviso(esito.message)
    setErroreAzione(!esito.ok)
    if (esito.ok) { setSelezionata(null); await carica() }
  }

  if (!dati) return <main className="iu-content iu-cs"><p className="iu-cs-stato">Caricamento del quadro dello studio…</p></main>
  if (!dati.ok) return <main className="iu-content iu-cs"><p className="iu-cs-stato is-errore" role="alert">{dati.message}</p><button type="button" className="iu-cs-aggiorna" disabled={caricamento} onClick={() => void carica()}><RefreshCw size={15}/>{caricamento ? 'Aggiorno…' : 'Riprova aggiornamento'}</button></main>
  const incassi = dati.incassi || { da_incassare: 0, scaduto: 0, parcelle_scadute: 0, incassato_mese: 0 }

  return (
    <main className="iu-content iu-cs">
      <header className="iu-cs-testa" data-iusentra-sequence-slot="page-header">
        <div>
          <span className="iu-cs-testa__data">{dataEstesa(dati.oggi)}</span>
          <h1>Controllo Studio</h1>
          <p className={dati.urgenti ? 'is-urgente' : ''}>{dati.urgenti ? <AlertTriangle size={16}/> : <CheckCircle2 size={16}/>} {dati.riepilogo}</p>
        </div>
        <button type="button" className="iu-cs-aggiorna" onClick={() => void carica()} disabled={caricamento || completamento}><RefreshCw size={15}/> {caricamento ? 'Aggiorno…' : 'Aggiorna'}</button>
      </header>

      {erroreCaricamento ? <p className="iu-cs-stato is-errore" role="alert">{erroreCaricamento}</p> : null}

      {dati.fonti_non_disponibili?.length ? <p className="iu-cs-stato is-avviso" role="status">Non disponibili in questo momento: {dati.fonti_non_disponibili.join(', ')}.</p> : null}
      {avviso ? <p className={`iu-cs-stato ${erroreAzione ? 'is-errore' : 'is-ok'}`} role={erroreAzione ? 'alert' : 'status'}>{avviso}</p> : null}

      <nav className="iu-cs-aree" aria-label="Filtra per area" data-iusentra-sequence-slot="filters">
        <button type="button" className={!area ? 'is-attiva' : ''} aria-pressed={!area} onClick={() => { setArea(''); setFiltri(FILTRI_VUOTI); setSelezione(new Set()) }}>
          <span>Tutto</span><strong>{dati.voci?.length || 0}</strong><span className="iu-cs-card-filter">Visualizza tutte</span><small>Tutte le attività</small>
        </button>
        {(dati.aree || []).map((a) => {
          const Icona = ICONE[a.area] || Inbox
          return (
            <button type="button" key={a.area} className={area === a.area ? 'is-attiva' : ''} onClick={() => { setArea(area === a.area ? '' : a.area); setFiltri(FILTRI_VUOTI); setSelezione(new Set()); setAperte(new Set((dati.fasce || []).map((f) => f.fascia))) }} aria-pressed={area === a.area}>
              <span><Icona size={15}/> {a.etichetta}</span>
              <strong>{a.totale}</strong><span className="iu-cs-card-filter">Filtra quest’area</span>
              {a.urgenti ? <small>{a.urgenti} urgenti</small> : <small>{a.totale && a.area === 'comunicazioni' ? 'da leggere' : a.area === 'notifiche' && a.totale ? 'da presidiare' : 'in ordine'}</small>}
            </button>
          )
        })}
      </nav>

      <section className="iu-cs-filtri" aria-label="Ricerca e periodo" data-iusentra-sequence-slot="filters">
        <div className="iu-cs-ricerca">
          <label htmlFor="controllo-ricerca">Cerca scadenze e attività</label>
          <div><Search size={18} aria-hidden="true"/>
            <input id="controllo-ricerca" className="selection:bg-blue-100" type="search" value={ricerca} placeholder="Titolo, fascicolo, numero di ruolo o data…"
              onChange={(e) => { setRicerca(e.target.value); setAperte(new Set((dati.fasce || []).map((f) => f.fascia))) }}/>
            {ricerca ? <button type="button" aria-label="Cancella ricerca" onClick={() => setRicerca('')}><X size={16}/></button> : null}
          </div>
        </div>
        <div className="iu-cs-periodo"><label htmlFor="controllo-periodo">Periodo</label>
          <select id="controllo-periodo" value={periodo} onChange={(e) => { setPeriodo(e.target.value); setAperte(new Set((dati.fasce || []).map((f) => f.fascia))) }}>
            <option value="">Tutti i periodi</option>
            {(dati.fasce || []).map((f) => <option key={f.fascia} value={f.fascia}>{f.etichetta}</option>)}
          </select>
        </div>
        <button type="button" className={`iu-cs-scadute ${area === 'scadenze' && periodo === 'scaduto' ? 'is-attiva' : ''}`}
          aria-pressed={area === 'scadenze' && periodo === 'scaduto'} onClick={tutteScadute}>
          <CalendarClock size={18}/> Tutte le scadute <strong>{scadute}</strong>
        </button>
      </section>
      <details className="iu-cs-advanced"><summary>Ricerca avanzata e filtri{Object.keys(FILTRI_VUOTI).some(key => filtri[key as keyof typeof filtri] !== FILTRI_VUOTI[key as keyof typeof filtri]) ? ' · attivi' : ''}</summary>
      <ControlloStudioFiltri voci={(dati.voci || []).filter(v => !area || v.area === area)} filtri={filtri} onChange={f => { setFiltri(f); setSelezione(new Set()); setAperte(new Set((dati.fasce || []).map(s => s.fascia))) }}/>
      </details>
      {area === 'notifiche' ? <p className="iu-cs-nota">La data della fonte o di creazione resta visibile. Il termine di notifica compare soltanto se determinato: la data del documento non diventa una scadenza.</p> : null}
      {pecFiltrate.length && (area === 'comunicazioni' || periodo === 'comunicazioni' || selezione.size > 0) ? <section className="iu-cs-selezione" aria-label="Selezione delle comunicazioni">
        <label><input type="checkbox" checked={Boolean(pecFiltrate.length && selezionate.length === pecFiltrate.length)} disabled={completamento}
          onChange={e => setSelezione(e.target.checked ? new Set(pecFiltrate.map(v => v.id)) : new Set())}/> Seleziona tutte le comunicazioni filtrate ({pecFiltrate.length}), anche nelle altre pagine</label>
        <span>{selezionate.length} selezionate</span>
        <button type="button" className="iu-cs-aggiorna" disabled={!selezionate.length || completamento} onClick={() => void segnaSelezionate()}>{completamento ? 'Salvataggio…' : 'Segna selezionate come lette'}</button>
      </section> : null}
      <div className="iu-cs-contesto" data-iusentra-sequence-slot="context-filters">
        <span role="status">{vociFiltrate.length} {vociFiltrate.length === 1 ? 'risultato' : 'risultati'}{area === 'scadenze' && periodo === 'scaduto' ? ' nelle scadenze scadute' : ''}{ricerca.trim() ? ` per «${ricerca.trim()}»` : ''}</span>
        {area === 'scadenze' && periodo === 'scaduto' && dati.puo_completare_scadenze && vociFiltrate.length > 0 ? <button type="button" className="iu-cs-completa-tutte" disabled={completamento || caricamento}
          onClick={preparaCompletamento}><CheckCircle2 size={17}/>{completamento ? 'Salvataggio delle scadenze…' : `Segna tutte come fatte (${vociFiltrate.length})`}</button> : null}
        {filtriAttivi ? <button type="button" onClick={() => { setArea(''); setPeriodo(''); setRicerca(''); setFiltri(FILTRI_VUOTI); setSelezione(new Set()); setAperte(new Set(FASCE_APERTE)) }}>Azzera filtri</button>
          : <span>Ricerca immediata su tutte le voci. Date: giorno/mese/anno.</span>}
      </div>

      {confermaCollettiva ? <section className="iu-cs-conferma" role="region" aria-label="Conferma completamento collettivo" data-iusentra-sequence-slot="context-filters">
        <h2>Segnare come fatte {confermaCollettiva.ids.length} scadenze?</h2>
        <p>{confermaCollettiva.ricerca ? `Sono comprese tutte le scadenze della ricerca «${confermaCollettiva.ricerca}», anche nelle altre pagine.` : 'Sono comprese tutte le scadenze scadute nei risultati, anche nelle altre pagine.'} Conferma soltanto se gli adempimenti sono stati eseguiti. I termini resteranno consultabili nello Scadenziario tra le completate.</p>
        <div><button ref={confermaPulsante} type="button" className="iu-cs-completa-tutte" disabled={completamento} onClick={() => void completaTutte()}>{completamento ? 'Salvataggio in corso…' : 'Confermo: sono tutte adempiute'}</button>
          <button type="button" disabled={completamento} onClick={() => setConfermaCollettiva(null)}>Annulla</button></div>
      </section> : null}

      <div className="iu-cs-corpo">
        <section className="iu-cs-coda" aria-label="Cose da lavorare">
          {gruppi.length ? gruppi.map((g) => {
            const aperta = aperte.has(g.fascia)
            return (
              <section key={g.fascia} className={`iu-cs-fascia is-${g.fascia}`}>
                <button type="button" className="iu-cs-fascia__testa" aria-expanded={aperta}
                  onClick={() => setAperte((s) => { const n = new Set(s); if (n.has(g.fascia)) n.delete(g.fascia); else n.add(g.fascia); return n })}>
                  <h2>{g.etichetta}</h2><span>{g.voci.length}</span><ChevronDown size={16}/>
                </button>
                {aperta ? <ElencoVoci key={`${g.fascia}:${area}:${periodo}:${ricerca}:${JSON.stringify(filtri)}:${resetCoda}`} voci={g.voci} onFatto={(voce, azione) => void fatto(voce, azione)} onApri={apri} selezione={selezione} onSeleziona={id => setSelezione(current => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next })}/> : null}
              </section>
            )
          }) : (
            <div className="iu-cs-vuoto">{filtriAttivi ? <Search size={28}/> : <CheckCircle2 size={28}/>}<strong>{filtriAttivi ? 'Nessun risultato con questi filtri.' : 'Niente da lavorare nei prossimi 30 giorni.'}</strong><span>{filtriAttivi ? 'Prova un nome, un numero di ruolo o una data, oppure azzera i filtri.' : 'Le nuove scadenze, udienze, PEC e parcelle compariranno qui appena registrate.'}</span></div>
          )}
        </section>

        <aside className="iu-cs-lato">
          <section className="iu-cs-scheda" aria-label="Incassi">
            <h2><Wallet size={16}/> Incassi</h2>
            <dl>
              <div><dt>Da incassare</dt><dd>{euro(incassi.da_incassare)}</dd></div>
              <div className={incassi.scaduto ? 'is-critico' : ''}><dt>Scaduto{incassi.parcelle_scadute ? ` (${incassi.parcelle_scadute})` : ''}</dt><dd>{euro(incassi.scaduto)}</dd></div>
              <div><dt>Incassato questo mese</dt><dd>{euro(incassi.incassato_mese)}</dd></div>
            </dl>
            <a href="/incassi-pagamenti">Apri incassi e pagamenti</a>
          </section>
          <section className="iu-cs-scheda" aria-label="Azioni rapide">
            <h2><Plus size={16}/> Nuovo</h2>
            <div className="iu-cs-rapide">
              <a href="/scadenziario/nuova"><CalendarClock size={15}/> Scadenza</a>
              <a href="/agenda/nuovo"><Gavel size={15}/> Udienza o appuntamento</a>
              <a href="/notifiche-legali?section=operazioni"><BellRing size={15}/> Notifica in proprio</a>
              <a href="/fatturazione/nuova"><FilePlus2 size={15}/> Parcella</a>
              <a href="/incassi-pagamenti#registra-incasso"><Banknote size={15}/> Incasso</a>
            </div>
          </section>
        </aside>
      </div>
      {selezionata ? <Suspense fallback={<p role="status">Apertura del dettaglio…</p>}><ControlloStudioDetail
        key={`${selezionata.id}:${azioneSelezionata?.href}`} voce={selezionata} azione={azioneSelezionata} onClose={() => setSelezionata(null)} onUpdated={() => void carica()}
        onFatto={(voce, azione) => void fatto(voce, azione)}/></Suspense> : null}
    </main>
  )
}
