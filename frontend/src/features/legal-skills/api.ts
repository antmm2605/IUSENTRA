import { apiJson, apiPostJson } from '@/api/client'
import type {
  LegalSkill,
  LegalSkillPack,
  LegalSkillProfile,
  LegalSkillRunResult,
  LegalSkillsPayload,
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
