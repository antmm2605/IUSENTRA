import type { Tone } from './data'

export type RegistryOption = {
  value: string
  label: string
  subtitle?: string
  tone?: Tone
  count?: number
}

export type ClientOption = {
  id: string
  label: string
  taxCode?: string
  email?: string
  type?: string
}

export type ClientiNuovoData = {
  source: string
  generatedAt: string
  contracts: {
    mock_fallback: boolean
    read_only: boolean
    writes: string
  }
  stats: {
    totalClients: number
    physicalClients: number
    legalClients: number
    activeClients: number
    potentialClients: number
    missingRegistry: number
    expiredDocuments: number
    totalSubjects: number
    subjectsWithoutClient: number
  }
  options: {
    clientTypes: RegistryOption[]
    clientStatuses: RegistryOption[]
    documentTypes: RegistryOption[]
    cieGenerations: RegistryOption[]
    subjectTypes: RegistryOption[]
    subjectRoles: RegistryOption[]
    legalForms: RegistryOption[]
    qualificationHints: RegistryOption[]
  }
  clientOptions: ClientOption[]
  actions: {
    newClient: string
    newSubject: string
    clientsList: string
    subjectsList: string
    legacyClientForm: string
    legacySubjectForm: string
  }
  query: {
    tab: string
    nextUrl: string
    idCliente: string
  }
  insights: string[]
}

const clientTypes: RegistryOption[] = [
  { value: 'PERSONA_FISICA', label: 'Persona fisica', subtitle: 'Privato, professionista o assistito', tone: 'primary' },
  { value: 'PERSONA_GIURIDICA', label: 'Persona giuridica', subtitle: 'Societa, ente o organizzazione', tone: 'purple' },
]

const clientStatuses: RegistryOption[] = [
  { value: 'ATTIVO', label: 'Attivo', tone: 'success' },
  { value: 'POTENZIALE', label: 'Potenziale', tone: 'warning' },
  { value: 'INATTIVO', label: 'Inattivo', tone: 'orange' },
  { value: 'ARCHIVIATO', label: 'Archiviato', tone: 'neutral' },
]

const documentTypes: RegistryOption[] = [
  { value: 'CARTA_IDENTITA', label: "Carta d'identita" },
  { value: 'PASSAPORTO', label: 'Passaporto' },
  { value: 'PATENTE', label: 'Patente' },
  { value: 'PERMESSO_SOGGIORNO', label: 'Permesso di soggiorno' },
  { value: 'ALTRO', label: 'Altro' },
]

const cieGenerations: RegistryOption[] = [
  { value: 'elettronica', label: 'Elettronica dal 2016 con MRZ', tone: 'primary' },
  { value: 'plastificata', label: 'Plastificata 2000-2016', tone: 'neutral' },
  { value: 'cartacea', label: 'Cartacea pre-2000', tone: 'neutral' },
]

const subjectTypes: RegistryOption[] = [
  { value: 'PERSONA_FISICA', label: 'Persona fisica', tone: 'primary' },
  { value: 'PERSONA_GIURIDICA', label: 'Persona giuridica', tone: 'purple' },
  { value: 'PUBBLICA_AMMINISTRAZIONE', label: 'Pubblica Amministrazione', tone: 'info' },
  { value: 'ENTE', label: 'Ente', tone: 'neutral' },
  { value: 'CONDOMINIO', label: 'Condominio', tone: 'orange' },
  { value: 'ASSOCIAZIONE', label: 'Associazione', tone: 'success' },
  { value: 'PROFESSIONISTA', label: 'Professionista', tone: 'primary' },
]

const subjectRoles: RegistryOption[] = [
  { value: 'ASSISTITO', label: 'Assistito / co-cliente', tone: 'success' },
  { value: 'CONTROPARTE', label: 'Controparte', tone: 'danger' },
  { value: 'DIFENSORE_CONTROPARTE', label: 'Difensore controparte', tone: 'danger' },
  { value: 'TESTIMONE', label: 'Testimone', tone: 'warning' },
  { value: 'PERITO_CTP', label: 'Perito CTP', tone: 'info' },
  { value: 'PERITO_CTU', label: 'Perito CTU', tone: 'info' },
  { value: 'CORRISPONDENTE', label: 'Corrispondente / domiciliatario', tone: 'primary' },
  { value: 'GIUDICE', label: 'Giudice', tone: 'neutral' },
  { value: 'PM', label: 'Pubblico Ministero', tone: 'neutral' },
  { value: 'NOTAIO', label: 'Notaio', tone: 'purple' },
  { value: 'MEDIATORE', label: 'Mediatore', tone: 'success' },
  { value: 'CURATORE', label: 'Curatore', tone: 'neutral' },
  { value: 'GARANTE', label: 'Garante', tone: 'warning' },
  { value: 'INTERVENIENTE', label: 'Interveniente', tone: 'info' },
  { value: 'CREDITORE', label: 'Creditore', tone: 'primary' },
  { value: 'DEBITORE', label: 'Debitore', tone: 'danger' },
  { value: 'ALTRO', label: 'Altro', tone: 'neutral' },
]

const legalForms: RegistryOption[] = [
  { value: '', label: '-' },
  { value: 'Srl', label: 'Srl' },
  { value: 'SpA', label: 'SpA' },
  { value: 'Sas', label: 'Sas' },
  { value: 'Snc', label: 'Snc' },
  { value: 'Ss', label: 'Ss' },
  { value: 'Impresa individuale', label: 'Impresa individuale' },
  { value: 'Cooperativa', label: 'Cooperativa' },
  { value: 'Associazione', label: 'Associazione' },
  { value: 'Fondazione', label: 'Fondazione' },
  { value: 'Ente pubblico', label: 'Ente pubblico' },
  { value: 'Altro', label: 'Altro' },
]

const qualificationHints: RegistryOption[] = [
  'Avvocato',
  'Procuratore',
  'Notaio',
  'Geometra',
  'Ingegnere',
  'Architetto',
  'Medico',
  'Perito industriale',
  'Commercialista',
  'Consulente del lavoro',
  'Mediatore',
  'Curatore fallimentare',
  'Liquidatore',
  'Magistrato',
  'Pubblico Ministero',
].map((item) => ({ value: item, label: item }))

export const emptyClientiNuovoData: ClientiNuovoData = {
  source: 'vuoto',
  generatedAt: '',
  contracts: { mock_fallback: false, read_only: false, writes: 'legacy_routes' },
  stats: {
    totalClients: 0,
    physicalClients: 0,
    legalClients: 0,
    activeClients: 0,
    potentialClients: 0,
    missingRegistry: 0,
    expiredDocuments: 0,
    totalSubjects: 0,
    subjectsWithoutClient: 0,
  },
  options: {
    clientTypes,
    clientStatuses,
    documentTypes,
    cieGenerations,
    subjectTypes,
    subjectRoles,
    legalForms,
    qualificationHints,
  },
  clientOptions: [],
  actions: {
    newClient: '/clienti/nuovo',
    newSubject: '/soggetti/nuovo',
    clientsList: '/clienti',
    subjectsList: '/soggetti',
    legacyClientForm: '/clienti/nuovo',
    legacySubjectForm: '/soggetti/nuovo',
  },
  query: { tab: '', nextUrl: '', idCliente: '' },
  insights: [
    'Verifica codice fiscale o partita IVA prima del salvataggio.',
    'Completa almeno un recapito utile per conferimento e notifiche.',
    'Il soggetto processuale usa il campo qualifica per mantenere compatibilita con la vista storica.',
  ],
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

function optionsFrom(value: unknown, fallback: RegistryOption[]): RegistryOption[] {
  if (!Array.isArray(value)) return fallback
  const rows = value.filter(isRecord).map((item) => ({
    value: text(item.value),
    label: text(item.label ?? item.value),
    subtitle: item.subtitle === undefined ? undefined : text(item.subtitle),
    tone: (text(item.tone, 'neutral') as Tone),
    count: item.count === undefined ? undefined : number(item.count),
  })).filter((item) => item.value || item.label)
  return rows.length ? rows : fallback
}

function clientOptionsFrom(value: unknown): ClientOption[] {
  if (!Array.isArray(value)) return []
  return value.filter(isRecord).map((item, index) => ({
    id: text(item.id, `cliente-${index}`),
    label: text(item.label ?? item.nome_completo ?? item.name, 'Cliente senza nome'),
    taxCode: text(item.taxCode ?? item.codice_fiscale ?? item.partita_iva),
    email: text(item.email),
    type: text(item.type ?? item.tipo),
  })).filter((item) => item.id)
}

function mergePayload(payload: unknown): ClientiNuovoData {
  if (!isRecord(payload)) return emptyClientiNuovoData
  const options = isRecord(payload.options) ? payload.options : {}
  const stats = isRecord(payload.stats) ? payload.stats : {}
  return {
    ...emptyClientiNuovoData,
    source: text(payload.source, emptyClientiNuovoData.source),
    generatedAt: text(payload.generatedAt ?? payload.generated_at),
    contracts: isRecord(payload.contracts)
      ? {
        mock_fallback: Boolean(payload.contracts.mock_fallback),
        read_only: payload.contracts.read_only === true,
        writes: text(payload.contracts.writes, emptyClientiNuovoData.contracts.writes),
      }
      : emptyClientiNuovoData.contracts,
    stats: {
      totalClients: number(stats.totalClients ?? stats.total_clients),
      physicalClients: number(stats.physicalClients ?? stats.physical_clients),
      legalClients: number(stats.legalClients ?? stats.legal_clients),
      activeClients: number(stats.activeClients ?? stats.active_clients),
      potentialClients: number(stats.potentialClients ?? stats.potential_clients),
      missingRegistry: number(stats.missingRegistry ?? stats.missing_registry),
      expiredDocuments: number(stats.expiredDocuments ?? stats.expired_documents),
      totalSubjects: number(stats.totalSubjects ?? stats.total_subjects),
      subjectsWithoutClient: number(stats.subjectsWithoutClient ?? stats.subjects_without_client),
    },
    options: {
      clientTypes: optionsFrom(options.clientTypes, emptyClientiNuovoData.options.clientTypes),
      clientStatuses: optionsFrom(options.clientStatuses, emptyClientiNuovoData.options.clientStatuses),
      documentTypes: optionsFrom(options.documentTypes, emptyClientiNuovoData.options.documentTypes),
      cieGenerations: optionsFrom(options.cieGenerations, emptyClientiNuovoData.options.cieGenerations),
      subjectTypes: optionsFrom(options.subjectTypes, emptyClientiNuovoData.options.subjectTypes),
      subjectRoles: optionsFrom(options.subjectRoles, emptyClientiNuovoData.options.subjectRoles),
      legalForms: optionsFrom(options.legalForms, emptyClientiNuovoData.options.legalForms),
      qualificationHints: optionsFrom(options.qualificationHints, emptyClientiNuovoData.options.qualificationHints),
    },
    clientOptions: clientOptionsFrom(payload.clientOptions ?? payload.client_options),
    actions: isRecord(payload.actions)
      ? {
        newClient: text(payload.actions.newClient ?? payload.actions.new_client, emptyClientiNuovoData.actions.newClient),
        newSubject: text(payload.actions.newSubject ?? payload.actions.new_subject, emptyClientiNuovoData.actions.newSubject),
        clientsList: text(payload.actions.clientsList ?? payload.actions.clients_list, emptyClientiNuovoData.actions.clientsList),
        subjectsList: text(payload.actions.subjectsList ?? payload.actions.subjects_list, emptyClientiNuovoData.actions.subjectsList),
        legacyClientForm: text(payload.actions.legacyClientForm ?? payload.actions.legacy_client_form, emptyClientiNuovoData.actions.legacyClientForm),
        legacySubjectForm: text(payload.actions.legacySubjectForm ?? payload.actions.legacy_subject_form, emptyClientiNuovoData.actions.legacySubjectForm),
      }
      : emptyClientiNuovoData.actions,
    query: isRecord(payload.query)
      ? {
        tab: text(payload.query.tab),
        nextUrl: text(payload.query.nextUrl ?? payload.query.next_url),
        idCliente: text(payload.query.idCliente ?? payload.query.id_cliente),
      }
      : emptyClientiNuovoData.query,
    insights: Array.isArray(payload.insights) ? payload.insights.map((item) => text(item)).filter(Boolean) : emptyClientiNuovoData.insights,
  }
}

export async function getClientiNuovoData(): Promise<ClientiNuovoData> {
  try {
    const search = typeof window !== 'undefined' ? window.location.search : ''
    const response = await fetch(`/api/v1/ui/clienti/nuovo${search}`, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
    if (!response.ok) return emptyClientiNuovoData
    return mergePayload(await response.json())
  } catch {
    return emptyClientiNuovoData
  }
}
