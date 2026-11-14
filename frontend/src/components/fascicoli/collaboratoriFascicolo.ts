import type { AvailableCollaborator, ClientCollaborator, CollaboratorRole } from '../../clientiCollaboratoriData'

/** Dati del pannello «Collaboratori del fascicolo» (GET /api/v1/fascicoli/<id>/collaboratori). */
export type CollaboratoriFascicolo = {
  matter: { id: string; number: string; title: string }
  permissions: { canManage: boolean }
  collaborators: ClientCollaborator[]
  availableUsers: AvailableCollaborator[]
  roleOptions: CollaboratorRole[]
}

export type NuovoCollaboratoreFascicolo = {
  id_utente: string
  ruolo: string
  data_scadenza: string
  note: string
  tags: string[]
}

/** Errore con lo stato HTTP: il pannello distingue «non autorizzato» (403) dagli altri guasti. */
export class ErroreCollaboratori extends Error {
  constructor(message: string, readonly status: number) {
    super(message)
  }
}

function csrfToken(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content || ''
}

async function leggi<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => ({})) as Record<string, unknown>
  if (!response.ok) throw new ErroreCollaboratori(String(payload.errore || 'Operazione non disponibile.'), response.status)
  return payload as T
}

const base = (fascicoloId: string) => `/api/v1/fascicoli/${encodeURIComponent(fascicoloId)}/collaboratori`

export async function leggiCollaboratoriFascicolo(fascicoloId: string): Promise<CollaboratoriFascicolo> {
  const response = await fetch(base(fascicoloId), { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } })
  return leggi<CollaboratoriFascicolo>(response)
}

export async function condividiFascicolo(fascicoloId: string, input: NuovoCollaboratoreFascicolo): Promise<{ messaggio: string }> {
  const response = await fetch(base(fascicoloId), {
    method: 'POST',
    credentials: 'same-origin',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
    body: JSON.stringify(input),
  })
  return leggi(response)
}

export async function revocaCollaboratoreFascicolo(fascicoloId: string, idUtente: string): Promise<{ messaggio: string }> {
  const response = await fetch(`${base(fascicoloId)}/${encodeURIComponent(idUtente)}`, {
    method: 'DELETE',
    credentials: 'same-origin',
    headers: { Accept: 'application/json', 'X-CSRFToken': csrfToken() },
  })
  return leggi(response)
}
