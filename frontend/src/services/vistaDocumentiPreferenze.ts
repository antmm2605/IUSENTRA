/**
 * Vista preferita dell'elenco documenti del fascicolo.
 * Si salva su richiesta dell'avvocato e vale per tutti i fascicoli dello studio:
 * chi lavora sulle scadenze riapre sui «Da firmare», chi controlla la
 * catalogazione sui «Senza sezione», senza rifare la scelta ogni volta.
 */
import { csrfHeader } from '../api/csrf'

export type VistaDocumenti = { sort: string; section: string; status: string }
export type VistaDocumentiSalvata = { configured: boolean; updatedAt: string; preferences: VistaDocumenti }

const ENDPOINT = '/api/v1/ui/fascicoli/preferenze-vista-documenti'

export const VISTA_DOCUMENTI_PREDEFINITA: VistaDocumenti = {
  sort: 'data_documento_desc',
  section: 'tutte',
  status: 'tutti',
}

function normalizza(payload: unknown): VistaDocumentiSalvata {
  const record = (payload && typeof payload === 'object' ? payload : {}) as Record<string, unknown>
  const grezze = (record.preferences && typeof record.preferences === 'object' ? record.preferences : {}) as Record<string, unknown>
  return {
    configured: record.configured === true,
    updatedAt: String(record.updatedAt || ''),
    preferences: {
      sort: String(grezze.sort || VISTA_DOCUMENTI_PREDEFINITA.sort),
      section: String(grezze.section || VISTA_DOCUMENTI_PREDEFINITA.section),
      status: String(grezze.status || VISTA_DOCUMENTI_PREDEFINITA.status),
    },
  }
}

export async function leggiVistaDocumenti(signal?: AbortSignal): Promise<VistaDocumentiSalvata> {
  const response = await fetch(ENDPOINT, {
    method: 'GET',
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
    signal,
  })
  if (!response.ok) throw new Error('Vista dei documenti non disponibile.')
  return normalizza(await response.json())
}

export async function salvaVistaDocumenti(vista: VistaDocumenti): Promise<VistaDocumentiSalvata> {
  return inviaVista({ ...vista })
}

export async function dimenticaVistaDocumenti(): Promise<VistaDocumentiSalvata> {
  return inviaVista({ reset: true })
}

async function inviaVista(corpo: Record<string, unknown>): Promise<VistaDocumentiSalvata> {
  const response = await fetch(ENDPOINT, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json', ...csrfHeader() },
    body: JSON.stringify(corpo),
  })
  const payload = await response.json().catch(() => null) as Record<string, unknown> | null
  if (!response.ok || payload?.ok !== true) {
    throw new Error(String(payload?.message || 'Vista non salvata. Riprova.'))
  }
  return normalizza(payload)
}
