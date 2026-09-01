import type { Tone } from './data'
import type { ReactContracts } from './timesheetData'

export type ClientCollaborator = {
  idUser: string
  username: string
  name: string
  role: string
  roleLabel: string
  roleTone: Tone
  sharedBy: string
  sharedAt: string
  sharedAtLabel: string
  deadline: string
  deadlineLabel: string
  daysToDeadline: number | null
  expired: boolean
  expiring: boolean
  notes: string
  tags: string[]
}

export type AvailableCollaborator = {
  id: string
  username: string
  name: string
}

export type CollaboratorRole = {
  value: string
  label: string
  tone: Tone
  description: string
}

export type ClientCollaboratorsData = {
  source: string
  contracts: ReactContracts
  client: {
    id: string
    name: string
    type: string
    href: string
    collaboratorsHref: string
  }
  permissions: { canManage: boolean }
  collaborators: ClientCollaborator[]
  availableUsers: AvailableCollaborator[]
  roleOptions: CollaboratorRole[]
  actions: {
    client: string
    folder: string
    sharedFolders: string
    audit: string
    collection: string
  }
  emptyStates: {
    noCollaborators: boolean
    noAvailableUsers: boolean
  }
}

export type AddClientCollaboratorInput = {
  id_utente: string
  ruolo: string
  data_scadenza: string
  note: string
  tags: string[]
}

function csrfToken(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content || ''
}

async function readJson<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => ({})) as Record<string, unknown>
  if (!response.ok) {
    throw new Error(String(payload.errore || payload.messaggio || 'Operazione non disponibile.'))
  }
  return payload as T
}

export async function getClientCollaborators(clientId: string): Promise<ClientCollaboratorsData> {
  const response = await fetch(`/api/v1/clienti/${encodeURIComponent(clientId)}/condivisioni`, {
    credentials: 'same-origin',
    cache: 'no-store',
    headers: { Accept: 'application/json' },
  })
  return readJson<ClientCollaboratorsData>(response)
}

export async function addClientCollaborator(
  clientId: string,
  input: AddClientCollaboratorInput,
): Promise<{ stato: string; messaggio: string }> {
  const response = await fetch(`/api/v1/clienti/${encodeURIComponent(clientId)}/condivisioni`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken(),
    },
    body: JSON.stringify(input),
  })
  return readJson(response)
}

export async function revokeClientCollaborator(clientId: string, userId: string): Promise<{ stato: string; messaggio: string }> {
  const response = await fetch(
    `/api/v1/clienti/${encodeURIComponent(clientId)}/condivisioni/${encodeURIComponent(userId)}`,
    {
      method: 'DELETE',
      credentials: 'same-origin',
      headers: { Accept: 'application/json', 'X-CSRFToken': csrfToken() },
    },
  )
  return readJson(response)
}
