import { useEffect, useState, type ReactNode } from 'react'
import { AlertTriangle, Bell, BriefcaseBusiness, CalendarDays, CircleHelp, Clock3, Crosshair, Home, LayoutDashboard, Mail, MessageCircle, PanelLeftClose, PanelLeftOpen, Plus, Search, Settings2, ShieldCheck, Sparkles, UsersRound } from 'lucide-react'
import { DashboardData, Metric, Row, Tone, emptyDashboard, getDashboard } from './data'
import './index.css'

const toneColor: Record<Tone,string> = { danger:'var(--iu-danger-500)', warning:'var(--iu-warning-500)', primary:'var(--iu-blue-600)', success:'var(--iu-success-500)', info:'var(--iu-sky-500)', purple:'var(--iu-purple-500)', orange:'var(--iu-warning-500)', neutral:'var(--iu-slate-300)' }
const metricIcon = { danger: AlertTriangle, primary: Mail, success: MessageCircle, purple: Clock3, orange: UsersRound, warning: AlertTriangle, info: Mail, neutral: Clock3 }

function Badge({ tone='neutral', children }:{tone?:Tone; children:ReactNode}) {
  return <span className={`iu-badge iu-badge--${tone}`}>{children}</span>
}

function Avatar({ label }:{label:string}) {
  const initials = label.split(' ').map(x=>x[0]).join('').slice(0,2).toUpperCase()
  return <span className="iu-avatar">{initials}</span>
}

function Logo() {
  return <svg width="46" height="46" viewBox="0 0 64 64" fill="none"><rect width="64" height="64" rx="16" fill="url(#g)"/><path d="M23.5 18.5h13.8c5 0 8.7 3.8 8.7 8.7v17.3H18V24c0-3 2.5-5.5 5.5-5.5Z" fill="url(#f)"/><rect x="29.2" y="26" width="5.8" height="15.5" rx="2.2" fill="#071329" opacity=".85"/><circle cx="48.2" cy="18.4" r="3.2" fill="#2F80ED"/><defs><linearGradient id="g" x1="8" x2="57" y1="4" y2="60"><stop stopColor="#F4B21B"/><stop offset="1" stopColor="#D49205"/></linearGradient><linearGradient id="f" x1="18" x2="47" y1="18" y2="45"><stop stopColor="#FCE7A3"/><stop offset="1" stopColor="#D4A017"/></linearGradient></defs></svg>
}

function Sidebar({ collapsed, mobileOpen, onToggle }:{collapsed:boolean; mobileOpen:boolean; onToggle:()=>void}) {
  const items = [
    ['Panoramica',LayoutDashboard,'/app-v2',true],
    ['Regia Operativa',Sparkles,'/workspace-intelligente'],
    ['Ricerca Studio',Search,'/global-search'],
    ['Agenda',CalendarDays,'/agenda'],
    ['Fascicoli',BriefcaseBusiness,'/fascicoli'],
    ['Clienti e Anagrafiche',UsersRound,'/clienti'],
    ['Soggetti e Parti',UsersRound,'/soggetti'],
    ['Comunicazioni',MessageCircle,'/messaggi'],
    ['Scadenze e Termini',Bell,'/scadenziario'],
    ['Controlli Atti',ShieldCheck,'/checklist-atti'],
    ['Lex - Assistente Legale',Sparkles,'/lex'],
    ['Servizi Telematici',Mail,'/telematico'],
    ['Studio',Home,'/applicazioni'],
    ['Amministrazione',ShieldCheck,'/admin']
  ] as const
  const ToggleIcon = collapsed ? PanelLeftOpen : PanelLeftClose
  return (
    <aside className={`iu-sidebar ${collapsed?'iu-sidebar--collapsed':''} ${mobileOpen?'iu-sidebar--mobile-open':''}`}>
      <div className="iu-sidebar__brand">
        <Logo/>
        <div><strong>IUSENTRA</strong><span>Lo studio legale, in un unico sistema</span></div>
        <button className="iu-sidebar__toggle" type="button" onClick={onToggle} aria-label={collapsed?'Espandi menu':'Comprimi menu'} title={collapsed?'Espandi menu':'Comprimi menu'}><ToggleIcon size={18}/></button>
      </div>
      <nav className="iu-sidebar__nav" aria-label="Navigazione principale">
        {items.map(([label,Icon,href,active],i)=><a key={label} className={`iu-nav-link ${active?'is-active':''} ${(i===3||i===5||i===8||i===11||i===13)?'has-gap':''}`} href={href} title={collapsed?label:undefined}><Icon size={18}/><span>{label}</span></a>)}
      </nav>
      <div className="iu-sidebar__user"><span>RR</span><div><strong>Avv. Roberto Rossi</strong><small>AMMINISTRATORE</small></div></div>
    </aside>
  )
}

function Topbar({ onOpenMenu }:{onOpenMenu:()=>void}) {
  const today = new Date().toLocaleDateString('it-IT')
  return <header className="iu-topbar"><button className="iu-icon iu-menu-mobile" type="button" onClick={onOpenMenu} aria-label="Apri menu"><PanelLeftOpen size={18}/></button><label className="iu-search"><Search size={18}/><input placeholder="Cerca fascicolo, cliente, pratica, scadenza..."/></label><div className="iu-topbar__actions"><button className="iu-date">{today} <CalendarDays size={16}/></button><button className="iu-icon notify"><Bell size={18}/><span>8</span></button><button className="iu-icon"><Settings2 size={18}/></button><button className="iu-icon"><CircleHelp size={18}/></button><button className="iu-new"><Plus size={16}/>Nuovo</button></div></header>
}

function MetricCard({ item }:{item:Metric}) {
  const Icon = metricIcon[item.tone] || AlertTriangle
  return <a href={item.href||'#'} className={`iu-metric iu-metric--${item.tone}`}><div className="iu-metric__icon"><Icon size={25}/></div><div className="iu-metric__content"><div className="iu-metric__top"><strong>{item.value}</strong>{item.tag?<Badge tone={item.tone}>{item.tag}</Badge>:null}</div><div className="iu-metric__label">{item.label}</div><div className="iu-link">{item.actionLabel||'Apri'} -&gt;</div></div></a>
}

function Panel({ title, icon, count, children }:{title:string; icon:ReactNode; count?:number|string; children:ReactNode}) {
  return <section className="iu-panel"><header><div>{icon}<strong>{title}</strong></div>{count!==undefined?<span>{count}</span>:null}</header><div className="iu-panel__body">{children}</div></section>
}

function Empty({ children='Nessun elemento da presidiare.' }:{children?:string}) {
  return <p className="iu-empty">{children}</p>
}

function List({ rows, avatar=false, href='/' }:{rows:Row[]; avatar?:boolean; href?:string}) {
  if (!rows.length) return <Empty/>
  return <div className="iu-list">{rows.map(r=><a className="iu-row" href={r.href||href} key={r.id}>{avatar?<Avatar label={r.avatar||r.title}/>:<i className={r.unread?'is-on':''}/>}<div><strong>{r.title}</strong><span>{r.subtitle}</span></div><time>{r.time}</time>{r.badge&&!avatar?<b className="iu-red-dot">{r.badge}</b>:null}</a>)}</div>
}

function italianDay(offset:number) {
  const d = new Date()
  d.setDate(d.getDate()+offset)
  const label = d.toLocaleDateString('it-IT', {weekday:'long', day:'numeric', month:'long', year:'numeric'})
  return `${offset===0?'Oggi':'Domani'} - ${label.charAt(0).toUpperCase()}${label.slice(1)}`
}

function Agenda({ data }:{data:DashboardData}) {
  const todayRows = data.agenda.filter(a=>a.badge==='OGGI')
  const tomorrowRows = data.agenda.filter(a=>a.badge==='DOMANI')
  const otherRows = data.agenda.filter(a=>a.badge!=='OGGI' && a.badge!=='DOMANI')
  return <Panel title="Agenda e udienze" icon={<CalendarDays size={17}/>} count={data.agenda.length}><div className="iu-agenda"><p>{italianDay(0)}</p>{todayRows.length?todayRows.map(a=><a className="iu-agenda-row" href={a.href||'/agenda'} key={a.id}><time>{a.time}</time><div><strong>{a.title}</strong><span>{a.subtitle}</span></div>{a.badge?<Badge tone="warning">{a.badge}</Badge>:null}</a>):<Empty>Nessun impegno per oggi.</Empty>}<p className="next">{italianDay(1)}</p>{[...tomorrowRows,...otherRows].length?[...tomorrowRows,...otherRows].map(a=><a className="iu-agenda-row" href={a.href||'/agenda'} key={a.id}><time>{a.time}</time><div><strong>{a.title}</strong><span>{a.subtitle}</span></div>{a.badge?<Badge tone="primary">{a.badge}</Badge>:null}</a>):<Empty>Nessun impegno programmato.</Empty>}</div><a className="iu-link" href="/agenda">Vai all'agenda completa -&gt;</a></Panel>
}

function Operations({ data }:{data:DashboardData}) {
  return <Panel title="Centro operativo di oggi" icon={<Crosshair size={17}/>} count={data.operations.length}>{data.operations.length?<div className="iu-ops">{data.operations.map(op=><div className="iu-op" key={op.id}><i className={`tone-${op.tone||'primary'}`}/><div><strong>{op.title}</strong><span>{op.subtitle}</span></div><a href={op.href||'#'}>{op.badge||'Apri'}</a></div>)}</div>:<Empty/>}<a className="iu-link" href="/workspace-intelligente">Vai alla regia operativa -&gt;</a></Panel>
}

function Completion({ data }:{data:DashboardData}) {
  const c=data.completion
  return <Panel title="Anagrafiche ancora da completare" icon={<Home size={17}/>} count={c.totalMissing}><div className="iu-completion"><div className="iu-ring" style={{background:`conic-gradient(var(--iu-blue-600) ${c.percent}%, var(--iu-slate-100) 0)`}}><div><strong>{c.percent}%</strong><span>Completate</span></div></div><div className="iu-legend"><strong>Da completare: {c.totalMissing}</strong>{c.items.map(x=><span key={x.label}><i/>{x.label}<b>{x.count}</b></span>)}</div></div><a className="iu-link" href="/clienti">Vai alle anagrafiche -&gt;</a></Panel>
}

function Compact({ title, icon, count, rows, href }:{title:string; icon:ReactNode; count:number; rows:Row[]; href:string}) {
  return <Panel title={title} icon={icon} count={count}>{rows.length?<div className="iu-compact">{rows.map(r=><a className="iu-compact-row" href={r.href||href} key={r.id}><div><strong>{r.title}</strong><span>{r.subtitle}</span></div>{r.badge?<Badge tone={r.tone||'neutral'}>{r.badge}</Badge>:null}</a>)}</div>:<Empty/>}<a className="iu-link" href={href}>Vai -&gt;</a></Panel>
}

function Donut({ data }:{data:DashboardData}) {
  let cur=0
  const parts=data.deadlines.filter(d=>d.percent>0).map(d=>{const s=cur; cur+=d.percent; return `${toneColor[d.tone]} ${s}% ${cur}%`})
  const total=data.deadlines.reduce((a,b)=>a+b.count,0)
  const chart=parts.length?`conic-gradient(${parts.join(',')})`:'conic-gradient(var(--iu-slate-100) 0 100%)'
  return <Panel title="Scadenze per priorita" icon={<Sparkles size={17}/>} count={total}><div className="iu-deadlines"><div className="iu-donut" style={{background:chart}}><div><strong>{total}</strong><span>Totali</span></div></div><div className="iu-deadlines__legend">{data.deadlines.map(d=><span key={d.label}><i style={{background:toneColor[d.tone]}}/>{d.label}<b>{d.percent}%</b></span>)}</div></div><a className="iu-link" href="/scadenziario">Vai a Scadenze e Termini -&gt;</a></Panel>
}

function Economic({ data }:{data:DashboardData}) {
  return <Panel title="Economico rapido" icon={<UsersRound size={17}/>}><div className="iu-economy">{data.economic.map(e=><div className="iu-money" key={e.label}><span>{e.label}</span><strong>{e.value}</strong><small>{e.note}{e.delta?<b>{e.delta}</b>:null}</small></div>)}</div><a className="iu-link" href="/fatturazione">Vai al controllo economico -&gt;</a></Panel>
}

function Lex({ data }:{data:DashboardData}) {
  return <Panel title="Suggerimenti Lex AI" icon={<Sparkles size={17}/>} count={data.lex.length}>{data.lex.length?<div className="iu-lex">{data.lex.map(s=><div key={s}><Sparkles size={15}/><span>{s}</span></div>)}</div>:<Empty>Nessun suggerimento prioritario.</Empty>}<a className="iu-link" href="/lex">Apri Lex AI -&gt;</a></Panel>
}

export default function App() {
  const [data,setData]=useState<DashboardData>(emptyDashboard)
  const [loading,setLoading]=useState(true)
  const [sidebarCollapsed,setSidebarCollapsed]=useState(false)
  const [mobileMenuOpen,setMobileMenuOpen]=useState(false)
  useEffect(()=>{let ok=true; getDashboard().then(d=>{if(ok)setData(d)}).finally(()=>{if(ok)setLoading(false)}); return()=>{ok=false}},[])
  return <div className={`iu-shell ${sidebarCollapsed?'iu-shell--collapsed':''}`}><Sidebar collapsed={sidebarCollapsed} mobileOpen={mobileMenuOpen} onToggle={()=>setSidebarCollapsed(v=>!v)}/>{mobileMenuOpen?<button className="iu-sidebar-scrim" type="button" aria-label="Chiudi menu" onClick={()=>setMobileMenuOpen(false)}/>:null}<div className="iu-main"><Topbar onOpenMenu={()=>setMobileMenuOpen(true)}/><main className="iu-content"><div className="iu-page-heading"><div><h1>Panoramica</h1><p>Centro operativo dello studio</p></div><span className={`iu-sync ${loading?'':'ok'}`}>{loading?'Sincronizzazione dati...':'Dati aggiornati'}</span></div><section className="iu-metrics">{data.metrics.map(m=><MetricCard item={m} key={m.id}/>)}</section><section className="iu-grid"><div className="span3"><Panel title="Ultime PEC ricevute" icon={<Mail size={17}/>} count={data.pec.length}><List rows={data.pec} href="/email"/><a className="iu-link" href="/email">Vai alla casella PEC -&gt;</a></Panel></div><div className="span3"><Panel title="Email recenti" icon={<Mail size={17}/>} count={data.emails.length}><List rows={data.emails} avatar href="/email"/><a className="iu-link" href="/email">Vai alla posta -&gt;</a></Panel></div><div className="span3"><Panel title="Messaggi recenti dai clienti" icon={<MessageCircle size={17}/>} count={data.messages.length}><List rows={data.messages} avatar href="/messaggi"/><a className="iu-link" href="/messaggi">Vai ai messaggi -&gt;</a></Panel></div><div className="span3"><Agenda data={data}/></div><div className="span4"><Operations data={data}/></div><div className="span3"><Completion data={data}/></div><div className="span3"><Compact title="Conferimenti incarico mancanti" icon={<UsersRound size={17}/>} count={data.engagements.length} rows={data.engagements} href="/preventivi"/></div><div className="span2"><Compact title="Fascicoli con priorita alta" icon={<BriefcaseBusiness size={17}/>} count={data.matters.length} rows={data.matters} href="/fascicoli"/></div><div className="span4"><Donut data={data}/></div><div className="span5"><Economic data={data}/></div><div className="span3"><Lex data={data}/></div></section></main></div><nav className="iu-mobile"><a className="active" href="/app-v2"><LayoutDashboard size={18}/>Home</a><a href="/fascicoli"><BriefcaseBusiness size={18}/>Fascicoli</a><a href="/agenda"><CalendarDays size={18}/>Agenda</a><a href="/messaggi"><MessageCircle size={18}/>Messaggi</a><a href="/lex"><Sparkles size={18}/>Lex</a></nav></div>
}
