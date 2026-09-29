import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowRightLeft, FilePlus2, FolderPlus, Gavel, Upload } from 'lucide-react'
import { csrfHeader } from '../api/csrf'
import './RecuperoCreditiPage.css'

type Opzione = { value: string; label: string }
type Posizione = {
  id: string; lotto: string; creditore: string; debitore: string; debitore_codice: string; commerciale: boolean
  documenti: { numero: string; data: string; scadenza: string; importo: number }[]
  capitale: number; stato: string; stato_etichetta: string; fascicolo_id: string
  eventi: { stato: string; data: string; nota: string }[]
}
type Dati = {
  ok: boolean; message?: string; puoModificare?: boolean; posizioni?: Posizione[]; stati?: Opzione[]; atti?: Opzione[]; creditori?: Opzione[]
  passaggi?: Record<string, string[]>
  riepilogo?: { posizioni: number; capitale: number; per_stato: { stato: string; etichetta: string; posizioni: number; capitale: number }[] }
}
type Conteggio = { ok: boolean; message?: string; capitale: number; interessi: number; indennizzo_forfettario: number; totale: number; tipo_interessi: string; al: string }

const euro = (v: number | undefined) => {
  const [intero, decimali] = Math.abs(Number(v || 0)).toFixed(2).split('.')
  return `${Number(v || 0) < 0 ? '-' : ''}€ ${intero.replace(/\B(?=(\d{3})+(?!\d))/g, '.')},${decimali}`
}
const oggiIso = () => new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Rome' })

async function invia(url: string, corpo: Record<string, unknown> | FormData): Promise<{ ok: boolean; message: string; errori?: string[]; saltate?: string[]; rifiutate?: string[] }> {
  try {
    const formData = corpo instanceof FormData
    const risposta = await fetch(url, {
      method: 'POST', credentials: 'same-origin', body: formData ? corpo : JSON.stringify(corpo),
      headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest', ...(formData ? {} : { 'Content-Type': 'application/json' }), ...csrfHeader() },
    })
    const dati = await risposta.json().catch(() => ({}))
    return { ok: Boolean(dati.ok), message: dati.message || 'Operazione non riuscita.', errori: dati.errori, saltate: dati.saltate, rifiutate: dati.rifiutate }
  } catch {
    return { ok: false, message: 'Operazione non riuscita.' }
  }
}

/** Recupero crediti in serie: posizioni per debitore, atti in blocco e scadenze di legge (artt. 633-647, 480-481, 543 c.p.c.). */
export function RecuperoCreditiPage() {
  const [dati, setDati] = useState<Dati | null>(null)
  const [scelte, setScelte] = useState<Set<string>>(new Set())
  const [filtroStato, setFiltroStato] = useState('')
  const [messaggio, setMessaggio] = useState<{ testo: string; dettagli: string[] } | null>(null)
  const [occupato, setOccupato] = useState(false)
  const [creditore, setCreditore] = useState('')
  const [lotto, setLotto] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [nuovoStato, setNuovoStato] = useState('')
  const [dataEvento, setDataEvento] = useState(oggiIso())
  const [conteggio, setConteggio] = useState<{ id: string; dati: Conteggio } | null>(null)

  const carica = useCallback(async () => {
    const risposta = await fetch('/api/v1/ui/recupero-crediti', { credentials: 'same-origin', headers: { Accept: 'application/json' } }).catch(() => null)
    setDati(risposta ? await risposta.json().catch(() => ({ ok: false, message: 'Dati non leggibili.' })) : { ok: false, message: 'Recupero crediti non disponibile.' })
  }, [])
  useEffect(() => { void carica() }, [carica])

  const visibili = useMemo(() => (dati?.posizioni || []).filter((p) => !filtroStato || p.stato === filtroStato), [dati, filtroStato])
  if (!dati) return <main className="iu-rc-page"><p role="status">Carico le posizioni…</p></main>
  if (!dati.ok) return <main className="iu-rc-page"><p role="alert">{dati.message}</p></main>

  const ids = [...scelte]
  const esegui = async (azione: () => Promise<{ ok: boolean; message: string; errori?: string[]; saltate?: string[]; rifiutate?: string[] }>) => {
    setOccupato(true)
    const esito = await azione()
    setOccupato(false)
    setMessaggio({ testo: esito.message, dettagli: [...(esito.errori || []), ...(esito.saltate || []), ...(esito.rifiutate || [])] })
    if (esito.ok) await carica()
  }
  const importa = () => esegui(() => {
    const corpo = new FormData()
    corpo.append('creditore_id', creditore); corpo.append('lotto', lotto); if (file) corpo.append('file', file)
    return invia('/recupero-crediti/importa', corpo)
  })
  const passaggiComuni = (() => {
    const scelti = (dati.posizioni || []).filter((p) => scelte.has(p.id))
    if (!scelti.length) return [] as string[]
    return (dati.passaggi?.[scelti[0].stato] || []).filter((s) => scelti.every((p) => (dati.passaggi?.[p.stato] || []).includes(s)))
  })()
  const etichetta = (stato: string) => dati.stati?.find((s) => s.value === stato)?.label || stato
  const apriConteggio = async (id: string) => {
    const risposta = await fetch(`/api/v1/ui/recupero-crediti/${encodeURIComponent(id)}/conteggio`, { credentials: 'same-origin', headers: { Accept: 'application/json' } }).catch(() => null)
    const valori = risposta ? await risposta.json().catch(() => null) as Conteggio | null : null
    if (valori) {
      setConteggio({ id, dati: valori })
      window.setTimeout(() => document.querySelector('.iu-rc-conteggio')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 50)
    }
  }

  return (
    <main className="iu-rc-page">
      <header className="iu-rc-hero">
        <div>
          <span><Gavel size={16}/> Recupero crediti</span>
          <h1>Recupero crediti in serie</h1>
          <p>Una posizione per debitore: diffida, ricorso per decreto ingiuntivo, precetto e pignoramento, con le scadenze di legge nello scadenziario del fascicolo. IUSENTRA prepara le bozze; deposito e notifica restano all'avvocato.</p>
        </div>
        <div className="iu-rc-hero__numeri">
          <article><strong>{dati.riepilogo?.posizioni || 0}</strong><small>Posizioni</small></article>
          <article><strong>{euro(dati.riepilogo?.capitale)}</strong><small>Capitale aperto</small></article>
        </div>
      </header>

      {dati.puoModificare ? (
        <section className="iu-rc-import" aria-label="Importa debitori">
          <strong><Upload size={15}/> Importa l'elenco dei debitori (CSV)</strong>
          <span>Una riga per fattura con le colonne Debitore, Codice fiscale/Partita IVA, Numero fattura, Data fattura, Scadenza, Importo; facoltative Indirizzo, PEC, Commerciale (sì/no). Da Excel: «Salva con nome» → CSV.</span>
          <div className="iu-rc-import__campi">
            <label><span>Creditore</span><select value={creditore} onChange={(e) => setCreditore(e.target.value)}>
              <option value="">Scegli il cliente creditore</option>{(dati.creditori || []).map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}</select></label>
            <label><span>Nome del lotto</span><input value={lotto} onChange={(e) => setLotto(e.target.value)} placeholder="Es. Fatture scadute 2026"/></label>
            <label><span>File CSV</span><input type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] || null)}/></label>
            <button type="button" disabled={occupato || !creditore || !file} onClick={() => void importa()}><Upload size={15}/> Importa</button>
          </div>
        </section>
      ) : null}

      <section className="iu-rc-stati" aria-label="Posizioni per stato">
        <button type="button" className={!filtroStato ? 'is-active' : ''} onClick={() => setFiltroStato('')}>Tutte ({dati.riepilogo?.posizioni || 0})</button>
        {(dati.riepilogo?.per_stato || []).map((s) => (
          <button type="button" key={s.stato} className={filtroStato === s.stato ? 'is-active' : ''} onClick={() => setFiltroStato(s.stato)}>{s.etichetta.split(':')[0].split(' (')[0]} ({s.posizioni})</button>
        ))}
      </section>

      {dati.puoModificare && scelte.size ? (
        <section className="iu-rc-azioni" aria-label="Azioni sulle posizioni scelte">
          <strong>{scelte.size} posizioni scelte</strong>
          <button type="button" disabled={occupato} onClick={() => void esegui(() => invia('/recupero-crediti/fascicoli', { ids }))}><FolderPlus size={15}/> Apri i fascicoli</button>
          {(dati.atti || []).map((a) => (
            <button type="button" key={a.value} disabled={occupato} onClick={() => void esegui(() => invia('/recupero-crediti/atti', { ids, tipo: a.value }))}><FilePlus2 size={15}/> Bozza: {a.label.split(' (')[0].toLowerCase()}</button>
          ))}
          <div className="iu-rc-azioni__avanza">
            <label><span>Evento</span><select value={nuovoStato} onChange={(e) => setNuovoStato(e.target.value)}>
              <option value="">Scegli l'evento</option>{passaggiComuni.map((s) => <option key={s} value={s}>{etichetta(s)}</option>)}</select></label>
            <label><span>Data</span><input type="date" value={dataEvento} max={oggiIso()} onChange={(e) => setDataEvento(e.target.value)}/></label>
            <button type="button" disabled={occupato || !nuovoStato} onClick={() => void esegui(() => invia('/recupero-crediti/avanza', { ids, stato: nuovoStato, data: dataEvento }))}><ArrowRightLeft size={15}/> Registra evento</button>
          </div>
        </section>
      ) : null}

      {messaggio ? (
        <div className="iu-rc-messaggio" role="status"><strong>{messaggio.testo}</strong>{messaggio.dettagli.length ? <ul>{messaggio.dettagli.slice(0, 20).map((d) => <li key={d}>{d}</li>)}</ul> : null}</div>
      ) : null}

      <section className="iu-rc-tabella">
        <table aria-label="Posizioni di recupero crediti">
          <thead><tr>
            <th><input type="checkbox" aria-label="Scegli tutte" checked={visibili.length > 0 && visibili.every((p) => scelte.has(p.id))}
              onChange={(e) => setScelte(e.target.checked ? new Set(visibili.map((p) => p.id)) : new Set())}/></th>
            <th>Debitore</th><th>Creditore / lotto</th><th>Documenti</th><th>Capitale</th><th>Stato</th><th>Fascicolo</th>
          </tr></thead>
          <tbody>
            {visibili.length ? visibili.map((p) => (
              <tr key={p.id}>
                <td className="iu-rc-cella-scelta"><input type="checkbox" aria-label={`Scegli ${p.debitore}`} checked={scelte.has(p.id)} onChange={(e) => setScelte((s) => { const n = new Set(s); if (e.target.checked) n.add(p.id); else n.delete(p.id); return n })}/></td>
                <td data-etichetta="Debitore"><strong>{p.debitore}</strong><small>{p.debitore_codice || '—'}{p.commerciale ? ' · commerciale' : ''}</small></td>
                <td data-etichetta="Creditore / lotto"><span>{p.creditore}</span><small>{p.lotto}</small></td>
                <td data-etichetta="Documenti">{p.documenti.length}</td>
                <td data-etichetta="Capitale"><button type="button" className="iu-rc-link" onClick={() => void apriConteggio(p.id)}>{euro(p.capitale)}</button></td>
                <td data-etichetta="Stato"><span className={`iu-rc-stato iu-rc-stato--${p.stato.startsWith('chiusa') ? 'chiusa' : 'aperta'}`}>{p.stato_etichetta.split(':')[0]}</span>{p.eventi.length ? <small>dal {p.eventi[p.eventi.length - 1].data.split('-').reverse().join('/')}</small> : null}</td>
                <td data-etichetta="Fascicolo">{p.fascicolo_id ? <a href={`/fascicoli/${encodeURIComponent(p.fascicolo_id)}`}>Apri</a> : '—'}</td>
              </tr>
            )) : <tr><td colSpan={7} className="iu-rc-vuoto">Nessuna posizione: importa l'elenco dei debitori.</td></tr>}
          </tbody>
        </table>
      </section>

      {conteggio ? (
        <section className="iu-rc-conteggio" aria-label="Conteggio del credito">
          <strong>Conteggio al {conteggio.dati.al?.split('-').reverse().join('/')}</strong>
          {conteggio.dati.ok ? (
            <dl>
              <div><dt>Capitale</dt><dd>{euro(conteggio.dati.capitale)}</dd></div>
              <div><dt>Interessi {conteggio.dati.tipo_interessi}</dt><dd>{euro(conteggio.dati.interessi)}</dd></div>
              {conteggio.dati.indennizzo_forfettario ? <div><dt>Indennizzo forfettario (art. 6 D.Lgs. 231/2002)</dt><dd>{euro(conteggio.dati.indennizzo_forfettario)}</dd></div> : null}
              <div className="is-totale"><dt>Totale</dt><dd>{euro(conteggio.dati.totale)}</dd></div>
            </dl>
          ) : <p role="alert">{conteggio.dati.message}</p>}
          <button type="button" onClick={() => setConteggio(null)}>Chiudi</button>
        </section>
      ) : null}
    </main>
  )
}

export default RecuperoCreditiPage
