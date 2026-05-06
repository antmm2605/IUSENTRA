import { useEffect, useMemo, useState } from 'react'
import { ExternalLink, Globe2, Mail, PenLine, RefreshCw } from 'lucide-react'
import {
  emptySitoStudioPage,
  getSitoStudioContattiPage,
  getSitoStudioPage,
  type SitoStudioPageData,
  type SitoStudioRecord,
} from '../sitoStudioData'
import { Badge } from '../ui/Badge'
import { ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LegacyPostForm } from '../ui/LegacyPostForm'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import './SitoStudioPage.css'

function routeKey(): string {
  return (window.location.pathname.replace(/\/+$/, '') || '/').toLowerCase()
}

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

function WarningPanel({ data }: { data: SitoStudioPageData }) {
  if (!data.warnings.length) return null
  return (
    <Panel title="Avvisi operativi">
      <div className="iu-sito-warnings">
        {data.warnings.map((warning) => (
          <div className="iu-sito-warning" key={`${warning.code}-${warning.message}`}>
            <Badge tone="warning">{warning.code}</Badge>
            <span>{warning.message}</span>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function SiteStatus({ data }: { data: SitoStudioPageData }) {
  const site = data.site
  return (
    <Panel title="Stato sito" subtitle={site.publicSlug || 'Slug pubblico non indicato'}>
      <div className="iu-sito-status">
        <div>
          <span>Nome sito</span>
          <strong>{site.siteName || site.title || site.studioName || 'Sito Studio'}</strong>
        </div>
        <div>
          <span>Pubblicazione</span>
          <Badge tone={site.published ? 'success' : 'warning'}>{site.published ? 'pubblicato' : 'bozza'}</Badge>
        </div>
        <div>
          <span>Operativita</span>
          <Badge tone={site.active ? 'success' : 'warning'}>{site.active ? 'attivo' : 'disattivo'}</Badge>
        </div>
        <div>
          <span>Contatto pubblico</span>
          <strong>{site.contactEmail || site.contactPhone || 'non configurato'}</strong>
        </div>
        <div>
          <span>Sede</span>
          <strong>{[site.address, site.city, site.province].filter(Boolean).join(', ') || 'non indicata'}</strong>
        </div>
        <div>
          <span>Aggiornato</span>
          <strong>{formatDate(site.updatedAt)}</strong>
        </div>
      </div>
    </Panel>
  )
}

function RecordMeta({ record }: { record: SitoStudioRecord }) {
  const visible = record.meta.filter((entry) => entry.value)
  if (!visible.length) return null
  return (
    <dl className="iu-sito-record__meta">
      {visible.map((entry) => (
        <div key={`${record.id}-${entry.label}-${entry.value}`}>
          <dt>{entry.label}</dt>
          <dd>{entry.label.toLowerCase() === 'data' ? formatDate(entry.value) : entry.value}</dd>
        </div>
      ))}
    </dl>
  )
}

function LegacyForms({ record }: { record: SitoStudioRecord }) {
  if (!record.forms.length) return null
  return (
    <div className="iu-sito-record__forms">
      {record.forms.map((form) => (
        <LegacyPostForm
          action={form.action}
          csrfField={form.csrfField || undefined}
          submitLabel={form.submitLabel}
          title={form.title}
          description={form.description}
          fields={form.fields}
          disabled={form.enabled === false}
          key={form.id}
        />
      ))}
    </div>
  )
}

function RecordCard({ record }: { record: SitoStudioRecord }) {
  return (
    <article className="iu-sito-record">
      <header className="iu-sito-record__head">
        <div>
          <span>{record.kind}</span>
          <h3>{record.title}</h3>
          {record.subtitle ? <p>{record.subtitle}</p> : null}
        </div>
        <Badge tone={record.statusTone}>{record.status || 'stato non indicato'}</Badge>
      </header>
      <RecordMeta record={record} />
      <div className="iu-sito-record__actions">
        {record.href ? (
          <ButtonLink href={record.href} tone="neutral">
            <ExternalLink size={15} />
            Apri percorso
          </ButtonLink>
        ) : null}
        <LegacyForms record={record} />
      </div>
    </article>
  )
}

function RecordsPanel({ title, records, emptyTitle }: { title: string; records: SitoStudioRecord[]; emptyTitle: string }) {
  return (
    <Panel title={title} subtitle={`${records.length} elementi reali`}>
      {records.length ? (
        <div className="iu-sito-records">
          {records.map((record) => <RecordCard record={record} key={`${record.kind}-${record.id}-${record.title}`} />)}
        </div>
      ) : (
        <EmptyState title={emptyTitle} />
      )}
    </Panel>
  )
}

function DashboardContent({ data }: { data: SitoStudioPageData }) {
  const publicAction = data.actions.find((action) => action.id === 'public' && action.href)
  const contentRecords = data.records.filter((record) => ['page', 'article', 'service'].includes(record.kind))
  const peopleRecords = data.records.filter((record) => ['professional', 'office'].includes(record.kind))
  const requestRecords = data.records.filter((record) => ['contact', 'booking'].includes(record.kind))

  return (
    <>
      <section className="iu-sito-banner" aria-label="Stato migrazione Sito Studio">
        <strong>Sito Studio servito dalla shell React</strong>
        <span>Builder, pubblicazione avanzata e gestione tecnica restano sulle route legacy auditabili.</span>
      </section>
      <WarningPanel data={data} />
      <section className="iu-sito-kpis" aria-label="KPI Sito Studio">
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
      <SiteStatus data={data} />
      <section className="iu-sito-grid" aria-label="Sezioni Sito Studio">
        {data.sections.map((section) => (
          <Panel title={section.title} subtitle={section.kind} key={section.id}>
            {section.items.length ? (
              <div className="iu-sito-list">
                {section.items.map((item) => (
                  <div className="iu-sito-list__item" key={item.id}>
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
      <RecordsPanel title="Contenuti pubblici" records={contentRecords} emptyTitle="Nessun contenuto pubblico configurato" />
      <RecordsPanel title="Studio e sedi" records={peopleRecords} emptyTitle="Nessun profilo studio configurato" />
      <RecordsPanel title="Ultime richieste" records={requestRecords} emptyTitle="Nessuna richiesta recente" />
      <Panel
        title="Azioni operative"
        subtitle="Solo link GET o form legacy, senza scritture via fetch."
        actions={publicAction ? <ButtonLink href={publicAction.href} tone="success" target="_blank" rel="noopener">Apri sito pubblico</ButtonLink> : null}
      >
        <div className="iu-sito-actions">
          {data.actions.filter((action) => action.id !== 'public').map((action) => (
            <ButtonLink href={action.href} tone={action.tone === 'info' ? 'neutral' : action.tone} key={action.id}>
              {action.id === 'builder' ? <PenLine size={15} /> : <ExternalLink size={15} />}
              {action.label}
            </ButtonLink>
          ))}
        </div>
      </Panel>
    </>
  )
}

function ContactsContent({ data }: { data: SitoStudioPageData }) {
  const contacts = data.records.filter((record) => record.kind === 'contact')
  const bookings = data.records.filter((record) => record.kind === 'booking')

  return (
    <>
      <section className="iu-sito-banner" aria-label="Contatti e prenotazioni">
        <strong>Contatti e prenotazioni reali</strong>
        <span>Le azioni di gestione inviano form standard ai percorsi legacy esistenti.</span>
      </section>
      <WarningPanel data={data} />
      <RecordsPanel title="Richieste contatto" records={contacts} emptyTitle="Nessuna richiesta contatto ricevuta" />
      <RecordsPanel title="Prenotazioni" records={bookings} emptyTitle="Nessuna prenotazione ricevuta" />
    </>
  )
}

export function SitoStudioPage() {
  const contactsRoute = routeKey() === '/sito-studio/contatti'
  const [data, setData] = useState<SitoStudioPageData>(emptySitoStudioPage)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    const loader = contactsRoute ? getSitoStudioContattiPage : getSitoStudioPage
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
  }, [contactsRoute])

  const hasData = useMemo(
    () => data.metrics.length > 0 || data.records.length > 0 || data.sections.some((section) => section.items.length > 0),
    [data],
  )

  return (
    <Page
      title={contactsRoute ? 'Contatti Sito Studio' : 'Sito Studio'}
      subtitle={contactsRoute ? 'Richieste contatto e prenotazioni dal sito pubblico.' : 'Dashboard React dei contenuti e dello stato pubblico dello studio.'}
      actions={
        <>
          <ButtonLink href="/sito-studio?_legacy=1" tone="neutral">
            <Globe2 size={16} />
            Dashboard legacy
          </ButtonLink>
          <ButtonLink href={contactsRoute ? '/sito-studio/contatti?_legacy=1' : '/sito-studio/builder?_legacy=1'} tone="primary">
            {contactsRoute ? <Mail size={16} /> : <PenLine size={16} />}
            {contactsRoute ? 'Contatti legacy' : 'Builder legacy'}
          </ButtonLink>
          <ButtonLink href={contactsRoute ? '/sito-studio/contatti' : '/sito-studio'} tone="neutral">
            <RefreshCw size={16} />
            Aggiorna
          </ButtonLink>
        </>
      }
    >
      {loading ? <LoadingState title="Caricamento Sito Studio" message="Lettura dei dati reali del sito in corso." /> : null}
      {!loading && !hasData ? (
        <EmptyState
          title="Nessun dato Sito Studio disponibile"
          message="Il repository del sito non espone ancora contenuti o richieste visualizzabili."
          action={<ButtonLink href="/sito-studio?_legacy=1" tone="primary">Apri dashboard legacy</ButtonLink>}
        />
      ) : null}
      {!loading && hasData ? (contactsRoute ? <ContactsContent data={data} /> : <DashboardContent data={data} />) : null}
      {!loading && hasData ? (
        <Panel title="Contratto dati" subtitle="Route GET servita dalla shell React, scritture conservate sui percorsi legacy.">
          <div className="iu-sito-contract">
            <span>Fonte: {data.source || 'non indicata'}</span>
            <span>Generato: {data.generated_at || 'non disponibile'}</span>
            <span>Scritture: {data.contracts.writes}</span>
            <span>Owner route: {data.contracts.route_owner}</span>
            <span>Mock fallback: {data.contracts.mock_fallback ? 'si' : 'no'}</span>
          </div>
        </Panel>
      ) : null}
    </Page>
  )
}
