import { useEffect, useMemo, useState } from 'react'
import { Download, Eye, RefreshCw, Search } from 'lucide-react'
import {
  emptyAuditPage,
  getAuditPage,
  getAuditEventDetail,
  getRegistroAttivitaPage,
  type AuditAction,
  type AuditEventDetail,
  type AuditPageData,
  type AuditRecord,
} from '../auditData'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import { displaySourceLabel, displayWritesLabel, sanitizeDisplayText } from '../displayText'
import './AuditPage.css'

function actionTone(action: AuditAction) {
  return action.tone === 'danger' || action.tone === 'success' || action.tone === 'warning'
    ? action.tone
    : action.id === 'refresh'
      ? 'primary'
      : 'neutral'
}

function formatTimestamp(value: string): string {
  if (!value) return 'Data non indicata'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('it-IT', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(parsed)
}

function matchesQuery(record: AuditRecord, query: string, result: string): boolean {
  const haystack = [
    record.username,
    record.action,
    record.resourceType,
    record.resourceId,
    record.details,
    record.ip,
    record.resourceLabel,
    record.resourceNote,
  ].join(' ').toLowerCase()
  const resultMatches = result === 'tutti' || record.result.toLowerCase() === result
  return resultMatches && (!query || haystack.includes(query.toLowerCase()))
}

function Warnings({ data }: { data: AuditPageData }) {
  if (!data.warnings.length) return null
  return (
    <Panel title="Avvisi operativi">
      <div className="iu-audit-warnings">
        {data.warnings.map((warning) => (
          <div className="iu-audit-warning" key={`${warning.code}-${warning.message}`}>
            <Badge tone="warning">{sanitizeDisplayText(warning.code)}</Badge>
            <span>{warning.message}</span>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function AuditRecordItem({ record, onDetail }: { record: AuditRecord; onDetail: (record: AuditRecord) => void }) {
  return (
    <article className="iu-audit-event">
      <div className="iu-audit-event__main">
        <time>{formatTimestamp(record.timestamp)}</time>
        <h2>{record.action}</h2>
        <p>{record.details || record.resourceNote || 'Nessun dettaglio testuale registrato.'}</p>
        <div className="iu-audit-event__badges">
          <Badge tone={record.resultTone}>{record.result}</Badge>
          {record.resourceBadgeLabel ? <Badge tone={record.resourceTone}>{record.resourceBadgeLabel}</Badge> : null}
          {record.resourceType ? <Badge tone="neutral">{record.resourceType}</Badge> : null}
        </div>
      </div>
      <aside className="iu-audit-event__side">
        <strong>{record.username}</strong>
        {record.resourceLabel ? <span>{record.resourceLabel}</span> : null}
        {record.resourceId ? <small>ID risorsa: {record.resourceId}</small> : null}
        {record.ip ? <small>IP: {record.ip}</small> : null}
        {record.resourceUrl ? <a href={record.resourceUrl}>Apri risorsa</a> : null}
        <Button type="button" tone="neutral" onClick={() => onDetail(record)}>
          <Eye size={15} />
          Dettaglio
        </Button>
      </aside>
    </article>
  )
}

function DetailPanel({ detail }: { detail: AuditEventDetail | null }) {
  if (!detail) return null
  const payloadRows = Object.entries(detail.payload)
  return (
    <Panel title="Dettaglio evento" subtitle="Dati sensibili filtrati e mostrati in forma leggibile.">
      <div className="iu-audit-detail">
        <div>
          <strong>{detail.action}</strong>
          <span>{formatTimestamp(detail.timestamp)}</span>
        </div>
        <p>{detail.details || 'Nessun dettaglio testuale.'}</p>
        {payloadRows.length ? (
          <dl>
            {payloadRows.map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{typeof value === 'string' || typeof value === 'number' ? String(value) : JSON.stringify(value)}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <EmptyState title="Dettagli non presenti" message="Non sono disponibili dati aggiuntivi per questo evento." />
        )}
      </div>
    </Panel>
  )
}

export function AuditPage() {
  const [data, setData] = useState<AuditPageData>(emptyAuditPage)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')
  const [detail, setDetail] = useState<AuditEventDetail | null>(null)
  const [query, setQuery] = useState('')
  const [result, setResult] = useState('tutti')
  const title = window.location.pathname.toLowerCase().includes('registro-attivita') ? 'Registro attivita' : 'Audit'

  function load() {
    setLoading(true)
    const loader = window.location.pathname.toLowerCase().includes('registro-attivita')
      ? getRegistroAttivitaPage
      : getAuditPage
    loader()
      .then((payload) => {
        setData(payload)
      })
      .finally(() => {
        setLoading(false)
      })
  }

  useEffect(() => {
    let active = true
    const loader = window.location.pathname.toLowerCase().includes('registro-attivita')
      ? getRegistroAttivitaPage
      : getAuditPage
    loader()
      .then((payload) => {
        if (active) setData(payload)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  async function showDetail(record: AuditRecord) {
    setSaving(true)
    setSuccess('')
    setError('')
    const response = await getAuditEventDetail(record.id)
    setSaving(false)
    if (!response.ok || !response.item) {
      setError(response.message)
      return
    }
    setDetail(response.item)
    setSuccess(response.message)
  }

  const visibleRecords = useMemo(
    () => data.records.filter((record) => matchesQuery(record, query.trim(), result)),
    [data.records, query, result],
  )
  const hasData = data.metrics.length > 0 || data.records.length > 0
  const safeActions = data.actions.links.filter((action) => action.method === 'GET' && action.href)

  return (
    <Page
      title={title}
      subtitle="Registro read-only delle attivita applicative e amministrative."
      actions={
        <>
          <Button type="button" tone="primary" onClick={load}>
            <RefreshCw size={16} />
            Aggiorna
          </Button>
          {safeActions.filter((action) => action.id === 'export_csv').map((action) => (
            <ButtonLink href={action.href} tone={actionTone(action)} key={action.id}>
              <Download size={16} />
              {action.label}
            </ButtonLink>
          ))}
        </>
      }
    >
      {loading ? <LoadingState title="Caricamento audit" message="Lettura del registro reale in corso." /> : null}
      {!loading && !hasData ? (
        <EmptyState
          title="Nessun evento audit disponibile"
          message="Il registro non contiene ancora eventi compatibili con i filtri correnti."
        />
      ) : null}
      {!loading && hasData ? (
        <>
          {saving ? <LoadingState title="Caricamento dettaglio audit" message="Lettura dettagli filtrati in corso." /> : null}
          {success ? <div className="iu-audit-state iu-audit-state--success" role="status">{success}</div> : null}
          {error ? <div className="iu-audit-state iu-audit-state--error" role="alert">{error}</div> : null}
          <Warnings data={data} />
          <section className="iu-audit-kpis" aria-label="KPI audit">
            {data.metrics.map((metric) => (
              <KpiCard
                label={metric.label}
                value={metric.value}
                note={metric.note}
                badge={<Badge tone={metric.tone}>{metric.tone}</Badge>}
                key={metric.id}
              />
            ))}
          </section>
          <Panel title="Filtri" subtitle="Ricerca locale sui record gia caricati.">
            <div className="iu-audit-filters">
              <label className="iu-audit-search">
                <span>Testo</span>
                <div>
                  <Search size={16} />
                  <input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Cerca per utente, azione, risorsa o dettaglio"
                  />
                </div>
              </label>
              <label className="iu-audit-select">
                <span>Esito</span>
                <select value={result} onChange={(event) => setResult(event.target.value)}>
                  <option value="tutti">Tutti</option>
                  <option value="ok">OK</option>
                  <option value="negato">Negato</option>
                  <option value="errore">Errore</option>
                </select>
              </label>
              <Button type="button" tone="neutral" onClick={() => { setQuery(''); setResult('tutti') }}>
                Reimposta
              </Button>
            </div>
          </Panel>
          <Panel title="Eventi attivita" subtitle={`${visibleRecords.length} record visualizzati`}>
            {visibleRecords.length ? (
              <div className="iu-audit-events">
                {visibleRecords.map((record) => <AuditRecordItem record={record} onDetail={showDetail} key={record.id} />)}
              </div>
            ) : (
              <EmptyState title="Nessun evento nei filtri correnti" />
            )}
          </Panel>
          <DetailPanel detail={detail} />
          <section className="iu-audit-grid" aria-label="Distribuzioni audit">
            {data.sections.filter((section) => section.items.length > 0).map((section) => (
              <Panel title={section.title} subtitle={section.kind} key={section.id}>
                <div className="iu-audit-list">
                  {section.items.slice(0, 8).map((item) => (
                    <div className="iu-audit-list__item" key={item.id}>
                      <span>{item.label}</span>
                      <strong>{item.value}</strong>
                      {item.note ? <small>{item.note}</small> : null}
                    </div>
                  ))}
                </div>
              </Panel>
            ))}
          </section>
          <Panel title="Presidio dati" subtitle="Origine dati e protezioni operative.">
            <div className="iu-audit-contract">
              <span>Fonte: {displaySourceLabel(data.source)}</span>
              <span>Generato: {data.generated_at || 'non disponibile'}</span>
              <span>Azioni: {displayWritesLabel(data.contracts.writes)}</span>
              <span>Mock fallback: {data.contracts.mock_fallback ? 'si' : 'no'}</span>
              <span>Dettagli filtrati: si</span>
            </div>
          </Panel>
        </>
      ) : null}
    </Page>
  )
}
