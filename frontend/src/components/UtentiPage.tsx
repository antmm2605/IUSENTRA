import { type FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  KeyRound,
  RefreshCw,
  Save,
  Search,
  ShieldAlert,
  ShieldCheck,
  UserCog,
  UserPlus,
  UsersRound,
} from 'lucide-react'
import {
  createUtente,
  emptyUtentiPage,
  getUtentiPage,
  resetUtentePassword,
  updateUtenteProfile,
  updateUtenteRole,
  updateUtenteStatus,
  type RoleOption,
  type UtenteMutationResult,
  type UtenteRecord,
  type UtentiPageData,
} from '../utentiData'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import './UtentiPage.css'

type LoadStatus = 'loading' | 'ready' | 'error'
type SaveStatus = 'idle' | 'saving' | 'success' | 'error'

type NewUserFormState = {
  username: string
  ruolo: string
  nome_completo: string
  email: string
}

type ProfileDraft = {
  name: string
  email: string
}

type UserFilter = 'tutti' | 'attivi' | 'disabilitati'

function formatValue(value: string | number): string {
  if (typeof value === 'number') return new Intl.NumberFormat('it-IT').format(value)
  return value
}

function formatDate(value: string): string {
  if (!value) return 'Mai'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value.replace('T', ' ').slice(0, 16)
  return new Intl.DateTimeFormat('it-IT', { dateStyle: 'short', timeStyle: 'short' }).format(parsed)
}

function formatGeneratedAt(value: string): string {
  if (!value) return 'non disponibile'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('it-IT', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(parsed)
}

function firstRole(roles: RoleOption[]): string {
  return roles[0]?.value || ''
}

function userLabel(user: UtenteRecord | null | undefined): string {
  if (!user) return 'utente'
  return user.name || user.username || 'utente'
}

function profileDraftFromUser(user: UtenteRecord | null | undefined): ProfileDraft {
  return { name: user?.name || '', email: user?.email || '' }
}

function validationItems(errors: Record<string, string>): string[] {
  return Object.values(errors).filter(Boolean)
}

function containsQuery(user: UtenteRecord, query: string): boolean {
  if (!query) return true
  const haystack = `${user.username} ${user.name} ${user.email} ${user.roleLabel} ${user.role}`.toLowerCase()
  return haystack.includes(query.toLowerCase())
}

function StatusMessage({
  status,
  message,
  errors,
}: {
  status: SaveStatus
  message: string
  errors: Record<string, string>
}) {
  if (status === 'idle' && !message && !Object.keys(errors).length) return null
  const tone = status === 'success' ? 'success' : status === 'saving' ? 'info' : 'danger'
  const title = status === 'success'
    ? 'Operazione completata'
    : status === 'saving'
      ? 'Salvataggio in corso'
      : errors.permission
        ? 'Permesso negato'
        : 'Controlla i dati'
  return (
    <section className={`iu-users-status iu-users-status--${tone}`} aria-live="polite">
      <div>
        {status === 'success' ? <CheckCircle2 size={18} /> : status === 'saving' ? <RefreshCw size={18} /> : <ShieldAlert size={18} />}
        <strong>{title}</strong>
      </div>
      {message ? <p>{message}</p> : null}
      {validationItems(errors).length ? (
        <ul>
          {validationItems(errors).map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}

function Warnings({ data }: { data: UtentiPageData }) {
  if (!data.warnings.length) return null
  return (
    <Panel title="Avvisi operativi">
      <div className="iu-users-warnings">
        {data.warnings.map((warning) => (
          <div className="iu-users-warning" key={`${warning.code}-${warning.message}`}>
            <Badge tone="warning">{warning.code}</Badge>
            <span>{warning.message}</span>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function UserRecord({
  record,
  selected,
  onSelect,
}: {
  record: UtenteRecord
  selected: boolean
  onSelect: (id: string) => void
}) {
  return (
    <article className={`iu-users-record ${selected ? 'is-selected' : ''}`}>
      <button
        className="iu-users-record__select"
        type="button"
        onClick={() => onSelect(record.id)}
        aria-pressed={selected}
      >
        <span className="iu-users-record__identity">
          <strong>{record.name || record.username}</strong>
          <span>{record.username}</span>
          {record.email ? <small>{record.email}</small> : <small>Email non indicata</small>}
        </span>
        <span className="iu-users-record__meta">
          <Badge tone={record.roleTone}>{record.roleLabel}</Badge>
          <Badge tone={record.active ? 'success' : 'neutral'}>{record.active ? 'Attivo' : 'Disabilitato'}</Badge>
          {record.hasOverride ? <Badge tone="warning">Permessi personalizzati</Badge> : null}
          {record.twoFactorEnabled ? <Badge tone="success">2FA</Badge> : null}
        </span>
        <span className="iu-users-record__details">
          <span>Ultimo accesso: {formatDate(record.lastAccess)}</span>
          {record.mustChangeCredential ? <span>Credenziale temporanea da cambiare al primo accesso</span> : null}
          {record.hasOverride ? (
            <span>
              Extra: {record.extraPermissionsCount} - Rimossi: {record.deniedPermissionsCount}
            </span>
          ) : null}
        </span>
      </button>
    </article>
  )
}

function UserFilters({
  query,
  onQuery,
  role,
  onRole,
  status,
  onStatus,
  roles,
}: {
  query: string
  onQuery: (value: string) => void
  role: string
  onRole: (value: string) => void
  status: UserFilter
  onStatus: (value: UserFilter) => void
  roles: RoleOption[]
}) {
  return (
    <Panel title="Ricerca e filtri" subtitle="Filtro locale sui dati gia ricevuti dal backend.">
      <div className="iu-users-filters">
        <label className="iu-users-field iu-users-field--search">
          <span>Cerca</span>
          <div className="iu-users-search">
            <Search size={16} />
            <input
              type="search"
              value={query}
              onChange={(event) => onQuery(event.target.value)}
              placeholder="Nome, username, email o ruolo"
            />
          </div>
        </label>
        <label className="iu-users-field">
          <span>Ruolo</span>
          <select value={role} onChange={(event) => onRole(event.target.value)}>
            <option value="">Tutti i ruoli</option>
            {roles.map((item) => (
              <option value={item.value} key={item.value}>{item.label}</option>
            ))}
          </select>
        </label>
        <label className="iu-users-field">
          <span>Stato account</span>
          <select value={status} onChange={(event) => onStatus(event.target.value as UserFilter)}>
            <option value="tutti">Tutti</option>
            <option value="attivi">Solo attivi</option>
            <option value="disabilitati">Solo disabilitati</option>
          </select>
        </label>
      </div>
    </Panel>
  )
}

function NewUserView({ data, onCreated }: { data: UtentiPageData; onCreated: () => Promise<void> }) {
  const passwordRef = useRef<HTMLInputElement>(null)
  const [form, setForm] = useState<NewUserFormState>({
    username: '',
    ruolo: firstRole(data.roles),
    nome_completo: '',
    email: '',
  })
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const [message, setMessage] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const roleOptions = data.roles
  const endpoint = data.createEndpoint || '/api/v1/ui/utenti/nuovo'

  useEffect(() => {
    setForm((current) => current.ruolo ? current : { ...current, ruolo: firstRole(roleOptions) })
  }, [roleOptions])

  const updateField = (field: keyof NewUserFormState, value: string) => {
    setForm((current) => ({ ...current, [field]: value }))
    setSaveStatus('idle')
    setMessage('')
    setErrors({})
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const temporaryCredential = passwordRef.current?.value || ''
    setSaveStatus('saving')
    setMessage('')
    setErrors({})
    try {
      const response = await createUtente(
        { ...form, password: temporaryCredential },
        endpoint,
      )
      if (passwordRef.current) passwordRef.current.value = ''
      if (response.ok) {
        setForm({
          username: '',
          ruolo: firstRole(roleOptions),
          nome_completo: '',
          email: '',
        })
        setSaveStatus('success')
        setMessage(response.message)
        await onCreated()
      } else {
        setSaveStatus('error')
        setMessage(response.message)
        setErrors(response.errors)
      }
    } catch {
      if (passwordRef.current) passwordRef.current.value = ''
      setSaveStatus('error')
      setMessage('Creazione non completata.')
      setErrors({ _form: 'Errore di rete durante la creazione.' })
    }
  }

  return (
    <section className="iu-users-new">
      <Panel
        title="Crea utente"
        subtitle="Salvataggio JSON protetto da sessione, CSRF, permessi e audit amministrativo."
      >
        {data.createEndpoint ? (
          <form className="iu-users-create-form" onSubmit={submit} noValidate>
            <StatusMessage status={saveStatus} message={message} errors={errors} />
            <div className="iu-users-form-grid">
              <label className="iu-users-field">
                <span>Username</span>
                <input
                  autoComplete="username"
                  aria-invalid={Boolean(errors.username)}
                  aria-describedby={errors.username ? 'nuovo-utente-username-errore' : undefined}
                  value={form.username}
                  onChange={(event) => updateField('username', event.target.value)}
                  disabled={saveStatus === 'saving'}
                  required
                />
                {errors.username ? <small id="nuovo-utente-username-errore">{errors.username}</small> : null}
              </label>
              <label className="iu-users-field">
                <span>Ruolo</span>
                <select
                  aria-invalid={Boolean(errors.ruolo)}
                  aria-describedby={errors.ruolo ? 'nuovo-utente-ruolo-errore' : undefined}
                  value={form.ruolo}
                  onChange={(event) => updateField('ruolo', event.target.value)}
                  disabled={saveStatus === 'saving'}
                  required
                >
                  {roleOptions.map((roleOption) => (
                    <option value={roleOption.value} key={roleOption.value}>{roleOption.label}</option>
                  ))}
                </select>
                {errors.ruolo ? <small id="nuovo-utente-ruolo-errore">{errors.ruolo}</small> : null}
              </label>
              <label className="iu-users-field">
                <span>Nome completo</span>
                <input
                  autoComplete="name"
                  value={form.nome_completo}
                  onChange={(event) => updateField('nome_completo', event.target.value)}
                  disabled={saveStatus === 'saving'}
                />
              </label>
              <label className="iu-users-field">
                <span>Email</span>
                <input
                  type="email"
                  autoComplete="email"
                  aria-invalid={Boolean(errors.email)}
                  aria-describedby={errors.email ? 'nuovo-utente-email-errore' : undefined}
                  value={form.email}
                  onChange={(event) => updateField('email', event.target.value)}
                  disabled={saveStatus === 'saving'}
                />
                {errors.email ? <small id="nuovo-utente-email-errore">{errors.email}</small> : null}
              </label>
              <label className="iu-users-field iu-users-field--wide">
                <span>Credenziale temporanea</span>
                <input
                  ref={passwordRef}
                  type="password"
                  autoComplete="new-password"
                  minLength={8}
                  aria-invalid={Boolean(errors.password)}
                  aria-describedby={errors.password ? 'nuovo-utente-credenziale-errore' : undefined}
                  disabled={saveStatus === 'saving'}
                  required
                />
                {errors.password ? <small id="nuovo-utente-credenziale-errore">{errors.password}</small> : (
                  <small>Il valore non viene conservato nello stato React.</small>
                )}
              </label>
            </div>
            <div className="iu-users-form-actions">
              <Button type="submit" tone="primary" disabled={saveStatus === 'saving'}>
                <UserPlus size={16} />
                {saveStatus === 'saving' ? 'Creazione in corso' : 'Crea utente'}
              </Button>
              <ButtonLink href="/utenti" tone="neutral">Annulla</ButtonLink>
            </div>
          </form>
        ) : (
          <EmptyState
            title="Permesso di creazione non disponibile"
            message="La creazione richiede il permesso utenti.scrivi."
          />
        )}
      </Panel>
      <Panel title="Ruoli disponibili" subtitle="Ruoli reali gestibili nello studio, escluso SUPERADMIN.">
        <div className="iu-users-role-list">
          {data.roles.map((role) => (
            <div className="iu-users-role" key={role.value}>
              <div>
                <strong>{role.label}</strong>
                <span>{role.description}</span>
              </div>
              <Badge tone={role.tone}>{role.value}</Badge>
            </div>
          ))}
        </div>
      </Panel>
    </section>
  )
}

function UserEditor({
  data,
  selectedUser,
  onResult,
}: {
  data: UtentiPageData
  selectedUser: UtenteRecord | null
  onResult: (result: UtenteMutationResult) => void
}) {
  const resetCredentialRef = useRef<HTMLInputElement>(null)
  const [profileDraft, setProfileDraft] = useState<ProfileDraft>(profileDraftFromUser(selectedUser))
  const [roleDraft, setRoleDraft] = useState(selectedUser?.role || '')
  const [statusConfirm, setStatusConfirm] = useState(false)
  const [resetConfirm, setResetConfirm] = useState(false)
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const [message, setMessage] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    setProfileDraft(profileDraftFromUser(selectedUser))
    setRoleDraft(selectedUser?.role || '')
    setStatusConfirm(false)
    setResetConfirm(false)
    setSaveStatus('idle')
    setMessage('')
    setErrors({})
    if (resetCredentialRef.current) resetCredentialRef.current.value = ''
  }, [selectedUser])

  if (!selectedUser) {
    return (
      <Panel title="Operazioni utente">
        <EmptyState title="Seleziona un utente" message="Scegli un account dalla lista per aprire le azioni operative JSON." />
      </Panel>
    )
  }

  const profileDirty = profileDraft.name !== selectedUser.name || profileDraft.email !== selectedUser.email
  const roleDirty = roleDraft !== selectedUser.role
  const canWrite = data.actions.canUpdate
  const activeAdmins = data.users.filter((user) => user.active && user.role === 'AMMINISTRATORE')
  const isLastActiveAdmin = selectedUser.active && selectedUser.role === 'AMMINISTRATORE' && activeAdmins.length <= 1
  const disabling = selectedUser.active
  const disableBlockedReason = !data.actions.canDisable
    ? 'Il backend non ha dichiarato il permesso utenti.scrivi.'
    : selectedUser.isCurrentUser
      ? 'Non puoi disabilitare il tuo account dalla sessione corrente.'
      : isLastActiveAdmin
        ? "Non puoi disabilitare l'ultimo amministratore attivo."
        : ''
  const roleBlockedReason = !data.actions.canChangeRole
    ? 'Il backend non ha dichiarato il permesso utenti.scrivi.'
    : isLastActiveAdmin && roleDraft !== 'AMMINISTRATORE'
      ? "Non puoi rimuovere il ruolo dall'ultimo amministratore attivo."
      : ''

  const applyMutation = async (callback: () => Promise<UtenteMutationResult>) => {
    setSaveStatus('saving')
    setMessage('')
    setErrors({})
    try {
      const result = await callback()
      if (result.ok) {
        setSaveStatus('success')
        setMessage(result.message)
        setErrors({})
        onResult(result)
      } else {
        setSaveStatus('error')
        setMessage(result.message)
        setErrors(result.errors)
      }
    } catch {
      setSaveStatus('error')
      setMessage('Operazione non completata.')
      setErrors({ _form: 'Errore di rete durante il salvataggio.' })
    }
  }

  const saveProfile = () => {
    if (!canWrite || !profileDirty) return
    applyMutation(() => updateUtenteProfile(
      selectedUser.id,
      profileDraft,
      data.actions.profileEndpoint,
    ))
  }

  const saveRole = () => {
    if (!data.actions.canChangeRole || !roleDirty || roleBlockedReason) return
    applyMutation(() => updateUtenteRole(
      selectedUser.id,
      { role: roleDraft },
      data.actions.roleEndpoint,
    ))
  }

  const saveAccountStatus = () => {
    if (!data.actions.canDisable || disableBlockedReason) return
    const nextActive = !selectedUser.active
    if (!nextActive && !statusConfirm) {
      setSaveStatus('error')
      setMessage('Conferma esplicitamente la disabilitazione account.')
      setErrors({ confirm: 'La disabilitazione richiede conferma.' })
      return
    }
    applyMutation(() => updateUtenteStatus(
      selectedUser.id,
      { active: nextActive },
      data.actions.statusEndpoint,
    ))
  }

  const resetCredential = () => {
    if (!data.actions.canResetPassword) return
    const temporaryCredential = resetCredentialRef.current?.value || ''
    applyMutation(() => resetUtentePassword(
      selectedUser.id,
      { temporaryPassword: temporaryCredential, confirm: resetConfirm },
      data.actions.resetPasswordEndpoint,
    )).then(() => {
      if (resetCredentialRef.current) resetCredentialRef.current.value = ''
      setResetConfirm(false)
    })
  }

  return (
    <Panel
      title={`Operazioni su ${userLabel(selectedUser)}`}
      subtitle="Profilo minimo, ruolo, stato account e credenziale temporanea via API JSON auditata."
    >
      <div className="iu-users-editor">
        <div className="iu-users-editor__summary">
          <Badge tone={selectedUser.active ? 'success' : 'neutral'}>{selectedUser.active ? 'Attivo' : 'Disabilitato'}</Badge>
          <Badge tone={selectedUser.roleTone}>{selectedUser.roleLabel}</Badge>
          {selectedUser.isCurrentUser ? <Badge tone="info">sessione corrente</Badge> : null}
          <span>{profileDirty || roleDirty ? 'Modifiche non salvate' : 'Allineato al repository'}</span>
        </div>
        <StatusMessage status={saveStatus} message={message} errors={errors} />
        <section className="iu-users-editor-section">
          <h3>Dati anagrafici minimi</h3>
          <div className="iu-users-form-grid">
            <label className="iu-users-field">
              <span>Nome completo</span>
              <input
                value={profileDraft.name}
                onChange={(event) => {
                  setProfileDraft((current) => ({ ...current, name: event.target.value }))
                  setSaveStatus('idle')
                  setErrors({})
                }}
                disabled={!canWrite || saveStatus === 'saving'}
              />
            </label>
            <label className="iu-users-field">
              <span>Email</span>
              <input
                type="email"
                value={profileDraft.email}
                onChange={(event) => {
                  setProfileDraft((current) => ({ ...current, email: event.target.value }))
                  setSaveStatus('idle')
                  setErrors({})
                }}
                disabled={!canWrite || saveStatus === 'saving'}
                aria-invalid={Boolean(errors.email)}
              />
              {errors.email ? <small>{errors.email}</small> : null}
            </label>
          </div>
          <div className="iu-users-form-actions">
            <Button type="button" tone="primary" onClick={saveProfile} disabled={!canWrite || !profileDirty || saveStatus === 'saving'}>
              <Save size={16} />
              Salva profilo
            </Button>
            {!canWrite ? <small>Modifica profilo non autorizzata dal backend.</small> : null}
          </div>
        </section>
        <section className="iu-users-editor-section">
          <h3>Ruolo</h3>
          <div className="iu-users-role-editor">
            <label className="iu-users-field">
              <span>Ruolo utente</span>
              <select
                value={roleDraft}
                onChange={(event) => {
                  setRoleDraft(event.target.value)
                  setSaveStatus('idle')
                  setErrors({})
                }}
                disabled={!data.actions.canChangeRole || saveStatus === 'saving'}
              >
                {data.roles.map((role) => (
                  <option value={role.value} key={role.value}>{role.label}</option>
                ))}
              </select>
            </label>
            <Button type="button" tone="primary" onClick={saveRole} disabled={!roleDirty || Boolean(roleBlockedReason) || saveStatus === 'saving'}>
              <UserCog size={16} />
              Salva ruolo
            </Button>
          </div>
          {roleBlockedReason ? <p className="iu-users-help">{roleBlockedReason}</p> : null}
        </section>
        <section className="iu-users-editor-section">
          <h3>Stato account</h3>
          <div className="iu-users-status-action">
            <div>
              <strong>{selectedUser.active ? 'Account abilitato' : 'Account disabilitato'}</strong>
              <span>{selectedUser.active ? 'La prossima azione lo disabilita.' : 'La prossima azione lo abilita.'}</span>
            </div>
            <Button
              type="button"
              tone={selectedUser.active ? 'warning' : 'success'}
              onClick={saveAccountStatus}
              disabled={Boolean(disableBlockedReason) || (disabling && !statusConfirm) || saveStatus === 'saving'}
              title={disableBlockedReason || undefined}
            >
              <ShieldCheck size={16} />
              {selectedUser.active ? 'Disabilita' : 'Abilita'}
            </Button>
          </div>
          {selectedUser.active ? (
            <label className="iu-users-check">
              <input
                type="checkbox"
                checked={statusConfirm}
                onChange={(event) => setStatusConfirm(event.target.checked)}
                disabled={Boolean(disableBlockedReason) || saveStatus === 'saving'}
              />
              <span>Confermo la disabilitazione dell'account selezionato.</span>
            </label>
          ) : null}
          {disableBlockedReason ? <p className="iu-users-help">{disableBlockedReason}</p> : null}
        </section>
        <section className="iu-users-editor-section">
          <h3>Reimpostazione credenziale</h3>
          <div className="iu-users-form-grid">
            <label className="iu-users-field iu-users-field--wide">
              <span>Nuova credenziale temporanea</span>
              <input
                ref={resetCredentialRef}
                type="password"
                minLength={8}
                autoComplete="new-password"
                disabled={!data.actions.canResetPassword || saveStatus === 'saving'}
                aria-invalid={Boolean(errors.temporaryPassword)}
              />
              {errors.temporaryPassword ? <small>{errors.temporaryPassword}</small> : <small>Il valore non viene restituito dal server e non viene salvato nello stato React.</small>}
            </label>
          </div>
          <label className="iu-users-check">
            <input
              type="checkbox"
              checked={resetConfirm}
              onChange={(event) => setResetConfirm(event.target.checked)}
              disabled={!data.actions.canResetPassword || saveStatus === 'saving'}
            />
            <span>Confermo la reimpostazione della credenziale temporanea.</span>
          </label>
          <div className="iu-users-form-actions">
            <Button type="button" tone="warning" onClick={resetCredential} disabled={!data.actions.canResetPassword || !resetConfirm || saveStatus === 'saving'}>
              <KeyRound size={16} />
              Reimposta credenziale
            </Button>
            {!data.actions.canResetPassword ? <small>Reimpostazione non autorizzata dal backend.</small> : null}
          </div>
        </section>
      </div>
    </Panel>
  )
}

export function UtentiPage() {
  const [data, setData] = useState<UtentiPageData>(emptyUtentiPage)
  const [loadStatus, setLoadStatus] = useState<LoadStatus>('loading')
  const [message, setMessage] = useState('')
  const [selectedUserId, setSelectedUserId] = useState('')
  const [query, setQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState<UserFilter>('tutti')
  const isNewUser = typeof window !== 'undefined' && window.location.pathname.toLowerCase() === '/utenti/nuovo'

  const refreshData = async () => {
    setLoadStatus('loading')
    setMessage('')
    try {
      const payload = await getUtentiPage()
      setData(payload)
      setLoadStatus(payload.ok || payload.users.length || payload.metrics.length ? 'ready' : 'error')
      setSelectedUserId((current) => current || payload.users[0]?.id || '')
    } catch {
      setLoadStatus('error')
      setMessage('Impossibile leggere gli utenti dal backend.')
    }
  }

  useEffect(() => {
    refreshData()
  }, [])

  const filteredUsers = useMemo(
    () => data.users.filter((user) => {
      if (!containsQuery(user, query)) return false
      if (roleFilter && user.role !== roleFilter) return false
      if (statusFilter === 'attivi' && !user.active) return false
      if (statusFilter === 'disabilitati' && user.active) return false
      return true
    }),
    [data.users, query, roleFilter, statusFilter],
  )
  const selectedUser = data.users.find((user) => user.id === selectedUserId) || filteredUsers[0] || null
  const hasData = data.metrics.length > 0 || data.users.length > 0

  const handleMutationResult = (result: UtenteMutationResult) => {
    if (result.payload) {
      setData(result.payload)
      if (result.user?.id) setSelectedUserId(result.user.id)
    } else if (result.user) {
      setData((current) => {
        const nextUsers = current.users.map((user) => user.id === result.user?.id ? result.user : user)
        return { ...current, users: nextUsers, records: nextUsers }
      })
    }
  }

  return (
    <Page
      title={isNewUser ? 'Nuovo utente' : 'Gestione utenti'}
      subtitle="Account reali dello studio, letti e aggiornati tramite API JSON protette."
      actions={
        <>
          <Button type="button" tone="neutral" onClick={refreshData} disabled={loadStatus === 'loading'}>
            <RefreshCw size={16} />
            Aggiorna
          </Button>
          {isNewUser ? (
            <ButtonLink href="/utenti" tone="neutral">
              <UsersRound size={16} />
              Lista utenti
            </ButtonLink>
          ) : null}
          {!isNewUser && data.actions.canCreate ? (
            <ButtonLink href={data.actions.create || '/utenti/nuovo'} tone="primary">
              <UserPlus size={16} />
              Nuovo utente
            </ButtonLink>
          ) : null}
          {data.actions.profiles ? (
            <ButtonLink href={data.actions.profiles} tone="neutral">
              <ShieldCheck size={16} />
              Profili
            </ButtonLink>
          ) : null}
        </>
      }
    >
      {loadStatus === 'loading' ? <LoadingState title="Caricamento utenti" message="Lettura del repository amministrativo in corso." /> : null}
      {loadStatus === 'error' ? (
        <EmptyState
          title="Utenti non disponibili"
          message={message || 'Il backend non ha restituito record utenti visualizzabili.'}
          action={<Button type="button" tone="primary" onClick={refreshData}>Riprova</Button>}
        />
      ) : null}
      {loadStatus === 'ready' && !hasData ? (
        <EmptyState
          title="Nessun dato utenti disponibile"
          message="Il repository utenti non ha restituito record visualizzabili."
        />
      ) : null}
      {loadStatus === 'ready' && hasData ? (
        <>
          <Warnings data={data} />
          <section className="iu-users-kpis" aria-label="KPI utenti">
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
          {isNewUser ? (
            <NewUserView data={data} onCreated={refreshData} />
          ) : (
            <>
              <UserFilters
                query={query}
                onQuery={setQuery}
                role={roleFilter}
                onRole={setRoleFilter}
                status={statusFilter}
                onStatus={setStatusFilter}
                roles={data.roles}
              />
              <section className="iu-users-workspace">
                <Panel title="Utenti reali" subtitle={`${filteredUsers.length} di ${data.users.length} account visualizzati`}>
                  {filteredUsers.length ? (
                    <div className="iu-users-list">
                      {filteredUsers.map((record) => (
                        <UserRecord
                          record={record}
                          selected={record.id === selectedUser?.id}
                          onSelect={setSelectedUserId}
                          key={record.id || record.username}
                        />
                      ))}
                    </div>
                  ) : (
                    <EmptyState
                      title="Nessun utente corrisponde ai filtri"
                      message="Modifica ricerca, ruolo o stato account per ampliare la lista."
                    />
                  )}
                </Panel>
                <UserEditor data={data} selectedUser={selectedUser} onResult={handleMutationResult} />
              </section>
              <section className="iu-users-grid" aria-label="Distribuzioni utenti">
                {data.sections.map((section) => (
                  <Panel title={section.title} subtitle={section.kind} key={section.id}>
                    {section.items.length ? (
                      <div className="iu-users-distribution">
                        {section.items.map((item) => (
                          <div className="iu-users-distribution__item" key={item.id}>
                            <span>{item.label}</span>
                            <strong>{formatValue(item.value)}</strong>
                            {item.note ? <small>{item.note}</small> : null}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <EmptyState title={section.emptyMessage} />
                    )}
                  </Panel>
                ))}
              </section>
            </>
          )}
          <Panel title="Contratto dati" subtitle="Scritture amministrative via JSON, dominio e audit restano nel backend Flask.">
            <div className="iu-users-contract">
              <span>Fonte: {data.source || 'non indicata'}</span>
              <span>Generato: {formatGeneratedAt(data.generated_at)}</span>
              <span>Scritture: {data.contracts.writes}</span>
              <span>Mock fallback: {data.contracts.mock_fallback ? 'si' : 'no'}</span>
            </div>
          </Panel>
          {data.actions.rollback ? (
            <Panel title="Rollback tecnico" subtitle="Percorso di assistenza mantenuto per confronto e recupero controllato.">
              <div className="iu-users-rollback">
                <AlertTriangle size={18} />
                <span>La vista Flask resta disponibile solo come fallback tecnico, non come flusso principale.</span>
                <ButtonLink href={data.actions.rollback.href} tone="neutral">{data.actions.rollback.label}</ButtonLink>
              </div>
            </Panel>
          ) : null}
        </>
      ) : null}
    </Page>
  )
}
