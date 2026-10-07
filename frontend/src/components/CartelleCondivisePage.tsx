import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { AlertTriangle, CheckCircle2, FolderOpen, KeyRound, RefreshCw, ShieldCheck, Trash2, UsersRound } from 'lucide-react'
import { Badge } from './dashboard'
import { FloatingLex } from './FloatingLex'
import { getCartelleCondivisePage, type CartelleCondiviseData, type ManagedFolder, type ReceivedFolder, type ReceivedMatter } from '../cartelleCondiviseData'
import './CartelleCondivisePage.css'
import { useOperationalRefresh } from '../hooks/useOperationalRefresh'
import type { SharedAccess } from '../cartelleCondiviseData'

type ShareFilter = 'folders' | 'accesses' | 'expired' | 'expiring' | 'links' | 'matters'

function csrfToken(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content || ''
}

function StatCard({ label, value, icon, active, onClick }: { label: string; value: string | number; icon: ReactNode; active: boolean; onClick: () => void }) {
  return (
    <button type="button" className="iu-share-stat" aria-pressed={active} onClick={onClick}>
      <span>{icon}</span>
      <strong>{value}</strong>
      <small>{label}</small>
    </button>
  )
}

function WarningStrip({ data }: { data: CartelleCondiviseData }) {
  if (!data.warnings.length) {
    return (
      <section className="iu-share-warnings ok">
        <CheckCircle2 size={18}/>
        <strong>Nessun avviso privacy attivo</strong>
        <span>Non risultano accessi scaduti o in scadenza nei dati correnti.</span>
      </section>
    )
  }
  return (
    <section className="iu-share-warnings" aria-label="Avvisi privacy">
      {data.warnings.map((warning) => (
        <article key={warning.label}>
          <AlertTriangle size={18}/>
          <div><strong>{warning.label}</strong><span>{warning.count}</span></div>
          <Badge tone={warning.tone}>Da verificare</Badge>
        </article>
      ))}
    </section>
  )
}

function AccessList({ accesses }: { accesses: ManagedFolder['accesses'] }) {
  if (!accesses.length) return <p className="iu-share-muted">Nessun collaboratore assegnato.</p>
  return (
    <div className="iu-share-accesses">
      {accesses.map((access) => (
        <div key={`${access.idUser}-${access.role}`}>
          <div>
            <strong>{access.name}</strong>
            <span>{access.username || access.sharedBy}</span>
          </div>
          <Badge tone={access.roleTone}>{access.roleLabel}</Badge>
          <small>{access.deadlineLabel}</small>
        </div>
      ))}
    </div>
  )
}

function ManagedFolderCard({ item }: { item: ManagedFolder }) {
  return (
    <article className="iu-share-card">
      <div className="iu-share-card__head">
        <div>
          <span className="iu-share-kicker"><FolderOpen size={15}/> Cartella gestita</span>
          <h3>{item.client.name}</h3>
        </div>
        <Badge tone={item.expiredCount ? 'danger' : item.expiringCount ? 'warning' : 'success'}>{item.collaboratorsCount} collaboratori</Badge>
      </div>
      <div className="iu-share-card__facts">
        <span><b>Accessi scaduti</b>{item.expiredCount}</span>
        <span><b>In scadenza</b>{item.expiringCount}</span>
        <span><b>Link attivi</b>{item.activeLinks.length}</span>
      </div>
      <AccessList accesses={item.accesses} />
      {item.activeLinks.length ? (
        <div className="iu-share-links">
          {item.activeLinks.map((link) => (
            <span key={link.id}><KeyRound size={14}/> {link.roleLabel} · scade {link.expiresLabel}</span>
          ))}
        </div>
      ) : null}
      <div className="iu-share-actions">
        {item.openHref ? <a className="iu-button" href={item.openHref}>Apri cliente</a> : null}
        {item.manageHref ? <a className="iu-button" href={item.manageHref}>Gestisci collaboratori</a> : null}
      </div>
    </article>
  )
}

function ReceivedFolderCard({ item }: { item: ReceivedFolder }) {
  return (
    <article className="iu-share-card">
      <div className="iu-share-card__head">
        <div>
          <span className="iu-share-kicker"><UsersRound size={15}/> Accesso ricevuto</span>
          <h3>{item.client.name}</h3>
        </div>
        <Badge tone={item.access.expired ? 'danger' : item.access.expiring ? 'warning' : item.access.roleTone}>{item.access.roleLabel}</Badge>
      </div>
      <p>{item.access.notes || 'Nessuna nota associata alla condivisione.'}</p>
      <div className="iu-share-card__facts">
        <span><b>Scadenza</b>{item.access.deadlineLabel}</span>
        <span><b>Condiviso da</b>{item.access.sharedBy || 'Studio'}</span>
      </div>
      <div className="iu-share-actions">
        {item.openHref ? <a className="iu-button" href={item.openHref}>Apri cartella cliente</a> : <span>Accesso non disponibile</span>}
        {item.manageHref ? <a className="iu-button" href={item.manageHref}>Gestisci accesso</a> : null}
      </div>
    </article>
  )
}

function ReceivedMatterCard({ item }: { item: ReceivedMatter }) {
  return (
    <article className="iu-share-card compact">
      <div>
        <span className="iu-share-kicker">Fascicolo condiviso</span>
        <h3>{item.title}</h3>
        <p>{item.client.name} · {item.number || item.id}</p>
      </div>
      <Badge tone={item.access.roleTone}>{item.access.roleLabel}</Badge>
      {item.href ? <a className="iu-button" href={item.href}>Apri fascicolo</a> : null}
    </article>
  )
}

function ManagerView({ data }: { data: CartelleCondiviseData }) {
  if (!data.managedFolders.length && !data.managedMatters.length) {
    return <div className="iu-share-empty"><FolderOpen size={26}/><strong>Nessuna condivisione da visualizzare</strong><span>Nessuna cartella o fascicolo corrisponde ai filtri. Puoi cambiare ricerca o selezionare un altro indicatore.</span></div>
  }
  return <div className="iu-share-grid">{data.managedFolders.map((folder) => <ManagedFolderCard item={folder} key={folder.client.id} />)}{data.managedMatters.map(matter => <article className="iu-share-card" key={matter.id}><header><span className="iu-share-kicker">Fascicolo condiviso</span><h3>{matter.title}</h3><p>{matter.client.name} · {matter.number || 'Numero di causa non indicato'}</p></header><AccessList accesses={matter.accesses}/><div className="iu-share-actions"><a className="iu-button" href={matter.href}>Apri fascicolo</a></div></article>)}</div>
}

function CollaboratorView({ data }: { data: CartelleCondiviseData }) {
  if (!data.receivedFolders.length && !data.receivedMatters.length) {
    return <div className="iu-share-empty"><UsersRound size={26}/><strong>Nessun accesso ricevuto</strong><span>Non risultano cartelle o fascicoli condivisi con questo profilo.</span></div>
  }
  return (
    <div className="iu-share-grid">
      {data.receivedFolders.map((folder) => <ReceivedFolderCard item={folder} key={folder.client.id} />)}
      {data.receivedMatters.map((matter) => <ReceivedMatterCard item={matter} key={matter.id} />)}
    </div>
  )
}

export function CartelleCondivisePage() {
  const [data, setData] = useState<CartelleCondiviseData | null>(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<ShareFilter>('folders')
  const mounted = useRef(false)
  const refreshFlight = useRef<Promise<void> | null>(null)
  const refresh = useCallback(() => {
    if (refreshFlight.current) return refreshFlight.current
    setRefreshing(true)
    const flight = getCartelleCondivisePage().then(payload => {
      if (mounted.current) { setData(payload); setError('') }
    }).catch((reason: unknown) => {
      if (mounted.current) setError(reason instanceof Error ? reason.message : 'Caricamento non riuscito. Riprova.')
    }).finally(() => { refreshFlight.current = null; if (mounted.current) setRefreshing(false) })
    refreshFlight.current = flight
    return flight
  }, [])

  useEffect(() => {
    mounted.current = true
    void refresh()
    return () => { mounted.current = false }
  }, [refresh])
  useOperationalRefresh(['clienti', 'fascicoli', 'utenti'], refresh)
  const visible = useMemo(() => {
    if (!data) return null
    const normalize = (value: string) => value.toLocaleLowerCase('it-IT').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    const needle = normalize(query.trim())
    const matches = (value: unknown) => !needle || normalize(JSON.stringify(value)).includes(needle)
    const accessMatches = (access: SharedAccess) => filter === 'expired' ? access.expired : filter === 'expiring' ? access.expiring : true
    const foldersAllowed = filter !== 'matters'
    const mattersAllowed = filter !== 'folders' && filter !== 'links'
    const managedFolders = foldersAllowed ? data.managedFolders.filter(matches).flatMap(folder => {
      const accesses = filter === 'links' ? [] : folder.accesses.filter(accessMatches)
      const activeLinks = filter === 'expired' || filter === 'expiring' || filter === 'accesses' ? [] : folder.activeLinks
      return accesses.length || activeLinks.length ? [{ ...folder, accesses, activeLinks, collaboratorsCount: accesses.length, expiredCount: accesses.filter(access => access.expired).length, expiringCount: accesses.filter(access => access.expiring).length }] : []
    }) : []
    return { ...data, managedFolders,
      managedMatters: mattersAllowed ? data.managedMatters.filter(matches).flatMap(matter => { const accesses = matter.accesses.filter(accessMatches); return accesses.length ? [{ ...matter, accesses }] : [] }) : [],
      receivedFolders: foldersAllowed && filter !== 'links' ? data.receivedFolders.filter(folder => matches(folder) && accessMatches(folder.access)) : [],
      receivedMatters: mattersAllowed ? data.receivedMatters.filter(matter => matches(matter) && accessMatches(matter.access)) : [],
    }
  }, [data, filter, query])

  const cleanupExpired = async () => {
    if (!data?.permissions.canCleanExpired) return
    setBusy(true)
    setMessage('')
    try {
      const response = await fetch(data.actions.cleanupExpired, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { Accept: 'application/json', 'X-CSRF-Token': csrfToken() },
      })
      const payload = await response.json() as { accessi_rimossi?: number; link_rimossi?: number; errore?: string }
      if (!response.ok || payload.errore) {
        setMessage(payload.errore || 'Pulizia non completata.')
      } else {
        setMessage(`Pulizia completata: ${payload.accessi_rimossi ?? 0} accessi e ${payload.link_rimossi ?? 0} link rimossi.`)
        await refresh()
      }
    } catch {
      setMessage('Pulizia non completata.')
    } finally {
      setBusy(false)
    }
  }

  if (!data) {
    return <main className="iu-content iu-share-page iusentra-route-sequence">{error ? <div role="alert" className="iu-share-message">{error}<button type="button" className="iu-button iu-button--secondary" onClick={() => { void refresh() }}>Riprova</button></div> : <div className="iu-share-loading" role="status">Caricamento cartelle condivise…</div>}</main>
  }

  return (
    <main className="iu-content iu-share-page iusentra-route-sequence">
      <section className="iu-share-hero">
        <div>
          <span className="iu-share-kicker"><ShieldCheck size={16}/> Cartelle condivise</span>
          <h1>Cartelle condivise</h1>
          <p>Accessi, ruoli, scadenze e presidi privacy sulle cartelle cliente e sui fascicoli condivisi.</p>
        </div>
        <div className="iu-share-hero__actions">
          <button type="button" className="iu-button iu-button--secondary" disabled={refreshing || busy} onClick={() => { void refresh() }}><RefreshCw size={16}/>{refreshing ? 'Aggiornamento…' : 'Aggiorna'}</button>
          <a className="iu-button iu-button--secondary" href={data.actions.clients}><UsersRound size={16}/>Clienti</a>
          <a className="iu-button iu-button--secondary" href={data.actions.audit}><CheckCircle2 size={16}/>Registro attività</a>
          <a className="iu-button iu-button--secondary" href={data.actions.gdpr}><ShieldCheck size={16}/>Registro GDPR</a>
          {data.permissions.canCleanExpired ? <button type="button" className="iu-button iu-button--secondary iu-share-cleanup" onClick={cleanupExpired} disabled={busy}><Trash2 size={16}/>{busy ? 'Pulizia…' : 'Pulisci scaduti'}</button> : null}
        </div>
      </section>

      {message ? <div className="iu-share-message" role="status">{message}</div> : null}
      {error ? <div className="iu-share-message" role="alert">{error}</div> : null}

      <section className="iu-share-stats">
        <StatCard icon={<FolderOpen size={18}/>} label="Cartelle condivise" value={data.stats.sharedFolders} active={filter === 'folders'} onClick={() => setFilter('folders')}/>
        <StatCard icon={<UsersRound size={18}/>} label="Accessi totali" value={data.stats.totalAccesses} active={filter === 'accesses'} onClick={() => setFilter('accesses')}/>
        <StatCard icon={<AlertTriangle size={18}/>} label="Accessi scaduti" value={data.stats.expiredAccesses} active={filter === 'expired'} onClick={() => setFilter('expired')}/>
        <StatCard icon={<AlertTriangle size={18}/>} label="In scadenza 7 giorni" value={data.stats.expiring7Days} active={filter === 'expiring'} onClick={() => setFilter('expiring')}/>
        <StatCard icon={<KeyRound size={18}/>} label="Link temporanei attivi" value={data.stats.activeTemporaryLinks} active={filter === 'links'} onClick={() => setFilter('links')}/>
        <StatCard icon={<FolderOpen size={18}/>} label="Fascicoli condivisi" value={data.stats.sharedMatters} active={filter === 'matters'} onClick={() => setFilter('matters')}/>
      </section>
      <section className="iu-share-filters" aria-label="Ricerca condivisioni"><label>Cerca cliente, fascicolo o collaboratore<input type="search" value={query} onChange={event => setQuery(event.currentTarget.value)}/></label><button type="button" className="iu-button iu-button--secondary" onClick={() => { setQuery(''); setFilter('folders') }}>Azzera filtri</button><span role="status">{visible ? (data.mode === 'gestore' ? visible.managedFolders.length + visible.managedMatters.length : visible.receivedFolders.length + visible.receivedMatters.length) : 0} risultati</span></section>

      <WarningStrip data={data} />

      <section className="iu-share-section">
        <div className="iu-share-section__head">
          <div>
            <span className="iu-share-kicker">{data.mode === 'gestore' ? 'Modalità gestore' : 'Modalità collaboratore'}</span>
            <h2>{filter === 'folders' ? (data.mode === 'gestore' ? 'Cartelle gestite' : 'Cartelle ricevute') : filter === 'matters' ? 'Fascicoli condivisi' : filter === 'expired' ? 'Accessi scaduti' : filter === 'expiring' ? 'Accessi in scadenza entro 7 giorni' : filter === 'links' ? 'Link temporanei attivi' : 'Condivisioni e accessi'}</h2>
          </div>
          {data.emptyStates.noExpiringAccesses ? <Badge tone="success">Nessun accesso in scadenza</Badge> : <Badge tone="warning">Accessi da verificare</Badge>}
        </div>
        {visible ? (data.mode === 'gestore' ? <ManagerView data={visible} /> : <CollaboratorView data={visible} />) : null}
      </section>

      {data.mode === 'gestore' && visible?.receivedFolders.length ? (
        <section className="iu-share-section">
          <div className="iu-share-section__head"><h2>Accessi ricevuti dal profilo corrente</h2></div>
          <div className="iu-share-grid">{visible.receivedFolders.map((folder) => <ReceivedFolderCard item={folder} key={folder.client.id} />)}</div>
        </section>
      ) : null}

      <FloatingLex
        context="cartelle-condivise"
        title="Lex condivisioni"
        body="Legge ruoli, scadenze e avvisi privacy per aiutarti a verificare accessi e cartelle condivise."
        primaryHref={data.actions.lex}
        primaryLabel="Apri Lex condivisioni"
        secondaryHref={data.actions.gdpr}
        secondaryLabel="Registro GDPR"
      />
    </main>
  )
}
