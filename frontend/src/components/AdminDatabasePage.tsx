import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  CloudUpload,
  Database,
  Download,
  ExternalLink,
  Gauge,
  HardDrive,
  RefreshCw,
  SearchCheck,
  ShieldCheck,
  Table,
  UploadCloud,
  Zap,
} from 'lucide-react'
import { Badge, Button, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import {
  emptyAdminDatabasePage,
  getAdminDatabasePage,
  type AdminDatabaseIntegrityResult,
  type AdminDatabaseMigrationResult,
  type AdminDatabaseModule,
  type AdminDatabaseOptimizeResult,
  type AdminDatabasePageData,
} from '../adminDatabaseData'
import type { Tone } from '../data'
import './AdminDatabasePage.css'

type AsyncState = 'idle' | 'loading' | 'success' | 'error'

type OperationState<T> = {
  status: AsyncState
  message: string
  payload: T | null
}

const emptyIntegrity: OperationState<AdminDatabaseIntegrityResult> = { status: 'idle', message: '', payload: null }
const emptyOptimization: OperationState<AdminDatabaseOptimizeResult> = { status: 'idle', message: '', payload: null }
const emptyMigration: OperationState<AdminDatabaseMigrationResult> = { status: 'idle', message: '', payload: null }

function sourceLabel(source: string): string {
  if (source === 'repository_reali') return 'Dati applicativi'
  if (source === 'errore_controllato') return 'Dati parziali'
  return source || 'Database'
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat('it-IT').format(value)
}

function formatPercent(value: number): string {
  return `${new Intl.NumberFormat('it-IT', { maximumFractionDigits: 1 }).format(value)}%`
}

function problemTone(level: string): Tone {
  const raw = level.toLowerCase()
  if (raw.includes('crit') || raw.includes('error')) return 'danger'
  if (raw.includes('warn') || raw.includes('avv')) return 'warning'
  return 'info'
}

function statusTone(status: AsyncState): Tone {
  if (status === 'success') return 'success'
  if (status === 'error') return 'danger'
  if (status === 'loading') return 'info'
  return 'neutral'
}

function csrfToken(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content || ''
}

async function jsonRequest<T>(url: string, init: RequestInit = {}): Promise<T> {
  const method = String(init.method || 'GET').toUpperCase()
  const response = await fetch(url, {
    credentials: 'same-origin',
    cache: 'no-store',
    headers: {
      Accept: 'application/json',
      ...(method === 'GET' ? {} : { 'X-CSRF-Token': csrfToken() }),
      ...(init.headers || {}),
    },
    ...init,
  })
  const contentType = response.headers.get('content-type') || ''
  const payload = contentType.includes('application/json') ? await response.json() : { errore: await response.text() }
  if (!response.ok) {
    const errorMessage = typeof payload?.errore === 'string' ? payload.errore : 'Operazione non completata.'
    throw new Error(errorMessage)
  }
  return payload as T
}

function StatCard({ icon, label, value, note, tone = 'primary' }: { icon: ReactNode; label: string; value: string; note: string; tone?: Tone }) {
  return (
    <article className={`iu-db-stat iu-db-stat--${tone}`}>
      <div>{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  )
}

function ModuleTable({ modules }: { modules: AdminDatabaseModule[] }) {
  if (!modules.length) {
    return (
      <div className="iu-db-empty">
        <Database size={24}/>
        <strong>Nessun modulo dati rilevato</strong>
        <span>Il runtime non ha restituito moduli monitorabili per questa sessione.</span>
      </div>
    )
  }

  return (
    <div className="iu-db-table-wrap">
      <table className="iu-db-table">
        <thead>
          <tr>
            <th>Modulo</th>
            <th>Tipo</th>
            <th>Record</th>
            <th>Dimensione</th>
            <th>Ultima modifica</th>
            <th>Stato</th>
          </tr>
        </thead>
        <tbody>
          {modules.map((module) => (
            <tr key={module.id}>
              <td>
                <strong>{module.label}</strong>
                <span>{module.path || 'Percorso non configurato'}</span>
              </td>
              <td>
                <Badge tone={module.kind.tone}>{module.kind.label}</Badge>
                {module.migratableSqlite ? <Badge tone="success">Migrabile</Badge> : null}
              </td>
              <td>{formatNumber(module.records)}</td>
              <td>{module.sizeLabel}</td>
              <td>{module.lastModifiedLabel}</td>
              <td>
                <Badge tone={module.status.tone}>{module.status.label}</Badge>
                {module.status.message ? <span>{module.status.message}</span> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function OperationAlert({ state, idleText }: { state: OperationState<unknown>; idleText: string }) {
  if (state.status === 'idle') return <p className="iu-db-muted">{idleText}</p>
  return (
    <div className={`iu-db-operation-alert iu-db-operation-alert--${statusTone(state.status)}`}>
      {state.status === 'success' ? <CheckCircle2 size={16}/> : <AlertTriangle size={16}/>}
      <span>{state.message}</span>
    </div>
  )
}

function IntegrityResult({ result }: { result: AdminDatabaseIntegrityResult | null }) {
  if (!result) return null
  const repairs = result.riparazioni || []
  const problems = result.problemi || []
  return (
    <div className="iu-db-integrity-result">
      {repairs.length ? (
        <div className="iu-db-repairs">
          {repairs.map((repair, index) => (
            <article key={`${repair.modulo}-${repair.id_record}-${repair.campo}-${index}`}>
              <Badge tone={repair.riuscita ? 'success' : 'danger'}>{repair.riuscita ? 'Riparato' : 'Errore'}</Badge>
              <strong>{repair.modulo} · {repair.campo}</strong>
              <span>{repair.dettagli || repair.azione}</span>
              {repair.valore_precedente ? <small>Valore originale: {repair.valore_precedente}</small> : null}
            </article>
          ))}
        </div>
      ) : null}
      {!problems.length ? (
        <div className="iu-db-okline"><CheckCircle2 size={16}/>Nessuna anomalia referenziale residua.</div>
      ) : (
        <div className="iu-db-problems">
          {problems.map((problem, index) => (
            <article key={`${problem.modulo}-${problem.tipo}-${index}`}>
              <Badge tone={problemTone(problem.livello)}>{problem.livello || 'Avviso'}</Badge>
              <strong>{problem.modulo} · {problem.tipo}</strong>
              <span>{problem.descrizione}</span>
              {problem.suggerimento ? <small>{problem.suggerimento}</small> : null}
            </article>
          ))}
        </div>
      )}
    </div>
  )
}

function OptimizationResult({ result }: { result: AdminDatabaseOptimizeResult | null }) {
  if (!result) return null
  if (!result.risultati.length) return <p className="iu-db-muted">Nessun modulo ottimizzato.</p>
  return (
    <div className="iu-db-mini-table">
      {result.risultati.map((item, index) => (
        <div key={`${item.modulo}-${item.operazione}-${index}`}>
          <span>
            <strong>{item.modulo}</strong>
            <small>{item.operazione}</small>
          </span>
          <Badge tone={item.ok || item.riuscita ? 'success' : 'danger'}>{item.ok || item.riuscita ? 'OK' : 'Errore'}</Badge>
          <span>{item.messaggio || item.dettagli || 'Operazione completata'}</span>
          <span>{formatNumber(item.risparmio_bytes)} B</span>
        </div>
      ))}
    </div>
  )
}

function MigrationResult({ result }: { result: AdminDatabaseMigrationResult | null }) {
  if (!result) return null
  return (
    <div className="iu-db-migration-result">
      <div className="iu-db-okline">
        {result.ok ? <CheckCircle2 size={16}/> : <AlertTriangle size={16}/>}
        {result.messaggio || result.errore || 'Operazione completata'}
      </div>
      {result.percorso_db ? <p><strong>Database:</strong> {result.percorso_db}</p> : null}
      <p><strong>Record migrati:</strong> {formatNumber(result.record_migrati || 0)}</p>
      {result.istruzione ? <p>{result.istruzione}</p> : null}
      {Object.keys(result.per_modulo || {}).length ? (
        <div className="iu-db-module-counts">
          {Object.entries(result.per_modulo).map(([name, count]) => (
            <span key={name}><strong>{name}</strong>{formatNumber(count)}</span>
          ))}
        </div>
      ) : null}
      {result.avvisi?.length ? (
        <div className="iu-db-warning-list">
          {result.avvisi.map((warning) => <span key={warning}><AlertTriangle size={14}/>{warning}</span>)}
        </div>
      ) : null}
      {result.errori?.length ? (
        <div className="iu-db-error-list">
          {result.errori.map((error) => <span key={error}><AlertTriangle size={14}/>{error}</span>)}
        </div>
      ) : null}
    </div>
  )
}

function UsagePanel({ data }: { data: AdminDatabasePageData }) {
  if (!data.usage.available && data.usage.error) {
    return <div className="iu-db-operation-alert iu-db-operation-alert--warning"><AlertTriangle size={16}/>{data.usage.error}</div>
  }
  return (
    <div className="iu-db-usage">
      <div className="iu-db-usage__summary">
        <span><strong>{formatNumber(data.usage.totalEvents)}</strong> eventi audit</span>
        <span><strong>{data.usage.peakHour === null ? 'n.d.' : `${data.usage.peakHour}:00`}</strong> ora di picco</span>
        <span><strong>{formatPercent(data.usage.errorRate)}</strong> tasso errori</span>
      </div>
      <div className="iu-db-usage__lists">
        <div>
          <h3>Azioni frequenti</h3>
          {data.usage.topActions.length ? data.usage.topActions.map((item) => (
            <span key={item.id}><strong>{item.label}</strong>{formatNumber(item.count)}</span>
          )) : <small>Nessuna azione auditata nel periodo.</small>}
        </div>
        <div>
          <h3>Utenti attivi</h3>
          {data.usage.topUsers.length ? data.usage.topUsers.map((item) => (
            <span key={item.id}><strong>{item.label}</strong>{formatNumber(item.count)}</span>
          )) : <small>Nessun utente rilevato nel periodo.</small>}
        </div>
      </div>
    </div>
  )
}

export function AdminDatabasePage() {
  const [data, setData] = useState<AdminDatabasePageData>(emptyAdminDatabasePage)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [integrity, setIntegrity] = useState<OperationState<AdminDatabaseIntegrityResult>>(emptyIntegrity)
  const [optimization, setOptimization] = useState<OperationState<AdminDatabaseOptimizeResult>>(emptyOptimization)
  const [migration, setMigration] = useState<OperationState<AdminDatabaseMigrationResult>>(emptyMigration)

  const loadData = async () => {
    setLoading(true)
    setError('')
    try {
      setData(await getAdminDatabasePage())
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Database amministrativo non disponibile.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    getAdminDatabasePage()
      .then((payload) => {
        if (active) setData(payload)
      })
      .catch((caught) => {
        if (active) setError(caught instanceof Error ? caught.message : 'Database amministrativo non disponibile.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [])

  const statusSummary = useMemo(() => {
    const ok = data.summary.statusCounts.OK || 0
    const warnings = (data.summary.statusCounts.NON_TROVATO || 0) + (data.summary.statusCounts.NON_CONFIGURATO || 0)
    const errors = data.summary.statusCounts.ERRORE || 0
    return { ok, warnings, errors }
  }, [data.summary.statusCounts])

  const runIntegrity = async () => {
    setIntegrity({ status: 'loading', message: 'Verifica e riparazione in corso...', payload: null })
    try {
      const payload = await jsonRequest<AdminDatabaseIntegrityResult>(data.actions.repair || data.actions.verify, { method: 'POST' })
      const repairs = payload.n_riparazioni || payload.riparazioni?.length || 0
      const message = payload.n_problemi
        ? `${repairs} problemi riparati, ${payload.n_problemi} anomalie residue da presidiare.`
        : repairs
          ? `${repairs} problemi riparati automaticamente. Integrità residua pulita.`
          : 'Integrità verificata senza anomalie.'
      setIntegrity({
        status: payload.n_problemi ? 'error' : 'success',
        message,
        payload,
      })
      await loadData()
    } catch (caught) {
      setIntegrity({ status: 'error', message: caught instanceof Error ? caught.message : 'Riparazione non completata.', payload: null })
    }
  }

  const runOptimization = async () => {
    setOptimization({ status: 'loading', message: 'Ottimizzazione in corso...', payload: null })
    try {
      const payload = await jsonRequest<AdminDatabaseOptimizeResult>(data.actions.optimize, { method: 'POST' })
      setOptimization({
        status: payload.ok ? 'success' : 'error',
        message: payload.ok ? 'Ottimizzazione completata sui moduli dati.' : (payload.errore || 'Ottimizzazione completata con errori.'),
        payload,
      })
      await loadData()
    } catch (caught) {
      setOptimization({ status: 'error', message: caught instanceof Error ? caught.message : 'Ottimizzazione non completata.', payload: null })
    }
  }

  const runMigration = async (activate = false) => {
    const action = activate ? data.actions.activateSqlite : data.actions.migrate
    setMigration({ status: 'loading', message: activate ? 'Attivazione SQLite in corso...' : 'Migrazione SQLite in corso...', payload: null })
    try {
      const payload = await jsonRequest<AdminDatabaseMigrationResult>(action, { method: 'POST' })
      setMigration({
        status: payload.ok ? 'success' : 'error',
        message: payload.messaggio || payload.errore || (payload.ok ? 'Operazione SQLite completata.' : 'Operazione SQLite completata con errori.'),
        payload,
      })
      await loadData()
    } catch (caught) {
      setMigration({ status: 'error', message: caught instanceof Error ? caught.message : 'Operazione SQLite non completata.', payload: null })
    }
  }

  return (
    <main className="iu-content iu-db-page">
      <section className="iu-db-hero">
        <div className="iu-db-hero__icon"><Database size={27}/></div>
        <div>
          <span className="iu-db-eyebrow">Amministrazione dati</span>
          <h1>{data.page.title}</h1>
          <p>{data.page.subtitle}</p>
        </div>
        <div className="iu-db-hero__actions">
          <button type="button" className="iu-button" onClick={loadData} disabled={loading}>
            <RefreshCw size={15}/>{loading ? 'Aggiornamento...' : 'Aggiorna'}
          </button>
          <Button href={data.actions.exportZip} variant="primary"><Download size={15}/>Export ZIP</Button>
        </div>
      </section>

      {error ? <div className="iu-db-operation-alert iu-db-operation-alert--danger"><AlertTriangle size={16}/>{error}</div> : null}
      {data.warning ? <div className="iu-db-operation-alert iu-db-operation-alert--warning"><AlertTriangle size={16}/>{data.warning}</div> : null}

      <section className="iu-db-stats" aria-label="Indicatori database">
        <StatCard icon={<Table size={22}/>} label="Moduli monitorati" value={formatNumber(data.summary.modulesMonitored)} note={`${statusSummary.ok} in stato OK`} tone="primary"/>
        <StatCard icon={<HardDrive size={22}/>} label="Record totali" value={formatNumber(data.summary.totalRecords)} note={`Dimensione ${data.summary.totalSizeLabel}`} tone="success"/>
        <StatCard icon={<Gauge size={22}/>} label="Frammentazione SQLite" value={formatPercent(data.summary.sqliteFragmentationPct)} note={data.sqlite.exists ? `${data.sqlite.freePages} pagine libere` : 'Snapshot non presente'} tone={data.sqlite.fragmentationPct > 20 ? 'warning' : 'info'}/>
        <StatCard icon={<CloudUpload size={22}/>} label="Migrabili SQLite" value={formatNumber(data.summary.modulesMigratableSqlite)} note={`${data.sqlite.tables.length} tabelle nello snapshot`} tone="purple"/>
        <StatCard icon={<ShieldCheck size={22}/>} label="Presidio" value={statusSummary.errors ? 'Critico' : 'Attivo'} note={`${statusSummary.warnings} avvisi configurazione`} tone={statusSummary.errors ? 'danger' : statusSummary.warnings ? 'warning' : 'success'}/>
      </section>

      <section className="iu-db-layout">
        <div className="iu-db-maincol">
          <Panel
            title="Moduli dati"
            subtitle={`Fonte: ${sourceLabel(data.source)} · generato ${data.summary.generatedLabel}`}
            icon={<Database size={17}/>}
            count={data.modules.length}
          >
            <ModuleTable modules={data.modules}/>
          </Panel>

          <Panel
            title="Verifica integrità"
            subtitle="Controllo referenziale con riparazione automatica dei problemi risolvibili."
            icon={<SearchCheck size={17}/>}
            action={(
              <button type="button" className="iu-button iu-button--primary" onClick={runIntegrity} disabled={integrity.status === 'loading'}>
                <SearchCheck size={15}/>{integrity.status === 'loading' ? 'Riparo...' : 'Verifica e ripara'}
              </button>
            )}
          >
            <OperationAlert state={integrity as OperationState<unknown>} idleText="Avvia il controllo: i problemi referenziali risolvibili vengono corretti automaticamente."/>
            <IntegrityResult result={integrity.payload}/>
          </Panel>

          <Panel
            title="Ottimizzazione"
            subtitle="Compatta e normalizza i file gestiti dal repository dati."
            icon={<Zap size={17}/>}
            action={(
              <button type="button" className="iu-button iu-button--primary" onClick={runOptimization} disabled={optimization.status === 'loading'}>
                <Zap size={15}/>{optimization.status === 'loading' ? 'Ottimizzo...' : 'Ottimizza'}
              </button>
            )}
          >
            <OperationAlert state={optimization as OperationState<unknown>} idleText="L'ottimizzazione usa la route amministrativa esistente e registra audit."/>
            <OptimizationResult result={optimization.payload}/>
          </Panel>
        </div>

        <aside className="iu-db-sidecol">
          <Panel title="SQLite" subtitle={data.sqlite.exists ? `Snapshot ${data.sqlite.sizeLabel}` : 'Snapshot non ancora disponibile'} icon={<HardDrive size={17}/>}>
            <div className="iu-db-sqlite">
              <div className="iu-db-sqlite__status">
                <Badge tone={data.sqlite.exists ? 'success' : 'warning'}>{data.sqlite.exists ? 'Presente' : 'Assente'}</Badge>
                {data.sqlite.error ? <span>{data.sqlite.error}</span> : <span>{data.sqlite.totalPages ? `${formatNumber(data.sqlite.totalPages)} pagine totali` : 'Nessun dettaglio SQLite disponibile'}</span>}
              </div>
              <div className="iu-db-sqlite__actions">
                <button type="button" className="iu-button iu-button--primary" onClick={() => runMigration(false)} disabled={migration.status === 'loading'}>
                  <UploadCloud size={15}/>{migration.status === 'loading' ? 'Migrazione...' : 'Migra JSON'}
                </button>
                <button
                  type="button"
                  className="iu-button"
                  onClick={() => {
                    if (window.confirm('Attivare SQLite operativo per questo runtime?')) void runMigration(true)
                  }}
                  disabled={migration.status === 'loading'}
                >
                  <HardDrive size={15}/>Attiva SQLite
                </button>
              </div>
              <OperationAlert state={migration as OperationState<unknown>} idleText="Migrazione e attivazione usano i POST amministrativi già auditati."/>
              <MigrationResult result={migration.payload}/>
              {data.sqlite.tables.length ? (
                <div className="iu-db-sqlite__tables">
                  {data.sqlite.tables.slice(0, 8).map((table) => (
                    <span key={table.name}><strong>{table.name}</strong>{formatNumber(table.records)}</span>
                  ))}
                </div>
              ) : null}
            </div>
          </Panel>

          <Panel title="Analisi uso" subtitle="Lettura audit amministrativa" icon={<Gauge size={17}/>}>
            <UsagePanel data={data}/>
          </Panel>

          <Panel title="Accessi collegati" subtitle="Superfici amministrative reali" icon={<ExternalLink size={17}/>}>
            <div className="iu-db-links">
                <Button href={data.actions.backup}><CloudUpload size={15}/>Backup</Button>
                <Button href={data.actions.audit}><ShieldCheck size={15}/>Registro attività</Button>
              </div>
            </Panel>
        </aside>
      </section>

      <FloatingLex
        context="database"
        title="Lex AI Database"
        body="Lex riceve il contesto della gestione database: moduli dati, migrazione SQLite, audit, export e controlli di integrità."
        primaryHref="/admin/database"
        primaryLabel="Contesto database"
        secondaryHref={data.actions.audit}
        secondaryLabel="Registro attività"
      />
    </main>
  )
}
