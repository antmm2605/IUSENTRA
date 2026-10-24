import { useEffect, useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import { apiPostJson, ensureJson } from '../api/client'
import { Page } from '../ui/Page'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { useBusyActivity } from '../ui/useBusyActivity'
import { SchedeFontiDettaglio } from './SchedeFontiDettaglio'
import './LegalIntelligencePage.css'
import './SchedeFontiPage.css'

type Proposta = { id: number; tipo: string; etichetta: string; scheda: string; titolo_scheda: string; atto: string; articolo: string; motivo: string; differenze: string; creata_il: string; decisa_da: string; nota: string }
type Riepilogo = { eseguito_il: string; norme: number; stati: Record<string, number>; commi_abrogati: number; acquisiti: { chiave: string; articoli: number; url: string }[]; proposte_aperte: number; per_tipo: { tipo: string; etichetta: string; numero: number }[] }
type Risposta = { riepilogo: Riepilogo; proposte: Proposta[]; puo_decidere: boolean }
const base = '/api/v1/ui/schede-fonti'
function dataIt(v: string) { return v ? new Date(v).toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'short' }) : 'non ancora eseguito' }

export function SchedeFontiPage() {
  const [dati, setDati] = useState<Risposta | null>(null)
  const [tipo, setTipo] = useState('')
  const [stato, setStato] = useState('aperta')
  const [scheda, setScheda] = useState('')
  const [note, setNote] = useState<Record<number, string>>({})
  const [errore, setErrore] = useState('')
  const [messaggio, setMessaggio] = useState('')
  const [busy, setBusy] = useState(true)
  const [carica, setCarica] = useState(0)
  useBusyActivity(busy, 'Caricamento del presidio delle norme…')
  useEffect(() => {
    const controller = new AbortController()
    setBusy(true); setErrore('')
    ensureJson<Risposta>(`${base}?${new URLSearchParams({ tipo, stato })}`, { signal: controller.signal })
      .then(setDati)
      .catch(e => { if (!controller.signal.aborted) setErrore(e.status === 403 ? 'Non hai il permesso per consultare le norme dei modelli d’atto.' : 'Il presidio non è ancora disponibile: si aggiorna ogni notte.') })
      .finally(() => { if (!controller.signal.aborted) setBusy(false) })
    return () => controller.abort()
  }, [tipo, stato, carica])
  async function decidi(id: number, esito: 'approvata' | 'respinta') {
    const r = await apiPostJson<{ ok: boolean; message: string }>(`${base}/proposte/${id}/decisione`, { esito, nota: note[id] || '' }, { ok: false, message: 'Decisione non registrata.' })
    setMessaggio(r.message)
    if (r.ok) setCarica(n => n + 1)
  }
  const r = dati?.riepilogo
  return <Page title="Norme dei modelli d’atto" subtitle="Ogni notte il software verifica le norme citate dai modelli, acquisisce dalle fonti ufficiali quelle mancanti e propone le revisioni." actions={<ButtonLink href="/ricerca-legale/codici" tone="neutral">Codici e leggi</ButtonLink>}>
    <div className="iu-li-page iu-sf-page">
      {errore ? <div role="alert" className="iu-li-warning">{errore} <Button tone="neutral" onClick={() => setCarica(n => n + 1)}>Riprova</Button></div> : null}
      {r ? <section className="iu-od-source-card iu-sf-riepilogo" aria-label="Riepilogo del presidio">
        <header className="iu-li-section-head"><ShieldCheck size={20} aria-hidden="true" /><div><h2>Ultimo controllo: {dataIt(r.eseguito_il)}</h2><p>{r.norme.toLocaleString('it-IT')} norme verificate · {(r.stati.presente || 0).toLocaleString('it-IT')} vigenti · {r.proposte_aperte} proposte aperte</p></div></header>
        <div className="iu-sf-badges">{r.per_tipo.map(t => <Badge key={t.tipo} tone={t.tipo === 'fonte_suggerita' ? 'info' : 'primary'}>{t.etichetta}: {t.numero}</Badge>)}{r.commi_abrogati ? <Badge tone="neutral">Norme con commi abrogati: {r.commi_abrogati}</Badge> : null}</div>
        {r.acquisiti.length ? <p>Acquisiti stanotte dalle fonti ufficiali: {r.acquisiti.map(a => `${a.chiave.replace(/_/g, ' ')} (${a.articoli} articoli)`).join(', ')}.</p> : null}
      </section> : null}
      <section className="iu-od-source-card iu-sf-filtri" aria-label="Filtri delle proposte">
        <label>Stato<select value={stato} onChange={e => setStato(e.target.value)}><option value="aperta">Da decidere</option><option value="approvata">Approvate</option><option value="respinta">Respinte</option></select></label>
        <label>Tipo<select value={tipo} onChange={e => setTipo(e.target.value)}><option value="">Tutte</option>{(r?.per_tipo || []).map(t => <option key={t.tipo} value={t.tipo}>{t.etichetta}</option>)}</select></label>
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
              <Button onClick={() => decidi(p.id, 'approvata')}>Approva</Button><Button tone="neutral" onClick={() => decidi(p.id, 'respinta')}>Respingi</Button>
            </div> : null}
          </li>)}</ul>
        </section>
        {scheda ? <SchedeFontiDettaglio schedaId={scheda} puoDecidere={!!dati?.puo_decidere} onClose={() => setScheda('')} onChanged={() => setCarica(n => n + 1)} /> : null}
      </div>
    </div>
  </Page>
}
