import type { Tone } from './data'

export type SoggettoTipo = 'tutti' | 'PERSONA_FISICA' | 'PERSONA_GIURIDICA' | 'PUBBLICA_AMMINISTRAZIONE' | 'ENTE' | 'CONDOMINIO' | 'ASSOCIAZIONE' | 'PROFESSIONISTA'

export type SoggettoRow = {
  id: string
  name: string
  type: Exclude<SoggettoTipo, 'tutti'>
  typeLabel: string
  role: string
  identifier: string
  email: string
  phone: string
  pec: string
  city: string
  province: string
  clientId: string
  clientName: string
  matters: number
  isLegal: boolean
  missingFields: string[]
  href: string
  editHref: string
  tone: Tone
}

export type SoggettiPageData = {
  source: string
  generatedAt: string
  contracts: { mock_fallback: boolean; read_only: boolean }
  summary: {
    total: number
    physical: number
    legal: number
    professionals: number
    linkedClients: number
    withMatters: number
    incomplete: number
    withoutContacts: number
  }
  items: SoggettoRow[]
  facets: {
    types: Array<{ value: SoggettoTipo; label: string; count: number }>
    roles: Array<{ value: string; label: string; count: number }>
  }
}

const emptySummary = {
  total: 0,
  physical: 0,
  legal: 0,
  professionals: 0,
  linkedClients: 0,
  withMatters: 0,
  incomplete: 0,
  withoutContacts: 0,
}

export const emptySoggettiPage: SoggettiPageData = {
  source: 'vuoto',
  generatedAt: '',
  contracts: { mock_fallback: false, read_only: true },
  summary: emptySummary,
  items: [],
  facets: {
    types: [{ value: 'tutti', label: 'Tutti i tipi', count: 0 }],
    roles: [{ value: 'tutti', label: 'Tutti i ruoli', count: 0 }],
  },
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

function arrayText(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => text(item)).filter(Boolean)
}

function toneFrom(type: string): Tone {
  if (type === 'PERSONA_GIURIDICA') return 'purple'
  if (type === 'PUBBLICA_AMMINISTRAZIONE') return 'info'
  if (type === 'CONDOMINIO') return 'orange'
  if (type === 'ASSOCIAZIONE') return 'success'
  if (type === 'PERSONA_FISICA' || type === 'PROFESSIONISTA') return 'primary'
  return 'neutral'
}

function normalizeType(value: unknown): Exclude<SoggettoTipo, 'tutti'> {
  const raw = text(value, 'PERSONA_FISICA').toUpperCase()
  const allowed = new Set(['PERSONA_FISICA', 'PERSONA_GIURIDICA', 'PUBBLICA_AMMINISTRAZIONE', 'ENTE', 'CONDOMINIO', 'ASSOCIAZIONE', 'PROFESSIONISTA'])
  return (allowed.has(raw) ? raw : 'PERSONA_FISICA') as Exclude<SoggettoTipo, 'tutti'>
}

function normalizeItem(value: unknown, index: number): SoggettoRow {
  const item = isRecord(value) ? value : {}
  const id = text(item.id, `soggetto-${index}`)
  const type = normalizeType(item.type ?? item.tipo)
  return {
    id,
    name: text(item.name ?? item.nome_completo, 'Soggetto senza nome'),
    type,
    typeLabel: text(item.typeLabel ?? item.type_label, type.replaceAll('_', ' ')),
    role: text(item.role ?? item.qualifica, 'ALTRO'),
    identifier: text(item.identifier ?? item.identificativo ?? item.codice_fiscale ?? item.partita_iva, '-'),
    email: text(item.email),
    phone: text(item.phone ?? item.telefono ?? item.cellulare),
    pec: text(item.pec),
    city: text(item.city ?? item.comune),
    province: text(item.province ?? item.provincia),
    clientId: text(item.clientId ?? item.client_id ?? item.id_cliente),
    clientName: text(item.clientName ?? item.client_name ?? item.cliente),
    matters: number(item.matters ?? item.fascicoli),
    isLegal: Boolean(item.isLegal ?? item.is_legal),
    missingFields: arrayText(item.missingFields ?? item.missing_fields),
    href: text(item.href, `/soggetti/${encodeURIComponent(id)}`),
    editHref: text(item.editHref ?? item.edit_href, `/soggetti/${encodeURIComponent(id)}/modifica`),
    tone: (text(item.tone) as Tone) || toneFrom(type),
  }
}

function normalizePayload(payload: unknown): SoggettiPageData {
  if (!isRecord(payload)) return emptySoggettiPage
  const items = (Array.isArray(payload.items) ? payload.items : []).map(normalizeItem)
  const summary = isRecord(payload.summary) ? payload.summary : {}
  return {
    source: text(payload.source, 'repository_reali'),
    generatedAt: text(payload.generatedAt ?? payload.generated_at),
    contracts: isRecord(payload.contracts)
      ? {
        mock_fallback: Boolean(payload.contracts.mock_fallback),
        read_only: payload.contracts.read_only !== false,
      }
      : emptySoggettiPage.contracts,
    summary: {
      total: number(summary.total ?? items.length),
      physical: number(summary.physical),
      legal: number(summary.legal),
      professionals: number(summary.professionals),
      linkedClients: number(summary.linkedClients ?? summary.linked_clients),
      withMatters: number(summary.withMatters ?? summary.with_matters),
      incomplete: number(summary.incomplete),
      withoutContacts: number(summary.withoutContacts ?? summary.without_contacts),
    },
    items,
    facets: isRecord(payload.facets) && Array.isArray(payload.facets.types) && Array.isArray(payload.facets.roles)
      ? payload.facets as SoggettiPageData['facets']
      : emptySoggettiPage.facets,
  }
}

export async function getSoggettiPage(): Promise<SoggettiPageData> {
  try {
    const response = await fetch('/api/v1/ui/soggetti', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
    if (!response.ok) return emptySoggettiPage
    return normalizePayload(await response.json())
  } catch {
    return emptySoggettiPage
  }
}
