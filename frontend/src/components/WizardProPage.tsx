import { useEffect, useState } from 'react'
import { CalendarClock, CheckCircle2, Gavel, MapPin, Play, UserRound } from 'lucide-react'
import { inviaPreparazione } from './preparazioneUdienzaApi'
import { FascicoloSearchSelect } from './FascicoloSearchSelect'
import './WizardProPage.css'

type Udienza = {
  idAppuntamento: string; idFascicolo: string; titolo: string; dataOra: string; quando: string; luogo: string; cliente: string; giudice: string
  fascicolo: { etichetta?: string; href?: string }; stato: string; passiFatti: number; href: string
}
type Elenco = {
  ok: boolean; message?: string; udienze?: Udienza[]; concluse?: Array<{ id: string; titolo: string; esito: string; data: string; rinvio: string; href: string }>
  riepilogo?: { settimana: number; daPreparare: number; preparate: number }; fascicoli?: Array<{ value: string; label: string }>; puoModificare?: boolean
}

const dataIt = (iso: string) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : '')

function RigaUdienza({ u, fascicoli, puoModificare }: { u: Udienza; fascicoli: Array<{ value: string; label: string }>; puoModificare: boolean }) {
  const [scelta, setScelta] = useState('')
  const [errore, setErrore] = useState('')
  const [occupato, setOccupato] = useState(false)
  const imminente = /^(Oggi|Domani)/.test(u.quando)
  const avvia = async () => {
    setOccupato(true)
    const esito = await inviaPreparazione('/api/v1/ui/preparazione-udienza/avvia', { idAppuntamento: u.idAppuntamento, idFascicolo: u.idFascicolo || scelta })
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
      </div>
      <div className="iu-pu-udienza__azione">
        <span className={`iu-pu-stato ${u.stato === 'Da preparare' ? 'is-da-fare' : u.stato === 'Preparata' || u.stato === 'Esito registrato' ? 'is-fatto' : 'is-corso'}`}>
          {u.stato}
        </span>
        <div className="iu-pu-avanzamento" role="img" aria-label={`${u.passiFatti} passi su 5`}>
          {[1, 2, 3, 4, 5].map((n) => <i key={n} className={n <= u.passiFatti ? 'is-fatto' : ''}/>)}
        </div>
        {u.href ? <a className="iu-pu-btn is-primario" href={u.href}><Play size={14}/> {u.stato === 'Esito registrato' ? 'Apri' : 'Continua'}</a>
          : puoModificare ? <button type="button" className="iu-pu-btn is-primario" disabled={occupato || (!u.idFascicolo && !scelta)} onClick={() => void avvia()}><Play size={14}/> Prepara</button> : null}
      </div>
    </article>
  )
}

/** Preparazione udienza: le prossime udienze con lo stato della preparazione, e gli esiti registrati. */
export function WizardProPage() {
  const [dati, setDati] = useState<Elenco | null>(null)
  useEffect(() => {
    fetch('/api/v1/ui/preparazione-udienza', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then((r) => r.json()).then((d: Elenco) => setDati(d)).catch(() => setDati({ ok: false, message: 'Elenco non disponibile: riprova tra poco.' }))
  }, [])
  if (!dati) return <main className="iu-content iu-pu"><p className="iu-pu-stato-pagina">Caricamento delle udienze…</p></main>
  if (!dati.ok) return <main className="iu-content iu-pu"><p className="iu-pu-stato-pagina is-errore" role="alert">{dati.message}</p></main>
  const r = dati.riepilogo || { settimana: 0, daPreparare: 0, preparate: 0 }
  return (
    <main className="iu-content iu-pu">
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
          <RigaUdienza key={`${u.idAppuntamento}-${u.idFascicolo}-${u.dataOra}`} u={u} fascicoli={dati.fascicoli || []} puoModificare={Boolean(dati.puoModificare)}/>
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
    </main>
  )
}

export default WizardProPage
