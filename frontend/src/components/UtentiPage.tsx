import { type FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, RefreshCw, ShieldCheck, UserPlus } from 'lucide-react'
import { apiPostJson } from '../lib/apiClient'
import {
  emptyUtentiPage,
  getUtentiPage,
  type AdminAction,
  type RoleOption,
  type UtentiPageData,
  type UtenteRecord,
} from '../utentiData'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import './UtentiPage.css'

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

function actionTone(action: AdminAction) {
  return action.tone === 'danger' || action.tone === 'success' || action.tone === 'warning'
    ? action.tone
    : action.id === 'nuovo'
      ? 'primary'
      : 'neutral'
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

function UserRecord({ record }: { record: UtenteRecord }) {
  return (
    <article className="iu-users-record">
      <div className="iu-users-record__identity">
        <strong>{record.name || record.username}</strong>
        <span>{record.username}</span>
        {record.email ? <small>{record.email}</small> : <small>Email non indicata</small>}
      </div>
      <div className="iu-users-record__meta">
        <Badge tone={record.roleTone}>{record.roleLabel}</Badge>
        <Badge tone={record.active ? 'success' : 'neutral'}>{record.active ? 'Attivo' : 'Disabilitato'}</Badge>
        {record.hasOverride ? <Badge tone="warning">Permessi personalizzati</Badge> : null}
        {record.twoFactorEnabled ? <Badge tone="success">2FA</Badge> : null}
      </div>
      <div className="iu-users-record__details">
        <span>Ultimo accesso: {formatDate(record.lastAccess)}</span>
        {record.mustChangePassword ? <span>Password temporanea da cambiare al primo accesso</span> : null}
        {record.hasOverride ? (
          <span>
            Extra: {record.extraPermissionsCount} · Rimossi: {record.deniedPermissionsCount}
          </span>
        ) : null}
      </div>
      <div className="iu-users-record__actions">
        {record.editHref ? <ButtonLink href={record.editHref} tone="neutral">Modifica legacy</ButtonLink> : null}
        {record.permissionsHref ? <ButtonLink href={record.permissionsHref} tone="neutral">Permessi legacy</ButtonLink> : null}
      </div>
    </article>
  )
}

type NewUserFormState = {
  username: string
  ruolo: string
  nome_completo: string
  email: string
}

type CreateUserResponse = {
  ok: boolean
  message: string
  errors: Record<string, string>
  item?: {
    id: string
    username: string
    name: string
    email: string
    role: string
    roleLabel: string
    active: boolean
  }
  status?: number
}

const emptyCreateResponse: CreateUserResponse = {
  ok: false,
  message: 'Creazione utente non completata.',
  errors: { _form: 'Il server non ha restituito una risposta valida.' },
}

function firstRole(roles: RoleOption[]): string {
  return roles[0]?.value || ''
}

function NewUserView({ data, onCreated }: { data: UtentiPageData; onCreated: () => Promise<void> }) {
  const passwordRef = useRef<HTMLInputElement>(null)
  const [form, setForm] = useState<NewUserFormState>({
    username: '',
    ruolo: firstRole(data.roles),
    nome_completo: '',
    email: '',
  })
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<CreateUserResponse | null>(null)
  const roleOptions = data.roles
  const endpoint = data.createEndpoint || '/api/v1/ui/utenti/nuovo'

  useEffect(() => {
    setForm((current) => current.ruolo ? current : { ...current, ruolo: firstRole(roleOptions) })
  }, [roleOptions])

  const updateField = (field: keyof NewUserFormState, value: string) => {
    setForm((current) => ({ ...current, [field]: value }))
    setResult(null)
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const password = passwordRef.current?.value || ''
    setSubmitting(true)
    setResult(null)
    const response = await apiPostJson<CreateUserResponse>(
      endpoint,
      { ...form, password },
      emptyCreateResponse,
    )
    if (passwordRef.current) passwordRef.current.value = ''
    setResult(response)
    if (response.ok) {
      setForm({
        username: '',
        ruolo: firstRole(roleOptions),
        nome_completo: '',
        email: '',
      })
      await onCreated()
    }
    setSubmitting(false)
  }

  const errors = result?.errors || {}
  const permissionDenied = result?.status === 403
  const serverError = result && !result.ok && !permissionDenied && !Object.keys(errors).some((key) => key !== '_form')
  const errorAlertClass = permissionDenied
    ? 'iu-users-form-alert--permission'
    : serverError
      ? 'iu-users-form-alert--server'
      : 'iu-users-form-alert--validation'

  return (
    <section className="iu-users-new">
      <Panel
        title="Crea utente"
        subtitle="Salvataggio JSON protetto da sessione, CSRF, permessi e audit amministrativo."
      >
        {data.createEndpoint ? (
          <form className="iu-users-create-form" onSubmit={submit} noValidate>
            {result?.ok ? (
              <div className="iu-users-form-alert iu-users-form-alert--success" role="status">
                <CheckCircle2 size={18} />
                <span>{result.message}</span>
                <ButtonLink href="/utenti" tone="success">Vai alla lista utenti</ButtonLink>
              </div>
            ) : null}
            {result && !result.ok ? (
              <div
                className={`iu-users-form-alert ${errorAlertClass}`}
                role="alert"
              >
                <AlertTriangle size={18} />
                <span>{result.message || errors._form || 'Controlla i campi evidenziati.'}</span>
              </div>
            ) : null}
            <div className="iu-users-form-grid">
              <label className="iu-users-field">
                <span>Username</span>
                <input
                  autoComplete="username"
                  aria-invalid={Boolean(errors.username)}
                  aria-describedby={errors.username ? 'nuovo-utente-username-errore' : undefined}
                  value={form.username}
                  onChange={(event) => updateField('username', event.target.value)}
                  disabled={submitting}
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
                  disabled={submitting}
                  required
                >
                  {roleOptions.map((role) => (
                    <option value={role.value} key={role.value}>{role.label}</option>
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
                  disabled={submitting}
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
                  disabled={submitting}
                />
                {errors.email ? <small id="nuovo-utente-email-errore">{errors.email}</small> : null}
              </label>
              <label className="iu-users-field iu-users-field--wide">
                <span>Password temporanea</span>
                <input
                  ref={passwordRef}
                  type="password"
                  autoComplete="new-password"
                  minLength={8}
                  aria-invalid={Boolean(errors.password)}
                  aria-describedby={errors.password ? 'nuovo-utente-password-errore' : undefined}
                  disabled={submitting}
                  required
                />
                {errors.password ? <small id="nuovo-utente-password-errore">{errors.password}</small> : (
                  <small>Non viene salvata nello stato persistente del browser.</small>
                )}
              </label>
            </div>
            <div className="iu-users-form-actions">
              <Button type="submit" tone="primary" disabled={submitting}>
                <UserPlus size={16} />
                {submitting ? 'Creazione in corso' : 'Crea utente'}
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
          {data.sections.find((section) => section.id === 'ruoli')?.items.map((item) => (
            <div className="iu-users-role" key={item.id}>
              <div>
                <strong>{item.label}</strong>
                <span>{item.note}</span>
              </div>
              <Badge tone={item.tone}>{formatValue(item.value)}</Badge>
            </div>
          ))}
        </div>
      </Panel>
      <Panel title="Rollback tecnico" subtitle="Fallback nascosto dal flusso principale e riservato al presidio amministrativo.">
        <div className="iu-users-rollback">
          <AlertTriangle size={18} />
          <span>La vista Flask resta disponibile solo come recupero tecnico controllato.</span>
          <ButtonLink href="/utenti/nuovo?_legacy=1" tone="neutral">Apri fallback legacy</ButtonLink>
        </div>
      </Panel>
    </section>
  )
}

export function UtentiPage() {
  const [data, setData] = useState<UtentiPageData>(emptyUtentiPage)
  const [loading, setLoading] = useState(true)
  const isNewUser = typeof window !== 'undefined' && window.location.pathname.toLowerCase() === '/utenti/nuovo'

  useEffect(() => {
    let active = true
    getUtentiPage()
      .then((payload) => {
        if (active) setData(payload)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const refreshData = async () => {
    const payload = await getUtentiPage()
    setData(payload)
  }

  const hasData = useMemo(
    () => data.metrics.length > 0 || data.records.length > 0 || data.forms.length > 0,
    [data],
  )
  const safeActions = data.actions.filter((action) => action.method === 'GET' && action.href)

  return (
    <Page
      title={isNewUser ? 'Nuovo utente' : 'Gestione utenti'}
      subtitle="Account, ruoli e permessi letti dal repository utenti reale."
      actions={
        <>
          <ButtonLink href="/utenti" tone="neutral">
            <RefreshCw size={16} />
            Lista utenti
          </ButtonLink>
          {safeActions.filter((action) => isNewUser ? action.id !== 'nuovo' : action.id !== 'lista').slice(0, 2).map((action) => (
            <ButtonLink href={action.href} tone={actionTone(action)} key={action.id}>
              {action.id === 'nuovo' ? <UserPlus size={16} /> : <ShieldCheck size={16} />}
              {action.label}
            </ButtonLink>
          ))}
        </>
      }
    >
      {loading ? <LoadingState title="Caricamento utenti" message="Lettura del repository amministrativo in corso." /> : null}
      {!loading && !hasData ? (
        <EmptyState
          title="Nessun dato utenti disponibile"
          message="Il repository utenti non ha restituito record visualizzabili."
        />
      ) : null}
      {!loading && hasData ? (
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
              <Panel title="Utenti reali" subtitle={`${data.records.length} account visualizzati`}>
                {data.records.length ? (
                  <div className="iu-users-list">
                    {data.records.map((record) => <UserRecord record={record} key={record.id || record.username} />)}
                  </div>
                ) : (
                  <EmptyState title="Nessun utente nel repository" />
                )}
              </Panel>
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
          <Panel title="Contratto dati" subtitle="Scritture amministrative mantenute sulle route legacy.">
            <div className="iu-users-contract">
              <span>Fonte: {data.source || 'non indicata'}</span>
              <span>Generato: {data.generated_at || 'non disponibile'}</span>
              <span>Scritture: {data.contracts.writes}</span>
              <span>Mock fallback: {data.contracts.mock_fallback ? 'si' : 'no'}</span>
            </div>
          </Panel>
        </>
      ) : null}
    </Page>
  )
}
