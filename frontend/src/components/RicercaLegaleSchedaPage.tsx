import { useEffect, useState } from 'react'
import { ArrowLeft, CheckCircle2, Download, ExternalLink } from 'lucide-react'
import {
  approvaVariazione,
  getFonteScheda,
  getNewsScheda,
  getVariazioneScheda,
  ricercaLegaleSchedaRoute,
  type Esito,
  type FonteScheda,
  type NewsScheda,
  type Variazione,
} from '../ricercaLegaleSchedeData'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import './RicercaLegaleSchedaPage.css'

function quando(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(value)
  if (!match) return value || '—'
  return `${match[3]}/${match[2]}/${match[1]}${match[4] ? ` ${match[4]}:${match[5]}` : ''}`
}

function toneStato(status: string): 'success' | 'warning' | 'neutral' {
  if (status === 'applied') return 'success'
  if (status === 'pending_review') return 'warning'
  return 'neutral'
}

function Voce({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </>
  )
}

function ApprovaButton({ action, onDone }: { action: string; onDone: (message: string, ok: boolean) => void }) {
  const [busy, setBusy] = useState(false)
  if (!action) return null
  return (
    <Button
      type="button"
      tone="success"
      disabled={busy}
      onClick={async () => {
        if (!window.confirm('Approvare l\'applicazione di questa variazione della fonte ufficiale?')) return
        setBusy(true)
        const esito = await approvaVariazione(action)
        setBusy(false)
        onDone(esito.message, esito.ok)
      }}
    >
      <CheckCircle2 size={15} aria-hidden="true" /> {busy ? 'Approvazione…' : 'Approva'}
    </Button>
  )
}

function NewsView({ item }: { item: NewsScheda }) {
  return (
    <Page
      title={item.title}
      subtitle={[item.type, item.matter, item.submatter].filter(Boolean).join(' · ')}
      actions={(
        <>
          <ButtonLink href="/ricerca-legale/news" tone="neutral"><ArrowLeft size={15} aria-hidden="true" /> Aggiornamenti</ButtonLink>
          {item.sourceHref ? <ButtonLink href={item.sourceHref} tone="primary" target="_blank" rel="noopener noreferrer"><ExternalLink size={15} aria-hidden="true" /> Fonte ufficiale</ButtonLink> : null}
        </>
      )}
    >
      <div className="iu-rls-grid">
        <Panel title="Sintesi">
          <p className="iu-rls-text">{item.summary || 'Sintesi non disponibile.'}</p>
          <h3 className="iu-rls-subtitle">Cosa cambia</h3>
          <p className="iu-rls-text">{item.content || 'Contenuto non disponibile.'}</p>
        </Panel>
        <Panel title="Dati della news">
          <dl className="iu-rls-facts">
            <Voce label="Pubblicazione">{quando(item.publishedAt)}</Voce>
            <Voce label="Tipologia">{item.type || '—'}</Voce>
            <Voce label="Materia">{item.matter || 'Da verificare'}</Voce>
            <Voce label="Sottomateria">{item.submatter || 'Non assegnata'}</Voce>
            <Voce label="Origine">{item.origin}</Voce>
            {item.sourceName ? <Voce label="Fonte">{item.sourceName}{item.sourceOfficial ? ' (ufficiale)' : ''}</Voce> : null}
          </dl>
        </Panel>
      </div>
    </Page>
  )
}

function VariazioniList({ updates, onDone }: { updates: Variazione[]; onDone: (message: string, ok: boolean) => void }) {
  if (!updates.length) return null
  return (
    <Panel title="Variazioni rilevate" subtitle={`${updates.length} variazioni`}>
      <ul className="iu-rls-updates">
        {updates.map((update) => (
          <li key={update.id}>
            <div>
              <strong>{update.title}</strong>
              <small>{update.summary}</small>
              <small>Rilevata: {quando(update.detectedAt)}</small>
            </div>
            <Badge tone={toneStato(update.status)}>{update.statusLabel || 'stato non indicato'}</Badge>
            <div className="iu-rls-actions">
              {update.detailHref ? <ButtonLink href={update.detailHref} tone="neutral">Vedi differenze</ButtonLink> : null}
              <ApprovaButton action={update.approveAction} onDone={onDone} />
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  )
}

function FonteView({ item, onDone }: { item: FonteScheda; onDone: (message: string, ok: boolean) => void }) {
  return (
    <Page
      title={item.name}
      subtitle={[item.area, item.channel && `canale ${item.channel}`, item.cadence && `frequenza ${item.cadence}`].filter(Boolean).join(' · ')}
      actions={(
        <>
          <ButtonLink href="/ricerca-legale" tone="neutral"><ArrowLeft size={15} aria-hidden="true" /> Ricerca legale</ButtonLink>
          {item.downloadHref ? <ButtonLink href={item.downloadHref} tone="primary" download><Download size={15} aria-hidden="true" /> Testo archiviato</ButtonLink> : null}
          {item.officialHref ? <ButtonLink href={item.officialHref} tone="neutral" target="_blank" rel="noopener noreferrer"><ExternalLink size={15} aria-hidden="true" /> Fonte ufficiale</ButtonLink> : null}
        </>
      )}
    >
      {item.warning ? <p className="iu-rls-warning" role="status">{item.warning}</p> : null}
      <div className="iu-rls-grid">
        <div className="iu-rls-stack">
          <Panel title="Profilo della fonte" actions={<Badge tone={item.freshness === 'aggiornata' ? 'success' : item.freshness === 'errore' ? 'danger' : 'warning'}>{item.freshness || 'non verificata'}</Badge>}>
            <dl className="iu-rls-facts">
              <Voce label="Identificativo"><code>{item.id}</code></Voce>
              {item.officialHref ? <Voce label="Indirizzo ufficiale"><a href={item.officialHref} target="_blank" rel="noopener noreferrer">{item.officialHref}</a></Voce> : null}
              {item.monitorHref ? <Voce label="Indirizzo controllato"><a href={item.monitorHref} target="_blank" rel="noopener noreferrer">{item.monitorHref}</a></Voce> : null}
              {item.formats.length ? <Voce label="Formati">{item.formats.join(', ')}</Voce> : null}
              {item.fetcherNote ? <Voce label="Nota di acquisizione">{item.fetcherNote}</Voce> : null}
              {item.impactAreas.length ? <Voce label="Aree di impatto">{item.impactAreas.join(', ')}</Voce> : null}
            </dl>
          </Panel>
          <Panel title="Storico dei controlli" subtitle={`${item.history.length} acquisizioni`}>
            {item.history.length ? (
              <div className="iu-rls-table-wrap">
                <table className="iu-rls-table">
                  <thead><tr><th>Quando</th><th>HTTP</th><th>Impronta SHA-256</th><th>Dimensione</th><th>ETag / Last-Modified</th></tr></thead>
                  <tbody>
                    {item.history.map((snap, index) => (
                      <tr key={`${snap.fetchedAt}-${index}`}>
                        <td>{quando(snap.fetchedAt)}</td>
                        <td>{snap.httpStatus || '—'}</td>
                        <td><code>{snap.sha256 ? `${snap.sha256.slice(0, 16)}…` : '—'}</code></td>
                        <td>{snap.bytes} byte</td>
                        <td>{[snap.etag && `ETag ${snap.etag}`, snap.lastModified].filter(Boolean).join(' · ') || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <EmptyState title="Nessuna acquisizione" message="La fonte non è ancora stata controllata dal motore giornaliero." />}
          </Panel>
          <VariazioniList updates={item.updates} onDone={onDone} />
        </div>
        <div className="iu-rls-stack">
          <Panel title="Stato del controllo">
            <dl className="iu-rls-facts">
              <Voce label="Ultimo controllo">{item.monitor.lastCheck ? quando(item.monitor.lastCheck) : 'mai'}</Voce>
              <Voce label="Esito">{item.monitor.status || '—'}</Voce>
              <Voce label="Codice HTTP">{item.monitor.httpStatus || '—'}</Voce>
              <Voce label="Cambiata dall'ultimo controllo">{item.monitor.changed ? 'Sì' : 'No'}</Voce>
              {item.monitor.version ? <Voce label="Versione">{item.monitor.version}</Voce> : null}
              {item.monitor.reference ? <Voce label="Riferimento">{item.monitor.reference}</Voce> : null}
              {item.monitor.package ? <Voce label="Pacchetto">{item.monitor.package}</Voce> : null}
              {item.monitor.packageStatus ? <Voce label="Stato del pacchetto">{item.monitor.packageStatus}</Voce> : null}
            </dl>
          </Panel>
          <Panel title="Testo in archivio">
            {item.latest ? (
              <dl className="iu-rls-facts">
                <Voce label="Acquisito">{quando(item.latest.fetchedAt)}</Voce>
                {item.latest.href ? <Voce label="Indirizzo effettivo"><a href={item.latest.href} target="_blank" rel="noopener noreferrer">{item.latest.href}</a></Voce> : null}
                <Voce label="Impronta SHA-256"><code>{item.latest.sha256 ? `${item.latest.sha256.slice(0, 32)}…` : '—'}</code></Voce>
                <Voce label="ETag">{item.latest.etag || '—'}</Voce>
                <Voce label="Last-Modified">{item.latest.lastModified || '—'}</Voce>
              </dl>
            ) : <EmptyState title="Nessun testo archiviato" message="Il primo controllo della fonte popola l'archivio." />}
          </Panel>
          {item.lastError ? <p className="iu-rls-warning" role="status">Ultimo errore: {item.lastError}</p> : null}
        </div>
      </div>
    </Page>
  )
}

function VariazioneView({ item, onDone }: { item: Variazione; onDone: (message: string, ok: boolean) => void }) {
  return (
    <Page
      title="Differenze della fonte ufficiale"
      subtitle="Confronto fra l'ultimo testo noto e la nuova versione acquisita dal motore giornaliero."
      actions={(
        <>
          <ButtonLink href="/ricerca-legale" tone="neutral"><ArrowLeft size={15} aria-hidden="true" /> Ricerca legale</ButtonLink>
          <ApprovaButton action={item.approveAction} onDone={onDone} />
        </>
      )}
    >
      <Panel title={item.title || 'Variazione'} subtitle={item.summary} actions={<Badge tone={toneStato(item.status)}>{item.statusLabel}</Badge>}>
        <dl className="iu-rls-facts">
          <Voce label="Applicazione">{item.applyMode || '—'}</Voce>
          <Voce label="Gravità">{item.severity || '—'}</Voce>
          <Voce label="Impronta precedente"><code>{item.oldSha256 || 'primo testo acquisito'}</code></Voce>
          <Voce label="Nuova impronta"><code>{item.newSha256 || '—'}</code></Voce>
        </dl>
        <pre className="iu-rls-diff" aria-label="Differenze">{item.diff || 'Differenze non disponibili per questo aggiornamento.'}</pre>
      </Panel>
    </Page>
  )
}

export function RicercaLegaleSchedaPage() {
  const route = ricercaLegaleSchedaRoute(window.location.pathname)
  const [state, setState] = useState<Esito<NewsScheda | FonteScheda | Variazione> | null>(null)
  const [notice, setNotice] = useState<{ ok: boolean; message: string } | null>(null)
  const [revision, setRevision] = useState(0)

  useEffect(() => {
    if (!route) return
    let active = true
    const load = route.mode === 'news' ? getNewsScheda(route.key) : route.mode === 'fonte' ? getFonteScheda(route.key) : getVariazioneScheda(route.key)
    load.then((esito) => { if (active) setState(esito) })
    return () => { active = false }
  }, [route?.mode, route?.key, revision])

  const onDone = (message: string, ok: boolean) => {
    setNotice({ ok, message })
    if (ok) setRevision((value) => value + 1)
  }

  if (!route) return <EmptyState title="Scheda non riconosciuta" message="L'indirizzo non corrisponde a una scheda della Ricerca legale." />
  if (!state) return <LoadingState title="Caricamento della scheda" />
  if (!state.ok || !state.item) {
    return (
      <Page title="Scheda non disponibile" actions={<ButtonLink href="/ricerca-legale" tone="neutral"><ArrowLeft size={15} aria-hidden="true" /> Ricerca legale</ButtonLink>}>
        <EmptyState title="Scheda non disponibile" message={state.message || 'La scheda richiesta non esiste o non è più pubblicata.'} />
      </Page>
    )
  }
  return (
    <>
      {notice ? <p className={notice.ok ? 'iu-rls-notice' : 'iu-rls-notice is-error'} role="status">{notice.message}</p> : null}
      {route.mode === 'news' ? <NewsView item={state.item as NewsScheda} /> : null}
      {route.mode === 'fonte' ? <FonteView item={state.item as FonteScheda} onDone={onDone} /> : null}
      {route.mode === 'variazione' ? <VariazioneView item={state.item as Variazione} onDone={onDone} /> : null}
    </>
  )
}
