import { useEffect, useState } from 'react'
import { ChevronDown, ChevronUp, RefreshCw, ShieldCheck } from 'lucide-react'
import {
  approvaVariazione,
  avviaControlloGiornaliero,
  getControlloGiornaliero,
  type ControlloGiornaliero,
} from '../ricercaLegaleSchedeData'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import './ControlloGiornalieroPanel.css'

function quando(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(value)
  if (!match) return value || 'mai'
  return `${match[3]}/${match[2]}/${match[1]}${match[4] ? ` ${match[4]}:${match[5]}` : ''}`
}

function toneFonte(status: string): 'success' | 'warning' | 'danger' | 'neutral' {
  if (status === 'errore') return 'danger'
  if (status === 'never') return 'neutral'
  if (status === 'ok' || status === 'invariata') return 'success'
  return 'warning'
}

function etichettaFonte(status: string): string {
  if (status === 'never') return 'mai controllata'
  if (status === 'ok') return 'acquisita'
  return status.replace(/_/g, ' ') || 'non indicato'
}

// Controllo giornaliero delle fonti ufficiali (motore con impronta SHA-256 e diff):
// era nella pagina storica /ricerca-legale, con avvio, variazioni e approvazione.
export function ControlloGiornalieroPanel() {
  const [data, setData] = useState<ControlloGiornaliero | null>(null)
  const [open, setOpen] = useState(false)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const [busy, setBusy] = useState('')

  async function load() {
    setData(await getControlloGiornaliero())
  }

  useEffect(() => { void load() }, [])

  useEffect(() => {
    if (!data?.running) return
    const timer = window.setTimeout(() => { void load() }, 5000)
    return () => window.clearTimeout(timer)
  }, [data?.running, data?.lastRun?.startedAt])

  if (!data || !data.ok) return null

  async function run() {
    if (!data?.runAction) return
    setBusy('run')
    const esito = await avviaControlloGiornaliero(data.runAction)
    setBusy('')
    setMessage({ ok: esito.ok, text: esito.message })
    await load()
  }

  async function approve(action: string) {
    if (!window.confirm('Approvare l\'applicazione di questa variazione della fonte ufficiale?')) return
    setBusy(action)
    const esito = await approvaVariazione(action)
    setBusy('')
    setMessage({ ok: esito.ok, text: esito.message })
    await load()
  }

  return (
    <section className="iu-cg-panel iu-od-source-card" aria-label="Controllo giornaliero delle fonti ufficiali">
      <button className="iu-cg-panel__toggle" type="button" aria-expanded={open} onClick={() => setOpen(!open)}>
        <ShieldCheck size={18} aria-hidden="true" />
        <div>
          <strong>Controllo giornaliero delle fonti ufficiali</strong>
          <span>
            {data.counts.sources} fonti · {data.counts.pending} variazioni da approvare · ultimo controllo {data.lastRun ? quando(data.lastRun.finishedAt || data.lastRun.startedAt) : 'mai eseguito'}
          </span>
        </div>
        {data.counts.pending ? <Badge tone="warning">{data.counts.pending} da approvare</Badge> : null}
        {open ? <ChevronUp size={18} aria-hidden="true" /> : <ChevronDown size={18} aria-hidden="true" />}
      </button>
      {open ? (
        <div className="iu-cg-panel__body">
          <p className="iu-cg-panel__note">
            Il motore scarica le fonti ufficiali, ne calcola l&apos;impronta SHA-256 e registra le differenze rispetto all&apos;ultimo testo noto.
            Una variazione da applicare a mano resta in attesa finché non la approvi.
          </p>
          {data.canRun ? (
            <Button type="button" tone="primary" disabled={busy === 'run' || data.running} onClick={() => void run()}>
              <RefreshCw size={15} aria-hidden="true" /> {data.running ? 'Controllo in corso…' : 'Esegui il controllo ora'}
            </Button>
          ) : null}
          {message ? <p className={message.ok ? 'iu-cg-panel__msg' : 'iu-cg-panel__msg is-error'} role="status">{message.text}</p> : null}
          {data.updates.length ? (
            <ul className="iu-cg-panel__updates" aria-label="Variazioni rilevate">
              {data.updates.map((update) => (
                <li key={update.id}>
                  <div>
                    <strong>{update.title}</strong>
                    <small>{update.summary}</small>
                    <small>Rilevata: {quando(update.detectedAt)}</small>
                  </div>
                  <Badge tone={update.status === 'applied' ? 'success' : update.status === 'pending_review' ? 'warning' : 'neutral'}>{update.statusLabel}</Badge>
                  <div className="iu-cg-panel__actions">
                    {update.detailHref ? <ButtonLink href={update.detailHref} tone="neutral">Vedi differenze</ButtonLink> : null}
                    {update.approveAction ? (
                      <Button type="button" tone="success" disabled={busy === update.approveAction} onClick={() => void approve(update.approveAction)}>Approva</Button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          ) : <p className="iu-cg-panel__note">Nessuna variazione registrata.</p>}
          <div className="iu-cg-panel__sources">
            {data.sources.map((source) => (
              <a key={source.id} href={source.href} className="iu-cg-panel__source">
                <strong>{source.name}</strong>
                <Badge tone={toneFonte(source.status)}>{etichettaFonte(source.status)}</Badge>
                <small>Ultimo controllo: {quando(source.lastCheck)}</small>
                {source.error ? <small className="is-error">{source.error}</small> : null}
              </a>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  )
}
