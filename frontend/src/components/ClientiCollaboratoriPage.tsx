import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ArrowLeft,
  CalendarDays,
  CheckCircle2,
  FolderOpen,
  History,
  Info,
  RefreshCw,
  ShieldCheck,
  Trash2,
  UserPlus,
  UsersRound,
} from 'lucide-react'
import { Badge } from './dashboard'
import {
  addClientCollaborator,
  getClientCollaborators,
  revokeClientCollaborator,
  type ClientCollaboratorsData,
} from '../clientiCollaboratoriData'
import './ClientiCollaboratoriPage.css'
import './ClientiCollaboratoriControls.css'

function clientIdFromLocation(): string {
  const parts = window.location.pathname.split('/').filter(Boolean)
  const clientiIndex = parts.indexOf('clienti')
  return clientiIndex >= 0 ? decodeURIComponent(parts[clientiIndex + 1] || '') : ''
}

function todayInRomeIso(): string {
  const parts = new Intl.DateTimeFormat('it-IT', {
    timeZone: 'Europe/Rome',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  const value = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${value.year}-${value.month}-${value.day}`
}

function LoadingPage() {
  return (
    <main className="iu-content iu-client-collab-page" aria-busy="true">
      <div className="iu-client-collab-skeleton iu-client-collab-skeleton--hero" />
      <div className="iu-client-collab-layout">
        <div className="iu-client-collab-skeleton iu-client-collab-skeleton--list" />
        <div className="iu-client-collab-skeleton iu-client-collab-skeleton--form" />
      </div>
      <span className="sr-only">Caricamento collaboratori…</span>
    </main>
  )
}

export function ClientiCollaboratoriPage() {
  const clientId = clientIdFromLocation()
  const [data, setData] = useState<ClientCollaboratorsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [selectedUser, setSelectedUser] = useState('')
  const [selectedRole, setSelectedRole] = useState('LETTURA')
  const [deadline, setDeadline] = useState('')
  const [notes, setNotes] = useState('')
  const [tags, setTags] = useState('')
  const [revokeTarget, setRevokeTarget] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const payload = await getClientCollaborators(clientId)
      setData(payload)
      if (payload.roleOptions.length) {
        setSelectedRole((current) => payload.roleOptions.some((role) => role.value === current) ? current : payload.roleOptions[0].value)
      }
    } catch (reason) {
      setData(null)
      setError(reason instanceof Error ? reason.message : 'Impossibile caricare i collaboratori del cliente.')
    } finally {
      setLoading(false)
    }
  }, [clientId])

  useEffect(() => {
    void load()
  }, [load])

  const selectedRoleDescription = useMemo(
    () => data?.roleOptions.find((role) => role.value === selectedRole)?.description || '',
    [data, selectedRole],
  )

  async function handleAdd(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedUser) {
      setError('Seleziona il collaboratore da aggiungere.')
      return
    }
    setSubmitting(true)
    setError('')
    setSuccess('')
    try {
      const result = await addClientCollaborator(clientId, {
        id_utente: selectedUser,
        ruolo: selectedRole,
        data_scadenza: deadline,
        note: notes.trim(),
        tags: tags.split(',').map((tag) => tag.trim()).filter(Boolean),
      })
      setSuccess(result.messaggio || 'Collaboratore aggiunto.')
      setSelectedUser('')
      setDeadline('')
      setNotes('')
      setTags('')
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Impossibile aggiungere il collaboratore.')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleRevoke(userId: string) {
    setSubmitting(true)
    setError('')
    setSuccess('')
    try {
      const result = await revokeClientCollaborator(clientId, userId)
      setSuccess(result.messaggio || 'Accesso revocato.')
      setRevokeTarget('')
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Impossibile revocare l’accesso.')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading && !data) return <LoadingPage />

  if (!data) {
    return (
      <main className="iu-content iu-client-collab-page">
        <section className="iu-client-collab-state iu-client-collab-state--error" role="alert">
          <ShieldCheck size={24} />
          <div>
            <h1>Collaboratori non disponibili</h1>
            <p>{error || 'Non è stato possibile leggere gli accessi alla cartella cliente.'}</p>
          </div>
          <button type="button" onClick={() => void load()}><RefreshCw size={16} />Riprova</button>
        </section>
      </main>
    )
  }

  return (
    <main className="iu-content iu-client-collab-page">
      <header className="iu-client-collab-hero">
        <div>
          <span className="iu-client-collab-kicker"><UsersRound size={15} />Accessi alla cartella cliente</span>
          <h1>Collaboratori di {data.client.name}</h1>
          <p>Assegna solo gli accessi necessari, definisci il ruolo e revoca l’autorizzazione quando il lavoro è concluso.</p>
        </div>
        <nav className="iu-client-collab-hero-actions" aria-label="Azioni cliente">
          <a href={data.actions.client}><ArrowLeft size={16} />Cliente</a>
          <a href={data.actions.folder}><FolderOpen size={16} />Cartella cliente</a>
          <a href={data.actions.audit}><History size={16} />Audit accessi</a>
        </nav>
      </header>

      {error ? <div className="iu-client-collab-feedback iu-client-collab-feedback--error" role="alert">{error}</div> : null}
      {success ? <div className="iu-client-collab-feedback iu-client-collab-feedback--success" role="status"><CheckCircle2 size={17} />{success}</div> : null}

      <section className="iu-client-collab-summary" aria-label="Riepilogo collaboratori">
        <div>
          <span>Accessi attivi</span>
          <strong>{data.collaborators.filter((item) => !item.expired).length}</strong>
        </div>
        <div>
          <span>In scadenza</span>
          <strong>{data.collaborators.filter((item) => item.expiring).length}</strong>
        </div>
        <div>
          <span>Scaduti</span>
          <strong>{data.collaborators.filter((item) => item.expired).length}</strong>
        </div>
      </section>

      <div className="iu-client-collab-layout">
        <section className="iu-client-collab-panel" aria-labelledby="collaboratori-attuali">
          <div className="iu-client-collab-panel-heading">
            <div>
              <span>Accessi correnti</span>
              <h2 id="collaboratori-attuali">Collaboratori autorizzati</h2>
            </div>
            <Badge tone={data.collaborators.length ? 'primary' : 'neutral'}>{data.collaborators.length}</Badge>
          </div>

          {data.collaborators.length ? (
            <div className="iu-client-collab-list">
              {data.collaborators.map((collaborator) => (
                <article className="iu-client-collab-card" key={collaborator.idUser}>
                  <div className="iu-client-collab-avatar" aria-hidden="true">
                    {(collaborator.name || collaborator.username).slice(0, 2).toUpperCase()}
                  </div>
                  <div className="iu-client-collab-card-main">
                    <div className="iu-client-collab-card-title">
                      <div>
                        <h3>{collaborator.name}</h3>
                        <span>{collaborator.username}</span>
                      </div>
                      <div className="iu-client-collab-badges">
                        <Badge tone={collaborator.roleTone}>{collaborator.roleLabel}</Badge>
                        {collaborator.expired ? <Badge tone="danger">Scaduto</Badge> : collaborator.expiring ? <Badge tone="warning">In scadenza</Badge> : <Badge tone="success">Attivo</Badge>}
                      </div>
                    </div>
                    <dl className="iu-client-collab-meta">
                      <div><dt>Condiviso da</dt><dd>{collaborator.sharedBy || 'Studio'}</dd></div>
                      <div><dt>Dal</dt><dd>{collaborator.sharedAtLabel || 'Data non disponibile'}</dd></div>
                      <div><dt>Scadenza</dt><dd>{collaborator.deadlineLabel}</dd></div>
                    </dl>
                    {collaborator.notes ? <p className="iu-client-collab-notes">{collaborator.notes}</p> : null}
                    {collaborator.tags.length ? <div className="iu-client-collab-tags">{collaborator.tags.map((tag) => <span key={tag}>{tag}</span>)}</div> : null}
                  </div>
                  {data.permissions.canManage ? (
                    <div className="iu-client-collab-revoke">
                      {revokeTarget === collaborator.idUser ? (
                        <div className="iu-client-collab-confirm" role="group" aria-label={`Conferma revoca per ${collaborator.name}`}>
                          <span>Revocare questo accesso?</span>
                          <button type="button" className="iu-client-collab-danger" disabled={submitting} onClick={() => void handleRevoke(collaborator.idUser)}>Conferma</button>
                          <button type="button" disabled={submitting} onClick={() => setRevokeTarget('')}>Annulla</button>
                        </div>
                      ) : (
                        <button type="button" className="iu-client-collab-revoke-button" disabled={submitting} onClick={() => setRevokeTarget(collaborator.idUser)}>
                          <Trash2 size={15} />Revoca accesso
                        </button>
                      )}
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          ) : (
            <div className="iu-client-collab-empty">
              <UsersRound size={24} />
              <div><strong>Nessun collaboratore autorizzato</strong><span>La cartella è accessibile solo ai profili già abilitati dallo studio.</span></div>
            </div>
          )}
        </section>

        <aside className="iu-client-collab-panel iu-client-collab-panel--form" aria-labelledby="aggiungi-collaboratore">
          <div className="iu-client-collab-panel-heading">
            <div>
              <span>Nuovo accesso</span>
              <h2 id="aggiungi-collaboratore">Aggiungi collaboratore</h2>
            </div>
            <UserPlus size={20} />
          </div>

          {data.permissions.canManage ? (
            data.availableUsers.length ? (
              <form onSubmit={handleAdd}>
                <label>
                  Collaboratore
                  <select value={selectedUser} onChange={(event) => setSelectedUser(event.target.value)} required>
                    <option value="">Seleziona un profilo</option>
                    {data.availableUsers.map((user) => <option key={user.id} value={user.id}>{user.name} · {user.username}</option>)}
                  </select>
                </label>
                <label>
                  Ruolo
                  <select value={selectedRole} onChange={(event) => setSelectedRole(event.target.value)} required>
                    {data.roleOptions.map((role) => <option key={role.value} value={role.value}>{role.label}</option>)}
                  </select>
                </label>
                {selectedRoleDescription ? <p className="iu-client-collab-role-help"><Info size={15} />{selectedRoleDescription}</p> : null}
                <label>
                  Scadenza accesso <span>facoltativa</span>
                  <input type="date" min={todayInRomeIso()} value={deadline} onChange={(event) => setDeadline(event.target.value)} />
                </label>
                <label>
                  Note operative <span>facoltative</span>
                  <textarea rows={3} maxLength={1000} value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Motivo o perimetro della collaborazione" />
                </label>
                <label>
                  Tag <span>separati da virgola</span>
                  <input type="text" value={tags} onChange={(event) => setTags(event.target.value)} placeholder="es. contenzioso, udienza" />
                </label>
                <button className="iu-client-collab-submit" type="submit" disabled={submitting || !selectedUser}>
                  {submitting ? <RefreshCw className="iu-client-collab-spin" size={17} /> : <UserPlus size={17} />}
                  {submitting ? 'Salvataggio…' : 'Aggiungi collaboratore'}
                </button>
              </form>
            ) : (
              <div className="iu-client-collab-empty iu-client-collab-empty--compact">
                <CheckCircle2 size={22} />
                <div><strong>Nessun altro profilo disponibile</strong><span>Tutti gli utenti attivi sono già autorizzati oppure coincidono con il profilo in uso.</span></div>
              </div>
            )
          ) : (
            <div className="iu-client-collab-empty iu-client-collab-empty--compact">
              <ShieldCheck size={22} />
              <div><strong>Consultazione in sola lettura</strong><span>Solo un gestore della cartella o un profilo con permesso clienti può modificare gli accessi.</span></div>
            </div>
          )}

          <div className="iu-client-collab-guidance">
            <CalendarDays size={17} />
            <p><strong>Principio di necessità</strong> Usa una scadenza quando l’incarico del collaboratore è temporaneo e assegna il ruolo meno esteso compatibile con il lavoro.</p>
          </div>
        </aside>
      </div>
    </main>
  )
}
