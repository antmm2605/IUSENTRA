import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import {
  ArrowLeft,
  AtSign,
  CheckCircle2,
  Clock3,
  ExternalLink,
  Filter,
  Mail,
  MessageCircle,
  Phone,
  Plus,
  Search,
  Send,
  Smartphone,
  Sparkles,
  Trash2,
  UsersRound,
  XCircle,
} from 'lucide-react'
import { Badge, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import {
  defaultTemplates,
  emptyMessaggiData,
  emptyNuovoMessaggioData,
  getMessaggiData,
  getNuovoMessaggioData,
  type ChannelInfo,
  type ClientOption,
  type MessageChannel,
  type MessageItem,
  type MessageTemplate,
  type MessaggiData,
  type NuovoMessaggioData,
} from '../messaggiData'
import type { Tone } from '../data'
import './MessaggiPage.css'

type ComposeState = {
  canale: MessageChannel
  id_cliente: string
  destinatario: string
  oggetto: string
  testo: string
}

function channelIcon(channel: MessageChannel, size = 18): ReactNode {
  if (channel === 'EMAIL') return <Mail size={size}/>
  if (channel === 'SMS') return <Smartphone size={size}/>
  return <MessageCircle size={size}/>
}

function text(value: unknown): string {
  return String(value ?? '').trim()
}

function toneForChannel(channel: MessageChannel): Tone {
  if (channel === 'EMAIL') return 'primary'
  return 'success'
}

function statRows(data: MessaggiData) {
  return [
    { label: 'Totali', value: data.summary.total, note: `${data.summary.recent} negli ultimi 7 giorni`, icon: MessageCircle, tone: 'primary' as Tone },
    { label: 'Inviati', value: data.summary.sent, note: `${data.summary.delivered} consegnati / ${data.summary.read} letti`, icon: Send, tone: 'success' as Tone },
    { label: 'In coda', value: data.summary.queued, note: `${data.summary.manualWhatsapp} WhatsApp Web manuali`, icon: Clock3, tone: 'warning' as Tone },
    { label: 'Da correggere', value: data.summary.failed, note: data.summary.failed ? 'Controlla configurazione canale' : 'Nessun errore aperto', icon: XCircle, tone: data.summary.failed ? 'danger' as Tone : 'neutral' as Tone },
  ]
}

function ChannelBadge({ channel, label }:{ channel: MessageChannel; label?: string }) {
  return <Badge tone={toneForChannel(channel)}>{channelIcon(channel, 13)} {label || (channel === 'WHATSAPP' ? 'WhatsApp' : channel)}</Badge>
}

function MessageStatus({ item }:{ item: MessageItem }) {
  return <Badge tone={item.tone}>{item.statusLabel}</Badge>
}

function StatStrip({ data }:{data: MessaggiData}) {
  return (
    <section className="iu-msg-stats" aria-label="Statistiche messaggi">
      {statRows(data).map((row) => {
        const Icon = row.icon
        return (
          <article className={`iu-msg-stat iu-msg-stat--${row.tone}`} key={row.label}>
            <Icon size={20}/>
            <span>{row.label}</span>
            <strong>{row.value}</strong>
            <small>{row.note}</small>
          </article>
        )
      })}
    </section>
  )
}

function MessageRow({ item }:{ item: MessageItem }) {
  return (
    <article className={`iu-msg-row iu-msg-row--${item.channel.toLowerCase()}`}>
      <div className="iu-msg-avatar" aria-hidden="true">{channelIcon(item.channel, 20)}</div>
      <div className="iu-msg-main">
        <div className="iu-msg-line">
          <a href={item.detailHref || `/messaggi/${item.id}`}>{item.recipient}</a>
          <span>{item.createdLabel || item.createdAt}</span>
        </div>
        <p>{item.preview}</p>
        <div className="iu-msg-meta">
          <ChannelBadge channel={item.channel} label={item.channelLabel}/>
          <MessageStatus item={item}/>
          {item.clientLabel ? <a href={item.clientHref || '#'}><UsersRound size={13}/>{item.clientLabel}</a> : null}
          {item.manualWhatsapp && item.whatsappLink ? <a href={item.whatsappLink} target="_blank" rel="noreferrer"><ExternalLink size={13}/>WhatsApp Web</a> : null}
        </div>
      </div>
      <div className="iu-msg-actions">
        <a href={item.detailHref || `/messaggi/${item.id}`} aria-label="Apri dettaglio messaggio">Apri</a>
        <form method="post" action={`/messaggi/${encodeURIComponent(item.id)}/elimina`} onSubmit={(event) => { if (!window.confirm('Eliminare il messaggio?')) event.preventDefault() }}>
          <button type="submit" aria-label="Elimina messaggio"><Trash2 size={15}/></button>
        </form>
      </div>
    </article>
  )
}

function ChannelHealth({ data }:{data: MessaggiData | NuovoMessaggioData}) {
  return (
    <div className="iu-msg-channel-health">
      {data.channelInfo.map((channel) => (
        <article key={channel.value}>
          <div>{channelIcon(channel.value)}<strong>{channel.label}</strong></div>
          <Badge tone={channel.configured || channel.value === 'WHATSAPP' ? 'success' : 'warning'}>
            {channel.configured ? 'Configurato' : channel.value === 'WHATSAPP' ? 'Alternativa Web' : 'Da configurare'}
          </Badge>
          <p>{channel.subtitle}</p>
        </article>
      ))}
    </div>
  )
}

function filterItems(items: MessageItem[], q: string, channel: string, status: string): MessageItem[] {
  const query = q.trim().toLowerCase()
  return items.filter((item) => {
    if (channel && item.channel !== channel) return false
    if (status && item.status !== status) return false
    if (!query) return true
    return [item.recipient, item.destination, item.subject, item.body, item.clientLabel, item.statusLabel]
      .some((value) => value.toLowerCase().includes(query))
  })
}

export function MessaggiPage() {
  const [data, setData] = useState<MessaggiData>(emptyMessaggiData)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [channel, setChannel] = useState('')
  const [status, setStatus] = useState('')

  useEffect(() => {
    let cancelled = false
    getMessaggiData().then((payload) => {
      if (cancelled) return
      setData(payload)
      setQuery(payload.filters.q)
      setChannel(payload.filters.channel)
      setStatus(payload.filters.status)
      setLoading(false)
    })
    return () => { cancelled = true }
  }, [])

  const filtered = useMemo(() => filterItems(data.items, query, channel, status), [data.items, query, channel, status])

  const applyFilters = (event: FormEvent) => {
    event.preventDefault()
    const params = new URLSearchParams()
    if (query.trim()) params.set('q', query.trim())
    if (channel) params.set('canale', channel)
    if (status) params.set('stato', status)
    const suffix = params.toString() ? `?${params.toString()}` : ''
    window.location.href = `/messaggi${suffix}`
  }

  return (
    <main className="iu-msg-page">
      <section className="iu-msg-hero">
        <div>
          <span className="iu-msg-eyebrow"><MessageCircle size={14}/>Comunicazioni</span>
          <h1>Messaggi</h1>
          <p>Storico operativo di email, SMS e WhatsApp con filtri rapidi, stato invio, cliente collegato e alternativa WhatsApp Web governata.</p>
        </div>
        <div className="iu-msg-hero__actions">
          <a href="/email/"><Mail size={16}/>Email studio</a>
          <a className="is-primary" href={data.actions.newMessage}><Plus size={16}/>Nuovo messaggio</a>
        </div>
      </section>

      <StatStrip data={data}/>

      <section className="iu-msg-layout">
        <div className="iu-msg-maincol">
          <form className="iu-msg-filters" onSubmit={applyFilters}>
            <label><Search size={16}/><input value={query} onChange={(event) => setQuery(event.currentTarget.value)} placeholder="Destinatario, oggetto, testo, cliente..."/></label>
            <select value={channel} onChange={(event) => setChannel(event.currentTarget.value)} aria-label="Filtra per canale">
              {data.facets.channels.map((option) => <option value={option.value} key={`canale-${option.value || 'all'}`}>{option.label}{option.count !== undefined ? ` (${option.count})` : ''}</option>)}
            </select>
            <select value={status} onChange={(event) => setStatus(event.currentTarget.value)} aria-label="Filtra per stato">
              {data.facets.statuses.map((option) => <option value={option.value} key={`stato-${option.value || 'all'}`}>{option.label}{option.count !== undefined ? ` (${option.count})` : ''}</option>)}
            </select>
            <button type="submit"><Filter size={15}/>Filtra</button>
            {(query || channel || status) ? <a href="/messaggi">Reset</a> : null}
          </form>

          <Panel title="Storico messaggi" subtitle={loading ? 'Caricamento...' : `${filtered.length} risultati visibili`} icon={<MessageCircle size={17}/>} action={<a className="iu-msg-panel-action" href={data.actions.newMessage}><Plus size={14}/>Nuovo</a>}>
            {filtered.length ? (
              <div className="iu-msg-list">
                {filtered.map((item) => <MessageRow item={item} key={item.id}/>) }
              </div>
            ) : (
              <div className="iu-msg-empty">
                <MessageCircle size={42}/>
                <strong>Nessun messaggio trovato</strong>
                <p>{loading ? 'Lettura dello storico in corso.' : query || channel || status ? 'Nessun risultato con i filtri attuali.' : 'Invia il primo messaggio a un cliente tramite email, SMS o WhatsApp.'}</p>
                {!loading ? <a href={data.actions.newMessage}><Plus size={16}/>Nuovo messaggio</a> : null}
              </div>
            )}
          </Panel>
        </div>

        <aside className="iu-msg-sidecol">
          <Panel title="Canali disponibili" subtitle="Configurazione e alternative operative" icon={<AtSign size={17}/>}>
            <ChannelHealth data={data}/>
          </Panel>
          <Panel title="Lex AI" subtitle="Controllo prima dellâ€™invio" icon={<Sparkles size={17}/>}>
            <div className="iu-msg-lex-list">
              {data.lex.map((item) => <p key={item}><Sparkles size={14}/>{item}</p>)}
            </div>
          </Panel>
        </aside>
      </section>

      <FloatingLex
        context="messaggi"
        title="Lex AI messaggi"
        body="Posso controllare tono, dati mancanti, canale corretto e rischio di inviare una comunicazione incompleta al cliente."
        primaryHref="/lex?context=messaggi"
        secondaryHref="/messaggi/nuovo"
        secondaryLabel="Nuovo messaggio"
      />
    </main>
  )
}

function selectedChannelInfo(data: NuovoMessaggioData, channel: MessageChannel): ChannelInfo {
  return data.channelInfo.find((item) => item.value === channel) || data.channelInfo[0]
}

function fillTemplate(template: MessageTemplate, client?: ClientOption): Pick<ComposeState, 'oggetto' | 'testo'> {
  const name = client?.label || 'Cliente'
  return {
    oggetto: template.subject.replaceAll('{nome}', name),
    testo: template.body.replaceAll('{nome}', name),
  }
}

function initialCompose(data: NuovoMessaggioData): ComposeState {
  const channel = data.query.channel || 'EMAIL'
  const client = data.clientOptions.find((item) => item.id === data.query.idCliente)
  const destination = channel === 'EMAIL' ? text(client?.email) : text(client?.phone)
  return {
    canale: channel,
    id_cliente: data.query.idCliente,
    destinatario: destination,
    oggetto: '',
    testo: '',
  }
}

function ComposeField({ label, children, wide = false, required = false }:{ label: string; children: ReactNode; wide?: boolean; required?: boolean }) {
  return <label className={`iu-msg-compose-field ${wide ? 'is-wide' : ''}`.trim()}><span>{label}{required ? <b>*</b> : null}</span>{children}</label>
}

function Preview({ values, info, client }:{ values: ComposeState; info: ChannelInfo; client?: ClientOption }) {
  const chars = values.testo.length
  const tooLong = info.maxLength ? chars > info.maxLength : false
  return (
    <section className="iu-msg-preview">
      <header>
        <div>{channelIcon(values.canale)}<strong>Anteprima {info.label}</strong></div>
        <Badge tone={tooLong ? 'warning' : 'success'}>{chars}{info.maxLength ? `/${info.maxLength}` : ''}</Badge>
      </header>
      <div className="iu-msg-phone-card">
        <small>{client?.label || 'Destinatario'}</small>
        {values.oggetto && values.canale === 'EMAIL' ? <strong>{values.oggetto}</strong> : null}
        <p>{values.testo || 'Scrivi il testo del messaggio...'}</p>
      </div>
      {tooLong ? <p className="iu-msg-warning"><Clock3 size={14}/>Il testo supera la lunghezza standard SMS: potrebbe essere diviso in piÃ¹ messaggi.</p> : null}
    </section>
  )
}

export function NuovoMessaggioPage() {
  const [data, setData] = useState<NuovoMessaggioData>(emptyNuovoMessaggioData)
  const [values, setValues] = useState<ComposeState>(() => initialCompose(emptyNuovoMessaggioData))
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    getNuovoMessaggioData().then((payload) => {
      if (cancelled) return
      setData(payload)
      setValues(initialCompose(payload))
      setLoading(false)
    })
    return () => { cancelled = true }
  }, [])

  const selectedClient = data.clientOptions.find((item) => item.id === values.id_cliente)
  const info = selectedChannelInfo(data, values.canale)
  const availableTemplates = data.templates.length ? data.templates : defaultTemplates

  const change = (name: keyof ComposeState, value: string) => {
    setValues((current) => ({ ...current, [name]: value }))
  }

  const changeChannel = (channel: MessageChannel) => {
    const nextDestination = selectedClient ? (channel === 'EMAIL' ? selectedClient.email : selectedClient.phone) : ''
    setValues((current) => ({ ...current, canale: channel, destinatario: text(nextDestination) || current.destinatario }))
  }

  const changeClient = (id: string) => {
    const client = data.clientOptions.find((item) => item.id === id)
    const nextDestination = client ? (values.canale === 'EMAIL' ? client.email : client.phone) : ''
    setValues((current) => ({ ...current, id_cliente: id, destinatario: text(nextDestination) || current.destinatario }))
  }

  const applyTemplate = (template: MessageTemplate) => {
    const filled = fillTemplate(template, selectedClient)
    setValues((current) => ({ ...current, ...filled }))
  }

  return (
    <main className="iu-msg-page iu-msg-compose-page">
      <section className="iu-msg-hero iu-msg-hero--compose">
        <div>
          <a className="iu-msg-back" href="/messaggi"><ArrowLeft size={14}/>Messaggi</a>
          <span className="iu-msg-eyebrow"><Send size={14}/>Invio guidato</span>
          <h1>Nuovo messaggio</h1>
          <p>Email, SMS e WhatsApp con cliente collegato, compilazione assistita e invio governato dai servizi operativi dello studio.</p>
        </div>
        <div className="iu-msg-hero__actions">
          <a href="/messaggi"><MessageCircle size={16}/>Storico</a>
          <a href="/impostazioni"><AtSign size={16}/>Configura canali</a>
        </div>
      </section>

      <section className="iu-msg-compose-layout">
        <form className="iu-msg-compose" method="post" action={data.actions.sendEndpoint}>
          <input type="hidden" name="from_cliente" value={data.query.fromCliente}/>

          <Panel title="Canale" subtitle="Scegli il mezzo piÃ¹ adatto" icon={<MessageCircle size={17}/>}>
            <div className="iu-msg-channel-picker">
              {data.channelInfo.map((channel) => (
                <label className={`iu-msg-channel-card ${values.canale === channel.value ? 'is-active' : ''}`} key={channel.value}>
                  <input type="radio" name="canale" value={channel.value} checked={values.canale === channel.value} onChange={() => changeChannel(channel.value)}/>
                  <span>{channelIcon(channel.value, 20)}</span>
                  <strong>{channel.label}</strong>
                  <small>{channel.destinationHelp}</small>
                  <Badge tone={channel.configured || channel.value === 'WHATSAPP' ? 'success' : 'warning'}>{channel.configured ? 'Pronto' : channel.value === 'WHATSAPP' ? 'Link Web' : 'Config'}</Badge>
                </label>
              ))}
            </div>
          </Panel>

          <Panel title="Destinatario" subtitle="Contesto cliente e recapito" icon={<UsersRound size={17}/>}>
            <div className="iu-msg-compose-grid">
              <ComposeField label="Cliente" wide>
                <select name="id_cliente" value={values.id_cliente} onChange={(event) => changeClient(event.currentTarget.value)}>
                  <option value="">â€” Nessun cliente â€”</option>
                  {data.clientOptions.map((client) => <option value={client.id} key={client.id}>{client.label}{client.fiscalId ? ` â€” ${client.fiscalId}` : ''}</option>)}
                </select>
              </ComposeField>
              <ComposeField label={values.canale === 'EMAIL' ? 'Email destinatario' : 'Telefono destinatario'} required wide>
                <input name="destinatario" required value={values.destinatario} placeholder={info.destinationPlaceholder} onChange={(event) => change('destinatario', event.currentTarget.value)}/>
                <small>{info.destinationHelp}</small>
              </ComposeField>
            </div>
          </Panel>

          <Panel title="Testo" subtitle="Scrittura assistita e compatibile con il backend di invio" icon={<Sparkles size={17}/>}>
            <div className="iu-msg-templates">
              {availableTemplates.map((template) => <button type="button" key={template.id} onClick={() => applyTemplate(template)}>{template.label}</button>)}
            </div>
            <div className="iu-msg-compose-grid">
              {info.subjectVisible ? (
                <ComposeField label="Oggetto" wide>
                  <input name="oggetto" value={values.oggetto} placeholder="Oggetto del messaggio" onChange={(event) => change('oggetto', event.currentTarget.value)}/>
                </ComposeField>
              ) : <input type="hidden" name="oggetto" value=""/>}
              <ComposeField label="Testo" required wide>
                <textarea name="testo" required rows={8} value={values.testo} placeholder="Scrivi il messaggio..." onChange={(event) => change('testo', event.currentTarget.value)}/>
              </ComposeField>
            </div>
          </Panel>

          <div className="iu-msg-submitbar">
            <button type="submit"><Send size={17}/>Invia</button>
            <a href="/messaggi">Annulla</a>
            <span>{loading ? 'Caricamento dati...' : 'Salvataggio su /messaggi/nuovo'}</span>
          </div>
        </form>

        <aside className="iu-msg-compose-side">
          <Preview values={values} info={info} client={selectedClient}/>
          <Panel title="Checklist qualitÃ " subtitle="Prima di inviare" icon={<CheckCircle2 size={17}/>}>
            <div className="iu-msg-checklist">
              <p><CheckCircle2 size={15}/>Destinatario compilato e coerente con il canale.</p>
              <p><CheckCircle2 size={15}/>Cliente collegato quando la comunicazione riguarda una pratica.</p>
              <p><CheckCircle2 size={15}/>Per WhatsApp senza Twilio verrÃ  generato un link manuale.</p>
            </div>
          </Panel>
          <Panel title="Canali" subtitle="Stato configurazione" icon={<AtSign size={17}/>}>
            <ChannelHealth data={data}/>
          </Panel>
        </aside>
      </section>

      <FloatingLex
        context="nuovo-messaggio"
        title="Lex AI invio messaggio"
        body="Posso aiutarti a rendere il testo piÃ¹ chiaro, professionale e coerente con cliente, canale e pratica."
        primaryHref="/lex?context=nuovo-messaggio"
        secondaryHref="/messaggi"
        secondaryLabel="Storico messaggi"
      />
    </main>
  )
}
