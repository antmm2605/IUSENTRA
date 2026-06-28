import { useEffect, useMemo, useState } from 'react'
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
  if (!value) return 'non disponibile'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('it-IT', {
    timeZone: 'Europe/Rome',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
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

function RoleCards({ roles }: { roles: ProfiloRole[] }) {
  if (!roles.length) {
    return <EmptyState title="Nessun ruolo disponibile" message="L'archivio utenti non ha restituito ruoli gestibili." />
  }
  return (
    <section className="iu-profiles-roles" aria-label="Ruoli reali">
      {roles.map((role) => (
        <Panel title={role.label} subtitle={role.description} key={role.id}>
          <div className="iu-profiles-role">
            <div className="iu-profiles-role__meta">
              <Badge tone={role.tone}>{role.role}</Badge>
              <strong>{role.usersCount} utenti</strong>
              <span>{role.permissionsCount} permessi base</span>
            </div>
            {role.users.length ? (
              <div className="iu-profiles-role__users">
                {role.users.slice(0, 5).map((user) => (
                  <span className="iu-profiles-user-chip" key={user.id || user.username}>
                    {user.label || user.username}
                    {user.hasOverride ? <Badge tone="warning">override</Badge> : null}
                  </span>
                ))}
                {role.users.length > 5 ? <span className="iu-profiles-user-chip">+{role.users.length - 5}</span> : null}
              </div>
            ) : (
              <small>Nessun utente collegato.</small>
            )}
          </div>
        </Panel>
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
  return (
    <Panel title="Matrice permessi reale" subtitle={`${data.matrix.length} permessi, ${roles.length} ruoli`}>
      {groups.length ? (
        <div className="iu-profiles-matrix" role="table" aria-label="Matrice ruoli e permessi">
          <div className="iu-profiles-matrix__head" role="row">
            <span role="columnheader">Permesso</span>
            {roles.map((role) => (
              <span role="columnheader" key={role}>{role.replace('_', ' ')}</span>
            ))}
          </div>
          {groups.map(([category, rows]) => (
            <section className="iu-profiles-category" key={category}>
              <h2>{category}</h2>
              {rows.map((row) => (
                <article className="iu-profiles-permission" role="row" key={row.id}>
                  <div className="iu-profiles-permission__label" role="cell">
                    <strong>{permissionLabel(permissions.get(row.permission), row)}</strong>
                    <span>{row.permission}</span>
                  </div>
                  {roles.map((role) => {
                    const grant = row.grants.find((item) => item.role === role)
                    return (
                      <span className="iu-profiles-grant" role="cell" key={`${row.id}-${role}`}>
                        {grant?.granted ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
                        <Badge tone={grant?.granted ? 'success' : 'neutral'}>{grant?.granted ? 'Si' : 'No'}</Badge>
                      </span>
                    )
                  })}
                </article>
              ))}
            </section>
          ))}
        </div>
      ) : (
        <EmptyState title="Nessun permesso censito" message="La matrice RBAC non ha restituito righe visualizzabili." />
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

  const refresh = () => {
    setLoadStatus('loading')
    setMessage('')
    getProfiliPage()
      .then((payload) => {
        setData(payload)
        setLoadStatus(payload.ok || payload.roles.length || payload.matrix.length ? 'ready' : 'error')
      })
      .catch(() => {
        setLoadStatus('error')
        setMessage('Impossibile leggere i profili.')
      })
  }

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
          <Button type="button" tone="neutral" onClick={refresh} disabled={loadStatus === 'loading'}>
            <RefreshCw size={16} />
            Aggiorna
          </Button>
          <ButtonLink href={data.actions.users || '/utenti'} tone="neutral">
            <UsersRound size={16} />
            Utenti
          </ButtonLink>
        </>
      }
    >
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
                badge={<Badge tone={metric.tone}>{metric.tone}</Badge>}
                key={metric.id}
              />
            ))}
          </section>
          <RoleCards roles={data.roles} />
          <Matrix data={data} roles={roles} />
          <OverrideEditor
            data={data}
            users={users}
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
          />
          <OverrideSummary overrides={data.overrides} />
          <Panel title="Presidio dati" subtitle="RBAC letto dal dominio esistente, modifiche auditabili.">
            <div className="iu-profiles-contract">
              <span>Origine: {displaySourceLabel(data.source)}</span>
              <span>Generato: {formatGeneratedAt(data.generated_at)}</span>
              <span>Azioni: {displayWritesLabel(data.contracts.writes)}</span>
              <span>Dati reali: {data.contracts.mock_fallback ? 'da verificare' : 'si'}</span>
            </div>
          </Panel>
          {data.actions.rollback ? (
            <Panel title="Percorso di recupero" subtitle="Assistenza mantenuta per confronto e recupero operativo.">
              <a className="iu-profiles-rollback" href={data.actions.rollback.href}>
                {data.actions.rollback.label}
              </a>
            </Panel>
          ) : null}
        </>
      ) : null}
    </Page>
  )
}
