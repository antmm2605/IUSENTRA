import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent, type FormEvent, type ReactNode, type RefObject } from 'react'
import { useOperationalRefresh } from '../hooks/useOperationalRefresh'
import { mergeRegistryRefresh } from '../features/anagrafiche/mergeRegistryRefresh'
import { registryCompleteness, type RegistryCompletenessItem } from '../features/anagrafiche/registryCompleteness'
import {
  ArrowLeft,
  AlertTriangle,
  BadgeCheck,
  BriefcaseBusiness,
  Building2,
  Camera,
  CheckCircle2,
  ClipboardCheck,
  CreditCard,
  FileText,
  Home,
  Landmark,
  Loader2,
  Mail,
  Phone,
  ScanLine,
  Search,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  UserCheck,
  UserPlus,
  UserRound,
  UsersRound,
} from 'lucide-react'
import { Badge, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import {
  emptyClientiNuovoData,
  getClientiNuovoData,
  searchPublicSubjectRegisters,
  type ClientiNuovoData,
  type PublicRegistrySubjectResult,
  type RegistryOption,
} from '../clientiNuovoData'
import { redirectAfterSuccess, submitFormJson } from '../formSubmit'
import { destinazioneDopoSalvataggio, destinazioneInterna, messaggioSalvataggio } from '../lib/salvataggioCliente'
import { anagraficaDraftKey, useAnagraficaDraft, type AnagraficaDraftStatus } from '../features/anagrafiche/useAnagraficaDraft'
import './NuovoClientePage.css'
import { formatDateIt } from '../formatting'

type Tab = 'cliente' | 'soggetto'
type PublicRegistryKind = 'reginde' | 'registro_ppaa' | 'inipec'
type ClientType = 'PERSONA_FISICA' | 'PERSONA_GIURIDICA'
type ClientFormState = Record<string, string | boolean>
type SubjectFormState = Record<string, string>
type SubmitState = { saving: boolean; tone: 'success' | 'danger' | 'neutral'; message: string }
type ComuneOption = {
  nome: string
  label: string
  cap: string[]
  siglaProvincia: string
  provincia: string
}

const subjectLegalTypes = new Set(['PERSONA_GIURIDICA', 'PUBBLICA_AMMINISTRAZIONE', 'ENTE', 'CONDOMINIO', 'ASSOCIAZIONE'])
const publicRegistryChoices: Array<{ id: PublicRegistryKind; label: string; note: string; placeholder: string }> = [
  { id: 'reginde', label: 'ReGIndE', note: 'Difensori e domiciliatari', placeholder: 'Nome, C.F. o PEC del professionista' },
  { id: 'registro_ppaa', label: 'Registro PP.AA.', note: 'Pubbliche amministrazioni locali', placeholder: 'Ente, C.F., P. IVA o PEC' },
  { id: 'inipec', label: 'INI-PEC', note: 'Imprese e professionisti', placeholder: 'Ragione sociale, P. IVA o PEC' },
]

const initialClient: ClientFormState = {
  tipo: 'PERSONA_FISICA',
  nome: '',
  cognome: '',
  ragione_sociale: '',
  codice_fiscale: '',
  partita_iva: '',
  forma_giuridica: '',
  data_nascita: '',
  luogo_nascita: '',
  provincia_nascita: '',
  sesso: '',
  nazionalita: 'Italiana',
  rappresentante_legale: '',
  cf_rappresentante: '',
  telefono: '',
  cellulare: '',
  email: '',
  pec: '',
  fax: '',
  sito_web: '',
  via: '',
  civico: '',
  cap: '',
  comune: '',
  provincia: '',
  nazione: 'Italia',
  dom_via: '',
  dom_civico: '',
  dom_cap: '',
  dom_comune: '',
  dom_provincia: '',
  dom_nazione: 'Italia',
  sl_via: '',
  sl_civico: '',
  sl_cap: '',
  sl_comune: '',
  sl_provincia: '',
  sl_nazione: 'Italia',
  doc_tipo: 'CARTA_IDENTITA',
  doc_numero: '',
  doc_rilasciato_da: '',
  doc_data_rilascio: '',
  doc_data_scadenza: '',
  avvocato_referente: '',
  provenienza: '',
  note: '',
  next_url: '',
  crea_preventivo_iniziale: true,
}

const initialSubject: SubjectFormState = {
  tipo: 'PERSONA_FISICA',
  nome: '',
  cognome: '',
  ragione_sociale: '',
  codice_fiscale: '',
  partita_iva: '',
  forma_giuridica: '',
  data_nascita: '',
  luogo_nascita: '',
  provincia_nascita: '',
  sesso: '',
  rappresentante_legale: '',
  qualifica: 'CONTROPARTE',
  ordine: '',
  numero_iscrizione: '',
  id_cliente: '',
  telefono: '',
  cellulare: '',
  email: '',
  pec: '',
  fax: '',
  sito_web: '',
  via: '',
  civico: '',
  cap: '',
  comune: '',
  provincia: '',
  nazione: 'Italia',
  note: '',
  tag: '',
}

function initialTab(): Tab {
  if (typeof window === 'undefined') return 'cliente'
  const path = window.location.pathname
  const params = new URLSearchParams(window.location.search)
  if (path.includes('/soggetti/nuovo') || /^\/soggetti\/[^/]+\/modifica$/.test(path)) return 'soggetto'
  return (params.get('tab') || params.get('tipo')) === 'soggetto' ? 'soggetto' : 'cliente'
}

function text(value: unknown, fallback = ''): string {
  return String(value ?? fallback).trim()
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

async function safeJson(response: Response): Promise<Record<string, unknown>> {
  try {
    const payload = await response.json()
    return isRecord(payload) ? payload : {}
  } catch {
    return {}
  }
}

function asInputValue(value: string | boolean | undefined): string {
  // Nessun trim durante la digitazione: altrimenti lo spazio finale sparisce e non si possono scrivere
  // nomi composti, indirizzi o ragioni sociali. La pulizia avviene al salvataggio lato server.
  return typeof value === 'boolean' ? (value ? '1' : '0') : String(value ?? '')
}

type ClientDocumentField = keyof typeof initialClient
type SubjectDocumentField = keyof typeof initialSubject
type ClientDocumentPatch = Partial<Record<ClientDocumentField, string>>
type SubjectDocumentPatch = Partial<Record<SubjectDocumentField, string>>
type ClientDocumentReaderPhase = 'idle' | 'selected' | 'reading' | 'success' | 'warning' | 'danger'
type ClientDocumentRecognizedField = {
  name: string
  label: string
  value: string
  confidence: number
  source: string
  status: string
  sources?: { label: string; href: string }[]
}
type ClientDocumentAutofillState = {
  phase: ClientDocumentReaderPhase
  tone: 'neutral' | 'success' | 'warning' | 'danger'
  message: string
  fields: string[]
  applied: string[]
  skipped: string[]
  missing: string[]
  warnings: string[]
  recognized: ClientDocumentRecognizedField[]
  filename: string
  models?: string[]
  sourceDocument?: { label: string; href: string }
}
type ClientDocumentAutofillResult = {
  ok: boolean
  applied: string[]
  skipped: string[]
  message: string
}

declare global {
  interface Window {
    IUSENTRA_CLIENTE_NUOVO?: {
      applicaDatiDocumento: (payload: unknown) => ClientDocumentAutofillResult
    }
    IUSENTRA_SOGGETTO_NUOVO?: {
      applicaDatiDocumento: (payload: unknown) => ClientDocumentAutofillResult
    }
  }
}

const emptyDocumentAutofillState: ClientDocumentAutofillState = {
  phase: 'idle',
  tone: 'neutral',
  message: 'Carica un PDF, JPG o PNG del documento per leggere dati anagrafici e MRZ.',
  fields: [],
  applied: [],
  skipped: [],
  missing: [],
  warnings: [],
  recognized: [],
  filename: '',
}

const clientDocumentFieldLabels: Partial<Record<ClientDocumentField, string>> = {
  codice_fiscale: 'codice fiscale',
  cognome: 'cognome',
  nome: 'nome',
  sesso: 'sesso',
  data_nascita: 'data di nascita',
  luogo_nascita: 'luogo di nascita',
  provincia_nascita: 'provincia di nascita',
  nazionalita: 'nazionalità',
  doc_tipo: 'tipo documento',
  doc_numero: 'numero documento',
  doc_rilasciato_da: 'rilasciato da',
  doc_data_rilascio: 'data rilascio',
  doc_data_scadenza: 'data scadenza',
  via: 'via',
  civico: 'civico',
  cap: 'CAP',
  comune: 'comune',
  provincia: 'provincia',
  nazione: 'nazione',
  telefono: 'telefono',
  cellulare: 'cellulare',
  email: 'email',
  pec: 'PEC',
}

const clientDocumentAliases: Partial<Record<ClientDocumentField, string[]>> = {
  codice_fiscale: ['codice_fiscale', 'codice fiscale', 'cf', 'fiscalCode', 'taxCode'],
  cognome: ['cognome', 'surname', 'lastName', 'familyName'],
  nome: ['nome', 'name', 'firstName', 'givenName'],
  sesso: ['sesso', 'sex', 'gender'],
  data_nascita: ['data_nascita', 'data nascita', 'birthDate', 'dateOfBirth', 'dob'],
  luogo_nascita: ['luogo_nascita', 'luogo nascita', 'comune_nascita', 'birthPlace', 'placeOfBirth'],
  provincia_nascita: ['provincia_nascita', 'provincia nascita', 'birthProvince', 'provinceOfBirth'],
  nazionalita: ['nazionalita', 'nazionalità', 'nationality', 'cittadinanza'],
  doc_tipo: ['doc_tipo', 'tipo_documento', 'tipo documento', 'documentType', 'documento_tipo', 'type'],
  doc_numero: ['doc_numero', 'numero_documento', 'numero documento', 'documentNumber', 'numero', 'number'],
  doc_rilasciato_da: ['doc_rilasciato_da', 'rilasciato_da', 'rilasciato da', 'issuingAuthority', 'issuer'],
  doc_data_rilascio: ['doc_data_rilascio', 'data_rilascio', 'data rilascio', 'issueDate', 'releasedAt'],
  doc_data_scadenza: ['doc_data_scadenza', 'data_scadenza', 'data scadenza', 'expiryDate', 'expirationDate', 'validUntil'],
  via: ['via', 'indirizzo', 'address', 'street', 'residenza_via'],
  civico: ['civico', 'numero_civico', 'houseNumber', 'streetNumber'],
  cap: ['cap', 'postalCode', 'zip', 'zipCode'],
  comune: ['comune', 'city', 'municipality', 'residenza_comune'],
  provincia: ['provincia', 'province', 'residenza_provincia'],
  nazione: ['nazione', 'country', 'residenza_nazione'],
  telefono: ['telefono', 'phone'],
  cellulare: ['cellulare', 'mobile', 'mobilePhone'],
  email: ['email', 'mail'],
  pec: ['pec', 'certifiedEmail'],
}

function normalizeScanKey(value: string): string {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]/g, '')
}

function rememberScanValue(bucket: Map<string, string[]>, key: string, value: unknown) {
  const normalizedKey = normalizeScanKey(key)
  const clean = text(value)
  if (!normalizedKey || !clean || clean === 'null' || clean === 'undefined') return
  const current = bucket.get(normalizedKey) || []
  current.push(clean)
  bucket.set(normalizedKey, current)
}

function collectScanValues(payload: unknown, parentKey = '', bucket = new Map<string, string[]>(), depth = 0): Map<string, string[]> {
  if (depth > 6 || payload === null || payload === undefined) return bucket
  if (Array.isArray(payload)) {
    payload.forEach((item) => collectScanValues(item, parentKey, bucket, depth + 1))
    return bucket
  }
  if (!isRecord(payload)) {
    if (parentKey) rememberScanValue(bucket, parentKey, payload)
    return bucket
  }
  Object.entries(payload).forEach(([key, value]) => {
    const compoundKey = parentKey ? `${parentKey}_${key}` : key
    if (isRecord(value) || Array.isArray(value)) {
      collectScanValues(value, compoundKey, bucket, depth + 1)
      return
    }
    rememberScanValue(bucket, key, value)
    rememberScanValue(bucket, compoundKey, value)
  })
  return bucket
}

function pickScanValue(values: Map<string, string[]>, aliases: string[]): string {
  for (const alias of aliases) {
    const candidates = values.get(normalizeScanKey(alias))
    const value = candidates?.find((item) => text(item))
    if (value) return value
  }
  return ''
}

function padDatePart(value: number): string {
  return String(value).padStart(2, '0')
}

function formatScanDate(year: number, month: number, day: number): string {
  if (year < 1900 || month < 1 || month > 12 || day < 1 || day > 31) return ''
  const candidate = new Date(Date.UTC(year, month - 1, day))
  if (candidate.getUTCFullYear() !== year || candidate.getUTCMonth() !== month - 1 || candidate.getUTCDate() !== day) return ''
  return `${year}-${padDatePart(month)}-${padDatePart(day)}`
}

function normalizeTwoDigitYear(year: number, purpose: 'birth' | 'expiry' | 'generic'): number {
  const currentYear = new Date().getFullYear()
  const century = Math.floor(currentYear / 100) * 100
  let fullYear = century + year
  if (purpose === 'birth') {
    if (fullYear > currentYear) fullYear -= 100
    return fullYear
  }
  if (purpose === 'expiry') {
    if (fullYear < currentYear - 30) fullYear += 100
    return fullYear
  }
  if (fullYear > currentYear + 30) fullYear -= 100
  return fullYear
}

function normalizeScanDate(value: unknown, purpose: 'birth' | 'expiry' | 'generic' = 'generic'): string {
  const raw = text(value)
  if (!raw) return ''
  const iso = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (iso) return formatScanDate(Number(iso[1]), Number(iso[2]), Number(iso[3]))
  const italian = raw.match(/^(\d{1,2})[./-](\d{1,2})[./-](\d{2}|\d{4})$/)
  if (italian) {
    const year = italian[3].length === 2 ? normalizeTwoDigitYear(Number(italian[3]), purpose) : Number(italian[3])
    return formatScanDate(year, Number(italian[2]), Number(italian[1]))
  }
  const digits = raw.replace(/\D/g, '')
  if (digits.length === 8) return formatScanDate(Number(digits.slice(0, 4)), Number(digits.slice(4, 6)), Number(digits.slice(6, 8)))
  if (digits.length === 6) return formatScanDate(normalizeTwoDigitYear(Number(digits.slice(0, 2)), purpose), Number(digits.slice(2, 4)), Number(digits.slice(4, 6)))
  return ''
}

function normalizeScanSex(value: unknown): string {
  const raw = normalizeScanKey(text(value))
  if (['m', 'male', 'maschio', 'maschile'].includes(raw)) return 'M'
  if (['f', 'female', 'femmina', 'femminile'].includes(raw)) return 'F'
  return ''
}

function normalizeDocumentType(value: unknown): string {
  const raw = normalizeScanKey(text(value))
  if (!raw) return ''
  if (raw.includes('pass')) return 'PASSAPORTO'
  if (raw.includes('patente')) return 'PATENTE'
  if (raw.includes('soggiorno')) return 'PERMESSO_SOGGIORNO'
  if (raw.includes('ident') || raw === 'ci' || raw.startsWith('i')) return 'CARTA_IDENTITA'
  return text(value).toUpperCase()
}

function normalizeNationality(value: unknown): string {
  const raw = normalizeScanKey(text(value))
  if (!raw) return ''
  if (['ita', 'italia', 'italiana', 'italian'].includes(raw)) return 'Italiana'
  return text(value)
}

function titleCaseScanValue(value: string): string {
  return value
    .replace(/</g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLocaleLowerCase('it-IT')
    .replace(/(^|[\s'-])([a-zàèéìòù])/g, (_, prefix: string, letter: string) => `${prefix}${letter.toLocaleUpperCase('it-IT')}`)
}

function cleanMrzValue(value: string): string {
  return value.replace(/</g, '').trim()
}

function parseMrzNames(segment: string): Pick<ClientDocumentPatch, 'nome' | 'cognome'> {
  const [surname = '', names = ''] = segment.split('<<')
  return {
    cognome: titleCaseScanValue(surname),
    nome: titleCaseScanValue(names.replace(/</g, ' ')),
  }
}

function parseMrzDocument(rawMrz: string): ClientDocumentPatch {
  const lines = rawMrz.toUpperCase().split(/\r?\n/).map((line) => line.replace(/\s/g, '')).filter((line) => line.includes('<'))
  if (lines.length >= 2 && lines[0].startsWith('P') && lines[0].length >= 40 && lines[1].length >= 40) {
    return {
      doc_tipo: 'PASSAPORTO',
      doc_numero: cleanMrzValue(lines[1].slice(0, 9)),
      nazionalita: normalizeNationality(lines[1].slice(10, 13)),
      data_nascita: normalizeScanDate(lines[1].slice(13, 19), 'birth'),
      sesso: normalizeScanSex(lines[1].slice(20, 21)),
      doc_data_scadenza: normalizeScanDate(lines[1].slice(21, 27), 'expiry'),
      ...parseMrzNames(lines[0].slice(5)),
    }
  }
  if (lines.length >= 3 && lines[0].length >= 30 && lines[1].length >= 30) {
    return {
      doc_tipo: 'CARTA_IDENTITA',
      doc_numero: cleanMrzValue(lines[0].slice(5, 14)),
      data_nascita: normalizeScanDate(lines[1].slice(0, 6), 'birth'),
      sesso: normalizeScanSex(lines[1].slice(7, 8)),
      doc_data_scadenza: normalizeScanDate(lines[1].slice(8, 14), 'expiry'),
      nazionalita: normalizeNationality(lines[1].slice(15, 18)),
      ...parseMrzNames(lines[2]),
    }
  }
  return {}
}

function normalizeClientDocumentScan(payload: unknown): ClientDocumentPatch {
  // Il lettore nativo fornisce già il patch verificato: i metadati dei
  // campi (name/label/source) non sono valori anagrafici.
  const values = collectScanValues(isRecord(payload) && payload.source === 'lettore_documento_cliente' ? payload.patch : payload)
  const patch: ClientDocumentPatch = {}
  const mrz = pickScanValue(values, ['mrz', 'mrzText', 'mrz_text', 'rawMrz', 'raw_mrz', 'machineReadableZone'])
  Object.assign(patch, mrz ? parseMrzDocument(mrz) : {})
  Object.entries(clientDocumentAliases).forEach(([field, aliases]) => {
    const raw = pickScanValue(values, aliases || [])
    if (!raw) return
    const target = field as ClientDocumentField
    let clean = text(raw)
    if (target === 'data_nascita') clean = normalizeScanDate(raw, 'birth')
    if (target === 'doc_data_scadenza') clean = normalizeScanDate(raw, 'expiry')
    if (target === 'doc_data_rilascio') clean = normalizeScanDate(raw, 'generic')
    if (target === 'sesso') clean = normalizeScanSex(raw)
    if (target === 'doc_tipo') clean = normalizeDocumentType(raw)
    if (target === 'nazionalita') clean = normalizeNationality(raw)
    if (['codice_fiscale', 'provincia_nascita', 'provincia'].includes(target)) clean = clean.toUpperCase()
    if (clean) patch[target] = clean
  })
  return patch
}

function normalizeSubjectDocumentScan(payload: unknown): SubjectDocumentPatch {
  const clientPatch = normalizeClientDocumentScan(payload)
  const subjectPatch: SubjectDocumentPatch = {}
  Object.entries(clientPatch).forEach(([field, value]) => {
    if (field in initialSubject && text(value)) {
      subjectPatch[field as SubjectDocumentField] = value
    }
  })
  return subjectPatch
}

function canAutofillClientField(field: ClientDocumentField, currentValue: string | boolean | undefined, nextValue: string, touchedFields: Set<string>): boolean {
  if (!text(nextValue) || touchedFields.has(field)) return false
  const current = asInputValue(currentValue)
  const defaultValue = asInputValue(initialClient[field])
  return !text(current) || current === defaultValue
}

function canAutofillSubjectField(field: SubjectDocumentField, currentValue: string | undefined, nextValue: string, touchedFields: Set<string>): boolean {
  if (!text(nextValue) || touchedFields.has(field)) return false
  const current = asInputValue(currentValue)
  const defaultValue = asInputValue(initialSubject[field])
  return !text(current) || current === defaultValue
}

function recognizedDocumentFields(payload: unknown): ClientDocumentRecognizedField[] {
  if (!isRecord(payload)) return []
  const explicitRows = Array.isArray(payload.fields)
    ? payload.fields.filter(isRecord).map((item) => ({
      name: text(item.name),
      label: text(item.label ?? item.name),
      value: text(item.value),
      confidence: Number(item.confidence ?? 0),
      source: text(item.source),
      status: text(item.status, 'da verificare'),
      sources: Array.isArray(item.sources) ? item.sources.filter(isRecord).filter((source) => /^\/fascicoli\/[a-zA-Z0-9_-]+\/documenti\/[a-zA-Z0-9_-]+\/visualizza$/.test(text(source.href))).map((source) => ({ label: text(source.label), href: text(source.href) })) : [],
    })).filter((item) => item.name && item.value)
    : []
  if (explicitRows.length) return explicitRows
  if (!isRecord(payload.patch)) return []
  return Object.entries(payload.patch).map(([name, value]) => ({
    name,
    label: clientDocumentFieldLabels[name as ClientDocumentField] || name,
    value: text(value),
    confidence: 0.9,
    source: 'documento',
    status: 'affidabile',
  })).filter((item) => item.value)
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => text(item)).filter(Boolean) : []
}

function recognizedDocumentModels(payload: unknown): string[] {
  if (!isRecord(payload) || !Array.isArray(payload.document_profiles)) return []
  const labels: Record<string, string> = {
    cie: 'CIE', carta_cartacea: 'Carta d’identità cartacea', tessera_sanitaria: 'Tessera sanitaria',
  }
  return [...new Set(payload.document_profiles.filter(isRecord).map(row => labels[text(row.model)]).filter(Boolean))]
}

function documentFieldEvidenceLabel(field: ClientDocumentRecognizedField): string {
  // I punteggi del parser sono pesi delle regole, non probabilità OCR misurate.
  if (field.status !== 'affidabile') return 'Da verificare'
  if (field.source === 'zona MRZ') return 'MRZ verificata'
  if (field.source.startsWith('codice a barre')) return 'Codice a barre'
  return 'Letto nel documento'
}

const documentTypeLabels = Object.fromEntries(emptyClientiNuovoData.options.documentTypes.map(option => [option.value, option.label]))

function documentFieldValue(field: ClientDocumentRecognizedField): string {
  if (['data_nascita', 'doc_data_rilascio', 'doc_data_scadenza'].includes(field.name)) return formatDateIt(field.value)
  if (field.name === 'doc_tipo') return documentTypeLabels[field.value] || field.value
  return field.value
}

function DocumentAutofillPanel({
  state,
  selectedFile,
  inputRef,
  onChooseFile,
  onReadFile,
  onFileChange,
}:{
  state: ClientDocumentAutofillState
  selectedFile: File | null
  inputRef: RefObject<HTMLInputElement | null>
  onChooseFile: () => void
  onReadFile: () => void
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void
}) {
  const isReading = state.phase === 'reading'
  return (
    <div className={`iu-cln-doc-reader iu-cln-doc-reader--${state.phase}`} role={state.tone === 'danger' ? 'alert' : 'status'}>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
        hidden
        onChange={onFileChange}
      />
      <div className="iu-cln-doc-reader__icon">
        {isReading ? <Loader2 className="iu-spin" size={20}/> : <ScanLine size={20}/>}
      </div>
      <div className="iu-cln-doc-reader__main">
        <div className="iu-cln-doc-reader__head">
          <div>
            <strong>Lettore documento</strong>
            <span>{selectedFile ? selectedFile.name : state.filename || 'PDF, JPG o PNG di carta identità, passaporto o documento compatibile'}</span>
            {state.models?.length ? <span aria-label="Modelli riconosciuti"> · Modello: {state.models.join(' · ')}</span> : null}
          </div>
          <div className="iu-cln-doc-reader__actions">
            <button type="button" className="iu-cln-doc-reader__button" onClick={onChooseFile} disabled={isReading}>
              <UploadCloud size={15}/> Carica documento
            </button>
            <button type="button" className="iu-cln-doc-reader__button iu-cln-doc-reader__button--primary" onClick={onReadFile} disabled={isReading}>
              <Camera size={15}/> {isReading ? 'Lettura in corso...' : 'Leggi documento / MRZ'}
            </button>
          </div>
        </div>
        <p>{state.message}</p>
        {state.recognized.length ? (
          <div className="iu-cln-doc-reader__fields" aria-label="Dati letti dal documento">
            <strong>Dati letti dal documento</strong>
            <div>
              {state.recognized.map((field) => (
                <span className={field.status === 'affidabile' ? 'is-ok' : 'is-check'} key={`${field.name}-${field.value}`}>
                  <b>{field.label}</b>
                  <i>{documentFieldValue(field)}</i>
                  <em title={field.source}>{documentFieldEvidenceLabel(field)}</em>
                  {field.sources?.length ? <small>{field.source} · {field.sources.slice(0, 2).map((source, index) => <a key={source.href} href={source.href} title={source.label}>Fonte {index + 1}{index + 1 < Math.min(2, field.sources?.length || 0) ? ' · ' : ''}</a>)}</small> : null}
                </span>
              ))}
            </div>
          </div>
        ) : null}
        {state.applied.length ? <small className="iu-cln-doc-reader__ok"><CheckCircle2 size={13}/> Applicati: {state.applied.join(', ')}</small> : null}
        {state.sourceDocument ? <a href={state.sourceDocument.href}>Fonte: {state.sourceDocument.label}</a> : null}
        {state.skipped.length ? <small className="iu-cln-doc-reader__skip" title="Valori preesistenti e modifiche manuali conservati, comprese le cancellazioni volontarie."><AlertTriangle size={13}/> Campi preservati: {state.skipped.join(', ')}</small> : null}
        {state.missing.length ? <small className="iu-cln-doc-reader__skip"><AlertTriangle size={13}/> Dati non ancora dimostrati: {state.missing.join(', ')}</small> : null}
        {state.warnings.length ? (
          <ul className="iu-cln-doc-reader__warnings">
            {state.warnings.map((warning) => <li key={warning}>{warning}</li>)}
          </ul>
        ) : null}
      </div>
    </div>
  )
}

function DraftAutosaveBar({ status, onRestore, onDiscard }:{ status: AnagraficaDraftStatus; onRestore: () => void; onDiscard: () => void }) {
  const hasDraft = Boolean(status.savedAt) || status.pendingRestore
  return (
    <div className={`iu-cln-draft iu-cln-draft--${status.tone}`} role="status" aria-live="polite">
      <ClipboardCheck size={15}/>
      <span>{status.message || 'Salvataggio automatico attivo: ogni campo compilato viene salvato in bozza quando passi al successivo.'}</span>
      {status.pendingRestore ? <button type="button" onClick={onRestore}>Ripristina bozza</button> : null}
      {hasDraft ? <button type="button" onClick={onDiscard}>Scarta bozza</button> : null}
    </div>
  )
}

function emptySubmitState(): SubmitState {
  return { saving: false, tone: 'neutral', message: '' }
}

function SubmitFeedback({ state }:{ state: SubmitState }) {
  if (!state.message) return null
  return (
    <p className={`iu-cln-field-note iu-cln-field-note--${state.tone}`} role={state.tone === 'danger' ? 'alert' : 'status'}>
      <CheckCircle2 size={14}/>{state.message}
    </p>
  )
}

function Field({
  label,
  name,
  value,
  onChange,
  type = 'text',
  required = false,
  placeholder = '',
  wide = false,
  mono = false,
  children,
}:{
  label: string
  name: string
  value: string
  onChange: (name: string, value: string) => void
  type?: string
  required?: boolean
  placeholder?: string
  wide?: boolean
  mono?: boolean
  children?: ReactNode
}) {
  return (
    <label className={`iu-cln-field ${wide ? 'is-wide' : ''} ${mono ? 'is-mono' : ''}`.trim()}>
      <span>{label}{required ? <b>*</b> : null}</span>
      <input name={name} type={type} value={value} required={required} placeholder={placeholder} onChange={(event) => onChange(name, event.currentTarget.value)}/>
      {children}
    </label>
  )
}

function TextAreaField({
  label,
  name,
  value,
  onChange,
  placeholder = '',
}:{
  label: string
  name: string
  value: string
  onChange: (name: string, value: string) => void
  placeholder?: string
}) {
  return (
    <label className="iu-cln-field is-wide">
      <span>{label}</span>
      <textarea name={name} value={value} placeholder={placeholder} onChange={(event) => onChange(name, event.currentTarget.value)}/>
    </label>
  )
}

function SelectField({
  label,
  name,
  value,
  options,
  onChange,
  required = false,
}:{
  label: string
  name: string
  value: string
  options: RegistryOption[]
  onChange: (name: string, value: string) => void
  required?: boolean
}) {
  return (
    <label className="iu-cln-field">
      <span>{label}{required ? <b>*</b> : null}</span>
      <select name={name} value={value} required={required} onChange={(event) => onChange(name, event.currentTarget.value)}>
        {options.map((option) => <option value={option.value} key={`${name}-${option.value}`}>{option.label}</option>)}
      </select>
    </label>
  )
}

function comuneKey(value: string): string {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/gi, '').toLowerCase()
}

function ComuneAutocompleteField({
  label,
  name,
  capName,
  provinciaName,
  value,
  capValue,
  provinciaValue,
  onChange,
}:{
  label: string
  name: string
  capName: string
  provinciaName: string
  value: string
  capValue: string
  provinciaValue: string
  onChange: (name: string, value: string) => void
}) {
  const [items, setItems] = useState<ComuneOption[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [resolutionNote, setResolutionNote] = useState('')

  useEffect(() => {
    const query = text(value)
    if (comuneKey(query).length < 2) {
      setItems([])
      setLoading(false)
      return
    }
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setLoading(true)
      fetch(`/api/v1/ui/territorio/comuni?q=${encodeURIComponent(query)}`, {
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      })
        .then((response) => response.ok ? response.json() : Promise.reject(new Error(`HTTP ${response.status}`)))
        .then((payload) => {
          const rawItems = Array.isArray(payload?.items) ? payload.items : []
          setItems(rawItems.map((item: Record<string, unknown>) => ({
            nome: text(item.nome),
            label: text(item.label),
            cap: Array.isArray(item.cap) ? item.cap.map((capItem) => text(capItem)).filter(Boolean) : [],
            siglaProvincia: text(item.siglaProvincia).toUpperCase(),
            provincia: text(item.provincia),
          })).filter((item: ComuneOption) => item.nome && item.siglaProvincia))
        })
        .catch((error) => {
          if ((error as Error).name !== 'AbortError') setItems([])
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false)
        })
    }, 180)
    return () => {
      controller.abort()
      window.clearTimeout(timer)
    }
  }, [value])

  useEffect(() => {
    const key = comuneKey(value)
    const exact = items.filter(item => comuneKey(item.nome) === key || comuneKey(item.label) === key)
    const province = provinciaValue.trim().toUpperCase()
    const matching = province ? exact.filter(item => item.siglaProvincia === province) : exact
    if (matching.length !== 1) {
      setResolutionNote(exact.length && province && !matching.length ? 'La provincia presente non coincide con il Comune: dato conservato.' : '')
      return
    }
    const option = matching[0]
    if (!province) onChange(provinciaName, option.siglaProvincia)
    const caps = [...new Set(option.cap)]
    if (!capValue.trim() && caps.length === 1) onChange(capName, caps[0])
    setResolutionNote(!capValue.trim() && caps.length > 1
      ? 'Il Comune ha più CAP: serve il CAP dell’indirizzo, non viene scelto il primo.'
      : capValue.trim() && caps.length && !caps.includes(capValue.trim())
        ? 'Il CAP presente non coincide con i CAP del Comune: dato conservato.' : '')
  }, [items, value, capValue, provinciaValue, capName, provinciaName, onChange])

  const applyComune = (option: ComuneOption) => {
    const caps = [...new Set(option.cap)]
    const selectedCap = caps.includes(capValue) ? capValue : caps.length === 1 ? caps[0] : ''
    onChange(name, option.nome)
    onChange(provinciaName, option.siglaProvincia)
    onChange(capName, selectedCap)
    setOpen(false)
  }

  return (
    <label className="iu-cln-field iu-cln-comune-field">
      <span>{label}</span>
      <input
        name={name}
        type="text"
        value={value}
        autoComplete="off"
        role="combobox"
        aria-expanded={open && items.length > 0}
        aria-autocomplete="list"
        placeholder="Scrivi il Comune"
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => {
          setOpen(false)
        }, 120)}
        onChange={(event) => {
          onChange(name, event.currentTarget.value)
          setOpen(true)
        }}
      />
      {resolutionNote ? <small role="status">{resolutionNote}</small> : null}
      {open && (items.length > 0 || loading) ? (
        <div className="iu-cln-comune-suggestions" role="listbox">
          {loading ? <span className="iu-cln-comune-suggestions__status">Ricerca Comuni...</span> : null}
          {items.map((item) => (
            <button type="button" role="option" key={`${item.nome}-${item.siglaProvincia}`} onMouseDown={(event) => event.preventDefault()} onClick={() => applyComune(item)}>
              <strong>{item.label || `${item.nome} (${item.siglaProvincia})`}</strong>
              <small>{item.cap[0] || 'CAP non disponibile'} - {item.provincia}</small>
            </button>
          ))}
        </div>
      ) : null}
    </label>
  )
}

function ChoiceGrid({
  name,
  value,
  options,
  onChange,
  columns = 'type',
}:{
  name: string
  value: string
  options: RegistryOption[]
  onChange: (name: string, value: string) => void
  columns?: 'type' | 'subject' | 'role'
}) {
  const className = columns === 'role' ? 'iu-cln-process-grid' : columns === 'subject' ? 'iu-cln-subject-type-grid' : 'iu-cln-type-grid'
  return (
    <div className={className}>
      {options.map((option) => (
        <label className={`iu-cln-choice iu-cln-choice--${option.tone || 'neutral'} ${value === option.value ? 'is-active' : ''}`} key={`${name}-${option.value}`}>
          <input type="radio" name={name} value={option.value} checked={value === option.value} onChange={() => onChange(name, option.value)}/>
          <span>{columns === 'role' ? <BriefcaseBusiness size={18}/> : subjectLegalTypes.has(option.value) ? <Building2 size={18}/> : <UserRound size={18}/>}</span>
          <strong>{option.label}</strong>
          {option.subtitle ? <small>{option.subtitle}</small> : null}
        </label>
      ))}
    </div>
  )
}

function Card({ title, icon, note, children }:{title: string; icon: ReactNode; note?: string; children: ReactNode}) {
  return (
    <section className="iu-cln-card">
      <header className="iu-cln-card__head">
        <div>{icon}<strong>{title}</strong></div>
        {note ? <span>{note}</span> : null}
      </header>
      <div className="iu-cln-card__body">{children}</div>
    </section>
  )
}

async function decodeFiscalCode(value: string): Promise<Record<string, string>> {
  const code = value.replace(/\s/g, '').toUpperCase()
  if (code.length !== 16) return {}
  const response = await fetch(`/api/cf/decodifica?cf=${encodeURIComponent(code)}`, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
  const payload = await safeJson(response)
  if (payload.errore) return {}
  return {
    sesso: text(payload.sesso),
    data_nascita: text(payload.data_nascita),
    luogo_nascita: text(payload.luogo_nascita),
    provincia_nascita: text(payload.provincia_nascita),
  }
}

async function calculateFiscalCode(values: Record<string, string>): Promise<Record<string, string>> {
  const params = new URLSearchParams({
    cognome: text(values.cognome),
    nome: text(values.nome),
    sesso: text(values.sesso),
    data_nascita: text(values.data_nascita),
    luogo_nascita: text(values.luogo_nascita),
    provincia_nascita: text(values.provincia_nascita),
  })
  if ([params.get('cognome'), params.get('nome'), params.get('sesso'), params.get('data_nascita'), params.get('luogo_nascita')].some((item) => !item)) return {}
  const response = await fetch(`/api/cf/calcola?${params.toString()}`, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
  const payload = await safeJson(response)
  if (payload.errore) return {}
  return {
    codice_fiscale: text(payload.codice_fiscale),
    luogo_nascita: text(payload.luogo_nascita),
    provincia_nascita: text(payload.provincia_nascita),
  }
}

function StatsStrip({ data }:{data: ClientiNuovoData}) {
  return (
    <section className="iu-cln-stats" aria-label="Stato anagrafiche">
      <article><UsersRound size={20}/><span>Clienti</span><strong>{data.stats.totalClients}</strong><small>{data.stats.activeClients} attivi</small></article>
      <article><UserRound size={20}/><span>Persone fisiche</span><strong>{data.stats.physicalClients}</strong><small>PF in archivio</small></article>
      <article><Building2 size={20}/><span>Persone giuridiche</span><strong>{data.stats.legalClients}</strong><small>Società ed enti</small></article>
      <article><ClipboardCheck size={20}/><span>Da completare</span><strong>{data.stats.missingRegistry}</strong><small>{data.stats.expiredDocuments} documenti scaduti</small></article>
    </section>
  )
}

function ClientForm({ data, onCompleteness }:{data: ClientiNuovoData; onCompleteness: (items: RegistryCompletenessItem[]) => void}) {
  const [values, setValues] = useState<ClientFormState>({...initialClient})
  const [cfStatus, setCfStatus] = useState('')
  const [submitState, setSubmitState] = useState<SubmitState>(() => emptySubmitState())
  const [autofillState, setAutofillState] = useState<ClientDocumentAutofillState>(() => emptyDocumentAutofillState)
  const [selectedDocumentFile, setSelectedDocumentFile] = useState<File | null>(null)
  const [touchedFields, setTouchedFields] = useState<Set<string>>(() => new Set())
  const persistedValues = useRef<ClientFormState | undefined>(undefined)
  const [refreshConflicts, setRefreshConflicts] = useState<string[]>([])
  const valuesRef = useRef(values)
  const touchedFieldsRef = useRef(touchedFields)
  const documentFileInputRef = useRef<HTMLInputElement | null>(null)
  const action = data.actions.operationalClientForm
  const isPhysical = values.tipo === 'PERSONA_FISICA'
  useEffect(() => {
    onCompleteness(registryCompleteness(values, { legal: !isPhysical, documentRejected: autofillState.phase === 'danger' }))
  }, [values, isPhysical, autofillState.phase, onCompleteness])
  const nextUrl = data.query.nextUrl
  const sourceMatter = new URLSearchParams(window.location.search).get('id_fascicolo') || ''
  const sourceDocument = new URLSearchParams(window.location.search).get('id_documento') || ''
  const clientDraftInitial = useMemo<ClientFormState>(
    () => (data.mode === 'edit' ? {...initialClient, ...data.initialClient} : {...initialClient}),
    [data.mode, data.initialClient],
  )
  const clientDraftKey = useMemo(
    () => anagraficaDraftKey('cliente', data.mode === 'edit' ? data.query.idCliente : '', data.mode === 'edit' ? '' : data.query.idCliente),
    [data.mode, data.query.idCliente],
  )
  const draft = useAnagraficaDraft<ClientFormState>({
    storageKey: clientDraftKey,
    ready: data.source !== 'vuoto',
    autoRestore: data.mode !== 'edit',
    values,
    initialValues: clientDraftInitial,
    protectedFields: touchedFields,
    excludedFields: ['next_url'],
    onRestore: (draftValues, restoredFields) => {
      setValues((current) => ({...current, ...draftValues}) as ClientFormState)
      setTouchedFields((current) => new Set([...current, ...restoredFields]))
    },
  })

  useEffect(() => {
    valuesRef.current = values
  }, [values])

  useEffect(() => {
    touchedFieldsRef.current = touchedFields
  }, [touchedFields])

  useEffect(() => {
    if (data.mode !== 'edit') return
    const incoming = {...initialClient, ...data.initialClient}
    const merged = mergeRegistryRefresh(valuesRef.current, persistedValues.current, incoming)
    persistedValues.current = incoming
    valuesRef.current = merged.values
    setValues(merged.values)
    setRefreshConflicts(current => [...new Set([...current, ...merged.conflicts])].filter(key => merged.values[key] !== incoming[key]))
  }, [data])

  useEffect(() => {
    if (nextUrl) setValues((current) => ({...current, next_url: nextUrl}))
  }, [nextUrl])

  useEffect(() => {
    const code = text(values.codice_fiscale).replace(/\s/g, '').toUpperCase()
    setCfStatus('')
    if (!isPhysical || code.length !== 16) return
    let cancelled = false
    const timer = window.setTimeout(() => {
      decodeFiscalCode(code).then((decoded) => {
        if (cancelled || !Object.keys(decoded).length) return
        setValues((current) => ({
          ...current,
          codice_fiscale: code,
          sesso: text(current.sesso) || decoded.sesso || '',
          data_nascita: text(current.data_nascita) || decoded.data_nascita || '',
          luogo_nascita: text(current.luogo_nascita) || decoded.luogo_nascita || '',
          provincia_nascita: text(current.provincia_nascita) || decoded.provincia_nascita || '',
        }))
        setCfStatus('Codice fiscale letto; conservati i dati già compilati.')
      })
    }, 240)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [values.codice_fiscale, isPhysical])

  useEffect(() => {
    if (!isPhysical || text(values.codice_fiscale)) return
    const fields = {
      cognome: text(values.cognome),
      nome: text(values.nome),
      sesso: text(values.sesso),
      data_nascita: text(values.data_nascita),
      luogo_nascita: text(values.luogo_nascita),
      provincia_nascita: text(values.provincia_nascita),
    }
    if (Object.values(fields).slice(0, 5).some((item) => !item)) return
    let cancelled = false
    const timer = window.setTimeout(() => {
      calculateFiscalCode(fields).then((result) => {
        if (cancelled || !result.codice_fiscale) return
        setValues((current) => text(current.codice_fiscale) ? current : ({...current, ...result}))
        setCfStatus('Codice fiscale generato: verifica prima del salvataggio.')
      })
    }, 420)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [values.cognome, values.nome, values.sesso, values.data_nascita, values.luogo_nascita, values.provincia_nascita, values.codice_fiscale, isPhysical])

  const applyDocumentPayload = useCallback((payload: unknown): ClientDocumentAutofillResult => {
    if (!isPhysical) {
      const result = { ok: false, applied: [], skipped: [], message: 'La lettura documento è disponibile per le persone fisiche.' }
      setAutofillState({ ...emptyDocumentAutofillState, phase: 'warning', tone: 'neutral', message: result.message, filename: selectedDocumentFile?.name || '' })
      return result
    }
    const patch = normalizeClientDocumentScan(payload)
    const entries = Object.entries(patch).filter(([, value]) => text(value))
    if (!entries.length) {
      const result = { ok: false, applied: [], skipped: [], message: 'Nessun dato anagrafico riconosciuto dal documento.' }
      setAutofillState({ ...emptyDocumentAutofillState, phase: 'danger', tone: 'danger', message: result.message, filename: selectedDocumentFile?.name || '' })
      return result
    }
    const currentValues = valuesRef.current
    const currentTouched = touchedFieldsRef.current
    const nextValues: ClientFormState = { ...currentValues }
    const applied: string[] = []
    const skipped: string[] = []
    const addressFields: ClientDocumentField[] = ['via', 'civico', 'cap', 'comune', 'provincia']
    const addressBlocked = addressFields.some((field) => currentTouched.has(field) && patch[field] && patch[field] !== asInputValue(currentValues[field]))
    entries.forEach(([field, value]) => {
      const target = field as ClientDocumentField
      const clean = text(value)
      if (!(addressBlocked && addressFields.includes(target)) && (canAutofillClientField(target, currentValues[target], clean, currentTouched) || (isRecord(payload) && isRecord(payload.source_document) && !currentTouched.has(target)))) {
        nextValues[target] = clean
        applied.push(clientDocumentFieldLabels[target] || target)
      } else {
        skipped.push(clientDocumentFieldLabels[target] || target)
      }
    })
    if (applied.includes(clientDocumentFieldLabels.comune || 'comune') && !patch.cap && nextValues.comune !== currentValues.comune) nextValues.cap = ''
    if (applied.length) {
      setValues(nextValues)
      setAutofillState({
        phase: 'success',
        tone: 'success',
        message: skipped.length ? 'Dati documento applicati. Alcuni campi già compilati sono stati lasciati invariati.' : 'Dati documento compilati nella scheda. Controlla gli esiti e salva le modifiche.',
        fields: applied,
        applied,
        skipped,
        missing: [],
        warnings: [],
        recognized: recognizedDocumentFields(payload),
        models: recognizedDocumentModels(payload),
        filename: selectedDocumentFile?.name || '',
      })
      return { ok: true, applied, skipped, message: 'Dati documento applicati.' }
    }
    const result = { ok: false, applied, skipped, message: 'I campi riconosciuti sono già compilati o protetti dalle tue modifiche.' }
    setAutofillState({
      ...emptyDocumentAutofillState,
      phase: 'warning',
      tone: 'warning',
      message: result.message,
      fields: skipped,
      skipped,
      recognized: recognizedDocumentFields(payload),
      models: recognizedDocumentModels(payload),
      filename: selectedDocumentFile?.name || '',
    })
    return result
  }, [isPhysical, selectedDocumentFile])

  const chooseDocumentFile = () => {
    documentFileInputRef.current?.click()
  }

  const handleDocumentFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0] || null
    setSelectedDocumentFile(file)
    if (!file) {
      setAutofillState(emptyDocumentAutofillState)
      return
    }
    setAutofillState({
      ...emptyDocumentAutofillState,
      phase: 'selected',
      tone: 'neutral',
      filename: file.name,
      message: 'Documento caricato. Premi Leggi documento / MRZ per compilare i dati riconosciuti.',
    })
  }

  const readSelectedDocumentFile = async () => {
    if (!selectedDocumentFile && !sourceMatter && !data.query.idCliente) {
      setAutofillState({
        ...emptyDocumentAutofillState,
        phase: 'warning',
        tone: 'warning',
        message: 'Carica prima un PDF, JPG o PNG del documento.',
      })
      documentFileInputRef.current?.click()
      return
    }
    setAutofillState({
      ...emptyDocumentAutofillState,
      phase: 'reading',
      tone: 'neutral',
      filename: selectedDocumentFile?.name || 'Documento del fascicolo',
      message: 'Lettura OCR/MRZ in corso...',
    })
    try {
      const formData = new FormData()
      if (selectedDocumentFile) formData.append('file', selectedDocumentFile)
      if (selectedDocumentFile && data.mode === 'edit') formData.append('id_cliente', data.query.idCliente)
      const response = await fetch(data.actions.documentReader, {
        method: 'POST',
        credentials: 'same-origin',
        body: selectedDocumentFile ? formData : JSON.stringify({ id_fascicolo: sourceMatter, id_cliente: data.query.idCliente, id_documento: sourceDocument }),
        headers: { ...(!selectedDocumentFile ? { 'Content-Type': 'application/json' } : {}), Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      })
      const payload = await safeJson(response)
      const recognized = recognizedDocumentFields(payload)
      const missing = stringList(payload.missing)
      const warnings = stringList(payload.warnings)
      if (!response.ok && !recognized.length) {
        throw new Error(text(payload.message ?? payload.errore, `Lettura documento non riuscita: HTTP ${response.status}`))
      }
      const result = applyDocumentPayload(payload)
      const phase: ClientDocumentReaderPhase = result.ok ? 'success' : recognized.length ? 'warning' : 'danger'
      setAutofillState({
        phase,
        tone: result.ok ? 'success' : recognized.length ? 'warning' : 'danger',
        message: result.ok ? "Dati riconosciuti compilati nella scheda. Le modifiche non sono ancora salvate." : result.message,
        sourceDocument: isRecord(payload.source_document) && /^\/fascicoli\/[a-zA-Z0-9_-]+\/documenti\/[a-zA-Z0-9_-]+\/visualizza$/.test(text(payload.source_document.href)) ? { href: text(payload.source_document.href), label: text(payload.source_document.label) } : undefined,
        fields: result.applied,
        applied: result.applied,
        skipped: result.skipped,
        missing,
        warnings,
        recognized,
        models: recognizedDocumentModels(payload),
        filename: text(payload.filename) || selectedDocumentFile?.name || 'Documento del fascicolo',
      })
    } catch (error) {
      setAutofillState({
        ...emptyDocumentAutofillState,
        phase: 'danger',
        tone: 'danger',
        filename: selectedDocumentFile?.name || 'Documento del fascicolo',
        message: error instanceof Error ? error.message : 'Lettura documento non riuscita.',
      })
    }
  }

  useEffect(() => {
    const api = { applicaDatiDocumento: applyDocumentPayload }
    window.IUSENTRA_CLIENTE_NUOVO = api
    const handleDocumentDetected = (event: Event) => {
      applyDocumentPayload((event as CustomEvent<unknown>).detail)
    }
    window.addEventListener('iusentra:cliente-documento-rilevato', handleDocumentDetected)
    return () => {
      window.removeEventListener('iusentra:cliente-documento-rilevato', handleDocumentDetected)
      if (window.IUSENTRA_CLIENTE_NUOVO?.applicaDatiDocumento === api.applicaDatiDocumento) {
        delete window.IUSENTRA_CLIENTE_NUOVO
      }
    }
  }, [applyDocumentPayload])

  const change = (name: string, value: string) => {
    if (asInputValue(valuesRef.current[name]) === value) return
    setTouchedFields((current) => {
      const next = new Set(current)
      next.add(name)
      return next
    })
    setValues((current) => ({...current, [name]: name.includes('codice') || name.includes('partita') || name.includes('provincia') ? value.toUpperCase() : value}))
  }
  const checkbox = (event: ChangeEvent<HTMLInputElement>) => {
    // Nome e stato vanno letti subito: React azzera event.currentTarget a fine evento e
    // l'aggiornamento funzionale può girare dopo (secondo click → errore → ricarica pagina).
    const { name, checked } = event.currentTarget
    setValues((current) => ({...current, [name]: checked}))
  }
  const generateNow = () => {
    calculateFiscalCode({
      cognome: text(values.cognome),
      nome: text(values.nome),
      sesso: text(values.sesso),
      data_nascita: text(values.data_nascita),
      luogo_nascita: text(values.luogo_nascita),
      provincia_nascita: text(values.provincia_nascita),
    }).then((result) => {
      if (!result.codice_fiscale) {
        setCfStatus('Completa cognome, nome, sesso, data e luogo di nascita.')
        return
      }
      setValues((current) => ({...current, ...result}))
      setCfStatus('Codice fiscale generato: verifica prima del salvataggio.')
    })
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitState({ saving: true, tone: 'neutral', message: 'Salvataggio in corso...' })
    try {
      const formData = new FormData(event.currentTarget)
      const submittedValues = { ...valuesRef.current }
      const result = await submitFormJson(action, formData)
      persistedValues.current = submittedValues
      if (JSON.stringify(valuesRef.current) === JSON.stringify(submittedValues)) {
        draft.clearAfterSave()
        setAutofillState(current => current.phase === 'success' ? {
          ...current,
          message: 'Dati riconosciuti del documento salvati nell’anagrafica.',
        } : current)
      }
      // In modifica si resta sulla scheda: chi sta correggendo un cliente non
      // va buttato fuori dal modulo a ogni salvataggio. In creazione si va
      // alla cartella del cliente appena nato; se la scheda e' stata aperta da
      // un'altra pagina (`next_url`) si torna li'.
      const destinazione = destinazioneInterna(result.redirect) ?? destinazioneDopoSalvataggio({
        mode: data.mode,
        query: { idCliente: data.query.idCliente },
        nextUrl: (formData.get('next_url') as string | null) ?? data.query.nextUrl,
        idSalvato: result.id || null,
      })
      setSubmitState({ saving: false, tone: 'success', message: messaggioSalvataggio(destinazione, result.message) })
      if (destinazione) redirectAfterSuccess({ ...result, redirect: destinazione }, destinazione)
    } catch (error) {
      setSubmitState({ saving: false, tone: 'danger', message: error instanceof Error ? error.message : 'Salvataggio non riuscito.' })
    }
  }

  return (
    <form className="iu-cln-form" onSubmit={handleSubmit} onBlur={draft.handleBlur}>
      {refreshConflicts.length ? <div role="alert" className="iu-cln-flow-alert"><div><strong>Anagrafica aggiornata in un’altra finestra</strong><span>Le tue modifiche non salvate sono preservate. Confronta i campi prima di salvare.</span>{refreshConflicts.map(key => <div key={key}><span>{clientDocumentFieldLabels[key] || key}: valore salvato {String(persistedValues.current?.[key] ?? '')}</span><button type="button" className="iu-button iu-button--secondary" onClick={() => { const value = persistedValues.current?.[key]; if (value !== undefined) setValues(current => ({ ...current, [key]: value })); setRefreshConflicts(current => current.filter(item => item !== key)) }}>Usa valore salvato</button><button type="button" className="iu-button iu-button--secondary" onClick={() => setRefreshConflicts(current => current.filter(item => item !== key))}>Mantieni la mia modifica</button></div>)}</div></div> : null}
      <input type="hidden" name="next_url" value={asInputValue(values.next_url)}/>
      <DraftAutosaveBar status={draft.status} onRestore={draft.restore} onDiscard={() => { draft.discard(true); touchedFieldsRef.current = new Set(); setTouchedFields(new Set()); setAutofillState(emptyDocumentAutofillState) }}/>
      <Card title="Tipo cliente" icon={<UserCheck size={18}/>} note={data.mode === 'edit' ? 'Aggiornamento anagrafica esistente' : 'Nuova anagrafica governata'}>
        <ChoiceGrid name="tipo" value={asInputValue(values.tipo)} options={data.options.clientTypes} onChange={change}/>
      </Card>

      <Card title={isPhysical ? 'Dati persona fisica' : 'Dati persona giuridica'} icon={isPhysical ? <UserRound size={18}/> : <Building2 size={18}/>} note="Campi coerenti con l'anagrafica dello studio">
        {isPhysical ? (
          <div className="iu-cln-grid">
            <DocumentAutofillPanel
              state={autofillState}
              selectedFile={selectedDocumentFile}
              inputRef={documentFileInputRef}
              onChooseFile={chooseDocumentFile}
              onReadFile={readSelectedDocumentFile}
              onFileChange={handleDocumentFileChange}
            />
            <Field label="Cognome" name="cognome" value={asInputValue(values.cognome)} required placeholder="Rossi" onChange={change}/>
            <Field label="Nome" name="nome" value={asInputValue(values.nome)} required placeholder="Mario" onChange={change}/>
            <SelectField label="Sesso" name="sesso" value={asInputValue(values.sesso)} required onChange={change} options={[{value: '', label: '-'}, {value: 'M', label: 'Maschile'}, {value: 'F', label: 'Femminile'}]}/>
            <Field label="Codice fiscale" name="codice_fiscale" value={asInputValue(values.codice_fiscale)} placeholder="RSSMRA80A01H501Z" mono onChange={change}>
              <button className="iu-cln-mini-action" type="button" onClick={generateNow}>Genera CF</button>
            </Field>
            <Field label="Data di nascita" name="data_nascita" type="date" value={asInputValue(values.data_nascita)} onChange={change}/>
            <Field label="Luogo di nascita" name="luogo_nascita" value={asInputValue(values.luogo_nascita)} placeholder="Roma" onChange={change}/>
            <Field label="Provincia nascita" name="provincia_nascita" value={asInputValue(values.provincia_nascita)} placeholder="RM" mono onChange={change}/>
            <Field label="Nazionalità" name="nazionalita" value={asInputValue(values.nazionalita)} placeholder="Italiana" onChange={change}/>
            {cfStatus ? <p className="iu-cln-field-note"><Sparkles size={14}/>{cfStatus}</p> : null}
          </div>
        ) : (
          <div className="iu-cln-grid">
            <Field label="Ragione sociale" name="ragione_sociale" value={asInputValue(values.ragione_sociale)} required placeholder="Rossi Srl" onChange={change}/>
            <SelectField label="Forma giuridica" name="forma_giuridica" value={asInputValue(values.forma_giuridica)} options={data.options.legalForms} onChange={change}/>
            <Field label="Partita IVA" name="partita_iva" value={asInputValue(values.partita_iva)} placeholder="12345678901" mono onChange={change}/>
            <Field label="Codice fiscale ente" name="codice_fiscale" value={asInputValue(values.codice_fiscale)} mono onChange={change}/>
            <Field label="Rappresentante legale" name="rappresentante_legale" value={asInputValue(values.rappresentante_legale)} onChange={change}/>
            <Field label="CF rappresentante" name="cf_rappresentante" value={asInputValue(values.cf_rappresentante)} mono onChange={change}/>
          </div>
        )}
      </Card>

      <Card title="Recapiti" icon={<Phone size={18}/>} note="Usati da conferimenti, messaggi e PEC">
        <div className="iu-cln-grid">
          <Field label="Telefono" name="telefono" value={asInputValue(values.telefono)} onChange={change}/>
          <Field label="Cellulare" name="cellulare" value={asInputValue(values.cellulare)} onChange={change}/>
          <Field label="Email" name="email" type="email" value={asInputValue(values.email)} onChange={change}/>
          <Field label="PEC" name="pec" type="email" value={asInputValue(values.pec)} onChange={change}/>
          <Field label="Fax" name="fax" value={asInputValue(values.fax)} onChange={change}/>
          <Field label="Sito web" name="sito_web" value={asInputValue(values.sito_web)} onChange={change}/>
        </div>
      </Card>

      <Card title={isPhysical ? 'Residenza e domicilio' : 'Sede legale'} icon={<Home size={18}/>} note="Campi coerenti con il modello anagrafico dello studio">
        <div className="iu-cln-grid">
          <Field label={isPhysical ? 'Via residenza' : 'Via sede'} name={isPhysical ? 'via' : 'sl_via'} value={asInputValue(values[isPhysical ? 'via' : 'sl_via'])} onChange={change}/>
          <Field label="Civico" name={isPhysical ? 'civico' : 'sl_civico'} value={asInputValue(values[isPhysical ? 'civico' : 'sl_civico'])} onChange={change}/>
          <Field label="CAP" name={isPhysical ? 'cap' : 'sl_cap'} value={asInputValue(values[isPhysical ? 'cap' : 'sl_cap'])} onChange={change}/>
          <ComuneAutocompleteField
            label="Comune"
            name={isPhysical ? 'comune' : 'sl_comune'}
            capName={isPhysical ? 'cap' : 'sl_cap'}
            provinciaName={isPhysical ? 'provincia' : 'sl_provincia'}
            value={asInputValue(values[isPhysical ? 'comune' : 'sl_comune'])}
            capValue={asInputValue(values[isPhysical ? 'cap' : 'sl_cap'])}
            provinciaValue={asInputValue(values[isPhysical ? 'provincia' : 'sl_provincia'])}
            onChange={change}
          />
          <Field label="Provincia" name={isPhysical ? 'provincia' : 'sl_provincia'} value={asInputValue(values[isPhysical ? 'provincia' : 'sl_provincia'])} mono onChange={change}/>
          <Field label="Nazione" name={isPhysical ? 'nazione' : 'sl_nazione'} value={asInputValue(values[isPhysical ? 'nazione' : 'sl_nazione'])} onChange={change}/>
          {isPhysical ? (
            <>
              <Field label="Domicilio via" name="dom_via" value={asInputValue(values.dom_via)} onChange={change}/>
              <Field label="Domicilio CAP" name="dom_cap" value={asInputValue(values.dom_cap)} onChange={change}/>
              <ComuneAutocompleteField
                label="Domicilio comune"
                name="dom_comune"
                capName="dom_cap"
                provinciaName="dom_provincia"
                value={asInputValue(values.dom_comune)}
                capValue={asInputValue(values.dom_cap)}
                provinciaValue={asInputValue(values.dom_provincia)}
                onChange={change}
              />
              <Field label="Domicilio provincia" name="dom_provincia" value={asInputValue(values.dom_provincia)} mono onChange={change}/>
            </>
          ) : null}
        </div>
      </Card>

      <Card title="Documento e studio" icon={<FileText size={18}/>} note="Documento salvato dal servizio anagrafico esteso">
        <div className="iu-cln-grid">
          <SelectField label="Tipo documento" name="doc_tipo" value={asInputValue(values.doc_tipo)} options={data.options.documentTypes.map(option => ({ ...option, label: documentTypeLabels[option.value] || option.label }))} onChange={change}/>
          <Field label="Numero documento" name="doc_numero" value={asInputValue(values.doc_numero)} mono onChange={change}/>
          <Field label="Rilasciato da" name="doc_rilasciato_da" value={asInputValue(values.doc_rilasciato_da)} onChange={change}/>
          <Field label="Data rilascio" name="doc_data_rilascio" type="date" value={asInputValue(values.doc_data_rilascio)} onChange={change}/>
          <Field label="Data scadenza" name="doc_data_scadenza" type="date" value={asInputValue(values.doc_data_scadenza)} onChange={change}/>
          <Field label="Avvocato referente" name="avvocato_referente" value={asInputValue(values.avvocato_referente)} onChange={change}/>
          <Field label="Provenienza" name="provenienza" value={asInputValue(values.provenienza)} placeholder="passaparola, web, cliente" onChange={change}/>
          <TextAreaField label="Note" name="note" value={asInputValue(values.note)} onChange={change}/>
        </div>
      </Card>

      {data.mode === 'edit' ? null : (
        <label className="iu-cln-switch">
          <input type="checkbox" name="crea_preventivo_iniziale" value="1" checked={Boolean(values.crea_preventivo_iniziale)} onChange={checkbox}/>
          <span><i/></span>
          <strong>Crea preventivo iniziale dopo il salvataggio</strong>
          <small>Prosegue con preventivo, conferimento e fascicolo collegati.</small>
        </label>
      )}

      <SubmitFeedback state={submitState}/>
      <div className="iu-cln-actions">
        <button className="iu-cln-submit" type="submit" disabled={submitState.saving || refreshConflicts.length > 0}><CheckCircle2 size={17}/>{submitState.saving ? 'Salvataggio...' : data.mode === 'edit' ? 'Salva modifiche' : 'Salva cliente'}</button>
        <a className="iu-cln-secondary" href={data.mode === 'edit' && data.query.idCliente ? `/clienti/${encodeURIComponent(data.query.idCliente)}/cartella` : '/clienti'}>Annulla</a>
      </div>
    </form>
  )
}

function SubjectForm({ data, onCompleteness }:{data: ClientiNuovoData; onCompleteness: (items: RegistryCompletenessItem[]) => void}) {
  const [values, setValues] = useState<SubjectFormState>({...initialSubject})
  const persistedSubject = useRef<SubjectFormState | undefined>(undefined)
  const [subjectConflicts, setSubjectConflicts] = useState<string[]>([])
  const [cfStatus, setCfStatus] = useState('')
  const [submitState, setSubmitState] = useState<SubmitState>(() => emptySubmitState())
  const [autofillState, setAutofillState] = useState<ClientDocumentAutofillState>(() => emptyDocumentAutofillState)
  const [selectedDocumentFile, setSelectedDocumentFile] = useState<File | null>(null)
  const [touchedFields, setTouchedFields] = useState<Set<string>>(() => new Set())
  const [registryQuery, setRegistryQuery] = useState('')
  const [registryResults, setRegistryResults] = useState<PublicRegistrySubjectResult[]>([])
  const [registryLoading, setRegistryLoading] = useState(false)
  const [registryMessage, setRegistryMessage] = useState('')
  const [registryError, setRegistryError] = useState('')
  const [registryKind, setRegistryKind] = useState<PublicRegistryKind>('reginde')
  const valuesRef = useRef(values)
  const touchedFieldsRef = useRef(touchedFields)
  const documentFileInputRef = useRef<HTMLInputElement | null>(null)
  const action = data.actions.operationalSubjectForm
  const isLegal = subjectLegalTypes.has(values.tipo)
  useEffect(() => {
    onCompleteness(registryCompleteness(values, { legal: isLegal, subject: true, allowedRoles: data.options.subjectRoles.map(item => item.value) }))
  }, [values, isLegal, data.options.subjectRoles, onCompleteness])
  const selectedRegistry = publicRegistryChoices.find((item) => item.id === registryKind) || publicRegistryChoices[0]
  const subjectCancelHref = data.mode === 'edit_subject' && data.query.idSoggetto
    ? `/soggetti/${encodeURIComponent(data.query.idSoggetto)}`
    : data.query.nextUrl || (data.query.idFascicolo ? `/fascicoli/${encodeURIComponent(data.query.idFascicolo)}/modifica` : '/soggetti')

  useEffect(() => {
    valuesRef.current = values
  }, [values])

  useEffect(() => {
    touchedFieldsRef.current = touchedFields
  }, [touchedFields])

  useEffect(() => {
    if (data.mode === 'edit_subject' || Object.keys(data.initialSubject).length) {
      const incoming = { ...initialSubject, ...data.initialSubject }
      const merged = mergeRegistryRefresh(valuesRef.current, persistedSubject.current, incoming)
      persistedSubject.current = incoming
      valuesRef.current = merged.values
      setValues(merged.values)
      setSubjectConflicts(current => [...new Set([...current.filter(key => merged.values[key] !== incoming[key]), ...merged.conflicts])])
      return
    }
  }, [data.mode, data.initialSubject])

  const subjectDraftInitial = useMemo<SubjectFormState>(() => ({ ...initialSubject, ...data.initialSubject }), [data.initialSubject])
  const subjectDraftKey = useMemo(
    () => anagraficaDraftKey(
      'soggetto',
      data.mode === 'edit_subject' ? data.query.idSoggetto : '',
      data.mode === 'edit_subject' ? '' : [data.query.idFascicolo, data.query.ruoloSoggetto].filter(Boolean).join('-'),
    ),
    [data.mode, data.query.idSoggetto, data.query.idFascicolo, data.query.ruoloSoggetto],
  )
  const draft = useAnagraficaDraft<SubjectFormState>({
    storageKey: subjectDraftKey,
    ready: data.source !== 'vuoto',
    autoRestore: data.mode !== 'edit_subject',
    values,
    initialValues: subjectDraftInitial,
    protectedFields: touchedFields,
    onRestore: (draftValues, restoredFields) => {
      const clean = Object.fromEntries(Object.entries(draftValues).map(([key, value]) => [key, String(value ?? '')]))
      setValues((current) => ({ ...current, ...clean }))
      setTouchedFields((current) => new Set([...current, ...restoredFields]))
    },
  })

  useEffect(() => {
    const code = text(values.codice_fiscale).replace(/\s/g, '').toUpperCase()
    setCfStatus('')
    if (isLegal || code.length !== 16) return
    let cancelled = false
    const timer = window.setTimeout(() => {
      decodeFiscalCode(code).then((decoded) => {
        if (cancelled || !Object.keys(decoded).length) return
        setValues((current) => ({
          ...current,
          codice_fiscale: code,
          sesso: text(current.sesso) || decoded.sesso || '',
          data_nascita: text(current.data_nascita) || decoded.data_nascita || '',
          luogo_nascita: text(current.luogo_nascita) || decoded.luogo_nascita || '',
          provincia_nascita: text(current.provincia_nascita) || decoded.provincia_nascita || '',
        }))
        setCfStatus('Codice fiscale letto; conservati i dati già compilati.')
      })
    }, 240)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [values.codice_fiscale, isLegal])

  useEffect(() => {
    if (isLegal || text(values.codice_fiscale)) return
    const fields = {
      cognome: text(values.cognome),
      nome: text(values.nome),
      sesso: text(values.sesso),
      data_nascita: text(values.data_nascita),
      luogo_nascita: text(values.luogo_nascita),
      provincia_nascita: text(values.provincia_nascita),
    }
    if (Object.values(fields).slice(0, 5).some((item) => !item)) return
    let cancelled = false
    const timer = window.setTimeout(() => {
      calculateFiscalCode(fields).then((result) => {
        if (cancelled || !result.codice_fiscale) return
        setValues((current) => text(current.codice_fiscale) ? current : ({...current, ...result}))
        setCfStatus('Codice fiscale generato: verifica prima del salvataggio.')
      })
    }, 420)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [values.cognome, values.nome, values.sesso, values.data_nascita, values.luogo_nascita, values.provincia_nascita, values.codice_fiscale, isLegal])

  const applyDocumentPayload = useCallback((payload: unknown): ClientDocumentAutofillResult => {
    if (isLegal) {
      const result = { ok: false, applied: [], skipped: [], message: 'La lettura documento è disponibile per le persone fisiche.' }
      setAutofillState({ ...emptyDocumentAutofillState, phase: 'warning', tone: 'neutral', message: result.message, filename: selectedDocumentFile?.name || '' })
      return result
    }
    const patch = normalizeSubjectDocumentScan(payload)
    const entries = Object.entries(patch).filter(([, value]) => text(value))
    if (!entries.length) {
      const result = { ok: false, applied: [], skipped: [], message: 'Nessun dato anagrafico riconosciuto dal documento.' }
      setAutofillState({ ...emptyDocumentAutofillState, phase: 'danger', tone: 'danger', message: result.message, filename: selectedDocumentFile?.name || '' })
      return result
    }
    const currentValues = valuesRef.current
    const currentTouched = touchedFieldsRef.current
    const nextValues: SubjectFormState = { ...currentValues }
    const applied: string[] = []
    const skipped: string[] = []
    entries.forEach(([field, value]) => {
      const target = field as SubjectDocumentField
      const clean = text(value)
      if (canAutofillSubjectField(target, currentValues[target], clean, currentTouched)) {
        nextValues[target] = clean
        applied.push(clientDocumentFieldLabels[target as ClientDocumentField] || target)
      } else {
        skipped.push(clientDocumentFieldLabels[target as ClientDocumentField] || target)
      }
    })
    if (applied.length) {
      setValues(nextValues)
      setAutofillState({
        phase: 'success',
        tone: 'success',
        message: skipped.length ? 'Dati documento applicati. Alcuni campi già compilati sono stati lasciati invariati.' : 'Dati documento applicati al nuovo soggetto.',
        fields: applied,
        applied,
        skipped,
        missing: [],
        warnings: [],
        recognized: recognizedDocumentFields(payload),
        models: recognizedDocumentModels(payload),
        filename: selectedDocumentFile?.name || '',
      })
      return { ok: true, applied, skipped, message: 'Dati documento applicati.' }
    }
    const result = { ok: false, applied, skipped, message: 'I campi riconosciuti erano già compilati.' }
    setAutofillState({
      ...emptyDocumentAutofillState,
      phase: 'warning',
      tone: 'warning',
      message: result.message,
      fields: skipped,
      skipped,
      recognized: recognizedDocumentFields(payload),
      models: recognizedDocumentModels(payload),
      filename: selectedDocumentFile?.name || '',
    })
    return result
  }, [isLegal, selectedDocumentFile])

  const chooseDocumentFile = () => {
    documentFileInputRef.current?.click()
  }

  const handleDocumentFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0] || null
    setSelectedDocumentFile(file)
    if (!file) {
      setAutofillState(emptyDocumentAutofillState)
      return
    }
    setAutofillState({
      ...emptyDocumentAutofillState,
      phase: 'selected',
      tone: 'neutral',
      filename: file.name,
      message: 'Documento caricato. Premi Leggi documento / MRZ per compilare i dati riconosciuti.',
    })
  }

  const readSelectedDocumentFile = async () => {
    if (!selectedDocumentFile) {
      setAutofillState({
        ...emptyDocumentAutofillState,
        phase: 'warning',
        tone: 'warning',
        message: 'Carica prima un PDF, JPG o PNG del documento.',
      })
      documentFileInputRef.current?.click()
      return
    }
    setAutofillState({
      ...emptyDocumentAutofillState,
      phase: 'reading',
      tone: 'neutral',
      filename: selectedDocumentFile.name,
      message: 'Lettura OCR/MRZ in corso...',
    })
    try {
      const formData = new FormData()
      formData.append('file', selectedDocumentFile)
      const response = await fetch(data.actions.documentReader, {
        method: 'POST',
        credentials: 'same-origin',
        body: formData,
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      })
      const payload = await safeJson(response)
      const recognized = recognizedDocumentFields(payload)
      const missing = stringList(payload.missing)
      const warnings = stringList(payload.warnings)
      if (!response.ok && !recognized.length) {
        throw new Error(text(payload.message ?? payload.errore, `Lettura documento non riuscita: HTTP ${response.status}`))
      }
      const result = applyDocumentPayload(payload)
      const phase: ClientDocumentReaderPhase = result.ok ? 'success' : recognized.length ? 'warning' : 'danger'
      setAutofillState({
        phase,
        tone: result.ok ? 'success' : recognized.length ? 'warning' : 'danger',
        message: text(payload.message, result.message),
        fields: result.applied,
        applied: result.applied,
        skipped: result.skipped,
        missing,
        warnings,
        recognized,
        models: recognizedDocumentModels(payload),
        filename: selectedDocumentFile.name,
      })
    } catch (error) {
      setAutofillState({
        ...emptyDocumentAutofillState,
        phase: 'danger',
        tone: 'danger',
        filename: selectedDocumentFile.name,
        message: error instanceof Error ? error.message : 'Lettura documento non riuscita.',
      })
    }
  }

  useEffect(() => {
    const api = { applicaDatiDocumento: applyDocumentPayload }
    window.IUSENTRA_SOGGETTO_NUOVO = api
    const handleDocumentDetected = (event: Event) => {
      applyDocumentPayload((event as CustomEvent<unknown>).detail)
    }
    window.addEventListener('iusentra:soggetto-documento-rilevato', handleDocumentDetected)
    return () => {
      window.removeEventListener('iusentra:soggetto-documento-rilevato', handleDocumentDetected)
      if (window.IUSENTRA_SOGGETTO_NUOVO?.applicaDatiDocumento === api.applicaDatiDocumento) {
        delete window.IUSENTRA_SOGGETTO_NUOVO
      }
    }
  }, [applyDocumentPayload])

  const change = (name: string, value: string) => {
    setTouchedFields((current) => {
      const next = new Set(current)
      next.add(name)
      return next
    })
    setValues((current) => ({...current, [name]: name.includes('codice') || name.includes('partita') || name.includes('provincia') ? value.toUpperCase() : value}))
  }
  const generateNow = () => {
    calculateFiscalCode(values).then((result) => {
      if (!result.codice_fiscale) {
        setCfStatus('Completa cognome, nome, sesso, data e luogo di nascita.')
        return
      }
      setValues((current) => ({...current, ...result}))
      setCfStatus('Codice fiscale generato: verifica prima del salvataggio.')
    })
  }

  const searchRegistries = async () => {
    const query = text(registryQuery)
    setRegistryError('')
    setRegistryMessage('')
    if (query.length < 3) {
      setRegistryResults([])
      setRegistryMessage(`Digita almeno 3 caratteri per cercare in ${selectedRegistry.label}.`)
      return
    }
    setRegistryLoading(true)
    try {
      const payload = await searchPublicSubjectRegisters(query, 12, registryKind)
      setRegistryResults(payload.results)
      setRegistryMessage(payload.message || `${payload.results.length} risultati in ${selectedRegistry.label}.`)
    } catch (error) {
      setRegistryResults([])
      setRegistryError(error instanceof Error ? error.message : 'Ricerca nei registri pubblici non riuscita.')
    } finally {
      setRegistryLoading(false)
    }
  }

  const applyRegistryResult = (item: PublicRegistrySubjectResult) => {
    const patch = item.subjectPatch
    setValues((current) => {
      const next = {...current}
      Object.entries(patch).forEach(([key, value]) => {
        if (key in initialSubject && text(value)) {
          next[key] = key.includes('codice') || key.includes('partita') || key.includes('provincia') ? value.toUpperCase() : value
        }
      })
      next.id_cliente = ''
      return next
    })
    setTouchedFields((current) => {
      const next = new Set(current)
      Object.keys(patch).forEach((key) => next.add(key))
      next.delete('id_cliente')
      return next
    })
    setRegistryMessage(`Dati ${item.registryLabel} applicati: verifica prima del salvataggio.`)
    setRegistryError('')
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (subjectConflicts.length) return
    setSubmitState({ saving: true, tone: 'neutral', message: 'Salvataggio in corso...' })
    try {
      const formData = new FormData(event.currentTarget)
      const submittedValues = { ...valuesRef.current }
      const result = await submitFormJson(action, formData)
      persistedSubject.current = submittedValues
      if (JSON.stringify(valuesRef.current) === JSON.stringify(submittedValues)) {
        draft.clearAfterSave()
        setAutofillState(current => current.phase === 'success' ? {
          ...current,
          message: 'Dati riconosciuti del documento salvati nell’anagrafica.',
        } : current)
      }
      setSubmitState({ saving: false, tone: 'success', message: result.message || 'Soggetto salvato.' })
      redirectAfterSuccess(result, subjectCancelHref)
    } catch (error) {
      setSubmitState({ saving: false, tone: 'danger', message: error instanceof Error ? error.message : 'Salvataggio non riuscito.' })
    }
  }

  return (
    <form className="iu-cln-form" onSubmit={handleSubmit} onBlur={draft.handleBlur}>
      {subjectConflicts.length ? <div className="iu-cln-flow-alert" role="alert"><strong>Soggetto aggiornato in un’altra finestra</strong><p>Le tue modifiche sono preservate. Confronta i campi prima di salvare.</p>{subjectConflicts.map(key => <div key={key}><span>{key.replaceAll('_', ' ')}: valore salvato {persistedSubject.current?.[key] || 'non presente'}</span><button type="button" className="iu-button iu-button--secondary" onClick={() => { setValues(current => ({ ...current, [key]: persistedSubject.current?.[key] || '' })); setSubjectConflicts(current => current.filter(item => item !== key)) }}>Usa valore salvato</button><button type="button" className="iu-button iu-button--secondary" onClick={() => setSubjectConflicts(current => current.filter(item => item !== key))}>Mantieni la mia modifica</button></div>)}</div> : null}
      <DraftAutosaveBar status={draft.status} onRestore={draft.restore} onDiscard={() => { draft.discard(true); touchedFieldsRef.current = new Set(); setTouchedFields(new Set()); setAutofillState(emptyDocumentAutofillState) }}/>
      <input type="hidden" name="id_fascicolo" value={data.query.idFascicolo}/>
      <input type="hidden" name="next_url" value={data.query.nextUrl}/>
      <input type="hidden" name="ruolo_collegamento" value={values.qualifica || data.query.ruoloSoggetto}/>
      <Card title="Registri pubblici" icon={<ShieldCheck size={18}/>} note={selectedRegistry.label}>
        <div className="iu-cln-registry">
          <div className="iu-cln-registry__switch" role="tablist" aria-label="Registro pubblico da consultare">
            {publicRegistryChoices.map((choice) => (
              <button
                type="button"
                role="tab"
                aria-selected={registryKind === choice.id}
                className={registryKind === choice.id ? 'is-active' : ''}
                onClick={() => {
                  setRegistryKind(choice.id)
                  setRegistryResults([])
                  setRegistryError('')
                  setRegistryMessage(`Ricerca impostata su ${choice.label}.`)
                }}
                key={choice.id}
              >
                <strong>{choice.label}</strong>
                <span>{choice.note}</span>
              </button>
            ))}
          </div>
          <label className="iu-cln-registry__search">
            <span>Cerca in {selectedRegistry.label}</span>
            <div>
              <Search size={16}/>
              <input
                value={registryQuery}
                onChange={(event) => setRegistryQuery(event.currentTarget.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault()
                    searchRegistries()
                  }
                }}
                placeholder={selectedRegistry.placeholder}
              />
              <button type="button" onClick={searchRegistries} disabled={registryLoading}>
                {registryLoading ? <Loader2 className="iu-spin" size={15}/> : <Search size={15}/>}
                {registryLoading ? 'Ricerca...' : 'Cerca'}
              </button>
            </div>
          </label>
          <div className="iu-cln-registry__status" aria-live="polite">
            {registryError ? <span className="is-error">{registryError}</span> : <span>{registryMessage || 'Elenchi locali pronti per la ricerca autenticata.'}</span>}
          </div>
          {registryResults.length ? (
            <div className="iu-cln-registry__results">
              {registryResults.map((item) => (
                <button type="button" key={item.id} onClick={() => applyRegistryResult(item)}>
                  <span>
                    <strong>{item.label}</strong>
                    <small>{item.taxCode || 'Identificativo non presente'} - {item.pec || 'PEC non presente'}</small>
                  </span>
                  <Badge tone={item.registry === 'registro_ppaa' ? 'info' : item.registry === 'inipec' ? 'purple' : 'primary'}>{item.registryLabel}</Badge>
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </Card>
      <Card title="Tipo soggetto" icon={<UsersRound size={18}/>} note={data.mode === 'edit_subject' ? 'Aggiornamento soggetto processuale esistente' : 'Anagrafica soggetto processuale'}>
        <ChoiceGrid name="tipo" value={values.tipo} options={data.options.subjectTypes} columns="subject" onChange={change}/>
      </Card>

      <Card title={isLegal ? 'Dati ente o parte giuridica' : 'Dati persona fisica'} icon={isLegal ? <Landmark size={18}/> : <UserRound size={18}/>} note={data.mode === 'edit_subject' ? 'Aggiornamento soggetto processuale' : 'Nuovo soggetto governato'}>
        {isLegal ? (
          <div className="iu-cln-grid">
            <Field label="Ragione sociale" name="ragione_sociale" value={values.ragione_sociale} required onChange={change}/>
            <SelectField label="Forma giuridica" name="forma_giuridica" value={values.forma_giuridica} options={data.options.legalForms} onChange={change}/>
            <Field label="Partita IVA" name="partita_iva" value={values.partita_iva} mono onChange={change}/>
            <Field label="Codice fiscale" name="codice_fiscale" value={values.codice_fiscale} mono onChange={change}/>
            <Field label="Rappresentante legale" name="rappresentante_legale" value={values.rappresentante_legale} onChange={change}/>
          </div>
        ) : (
          <div className="iu-cln-grid">
            <DocumentAutofillPanel
              state={autofillState}
              selectedFile={selectedDocumentFile}
              inputRef={documentFileInputRef}
              onChooseFile={chooseDocumentFile}
              onReadFile={readSelectedDocumentFile}
              onFileChange={handleDocumentFileChange}
            />
            <Field label="Cognome" name="cognome" value={values.cognome} required onChange={change}/>
            <Field label="Nome" name="nome" value={values.nome} required onChange={change}/>
            <SelectField label="Sesso" name="sesso" value={values.sesso} onChange={change} options={[{value: '', label: '-'}, {value: 'M', label: 'Maschile'}, {value: 'F', label: 'Femminile'}]}/>
            <Field label="Codice fiscale" name="codice_fiscale" value={values.codice_fiscale} mono onChange={change}>
              <button className="iu-cln-mini-action" type="button" onClick={generateNow}>Genera CF</button>
            </Field>
            <Field label="Data di nascita" name="data_nascita" type="date" value={values.data_nascita} onChange={change}/>
            <Field label="Luogo di nascita" name="luogo_nascita" value={values.luogo_nascita} onChange={change}/>
            <Field label="Provincia nascita" name="provincia_nascita" value={values.provincia_nascita} mono onChange={change}/>
            {cfStatus ? <p className="iu-cln-field-note"><Sparkles size={14}/>{cfStatus}</p> : null}
          </div>
        )}
      </Card>

      <Card title="Tipo soggetto processuale" icon={<BriefcaseBusiness size={18}/>} note="Salvato nel campo qualifica">
        <ChoiceGrid name="qualifica" value={values.qualifica} options={data.options.subjectRoles} columns="role" onChange={change}/>
      </Card>

      <Card title="Qualifica professionale" icon={<UserCheck size={18}/>} note="Dati professionali, ordine e tag">
        <div className="iu-cln-grid">
          <Field label="Ordine professionale" name="ordine" value={values.ordine} onChange={change}/>
          <Field label="Numero iscrizione" name="numero_iscrizione" value={values.numero_iscrizione} onChange={change}/>
          <Field label="Tag" name="tag" value={values.tag} placeholder="controparte, assicurazione" onChange={change}/>
        </div>
      </Card>

      <Card title="Recapiti e indirizzo" icon={<Mail size={18}/>} note="Compatibile con il modello soggetti e parti">
        <div className="iu-cln-grid">
          <Field label="Telefono" name="telefono" value={values.telefono} onChange={change}/>
          <Field label="Cellulare" name="cellulare" value={values.cellulare} onChange={change}/>
          <Field label="Email" name="email" type="email" value={values.email} onChange={change}/>
          <Field label="PEC" name="pec" type="email" value={values.pec} onChange={change}/>
          <Field label="Via" name="via" value={values.via} onChange={change}/>
          <Field label="Civico" name="civico" value={values.civico} onChange={change}/>
          <Field label="CAP" name="cap" value={values.cap} onChange={change}/>
          <ComuneAutocompleteField
            label="Comune"
            name="comune"
            capName="cap"
            provinciaName="provincia"
            value={values.comune}
            capValue={values.cap}
            provinciaValue={values.provincia}
            onChange={change}
          />
          <Field label="Provincia" name="provincia" value={values.provincia} mono onChange={change}/>
          <Field label="Nazione" name="nazione" value={values.nazione} onChange={change}/>
          <TextAreaField label="Note" name="note" value={values.note} onChange={change}/>
        </div>
      </Card>

      <SubmitFeedback state={submitState}/>
      <div className="iu-cln-actions">
        <button className="iu-cln-submit" type="submit" disabled={submitState.saving}><CheckCircle2 size={17}/>{submitState.saving ? 'Salvataggio...' : data.mode === 'edit_subject' ? 'Salva modifiche' : 'Salva soggetto'}</button>
        <a className="iu-cln-secondary" href={subjectCancelHref}>Annulla</a>
      </div>
    </form>
  )
}

function QualityRail({ data, items }:{data: ClientiNuovoData; items: RegistryCompletenessItem[]}) {
  return (
    <aside className="iu-cln-rail">
      <Panel title="Completezza dei campi" icon={<BadgeCheck size={17}/>} count={items.filter(item => item.complete).length}>
        <div className="iu-cln-checklist" aria-live="polite">
          {items.map((item) => <span key={item.label} className={item.complete ? 'is-complete' : 'is-pending'}>
            {item.complete ? <CheckCircle2 size={15}/> : <AlertTriangle size={15}/>}
            <div><strong>{item.label}</strong><small>{item.detail}</small></div>
          </span>)}
        </div>
      </Panel>
      <Panel title="Statistiche rapide" icon={<ClipboardCheck size={17}/>}>
        <div className="iu-cln-briefing">
          <article><span>Clienti da completare</span><strong>{data.stats.missingRegistry}</strong><small>prima del conferimento</small></article>
          <article><span>Soggetti non collegati</span><strong>{data.stats.subjectsWithoutClient}</strong><small>da associare se necessario</small></article>
          <article><span>Documenti scaduti</span><strong>{data.stats.expiredDocuments}</strong><small>da aggiornare</small></article>
        </div>
      </Panel>
      <Panel title="Azioni collegate" icon={<Sparkles size={17}/>}>
        <div className="iu-cln-shortcuts">
          <a href="/clienti"><UsersRound size={15}/>Anagrafica clienti</a>
          <a href="/soggetti"><UserCheck size={15}/>Soggetti e parti</a>
          <a href="/global-search?tipo=clienti"><ScanLine size={15}/>Cerca duplicati</a>
          <a href="/preventivi/"><CreditCard size={15}/>Preventivi e incarichi</a>
        </div>
      </Panel>
    </aside>
  )
}

export function NuovoClientePage() {
  const [data, setData] = useState<ClientiNuovoData>(emptyClientiNuovoData)
  const [tab, setTab] = useState<Tab>(initialTab)
  const [loading, setLoading] = useState(true)
  const [clientCompleteness, setClientCompleteness] = useState<RegistryCompletenessItem[]>([])
  const [subjectCompleteness, setSubjectCompleteness] = useState<RegistryCompletenessItem[]>([])
  const refreshSequence = useRef(0)
  useOperationalRefresh(['clienti', 'soggetti'], async () => {
    const sequence = ++refreshSequence.current
    const payload = await getClientiNuovoData()
    if (sequence === refreshSequence.current && payload.source !== 'vuoto') setData(payload)
  })

  useEffect(() => {
    let alive = true
    getClientiNuovoData().then((payload) => {
      if (!alive) return
      setData(payload)
      if (payload.mode === 'edit') setTab('cliente')
      else if (payload.mode === 'edit_subject' || payload.query.tab === 'soggetto') setTab('soggetto')
    }).finally(() => {
      if (alive) setLoading(false)
    })
    return () => {
      alive = false
    }
  }, [])

  const heroText = useMemo(() => {
    if (data.mode === 'edit') return 'Modifica anagrafica cliente mantenendo invariati id, collegamenti, fascicoli, preventivi e conferimenti.'
    if (data.mode === 'edit_subject') return 'Modifica soggetto o parte processuale mantenendo invariati collegamenti a cliente e fascicoli.'
    return tab === 'cliente'
      ? 'Nuova anagrafica cliente con dati fiscali, recapiti, documento, indirizzi e onboarding preventivo.'
      : 'Nuovo soggetto o parte processuale distinto dai clienti, con ruolo, fonte pubblica e dati anagrafici completi.'
  }, [data.mode, tab])
  const subjectFlowRole = data.options.subjectRoles.find((item) => item.value === data.query.ruoloSoggetto)?.label || 'controparte'

  return (
    <main className="iu-content iu-clienti-new-page">
      <section className="iu-cln-hero">
        <div>
          <a className="iu-cln-back" href={tab === 'cliente' ? '/clienti' : '/soggetti'}><ArrowLeft size={15}/>Torna all'anagrafica</a>
          <span className="iu-cln-eyebrow"><Sparkles size={14}/>Anagrafica guidata</span>
          <h1>{data.mode === 'edit' ? 'Modifica Cliente' : data.mode === 'edit_subject' ? 'Modifica Soggetto' : tab === 'cliente' ? 'Nuovo Cliente' : 'Nuovo Soggetto'}</h1>
          <p>{heroText}</p>
        </div>
        <div className="iu-cln-hero__actions">
          <a href="/clienti">Anagrafiche</a>
          <a href="/soggetti">Soggetti e parti</a>
        </div>
      </section>

      <StatsStrip data={data}/>

      <div className="iu-cln-tabs" role="group" aria-label="Scelta anagrafica">
        <button type="button" className={tab === 'cliente' ? 'is-active' : ''} aria-pressed={tab === 'cliente'} onClick={() => setTab('cliente')} disabled={data.mode === 'edit_subject'}><UserPlus size={17}/>{data.mode === 'edit' ? 'Cliente' : 'Nuovo Cliente'}</button>
        <button type="button" className={tab === 'soggetto' ? 'is-active' : ''} aria-pressed={tab === 'soggetto'} onClick={() => setTab('soggetto')} disabled={data.mode === 'edit'}><UsersRound size={17}/>{data.mode === 'edit_subject' ? 'Soggetto' : 'Nuovo Soggetto'}</button>
        <span>{loading ? 'Caricamento dati...' : 'Salvataggio sicuro attivo'}</span>
      </div>

      {data.query.idCliente && tab === 'cliente' ? (
        <section className="iu-cln-flow-alert">
          <UserCheck size={18}/>
          <div><strong>Cliente precompilato dal contesto</strong><span>Il collegamento resta modificabile prima del salvataggio.</span></div>
        </section>
      ) : null}
      {data.query.idFascicolo && tab === 'soggetto' ? (
        <section className="iu-cln-flow-alert">
          <UsersRound size={18}/>
          <div><strong>Parte collegata al fascicolo</strong><span>Salvando il soggetto lo riporti al fascicolo come {subjectFlowRole}.</span></div>
        </section>
      ) : null}

      <section className="iu-cln-layout">
        <div className="iu-cln-main">
          {tab === 'cliente' ? <ClientForm data={data} onCompleteness={setClientCompleteness}/> : <SubjectForm data={data} onCompleteness={setSubjectCompleteness}/>}
        </div>
        <QualityRail data={data} items={tab === 'cliente' ? clientCompleteness : subjectCompleteness}/>
      </section>

      <FloatingLex
        context={tab === 'cliente' ? 'nuovo-cliente' : 'nuovo-soggetto'}
        title="Lex AI anagrafiche"
        body="Posso controllare dati minimi, suggerire ruolo processuale, verificare recapiti mancanti e preparare il passaggio a preventivo, fascicolo o conferimento."
        primaryHref="#lex"
        primaryLabel="Apri Lex anagrafica"
        secondaryHref="/global-search?tipo=clienti"
        secondaryLabel="Cerca duplicati"
      />
    </main>
  )
}
