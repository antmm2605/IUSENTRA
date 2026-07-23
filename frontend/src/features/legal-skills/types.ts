export type TrustFinding = {
  code: string
  severity: 'clean' | 'warning' | 'concern' | 'material_concern' | 'refuse' | string
  message: string
  action?: string
}

export type LegalSkill = {
  pack_id: string
  skill_id: string
  name: string
  description: string
  area: string
  argument_hint?: string
  allowed_tools?: string[]
  references?: string[]
  required_context?: string[]
  source_mode?: string
  trust_status?: string
  trust_findings?: TrustFinding[]
  output_schema?: Record<string, unknown>
}

export type LegalSkillPack = {
  pack_id: string
  name: string
  description: string
  area: string
  jurisdiction: string
  source_mode: string
  skills_count?: number
  skills?: LegalSkill[]
}

export type LegalSkillProfile = {
  profile_id: string
  status: 'ready' | 'incomplete' | string
  firm_name: string
  jurisdictions: string[]
  practice_areas: string[]
  preferred_source_mode: string
  missing_fields: string[]
  updated_at?: string
  updated_by?: string
}

export type LegalSkillCitation = {
  label: string
  source_type: string
  reference: string
  reliability: string
  url?: string
  excerpt?: string
}

export type LegalSkillFinding = {
  title: string
  status: string
  severity: string
  summary: string
  recommendation: string
  citations?: LegalSkillCitation[]
}

export type LegalSkillReviewerNote = {
  text: string
  needs_review: boolean
  blocks_export: boolean
  reasons: string[]
}

export type LegalSkillRunResult = {
  run_id: string
  pack_id: string
  skill_id: string
  status: string
  question: string
  answer: string
  findings: LegalSkillFinding[]
  citations: LegalSkillCitation[]
  reviewer_note: LegalSkillReviewerNote
  confidence: string
  source_mode: string
  needs_review: boolean
  disable_exports: boolean
  approved_at?: string
  approved_by?: string
  created_at: string
}

export type ScheduledLegalSkillAgent = {
  agent_id: string
  name: string
  description: string
  skill_ref: string
  enabled: boolean
  read_only: boolean
}

export type LegalSkillsPayload<T> = {
  ok: boolean
  code?: string
  message?: string
} & T

export type PromptLibraryArea = {
  area_id: string
  nome: string
  descrizione: string
  numero_voci: number
  numero_prompt: number
  preferita?: boolean
}

export type PromptLibraryCaseContext = {
  fascicolo_id: string
  numero: string
  titolo: string
  cliente: string
  controparte: string
  ufficio: string
  rg: string
  oggetto: string
  documenti: string[]
  scadenze: string[]
}

export type PromptLibraryForma = {
  forma_id: string
  label: string
  descrizione: string
}

export type PromptLibraryEntry = {
  prompt_id: string
  titolo: string
  area_id: string
  area_nome: string
  voce_id: string
  forma: string
  forma_label: string
  descrizione: string
  riferimenti: string[]
  tags: string[]
}

export type PromptLibraryDetail = PromptLibraryEntry & {
  testo: string
  forma_descrizione: string
  contesto_fascicolo?: PromptLibraryCaseContext
}
