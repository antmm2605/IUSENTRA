import { useEffect, useMemo, useRef, useState } from 'react'
import { useOperationalRefresh } from '../hooks/useOperationalRefresh'
import { formatDateTimeIt } from '../formatting'
import { CheckCircle2, RefreshCw, Save, ShieldAlert, UsersRound, XCircle } from 'lucide-react'
import {
  allProfiloUsers,
  emptyProfiliPage,
  getProfiliPage,
  saveProfiliPermissions,
  type ProfiloMatrixRow,
  type ProfiloOverride,
  type ProfiloPermission,
  type ProfiloRole,
  type ProfiloRoleUser,
  type ProfiliPageData,
  type SaveProfiliPayload,
} from '../profiliData'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import { displaySourceLabel, displayWritesLabel } from '../displayText'
import './ProfiliPage.css'

type DraftOverride = {
  extraPermissions: string[]
  deniedPermissions: string[]
}

type SaveStatus = 'idle' | 'saving' | 'success' | 'error'
type LoadStatus = 'loading' | 'ready' | 'error'

const emptyDraft: DraftOverride = { extraPermissions: [], deniedPermissions: [] }

function formatValue(value: string | number): string {
  if (typeof value === 'number') return new Intl.NumberFormat('it-IT').format(value)
  return value
}

function formatGeneratedAt(value: string): string {
  return formatDateTimeIt(value, 'Non disponibile')
}

function sameList(a: string[], b: string[]): boolean {
  const left = [...a].sort()
  const right = [...b].sort()
  return left.length === right.length && left.every((item, index) => item === right[index])
}

function listLabel(items: string[]): string {
  return items.length ? items.join(', ') : 'nessuno'
}

function draftFromOverride(override: ProfiloOverride | undefined): DraftOverride {
  return override
    ? {
      extraPermissions: [...override.extraPermissions],
      deniedPermissions: [...override.deniedPermissions],
    }
    : emptyDraft
}

function permissionRowsByCategory(matrix: ProfiloMatrixRow[]): Array<[string, ProfiloMatrixRow[]]> {
  const grouped = new Map<string, ProfiloMatrixRow[]>()
  for (const permission of matrix) {
    const items = grouped.get(permission.category) || []
    items.push(permission)
    grouped.set(permission.category, items)
  }
  return [...grouped.entries()]
}

function roleLabel(role: ProfiloRole | undefined, fallback: string): string {
  return role?.label || fallback.replace('_', ' ')
}

function roleHasPermission(role: ProfiloRole | undefined, permission: string): boolean {
  return Boolean(role?.permissions.includes(permission))
}

function permissionLabel(permission: ProfiloPermission | undefined, row: ProfiloMatrixRow): string {
  return permission?.label || row.label || row.permission
}

function StatusMessage({
  saveStatus,
  message,
  validationErrors,
}: {
  saveStatus: SaveStatus
  message: string
  validationErrors: Record<string, string>
}) {
  if (saveStatus === 'idle' && !Object.keys(validationErrors).length) return null
  const tone = saveStatus === 'success' ? 'success' : saveStatus === 'saving' ? 'info' : 'danger'
  const title = saveStatus === 'success'
    ? 'Modifiche salvate'
    : saveStatus === 'saving'
      ? 'Salvataggio in corso'
      : 'Controlla i dati'
  return (
    <section className={`iu-profiles-status iu-profiles-status--${tone}`} aria-live="polite">
      <div>
        {saveStatus === 'success' ? <CheckCircle2 size={18} /> : saveStatus === 'saving' ? <RefreshCw size={18} /> : <ShieldAlert size={18} />}
        <strong>{title}</strong>
      </div>
      {message ? <p>{message}</p> : null}
      {Object.keys(validationErrors).length ? (
        <ul>
          {Object.entries(validationErrors).map(([field, error]) => (
            <li key={field}>{error}</li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}

function Warnings({ data }: { data: ProfiliPageData }) {
  if (!data.warnings.length) return null
  return (
    <Panel title="Avvisi operativi">
      <div className="iu-profiles-warnings">
        {data.warnings.map((warning) => (
          <div className="iu-profiles-warning" key={`${warning.code}-${warning.message}`}>
            <Badge tone="warning">{warning.code}</Badge>
            <span>{warning.message}</span>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function RoleCards({ roles, onSelectRole }: { roles: ProfiloRole[]; onSelectRole: (role: string) => void }) {
  if (!roles.length) {
    return <EmptyState title="Nessun ruolo disponibile" message="L'archivio utenti non ha restituito ruoli gestibili." />
  }
  return (
    <section className="iu-profiles-roles" aria-label="Ruoli reali">
      {roles.map((role) => (
        <button className="iu-profiles-role-summary" type="button" key={role.id} title={role.description} aria-label={`Mostra permessi e utenti di ${role.label}`} onClick={() => onSelectRole(role.role)}>
          <strong>{role.label}</strong>
          <span>{role.usersCount} {role.usersCount === 1 ? 'utente' : 'utenti'} · {role.permissionsCount} permessi base</span>
          <small>Mostra permessi e utenti</small>
        </button>
      ))}
    </section>
  )
}

function Matrix({
  data,
  roles,
}: {
  data: ProfiliPageData
  roles: string[]
}) {
  const permissions = new Map(data.permissions.map((permission) => [permission.permission, permission]))
  const groups = permissionRowsByCategory(data.matrix)
  const rowStyle = { gridTemplateColumns: `minmax(140px,1.25fr) repeat(${roles.length},minmax(100px,.55fr))`, minWidth: `${160 + roles.length * 108}px` }
  return (
    <Panel title="Matrice permessi reale" subtitle={`${data.matrix.length} ${data.matrix.length === 1 ? 'permesso' : 'permessi'}, ${roles.length} ${roles.length === 1 ? 'ruolo' : 'ruoli'}`}>
      {groups.length ? (
        <div className="iu-profiles-matrix-wrap">
        {roles.length > 1 ? <p className="iu-profiles-matrix-hint">Scorri orizzontalmente per confrontare i ruoli oppure seleziona un ruolo nel filtro.</p> : null}
        <div className="iu-profiles-matrix" role="table" aria-label="Matrice ruoli e permessi" tabIndex={0}>
          <div className="iu-profiles-matrix__head" role="row" style={rowStyle}>
            <span role="columnheader">Permesso</span>
            {roles.map((role) => (
              <span role="columnheader" key={role}>{data.roles.find(item => item.role === role)?.label || role.replace('_', ' ')}</span>
            ))}
          </div>
          {groups.map(([category, rows]) => (
            <section className="iu-profiles-category" key={category}>
              <h2>{category}</h2>
              {rows.map((row) => (
                <article className="iu-profiles-permission" role="row" key={row.id} style={rowStyle}>
                  <div className="iu-profiles-permission__label" role="cell">
                    <strong>{permissionLabel(permissions.get(row.permission), row)}</strong>
                    <span>{row.permission}</span>
                  </div>
                  {roles.map((role) => {
                    const grant = row.grants.find((item) => item.role === role)
                    return (
                      <span className="iu-profiles-grant" role="cell" key={`${row.id}-${role}`}>
                        {grant?.granted ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
                        <Badge tone={grant?.granted ? 'success' : 'neutral'}>{grant?.granted ? 'Sì' : 'No'}</Badge>
                      </span>
                    )
                  })}
                </article>
              ))}
            </section>
          ))}
        </div>
        </div>
      ) : (
        <EmptyState title="Nessun permesso da visualizzare" message="Controlla la ricerca e il ruolo selezionato." />
      )}
    </Panel>
  )
}

function OverrideSummary({ overrides }: { overrides: ProfiloOverride[] }) {
  return (
    <Panel title="Override presenti" subtitle="Eccezioni salvate rispetto ai permessi base del ruolo.">
      {overrides.length ? (
        <div className="iu-profiles-overrides">
          {overrides.map((override) => (
            <article className="iu-profiles-override" key={override.id || override.username}>
              <div>
                <strong>{override.label || override.username}</strong>
                <span>{override.role}</span>
                <small>Extra: {listLabel(override.extraPermissions)}</small>
                <small>Rimossi: {listLabel(override.deniedPermissions)}</small>
              </div>
              <Badge tone="warning">override</Badge>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState title="Nessun override configurato" message="Tutti gli utenti seguono i permessi standard del ruolo." />
      )}
    </Panel>
  )
}

function OverrideEditor({
  data,
  users,
  selectedUserId,
  onSelectUser,
  draft,
  selectedUser,
  selectedRole,
  selectedOverride,
  dirty,
  onToggle,
  onReset,
  onSave,
  saveStatus,
  validationErrors,
}: {
  data: ProfiliPageData
  users: ProfiloRoleUser[]
  selectedUserId: string
  onSelectUser: (id: string) => void
  draft: DraftOverride
  selectedUser: ProfiloRoleUser | undefined
  selectedRole: ProfiloRole | undefined
  selectedOverride: ProfiloOverride | undefined
  dirty: boolean
  onToggle: (permission: string, kind: 'extraPermissions' | 'deniedPermissions', checked: boolean) => void
  onReset: () => void
  onSave: () => void
  saveStatus: SaveStatus
  validationErrors: Record<string, string>
}) {
  const groups = permissionRowsByCategory(data.matrix)
  if (!data.actions.canWrite) {
    return (
      <Panel title="Modifiche non autorizzate" subtitle="La lettura resta disponibile, le scritture richiedono permessi amministrativi.">
        <div className="iu-profiles-denied">
          <ShieldAlert size={20} />
          <div>
            <strong>Permesso negato</strong>
            <p>La sessione corrente non autorizza la modifica dei permessi utente.</p>
          </div>
        </div>
      </Panel>
    )
  }
  if (!users.length) {
    return (
      <Panel title="Editor override utente">
        <EmptyState title="Nessun utente modificabile" message="L'archivio non ha restituito utenti su cui applicare modifiche." />
      </Panel>
    )
  }
  return (
    <Panel
      title="Editor override utente"
      subtitle="Le modifiche valgono solo per l'utente selezionato e vengono salvate con audit."
      actions={
        <>
          <Button type="button" tone="neutral" onClick={onReset} disabled={!selectedUser || saveStatus === 'saving'}>
            Ripristina standard
          </Button>
          <Button type="button" tone="primary" onClick={onSave} disabled={!selectedUser || !dirty || saveStatus === 'saving'}>
            <Save size={16} />
            {saveStatus === 'saving' ? 'Salvataggio...' : 'Salva permessi'}
          </Button>
        </>
      }
    >
      <div className="iu-profiles-editor">
        <label className="iu-profiles-select">
          <span>Utente</span>
          <select value={selectedUserId} onChange={(event) => onSelectUser(event.target.value)}>
            {users.map((user) => (
              <option value={user.id} key={user.id || user.username}>
                {user.label || user.username} - {user.role}
              </option>
            ))}
          </select>
        </label>
        {selectedUser ? (
          <div className="iu-profiles-editor__context">
            <Badge tone={selectedOverride?.hasOverride ? 'warning' : 'neutral'}>
              {selectedOverride?.hasOverride ? 'override attivo' : 'standard'}
            </Badge>
            <span>Ruolo: {roleLabel(selectedRole, selectedUser.role)}</span>
            <span>Stato: {dirty ? 'modifiche non salvate' : "allineato all'archivio"}</span>
          </div>
        ) : null}
        <StatusMessage saveStatus={saveStatus} message="" validationErrors={validationErrors} />
        {groups.map(([category, rows]) => (
          <section className="iu-profiles-editor-category" key={`editor-${category}`}>
            <h3>{category}</h3>
            <div className="iu-profiles-editor-rows">
              {rows.map((row) => {
                const baseGranted = roleHasPermission(selectedRole, row.permission)
                const isExtra = draft.extraPermissions.includes(row.permission)
                const isDenied = draft.deniedPermissions.includes(row.permission)
                const effective = !isDenied && (baseGranted || isExtra)
                return (
                  <article className="iu-profiles-editor-row" key={`editor-${row.id}`}>
                    <div>
                      <strong>{row.label}</strong>
                      <span>{row.permission}</span>
                    </div>
                    <Badge tone={baseGranted ? 'success' : 'neutral'}>{baseGranted ? 'dal ruolo' : 'non base'}</Badge>
                    <label className="iu-profiles-check">
                      <input
                        type="checkbox"
                        checked={isExtra}
                        disabled={baseGranted || saveStatus === 'saving'}
                        onChange={(event) => onToggle(row.permission, 'extraPermissions', event.target.checked)}
                      />
                      <span>Aggiungi</span>
                    </label>
                    <label className="iu-profiles-check">
                      <input
                        type="checkbox"
                        checked={isDenied}
                        disabled={!baseGranted || saveStatus === 'saving'}
                        onChange={(event) => onToggle(row.permission, 'deniedPermissions', event.target.checked)}
                      />
                      <span>Rimuovi</span>
                    </label>
                    <Badge tone={effective ? 'success' : 'neutral'}>{effective ? 'effettivo' : 'non concesso'}</Badge>
                  </article>
                )
              })}
            </div>
          </section>
        ))}
      </div>
    </Panel>
  )
}

export function ProfiliPage() {
  const [data, setData] = useState<ProfiliPageData>(emptyProfiliPage)
  const [loadStatus, setLoadStatus] = useState<LoadStatus>('loading')
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const [selectedUserId, setSelectedUserId] = useState('')
  const [drafts, setDrafts] = useState<Record<string, DraftOverride>>({})
  const [message, setMessage] = useState('')
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({})
  const [context, setContext] = useState(() => {
    const value = new URLSearchParams(window.location.search).get('vista') || ''
    return value === 'ruoli-usati' ? 'ruoli' : ['ruoli', 'permessi', 'utenti', 'override'].includes(value) ? value : ''
  })
  const [query, setQuery] = useState(() => new URLSearchParams(window.location.search).get('q') || '')
  const [roleFilter, setRoleFilter] = useState(() => new URLSearchParams(window.location.search).get('ruolo') || '')
  const [onlyUsedRoles, setOnlyUsedRoles] = useState(() => new URLSearchParams(window.location.search).get('vista') === 'ruoli-usati')
  const [refreshing, setRefreshing] = useState(false)
  const [refreshError, setRefreshError] = useState('')
  const refreshFlight = useRef<Promise<void> | null>(null)

  const refresh = () => {
    if (refreshFlight.current) return refreshFlight.current
    setRefreshing(true)
    const flight = getProfiliPage()
      .then((payload) => {
        if (!payload.ok) throw new Error('Dati non disponibili')
        setData(payload)
        setLoadStatus('ready')
        setRefreshError('')
      })
      .catch(() => {
        if (!data.ok) setLoadStatus('error')
        setRefreshError('Aggiornamento non riuscito. Filtri e modifiche non salvate restano conservati: riprova.')
      })
      .finally(() => { setRefreshing(false); refreshFlight.current = null })
    refreshFlight.current = flight
    return flight
  }
  useOperationalRefresh(['utenti'], refresh)

  useEffect(() => {
    refresh()
  }, [])

  const users = useMemo(() => allProfiloUsers(data), [data])
  useEffect(() => {
    if (!selectedUserId && users.length) setSelectedUserId(users[0].id)
  }, [selectedUserId, users])

  const roles = useMemo(() => data.roles.map((role) => role.role), [data.roles])
  const selectedUser = users.find((user) => user.id === selectedUserId)
  const selectedRole = data.roles.find((role) => role.role === selectedUser?.role)
  const selectedOverride = data.overrides.find((override) => override.id === selectedUserId)
  const originalDraft = draftFromOverride(selectedOverride)
  const draft = selectedUserId ? drafts[selectedUserId] || originalDraft : emptyDraft
  const dirty = !sameList(draft.extraPermissions, originalDraft.extraPermissions) || !sameList(draft.deniedPermissions, originalDraft.deniedPermissions)
  const hasData = data.roles.length > 0 || data.matrix.length > 0
  const matches = (values: string[]) => values.join(' ').toLocaleLowerCase('it-IT').includes(query.trim().toLocaleLowerCase('it-IT'))
  const filteredRoles = data.roles.filter(role => (!onlyUsedRoles || role.usersCount > 0) && (!roleFilter || role.role === roleFilter) && matches([role.label, role.description, ...role.users.map(user => user.label || user.username)]))
  const matrixData = { ...data, matrix: data.matrix.filter(row => matches([row.label, row.permission, row.category])) }
  const filteredUsers = users.filter(user => (!roleFilter || user.role === roleFilter) && matches([user.label, user.username]))
  const filteredOverrides = data.overrides.filter(user => (!roleFilter || user.role === roleFilter) && matches([user.label, user.username, ...user.extraPermissions, ...user.deniedPermissions]))

  const updateDraft = (next: DraftOverride) => {
    if (!selectedUserId) return
    setDrafts((current) => ({ ...current, [selectedUserId]: next }))
    setSaveStatus('idle')
    setValidationErrors({})
    setMessage('')
  }

  const handleToggle = (permission: string, kind: 'extraPermissions' | 'deniedPermissions', checked: boolean) => {
    const other = kind === 'extraPermissions' ? 'deniedPermissions' : 'extraPermissions'
    const next = {
      extraPermissions: [...draft.extraPermissions],
      deniedPermissions: [...draft.deniedPermissions],
    }
    next[kind] = checked
      ? [...new Set([...next[kind], permission])]
      : next[kind].filter((item) => item !== permission)
    if (checked) next[other] = next[other].filter((item) => item !== permission)
    updateDraft(next)
  }

  const handleReset = () => {
    updateDraft({ extraPermissions: [], deniedPermissions: [] })
  }

  const handleSave = () => {
    if (!selectedUserId) {
      setSaveStatus('error')
      setValidationErrors({ userId: 'Seleziona un utente.' })
      return
    }
    const payload: SaveProfiliPayload = {
      action: 'update_user_override',
      userId: selectedUserId,
      extraPermissions: draft.extraPermissions,
      deniedPermissions: draft.deniedPermissions,
    }
    setSaveStatus('saving')
    setValidationErrors({})
    saveProfiliPermissions(payload).then((result) => {
      if (result.ok && result.payload) {
        setData(result.payload)
        setDrafts({})
        setSaveStatus('success')
        setMessage(result.message)
      } else {
        setSaveStatus('error')
        setValidationErrors(result.errors)
        setMessage(result.message)
      }
    }).catch(() => {
      setSaveStatus('error')
      setValidationErrors({ _form: 'Errore di rete durante il salvataggio.' })
      setMessage('Salvataggio non completato.')
    })
  }

  return (
    <Page
      title="Profili e permessi"
      subtitle="Matrice RBAC reale dello studio e override utente salvati con servizi protetti."
      actions={
        <>
          <Button type="button" tone="neutral" onClick={refresh} disabled={refreshing}>
            <RefreshCw size={16} />
            {refreshing ? 'Aggiornamento…' : 'Aggiorna'}
          </Button>
          <ButtonLink href={data.actions.users || '/utenti'} tone="neutral">
            <UsersRound size={16} />
            Utenti
          </ButtonLink>
        </>
      }
    >
      {refreshing && loadStatus !== 'loading' ? <p role="status">Aggiornamento dei profili in corso.</p> : null}
      {refreshError ? <p role="alert">{refreshError}</p> : null}
      {loadStatus === 'loading' ? <LoadingState title="Caricamento profili" message="Lettura di ruoli, permessi e override reali in corso." /> : null}
      {loadStatus === 'error' ? (
        <EmptyState
          title="Profili non disponibili"
          message={message || 'Non sono disponibili permessi utilizzabili per questa sessione.'}
          action={<Button type="button" tone="primary" onClick={refresh}>Riprova</Button>}
        />
      ) : null}
      {loadStatus === 'ready' && !hasData ? (
        <EmptyState
          title="Nessuna matrice permessi disponibile"
          message="L'archivio utenti non ha restituito ruoli o permessi visualizzabili."
        />
      ) : null}
      {loadStatus === 'ready' && hasData ? (
        <>
          <StatusMessage saveStatus={saveStatus} message={message} validationErrors={validationErrors} />
          <Warnings data={data} />
          <section className="iu-profiles-kpis" aria-label="Indicatori profili">
            {data.metrics.map((metric) => (
              <KpiCard
                label={metric.label}
                value={formatValue(metric.value)}
                note={metric.note}
                key={metric.id}
                active={context === metric.id}
                onClick={() => setContext(current => current === metric.id ? '' : metric.id)}
                actionLabel="Filtra elenco"
              />
            ))}
          </section>
          <section className="iu-profiles-filters" aria-label="Ricerca e filtri profili">
            <label>Cerca ruoli, permessi e utenti<input type="search" value={query} onChange={event => setQuery(event.target.value)} /></label>
            <label>Ruolo<select value={roleFilter} onChange={event => setRoleFilter(event.target.value)}><option value="">Tutti i ruoli</option>{data.roles.map(role => <option key={role.id} value={role.role}>{role.label}</option>)}</select></label>
            {(!context || context === 'ruoli') ? <label><span>Ruoli utilizzati</span><select value={onlyUsedRoles ? 'usati' : 'tutti'} onChange={event => setOnlyUsedRoles(event.currentTarget.value === 'usati')}><option value="tutti">Tutti i ruoli</option><option value="usati">Con almeno un utente</option></select></label> : null}
            <Button type="button" tone="neutral" disabled={!query && !context && !roleFilter && !onlyUsedRoles} onClick={() => { setQuery(''); setContext(''); setRoleFilter(''); setOnlyUsedRoles(false) }}>Azzera filtri</Button>
          </section>
          {(!context || context === 'ruoli') ? <RoleCards roles={filteredRoles} onSelectRole={role => { setRoleFilter(role); setContext(''); setQuery('') }} /> : null}
          {(!context || context === 'permessi') ? <Matrix data={matrixData} roles={roleFilter ? roles.filter(role => role === roleFilter) : roles} /> : null}
          {(!context || context === 'utenti') ? <>
          <Panel title="Utenti collegati" subtitle={`${filteredUsers.length} di ${users.length} utenti`}>
            {filteredUsers.length ? <div className="iu-profiles-user-results">{filteredUsers.map(user => <Button key={user.id} type="button" tone="neutral" onClick={() => setSelectedUserId(user.id)}>{user.label || user.username}</Button>)}</div> : <EmptyState title="Nessun utente corrisponde ai filtri" />}
          </Panel>
          {filteredUsers.some(user => user.id === selectedUserId) ? <OverrideEditor
            data={data}
            users={filteredUsers}
            selectedUserId={selectedUserId}
            onSelectUser={setSelectedUserId}
            draft={draft}
            selectedUser={selectedUser}
            selectedRole={selectedRole}
            selectedOverride={selectedOverride}
            dirty={dirty}
            onToggle={handleToggle}
            onReset={handleReset}
            onSave={handleSave}
            saveStatus={saveStatus}
            validationErrors={validationErrors}
          /> : filteredUsers.length ? <p role="status">Seleziona un utente dell’elenco per consultare i suoi permessi.</p> : null}
          </> : null}
          {(!context || context === 'override') ? <OverrideSummary overrides={filteredOverrides} /> : null}
          <Panel title="Presidio dati" subtitle="Permessi letti dall’archivio dello studio, modifiche tracciate.">
            <div className="iu-profiles-contract">
              <span>Origine: {displaySourceLabel(data.source)}</span>
              <span>Generato: {formatGeneratedAt(data.generated_at)}</span>
              <span>Azioni: {displayWritesLabel(data.contracts.writes)}</span>
              <span>Dati reali: {data.contracts.mock_fallback ? 'da verificare' : 'sì'}</span>
            </div>
          </Panel>
        </>
      ) : null}
    </Page>
  )
}
