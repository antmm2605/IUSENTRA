import { apiJson, apiPostJson } from '../../lib/apiClient'
import { sanitizeDisplayText } from '../../displayText'

export type PceGap = {
  id: string
  codice_gap: string
  descrizione: string
  severita: 'info' | 'warning' | 'blocking'
  azione_suggerita: string
}

export type PceSource = {
  id: string
  source_type: string
  title: string
  url: string
  authority: string
  trust_class: string
  copyright_policy: string
  excerpt: string
  origin: string
}

export type PceCitation = {
  id: string
  riferimento: string
  atto_normativo: string
  articolo: string
  versione: string
  url: string
  source_id: string
  snippet: string
}

export type PceTemplateCandidate = {
  template_id: string
  titolo: string
  score: number
  canale: string
  area: string
  motivi: string[]
}

export type PceCardSummary = {
  id: string
  codice: string
  denominazione: string
  categoria: string
  status: string
  confidence: string
  riskLevel: string
  gaps: number
  gapsBlocking: number
  fontiUfficiali: number
  citazioni: number
  templateSelezionato: string
  generatedAt: string
}

export type PceCard = {
  id: string
  codice: string
  denominazione: string
  categoria: string
  rito: string
  competenza: string
  uffici_destinatari: string[]
  fonte_catalogo: Record<string, string>
  fonte_normativa: Array<Record<string, string>>
  articoli_rilevanti: string[]
  sintesi_articoli: Array<{ riferimento: string; sintesi: string; fonte_url: string }>
  condizioni_procedibilita: Array<Record<string, string>>
  guida_pratica: string[]
  adempimenti_fiscali: Array<Record<string, string>>
  termini_processuali: Array<Record<string, string>>
  allegati_obbligatori: Array<Record<string, string>>
  avvertimenti_obbligatori: string[]
  atto_principale: Record<string, string>
  template_candidates: PceTemplateCandidate[]
  template_selected: Partial<PceTemplateCandidate>
  checklist_operativa: Array<{ voce: string; completata: boolean; ordine: number }>
  lifecycle_steps: Array<{ ordine: number; step: string; label: string; note: string }>
  firma_digitale: Record<string, unknown>
  deposito_telematico: Record<string, unknown>
  ricevute_attese: string[]
  notifiche: Record<string, unknown>
  prova_notifica: Record<string, unknown>
  rischi_operativi: string[]
  gap_evidenza: PceGap[]
  confidence: string
  status: string
  risk_level: string
  review_avvocato: { reviewer: string; reviewed_at: string; reason: string; esito: string }
  citations: PceCitation[]
  sources: PceSource[]
  generated_at: string
}

export type PceValidation = {
  valid: boolean
  approvable: boolean
  publishable: boolean
  errors: string[]
  warnings: string[]
  blocking_errors: string[]
  privacy_review_required: boolean
}

export type PceDashboard = {
  ok: boolean
  errore: string
  enabled: boolean
  flags: { engine: boolean; voiceRead: boolean; voiceReadLocalOnly: boolean }
  permissions: string[]
  cards: PceCardSummary[]
  gaps: PceGap[]
  counters: { cards: number; needsReview: number; approved: number; published: number; gapsBlocking: number }
  disclaimer: string
}

export type PceCardDetailPayload = {
  ok: boolean
  errore: string
  card: PceCard | null
  validation: PceValidation | null
  draftBanner: string
}

export type PcePreviewResult = {
  ok: boolean
  errore: string
  card: PceCard | null
  validation: PceValidation | null
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function text(value: unknown): string {
  return sanitizeDisplayText(String(value ?? '').trim())
}

function stringList(value: unknown): string[] {
  return list(value).map((item) => text(item)).filter(Boolean)
}

function recordList(value: unknown): Array<Record<string, string>> {
  return list(value).map((item) => {
    const row = record(item)
    const out: Record<string, string> = {}
    for (const [key, raw] of Object.entries(row)) out[key] = text(raw)
    return out
  })
}

function normaliseGap(input: unknown): PceGap {
  const item = record(input)
  const severita = text(item.severita)
  return {
    id: text(item.id) || text(item.codice_gap) || 'gap',
    codice_gap: text(item.codice_gap),
    descrizione: text(item.descrizione),
    severita: severita === 'blocking' || severita === 'info' ? severita : 'warning',
    azione_suggerita: text(item.azione_suggerita),
  }
}

function normaliseValidation(input: unknown): PceValidation | null {
  const item = record(input)
  if (!Object.keys(item).length) return null
  return {
    valid: item.valid === true,
    approvable: item.approvable === true,
    publishable: item.publishable === true,
    errors: stringList(item.errors),
    warnings: stringList(item.warnings),
    blocking_errors: stringList(item.blocking_errors),
    privacy_review_required: item.privacy_review_required === true,
  }
}

function normaliseCard(input: unknown): PceCard | null {
  const item = record(input)
  if (!text(item.id)) return null
  return {
    id: text(item.id),
    codice: text(item.codice),
    denominazione: text(item.denominazione),
    categoria: text(item.categoria),
    rito: text(item.rito),
    competenza: text(item.competenza),
    uffici_destinatari: stringList(item.uffici_destinatari),
    fonte_catalogo: recordList([item.fonte_catalogo])[0] || {},
    fonte_normativa: recordList(item.fonte_normativa),
    articoli_rilevanti: stringList(item.articoli_rilevanti),
    sintesi_articoli: recordList(item.sintesi_articoli) as PceCard['sintesi_articoli'],
    condizioni_procedibilita: recordList(item.condizioni_procedibilita),
    guida_pratica: stringList(item.guida_pratica),
    adempimenti_fiscali: recordList(item.adempimenti_fiscali),
    termini_processuali: recordList(item.termini_processuali),
    allegati_obbligatori: recordList(item.allegati_obbligatori),
    avvertimenti_obbligatori: stringList(item.avvertimenti_obbligatori),
    atto_principale: recordList([item.atto_principale])[0] || {},
    template_candidates: list(item.template_candidates).map((cand) => {
      const row = record(cand)
      return {
        template_id: text(row.template_id),
        titolo: text(row.titolo),
        score: Number(row.score) || 0,
        canale: text(row.canale),
        area: text(row.area),
        motivi: stringList(row.motivi),
      }
    }),
    template_selected: recordList([item.template_selected])[0] || {},
    checklist_operativa: list(item.checklist_operativa).map((voce) => {
      const row = record(voce)
      return { voce: text(row.voce), completata: row.completata === true, ordine: Number(row.ordine) || 0 }
    }),
    lifecycle_steps: list(item.lifecycle_steps).map((step) => {
      const row = record(step)
      return { ordine: Number(row.ordine) || 0, step: text(row.step), label: text(row.label), note: text(row.note) }
    }),
    firma_digitale: record(item.firma_digitale),
    deposito_telematico: record(item.deposito_telematico),
    ricevute_attese: stringList(item.ricevute_attese),
    notifiche: record(item.notifiche),
    prova_notifica: record(item.prova_notifica),
    rischi_operativi: stringList(item.rischi_operativi),
    gap_evidenza: list(item.gap_evidenza).map(normaliseGap),
    confidence: text(item.confidence) || 'LOW',
    status: text(item.status) || 'draft',
    risk_level: text(item.risk_level) || 'medium',
    review_avvocato: {
      reviewer: text(record(item.review_avvocato).reviewer),
      reviewed_at: text(record(item.review_avvocato).reviewed_at),
      reason: text(record(item.review_avvocato).reason),
      esito: text(record(item.review_avvocato).esito),
    },
    citations: list(item.citations).map((cit) => {
      const row = record(cit)
      return {
        id: text(row.id),
        riferimento: text(row.riferimento),
        atto_normativo: text(row.atto_normativo),
        articolo: text(row.articolo),
        versione: text(row.versione),
        url: String(row.url ?? '').trim(),
        source_id: text(row.source_id),
        snippet: text(row.snippet),
      }
    }),
    sources: list(item.sources).map((src) => {
      const row = record(src)
      return {
        id: text(row.id),
        source_type: text(row.source_type),
        title: text(row.title),
        url: String(row.url ?? '').trim(),
        authority: text(row.authority),
        trust_class: text(row.trust_class),
        copyright_policy: text(row.copyright_policy),
        excerpt: text(row.excerpt),
        origin: text(row.origin),
      }
    }),
    generated_at: text(item.generated_at),
  }
}

function normaliseSummary(input: unknown): PceCardSummary {
  const item = record(input)
  return {
    id: text(item.id),
    codice: text(item.codice),
    denominazione: text(item.denominazione),
    categoria: text(item.categoria),
    status: text(item.status) || 'draft',
    confidence: text(item.confidence) || 'LOW',
    riskLevel: text(item.riskLevel),
    gaps: Number(item.gaps) || 0,
    gapsBlocking: Number(item.gapsBlocking) || 0,
    fontiUfficiali: Number(item.fontiUfficiali) || 0,
    citazioni: Number(item.citazioni) || 0,
    templateSelezionato: text(item.templateSelezionato),
    generatedAt: text(item.generatedAt),
  }
}

export async function getPceDashboard(): Promise<PceDashboard> {
  const payload = await apiJson<Record<string, unknown>>('/api/v1/ui/procedure-completion', { ok: false })
  const flags = record(payload.flags)
  const counters = record(payload.counters)
  return {
    ok: payload.ok === true,
    errore: payload.ok === true ? '' : text(payload.errore) || 'Procedure Completion non disponibile.',
    enabled: payload.enabled === true,
    flags: {
      engine: flags.engine === true,
      voiceRead: flags.voiceRead === true,
      voiceReadLocalOnly: flags.voiceReadLocalOnly !== false,
    },
    permissions: stringList(payload.permissions),
    cards: list(payload.cards).map(normaliseSummary).filter((card) => card.id),
    gaps: list(payload.gaps).map(normaliseGap),
    counters: {
      cards: Number(counters.cards) || 0,
      needsReview: Number(counters.needsReview) || 0,
      approved: Number(counters.approved) || 0,
      published: Number(counters.published) || 0,
      gapsBlocking: Number(counters.gapsBlocking) || 0,
    },
    disclaimer: text(payload.disclaimer),
  }
}

export async function postPcePreview(input: {
  codice: string
  denominazione: string
  categoria: string
  rito: string
  competenza: string
}): Promise<PcePreviewResult> {
  const payload = await apiPostJson<Record<string, unknown>>(
    '/api/v1/ui/procedure-completion/preview',
    input,
    { ok: false, errore: 'Anteprima non completata.' },
  )
  return {
    ok: payload.ok === true,
    errore: text(payload.errore),
    card: normaliseCard(payload.card),
    validation: normaliseValidation(payload.validation),
  }
}

export async function getPceCard(cardId: string): Promise<PceCardDetailPayload> {
  const payload = await apiJson<Record<string, unknown>>(
    `/api/v1/ui/procedure-completion/cards/${encodeURIComponent(cardId)}`,
    { ok: false },
  )
  return {
    ok: payload.ok === true,
    errore: payload.ok === true ? '' : text(payload.errore) || 'Scheda non disponibile.',
    card: normaliseCard(payload.card),
    validation: normaliseValidation(payload.validation),
    draftBanner: text(payload.draftBanner),
  }
}

async function postCardAction(cardId: string, action: string, body: Record<string, unknown> = {}): Promise<PcePreviewResult> {
  const payload = await apiPostJson<Record<string, unknown>>(
    `/api/v1/ui/procedure-completion/cards/${encodeURIComponent(cardId)}/${action}`,
    body,
    { ok: false, errore: 'Operazione non completata.' },
  )
  return {
    ok: payload.ok === true,
    errore: text(payload.errore),
    card: normaliseCard(payload.card),
    validation: normaliseValidation(payload.validation),
  }
}

export function postPceSubmitReview(cardId: string, reason: string): Promise<PcePreviewResult> {
  return postCardAction(cardId, 'submit-review', { reason })
}

export function postPceApprove(cardId: string, reason: string): Promise<PcePreviewResult> {
  return postCardAction(cardId, 'approve', { reason })
}

export function postPcePublish(cardId: string): Promise<PcePreviewResult> {
  return postCardAction(cardId, 'publish')
}

export async function getPceGaps(): Promise<{ gaps: PceGap[]; errore: string }> {
  const payload = await apiJson<Record<string, unknown>>('/api/v1/ui/procedure-completion/gaps', { ok: false })
  return {
    gaps: list(payload.gaps).map(normaliseGap),
    errore: payload.ok === true ? '' : text(payload.errore) || 'Gap non disponibili.',
  }
}

export function confidenceLabel(confidence: string): string {
  if (confidence === 'HIGH') return 'Affidabilità documentale alta'
  if (confidence === 'MEDIUM') return 'Affidabilità documentale media'
  return 'Affidabilità documentale bassa'
}

export function statusLabel(status: string): string {
  if (status === 'published') return 'Pubblicata'
  if (status === 'approved') return 'Approvata'
  if (status === 'needs_review') return 'Da revisionare'
  return 'Bozza'
}
