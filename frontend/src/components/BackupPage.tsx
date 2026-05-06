import { useEffect, useState } from 'react'
import { Archive, RefreshCw } from 'lucide-react'
import {
  emptyBackupPage,
  getBackupPage,
  type BackupPageData,
  type BackupRecord,
} from '../backupData'
import { Badge } from '../ui/Badge'
import { ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LegacyPostForm } from '../ui/LegacyPostForm'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import './BackupPage.css'

function formatValue(value: string | number): string {
  if (typeof value === 'number') return new Intl.NumberFormat('it-IT').format(value)
  return value
}

function formatDate(value: string): string {
  if (!value) return 'Data non indicata'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value.replace('T', ' ').slice(0, 16)
  return new Intl.DateTimeFormat('it-IT', { dateStyle: 'short', timeStyle: 'short' }).format(parsed)
}

function Warnings({ data }: { data: BackupPageData }) {
  if (!data.warnings.length) return null
  return (
    <Panel title="Avvisi operativi">
      <div className="iu-backup-warnings">
        {data.warnings.map((warning) => (
          <div className="iu-backup-warning" key={`${warning.code}-${warning.message}`}>
            <Badge tone="warning">{warning.code}</Badge>
            <span>{warning.message}</span>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function BackupRecordItem({ record }: { record: BackupRecord }) {
  return (
    <article className="iu-backup-record">
      <div className="iu-backup-record__main">
        <time>{formatDate(record.timestamp)}</time>
        <strong>{record.fileName || record.id}</strong>
        <span>{record.type} · {record.filesCount} file · {record.sizeMb} MB</span>
        {record.note ? <small>{record.note}</small> : null}
        {record.error ? <small>{record.error}</small> : null}
      </div>
      <div className="iu-backup-record__state">
        <Badge tone={record.statusTone}>{record.status || 'stato non indicato'}</Badge>
        {record.encrypted ? <Badge tone="warning">Protetto</Badge> : <Badge tone="neutral">Non cifrato</Badge>}
        {record.components.length ? <span>{record.components.join(', ')}</span> : <span>Componenti non indicati</span>}
      </div>
      <div className="iu-backup-record__actions">
        {record.downloadHref ? <ButtonLink href={record.downloadHref} tone="neutral">Scarica legacy</ButtonLink> : null}
        {record.restoreHref ? <ButtonLink href={record.restoreHref} tone="warning">Ripristino legacy</ButtonLink> : null}
        {record.verifyAction ? (
          <LegacyPostForm
            action={record.verifyAction}
            submitLabel="Verifica legacy"
            fields={[]}
          />
        ) : null}
      </div>
    </article>
  )
}

export function BackupPage() {
  const [data, setData] = useState<BackupPageData>(emptyBackupPage)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    getBackupPage()
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

  const backupForm = data.forms.find((form) => form.id === 'esegui_backup')
  const hasData = data.metrics.length > 0 || data.records.length > 0 || data.sections.some((section) => section.items.length > 0)

  return (
    <Page
      title="Backup"
      subtitle="Superficie preparatoria read-only: la route ufficiale resta servita dal legacy gate."
      actions={
        <>
          <ButtonLink href="/backup?_legacy=1" tone="primary">
            <Archive size={16} />
            Apri backup legacy
          </ButtonLink>
          <ButtonLink href="/backup?_legacy=1" tone="neutral">
            <RefreshCw size={16} />
            Aggiorna legacy
          </ButtonLink>
        </>
      }
    >
      {loading ? <LoadingState title="Caricamento backup" message="Lettura del registro backup reale in corso." /> : null}
      {!loading && !hasData ? (
        <EmptyState
          title="Nessun backup disponibile"
          message="Il registro backup non contiene ancora copie visualizzabili."
          action={<ButtonLink href="/backup?_legacy=1" tone="primary">Apri modulo legacy</ButtonLink>}
        />
      ) : null}
      {!loading && hasData ? (
        <>
          <section className="iu-backup-banner" aria-label="Stato migrazione backup">
            <strong>Backup ancora servito da legacy gate in questa tranche</strong>
            <span>React espone API e pagina preparatoria, ma operazioni tecniche, restore e download restano sui flussi legacy.</span>
          </section>
          <Warnings data={data} />
          <section className="iu-backup-kpis" aria-label="KPI backup">
            {data.metrics.map((metric) => (
              <KpiCard
                label={metric.label}
                value={formatValue(metric.value)}
                note={metric.note}
                badge={<Badge tone={metric.tone}>{metric.tone}</Badge>}
                key={metric.id}
              />
            ))}
          </section>
          <section className="iu-backup-grid" aria-label="Sezioni backup">
            {data.sections.map((section) => (
              <Panel title={section.title} subtitle={section.kind} key={section.id}>
                {section.items.length ? (
                  <div className="iu-backup-list">
                    {section.items.map((item) => (
                      <div className="iu-backup-list__item" key={item.id}>
                        <span>{item.label}</span>
                        <strong>{formatValue(item.value)}</strong>
                        {item.note ? <small>{item.note}</small> : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState title={section.emptyMessage} />
                )}
              </Panel>
            ))}
          </section>
          <Panel title="Azioni legacy" subtitle="Form standard verso route Flask esistenti, senza fetch POST.">
            {backupForm ? (
              <LegacyPostForm
                action={backupForm.action}
                csrfField={backupForm.csrfField}
                submitLabel={backupForm.submitLabel}
                title={backupForm.title}
                description={backupForm.description}
                fields={backupForm.fields}
                disabled={backupForm.enabled === false}
              />
            ) : (
              <EmptyState title="Nessuna azione backup esposta" />
            )}
          </Panel>
          <Panel title="Storico backup" subtitle={`${data.records.length} copie dal registro reale`}>
            {data.records.length ? (
              <div className="iu-backup-records">
                {data.records.map((record) => <BackupRecordItem record={record} key={record.id} />)}
              </div>
            ) : (
              <EmptyState title="Nessuna copia nello storico" />
            )}
          </Panel>
          <Panel title="Contratto dati" subtitle="Route bloccata dal gate legacy in questa tranche.">
            <div className="iu-backup-contract">
              <span>Fonte: {data.source || 'non indicata'}</span>
              <span>Generato: {data.generated_at || 'non disponibile'}</span>
              <span>Scritture: {data.contracts.writes}</span>
              <span>Owner route: {data.contracts.route_owner}</span>
              <span>Mock fallback: {data.contracts.mock_fallback ? 'si' : 'no'}</span>
            </div>
          </Panel>
        </>
      ) : null}
    </Page>
  )
}
