import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { AlertTriangle, CheckCircle2, FolderOpen, KeyRound, ShieldCheck, UsersRound } from 'lucide-react'
import { Badge } from './dashboard'
import { FloatingLex } from './FloatingLex'
import { getCartelleCondivisePage, type CartelleCondiviseData, type ManagedFolder, type ReceivedFolder, type ReceivedMatter } from '../cartelleCondiviseData'
import './CartelleCondivisePage.css'

function csrfToken(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content || ''
}

function StatCard({ label, value, icon }: { label: string; value: string | number; icon: ReactNode }) {
  return (
    <article className="iu-share-stat">
      <span>{icon}</span>
      <strong>{value}</strong>
      <small>{label}</small>
    </article>
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
        {item.openHref ? <a href={item.openHref}>Apri cliente</a> : null}
        {item.manageHref ? <a href={item.manageHref}>Gestisci collaboratori</a> : null}
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
        {item.openHref ? <a href={item.openHref}>Apri cartella cliente</a> : <span>Accesso non disponibile</span>}
        {item.manageHref ? <a href={item.manageHref}>Gestisci accesso</a> : null}
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
      {item.href ? <a href={item.href}>Apri fascicolo</a> : null}
    </article>
  )
}

function ManagerView({ data }: { data: CartelleCondiviseData }) {
  if (data.emptyStates.noManagedFolders) {
    return <div className="iu-share-empty"><FolderOpen size={26}/><strong>Nessuna cartella gestita</strong><span>Le cartelle condivise appariranno qui quando saranno associati collaboratori reali.</span></div>
  }
  return <div className="iu-share-grid">{data.managedFolders.map((folder) => <ManagedFolderCard item={folder} key={folder.client.id} />)}</div>
}

function CollaboratorView({ data }: { data: CartelleCondiviseData }) {
  if (data.emptyStates.noReceivedFolders && !data.receivedMatters.length) {
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

  useEffect(() => {
    let active = true
    getCartelleCondivisePage().then((payload) => { if (active) setData(payload) })
    return () => { active = false }
  }, [])

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
        const refreshed = await getCartelleCondivisePage()
        setData(refreshed)
      }
    } catch {
      setMessage('Pulizia non completata.')
    } finally {
      setBusy(false)
    }
  }

  if (!data) {
    return <main className="iu-content iu-share-page iusentra-route-sequence"><div className="iu-share-loading">Caricamento cartelle condivise...</div></main>
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
          <a href={data.actions.clients}>Clienti</a>
          <a href={data.actions.audit}>Registro attivita</a>
          <a href={data.actions.gdpr}>Registro GDPR</a>
          {data.permissions.canCleanExpired ? <button type="button" onClick={cleanupExpired} disabled={busy}>{busy ? 'Pulizia...' : 'Pulisci scaduti'}</button> : null}
        </div>
      </section>

      {message ? <div className="iu-share-message" role="status">{message}</div> : null}

      <section className="iu-share-stats">
        <StatCard icon={<FolderOpen size={18}/>} label="Cartelle condivise" value={data.stats.sharedFolders} />
        <StatCard icon={<UsersRound size={18}/>} label="Accessi totali" value={data.stats.totalAccesses} />
        <StatCard icon={<AlertTriangle size={18}/>} label="Accessi scaduti" value={data.stats.expiredAccesses} />
        <StatCard icon={<AlertTriangle size={18}/>} label="In scadenza 7 giorni" value={data.stats.expiring7Days} />
        <StatCard icon={<KeyRound size={18}/>} label="Link temporanei attivi" value={data.stats.activeTemporaryLinks} />
        <StatCard icon={<FolderOpen size={18}/>} label="Fascicoli condivisi" value={data.stats.sharedMatters} />
      </section>

      <WarningStrip data={data} />

      <section className="iu-share-section">
        <div className="iu-share-section__head">
          <div>
            <span className="iu-share-kicker">{data.mode === 'gestore' ? 'Modalita gestore' : 'Modalita collaboratore'}</span>
            <h2>{data.mode === 'gestore' ? 'Cartelle gestite' : 'Accessi ricevuti'}</h2>
          </div>
          {data.emptyStates.noExpiringAccesses ? <Badge tone="success">Nessun accesso in scadenza</Badge> : <Badge tone="warning">Accessi da verificare</Badge>}
        </div>
        {data.mode === 'gestore' ? <ManagerView data={data} /> : <CollaboratorView data={data} />}
      </section>

      {data.mode === 'gestore' && data.receivedFolders.length ? (
        <section className="iu-share-section">
          <div className="iu-share-section__head"><h2>Accessi ricevuti dal profilo corrente</h2></div>
          <div className="iu-share-grid">{data.receivedFolders.map((folder) => <ReceivedFolderCard item={folder} key={folder.client.id} />)}</div>
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
