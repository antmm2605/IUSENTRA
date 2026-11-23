import { useEffect, useState } from 'react'
import { BookMarked, Search } from 'lucide-react'
import { ensureJson } from '../api/client'
import { Page } from '../ui/Page'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { useBusyActivity } from '../ui/useBusyActivity'
import { ConoscenzaScheda } from './ConoscenzaScheda'
import { type Catalogo, type Evento, type VoceIndice, OPERAZIONI, STATI, dataOraIt } from './conoscenzaDati'
import './LegalIntelligencePage.css'
import './ConoscenzaPage.css'

const base = '/api/v1/ui/conoscenza'

function schedaDallIndirizzo(): string {
  try { return new URLSearchParams(window.location.search).get('scheda') || '' } catch { return '' }
}

function VoceCatalogo({ v, onApri }: { v: VoceIndice; onApri: (id: string) => void }) {
  const stato = STATI[v.stato] || STATI.lacune
  return <li>
    <div>
      <button type="button" className="iu-cn-apri" onClick={() => onApri(v.id)}><h3>{v.titolo}</h3></button>
      <p>{v.frammento || v.sintesi}</p>
      <small>{v.id} · revisione {v.revisione} · ultimo controllo {dataOraIt(v.ultimo_controllo)}</small>
    </div>
    <div className="iu-cn-badges">
      <Badge tone={stato.tono}>{stato.etichetta}</Badge>
      <Badge tone="neutral">{v.fonti_dirette} fonti dirette</Badge>
      <Badge tone="neutral">{v.sezioni_compilate}/9 sezioni</Badge>
    </div>
  </li>
}

export function ConoscenzaPage() {
  const [catalogo, setCatalogo] = useState<Catalogo | null>(null)
  const [materia, setMateria] = useState('')
  const [stato, setStato] = useState('')
  const [q, setQ] = useState('')
  const [risultati, setRisultati] = useState<VoceIndice[] | null>(null)
  const [scheda, setScheda] = useState(schedaDallIndirizzo())
  const [vista, setVista] = useState<'schede' | 'registro'>('schede')
  const [eventi, setEventi] = useState<Evento[]>([])
  const [operazione, setOperazione] = useState('')
  const [errore, setErrore] = useState('')
  const [busy, setBusy] = useState(true)
  useBusyActivity(busy, 'Caricamento delle schede di istituto…')

  useEffect(() => {
    const controller = new AbortController()
    ensureJson<Catalogo>(base, { signal: controller.signal })
      .then(d => { if (!controller.signal.aborted) { setCatalogo(d); setMateria(m => m || d.materie[0]?.materia || '') } })
      .catch(e => { if (!controller.signal.aborted) setErrore(e.status === 403 ? 'Non hai il permesso per consultare le schede di istituto.' : 'Non riesco a caricare le schede di istituto. Riprova.') })
      .finally(() => { if (!controller.signal.aborted) setBusy(false) })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (vista !== 'registro') return
    const controller = new AbortController()
    ensureJson<{ eventi: Evento[] }>(`${base}/registro?${new URLSearchParams({ operazione })}`, { signal: controller.signal })
      .then(d => { if (!controller.signal.aborted) setEventi(d.eventi) })
      .catch(() => { if (!controller.signal.aborted) setErrore('Non riesco a caricare il registro della conoscenza.') })
    return () => controller.abort()
  }, [vista, operazione])

  function apri(id: string) {
    setScheda(id)
    try { window.history.replaceState({}, '', `${window.location.pathname}?scheda=${encodeURIComponent(id)}`) } catch { /* indirizzo non aggiornabile */ }
  }
  function chiudi() {
    setScheda('')
    try { window.history.replaceState({}, '', window.location.pathname) } catch { /* indirizzo non aggiornabile */ }
  }
  async function cerca(e: React.FormEvent) {
    e.preventDefault()
    if (!q.trim()) { setRisultati(null); return }
    try {
      const r = await ensureJson<{ risultati: VoceIndice[] }>(`${base}/cerca?${new URLSearchParams({ q, materia: '' })}`)
      setRisultati(r.risultati)
    } catch { setErrore('Ricerca non riuscita. Riprova.') }
  }

  const corrente = catalogo?.materie.find(m => m.materia === materia)
  const elenco = (risultati ?? corrente?.schede ?? []).filter(v => !stato || v.stato === stato)
  const c = catalogo?.conteggi || {}
  return <Page title="Conoscenza — schede di istituto" subtitle="Per ogni istituto: presupposti, termini, rimedi, giudice e rito, prove, documenti, orientamenti. Ogni voce porta la norma vigente o la pronuncia da cui deriva; le sezioni senza fonte sono dichiarate mancanti." actions={<><ButtonLink href="/ricerca-legale/codici" tone="neutral">Codici e leggi</ButtonLink><ButtonLink href="/ricerca-legale/schede-atti" tone="neutral">Norme dei modelli d’atto</ButtonLink></>}>
    <div className="iu-li-page iu-cn-page">
      {errore ? <div role="alert" className="iu-li-warning">{errore}</div> : null}
      {catalogo ? <section className="iu-od-source-card iu-cn-riepilogo" aria-label="Riepilogo delle schede">
        <header className="iu-li-section-head"><BookMarked size={20} aria-hidden="true" /><div>
          <h2>{catalogo.totale} schede in {catalogo.materie.length} materie</h2>
          <p>Ultima generazione dalle fonti: {dataOraIt(catalogo.aggiornato_il) || 'non ancora eseguita'}. Il numero di fonti non misura la correttezza giuridica.</p>
        </div></header>
        <div className="iu-cn-badges">
          {Object.entries(STATI).map(([k, s]) => <Button key={k} tone="neutral" aria-pressed={stato === k} onClick={() => setStato(stato === k ? '' : k)}>{s.etichetta}: {c[k] || 0}</Button>)}
          <Button tone="neutral" aria-pressed={vista === 'registro'} onClick={() => setVista(vista === 'registro' ? 'schede' : 'registro')}>{vista === 'registro' ? 'Torna alle schede' : 'Registro delle operazioni'}</Button>
        </div>
      </section> : null}

      {vista === 'registro' ? <section className="iu-od-source-card iu-cn-registro" aria-label="Registro delle operazioni">
        <label>Operazione<select value={operazione} onChange={e => setOperazione(e.target.value)}><option value="">Tutte</option>{Object.entries(OPERAZIONI).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <ol>{eventi.map(e => <li key={e.evento_id}>
          <strong>{dataOraIt(e.ts)} · {OPERAZIONI[e.operazione] || e.operazione}</strong>
          <span>{e.titolo || (e.operazione === 'controllo' ? `Controllo di tutte le schede: ${e.generate || 0} generate, ${e.aggiornate || 0} aggiornate, ${e.invariate || 0} invariate, ${e.rinominate || 0} rinominate, ${e.ritirate || 0} ritirate` : '')}</span>
          {e.revisione_precedente != null ? <small>Revisione {e.revisione_precedente} → {e.revisione}{e.motivo ? ` · ${e.motivo}` : ''}</small> : e.revisione ? <small>Revisione {e.revisione}</small> : null}
          {e.scheda ? <Button tone="neutral" onClick={() => { setVista('schede'); apri(e.scheda) }}>Apri la scheda</Button> : null}
        </li>)}</ol>
        {!eventi.length ? <p>Nessuna operazione registrata con questo filtro.</p> : null}
      </section> : <>
        <section className="iu-od-source-card iu-cn-filtri" aria-label="Ricerca e materie">
          <form onSubmit={cerca} className="iu-cn-cerca" role="search">
            <label>Cerca negli istituti, nelle norme e nei passaggi<input value={q} onChange={e => { setQ(e.target.value); if (!e.target.value) setRisultati(null) }} placeholder="Es. licenziamento, art. 414 c.p.c., precetto contro la PA" /></label>
            <Button type="submit"><Search size={16} aria-hidden="true" /> Cerca</Button>
          </form>
          {risultati ? <p role="status">{risultati.length} schede trovate (ricerca testuale, senza embeddings). <Button tone="neutral" onClick={() => { setQ(''); setRisultati(null) }}>Mostra le materie</Button></p> : <label>Materia<select value={materia} onChange={e => setMateria(e.target.value)}>{catalogo?.materie.map(m => <option key={m.materia} value={m.materia}>{m.materia} ({m.schede.length})</option>)}</select></label>}
        </section>
        <div className={scheda ? 'iu-cn-workbench iu-cn-workbench--dettaglio' : 'iu-cn-workbench'}>
          <section className="iu-od-source-card iu-cn-elenco" aria-label="Schede di istituto" aria-busy={busy}>
            {!busy && !elenco.length ? <p>Nessuna scheda in questo elenco.</p> : null}
            <ul>{elenco.map(v => <VoceCatalogo key={v.id} v={v} onApri={apri} />)}</ul>
          </section>
          {scheda ? <ConoscenzaScheda schedaId={scheda} puoAnnotare={!!catalogo?.puo_annotare} onClose={chiudi} /> : null}
        </div>
      </>}
    </div>
  </Page>
}
