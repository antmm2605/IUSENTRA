import { apiJson, apiPostJson } from '@/api/client'
import type {
  LegalSkill,
  LegalSkillPack,
  LegalSkillProfile,
  LegalSkillRunResult,
  LegalSkillsPayload,
  Pathway,
  PromptLibraryArea,
  PromptRevision,
  PromptLibraryDetail,
  PromptLibraryEntry,
  PromptLibraryForma,
  ScheduledLegalSkillAgent,
} from './types'

const API_BASE = '/api/v1/legal-skills'

const emptyPacks: LegalSkillsPayload<{ packs: LegalSkillPack[] }> = { ok: false, packs: [] }
const emptySkills: LegalSkillsPayload<{ skills: LegalSkill[] }> = { ok: false, skills: [] }
const emptyProfile: LegalSkillsPayload<{ profile: LegalSkillProfile | null; status?: string; placeholders?: string[] }> = {
  ok: false,
  profile: null,
  placeholders: [],
}
const emptyAgents: LegalSkillsPayload<{ agents: ScheduledLegalSkillAgent[] }> = { ok: false, agents: [] }

export async function fetchLegalSkillPacks(signal?: AbortSignal) {
  return apiJson(`${API_BASE}/packs`, emptyPacks, { signal })
}

export async function fetchLegalSkillPack(packId: string, signal?: AbortSignal) {
  return apiJson<LegalSkillsPayload<{ pack: LegalSkillPack | null }>>(`${API_BASE}/packs/${packId}`, { ok: false, pack: null }, { signal })
}

export async function fetchLegalSkills(packId: string, signal?: AbortSignal) {
  return apiJson(`${API_BASE}/packs/${packId}/skills`, emptySkills, { signal })
}

export async function fetchLegalSkillsProfile(signal?: AbortSignal) {
  return apiJson(`${API_BASE}/profile`, emptyProfile, { signal })
}

export async function saveLegalSkillsProfile(payload: {
  firm_name: string
  jurisdictions: string[]
  practice_areas: string[]
  preferred_source_mode: string
}) {
  return apiPostJson<LegalSkillsPayload<{ profile: LegalSkillProfile | null }>>(`${API_BASE}/profile/cold-start`, payload, {
    ok: false,
    profile: null,
  })
}

export async function runLegalSkill(payload: {
  pack_id: string
  skill_id: string
  question: string
  source_mode?: string
  context?: Record<string, unknown>
  documents?: Array<{ title: string; text: string }>
}) {
  return apiPostJson<LegalSkillsPayload<{ result: LegalSkillRunResult | null }>>(`${API_BASE}/run`, payload, {
    ok: false,
    result: null,
  })
}

export async function fetchLegalSkillRun(runId: string, signal?: AbortSignal) {
  return apiJson<LegalSkillsPayload<{ result: LegalSkillRunResult | null }>>(`${API_BASE}/runs/${runId}`, { ok: false, result: null }, { signal })
}

export async function approveLegalSkillRun(runId: string) {
  return apiPostJson<LegalSkillsPayload<{ result: LegalSkillRunResult | null }>>(`${API_BASE}/runs/${runId}/approve`, {}, {
    ok: false,
    result: null,
  })
}

export async function exportLegalSkillRun(runId: string) {
  return apiPostJson<LegalSkillsPayload<{ export?: { result: LegalSkillRunResult } }>>(`${API_BASE}/runs/${runId}/export`, {}, {
    ok: false,
  })
}

export async function fetchScheduledLegalSkillAgents(signal?: AbortSignal) {
  return apiJson(`${API_BASE}/scheduled`, emptyAgents, { signal })
}

const PROMPT_LIBRARY_BASE = `${API_BASE}/prompt-library`

export async function fetchPromptLibraryAree(signal?: AbortSignal) {
  return apiJson<
    LegalSkillsPayload<{
      totale_prompt: number
      aree: PromptLibraryArea[]
      forme: PromptLibraryForma[]
      aree_preferite: string[]
    }>
  >(`${PROMPT_LIBRARY_BASE}/aree`, { ok: false, totale_prompt: 0, aree: [], forme: [], aree_preferite: [] }, { signal })
}

export async function searchPromptLibrary(
  params: { q?: string; area?: string; forma?: string; limit?: number },
  signal?: AbortSignal,
) {
  const query = new URLSearchParams()
  if (params.q) query.set('q', params.q)
  if (params.area) query.set('area', params.area)
  if (params.forma) query.set('forma', params.forma)
  if (params.limit) query.set('limit', String(params.limit))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return apiJson<LegalSkillsPayload<{ totale: number; prompts: PromptLibraryEntry[] }>>(
    `${PROMPT_LIBRARY_BASE}/prompts${suffix}`,
    { ok: false, totale: 0, prompts: [] },
    { signal },
  )
}

export async function fetchPromptLibraryPrompt(promptId: string, fascicoloId?: string, signal?: AbortSignal) {
  const suffix = fascicoloId ? `?fascicolo=${encodeURIComponent(fascicoloId)}` : ''
  return apiJson<LegalSkillsPayload<{ prompt: PromptLibraryDetail | null }>>(
    `${PROMPT_LIBRARY_BASE}/prompts/${encodeURIComponent(promptId)}${suffix}`,
    { ok: false, prompt: null },
    { signal },
  )
}

export async function runPromptLibraryPrompt(payload: {
  prompt_id: string
  fascicolo?: string
  nota?: string
  source_mode?: string
}) {
  return apiPostJson<LegalSkillsPayload<{ result: (LegalSkillRunResult & { prompt_id?: string }) | null }>>(
    `${PROMPT_LIBRARY_BASE}/run`,
    payload,
    { ok: false, result: null },
  )
}

const PATHWAYS_BASE = `${PROMPT_LIBRARY_BASE}/percorsi`

export async function fetchPathways(signal?: AbortSignal) {
  return apiJson<LegalSkillsPayload<{ percorsi: Pathway[]; totale: number }>>(
    PATHWAYS_BASE,
    { ok: false, percorsi: [], totale: 0 },
    { signal },
  )
}

export async function fetchPathway(percorsoId: string, fascicoloId?: string, signal?: AbortSignal) {
  const suffix = fascicoloId ? `?fascicolo=${encodeURIComponent(fascicoloId)}` : ''
  return apiJson<LegalSkillsPayload<{ percorso: Pathway | null }>>(
    `${PATHWAYS_BASE}/${encodeURIComponent(percorsoId)}${suffix}`,
    { ok: false, percorso: null },
    { signal },
  )
}

export async function setPathwayStepState(
  percorsoId: string,
  passoId: string,
  payload: { fascicolo: string; completato: boolean },
) {
  return apiPostJson<LegalSkillsPayload<{ percorso: Pathway | null }>>(
    `${PATHWAYS_BASE}/${encodeURIComponent(percorsoId)}/passi/${encodeURIComponent(passoId)}/stato`,
    payload,
    { ok: false, percorso: null },
  )
}

export async function fetchPromptLibraryRevisioni(signal?: AbortSignal) {
  return apiJson<
    LegalSkillsPayload<{
      totale: number
      revisioni: PromptRevision[]
      voci_da_rivedere: Array<{ area_id: string; voce_id: string }>
      fonte_disponibile: boolean
    }>
  >(
    `${PROMPT_LIBRARY_BASE}/revisioni`,
    { ok: false, totale: 0, revisioni: [], voci_da_rivedere: [], fonte_disponibile: false },
    { signal },
  )
}

export async function importDraftToEditor(fascicoloId: string, payload: { answer: string; title?: string }) {
  return apiPostJson<LegalSkillsPayload<{ document_id?: string; open_url?: string; message?: string }>>(
    `/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/editor-ai/importa-bozza`,
    payload,
    { ok: false },
  )
}
