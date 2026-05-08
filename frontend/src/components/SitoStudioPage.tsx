import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, ExternalLink, Globe2, Link2, Mail, PenLine, RefreshCw, XCircle } from 'lucide-react'
import {
  emptySitoStudioContattiPage,
  emptySitoStudioPage,
  getSitoStudioContattiPage,
  getSitoStudioPage,
  linkSitoContatto,
  updateSitoBookingStatus,
  type SitoBookingRow,
  type SitoContattoRow,
  type SitoStudioContattiPageData,
  type SitoStudioPageData,
} from '../sitoStudioData'
import { buttonTone } from '../studioData'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
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

function WarningList({ warnings }: { warnings: SitoStudioPageData['warnings'] }) {
  if (!warnings.length) return null
  return (
    <Panel title="Avvisi operativi">
      <div className="iu-sito-warnings">
        {warnings.map((warning) => (
          <div className="iu-sito-warning" key={`${warning.code}-${warning.message}`}>
            <Badge tone="warning">{warning.code}</Badge>
            <span>{warning.message}</span>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function DashboardContent({ data }: { data: SitoStudioPageData }) {
  const content = data.pages.filter((item) => ['page', 'article', 'service'].includes(item.kind))
  const studio = data.pages.filter((item) => ['professional', 'office'].includes(item.kind))
  const publicAction = data.actions.find((action) => action.id === 'public' && data.preview.safe)

  return (
    <>
      <section className="iu-sito-banner" aria-label="Sito Studio operativo">
        <strong>Sito Studio React operativo</strong>
        <span>Dashboard, contatti e prenotazioni leggono dati reali; builder e pubblicazione avanzata restano legacy protetti.</span>
      </section>
      <WarningList warnings={data.warnings} />
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
      <Panel title="Stato pubblicazione" subtitle={data.site.publicSlug || 'Slug pubblico non indicato'}>
        <div className="iu-sito-status">
          <div>
            <span>Nome sito</span>
            <strong>{data.site.siteName || data.site.title || data.site.studioName || 'Sito Studio'}</strong>
          </div>
          <div>
            <span>Pubblicazione</span>
            <Badge tone={data.site.published ? 'success' : 'warning'}>{data.site.published ? 'pubblicato' : 'bozza'}</Badge>
          </div>
          <div>
            <span>Operativita</span>
            <Badge tone={data.site.active ? 'success' : 'warning'}>{data.site.active ? 'attivo' : 'disattivo'}</Badge>
          </div>
          <div>
            <span>Contatto pubblico</span>
            <strong>{data.site.contactEmail || data.site.contactPhone || 'non configurato'}</strong>
          </div>
          <div>
            <span>Sede</span>
            <strong>{[data.site.address, data.site.city, data.site.province].filter(Boolean).join(', ') || 'non indicata'}</strong>
          </div>
          <div>
            <span>Aggiornato</span>
            <strong>{formatDate(data.site.updatedAt)}</strong>
          </div>
        </div>
      </Panel>
      <Panel
        title="Contenuti pubblici sicuri"
        subtitle={`${content.length} contenuti letti dal repository`}
        actions={publicAction ? <ButtonLink href={publicAction.href} tone="success" target="_blank" rel="noopener">Anteprima pubblica</ButtonLink> : null}
      >
        {content.length ? (
          <div className="iu-sito-records">
            {content.map((item) => (
              <article className="iu-sito-record" key={`${item.kind}-${item.id}`}>
                <header className="iu-sito-record__head">
                  <div>
                    <span>{item.kind}</span>
                    <h3>{item.title}</h3>
                    {item.subtitle ? <p>{item.subtitle}</p> : null}
                  </div>
                  <Badge tone={item.statusTone}>{item.status || 'stato non indicato'}</Badge>
                </header>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState title="Nessun contenuto pubblico configurato" />
        )}
      </Panel>
      <Panel title="Studio e sedi" subtitle={`${studio.length} elementi pubblici`}>
        {studio.length ? (
          <div className="iu-sito-records">
            {studio.map((item) => (
              <article className="iu-sito-record" key={`${item.kind}-${item.id}`}>
                <header className="iu-sito-record__head">
                  <div>
                    <span>{item.kind}</span>
                    <h3>{item.title}</h3>
                    {item.subtitle ? <p>{item.subtitle}</p> : null}
                  </div>
                  <Badge tone={item.statusTone}>{item.status || 'stato non indicato'}</Badge>
                </header>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState title="Nessun profilo pubblico configurato" />
        )}
      </Panel>
      <Panel title="Azioni operative">
        <div className="iu-sito-actions">
          {data.actions.filter((action) => !action.protected && action.id !== 'public-disabled').map((action) => (
            <ButtonLink href={action.href} tone={buttonTone(action.tone)} key={action.id}>
              {action.id === 'public' ? <Globe2 size={15} /> : <ExternalLink size={15} />}
              {action.label}
            </ButtonLink>
          ))}
        </div>
      </Panel>
      <Panel title="Rollback tecnico" subtitle="Builder/editor/pubblicazione avanzata restano legacy protetti">
        <div className="iu-sito-actions">
          {data.actions.filter((action) => action.protected).map((action) => (
            <ButtonLink href={action.href} tone={buttonTone(action.tone)} key={action.id}>
              {action.id === 'builder' ? <PenLine size={15} /> : <ExternalLink size={15} />}
              {action.label}
            </ButtonLink>
          ))}
        </div>
      </Panel>
    </>
  )
}

function ContactCard({
  contact,
  clients,
  canLink,
  selectedClient,
  saving,
  onClientChange,
  onCreateLead,
  onLinkClient,
}: {
  contact: SitoContattoRow
  clients: SitoStudioContattiPageData['clients']
  canLink: boolean
  selectedClient: string
  saving: boolean
  onClientChange: (id: string, value: string) => void
  onCreateLead: (id: string) => void
  onLinkClient: (id: string) => void
}) {
  const disabledReason = contact.leadClienteId ? 'Cliente gia collegato' : 'Azione non supportata per questo profilo'
  return (
    <article className="iu-sito-contact">
      <header className="iu-sito-contact__head">
        <div>
          <span>Richiesta contatto</span>
          <h3>{contact.fullName || 'Nominativo non indicato'}</h3>
          {contact.subject ? <p>{contact.subject}</p> : null}
        </div>
        <Badge tone={contact.statusTone}>{contact.statusLabel || contact.status}</Badge>
      </header>
      <dl className="iu-sito-contact__meta">
        <div>
          <dt>Email</dt>
          <dd>{contact.email || 'non indicata'}</dd>
        </div>
        <div>
          <dt>Telefono</dt>
          <dd>{contact.phone || 'non indicato'}</dd>
        </div>
        <div>
          <dt>Ricezione</dt>
          <dd>{formatDate(contact.createdAt)}</dd>
        </div>
      </dl>
      {contact.message ? <p className="iu-sito-contact__message">{contact.message}</p> : null}
      <div className="iu-sito-contact__actions">
        {contact.clientHref ? (
          <ButtonLink href={contact.clientHref} tone="success">
            <ExternalLink size={15} />
            Apri cliente
          </ButtonLink>
        ) : null}
        <Button
          tone="primary"
          disabled={!canLink || !contact.actions.canLinkClient || saving}
          onClick={() => onCreateLead(contact.id)}
          title={!canLink || !contact.actions.canLinkClient ? disabledReason : undefined}
        >
          <Link2 size={15} />
          {saving ? 'Salvataggio' : 'Crea cliente'}
        </Button>
        {clients.length ? (
          <>
            <select
              className="iu-sito-select"
              value={selectedClient}
              disabled={!canLink || !contact.actions.canLinkClient || saving}
              onChange={(event) => onClientChange(contact.id, event.target.value)}
              aria-label="Cliente da collegare"
            >
              <option value="">Seleziona cliente</option>
              {clients.map((client) => (
                <option value={client.id} key={client.id}>{client.label}</option>
              ))}
            </select>
            <Button
              tone="neutral"
              disabled={!canLink || !contact.actions.canLinkClient || !selectedClient || saving}
              onClick={() => onLinkClient(contact.id)}
              title={!canLink || !contact.actions.canLinkClient ? disabledReason : undefined}
            >
              Collega cliente
            </Button>
          </>
        ) : null}
        <Button tone="neutral" disabled title="Nota interna non supportata dal backend legacy corrente">
          Nota interna
        </Button>
        <Button tone="neutral" disabled title="Archiviazione non supportata dal backend legacy corrente">
          Archivia
        </Button>
      </div>
    </article>
  )
}

function BookingCard({
  booking,
  canUpdate,
  saving,
  onUpdate,
}: {
  booking: SitoBookingRow
  canUpdate: boolean
  saving: boolean
  onUpdate: (id: string, status: 'approved' | 'rejected') => void
}) {
  return (
    <article className="iu-sito-contact">
      <header className="iu-sito-contact__head">
        <div>
          <span>Prenotazione</span>
          <h3>{booking.customerName || 'Nominativo non indicato'}</h3>
          {booking.subject ? <p>{booking.subject}</p> : null}
        </div>
        <Badge tone={booking.statusTone}>{booking.statusLabel || booking.status}</Badge>
      </header>
      <dl className="iu-sito-contact__meta">
        <div>
          <dt>Email</dt>
          <dd>{booking.email || 'non indicata'}</dd>
        </div>
        <div>
          <dt>Telefono</dt>
          <dd>{booking.phone || 'non indicato'}</dd>
        </div>
        <div>
          <dt>Richiesta</dt>
          <dd>{booking.requestedAt || 'non indicata'}</dd>
        </div>
        <div>
          <dt>Sede</dt>
          <dd>{booking.officeName || 'non indicata'}</dd>
        </div>
      </dl>
      {booking.notes ? <p className="iu-sito-contact__message">{booking.notes}</p> : null}
      <div className="iu-sito-contact__actions">
        <Button
          tone="success"
          disabled={!canUpdate || !booking.actions.canUpdateStatus || saving}
          onClick={() => onUpdate(booking.id, 'approved')}
          title={!canUpdate || !booking.actions.canUpdateStatus ? 'Prenotazione non modificabile' : undefined}
        >
          <CheckCircle2 size={15} />
          Approva
        </Button>
        <Button
          tone="warning"
          disabled={!canUpdate || !booking.actions.canUpdateStatus || saving}
          onClick={() => onUpdate(booking.id, 'rejected')}
          title={!canUpdate || !booking.actions.canUpdateStatus ? 'Prenotazione non modificabile' : undefined}
        >
          <XCircle size={15} />
          Rifiuta
        </Button>
      </div>
    </article>
  )
}

function ContactsContent({ data, reload }: { data: SitoStudioContattiPageData; reload: () => void }) {
  const [query, setQuery] = useState('')
  const [selectedClients, setSelectedClients] = useState<Record<string, string>>({})
  const [savingId, setSavingId] = useState('')
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')
  const [validation, setValidation] = useState<Record<string, string>>({})
  const visibleContacts = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return data.contacts
    return data.contacts.filter((contact) => (
      `${contact.fullName} ${contact.email} ${contact.phone} ${contact.subject} ${contact.statusLabel}`.toLowerCase().includes(needle)
    ))
  }, [data.contacts, query])

  function updateClientSelection(id: string, value: string) {
    setSelectedClients((current) => ({ ...current, [id]: value }))
  }

  async function createLead(id: string) {
    setSavingId(`contact-${id}`)
    setError('')
    setSuccess('')
    setValidation({})
    const result = await linkSitoContatto(id, { mode: 'create_lead' })
    setSavingId('')
    if (result.ok) {
      setSuccess(result.message)
      reload()
      return
    }
    setError(result.message)
    setValidation(result.errors)
  }

  async function linkClient(id: string) {
    const clienteId = selectedClients[id]
    if (!clienteId) {
      setValidation({ cliente_id: 'Seleziona un cliente.' })
      return
    }
    setSavingId(`contact-${id}`)
    setError('')
    setSuccess('')
    setValidation({})
    const result = await linkSitoContatto(id, { cliente_id: clienteId })
    setSavingId('')
    if (result.ok) {
      setSuccess(result.message)
      reload()
      return
    }
    setError(result.message)
    setValidation(result.errors)
  }

  async function updateBooking(id: string, status: 'approved' | 'rejected') {
    const confirmed = status === 'approved'
      ? window.confirm('Confermi approvazione della prenotazione?')
      : window.confirm('Confermi rifiuto della prenotazione?')
    if (!confirmed) return
    setSavingId(`booking-${id}`)
    setError('')
    setSuccess('')
    setValidation({})
    const result = await updateSitoBookingStatus(id, status)
    setSavingId('')
    if (result.ok) {
      setSuccess(result.message)
      reload()
      return
    }
    setError(result.message)
    setValidation(result.errors)
  }

  return (
    <>
      <section className="iu-sito-banner" aria-label="Contatti e prenotazioni">
        <strong>Contatti e prenotazioni reali</strong>
        <span>Le azioni abilitate usano API JSON con sessione, CSRF e audit legacy conservato.</span>
      </section>
      <WarningList warnings={data.warnings} />
      {success ? <div className="iu-sito-flash iu-sito-flash--success">{success}</div> : null}
      {error ? <div className="iu-sito-flash iu-sito-flash--danger">{error}</div> : null}
      {Object.keys(validation).length ? (
        <div className="iu-sito-flash iu-sito-flash--warning">
          {Object.entries(validation).map(([key, message]) => <span key={key}>{message}</span>)}
        </div>
      ) : null}
      <Panel title="Ricerca contatti" subtitle={`${visibleContacts.length} richieste visibili`}>
        <input
          className="iu-sito-input"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Cerca per nominativo, email, telefono, oggetto o stato"
        />
      </Panel>
      <Panel title="Richieste contatto" subtitle={`${data.contacts.length} richieste reali`}>
        {visibleContacts.length ? (
          <div className="iu-sito-records">
            {visibleContacts.map((contact) => (
              <ContactCard
                contact={contact}
                clients={data.clients}
                canLink={data.actions.canLinkClient}
                selectedClient={selectedClients[contact.id] || ''}
                saving={savingId === `contact-${contact.id}`}
                onClientChange={updateClientSelection}
                onCreateLead={createLead}
                onLinkClient={linkClient}
                key={contact.id}
              />
            ))}
          </div>
        ) : (
          <EmptyState title="Nessuna richiesta contatto ricevuta" />
        )}
      </Panel>
      <Panel title="Prenotazioni" subtitle={`${data.bookings.length} richieste reali`}>
        {data.bookings.length ? (
          <div className="iu-sito-records">
            {data.bookings.map((booking) => (
              <BookingCard
                booking={booking}
                canUpdate={data.actions.canUpdateBookingStatus}
                saving={savingId === `booking-${booking.id}`}
                onUpdate={updateBooking}
                key={booking.id}
              />
            ))}
          </div>
        ) : (
          <EmptyState title="Nessuna prenotazione ricevuta" />
        )}
      </Panel>
      {data.actions.rollback ? (
        <Panel title="Rollback tecnico" subtitle={data.actions.unsupportedReason || 'Percorso legacy disponibile solo come fallback tecnico'}>
          <div className="iu-sito-actions">
            <ButtonLink href={data.actions.rollback.href} tone="neutral">
              <ExternalLink size={15} />
              {data.actions.rollback.label}
            </ButtonLink>
          </div>
        </Panel>
      ) : null}
    </>
  )
}

function ContractPanel({ data }: { data: SitoStudioPageData | SitoStudioContattiPageData }) {
  return (
    <Panel title="Contratto dati" subtitle="Route servita dalla shell React con JSON backend.">
      <div className="iu-sito-contract">
        <span>Fonte: {data.source || 'non indicata'}</span>
        <span>Generato: {data.generated_at || 'non disponibile'}</span>
        <span>Scritture: {data.contracts.writes}</span>
        <span>Owner route: {data.contracts.route_owner}</span>
        <span>Operativo: {data.contracts.operational ? 'si' : 'no'}</span>
        <span>Mock fallback: {data.contracts.mock_fallback ? 'si' : 'no'}</span>
      </div>
    </Panel>
  )
}

export function SitoStudioPage() {
  const contactsRoute = routeKey() === '/sito-studio/contatti'
  const [dashboardData, setDashboardData] = useState<SitoStudioPageData>(emptySitoStudioPage)
  const [contactsData, setContactsData] = useState<SitoStudioContattiPageData>(emptySitoStudioContattiPage)
  const [loading, setLoading] = useState(true)
  const [reloadCounter, setReloadCounter] = useState(0)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    const loader = contactsRoute ? getSitoStudioContattiPage : getSitoStudioPage
    loader()
      .then((payload) => {
        if (!active) return
        if (contactsRoute) {
          const contactsPayload = payload as SitoStudioContattiPageData
          setContactsData(contactsPayload)
          setError(contactsPayload.ok ? '' : contactsPayload.warnings[0]?.message || 'Contatti Sito Studio non disponibili.')
          return
        }
        const dashboardPayload = payload as SitoStudioPageData
        setDashboardData(dashboardPayload)
        setError(dashboardPayload.ok ? '' : dashboardPayload.warnings[0]?.message || 'Sito Studio non disponibile.')
      })
      .catch(() => {
        if (active) setError(contactsRoute ? 'Contatti Sito Studio non disponibili.' : 'Sito Studio non disponibile.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [contactsRoute, reloadCounter])

  const dashboardHasData = dashboardData.metrics.length > 0 || dashboardData.pages.length > 0
  const contactsHasData = contactsData.contacts.length > 0 || contactsData.bookings.length > 0
  const hasData = contactsRoute ? contactsHasData : dashboardHasData
  const pageTitle = contactsRoute ? 'Contatti Sito Studio' : 'Sito Studio'

  return (
    <Page
      title={pageTitle}
      subtitle={contactsRoute ? 'Richieste contatto e prenotazioni gestite con API JSON sicure.' : 'Dashboard operativa del sito pubblico dello studio.'}
      actions={
        <>
          <ButtonLink href={contactsRoute ? '/sito-studio' : '/sito-studio/contatti'} tone="primary">
            {contactsRoute ? <Globe2 size={16} /> : <Mail size={16} />}
            {contactsRoute ? 'Dashboard sito' : 'Contatti sito'}
          </ButtonLink>
          <ButtonLink href={contactsRoute ? '/sito-studio/contatti' : '/sito-studio'} tone="neutral">
            <RefreshCw size={16} />
            Aggiorna
          </ButtonLink>
        </>
      }
    >
      {loading ? <LoadingState title="Caricamento Sito Studio" message="Lettura dei dati reali del sito in corso." /> : null}
      {!loading && error ? (
        <EmptyState
          title={contactsRoute ? 'Contatti non disponibili' : 'Sito Studio non disponibile'}
          message={error}
          action={<ButtonLink href={contactsRoute ? '/sito-studio' : '/sito-studio/contatti'} tone="primary">{contactsRoute ? 'Dashboard sito' : 'Contatti sito'}</ButtonLink>}
        />
      ) : null}
      {!loading && !error && !hasData ? (
        <EmptyState
          title={contactsRoute ? 'Nessun contatto o prenotazione' : 'Nessun dato Sito Studio disponibile'}
          message={contactsRoute ? 'Il repository non contiene richieste visualizzabili.' : 'Il repository del sito non espone ancora contenuti o KPI visualizzabili.'}
          action={<ButtonLink href={contactsRoute ? '/sito-studio' : '/sito-studio/contatti'} tone="primary">{contactsRoute ? 'Dashboard sito' : 'Contatti sito'}</ButtonLink>}
        />
      ) : null}
      {!loading && !error && hasData ? (
        contactsRoute
          ? <ContactsContent data={contactsData} reload={() => setReloadCounter((value) => value + 1)} />
          : <DashboardContent data={dashboardData} />
      ) : null}
      {!loading && !error && hasData ? <ContractPanel data={contactsRoute ? contactsData : dashboardData} /> : null}
    </Page>
  )
}
