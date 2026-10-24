import { useEffect, useState } from 'react'
import { useOperationalRefresh } from '../hooks/useOperationalRefresh'
import { ShieldCheck } from 'lucide-react'
import { apiPostJson, ensureJson } from '../api/client'
import { Page } from '../ui/Page'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { useBusyActivity } from '../ui/useBusyActivity'
import { SchedeFontiDettaglio } from './SchedeFontiDettaglio'
import './LegalIntelligencePage.css'
import './SchedeFontiPage.css'

type Proposta = { id: string; impronta: string; tipo: string; etichetta: string; scheda: string; titolo_scheda: string; atto: string; articolo: string; motivo: string; differenze: string; creata_il: string; decisa_da: string; nota: string }
type Riepilogo = { eseguito_il: string; norme: number; stati: Record<string, number>; commi_abrogati: number; acquisiti: { chiave: string; articoli: number; url: string }[]; proposte_aperte: number; per_tipo: { tipo: string; etichetta: string; numero: number }[] }
type Risposta = { riepilogo: Riepilogo; proposte: Proposta[]; puo_decidere: boolean; modelli: { id: string; titolo: string }[]; paginazione: { pagina: number; pagine: number; totale: number } }
const base = '/api/v1/ui/schede-fonti'
function dataIt(v: string) { return v ? new Date(v).toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'short' }) : 'non ancora eseguito' }

export function SchedeFontiPage() {
  const [dati, setDati] = useState<Risposta | null>(null)
  const [tipo, setTipo] = useState('')
  const [stato, setStato] = useState('aperta')
  const [scheda, setScheda] = useState('')
  const [note, setNote] = useState<Record<string, string>>({})
  const [errore, setErrore] = useState('')
  const [messaggio, setMessaggio] = useState('')
  const [busy, setBusy] = useState(true)
  const [carica, setCarica] = useState(0)
  const [pagina, setPagina] = useState(1)
  const [selezione, setSelezione] = useState('')
  const [cerca, setCerca] = useState('')
  const [salvataggio, setSalvataggio] = useState('')
  useOperationalRefresh(['fascicoli'], () => setCarica(n => n + 1))
  useBusyActivity(busy || !!salvataggio, 'Caricamento del presidio delle norme…')
  useEffect(() => {
    const controller = new AbortController()
    setBusy(true); setErrore('')
    ensureJson<Risposta>(`${base}?${new URLSearchParams({ tipo, stato, pagina: String(pagina) })}`, { signal: controller.signal })
      .then(d => { if (!controller.signal.aborted) setDati(d) })
      .catch(e => { if (!controller.signal.aborted) setErrore(e.status === 403 ? 'Non hai il permesso per consultare le norme dei modelli d’atto.' : 'Il presidio non è ancora disponibile: si aggiorna ogni notte.') })
      .finally(() => { if (!controller.signal.aborted) setBusy(false) })
    return () => controller.abort()
  }, [tipo, stato, carica, pagina])
  async function decidi(p: Proposta, esito: 'approvata' | 'respinta') {
    if (salvataggio) return
    setSalvataggio(p.id); setMessaggio('')
    try {
      const r = await apiPostJson<{ ok: boolean; message: string }>(`${base}/proposte/${encodeURIComponent(p.id)}/decisione`, { esito, nota: note[p.id] || '', impronta: p.impronta }, { ok: false, message: 'Decisione non registrata: ricarica l’elenco.' })
      setMessaggio(r.message)
      if (r.ok) setCarica(n => n + 1)
    } catch { setMessaggio('Decisione non registrata. Verifica il collegamento e riprova.') }
    finally { setSalvataggio('') }
  }
  const r = dati?.riepilogo
  return <Page title="Norme dei modelli d’atto" subtitle="Ogni notte il software verifica le norme citate dai modelli, acquisisce dalle fonti ufficiali quelle mancanti e propone le revisioni." actions={<ButtonLink href="/ricerca-legale/codici" tone="neutral">Codici e leggi</ButtonLink>}>
    <div className="iu-li-page iu-sf-page">
      {errore ? <div role="alert" className="iu-li-warning">{errore} <Button tone="neutral" onClick={() => setCarica(n => n + 1)}>Riprova</Button></div> : null}
      {r ? <section className="iu-od-source-card iu-sf-riepilogo" aria-label="Riepilogo del presidio">
        <header className="iu-li-section-head"><ShieldCheck size={20} aria-hidden="true" /><div><h2>Ultimo controllo: {dataIt(r.eseguito_il)}</h2><p>{r.eseguito_il ? `${r.norme.toLocaleString('it-IT')} norme verificate · ${(r.stati.presente || 0).toLocaleString('it-IT')} presenti in biblioteca · ${r.proposte_aperte} proposte aperte` : 'Il primo controllo notturno non è ancora stato eseguito. Puoi già consultare i modelli disponibili.'}</p></div></header>
        <div className="iu-sf-badges">{r.per_tipo.map(t => <Button key={t.tipo} tone="neutral" onClick={() => { setTipo(t.tipo); setStato('aperta'); setPagina(1) }}>{t.etichetta}: {t.numero}</Button>)}{r.commi_abrogati ? <Badge tone="neutral">Norme con commi abrogati: {r.commi_abrogati}</Badge> : null}</div>
        {r.acquisiti.length ? <p>Acquisiti stanotte dalle fonti ufficiali: {r.acquisiti.map(a => `${a.chiave.replace(/_/g, ' ')} (${a.articoli} articoli)`).join(', ')}.</p> : null}
      </section> : null}
      <section className="iu-od-source-card iu-sf-filtri" aria-label="Consulta tutti i modelli">
        <label>Cerca modello<input value={cerca} onChange={e => setCerca(e.target.value)} /></label>
        <label>Modello d’atto<select value={selezione} onChange={e => setSelezione(e.target.value)}><option value="">Scegli un modello</option>{(dati?.modelli || []).filter(m => `${m.id} ${m.titolo}`.toLocaleLowerCase('it-IT').includes(cerca.toLocaleLowerCase('it-IT'))).map(m => <option key={m.id} value={m.id}>{m.id} — {m.titolo}</option>)}</select></label>
        <Button disabled={!selezione} onClick={() => setScheda(selezione)}>Apri le norme del modello</Button>
      </section>
      <section className="iu-od-source-card iu-sf-filtri" aria-label="Filtri delle proposte">
        <label>Stato<select value={stato} onChange={e => { setStato(e.target.value); setPagina(1) }}><option value="aperta">Da decidere</option><option value="approvata">Approvate</option><option value="respinta">Respinte</option></select></label>
        <label>Tipo<select value={tipo} onChange={e => { setTipo(e.target.value); setPagina(1) }}><option value="">Tutte</option>{(r?.per_tipo || []).map(t => <option key={t.tipo} value={t.tipo}>{t.etichetta}</option>)}</select></label>
      </section>
      {messaggio ? <p role="status">{messaggio}</p> : null}
      <div className={scheda ? "iu-sf-workbench iu-sf-workbench--dettaglio" : "iu-sf-workbench"}>
        <section className="iu-od-source-card iu-sf-proposte" aria-label="Proposte di revisione" aria-busy={busy}>
          {!busy && dati && !dati.proposte.length ? <p>Nessuna proposta in questo elenco.</p> : null}
          <ul>{(dati?.proposte || []).map(p => <li key={p.id}>
            <div className="iu-sf-badges"><Badge tone={p.tipo === 'fonte_suggerita' ? 'info' : 'primary'}>{p.etichetta}</Badge><Button tone="neutral" onClick={() => setScheda(p.scheda)}>{p.scheda} — {p.titolo_scheda}</Button></div>
            <p>{p.motivo}</p>
            {p.differenze ? (p.differenze.startsWith('http') ? <a href={p.differenze} rel="noreferrer">Fonte ufficiale indicata dal registro</a> : <details><summary>Differenze di testo</summary><pre className="iu-sf-diff">{p.differenze}</pre></details>) : null}
            {p.decisa_da ? <small>Decisa da {p.decisa_da}{p.nota ? `: ${p.nota}` : ''}</small> : null}
            {dati?.puo_decidere && stato === 'aperta' ? <div className="iu-sf-azioni">
              <input aria-label="Nota della decisione" placeholder="Nota (facoltativa)" value={note[p.id] || ''} onChange={e => setNote({ ...note, [p.id]: e.target.value })} />
              <Button disabled={!!salvataggio} onClick={() => decidi(p, 'approvata')}>Approva</Button><Button tone="neutral" disabled={!!salvataggio} onClick={() => decidi(p, 'respinta')}>Respingi</Button>
            </div> : null}
          </li>)}</ul>
          {dati?.paginazione ? <nav aria-label="Pagine delle proposte"><Button tone="neutral" disabled={busy || dati.paginazione.pagina <= 1} onClick={() => setPagina(n => n - 1)}>Precedente</Button><span> Pagina {dati.paginazione.pagina} di {dati.paginazione.pagine} · {dati.paginazione.totale} proposte </span><Button tone="neutral" disabled={busy || dati.paginazione.pagina >= dati.paginazione.pagine} onClick={() => setPagina(n => n + 1)}>Successiva</Button></nav> : null}
        </section>
        {scheda ? <SchedeFontiDettaglio schedaId={scheda} puoDecidere={!!dati?.puo_decidere} onClose={() => setScheda('')} onChanged={() => setCarica(n => n + 1)} /> : null}
      </div>
    </div>
  </Page>
}
