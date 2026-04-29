import type { Tone } from './data'

export type FascicoloTipo = 'tutti' | 'civile' | 'penale' | 'amministrativo' | 'tributario' | 'stragiudiziale' | 'altro'
export type FascicoloStato = 'tutti' | 'aperto' | 'in_corso' | 'definito' | 'da_archiviare' | 'archiviato' | 'sospeso'

export type FascicoloRow = {
  id: string
  ref: string
  internalRef: string
  title: string
  subtitle: string
  type: Exclude<FascicoloTipo, 'tutti'>
  client: string
  court: string
  rg: string
  nextDeadline: string
  nextDeadlineIso: string
  status: Exclude<FascicoloStato, 'tutti'>
  documents: number
  unreadCommunications: number
  alerts: number
  href: string
  editHref: string
  tone: Tone
}

export type FascicoliSummary = {
  total: number
  active: number
  inProgress: number
  toArchive: number
  archived: number
  deadlines30: number
  documentsToClassify: number
  unreadCommunications: number
}

export type FascicoliPageData = {
  source: string
  generatedAt: string
  contracts: { mock_fallback: boolean; read_only: boolean }
  summary: FascicoliSummary
  items: FascicoloRow[]
  facets: {
    types: Array<{ value: FascicoloTipo; label: string; count: number }>
    statuses: Array<{ value: FascicoloStato; label: string; count: number }>
  }
}

const emptySummary: FascicoliSummary = {
  total: 0,
  active: 0,
  inProgress: 0,
  toArchive: 0,
  archived: 0,
  deadlines30: 0,
  documentsToClassify: 0,
  unreadCommunications: 0,
}

export const emptyFascicoliPage: FascicoliPageData = {
  source: 'vuoto',
  generatedAt: '',
  contracts: { mock_fallback: false, read_only: true },
  summary: emptySummary,
  items: [],
  facets: {
    types: [{ value: 'tutti', label: 'Tutti i tipi', count: 0 }],
    statuses: [{ value: 'tutti', label: 'Tutti gli stati', count: 0 }],
  },
}

const typeLabels: Record<Exclude<FascicoloTipo, 'tutti'>, string> = {
  civile: 'Civile',
  penale: 'Penale',
  amministrativo: 'Amministrativo',
  tributario: 'Tributario',
  stragiudiziale: 'Stragiudiziale',
  altro: 'Altro',
}

const statusLabels: Record<Exclude<FascicoloStato, 'tutti'>, string> = {
  aperto: 'Aperto',
  in_corso: 'In corso',
  definito: 'Definito',
  da_archiviare: 'Da archiviare',
  archiviato: 'Archiviato',
  sospeso: 'Sospeso',
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function text(value: unknown, fallback = ''): string {
  return String(value ?? fallback).trim()
}

function number(value: unknown): number {
  const parsed = Number(value ?? 0)
  return Number.isFinite(parsed) ? parsed : 0
}

function normaliseType(value: unknown): Exclude<FascicoloTipo, 'tutti'> {
  const raw = text(value).toLowerCase()
  if (raw.includes('civ')) return 'civile'
  if (raw.includes('pen') || raw.includes('rgnr')) return 'penale'
  if (raw.includes('amm') || raw.includes('tar') || raw.includes('consiglio')) return 'amministrativo'
  if (raw.includes('trib') || raw.includes('sigit') || raw.includes('ptt')) return 'tributario'
  if (raw.includes('stragiud') || raw.includes('mediazione') || raw.includes('negoziazione')) return 'stragiudiziale'
  return 'altro'
}

function normaliseStatus(value: unknown): Exclude<FascicoloStato, 'tutti'> {
  const raw = text(value).toLowerCase().replace(/\s+/g, '_')
  if (raw.includes('archivi')) return 'archiviato'
  if (raw.includes('defin') || raw.includes('chius')) return 'definito'
  if (raw.includes('sosp')) return 'sospeso'
  if (raw.includes('corso')) return 'in_corso'
  if (raw.includes('da_arch') || raw.includes('archiviare')) return 'da_archiviare'
  return 'aperto'
}

function statusTone(status: FascicoloRow['status']): Tone {
  if (status === 'definito') return 'info'
  if (status === 'in_corso') return 'success'
  if (status === 'da_archiviare') return 'warning'
  if (status === 'archiviato') return 'neutral'
  if (status === 'sospeso') return 'orange'
  return 'primary'
}

function normalizeItem(value: unknown, index: number): FascicoloRow {
  const item = isRecord(value) ? value : {}
  const id = text(item.id, `fascicolo-${index}`)
  const type = normaliseType(item.type ?? item.tipo)
  const status = normaliseStatus(item.status ?? item.stato)
  const rg = text(item.rg ?? item.numero_rg ?? item.n_causa, 'n.d.')
  const title = text(item.title ?? item.titolo ?? item.oggetto, 'Fascicolo senza titolo')
  const client = text(item.client ?? item.cliente ?? item.nome_cliente, 'Cliente non collegato')
  return {
    id,
    ref: text(item.ref ?? item.riferimento ?? item.numero, rg || id),
    internalRef: text(item.internalRef ?? item.internal_ref ?? item.interno, 'n.d.'),
    title,
    subtitle: text(item.subtitle ?? item.sottotitolo ?? item.descrizione, ''),
    type,
    client,
    court: text(item.court ?? item.tribunale ?? item.ufficio, 'Ufficio non impostato'),
    rg,
    nextDeadline: text(item.nextDeadline ?? item.prossima_scadenza_label ?? item.next_deadline, 'n.d.'),
    nextDeadlineIso: text(item.nextDeadlineIso ?? item.prossima_scadenza ?? item.next_deadline_iso, ''),
    status,
    documents: number(item.documents ?? item.docs ?? item.documenti),
    unreadCommunications: number(item.unreadCommunications ?? item.comunicazioni_non_lette ?? item.unread_communications),
    alerts: number(item.alerts ?? item.alert ?? item.criticita),
    href: text(item.href, `/fascicoli/${encodeURIComponent(id)}`),
    editHref: text(item.editHref ?? item.edit_href, `/fascicoli/${encodeURIComponent(id)}/modifica`),
    tone: statusTone(status),
  }
}

function buildFacets(items: FascicoloRow[]): FascicoliPageData['facets'] {
  const typeCounts = new Map<FascicoloTipo, number>([['tutti', items.length]])
  const statusCounts = new Map<FascicoloStato, number>([['tutti', items.length]])
  items.forEach((item) => {
    typeCounts.set(item.type, (typeCounts.get(item.type) || 0) + 1)
    statusCounts.set(item.status, (statusCounts.get(item.status) || 0) + 1)
  })
  return {
    types: [
      { value: 'tutti', label: 'Tutti i tipi', count: typeCounts.get('tutti') || 0 },
      ...Object.entries(typeLabels).map(([value, label]) => ({ value: value as FascicoloTipo, label, count: typeCounts.get(value as FascicoloTipo) || 0 })),
    ],
    statuses: [
      { value: 'tutti', label: 'Tutti gli stati', count: statusCounts.get('tutti') || 0 },
      ...Object.entries(statusLabels).map(([value, label]) => ({ value: value as FascicoloStato, label, count: statusCounts.get(value as FascicoloStato) || 0 })),
    ],
  }
}

function buildSummary(items: FascicoloRow[], payloadSummary?: unknown): FascicoliSummary {
  if (isRecord(payloadSummary)) {
    return {
      total: number(payloadSummary.total ?? items.length),
      active: number(payloadSummary.active ?? payloadSummary.attivi),
      inProgress: number(payloadSummary.inProgress ?? payloadSummary.in_corso),
      toArchive: number(payloadSummary.toArchive ?? payloadSummary.da_archiviare),
      archived: number(payloadSummary.archived ?? payloadSummary.archiviati),
      deadlines30: number(payloadSummary.deadlines30 ?? payloadSummary.scadenze_30),
      documentsToClassify: number(payloadSummary.documentsToClassify ?? payloadSummary.documenti_da_classificare),
      unreadCommunications: number(payloadSummary.unreadCommunications ?? payloadSummary.comunicazioni_non_lette),
    }
  }
  return {
    total: items.length,
    active: items.filter((item) => item.status !== 'archiviato').length,
    inProgress: items.filter((item) => item.status === 'in_corso').length,
    toArchive: items.filter((item) => item.status === 'da_archiviare' || item.status === 'definito').length,
    archived: items.filter((item) => item.status === 'archiviato').length,
    deadlines30: items.filter((item) => item.nextDeadlineIso || item.nextDeadline !== 'n.d.').length,
    documentsToClassify: items.reduce((total, item) => total + Math.max(0, item.alerts), 0),
    unreadCommunications: items.reduce((total, item) => total + item.unreadCommunications, 0),
  }
}

function normalisePayload(payload: unknown): FascicoliPageData {
  if (!isRecord(payload)) return emptyFascicoliPage
  const rawItems = Array.isArray(payload.items) ? payload.items : Array.isArray(payload.fascicoli) ? payload.fascicoli : []
  const items = rawItems.map(normalizeItem)
  return {
    source: text(payload.source, 'repository_reali'),
    generatedAt: text(payload.generatedAt ?? payload.generated_at, ''),
    contracts: isRecord(payload.contracts)
      ? {
        mock_fallback: Boolean(payload.contracts.mock_fallback),
        read_only: payload.contracts.read_only !== false,
      }
      : { mock_fallback: false, read_only: true },
    summary: buildSummary(items, payload.summary),
    items,
    facets: isRecord(payload.facets) && Array.isArray(payload.facets.types) && Array.isArray(payload.facets.statuses)
      ? payload.facets as FascicoliPageData['facets']
      : buildFacets(items),
  }
}

export function formatFascicoloType(value: FascicoloRow['type']): string {
  return typeLabels[value] || 'Altro'
}

export function formatFascicoloStatus(value: FascicoloRow['status']): string {
  return statusLabels[value] || 'Aperto'
}

export async function getFascicoliPage(): Promise<FascicoliPageData> {
  try {
    const response = await fetch('/api/v1/ui/fascicoli', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
    if (!response.ok) return emptyFascicoliPage
    return normalisePayload(await response.json())
  } catch {
    return emptyFascicoliPage
  }
}
