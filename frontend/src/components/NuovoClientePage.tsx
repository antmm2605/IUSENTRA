import { useCallback, useEffect, useMemo, useState, type ChangeEvent, type FormEvent, type ReactNode } from 'react'
import {
  ArrowLeft,
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
  Mail,
  Phone,
  ScanLine,
  ShieldCheck,
  Sparkles,
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
  type ClientiNuovoData,
  type RegistryOption,
} from '../clientiNuovoData'
import { redirectAfterSuccess, submitFormJson } from '../formSubmit'
import './NuovoClientePage.css'

type Tab = 'cliente' | 'soggetto'
type ClientType = 'PERSONA_FISICA' | 'PERSONA_GIURIDICA'
type ClientFormState = Record<string, string | boolean>
type SubjectFormState = Record<string, string>
type SubmitState = { saving: boolean; tone: 'success' | 'danger' | 'neutral'; message: string }
type DocumentAutofillState = { tone: 'neutral' | 'success' | 'danger'; message: string; fields: string[] }

const subjectLegalTypes = new Set(['PERSONA_GIURIDICA', 'PUBBLICA_AMMINISTRAZIONE', 'ENTE', 'CONDOMINIO', 'ASSOCIAZIONE'])

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

const clientDocumentAutofillLabels = {
  cognome: 'Cognome',
  nome: 'Nome',
  codice_fiscale: 'Codice fiscale',
  sesso: 'Sesso',
  data_nascita: 'Data di nascita',
  luogo_nascita: 'Luogo di nascita',
  provincia_nascita: 'Provincia di nascita',
  nazionalita: 'Nazionalità',
  doc_tipo: 'Tipo documento',
  doc_numero: 'Numero documento',
  doc_rilasciato_da: 'Rilasciato da',
  doc_data_rilascio: 'Data rilascio',
  doc_data_scadenza: 'Scadenza documento',
  via: 'Via residenza',
  civico: 'Civico',
  cap: 'CAP',
  comune: 'Comune',
  provincia: 'Provincia',
  nazione: 'Nazione',
  telefono: 'Telefono',
  cellulare: 'Cellulare',
  email: 'Email',
  pec: 'PEC',
} as const

type ClientDocumentAutofillField = keyof typeof clientDocumentAutofillLabels
type ClientDocumentAutofillValues = Partial<Record<ClientDocumentAutofillField, string>>

const clientDocumentAutofillOrder = Object.keys(clientDocumentAutofillLabels) as ClientDocumentAutofillField[]

const clientDocumentAutofillAliases: Record<ClientDocumentAutofillField, string[]> = {
  cognome: ['cognome', 'surname', 'last_name', 'lastName', 'family_name', 'familyName', 'primary_identifier', 'primaryIdentifier'],
  nome: ['nome', 'first_name', 'firstName', 'given_name', 'givenName', 'given_names', 'givenNames', 'secondary_identifier', 'secondaryIdentifier'],
  codice_fiscale: ['codice_fiscale', 'codiceFiscale', 'fiscal_code', 'fiscalCode', 'tax_code', 'taxCode', 'cf', 'personal_number', 'personalNumber'],
  sesso: ['sesso', 'sex', 'gender'],
  data_nascita: ['data_nascita', 'dataNascita', 'birth_date', 'birthDate', 'date_of_birth', 'dateOfBirth', 'dob'],
  luogo_nascita: ['luogo_nascita', 'luogoNascita', 'birth_place', 'birthPlace', 'place_of_birth', 'placeOfBirth', 'comune_nascita', 'comuneNascita'],
  provincia_nascita: ['provincia_nascita', 'provinciaNascita', 'birth_province', 'birthProvince', 'province_of_birth', 'provinceOfBirth', 'provincia_nascita_sigla'],
  nazionalita: ['nazionalita', 'nazionalità', 'cittadinanza', 'nationality', 'citizenship'],
  doc_tipo: ['doc_tipo', 'docTipo', 'tipo_documento', 'tipoDocumento', 'document_type', 'documentType', 'doctype', 'docType'],
  doc_numero: ['doc_numero', 'docNumero', 'numero_documento', 'numeroDocumento', 'document_number', 'documentNumber', 'document_no', 'documentNo', 'doc_number', 'docNumber'],
  doc_rilasciato_da: ['doc_rilasciato_da', 'docRilasciatoDa', 'rilasciato_da', 'rilasciatoDa', 'issuing_authority', 'issuingAuthority', 'issuer', 'authority'],
  doc_data_rilascio: ['doc_data_rilascio', 'docDataRilascio', 'data_rilascio', 'dataRilascio', 'issue_date', 'issueDate', 'date_of_issue', 'dateOfIssue'],
  doc_data_scadenza: ['doc_data_scadenza', 'docDataScadenza', 'data_scadenza', 'dataScadenza', 'scadenza_documento', 'scadenzaDocumento', 'expiry_date', 'expiryDate', 'expiration_date', 'expirationDate', 'date_of_expiry', 'dateOfExpiry'],
  via: ['via', 'indirizzo', 'address', 'street', 'street_name', 'streetName'],
  civico: ['civico', 'numero_civico', 'numeroCivico', 'house_number', 'houseNumber', 'street_number', 'streetNumber'],
  cap: ['cap', 'postal_code', 'postalCode', 'zip', 'zip_code', 'zipCode'],
  comune: ['comune', 'citta', 'città', 'city', 'municipality', 'residence_city', 'residenceCity'],
  provincia: ['provincia', 'province', 'residence_province', 'residenceProvince'],
  nazione: ['nazione', 'country', 'state', 'residence_country', 'residenceCountry'],
  telefono: ['telefono', 'phone', 'telephone', 'landline'],
  cellulare: ['cellulare', 'mobile', 'mobile_phone', 'mobilePhone'],
  email: ['email', 'mail', 'e_mail', 'eMail'],
  pec: ['pec', 'certified_email', 'certifiedEmail'],
}

declare global {
  interface Window {
    IUSENTRA_CLIENTE_NUOVO?: {
      applicaDatiDocumento: (payload: unknown) => void
    }
  }
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

function text(value: unknown): string {
  return String(value ?? '').trim()
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
  return typeof value === 'boolean' ? (value ? '1' : '0') : text(value)
}

function emptySubmitState(): SubmitState {
  return { saving: false, tone: 'neutral', message: '' }
}

function emptyDocumentAutofillState(): DocumentAutofillState {
  return {
    tone: 'neutral',
    message: 'In attesa della lettura del documento. I dati riconosciuti compileranno solo i campi liberi.',
    fields: [],
  }
}

function normalizeScanKey(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9]/g, '')
    .toLowerCase()
}

function flattenScanPayload(value: unknown, output = new Map<string, string>()): Map<string, string> {
  if (Array.isArray(value)) {
    value.forEach((item) => flattenScanPayload(item, output))
    return output
  }
  if (!isRecord(value)) return output
  Object.entries(value).forEach(([key, item]) => {
    const normalized = normalizeScanKey(key)
    if (isRecord(item) || Array.isArray(item)) {
      flattenScanPayload(item, output)
      return
    }
    const content = text(item)
    if (content && !output.has(normalized)) output.set(normalized, content)
  })
  return output
}

function firstScanValue(payload: Map<string, string>, aliases: string[]): string {
  for (const alias of aliases) {
    const value = payload.get(normalizeScanKey(alias))
    if (value) return value
  }
  return ''
}

function parseDateParts(year: number, month: number, day: number): string {
  if (year < 1900 || month < 1 || month > 12 || day < 1 || day > 31) return ''
  const date = new Date(Date.UTC(year, month - 1, day))
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return ''
  return `${year.toString().padStart(4, '0')}-${month.toString().padStart(2, '0')}-${day.toString().padStart(2, '0')}`
}

function normalizeScanDate(value: string, mode: 'birth' | 'document' = 'document'): string {
  const raw = text(value)
  if (!raw) return ''
  const iso = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (iso) return parseDateParts(Number(iso[1]), Number(iso[2]), Number(iso[3]))
  const italian = raw.match(/^(\d{1,2})[/. -](\d{1,2})[/. -](\d{2,4})$/)
  if (italian) {
    let year = Number(italian[3].length === 2 ? `20${italian[3]}` : italian[3])
    if (mode === 'birth' && italian[3].length === 2) {
      const candidate = new Date(Date.UTC(year, Number(italian[2]) - 1, Number(italian[1])))
      if (candidate.getTime() > Date.now()) year -= 100
    }
    return parseDateParts(year, Number(italian[2]), Number(italian[1]))
  }
  const compact = raw.replace(/\D/g, '')
  if (compact.length === 8) return parseDateParts(Number(compact.slice(0, 4)), Number(compact.slice(4, 6)), Number(compact.slice(6, 8)))
  if (compact.length !== 6) return ''
  const today = new Date()
  let year = 2000 + Number(compact.slice(0, 2))
  const month = Number(compact.slice(2, 4))
  const day = Number(compact.slice(4, 6))
  if (mode === 'birth') {
    const candidate = new Date(Date.UTC(year, month - 1, day))
    if (candidate.getTime() > today.getTime()) year -= 100
  }
  return parseDateParts(year, month, day)
}

function titleCaseScanValue(value: string): string {
  const cleaned = text(value).replace(/</g, ' ').replace(/\s+/g, ' ')
  if (!cleaned) return ''
  return cleaned
    .toLocaleLowerCase('it-IT')
    .replace(/(^|\s|')([a-zàèéìòù])/g, (match) => match.toLocaleUpperCase('it-IT'))
}

function normalizeScanGender(value: string): string {
  const raw = text(value).toUpperCase()
  if (['M', 'MASCHIO', 'MASCHILE', 'MALE', '1'].includes(raw)) return 'M'
  if (['F', 'FEMMINA', 'FEMMINILE', 'FEMALE', '2'].includes(raw)) return 'F'
  return ''
}

function normalizeNationality(value: string): string {
  const raw = text(value)
  const normalized = raw.toUpperCase()
  if (['ITA', 'IT', 'ITALIA', 'ITALIANA', 'ITALIAN'].includes(normalized)) return 'Italiana'
  return titleCaseScanValue(raw)
}

function normalizeDocumentType(value: string): string {
  const raw = text(value).toUpperCase().replace(/[\s-]+/g, '_')
  if (!raw) return ''
  if (raw.startsWith('P') || raw.includes('PASSAP')) return 'PASSAPORTO'
  if (raw.includes('PATENTE') || raw.includes('DRIVING') || raw.includes('LICENSE')) return 'PATENTE'
  if (raw.includes('SOGGIORNO') || raw.includes('RESIDENCE_PERMIT')) return 'PERMESSO_SOGGIORNO'
  if (raw.startsWith('I') || raw.includes('IDENT') || raw.includes('CIE') || raw.includes('CARTA')) return 'CARTA_IDENTITA'
  return ''
}

function cleanMrzToken(value: string): string {
  return text(value).replace(/</g, ' ').replace(/\s+/g, ' ').trim()
}

function parseMrzNames(value: string): Pick<ClientDocumentAutofillValues, 'cognome' | 'nome'> {
  const [surname = '', names = ''] = value.split('<<')
  return {
    cognome: titleCaseScanValue(cleanMrzToken(surname)),
    nome: titleCaseScanValue(cleanMrzToken(names)),
  }
}

function parseMrzPayload(rawValue: string): ClientDocumentAutofillValues {
  const lines = text(rawValue).toUpperCase().split(/\r?\n|\|/).map((line) => line.trim()).filter((line) => line.includes('<'))
  if (!lines.length) return {}
  if (lines[0].startsWith('P<') && lines.length >= 2) {
    const names = parseMrzNames(lines[0].slice(5))
    return {
      ...names,
      doc_tipo: 'PASSAPORTO',
      doc_numero: cleanMrzToken(lines[1].slice(0, 9)).replace(/\s/g, ''),
      nazionalita: normalizeNationality(lines[1].slice(10, 13)),
      data_nascita: normalizeScanDate(lines[1].slice(13, 19), 'birth'),
      sesso: normalizeScanGender(lines[1].slice(20, 21)),
      doc_data_scadenza: normalizeScanDate(lines[1].slice(21, 27), 'document'),
    }
  }
  if (lines.length >= 3) {
    const names = parseMrzNames(lines[2])
    return {
      ...names,
      doc_tipo: normalizeDocumentType(lines[0].slice(0, 1)) || 'CARTA_IDENTITA',
      doc_numero: cleanMrzToken(lines[0].slice(5, 14)).replace(/\s/g, ''),
      data_nascita: normalizeScanDate(lines[1].slice(0, 6), 'birth'),
      sesso: normalizeScanGender(lines[1].slice(7, 8)),
      doc_data_scadenza: normalizeScanDate(lines[1].slice(8, 14), 'document'),
      nazionalita: normalizeNationality(lines[1].slice(15, 18)),
    }
  }
  return {}
}

function normalizeDocumentAutofillValue(field: ClientDocumentAutofillField, value: string): string {
  if (!text(value)) return ''
  if (field === 'doc_tipo') return normalizeDocumentType(value)
  if (field === 'data_nascita') return normalizeScanDate(value, 'birth')
  if (field === 'doc_data_rilascio' || field === 'doc_data_scadenza') return normalizeScanDate(value, 'document')
  if (field === 'sesso') return normalizeScanGender(value)
  if (field === 'nazionalita') return normalizeNationality(value)
  if (['codice_fiscale', 'provincia_nascita', 'provincia', 'doc_numero'].includes(field)) return text(value).toUpperCase()
  if (field === 'email' || field === 'pec') return text(value).toLocaleLowerCase('it-IT')
  if (field === 'nome' || field === 'cognome' || field === 'luogo_nascita' || field === 'comune' || field === 'nazione') return titleCaseScanValue(value)
  return text(value)
}

function normalizeClientDocumentScan(payload: unknown): ClientDocumentAutofillValues {
  const flat = flattenScanPayload(payload)
  const mrz = parseMrzPayload(firstScanValue(flat, ['mrz', 'mrz_raw', 'raw_mrz', 'rawMrz', 'machine_readable_zone', 'machineReadableZone']))
  const result: ClientDocumentAutofillValues = { ...mrz }

  clientDocumentAutofillOrder.forEach((field) => {
    const raw = firstScanValue(flat, clientDocumentAutofillAliases[field])
    const normalized = normalizeDocumentAutofillValue(field, raw)
    if (normalized) result[field] = normalized
  })

  const fullName = firstScanValue(flat, ['nome_completo', 'nomeCompleto', 'full_name', 'fullName'])
  if (fullName && fullName.includes(',')) {
    const [surname, names] = fullName.split(',', 2)
    if (!result.cognome) result.cognome = titleCaseScanValue(surname)
    if (!result.nome) result.nome = titleCaseScanValue(names)
  }

  return Object.fromEntries(Object.entries(result).filter(([, value]) => text(value))) as ClientDocumentAutofillValues
}

function shouldApplyDocumentField(current: ClientFormState, field: ClientDocumentAutofillField, value: string, touchedFields: Set<string>): boolean {
  const currentValue = asInputValue(current[field])
  if (!currentValue) return true
  if (currentValue === value) return false
  if (touchedFields.has(field)) return false
  const initialValue = asInputValue(initialClient[field])
  return Boolean(initialValue && currentValue === initialValue)
}

function applyClientDocumentAutofill(
  current: ClientFormState,
  incoming: ClientDocumentAutofillValues,
  touchedFields: Set<string>,
): { next: ClientFormState; applied: string[]; kept: string[] } {
  const next = { ...current }
  const applied: string[] = []
  const kept: string[] = []

  clientDocumentAutofillOrder.forEach((field) => {
    const value = normalizeDocumentAutofillValue(field, incoming[field] || '')
    if (!value) return
    const currentValue = asInputValue(current[field])
    if (shouldApplyDocumentField(current, field, value, touchedFields)) {
      next[field] = value
      applied.push(clientDocumentAutofillLabels[field])
    } else if (currentValue && currentValue !== value) {
      kept.push(clientDocumentAutofillLabels[field])
    }
  })

  return { next, applied, kept }
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
      <article><Building2 size={20}/><span>Persone giuridiche</span><strong>{data.stats.legalClients}</strong><small>Societa ed enti</small></article>
      <article><ClipboardCheck size={20}/><span>Da completare</span><strong>{data.stats.missingRegistry}</strong><small>{data.stats.expiredDocuments} documenti scaduti</small></article>
    </section>
  )
}

function DocumentAutofillPanel({ state }:{ state: DocumentAutofillState }) {
  const hasFields = state.fields.length > 0
  return (
    <section className={`iu-cln-doc-hook iu-cln-doc-hook--${state.tone}`} aria-label="Lettura automatica documento">
      <div className="iu-cln-doc-hook__icon"><Camera size={19}/></div>
      <div className="iu-cln-doc-hook__body">
        <strong>Lettura documento pronta</strong>
        <span>{state.message}</span>
        <small>
          {hasFields
            ? `Campi compilati: ${state.fields.join(', ')}.`
            : 'Pronta per CF, nome, cognome, nascita, documento, scadenza, indirizzo e recapiti quando disponibili.'}
        </small>
      </div>
      <Badge tone={hasFields ? 'success' : 'info'}>{hasFields ? 'Dati applicati' : 'In attesa'}</Badge>
    </section>
  )
}

function ClientForm({ data }:{data: ClientiNuovoData}) {
  const [values, setValues] = useState<ClientFormState>({...initialClient})
  const [touchedFields, setTouchedFields] = useState<Set<string>>(() => new Set())
  const [cfStatus, setCfStatus] = useState('')
  const [documentAutofill, setDocumentAutofill] = useState<DocumentAutofillState>(() => emptyDocumentAutofillState())
  const [submitState, setSubmitState] = useState<SubmitState>(() => emptySubmitState())
  const action = data.actions.operationalClientForm
  const isPhysical = values.tipo === 'PERSONA_FISICA'
  const nextUrl = data.query.nextUrl

  useEffect(() => {
    if (data.mode !== 'edit') return
    setValues({...initialClient, ...data.initialClient})
  }, [data])

  useEffect(() => {
    if (nextUrl) setValues((current) => ({...current, next_url: nextUrl}))
  }, [nextUrl])

  const applyRecognizedDocument = useCallback((payload: unknown) => {
    const incoming = normalizeClientDocumentScan(payload)
    if (!Object.keys(incoming).length) {
      setDocumentAutofill({
        tone: 'danger',
        message: 'La lettura non contiene ancora dati utilizzabili per questa anagrafica.',
        fields: [],
      })
      return
    }

    const result = applyClientDocumentAutofill(values, incoming, touchedFields)
    const applied = result.applied
    const kept = result.kept
    setValues(result.next)

    if (applied.length) {
      setDocumentAutofill({
        tone: 'success',
        message: kept.length
          ? 'Dati riconosciuti applicati. I campi già modificati sono stati lasciati invariati.'
          : 'Dati riconosciuti applicati automaticamente.',
        fields: applied,
      })
      return
    }

    setDocumentAutofill({
      tone: 'neutral',
      message: kept.length
        ? 'I dati riconosciuti coincidono con campi già compilati o modificati.'
        : 'Nessun campo nuovo da compilare.',
      fields: [],
    })
  }, [touchedFields, values])

  useEffect(() => {
    if (typeof window === 'undefined') return undefined
    const handler = (event: Event) => {
      applyRecognizedDocument((event as CustomEvent<unknown>).detail)
    }
    window.addEventListener('iusentra:cliente-documento-rilevato', handler)
    window.IUSENTRA_CLIENTE_NUOVO = { applicaDatiDocumento: applyRecognizedDocument }
    return () => {
      window.removeEventListener('iusentra:cliente-documento-rilevato', handler)
      if (window.IUSENTRA_CLIENTE_NUOVO?.applicaDatiDocumento === applyRecognizedDocument) {
        delete window.IUSENTRA_CLIENTE_NUOVO
      }
    }
  }, [applyRecognizedDocument])

  useEffect(() => {
    const code = text(values.codice_fiscale).replace(/\s/g, '').toUpperCase()
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
        setCfStatus('Dati di nascita compilati dal codice fiscale.')
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

  const change = (name: string, value: string) => {
    setTouchedFields((current) => new Set(current).add(name))
    setValues((current) => ({...current, [name]: name.includes('codice') || name.includes('partita') || name.includes('provincia') || name === 'doc_numero' ? value.toUpperCase() : value}))
  }
  const checkbox = (event: ChangeEvent<HTMLInputElement>) => {
    setTouchedFields((current) => new Set(current).add(event.currentTarget.name))
    setValues((current) => ({...current, [event.currentTarget.name]: event.currentTarget.checked}))
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
      const result = await submitFormJson(action, new FormData(event.currentTarget))
      setSubmitState({ saving: false, tone: 'success', message: result.message || 'Cliente salvato.' })
      redirectAfterSuccess(result, data.mode === 'edit' && data.query.idCliente ? `/clienti/${encodeURIComponent(data.query.idCliente)}` : '/clienti')
    } catch (error) {
      setSubmitState({ saving: false, tone: 'danger', message: error instanceof Error ? error.message : 'Salvataggio non riuscito.' })
    }
  }

  return (
    <form className="iu-cln-form" onSubmit={handleSubmit}>
      <input type="hidden" name="next_url" value={asInputValue(values.next_url)}/>
      <Card title="Tipo cliente" icon={<UserCheck size={18}/>} note={data.mode === 'edit' ? 'Aggiornamento anagrafica esistente' : 'Nuova anagrafica governata'}>
        <ChoiceGrid name="tipo" value={asInputValue(values.tipo)} options={data.options.clientTypes} onChange={change}/>
      </Card>

      {isPhysical ? <DocumentAutofillPanel state={documentAutofill}/> : null}

      <Card title={isPhysical ? 'Dati persona fisica' : 'Dati persona giuridica'} icon={isPhysical ? <UserRound size={18}/> : <Building2 size={18}/>} note="Campi coerenti con l'anagrafica dello studio">
        {isPhysical ? (
          <div className="iu-cln-grid">
            <Field label="Cognome" name="cognome" value={asInputValue(values.cognome)} required placeholder="Rossi" onChange={change}/>
            <Field label="Nome" name="nome" value={asInputValue(values.nome)} required placeholder="Mario" onChange={change}/>
            <SelectField label="Sesso" name="sesso" value={asInputValue(values.sesso)} required onChange={change} options={[{value: '', label: '-'}, {value: 'M', label: 'Maschile'}, {value: 'F', label: 'Femminile'}]}/>
            <Field label="Codice fiscale" name="codice_fiscale" value={asInputValue(values.codice_fiscale)} placeholder="RSSMRA80A01H501Z" mono onChange={change}>
              <button className="iu-cln-mini-action" type="button" onClick={generateNow}>Genera CF</button>
            </Field>
            <Field label="Data di nascita" name="data_nascita" type="date" value={asInputValue(values.data_nascita)} onChange={change}/>
            <Field label="Luogo di nascita" name="luogo_nascita" value={asInputValue(values.luogo_nascita)} placeholder="Roma" onChange={change}/>
            <Field label="Provincia nascita" name="provincia_nascita" value={asInputValue(values.provincia_nascita)} placeholder="RM" mono onChange={change}/>
            <Field label="Nazionalita" name="nazionalita" value={asInputValue(values.nazionalita)} placeholder="Italiana" onChange={change}/>
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
          <Field label="Comune" name={isPhysical ? 'comune' : 'sl_comune'} value={asInputValue(values[isPhysical ? 'comune' : 'sl_comune'])} onChange={change}/>
          <Field label="Provincia" name={isPhysical ? 'provincia' : 'sl_provincia'} value={asInputValue(values[isPhysical ? 'provincia' : 'sl_provincia'])} mono onChange={change}/>
          <Field label="Nazione" name={isPhysical ? 'nazione' : 'sl_nazione'} value={asInputValue(values[isPhysical ? 'nazione' : 'sl_nazione'])} onChange={change}/>
          {isPhysical ? (
            <>
              <Field label="Domicilio via" name="dom_via" value={asInputValue(values.dom_via)} onChange={change}/>
              <Field label="Domicilio comune" name="dom_comune" value={asInputValue(values.dom_comune)} onChange={change}/>
              <Field label="Domicilio provincia" name="dom_provincia" value={asInputValue(values.dom_provincia)} mono onChange={change}/>
            </>
          ) : null}
        </div>
      </Card>

      <Card title="Documento e studio" icon={<FileText size={18}/>} note="Documento salvato dal servizio anagrafico esteso">
        <div className="iu-cln-grid">
          <SelectField label="Tipo documento" name="doc_tipo" value={asInputValue(values.doc_tipo)} options={data.options.documentTypes} onChange={change}/>
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
        <button className="iu-cln-submit" type="submit" disabled={submitState.saving}><CheckCircle2 size={17}/>{submitState.saving ? 'Salvataggio...' : data.mode === 'edit' ? 'Salva modifiche' : 'Salva cliente'}</button>
        <a className="iu-cln-secondary" href={data.mode === 'edit' && data.query.idCliente ? `/clienti/${encodeURIComponent(data.query.idCliente)}/cartella` : '/clienti'}>Annulla</a>
      </div>
    </form>
  )
}

function SubjectForm({ data }:{data: ClientiNuovoData}) {
  const [values, setValues] = useState<SubjectFormState>({...initialSubject})
  const [cfStatus, setCfStatus] = useState('')
  const [submitState, setSubmitState] = useState<SubmitState>(() => emptySubmitState())
  const action = data.actions.operationalSubjectForm
  const isLegal = subjectLegalTypes.has(values.tipo)

  useEffect(() => {
    if (data.mode === 'edit_subject') {
      setValues({ ...initialSubject, ...data.initialSubject })
      return
    }
    if (data.query.idCliente) setValues((current) => ({...current, id_cliente: data.query.idCliente}))
  }, [data.mode, data.initialSubject, data.query.idCliente])

  useEffect(() => {
    const code = text(values.codice_fiscale).replace(/\s/g, '').toUpperCase()
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
        setCfStatus('Dati di nascita compilati dal codice fiscale.')
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

  const change = (name: string, value: string) => {
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

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitState({ saving: true, tone: 'neutral', message: 'Salvataggio in corso...' })
    try {
      const result = await submitFormJson(action, new FormData(event.currentTarget))
      setSubmitState({ saving: false, tone: 'success', message: result.message || 'Soggetto salvato.' })
      redirectAfterSuccess(result, data.mode === 'edit_subject' && data.query.idSoggetto ? `/soggetti/${encodeURIComponent(data.query.idSoggetto)}` : '/soggetti')
    } catch (error) {
      setSubmitState({ saving: false, tone: 'danger', message: error instanceof Error ? error.message : 'Salvataggio non riuscito.' })
    }
  }

  return (
    <form className="iu-cln-form" onSubmit={handleSubmit}>
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

      <Card title="Collegamenti e qualifica" icon={<UserCheck size={18}/>} note="Cliente collegato e dati professionali">
        <div className="iu-cln-grid">
          <label className="iu-cln-field is-wide">
            <span>Cliente collegato</span>
            <select name="id_cliente" value={values.id_cliente} onChange={(event) => change('id_cliente', event.currentTarget.value)}>
              <option value="">Nessun cliente collegato</option>
              {data.clientOptions.map((cliente) => <option value={cliente.id} key={cliente.id}>{cliente.label}{cliente.taxCode ? ` - ${cliente.taxCode}` : ''}</option>)}
            </select>
          </label>
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
          <Field label="Comune" name="comune" value={values.comune} onChange={change}/>
          <Field label="Provincia" name="provincia" value={values.provincia} mono onChange={change}/>
          <Field label="Nazione" name="nazione" value={values.nazione} onChange={change}/>
          <TextAreaField label="Note" name="note" value={values.note} onChange={change}/>
        </div>
      </Card>

      <SubmitFeedback state={submitState}/>
      <div className="iu-cln-actions">
        <button className="iu-cln-submit" type="submit" disabled={submitState.saving}><CheckCircle2 size={17}/>{submitState.saving ? 'Salvataggio...' : data.mode === 'edit_subject' ? 'Salva modifiche' : 'Salva soggetto'}</button>
        <a className="iu-cln-secondary" href={data.mode === 'edit_subject' && data.query.idSoggetto ? `/soggetti/${encodeURIComponent(data.query.idSoggetto)}` : '/soggetti'}>Annulla</a>
      </div>
    </form>
  )
}

function QualityRail({ data, activeTab }:{data: ClientiNuovoData; activeTab: Tab}) {
  const checkItems = activeTab === 'cliente'
    ? ['Dati fiscali verificati', 'Almeno un recapito presente', 'Indirizzo utile al conferimento', 'Documento identita controllato']
    : ['Ruolo processuale assegnato', 'Cliente collegato se pertinente', 'Recapiti della parte completi', 'Qualifica coerente con il fascicolo']
  return (
    <aside className="iu-cln-rail">
      <Panel title="Qualita anagrafica" icon={<BadgeCheck size={17}/>} count={checkItems.length}>
        <div className="iu-cln-checklist">
          {checkItems.map((item) => <span key={item}><CheckCircle2 size={15}/>{item}</span>)}
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

  useEffect(() => {
    let alive = true
    getClientiNuovoData().then((payload) => {
      if (!alive) return
      setData(payload)
      if (payload.query.tab === 'soggetto') setTab('soggetto')
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
      : 'Nuovo soggetto o parte processuale con ruolo, collegamento cliente e dati anagrafici completi.'
  }, [data.mode, tab])

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

      <div className="iu-cln-tabs" role="tablist" aria-label="Scelta anagrafica">
        <button type="button" className={tab === 'cliente' ? 'is-active' : ''} onClick={() => setTab('cliente')} disabled={data.mode === 'edit_subject'}><UserPlus size={17}/>{data.mode === 'edit' ? 'Cliente' : 'Nuovo Cliente'}</button>
        <button type="button" className={tab === 'soggetto' ? 'is-active' : ''} onClick={() => setTab('soggetto')} disabled={data.mode === 'edit'}><UsersRound size={17}/>{data.mode === 'edit_subject' ? 'Soggetto' : 'Nuovo Soggetto'}</button>
        <span>{loading ? 'Caricamento dati...' : 'Salvataggio sicuro attivo'}</span>
      </div>

      {data.query.idCliente ? (
        <section className="iu-cln-flow-alert">
          <UserCheck size={18}/>
          <div><strong>Cliente precompilato dal contesto</strong><span>Il collegamento resta modificabile prima del salvataggio.</span></div>
        </section>
      ) : null}

      <section className="iu-cln-layout">
        <div className="iu-cln-main">
          {tab === 'cliente' ? <ClientForm data={data}/> : <SubjectForm data={data}/>}
        </div>
        <QualityRail data={data} activeTab={tab}/>
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
