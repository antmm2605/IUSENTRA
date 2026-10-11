import { useBusyActivity } from '../ui/useBusyActivity'
import { useCallback, useEffect, useState } from 'react'
import { CalendarClock, CheckCircle2, Gavel, MapPin, Play, UserRound } from 'lucide-react'
import { inviaPreparazione } from './preparazioneUdienzaApi'
import { FascicoloSearchSelect } from './FascicoloSearchSelect'
import './WizardProPage.css'
import { useOperationalRefresh } from '../hooks/useOperationalRefresh'
import { loadPreparationCommand, preparationCommand, type PreparationProtocol } from '../preparazioneUdienzaCommand'
import { formatDateIt, formatDateTimeIt } from '../formatting'

type Udienza = {
  idAppuntamento: string; idFascicolo: string; titolo: string; dataOra: string; quando: string; luogo: string; cliente: string; giudice: string
  fascicolo: { etichetta?: string; href?: string }; stato: string; passiFatti: number; href: string
}
type Elenco = {
  preservate?: Array<{ id: string; titolo: string; motivo: string; idFascicoloStorico: string; dati: Record<string, unknown> }>
  writeProtocol?: PreparationProtocol
  ok: boolean; message?: string; udienze?: Udienza[]; concluse?: Array<{ id: string; titolo: string; esito: string; data: string; rinvio: string; href: string }>
  riepilogo?: { settimana: number; daPreparare: number; preparate: number }; fascicoli?: Array<{ value: string; label: string }>; puoModificare?: boolean
}

const dataIt = (iso: string) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : '')

const campiStorici: Array<[string, string]> = [
  ['avvocato', 'Professionista registrato'], ['step1_note', 'Briefing'], ['note_preparazione', 'Preparazione'],
  ['verbale_preparazione', 'Bozza del verbale'], ['argomenti_principali', 'Argomenti'], ['richieste_giudice', 'Richieste al giudice'], ['eccezioni_da_sollevare', 'Eccezioni'],
  ['precheck_note', 'Prima dell’udienza'], ['esito', 'Esito storico'], ['esito_note_verbale', 'Verbale'], ['esito_azioni', 'Azioni previste'],
]

function PreparazioneStorica({ p }: { p: NonNullable<Elenco['preservate']>[number] }) {
  const docs = Array.isArray(p.dati.checklist_documenti) ? p.dati.checklist_documenti as Array<Record<string, unknown>> : []
  const terms = Array.isArray(p.dati.termini_assegnati) ? p.dati.termini_assegnati as Array<Record<string, unknown>> : []
  return <details className="iu-pu-storica">
    <summary><strong>{p.titolo}</strong><span>Collegamento da verificare · Solo lettura</span></summary>
    <p className="iu-pu-nota">{p.motivo} Nessun aggiornamento automatico viene applicato da questa preparazione.</p>
    <dl>
      <dt>Ultima modifica registrata</dt><dd>{formatDateTimeIt(String(p.dati.modificato_il || p.dati.creato_il || ''), 'Non registrata')}</dd>
      {campiStorici.filter(([key]) => p.dati[key]).map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{String(p.dati[key])}</dd></div>)}
      {p.dati.esito_rinvio_data ? <><dt>Rinvio storico</dt><dd>{formatDateIt(String(p.dati.esito_rinvio_data))} {String(p.dati.esito_rinvio_ora || '')}</dd></> : null}
    </dl>
    {docs.length ? <><h3>Checklist conservata</h3><ul>{docs.map((d, i) => <li key={i}>{String(d.label || d.nome_file || 'Documento')} · {String(d.stato || '').replaceAll('_', ' ')}{d.note ? ` · ${d.note}` : ''}</li>)}</ul></> : null}
    {terms.length ? <><h3>Termini storici non verificati</h3><ul>{terms.map((t, i) => <li key={i}>{String(t.descrizione || 'Termine')} · {formatDateIt(String(t.data || ''), 'Data non registrata')}</li>)}</ul></> : null}
  </details>
}

function RigaUdienza({ u, fascicoli, puoModificare, protocol }: { u: Udienza; fascicoli: Array<{ value: string; label: string }>; puoModificare: boolean; protocol?: PreparationProtocol }) {
  const [scelta, setScelta] = useState('')
  const [errore, setErrore] = useState('')
  const [occupato, setOccupato] = useState(false)
  useBusyActivity(occupato, 'Avvio della preparazione udienza…')
  const [pending, setPending] = useState(false)
  const [storageError, setStorageError] = useState('')
  const target = `nuovo-${u.idAppuntamento || u.idFascicolo}`
  const scope = protocol?.scope
  const readPending = useCallback(() => {
    if (!scope) return
    try { setPending(Boolean(loadPreparationCommand(sessionStorage, scope, target))); setStorageError('') }
    catch { setStorageError('Impossibile recuperare il comando conservato: nessun nuovo avvio consentito.') }
  }, [scope, target])
  useEffect(readPending, [readPending])
  const imminente = /^(Oggi|Domani)/.test(u.quando)
  const avvia = async (recover = false) => {
    setOccupato(true)
    const url = '/api/v1/ui/preparazione-udienza/avvia'
    const body = { idAppuntamento: u.idAppuntamento, idFascicolo: u.idFascicolo || scelta }
    const esito = protocol?.persistentCommands && scope
      ? await preparationCommand(sessionStorage, inviaPreparazione, { scope, target, sessionId: '' }, 0, url, body, recover)
      : await inviaPreparazione(url, body)
    readPending()
    setOccupato(false)
    if (esito.ok && esito.redirect) window.location.assign(String(esito.redirect))
    else setErrore(String(esito.message || 'Non riesco ad aprire la preparazione.'))
  }
  return (
    <article className={`iu-pu-udienza ${imminente && u.stato === 'Da preparare' ? 'is-urgente' : ''}`}>
      <div className="iu-pu-udienza__quando">
        <strong>{u.quando}</strong>
        <span>{dataIt(u.dataOra)}</span>
      </div>
      <div className="iu-pu-udienza__testo">
        <h2>{u.titolo}</h2>
        <p>
          {u.luogo ? <span><MapPin size={13}/> {u.luogo}</span> : null}
          {u.cliente ? <span><UserRound size={13}/> {u.cliente}</span> : null}
          {u.giudice ? <span><Gavel size={13}/> {u.giudice}</span> : null}
        </p>
        {u.fascicolo?.href ? <a href={u.fascicolo.href}>{u.fascicolo.etichetta}</a> : (
          puoModificare ? (
            <FascicoloSearchSelect options={fascicoli} value={scelta} onChange={setScelta} disabled={occupato}/>
          ) : <em>Udienza non collegata a un fascicolo</em>
        )}
        {errore ? <p className="iu-pu-errore" role="alert">{errore}</p> : null}
        {storageError ? <p className="iu-pu-errore" role="alert">{storageError}</p> : null}
      </div>
      <div className="iu-pu-udienza__azione">
        <span className={`iu-pu-stato ${u.stato === 'Da preparare' ? 'is-da-fare' : u.stato === 'Preparata' || u.stato === 'Esito registrato' ? 'is-fatto' : 'is-corso'}`}>
          {u.stato}
        </span>
        <div className="iu-pu-avanzamento" role="img" aria-label={`${u.passiFatti} passi su 5`}>
          {[1, 2, 3, 4, 5].map((n) => <i key={n} className={n <= u.passiFatti ? 'is-fatto' : ''}/>)}
        </div>
        {pending ? <button type="button" className="iu-pu-btn" disabled={occupato || Boolean(storageError)} onClick={() => void avvia(true)}>Recupera avvio</button>
          : u.href ? <a className="iu-pu-btn is-primario" href={u.href}><Play size={14}/> {u.stato === 'Esito registrato' ? 'Apri' : 'Continua'}</a>
          : puoModificare ? <button type="button" className="iu-pu-btn is-primario" disabled={occupato || Boolean(storageError) || (!u.idFascicolo && !scelta)} onClick={() => void avvia()}><Play size={14}/> Prepara</button> : null}
      </div>
    </article>
  )
}

/** Preparazione udienza: le prossime udienze con lo stato della preparazione, e gli esiti registrati. */
export function WizardProPage() {
  const [dati, setDati] = useState<Elenco | null>(null)
  const [liveError, setLiveError] = useState('')
  const refresh = useCallback(async () => {
    try {
      const response = await fetch('/api/v1/ui/preparazione-udienza', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      const data = await response.json() as Elenco
      if (!response.ok || !data.ok) throw new Error(data.message || 'Elenco non disponibile.')
      setDati(data); setLiveError(''); return true
    } catch { setLiveError('Aggiornamento delle udienze non riuscito. Le scelte correnti sono conservate.'); return false }
  }, [])
  useEffect(() => { void refresh() }, [refresh])
  useOperationalRefresh(['agenda', 'fascicoli', 'clienti'], refresh)
  if (!dati) return <main className="iu-content iu-pu"><p className={`iu-pu-stato-pagina ${liveError ? 'is-errore' : ''}`} role="status">{liveError || 'Caricamento delle udienze…'}</p>{liveError ? <button onClick={() => void refresh()}>Riprova</button> : null}</main>
  if (!dati.ok) return <main className="iu-content iu-pu"><p className="iu-pu-stato-pagina is-errore" role="alert">{dati.message}</p></main>
  const r = dati.riepilogo || { settimana: 0, daPreparare: 0, preparate: 0 }
  return (
    <main className="iu-content iu-pu">
      {liveError ? <p className="iu-pu-errore" role="alert">{liveError} <button onClick={() => void refresh()}>Riprova</button></p> : null}
      <header className="iu-pu-testa">
        <div>
          <span className="iu-pu-kicker"><Gavel size={15}/> Preparazione udienza</span>
          <h1>Prossime udienze</h1>
          <p>Per ogni udienza: quadro della causa con le verifiche di legge, documenti, strategia, controlli prima di uscire ed esito, che crea da solo il rinvio in agenda e i termini assegnati.</p>
        </div>
        <div className="iu-pu-numeri">
          <span><strong>{r.settimana}</strong> nei prossimi 7 giorni</span>
          <span className={r.daPreparare ? 'is-da-fare' : ''}><strong>{r.daPreparare}</strong> da preparare</span>
          <span><strong>{r.preparate}</strong> preparate</span>
        </div>
      </header>
      <section className="iu-pu-elenco" aria-label="Prossime udienze">
        {(dati.udienze || []).length ? (dati.udienze || []).map((u) => (
          <RigaUdienza key={`${u.idAppuntamento || u.idFascicolo}`} u={u} fascicoli={dati.fascicoli || []} puoModificare={Boolean(dati.puoModificare)} protocol={dati.writeProtocol}/>
        )) : (
          <div className="iu-pu-vuoto"><CalendarClock size={26}/><strong>Nessuna udienza nei prossimi 60 giorni.</strong>
            <span>Le udienze inserite in agenda o come prossima udienza del fascicolo compaiono qui.</span><a href="/agenda/nuovo">Inserisci un'udienza</a></div>
        )}
      </section>
      {(dati.concluse || []).length ? (
        <section className="iu-pu-concluse" aria-label="Esiti registrati">
          <h2><CheckCircle2 size={16}/> Esiti registrati</h2>
          <ul>{(dati.concluse || []).map((c) => (
            <li key={c.id}><a href={c.href}><strong>{c.titolo}</strong></a><span>{c.esito}{c.rinvio ? ` al ${dataIt(c.rinvio)}` : ''} · {dataIt(c.data)}</span></li>
          ))}</ul>
        </section>
      ) : null}
      {dati.preservate?.length ? <section className="iu-pu-conservate" aria-label="Preparazioni storiche da verificare">
        <h2>Preparazioni storiche da verificare <small>({dati.preservate.length})</small></h2>
        <p>Apri una preparazione per consultare i dati conservati. I collegamenti con il fascicolo e le fonti devono essere recuperati e verificati prima di riprendere il lavoro.</p>
        {dati.preservate.map(p => <PreparazioneStorica key={p.id} p={p}/>)}
      </section> : null}
    </main>
  )
}

export default WizardProPage
