import { useEffect, useMemo, useState } from 'react'
import { RefreshCw, UsersRound } from 'lucide-react'
import {
  emptyProfiliPage,
  getProfiliPage,
  type ProfiloPermissionRecord,
  type ProfiliPageData,
} from '../profiliData'
import { Badge } from '../ui/Badge'
import { ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LegacyPostForm } from '../ui/LegacyPostForm'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import './ProfiliPage.css'

function formatValue(value: string | number): string {
  if (typeof value === 'number') return new Intl.NumberFormat('it-IT').format(value)
  return value
}

function PermissionLine({ permission, roles }: { permission: ProfiloPermissionRecord; roles: string[] }) {
  return (
    <article className="iu-profiles-permission">
      <div className="iu-profiles-permission__label">
        <strong>{permission.label}</strong>
        <span>{permission.category} · {permission.permission}</span>
      </div>
      <div className="iu-profiles-permission__grants">
        {roles.map((role) => {
          const grant = permission.grants.find((item) => item.role === role)
          return (
            <span className="iu-profiles-grant" key={`${permission.id}-${role}`}>
              <small>{role.replace('_', ' ')}</small>
              <Badge tone={grant?.granted ? 'success' : 'neutral'}>{grant?.granted ? 'Si' : 'No'}</Badge>
            </span>
          )
        })}
      </div>
    </article>
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

export function ProfiliPage() {
  const [data, setData] = useState<ProfiliPageData>(emptyProfiliPage)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    getProfiliPage()
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

  const hasData = data.metrics.length > 0 || data.records.roles.length > 0 || data.records.permissions.length > 0
  const roles = useMemo(() => data.records.roles.map((role) => role.role), [data.records.roles])
  const permissionsByCategory = useMemo(() => {
    const grouped = new Map<string, ProfiloPermissionRecord[]>()
    for (const permission of data.records.permissions) {
      const items = grouped.get(permission.category) || []
      items.push(permission)
      grouped.set(permission.category, items)
    }
    return [...grouped.entries()]
  }, [data.records.permissions])

  return (
    <Page
      title="Profili e permessi"
      subtitle="Matrice RBAC reale dello studio, con scritture mantenute sulle route legacy."
      actions={
        <>
          <ButtonLink href="/profili" tone="primary">
            <RefreshCw size={16} />
            Aggiorna
          </ButtonLink>
          <ButtonLink href="/utenti" tone="neutral">
            <UsersRound size={16} />
            Utenti
          </ButtonLink>
        </>
      }
    >
      {loading ? <LoadingState title="Caricamento profili" message="Lettura di ruoli e permessi reali in corso." /> : null}
      {!loading && !hasData ? (
        <EmptyState
          title="Nessuna matrice permessi disponibile"
          message="Il repository utenti non ha restituito ruoli o permessi visualizzabili."
        />
      ) : null}
      {!loading && hasData ? (
        <>
          <Warnings data={data} />
          <section className="iu-profiles-kpis" aria-label="KPI profili">
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
          <section className="iu-profiles-roles" aria-label="Ruoli">
            {data.records.roles.map((role) => (
              <Panel title={role.label} subtitle={role.description} key={role.id}>
                <div className="iu-profiles-role">
                  <Badge tone={role.tone}>{role.role}</Badge>
                  <strong>{role.usersCount} utenti</strong>
                  <span>{role.permissionsCount} permessi base</span>
                  {role.users.length ? (
                    <div className="iu-profiles-role__users">
                      {role.users.slice(0, 5).map((user) => (
                        <a href={user.permissionsHref} key={user.id || user.username}>
                          {user.label || user.username}
                          {user.hasOverride ? <Badge tone="warning">override</Badge> : null}
                        </a>
                      ))}
                    </div>
                  ) : (
                    <small>Nessun utente collegato.</small>
                  )}
                </div>
              </Panel>
            ))}
          </section>
          <Panel title="Matrice permessi" subtitle={`${data.records.permissions.length} permessi, ${roles.length} ruoli`}>
            {permissionsByCategory.length ? (
              <div className="iu-profiles-matrix">
                {permissionsByCategory.map(([category, permissions]) => (
                  <section className="iu-profiles-category" key={category}>
                    <h2>{category}</h2>
                    <div className="iu-profiles-permissions">
                      {permissions.map((permission) => (
                        <PermissionLine permission={permission} roles={roles} key={permission.id} />
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            ) : (
              <EmptyState title="Nessun permesso censito" />
            )}
          </Panel>
          <Panel title="Override utente" subtitle="Eccezioni reali rispetto ai permessi base del ruolo.">
            {data.records.overrides.length ? (
              <div className="iu-profiles-overrides">
                {data.records.overrides.map((override) => {
                  const form = data.forms.find((item) => item.id === `reset-${override.id}`)
                  return (
                    <article className="iu-profiles-override" key={override.id || override.username}>
                      <div>
                        <strong>{override.label || override.username}</strong>
                        <span>{override.role}</span>
                        <small>Extra: {override.extraPermissions.join(', ') || 'nessuno'}</small>
                        <small>Rimossi: {override.deniedPermissions.join(', ') || 'nessuno'}</small>
                      </div>
                      <div className="iu-profiles-override__actions">
                        <ButtonLink href={override.permissionsHref} tone="neutral">Modifica legacy</ButtonLink>
                        {form ? (
                          <LegacyPostForm
                            action={form.action}
                            csrfField={form.csrfField}
                            submitLabel={form.submitLabel}
                            fields={form.fields}
                            disabled={form.enabled === false}
                          />
                        ) : null}
                      </div>
                    </article>
                  )
                })}
              </div>
            ) : (
              <EmptyState title="Nessun override configurato" message="Tutti gli utenti seguono i permessi standard del ruolo." />
            )}
          </Panel>
          <Panel title="Contratto dati" subtitle="RBAC letto dal dominio esistente.">
            <div className="iu-profiles-contract">
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
