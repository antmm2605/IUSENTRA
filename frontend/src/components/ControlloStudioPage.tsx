import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle, Banknote, BellRing, CalendarClock, CheckCircle2, ChevronDown, FilePlus2, Gavel, Inbox, Mail,
  Plus, RefreshCw, ShieldCheck, Wallet,
} from 'lucide-react'
import './ControlloStudioPage.css'

type Azione = { etichetta: string; href: string; endpoint: string; conferma: string; principale: boolean }
type Voce = {
  id: string; area: string; area_etichetta: string; titolo: string; dettaglio: string; data: string; ora: string
  gravita: 'critica' | 'alta' | 'normale'; etichetta: string; fascicolo: { id?: string; etichetta?: string; href?: string }
  importo: number; azioni: Azione[]; fascia: string
}
type Area = { area: string; etichetta: string; totale: number; urgenti: number }
type Dati = {
  ok: boolean; message?: string; oggi?: string; voci?: Voce[]; aree?: Area[]; fasce?: Array<{ fascia: string; etichetta: string }>
  incassi?: { da_incassare: number; scaduto: number; parcelle_scadute: number; incassato_mese: number }
  fonti_non_disponibili?: string[]; riepilogo?: string; urgenti?: number
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
const dataBreve = (iso: string) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}` : '')

async function esegui(endpoint: string): Promise<{ ok: boolean; message: string }> {
  const risposta = await fetch(endpoint, {
    method: 'POST', credentials: 'same-origin',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    body: '{}',
  }).catch(() => null)
  if (!risposta) return { ok: false, message: 'Connessione non riuscita.' }
  return await risposta.json().catch(() => ({ ok: false, message: 'Operazione non riuscita.' })) as { ok: boolean; message: string }
}

function RigaVoce({ voce, onFatto }: { voce: Voce; onFatto: (voce: Voce, azione: Azione) => void }) {
  const Icona = ICONE[voce.area] || Inbox
  const principale = voce.azioni.find((a) => a.principale) || voce.azioni[0]
  const altre = voce.azioni.filter((a) => a !== principale)
  return (
    <li className={`iu-cs-voce is-${voce.gravita}`}>
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
        {voce.fascia !== 'oggi' ? <span>{dataBreve(voce.data)}</span> : null}
      </div>
      <div className="iu-cs-voce__azioni">
        {principale ? (principale.endpoint
          ? <button type="button" className="is-primaria" onClick={() => onFatto(voce, principale)}>{principale.etichetta}</button>
          : <a className="is-primaria" href={principale.href}>{principale.etichetta}</a>) : null}
        {altre.map((a) => a.endpoint
          ? <button type="button" key={a.etichetta} onClick={() => onFatto(voce, a)}><CheckCircle2 size={14}/> {a.etichetta}</button>
          : <a key={a.etichetta} href={a.href}>{a.etichetta}</a>)}
      </div>
    </li>
  )
}

/** Controllo Studio: scadenze, udienze, notifiche, comunicazioni e incassi in un'unica coda ordinata per urgenza. */
export default function ControlloStudioPage() {
  const [dati, setDati] = useState<Dati | null>(null)
  const [area, setArea] = useState('')
  const [avviso, setAvviso] = useState('')
  const [aperte, setAperte] = useState<Set<string>>(new Set(FASCE_APERTE))
  const [caricamento, setCaricamento] = useState(false)

  const carica = useCallback(async () => {
    setCaricamento(true)
    const risposta = await fetch('/api/v1/ui/controllo-studio', { credentials: 'same-origin', headers: { Accept: 'application/json' } }).catch(() => null)
    const valori = risposta ? await risposta.json().catch(() => null) as Dati | null : null
    setDati(valori || { ok: false, message: 'Il quadro dello studio non si è caricato: riprova tra poco.' })
    setCaricamento(false)
  }, [])
  useEffect(() => { void carica() }, [carica])

  const voci = useMemo(() => (dati?.voci || []).filter((v) => !area || v.area === area), [dati, area])
  const gruppi = useMemo(() => (dati?.fasce || []).map((f) => ({ ...f, voci: voci.filter((v) => v.fascia === f.fascia) })).filter((g) => g.voci.length), [dati, voci])

  const fatto = async (voce: Voce, azione: Azione) => {
    if (azione.conferma && !window.confirm(azione.conferma)) return
    const esito = await esegui(azione.endpoint)
    setAvviso(esito.message)
    if (esito.ok) setDati((d) => (d ? { ...d, voci: (d.voci || []).filter((v) => v.id !== voce.id) } : d))
  }

  if (!dati) return <main className="iu-content iu-cs"><p className="iu-cs-stato">Caricamento del quadro dello studio…</p></main>
  if (!dati.ok) return <main className="iu-content iu-cs"><p className="iu-cs-stato is-errore" role="alert">{dati.message}</p></main>
  const incassi = dati.incassi || { da_incassare: 0, scaduto: 0, parcelle_scadute: 0, incassato_mese: 0 }

  return (
    <main className="iu-content iu-cs">
      <header className="iu-cs-testa">
        <div>
          <span className="iu-cs-testa__data">{dataEstesa(dati.oggi)}</span>
          <h1>Controllo Studio</h1>
          <p className={dati.urgenti ? 'is-urgente' : ''}>{dati.urgenti ? <AlertTriangle size={16}/> : <CheckCircle2 size={16}/>} {dati.riepilogo}</p>
        </div>
        <button type="button" className="iu-cs-aggiorna" onClick={() => void carica()} disabled={caricamento}><RefreshCw size={15}/> {caricamento ? 'Aggiorno…' : 'Aggiorna'}</button>
      </header>

      {dati.fonti_non_disponibili?.length ? <p className="iu-cs-stato is-avviso" role="status">Non disponibili in questo momento: {dati.fonti_non_disponibili.join(', ')}.</p> : null}
      {avviso ? <p className="iu-cs-stato is-ok" role="status">{avviso}</p> : null}

      <nav className="iu-cs-aree" aria-label="Filtra per area">
        <button type="button" className={!area ? 'is-attiva' : ''} onClick={() => setArea('')}>
          <span>Tutto</span><strong>{dati.voci?.length || 0}</strong>
        </button>
        {(dati.aree || []).map((a) => {
          const Icona = ICONE[a.area] || Inbox
          return (
            <button type="button" key={a.area} className={area === a.area ? 'is-attiva' : ''} onClick={() => setArea(area === a.area ? '' : a.area)} aria-pressed={area === a.area}>
              <span><Icona size={15}/> {a.etichetta}</span>
              <strong>{a.totale}</strong>
              {a.urgenti ? <small>{a.urgenti} urgenti</small> : <small>in ordine</small>}
            </button>
          )
        })}
      </nav>

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
                {aperta ? <ul>{g.voci.map((v) => <RigaVoce voce={v} key={v.id} onFatto={(voce, azione) => void fatto(voce, azione)}/>)}</ul> : null}
              </section>
            )
          }) : (
            <div className="iu-cs-vuoto"><CheckCircle2 size={28}/><strong>Niente da lavorare {area ? 'in quest\'area' : 'nei prossimi 30 giorni'}.</strong><span>Le nuove scadenze, udienze, PEC e parcelle compariranno qui appena registrate.</span></div>
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
    </main>
  )
}
