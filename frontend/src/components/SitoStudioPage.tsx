import { useEffect, useMemo, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { ArrowLeft, Bot, CalendarDays, CheckCircle2, ExternalLink, FileText, Globe2, ImagePlus, Link2, Mail, PenLine, RefreshCw, Save, XCircle } from 'lucide-react'
import {
  emptySitoArticleEditPage,
  emptySitoStudioContattiPage,
  emptySitoStudioPage,
  getSitoArticleEditPage,
  getSitoStudioContattiPage,
  getSitoStudioPage,
  linkSitoContatto,
  saveSitoArticle,
  updateSitoBookingStatus,
  type SitoArticleEditPageData,
  type SitoArticleSavePayload,
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
import { displaySourceLabel, displayWritesLabel } from '../displayText'
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
  return new Intl.DateTimeFormat('it-IT', { timeZone: 'Europe/Rome', dateStyle: 'short', timeStyle: 'short' }).format(parsed)
}

function bodyTextToBlocks(value: string): string {
  const paragraphs = value
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter(Boolean)
  const blocks = paragraphs.length
    ? paragraphs.map((text, index) => ({
        type: 'rich_text',
        title: index === 0 ? 'Contenuto' : '',
        text,
      }))
    : []
  return JSON.stringify(blocks)
}

function articleToForm(article: SitoArticleEditPageData['article']): SitoArticleSavePayload {
  return {
    title: article?.title || '',
    slug: article?.slug || '',
    excerpt: article?.excerpt || '',
    coverUrl: article?.coverUrl || '',
    category: article?.category || '',
    tagsCsv: article?.tagsCsv || '',
    authorName: article?.authorName || '',
    bodyJsonText: article?.bodyJsonText || '[]',
    bodyText: article?.bodyText || '',
    status: article?.status || 'draft',
    publishedAt: article?.publishedAt || '',
    seoTitle: article?.seoTitle || '',
    seoDescription: article?.seoDescription || '',
  }
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
        <strong>Sito Studio operativo</strong>
        <span>Cruscotto, contatti, editor sito e redazione assistita leggono dati reali e usano azioni operative controllate.</span>
      </section>
      <WarningList warnings={data.warnings} />
      <section className="iu-sito-kpis" aria-label="Indicatori Sito Studio">
        {data.metrics.map((metric) => (
          <KpiCard
            label={metric.label}
            value={formatValue(metric.value)}
            note={metric.note}
            badge={<Badge tone={metric.tone}>{metric.value ? 'attivo' : 'vuoto'}</Badge>}
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
        subtitle={`${content.length} contenuti letti dall'archivio`}
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
              {action.id === 'public' ? <Globe2 size={15} /> : action.id === 'builder' ? <PenLine size={15} /> : action.id === 'redazione-ai' ? <Bot size={15} /> : <ExternalLink size={15} />}
              {action.label}
            </ButtonLink>
          ))}
        </div>
      </Panel>
      <Panel title="Percorso di recupero" subtitle="Disponibile solo come uscita controllata se serve confrontare un dato">
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
        <Button tone="neutral" disabled title="Nota interna non disponibile per questa scheda">
          Nota interna
        </Button>
        <Button tone="neutral" disabled title="Archiviazione non disponibile per questa scheda">
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
  const entrypointActions = [
    {
      id: 'contatto',
      href: data.entrypoints.publicContact,
      label: 'Apri modulo contatti',
      tone: 'primary' as const,
      icon: <Mail size={15} />,
    },
    {
      id: 'prenotazione',
      href: data.entrypoints.publicBooking,
      label: 'Apri prenotazione',
      tone: 'success' as const,
      icon: <CalendarDays size={15} />,
    },
    {
      id: 'sito',
      href: data.entrypoints.publicSite,
      label: 'Apri sito pubblico',
      tone: 'neutral' as const,
      icon: <Globe2 size={15} />,
    },
  ].filter((action) => action.href)

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
        <span>La scheda resta operativa anche quando non ci sono richieste: puoi aprire i moduli pubblici e presidiare gli ingressi dello studio.</span>
      </section>
      <WarningList warnings={data.warnings} />
      <Panel title="Ingressi pubblici" subtitle="Accessi usati dai visitatori per inviare nuove richieste.">
        {entrypointActions.length ? (
          <div className="iu-sito-actions">
            {entrypointActions.map((action) => (
              <ButtonLink href={action.href} tone={action.tone} target="_blank" rel="noopener" key={action.id}>
                {action.icon}
                {action.label}
              </ButtonLink>
            ))}
          </div>
        ) : (
          <EmptyState title="Modulo pubblico non configurato" message="Configura il sito pubblico per ricevere richieste direttamente da questa scheda." />
        )}
      </Panel>
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
          <EmptyState
            title="Nessuna richiesta contatto ricevuta"
            message="Quando un visitatore invia il modulo pubblico, la richiesta compare qui con le azioni di collegamento cliente."
            action={data.entrypoints.publicContact ? <ButtonLink href={data.entrypoints.publicContact} tone="primary" target="_blank" rel="noopener">Apri modulo contatti</ButtonLink> : undefined}
          />
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
          <EmptyState
            title="Nessuna prenotazione ricevuta"
            message="Quando un visitatore richiede un appuntamento, puoi approvarlo o rifiutarlo da questa scheda."
            action={data.entrypoints.publicBooking ? <ButtonLink href={data.entrypoints.publicBooking} tone="success" target="_blank" rel="noopener">Apri prenotazione</ButtonLink> : undefined}
          />
        )}
      </Panel>
      {data.actions.rollback ? (
        <Panel title="Percorso di recupero" subtitle={data.actions.unsupportedReason || 'Percorso disponibile solo per assistenza controllata'}>
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

function ArticleField({
  label,
  children,
  wide = false,
  help,
}: {
  label: string
  children: ReactNode
  wide?: boolean
  help?: string
}) {
  return (
    <label className={`iu-sito-form-field ${wide ? 'is-wide' : ''}`.trim()}>
      <span>{label}</span>
      {children}
      {help ? <small>{help}</small> : null}
    </label>
  )
}

function ArticleEditContent({ data, reload }: { data: SitoArticleEditPageData; reload: () => void }) {
  const [form, setForm] = useState<SitoArticleSavePayload>(() => articleToForm(data.article))
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')
  const [validation, setValidation] = useState<Record<string, string>>({})

  useEffect(() => {
    setForm(articleToForm(data.article))
    setError('')
    setValidation({})
  }, [data.article])

  function updateField(name: keyof SitoArticleSavePayload, value: string) {
    setForm((current) => ({ ...current, [name]: value }))
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!data.article) return
    if (!form.title.trim()) {
      setValidation({ title: 'Indica il titolo dell’articolo.' })
      return
    }
    setSaving(true)
    setSuccess('')
    setError('')
    setValidation({})
    const bodyChanged = form.bodyText.trim() !== (data.article.bodyText || '').trim()
    const result = await saveSitoArticle(data.article.id, {
      ...form,
      bodyJsonText: bodyChanged ? bodyTextToBlocks(form.bodyText) : form.bodyJsonText,
    })
    setSaving(false)
    if (result.ok) {
      setSuccess(result.message)
      if (result.payload) {
        setForm(articleToForm(result.payload.article))
      }
      reload()
      return
    }
    setError(result.message)
    setValidation(result.errors)
  }

  if (data.notFound || !data.article) {
    return (
      <>
        <WarningList warnings={data.warnings} />
        <EmptyState
          title="Articolo non trovato"
          message="Il contenuto richiesto non risulta nel sito dello studio corrente."
          action={<ButtonLink href={data.actions.dashboard} tone="primary">Cruscotto sito</ButtonLink>}
        />
      </>
    )
  }

  return (
    <>
      <section className="iu-sito-banner" aria-label="Modifica articolo">
        <strong>Modifica articolo Sito Studio</strong>
        <span>La scheda salva titolo, stato, contenuto, immagine, categoria e dati di pubblicazione sull’archivio reale dello studio.</span>
      </section>
      <WarningList warnings={data.warnings} />
      {success ? <div className="iu-sito-flash iu-sito-flash--success">{success}</div> : null}
      {error ? <div className="iu-sito-flash iu-sito-flash--danger">{error}</div> : null}
      {Object.keys(validation).length ? (
        <div className="iu-sito-flash iu-sito-flash--warning">
          {Object.entries(validation).map(([key, message]) => <span key={key}>{message}</span>)}
        </div>
      ) : null}
      <div className="iu-sito-article-layout">
        <Panel title="Contenuto articolo" subtitle={`Ultimo aggiornamento: ${formatDate(data.article.updatedAt)}`}>
          <form className="iu-sito-article-form" onSubmit={submit}>
            <ArticleField label="Titolo" wide>
              <input
                className="iu-sito-input"
                value={form.title}
                onChange={(event) => updateField('title', event.currentTarget.value)}
                required
              />
            </ArticleField>
            <ArticleField label="Indirizzo pagina" help="Lascia vuoto per rigenerarlo dal titolo.">
              <input
                className="iu-sito-input"
                value={form.slug}
                onChange={(event) => updateField('slug', event.currentTarget.value)}
              />
            </ArticleField>
            <ArticleField label="Stato">
              <select
                className="iu-sito-select"
                value={form.status}
                onChange={(event) => updateField('status', event.currentTarget.value)}
              >
                {data.statuses.map((option) => (
                  <option value={option.value} key={option.value}>{option.label}</option>
                ))}
              </select>
            </ArticleField>
            <ArticleField label="Categoria">
              <input
                className="iu-sito-input"
                value={form.category}
                onChange={(event) => updateField('category', event.currentTarget.value)}
              />
            </ArticleField>
            <ArticleField label="Parole chiave">
              <input
                className="iu-sito-input"
                value={form.tagsCsv}
                onChange={(event) => updateField('tagsCsv', event.currentTarget.value)}
              />
            </ArticleField>
            <ArticleField label="Autore">
              <input
                className="iu-sito-input"
                value={form.authorName}
                onChange={(event) => updateField('authorName', event.currentTarget.value)}
              />
            </ArticleField>
            <ArticleField label="Pubblicazione">
              <input
                className="iu-sito-input"
                value={form.publishedAt}
                onChange={(event) => updateField('publishedAt', event.currentTarget.value)}
                placeholder="AAAA-MM-GG"
              />
            </ArticleField>
            <ArticleField label="Immagine copertina" wide help="Usa un indirizzo immagine già approvato o generato dalla redazione assistita.">
              <input
                className="iu-sito-input"
                value={form.coverUrl}
                onChange={(event) => updateField('coverUrl', event.currentTarget.value)}
              />
            </ArticleField>
            <ArticleField label="Sommario" wide>
              <textarea
                className="iu-sito-textarea"
                rows={4}
                value={form.excerpt}
                onChange={(event) => updateField('excerpt', event.currentTarget.value)}
              />
            </ArticleField>
            <ArticleField label="Testo principale" wide help="Se modifichi questo testo, viene salvato come sezioni editoriali del sito.">
              <textarea
                className="iu-sito-textarea iu-sito-textarea--article"
                rows={12}
                value={form.bodyText}
                onChange={(event) => updateField('bodyText', event.currentTarget.value)}
              />
            </ArticleField>
            <ArticleField label="Titolo per motori di ricerca" wide>
              <input
                className="iu-sito-input"
                value={form.seoTitle}
                onChange={(event) => updateField('seoTitle', event.currentTarget.value)}
              />
            </ArticleField>
            <ArticleField label="Descrizione per motori di ricerca" wide>
              <textarea
                className="iu-sito-textarea"
                rows={3}
                value={form.seoDescription}
                onChange={(event) => updateField('seoDescription', event.currentTarget.value)}
              />
            </ArticleField>
            <div className="iu-sito-article-submit">
              <Button tone="primary" type="submit" disabled={saving}>
                <Save size={16} />
                {saving ? 'Salvataggio' : 'Salva articolo'}
              </Button>
              <Button tone="neutral" type="button" disabled={saving} onClick={reload}>
                <RefreshCw size={16} />
                Ricarica
              </Button>
            </div>
          </form>
        </Panel>
        <aside className="iu-sito-article-side" aria-label="Stato articolo">
          <Panel title="Stato e azioni">
            <div className="iu-sito-article-status">
              <Badge tone={data.article.statusTone}>{data.article.statusLabel}</Badge>
              <span>{data.site.siteName || data.site.studioName || 'Sito Studio'}</span>
              <strong>{data.article.title || 'Articolo senza titolo'}</strong>
            </div>
            <div className="iu-sito-actions iu-sito-actions--stacked">
              <ButtonLink href={data.actions.dashboard} tone="neutral">
                <ArrowLeft size={15} />
                Cruscotto sito
              </ButtonLink>
              <ButtonLink href={data.actions.redazioneAi} tone="primary">
                <FileText size={15} />
                Redazione assistita
              </ButtonLink>
              {data.actions.publicPreview ? (
                <ButtonLink href={data.actions.publicPreview} tone="success" target="_blank" rel="noopener">
                  <Globe2 size={15} />
                  Anteprima pubblica
                </ButtonLink>
              ) : null}
            </div>
          </Panel>
          <Panel title="Copertina">
            {form.coverUrl ? (
              <img className="iu-sito-article-cover" src={form.coverUrl} alt="Copertina articolo" />
            ) : (
              <EmptyState title="Copertina non indicata" message="Aggiungi un’immagine dall’archivio o dalla redazione assistita." />
            )}
            <div className="iu-sito-actions iu-sito-actions--stacked">
              <ButtonLink href={data.actions.redazioneAi} tone="neutral">
                <ImagePlus size={15} />
                Prepara immagine
              </ButtonLink>
            </div>
          </Panel>
          {data.actions.rollback ? (
            <Panel title="Percorso di recupero" subtitle="Disponibile solo come uscita controllata se serve confrontare il dato.">
              <ButtonLink href={data.actions.rollback.href} tone="neutral">
                <ExternalLink size={15} />
                {data.actions.rollback.label}
              </ButtonLink>
            </Panel>
          ) : null}
        </aside>
      </div>
    </>
  )
}

function ContractPanel({ data }: { data: SitoStudioPageData | SitoStudioContattiPageData | SitoArticleEditPageData }) {
  return (
    <Panel title="Stato dati" subtitle="Dati e azioni disponibili per questa pagina.">
      <div className="iu-sito-contract">
        <span>Origine: {displaySourceLabel(data.source)}</span>
        <span>Generato: {data.generated_at || 'non disponibile'}</span>
        <span>Azioni: {displayWritesLabel(data.contracts.writes)}</span>
        <span>Operativo: {data.contracts.operational ? 'si' : 'no'}</span>
        <span>Dati reali: {data.contracts.mock_fallback ? 'da verificare' : 'si'}</span>
      </div>
    </Panel>
  )
}

export function SitoStudioPage() {
  const currentRoute = routeKey()
  const contactsRoute = currentRoute === '/sito-studio/contatti'
  const articleMatch = currentRoute.match(/^\/sito-studio\/articoli\/(\d+)\/modifica$/)
  const articleId = articleMatch?.[1] || ''
  const articleRoute = Boolean(articleId)
  const [dashboardData, setDashboardData] = useState<SitoStudioPageData>(emptySitoStudioPage)
  const [contactsData, setContactsData] = useState<SitoStudioContattiPageData>(emptySitoStudioContattiPage)
  const [articleData, setArticleData] = useState<SitoArticleEditPageData>(emptySitoArticleEditPage)
  const [loading, setLoading] = useState(true)
  const [reloadCounter, setReloadCounter] = useState(0)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    const loader = articleRoute
      ? () => getSitoArticleEditPage(articleId)
      : contactsRoute
        ? getSitoStudioContattiPage
        : getSitoStudioPage
    loader()
      .then((payload) => {
        if (!active) return
        if (articleRoute) {
          const articlePayload = payload as SitoArticleEditPageData
          setArticleData(articlePayload)
          setError(articlePayload.ok || articlePayload.notFound ? '' : articlePayload.warnings[0]?.message || 'Articolo Sito Studio non disponibile.')
          return
        }
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
        if (active) setError(articleRoute ? 'Articolo Sito Studio non disponibile.' : contactsRoute ? 'Contatti Sito Studio non disponibili.' : 'Sito Studio non disponibile.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [articleId, articleRoute, contactsRoute, reloadCounter])

  const dashboardHasData = dashboardData.metrics.length > 0 || dashboardData.pages.length > 0
  const hasData = articleRoute ? (articleData.ok || articleData.notFound) : contactsRoute ? contactsData.ok : dashboardHasData
  const pageTitle = articleRoute ? 'Modifica articolo Sito Studio' : contactsRoute ? 'Contatti Sito Studio' : 'Sito Studio'
  const pageSubtitle = articleRoute
    ? 'Revisione e pubblicazione del contenuto editoriale collegato al sito dello studio.'
    : contactsRoute
      ? 'Richieste contatto e prenotazioni gestite con servizi sicuri.'
      : 'Cruscotto operativo del sito pubblico dello studio.'

  return (
    <Page
      title={pageTitle}
      subtitle={pageSubtitle}
      actions={
        <>
          <ButtonLink href={articleRoute || contactsRoute ? '/sito-studio' : '/sito-studio/contatti'} tone="primary">
            {articleRoute || contactsRoute ? <Globe2 size={16} /> : <Mail size={16} />}
            {articleRoute || contactsRoute ? 'Cruscotto sito' : 'Contatti sito'}
          </ButtonLink>
          <Button tone="neutral" onClick={() => setReloadCounter((value) => value + 1)}>
            <RefreshCw size={16} />
            Aggiorna
          </Button>
        </>
      }
    >
      {loading ? <LoadingState title="Caricamento Sito Studio" message="Lettura dei dati reali del sito in corso." /> : null}
      {!loading && error ? (
        <EmptyState
          title={articleRoute ? 'Articolo non disponibile' : contactsRoute ? 'Contatti non disponibili' : 'Sito Studio non disponibile'}
          message={error}
          action={<ButtonLink href={articleRoute || contactsRoute ? '/sito-studio' : '/sito-studio/contatti'} tone="primary">{articleRoute || contactsRoute ? 'Cruscotto sito' : 'Contatti sito'}</ButtonLink>}
        />
      ) : null}
      {!loading && !error && !contactsRoute && !articleRoute && !hasData ? (
        <EmptyState
          title="Nessun dato Sito Studio disponibile"
          message="Il sito non espone ancora contenuti o indicatori visualizzabili."
          action={<ButtonLink href="/sito-studio/contatti" tone="primary">Contatti sito</ButtonLink>}
        />
      ) : null}
      {!loading && !error && hasData ? (
        articleRoute
          ? <ArticleEditContent data={articleData} reload={() => setReloadCounter((value) => value + 1)} />
          : contactsRoute
          ? <ContactsContent data={contactsData} reload={() => setReloadCounter((value) => value + 1)} />
          : <DashboardContent data={dashboardData} />
      ) : null}
      {!loading && !error && hasData ? <ContractPanel data={articleRoute ? articleData : contactsRoute ? contactsData : dashboardData} /> : null}
    </Page>
  )
}
