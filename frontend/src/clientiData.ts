import type { Tone } from './data'

export type ClienteTipo = 'tutti' | 'pf' | 'pg'
export type ClienteStato = 'tutti' | 'attivo' | 'potenziale' | 'archiviato' | 'inattivo'

export type ClienteRow = {
  id: string
  name: string
  subtitle: string
  type: Exclude<ClienteTipo, 'tutti'>
  fiscalId: string
  email: string
  phone: string
  pec: string
  attorney: string
  matters: number
  activeMatters: number
  status: Exclude<ClienteStato, 'tutti'>
  missingFields: string[]
  privacyOk: boolean
  documentExpired: boolean
  tags: string[]
  lastUpdated: string
  href: string
  editHref: string
  folderHref: string
  tone: Tone
}

export type ClientiSummary = {
  total: number
  active: number
  potential: number
  archived: number
  withMatters: number
  incomplete: number
  withoutContacts: number
  privacyMissing: number
  documentsExpired: number
}

export type ClientiPageData = {
  source: string
  generatedAt: string
  contracts: { mock_fallback: boolean; read_only: boolean }
  summary: ClientiSummary
  items: ClienteRow[]
  facets: {
    types: Array<{ value: ClienteTipo; label: string; count: number }>
    statuses: Array<{ value: ClienteStato; label: string; count: number }>
  }
}

const emptySummary: ClientiSummary = {
  total: 0,
  active: 0,
  potential: 0,
  archived: 0,
  withMatters: 0,
  incomplete: 0,
  withoutContacts: 0,
  privacyMissing: 0,
  documentsExpired: 0,
}

export const emptyClientiPage: ClientiPageData = {
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

const typeLabels: Record<Exclude<ClienteTipo, 'tutti'>, string> = {
  pf: 'Persona fisica',
  pg: 'Persona giuridica',
}

const statusLabels: Record<Exclude<ClienteStato, 'tutti'>, string> = {
  attivo: 'Attivo',
  potenziale: 'Potenziale',
  archiviato: 'Archiviato',
  inattivo: 'Inattivo',
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

function bool(value: unknown): boolean {
  return value === true || value === 'true' || value === 1 || value === '1'
}

function arrayText(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => text(item)).filter(Boolean)
}

function normaliseType(value: unknown): Exclude<ClienteTipo, 'tutti'> {
  const raw = text(value).toLowerCase()
  if (raw.includes('giurid') || raw.includes('societ') || raw === 'pg' || raw.includes('persona_giuridica')) return 'pg'
  return 'pf'
}

function normaliseStatus(value: unknown): Exclude<ClienteStato, 'tutti'> {
  const raw = text(value).toLowerCase().replace(/\s+/g, '_')
  if (raw.includes('archiv')) return 'archiviato'
  if (raw.includes('potenzial')) return 'potenziale'
  if (raw.includes('inatt')) return 'inattivo'
  return 'attivo'
}

function statusTone(status: ClienteRow['status']): Tone {
  if (status === 'attivo') return 'success'
  if (status === 'potenziale') return 'warning'
  if (status === 'archiviato') return 'neutral'
  return 'orange'
}

function normalizeItem(value: unknown, index: number): ClienteRow {
  const item = isRecord(value) ? value : {}
  const contacts = isRecord(item.contacts) ? item.contacts : {}
  const id = text(item.id, `cliente-${index}`)
  const status = normaliseStatus(item.status ?? item.stato)
  const type = normaliseType(item.type ?? item.tipo)
  const missingFields = arrayText(item.missingFields ?? item.missing_fields ?? item.campi_mancanti)
  return {
    id,
    name: text(item.name ?? item.nome_completo ?? item.cliente ?? item.ragione_sociale, 'Cliente senza nome'),
    subtitle: text(item.subtitle ?? item.descrizione ?? item.note_brevi),
    type,
    fiscalId: text(item.fiscalId ?? item.fiscal_id ?? item.identificativo_fiscale ?? item.codice_fiscale ?? item.partita_iva, '-'),
    email: text(item.email ?? contacts.email),
    phone: text(item.phone ?? item.telefono ?? item.cellulare ?? contacts.phone),
    pec: text(item.pec ?? contacts.pec),
    attorney: text(item.attorney ?? item.avvocato_referente ?? item.avv_referente, '-'),
    matters: number(item.matters ?? item.pratiche ?? item.procedimenti),
    activeMatters: number(item.activeMatters ?? item.active_matters ?? item.procedimenti_attivi),
    status,
    missingFields,
    privacyOk: bool(item.privacyOk ?? item.privacy_ok ?? item.consenso_trattamento),
    documentExpired: bool(item.documentExpired ?? item.document_expired ?? item.documento_scaduto),
    tags: arrayText(item.tags ?? item.tag),
    lastUpdated: text(item.lastUpdated ?? item.last_updated ?? item.modificato_il),
    href: text(item.href, `/clienti/${encodeURIComponent(id)}`),
    editHref: text(item.editHref ?? item.edit_href, `/clienti/${encodeURIComponent(id)}/modifica`),
    folderHref: text(item.folderHref ?? item.folder_href, `/clienti/${encodeURIComponent(id)}/cartella`),
    tone: statusTone(status),
  }
}

function buildFacets(items: ClienteRow[]): ClientiPageData['facets'] {
  const typeCounts = new Map<ClienteTipo, number>([['tutti', items.length]])
  const statusCounts = new Map<ClienteStato, number>([['tutti', items.length]])
  items.forEach((item) => {
    typeCounts.set(item.type, (typeCounts.get(item.type) || 0) + 1)
    statusCounts.set(item.status, (statusCounts.get(item.status) || 0) + 1)
  })
  return {
    types: [
      { value: 'tutti', label: 'Tutti i tipi', count: typeCounts.get('tutti') || 0 },
      ...Object.entries(typeLabels).map(([value, label]) => ({ value: value as ClienteTipo, label, count: typeCounts.get(value as ClienteTipo) || 0 })),
    ],
    statuses: [
      { value: 'tutti', label: 'Tutti gli stati', count: statusCounts.get('tutti') || 0 },
      ...Object.entries(statusLabels).map(([value, label]) => ({ value: value as ClienteStato, label, count: statusCounts.get(value as ClienteStato) || 0 })),
    ],
  }
}

function buildSummary(items: ClienteRow[], payloadSummary?: unknown): ClientiSummary {
  if (isRecord(payloadSummary)) {
    return {
      total: number(payloadSummary.total ?? items.length),
      active: number(payloadSummary.active ?? payloadSummary.attivi),
      potential: number(payloadSummary.potential ?? payloadSummary.potenziali),
      archived: number(payloadSummary.archived ?? payloadSummary.archiviati),
      withMatters: number(payloadSummary.withMatters ?? payloadSummary.con_procedimenti),
      incomplete: number(payloadSummary.incomplete ?? payloadSummary.da_completare),
      withoutContacts: number(payloadSummary.withoutContacts ?? payloadSummary.senza_recapiti),
      privacyMissing: number(payloadSummary.privacyMissing ?? payloadSummary.privacy_mancante),
      documentsExpired: number(payloadSummary.documentsExpired ?? payloadSummary.documenti_scaduti),
    }
  }
  return {
    total: items.length,
    active: items.filter((item) => item.status === 'attivo').length,
    potential: items.filter((item) => item.status === 'potenziale').length,
    archived: items.filter((item) => item.status === 'archiviato').length,
    withMatters: items.filter((item) => item.matters > 0 || item.activeMatters > 0).length,
    incomplete: items.filter((item) => item.missingFields.length > 0).length,
    withoutContacts: items.filter((item) => !item.email && !item.phone && !item.pec).length,
    privacyMissing: items.filter((item) => !item.privacyOk).length,
    documentsExpired: items.filter((item) => item.documentExpired).length,
  }
}

function normalisePayload(payload: unknown): ClientiPageData {
  if (!isRecord(payload)) return emptyClientiPage
  const rawItems = Array.isArray(payload.items) ? payload.items : Array.isArray(payload.clienti) ? payload.clienti : []
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
      ? payload.facets as ClientiPageData['facets']
      : buildFacets(items),
  }
}

export function formatClienteType(value: ClienteRow['type']): string {
  return typeLabels[value] || 'Persona fisica'
}

export function formatClienteStatus(value: ClienteRow['status']): string {
  return statusLabels[value] || 'Attivo'
}

export async function getClientiPage(): Promise<ClientiPageData> {
  try {
    const response = await fetch('/api/v1/ui/clienti', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
    if (!response.ok) return emptyClientiPage
    return normalisePayload(await response.json())
  } catch {
    return emptyClientiPage
  }
}
