import { useEffect, useState } from 'react'
import { ExternalLink, X } from 'lucide-react'
import { apiPostJson, ensureJson } from '../api/client'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'

type Norma = { atto: string; articolo: string; perche: string; origine: string; stato: string; url: string; aggiornato_al: string; commi_abrogati: number; approvata: boolean; approvata_da: string; approvata_il: string }
type Scheda = { id: string; titolo: string; norme: Norma[] }
const base = '/api/v1/ui/schede-fonti'
const STATI: Record<string, string> = { presente: 'Vigente', abrogato: 'Abrogata', atto_assente: 'Atto assente', articolo_assente: 'Articolo assente' }

export function SchedeFontiDettaglio({ schedaId, puoDecidere, onClose, onChanged }: { schedaId: string; puoDecidere: boolean; onClose: () => void; onChanged: () => void }) {
  const [scheda, setScheda] = useState<Scheda | null>(null)
  const [errore, setErrore] = useState('')
  const [messaggio, setMessaggio] = useState('')
  const [carica, setCarica] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setErrore('')
    ensureJson<{ scheda: Scheda }>(`${base}/schede/${encodeURIComponent(schedaId)}`, { signal: controller.signal })
      .then(d => setScheda(d.scheda))
      .catch(() => { if (!controller.signal.aborted) setErrore('Il modello non è disponibile. Riprova fra poco.') })
    return () => controller.abort()
  }, [schedaId, carica])
  async function approva() {
    const esito = await apiPostJson<{ ok: boolean; message: string }>(`${base}/schede/${encodeURIComponent(schedaId)}/approva`, {}, { ok: false, message: 'Approvazione non riuscita.' })
    setMessaggio(esito.message)
    if (esito.ok) { setCarica(n => n + 1); onChanged() }
  }
  const daApprovare = scheda ? scheda.norme.filter(n => n.stato === 'presente' && !n.approvata).length : 0
  return <section className="iu-od-source-card iu-sf-dettaglio" aria-label="Norme del modello d'atto">
    <header className="iu-sf-dettaglio-head"><div><p>{schedaId}</p><h2>{scheda?.titolo || 'Modello d’atto'}</h2></div><Button tone="neutral" aria-label="Chiudi" onClick={onClose}><X size={16} /></Button></header>
    {errore ? <p role="alert">{errore}</p> : null}
    {messaggio ? <p role="status">{messaggio}</p> : null}
    {scheda ? <>
      <p>{scheda.norme.length} norme citate · {daApprovare} da approvare. L’approvazione vale per il testo vigente esaminato: se cambia, il presidio notturno lo riapre con le differenze.</p>
      {puoDecidere && daApprovare ? <Button onClick={approva}>Approva le norme vigenti di questo modello</Button> : null}
      <ul className="iu-sf-norme">{scheda.norme.map(n => <li key={`${n.atto}-${n.articolo}`}>
        <div><strong>Art. {n.articolo}</strong> <span>{n.atto.replace(/_/g, ' ')}</span></div>
        <div className="iu-sf-badges"><Badge tone={n.stato === 'presente' ? 'success' : 'primary'}>{STATI[n.stato] || n.stato}</Badge>{n.approvata ? <Badge tone="info">Approvata da {n.approvata_da}</Badge> : n.stato === 'presente' ? <Badge tone="neutral">Da approvare</Badge> : null}{n.commi_abrogati ? <Badge tone="neutral">Commi abrogati: verificare il comma citato</Badge> : null}</div>
        <small>{n.origine === 'base_normativa' ? 'Base normativa' : `Campo «${n.origine.replace('campo:', '')}»`}: {n.perche}</small>
        {n.url ? <a href={n.url} rel="noreferrer">Testo ufficiale <ExternalLink size={12} aria-hidden="true" /></a> : null}
      </li>)}</ul>
    </> : !errore ? <p role="status">Caricamento…</p> : null}
  </section>
}
