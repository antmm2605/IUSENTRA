import { useEffect, useMemo, useState } from 'react'
import { RefreshCw, ShieldCheck, UserPlus } from 'lucide-react'
import {
  emptyUtentiPage,
  getUtentiPage,
  type AdminAction,
  type UtentiPageData,
  type UtenteRecord,
} from '../utentiData'
import { Badge } from '../ui/Badge'
import { ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LegacyPostForm } from '../ui/LegacyPostForm'
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

function NewUserView({ data }: { data: UtentiPageData }) {
  const form = data.forms.find((item) => item.id === 'nuovo_utente')
  return (
    <section className="iu-users-new">
      <Panel
        title="Crea utente"
        subtitle="Il submit usa il POST legacy /utenti/nuovo con sessione, CSRF e audit esistenti."
      >
        {form ? (
          <LegacyPostForm
            action={form.action}
            csrfField={form.csrfField}
            submitLabel={form.submitLabel}
            title={form.title}
            description={form.description}
            fields={form.fields}
            disabled={form.enabled === false}
          />
        ) : (
          <EmptyState
            title="Permesso di creazione non disponibile"
            message="La creazione richiede il permesso utenti.scrivi. Le scritture restano sulle route legacy."
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
            <NewUserView data={data} />
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
