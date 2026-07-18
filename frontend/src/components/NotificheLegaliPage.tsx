import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  FileDown,
  FileCheck2,
  FileSignature,
  FileText,
  FolderOpen,
  ExternalLink,
  Inbox,
  Info,
  LockKeyhole,
  Mail,
  PencilLine,
  PlusCircle,
  RefreshCw,
  RotateCcw,
  Save,
  Scale,
  Search,
  Send,
  ShieldCheck,
  Paperclip,
  Trash2,
  UploadCloud,
  UserRound,
  WandSparkles,
  X,
} from 'lucide-react'
import { Button, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import {
  emptyNotificheLegaliData,
  confirmLegalPublicRegister,
  downloadLegalAttestation,
  getNotificheLegaliData,
  getNotificheLegaliPractice,
  getNotificheLegaliPracticeDocuments,
  postLegalWorkflow,
  previewLegalRelata,
  saveLegalRelataDraft,
  saveLegalRelataTemplate,
  type LegalAutomationStep,
  type LegalDocumentSuggestion,
  type LegalNotificationDirective,
  type LegalRelataPreviewResult,
  type LegalPracticeIndexItem,
  type LegalPracticeSuggestion,
  type LegalRecipientSuggestion,
  type LegalTemplateFieldToken,
  type LegalUnepOffice,
  type LegalWorkflowResult,
  type NotificheLegaliData,
} from '../notificheLegaliData'
import { formatDateIt } from '../formatting'
import './NotificheLegaliPage.css'

type TabKey = 'notifica' | 'deposito' | 'unep' | 'nonpec' | 'cliente'

type NotificaDocumentPayload = {
  nome_file: string
  descrizione: string
  origine: string
  hash_sha256: string
  data_comunicazione_cancelleria: string
  fonte_documento?: string
  riferimento_portale?: string
  file_originale?: string
  servizio_portale?: string
  documento_ufficio?: boolean
  acquisito_da_portale?: boolean
  notifica_richiesta?: boolean
  data_rilascio_portale?: string
  attestazione_conformita?: string
  attestazione_conformita_presente?: boolean
}

type ManualNotificationDocument = NotificaDocumentPayload & {
  id: string
}

type EvidenceDocumentPayload = {
  nome_file: string
  descrizione: string
  origine: string
  hash_sha256: string
  riferimento_portale: string
  file_originale: string
}

type DepositEvidenceKind = 'atto' | 'relata' | 'pec' | 'rac' | 'rdac'

const emptyResult: LegalWorkflowResult = {
  ok: false,
  blockers: [],
  warnings: [],
  subject: '',
  body: '',
  relataText: '',
  nextActions: [],
  templateId: '',
  templateLabel: '',
  templateVersion: '',
  selectedBlocks: [],
  checklistText: '',
  logJson: {},
  outputPlan: {},
}

const emptyRelataPreview: LegalRelataPreviewResult = {
  ok: false,
  previewText: '',
  missingFields: [],
  warnings: [],
  blockers: [],
  templateId: '',
  templateLabel: '',
}

function todayLocalDate() {
  const now = new Date()
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset())
  return now.toISOString().slice(0, 10)
}

function currentLocalTime() {
  return new Intl.DateTimeFormat('it-IT', {
    timeZone: 'Europe/Rome',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date())
}

function localDateTime() {
  const now = new Date()
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset())
  return now.toISOString().slice(0, 19)
}

function localClockLabel(value: string) {
  const parsed = value ? new Date(value) : new Date()
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('it-IT', {
    timeZone: 'Europe/Rome',
    weekday: 'long',
    day: '2-digit',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(parsed)
}

function templateVersionDate(value: string) {
  const match = String(value || '').trim().match(/^(\d{4})[.-](\d{2})[.-](\d{2})(?:\b|[-_])/)
  if (!match) return ''
  const [, year, month, day] = match
  return formatDateIt(`${year}-${month}-${day}`)
}

function templateVersionLabel(value: string) {
  const date = templateVersionDate(value)
  return date ? ` · aggiornato il ${date}` : ''
}

function userFacingNotice(value: string) {
  return String(value || '')
    .replace(/^[A-Z0-9_]+:\s*/, '')
    .replace(/\b(?:QuickOrganizer|Studio\s+Telematico)\b/gi, 'gestionale precedente')
    .replace(/\bhash SHA-256\b/gi, 'impronta del file')
    .replace(/\bSHA-256\b/g, 'impronta del file')
    .replace(/\bDatiAtto\.xml\b/g, 'riepilogo del deposito')
    .replace(/\bTAVOLA\b/g, 'prospetto dati')
    .replace(/\bRAC\b/g, 'ricevuta di accettazione')
    .replace(/\bRdAC\b/g, 'ricevuta di consegna')
    .trim()
}

function Field({
  label,
  children,
  wide = false,
  hint,
}: {
  label: string
  children: ReactNode
  wide?: boolean
  hint?: string
}) {
  return (
    <label className={`iu-legal-field ${wide ? 'iu-legal-field--wide' : ''}`}>
      <span>{label}</span>
      {children}
      {hint ? <small>{hint}</small> : null}
    </label>
  )
}

function practiceSearchText(value: string) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase('it-IT')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
}

function PracticePicker({
  practices,
  value,
  loading,
  message,
  hint,
  onSelect,
}: {
  practices: LegalPracticeIndexItem[]
  value: string
  loading: boolean
  message: string
  hint: string
  onSelect: (practiceId: string) => void
}) {
  const inputId = useId()
  const listId = `${inputId}-risultati`
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const selected = useMemo(() => practices.find((item) => item.id === value), [practices, value])
  const indexedPractices = useMemo(() => practices.map((item) => ({
    item,
    search: practiceSearchText([
      item.label,
      item.numero,
      item.titolo,
      item.assistitoNome,
      item.controparte,
      item.ufficio,
      item.numeroRg,
      item.annoRg,
      item.oggetto,
    ].join(' ')),
  })), [practices])
  const matches = useMemo(() => {
    const tokens = practiceSearchText(query).split(' ').filter(Boolean)
    if (!tokens.length) return indexedPractices.map(({ item }) => item)
    return indexedPractices
      .filter(({ search }) => tokens.every((token) => search.includes(token)))
      .map(({ item }) => item)
  }, [indexedPractices, query])
  const visibleMatches = matches.slice(0, 50)

  const choose = (practice: LegalPracticeIndexItem) => {
    onSelect(practice.id)
    setQuery('')
    setOpen(false)
    setActiveIndex(0)
  }

  return (
    <div className="iu-legal-field iu-legal-field--wide iu-legal-practice-picker">
      <label htmlFor={inputId}>Pratica IUSENTRA</label>
      {selected ? (
        <div className="iu-legal-practice-picker__selected">
          <CheckCircle2 size={17} />
          <span>
            <strong>{selected.label}</strong>
            <small>{[
              selected.numeroRg ? `RG ${selected.numeroRg}${selected.annoRg ? `/${selected.annoRg}` : ''}` : '',
              selected.assistitoNome,
              selected.ufficio,
              selected.archiviata ? 'Archiviata' : '',
            ].filter(Boolean).join(' - ')}</small>
          </span>
          <button type="button" aria-label="Rimuovi pratica selezionata" title="Rimuovi pratica selezionata" onClick={() => onSelect('')}>
            <X size={16} />
          </button>
        </div>
      ) : null}
      <div className="iu-legal-practice-picker__input">
        {loading ? <RefreshCw className="is-spinning" size={17} /> : <Search size={17} />}
        <input
          id={inputId}
          type="search"
          value={query}
          autoComplete="off"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={listId}
          aria-activedescendant={open && visibleMatches[activeIndex] ? `${listId}-${visibleMatches[activeIndex].id}` : undefined}
          placeholder={selected ? 'Cerca un’altra pratica' : 'Cerca per numero, RG, cliente o oggetto'}
          onFocus={() => setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 140)}
          onChange={(event) => {
            setQuery(event.currentTarget.value)
            setActiveIndex(0)
            setOpen(true)
          }}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown') {
              event.preventDefault()
              setOpen(true)
              setActiveIndex((current) => Math.min(current + 1, Math.max(visibleMatches.length - 1, 0)))
            } else if (event.key === 'ArrowUp') {
              event.preventDefault()
              setActiveIndex((current) => Math.max(current - 1, 0))
            } else if (event.key === 'Enter' && open && visibleMatches[activeIndex]) {
              event.preventDefault()
              choose(visibleMatches[activeIndex])
            } else if (event.key === 'Escape') {
              setOpen(false)
            }
          }}
        />
        {query ? (
          <button type="button" aria-label="Cancella ricerca" title="Cancella ricerca" onMouseDown={(event) => event.preventDefault()} onClick={() => { setQuery(''); setActiveIndex(0) }}>
            <X size={16} />
          </button>
        ) : null}
      </div>
      {open ? (
        <div className="iu-legal-practice-picker__results" id={listId} role="listbox" aria-label="Pratiche trovate">
          <div className="iu-legal-practice-picker__status">
            <span>{query ? `${matches.length} risultati` : `${practices.length} pratiche disponibili`}</span>
            {matches.length > visibleMatches.length ? <small>Affina la ricerca per vedere altri risultati.</small> : null}
          </div>
          {visibleMatches.map((item, index) => (
            <button
              type="button"
              role="option"
              aria-selected={item.id === value}
              id={`${listId}-${item.id}`}
              className={`${index === activeIndex ? 'is-active' : ''} ${item.id === value ? 'is-selected' : ''}`}
              key={item.id}
              onMouseDown={(event) => event.preventDefault()}
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => choose(item)}
            >
              <strong>{item.label}</strong>
              <span>{[
                item.numeroRg ? `RG ${item.numeroRg}${item.annoRg ? `/${item.annoRg}` : ''}` : '',
                item.assistitoNome,
                item.controparte,
                item.ufficio,
              ].filter(Boolean).join(' - ') || 'Dati pratica disponibili nel fascicolo'}</span>
              {item.archiviata ? <small>Archiviata</small> : null}
            </button>
          ))}
          {!visibleMatches.length ? <p>Nessuna pratica corrisponde alla ricerca.</p> : null}
        </div>
      ) : null}
      <small>{message || hint}</small>
    </div>
  )
}

function UnepOfficePicker({
  offices,
  value,
  onSelect,
}: {
  offices: LegalUnepOffice[]
  value: string
  onSelect: (office: LegalUnepOffice | null) => void
}) {
  const inputId = useId()
  const listId = `${inputId}-risultati`
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const selected = useMemo(() => offices.find((item) => item.codice === value || item.id === value), [offices, value])
  const matches = useMemo(() => {
    const tokens = practiceSearchText(query).split(' ').filter(Boolean)
    if (!tokens.length) return offices
    return offices.filter((office) => {
      const search = practiceSearchText([
        office.nome,
        office.codice,
        office.pec,
        office.distretto,
        office.comune,
        office.provincia,
        office.regione,
      ].join(' '))
      return tokens.every((token) => search.includes(token))
    })
  }, [offices, query])
  const visibleMatches = matches.slice(0, 60)

  const choose = (office: LegalUnepOffice) => {
    onSelect(office)
    setQuery('')
    setOpen(false)
    setActiveIndex(0)
  }

  return (
    <div className="iu-legal-field iu-legal-field--wide iu-legal-practice-picker">
      <label htmlFor={inputId}>Ufficio UNEP</label>
      {selected ? (
        <div className="iu-legal-practice-picker__selected">
          <CheckCircle2 size={17} />
          <span>
            <strong>{selected.nome}</strong>
            <small>{[selected.distretto, selected.pec, selected.codice ? `Codice ${selected.codice}` : ''].filter(Boolean).join(' - ')}</small>
          </span>
          <button type="button" aria-label="Rimuovi ufficio UNEP" title="Rimuovi ufficio UNEP" onClick={() => onSelect(null)}>
            <X size={16} />
          </button>
        </div>
      ) : null}
      <div className="iu-legal-practice-picker__input">
        <Search size={17} />
        <input
          id={inputId}
          type="search"
          value={query}
          autoComplete="off"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={listId}
          aria-activedescendant={open && visibleMatches[activeIndex] ? `${listId}-${visibleMatches[activeIndex].id}` : undefined}
          placeholder={selected ? 'Cerca un altro ufficio' : 'Cerca per ufficio, città, distretto, codice o PEC'}
          onFocus={() => setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 140)}
          onChange={(event) => {
            setQuery(event.currentTarget.value)
            setActiveIndex(0)
            setOpen(true)
          }}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown') {
              event.preventDefault()
              setOpen(true)
              setActiveIndex((current) => Math.min(current + 1, Math.max(visibleMatches.length - 1, 0)))
            } else if (event.key === 'ArrowUp') {
              event.preventDefault()
              setActiveIndex((current) => Math.max(current - 1, 0))
            } else if (event.key === 'Enter' && open && visibleMatches[activeIndex]) {
              event.preventDefault()
              choose(visibleMatches[activeIndex])
            } else if (event.key === 'Escape') {
              setOpen(false)
            }
          }}
        />
        {query ? (
          <button type="button" aria-label="Cancella ricerca" title="Cancella ricerca" onMouseDown={(event) => event.preventDefault()} onClick={() => { setQuery(''); setActiveIndex(0) }}>
            <X size={16} />
          </button>
        ) : null}
      </div>
      {open ? (
        <div className="iu-legal-practice-picker__results" id={listId} role="listbox" aria-label="Uffici UNEP trovati">
          <div className="iu-legal-practice-picker__status">
            <span>{query ? `${matches.length} risultati` : `${offices.length} uffici disponibili`}</span>
            {matches.length > visibleMatches.length ? <small>Affina la ricerca per vedere altri risultati.</small> : null}
          </div>
          {visibleMatches.map((office, index) => (
            <button
              type="button"
              role="option"
              aria-selected={office.codice === value || office.id === value}
              id={`${listId}-${office.id}`}
              className={`${index === activeIndex ? 'is-active' : ''} ${office.codice === value || office.id === value ? 'is-selected' : ''}`}
              key={office.id}
              onMouseDown={(event) => event.preventDefault()}
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => choose(office)}
            >
              <strong>{office.nome}</strong>
              <span>{[office.distretto, office.pec].filter(Boolean).join(' - ')}</span>
              <small>{[office.comune, office.provincia, office.codice].filter(Boolean).join(' - ')}</small>
            </button>
          ))}
          {!visibleMatches.length ? <p>Nessun ufficio corrisponde alla ricerca.</p> : null}
        </div>
      ) : null}
      <small>Elenco ufficiale condiviso con la sezione Tribunali e indirizzi PEC.</small>
    </div>
  )
}

const SHA256_HEX_PATTERN = /^[a-f0-9]{64}$/i

const UNEP_OFFICE_GENERIC_TOKENS = new Set([
  'tribunale', 'ordinario', 'corte', 'appello', 'giudice', 'pace', 'ufficio', 'unep', 'nep', 'di', 'della', 'del', 'sezione',
])

function suggestUnepOffice(court: string, offices: LegalUnepOffice[]): LegalUnepOffice | null {
  const courtSearch = practiceSearchText(court)
  const tokens = courtSearch.split(' ').filter((token) => token.length > 2 && !UNEP_OFFICE_GENERIC_TOKENS.has(token))
  if (!tokens.length) return null
  const courtWantsAppeal = courtSearch.includes('corte') && courtSearch.includes('appello')
  const ranked = offices.map((office) => {
    const officeSearch = practiceSearchText([office.nome, office.comune, office.provincia, office.distretto].join(' '))
    const matches = tokens.filter((token) => officeSearch.includes(token)).length
    const exactCity = practiceSearchText(office.comune)
    const cityBonus = exactCity && courtSearch.includes(exactCity) ? 8 : 0
    const kindBonus = courtWantsAppeal === officeSearch.includes('corte appello') ? 2 : 0
    return { office, score: matches * 3 + cityBonus + kindBonus }
  }).filter((item) => item.score > 0)
  ranked.sort((left, right) => right.score - left.score || left.office.nome.localeCompare(right.office.nome, 'it'))
  return ranked[0]?.office || null
}

function normalizeSha256Input(value: string) {
  return value.replace(/\s+/g, '').toLowerCase().replace(/[^a-f0-9]/g, '').slice(0, 64)
}

async function calculateSha256(file: File): Promise<string> {
  if (!window.crypto?.subtle) {
    throw new Error('sha256-unavailable')
  }
  const buffer = await file.arrayBuffer()
  const digest = await window.crypto.subtle.digest('SHA-256', buffer)
  return Array.from(new Uint8Array(digest)).map((byte) => byte.toString(16).padStart(2, '0')).join('')
}

const RELATA_LOCAL_SIGNER_RESTART_URI = 'iusentra-local-signer://restart'
const RELATA_LOCAL_SIGNER_TIMEOUT_MS = 45000

type RelataSignerToken = { slot_id?: number | string; label?: string; manufacturer?: string; model?: string }
type RelataSignerCertificate = { thumbprint?: string; soggetto?: string; scadenza?: string; codice_fiscale?: string }
type RelataSignerStatus = {
  ok?: boolean
  token?: RelataSignerToken[]
  token_probe_fresh?: RelataSignerToken[]
  certificato_windows_firma_selezionato?: RelataSignerCertificate
  certificato_windows_selezionato?: RelataSignerCertificate
  riavvio_signer_consigliato?: boolean
  nota_riavvio_signer?: string
  errore_token?: string
  messaggio?: string
  versione?: string
}

type LocalNetworkRequestInit = RequestInit & { targetAddressSpace?: 'local' }

type SignedRelataRecord = {
  documentId: string
  fileName: string
  sha256: string
  sourceSha256: string
  previewUrl: string
  downloadUrl: string
  payloadKey: string
}

type PecVerificationEvidence = {
  key: string
  source: string
  verified: boolean
  found: boolean
  address: string
  taxCode: string
  checkedAt: string
  evidenceSha256: string
  evidenceBodyBase64: string
  name: string
  status: string
  message: string
  verificationMethod: string
  confirmedBy: string
  confirmedAt: string
  consultedAt: string
  officialUrl: string
}

type PecVerificationSubject = {
  key: string
  kind: 'sender' | 'recipient'
  source: string
  address: string
  taxCode: string
  label: string
}

function normalizePecSource(value: unknown): string {
  const raw = String(value || '').trim().toLowerCase().replace(/[-.\s]+/g, '_')
  const aliases: Record<string, string> = {
    reginde: 'reginde',
    re_g_ind_e: 'reginde',
    registro_generale_indirizzi_elettronici: 'reginde',
    inipec: 'ini_pec',
    ini_pec: 'ini_pec',
    registroimprese: 'registro_imprese',
    registro_imprese: 'registro_imprese',
    imprese: 'registro_imprese',
    registro_ppaa: 'registro_ppaa',
    registro_pst: 'registro_ppaa',
    pst: 'registro_ppaa',
    ipa: 'ipa',
    inad: 'inad',
    anpr: 'anpr',
    altro: 'altro_pubblico_elenco',
    altro_pubblico_elenco: 'altro_pubblico_elenco',
  }
  return aliases[raw] || raw
}

function normalizePecIdentity(value: unknown): string {
  return String(value || '').toUpperCase().replace(/[^A-Z0-9]/g, '')
}

function normalizePecAddress(value: unknown): string {
  return String(value || '').trim().toLowerCase()
}

function pecVerificationKey(source: unknown, taxCode: unknown, address: unknown): string {
  return `${normalizePecSource(source)}|${normalizePecIdentity(taxCode)}|${normalizePecAddress(address)}`
}

function pecBoolean(value: unknown): boolean {
  return value === true || ['1', 'true', 'yes', 'si', 'sì'].includes(String(value || '').trim().toLowerCase())
}

function pecVerificationMessage(raw: Record<string, unknown>): string {
  const message = String(raw.message || '').trim()
  const detail = String(raw.error || raw.errore || '').trim()
  const combined = `${message} ${detail}`
  if (/certificato client|certificato del dispositivo|private key|chiave privata/i.test(combined)) {
    return 'Il certificato di autenticazione del dispositivo non è disponibile. Inserisci il dispositivo di firma, attendi il rilevamento e riprova.'
  }
  if (/smart card|token|dispositivo di firma|lettore/i.test(combined)) {
    return 'Il dispositivo di firma non è stato rilevato. Inseriscilo, attendi il rilevamento e riprova.'
  }
  return detail || message
}

function pecEvidenceFromResponse(raw: Record<string, unknown>, subject: PecVerificationSubject): PecVerificationEvidence {
  const source = normalizePecSource(raw.source || subject.source)
  const address = normalizePecAddress(raw.pec_attesa || raw.address || raw.pec || subject.address)
  const taxCode = normalizePecIdentity(raw.codice_fiscale || raw.taxCode || raw.codiceFiscale || subject.taxCode)
  const checkedAt = String(raw.verified_at || raw.verifiedAt || raw.checked_at || raw.checkedAt || '').trim()
  const evidenceSha256 = String(raw.evidence_sha256 || raw.evidenceSha256 || '').trim().toLowerCase()
  const evidenceBodyBase64 = String(raw.evidence_body_b64 || raw.evidenceBodyBase64 || '').trim()
  const status = String(raw.stato || raw.status || '').trim()
  const inactive = /radiat|cancellat|sospes|cessat|revocat/i.test(status)
  const exactMatch = source === subject.source
    && address === subject.address
    && (!subject.taxCode || taxCode === subject.taxCode)
  const verified = pecBoolean(raw.verified)
    && exactMatch
    && Boolean(checkedAt)
    && SHA256_HEX_PATTERN.test(evidenceSha256)
    && Boolean(evidenceBodyBase64)
    && !inactive
  return {
    key: subject.key,
    source,
    verified,
    found: pecBoolean(raw.found),
    address,
    taxCode,
    checkedAt,
    evidenceSha256,
    evidenceBodyBase64,
    name: String(raw.nome || raw.name || subject.label || '').trim(),
    status,
    message: pecVerificationMessage(raw),
    verificationMethod: String(raw.verification_method || raw.verificationMethod || '').trim(),
    confirmedBy: String(raw.confirmed_by || raw.confirmedBy || '').trim(),
    confirmedAt: String(raw.confirmed_at || raw.confirmedAt || '').trim(),
    consultedAt: String(raw.consulted_at || raw.consultedAt || '').trim(),
    officialUrl: String(raw.official_url || raw.officialUrl || '').trim(),
  }
}

function pecEvidenceMatches(evidence: PecVerificationEvidence | null | undefined, subject: PecVerificationSubject): boolean {
  return Boolean(
    evidence?.verified
    && evidence.key === subject.key
    && evidence.source === subject.source
    && evidence.address === subject.address
    && (!subject.taxCode || evidence.taxCode === subject.taxCode)
    && evidence.checkedAt
    && SHA256_HEX_PATTERN.test(evidence.evidenceSha256)
    && evidence.evidenceBodyBase64,
  )
}

function pecEvidenceTargets(evidence: PecVerificationEvidence | null | undefined, subject: PecVerificationSubject): boolean {
  return Boolean(
    evidence
    && evidence.key === subject.key
    && evidence.source === subject.source
    && evidence.address === subject.address
    && (!subject.taxCode || evidence.taxCode === subject.taxCode),
  )
}

function pecEvidencePayload(evidence: PecVerificationEvidence | null | undefined): Record<string, unknown> {
  if (!evidence) return {}
  return {
    source: evidence.source,
    verified: evidence.verified,
    found: evidence.found,
    pec_attesa: evidence.address,
    codice_fiscale: evidence.taxCode,
    checked_at: evidence.checkedAt,
    verified_at: evidence.checkedAt,
    evidence_sha256: evidence.evidenceSha256,
    evidence_body_b64: evidence.evidenceBodyBase64,
    nome: evidence.name,
    stato: evidence.status,
    verification_method: evidence.verificationMethod,
    confirmed_by: evidence.confirmedBy,
    confirmed_at: evidence.confirmedAt,
    consulted_at: evidence.consultedAt,
    official_url: evidence.officialUrl,
  }
}

function notificationControlPayloadKey(payload: Record<string, unknown>): string {
  const controlled = { ...payload }
  delete controlled.relata_firmata
  delete controlled.approvazione_avvocato
  delete controlled.data_ora_invio_pec
  delete controlled.invio_finale
  delete controlled.conferma_invio_pec
  return JSON.stringify(controlled)
}

function relataLocalSignerBaseUrl(): string {
  const configured = typeof window !== 'undefined' ? window.__IUSENTRA_LOCAL_SIGNER_URL__ : ''
  return String(configured || 'http://127.0.0.1:27272').replace(/\/+$/, '')
}

function relataLocalSignerEndpoint(path: string): string {
  const suffix = path.startsWith('/') ? path : `/${path}`
  return `${relataLocalSignerBaseUrl()}${suffix}`
}

function requestRelataLocalSignerStart(): boolean {
  if (typeof document === 'undefined') return false
  const link = document.createElement('a')
  link.href = RELATA_LOCAL_SIGNER_RESTART_URI
  link.rel = 'noreferrer'
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  window.setTimeout(() => link.remove(), 1500)
  return true
}

async function fetchRelataLocalSignerStatus(timeoutMs = 3500): Promise<RelataSignerStatus | null> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const requestOptions: LocalNetworkRequestInit = {
      cache: 'no-store',
      mode: 'cors',
      targetAddressSpace: 'local',
      signal: controller.signal,
    }
    const response = await fetch(relataLocalSignerEndpoint('/ping'), requestOptions)
    const payload = await response.json().catch(() => ({} as RelataSignerStatus))
    return { ...payload, ok: response.ok ? payload.ok : false }
  } catch {
    return null
  } finally {
    window.clearTimeout(timeout)
  }
}

function relataSignerCertificate(status?: RelataSignerStatus | null): RelataSignerCertificate | null {
  const certificate = status?.certificato_windows_firma_selezionato || status?.certificato_windows_selezionato
  return certificate?.thumbprint ? certificate : null
}

function relataSignerNeedsRestart(status?: RelataSignerStatus | null): boolean {
  return Boolean(status?.riavvio_signer_consigliato && status?.token_probe_fresh?.length && !status?.token?.length)
}

function relataSignerCanSign(status?: RelataSignerStatus | null): boolean {
  return Boolean(status?.ok !== false && !relataSignerNeedsRestart(status) && (status?.token?.[0] || relataSignerCertificate(status)))
}

function waitForRelataSigner(delayMs: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, delayMs))
}

async function ensureRelataSignerReady(): Promise<RelataSignerStatus | null> {
  let status = await fetchRelataLocalSignerStatus()
  if (status && relataSignerCanSign(status)) return status
  if (!status || relataSignerNeedsRestart(status)) requestRelataLocalSignerStart()
  for (let attempt = 0; attempt < 12; attempt += 1) {
    if (attempt > 0) await waitForRelataSigner(900)
    status = await fetchRelataLocalSignerStatus()
    if (status && relataSignerCanSign(status)) return status
  }
  return status
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  const chunkSize = 0x8000
  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize))
  }
  return btoa(binary)
}

function base64ToBytes(value: string): Uint8Array {
  const binary = atob(value)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index)
  return bytes
}

async function parseRelataSignerResponse(response: Response): Promise<Record<string, unknown>> {
  const payload = await response.json().catch(() => ({} as Record<string, unknown>))
  if (!response.ok || payload.ok === false) {
    throw new Error(String(payload.errore || payload.messaggio || `Firma non completata (HTTP ${response.status}).`))
  }
  return payload
}

async function pdfContainsPadesSignature(file: File): Promise<boolean> {
  if (!file.name.toLowerCase().endsWith('.pdf')) return false
  const buffer = await file.arrayBuffer()
  const header = new TextDecoder('latin1').decode(buffer.slice(0, Math.min(buffer.byteLength, 4096)))
  if (!header.includes('%PDF')) return false
  const body = new TextDecoder('latin1').decode(buffer)
  return /\/Type\s*\/Sig\b/.test(body)
    && /\/ByteRange\s*\[/.test(body)
    && /\/SubFilter\s*\/(?:adbe\.pkcs7\.detached|ETSI\.CAdES\.detached|ETSI\.RFC3161)/.test(body)
}

function isRelataSignedContainerName(fileName: string): boolean {
  const lower = fileName.toLowerCase()
  return lower.endsWith('.p7m') || lower.endsWith('.sig') || lower.endsWith('.pkcs7')
}

async function fileContainsCadesSignedData(file: File): Promise<boolean> {
  if (!isRelataSignedContainerName(file.name)) return false
  const bytes = new Uint8Array(await file.arrayBuffer())
  const signedDataOid = [0x06, 0x09, 0x2a, 0x86, 0x48, 0x86, 0xf7, 0x0d, 0x01, 0x07, 0x02]
  for (let index = 0; index <= bytes.length - signedDataOid.length; index += 1) {
    let matches = true
    for (let offset = 0; offset < signedDataOid.length; offset += 1) {
      if (bytes[index + offset] !== signedDataOid[offset]) {
        matches = false
        break
      }
    }
    if (matches) return true
  }
  const header = new TextDecoder('latin1').decode(bytes.slice(0, Math.min(bytes.length, 2048)))
  return /-----BEGIN (?:PKCS7|CMS)-----/.test(header)
}

function DepositFileField({
  label,
  fileName,
  shaValue,
  filePlaceholder,
  accept,
  hint,
  onFileNameChange,
  onShaChange,
  onFileComputed,
}: {
  label: string
  fileName: string
  shaValue: string
  filePlaceholder: string
  accept: string
  hint: string
  onFileNameChange: (value: string) => void
  onShaChange: (value: string) => void
  onFileComputed: (fileName: string, sha256: string) => void
}) {
  const [status, setStatus] = useState('')
  const hasInvalidSha = Boolean(shaValue) && !SHA256_HEX_PATTERN.test(shaValue)

  const handleFile = async (file: File | undefined) => {
    if (!file) return
    setStatus('Calcolo impronta del file...')
    try {
      const digest = await calculateSha256(file)
      onFileComputed(file.name, digest)
      setStatus(`Impronta calcolata: ${digest.slice(0, 12)}...`)
    } catch {
      onFileNameChange(file.name)
      setStatus('Calcolo automatico non disponibile: incolla una impronta del file valida.')
    }
  }

  return (
    <div className="iu-legal-evidence-field">
      <div className="iu-legal-evidence-field__header">
        <strong>{label}</strong>
        <span>{hint}</span>
      </div>
      <div className="iu-legal-file-row">
        <input value={fileName} onChange={(event) => onFileNameChange(event.currentTarget.value)} placeholder={filePlaceholder} />
        <label className="iu-legal-file-button">
          <UploadCloud size={15} />
          Scegli file
          <input type="file" accept={accept} onChange={(event) => void handleFile(event.currentTarget.files?.[0])} />
        </label>
      </div>
      <div className="iu-legal-hash-row">
        <input
          value={shaValue}
          onChange={(event) => onShaChange(normalizeSha256Input(event.currentTarget.value))}
          placeholder="Impronta calcolata dal file"
          aria-invalid={hasInvalidSha}
          maxLength={64}
        />
        <small className={hasInvalidSha ? 'is-error' : ''}>
          {hasInvalidSha ? 'L\'impronta del file non è valida.' : status || 'Scegli il file: IUSENTRA calcola l\'impronta automaticamente.'}
        </small>
      </div>
    </div>
  )
}

function classifyDepositFile(fileName: string): DepositEvidenceKind {
  const lower = fileName.toLowerCase()
  if (lower.includes('rac') || lower.includes('accettazione')) return 'rac'
  if ((lower.includes('rdac') || lower.includes('consegna') || lower.includes('avvenuta')) && !lower.includes('mancata')) return 'rdac'
  if (lower.includes('relata')) return 'relata'
  if (lower.includes('pec') || lower.includes('postacert') || lower.includes('inviata') || lower.endsWith('.eml') || lower.endsWith('.msg')) return 'pec'
  return 'atto'
}

function depositReference(values: {
  destinatario_nome: string
  destinatario_cf: string
  destinatario_pec: string
  pec_inviata: string
  rac_file: string
  rdac_file: string
}) {
  const rows = [
    values.destinatario_nome ? `Destinatario: ${values.destinatario_nome}` : '',
    values.destinatario_cf ? `C.F./P. IVA: ${values.destinatario_cf}` : '',
    values.destinatario_pec ? `PEC destinatario: ${values.destinatario_pec}` : '',
    values.pec_inviata ? `PEC inviata: ${values.pec_inviata}` : '',
    values.rac_file ? `Ricevuta di accettazione: ${values.rac_file}` : '',
    values.rdac_file ? `Ricevuta di consegna completa: ${values.rdac_file}` : '',
  ].filter(Boolean)
  return rows.join('; ')
}

function EvidenceSummaryRow({ label, fileName, shaValue }: { label: string; fileName: string; shaValue: string }) {
  const ready = Boolean(fileName && SHA256_HEX_PATTERN.test(shaValue))
  return (
    <span className={ready ? 'is-ready' : ''}>
      {ready ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}
      <strong>{label}</strong>
      <em>{fileName || 'Da associare'}</em>
      <small>{shaValue ? `Impronta ${shaValue.slice(0, 12)}...` : 'Impronta non calcolata'}</small>
    </span>
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function planFiles(outputPlan: Record<string, unknown>): string[] {
  const files = outputPlan.files
  return Array.isArray(files) ? files.map((item) => String(item || '').trim()).filter(Boolean) : []
}

function evidenceItems(outputPlan: Record<string, unknown>): Array<{ label: string; filename: string; sha256: string; generated: boolean }> {
  const pack = isRecord(outputPlan.evidencePack) ? outputPlan.evidencePack : null
  const items = Array.isArray(pack?.items) ? pack.items : []
  return items.map((item) => {
    const row = isRecord(item) ? item : {}
    return {
      label: String(row.label || row.kind || '').trim(),
      filename: String(row.filename || '').trim(),
      sha256: String(row.sha256 || '').trim(),
      generated: Boolean(row.generated),
    }
  }).filter((item) => item.label || item.filename)
}

function workflowSteps(outputPlan: Record<string, unknown>): LegalAutomationStep[] {
  const steps = outputPlan.workflowSteps
  if (!Array.isArray(steps)) return []
  return steps.map((item) => {
    const row = isRecord(item) ? item : {}
    return {
      id: String(row.id || row.title || '').trim(),
      title: String(row.title || '').trim(),
      body: String(row.body || '').trim(),
      source: String(row.source || '').trim(),
    }
  }).filter((item) => item.id && item.title)
}

function normativeChecks(outputPlan: Record<string, unknown>): Array<{ id: string; label: string; status: string; source: string; detail: string }> {
  const checks = outputPlan.normativeChecks
  if (!Array.isArray(checks)) return []
  return checks.map((item) => {
    const row = isRecord(item) ? item : {}
    return {
      id: String(row.id || row.label || '').trim(),
      label: String(row.label || '').trim(),
      status: String(row.status || '').trim(),
      source: String(row.source || '').trim(),
      detail: String(row.detail || '').trim(),
    }
  }).filter((item) => item.id && item.label)
}

function auditTrail(outputPlan: Record<string, unknown>) {
  return isRecord(outputPlan.auditTrail) ? outputPlan.auditTrail : null
}

function auditText(value: unknown) {
  return String(value || '').trim()
}

function deliveryPlan(outputPlan: Record<string, unknown>) {
  return isRecord(outputPlan.deliveryPlan) ? outputPlan.deliveryPlan : null
}

function signaturePlan(outputPlan: Record<string, unknown>) {
  if (isRecord(outputPlan.signaturePlan)) return outputPlan.signaturePlan
  const delivery = deliveryPlan(outputPlan)
  return isRecord(delivery?.signaturePlan) ? delivery.signaturePlan : null
}

function timingPlan(outputPlan: Record<string, unknown>) {
  if (isRecord(outputPlan.timingPlan)) return outputPlan.timingPlan
  const delivery = deliveryPlan(outputPlan)
  return isRecord(delivery?.timingPlan) ? delivery.timingPlan : null
}

function timingBasis(plan: Record<string, unknown> | null) {
  const rows = plan && Array.isArray(plan.legalBasis) ? plan.legalBasis : []
  return rows.map((item) => {
    const row = isRecord(item) ? item : {}
    return String(row.label || '').trim()
  }).filter(Boolean)
}

function signatureRequired(plan: Record<string, unknown> | null) {
  const required = plan && Array.isArray(plan.requiredBeforeSend) ? plan.requiredBeforeSend : []
  return required.map((item) => {
    const row = isRecord(item) ? item : {}
    return {
      id: String(row.id || '').trim(),
      label: String(row.label || '').trim(),
      sourceFile: String(row.sourceFile || '').trim(),
      signedFile: String(row.signedFile || '').trim(),
      format: String(row.format || '').trim(),
      reason: String(row.reason || '').trim(),
      source: String(row.source || '').trim(),
    }
  }).filter((item) => item.id && (item.sourceFile || item.signedFile))
}

function signatureNotToSign(plan: Record<string, unknown> | null) {
  const rows = plan && Array.isArray(plan.notToSign) ? plan.notToSign : []
  return rows.map((item) => {
    const row = isRecord(item) ? item : {}
    return {
      filename: String(row.filename || '').trim(),
      reason: String(row.reason || '').trim(),
    }
  }).filter((item) => item.filename)
}

function signatureChecks(plan: Record<string, unknown> | null) {
  const rows = plan && Array.isArray(plan.checks) ? plan.checks : []
  return rows.map((item) => {
    const row = isRecord(item) ? item : {}
    return {
      id: String(row.id || '').trim(),
      label: String(row.label || '').trim(),
      status: String(row.status || '').trim(),
      detail: String(row.detail || '').trim(),
      source: String(row.source || '').trim(),
    }
  }).filter((item) => item.id && item.label)
}

function deliveryRecipients(plan: Record<string, unknown> | null) {
  const recipients = plan && Array.isArray(plan.recipients) ? plan.recipients : []
  return recipients.map((item) => {
    const row = isRecord(item) ? item : {}
    return {
      name: String(row.name || '').trim(),
      pec: String(row.pec || '').trim(),
      role: String(row.role || '').trim(),
    }
  }).filter((item) => item.name || item.pec)
}

function deliveryAttachments(plan: Record<string, unknown> | null) {
  const attachments = plan && Array.isArray(plan.attachments) ? plan.attachments : []
  return attachments.map((item) => {
    const row = isRecord(item) ? item : {}
    return {
      label: String(row.label || '').trim(),
      filename: String(row.filename || '').trim(),
      source: String(row.source || '').trim(),
    }
  }).filter((item) => item.label || item.filename)
}

function deliveryChecks(plan: Record<string, unknown> | null) {
  const checks = plan && Array.isArray(plan.sendChecks) ? plan.sendChecks : []
  return checks.map((item) => {
    const row = isRecord(item) ? item : {}
    return {
      id: String(row.id || '').trim(),
      label: String(row.label || '').trim(),
      status: String(row.status || '').trim(),
      detail: String(row.detail || '').trim(),
    }
  }).filter((item) => item.id && item.label)
}

function ResultPanel({ result }: { result: LegalWorkflowResult }) {
  if (!result.message && !result.blockers.length && !result.warnings.length && !result.relataText && !result.body) {
    return (
      <Panel title="Esito controllo" subtitle="Compila i dati e avvia la verifica" icon={<ShieldCheck size={17} />}>
        <p className="iu-legal-empty">IUSENTRA prepara il testo e segnala i blocchi, poi l'avvocato controlla, firma e invia.</p>
      </Panel>
    )
  }
  return (
    <Panel
      title={result.ok ? 'Controllo superato' : 'Da completare'}
      subtitle={result.message || 'Risultato verifica'}
      icon={result.ok ? <CheckCircle2 size={17} /> : <AlertTriangle size={17} />}
      className={result.ok ? 'iu-legal-result--ok' : 'iu-legal-result--warn'}
    >
      {result.blockers.length ? (
        <div className="iu-legal-list iu-legal-list--blockers">
          {result.blockers.map((item) => <span key={item}><AlertTriangle size={15} /> {userFacingNotice(item)}</span>)}
        </div>
      ) : null}
      {result.warnings.length ? (
        <div className="iu-legal-list">
          {result.warnings.map((item) => <span key={item}><ShieldCheck size={15} /> {userFacingNotice(item)}</span>)}
        </div>
      ) : null}
      {result.templateLabel ? <div className="iu-legal-output"><span>Modello scelto</span><strong>{result.templateLabel}{templateVersionLabel(result.templateVersion)}</strong></div> : null}
      {result.subject ? <div className="iu-legal-output"><span>Oggetto</span><strong>{result.subject}</strong></div> : null}
      {planFiles(result.outputPlan).length ? (
        <div className="iu-legal-output">
          <span>File da produrre</span>
          <div className="iu-legal-evidence-grid">
            {planFiles(result.outputPlan).map((item) => <strong key={item}>{item}</strong>)}
          </div>
        </div>
      ) : null}
      {evidenceItems(result.outputPlan).length ? (
        <div className="iu-legal-output">
          <span>Pacchetto prova</span>
          <div className="iu-legal-evidence-grid">
            {evidenceItems(result.outputPlan).map((item) => (
              <strong key={`${item.label}-${item.filename}`}>
                {item.label}{item.filename ? ` - ${item.filename}` : ''}{item.sha256 ? ` - impronta ${item.sha256.slice(0, 12)}...` : ''}{item.generated ? ' - preparato' : ''}
              </strong>
            ))}
          </div>
        </div>
      ) : null}
      {workflowSteps(result.outputPlan).length ? (
        <div className="iu-legal-output">
          <span>Passaggi effettuati</span>
          <div className="iu-legal-automation-list">
            {workflowSteps(result.outputPlan).map((item, index) => (
              <article key={`${item.id}-${index}`}>
                <strong>{index + 1}. {item.title}</strong>
                <p>{item.body}</p>
                {item.source ? <small>{item.source}</small> : null}
              </article>
            ))}
          </div>
        </div>
      ) : null}
      {normativeChecks(result.outputPlan).length ? (
        <div className="iu-legal-output">
          <span>Verifiche normativa</span>
          <div className="iu-legal-check-grid">
            {normativeChecks(result.outputPlan).map((item) => (
              <article className={`is-${item.status.replace(/\s+/g, '-')}`} key={item.id}>
                <strong>{item.label}</strong>
                <em>{item.status}</em>
                <p>{item.detail}</p>
                {item.source ? <small>{item.source}</small> : null}
              </article>
            ))}
          </div>
        </div>
      ) : null}
      {signaturePlan(result.outputPlan) ? (
        <div className="iu-legal-output">
          <span>Firma digitale automatica</span>
          <div className="iu-legal-signature-summary">
            <div className="iu-legal-signature-summary__heading">
              <FileSignature size={17} />
              <strong>Relata da firmare prima dell'invio PEC</strong>
            </div>
            <div className="iu-legal-evidence-grid">
              {signatureRequired(signaturePlan(result.outputPlan)).map((item) => (
                <strong key={item.id}>
                  {item.label}{item.sourceFile ? ` - ${item.sourceFile}` : ''}{item.signedFile ? ` -> ${item.signedFile}` : ''}{item.format ? ` - ${item.format}` : ''}
                </strong>
              ))}
            </div>
            {signatureRequired(signaturePlan(result.outputPlan)).map((item) => (
              <small key={`${item.id}-reason`}>{item.reason}{item.source ? ` Fonte: ${item.source}.` : ''}</small>
            ))}
            {signatureNotToSign(signaturePlan(result.outputPlan)).length ? (
              <div className="iu-legal-signature-summary__not-to-sign">
                <strong>Allegati da non rifirmare automaticamente</strong>
                {signatureNotToSign(signaturePlan(result.outputPlan)).map((item) => (
                  <small key={item.filename}>{item.filename}: {item.reason}</small>
                ))}
              </div>
            ) : null}
            <div className="iu-legal-check-grid">
              {signatureChecks(signaturePlan(result.outputPlan)).map((item) => (
                <article className={`is-${item.status.replace(/\s+/g, '-')}`} key={item.id}>
                  <strong>{item.label}</strong>
                  <em>{item.status}</em>
                  <p>{item.detail}</p>
                  {item.source ? <small>{item.source}</small> : null}
                </article>
              ))}
            </div>
          </div>
        </div>
      ) : null}
      {deliveryPlan(result.outputPlan) ? (
        <div className="iu-legal-output">
          <span>Invio PEC controllato</span>
          <div className="iu-legal-delivery-summary">
            <strong>{auditText(deliveryPlan(result.outputPlan)?.subject) || 'notificazione ai sensi della legge n. 53 del 1994'}</strong>
            <small>{deliveryRecipients(deliveryPlan(result.outputPlan)).length} PEC distinta/e da preparare</small>
            {timingPlan(result.outputPlan) ? (
              <div className="iu-legal-timing-summary">
                <strong>Orario PEC e perfezionamento</strong>
                <small>{auditText(timingPlan(result.outputPlan)?.plannedAt) || 'Da pianificare'}</small>
                <small>{auditText(timingPlan(result.outputPlan)?.senderEffect)}</small>
                <small>{auditText(timingPlan(result.outputPlan)?.recipientEffect)}</small>
                {auditText(timingPlan(result.outputPlan)?.warning) ? <small>{auditText(timingPlan(result.outputPlan)?.warning)}</small> : null}
                {timingBasis(timingPlan(result.outputPlan)).length ? (
                  <small>Fonti: {timingBasis(timingPlan(result.outputPlan)).join('; ')}</small>
                ) : null}
              </div>
            ) : null}
            <div className="iu-legal-evidence-grid">
              {deliveryRecipients(deliveryPlan(result.outputPlan)).map((item) => (
                <strong key={`${item.pec}-${item.role}`}>{item.name || 'Destinatario'}{item.pec ? ` - ${item.pec}` : ''}{item.role ? ` - ${item.role}` : ''}</strong>
              ))}
            </div>
            <div className="iu-legal-evidence-grid">
              {deliveryAttachments(deliveryPlan(result.outputPlan)).map((item) => (
                <strong key={`${item.label}-${item.filename}`}>{item.label}{item.filename ? ` - ${item.filename}` : ''}</strong>
              ))}
            </div>
            <div className="iu-legal-check-grid">
              {deliveryChecks(deliveryPlan(result.outputPlan)).map((item) => (
                <article className={`is-${item.status.replace(/\s+/g, '-')}`} key={item.id}>
                  <strong>{item.label}</strong>
                  <em>{item.status}</em>
                  <p>{item.detail}</p>
                </article>
              ))}
            </div>
          </div>
        </div>
      ) : null}
      {auditTrail(result.outputPlan) ? (
        <div className="iu-legal-output">
          <span>Audit</span>
          <div className="iu-legal-audit-summary">
            <strong>{auditText(auditTrail(result.outputPlan)?.phase) || 'controllo'}</strong>
            <small>{auditText(auditTrail(result.outputPlan)?.generatedAt)}</small>
            {auditText(auditTrail(result.outputPlan)?.practice) ? <small>Pratica: {auditText(auditTrail(result.outputPlan)?.practice)}</small> : null}
            {auditText(auditTrail(result.outputPlan)?.recipient) ? <small>Destinatario: {auditText(auditTrail(result.outputPlan)?.recipient)}</small> : null}
            {auditTrail(result.outputPlan)?.documentsCount !== undefined ? <small>Allegati controllati: {String(auditTrail(result.outputPlan)?.documentsCount)}</small> : null}
          </div>
        </div>
      ) : null}
      {result.body ? <pre className="iu-legal-preview">{result.body}</pre> : null}
      {result.relataText ? <pre className="iu-legal-preview iu-legal-preview--relata">{result.relataText}</pre> : null}
      {result.checklistText ? <pre className="iu-legal-preview">{result.checklistText}</pre> : null}
      {result.nextActions.length ? (
        <div className="iu-legal-list iu-legal-list--actions">
          {result.nextActions.map((item) => <span key={item}><CheckCircle2 size={15} /> {item}</span>)}
        </div>
      ) : null}
    </Panel>
  )
}

function WorkflowCard({
  active,
  icon,
  title,
  text,
  onClick,
}: {
  active: boolean
  icon: React.ReactNode
  title: string
  text: string
  onClick: () => void
}) {
  return (
    <button className={`iu-legal-flow-card ${active ? 'is-active' : ''}`} type="button" onClick={onClick}>
      {icon}
      <strong>{title}</strong>
      <span>{text}</span>
    </button>
  )
}

export function NotificheLegaliPage() {
  const [data, setData] = useState<NotificheLegaliData>(emptyNotificheLegaliData)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<TabKey>('notifica')
  const [result, setResult] = useState<LegalWorkflowResult>(emptyResult)
  const [working, setWorking] = useState(false)
  const resultPanelRef = useRef<HTMLDivElement | null>(null)
  const [lastControlLabel, setLastControlLabel] = useState('')
  const [lastControlPayloadKey, setLastControlPayloadKey] = useState('')
  const [attestationPreviewOpen, setAttestationPreviewOpen] = useState(false)
  const [signatureMessage, setSignatureMessage] = useState('')
  const [signatureChecking, setSignatureChecking] = useState(false)
  const [signaturePin, setSignaturePin] = useState('')
  const [signatureStatus, setSignatureStatus] = useState<RelataSignerStatus | null>(null)
  const [signedRelata, setSignedRelata] = useState<SignedRelataRecord | null>(null)
  const signaturePinRef = useRef<HTMLInputElement | null>(null)
  const [senderPecVerification, setSenderPecVerification] = useState<PecVerificationEvidence | null>(null)
  const senderPecVerificationRef = useRef<PecVerificationEvidence | null>(null)
  const [recipientPecVerifications, setRecipientPecVerifications] = useState<Record<string, PecVerificationEvidence>>({})
  const recipientPecVerificationsRef = useRef<Record<string, PecVerificationEvidence>>({})
  const [pecVerificationWorking, setPecVerificationWorking] = useState(false)
  const [pecVerificationMessage, setPecVerificationMessage] = useState('')
  const [publicRegisterConsultedAt, setPublicRegisterConsultedAt] = useState<Record<string, string>>({})
  const [publicRegisterConfirmationWorking, setPublicRegisterConfirmationWorking] = useState(false)

  const [notifica, setNotifica] = useState({
    template_id: 'relata_pec_base_l53',
    caso_notifica: 'ordinaria',
    pratica_codice: '',
    avvocato_nome: '',
    avvocato_cf: '',
    avvocato_foro: '',
    studio_indirizzo: '',
    studio_cap: '',
    studio_citta: '',
    studio_provincia: '',
    luogo: '',
    data_relata: todayLocalDate(),
    ora_relata: currentLocalTime(),
    mittente_pec: '',
    fonte_pec_mittente: 'ReGIndE',
    mittente_pec_pubblico_elenco: true,
    mittente_pec_validata: false,
    assistito_nome: '',
    assistito_cf: '',
    ruolo_destinatario: 'controparte',
    destinatario_nome: '',
    destinatario_cf: '',
    destinatario_pec: '',
    destinatario_parte_rappresentata: '',
    fonte_pec_destinatario: 'reginde',
    destinatario_pec_pubblico_elenco: false,
    data_verifica_pec: '',
    data_ora_invio_pec: '',
    nome_file: '',
    descrizione_documento: '',
    origine_documento: 'originale_informatico',
    hash_sha256: '',
    data_comunicazione_cancelleria: '',
    attestazione_conformita: '',
    note_integrative_relata: '',
    procedimento_pendente: false,
    ufficio_giudiziario: '',
    sezione: '',
    numero_rg: '',
    anno_rg: '',
    ricevuta_completa: true,
    relata_firmata: false,
    relata_documento_separato: true,
    approvazione_avvocato: false,
  })
  const [modelFields, setModelFields] = useState<Record<string, string>>({})
  const [selectedPracticeId, setSelectedPracticeId] = useState('')
  const [practiceDetailsById, setPracticeDetailsById] = useState<Record<string, LegalPracticeSuggestion>>({})
  const [practiceSelectionWorking, setPracticeSelectionWorking] = useState(false)
  const [practiceSelectionMessage, setPracticeSelectionMessage] = useState('')
  const [selectedRecipientId, setSelectedRecipientId] = useState('')
  const [selectedRecipientIds, setSelectedRecipientIds] = useState<string[]>([])
  const [selectedDocumentId, setSelectedDocumentId] = useState('')
  const [selectedNotificationDocumentIds, setSelectedNotificationDocumentIds] = useState<string[]>([])
  const [manualNotificationDocuments, setManualNotificationDocuments] = useState<ManualNotificationDocument[]>([])
  const [notificationFilesMessage, setNotificationFilesMessage] = useState('')
  const [selectedDepositDocumentIds, setSelectedDepositDocumentIds] = useState<string[]>([])
  const [selectedClientId, setSelectedClientId] = useState('')
  const [templateCatalogExpanded, setTemplateCatalogExpanded] = useState(false)
  const [templateEditorOpen, setTemplateEditorOpen] = useState(false)
  const [templateSaving, setTemplateSaving] = useState(false)
  const [templateMessage, setTemplateMessage] = useState('')
  const [templateDraft, setTemplateDraft] = useState({
    label: '',
    description: '',
    body: '',
    requiresProceeding: false,
  })
  const templateBodyRef = useRef<HTMLTextAreaElement | null>(null)
  const [relataPreview, setRelataPreview] = useState<LegalRelataPreviewResult>(emptyRelataPreview)
  const [relataPreviewWorking, setRelataPreviewWorking] = useState(false)
  const [relataDraftText, setRelataDraftText] = useState('')
  const [relataDraftDirty, setRelataDraftDirty] = useState(false)
  const [relataDraftSaving, setRelataDraftSaving] = useState(false)
  const [relataDraftMessage, setRelataDraftMessage] = useState('')
  const [attestationDownloading, setAttestationDownloading] = useState(false)
  const [attestationDownloadMessage, setAttestationDownloadMessage] = useState('')
  const [hydratedDocumentsByPractice, setHydratedDocumentsByPractice] = useState<Record<string, LegalDocumentSuggestion[]>>({})
  const [documentHydrationMessage, setDocumentHydrationMessage] = useState('')

  const [deposito, setDeposito] = useState({
    atto_notificato: '',
    atto_sha256: '',
    relata_firmata: '',
    relata_sha256: '',
    pec_inviata: '',
    pec_inviata_sha256: '',
    destinatario_nome: '',
    destinatario_cf: '',
    destinatario_pec: '',
    fonte_pec_destinatario: '',
    rac_file: '',
    rac_sha256: '',
    rdac_file: '',
    rdac_sha256: '',
    ricevuta_completa: false,
    dati_atto_ricevute: '',
  })
  const [depositAutoMessage, setDepositAutoMessage] = useState('')

  const [unep, setUnep] = useState({
    tipo_richiesta_unep: 'notifica_civile_pagamento',
    tipo_notifica_unep: 'mani',
    ufficio_unep: '',
    ufficio_unep_codice: '',
    ufficio_unep_pec: '',
    atto_notificare: '',
    atto_sha256: '',
    richiesta_o_relata: '',
    richiesta_sha256: '',
    destinatario_nome: '',
    destinatario_cf: '',
    destinatario_indirizzo: '',
    destinatario_comune: '',
    destinatario_paese: '',
    destinatario_pec: '',
    fonte_pec_destinatario: '',
    precetto_gia_notificato: false,
    data_notifica_precetto: '',
    spese_unep_dovute: false,
    ricevuta_pagamento: '',
    ricevuta_pagamento_sha256: '',
    note: '',
  })

  const [nonPec, setNonPec] = useState({
    tipo_notifica_non_pec: 'raccomandata',
    data_notifica: todayLocalDate(),
    notifica_id: '',
    destinatario_nome: '',
    destinatario_cf: '',
    destinatario_indirizzo: '',
    destinatario_comune: '',
    destinatario_paese: '',
    atto_notificato: '',
    atto_sha256: '',
    numero_raccomandata: '',
    data_spedizione: todayLocalDate(),
    data_ricevuta_raccomandata: '',
    ufficio_unep: '',
    ufficio_unep_codice: '',
    ufficio_unep_pec: '',
    numero_cronologico: '',
    consegnatario: '',
    autorita_o_canale: '',
    prova_file: '',
    prova_sha256: '',
    note: '',
  })

  const [cliente, setCliente] = useState({
    template_id: 'aggiornamento_pratica',
    cliente_nome: '',
    ufficio_giudiziario: '',
    numero_rg: '',
    anno_rg: '',
    provvedimento_descrizione: '',
    oggetto: '',
    corpo: '',
  })

  useEffect(() => {
    let active = true
    getNotificheLegaliData()
      .then((payload) => {
        if (!active) return
        setData(payload)
        setNotifica((current) => ({
          ...current,
          avvocato_nome: payload.defaults.avvocatoNome,
          avvocato_cf: payload.defaults.avvocatoCf,
          avvocato_foro: payload.defaults.avvocatoForo,
          studio_indirizzo: payload.defaults.studioIndirizzo,
          studio_cap: payload.defaults.studioCap,
          studio_citta: payload.defaults.studioCitta,
          studio_provincia: payload.defaults.studioProvincia,
          luogo: [payload.defaults.studioCitta, payload.defaults.studioProvincia ? `(${payload.defaults.studioProvincia})` : ''].filter(Boolean).join(' '),
          mittente_pec: payload.defaults.mittentePec,
          fonte_pec_mittente: payload.defaults.fontePecMittente || 'ReGIndE',
        }))
        setCliente((current) => ({
          ...current,
          template_id: payload.modelliComunicazioneCliente[0]?.value || current.template_id,
        }))
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const selectedTemplate = useMemo(() => data.modelliRelata.find((item) => item.value === notifica.template_id), [data.modelliRelata, notifica.template_id])
  const selectedClientTemplate = useMemo(() => data.modelliComunicazioneCliente.find((item) => item.value === cliente.template_id), [data.modelliComunicazioneCliente, cliente.template_id])
  const selectedCaseDirective = useMemo<LegalNotificationDirective | undefined>(
    () => data.matriceNotifica.cases.find((item) => item.value === notifica.caso_notifica),
    [data.matriceNotifica.cases, notifica.caso_notifica],
  )
  const selectedRoleDirective = useMemo<LegalNotificationDirective | undefined>(
    () => data.matriceNotifica.roles.find((item) => item.value === notifica.ruolo_destinatario),
    [data.matriceNotifica.roles, notifica.ruolo_destinatario],
  )
  const templateFieldGroups = useMemo(() => {
    const groups = new Map<string, LegalTemplateFieldToken[]>()
    data.campiDisponibili.forEach((field) => {
      const key = field.group || 'Dati'
      groups.set(key, [...(groups.get(key) || []), field])
    })
    return Array.from(groups.entries()).slice(0, 7)
  }, [data.campiDisponibili])
  const selectedPractice = useMemo(
    () => practiceDetailsById[selectedPracticeId] || data.precompilazione.pratiche.find((item) => item.id === selectedPracticeId),
    [data.precompilazione.pratiche, practiceDetailsById, selectedPracticeId],
  )
  const practiceRecipientSuggestions = selectedPractice?.destinatari || []
  const recipientSuggestions = useMemo(() => {
    const seen = new Set<string>()
    return [...practiceRecipientSuggestions, ...data.precompilazione.destinatari].filter((item) => {
      const key = (item.pec || item.id || item.nome || item.label).trim().toLocaleLowerCase('it-IT')
      if (!key || seen.has(key)) return false
      seen.add(key)
      return true
    })
  }, [data.precompilazione.destinatari, practiceRecipientSuggestions])
  const visibleRecipientSuggestions = selectedPractice
    ? practiceRecipientSuggestions
    : data.precompilazione.destinatari
  const documentSuggestions = (selectedPracticeId && hydratedDocumentsByPractice[selectedPracticeId]?.length)
    ? hydratedDocumentsByPractice[selectedPracticeId]
    : selectedPractice?.documenti || []
  const selectedRecipients = useMemo(
    () => selectedRecipientIds
      .map((id) => recipientSuggestions.find((item) => item.id === id))
      .filter((item): item is LegalRecipientSuggestion => Boolean(item)),
    [recipientSuggestions, selectedRecipientIds],
  )
  const selectedNotificationDocuments = useMemo(
    () => selectedNotificationDocumentIds
      .map((id) => documentSuggestions.find((item) => item.id === id))
      .filter((item): item is LegalDocumentSuggestion => Boolean(item)),
    [documentSuggestions, selectedNotificationDocumentIds],
  )
  const selectedDepositDocuments = useMemo(
    () => selectedDepositDocumentIds
      .map((id) => documentSuggestions.find((item) => item.id === id))
      .filter((item): item is LegalDocumentSuggestion => Boolean(item)),
    [documentSuggestions, selectedDepositDocumentIds],
  )
  const officeDocuments = useMemo(
    () => documentSuggestions.filter((item) => item.documentoUfficio || item.notificaRichiesta),
    [documentSuggestions],
  )
  const officeMonitor = selectedPractice?.documentoUfficioMonitor
  const officeEvidenceReleases = officeMonitor?.documentiRilevati || []
  const pendingOfficeReleases = officeMonitor?.documentiRilasciati || []
  const officeProofRelease = officeEvidenceReleases[0] || pendingOfficeReleases[0]
  const officeAcquisitionHref = pendingOfficeReleases[0]?.acquisitionHref || selectedPractice?.portaleAcquisizioneHref || data.portaleServizi.acquisizioneHref
  const officePecHref = pendingOfficeReleases[0]?.pecHref || ''
  const officeAcquisitionRequired = Boolean(officeMonitor?.documentiDaAcquisire || officeMonitor?.stato === 'da_acquisire')
  const officeAcquisitionCompleted = officeDocuments.length > 0
  const selectedOrigin = useMemo(() => data.originiDocumento.find((item) => item.value === notifica.origine_documento), [data.originiDocumento, notifica.origine_documento])
  const originNeedsAttestazione = (origin: string) => Boolean(
    data.originiDocumento.find((item) => item.value === origin)?.needsAttestazione
    || ['copia_fascicolo_informatico', 'comunicazione_cancelleria', 'scansione_analogico'].includes(origin),
  )
  const notificationNeedsAttestazione = Boolean(
    selectedOrigin?.needsAttestazione
    || selectedNotificationDocuments.some((item) => item.necessitaAttestazione)
    || manualNotificationDocuments.some((item) => originNeedsAttestazione(item.origine)),
  )
  const guidedAutomationSteps = tab === 'notifica'
    ? [...data.automazioneGuidata.notifica, ...data.automazioneGuidata.allegati]
    : tab === 'deposito'
      ? data.automazioneGuidata.deposito
      : tab === 'unep'
        ? data.automazioneGuidata.unep
        : tab === 'nonpec'
          ? data.automazioneGuidata.nonPec
      : []
  const automaticValuesCount = [
    notifica.avvocato_nome,
    notifica.mittente_pec,
    notifica.assistito_nome,
    notifica.destinatario_nome,
    notifica.destinatario_pec,
    notifica.nome_file,
    selectedNotificationDocuments.length,
    notifica.ufficio_giudiziario,
    officeAcquisitionCompleted ? 'documento_ufficio_collegato' : '',
  ].filter(Boolean).length

  const applyClient = (client: { id: string; nome: string; codiceFiscalePiva: string; pec: string }) => {
    setSelectedClientId(client.id)
    setNotifica((current) => ({
      ...current,
      assistito_nome: client.nome || current.assistito_nome,
      assistito_cf: client.codiceFiscalePiva || current.assistito_cf,
    }))
    setCliente((current) => ({
      ...current,
      cliente_nome: client.nome || current.cliente_nome,
    }))
  }

  const startTemplateEdit = (mode: 'copy' | 'new') => {
    const base = mode === 'copy' ? selectedTemplate : null
    setTemplateDraft({
      label: base ? `Copia ${base.label}` : 'Nuovo modello relata',
      description: base?.description || 'Modello predisposto con i campi automatici IUSENTRA.',
      body: base?.previewText || [
        'RELAZIONE DI NOTIFICAZIONE A MEZZO PEC',
        "ai sensi dell'art. 3-bis L. 53/1994",
        '',
        'Io sottoscritto Avv. {{ avvocato.full_name }}, difensore di {{ cliente.nome_denominazione }},',
        "notifico a {{ destinatario.nome_denominazione }} all'indirizzo PEC {{ destinatario.pec }}",
        'i seguenti documenti:',
        '',
        '{{ documenti_righe }}',
        '',
        '{{ blocco_procedimento }}',
        '',
        '{{ attestazioni_testo }}',
        '',
        '{{ notifica.luogo }}, {{ notifica.data }} alle ore {{ notifica.ora }}',
        '',
        'Avv. {{ avvocato.full_name }}',
        'Documento informatico separato sottoscritto con firma digitale.',
      ].join('\n'),
      requiresProceeding: Boolean(base?.requiresProceeding),
    })
    setTemplateMessage('')
    setTemplateEditorOpen(true)
  }

  const insertTemplateToken = (token: string) => {
    const textarea = templateBodyRef.current
    if (!textarea) {
      setTemplateDraft((current) => ({ ...current, body: `${current.body}${current.body ? '\n' : ''}${token}` }))
      return
    }
    const start = textarea.selectionStart ?? templateDraft.body.length
    const end = textarea.selectionEnd ?? start
    const before = templateDraft.body.slice(0, start)
    const after = templateDraft.body.slice(end)
    const next = `${before}${token}${after}`
    setTemplateDraft((current) => ({ ...current, body: next }))
    window.setTimeout(() => {
      textarea.focus()
      const position = start + token.length
      textarea.setSelectionRange(position, position)
    }, 0)
  }

  const saveTemplate = async () => {
    setTemplateSaving(true)
    setTemplateMessage('Salvataggio modello in corso...')
    const saved = await saveLegalRelataTemplate(templateDraft).catch(() => ({ ok: false, message: 'Salvataggio non completato.', template: undefined }))
    if (saved.ok && saved.template) {
      setData((current) => ({
        ...current,
        modelliRelata: [...current.modelliRelata.filter((item) => item.value !== saved.template?.value), saved.template!],
      }))
      setNotifica((current) => ({ ...current, template_id: saved.template!.value }))
      setTemplateEditorOpen(false)
    }
    setTemplateMessage(saved.message)
    setTemplateSaving(false)
  }

  const applyRecipient = (recipient: LegalRecipientSuggestion) => {
    setSelectedRecipientId(recipient.id)
    setSelectedRecipientIds((current) => current.includes(recipient.id) ? current : [...current, recipient.id])
    setNotifica((current) => ({
      ...current,
      ruolo_destinatario: recipient.ruolo || current.ruolo_destinatario,
      destinatario_nome: recipient.nome || current.destinatario_nome,
      destinatario_cf: recipient.codiceFiscalePiva || current.destinatario_cf,
      destinatario_pec: recipient.pec || current.destinatario_pec,
      destinatario_parte_rappresentata: recipient.parteRappresentata || current.destinatario_parte_rappresentata,
      fonte_pec_destinatario: recipient.fontePecSuggerita || current.fonte_pec_destinatario,
      template_id: recipient.ruolo === 'difensore' ? 'relata_pec_a_difensore_costituito' : current.template_id,
    }))
    if (recipient.parteRappresentata) {
      setModelFields((current) => ({
        ...current,
        destinatario_parte_rappresentata: recipient.parteRappresentata,
        parte_rappresentata: recipient.parteRappresentata,
      }))
    }
    setDeposito((current) => ({
      ...current,
      destinatario_nome: recipient.nome || current.destinatario_nome,
      destinatario_cf: recipient.codiceFiscalePiva || current.destinatario_cf,
      destinatario_pec: recipient.pec || current.destinatario_pec,
      fonte_pec_destinatario: recipient.fontePecSuggerita || current.fonte_pec_destinatario,
    }))
    setUnep((current) => ({
      ...current,
      destinatario_nome: recipient.nome || current.destinatario_nome,
      destinatario_cf: recipient.codiceFiscalePiva || current.destinatario_cf,
      destinatario_pec: recipient.pec || current.destinatario_pec,
      fonte_pec_destinatario: recipient.fontePecSuggerita || current.fonte_pec_destinatario,
    }))
    setNonPec((current) => ({
      ...current,
      destinatario_nome: recipient.nome || current.destinatario_nome,
      destinatario_cf: recipient.codiceFiscalePiva || current.destinatario_cf,
    }))
  }

  const removeRecipient = (recipientId: string) => {
    setSelectedRecipientIds((current) => {
      const nextIds = current.filter((id) => id !== recipientId)
      if (selectedRecipientId === recipientId) {
        const nextRecipient = nextIds
          .map((id) => recipientSuggestions.find((item) => item.id === id))
          .find((item): item is LegalRecipientSuggestion => Boolean(item))
        if (nextRecipient) {
          window.setTimeout(() => applyRecipient(nextRecipient), 0)
        } else {
          setSelectedRecipientId('')
        }
      }
      return nextIds
    })
  }

  const isTimestampDocumentName = (value: string) => /^\d{12,20}\.pdf$/i.test((value || '').trim())

  const documentPrimaryName = (documento: LegalDocumentSuggestion) => (
    isTimestampDocumentName(documento.nomeFile) && documento.label && documento.label !== documento.nomeFile
      ? documento.label
      : documento.nomeFile || documento.label || documento.riferimentoPortale || 'Documento senza nome'
  )

  const documentEvidenceName = (documento: LegalDocumentSuggestion) => {
    const name = documentPrimaryName(documento)
    if (documento.riferimentoPortale && name) return `${documento.riferimentoPortale} - ${name}`
    return documento.riferimentoPortale || name
  }

  const depositEvidenceKindFromDocument = (documento: LegalDocumentSuggestion): DepositEvidenceKind => {
    const proofKind = documento.tipoProvaNotifica.toLowerCase()
    if (proofKind === 'relata') return 'relata'
    if (proofKind === 'rac') return 'rac'
    if (proofKind === 'rdac') return 'rdac'
    if (proofKind === 'pec') return 'pec'
    return classifyDepositFile(documentEvidenceName(documento))
  }

  const depositEvidenceKindLabel = (documento: LegalDocumentSuggestion) => {
    const kind = depositEvidenceKindFromDocument(documento)
    if (kind === 'relata') return 'Relata'
    if (kind === 'rac') return 'Ricevuta di accettazione'
    if (kind === 'rdac') return 'Ricevuta di consegna'
    if (kind === 'pec') return 'PEC inviata'
    return documento.provaNotifica ? 'Atto notificato' : 'Documento'
  }

  const isDepositProofDocument = (documento: LegalDocumentSuggestion) => (
    documento.provaNotifica
    || Boolean(documento.tipoProvaNotifica)
    || ['relata', 'rac', 'rdac', 'pec'].includes(depositEvidenceKindFromDocument(documento))
  )

  const syncDepositDraftFromRows = (rows: LegalDocumentSuggestion[], current: typeof deposito) => (
    rows.reduce((draft, documento) => applyDepositFile(
      draft,
      depositEvidenceKindFromDocument(documento),
      documentEvidenceName(documento),
      documento.hashSha256,
    ), current)
  )

  const documentDetailLine = (documento: LegalDocumentSuggestion) => {
    const details = [
      documento.descrizione && documento.descrizione !== documentPrimaryName(documento) ? documento.descrizione : '',
      documento.origine ? data.originiDocumento.find((item) => item.value === documento.origine)?.label || documento.origine : '',
      documento.riferimentoPortale ? `Rif. ${documento.riferimentoPortale}` : '',
    ].filter(Boolean)
    return details.join(' · ')
  }

  const hasNotifiableExtension = (value: string) => /\.(?:pdf|pdfa|p7m)$/i.test((value || '').trim())
  const hasSendableNotificationAttachmentExtension = (value: string) => /\.(?:pdf|pdfa|p7m|eml|msg)$/i.test((value || '').trim())
  const hasEmailEvidenceExtension = (value: string) => /\.(?:eml|msg)$/i.test((value || '').trim())
  const isNotifiableNotificationDocument = (documento: LegalDocumentSuggestion) => (
    hasNotifiableExtension(documentPrimaryName(documento))
    || hasNotifiableExtension(documento.nomeFile)
    || hasNotifiableExtension(documento.nomeOriginale)
  )
  const isNotifiablePayloadDocument = (documento: NotificaDocumentPayload) => (
    hasSendableNotificationAttachmentExtension(documento.nome_file)
    || hasSendableNotificationAttachmentExtension(documento.file_originale || '')
  )
  const deriveProceedingRg = (...values: string[]) => {
    for (const value of values) {
      const exact = String(value || '').trim().match(/^0*(\d{1,8})\s*\/\s*(20\d{2})$/)
      if (exact) return { numero: exact[1], anno: exact[2] }
      const prefixed = String(value || '').match(/\b(?:R\.?\s*G\.?|N\.?\s*R\.?\s*G\.?|NRG)\s*:?\s*0*(\d{1,8})(?:\s*\/\s*|\s+)(20\d{2})\b/i)
      if (prefixed) return { numero: prefixed[1], anno: prefixed[2] }
    }
    return { numero: '', anno: '' }
  }
  useEffect(() => {
    if (!selectedPracticeId || hydratedDocumentsByPractice[selectedPracticeId]?.length) return
    let active = true
    setDocumentHydrationMessage('Lettura dei nomi documento in corso...')
    getNotificheLegaliPracticeDocuments(selectedPracticeId)
      .then((documents) => {
        if (!active) return
        if (!documents.length) {
          setDocumentHydrationMessage('')
          return
        }
        setHydratedDocumentsByPractice((current) => ({ ...current, [selectedPracticeId]: documents }))
        const enriched = documents.filter((documento) => (
          isTimestampDocumentName(documento.nomeFile) && documento.label && documento.label !== documento.nomeFile
        )).length
        setDocumentHydrationMessage(enriched ? `${enriched} nomi documento letti dal contenuto.` : 'Documenti della pratica verificati.')
      })
      .catch(() => { if (active) setDocumentHydrationMessage('Lettura documenti non completata: puoi comunque selezionare gli allegati.') })
    return () => { active = false }
  }, [selectedPracticeId])

  const depositDocumentPayload = (documento: LegalDocumentSuggestion): EvidenceDocumentPayload => ({
    nome_file: documentEvidenceName(documento),
    descrizione: documento.descrizione || documento.label,
    origine: documento.origine || 'nativo_digitale',
    hash_sha256: documento.hashSha256,
    riferimento_portale: documento.riferimentoPortale,
    file_originale: documento.nomeOriginale || documento.nomeFile,
  })

  const syncDepositoFromDocuments = (ids: string[]) => {
    const rows = ids
      .map((id) => documentSuggestions.find((item) => item.id === id))
      .filter((item): item is LegalDocumentSuggestion => Boolean(item))
    setDeposito((current) => syncDepositDraftFromRows(rows, current))
  }

  const applyDocument = (documento: LegalDocumentSuggestion) => {
    setSelectedDocumentId(documento.id)
    setSelectedDepositDocumentIds([documento.id])
    setNotifica((current) => ({
      ...current,
      nome_file: documentPrimaryName(documento) || current.nome_file,
      descrizione_documento: documento.descrizione || current.descrizione_documento,
      origine_documento: documento.origine || current.origine_documento,
      hash_sha256: documento.hashSha256 || current.hash_sha256,
      template_id: documento.origine === 'copia_fascicolo_informatico'
        ? 'relata_pec_con_attestazione_fascicolo'
        : documento.origine === 'scansione_analogico'
          ? 'relata_pec_con_attestazione_scansione_analogica'
          : current.template_id,
      procedimento_pendente: documento.origine === 'copia_fascicolo_informatico' ? true : current.procedimento_pendente,
    }))
    setDeposito((current) => syncDepositDraftFromRows([documento], current))
    setUnep((current) => ({
      ...current,
      atto_notificare: documentEvidenceName(documento) || current.atto_notificare,
      atto_sha256: documento.hashSha256 || current.atto_sha256,
    }))
    setNonPec((current) => ({
      ...current,
      atto_notificato: documentEvidenceName(documento) || current.atto_notificato,
      atto_sha256: documento.hashSha256 || current.atto_sha256,
    }))
    setCliente((current) => ({
      ...current,
      provvedimento_descrizione: documento.descrizione || current.provvedimento_descrizione,
    }))
  }

  const documentSuggestionPayload = (documento: LegalDocumentSuggestion): NotificaDocumentPayload => {
    return {
      nome_file: documentPrimaryName(documento),
      descrizione: documento.descrizione || documento.label,
      origine: documento.origine || 'nativo_digitale',
      hash_sha256: documento.hashSha256,
      data_comunicazione_cancelleria: documento.origine === 'comunicazione_cancelleria' ? documento.dataDocumento : '',
      fonte_documento: documento.fonte,
      riferimento_portale: documento.riferimentoPortale,
      file_originale: documento.nomeOriginale || documento.nomeFile,
      servizio_portale: documento.servizioPortale,
      documento_ufficio: documento.documentoUfficio,
      acquisito_da_portale: documento.acquisitoDaPortale,
      notifica_richiesta: documento.notificaRichiesta,
      data_rilascio_portale: documento.dataRilascioPortale,
      attestazione_conformita: '',
      attestazione_conformita_presente: false,
    }
  }

  const recipientPayload = (recipient: LegalRecipientSuggestion) => {
    const isActive = recipient.id === selectedRecipientId
    return {
      nome: isActive ? notifica.destinatario_nome || recipient.nome : recipient.nome,
      pec: isActive ? notifica.destinatario_pec || recipient.pec : recipient.pec,
      ruolo: isActive ? notifica.ruolo_destinatario || recipient.ruolo : recipient.ruolo || notifica.ruolo_destinatario,
      fonte_pec: isActive ? notifica.fonte_pec_destinatario || recipient.fontePecSuggerita : recipient.fontePecSuggerita,
      parte_rappresentata: isActive ? notifica.destinatario_parte_rappresentata || recipient.parteRappresentata : recipient.parteRappresentata,
      codice_fiscale_piva: isActive ? notifica.destinatario_cf || recipient.codiceFiscalePiva : recipient.codiceFiscalePiva,
    }
  }

  const notificationRecipientPayloads = () => {
    if (selectedRecipients.length) return selectedRecipients.map(recipientPayload)
    if (!notifica.destinatario_nome && !notifica.destinatario_pec) return []
    return [{
      nome: notifica.destinatario_nome,
      pec: notifica.destinatario_pec,
      ruolo: notifica.ruolo_destinatario,
      fonte_pec: notifica.fonte_pec_destinatario,
      parte_rappresentata: notifica.destinatario_parte_rappresentata,
      codice_fiscale_piva: notifica.destinatario_cf,
    }]
  }

  const currentPecVerificationSubjects = () => {
    const sender: PecVerificationSubject = {
      key: pecVerificationKey(notifica.fonte_pec_mittente, notifica.avvocato_cf, notifica.mittente_pec),
      kind: 'sender',
      source: normalizePecSource(notifica.fonte_pec_mittente),
      address: normalizePecAddress(notifica.mittente_pec),
      taxCode: normalizePecIdentity(notifica.avvocato_cf),
      label: notifica.avvocato_nome || 'Avvocato notificante',
    }
    const recipients = notificationRecipientPayloads().map((recipient, index): PecVerificationSubject => ({
      key: pecVerificationKey(recipient.fonte_pec, recipient.codice_fiscale_piva, recipient.pec),
      kind: 'recipient',
      source: normalizePecSource(recipient.fonte_pec),
      address: normalizePecAddress(recipient.pec),
      taxCode: normalizePecIdentity(recipient.codice_fiscale_piva),
      label: recipient.nome || `Destinatario ${index + 1}`,
    }))
    return { sender, recipients }
  }

  const ensureAutomaticPecVerification = async (force = false) => {
    const { sender, recipients } = currentPecVerificationSubjects()
    const subjects = [sender, ...recipients]
    const nextByKey: Record<string, PecVerificationEvidence> = { ...recipientPecVerificationsRef.current }
    if (senderPecVerificationRef.current) nextByKey[senderPecVerificationRef.current.key] = senderPecVerificationRef.current

    const pending: PecVerificationSubject[] = []
    subjects.forEach((subject) => {
      const cached = nextByKey[subject.key]
      if (!force && pecEvidenceMatches(cached, subject)) return
      if (!subject.address || !subject.address.includes('@')) {
        nextByKey[subject.key] = pecEvidenceFromResponse({
          verified: false,
          message: `${subject.kind === 'sender' ? 'PEC del notificante' : 'PEC del destinatario'} mancante o non valida.`,
        }, subject)
        return
      }
      if (!subject.source) {
        nextByKey[subject.key] = pecEvidenceFromResponse({
          verified: false,
          message: `Indica l’elenco pubblico della ${subject.kind === 'sender' ? 'PEC notificante' : 'PEC destinataria'}.`,
        }, subject)
        return
      }
      const capability = data.registriPec.find((item) => item.value === subject.source)
      if (!capability?.validForNotification) {
        nextByKey[subject.key] = pecEvidenceFromResponse({
          verified: false,
          message: capability
            ? `${capability.label} non certifica un indirizzo PEC utilizzabile per questa notifica.`
            : 'Seleziona un pubblico elenco ammesso per la notifica.',
        }, subject)
        return
      }
      if (!subject.taxCode) {
        nextByKey[subject.key] = pecEvidenceFromResponse({
          verified: false,
          message: `Codice fiscale o partita IVA ${subject.kind === 'sender' ? 'del notificante' : 'del destinatario'} mancante: serve per associare la PEC al soggetto corretto.`,
        }, subject)
        return
      }
      pending.push(subject)
    })

    setPecVerificationWorking(true)
    setPecVerificationMessage(pending.length ? 'Verifica delle PEC in corso...' : '')

    const markFailed = (subject: PecVerificationSubject, message: string) => {
      nextByKey[subject.key] = pecEvidenceFromResponse({ verified: false, message }, subject)
    }

    const regindeSubjects = pending.filter((subject) => subject.source === 'reginde')
    if (regindeSubjects.length) {
      const verificationPin = signaturePin.trim()
      if (!verificationPin) {
        regindeSubjects.forEach((subject) => markFailed(
          subject,
          'Inserisci il PIN nel riquadro Firma relata: lo stesso comando verificherà le PEC e firmerà il documento.',
        ))
      } else {
        const controller = new AbortController()
        const timeout = window.setTimeout(() => controller.abort(), 80000)
        try {
          const requestOptions: LocalNetworkRequestInit = {
            method: 'POST',
            mode: 'cors',
            targetAddressSpace: 'local',
            headers: { 'Content-Type': 'application/json' },
            signal: controller.signal,
            body: JSON.stringify({
              pin: verificationPin,
              soggetti: regindeSubjects.map((subject) => ({
                key: subject.key,
                codice_fiscale: subject.taxCode,
                pec_attesa: subject.address,
                descrizione: subject.label,
                entity_hint: subject.kind === 'recipient' && (
                  /@mailcert\.avvocaturastato\.it$/i.test(subject.address)
                  || /\b(?:avvocatura|ordine\s+degli?\s+avvocati|consiglio\s+nazionale\s+forense)\b/i.test(subject.label)
                ),
              })),
            }),
          }
          const response = await fetch(relataLocalSignerEndpoint('/pst/reginde'), requestOptions)
          const payload = await response.json().catch(() => ({})) as Record<string, unknown>
          const rows = Array.isArray(payload.results) ? payload.results.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object')) : []
          regindeSubjects.forEach((subject) => {
            const row = rows.find((item) => String(item.key || '') === subject.key)
            if (response.ok && row) {
              nextByKey[subject.key] = pecEvidenceFromResponse({ ...row, key: subject.key, source: 'reginde' }, subject)
            }
            else markFailed(subject, String(payload.errore || 'Verifica della PEC non completata. Controlla il dispositivo e riprova.'))
          })
        } catch (error) {
          const message = error instanceof DOMException && error.name === 'AbortError'
            ? 'Verifica della PEC non completata entro il tempo previsto. Controlla il dispositivo e riprova.'
            : 'Verifica della PEC non completata. Controlla il dispositivo e riprova.'
          regindeSubjects.forEach((subject) => markFailed(subject, message))
        } finally {
          window.clearTimeout(timeout)
        }
      }
    }

    pending
      .filter((subject) => subject.source !== 'reginde')
      .forEach((subject) => {
        const capability = data.registriPec.find((item) => item.value === subject.source)
        markFailed(
          subject,
          capability?.requiresUserConfirmation
            ? `Apri ${capability.label}, scegli il soggetto corretto e conferma l’indirizzo PEC visualizzato.`
            : `${capability?.label || 'La fonte selezionata'} non consente la verifica richiesta.`,
        )
      })

    const senderEvidence = nextByKey[sender.key] || null
    const recipientEvidence: Record<string, PecVerificationEvidence> = {}
    recipients.forEach((subject) => {
      const evidence = nextByKey[subject.key]
      if (evidence) recipientEvidence[subject.key] = evidence
    })
    const senderVerified = pecEvidenceMatches(senderEvidence, sender)
    const recipientsVerified = recipients.length > 0 && recipients.every((subject) => pecEvidenceMatches(recipientEvidence[subject.key], subject))
    const checkedAt = [senderEvidence, ...Object.values(recipientEvidence)]
      .map((item) => item?.checkedAt || '')
      .filter(Boolean)
      .sort()
      .at(-1) || ''

    senderPecVerificationRef.current = senderEvidence
    recipientPecVerificationsRef.current = recipientEvidence
    setSenderPecVerification(senderEvidence)
    setRecipientPecVerifications(recipientEvidence)
    setNotifica((current) => ({
      ...current,
      mittente_pec_pubblico_elenco: senderVerified,
      mittente_pec_validata: senderVerified,
      destinatario_pec_pubblico_elenco: recipientsVerified,
      data_verifica_pec: checkedAt,
    }))
    const firstFailure = [senderEvidence, ...recipients.map((subject) => recipientEvidence[subject.key])]
      .find((item) => item && !item.verified)
    const ok = senderVerified && recipientsVerified
    setPecVerificationMessage(ok
      ? `PEC verificate${checkedAt ? ` il ${localClockLabel(checkedAt)}` : ''}.`
      : firstFailure?.message || 'Completa i dati indicati per verificare le PEC.'
    )
    setPecVerificationWorking(false)
    return { ok, sender: senderEvidence, recipients: recipientEvidence }
  }

  const openSelectedPublicRegister = () => {
    const source = normalizePecSource(notifica.fonte_pec_destinatario)
    const capability = data.registriPec.find((item) => item.value === source)
    const subject = currentPecVerificationSubjects().recipients.find((item) => item.source === source)
    if (!capability || !subject) {
      setPecVerificationMessage('Completa destinatario, PEC e pubblico elenco prima della consultazione.')
      return
    }
    if (!capability.validForNotification) {
      setPecVerificationMessage(`${capability.label} non certifica indirizzi PEC utilizzabili per questa notifica.`)
      return
    }
    const consultedAt = new Date().toISOString()
    if (capability.officialUrl) {
      const opened = window.open(capability.officialUrl, '_blank')
      if (!opened) {
        setPecVerificationMessage('Il browser ha bloccato l’apertura del pubblico elenco. Consenti l’apertura e riprova.')
        return
      }
      opened.opener = null
    }
    setPublicRegisterConsultedAt((current) => ({ ...current, [subject.key]: consultedAt }))
    setPecVerificationMessage(`Seleziona ${subject.label} nella fonte aperta, controlla la PEC e torna qui per confermarla.`)
  }

  const confirmSelectedPublicRegister = async () => {
    const source = normalizePecSource(notifica.fonte_pec_destinatario)
    const capability = data.registriPec.find((item) => item.value === source)
    const subjects = currentPecVerificationSubjects()
    const subject = subjects.recipients.find((item) => item.source === source && item.address === normalizePecAddress(notifica.destinatario_pec))
      || subjects.recipients.find((item) => item.source === source)
    if (!capability?.requiresUserConfirmation || !subject) {
      setPecVerificationMessage('La fonte selezionata non richiede questa conferma.')
      return
    }
    setPublicRegisterConfirmationWorking(true)
    setPecVerificationMessage('Registrazione della verifica in corso...')
    try {
      const payload = await confirmLegalPublicRegister(data.azioni.verificaPecConsultata, {
        fascicolo_id: selectedPracticeId,
        source,
        pec: subject.address,
        codice_fiscale: subject.taxCode,
        soggetto: subject.label,
        consulted_at: publicRegisterConsultedAt[subject.key] || '',
      })
      const evidence = pecEvidenceFromResponse(payload, subject)
      if (!evidence.verified) throw new Error('La prova restituita non corrisponde al soggetto e alla PEC selezionati.')
      const nextRecipients = { ...recipientPecVerificationsRef.current, [subject.key]: evidence }
      recipientPecVerificationsRef.current = nextRecipients
      setRecipientPecVerifications(nextRecipients)
      const allRecipientsVerified = subjects.recipients.length > 0
        && subjects.recipients.every((item) => pecEvidenceMatches(nextRecipients[item.key], item))
      const senderVerified = pecEvidenceMatches(senderPecVerificationRef.current, subjects.sender)
      setNotifica((current) => ({
        ...current,
        destinatario_pec_pubblico_elenco: allRecipientsVerified,
        mittente_pec_pubblico_elenco: senderVerified,
        mittente_pec_validata: senderVerified,
        data_verifica_pec: evidence.checkedAt,
      }))
      setPecVerificationMessage(`PEC di ${subject.label} verificata su ${capability.label}; prova salvata nel fascicolo il ${localClockLabel(evidence.checkedAt)}.`)
    } catch (error) {
      setPecVerificationMessage(error instanceof Error ? error.message : 'La verifica dell’indirizzo PEC non è stata registrata.')
    } finally {
      setPublicRegisterConfirmationWorking(false)
    }
  }

  const manualNotificationDocument = (): NotificaDocumentPayload | null => {
    if (!notifica.nome_file && !notifica.descrizione_documento) return null
    return {
      nome_file: notifica.nome_file,
      descrizione: notifica.descrizione_documento,
      origine: notifica.origine_documento,
      hash_sha256: notifica.hash_sha256,
      data_comunicazione_cancelleria: notifica.data_comunicazione_cancelleria,
      fonte_documento: 'IMPORT_ESTERNO',
      documento_ufficio: false,
      acquisito_da_portale: false,
      notifica_richiesta: false,
      attestazione_conformita: '',
      attestazione_conformita_presente: false,
    }
  }

  const notificationDocumentPayloads = (): NotificaDocumentPayload[] => {
    const selectedRows = selectedNotificationDocuments.map(documentSuggestionPayload)
    const uploadedRows = manualNotificationDocuments.map((documento) => ({
      ...documento,
      attestazione_conformita: '',
      attestazione_conformita_presente: false,
    }))
    const rows = [...selectedRows, ...uploadedRows]
    const seen = new Set<string>()
    return rows.filter((item) => {
      const key = `${item.nome_file.trim().toLowerCase()}|${item.descrizione.trim().toLowerCase()}`
      if (!key.trim() || seen.has(key)) return false
      seen.add(key)
      return true
    })
  }

  const addManualNotificationDocument = () => {
    const manual = manualNotificationDocument()
    if (!manual) {
      setNotificationFilesMessage('Indica almeno nome file o descrizione prima di aggiungere un allegato.')
      return
    }
    setManualNotificationDocuments((current) => [
      ...current,
      { ...manual, id: `${Date.now()}-${current.length}` },
    ])
    setNotifica((current) => ({
      ...current,
      nome_file: '',
      descrizione_documento: '',
      hash_sha256: '',
      data_comunicazione_cancelleria: '',
    }))
    setNotificationFilesMessage('Allegato aggiunto alla notifica.')
  }

  const removeManualNotificationDocument = (id: string) => {
    setManualNotificationDocuments((current) => current.filter((item) => item.id !== id))
  }

  const handleNotificationFiles = async (files: FileList | null) => {
    const selected = Array.from(files || [])
    if (!selected.length) return
    setNotificationFilesMessage('Calcolo impronte degli allegati...')
    const calculated: ManualNotificationDocument[] = []
    for (const file of selected) {
      let sha256 = ''
      try {
        sha256 = await calculateSha256(file)
      } catch {
        sha256 = ''
      }
      const origin = notifica.origine_documento || 'originale_informatico'
      calculated.push({
        id: `${Date.now()}-${file.name}-${calculated.length}`,
        nome_file: file.name,
        descrizione: file.name.replace(/\.[^.]+$/, ''),
        origine: origin,
        hash_sha256: sha256,
        data_comunicazione_cancelleria: origin === 'comunicazione_cancelleria' ? notifica.data_comunicazione_cancelleria : '',
        fonte_documento: 'IMPORT_ESTERNO',
        documento_ufficio: false,
        acquisito_da_portale: false,
        notifica_richiesta: false,
        attestazione_conformita: '',
        attestazione_conformita_presente: false,
      })
    }
    setManualNotificationDocuments((current) => [...current, ...calculated])
    const withoutHash = calculated.filter((item) => !item.hash_sha256)
    setNotificationFilesMessage(withoutHash.length ? 'Allegati aggiunti; per alcuni file incolla l’impronta del file se richiesta dal controllo.' : 'Allegati aggiunti e impronte calcolate.')
  }

  const toggleNotificationDocument = (documento: LegalDocumentSuggestion, checked: boolean) => {
    setSelectedNotificationDocumentIds((current) => {
      const next = checked
        ? Array.from(new Set([...current, documento.id]))
        : current.filter((id) => id !== documento.id)
      return next
    })
  }

  const toggleDepositDocument = (documento: LegalDocumentSuggestion, checked: boolean) => {
    setSelectedDepositDocumentIds((current) => {
      const next = checked
        ? Array.from(new Set([...current, documento.id]))
        : current.filter((id) => id !== documento.id)
      syncDepositoFromDocuments(next)
      if (checked && next.length === 1) setSelectedDocumentId(documento.id)
      return next
    })
  }

  const applyPractice = (practice: LegalPracticeSuggestion) => {
    setSignaturePin('')
    setSignatureMessage('')
    setSignatureStatus(null)
    setSignedRelata(null)
    setResult(emptyResult)
    setLastControlLabel('')
    setLastControlPayloadKey('')
    setPecVerificationMessage('')
    setPracticeDetailsById((current) => ({ ...current, [practice.id]: practice }))
    setPracticeSelectionMessage('Pratica selezionata e dati compilati.')
    setSelectedPracticeId(practice.id)
    const destinatariCompleti = practice.destinatari.filter((item) => Boolean(item.pec))
    const primoDestinatario = destinatariCompleti[0] || practice.destinatari[0] || null
    setSelectedRecipientId(primoDestinatario?.id || '')
    setSelectedRecipientIds(destinatariCompleti.map((item) => item.id).filter(Boolean))
    setSelectedDocumentId('')
    setSelectedNotificationDocumentIds([])
    setSelectedDepositDocumentIds([])
    setSelectedClientId(practice.clienteId || '')
    const derivedRg = deriveProceedingRg(practice.procedimento.numeroRg && practice.procedimento.annoRg ? `${practice.procedimento.numeroRg}/${practice.procedimento.annoRg}` : '', practice.numero, practice.titolo, practice.label)
    const resolvedNumeroRg = practice.procedimento.numeroRg || derivedRg.numero
    const resolvedAnnoRg = practice.procedimento.numeroRg
      ? (practice.procedimento.annoRg || derivedRg.anno)
      : (derivedRg.anno || practice.procedimento.annoRg)
    const suggestedCase = data.matriceNotifica.cases.find(
      (item) => item.templateId === practice.modelloSuggerito,
    )
    setNotifica((current) => ({
      ...current,
      pratica_codice: practice.numero || current.pratica_codice,
      caso_notifica: suggestedCase?.value || current.caso_notifica,
      template_id: practice.modelloSuggerito || current.template_id,
      assistito_nome: practice.assistitoNome || current.assistito_nome,
      assistito_cf: practice.assistitoCf || current.assistito_cf,
      procedimento_pendente: practice.procedimento.presente || current.procedimento_pendente,
      ufficio_giudiziario: practice.procedimento.ufficio || current.ufficio_giudiziario,
      sezione: practice.procedimento.sezione || current.sezione,
      numero_rg: resolvedNumeroRg || current.numero_rg,
      anno_rg: resolvedAnnoRg || current.anno_rg,
      destinatario_nome: primoDestinatario?.nome || current.destinatario_nome || practice.controparte,
      destinatario_cf: primoDestinatario?.codiceFiscalePiva || current.destinatario_cf || practice.controparteCf,
      destinatario_pec: primoDestinatario?.pec || current.destinatario_pec,
      destinatario_parte_rappresentata: primoDestinatario?.parteRappresentata || current.destinatario_parte_rappresentata || practice.controparte,
      ruolo_destinatario: primoDestinatario?.ruolo || current.ruolo_destinatario,
      fonte_pec_destinatario: primoDestinatario?.fontePecSuggerita || current.fonte_pec_destinatario,
      nome_file: '',
      descrizione_documento: '',
      origine_documento: 'originale_informatico',
      hash_sha256: '',
    }))
    setModelFields((current) => ({
      ...current,
      procedimento_giudice: practice.procedimento.giudice || current.procedimento_giudice || '',
      tipo_procedimento: practice.procedimento.tipoProcedimento || current.tipo_procedimento || '',
      destinatario_parte_rappresentata: primoDestinatario?.parteRappresentata || current.destinatario_parte_rappresentata || practice.controparte || '',
    }))
    setCliente((current) => ({
      ...current,
      cliente_nome: practice.assistitoNome || current.cliente_nome,
      ufficio_giudiziario: practice.procedimento.ufficio || current.ufficio_giudiziario,
      numero_rg: resolvedNumeroRg || current.numero_rg,
      anno_rg: resolvedAnnoRg || current.anno_rg,
      provvedimento_descrizione: '',
    }))
    setDeposito((current) => ({
      ...current,
      atto_notificato: '',
      atto_sha256: '',
      relata_firmata: '',
      relata_sha256: '',
      pec_inviata: '',
      pec_inviata_sha256: '',
      rac_file: '',
      rac_sha256: '',
      rdac_file: '',
      rdac_sha256: '',
      ricevuta_completa: false,
      dati_atto_ricevute: '',
      destinatario_nome: primoDestinatario?.nome || current.destinatario_nome,
      destinatario_cf: primoDestinatario?.codiceFiscalePiva || current.destinatario_cf,
      destinatario_pec: primoDestinatario?.pec || current.destinatario_pec,
      fonte_pec_destinatario: primoDestinatario?.fontePecSuggerita || current.fonte_pec_destinatario,
    }))
    const suggestedUnep = suggestUnepOffice(practice.procedimento.ufficio, data.ufficiUnep)
    setUnep((current) => ({
      ...current,
      ufficio_unep: suggestedUnep?.nome || current.ufficio_unep || practice.procedimento.ufficio,
      ufficio_unep_codice: suggestedUnep?.codice || current.ufficio_unep_codice,
      ufficio_unep_pec: suggestedUnep?.pec || current.ufficio_unep_pec,
      atto_notificare: '',
      atto_sha256: '',
      destinatario_nome: primoDestinatario?.nome || current.destinatario_nome || practice.controparte,
      destinatario_cf: primoDestinatario?.codiceFiscalePiva || current.destinatario_cf || practice.controparteCf,
      destinatario_pec: primoDestinatario?.pec || current.destinatario_pec,
      fonte_pec_destinatario: primoDestinatario?.fontePecSuggerita || current.fonte_pec_destinatario,
    }))
    setNonPec((current) => ({
      ...current,
      notifica_id: current.notifica_id || practice.numero || practice.id,
      atto_notificato: '',
      atto_sha256: '',
      destinatario_nome: primoDestinatario?.nome || current.destinatario_nome || practice.controparte,
      destinatario_cf: primoDestinatario?.codiceFiscalePiva || current.destinatario_cf || practice.controparteCf,
      ufficio_unep: suggestedUnep?.nome || current.ufficio_unep || practice.procedimento.ufficio,
      ufficio_unep_codice: suggestedUnep?.codice || current.ufficio_unep_codice,
      ufficio_unep_pec: suggestedUnep?.pec || current.ufficio_unep_pec,
    }))
  }

  useEffect(() => {
    if (!data.precompilazione.indicePratiche.length || selectedPracticeId) return
    const params = new URLSearchParams(window.location.search)
    const practiceId = params.get('id_fascicolo') || params.get('id_fasc') || params.get('fascicolo')
    const phase = params.get('fase')
    if (phase === 'deposito') setTab('deposito')
    if (phase === 'notifica') setTab('notifica')
    if (phase === 'unep') setTab('unep')
    if (phase === 'nonpec' || phase === 'non-pec') setTab('nonpec')
    if (!practiceId) return
    if (data.precompilazione.indicePratiche.some((item) => item.id === practiceId)) {
      void selectPracticeById(practiceId)
    }
  }, [data.precompilazione.indicePratiche, selectedPracticeId])

  const buildNotificaPayload = (
    includeDraft: boolean,
    overrides: Partial<typeof notifica> = {},
  ): Record<string, unknown> => {
    const effectiveNotifica = { ...notifica, ...overrides }
    const selectedOfficeAcquired = selectedNotificationDocuments.some((documento) => documento.documentoUfficio || documento.notificaRichiesta)
    const documentOfficeAcquired = selectedOfficeAcquired || officeAcquisitionCompleted
    const { sender, recipients } = currentPecVerificationSubjects()
    const senderEvidence = senderPecVerificationRef.current
    const recipientEvidence = recipientPecVerificationsRef.current
    const senderVerified = pecEvidenceMatches(senderEvidence, sender)
    const recipientsVerified = recipients.length > 0 && recipients.every((subject) => pecEvidenceMatches(recipientEvidence[subject.key], subject))
    const verificaPec = [senderEvidence, ...recipients.map((subject) => recipientEvidence[subject.key])]
      .map((item) => item?.checkedAt || '')
      .filter(Boolean)
      .sort()
      .at(-1) || ''
    const payload: Record<string, unknown> = {
      ...effectiveNotifica,
      practice_id: selectedPracticeId,
      fascicolo_id: selectedPracticeId,
      data_verifica_pec: verificaPec,
      data_ora_invio_pec: effectiveNotifica.data_ora_invio_pec,
      operazione: 'notifica_pec_l53',
      mittente_pec_pubblico_elenco: senderVerified,
      mittente_pec_validata: senderVerified,
      destinatario_pec_pubblico_elenco: recipientsVerified,
      relata_documento_separato: true,
      ricevuta_completa: true,
      verifica_pec_mittente: pecEvidencePayload(senderEvidence),
      verifiche_pec_destinatari: recipients.map((subject) => pecEvidencePayload(recipientEvidence[subject.key])),
      template_fields: modelFields,
      oggetto_pec: data.mandatorySubject,
      documenti: notificationDocumentPayloads(),
      destinatari: notificationRecipientPayloads(),
      attestazione_multipla: notificationNeedsAttestazione,
      documento_ufficio_rilasciato: Boolean(officeDocuments.length || officeAcquisitionRequired || pendingOfficeReleases.length),
      acquisizione_portale_richiesta: officeAcquisitionRequired,
      documento_ufficio_acquisito: documentOfficeAcquired,
      acquisizione_portale_completata: documentOfficeAcquired,
      portale_servizi: data.portaleServizi.defaultPortal,
      portale_acquisizione_href: officeAcquisitionHref,
      pec_ufficio_rilascio: Boolean(officeEvidenceReleases.length || pendingOfficeReleases.length),
      pec_ufficio_eml_file: officeProofRelease?.pecEmlFile || '',
      pec_ufficio_eml_sha256: officeProofRelease?.pecEmlSha256 || '',
      pec_ufficio_message_id: officeProofRelease?.pecMessageId || officeProofRelease?.pecId || '',
    }
    if (includeDraft && relataDraftDirty && relataDraftText.trim()) {
      payload.relata_override_text = relataDraftText.trim()
    }
    return payload
  }

  const downloadAttestation = async () => {
    setAttestationDownloading(true)
    setAttestationDownloadMessage('Preparo l’attestazione unica...')
    try {
      const result = await downloadLegalAttestation(
        data.azioni.attestazioneConformita,
        buildNotificaPayload(false),
      )
      setAttestationDownloadMessage(result.message)
    } catch {
      setAttestationDownloadMessage('Attestazione non generata. Riprova dopo aver controllato i dati indicati.')
    } finally {
      setAttestationDownloading(false)
    }
  }

  const refreshRelataPreview = async (silent = false) => {
    if (!silent) setRelataPreviewWorking(true)
    const preview = await previewLegalRelata(buildNotificaPayload(false)).catch(() => ({
      ...emptyRelataPreview,
      blockers: ['Anteprima compilata non disponibile.'],
    }))
    setRelataPreview(preview)
    if (preview.ok && !relataDraftDirty) {
      setRelataDraftText(preview.previewText)
    }
    if (!silent) setRelataPreviewWorking(false)
  }

  const saveRelataDraft = async () => {
    setRelataDraftSaving(true)
    setRelataDraftMessage('Salvataggio bozza in corso...')
    const saved = await saveLegalRelataDraft({
      practiceId: selectedPracticeId,
      templateId: notifica.template_id,
      relataText: relataDraftText,
    }).catch(() => ({ ok: false, message: 'Salvataggio bozza non completato.', draftId: '', savedAt: '' }))
    setRelataDraftMessage(saved.message)
    setRelataDraftSaving(false)
  }

  const restoreRelataDraftFromModel = () => {
    setRelataDraftText(relataPreview.previewText)
    setRelataDraftDirty(false)
    setRelataDraftMessage('Bozza ripristinata dal modello compilato.')
  }

  const previewStableNotifica = {
    ...notifica,
    data_verifica_pec: '',
    data_ora_invio_pec: '',
  }
  const previewPayloadKey = JSON.stringify({
    notifica: previewStableNotifica,
    modelFields,
    selectedNotificationDocumentIds,
    manualNotificationDocuments,
  })
  const buildSignedRelataPayloadKey = (overrides: Partial<typeof notifica> = {}) => {
    const effectiveNotifica = { ...notifica, ...overrides }
    return JSON.stringify({
      practiceId: selectedPracticeId,
      templateId: effectiveNotifica.template_id,
      luogo: effectiveNotifica.luogo,
      dataRelata: effectiveNotifica.data_relata,
      oraRelata: effectiveNotifica.ora_relata,
      relataText: relataDraftDirty ? relataDraftText.trim() : relataPreview.previewText,
      documents: notificationDocumentPayloads().map((item) => ({
        name: item.nome_file,
        description: item.descrizione,
        origin: item.origine,
        sha256: item.hash_sha256,
      })),
      recipients: notificationRecipientPayloads(),
      modelFields,
    })
  }
  const signedRelataPayloadKey = buildSignedRelataPayloadKey()

  useEffect(() => {
    if (!signedRelata || signedRelata.payloadKey === signedRelataPayloadKey) return
    setSignedRelata(null)
    setNotifica((current) => ({ ...current, relata_firmata: false }))
    setDeposito((current) => refreshDepositReference(current, {
      ...current,
      relata_firmata: '',
      relata_sha256: '',
    }))
    setSignatureMessage('La relata è cambiata: firma nuovamente il documento aggiornato.')
  }, [signedRelataPayloadKey, signedRelata])

  useEffect(() => {
    if (tab === 'notifica' && selectedPracticeId) return
    setSignaturePin('')
  }, [tab, selectedPracticeId])

  useEffect(() => {
    if (loading || tab !== 'notifica') return undefined
    const handle = window.setTimeout(() => {
      void refreshRelataPreview(true)
    }, 700)
    return () => window.clearTimeout(handle)
  }, [previewPayloadKey, loading, tab])

  const buildDepositoPayload = (): Record<string, unknown> => {
    const atti = selectedDepositDocuments.map(depositDocumentPayload)
    const destinatarioCf = deposito.destinatario_cf || notifica.destinatario_cf
    const destinatarioPec = deposito.destinatario_pec || notifica.destinatario_pec
    const fontePec = deposito.fonte_pec_destinatario || notifica.fonte_pec_destinatario
    const payload: Record<string, unknown> = {
      ...deposito,
      destinatario_cf: destinatarioCf,
      destinatario_pec: destinatarioPec,
      fonte_pec_destinatario: fontePec,
      destinatari: [{
        nome: deposito.destinatario_nome || notifica.destinatario_nome,
        codice_fiscale_piva: destinatarioCf,
        pec: destinatarioPec,
        fonte_pec: fontePec,
        rac_file: deposito.rac_file,
        rdac_file: deposito.rdac_file,
        rac_sha256: deposito.rac_sha256,
        rdac_sha256: deposito.rdac_sha256,
      }],
    }
    if (atti.length) {
      payload.atti_notificati = atti
      payload.atto_notificato = atti.map((item) => item.nome_file).join('; ')
      if (atti.length === 1 && atti[0].hash_sha256) payload.atto_sha256 = atti[0].hash_sha256
    }
    return payload
  }

  const buildUnepPayload = (): Record<string, unknown> => ({
    ...unep,
    operazione: 'notifica_unep',
    practice_id: selectedPracticeId,
    fascicolo_id: selectedPracticeId,
    atto_descrizione: unep.atto_notificare || notifica.descrizione_documento,
    destinatario_nome: unep.destinatario_nome || notifica.destinatario_nome,
    destinatario_cf: unep.destinatario_cf || notifica.destinatario_cf,
    destinatario_pec: unep.destinatario_pec || notifica.destinatario_pec,
    fonte_pec_destinatario: unep.fonte_pec_destinatario || notifica.fonte_pec_destinatario,
  })

  const buildNonPecPayload = (): Record<string, unknown> => ({
    ...nonPec,
    operazione: 'notifica_non_pec',
    practice_id: selectedPracticeId,
    fascicolo_id: selectedPracticeId,
    destinatario_nome: nonPec.destinatario_nome || notifica.destinatario_nome,
    destinatario_cf: nonPec.destinatario_cf || notifica.destinatario_cf,
    atto_notificato: nonPec.atto_notificato || notifica.nome_file,
  })

  const run = async (key: TabKey, notificaOverrides: Partial<typeof notifica> = {}) => {
    const scrollResultIntoView = () => window.setTimeout(
      () => resultPanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
      0,
    )
    setWorking(true)
    setResult({ ...emptyResult, message: 'Controllo in corso...' })
    const endpoint = key === 'notifica'
      ? data.azioni.notifica
      : key === 'deposito'
        ? data.azioni.provaDeposito
        : key === 'unep'
          ? data.azioni.unep
          : key === 'nonpec'
            ? data.azioni.nonPec
            : data.azioni.comunicazioneCliente
    if (key === 'notifica') {
      await ensureAutomaticPecVerification()
    }
    const payload = key === 'notifica'
      ? buildNotificaPayload(true, notificaOverrides)
      : key === 'deposito'
        ? buildDepositoPayload()
        : key === 'unep'
          ? buildUnepPayload()
          : key === 'nonpec'
            ? buildNonPecPayload()
            : {
                ...cliente,
                operazione: 'comunicazione_cliente_non_notifica',
                body_override: cliente.corpo,
                template_id: cliente.template_id,
              }
    const response = await postLegalWorkflow(endpoint, payload).catch(() => ({ ...emptyResult, blockers: ['Verifica non completata. Riprova tra poco.'] }))
    if (key === 'cliente' && response.ok) {
      setCliente((current) => ({
        ...current,
        oggetto: response.subject || current.oggetto,
        corpo: response.body || current.corpo,
      }))
    }
    if (key === 'notifica') {
      const checkedAt = new Intl.DateTimeFormat('it-IT', {
        timeZone: 'Europe/Rome',
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }).format(new Date())
      setLastControlLabel(response.ok
        ? `Controllo relata superato il ${checkedAt}.`
        : `Controllo relata eseguito il ${checkedAt}: completa i punti segnalati.`
      )
      setRelataDraftMessage(response.ok
        ? 'Controllo completato: ora puoi firmare la relata e preparare la PEC.'
        : 'Controllo eseguito: l’esito è nel pannello laterale con i punti da completare.'
      )
      if (notificationNeedsAttestazione) setAttestationPreviewOpen(true)
      if (!relataDraftText.trim() && response.relataText) {
        setRelataDraftText(response.relataText)
        setRelataDraftDirty(false)
      }
      setLastControlPayloadKey(notificationControlPayloadKey(payload))
    }
    setResult(response)
    scrollResultIntoView()
    setWorking(false)
  }

  const sendNotification = async () => {
    const invioPec = localDateTime()
    setWorking(true)
    setResult({ ...emptyResult, message: 'Preparazione invio PEC in corso...' })
    await ensureAutomaticPecVerification()
    setNotifica((current) => ({
      ...current,
      data_ora_invio_pec: invioPec,
    }))
    const payload = {
      ...buildNotificaPayload(true),
      operazione: 'invio_pec_l53',
      conferma_invio_pec: true,
      invio_finale: true,
      data_ora_invio_pec: invioPec,
    }
    const response = await postLegalWorkflow(data.azioni.notifica, payload).catch(() => ({ ...emptyResult, blockers: ['Preparazione invio PEC non completata. Riprova tra poco.'] }))
    setResult(response.ok ? {
      ...response,
      message: response.message || 'Piano di invio PEC pronto: verifica allegati, relata firmata e ricevute attese prima della trasmissione.',
    } : response)
    setWorking(false)
  }

  const verifyNotificationPec = async () => {
    await ensureAutomaticPecVerification(true)
    await run('notifica')
  }

  const clearPracticeSelection = () => {
    setSelectedPracticeId('')
    setPracticeSelectionMessage('')
    setSelectedRecipientId('')
    setSelectedRecipientIds([])
    setSelectedDocumentId('')
    setSelectedNotificationDocumentIds([])
    setSelectedDepositDocumentIds([])
    setSelectedClientId('')
  }

  async function selectPracticeById(practiceId: string) {
    if (!practiceId) {
      clearPracticeSelection()
      return
    }
    const cached = practiceDetailsById[practiceId]
      || data.precompilazione.pratiche.find((item) => item.id === practiceId)
    if (cached) {
      applyPractice(cached)
      return
    }
    setPracticeSelectionWorking(true)
    setPracticeSelectionMessage('Caricamento dati pratica...')
    const practice = await getNotificheLegaliPractice(practiceId).catch(() => null)
    if (practice) {
      applyPractice(practice)
    } else {
      setPracticeSelectionMessage('Pratica non caricata. Riprova la selezione.')
    }
    setPracticeSelectionWorking(false)
  }

  const changeNotifica = (key: keyof typeof notifica, value: string | boolean) => {
    setNotifica((current) => ({ ...current, [key]: value }))
    if (key !== 'approvazione_avvocato') {
      setLastControlPayloadKey('')
      setLastControlLabel('')
    }
  }
  const changeNotificationCase = (value: string) => {
    const directive = data.matriceNotifica.cases.find((item) => item.value === value)
    setNotifica((current) => ({
      ...current,
      caso_notifica: value,
      template_id: directive?.templateId || current.template_id,
      procedimento_pendente: directive?.proceedingRequired ? true : current.procedimento_pendente,
    }))
  }
  const changeRecipientRole = (value: string) => {
    const directive = data.matriceNotifica.roles.find((item) => item.value === value)
    setNotifica((current) => ({
      ...current,
      ruolo_destinatario: value,
      template_id: current.caso_notifica === 'ordinaria' && directive?.templateId ? directive.templateId : current.template_id,
      fonte_pec_destinatario: directive?.allowedRegisters.includes(current.fonte_pec_destinatario)
        ? current.fonte_pec_destinatario
        : directive?.allowedRegisters[0] || current.fonte_pec_destinatario,
    }))
  }
  const refreshDepositReference = (current: typeof deposito, next: typeof deposito) => {
    const previousReference = depositReference(current)
    const reference = depositReference(next)
    if (reference && (!next.dati_atto_ricevute || next.dati_atto_ricevute === previousReference || next.dati_atto_ricevute.startsWith('Destinatario:'))) {
      next.dati_atto_ricevute = reference
    }
    return next
  }
  const changeDeposito = (key: keyof typeof deposito, value: string | boolean) => setDeposito((current) => {
    const next = { ...current, [key]: value }
    if (
      key === 'destinatario_nome'
      || key === 'destinatario_cf'
      || key === 'destinatario_pec'
      || key === 'pec_inviata'
      || key === 'rac_file'
      || key === 'rdac_file'
    ) {
      return refreshDepositReference(current, next)
    }
    return next
  })
  const updateDepositoFile = (fileKey: keyof typeof deposito, shaKey: keyof typeof deposito, fileName: string, sha256: string) => {
    setDeposito((current) => refreshDepositReference(current, { ...current, [fileKey]: fileName, [shaKey]: sha256 }))
  }
  const changeUnep = (key: keyof typeof unep, value: string | boolean) => setUnep((current) => ({ ...current, [key]: value }))
  const applyUnepOffice = (office: LegalUnepOffice | null) => setUnep((current) => ({
    ...current,
    ufficio_unep: office?.nome || '',
    ufficio_unep_codice: office?.codice || '',
    ufficio_unep_pec: office?.pec || '',
  }))
  const applyNonPecUnepOffice = (office: LegalUnepOffice | null) => setNonPec((current) => ({
    ...current,
    ufficio_unep: office?.nome || '',
    ufficio_unep_codice: office?.codice || '',
    ufficio_unep_pec: office?.pec || '',
  }))
  const updateUnepFile = (fileKey: keyof typeof unep, shaKey: keyof typeof unep, fileName: string, sha256: string) => {
    setUnep((current) => ({ ...current, [fileKey]: fileName, [shaKey]: sha256 }))
  }
  const changeNonPec = (key: keyof typeof nonPec, value: string) => setNonPec((current) => ({ ...current, [key]: value }))
  const updateNonPecFile = (fileKey: keyof typeof nonPec, shaKey: keyof typeof nonPec, fileName: string, sha256: string) => {
    setNonPec((current) => ({ ...current, [fileKey]: fileName, [shaKey]: sha256 }))
  }
  const saveSignedRelata = async (
    file: File,
    payloadKey: string,
    notificaOverrides: Partial<typeof notifica> = {},
  ) => {
    const form = new FormData()
    form.append('file', file)
    form.append('payload', JSON.stringify(buildNotificaPayload(true, notificaOverrides)))
    const response = await fetch(data.azioni.relataFirmata, {
      method: 'POST',
      body: form,
      credentials: 'same-origin',
    })
    const payload = await response.json().catch(() => ({})) as Record<string, unknown>
    if (!response.ok || payload.ok === false) {
      const blockers = Array.isArray(payload.blockers)
        ? payload.blockers.map((item: unknown) => String(item).replace(/^[A-Z0-9_]+:\s*/, '')).filter(Boolean)
        : []
      throw new Error(String(blockers.join(' ') || payload.message || 'Relata firmata non verificabile.'))
    }
    const record: SignedRelataRecord = {
      documentId: String(payload.documentId || ''),
      fileName: String(payload.fileName || file.name),
      sha256: String(payload.sha256 || ''),
      sourceSha256: String(payload.sourceSha256 || ''),
      previewUrl: String(payload.previewUrl || ''),
      downloadUrl: String(payload.downloadUrl || ''),
      payloadKey,
    }
    setSignedRelata(record)
    setNotifica((current) => ({ ...current, ...notificaOverrides, relata_firmata: true }))
    setDeposito((current) => refreshDepositReference(current, {
      ...current,
      relata_firmata: record.fileName,
      relata_sha256: record.sha256,
    }))
    setSignatureMessage('Relata firmata e salvata nel fascicolo.')
    await run('notifica', { ...notificaOverrides, relata_firmata: true })
  }

  const signRelata = async () => {
    if (!selectedPracticeId) {
      setSignatureMessage('Seleziona prima la pratica della notifica.')
      return
    }
    if (!signaturePin.trim()) {
      setSignatureMessage('Inserisci il PIN del dispositivo di firma.')
      signaturePinRef.current?.focus()
      return
    }
    setSignatureChecking(true)
    setSignatureMessage('Firma e salvataggio della relata in corso...')
    try {
      const signatureOverrides = {
        data_relata: todayLocalDate(),
        ora_relata: currentLocalTime(),
      }
      setNotifica((current) => ({ ...current, ...signatureOverrides }))
      const pecVerification = await ensureAutomaticPecVerification()
      if (!pecVerification.ok) {
        throw new Error(pecVerification.sender?.message || Object.values(pecVerification.recipients)[0]?.message || 'Verifica delle PEC non completata.')
      }
      const status = relataSignerCanSign(signatureStatus) ? signatureStatus : await ensureRelataSignerReady()
      setSignatureStatus(status)
      if (!relataSignerCanSign(status)) throw new Error('Dispositivo di firma non pronto.')

      const sourceResponse = await fetch(data.azioni.relataPdf, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildNotificaPayload(true, signatureOverrides)),
      })
      if (!sourceResponse.ok) {
        const sourceError = await sourceResponse.json().catch(() => ({})) as Record<string, unknown>
        const blockers = Array.isArray(sourceError.blockers)
          ? sourceError.blockers.map((item: unknown) => userFacingNotice(String(item))).filter(Boolean)
          : []
        throw new Error(String(blockers.join(' ') || sourceError.message || 'Completa i dati della relata prima della firma.'))
      }
      const sourceBuffer = await sourceResponse.arrayBuffer()
      const token = status?.token?.[0]
      const certificate = relataSignerCertificate(status)
      const controller = new AbortController()
      const timeout = window.setTimeout(() => controller.abort(), RELATA_LOCAL_SIGNER_TIMEOUT_MS)
      let signerResponse: Response
      try {
        const requestOptions: LocalNetworkRequestInit = {
          method: 'POST',
          mode: 'cors',
          targetAddressSpace: 'local',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify({
            documento: arrayBufferToBase64(sourceBuffer),
            pin: signaturePin.trim(),
            slot_id: token?.slot_id,
            cert_thumbprint: certificate?.thumbprint,
          }),
        }
        signerResponse = await fetch(relataLocalSignerEndpoint('/firma'), requestOptions)
      } finally {
        window.clearTimeout(timeout)
      }
      const signedPayload = await parseRelataSignerResponse(signerResponse)
      const signedBase64 = String(signedPayload.firmato_b64 || '')
      if (!signedBase64) throw new Error('Il dispositivo non ha restituito la relata firmata.')
      const signedBytes = base64ToBytes(signedBase64)
      const signedCopy = new Uint8Array(signedBytes.byteLength)
      signedCopy.set(signedBytes)
      const signedFile = new File([signedCopy.buffer], 'Relata_di_notificazione.pdf.p7m', { type: 'application/pkcs7-mime' })
      await saveSignedRelata(
        signedFile,
        buildSignedRelataPayloadKey(signatureOverrides),
        signatureOverrides,
      )
    } catch (error) {
      const message = error instanceof DOMException && error.name === 'AbortError'
        ? 'Il dispositivo non ha risposto entro 45 secondi. Riprova la firma.'
        : error instanceof Error ? error.message : 'Firma della relata non completata.'
      setNotifica((current) => ({ ...current, relata_firmata: false }))
      setSignatureMessage(message)
    } finally {
      setSignaturePin('')
      setSignatureChecking(false)
    }
  }
  const applyDepositFile = (current: typeof deposito, kind: DepositEvidenceKind, fileName: string, sha256: string): typeof deposito => {
    const next = { ...current }
    const assignFile = (fileKey: keyof typeof deposito, shaKey: keyof typeof deposito, overwriteFile = true) => {
      if (fileName && (overwriteFile || !next[fileKey])) next[fileKey] = fileName as never
      if (sha256 && !next[shaKey]) next[shaKey] = sha256 as never
    }
    if (kind === 'atto') {
      assignFile('atto_notificato', 'atto_sha256', false)
    } else if (kind === 'relata') {
      assignFile('relata_firmata', 'relata_sha256')
    } else if (kind === 'pec') {
      assignFile('pec_inviata', 'pec_inviata_sha256')
    } else if (kind === 'rac') {
      assignFile('rac_file', 'rac_sha256')
    } else if (kind === 'rdac') {
      assignFile('rdac_file', 'rdac_sha256')
    }
    if (next.rac_file && next.rdac_file) next.ricevuta_completa = true
    return refreshDepositReference(current, next)
  }
  const handleDepositEvidenceFiles = async (files: FileList | null) => {
    const selected = Array.from(files || [])
    if (!selected.length) return
    setDepositAutoMessage('Calcolo impronte in corso...')
    const calculated: Array<{ fileName: string; sha256: string; kind: DepositEvidenceKind }> = []
    for (const file of selected) {
      try {
        calculated.push({ fileName: file.name, sha256: await calculateSha256(file), kind: classifyDepositFile(file.name) })
      } catch {
        calculated.push({ fileName: file.name, sha256: '', kind: classifyDepositFile(file.name) })
      }
    }
    setDeposito((current) => calculated.reduce((draft, item) => applyDepositFile(draft, item.kind, item.fileName, item.sha256), current))
    const incomplete = calculated.filter((item) => !item.sha256)
    setDepositAutoMessage(incomplete.length ? 'Alcune impronte non sono state calcolate: riprova o inseriscile manualmente.' : 'File riconosciuti e impronte calcolate.')
  }
  const changeCliente = (key: keyof typeof cliente, value: string) => setCliente((current) => ({ ...current, [key]: value }))
  const changeModelField = (key: string, value: string) => setModelFields((current) => ({ ...current, [key]: value }))

  const currentNotificationDocuments = notificationDocumentPayloads()
  const currentNotificationDocumentsReady = currentNotificationDocuments.length > 0
    && currentNotificationDocuments.every(isNotifiablePayloadDocument)
  const currentNotificationControlPayloadKey = notificationControlPayloadKey(buildNotificaPayload(true))
  const hasPassingNotificationControl = result.ok === true
    && Array.isArray(result.blockers)
    && result.blockers.length === 0
    && lastControlLabel.toLowerCase().includes('superato')
    && lastControlPayloadKey === currentNotificationControlPayloadKey
  const controlBlockers = Array.isArray(result.blockers)
    ? result.blockers.map((item) => userFacingNotice(item)).filter(Boolean)
    : []
  const sendDisabledReasons = [
    !hasPassingNotificationControl ? (controlBlockers.join(' ') || 'esegui il controllo automatico della relata') : '',
    !notifica.relata_firmata ? 'relata firmata non acquisita' : '',
    !notifica.approvazione_avvocato ? 'approvazione finale avvocato mancante' : '',
    !currentNotificationDocumentsReady ? 'seleziona almeno un documento notificabile' : '',
  ].filter(Boolean)
  const canPrepareNotificationSend = !working && sendDisabledReasons.length === 0
  const sendNotificationTitle = canPrepareNotificationSend
    ? 'Prepara invio PEC dal PC locale dopo controllo positivo.'
    : `Invio PEC bloccato: ${sendDisabledReasons.join('; ')}.`
  const currentPecSubjects = currentPecVerificationSubjects()
  const selectedRecipientRegister = data.registriPec.find(
    (item) => item.value === normalizePecSource(notifica.fonte_pec_destinatario),
  )
  const selectedRecipientVerificationSubject = currentPecSubjects.recipients.find(
    (item) => item.source === selectedRecipientRegister?.value
      && item.address === normalizePecAddress(notifica.destinatario_pec),
  ) || currentPecSubjects.recipients.find((item) => item.source === selectedRecipientRegister?.value)
  const selectedRegisterConsulted = Boolean(
    selectedRecipientVerificationSubject
    && publicRegisterConsultedAt[selectedRecipientVerificationSubject.key],
  )
  const currentSenderPecEvidence = pecEvidenceTargets(senderPecVerification, currentPecSubjects.sender)
    ? senderPecVerification
    : null
  const currentRecipientPecEvidence = currentPecSubjects.recipients
    .map((subject) => pecEvidenceTargets(recipientPecVerifications[subject.key], subject) ? recipientPecVerifications[subject.key] : null)
  const verifiedRecipientPecCount = currentRecipientPecEvidence.filter((evidence) => evidence?.verified).length
  const recipientPecStatusOk = currentPecSubjects.recipients.length > 0
    && verifiedRecipientPecCount === currentPecSubjects.recipients.length
  const recipientPecStatusMessage = currentPecSubjects.recipients.length === 0
    ? 'Seleziona almeno un destinatario.'
    : recipientPecStatusOk
      ? `${verifiedRecipientPecCount} ${verifiedRecipientPecCount === 1 ? 'PEC verificata' : 'PEC verificate'}.`
      : currentRecipientPecEvidence.find((evidence) => evidence && !evidence.verified)?.message
        || 'La verifica parte automaticamente con il controllo.'
  const unepTelematica = unep.tipo_notifica_unep === 'telematica'
  const unepEstero = unep.tipo_notifica_unep === 'estero'
  const nonPecRaccomandata = nonPec.tipo_notifica_non_pec === 'raccomandata'
  const nonPecUfficiale = nonPec.tipo_notifica_non_pec === 'ufficiale_giudiziario'
  const nonPecMani = nonPec.tipo_notifica_non_pec === 'mani'
  const nonPecEstero = nonPec.tipo_notifica_non_pec === 'estero'
  const automationSubtitle = tab === 'deposito'
    ? 'Prova e deposito'
    : tab === 'unep'
      ? 'Canale UNEP'
      : tab === 'nonpec'
        ? 'Tracciamento non PEC'
        : 'Notifica L. 53/1994'
  const blockingRules = tab === 'unep'
    ? [
        { icon: <Scale size={15} />, text: 'Ufficio NEP, tipo notifica e destinatario sempre espliciti.' },
        { icon: <FileText size={15} />, text: 'Atto e richiesta o relata separati con impronta del file.' },
        { icon: <UserRound size={15} />, text: 'PEC e pubblico elenco solo per canale telematico; indirizzo fisico per gli altri canali.' },
        { icon: <Inbox size={15} />, text: 'Spese, pagamenti e ritorni dell’ufficio conservati nel fascicolo.' },
      ]
    : tab === 'nonpec'
      ? [
          { icon: <ClipboardCheck size={15} />, text: 'Tipo, data e identificativo notifica obbligatori.' },
          { icon: <UserRound size={15} />, text: 'Destinatario e atto notificato devono essere riconoscibili.' },
          { icon: <FileCheck2 size={15} />, text: 'Raccomandata, relata o prova di consegna devono avere file e impronta.' },
          { icon: <AlertTriangle size={15} />, text: 'Il canale non PEC non viene trattato come PEC L. 53.' },
        ]
      : [
          { icon: <ShieldCheck size={15} />, text: 'PEC mittente e destinatario da pubblico elenco.' },
          { icon: <FileDown size={15} />, text: "Documento d'ufficio rilasciato acquisito dal Portale Servizi prima della relata." },
          { icon: <FileSignature size={15} />, text: 'Relata separata e firmata digitalmente.' },
          { icon: <Inbox size={15} />, text: 'Ricevuta completa e originali digitali conservati.' },
          { icon: <UserRound size={15} />, text: 'Il cliente resta nel percorso informativo.' },
        ]
  const attestationDocuments = currentNotificationDocuments.filter((documento) => originNeedsAttestazione(documento.origine))
  const attestationLawyerName = /^(?:avv\.?|avvocato)\s+/i.test(notifica.avvocato_nome.trim())
    ? notifica.avvocato_nome.trim()
    : `Avv. ${notifica.avvocato_nome.trim() || 'Avvocato notificante'}`
  const attestationRg = notifica.numero_rg && notifica.anno_rg
    ? `R.G. n. ${notifica.numero_rg}/${notifica.anno_rg}`
    : ''
  const attestationPreviewRows = attestationDocuments.map((documento) => {
    const description = (documento.descrizione || documento.nome_file || 'Documento')
      .replace(/\.(?:pdf|p7m|docx?|eml|msg)$/i, '')
      .trim()
    const match = description.match(/^(Decreto fissazione udienza|Atto di citazione|Sentenza|Ordinanza|Provvedimento|Ricorso|Procura|Memoria|Verbale|Istanza)\b\s*,?\s*(.*)$/i)
    if (!match) return `- ${description};`
    const title = match[1].replace(/^./, (value) => value.toUpperCase())
    let detail = match[2].trim().replace(/^[-,:;\s]+/, '')
    if (title === 'Procura' && (!detail || detail.toLowerCase() === 'alle liti')) {
      detail = 'mandato alle liti'
    }
    if (!detail && ['Sentenza', 'Ordinanza', 'Provvedimento', 'Decreto', 'Decreto fissazione udienza'].includes(title)) {
      const participle = ['Sentenza', 'Ordinanza'].includes(title) ? 'emessa' : 'emesso'
      detail = `${participle} dal ${notifica.ufficio_giudiziario || 'ufficio giudiziario indicato'}${notifica.sezione ? ` Sez. ${notifica.sezione}` : ''}`
    }
    return `- ${title}${detail ? `, ${detail}` : ''};`
  })
  const allAttestationsFromFile = attestationDocuments.every((documento) => documento.origine === 'copia_fascicolo_informatico')
  const attestationConclusion = allAttestationsFromFile
    ? `${attestationDocuments.length === 1 ? 'è conforme alla copia informatica presente' : 'sono conformi alle copie informatiche presenti'} nel fascicolo informatico${attestationRg ? ` del relativo procedimento ${attestationRg}` : ''} dal quale ${attestationDocuments.length === 1 ? 'è estratta' : 'sono estratte'}.`
    : `${attestationDocuments.length === 1 ? 'è conforme alla rispettiva fonte indicata' : 'sono conformi alle rispettive fonti indicate'} nella relazione di notificazione.`
  const attestationPreviewText = [
    'ATTESTAZIONE DI CONFORMITÀ',
    '',
    `Il sottoscritto ${attestationLawyerName}${notifica.avvocato_cf ? ` C. F. ${notifica.avvocato_cf}` : ''}${notifica.avvocato_foro ? `, del Foro di ${notifica.avvocato_foro}` : ''},`,
    '',
    'Attesta',
    '',
    `ai sensi di legge, che ${attestationDocuments.length === 1 ? 'la copia informatica' : 'le copie informatiche'}:`,
    ...attestationPreviewRows,
    attestationConclusion,
    ...(notifica.attestazione_conformita.trim()
      ? ['', 'Precisazione dell’avvocato:', notifica.attestazione_conformita.trim()]
      : []),
    '',
    attestationLawyerName,
    'Firmato digitalmente',
  ].join('\n')
  return (
    <main className="iu-content iu-legal-notice-page">
      <section className="iu-legal-hero">
        <div>
          <span className="iu-legal-eyebrow"><Scale size={16} /> Notifiche e comunicazioni</span>
          <h1>Notifica, prova e canali separati</h1>
          <p>PEC L. 53, deposito prova, UNEP, notifiche non PEC e comunicazioni cliente restano distinti. Ogni canale mostra solo i dati necessari e blocca ciò che non è documentato.</p>
        </div>
        <div className="iu-legal-hero__actions">
          <Button href={data.azioni.pecCompose}><Send size={15} /> PEC studio</Button>
          <Button href={data.azioni.clientCompose}><Mail size={15} /> Comunica al cliente</Button>
          <Button variant="primary" href={data.azioni.depositoChecklist}><UploadCloud size={15} /> Controlli deposito</Button>
        </div>
      </section>

      <section className="iu-legal-flows" aria-label="Percorsi distinti">
        <WorkflowCard
          active={tab === 'notifica'}
          icon={<FileSignature size={21} />}
          title="Notifica ex L. 53/1994"
          text="Controparte, difensori, PA, imprese, professionisti o terzi."
          onClick={() => { setTab('notifica'); setResult(emptyResult) }}
        />
        <WorkflowCard
          active={tab === 'deposito'}
          icon={<FileCheck2 size={21} />}
          title="Deposito prova notifica"
          text="Atto notificato, relata firmata e ricevute originali."
          onClick={() => { setTab('deposito'); setResult(emptyResult) }}
        />
        <WorkflowCard
          active={tab === 'unep'}
          icon={<Scale size={21} />}
          title="UNEP"
          text="Richieste a mani, posta, estero o telematiche."
          onClick={() => { setTab('unep'); setResult(emptyResult) }}
        />
        <WorkflowCard
          active={tab === 'nonpec'}
          icon={<ClipboardCheck size={21} />}
          title="Non PEC"
          text="Raccomandata, ufficiale giudiziario e prove cartacee."
          onClick={() => { setTab('nonpec'); setResult(emptyResult) }}
        />
        <WorkflowCard
          active={tab === 'cliente'}
          icon={<UserRound size={21} />}
          title="Comunica al cliente"
          text="Messaggio informativo, senza relata e senza oggetto L. 53."
          onClick={() => { setTab('cliente'); setResult(emptyResult) }}
        />
      </section>

      <section className="iu-legal-status-line">
        <span className={loading ? '' : 'is-ok'}>{loading ? 'Caricamento dati studio...' : 'Percorsi separati pronti'}</span>
        <small><LockKeyhole size={14} /> Nessun invio automatico: firma, invio e deposito restano confermati dall'avvocato.</small>
      </section>

      <section className="iu-legal-layout">
        <div className="iu-legal-form-column">
          {tab === 'notifica' ? (
            <Panel title="Relata e invio controllato" subtitle="Percorso per destinatari esterni allo studio" icon={<FileSignature size={17} />}>
              <div className="iu-legal-auto-box">
                <div className="iu-legal-auto-box__title">
                  <WandSparkles size={17} />
                  <div>
                    <strong>Compilazione assistita da IUSENTRA</strong>
                    <span>{automaticValuesCount} dati già proposti da studio, fascicoli, soggetti e documenti.</span>
                  </div>
                </div>
                <div className="iu-legal-form-grid">
                  <PracticePicker
                    practices={data.precompilazione.indicePratiche}
                    value={selectedPracticeId}
                    loading={practiceSelectionWorking}
                    message={practiceSelectionMessage}
                    hint="Cerca e scegli una pratica per compilare assistito, procedimento, destinatari e documenti già presenti."
                    onSelect={(practiceId) => { void selectPracticeById(practiceId) }}
                  />
                  <Field label="Aggiungi destinatario suggerito" hint={recipientSuggestions.length ? 'Puoi aggiungere più destinatari: IUSENTRA preparerà una PEC distinta per ciascuno.' : 'Aggiungi soggetti con PEC alla pratica per compilare anche questo campo.'}>
                    <select
                      value=""
                      onChange={(event) => {
                        const recipient = recipientSuggestions.find((item) => item.id === event.currentTarget.value)
                        if (recipient) applyRecipient(recipient)
                      }}
                    >
                      <option value="">Aggiungi destinatario</option>
                      {recipientSuggestions.map((item) => (
                        <option value={item.id} key={`${item.id}-${item.ruolo}`}>
                          {selectedRecipientIds.includes(item.id) ? '✓ ' : ''}{item.label}{item.pec ? ` - ${item.pec}` : ''}
                        </option>
                      ))}
                    </select>
                  </Field>
                  {visibleRecipientSuggestions.length ? (
                    <div className="iu-legal-recipient-picker iu-legal-field--wide" aria-label="Destinatari suggeriti">
                      {visibleRecipientSuggestions.map((item) => {
                        const selected = selectedRecipientIds.includes(item.id)
                        return (
                          <button
                            type="button"
                            key={`${item.id}-${item.ruolo}-choice`}
                            className={selected ? 'is-selected' : ''}
                            onClick={() => selected ? removeRecipient(item.id) : applyRecipient(item)}
                          >
                            <strong>{item.label || item.nome}</strong>
                            <span>{[item.ruoloPratica || item.ruolo, item.pec, item.parteRappresentata ? `parte: ${item.parteRappresentata}` : ''].filter(Boolean).join(' · ')}</span>
                          </button>
                        )
                      })}
                    </div>
                  ) : null}
                  {selectedRecipients.length ? (
                    <div className="iu-legal-selected-recipients iu-legal-field--wide" aria-label="Destinatari scelti per la notifica">
                      {selectedRecipients.map((item, index) => (
                        <span key={`${item.id}-${index}`}>
                          <UserRound size={15} />
                          <em>{index + 1}. {item.nome || item.label}{item.pec ? ` - ${item.pec}` : ''}</em>
                          {selectedRecipientId === item.id ? <strong>campi principali</strong> : null}
                          <button type="button" aria-label="Rimuovi destinatario" onClick={() => removeRecipient(item.id)}>
                            <Trash2 size={14} />
                          </button>
                        </span>
                      ))}
                    </div>
                  ) : null}
                  <div className="iu-legal-document-picker iu-legal-field--wide">
                    <div className="iu-legal-template-preview__header">
                      <div>
                        <strong>Documenti da notificare</strong>
                        <span>{documentSuggestions.length ? "I documenti della pratica sono proposti, ma entrano nella relata solo dopo la scelta dell'avvocato." : "Seleziona una pratica con documenti per compilare l'elenco."}</span>
                      </div>
                      {documentSuggestions.length ? (
                        <div className="iu-legal-picker-actions">
                          <button type="button" onClick={() => setSelectedNotificationDocumentIds(documentSuggestions.filter(isNotifiableNotificationDocument).map((item) => item.id).filter(Boolean))}>
                            <CheckCircle2 size={14} /> Tutti notificabili
                          </button>
                          <button type="button" onClick={() => setSelectedNotificationDocumentIds([])}>
                            <Trash2 size={14} /> Svuota
                          </button>
                        </div>
                      ) : null}
                    </div>
                    <div className="iu-legal-evidence-uploader iu-legal-evidence-uploader--compact">
                      <div className="iu-legal-evidence-uploader__text">
                        <strong>Allegati esterni alla pratica</strong>
                        <span>PDF/PDF-A/P7M sono i documenti notificabili proposti; EML/MSG entrano nell'invio solo se scelti manualmente.</span>
                        {notificationFilesMessage ? <small>{notificationFilesMessage}</small> : null}
                        {documentHydrationMessage ? <small>{documentHydrationMessage}</small> : null}
                      </div>
                      <label className="iu-legal-evidence-uploader__button">
                        <Paperclip size={17} />
                        Scegli allegati
                        <input
                          type="file"
                          multiple
                          accept=".pdf,.pdfa,.p7m,.eml,.msg"
                          onChange={(event) => void handleNotificationFiles(event.currentTarget.files)}
                        />
                      </label>
                    </div>
                    {documentSuggestions.length ? (
                      <div className="iu-legal-document-picker__grid">
                        {documentSuggestions.map((documento) => (
                          <label className="iu-legal-check" key={documento.id}>
                            <input
                              type="checkbox"
                              checked={selectedNotificationDocumentIds.includes(documento.id)}
                              onChange={(event) => toggleNotificationDocument(documento, event.currentTarget.checked)}
                            />
                            <span className="iu-legal-document-line">
                              <strong>{documentPrimaryName(documento)}</strong>
                              {documentDetailLine(documento) ? <small>{documentDetailLine(documento)}</small> : null}
                              {hasEmailEvidenceExtension(documentPrimaryName(documento)) ? <em>EML/MSG selezionabile manualmente</em> : null}
                              {documento.necessitaAttestazione ? <em>Incluso nell’attestazione unica in relata</em> : null}
                            </span>
                          </label>
                        ))}
                      </div>
                    ) : <p className="iu-legal-empty">Nessun documento disponibile per la pratica selezionata.</p>}
                    {currentNotificationDocuments.length ? (
                      <div className="iu-legal-selected-documents" aria-label="Elenco documenti allegati alla relata">
                        {currentNotificationDocuments.map((documento, index) => (
                          <span key={`${documento.nome_file}-${index}`}>
                            <FileText size={15} />
                            <em>
                              <strong>{index + 1}. {documento.nome_file || 'Documento senza nome'}</strong>
                              {documento.descrizione ? <small>{documento.descrizione}</small> : null}
                            </em>
                            {'id' in documento ? (
                              <button type="button" aria-label="Rimuovi allegato" onClick={() => removeManualNotificationDocument(String(documento.id))}>
                                <Trash2 size={14} />
                              </button>
                            ) : null}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                  <div className={`iu-legal-office-monitor iu-legal-office-monitor--${officeMonitor?.stato || 'monitoraggio'} iu-legal-field--wide`}>
                    <div className="iu-legal-office-monitor__head">
                      <div>
                        <strong>{officeAcquisitionRequired ? "Provvedimento da scaricare dal portale" : officeAcquisitionCompleted ? "Documento d'ufficio già in atti" : 'Controllo PEC ufficio pronto'}</strong>
                        <span>{officeMonitor?.messaggio || "IUSENTRA controlla le PEC dell'ufficio, apre l'acquisizione mirata e collega solo il provvedimento comunicato per la notifica."}</span>
                      </div>
                      <a href={officeAcquisitionHref}><FileDown size={15}/> {officeAcquisitionRequired ? 'Scarica dal portale' : 'Documenti e atti'}</a>
                      {officeAcquisitionRequired && officePecHref ? <a href={officePecHref}><Inbox size={15}/> Apri PEC</a> : null}
                    </div>
                    {pendingOfficeReleases.length ? (
                      <div className="iu-legal-office-monitor__list" aria-label="Documenti comunicati dall'ufficio">
                        {pendingOfficeReleases.map((release, index) => (
                          <span key={release.documentoId || release.riferimentoPortale || `${release.nome}-${index}`}>
                            <Inbox size={15}/>
                            <em>{release.nome || release.tipo || "Documento d'ufficio"}</em>
                            <small>{[release.fontePortale || data.portaleServizi.label, release.ufficio, release.numeroRg && release.annoRg ? `R.G. ${release.numeroRg}/${release.annoRg}` : '', release.dataDeposito ? formatDateIt(release.dataDeposito, release.dataDeposito) : ''].filter(Boolean).join(' · ')}</small>
                          </span>
                        ))}
                      </div>
                    ) : null}
                    {officeDocuments.length ? (
                      <div className="iu-legal-office-monitor__list" aria-label="Documenti d'ufficio acquisiti">
                        {officeDocuments.map((documento) => (
                          <span key={documento.id}>
                            <FileText size={15}/>
                            <em>{documento.label || documento.nomeFile}</em>
                            <small>{documento.notificaRichiesta ? 'Da notificare' : 'Da verificare'}</small>
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>
                <div className="iu-legal-auto-notes">
                  <span><FolderOpen size={15} /> {data.precompilazione.totalePratiche || data.precompilazione.indicePratiche.length} pratiche ricercabili per la compilazione assistita.</span>
                  <span><UserRound size={15} /> {recipientSuggestions.length} destinatari con PEC suggeribili.</span>
                  <span><FileText size={15} /> {documentSuggestions.length} documenti selezionabili dalla pratica corrente.</span>
                </div>
              </div>
              <div className="iu-legal-form-grid">
                <Field label="Modello relata" wide hint={selectedTemplate?.description || 'Il sistema può selezionare automaticamente il modello in base ai dati inseriti.'}>
                  <select
                    value={notifica.template_id}
                    onChange={(event) => {
                      changeNotifica('template_id', event.currentTarget.value)
                      setRelataDraftDirty(false)
                      setRelataDraftMessage('')
                    }}
                  >
                    {data.modelliRelata.map((item) => <option value={item.value} key={item.value}>{item.code ? `${item.code} - ${item.label}` : item.label}</option>)}
                  </select>
                </Field>
                <Field label="Caso notifica" wide hint={selectedCaseDirective?.note || 'Scegli il caso operativo: destinatario, modello e campi richiesti vengono controllati insieme.'}>
                  <select value={notifica.caso_notifica} onChange={(event) => changeNotificationCase(event.currentTarget.value)}>
                    {(data.matriceNotifica.cases.length ? data.matriceNotifica.cases : [{ value: 'ordinaria', label: 'Notifica ordinaria a mezzo PEC', templateId: 'relata_pec_base_l53', requiredFields: [], allowedRegisters: [], allowedRecipientRoles: [], proceedingRequired: false, recipientRule: '', legalBasis: [], note: '' }]).map((item) => (
                      <option value={item.value} key={item.value}>{item.label}</option>
                    ))}
                  </select>
                </Field>
                {(selectedCaseDirective || selectedRoleDirective) ? (
                  <div className="iu-legal-directive-box iu-legal-field--wide">
                    {selectedCaseDirective ? <span><ClipboardCheck size={15}/> {selectedCaseDirective.label}{selectedCaseDirective.requiredFields.length ? `: ${selectedCaseDirective.requiredFields.length} dati obbligatori` : ''}</span> : null}
                    {selectedRoleDirective ? <span><ShieldCheck size={15}/> {selectedRoleDirective.label}: {selectedRoleDirective.allowedRegisters.length ? selectedRoleDirective.allowedRegisters.join(', ') : 'pubblico elenco da verificare'}</span> : null}
                    {selectedCaseDirective?.recipientRule ? <span><Info size={15}/> {selectedCaseDirective.recipientRule}</span> : null}
                    {selectedCaseDirective?.legalBasis.length ? <span><Scale size={15}/> Fonti: {selectedCaseDirective.legalBasis.map((item) => item.label).join('; ')}</span> : null}
                  </div>
                ) : null}
                <div className="iu-legal-template-preview iu-legal-field--wide">
                  <div className="iu-legal-template-preview__header">
                    <div>
                      <strong>Anteprima modello relata</strong>
                      <span>{selectedTemplate ? `${selectedTemplate.code ? `${selectedTemplate.code} - ` : ''}${selectedTemplate.label}` : 'Seleziona un modello'}</span>
                    </div>
                    {selectedTemplate?.custom ? <em>Personalizzato</em> : null}
                  </div>
                  <div className="iu-legal-preview-stack">
                    <section>
                      <div className="iu-legal-preview-stack__title">
                        <strong>Testo modello</strong>
                        <span>Campi automatici visibili prima della compilazione.</span>
                      </div>
                      <pre>{selectedTemplate?.previewText || 'Il testo del modello sarà visibile qui prima del controllo.'}</pre>
                    </section>
                    <section>
                      <div className="iu-legal-preview-stack__title iu-legal-preview-stack__title--action">
                        <div>
                          <strong>Anteprima compilata</strong>
                          <span>{relataPreview.templateLabel || selectedTemplate?.label || 'Modello selezionato'}</span>
                        </div>
                        <button type="button" disabled={relataPreviewWorking} onClick={() => refreshRelataPreview(false)}>
                          <RefreshCw size={14} /> {relataPreviewWorking ? 'Aggiorno...' : 'Aggiorna'}
                        </button>
                      </div>
                      {relataPreview.blockers.length ? (
                        <div className="iu-legal-list iu-legal-list--blockers">
                          {relataPreview.blockers.map((item) => <span key={item}><AlertTriangle size={15} /> {userFacingNotice(item)}</span>)}
                        </div>
                      ) : (
                        <pre>{relataPreview.previewText || 'Compila i dati principali per vedere la relata con valori e dati mancanti evidenziati.'}</pre>
                      )}
                      {relataPreview.missingFields.length ? (
                        <div className="iu-legal-missing-fields" aria-label="Dati mancanti nell'anteprima compilata">
                          {relataPreview.missingFields.map((item) => <span key={item}>[dato mancante: {item}]</span>)}
                        </div>
                      ) : null}
                    </section>
                  </div>
                  <div className="iu-legal-draft-editor">
                    <div className="iu-legal-preview-stack__title iu-legal-preview-stack__title--action">
                      <div>
                        <strong>Modifica bozza relata</strong>
                        <span>{relataDraftDirty ? 'Bozza modificata manualmente' : 'Testo allineato al modello compilato'}</span>
                      </div>
                      {relataDraftDirty ? <em>Bozza modificata manualmente</em> : null}
                    </div>
                    <textarea
                      value={relataDraftText}
                      rows={12}
                      onChange={(event) => {
                        setRelataDraftText(event.currentTarget.value)
                        setRelataDraftDirty(true)
                        setRelataDraftMessage('')
                      }}
                      placeholder="Aggiorna l'anteprima compilata, poi modifica qui la bozza della relata per questa notifica."
                    />
                    {relataDraftMessage ? <p className="iu-legal-template-message">{relataDraftMessage}</p> : null}
                    <div className="iu-legal-template-actions">
                      <button type="button" disabled={relataDraftSaving || !relataDraftText.trim()} onClick={saveRelataDraft}>
                        <Save size={15} /> {relataDraftSaving ? 'Salvataggio...' : 'Salva bozza per questa notifica'}
                      </button>
                      <button type="button" disabled={!relataPreview.previewText} onClick={restoreRelataDraftFromModel}>
                        <RotateCcw size={15} /> Ripristina dal modello
                      </button>
                    </div>
                  </div>
                  <div className="iu-legal-template-actions">
                    <button type="button" onClick={() => startTemplateEdit('copy')}><PencilLine size={15} /> Personalizza modello</button>
                    <button type="button" onClick={() => startTemplateEdit('new')}><PlusCircle size={15} /> Nuovo modello su misura</button>
                  </div>
                  <small>La bozza compilata resta legata a questa notifica; solo il testo con campi automatici può diventare modello riutilizzabile.</small>
                </div>
                {templateEditorOpen ? (
                  <div className="iu-legal-template-editor iu-legal-field--wide">
                    <div className="iu-legal-template-preview__header">
                      <div>
                        <strong>Modello personalizzato</strong>
                        <span>Scrivi il testo una volta, poi inserisci i campi automatici necessari.</span>
                      </div>
                      <button type="button" onClick={() => setTemplateEditorOpen(false)}>Chiudi</button>
                    </div>
                    <div className="iu-legal-form-grid">
                      <Field label="Nome modello"><input value={templateDraft.label} onChange={(event) => setTemplateDraft((current) => ({ ...current, label: event.currentTarget.value }))} /></Field>
                      <Field label="Descrizione"><input value={templateDraft.description} onChange={(event) => setTemplateDraft((current) => ({ ...current, description: event.currentTarget.value }))} /></Field>
                      <Field label="Testo modello" wide hint="Usa i campi automatici per far compilare a IUSENTRA pratica, assistito, destinatario, documenti e procedimento.">
                        <textarea
                          ref={templateBodyRef}
                          value={templateDraft.body}
                          rows={16}
                          onChange={(event) => setTemplateDraft((current) => ({ ...current, body: event.currentTarget.value }))}
                        />
                      </Field>
                    </div>
                    <label className="iu-legal-check">
                      <input type="checkbox" checked={templateDraft.requiresProceeding} onChange={(event) => setTemplateDraft((current) => ({ ...current, requiresProceeding: event.currentTarget.checked }))} />
                      <span>Richiede sempre i dati del procedimento</span>
                    </label>
                    <div className="iu-legal-field-palette">
                      <strong>Campi automatici disponibili</strong>
                      {templateFieldGroups.map(([group, fields]) => (
                        <div className="iu-legal-field-palette__group" key={group}>
                          <span>{group}</span>
                          <div>
                            {fields.map((field) => (
                              <button type="button" key={`${group}-${field.token}`} onClick={() => insertTemplateToken(field.token)}>{field.label}</button>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                    {templateMessage ? <p className="iu-legal-template-message">{templateMessage}</p> : null}
                    <div className="iu-legal-template-actions">
                      <button type="button" disabled={templateSaving} onClick={saveTemplate}><ShieldCheck size={15} /> {templateSaving ? 'Salvataggio...' : 'Salva come modello riutilizzabile'}</button>
                    </div>
                  </div>
                ) : null}
                <Field label="Codice pratica"><input value={notifica.pratica_codice} onChange={(event) => changeNotifica('pratica_codice', event.currentTarget.value)} /></Field>
                <Field label="Oggetto PEC obbligatorio" wide hint="Il valore è bloccato dal percorso guidato.">
                  <input value={data.mandatorySubject} readOnly />
                </Field>
                <Field label="Avvocato notificante"><input value={notifica.avvocato_nome} onChange={(event) => changeNotifica('avvocato_nome', event.currentTarget.value)} /></Field>
                <Field label="Codice fiscale avvocato"><input value={notifica.avvocato_cf} onChange={(event) => changeNotifica('avvocato_cf', event.currentTarget.value.toUpperCase())} /></Field>
                <Field label="Ordine / foro"><input value={notifica.avvocato_foro} onChange={(event) => changeNotifica('avvocato_foro', event.currentTarget.value)} /></Field>
                <Field label="PEC notificante"><input type="email" value={notifica.mittente_pec} onChange={(event) => changeNotifica('mittente_pec', event.currentTarget.value)} /></Field>
                <Field label="Indirizzo studio"><input value={notifica.studio_indirizzo} onChange={(event) => changeNotifica('studio_indirizzo', event.currentTarget.value)} /></Field>
                <Field label="CAP studio"><input inputMode="numeric" maxLength={5} value={notifica.studio_cap} onChange={(event) => changeNotifica('studio_cap', event.currentTarget.value.replace(/\D/g, '').slice(0, 5))} /></Field>
                <Field label="Città studio"><input value={notifica.studio_citta} onChange={(event) => changeNotifica('studio_citta', event.currentTarget.value)} /></Field>
                <Field label="Provincia studio"><input maxLength={2} value={notifica.studio_provincia} onChange={(event) => changeNotifica('studio_provincia', event.currentTarget.value.toUpperCase().replace(/[^A-Z]/g, '').slice(0, 2))} /></Field>
                <Field label="Luogo relata" wide><input value={notifica.luogo} onChange={(event) => changeNotifica('luogo', event.currentTarget.value)} /></Field>
                <Field label="Data relata"><input type="date" value={notifica.data_relata} onChange={(event) => changeNotifica('data_relata', event.currentTarget.value)} /></Field>
                <Field label="Ora relata" hint="Ora italiana riportata nella relata."><input type="time" step="60" value={notifica.ora_relata} onChange={(event) => changeNotifica('ora_relata', event.currentTarget.value)} /></Field>
                <Field label="Parte assistita"><input value={notifica.assistito_nome} onChange={(event) => changeNotifica('assistito_nome', event.currentTarget.value)} /></Field>
                <Field label="C.F. / P. IVA assistito"><input value={notifica.assistito_cf} onChange={(event) => changeNotifica('assistito_cf', event.currentTarget.value.toUpperCase())} /></Field>
                <Field label="Ruolo destinatario">
                  <select value={notifica.ruolo_destinatario} onChange={(event) => changeRecipientRole(event.currentTarget.value)}>
                    {data.ruoliDestinatario.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    <option value="cliente">Cliente (da bloccare come notifica ordinaria)</option>
                  </select>
                </Field>
                <Field label="Destinatario"><input value={notifica.destinatario_nome} onChange={(event) => changeNotifica('destinatario_nome', event.currentTarget.value)} /></Field>
                <Field label="C.F. / P. IVA destinatario"><input value={notifica.destinatario_cf} onChange={(event) => changeNotifica('destinatario_cf', event.currentTarget.value.toUpperCase())} /></Field>
                <Field label="PEC destinatario"><input type="email" value={notifica.destinatario_pec} onChange={(event) => changeNotifica('destinatario_pec', event.currentTarget.value)} /></Field>
                <Field label="Elenco pubblico PEC">
                  <select value={notifica.fonte_pec_destinatario} onChange={(event) => changeNotifica('fonte_pec_destinatario', event.currentTarget.value)}>
                    {data.registriPec.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                  </select>
                </Field>
                <Field label="Parte rappresentata"><input value={notifica.destinatario_parte_rappresentata} onChange={(event) => changeNotifica('destinatario_parte_rappresentata', event.currentTarget.value)} /></Field>
                <div className="iu-legal-pec-verification iu-legal-field--wide" aria-live="polite">
                  <div className="iu-legal-pec-verification__header">
                    <div>
                      <strong>Verifica automatica delle PEC</strong>
                      <span>Il sistema controlla indirizzo, soggetto ed elenco prima di preparare la relata.</span>
                    </div>
                    <button type="button" onClick={() => void verifyNotificationPec()} disabled={pecVerificationWorking || working}>
                      <RefreshCw size={15} className={pecVerificationWorking ? 'is-spinning' : ''} />
                      {pecVerificationWorking ? 'Verifica...' : 'Verifica di nuovo'}
                    </button>
                  </div>
                  {selectedRecipientRegister?.requiresUserConfirmation ? (
                    <div className="iu-legal-register-actions">
                      <button type="button" onClick={openSelectedPublicRegister} disabled={pecVerificationWorking || publicRegisterConfirmationWorking}>
                        <ExternalLink size={15} /> {selectedRecipientRegister.actionLabel}
                      </button>
                      <button
                        type="button"
                        className="is-primary"
                        onClick={() => void confirmSelectedPublicRegister()}
                        disabled={!selectedRegisterConsulted || !selectedPracticeId || publicRegisterConfirmationWorking || pecVerificationWorking}
                      >
                        <ShieldCheck size={15} /> {publicRegisterConfirmationWorking ? 'Registrazione...' : 'Conferma soggetto e PEC'}
                      </button>
                      <span>
                        {selectedRegisterConsulted
                          ? 'Confronta soggetto, codice fiscale e PEC visualizzati, poi conferma.'
                          : 'Apri la fonte selezionata per cercare il soggetto.'}
                      </span>
                    </div>
                  ) : selectedRecipientRegister && !selectedRecipientRegister.validForNotification ? (
                    <div className="iu-legal-register-warning">
                      <AlertTriangle size={16} />
                      <span>{selectedRecipientRegister.label} non certifica indirizzi PEC utilizzabili per questa notifica.</span>
                    </div>
                  ) : null}
                  <div className={`iu-legal-pec-verification__row ${currentSenderPecEvidence?.verified ? 'is-ok' : currentSenderPecEvidence ? 'is-error' : ''}`}>
                    {currentSenderPecEvidence?.verified ? <CheckCircle2 size={17} /> : <ShieldCheck size={17} />}
                    <div>
                      <strong>Notificante</strong>
                      <span>{currentSenderPecEvidence?.verified
                        ? `PEC verificata${currentSenderPecEvidence.checkedAt ? ` il ${localClockLabel(currentSenderPecEvidence.checkedAt)}` : ''}.`
                        : currentSenderPecEvidence?.message || 'La verifica parte automaticamente con il controllo.'}</span>
                    </div>
                  </div>
                  <div className={`iu-legal-pec-verification__row ${recipientPecStatusOk ? 'is-ok' : currentRecipientPecEvidence.some(Boolean) ? 'is-error' : ''}`}>
                    {recipientPecStatusOk ? <CheckCircle2 size={17} /> : <ShieldCheck size={17} />}
                    <div>
                      <strong>{currentPecSubjects.recipients.length === 1 ? 'Destinatario' : 'Destinatari'}</strong>
                      <span>{recipientPecStatusMessage}</span>
                    </div>
                  </div>
                  {pecVerificationMessage ? <small>{pecVerificationMessage}</small> : null}
                </div>
                <Field label={selectedNotificationDocuments.length ? 'Nome file aggiuntivo' : 'Nome file atto'}><input value={notifica.nome_file} onChange={(event) => changeNotifica('nome_file', event.currentTarget.value)} placeholder="ricorso.pdf" /></Field>
                <Field label={selectedNotificationDocuments.length ? 'Descrizione aggiuntiva' : 'Descrizione documento'}><input value={notifica.descrizione_documento} onChange={(event) => changeNotifica('descrizione_documento', event.currentTarget.value)} /></Field>
                <Field label={selectedNotificationDocuments.length ? 'Origine documento aggiuntivo' : 'Origine documento'}>
                  <select value={notifica.origine_documento} onChange={(event) => changeNotifica('origine_documento', event.currentTarget.value)}>
                    {data.originiDocumento.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                  </select>
                </Field>
                {notifica.origine_documento === 'comunicazione_cancelleria' ? (
                  <Field label="Data comunicazione cancelleria"><input type="date" value={notifica.data_comunicazione_cancelleria} onChange={(event) => changeNotifica('data_comunicazione_cancelleria', event.currentTarget.value)} /></Field>
                ) : null}
                <Field label="Impronta allegato" hint="Facoltativa per la notifica; viene compilata automaticamente quando scegli file dal browser.">
                  <input value={notifica.hash_sha256} maxLength={64} onChange={(event) => changeNotifica('hash_sha256', normalizeSha256Input(event.currentTarget.value))} placeholder="64 caratteri esadecimali" />
                </Field>
                <div className="iu-legal-template-actions iu-legal-field--wide">
                  <button type="button" onClick={addManualNotificationDocument}>
                    <PlusCircle size={15} /> Aggiungi allegato manuale
                  </button>
                </div>
                {notificationNeedsAttestazione ? (
                  <div className="iu-legal-action-panel iu-legal-field--wide">
                    <div className="iu-legal-action-panel__head">
                      <div>
                        <strong>Attestazione unica nella relata</strong>
                        <span>Una sola dichiarazione comprende {attestationDocuments.length} {attestationDocuments.length === 1 ? 'documento' : 'documenti'}.</span>
                      </div>
                      <div className="iu-legal-action-panel__actions">
                        <button type="button" onClick={() => setAttestationPreviewOpen((current) => !current)}>
                          <ClipboardCheck size={15} /> {attestationPreviewOpen ? 'Nascondi testo unico' : 'Vedi testo unico'}
                        </button>
                        <button type="button" disabled={attestationDownloading} onClick={downloadAttestation}>
                          <FileDown size={15} /> {attestationDownloading ? 'Preparazione...' : 'Scarica attestazione unica'}
                        </button>
                      </div>
                    </div>
                    {attestationPreviewOpen ? (
                      <pre>{attestationPreviewText}</pre>
                    ) : null}
                    {attestationDownloadMessage ? <p className="iu-legal-template-message" role="status">{attestationDownloadMessage}</p> : null}
                    <Field label="Precisazione facoltativa dell'avvocato" wide hint="Il sistema inserisce già la dichiarazione cumulativa nella relata. Usa questo campo solo per una precisazione, senza ripetere l’attestazione.">
                      <textarea value={notifica.attestazione_conformita} rows={4} onChange={(event) => changeNotifica('attestazione_conformita', event.currentTarget.value)} />
                    </Field>
                  </div>
                ) : null}
                <Field label="Integrazione libera dell'avvocato" wide hint="Facoltativa: il testo viene aggiunto alla relata generata senza sostituire i controlli automatici.">
                  <textarea value={notifica.note_integrative_relata} rows={3} onChange={(event) => changeNotifica('note_integrative_relata', event.currentTarget.value)} />
                </Field>
                {selectedTemplate?.requiresProceeding ? (
                  <label className="iu-legal-check iu-legal-field--wide"><input type="checkbox" checked readOnly /><span>Questo modello richiede i dati del procedimento.</span></label>
                ) : null}
                <label className="iu-legal-check iu-legal-field--wide"><input type="checkbox" checked={notifica.procedimento_pendente} onChange={(event) => changeNotifica('procedimento_pendente', event.currentTarget.checked)} /><span>Notifica in corso di procedimento</span></label>
                {notifica.procedimento_pendente ? (
                  <>
                    <Field label="Ufficio giudiziario"><input value={notifica.ufficio_giudiziario} onChange={(event) => changeNotifica('ufficio_giudiziario', event.currentTarget.value)} /></Field>
                    <Field label="Sezione"><input value={notifica.sezione} onChange={(event) => changeNotifica('sezione', event.currentTarget.value)} /></Field>
                    <Field label="Numero RG"><input value={notifica.numero_rg} onChange={(event) => changeNotifica('numero_rg', event.currentTarget.value)} /></Field>
                    <Field label="Anno RG"><input value={notifica.anno_rg} onChange={(event) => changeNotifica('anno_rg', event.currentTarget.value)} /></Field>
                  </>
                ) : null}
                {selectedTemplate?.fields.length ? (
                  <div className="iu-legal-model-fields iu-legal-field--wide">
                    <strong>Dati del modello scelto</strong>
                    <div className="iu-legal-form-grid">
                      {selectedTemplate.fields.map((field) => (
                        <Field label={field.label} key={field.name}>
                          <input value={modelFields[field.name] || ''} onChange={(event) => changeModelField(field.name, event.currentTarget.value)} />
                        </Field>
                      ))}
                    </div>
                  </div>
                ) : null}
                <div className="iu-legal-action-panel iu-legal-field--wide" aria-busy={signatureChecking}>
                  <div className="iu-legal-action-panel__head">
                    <div>
                      <strong>Relata firmata digitalmente</strong>
                      <span>IUSENTRA genera la relata corrente, la firma sul PC e la salva automaticamente nel fascicolo.</span>
                    </div>
                    <div className="iu-legal-signature-actions">
                      <label className="iu-legal-signature-pin">
                        <span>PIN</span>
                        <input
                          ref={signaturePinRef}
                          type="password"
                          inputMode="numeric"
                          autoComplete="off"
                          value={signaturePin}
                          onChange={(event) => setSignaturePin(event.currentTarget.value)}
                          disabled={signatureChecking || !selectedPracticeId}
                          placeholder="PIN dispositivo"
                          aria-label="PIN del dispositivo di firma"
                          aria-describedby={signatureMessage ? 'relata-signature-privacy relata-signature-status' : 'relata-signature-privacy'}
                        />
                      </label>
                      <button type="button" className="iu-legal-signature-button iu-legal-signature-button--primary" onClick={() => void signRelata()} disabled={signatureChecking || !selectedPracticeId || !signaturePin.trim()}>
                        <FileSignature size={15} /> {signatureChecking ? 'Firma in corso...' : signedRelata ? 'Firma nuovamente' : 'Firma relata'}
                      </button>
                    </div>
                  </div>
                  <small id="relata-signature-privacy" className="iu-legal-signature-privacy"><LockKeyhole size={13} /> Il PIN resta su questo PC e viene cancellato dopo la firma. Lo stesso PIN verifica le PEC e firma la relata.</small>
                  {signatureMessage ? <small id="relata-signature-status" role="status" aria-live="polite">{signatureMessage}</small> : null}
                  {signedRelata?.previewUrl ? (
                    <a className="iu-legal-signature-evidence" href={signedRelata.previewUrl} target="_blank" rel="noreferrer">
                      <FileText size={14} /> Visualizza relata firmata
                    </a>
                  ) : null}
                  <label className="iu-legal-check">
                    <input type="checkbox" checked={notifica.relata_firmata} readOnly disabled />
                    <span>{notifica.relata_firmata ? 'Relata firmata e salvata nel fascicolo' : 'Relata da firmare'}</span>
                  </label>
                  <div className="iu-legal-automatic-rules">
                    <span><CheckCircle2 size={14} /> Relata separata predisposta automaticamente</span>
                    <span><CheckCircle2 size={14} /> Ricevuta completa prevista automaticamente</span>
                  </div>
                </div>
                <label className="iu-legal-check iu-legal-field--wide"><input type="checkbox" checked={notifica.approvazione_avvocato} onChange={(event) => changeNotifica('approvazione_avvocato', event.currentTarget.checked)} /><span>Approvazione finale dell'avvocato prima dell'invio</span></label>
              </div>
              <div className="iu-legal-submit-row">
                <button className="iu-legal-submit" type="button" disabled={working} onClick={() => run('notifica')}><ShieldCheck size={16} /> {working ? 'Controllo...' : 'Controlla relata'}</button>
                <button className="iu-legal-submit iu-legal-submit--send" type="button" disabled={!canPrepareNotificationSend} title={sendNotificationTitle} onClick={sendNotification}><Send size={16} /> {working ? 'Preparazione...' : 'Invia PEC'}</button>
                <span className="iu-legal-control-status">{lastControlLabel || sendNotificationTitle || 'Il controllo aggiorna anteprima, blocchi, attestazione e piano firma.'}</span>
              </div>
            </Panel>
          ) : null}

          {tab === 'deposito' ? (
            <Panel title="Prova della notifica" subtitle="Preparazione fascicolo interno e busta" icon={<FileCheck2 size={17} />}>
              <div className="iu-legal-auto-box">
                <div className="iu-legal-auto-box__title">
                  <WandSparkles size={17} />
                  <div>
                    <strong>Compilazione da pratica IUSENTRA</strong>
                    <span>Seleziona la pratica e IUSENTRA propone atto notificato e destinatario quando sono già presenti.</span>
                  </div>
                </div>
                <div className="iu-legal-form-grid">
                  <PracticePicker
                    practices={data.precompilazione.indicePratiche}
                    value={selectedPracticeId}
                    loading={practiceSelectionWorking}
                    message={practiceSelectionMessage}
                    hint="Usa la stessa pratica della notifica o cercane una per preparare la prova."
                    onSelect={(practiceId) => { void selectPracticeById(practiceId) }}
                  />
                  <Field label="Atto dal fascicolo" hint={documentSuggestions.length ? 'Il nome file viene riportato nella prova deposito.' : 'Nessun documento selezionabile per la pratica corrente.'}>
                    <select
                      value={selectedDocumentId}
                      disabled={!documentSuggestions.length}
                      onChange={(event) => {
                        const document = documentSuggestions.find((item) => item.id === event.currentTarget.value)
                        if (document) applyDocument(document)
                        else setSelectedDocumentId('')
                      }}
                    >
                      <option value="">Seleziona atto</option>
                      {documentSuggestions.map((item) => <option value={item.id} key={`deposito-doc-${item.id}`}>{item.label}</option>)}
                    </select>
                  </Field>
                  {documentSuggestions.length ? (
                    <div className="iu-legal-document-picker iu-legal-field--wide">
                      <strong>Documenti da inserire nella prova</strong>
                      <div className="iu-legal-document-picker__grid">
                        {documentSuggestions.map((item) => (
                          <label className="iu-legal-check" key={`deposito-multi-${item.id}`}>
                            <input
                              type="checkbox"
                              checked={selectedDepositDocumentIds.includes(item.id)}
                              onChange={(event) => toggleDepositDocument(item, event.currentTarget.checked)}
                            />
                            <span>{depositEvidenceKindLabel(item)} - {item.riferimentoPortale ? `${item.riferimentoPortale} - ${item.label}` : item.label}</span>
                          </label>
                        ))}
                      </div>
                      {selectedDepositDocuments.length ? (
                        <div className="iu-legal-selected-documents">
                          {selectedDepositDocuments.map((item) => (
                            <span key={`deposito-selected-${item.id}`}>
                              <FileCheck2 size={15} />
                              {depositEvidenceKindLabel(item)} - {documentEvidenceName(item)}{item.hashSha256 ? ` - impronta ${item.hashSha256.slice(0, 12)}...` : ''}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  <Field label="Destinatario della prova" hint={recipientSuggestions.length ? 'Il nominativo viene proposto dai soggetti collegati.' : 'Seleziona o compila manualmente il destinatario.'}>
                    <select
                      value={selectedRecipientId}
                      onChange={(event) => {
                        const recipient = recipientSuggestions.find((item) => item.id === event.currentTarget.value)
                        if (recipient) applyRecipient(recipient)
                        else setSelectedRecipientId('')
                      }}
                    >
                      <option value="">Seleziona destinatario</option>
                      {recipientSuggestions.map((item) => <option value={item.id} key={`deposito-rec-${item.id}`}>{item.label}{item.pec ? ` - ${item.pec}` : ''}</option>)}
                    </select>
                  </Field>
                </div>
                <div className="iu-legal-auto-notes">
                  <span><FileText size={15} /> {documentSuggestions.length} atti dalla pratica corrente.</span>
                  <span><UserRound size={15} /> {recipientSuggestions.length} destinatari proponibili.</span>
                  <span><Inbox size={15} /> Le ricevute restano originali digitali da associare.</span>
                </div>
              </div>
              <div className="iu-legal-evidence-uploader">
                <div className="iu-legal-evidence-uploader__text">
                  <strong>Allega i file della prova</strong>
                  <span>Scegli insieme atto, relata firmata, PEC inviata e ricevute: IUSENTRA li riconosce dal nome e calcola automaticamente le impronte dei file.</span>
                  {depositAutoMessage ? <small>{depositAutoMessage}</small> : null}
                </div>
                <label className="iu-legal-evidence-uploader__button">
                  <UploadCloud size={17} />
                  Scegli file prova
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.p7m,.eml,.msg"
                    onChange={(event) => void handleDepositEvidenceFiles(event.currentTarget.files)}
                  />
                </label>
              </div>
              <div className="iu-legal-evidence-summary">
                <EvidenceSummaryRow label="Atto" fileName={deposito.atto_notificato} shaValue={deposito.atto_sha256} />
                <EvidenceSummaryRow label="Relata firmata" fileName={deposito.relata_firmata} shaValue={deposito.relata_sha256} />
                <EvidenceSummaryRow label="PEC inviata" fileName={deposito.pec_inviata} shaValue={deposito.pec_inviata_sha256} />
                <EvidenceSummaryRow label="Ricevuta di accettazione" fileName={deposito.rac_file} shaValue={deposito.rac_sha256} />
                <EvidenceSummaryRow label="Ricevuta di consegna" fileName={deposito.rdac_file} shaValue={deposito.rdac_sha256} />
              </div>
              <div className="iu-legal-form-grid iu-legal-form-grid--compact">
                <Field label="Destinatario" hint="Il nominativo può arrivare dalla pratica o essere inserito manualmente.">
                  <input value={deposito.destinatario_nome} onChange={(event) => changeDeposito('destinatario_nome', event.currentTarget.value)} />
                </Field>
                <Field label="C.F. / P. IVA destinatario">
                  <input value={deposito.destinatario_cf} onChange={(event) => changeDeposito('destinatario_cf', event.currentTarget.value.toUpperCase())} />
                </Field>
                <Field label="PEC destinatario">
                  <input type="email" value={deposito.destinatario_pec} onChange={(event) => changeDeposito('destinatario_pec', event.currentTarget.value)} />
                </Field>
                <Field label="Elenco pubblico PEC">
                  <select value={deposito.fonte_pec_destinatario} onChange={(event) => changeDeposito('fonte_pec_destinatario', event.currentTarget.value)}>
                    <option value="">Usa quello già scelto</option>
                    {data.registriPec.map((item) => <option value={item.value} key={`deposito-fonte-${item.value}`}>{item.label}</option>)}
                  </select>
                </Field>
                <label className="iu-legal-check"><input type="checkbox" checked={Boolean(deposito.ricevuta_completa)} onChange={(event) => changeDeposito('ricevuta_completa', event.currentTarget.checked)} /><span>Confermo che la ricevuta di consegna selezionata è completa</span></label>
                <Field label="Note sulle ricevute da depositare" wide hint="Aggiungi solo le informazioni utili per riconoscere le ricevute.">
                  <textarea value={deposito.dati_atto_ricevute} rows={3} onChange={(event) => changeDeposito('dati_atto_ricevute', event.currentTarget.value)} placeholder="Ricevute associate al destinatario..." />
                </Field>
              </div>
              <details className="iu-legal-manual-evidence">
                <summary>Correggi manualmente i dati riconosciuti</summary>
                <div className="iu-legal-form-grid">
                  <DepositFileField
                    label="Atto notificato"
                    fileName={deposito.atto_notificato}
                    shaValue={deposito.atto_sha256}
                    filePlaceholder="ricorso.pdf"
                    accept=".pdf,.p7m,.eml,.msg"
                    hint="Usa questo campo solo se il riconoscimento automatico non ha associato il file corretto."
                    onFileNameChange={(value) => changeDeposito('atto_notificato', value)}
                    onShaChange={(value) => changeDeposito('atto_sha256', value)}
                    onFileComputed={(fileName, sha256) => updateDepositoFile('atto_notificato', 'atto_sha256', fileName, sha256)}
                  />
                  <DepositFileField
                    label="Relata firmata"
                    fileName={deposito.relata_firmata}
                    shaValue={deposito.relata_sha256}
                    filePlaceholder="relata_notifica.pdf.p7m"
                    accept=".p7m,.pdf"
                    hint="Correzione manuale della relata firmata."
                    onFileNameChange={(value) => changeDeposito('relata_firmata', value)}
                    onShaChange={(value) => changeDeposito('relata_sha256', value)}
                    onFileComputed={(fileName, sha256) => updateDepositoFile('relata_firmata', 'relata_sha256', fileName, sha256)}
                  />
                  <DepositFileField
                    label="PEC inviata"
                    fileName={deposito.pec_inviata}
                    shaValue={deposito.pec_inviata_sha256}
                    filePlaceholder="pec_inviata.eml"
                    accept=".eml,.msg"
                    hint="Correzione manuale del messaggio PEC inviato."
                    onFileNameChange={(value) => changeDeposito('pec_inviata', value)}
                    onShaChange={(value) => changeDeposito('pec_inviata_sha256', value)}
                    onFileComputed={(fileName, sha256) => updateDepositoFile('pec_inviata', 'pec_inviata_sha256', fileName, sha256)}
                  />
                  <DepositFileField
                    label="Ricevuta di accettazione"
                    fileName={deposito.rac_file}
                    shaValue={deposito.rac_sha256}
                    filePlaceholder="accettazione.eml"
                    accept=".eml,.msg"
                    hint="Correzione manuale della ricevuta di accettazione."
                    onFileNameChange={(value) => changeDeposito('rac_file', value)}
                    onShaChange={(value) => changeDeposito('rac_sha256', value)}
                    onFileComputed={(fileName, sha256) => updateDepositoFile('rac_file', 'rac_sha256', fileName, sha256)}
                  />
                  <DepositFileField
                    label="Ricevuta di consegna completa"
                    fileName={deposito.rdac_file}
                    shaValue={deposito.rdac_sha256}
                    filePlaceholder="consegna.eml"
                    accept=".eml,.msg"
                    hint="Correzione manuale della ricevuta completa."
                    onFileNameChange={(value) => changeDeposito('rdac_file', value)}
                    onShaChange={(value) => changeDeposito('rdac_sha256', value)}
                    onFileComputed={(fileName, sha256) => updateDepositoFile('rdac_file', 'rdac_sha256', fileName, sha256)}
                  />
                </div>
              </details>
              <button className="iu-legal-submit" type="button" disabled={working} onClick={() => run('deposito')}><UploadCloud size={16} /> {working ? 'Controllo...' : 'Controlla prova deposito'}</button>
            </Panel>
          ) : null}

          {tab === 'unep' ? (
            <Panel title="Richiesta UNEP" subtitle="Canale autonomo per notifiche presso l'ufficio competente" icon={<Scale size={17} />}>
              <div className="iu-legal-auto-box">
                <div className="iu-legal-auto-box__title">
                  <WandSparkles size={17} />
                  <div>
                    <strong>Compilazione da fascicolo</strong>
                    <span>Pratica, destinatario e atto possono essere proposti dai dati già presenti; il canale resta distinto dalla notifica PEC.</span>
                  </div>
                </div>
                <div className="iu-legal-form-grid">
                  <PracticePicker
                    practices={data.precompilazione.indicePratiche}
                    value={selectedPracticeId}
                    loading={practiceSelectionWorking}
                    message={practiceSelectionMessage}
                    hint="Cerca una pratica per proporre ufficio, atto e destinatario."
                    onSelect={(practiceId) => { void selectPracticeById(practiceId) }}
                  />
                  <Field label="Atto dal fascicolo" hint={documentSuggestions.length ? 'Il file viene riportato nella richiesta.' : 'Nessun documento selezionabile.'}>
                    <select
                      value={selectedDocumentId}
                      disabled={!documentSuggestions.length}
                      onChange={(event) => {
                        const document = documentSuggestions.find((item) => item.id === event.currentTarget.value)
                        if (document) applyDocument(document)
                        else setSelectedDocumentId('')
                      }}
                    >
                      <option value="">Seleziona atto</option>
                      {documentSuggestions.map((item) => <option value={item.id} key={`unep-doc-${item.id}`}>{item.label}</option>)}
                    </select>
                  </Field>
                  <Field label="Destinatario suggerito" hint={recipientSuggestions.length ? 'Compila nominativo e recapiti dal soggetto collegato.' : 'Compila manualmente se la pratica non contiene il destinatario.'}>
                    <select
                      value={selectedRecipientId}
                      onChange={(event) => {
                        const recipient = recipientSuggestions.find((item) => item.id === event.currentTarget.value)
                        if (recipient) applyRecipient(recipient)
                        else setSelectedRecipientId('')
                      }}
                    >
                      <option value="">Seleziona destinatario</option>
                      {recipientSuggestions.map((item) => <option value={item.id} key={`unep-rec-${item.id}`}>{item.label}{item.pec ? ` - ${item.pec}` : ''}</option>)}
                    </select>
                  </Field>
                </div>
                <div className="iu-legal-auto-notes">
                  <span><Scale size={15} /> Il canale UNEP non genera busta PCT civile.</span>
                  <span><FileText size={15} /> Atto e richiesta restano documenti separati.</span>
                  <span><Inbox size={15} /> Ricevute e ritorni vanno conservati nel fascicolo.</span>
                </div>
              </div>
              <div className="iu-legal-form-grid">
                <Field label="Tipo richiesta UNEP" wide>
                  <select value={unep.tipo_richiesta_unep} onChange={(event) => changeUnep('tipo_richiesta_unep', event.currentTarget.value)}>
                    {data.tipiRichiestaUnep.map((item) => <option value={item.value} key={`unep-request-${item.value}`}>{item.label}</option>)}
                  </select>
                </Field>
                <Field label="Tipo notifica">
                  <select value={unep.tipo_notifica_unep} onChange={(event) => changeUnep('tipo_notifica_unep', event.currentTarget.value)}>
                    {data.tipiNotificaUnep.map((item) => <option value={item.value} key={`unep-tipo-${item.value}`}>{item.label}</option>)}
                  </select>
                </Field>
                <UnepOfficePicker
                  offices={data.ufficiUnep}
                  value={unep.ufficio_unep_codice}
                  onSelect={applyUnepOffice}
                />
                <Field label="Destinatario">
                  <input value={unep.destinatario_nome} onChange={(event) => changeUnep('destinatario_nome', event.currentTarget.value)} />
                </Field>
                <Field label="C.F. / P. IVA destinatario">
                  <input value={unep.destinatario_cf} onChange={(event) => changeUnep('destinatario_cf', event.currentTarget.value.toUpperCase())} />
                </Field>
                {unepTelematica ? (
                  <>
                    <Field label="PEC destinatario">
                      <input type="email" value={unep.destinatario_pec} onChange={(event) => changeUnep('destinatario_pec', event.currentTarget.value)} />
                    </Field>
                    <Field label="Elenco pubblico PEC">
                      <select value={unep.fonte_pec_destinatario} onChange={(event) => changeUnep('fonte_pec_destinatario', event.currentTarget.value)}>
                        <option value="">Seleziona elenco</option>
                        {data.registriPec.map((item) => <option value={item.value} key={`unep-fonte-${item.value}`}>{item.label}</option>)}
                      </select>
                    </Field>
                  </>
                ) : (
                  <>
                    <Field label="Indirizzo destinatario">
                      <input value={unep.destinatario_indirizzo} onChange={(event) => changeUnep('destinatario_indirizzo', event.currentTarget.value)} />
                    </Field>
                    <Field label={unepEstero ? 'Paese destinatario' : 'Comune destinatario'}>
                      <input value={unepEstero ? unep.destinatario_paese : unep.destinatario_comune} onChange={(event) => changeUnep(unepEstero ? 'destinatario_paese' : 'destinatario_comune', event.currentTarget.value)} />
                    </Field>
                  </>
                )}
                <label className="iu-legal-check">
                  <input type="checkbox" checked={unep.precetto_gia_notificato} onChange={(event) => changeUnep('precetto_gia_notificato', event.currentTarget.checked)} />
                  <span>La richiesta riguarda un precetto già notificato</span>
                </label>
                <Field label="Data notifica precetto">
                  <input type="date" value={unep.data_notifica_precetto} onChange={(event) => changeUnep('data_notifica_precetto', event.currentTarget.value)} disabled={!unep.precetto_gia_notificato} />
                </Field>
                <label className="iu-legal-check">
                  <input type="checkbox" checked={unep.spese_unep_dovute} onChange={(event) => changeUnep('spese_unep_dovute', event.currentTarget.checked)} />
                  <span>Spese o anticipazioni da documentare</span>
                </label>
                <Field label="Note richiesta" wide hint="Usa note sintetiche per dati non presenti nei campi strutturati.">
                  <textarea value={unep.note} rows={3} onChange={(event) => changeUnep('note', event.currentTarget.value)} />
                </Field>
                <DepositFileField
                  label="Atto da notificare"
                  fileName={unep.atto_notificare}
                  shaValue={unep.atto_sha256}
                  filePlaceholder="atto.pdf"
                  accept=".pdf,.p7m"
                  hint="Documento da inviare all'ufficio NEP."
                  onFileNameChange={(value) => changeUnep('atto_notificare', value)}
                  onShaChange={(value) => changeUnep('atto_sha256', value)}
                  onFileComputed={(fileName, sha256) => updateUnepFile('atto_notificare', 'atto_sha256', fileName, sha256)}
                />
                <DepositFileField
                  label="Richiesta o relata"
                  fileName={unep.richiesta_o_relata}
                  shaValue={unep.richiesta_sha256}
                  filePlaceholder="richiesta_unep.pdf"
                  accept=".pdf,.p7m"
                  hint="Documento di richiesta, relata o modulo collegato al canale UNEP."
                  onFileNameChange={(value) => changeUnep('richiesta_o_relata', value)}
                  onShaChange={(value) => changeUnep('richiesta_sha256', value)}
                  onFileComputed={(fileName, sha256) => updateUnepFile('richiesta_o_relata', 'richiesta_sha256', fileName, sha256)}
                />
                <DepositFileField
                  label="Ricevuta pagamento"
                  fileName={unep.ricevuta_pagamento}
                  shaValue={unep.ricevuta_pagamento_sha256}
                  filePlaceholder="pagamento_unep.pdf"
                  accept=".pdf,.p7m"
                  hint={unep.spese_unep_dovute ? 'Obbligatoria quando sono dovute spese o anticipazioni.' : 'Da compilare solo se presente.'}
                  onFileNameChange={(value) => changeUnep('ricevuta_pagamento', value)}
                  onShaChange={(value) => changeUnep('ricevuta_pagamento_sha256', value)}
                  onFileComputed={(fileName, sha256) => updateUnepFile('ricevuta_pagamento', 'ricevuta_pagamento_sha256', fileName, sha256)}
                />
              </div>
              <button className="iu-legal-submit" type="button" disabled={working} onClick={() => run('unep')}><ShieldCheck size={16} /> {working ? 'Controllo...' : 'Controlla richiesta UNEP'}</button>
            </Panel>
          ) : null}

          {tab === 'nonpec' ? (
            <Panel title="Tracciamento non PEC" subtitle="Raccomandata, ufficiale giudiziario e prove documentali" icon={<ClipboardCheck size={17} />}>
              <div className="iu-legal-auto-box">
                <div className="iu-legal-auto-box__title">
                  <WandSparkles size={17} />
                  <div>
                    <strong>Allineamento con il fascicolo</strong>
                    <span>Il tracciamento registra data, tipo, identificativo e prova, senza trasformare il canale in notifica PEC.</span>
                  </div>
                </div>
                <div className="iu-legal-form-grid">
                  <PracticePicker
                    practices={data.precompilazione.indicePratiche}
                    value={selectedPracticeId}
                    loading={practiceSelectionWorking}
                    message={practiceSelectionMessage}
                    hint="Cerca una pratica e compila identificativo, atto e destinatario dai dati già presenti."
                    onSelect={(practiceId) => { void selectPracticeById(practiceId) }}
                  />
                  <Field label="Atto dal fascicolo">
                    <select
                      value={selectedDocumentId}
                      disabled={!documentSuggestions.length}
                      onChange={(event) => {
                        const document = documentSuggestions.find((item) => item.id === event.currentTarget.value)
                        if (document) applyDocument(document)
                        else setSelectedDocumentId('')
                      }}
                    >
                      <option value="">Seleziona atto</option>
                      {documentSuggestions.map((item) => <option value={item.id} key={`nonpec-doc-${item.id}`}>{item.label}</option>)}
                    </select>
                  </Field>
                  <Field label="Destinatario suggerito">
                    <select
                      value={selectedRecipientId}
                      onChange={(event) => {
                        const recipient = recipientSuggestions.find((item) => item.id === event.currentTarget.value)
                        if (recipient) applyRecipient(recipient)
                        else setSelectedRecipientId('')
                      }}
                    >
                      <option value="">Seleziona destinatario</option>
                      {recipientSuggestions.map((item) => <option value={item.id} key={`nonpec-rec-${item.id}`}>{item.label}</option>)}
                    </select>
                  </Field>
                </div>
              </div>
              <div className="iu-legal-form-grid">
                <Field label="Tipo notifica">
                  <select value={nonPec.tipo_notifica_non_pec} onChange={(event) => changeNonPec('tipo_notifica_non_pec', event.currentTarget.value)}>
                    {data.tipiNotificaNonPec.map((item) => <option value={item.value} key={`nonpec-tipo-${item.value}`}>{item.label}</option>)}
                  </select>
                </Field>
                <Field label="Identificativo notifica">
                  <input value={nonPec.notifica_id} onChange={(event) => changeNonPec('notifica_id', event.currentTarget.value)} placeholder="Numero o riferimento interno" />
                </Field>
                <Field label="Data notifica">
                  <input type="date" value={nonPec.data_notifica} onChange={(event) => changeNonPec('data_notifica', event.currentTarget.value)} />
                </Field>
                <Field label="Destinatario">
                  <input value={nonPec.destinatario_nome} onChange={(event) => changeNonPec('destinatario_nome', event.currentTarget.value)} />
                </Field>
                <Field label="C.F. / P. IVA destinatario">
                  <input value={nonPec.destinatario_cf} onChange={(event) => changeNonPec('destinatario_cf', event.currentTarget.value.toUpperCase())} />
                </Field>
                <Field label="Atto notificato">
                  <input value={nonPec.atto_notificato} onChange={(event) => changeNonPec('atto_notificato', event.currentTarget.value)} />
                </Field>
                {nonPecRaccomandata ? (
                  <>
                    <Field label="Numero raccomandata">
                      <input value={nonPec.numero_raccomandata} onChange={(event) => changeNonPec('numero_raccomandata', event.currentTarget.value)} />
                    </Field>
                    <Field label="Data spedizione">
                      <input type="date" value={nonPec.data_spedizione} onChange={(event) => changeNonPec('data_spedizione', event.currentTarget.value)} />
                    </Field>
                    <Field label="Data ricezione o compiuta giacenza">
                      <input type="date" value={nonPec.data_ricevuta_raccomandata} onChange={(event) => changeNonPec('data_ricevuta_raccomandata', event.currentTarget.value)} />
                    </Field>
                  </>
                ) : null}
                {nonPecUfficiale ? (
                  <>
                    <UnepOfficePicker
                      offices={data.ufficiUnep}
                      value={nonPec.ufficio_unep_codice}
                      onSelect={applyNonPecUnepOffice}
                    />
                    <Field label="Numero cronologico">
                      <input value={nonPec.numero_cronologico} onChange={(event) => changeNonPec('numero_cronologico', event.currentTarget.value)} />
                    </Field>
                  </>
                ) : null}
                {nonPecMani ? (
                  <Field label="Consegnatario">
                    <input value={nonPec.consegnatario} onChange={(event) => changeNonPec('consegnatario', event.currentTarget.value)} />
                  </Field>
                ) : null}
                {nonPecEstero ? (
                  <>
                    <Field label="Paese destinatario">
                      <input value={nonPec.destinatario_paese} onChange={(event) => changeNonPec('destinatario_paese', event.currentTarget.value)} />
                    </Field>
                    <Field label="Autorità o canale">
                      <input value={nonPec.autorita_o_canale} onChange={(event) => changeNonPec('autorita_o_canale', event.currentTarget.value)} />
                    </Field>
                  </>
                ) : null}
                <Field label="Note" wide hint="Annota solo elementi utili per ricostruire la prova e la data.">
                  <textarea value={nonPec.note} rows={3} onChange={(event) => changeNonPec('note', event.currentTarget.value)} />
                </Field>
                <DepositFileField
                  label="Prova documentale"
                  fileName={nonPec.prova_file}
                  shaValue={nonPec.prova_sha256}
                  filePlaceholder={nonPecRaccomandata ? 'avviso_ricevimento.pdf' : 'relata_o_prova.pdf'}
                  accept=".pdf,.p7m,.jpg,.jpeg,.png"
                  hint="Avviso, relata, ricevuta o prova di consegna con impronta verificabile."
                  onFileNameChange={(value) => changeNonPec('prova_file', value)}
                  onShaChange={(value) => changeNonPec('prova_sha256', value)}
                  onFileComputed={(fileName, sha256) => updateNonPecFile('prova_file', 'prova_sha256', fileName, sha256)}
                />
              </div>
              <button className="iu-legal-submit" type="button" disabled={working} onClick={() => run('nonpec')}><ClipboardCheck size={16} /> {working ? 'Controllo...' : 'Controlla notifica non PEC'}</button>
            </Panel>
          ) : null}

          {tab === 'cliente' ? (
            <Panel title="Comunicazione al cliente" subtitle="Informativa separata dalla notifica legale" icon={<UserRound size={17} />}>
              <div className="iu-legal-auto-box">
                <div className="iu-legal-auto-box__title">
                  <WandSparkles size={17} />
                  <div>
                    <strong>Compilazione informativa da IUSENTRA</strong>
                    <span>Pratica, cliente, procedimento e documento vengono proposti dai dati già registrati.</span>
                  </div>
                </div>
                <div className="iu-legal-form-grid">
                  <PracticePicker
                    practices={data.precompilazione.indicePratiche}
                    value={selectedPracticeId}
                    loading={practiceSelectionWorking}
                    message={practiceSelectionMessage}
                    hint="Cerca una pratica per compilare cliente, ufficio, RG e documento informativo."
                    onSelect={(practiceId) => { void selectPracticeById(practiceId) }}
                  />
                  <Field label="Cliente IUSENTRA" hint={data.precompilazione.clienti.length ? 'Scegli un cliente se la comunicazione non parte da una pratica.' : 'Nessun cliente disponibile nella precompilazione.'}>
                    <select
                      value={selectedClientId}
                      onChange={(event) => {
                        const client = data.precompilazione.clienti.find((item) => item.id === event.currentTarget.value)
                        if (client) applyClient(client)
                        else setSelectedClientId('')
                      }}
                    >
                      <option value="">Seleziona cliente</option>
                      {data.precompilazione.clienti.map((item) => <option value={item.id} key={`cliente-${item.id}`}>{item.nome}{item.codiceFiscalePiva ? ` - ${item.codiceFiscalePiva}` : ''}</option>)}
                    </select>
                  </Field>
                  <Field label="Documento informativo" hint={documentSuggestions.length ? 'Descrizione e riferimento vengono riportati nel messaggio.' : 'Seleziona una pratica con documenti o compila manualmente.'}>
                    <select
                      value={selectedDocumentId}
                      disabled={!documentSuggestions.length}
                      onChange={(event) => {
                        const document = documentSuggestions.find((item) => item.id === event.currentTarget.value)
                        if (document) applyDocument(document)
                        else setSelectedDocumentId('')
                      }}
                    >
                      <option value="">Seleziona documento</option>
                      {documentSuggestions.map((item) => <option value={item.id} key={`cliente-doc-${item.id}`}>{item.label}</option>)}
                    </select>
                  </Field>
                </div>
                <div className="iu-legal-auto-notes">
                  <span><FolderOpen size={15} /> {data.precompilazione.totalePratiche || data.precompilazione.indicePratiche.length} pratiche ricercabili.</span>
                  <span><UserRound size={15} /> {data.precompilazione.clienti.length} clienti disponibili.</span>
                  <span><Mail size={15} /> La comunicazione resta senza relata e senza oggetto L. 53.</span>
                </div>
              </div>
              <div className="iu-legal-form-grid">
                <div className="iu-legal-client-template iu-legal-field--wide">
                  <div className="iu-legal-template-preview__header">
                    <div>
                      <strong>Modelli comunicazione cliente</strong>
                      <span>{data.clientCommunicationTemplateVersion || 'Catalogo comunicazioni cliente'}</span>
                    </div>
                  </div>
                  <Field label="Modello cliente" wide hint={selectedClientTemplate?.description || 'Scegli un testo semplice, separato dai modelli relata.'}>
                    <select
                      value={cliente.template_id}
                      onChange={(event) => {
                        changeCliente('template_id', event.currentTarget.value)
                        setCliente((current) => ({ ...current, oggetto: '', corpo: '' }))
                      }}
                    >
                      {data.modelliComunicazioneCliente.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    </select>
                  </Field>
                  {selectedClientTemplate ? (
                    <div className="iu-legal-client-template__preview">
                      <strong>{selectedClientTemplate.subjectPreview}</strong>
                      <pre>{selectedClientTemplate.bodyPreview}</pre>
                    </div>
                  ) : null}
                </div>
                <Field label="Cliente"><input value={cliente.cliente_nome} onChange={(event) => changeCliente('cliente_nome', event.currentTarget.value)} /></Field>
                <Field label="Ufficio"><input value={cliente.ufficio_giudiziario} onChange={(event) => changeCliente('ufficio_giudiziario', event.currentTarget.value)} /></Field>
                <Field label="Numero RG"><input value={cliente.numero_rg} onChange={(event) => changeCliente('numero_rg', event.currentTarget.value)} /></Field>
                <Field label="Anno RG"><input value={cliente.anno_rg} onChange={(event) => changeCliente('anno_rg', event.currentTarget.value)} /></Field>
                <Field label="Provvedimento o documento" wide><input value={cliente.provvedimento_descrizione} onChange={(event) => changeCliente('provvedimento_descrizione', event.currentTarget.value)} /></Field>
                <Field label="Oggetto comunicazione" wide hint="Non usare l'oggetto riservato alla notifica L. 53/1994.">
                  <input value={cliente.oggetto} onChange={(event) => changeCliente('oggetto', event.currentTarget.value)} placeholder="Viene proposto dal modello cliente" />
                </Field>
                <Field label="Corpo comunicazione" wide hint="Testo ordinario modificabile prima dell'invio al cliente.">
                  <textarea value={cliente.corpo} rows={10} onChange={(event) => changeCliente('corpo', event.currentTarget.value)} placeholder="Premi Prepara comunicazione per generare il testo dal modello cliente." />
                </Field>
              </div>
              <button className="iu-legal-submit" type="button" disabled={working} onClick={() => run('cliente')}><Mail size={16} /> {working ? 'Preparazione...' : 'Prepara comunicazione'}</button>
            </Panel>
          ) : null}
        </div>

        <aside className="iu-legal-side">
          {guidedAutomationSteps.length ? (
            <Panel title="Passaggi automatici" subtitle={automationSubtitle} icon={<ClipboardCheck size={17} />}>
              <div className="iu-legal-automation-list">
                {guidedAutomationSteps.map((item, index) => (
                  <article key={item.id}>
                    <strong>{index + 1}. {item.title}</strong>
                    <p>{item.body}</p>
                    {item.source ? <small>{item.source}</small> : null}
                  </article>
                ))}
              </div>
            </Panel>
          ) : null}
          <div ref={resultPanelRef}>
            <ResultPanel result={result} />
          </div>
          <Panel title="Regole di blocco" subtitle="Controlli prima di firma e invio" icon={<AlertTriangle size={17} />}>
            <div className="iu-legal-list">
              {blockingRules.map((item) => <span key={item.text}>{item.icon} {item.text}</span>)}
            </div>
          </Panel>
          {tab === 'cliente' ? (
            <Panel title="Modelli cliente" subtitle={data.clientCommunicationTemplateVersion || 'Comunicazioni informative'} icon={<Mail size={17} />}>
              <div className="iu-legal-list">
                <span><Mail size={15} /> {data.modelliComunicazioneCliente.length} modelli comunicazione cliente disponibili.</span>
                <span><UserRound size={15} /> Oggetto e corpo restano ordinari e modificabili.</span>
                <span><LockKeyhole size={15} /> Nessuna relata viene generata da questo percorso.</span>
              </div>
              <div className="iu-legal-template-catalog">
                {data.modelliComunicazioneCliente.map((item) => (
                  <button
                    type="button"
                    key={item.value}
                    className={item.value === cliente.template_id ? 'is-active' : ''}
                    onClick={() => {
                      changeCliente('template_id', item.value)
                      setCliente((current) => ({ ...current, oggetto: '', corpo: '' }))
                    }}
                  >
                    <strong>{item.label}</strong>
                    <span>{item.description || 'Modello informativo per il cliente.'}</span>
                  </button>
                ))}
              </div>
            </Panel>
          ) : (
            <Panel title="Catalogo modelli relata" subtitle={templateVersionDate(data.templateCatalogVersion) ? `Aggiornato il ${templateVersionDate(data.templateCatalogVersion)}` : 'Modelli caricati'} icon={<FileSignature size={17} />}>
              <div className="iu-legal-list">
                <span><FileCheck2 size={15} /> {data.modelliRelata.length} modelli relata disponibili.</span>
                <span><ShieldCheck size={15} /> Attestazioni scelte in base all'origine del documento.</span>
                <span><LockKeyhole size={15} /> Nessun invio automatico senza firma e conferma finale.</span>
              </div>
              <div className="iu-legal-template-catalog">
                {data.modelliRelata.slice(0, templateCatalogExpanded ? data.modelliRelata.length : 8).map((item) => (
                  <button
                    type="button"
                    key={item.value}
                    className={item.value === notifica.template_id ? 'is-active' : ''}
                    onClick={() => {
                      setTab('notifica')
                      changeNotifica('template_id', item.value)
                      setRelataDraftDirty(false)
                    }}
                  >
                    <strong>{item.code ? `${item.code} - ${item.label}` : item.label}</strong>
                    <span>{item.description || 'Modello disponibile per la relata.'}</span>
                  </button>
                ))}
                {data.modelliRelata.length > 8 ? (
                  <button type="button" className="iu-legal-template-catalog__toggle" onClick={() => setTemplateCatalogExpanded((current) => !current)}>
                    {templateCatalogExpanded ? 'Mostra meno modelli' : 'Mostra tutti i modelli'}
                  </button>
                ) : null}
              </div>
            </Panel>
          )}
          <Panel title="Fonti operative" subtitle="Da verificare nei flussi reali" icon={<Scale size={17} />}>
            <div className="iu-legal-sources">
              {data.fontiOperative.map((item) => <span key={item}>{item}</span>)}
            </div>
          </Panel>
        </aside>
      </section>

      <FloatingLex
        context="notifiche-legali"
        title="Lex AI notifiche"
        body="Posso aiutarti a controllare relata, pubblico elenco PEC, richiesta UNEP, prova non PEC e deposito, tenendo separati i canali."
        primaryHref="#lex"
        primaryLabel="Controlla percorso"
        secondaryHref={data.azioni.fascicoli}
        secondaryLabel="Vai ai fascicoli"
      />
    </main>
  )
}
