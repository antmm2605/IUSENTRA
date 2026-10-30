import { useEffect, useRef, useState } from 'react'
import { useOperationalRefresh } from '../hooks/useOperationalRefresh'
import { NormativeArticleLink } from './NormativeArticleLink'
import { ExternalLink, X } from 'lucide-react'
import { apiPostJson, ensureJson } from '../api/client'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { useBusyActivity } from '../ui/useBusyActivity'

type Norma = { atto: string; articolo: string; perche: string; origine: string; stato: string; url: string; aggiornato_al: string; commi_abrogati: number; testo: string; sha256: string; differenze: string; approvata: boolean; approvata_da: string }
type Scheda = { id: string; titolo: string; norme: Norma[]; impronta: string; stato_collegamento?: string; schede_collegate?: string[] }
const base = '/api/v1/ui/schede-fonti'
const STATI: Record<string, string> = { presente: 'Presente in biblioteca', abrogato: 'Abrogata', atto_assente: 'Atto assente', articolo_assente: 'Articolo assente' }
export function SchedeFontiDettaglio({ schedaId, puoDecidere, onClose, onChanged }: { schedaId: string; puoDecidere: boolean; onClose: () => void; onChanged: () => void }) {
  const [scheda, setScheda] = useState<Scheda | null>(null)
  const [errore, setErrore] = useState('')
  const [messaggio, setMessaggio] = useState('')
  const [conferma, setConferma] = useState(false)
  const [busy, setBusy] = useState(true)
  const [salva, setSalva] = useState(false)
  const [carica, setCarica] = useState(0)
  const dettaglioRef = useRef<HTMLElement>(null)
  useEffect(() => {
    dettaglioRef.current?.scrollIntoView({ block: 'start' })
    dettaglioRef.current?.focus({ preventScroll: true })
  }, [schedaId, busy])
  const liveScheda = useRef(schedaId)
  liveScheda.current = schedaId
  useOperationalRefresh(['fascicoli', 'normativa'], async () => {
    if (salva) return false
    const id = schedaId
    const response = await ensureJson<{ scheda: Scheda }>(`${base}/schede/${encodeURIComponent(id)}`)
    if (id === liveScheda.current) setScheda(response.scheda)
  })
  useBusyActivity(busy || salva, salva ? 'Registrazione dell’approvazione…' : 'Caricamento delle norme…')
  useEffect(() => {
    const controller = new AbortController()
    setErrore(''); setBusy(true)
    ensureJson<{ scheda: Scheda }>(`${base}/schede/${encodeURIComponent(schedaId)}`, { signal: controller.signal })
      .then(d => { if (!controller.signal.aborted) setScheda(d.scheda) })
      .catch(() => { if (!controller.signal.aborted) setErrore('Il modello non è disponibile. Riprova.') })
      .finally(() => { if (!controller.signal.aborted) setBusy(false) })
    return () => controller.abort()
  }, [schedaId, carica])
  useEffect(() => { setMessaggio(''); setScheda(null); setConferma(false) }, [schedaId])
  useEffect(() => { setConferma(false) }, [scheda?.impronta])
  async function approva() {
    if (!scheda || !conferma || salva) return
    setSalva(true); setMessaggio('')
    try {
      const r = await apiPostJson<{ ok: boolean; message: string }>(`${base}/schede/${encodeURIComponent(schedaId)}/approva`, { impronta: scheda.impronta }, { ok: false, message: 'Approvazione non registrata: riapri il modello per verificare eventuali modifiche.' })
      if (r.ok) { setCarica(n => n + 1); onChanged() }
      setMessaggio(r.message)
    } catch { setMessaggio('Approvazione non registrata. Riprova dopo aver verificato il collegamento.') }
    finally { setSalva(false) }
  }
  const daApprovare = scheda?.norme.filter(n => n.stato === 'presente' && !n.approvata).length || 0
  return <section ref={dettaglioRef} tabIndex={-1} className="iu-od-source-card iu-sf-dettaglio" aria-label="Norme del modello d’atto" aria-busy={busy || salva}>
    <header className="iu-sf-dettaglio-head"><div><p>{schedaId}</p><h2>{scheda?.titolo || 'Modello d’atto'}</h2></div><Button tone="neutral" aria-label="Chiudi" onClick={onClose}><X size={16} /></Button></header>
    {busy ? <p role="status">Caricamento delle norme del modello…</p> : null}
    {errore ? <p role="alert">{errore} <Button tone="neutral" onClick={() => setCarica(n => n + 1)}>Riprova</Button></p> : null}
    {messaggio ? <p role="status">{messaggio}</p> : null}
    {scheda?.stato_collegamento === 'da_associare' ? <p role="status">Questa voce è presente nel catalogo, ma non ha ancora una scheda normativa specifica collegata. Il testo del modello non è stato escluso: i riferimenti devono essere associati e verificati prima di dichiararli completi.</p> : null}
    {scheda ? <><p>{scheda.norme.length} norme citate · {daApprovare} da approvare. Presenza in biblioteca e approvazione per questo studio sono due verifiche distinte.</p>
      <ul className="iu-sf-norme">{scheda.norme.map(n => <li key={`${n.atto}-${n.articolo}`}>
        <div><strong>Art. {n.articolo}</strong> <span>{n.atto.replace(/_/g, ' ')}</span></div>
        <div className="iu-sf-badges"><Badge tone={n.stato === 'presente' ? 'success' : 'primary'}>{STATI[n.stato] || n.stato}</Badge>{n.approvata ? <Badge tone="info">Approvata da {n.approvata_da}</Badge> : n.stato === 'presente' ? <Badge tone="neutral">Da approvare</Badge> : null}{n.commi_abrogati ? <Badge tone="neutral">Commi abrogati: verificare il comma citato</Badge> : null}</div>
        <small>{n.origine === 'base_normativa' ? 'Base normativa' : `Campo «${n.origine.replace('campo:', '')}»`}: {n.perche}</small>
        {n.testo ? <details><summary>Testo da esaminare</summary><pre className="iu-sf-diff">{n.testo}</pre></details> : null}
        {n.differenze ? <details open><summary>Variazione rispetto all’approvazione</summary><pre className="iu-sf-diff">{n.differenze}</pre></details> : null}
        {n.url ? <NormativeArticleLink url={n.url} article={n.articolo} act={n.atto} sha={n.sha256}>Testo ufficiale <ExternalLink size={12} aria-hidden="true" /></NormativeArticleLink> : null}
      </li>)}</ul>
      {puoDecidere && daApprovare ? <div className="iu-sf-azioni"><label><input type="checkbox" checked={conferma} onChange={e => setConferma(e.target.checked)} disabled={salva} /> Ho esaminato i testi presenti e le relative fonti.</label><Button onClick={approva} disabled={!conferma || salva}>Approva questi testi per lo studio</Button></div> : null}
    </> : null}
  </section>
}
