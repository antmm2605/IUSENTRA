import { apiJson, apiPostJson } from '@/lib/apiClient'
import type { Correzione, EsitoCorrezione, Passaggio, RegolaStudio } from './types'

type PassaggiPayload = { ok: boolean; passaggi: Passaggio[]; errore?: string }
type RegolePayload = { ok: boolean; regole: RegolaStudio[]; errore?: string }
type RegolaPayload = { ok: boolean; regola?: RegolaStudio; errore?: string }

export function leggiPassaggi(fascicoloId: string, signal?: AbortSignal): Promise<PassaggiPayload> {
  return apiJson<PassaggiPayload>(
    `/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/passaggi`,
    { ok: false, passaggi: [], errore: 'Passaggi del software non disponibili.' },
    { signal, activity: false },
  )
}

export function correggiPassaggio(fascicoloId: string, correzione: Correzione): Promise<EsitoCorrezione> {
  return apiPostJson<EsitoCorrezione>(
    `/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/passaggi/correzioni`,
    correzione,
    { ok: false, errore: 'Correzione non registrata.' },
    { activity: 'Registrazione della regola dello studio…' },
  )
}

export function leggiRegoleStudio(signal?: AbortSignal): Promise<RegolePayload> {
  return apiJson<RegolePayload>('/api/v1/ui/regole-studio', { ok: false, regole: [], errore: 'Regole dello studio non disponibili.' }, { signal })
}

export function aggiornaRegolaStudio(id: string, modifiche: { valore?: string; motivo?: string; attiva?: boolean }): Promise<RegolaPayload> {
  return apiPostJson<RegolaPayload>(`/api/v1/ui/regole-studio/${encodeURIComponent(id)}`, modifiche, { ok: false, errore: 'Regola non aggiornata.' })
}
