import { apiJson, apiPostJson } from './lib/apiClient'
import { sanitizeDisplayText } from './displayText'

export type AiRisk = {
  area: string
  severity: string
  severityLabel: string
  message: string
  suggestion: string
}

export type AiJob = {
  id: number
  topic: string
  title: string
  excerpt: string
  statusLabel: string
  articleId: number
  createdAt: string
  createdBy: string
  risks: AiRisk[]
  draftAvailable: boolean
}

export type AiArticle = {
  id: number
  title: string
  excerpt: string
  category: string
  statusLabel: string
  published: boolean
  coverUrl: string
  updatedAt: string
  editHref: string
}

export type AiSummary = {
  jobs: number
  articles: number
  drafts: number
  published: number
  checks: number
}

export type SitoStudioAiData = {
  ok: boolean
  message: string
  generatedAt: string
  site: { id: number; siteName: string; studioName: string; publicSlug: string }
  jobs: AiJob[]
  articles: AiArticle[]
  summary: AiSummary
  actions: { builder: string; dashboard: string; publicSite: string }
}

export type AiMutation = {
  ok: boolean
  message: string
  payload?: SitoStudioAiData
}

export type AiGenerateForm = {
  argomento: string
  area_diritto: string
  servizio_collegato: string
  pubblico_destinatario: string
  tono: string
  lunghezza: string
  parole_chiave_seo: string
  call_to_action: string
  fonte_manual: string
  note_interne: string
}

export const emptyAiForm: AiGenerateForm = {
  argomento: '',
  area_diritto: '',
  servizio_collegato: '',
  pubblico_destinatario: 'Privati',
  tono: 'divulgativo',
  lunghezza: 'media',
  parole_chiave_seo: '',
  call_to_action: '',
  fonte_manual: '',
  note_interne: '',
}

export const emptySitoStudioAiData: SitoStudioAiData = {
  ok: false,
  message: '',
  generatedAt: '',
  site: { id: 0, siteName: '', studioName: '', publicSlug: '' },
  jobs: [],
  articles: [],
  summary: { jobs: 0, articles: 0, drafts: 0, published: 0, checks: 0 },
  actions: { builder: '/sito-studio/builder', dashboard: '/sito-studio', publicSite: '/sito-studio' },
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function text(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? sanitizeDisplayText(value.trim()) : fallback
}

function rawText(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value.trim() : fallback
}

function number(value: unknown): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function bool(value: unknown): boolean {
  return value === true || value === 'true' || value === 1 || value === '1'
}

function normaliseRisk(raw: unknown): AiRisk {
  const item = asRecord(raw)
  return {
    area: text(item.area, 'Controllo'),
    severity: rawText(item.severity),
    severityLabel: text(item.severityLabel, 'Nota'),
    message: text(item.message),
    suggestion: text(item.suggestion),
  }
}

function normaliseJob(raw: unknown): AiJob {
  const item = asRecord(raw)
  return {
    id: number(item.id),
    topic: text(item.topic),
    title: text(item.title, 'Bozza articolo'),
    excerpt: text(item.excerpt),
    statusLabel: text(item.statusLabel, 'Da rivedere'),
    articleId: number(item.articleId),
    createdAt: rawText(item.createdAt),
    createdBy: text(item.createdBy),
    risks: list(item.risks).map(normaliseRisk),
    draftAvailable: bool(item.draftAvailable),
  }
}

function normaliseArticle(raw: unknown): AiArticle {
  const item = asRecord(raw)
  return {
    id: number(item.id),
    title: text(item.title, 'Articolo senza titolo'),
    excerpt: text(item.excerpt),
    category: text(item.category, 'Senza categoria'),
    statusLabel: text(item.statusLabel, 'Bozza'),
    published: bool(item.published),
    coverUrl: rawText(item.coverUrl),
    updatedAt: rawText(item.updatedAt),
    editHref: rawText(item.editHref, '/sito-studio'),
  }
}

export function normaliseSitoStudioAi(raw: unknown): SitoStudioAiData {
  const item = asRecord(raw)
  const summary = asRecord(item.summary)
  const site = asRecord(item.site)
  const actions = asRecord(item.actions)
  return {
    ...emptySitoStudioAiData,
    ok: item.ok !== false,
    message: text(item.message),
    generatedAt: rawText(item.generated_at ?? item.generatedAt),
    site: {
      id: number(site.id),
      siteName: text(site.siteName, 'Sito Studio'),
      studioName: text(site.studioName),
      publicSlug: rawText(site.publicSlug),
    },
    jobs: list(item.jobs).map(normaliseJob).filter((job) => job.id),
    articles: list(item.articles).map(normaliseArticle).filter((article) => article.id),
    summary: {
      jobs: number(summary.jobs),
      articles: number(summary.articles),
      drafts: number(summary.drafts),
      published: number(summary.published),
      checks: number(summary.checks),
    },
    actions: {
      builder: rawText(actions.builder, '/sito-studio/builder'),
      dashboard: rawText(actions.dashboard, '/sito-studio'),
      publicSite: rawText(actions.publicSite, '/sito-studio'),
    },
  }
}

function normaliseMutation(raw: unknown): AiMutation {
  const item = asRecord(raw)
  return {
    ok: item.ok === true,
    message: text(item.message, item.ok === true ? 'Operazione completata.' : 'Operazione non completata.'),
    payload: item.payload ? normaliseSitoStudioAi(item.payload) : undefined,
  }
}

export async function getSitoStudioAi(signal?: AbortSignal): Promise<SitoStudioAiData> {
  const payload = await apiJson('/api/v1/ui/sito-studio/redazione-ai', emptySitoStudioAiData, { signal })
  return normaliseSitoStudioAi(payload)
}

export async function postSitoStudioAi(url: string, body: unknown = {}): Promise<AiMutation> {
  const payload = await apiPostJson(url, body, { ok: false, message: 'Operazione non completata.' })
  return normaliseMutation(payload)
}
