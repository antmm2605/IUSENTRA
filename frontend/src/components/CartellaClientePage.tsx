import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  Archive,
  BadgeCheck,
  BriefcaseBusiness,
  CalendarDays,
  Clock3,
  Download,
  Euro,
  FileText,
  FolderOpen,
  Mail,
  MessageCircle,
  PencilLine,
  Phone,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  UserRound,
} from 'lucide-react'
import { Badge, Button, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import {
  emptyCartellaCliente,
  getCartellaClientePage,
  type CartellaClienteData,
  type CartellaClienteItem,
  type CartellaClienteMatter,
} from '../clientiCartellaData'
import './CartellaClientePage.css'

function idClienteFromLocation(): string {
  const parts = window.location.pathname.split('/').filter(Boolean)
  const clientiIndex = parts.indexOf('clienti')
  return clientiIndex >= 0 ? decodeURIComponent(parts[clientiIndex + 1] || '') : ''
}

function StatCard({
  icon,
  value,
  label,
  tone = 'primary',
}:{
  icon: ReactNode
  value: number | string
  label: string
  tone?: string
}) {
  return (
    <article className={`iu-cart-stat iu-cart-stat--${tone}`}>
      <div>{icon}</div>
      <strong>{value}</strong>
      <span>{label}</span>
    </article>
  )
}

function EmptyBlock({ children }:{children: string}) {
  return <div className="iu-cart-empty"><Sparkles size={18}/><span>{children}</span></div>
}

function InfoLine({ icon, label, value }:{icon: ReactNode; label: string; value: string}) {
  return (
    <div className="iu-cart-info-line">
      {icon}
      <span>{label}</span>
      <strong>{value || '-'}</strong>
    </div>
  )
}

function MatterCard({ item }:{item: CartellaClienteMatter}) {
  return (
    <a className="iu-cart-matter" href={item.href}>
      <header>
        <Badge tone={item.tone}>{item.status || 'Aperto'}</Badge>
        <span>{item.type || 'Fascicolo'}</span>
      </header>
      <strong>{item.title}</strong>
      <p>{item.subtitle || item.counterparty || 'Fascicolo collegato al cliente'}</p>
      <footer>
        <span><FileText size={14}/> {item.documents} documenti</span>
        <span><Clock3 size={14}/> {item.activities} attivita</span>
      </footer>
    </a>
  )
}

function ItemList({
  items,
  empty,
  withActions = false,
}:{
  items: CartellaClienteItem[]
  empty: string
  withActions?: boolean
}) {
  if (!items.length) return <EmptyBlock>{empty}</EmptyBlock>
  return (
    <div className="iu-cart-list">
      {items.map((item) => (
        <article className="iu-cart-list-item" key={item.id}>
          <a href={item.href}>
            <Badge tone={item.tone}>{item.status || item.priority || item.channel || 'Apri'}</Badge>
            <strong>{item.title}</strong>
            <span>{item.subtitle || item.amount || item.date || 'Elemento collegato'}</span>
          </a>
          <time>{[item.date, item.time].filter(Boolean).join(' ')}</time>
          {withActions ? (
            <div className="iu-cart-row-actions">
              {item.editHref ? <a href={item.editHref}>Modifica</a> : null}
              {item.completeHref ? <a href={item.completeHref}>Completa</a> : null}
            </div>
          ) : null}
        </article>
      ))}
    </div>
  )
}

export function CartellaClientePage() {
  const idCliente = idClienteFromLocation()
  const [data, setData] = useState<CartellaClienteData>(emptyCartellaCliente)
  const [loading, setLoading] = useState(true)
  const [errore, setErrore] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    getCartellaClientePage(idCliente)
      .then((payload) => {
        if (!active) return
        setData(payload)
        setErrore(payload.cliente.id ? '' : 'Cartella cliente non disponibile o non autorizzata.')
      })
      .catch(() => {
        if (!active) return
        setData(emptyCartellaCliente)
        setErrore('Impossibile caricare la cartella cliente.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [idCliente])

  const qualityWarnings = useMemo(() => {
    const warnings: string[] = []
    if (data.cliente.missingFields.length) warnings.push(`Anagrafica incompleta: ${data.cliente.missingFields.join(', ')}`)
    if (!data.cliente.privacyOk) warnings.push('Privacy e consenso trattamento da verificare.')
    if (data.cliente.documentExpired) warnings.push('Documento di identita scaduto o da aggiornare.')
    if (!data.cliente.email && !data.cliente.phone && !data.cliente.pec) warnings.push('Nessun recapito operativo registrato.')
    return warnings
  }, [data])

  return (
    <main className="iu-content iu-cartella-cliente-page">
      <div className="iu-cart-hero">
        <div>
          <span className="iu-cart-kicker">Cartella cliente</span>
          <h1>{data.cliente.name}</h1>
          <p>{data.cliente.subtitle || 'Fascicoli, scadenze, incarichi, comunicazioni ed economia in un unico quadro operativo.'}</p>
          <div className="iu-cart-badges">
            <Badge tone={data.cliente.status === 'potenziale' ? 'warning' : 'success'}>{data.cliente.status === 'potenziale' ? 'Cliente potenziale' : 'Cliente censito'}</Badge>
            <Badge tone="neutral">{data.cliente.type === 'pg' ? 'Persona giuridica' : 'Persona fisica'}</Badge>
            {data.cliente.fiscalId ? <Badge tone="primary">{data.cliente.fiscalId}</Badge> : null}
          </div>
        </div>
        <div className="iu-cart-hero-actions">
          <Button href={data.actions.editClient || data.cliente.editHref} variant="secondary"><PencilLine size={16}/>Modifica anagrafica</Button>
          <Button href={data.actions.newMatter || '/fascicoli/nuovo'}><Plus size={16}/>Nuovo fascicolo</Button>
          <a href={data.actions.legacy || data.contracts.legacy_route || `${data.cliente.folderHref}?_legacy=1`}>Percorso di recupero</a>
        </div>
      </div>

      {errore ? <div className="iu-cart-alert iu-cart-alert--danger"><AlertTriangle size={18}/>{errore}</div> : null}
      {qualityWarnings.length ? (
        <section className="iu-cart-alert">
          <AlertTriangle size={18}/>
          <div>
            <strong>Controlli anagrafici da presidiare</strong>
            {qualityWarnings.map((warning) => <span key={warning}>{warning}</span>)}
          </div>
        </section>
      ) : null}

      <section className="iu-cart-stats" aria-label="Indicatori cartella cliente">
        <StatCard icon={<BriefcaseBusiness size={18}/>} value={data.summary.activeMatters} label="Fascicoli attivi" tone="primary"/>
        <StatCard icon={<CalendarDays size={18}/>} value={data.summary.deadlines} label="Scadenze aperte" tone={data.summary.overdueDeadlines ? 'danger' : 'warning'}/>
        <StatCard icon={<FileText size={18}/>} value={data.summary.documents} label="Documenti" tone="neutral"/>
        <StatCard icon={<MessageCircle size={18}/>} value={data.summary.messages} label="Comunicazioni" tone="success"/>
        <StatCard icon={<Euro size={18}/>} value={data.summary.invoices} label="Parcelle" tone="orange"/>
      </section>

      <section className="iu-cart-grid">
        <div className="span4">
          <Panel title="Dati cliente" icon={<UserRound size={17}/>}>
            <div className="iu-cart-info">
              <InfoLine icon={<Phone size={15}/>} label="Telefono" value={data.cliente.phone}/>
              <InfoLine icon={<Mail size={15}/>} label="Email" value={data.cliente.email}/>
              <InfoLine icon={<ShieldCheck size={15}/>} label="PEC" value={data.cliente.pec}/>
              <InfoLine icon={<BadgeCheck size={15}/>} label="Avvocato referente" value={data.cliente.attorney}/>
            </div>
          </Panel>
        </div>
        <div className="span8">
          <Panel title="Azioni rapide" icon={<Sparkles size={17}/>} subtitle="Operazioni collegate alla stessa anagrafica, senza reinserire dati gia presenti.">
            <div className="iu-cart-actions">
              <a href={data.actions.newDeadline || '/scadenziario/nuova'}><CalendarDays size={17}/>Nuova scadenza</a>
              <a href={data.actions.newAppointment || '/agenda/nuovo'}><Clock3 size={17}/>Nuovo appuntamento</a>
              <a href={data.actions.newMessage || '/messaggi/nuovo'}><MessageCircle size={17}/>Nuovo messaggio</a>
              <a href={data.actions.newQuote || '/preventivi/nuovo'}><FileText size={17}/>Nuovo preventivo</a>
              <a href={data.actions.exportFolder || '#'}><Download size={17}/>Esporta cartella</a>
            </div>
          </Panel>
        </div>

        <div className="span8">
          <Panel title="Fascicoli attivi" icon={<FolderOpen size={17}/>} count={data.matters.active.length}>
            {data.matters.active.length ? <div className="iu-cart-matter-grid">{data.matters.active.map((item) => <MatterCard key={item.id} item={item}/>)}</div> : <EmptyBlock>Nessun fascicolo attivo collegato.</EmptyBlock>}
          </Panel>
        </div>
        <div className="span4">
          <Panel title="Scadenze e termini" icon={<CalendarDays size={17}/>} count={data.deadlines.length}>
            <ItemList items={data.deadlines} empty="Nessuna scadenza aperta per questa cartella." withActions/>
          </Panel>
        </div>

        <div className="span4">
          <Panel title="Preventivi e incarichi" icon={<FileText size={17}/>} count={data.quotes.length + data.engagements.length}>
            <ItemList items={[...data.quotes, ...data.engagements]} empty="Nessun preventivo o conferimento collegato."/>
          </Panel>
        </div>
        <div className="span4">
          <Panel title="Comunicazioni" icon={<MessageCircle size={17}/>} count={data.messages.length}>
            <ItemList items={data.messages} empty="Nessuna comunicazione registrata."/>
          </Panel>
        </div>
        <div className="span4">
          <Panel title="Agenda" icon={<Clock3 size={17}/>} count={data.appointments.length}>
            <ItemList items={data.appointments} empty="Nessun appuntamento collegato."/>
          </Panel>
        </div>

        <div className="span6">
          <Panel title="Economia" icon={<Euro size={17}/>} count={data.invoices.length}>
            <ItemList items={data.invoices} empty="Nessuna parcella collegata."/>
          </Panel>
        </div>
        <div className="span6">
          <Panel title="Timeline operativa" icon={<Clock3 size={17}/>} count={data.timeline.length}>
            <ItemList items={data.timeline} empty="Nessuna attivita recente sui fascicoli del cliente."/>
          </Panel>
        </div>

        {data.matters.archived.length ? (
          <div className="span12">
            <Panel title="Fascicoli archiviati" icon={<Archive size={17}/>} count={data.matters.archived.length}>
              <div className="iu-cart-matter-grid iu-cart-matter-grid--archived">{data.matters.archived.map((item) => <MatterCard key={item.id} item={item}/>)}</div>
            </Panel>
          </div>
        ) : null}
      </section>

      <FloatingLex
        context="cartella-cliente"
        title="Lex sulla cartella"
        body={`Analizza la cartella cliente ${data.cliente.name} e segnala fascicoli, scadenze e azioni da presidiare.`}
        primaryHref="#lex"
        primaryLabel="Apri Lex sulla cartella"
        secondaryHref={data.cliente.folderHref}
        secondaryLabel="Resta nella cartella"
      />
      {loading ? <div className="iu-cart-loading"><RefreshCw size={18}/>Caricamento cartella cliente...</div> : null}
    </main>
  )
}
