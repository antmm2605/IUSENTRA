import { apiJson } from './lib/apiClient'
import { sanitizeDisplayText } from './displayText'

export type LexOpTone = 'danger' | 'warning' | 'success' | 'info' | 'neutral'

export type LexOpFascicolo = {
  id: string
  title: string
  numero: string
  tribunale: string
  missing: string
  nextActions: string[]
  warnings: string[]
}

export type LexOpUdienza = {
  id: string
  title: string
  cliente: string
  udienza: string
  timeline: string
  acquisiti: number
  mancanti: number
  criticalPoints: string[]
}

export type LexOpTelematico = {
  serviceLabel: string
  officeName: string
  practiceTitle: string
  status: string
  openTasks: number
}

export type LexOpAzione = { title: string; description: string; tone: LexOpTone }

export type LexOpScadenza = { titolo: string; data: string }

export type LexOperativoData = {
  ok: boolean
  error: string
  fascicolo: { label: string; summary: string; cards: LexOpFascicolo[] }
  udienza: { label: string; summary: string; metrics: { label: string; value: string }[]; cases: LexOpUdienza[] }
  telematico: { label: string; summary: string; warnings: number; cases: LexOpTelematico[] }
  controlTower: { pendingOutcomes: number; importsIncomplete: number; blocked: number }
  operativo: { label: string; summary: string; actions: LexOpAzione[]; urgentDeadlines: LexOpScadenza[] }
}

export const emptyLexOperativo: LexOperativoData = {
  ok: false,
  error: '',
  fascicolo: { label: 'Lex Fascicolo', summary: '', cards: [] },
  udienza: { label: 'Lex Udienza', summary: '', metrics: [], cases: [] },
  telematico: { label: 'Lex Telematico', summary: '', warnings: 0, cases: [] },
  controlTower: { pendingOutcomes: 0, importsIncomplete: 0, blocked: 0 },
  operativo: { label: 'Lex Operativo', summary: '', actions: [], urgentDeadlines: [] },
}

type Raw = Record<string, unknown>

function obj(value: unknown): Raw {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Raw) : {}
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function text(value: unknown, fallback = ''): string {
  if (value === null || value === undefined) return fallback
  const clean = sanitizeDisplayText(String(value)).trim()
  return clean || fallback
}

function num(value: unknown): number {
  const parsed = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function texts(value: unknown): string[] {
  return list(value).map((item) => text(item)).filter(Boolean)
}

function tone(value: unknown): LexOpTone {
  const raw = text(value).toLowerCase()
  if (raw === 'danger' || raw === 'warning' || raw === 'success' || raw === 'info') return raw
  return 'neutral'
}

export function normaliseLexOperativo(payload: unknown): LexOperativoData {
  const data = obj(payload)
  const fascicolo = obj(data.fascicolo)
  const udienza = obj(data.udienza)
  const telematico = obj(data.telematico)
  const tower = obj(obj(data.control_tower).summary)
  const operativo = obj(data.operativo)
  return {
    ok: data.ok !== false,
    error: text(data.errore),
    fascicolo: {
      label: text(fascicolo.label, emptyLexOperativo.fascicolo.label),
      summary: text(fascicolo.summary),
      cards: list(fascicolo.cards).map((raw) => {
        const item = obj(raw)
        return {
          id: text(item.id),
          title: text(item.title, 'Fascicolo'),
          numero: text(item.numero),
          tribunale: text(item.tribunale),
          missing: text(item.missing),
          nextActions: texts(item.next_actions),
          warnings: texts(item.warnings),
        }
      }),
    },
    udienza: {
      label: text(udienza.label, emptyLexOperativo.udienza.label),
      summary: text(udienza.summary),
      metrics: list(udienza.metrics).map((raw) => {
        const item = obj(raw)
        return { label: text(item.label), value: text(item.value, '0') }
      }),
      cases: list(udienza.cases).map((raw) => {
        const item = obj(raw)
        const documenti = obj(item.documenti)
        return {
          id: text(item.id),
          title: text(item.title, 'Udienza'),
          cliente: text(item.cliente),
          udienza: text(item.udienza),
          timeline: text(item.timeline),
          acquisiti: num(documenti.acquisiti),
          mancanti: num(documenti.mancanti),
          criticalPoints: texts(item.critical_points),
        }
      }),
    },
    telematico: {
      label: text(telematico.label, emptyLexOperativo.telematico.label),
      summary: text(telematico.summary),
      warnings: num(obj(telematico.summary_counts).warnings),
      cases: list(telematico.warning_cases).map((raw) => {
        const item = obj(raw)
        return {
          serviceLabel: text(item.service_label, 'Servizio telematico'),
          officeName: text(item.office_name),
          practiceTitle: text(item.practice_title),
          status: ({manual_review_required: 'Revisione manuale richiesta', draft: 'Bozza', opened_official_portal: 'Portale ufficiale aperto'} as Record<string, string>)[text(item.internal_status)] || text(item.internal_status).replace(/_/g, ' '),
          openTasks: num(item.open_tasks_count),
        }
      }),
    },
    controlTower: {
      pendingOutcomes: num(tower.pending_outcomes),
      importsIncomplete: num(tower.imports_incomplete),
      blocked: num(tower.blocked),
    },
    operativo: {
      label: text(operativo.label, emptyLexOperativo.operativo.label),
      summary: text(operativo.summary),
      actions: list(operativo.actions).map((raw) => {
        const item = obj(raw)
        return { title: text(item.title, 'Azione'), description: text(item.description), tone: tone(item.tone) }
      }),
      urgentDeadlines: list(operativo.urgent_deadlines).map((raw) => {
        const item = obj(raw)
        return { titolo: text(item.titolo, 'Scadenza'), data: text(item.data_scadenza) }
      }),
    },
  }
}

export async function getLexOperativo(giorni: number): Promise<LexOperativoData> {
  const payload = await apiJson<unknown>(`/api/lex-operativo?giorni=${encodeURIComponent(String(giorni))}`, { ok: false })
  return normaliseLexOperativo(payload)
}

export function dataItaliana(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
  return match ? `${match[3]}/${match[2]}/${match[1]}` : value
}
