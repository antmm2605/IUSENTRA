import { useEffect, useId, useMemo, useRef, useState, type FormEvent, type MouseEvent, type ReactNode } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  BadgeCheck,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  ClipboardCheck,
  Clock3,
  Download,
  Edit3,
  Eye,
  FileArchive,
  FileCheck2,
  FileText,
  Fingerprint,
  FolderOpen,
  Gavel,
  Landmark,
  ListChecks,
  Mail,
  PackageCheck,
  PencilLine,
  RefreshCw,
  RotateCcw,
  Save,
  Send,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  UploadCloud,
} from 'lucide-react'
import { Badge, Button, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import {
  emptyFascicoloDetail,
  getFascicoloDetail,
  type FascicoloDeposit,
  type FascicoloDepositCatalog,
  type FascicoloDepositCatalogEntry,
  type FascicoloDepositInputField,
  type FascicoloDepositInputOption,
  type FascicoloDepositOffice,
  type FascicoloDepositReadiness,
  type FascicoloDetailData,
  type FascicoloDocument,
  type FascicoloFull,
  type FascicoloRow,
  type KeyValue,
} from '../fascicoliData'
import { csrfToken, redirectAfterSuccess, submitFormJson } from '../formSubmit'
import './FascicoliPage.css'

function normaliseText(value: string): string {
  return value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
}

function StatCard({ icon, label, value, note, tone = 'primary', href, onClick }:{icon:ReactNode; label:string; value:number|string; note:string; tone?:FascicoloRow['tone']; href?:string; onClick?:(event:MouseEvent<HTMLAnchorElement>)=>void}) {
  const body = (
    <>
      <div>{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </>
  )
  return href ? <a className={`iu-fas-stat iu-fas-stat--${tone}`} href={href} onClick={onClick} title={`Apri ${label}`}>{body}</a> : <article className={`iu-fas-stat iu-fas-stat--${tone}`}>{body}</article>
}

function EmptyState({ icon, title, children, action }:{icon:ReactNode; title:string; children:ReactNode; action?:ReactNode}) {
  return (
    <section className="iu-fas-empty">
      <div>{icon}</div>
      <h2>{title}</h2>
      <p>{children}</p>
      {action}
    </section>
  )
}

type ActionPayload = {
  ok?: boolean
  messaggio?: string
  message?: string
  errore?: string
  error?: string
  redirect_url?: string
  requires_guided_completion?: boolean
  requires_local_signature?: boolean
  requires_local_pec?: boolean
  package_ready?: boolean
  id_deposito?: string
  pec_dest?: string
  oggetto_pec?: string
  corpo_pec?: string
  documenti_busta?: string[]
  next_actions?: string[]
  busta_audit?: Record<string, unknown>
  pec_sender_ready?: boolean
  local_pec?: Record<string, unknown>
  local_signature?: Record<string, unknown>
  compatibility_report?: Record<string, unknown>
}

function PostAction({ action, children, tone = 'secondary', confirm, confirmTitle = 'Conferma operazione', onDone, onError, redirectTo, title, ariaLabel }:{action:string; children:ReactNode; tone?:'primary'|'secondary'|'danger'|'ghost'; confirm?:string; confirmTitle?:string; onDone?:(message?:string)=>void; onError?:(message:string)=>void; redirectTo?:string; title?:string; ariaLabel?:string}) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  if (!action) return null
  const run = async () => {
    setBusy(true)
    setError('')
    try {
      const response = await fetch(action, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      })
      const contentType = response.headers.get('content-type') || ''
      const payload = contentType.includes('application/json') ? await response.json().catch(() => ({} as ActionPayload)) : {} as ActionPayload
      if (!response.ok || payload.ok === false) throw new Error(String(payload.messaggio || payload.errore || payload.error || `Operazione non riuscita: HTTP ${response.status}`))
      const message = String(payload.messaggio || payload.message || '')
      setConfirming(false)
      if (onDone) {
        onDone(message)
        return
      }
      const target = String(payload.redirect_url || redirectTo || response.url || '')
      if (target) window.location.href = target
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Operazione non riuscita.'
      setError(message)
      onError?.(message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <button className={`iu-fas-post iu-fas-post--${tone}`} type="button" onClick={() => confirm ? setConfirming(true) : void run()} disabled={busy} title={title} aria-label={ariaLabel}>
        {busy ? <span className="iu-fas-post__busy"><RefreshCw size={15}/> Operazione...</span> : children}
      </button>
      {!confirming && error ? <span className="iu-fas-inline-error" role="alert">{error}</span> : null}
      {confirming ? (
        <div className="iu-fas-confirm-modal" role="dialog" aria-modal="true" aria-label={confirmTitle}>
          <div className="iu-fas-confirm-modal__box">
            <strong>{confirmTitle}</strong>
            <p>{confirm}</p>
            {error ? <span className="iu-fas-inline-error">{error}</span> : null}
            <footer>
              <button type="button" onClick={() => setConfirming(false)} disabled={busy}>Annulla</button>
              <button className="is-danger" type="button" onClick={run} disabled={busy}>{busy ? 'Operazione...' : 'Conferma'}</button>
            </footer>
          </div>
        </div>
      ) : null}
    </>
  )
}

type DepositActionPayload = Record<string, string | string[]>
type BatchSignatureResult = { pinSessionId?: string; pinSessionTtlSeconds?: number }
type BatchSignatureAction = () => Promise<BatchSignatureResult | void>
type LocalSignatureCompletion = { payload: ActionPayload; submittedPayload: DepositActionPayload }
type DepositDocumentRole = 'atto_principale' | 'procura' | 'allegato_prova' | 'allegato' | 'prova_notifica' | 'fuori_busta'

type DepositPackagePreview = {
  idDeposito: string
  pecDest: string
  oggettoPec: string
  corpoPec: string
  documenti: string[]
  nextActions: string[]
  packageReady: boolean
  requiresGuidedCompletion: boolean
  requiresLocalPec: boolean
  localPec: Record<string, unknown>
  bustaAudit: Record<string, unknown>
  compatibilityReport: Record<string, unknown>
  pecSenderReady: boolean
  message: string
}

type LocalPecPasswordRequest = {
  from: string
  username: string
  to: string
  subject: string
  attachments: string[]
  resolve: (password: string) => void
  reject: (error: Error) => void
}

const SIGNATURE_INPUT_REQUIRED_PREFIX = 'SIGNATURE_INPUT_REQUIRED:'

function signatureInputRequired(message: string): Error {
  return new Error(`${SIGNATURE_INPUT_REQUIRED_PREFIX}${message}`)
}

function signatureInputRequiredMessage(message: string): string {
  return message.startsWith(SIGNATURE_INPUT_REQUIRED_PREFIX)
    ? message.slice(SIGNATURE_INPUT_REQUIRED_PREFIX.length).trim()
    : ''
}

type DepositDocumentClassification = {
  selected: boolean
  role: DepositDocumentRole
  alreadySigned: boolean
  requiresSignature?: boolean
}

type DepositCatalogPreviewOption = FascicoloDepositCatalogEntry

type DepositCatalogPreviewCategory = {
  id: string
  label: string
  total: number
  options: DepositCatalogPreviewOption[]
}

type DepositCatalogPreviewMacro = {
  id: string
  label: string
  total: number
  service: string
  categories: DepositCatalogPreviewCategory[]
}

const DEPOSIT_DOCUMENT_ROLE_OPTIONS: Array<{ value: DepositDocumentRole; label: string }> = [
  { value: 'atto_principale', label: 'Atto principale' },
  { value: 'procura', label: 'Procura alle liti' },
  { value: 'allegato', label: 'Allegato' },
  { value: 'prova_notifica', label: 'Prova notifica' },
  { value: 'fuori_busta', label: 'Fuori busta' },
]

type DepositCatalogPreviewState = {
  total: number
  macroareas: DepositCatalogPreviewMacro[]
}

const EMPTY_DEPOSIT_CATALOG_PREVIEW: DepositCatalogPreviewState = { total: 0, macroareas: [] }

function buildDepositCatalogPreviewState(catalog: FascicoloDepositCatalog | undefined): DepositCatalogPreviewState {
  const entries = (catalog?.entries || []).filter((entry) => Boolean(entry.key))
  const entryByKey = new Map(entries.map((entry) => [entry.key, entry]))
  const macroareas = (catalog?.macroareas || [])
    .map((macro) => ({
      id: macro.id,
      label: macro.label,
      total: macro.total,
      service: macro.service,
      categories: macro.categories.map((category) => ({
        id: category.id,
        label: category.label,
        total: category.total,
        options: category.optionKeys.map((key) => entryByKey.get(key)).filter(Boolean) as DepositCatalogPreviewOption[],
      })).filter((category) => category.options.length > 0),
    }))
    .filter((macro) => macro.categories.length > 0)
  return {
    total: catalog?.counts.totalDepositTypes || entries.length,
    macroareas: macroareas.length ? macroareas : buildDepositCatalogPreviewMacroareasFromEntries(entries),
  }
}

function buildDepositCatalogPreviewMacroareasFromEntries(entries: FascicoloDepositCatalogEntry[]): DepositCatalogPreviewMacro[] {
  const orderedMacroNames = entries.map((entry) => entry.macro).filter(Boolean).filter((macro, index, all) => all.indexOf(macro) === index)
  return orderedMacroNames.map((macroName) => {
    const macroEntries = entries.filter((entry) => entry.macro === macroName)
    const categoryNames = macroEntries.map((entry) => entry.category).filter(Boolean).filter((category, index, all) => all.indexOf(category) === index)
    return {
      id: depositCatalogSlug(macroName),
      label: macroName,
      total: macroEntries.length,
      service: macroEntries[0]?.ui.service || macroEntries[0]?.registry.label || '',
      categories: categoryNames.map((categoryName) => {
        const categoryEntries = macroEntries.filter((entry) => entry.category === categoryName)
        return {
          id: `${depositCatalogSlug(macroName)}-${depositCatalogSlug(categoryName)}`,
          label: categoryName,
          total: categoryEntries.length,
          options: categoryEntries,
        }
      }).filter((category) => category.options.length > 0),
    }
  }).filter((macro) => macro.categories.length > 0)
}

function depositCatalogSlug(value: string) {
  const normalized = value.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
  return normalized.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'catalogo'
}

const DEPOSIT_PROGRESS_USER_STEPS = [
  'Controllo dati deposito',
  'Firma controlli',
  'Indice documenti',
  'Preparazione pacchetto',
  'Verifica finale',
]

function depositUserControlLabel(value: string): string {
  const text = normaliseText(value)
  if (/datiatto|metadat/.test(text)) return 'Dati deposito'
  if (/indicebusta/.test(text)) return 'Indice del pacchetto'
  if (/indicedocumenti|indice document/.test(text)) return 'Indice documenti'
  if (/atto\.enc|aes|certificato|\.cer|pst/.test(text)) return 'Pacchetto protetto'
  if (/pec locale/.test(text)) return 'Invio PEC dal PC in uso'
  if (/codice deposito|codice oggetto/.test(text)) return 'Codice deposito'
  if (/ufficio/.test(text)) return 'Ufficio giudiziario'
  if (/registro/.test(text)) return 'Registro e ruolo'
  return value
}

function uniqueDepositUserList(values: string[]): string[] {
  const result: string[] = []
  for (const item of values.map(depositUserControlLabel).filter(Boolean)) {
    if (!result.includes(item)) result.push(item)
  }
  return result
}

function depositUserTransportLabel(entry: FascicoloDepositCatalogEntry): string {
  const transport = normaliseText(`${entry.ui.transport} ${entry.channel}`)
  if (/unep|notific/.test(transport)) return 'Flusso notifiche separato'
  if (/portale|upload/.test(transport)) return 'Caricamento sul portale ufficiale'
  if (/pec|atto|busta|datiatto|indice/.test(transport)) return 'Preparazione busta e invio PEC dal PC in uso'
  return entry.ui.transport || 'Preparazione deposito'
}

function depositCatalogEntrySearchText(entry: FascicoloDepositCatalogEntry): string {
  const ui = entry.ui || {}
  const payload = entry.payload || {}
  const rules = entry.rules || {}
  const registry = entry.registry || { code: '', label: '' }
  const schema = entry.schema || {}
  const controls = Array.isArray(ui.controls) ? ui.controls.join(' ') : ''
  const documents = Array.isArray(ui.documents) ? ui.documents.join(' ') : ''
  return normaliseText([
    entry.key,
    entry.label,
    entry.macro,
    entry.category,
    entry.path,
    entry.prefix,
    entry.channel,
    registry.code,
    registry.label,
    payload.tipo_atto,
    payload.codice_registro,
    payload.tipo_deposito_telematico_key,
    payload.tipo_deposito_telematico_label,
    payload.tipo_deposito_telematico_channel,
    payload.tipo_deposito_telematico_registry,
    rules.official_channel,
    rules.registry_code,
    rules.registry_label,
    rules.policy_code,
    schema.supportedMinisterialRoot,
    controls,
    documents,
  ].filter(Boolean).join(' '))
}

function suggestDepositTypeKey(
  catalog: FascicoloDepositCatalog,
  fascicolo: FascicoloFull,
  office: FascicoloDepositOffice,
  mainAct: FascicoloDocument | undefined,
  profileName: string,
  officialChannel: string,
  fallbackChannel: string,
): string {
  const entries = catalog.entries || []
  if (!entries.length) return ''
  const actText = normaliseText(`${mainAct?.name || ''} ${mainAct?.type || ''} ${mainAct?.catalogLabel || ''} ${mainAct?.notes || ''}`)
  const context = normaliseText([
    fascicolo.type,
    fascicolo.procedureType,
    fascicolo.practiceArea,
    fascicolo.practiceId,
    fascicolo.codiceOggettoPst,
    profileName,
    officialChannel,
    fallbackChannel,
    office.name,
    office.kind,
    office.code,
    office.ministerialCode,
  ].filter(Boolean).join(' '))
  const isGiudicePace = /sigp|giudice di pace|\bgdp\b/.test(context)
  const isSiecic = /siecic|esecuz|concors/.test(context)
  const isLavoro = /lavoro|rgl|retribuzion/.test(context)
  const wantsNotesDeposit = /note scritte|trattazione scritta|sostitutiv|udienza|memoria|istanza/.test(actText)
  const wantsCitation = /citazion/.test(actText)
  const wantsRicorso = /ricorso/.test(actText)
  const wantsComparsa = /comparsa/.test(actText)
  const wantsAppeal = /appello|reclamo|impugnazion/.test(actText)

  let bestKey = ''
  let bestScore = 0
  let bestIndex = Number.MAX_SAFE_INTEGER
  entries.forEach((entry, index) => {
    const text = depositCatalogEntrySearchText(entry)
    let score = 0

    if (isGiudicePace) {
      if (/sigp|giudice di pace|\bgdp\b/.test(text)) score += 140
      if (/sicid|siecic|cassazione|unep/.test(text)) score -= 180
    } else if (isSiecic) {
      if (/siecic|esecuz|concors/.test(text)) score += 110
      if (/sigp|giudice di pace|\bgdp\b/.test(text)) score -= 160
    } else if (isLavoro) {
      if (/sicid|lavoro|rgl/.test(text)) score += 80
      if (/sigp|giudice di pace|\bgdp\b/.test(text)) score -= 120
    } else if (/sicid|contenzioso civile|civile/.test(context)) {
      if (/sicid|contenzioso civile|civile/.test(text)) score += 60
      if (/sigp|giudice di pace|\bgdp\b/.test(text)) score -= 120
    }

    if (wantsNotesDeposit) {
      if (isGiudicePace && entry.key === 'CorsoCausa_SIGP::DepositoNoteScritteSostUdie') score += 180
      if (/depositonotescrittesostudie|deposito note scritte|note scritte sostitutive|trattazione scritta|memoria|istanza/.test(text)) score += 120
      if (/citazion|decreto ingiuntivo|opposizione|appello|ricorso introduttivo/.test(text)) score -= 40
    } else if (wantsCitation) {
      if (/citazion/.test(text)) score += 80
      if (/note scritte|memoria|istanza/.test(text)) score -= 30
    } else if (wantsRicorso) {
      if (/ricorso/.test(text)) score += 70
      if (/citazion|note scritte/.test(text)) score -= 25
    } else if (wantsComparsa) {
      if (/comparsa|costituzione|risposta/.test(text)) score += 70
      if (/citazion|ricorso introduttivo/.test(text)) score -= 25
    } else if (wantsAppeal) {
      if (/appello|reclamo|impugnazion/.test(text)) score += 70
    }

    if (score > 0 && (score > bestScore || (score === bestScore && index < bestIndex))) {
      bestKey = entry.key
      bestScore = score
      bestIndex = index
    }
  })
  return bestKey
}

function depositAttachmentDisplayName(value: string): string {
  const text = value.trim()
  if (!text) return ''
  const lowered = text.toLowerCase()
  if (lowered === 'atto.enc' || /datiatto|indicebusta|cms|pkcs|\.cer|aes256/.test(lowered)) return 'Pacchetto deposito'
  if (lowered === 'indicedocumentidepositati.pdf') return 'Indice documenti'
  return text
}

function depositUserFacingMessage(value: string): string {
  const raw = value.trim()
  if (!raw) return ''
  let result = raw
  const hiddenTechnicalSources = [
    [83, 116, 117, 100, 105, 111, 32, 84, 101, 108, 101, 109, 97, 116, 105, 99, 111],
    [81, 117, 105, 99, 107, 79, 114, 103, 97, 110, 105, 122, 101, 114],
  ].map((codes) => String.fromCharCode(...codes))
  hiddenTechnicalSources.forEach((sourceName) => {
    result = result.replace(new RegExp(sourceName, 'gi'), 'IUSENTRA')
  })
  result = result.replace(/DatiAtto\.xml(?:\.p7m)?/gi, 'dati del deposito')
  result = result.replace(/IndiceBusta\.xml/gi, 'indice del pacchetto')
  result = result.replace(/IndiceDocumentiDepositati\.PDF/gi, 'indice documenti')
  result = result.replace(/Atto\.msg/gi, 'messaggio di deposito')
  result = result.replace(/Atto\.enc/gi, 'pacchetto deposito')
  result = result.replace(/AES256|CMS EnvelopedData|PKCS#?7/gi, 'formato protetto')
  result = result.replace(/\.cer/gi, "certificato dell'ufficio")
  result = result.replace(/\.cer\s*PST|PST\s*\.cer|certificato PST/gi, "certificato dell'ufficio")
  result = result.replace(/Catalogo ministeriale|CatalogoServizi\.getCertificato/gi, 'servizio ufficiale')
  result = result.replace(/\bPCT\b/gi, 'deposito telematico')
  result = result.replace(/\bPST\b/gi, 'servizio ufficiale')
  result = result.replace(/token\s+PKCS#?11|PKCS#?11|token/gi, 'dispositivo di firma')
  result = result.replace(/\bhash\b/gi, 'impronta')
  result = result.replace(/\bslot documentali\b|\bslot\b/gi, 'documenti richiesti')
  result = result.replace(/ministeriale|ministeriali/gi, 'ufficiale')
  result = result.replace(/blocco tecnico/gi, 'requisito mancante')
  result = result.replace(/metadato ministeriale/gi, 'dati del deposito')
  result = result.replace(/artefatti ministeriali/gi, 'documenti prodotti')
  result = result.replace(/schema ministeriale|schema/gi, 'controllo')
  result = result.replace(/Deposito\s+deposito telematico/gi, 'Deposito telematico')
  return result
}

function depositUserFacingLabel(value: string): string {
  const registerCodes = '(SICID|SIECIC|SIGP|SIL|SIVG|SIMIN|MIN|RGN|LAV|VG|CASSCI|CASSPE)'
  let result = depositUserFacingMessage(value)
  result = result.replace(new RegExp(`\\s*\\(${registerCodes}\\)`, 'gi'), '')
  result = result.replace(new RegExp(`\\s*/\\s*${registerCodes}\\b`, 'gi'), '')
  result = result.replace(new RegExp(`\\b${registerCodes}\\b`, 'gi'), '')
  result = result.replace(/\s{2,}/g, ' ').replace(/\s+[-/]\s*$/g, '').trim()
  return result || value
}

function DepositRolePicker({
  documentName,
  value,
  onChange,
}: {
  documentName: string
  value: DepositDocumentRole
  onChange: (role: DepositDocumentRole) => void
}) {
  const [open, setOpen] = useState(false)
  const labelId = useId()
  const buttonRef = useRef<HTMLButtonElement | null>(null)
  const currentValue = normaliseDepositRoleForUi(value)
  const current = DEPOSIT_DOCUMENT_ROLE_OPTIONS.find((option) => option.value === currentValue) || DEPOSIT_DOCUMENT_ROLE_OPTIONS[2]

  return (
    <div className="iu-fas-deposit-role-picker" onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false)
    }} onKeyDown={(event) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        setOpen(false)
        buttonRef.current?.focus()
      }
    }}>
      <span id={labelId}>Ruolo</span>
      <div className="iu-fas-deposit-role-picker__box">
        <button
          ref={buttonRef}
          type="button"
          className="iu-fas-deposit-role-picker__button"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-labelledby={labelId}
          aria-label={`Ruolo deposito per ${documentName}`}
          onClick={() => setOpen((currentOpen) => !currentOpen)}
        >
          <strong>{current.label}</strong>
          <ChevronDown size={14} aria-hidden="true" />
        </button>
        {open ? (
          <div className="iu-fas-deposit-role-picker__menu" role="listbox" aria-label={`Seleziona ruolo deposito per ${documentName}`}>
            {DEPOSIT_DOCUMENT_ROLE_OPTIONS.map((option) => {
              const selected = option.value === currentValue
              return (
                <button
                  type="button"
                  role="option"
                  aria-selected={selected}
                  className={selected ? 'is-selected' : ''}
                  key={`${documentName}-${option.value}`}
                  onClick={() => {
                    onChange(option.value)
                    setOpen(false)
                  }}
                >
                  {option.label}
                </button>
              )
            })}
          </div>
        ) : null}
      </div>
    </div>
  )
}

function normaliseDepositRoleForUi(role: DepositDocumentRole | undefined): DepositDocumentRole {
  if (role === 'allegato_prova') return 'allegato'
  return role || 'allegato'
}

function savedDepositDocumentRole(value: string | undefined, fallback: DepositDocumentRole): DepositDocumentRole {
  const role = String(value || '').trim() as DepositDocumentRole
  return ['atto_principale', 'procura', 'allegato_prova', 'allegato', 'prova_notifica', 'fuori_busta'].includes(role)
    ? role
    : fallback
}

type DepositSpecificData = Record<string, unknown>

function depositObject(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function depositObjectList(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object' && !Array.isArray(item)))
    : []
}

function depositValueText(value: unknown): string {
  return typeof value === 'string' || typeof value === 'number' ? String(value) : ''
}

function depositPositiveNumber(value: unknown): boolean {
  const raw = depositValueText(value).trim().replace(/\s|€/g, '')
  if (!raw) return false
  const normalized = raw.includes(',') ? raw.replace(/\./g, '').replace(',', '.') : raw
  const amount = Number(normalized)
  return Number.isFinite(amount) && amount > 0
}

function depositRequiredValuesPresent(value: Record<string, unknown>, keys: string[]): boolean {
  return keys.every((key) => depositValueText(value[key]).trim())
}

function depositSpecificFieldComplete(field: FascicoloDepositInputField, value: unknown): boolean {
  if (!field.required) return true
  if (field.type === 'boolean') return typeof value === 'boolean'
  if (field.type === 'currency' || field.type === 'integer') return depositPositiveNumber(value)
  if (field.type === 'year') return /^\d{4}$/.test(depositValueText(value).trim())
  if (field.type === 'cassazione-materia') return /^\d{3}$/.test(depositValueText(value).trim())
  if (field.type === 'beni-pignorati') {
    const items = depositObjectList(value)
    return items.length > 0 && items.every((item) => {
      if (!depositRequiredValuesPresent(item, ['tipo', 'descrizione'])) return false
      if (!normaliseText(depositValueText(item.tipo)).includes('immob')) return depositPositiveNumber(item.valore)
      return depositRequiredValuesPresent(depositObject(item.indirizzo), ['via', 'cap', 'localita', 'provincia'])
        && depositRequiredValuesPresent(depositObject(item.dati_catastali), ['sezione', 'foglio', 'particella'])
        && depositRequiredValuesPresent(item, ['catasto', 'classe'])
    })
  }
  if (field.type === 'titolo-esecutivo') {
    return depositRequiredValuesPresent(depositObject(value), ['tipologia', 'descrizione'])
  }
  if (field.type === 'persona-indirizzo') {
    return depositRequiredValuesPresent(depositObject(value), ['cognome', 'codice_fiscale', 'via', 'cap', 'localita', 'provincia'])
  }
  if (field.type === 'terzi-pignorati') {
    const items = depositObjectList(value)
    return items.length > 0 && items.every((item) => depositRequiredValuesPresent(
      item,
      ['codice_fiscale', 'denominazione', 'via', 'cap', 'localita', 'provincia', 'data_notifica_pignoramento'],
    ))
  }
  if (field.type === 'provvedimento-cassazione') {
    return depositRequiredValuesPresent(depositObject(value), ['ufficio', 'ruolo', 'numero_fascicolo', 'anno_fascicolo'])
  }
  if (field.type === 'motivi-cassazione') {
    const items = depositObjectList(value)
    return items.length > 0 && items.every((item) => ['1', '2', '3', '4', '5'].includes(depositValueText(item.numero_art_360)))
  }
  if (field.type === 'contromotivi-cassazione') {
    const items = depositObjectList(value)
    return items.length > 0 && items.every((item) => (
      /^\d+$/.test(depositValueText(item.numero_riferimento_motivo))
      && depositPositiveNumber(item.pagina)
    ))
  }
  return depositValueText(value).trim().length > 0
}

function missingDepositSpecificFields(fields: FascicoloDepositInputField[], values: DepositSpecificData): FascicoloDepositInputField[] {
  return fields.filter((field) => !depositSpecificFieldComplete(field, values[field.id]))
}

function DepositRequiredMark({ required }: { required: boolean }) {
  return required ? <span className="iu-fas-deposit-specific__required" aria-label="obbligatorio">Obbligatorio</span> : null
}

function DepositTextInput({
  label,
  value,
  onChange,
  type = 'text',
  required = false,
  placeholder = '',
  inputMode,
}: {
  label: string
  value: unknown
  onChange: (value: string) => void
  type?: 'text' | 'date' | 'number'
  required?: boolean
  placeholder?: string
  inputMode?: 'decimal' | 'numeric' | 'text'
}) {
  return (
    <label className="iu-fas-deposit-specific__field">
      <span>{label}{required ? <b aria-hidden="true"> *</b> : null}</span>
      <input
        type={type}
        value={depositValueText(value)}
        onChange={(event) => onChange(event.currentTarget.value)}
        required={required}
        aria-required={required}
        placeholder={placeholder}
        inputMode={inputMode}
      />
    </label>
  )
}

function DepositSelectInput({
  label,
  value,
  options,
  onChange,
  required = false,
}: {
  label: string
  value: unknown
  options: FascicoloDepositInputOption[]
  onChange: (value: string) => void
  required?: boolean
}) {
  return (
    <label className="iu-fas-deposit-specific__field">
      <span>{label}{required ? <b aria-hidden="true"> *</b> : null}</span>
      <select value={depositValueText(value)} onChange={(event) => onChange(event.currentTarget.value)} required={required} aria-required={required}>
        <option value="">Seleziona</option>
        {options.map((option) => <option value={option.value} key={`${label}-${option.value}`}>{option.label}</option>)}
      </select>
    </label>
  )
}

function DepositRepeatingHeader({ label, onAdd }: { label: string; onAdd: () => void }) {
  return (
    <div className="iu-fas-deposit-specific__repeat-head">
      <span>{label}</span>
      <button type="button" onClick={onAdd}><UploadCloud size={14} aria-hidden="true" /> Aggiungi</button>
    </div>
  )
}

function DepositSpecificComplexField({
  field,
  value,
  onChange,
  catalogKey,
  titleOptions,
  roleOptions,
  matterOptions,
  propertyClassOptions,
}: {
  field: FascicoloDepositInputField
  value: unknown
  onChange: (value: unknown) => void
  catalogKey: string
  titleOptions: FascicoloDepositInputOption[]
  roleOptions: FascicoloDepositInputOption[]
  matterOptions: FascicoloDepositInputOption[]
  propertyClassOptions: FascicoloDepositInputOption[]
}) {
  if (field.type === 'cassazione-materia') {
    return <DepositSelectInput label={field.label} value={value} options={matterOptions} onChange={onChange} required={field.required} />
  }

  if (field.type === 'titolo-esecutivo') {
    const item = depositObject(value)
    const set = (key: string, nextValue: unknown) => onChange({ ...item, [key]: nextValue })
    return (
      <fieldset className="iu-fas-deposit-specific__complex">
        <legend>{field.label} <DepositRequiredMark required={field.required} /></legend>
        <div className="iu-fas-deposit-specific__grid">
          <DepositSelectInput label="Tipologia" value={item.tipologia} options={titleOptions} onChange={(next) => set('tipologia', next)} required />
          <DepositTextInput label="Descrizione" value={item.descrizione} onChange={(next) => set('descrizione', next)} required />
          <DepositTextInput label="Numero" value={item.numero} onChange={(next) => set('numero', next)} />
          <DepositTextInput label="Data di emissione" value={item.data_emissione} onChange={(next) => set('data_emissione', next)} type="date" />
        </div>
      </fieldset>
    )
  }

  if (field.type === 'persona-indirizzo') {
    const item = depositObject(value)
    const set = (key: string, nextValue: unknown) => onChange({ ...item, [key]: nextValue })
    return (
      <fieldset className="iu-fas-deposit-specific__complex">
        <legend>{field.label} <DepositRequiredMark required={field.required} /></legend>
        <div className="iu-fas-deposit-specific__grid">
          <DepositTextInput label="Cognome o denominazione" value={item.cognome} onChange={(next) => set('cognome', next)} required />
          <DepositTextInput label="Nome" value={item.nome} onChange={(next) => set('nome', next)} />
          <DepositTextInput label="Codice fiscale" value={item.codice_fiscale} onChange={(next) => set('codice_fiscale', next.toUpperCase())} required />
          <DepositTextInput label="Indirizzo" value={item.via} onChange={(next) => set('via', next)} required />
          <DepositTextInput label="CAP" value={item.cap} onChange={(next) => set('cap', next)} required inputMode="numeric" />
          <DepositTextInput label="Comune" value={item.localita} onChange={(next) => set('localita', next)} required />
          <DepositTextInput label="Provincia" value={item.provincia} onChange={(next) => set('provincia', next.toUpperCase())} required />
          <DepositTextInput label="PEC" value={item.pec} onChange={(next) => set('pec', next)} />
        </div>
      </fieldset>
    )
  }

  if (field.type === 'provvedimento-cassazione') {
    const item = depositObject(value)
    const set = (key: string, nextValue: unknown) => onChange({ ...item, [key]: nextValue })
    return (
      <fieldset className="iu-fas-deposit-specific__complex">
        <legend>{field.label} <DepositRequiredMark required={field.required} /></legend>
        <div className="iu-fas-deposit-specific__grid">
          <DepositTextInput label="Ufficio" value={item.ufficio} onChange={(next) => set('ufficio', next)} required />
          <DepositSelectInput label="Ruolo" value={item.ruolo} options={roleOptions} onChange={(next) => set('ruolo', next)} required />
          <DepositTextInput label="Numero fascicolo" value={item.numero_fascicolo} onChange={(next) => set('numero_fascicolo', next)} required inputMode="numeric" />
          <DepositTextInput label="Anno fascicolo" value={item.anno_fascicolo} onChange={(next) => set('anno_fascicolo', next)} required inputMode="numeric" />
          <DepositTextInput label="Rito" value={item.rito} onChange={(next) => set('rito', next)} />
          <DepositTextInput label="Sub" value={item.sub} onChange={(next) => set('sub', next)} />
        </div>
      </fieldset>
    )
  }

  if (field.type === 'beni-pignorati') {
    const items = depositObjectList(value)
    const defaultType = /immobiliare/i.test(catalogKey) ? 'immobiliare' : 'mobiliare'
    const update = (index: number, nextItem: Record<string, unknown>) => onChange(items.map((item, itemIndex) => itemIndex === index ? nextItem : item))
    const remove = (index: number) => onChange(items.filter((_, itemIndex) => itemIndex !== index))
    return (
      <fieldset className="iu-fas-deposit-specific__complex">
        <legend>{field.label} <DepositRequiredMark required={field.required} /></legend>
        <DepositRepeatingHeader label={items.length ? `${items.length} ${items.length === 1 ? 'bene inserito' : 'beni inseriti'}` : 'Nessun bene inserito'} onAdd={() => onChange([...items, { tipo: defaultType }])} />
        <div className="iu-fas-deposit-specific__repeat-list">
          {items.map((item, index) => {
            const isImmobile = normaliseText(depositValueText(item.tipo)).includes('immob')
            const address = depositObject(item.indirizzo)
            const cadastral = depositObject(item.dati_catastali)
            const set = (key: string, nextValue: unknown) => update(index, { ...item, [key]: nextValue })
            const setAddress = (key: string, nextValue: unknown) => set('indirizzo', { ...address, [key]: nextValue })
            const setCadastral = (key: string, nextValue: unknown) => set('dati_catastali', { ...cadastral, [key]: nextValue })
            return (
              <article className="iu-fas-deposit-specific__repeat-row" key={`bene-${index}`}>
                <header><strong>Bene {index + 1}</strong><button type="button" onClick={() => remove(index)} title={`Rimuovi bene ${index + 1}`} aria-label={`Rimuovi bene ${index + 1}`}><Trash2 size={15} /></button></header>
                <div className="iu-fas-deposit-specific__grid">
                  <DepositSelectInput label="Tipo" value={item.tipo} options={[{ value: 'mobiliare', label: 'Bene mobile' }, { value: 'immobiliare', label: 'Bene immobile' }]} onChange={(next) => set('tipo', next)} required />
                  <DepositTextInput label="Descrizione" value={item.descrizione} onChange={(next) => set('descrizione', next)} required />
                  {!isImmobile ? <DepositTextInput label="Valore (€)" value={item.valore} onChange={(next) => set('valore', next)} required inputMode="decimal" placeholder="0,00" /> : null}
                  {isImmobile ? <DepositTextInput label="Indirizzo" value={address.via} onChange={(next) => setAddress('via', next)} required /> : null}
                  {isImmobile ? <DepositTextInput label="CAP" value={address.cap} onChange={(next) => setAddress('cap', next)} required inputMode="numeric" /> : null}
                  {isImmobile ? <DepositTextInput label="Comune" value={address.localita} onChange={(next) => setAddress('localita', next)} required /> : null}
                  {isImmobile ? <DepositTextInput label="Provincia" value={address.provincia} onChange={(next) => setAddress('provincia', next.toUpperCase())} required /> : null}
                  {isImmobile ? <DepositSelectInput label="Catasto" value={item.catasto} options={[{ value: 'NCEU', label: 'Catasto edilizio urbano (NCEU)' }, { value: 'NCT', label: 'Catasto terreni (NCT)' }]} onChange={(next) => set('catasto', next)} required /> : null}
                  {isImmobile ? <DepositTextInput label="Sezione" value={cadastral.sezione} onChange={(next) => setCadastral('sezione', next)} required /> : null}
                  {isImmobile ? <DepositTextInput label="Foglio" value={cadastral.foglio} onChange={(next) => setCadastral('foglio', next)} required /> : null}
                  {isImmobile ? <DepositTextInput label="Particella" value={cadastral.particella} onChange={(next) => setCadastral('particella', next)} required /> : null}
                  {isImmobile ? <DepositSelectInput label="Classe" value={item.classe} options={propertyClassOptions} onChange={(next) => set('classe', next)} required /> : null}
                </div>
              </article>
            )
          })}
        </div>
      </fieldset>
    )
  }

  if (field.type === 'terzi-pignorati') {
    const items = depositObjectList(value)
    const update = (index: number, nextItem: Record<string, unknown>) => onChange(items.map((item, itemIndex) => itemIndex === index ? nextItem : item))
    return (
      <fieldset className="iu-fas-deposit-specific__complex">
        <legend>{field.label} <DepositRequiredMark required={field.required} /></legend>
        <DepositRepeatingHeader label={items.length ? `${items.length} ${items.length === 1 ? 'terzo inserito' : 'terzi inseriti'}` : 'Nessun terzo inserito'} onAdd={() => onChange([...items, {}])} />
        <div className="iu-fas-deposit-specific__repeat-list">
          {items.map((item, index) => {
            const set = (key: string, nextValue: unknown) => update(index, { ...item, [key]: nextValue })
            return (
              <article className="iu-fas-deposit-specific__repeat-row" key={`terzo-${index}`}>
                <header><strong>Terzo {index + 1}</strong><button type="button" onClick={() => onChange(items.filter((_, itemIndex) => itemIndex !== index))} title={`Rimuovi terzo ${index + 1}`} aria-label={`Rimuovi terzo ${index + 1}`}><Trash2 size={15} /></button></header>
                <div className="iu-fas-deposit-specific__grid">
                  <DepositTextInput label="Denominazione o cognome" value={item.denominazione} onChange={(next) => set('denominazione', next)} required />
                  <DepositTextInput label="Nome" value={item.nome} onChange={(next) => set('nome', next)} />
                  <DepositTextInput label="Codice fiscale" value={item.codice_fiscale} onChange={(next) => set('codice_fiscale', next.toUpperCase())} required />
                  <DepositTextInput label="Indirizzo" value={item.via} onChange={(next) => set('via', next)} required />
                  <DepositTextInput label="CAP" value={item.cap} onChange={(next) => set('cap', next)} required inputMode="numeric" />
                  <DepositTextInput label="Comune" value={item.localita} onChange={(next) => set('localita', next)} required />
                  <DepositTextInput label="Provincia" value={item.provincia} onChange={(next) => set('provincia', next.toUpperCase())} required />
                  <DepositTextInput label="Notifica del pignoramento" value={item.data_notifica_pignoramento} onChange={(next) => set('data_notifica_pignoramento', next)} type="date" required />
                  <DepositTextInput label="Notifica del precetto" value={item.data_notifica_precetto} onChange={(next) => set('data_notifica_precetto', next)} type="date" />
                </div>
              </article>
            )
          })}
        </div>
      </fieldset>
    )
  }

  if (field.type === 'motivi-cassazione' || field.type === 'contromotivi-cassazione') {
    const counter = field.type === 'contromotivi-cassazione'
    const items = depositObjectList(value)
    const update = (index: number, nextItem: Record<string, unknown>) => onChange(items.map((item, itemIndex) => itemIndex === index ? nextItem : item))
    return (
      <fieldset className="iu-fas-deposit-specific__complex">
        <legend>{field.label} <DepositRequiredMark required={field.required} /></legend>
        <DepositRepeatingHeader label={items.length ? `${items.length} ${items.length === 1 ? 'voce inserita' : 'voci inserite'}` : 'Nessuna voce inserita'} onAdd={() => onChange([...items, counter ? {} : { numero: String(items.length + 1) }])} />
        <div className="iu-fas-deposit-specific__repeat-list">
          {items.map((item, index) => {
            const set = (key: string, nextValue: unknown) => update(index, { ...item, [key]: nextValue })
            return (
              <article className="iu-fas-deposit-specific__repeat-row" key={`${counter ? 'contromotivo' : 'motivo'}-${index}`}>
                <header><strong>{counter ? 'Contromotivo' : 'Motivo'} {index + 1}</strong><button type="button" onClick={() => onChange(items.filter((_, itemIndex) => itemIndex !== index))} title={`Rimuovi voce ${index + 1}`} aria-label={`Rimuovi voce ${index + 1}`}><Trash2 size={15} /></button></header>
                <div className="iu-fas-deposit-specific__grid">
                  {counter ? <DepositTextInput label="Motivo richiamato" value={item.numero_riferimento_motivo} onChange={(next) => set('numero_riferimento_motivo', next)} required inputMode="numeric" /> : null}
                  {!counter ? <DepositSelectInput label="Numero dell’art. 360" value={item.numero_art_360} options={[1, 2, 3, 4, 5].map((number) => ({ value: String(number), label: String(number) }))} onChange={(next) => set('numero_art_360', next)} required /> : null}
                  <DepositTextInput label="Pagina" value={item.pagina} onChange={(next) => set('pagina', next)} required={counter} inputMode="numeric" />
                  <DepositTextInput label="Descrizione" value={item.descrizione} onChange={(next) => set('descrizione', next)} />
                </div>
              </article>
            )
          })}
        </div>
      </fieldset>
    )
  }

  return null
}

function DepositSpecificDataForm({
  entry,
  catalog,
  values,
  onChange,
}: {
  entry: FascicoloDepositCatalogEntry | undefined
  catalog: FascicoloDepositCatalog
  values: DepositSpecificData
  onChange: (fieldId: string, value: unknown) => void
}) {
  const fields = entry?.schema.inputFields || []
  if (!fields.length) return null
  const missing = missingDepositSpecificFields(fields, values)
  const groups = fields.reduce<Array<{ label: string; fields: FascicoloDepositInputField[] }>>((result, field) => {
    const label = field.group || 'Dati del deposito'
    const group = result.find((item) => item.label === label)
    if (group) group.fields.push(field)
    else result.push({ label, fields: [field] })
    return result
  }, [])
  const complexTypes = new Set([
    'beni-pignorati',
    'titolo-esecutivo',
    'persona-indirizzo',
    'terzi-pignorati',
    'provvedimento-cassazione',
    'motivi-cassazione',
    'contromotivi-cassazione',
    'cassazione-materia',
  ])
  return (
    <section id="dati-specifici-deposito" className="iu-fas-deposit-specific" aria-label="Dati richiesti per il deposito selezionato">
      <header>
        <div>
          <strong>Dati del deposito</strong>
          <span>Mostriamo solo i dati necessari per il tipo selezionato. Il salvataggio li conserva nel fascicolo.</span>
        </div>
        <Badge tone={missing.length ? 'warning' : 'success'}>{missing.length ? `${missing.length} da completare` : 'Completi'}</Badge>
      </header>
      {missing.length ? <p className="iu-fas-deposit-specific__notice" role="status">Prima dell’invio reale completa: {missing.map((field) => field.label).join(', ')}. I comandi di prova restano disponibili e indicano subito il dato mancante.</p> : null}
      {groups.map((group) => (
        <div className="iu-fas-deposit-specific__group" key={`${entry?.key}-${group.label}`}>
          <h4>{group.label}</h4>
          <div className="iu-fas-deposit-specific__grid">
            {group.fields.filter((field) => !complexTypes.has(field.type)).map((field) => {
              const value = values[field.id]
              if (field.type === 'select') {
                return <DepositSelectInput key={field.id} label={field.label} value={value} options={field.options} onChange={(next) => onChange(field.id, next)} required={field.required} />
              }
              if (field.type === 'boolean') {
                return (
                  <label className="iu-fas-deposit-specific__toggle" key={field.id}>
                    <input type="checkbox" checked={value === true || value === 'true' || value === '1'} onChange={(event) => onChange(field.id, event.currentTarget.checked)} />
                    <span><strong>{field.label}</strong>{field.note ? <small>{field.note}</small> : null}</span>
                  </label>
                )
              }
              return (
                <DepositTextInput
                  key={field.id}
                  label={field.type === 'currency' ? `${field.label} (€)` : field.label}
                  value={value}
                  onChange={(next) => onChange(field.id, next)}
                  type={field.type === 'date' ? 'date' : field.type === 'integer' ? 'number' : 'text'}
                  inputMode={field.type === 'currency' ? 'decimal' : field.type === 'year' || field.type === 'integer' ? 'numeric' : 'text'}
                  placeholder={field.type === 'currency' ? '0,00' : ''}
                  required={field.required}
                />
              )
            })}
          </div>
          {group.fields.filter((field) => complexTypes.has(field.type)).map((field) => (
            <DepositSpecificComplexField
              key={field.id}
              field={field}
              value={values[field.id]}
              onChange={(next) => onChange(field.id, next)}
              catalogKey={entry?.key || ''}
              titleOptions={catalog.referenceData.titoliEsecutivi}
              roleOptions={catalog.referenceData.ruoliProvvedimentoCassazione}
              matterOptions={catalog.referenceData.materieCassazione}
              propertyClassOptions={catalog.referenceData.classiImmobiliari}
            />
          ))}
        </div>
      ))}
    </section>
  )
}

function DepositTypePreviewPanel({
  catalog,
  selectedKey,
  onSelect,
  currentProfile,
}: {
  catalog: FascicoloDepositCatalog
  selectedKey: string
  onSelect: (key: string) => void
  currentProfile: string
}) {
  const catalogPreview = useMemo(() => buildDepositCatalogPreviewState(catalog), [catalog])
  const [macroId, setMacroId] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [schemaOpen, setSchemaOpen] = useState(true)
  const [treeOpen, setTreeOpen] = useState(false)
  const macroareas = catalogPreview.macroareas

  const selectedByKey = useMemo(() => {
    for (const macro of macroareas) {
      for (const category of macro.categories) {
        const type = category.options.find((option) => option.key === selectedKey)
        if (type) return { macro, category, type }
      }
    }
    return null
  }, [macroareas, selectedKey])

  const selectedMacro = selectedByKey?.macro || macroareas.find((macro) => macro.id === macroId) || macroareas[0]
  const selectedCategory = selectedByKey?.category || selectedMacro?.categories.find((category) => category.id === categoryId) || selectedMacro?.categories[0]
  const selectedType = selectedByKey?.type

  useEffect(() => {
    if (!selectedMacro || !selectedCategory) return
    if (macroId !== selectedMacro.id) setMacroId(selectedMacro.id)
    if (categoryId !== selectedCategory.id) setCategoryId(selectedCategory.id)
  }, [categoryId, macroId, selectedCategory, selectedMacro])

  const selectMacro = (nextMacroId: string) => {
    const nextMacro = macroareas.find((macro) => macro.id === nextMacroId) || macroareas[0]
    const nextCategory = nextMacro?.categories[0]
    if (!nextMacro || !nextCategory) return
    setMacroId(nextMacro.id)
    setCategoryId(nextCategory.id)
    onSelect('')
  }

  const selectCategory = (nextCategoryId: string) => {
    if (!selectedMacro) return
    const nextCategory = selectedMacro.categories.find((category) => category.id === nextCategoryId) || selectedMacro.categories[0]
    if (!nextCategory) return
    setCategoryId(nextCategory.id)
    onSelect('')
  }

  if (!selectedMacro || !selectedCategory) {
    return (
      <section className="iu-fas-deposit-type-panel" aria-label="Tipo deposito telematico">
        <header>
          <div>
            <strong>Tipo deposito</strong>
            <span>Elenco depositi non disponibile.</span>
          </div>
          <Badge tone="warning">Da caricare</Badge>
        </header>
      </section>
    )
  }

  const sendReady = Boolean(selectedType?.rules.real_send_allowed_from_pct_panel)
  const userControls = selectedType ? uniqueDepositUserList(selectedType.ui.controls) : []
  const transportLabel = selectedType ? depositUserTransportLabel(selectedType) : 'Da scegliere'

  return (
    <section className="iu-fas-deposit-type-panel" aria-label="Tipo deposito telematico">
      <header>
        <div>
          <strong>Tipo deposito</strong>
          <span>{catalogPreview.total} tipi disponibili in {macroareas.length} aree. La scelta governa controlli, documenti richiesti e preparazione della busta.</span>
        </div>
        <Badge tone={sendReady ? 'success' : 'warning'}>{selectedType ? (sendReady ? 'Operativo' : 'Da completare') : 'Da scegliere'}</Badge>
      </header>
      <div className="iu-fas-deposit-type-panel__controls">
        <label>
          <span>Macroarea</span>
          <select value={selectedMacro.id} onChange={(event) => selectMacro(event.currentTarget.value)}>
            {macroareas.map((macro) => (
              <option value={macro.id} key={macro.id}>{depositUserFacingLabel(macro.label)} ({macro.total})</option>
            ))}
          </select>
        </label>
        <label>
          <span>Categoria</span>
          <select value={selectedCategory.id} onChange={(event) => selectCategory(event.currentTarget.value)}>
            {selectedMacro.categories.map((category) => (
              <option value={category.id} key={category.id}>{depositUserFacingLabel(category.label)} ({category.total})</option>
            ))}
          </select>
        </label>
        <label>
          <span>Deposito</span>
          <select value={selectedType?.key || ''} onChange={(event) => onSelect(event.currentTarget.value)} required aria-required="true">
            <option value="">Scegli il tipo di deposito</option>
            {selectedCategory.options.map((option) => (
              <option value={option.key} key={option.key}>{option.label}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="iu-fas-deposit-type-panel__summary">
        <article>
          <span>Area</span>
          <strong>{depositUserFacingLabel(selectedMacro.label)}</strong>
          <small>{depositUserFacingLabel(selectedCategory.label)}</small>
        </article>
        <article>
          <span>Preparazione</span>
          <strong>{selectedType ? (sendReady ? 'Pronta per i controlli' : 'Da completare') : 'Scelta dell’avvocato'}</strong>
          <small>{selectedType?.label || 'Seleziona il deposito corretto per la pratica'}</small>
        </article>
        <article>
          <span>Invio</span>
          <strong>{transportLabel}</strong>
          <small>{sendReady ? 'Controllabile nel flusso deposito' : 'Richiede flusso dedicato'}</small>
        </article>
      </div>
      <div className="iu-fas-deposit-type-panel__behavior">
        <ShieldCheck size={16} aria-hidden="true" />
        <div>
          <strong>{selectedType ? 'Comportamento previsto' : 'Tipo da scegliere'}</strong>
          <span>{selectedType ? depositUserFacingMessage(selectedType.ui.behavior) : 'L’avvocato sceglie il tipo di deposito; il software applica poi soltanto i controlli pertinenti.'}</span>
        </div>
      </div>
      {selectedType && !sendReady && selectedType.rules.real_send_blocker ? (
        <div className="iu-fas-deposit-type-panel__blocker" role="status">
          <ShieldAlert size={16} aria-hidden="true" />
          <span>{depositUserFacingMessage(selectedType.rules.real_send_blocker)}</span>
        </div>
      ) : null}
      <div className="iu-fas-deposit-type-panel__actions">
        <button type="button" onClick={() => setSchemaOpen((open) => !open)} aria-expanded={schemaOpen} disabled={!selectedType}>
          {schemaOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />} Dettagli
        </button>
        <button type="button" onClick={() => setTreeOpen((open) => !open)} aria-expanded={treeOpen}>
          {treeOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />} {treeOpen ? 'Compatta' : 'Esplodi tutto'}
        </button>
      </div>
      {schemaOpen && selectedType ? (
        <div className="iu-fas-deposit-type-panel__schema">
          <section>
            <strong>Scelta attuale</strong>
            <ul>
              <li>Area: {depositUserFacingLabel(selectedMacro.label)}</li>
              <li>Categoria: {depositUserFacingLabel(selectedCategory.label)}</li>
              <li>Tipo: {selectedType.label}</li>
              <li>{sendReady ? 'Controlli disponibili in questo flusso' : 'Serve un percorso dedicato prima dell’invio'}</li>
            </ul>
          </section>
          <section>
            <strong>Controlli automatici</strong>
            <ul>
              {userControls.map((item) => <li key={`${selectedType.key}-control-${item}`}>{item}</li>)}
            </ul>
          </section>
          <section>
            <strong>Documenti attesi</strong>
            <ul>
              {selectedType.ui.documents.map((item, index) => <li key={`${selectedType.key}-document-${item}-${index}`}>{depositUserFacingMessage(depositAttachmentDisplayName(item) || item)}</li>)}
            </ul>
          </section>
        </div>
      ) : null}
      {treeOpen ? (
        <div className="iu-fas-deposit-type-panel__tree" aria-label="Elenco tipi deposito">
          {macroareas.map((macro) => (
            <section key={`macro-${macro.id}`}>
              <h4>{depositUserFacingLabel(macro.label)} <span>{macro.total}</span></h4>
              {macro.categories.map((category) => (
                <div key={`category-${category.id}`}>
                  <strong>{depositUserFacingLabel(category.label)} <span>{category.total}</span></strong>
                  <ul>
                    {category.options.map((option) => (
                      <li key={`tree-${option.key}`} className={option.key === selectedType?.key ? 'is-selected' : ''}>
                        <button
                          type="button"
                          onClick={() => {
                            setMacroId(macro.id)
                            setCategoryId(category.id)
                            onSelect(option.key)
                          }}
                        >
                          {option.label}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </section>
          ))}
        </div>
      ) : null}
      <p className="iu-fas-deposit-type-panel__current">
        <Gavel size={14} aria-hidden="true" />
        <span>{depositUserFacingLabel(currentProfile) || 'Profilo pratica da confermare'}</span>
      </p>
    </section>
  )
}

const DEPOSIT_PHASE_IDS = [
  'verifica-deposito',
  'proposta-busta',
  'firma-busta',
  'generazione-busta',
  'inventario-fascicolo',
] as const

type DepositPhaseId = typeof DEPOSIT_PHASE_IDS[number]
const DEPOSIT_DETAIL_INCLUDE = ['documenti', 'depositi', 'regia', 'relata', 'audit'] as const

function isDepositPhaseId(value: string): value is DepositPhaseId {
  return DEPOSIT_PHASE_IDS.includes(value as DepositPhaseId)
}

function initialDepositPhaseFromHash(): DepositPhaseId {
  if (typeof window === 'undefined') return 'verifica-deposito'
  const value = decodeURIComponent(window.location.hash.replace(/^#/, ''))
  return isDepositPhaseId(value) ? value : 'verifica-deposito'
}

async function submitJsonPayload(endpoint: string, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  const token = csrfToken()
  const response = await fetch(endpoint, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
      ...(token ? { 'X-CSRFToken': token } : {}),
    },
    body: JSON.stringify(payload),
  })
  const data = await response.json().catch(() => ({})) as Record<string, unknown>
  if (!response.ok || data.ok === false) {
    throw new Error(String(data.message || data.errore || data.error || 'Non ho potuto salvare la classificazione deposito.'))
  }
  return data
}

function DepositActionButton({
  action,
  payload,
  children,
  tone = 'primary',
  disabled,
  confirm,
  confirmTitle = 'Conferma deposito',
  disabledReason,
  beforeSubmit,
  onDone,
  onError,
  onPackageReady,
  completeLocalSignature,
  completeLocalPec,
  progressItems = [],
  progressLabel = 'Preparazione deposito in corso',
}: {
  action: string
  payload: DepositActionPayload
  children: ReactNode
  tone?: 'primary' | 'secondary'
  disabled?: boolean
  confirm?: string
  confirmTitle?: string
  disabledReason?: string
  beforeSubmit?: () => Promise<void>
  onDone?: (message?: string) => void
  onError?: (message: string) => void
  onPackageReady?: (payload: ActionPayload) => void
  completeLocalSignature?: (payload: ActionPayload, submittedPayload: DepositActionPayload) => Promise<LocalSignatureCompletion>
  completeLocalPec?: (payload: ActionPayload, submittedPayload: DepositActionPayload) => Promise<string | void>
  progressItems?: string[]
  progressLabel?: string
}) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [progressIndex, setProgressIndex] = useState(0)
  const progressQueue = progressItems.length ? progressItems : DEPOSIT_PROGRESS_USER_STEPS
  const currentProgressItem = depositUserFacingMessage(progressQueue[progressIndex % progressQueue.length] || 'Pacchetto deposito')
  useEffect(() => {
    if (!busy) {
      setProgressIndex(0)
      return undefined
    }
    const timer = window.setInterval(() => {
      setProgressIndex((current) => (current + 1) % progressQueue.length)
    }, 1100)
    return () => window.clearInterval(timer)
  }, [busy, progressQueue.length])
  if (!action) return null
  const handleJsonResult = async (result: ActionPayload, submittedPayload: DepositActionPayload, responseOk = true) => {
    if (result.requires_local_signature && completeLocalSignature) {
      setConfirming(false)
      const completion = await completeLocalSignature(result, submittedPayload)
      return handleJsonResult(completion.payload, completion.submittedPayload, true)
    }
    if (result.requires_local_pec && completeLocalPec) {
      setConfirming(false)
      const message = await completeLocalPec(result, submittedPayload)
      onDone?.(message || String(result.messaggio || result.message || 'Invio PEC locale confermato.'))
      return undefined
    }
    if (result.package_ready || result.requires_guided_completion || result.requires_local_pec) {
      setConfirming(false)
      onPackageReady?.(result)
      if (!onPackageReady) onDone?.(String(result.messaggio || result.message || 'Pacchetto deposito preparato.'))
      return undefined
    }
    if (!responseOk || result.ok === false) {
      const nextActions = Array.isArray(result.next_actions)
        ? result.next_actions.map((item) => String(item || '').trim()).filter(Boolean)
        : []
      const baseMessage = String(result.message || result.messaggio || result.errore || result.error || 'Deposito non completato.')
      throw new Error(nextActions.length ? `${baseMessage} Prossimi passi: ${nextActions.join(' ')}` : baseMessage)
    }
    setConfirming(false)
    onDone?.(String(result.messaggio || result.message || 'Operazione deposito completata.'))
    return undefined
  }
  const run = async () => {
    setBusy(true)
    setError('')
    try {
      if (beforeSubmit) await beforeSubmit()
      const form = new FormData()
      Object.entries(payload).forEach(([key, value]) => {
        if (Array.isArray(value)) value.forEach((item: string) => form.append(key, item))
        else form.append(key, value)
      })
      const response = await fetch(action, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { Accept: 'application/json, application/octet-stream', 'X-Requested-With': 'XMLHttpRequest' },
        body: form,
      })
      const contentType = response.headers.get('content-type') || ''
      if (contentType.includes('application/json')) {
        const result = (await response.json().catch(() => ({}))) as ActionPayload
        await handleJsonResult(result, payload, response.ok)
        return
      }
      if (!response.ok) throw new Error(`Operazione non riuscita: HTTP ${response.status}`)
      const blob = await response.blob()
      const header = response.headers.get('content-disposition') || ''
      const match = /filename\*?=(?:UTF-8''|")?([^";]+)/i.exec(header)
      const filename = decodeURIComponent((match?.[1] || 'busta-deposito.enc').replace(/"/g, ''))
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      setConfirming(false)
      onDone?.('Busta generata e scaricata.')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Deposito non completato.'
      const signatureMessage = signatureInputRequiredMessage(message)
      const visibleMessage = depositUserFacingMessage(signatureMessage || message)
      if (signatureMessage || message.startsWith('Completa i dati obbligatori del deposito:')) {
        setConfirming(false)
        setError(visibleMessage)
      } else {
        setError(visibleMessage)
        onError?.(visibleMessage)
      }
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <button
        className={`iu-fas-post iu-fas-post--${tone}`}
        type="button"
        onClick={() => confirm ? setConfirming(true) : void run()}
        disabled={busy || disabled}
        title={disabled && disabledReason ? depositUserFacingMessage(disabledReason) : undefined}
        aria-disabled={disabled ? true : undefined}
      >
        {children}
      </button>
      {busy ? (
        <div className="iu-fas-package-progress" role="status" aria-live="polite">
          <div className="iu-fas-package-progress__head">
            <span>{progressLabel}</span>
            <strong title={currentProgressItem}>{currentProgressItem}</strong>
          </div>
          <div className="iu-fas-package-progress__bar" aria-hidden="true"><span/></div>
          <div className="iu-fas-package-progress__ticker" aria-hidden="true">
            <span>{progressQueue.map(depositUserFacingMessage).join(' - ')}</span>
          </div>
        </div>
      ) : null}
      {confirming ? (
        <div className="iu-fas-confirm-modal" role="dialog" aria-modal="true" aria-label={confirmTitle}>
          <div className="iu-fas-confirm-modal__box">
            <strong>{confirmTitle}</strong>
            <p>{confirm}</p>
            {error ? <span className="iu-fas-inline-error">{depositUserFacingMessage(error)}</span> : null}
            <footer>
              <button type="button" onClick={() => setConfirming(false)} disabled={busy}>Annulla</button>
              <button className="is-danger" type="button" onClick={run} disabled={busy || disabled}>{busy ? 'Operazione...' : 'Conferma'}</button>
            </footer>
          </div>
        </div>
      ) : null}
    </>
  )
}

function DepositPdfPreviewButton({
  action,
  payload,
  onPreview,
  onError,
  disabled = false,
  disabledReason = '',
}: {
  action: string
  payload: DepositActionPayload
  onPreview: (preview: PreviewDocument) => void
  onError?: (message: string) => void
  disabled?: boolean
  disabledReason?: string
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const openPreview = async () => {
    if (!action || busy || disabled) return
    setBusy(true)
    setError('')
    try {
      const params = new URLSearchParams()
      Object.entries(payload).forEach(([key, value]) => {
        if (Array.isArray(value)) value.forEach((item) => params.append(key, item))
        else params.append(key, value)
      })
      const previewUrl = `${action}?${params.toString()}`
      const response = await fetch(previewUrl, {
        method: 'GET',
        credentials: 'same-origin',
        headers: { Accept: 'application/pdf', 'X-Requested-With': 'XMLHttpRequest' },
      })
      if (!response.ok) {
        const contentType = response.headers.get('content-type') || ''
        const jsonBody = contentType.includes('application/json') ? await response.json().catch(() => null) : null
        const textBody = jsonBody ? '' : await response.text().catch(() => '')
        const message = String(jsonBody?.errore || jsonBody?.message || textBody || '').trim()
        throw new Error(message || `Indice non disponibile: HTTP ${response.status}`)
      }
      onPreview({
        name: 'IndiceDocumentiDepositati.PDF',
        url: previewUrl,
        downloadUrl: previewUrl,
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Indice documenti non disponibile.'
      setError(message)
      onError?.(message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <span className="iu-fas-package-preview-button">
      <button
        type="button"
        onClick={openPreview}
        disabled={busy || disabled}
        title={disabled ? disabledReason || 'Indice non ancora disponibile' : 'Visualizza indice documenti'}
        aria-label="Visualizza IndiceDocumentiDepositati.PDF"
      >
        {busy ? <RefreshCw size={16} aria-hidden="true"/> : <Eye size={16} aria-hidden="true"/>}
      </button>
      {error ? <small role="alert">{error}</small> : disabled && disabledReason ? <small>{disabledReason}</small> : null}
    </span>
  )
}

type LocalSignaturePinRequest = {
  filename: string
  outputFilename: string
  resolve: (pin: string) => void
  reject: (error: Error) => void
}

function KvGrid({ items }:{items:KeyValue[]}) {
  return <div className="iu-fas-kv-grid">{items.map((item) => {
    const value = String(item.value || '')
    const sizeClass = value.length > 34 ? 'iu-fas-kv-grid__item--full' : value.length > 18 ? 'iu-fas-kv-grid__item--wide' : ''
    return <div key={`${item.label}-${item.value}`} className={sizeClass || undefined}><span>{item.label}</span>{item.href ? <a href={item.href} className={item.mono ? 'mono' : ''}>{item.value || 'n.d.'}</a> : <strong className={item.mono ? 'mono' : ''}>{item.value || 'n.d.'}</strong>}</div>
  })}</div>
}

function DetailSection({
  id,
  title,
  icon,
  count,
  defaultOpen = false,
  open,
  onOpen,
  onToggle,
  children,
}:{
  id:string
  title:string
  icon:ReactNode
  count?:number
  defaultOpen?:boolean
  open?:boolean
  onOpen?:()=>void
  onToggle?:(open:boolean)=>void
  children:ReactNode
}) {
  const isControlled = typeof open === 'boolean'
  const detailsRef = useRef<HTMLDetailsElement | null>(null)
  const [internalOpen, setInternalOpen] = useState(defaultOpen)
  const actualOpen = isControlled ? Boolean(open) : internalOpen
  useEffect(() => {
    if (detailsRef.current && detailsRef.current.open !== actualOpen) {
      detailsRef.current.open = actualOpen
    }
  }, [actualOpen])
  return (
    <details ref={detailsRef} id={id} open={actualOpen} className="iu-fas-detail-section" onToggle={(event) => {
      const nextOpen = event.currentTarget.open
      if (!isControlled) {
        setInternalOpen(nextOpen)
      } else if (nextOpen !== actualOpen && detailsRef.current) {
        window.setTimeout(() => {
          if (detailsRef.current) detailsRef.current.open = actualOpen
        }, 0)
      }
      if (nextOpen) onOpen?.()
      onToggle?.(nextOpen)
    }}>
      <summary className="iu-fas-detail-section__summary">
        <span className="iu-fas-detail-section__icon">{icon}</span>
        <span className="iu-fas-detail-section__title">{title}</span>
        {typeof count === 'number' ? <span className="iu-fas-detail-section__count">{count}</span> : null}
        <ChevronDown className="iu-fas-detail-section__chevron" size={17}/>
      </summary>
      <div className="iu-fas-detail-section__body">{children}</div>
    </details>
  )
}

type PreviewDocument = { name: string; url: string; downloadUrl: string; objectUrl?: string; mobileUrl?: string }

function mobilePreviewUrl(url: string): string {
  if (!url || !url.includes('/documenti/') || !url.includes('/visualizza')) return ''
  try {
    const parsed = new URL(url, typeof window !== 'undefined' ? window.location.origin : 'http://localhost')
    parsed.searchParams.set('viewer', 'mobile')
    return `${parsed.pathname}${parsed.search}${parsed.hash}`
  } catch {
    const separator = url.includes('?') ? '&' : '?'
    return `${url}${separator}viewer=mobile`
  }
}

function PdfPreviewModal({ preview, onClose }:{preview:PreviewDocument | null; onClose:()=>void}) {
  const [isMobileReader, setIsMobileReader] = useState(() => (
    typeof window !== 'undefined' && window.matchMedia('(max-width: 900px)').matches
  ))

  useEffect(() => {
    const objectUrl = preview?.objectUrl
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [preview?.objectUrl])

  useEffect(() => {
    if (typeof window === 'undefined') return undefined
    const media = window.matchMedia('(max-width: 900px)')
    const update = () => setIsMobileReader(media.matches)
    update()
    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', update)
      return () => media.removeEventListener('change', update)
    }
    media.addListener(update)
    return () => media.removeListener(update)
  }, [])

  if (!preview) return null
  const mobileUrl = preview.mobileUrl || mobilePreviewUrl(preview.url)
  const viewerUrl = isMobileReader && mobileUrl ? mobileUrl : preview.url
  return (
    <div className="iu-fas-preview-modal" role="dialog" aria-modal="true" aria-label={`Anteprima ${preview.name}`}>
      <div className="iu-fas-preview-modal__box">
        <header>
          <div className="iu-fas-preview-modal__title">
            <span><Eye size={14}/> Lettore documento</span>
            <strong>{preview.name}</strong>
          </div>
          <nav>
            <a href={preview.downloadUrl}><Download size={15}/> Scarica</a>
            <button type="button" onClick={onClose} aria-label="Chiudi anteprima">Chiudi</button>
          </nav>
        </header>
        <iframe src={viewerUrl} title={`Anteprima documento ${preview.name}`}/>
      </div>
    </div>
  )
}

function recordText(row: Record<string, unknown> | undefined, key: string, fallback = '') {
  const value = row?.[key]
  return String(value ?? fallback).trim()
}

async function parseLocalSignerResponse(response: Response): Promise<Record<string, unknown>> {
  const rawText = await response.text().catch(() => '')
  const text = rawText.trim()
  if (!text) return {}
  try {
    const payload = JSON.parse(text)
    return payload && typeof payload === 'object' && !Array.isArray(payload)
      ? payload as Record<string, unknown>
      : { errore: text }
  } catch {
    return { errore: text }
  }
}

function recordBool(row: Record<string, unknown> | undefined, key: string) {
  const value = row?.[key]
  return value === true || value === 'true' || value === '1' || value === 1
}

function recordNumber(row: Record<string, unknown> | undefined, key: string, fallback = 0) {
  const value = Number(row?.[key] ?? fallback)
  return Number.isFinite(value) ? value : fallback
}

function recordHref(row: Record<string, unknown> | undefined, key: string, fallback = '') {
  const value = recordText(row, key, fallback)
  return value.startsWith('/') || value.startsWith('#') ? value : fallback
}

function DepositPreparePage({ id }:{id:string}) {
  const [data, setData] = useState<FascicoloDetailData>(emptyFascicoloDetail)
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState<{ tone: 'success' | 'danger'; message: string } | null>(null)
  const [previewDoc, setPreviewDoc] = useState<PreviewDocument | null>(null)
  const [depositClassificationById, setDepositClassificationById] = useState<Record<string, DepositDocumentClassification>>({})
  const [classificationSaving, setClassificationSaving] = useState(false)
  const [depositRenameDocId, setDepositRenameDocId] = useState('')
  const [depositRenameDraft, setDepositRenameDraft] = useState('')
  const [depositRenameBusy, setDepositRenameBusy] = useState(false)
  const [depositRenameMessage, setDepositRenameMessage] = useState('')
  const [activeDepositPanel, setActiveDepositPanel] = useState<DepositPhaseId>(initialDepositPhaseFromHash)
  const [depositActionNotice, setDepositActionNotice] = useState<{ tone: 'success' | 'danger'; message: string } | null>(null)
  const [packagePreview, setPackagePreview] = useState<DepositPackagePreview | null>(null)
  const [pecBodyDraft, setPecBodyDraft] = useState('')
  const [pecBodyEdited, setPecBodyEdited] = useState(false)
  const [pecBodyEditorOpen, setPecBodyEditorOpen] = useState(false)
  const [selectedDepositTypeKey, setSelectedDepositTypeKey] = useState('')
  const [depositSpecificData, setDepositSpecificData] = useState<DepositSpecificData>({})
  const [depositProofInvalidated, setDepositProofInvalidated] = useState(false)
  const depositSpecificDataHydrationRef = useRef('')
  const depositProofInputSignatureRef = useRef('')
  const [localPecPasswordRequest, setLocalPecPasswordRequest] = useState<LocalPecPasswordRequest | null>(null)
  const [localPecPassword, setLocalPecPassword] = useState('')
  const [localPecPasswordError, setLocalPecPasswordError] = useState('')
  const [localSignaturePinRequest, setLocalSignaturePinRequest] = useState<LocalSignaturePinRequest | null>(null)
  const [localSignaturePin, setLocalSignaturePin] = useState('')
  const [localSignaturePinError, setLocalSignaturePinError] = useState('')
  const batchSignatureActionRef = useRef<BatchSignatureAction | null>(null)
  const batchSignaturePinSessionRef = useRef('')

  const refreshDetail = (message?: string) => {
    if (message) {
      setToast({ tone: 'success', message })
      setDepositActionNotice({ tone: 'success', message })
    }
    getFascicoloDetail(id, { include: [...DEPOSIT_DETAIL_INCLUDE] }).then(setData).catch(() => {
      setToast({ tone: 'danger', message: 'Non ho potuto aggiornare i dati del deposito.' })
      setDepositActionNotice({ tone: 'danger', message: 'Non ho potuto aggiornare i dati del deposito.' })
    })
  }
  const failDetail = (message: string) => {
    setToast({ tone: 'danger', message })
    setDepositActionNotice({ tone: 'danger', message })
  }
  const startDepositDocumentRename = (doc: FascicoloDocument) => {
    setDepositRenameDocId(doc.id)
    setDepositRenameDraft(doc.name)
    setDepositRenameMessage('')
  }
  const cancelDepositDocumentRename = () => {
    if (depositRenameBusy) return
    setDepositRenameDocId('')
    setDepositRenameDraft('')
    setDepositRenameMessage('')
  }
  const submitDepositDocumentRename = async (event: FormEvent<HTMLFormElement>, doc: FascicoloDocument) => {
    event.preventDefault()
    if (!doc.actions.rename || depositRenameBusy) return
    const value = depositRenameDraft.trim()
    if (!value) {
      setDepositRenameMessage('Indica il nuovo nome del documento.')
      return
    }
    setDepositRenameBusy(true)
    setDepositRenameMessage('')
    const formData = new FormData()
    formData.set('nome_file', value)
    try {
      const response = await fetch(doc.actions.rename, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          Accept: 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrfToken(),
        },
        body: formData,
      })
      const payload = await response.json().catch(() => ({})) as Record<string, unknown>
      const message = String(payload.message || payload.messaggio || '')
      if (!response.ok || payload.ok === false) throw new Error(message || 'Rinomina non completata.')
      setDepositRenameDocId('')
      setDepositRenameDraft('')
      refreshDetail(message || 'Nome documento aggiornato.')
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Rinomina non completata.'
      setDepositRenameMessage(message)
      failDetail(message)
    } finally {
      setDepositRenameBusy(false)
    }
  }
  const handlePackageReady = (payload: ActionPayload) => {
    const message = String(payload.message || payload.messaggio || 'Pacchetto di controllo preparato. Nessun invio PEC reale eseguito.')
    setPackagePreview({
      idDeposito: String(payload.id_deposito || ''),
      pecDest: String(payload.pec_dest || ''),
      oggettoPec: String(payload.oggetto_pec || ''),
      corpoPec: String(payload.corpo_pec || ''),
      documenti: Array.isArray(payload.documenti_busta) ? payload.documenti_busta.map((item) => String(item || '').trim()).filter(Boolean) : [],
      nextActions: Array.isArray(payload.next_actions) ? payload.next_actions.map((item) => String(item || '').trim()).filter(Boolean) : [],
      packageReady: Boolean(payload.package_ready),
      requiresGuidedCompletion: Boolean(payload.requires_guided_completion),
      requiresLocalPec: Boolean(payload.requires_local_pec),
      localPec: payload.local_pec && typeof payload.local_pec === 'object' && !Array.isArray(payload.local_pec) ? payload.local_pec as Record<string, unknown> : {},
      bustaAudit: payload.busta_audit || {},
      compatibilityReport: payload.compatibility_report && typeof payload.compatibility_report === 'object' && !Array.isArray(payload.compatibility_report) ? payload.compatibility_report as Record<string, unknown> : {},
      pecSenderReady: payload.pec_sender_ready !== false,
      message,
    })
    const body = String(payload.corpo_pec || '')
    if (body) {
      setPecBodyDraft(body)
      setPecBodyEdited(false)
      setPecBodyEditorOpen(false)
    }
    setToast({ tone: 'success', message })
    setDepositActionNotice({ tone: 'success', message })
    setDepositProofInvalidated(false)
    goToDepositPhase('generazione-busta')
  }
  const registerBatchSignatureAction = (action: BatchSignatureAction | null) => {
    batchSignatureActionRef.current = action
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    getFascicoloDetail(id, { include: [...DEPOSIT_DETAIL_INCLUDE] }).then((payload) => {
      if (active) setData(payload)
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [id])

  const f = data.fascicolo
  const encodedId = encodeURIComponent(f.id || id)
  const detailHref = `/fascicoli/${encodedId}`
  const visibleRg = depositVisibleReference(f.rg, f.ref || f.id)
  const portalCatalog = buildPortalCatalogRows(data)
  const depositCandidateDocuments = data.documents.filter(isDepositCandidateDocument)
  const signedCandidateDocuments = depositCandidateDocuments.filter((doc) => doc.signed).length
  const communicationDocuments = data.documents.filter(isCommunicationDocument)
  const documentsToClassify = data.documents.filter((doc) => documentOperationalRole(doc).label === 'Da classificare')
  const mainActs = depositCandidateDocuments.filter((doc) => {
    const haystack = normaliseText(`${doc.type} ${doc.name} ${doc.statusLabel} ${doc.tags.join(' ')}`)
    return haystack.includes('atto') || haystack.includes('ricorso') || haystack.includes('memoria') || haystack.includes('istanza')
  })
  const documentSections = buildDocumentSections(depositCandidateDocuments)
  const regia = data.regia
  const deposit = regia.deposit
  const blocked = recordBool(deposit, 'blocked')
  const ready = recordBool(deposit, 'ready') || regia.validation.ready
  const statusTone: FascicoloRow['tone'] = blocked || regia.validation.blockers.length ? 'danger' : ready ? 'success' : 'warning'
  const deliveryPolicy = deposit.deliveryPolicy && typeof deposit.deliveryPolicy === 'object' && !Array.isArray(deposit.deliveryPolicy) ? deposit.deliveryPolicy as Record<string, unknown> : {}
  const directPecAllowed = recordBool(deliveryPolicy, 'allowsDirectPec')
  const directPecReady = directPecAllowed && recordBool(deliveryPolicy, 'directPecReady')
  const guidedCompletion = recordBool(deliveryPolicy, 'requiresGuidedCompletion')
  const depositOfficePecAvailable = Boolean(data.depositOffice.pec)
  const depositOfficeCodeAvailable = Boolean(data.depositOffice.code || data.depositOffice.ministerialCode)
  const depositOfficeVerified = Boolean(data.depositOffice.verified && depositOfficePecAvailable)
  const pecWorkflowAvailable = depositOfficePecAvailable
  const portalUploadRequired = recordBool(deliveryPolicy, 'requiresManualFinalUpload') || recordBool(deliveryPolicy, 'allowsPortalUpload')
  const deliveryMode = recordText(deliveryPolicy, 'mode')
  const deliveryLabel = recordText(deliveryPolicy, 'label', directPecAllowed ? (directPecReady ? 'Invio PEC da software' : 'Invio PEC da completare') : portalUploadRequired ? 'Deposito su portale' : 'Canale da verificare')
  const deliveryDetail = recordText(deliveryPolicy, 'detail', 'La Regia sceglie il canale operativo dopo la verifica del profilo e del registro.')
  const prepareLabel = recordText(deliveryPolicy, 'prepareButtonLabel', portalUploadRequired ? 'Prepara pacchetto' : 'Prepara sessione')
  const sendLabel = recordText(deliveryPolicy, 'sendButtonLabel', directPecAllowed ? 'Invia via PEC' : 'Invia deposito')
  const missingOperationalStep = recordText(deliveryPolicy, 'missingOperationalStep')
  const guidedNextActions = Array.isArray(deliveryPolicy.guidedNextActions)
    ? deliveryPolicy.guidedNextActions.map((item) => String(item || '').trim()).filter(Boolean)
    : []
  const blockingRule = recordText(deliveryPolicy, 'blockingRule', 'Bloccano l’invio solo i requisiti obbligatori previsti dal canale e dalla normativa.')
  const nonBlockingRule = recordText(deliveryPolicy, 'nonBlockingRule', 'Le mancanze non obbligatorie vengono segnalate come avvisi e non fermano l’invio.')
  const oneStepSigning = recordBool(deliveryPolicy, 'oneStepSigning')
  const immediateBatchSigning = recordBool(deliveryPolicy, 'immediateBatchSigning')
  const documentIndexGeneratedBySoftware = recordBool(deliveryPolicy, 'documentIndexGeneratedBySoftware')
  const packageKindLabel = depositPackageKindLabel(recordText(deliveryPolicy, 'packageKind'))
  const deliveryOfficialChannel = recordText(deliveryPolicy, 'officialChannel', regia.header.channel || 'Canale da verificare')
  const pctJsonPackageChannel = /pct|sicid|siecic|sigp|giudice di pace/i.test(`${deliveryOfficialChannel} ${regia.header.channel}`)
  const portalHref = portalDepositHref(deliveryOfficialChannel, regia.header.channel)
  const prepareAction = recordText(deposit, 'prepareAction')
  const sendAction = recordText(deposit, 'sendAction')
  const predepositAction = recordText(regia.actions, 'predepositCheck')
  const evidenceHref = recordText(regia.evidencePack, 'href')
  const practiceProfileName = recordText(regia.profile, 'name', regia.header.practiceType || 'Profilo pratica da confermare')
  const practiceProfileReason = recordText(regia.profile, 'reason')
  const deliveryNote = depositDeliveryNote(recordText(deliveryPolicy, 'note'), deliveryOfficialChannel, practiceProfileName, regia.header.channel)
  const selectedDepositType = data.depositCatalog.entries.find((entry) => entry.key === selectedDepositTypeKey)
  const selectedDepositInputFields = selectedDepositType?.schema.inputFields || []
  const missingRequiredDepositSpecificFields = missingDepositSpecificFields(selectedDepositInputFields, depositSpecificData)
  useEffect(() => {
    const savedTypeKey = data.depositPreparation.typeKey
    if (!savedTypeKey || !data.depositCatalog.entries.some((entry) => entry.key === savedTypeKey)) return
    setSelectedDepositTypeKey((current) => current || savedTypeKey)
  }, [data.depositCatalog.entries, data.depositPreparation.typeKey])
  useEffect(() => {
    const signature = `${f.id || id}:${data.depositPreparation.updatedAt}:${JSON.stringify(data.depositPreparation.datiattoExtra)}`
    if (depositSpecificDataHydrationRef.current === signature) return
    depositSpecificDataHydrationRef.current = signature
    setDepositSpecificData(data.depositPreparation.datiattoExtra)
  }, [data.depositPreparation.datiattoExtra, data.depositPreparation.updatedAt, f.id, id])
  const blockReasons = Array.isArray(deposit.blockReasons) ? deposit.blockReasons.map((item) => String(item || '').trim()).filter(Boolean) : []
  const validationRows = [
    ...regia.validation.blockers.map((row) => ({ tone: 'danger' as const, label: recordText(row, 'title', recordText(row, 'code', 'Blocco')), message: recordText(row, 'message'), note: recordText(row, 'suggested_action', recordText(row, 'suggestedAction')) })),
    ...regia.validation.warnings.map((row) => ({ tone: 'warning' as const, label: recordText(row, 'title', recordText(row, 'code', 'Avviso')), message: recordText(row, 'message'), note: recordText(row, 'suggested_action', recordText(row, 'suggestedAction')) })),
    ...regia.validation.results.map((row) => ({ tone: recordText(row, 'status') === 'OK' ? 'success' as const : 'neutral' as const, label: recordText(row, 'title', recordText(row, 'code', 'Controllo')), message: recordText(row, 'message'), note: recordText(row, 'suggested_action', recordText(row, 'suggestedAction')) })),
  ].filter((row) => row.label || row.message || row.note)
  const decisiveValidationRows = validationRows.filter(isDecisiveDepositIssue)
  const advisoryValidationRows = validationRows.filter((row) => !isDecisiveDepositIssue(row))
  const recentDeposits = data.deposits.slice(0, 8)
  const documentsById = new Map(data.documents.map((doc) => [doc.id, doc]))
  const sortedSlots = buildDepositCatalogSlots(selectedDepositType, regia.documentSlots)
    .sort((a, b) => Number(recordText(a, 'sortOrder') || 0) - Number(recordText(b, 'sortOrder') || 0))
  const mainSlot = sortedSlots.find(isMainActSlot)
  const proposedMainActDocument = mainSlot ? documentsById.get(recordText(mainSlot, 'documentId')) : undefined
  const linkedSlotDocuments = sortedSlots
    .map((slot) => ({ slot, document: documentsById.get(recordText(slot, 'documentId')) }))
    .filter((row): row is { slot: Record<string, unknown>; document: FascicoloDocument } => Boolean(row.document))
  const usableLinkedSlotDocuments = linkedSlotDocuments.filter((row) => !isMainActSlot(row.slot) || isMainActCandidateDocument(row.document))
  const usableProposedMainActDocument = proposedMainActDocument && isMainActCandidateDocument(proposedMainActDocument) ? proposedMainActDocument : undefined
  const notificationProofDocuments = data.documents.filter(isNotificationProofDocument)
  const manualSelectableDocuments = data.documents.filter(isDepositManualSelectableDocument)
  const depositSelectableDocuments = uniqueFascicoloDocuments([...depositCandidateDocuments, ...manualSelectableDocuments, ...notificationProofDocuments, ...data.documents])
  const linkedDefaultDocuments = uniqueFascicoloDocuments(usableLinkedSlotDocuments.map((row) => row.document))
  const suggestedDepositSelectionIds = linkedDefaultDocuments.map((doc) => doc.id)
  const defaultMainActDocumentId = usableProposedMainActDocument?.id || preferredMainActCandidateDocument(depositCandidateDocuments)?.id || ''
  const persistedDepositClassificationById = new Map(data.depositPreparation.documents.map((row) => [row.documentId, row]))
  const persistedDepositSelectionIds = data.depositPreparation.saved
    ? data.depositPreparation.documents.filter((row) => row.selected).map((row) => row.documentId)
    : []
  const defaultDepositSelectionIds = data.depositPreparation.saved
    ? persistedDepositSelectionIds
    : []
  const validMainActDocumentIds = new Set(depositSelectableDocuments.filter(isMainActCandidateDocument).map((doc) => doc.id))
  const depositClassificationSignature = [
    f.id || id,
    depositSelectableDocuments.map((doc) => doc.id).join('|'),
    defaultDepositSelectionIds.join('|'),
    data.depositPreparation.documents.map((row) => `${row.documentId}:${row.selected}:${row.role}:${row.requiresSignature}`).join('|'),
    usableLinkedSlotDocuments.map((row) => `${recordText(row.slot, 'slotKey')}:${row.document.id}`).join('|'),
  ].join('::')
  useEffect(() => {
    setDepositClassificationById((current) => {
      const next: Record<string, DepositDocumentClassification> = {}
      const knownSelection = depositSelectableDocuments.some((doc) => Object.prototype.hasOwnProperty.call(current, doc.id))
      const proposed = new Set(defaultDepositSelectionIds)
      const linkedSlotByDocumentId = new Map(usableLinkedSlotDocuments.map((row) => [row.document.id, recordText(row.slot, 'slotKey')]))
      depositSelectableDocuments.forEach((doc) => {
        const currentRow = current[doc.id]
        const persistedRow = persistedDepositClassificationById.get(doc.id)
        const defaultSelected = proposed.has(doc.id)
        const defaultRole = defaultDepositRoleForDocument(doc, linkedSlotByDocumentId.get(doc.id), defaultMainActDocumentId === doc.id)
        const persistedRole = savedDepositDocumentRole(persistedRow?.role, defaultRole)
        next[doc.id] = currentRow || (persistedRow ? {
          selected: persistedRow.selected,
          role: persistedRole,
          alreadySigned: persistedRow.alreadySigned || doc.signed,
          requiresSignature: persistedRow.requiresSignature,
        } : {
          selected: knownSelection ? false : defaultSelected,
          role: defaultRole,
          alreadySigned: doc.signed,
          requiresSignature: defaultSelected && defaultSignatureRequiredForDepositRole(doc, defaultRole),
        })
      })
      const currentKeys = Object.keys(current).sort()
      const nextKeys = Object.keys(next).sort()
      if (
        currentKeys.length === nextKeys.length
        && nextKeys.every((key, index) => key === currentKeys[index]
          && current[key]?.selected === next[key]?.selected
          && current[key]?.role === next[key]?.role
          && current[key]?.alreadySigned === next[key]?.alreadySigned
          && current[key]?.requiresSignature === next[key]?.requiresSignature)
      ) {
        return current
      }
      return next
    })
  }, [depositClassificationSignature])
  const effectiveDepositClassificationById = normaliseDepositClassificationMainAct(depositClassificationById, defaultMainActDocumentId, validMainActDocumentIds)
  const depositSelectionReady = depositSelectableDocuments.some((doc) => Object.prototype.hasOwnProperty.call(effectiveDepositClassificationById, doc.id))
  const selectedDepositDocuments = depositSelectableDocuments.filter((doc) => (
    depositSelectionReady ? Boolean(effectiveDepositClassificationById[doc.id]?.selected) : defaultDepositSelectionIds.includes(doc.id)
  ))
  const mainActDocument =
    selectedDepositDocuments.find((doc) => effectiveDepositClassificationById[doc.id]?.role === 'atto_principale')
    || (usableProposedMainActDocument && selectedDepositDocuments.some((doc) => doc.id === usableProposedMainActDocument.id) ? usableProposedMainActDocument : undefined)
    || selectedDepositDocuments.find(isMainActCandidateDocument)
  const packageDocuments = uniqueFascicoloDocuments(selectedDepositDocuments)
  const packageDocumentNames = packageDocuments.map((doc) => doc.name).filter(Boolean)
  const standardPecBody = buildDepositPecBody(packageDocumentNames)
  useEffect(() => {
    if (!pecBodyEdited) setPecBodyDraft(standardPecBody)
  }, [standardPecBody, pecBodyEdited])
  const depositProofInputSignature = JSON.stringify({
    type: selectedDepositTypeKey,
    documents: packageDocuments.map((doc) => ({
      id: doc.id,
      role: effectiveDepositClassificationById[doc.id]?.role || '',
      signature: Boolean(effectiveDepositClassificationById[doc.id]?.requiresSignature),
    })),
    data: depositSpecificData,
    pecBody: pecBodyDraft,
  })
  useEffect(() => {
    if (loading || !f.id) return
    if (!depositProofInputSignatureRef.current) {
      depositProofInputSignatureRef.current = depositProofInputSignature
      return
    }
    if (depositProofInputSignatureRef.current === depositProofInputSignature) return
    depositProofInputSignatureRef.current = depositProofInputSignature
    setPackagePreview(null)
    setDepositProofInvalidated(true)
  }, [depositProofInputSignature, f.id, loading])
  const selectedAttachmentIds = packageDocuments.filter((doc) => doc.id !== mainActDocument?.id).map((doc) => doc.id)
  const unsignedPackageDocuments = packageDocuments.filter((doc) => {
    const role = effectiveDepositClassificationById[doc.id]?.role || defaultDepositRoleForDocument(doc, '', defaultMainActDocumentId === doc.id)
    const mandatory = defaultSignatureRequiredForDepositRole(doc, role)
    const requested = mandatory || Boolean(effectiveDepositClassificationById[doc.id]?.requiresSignature)
    return !doc.signed && requested && requiresPackageSignature(doc)
  })
  const unsignedCandidateDocuments = unsignedPackageDocuments.length
  const signatureBatchRequired = unsignedPackageDocuments.length > 0
  const missingRequiredSlots = sortedSlots.filter((slot) => {
    if (!recordBool(slot, 'required')) return false
    const readinessState = depositReadinessSatisfiesSlot(slot, data.depositReadiness)
    return readinessState === null
      ? !depositSelectionSatisfiesSlot(slot, packageDocuments, mainActDocument, effectiveDepositClassificationById)
      : !readinessState
  })
  const officeRecipientRequired = directPecAllowed || guidedCompletion || pctJsonPackageChannel
  const officeRecipientReady = !officeRecipientRequired || (pecWorkflowAvailable && (!pctJsonPackageChannel || depositOfficeCodeAvailable))
  const officeRecipientBlockingReason = !officeRecipientReady
    ? !depositOfficePecAvailable
      ? 'IUSENTRA non ha risolto automaticamente la PEC dell’ufficio: aggiorna il catalogo uffici o verifica l’ufficio giudiziario della pratica.'
      : pctJsonPackageChannel && !depositOfficeCodeAvailable
        ? 'IUSENTRA non ha risolto automaticamente il codice dell’ufficio: aggiorna il catalogo uffici o verifica l’ufficio giudiziario della pratica.'
        : 'Controlla ufficio giudiziario e destinatario prima della prova deposito.'
    : ''
  const officeRecipientShortState = !depositOfficePecAvailable
    ? 'PEC ufficio non risolta'
    : pctJsonPackageChannel && !depositOfficeCodeAvailable
      ? 'Codice ufficio non risolto'
      : 'Ufficio da verificare'
  const officeRecipientBadgeTone: FascicoloRow['tone'] = !officeRecipientReady ? 'warning' : depositOfficeVerified ? 'success' : 'info'
  const officeRecipientBadgeLabel = !officeRecipientReady ? 'Dato ufficio non risolto' : depositOfficeVerified ? 'Ufficio risolto' : 'PEC disponibile'
  const officeRecipientDefaultMessage = officeRecipientReady
    ? depositOfficeVerified
      ? 'Destinatario verificato per la prova deposito.'
      : 'PEC presente: la prova recupera il certificato dell’ufficio quando serve e segnala solo requisiti obbligatori mancanti.'
    : 'Controlla ufficio, tipo deposito e destinatario prima della generazione.'
  const jsonPecAction = `/fascicoli/${encodedId}/deposito/invia-pec`
  const downloadBustaAction = `/fascicoli/${encodedId}/deposito/genera-busta`
  const dryRunBustaAction = (directPecReady || guidedCompletion || pctJsonPackageChannel) ? jsonPecAction : downloadBustaAction
  const realSendAction = (directPecReady || guidedCompletion || pctJsonPackageChannel) ? jsonPecAction : downloadBustaAction
  const requestLocalPecPassword = (localPayload: Record<string, unknown>) => new Promise<string>((resolve, reject) => {
    const attachments = Array.isArray(localPayload.attachments)
      ? localPayload.attachments
        .map((item) => item && typeof item === 'object' && !Array.isArray(item) ? recordText(item as Record<string, unknown>, 'filename') : '')
        .filter(Boolean)
      : []
    setLocalPecPassword('')
    setLocalPecPasswordError('')
    setLocalPecPasswordRequest({
      from: recordText(localPayload, 'from', recordText(localPayload, 'indirizzo', recordText(localPayload, 'username'))),
      username: recordText(localPayload, 'username', recordText(localPayload, 'indirizzo')),
      to: recordText(localPayload, 'to'),
      subject: recordText(localPayload, 'subject'),
      attachments,
      resolve,
      reject,
    })
  })
  const requestLocalSignaturePin = (localSignature: Record<string, unknown>) => new Promise<string>((resolve, reject) => {
    setLocalSignaturePin('')
    setLocalSignaturePinError('')
    setLocalSignaturePinRequest({
      filename: recordText(localSignature, 'filename', 'DatiAtto.xml'),
      outputFilename: recordText(localSignature, 'output_filename', 'DatiAtto.xml.p7m'),
      resolve,
      reject,
    })
  })
  const completeDepositLocalSignature = async (payload: ActionPayload, submittedPayload: DepositActionPayload): Promise<LocalSignatureCompletion> => {
    const localSignature = payload.local_signature && typeof payload.local_signature === 'object' && !Array.isArray(payload.local_signature)
      ? payload.local_signature as Record<string, unknown>
      : {}
    const signPayload = localSignature.payload && typeof localSignature.payload === 'object' && !Array.isArray(localSignature.payload)
      ? localSignature.payload as Record<string, unknown>
      : null
    let endpoint = recordText(localSignature, 'endpoint', localSignerEndpoint('/firma'))
    if (!signPayload || !endpoint || !recordText(signPayload, 'documento')) {
      throw new Error('Dati del deposito non disponibili per la firma. Ripeti la prova deposito.')
    }
    let signerStatus = await fetchLocalSignerStatus(LOCAL_SIGNER_BROWSER_PROBE_TIMEOUT_MS)
    if (!signerStatus || signerStatus.ok === false) {
      requestLocalSignerStart()
      await sleep(900)
      signerStatus = await fetchLocalSignerStatus(LOCAL_SIGNER_BROWSER_PROBE_TIMEOUT_MS)
    }
    signerStatus = signerStatus ? await recoverLocalSignerAutomatically(signerStatus, {
      onMessage: (message) => setDepositActionNotice({ tone: 'success', message }),
    }) : signerStatus
    if (!signerStatus || signerStatus.ok === false) {
      throw new Error(localSignerProbeFailureMessage(signerStatus, 'firmare i dati del deposito'))
    }
    if (!localSignerStatusCanSign(signerStatus)) {
      const signerDetail = String(signerStatus.errore_token || signerStatus.errore_libreria || signerStatus.messaggio || signerStatus.error || '').trim()
      throw new Error(signerDetail ? `Dispositivo non pronto per firmare i dati del deposito: ${depositUserFacingMessage(signerDetail)}` : 'Dispositivo non pronto per firmare i dati del deposito. Inserisci il dispositivo fisico o seleziona un certificato Windows utilizzabile, poi ripeti la prova deposito.')
    }
    endpoint = localSignerEndpointForPayload(endpoint, '/firma', signerStatus)
    const windowsCertificate = localSignerWindowsCertificate(signerStatus)
    const token = Array.isArray(signerStatus?.token) ? signerStatus?.token?.[0] : undefined
    const reusablePinSessionId = batchSignaturePinSessionRef.current.trim()
    const pin = reusablePinSessionId ? '' : await requestLocalSignaturePin(localSignature)
    if (!reusablePinSessionId && !pin.trim()) {
      throw new Error('PIN firma mancante. Inseriscilo per firmare i dati del deposito e proseguire.')
    }
    let signatureResponse: Response
    try {
      const requestOptions: LocalNetworkRequestInit = {
        method: 'POST',
        mode: 'cors',
        targetAddressSpace: 'local',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...signPayload,
          pin: reusablePinSessionId ? '' : pin.trim(),
          pin_session_id: reusablePinSessionId || undefined,
          slot_id: token?.slot_id,
          cert_thumbprint: windowsCertificate?.thumbprint,
          visible_signature_mode: 'nessuna',
          visible_signature_datetime_mode: 'nessuna',
        }),
      }
      signatureResponse = await fetch(endpoint, requestOptions)
    } catch {
      throw new Error('Local Signer non raggiungibile dal browser per firmare i dati del deposito. Verifica che il servizio locale sia attivo e ripeti la prova deposito.')
    }
    const signaturePayload = await parseLocalSignerResponse(signatureResponse)
    const signedB64 = recordText(signaturePayload, 'firmato_b64')
    if (!signatureResponse.ok || signaturePayload.ok === false || !signedB64) {
      throw new Error(recordText(signaturePayload, 'errore', recordText(signaturePayload, 'messaggio', 'Firma dei dati del deposito non completata dal Local Signer.')))
    }
    const nextPinSessionId = recordText(signaturePayload, 'pin_session_id', reusablePinSessionId)
    if (nextPinSessionId) batchSignaturePinSessionRef.current = nextPinSessionId
    const nextSubmittedPayload: DepositActionPayload = {
      ...submittedPayload,
      busta_id: recordText(payload, 'busta_id', recordText(localSignature, 'busta_id')),
      busta_timestamp: recordText(payload, 'busta_timestamp', recordText(localSignature, 'busta_timestamp')),
      dati_atto_sha256: recordText(payload, 'dati_atto_sha256', recordText(localSignature, 'dati_atto_sha256')),
      dati_atto_signature_confirmed: '1',
      dati_atto_firmato_b64: signedB64,
    }
    const confirmation = new FormData()
    Object.entries(nextSubmittedPayload).forEach(([key, value]) => {
      if (Array.isArray(value)) value.forEach((item: string) => confirmation.append(key, item))
      else confirmation.append(key, value)
    })
    const response = await fetch(jsonPecAction, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      body: confirmation,
    })
    const nextPayload = await response.json().catch(() => ({})) as ActionPayload
    if (!response.ok && !nextPayload.requires_local_pec && !nextPayload.package_ready && !nextPayload.requires_guided_completion) {
      throw new Error(String(nextPayload.messaggio || nextPayload.message || nextPayload.errore || nextPayload.error || `Deposito non completato dopo la firma dei dati: HTTP ${response.status}`))
    }
    return { payload: nextPayload, submittedPayload: nextSubmittedPayload }
  }
  const completeDepositLocalPec = async (payload: ActionPayload, submittedPayload: DepositActionPayload) => {
    const localPec = payload.local_pec && typeof payload.local_pec === 'object' && !Array.isArray(payload.local_pec)
      ? payload.local_pec as Record<string, unknown>
      : {}
    const localPayload = localPec.payload && typeof localPec.payload === 'object' && !Array.isArray(localPec.payload)
      ? localPec.payload as Record<string, unknown>
      : null
    let endpoint = recordText(localPec, 'endpoint', localSignerEndpoint('/pec/send'))
    if (!localPayload || !endpoint) {
      throw new Error('Payload Local Signer PEC non disponibile. Ripeti la prova senza invio reale.')
    }
    assertLocalPecAttoEncBase64(localPayload)
    let signerStatus = await fetchLocalSignerStatus(LOCAL_SIGNER_BROWSER_PROBE_TIMEOUT_MS)
    if (!signerStatus || signerStatus.ok === false) {
      requestLocalSignerStart()
      await sleep(900)
      signerStatus = await fetchLocalSignerStatus(LOCAL_SIGNER_BROWSER_PROBE_TIMEOUT_MS)
    }
    if (!signerStatus || signerStatus.ok === false) {
      throw new Error(localSignerProbeFailureMessage(signerStatus, 'inviare la PEC dal PC locale'))
    }
    endpoint = localSignerEndpointForPayload(endpoint, '/pec/send', signerStatus)
    const password = await requestLocalPecPassword(localPayload)
    if (!password.trim()) {
      throw new Error('Password PEC mancante. Inseriscila per completare l’invio dal PC locale.')
    }
    const localRequestOptions: LocalNetworkRequestInit = {
      method: 'POST',
      mode: 'cors',
      targetAddressSpace: 'local',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...localPayload, password }),
    }
    const localResponse = await fetch(endpoint, localRequestOptions)
    const localResult = await parseLocalSignerResponse(localResponse)
    if (!localResponse.ok || localResult.ok === false) {
      throw new Error(recordText(localResult, 'messaggio', recordText(localResult, 'errore', 'Local Signer non ha confermato l’invio PEC.')))
    }
    const messageId = recordText(localResult, 'message_id')
      || recordText(localResult, 'messageId')
      || recordText(localResult, 'id')
    if (!messageId) {
      throw new Error('Local Signer ha risposto senza Message-ID: invio non registrato.')
    }

    const confirmation = new FormData()
    Object.entries(submittedPayload).forEach(([key, value]) => {
      if (Array.isArray(value)) value.forEach((item: string) => confirmation.append(key, item))
      else confirmation.append(key, value)
    })
    confirmation.set('local_pec_confirmed', '1')
    confirmation.set('local_pec_message_id', messageId)
    if (payload.id_deposito) confirmation.set('local_pec_id_deposito', String(payload.id_deposito))
    const confirmationResponse = await fetch(jsonPecAction, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      body: confirmation,
    })
    const confirmationPayload = await confirmationResponse.json().catch(() => ({})) as ActionPayload
    if (!confirmationResponse.ok || confirmationPayload.ok === false) {
      throw new Error(String(confirmationPayload.messaggio || confirmationPayload.message || confirmationPayload.errore || confirmationPayload.error || 'Conferma invio PEC locale non registrata.'))
    }
    return String(confirmationPayload.messaggio || confirmationPayload.message || `Invio PEC locale confermato. Message-ID: ${messageId}`)
  }
  const runBatchSignatureBeforeDeposit = async () => {
    if (!signatureBatchRequired) return
    if (!batchSignatureActionRef.current) {
      setActiveDepositPanel('generazione-busta')
      window.location.hash = 'generazione-busta'
      throw signatureInputRequired('Inserisci il PIN nel riquadro firma di questa fase. Il software firmerà i documenti e poi genererà la busta.')
    }
    try {
      const result = await batchSignatureActionRef.current()
      if (result?.pinSessionId) batchSignaturePinSessionRef.current = result.pinSessionId
    } catch (err) {
      setActiveDepositPanel('generazione-busta')
      window.location.hash = 'generazione-busta'
      throw err
    }
  }
  const resetDepositSelectionToProposal = () => {
    const proposed = new Set(suggestedDepositSelectionIds)
    const linkedSlotByDocumentId = new Map(usableLinkedSlotDocuments.map((row) => [row.document.id, recordText(row.slot, 'slotKey')]))
    setDepositClassificationById(Object.fromEntries(depositSelectableDocuments.map((doc) => {
      const role = defaultDepositRoleForDocument(doc, linkedSlotByDocumentId.get(doc.id), defaultMainActDocumentId === doc.id)
      return [doc.id, {
        selected: proposed.has(doc.id),
        role,
        alreadySigned: doc.signed,
        requiresSignature: proposed.has(doc.id) && defaultSignatureRequiredForDepositRole(doc, role),
      }]
    })))
  }
  const deselectAllDepositDocuments = () => {
    setDepositClassificationById((current) => Object.fromEntries(depositSelectableDocuments.map((doc) => {
      const role = current[doc.id]?.role || defaultDepositRoleForDocument(doc, '', defaultMainActDocumentId === doc.id)
      return [doc.id, {
        selected: false,
        role,
        alreadySigned: current[doc.id]?.alreadySigned ?? doc.signed,
        requiresSignature: false,
      }]
    })))
  }
  const updateDepositClassification = (documentId: string, patch: Partial<DepositDocumentClassification>) => {
    setDepositClassificationById((current) => {
      const doc = depositSelectableDocuments.find((item) => item.id === documentId)
      const defaultRole = defaultDepositRoleForDocument(doc, '', defaultMainActDocumentId === documentId)
      const existing = current[documentId] || {
        selected: defaultDepositSelectionIds.includes(documentId),
        role: defaultRole,
        alreadySigned: Boolean(doc?.signed),
        requiresSignature: doc ? defaultSignatureRequiredForDepositRole(doc, defaultRole) : false,
      }
      const normalizedPatch = { ...patch }
      if (normalizedPatch.role && normalizedPatch.role !== 'fuori_busta') normalizedPatch.selected = true
      if (doc && normalizedPatch.role && normalizedPatch.role !== 'fuori_busta') {
        normalizedPatch.requiresSignature = defaultSignatureRequiredForDepositRole(doc, normalizedPatch.role)
      }
      if (normalizedPatch.role === 'fuori_busta') {
        normalizedPatch.selected = false
        normalizedPatch.requiresSignature = false
      }
      const next = { ...current, [documentId]: { ...existing, ...normalizedPatch } }
      if (normalizedPatch.role === 'atto_principale') {
        Object.keys(next).forEach((key) => {
          if (key !== documentId && next[key]?.role === 'atto_principale') {
            next[key] = { ...next[key], role: 'allegato' }
          }
        })
      }
      return next
    })
  }
  const depositClassificationPayload = () => ({
    tipo_deposito_telematico_key: selectedDepositType?.key || '',
    tipo_deposito_telematico_label: selectedDepositType?.label || '',
    tipo_deposito_telematico_policy: selectedDepositType?.rules.policy_code || '',
    datiatto_extra: depositSpecificData,
    documents: depositSelectableDocuments.map((doc) => {
      const selected = Boolean(effectiveDepositClassificationById[doc.id]?.selected)
      const role = effectiveDepositClassificationById[doc.id]?.role || defaultDepositRoleForDocument(doc, '', defaultMainActDocumentId === doc.id)
      const mandatorySignature = selected && defaultSignatureRequiredForDepositRole(doc, role)
      const requestedSignature = selected && Boolean(effectiveDepositClassificationById[doc.id]?.requiresSignature)
      return {
        document_id: doc.id,
        selected,
        role: normaliseDepositRoleForUi(role),
        already_signed: Boolean(doc.signed),
        requires_signature: Boolean(mandatorySignature || requestedSignature),
      }
    }),
  })
  const submitDepositClassification = () => submitJsonPayload(`/api/v1/ui/fascicoli/${encodedId}/deposito/classifica-documenti`, depositClassificationPayload())
  const saveDepositClassification = async () => {
    if (classificationSaving) return
    setClassificationSaving(true)
    try {
      const result = await submitDepositClassification()
      refreshDetail(String(result.message || 'Classificazione deposito salvata.'))
    } catch (err) {
      failDetail(err instanceof Error ? err.message : 'Classificazione deposito non salvata.')
    } finally {
      setClassificationSaving(false)
    }
  }
  const recoverPstOfficeCertificateBeforePackage = async () => {
    const codiceUfficio = String(data.depositOffice.code || data.depositOffice.ministerialCode || '').trim()
    if (!codiceUfficio || !pctJsonPackageChannel) return
    const certEndpoint = `/api/v1/ui/fascicoli/${encodedId}/deposito/certificato-cifratura`
    try {
      const statusResponse = await fetch(`${certEndpoint}?codice_ufficio=${encodeURIComponent(codiceUfficio)}`, {
        credentials: 'same-origin',
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        cache: 'no-store',
      })
      const statusPayload = await statusResponse.json().catch(() => ({} as Record<string, unknown>))
      if (statusResponse.ok && statusPayload.cached) return
    } catch {
      // Se il controllo cache fallisce, la generazione busta dara' comunque il blocco puntuale.
    }

    let signerStatus = await fetchLocalSignerStatus(LOCAL_SIGNER_BROWSER_PROBE_TIMEOUT_MS)
    if (!signerStatus || signerStatus.ok === false) {
      setDepositActionNotice({
        tone: 'danger',
        message: 'Servizio locale non raggiungibile per recuperare il certificato dell’ufficio. La prova deposito mostrerà il requisito mancante.',
      })
      return
    }
    signerStatus = await recoverLocalSignerAutomatically(signerStatus, {
      onMessage: (message) => setDepositActionNotice({ tone: 'success', message }),
    })
    const windowsCertificate = localSignerWindowsCertificate(signerStatus)
    if (!windowsCertificate?.thumbprint) {
      setDepositActionNotice({
        tone: 'danger',
        message: 'Seleziona il certificato CNS/CIE per recuperare il certificato dell’ufficio.',
      })
      return
    }
    setDepositActionNotice({
      tone: 'success',
      message: 'Recupero del certificato dell’ufficio dal servizio ufficiale.',
    })
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 90000)
    try {
      const localRequestOptions: LocalNetworkRequestInit = {
        method: 'POST',
        cache: 'no-store',
        mode: 'cors',
        targetAddressSpace: 'local',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({
          codice_ufficio: codiceUfficio,
          cert_thumbprint: windowsCertificate.thumbprint,
        }),
        signal: controller.signal,
      }
      const localResponse = await fetch(localSignerEndpointForStatus('/pst/certificato-ufficio', signerStatus), localRequestOptions)
      const localPayload = await localResponse.json().catch(() => ({} as Record<string, unknown>))
      const certificatoB64 = String(localPayload.certificato_b64 || '').trim()
      if (!localResponse.ok || localPayload.ok === false || !certificatoB64) {
        throw new Error(String(localPayload.errore || localPayload.error || 'Certificato dell’ufficio non restituito dal servizio ufficiale.'))
      }
      await submitJsonPayload(certEndpoint, {
        codice_ufficio: codiceUfficio,
        certificato_b64: certificatoB64,
        source_url: String(localPayload.source_url || 'CatalogoServizi.getCertificato'),
      })
      setDepositActionNotice({
        tone: 'success',
        message: 'Certificato dell’ufficio recuperato e validato.',
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Certificato dell’ufficio non recuperato dal servizio ufficiale.'
      setDepositActionNotice({
        tone: 'danger',
        message: `${message} La prova deposito resta eseguibile e mostrerà il requisito mancante se il certificato dell’ufficio non è ancora disponibile.`,
      })
    } finally {
      window.clearTimeout(timeout)
    }
  }
  const prepareDepositBeforeSubmit = async () => {
    if (missingRequiredDepositSpecificFields.length) {
      goToDepositPhase('proposta-busta', 'auto')
      throw new Error(`Completa i dati obbligatori del deposito: ${missingRequiredDepositSpecificFields.map((field) => field.label).join(', ')}.`)
    }
    await submitDepositClassification()
    await recoverPstOfficeCertificateBeforePackage()
    await runBatchSignatureBeforeDeposit()
  }
  const selectedDepositPayload = selectedDepositType?.payload
  const depositActionPayload: DepositActionPayload = {
    tipo_atto: selectedDepositPayload?.tipo_atto || depositActCodeFromDocument(mainActDocument, regia.profile),
    codice_registro: selectedDepositPayload?.codice_registro || depositRegistryCode(f),
    oggetto: f.codiceOggettoPst || f.object || f.title,
    codice_oggetto_pst: f.codiceOggettoPst,
    tipo_deposito_telematico_key: selectedDepositPayload?.tipo_deposito_telematico_key || '',
    tipo_deposito_telematico_label: selectedDepositPayload?.tipo_deposito_telematico_label || '',
    tipo_deposito_telematico_channel: selectedDepositPayload?.tipo_deposito_telematico_channel || '',
    tipo_deposito_telematico_registry: selectedDepositPayload?.tipo_deposito_telematico_registry || '',
    tipo_deposito_telematico_policy: selectedDepositPayload?.tipo_deposito_telematico_policy || '',
    tipo_deposito_telematico_schema_status: selectedDepositPayload?.tipo_deposito_telematico_schema_status || '',
    tipo_deposito_telematico_real_send_allowed: selectedDepositType?.rules.real_send_allowed_from_pct_panel ? '1' : selectedDepositType ? '0' : '',
    tipo_deposito_telematico_blocker: selectedDepositType?.rules.real_send_blocker || '',
    numero_rg: f.rgNumber ? String(f.rgNumber) : '',
    anno_rg: f.rgYear ? String(f.rgYear) : '',
    tribunale_nome: data.depositOffice.name || f.court || '',
    tribunale_pec: data.depositOffice.pec || '',
    codice_ufficio: data.depositOffice.code || data.depositOffice.ministerialCode || '',
    atto_principale_id: mainActDocument?.id || '',
    allegati_ids: selectedAttachmentIds,
    documenti_selezionati_ids: packageDocuments.map((doc) => doc.id),
    firma_unica: signatureBatchRequired ? '1' : '0',
    documenti_da_firmare_ids: unsignedPackageDocuments.map((doc) => doc.id),
    corpo_pec: pecBodyDraft || standardPecBody,
    datiatto_extra: JSON.stringify(depositSpecificData),
    data_notifica_citazione: depositValueText(depositSpecificData.data_notifica_citazione),
  }
  const depositDryRunActionPayload: DepositActionPayload = { ...depositActionPayload, prova_senza_invio: '1' }
  const depositSimulationActionPayload: DepositActionPayload = { ...depositActionPayload, simula_invio_pec: '1' }
  const indicePreviewDisabled = loading || !f.id || !mainActDocument || !packageDocuments.length
  const indicePreviewDisabledReason = loading || !f.id
    ? 'Caricamento proposta busta in corso.'
    : !mainActDocument
      ? 'Seleziona l’atto principale prima di visualizzare l’indice.'
      : 'Seleziona almeno un documento prima di visualizzare l’indice.'
  const actionBlocked = !selectedDepositType || !mainActDocument || !officeRecipientReady
  const requiredDepositDataBlocked = missingRequiredSlots.length > 0 || missingRequiredDepositSpecificFields.length > 0
  const actionBlockedReason = !selectedDepositType
    ? 'Scegli il tipo di deposito prima di preparare la prova.'
    : !officeRecipientReady
    ? officeRecipientBlockingReason
    : depositGenerationBlockedReason(mainActDocument, missingRequiredSlots)
  const requiredChoicesNotice = missingRequiredSlots.length
    ? `${missingRequiredSlots.length === 1 ? 'Documento richiesto da verificare' : 'Documenti richiesti da verificare'}: ${missingDepositSlotsSummary(missingRequiredSlots) || `${missingRequiredSlots.length} scelte`}. La scelta salvata dall’avvocato nei Documenti da inviare resta prevalente e non blocca la prova.`
    : ''
  const requiredSpecificDataNotice = missingRequiredDepositSpecificFields.length
    ? `Dati obbligatori da completare: ${missingRequiredDepositSpecificFields.map((field) => field.label).join(', ')}.`
    : ''
  const proofBlocksDirectSend = Boolean(
    packagePreview?.pecSenderReady === false
    || recordBool(packagePreview?.bustaAudit, 'blocks_direct_send')
    || recordBool(packagePreview?.bustaAudit, 'guided_completion_required')
  )
  const compatibilityReport = packagePreview?.compatibilityReport || {}
  const compatibilityPercent = packagePreview ? recordNumber(compatibilityReport, 'percentuale', -1) : -1
  const compatibilityChecks = Array.isArray(compatibilityReport.checks)
    ? compatibilityReport.checks.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object' && !Array.isArray(item)))
    : []
  const compatibilityReceipts = Array.isArray(compatibilityReport.ricevute_attese)
    ? compatibilityReport.ricevute_attese.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object' && !Array.isArray(item)))
    : []
  const packageReadyForRealSend = Boolean(packagePreview?.packageReady && !depositProofInvalidated)
  const selectedDepositTypeBlocksRealSend = Boolean(selectedDepositType && !selectedDepositType.rules.real_send_allowed_from_pct_panel)
  const realSendAvailable = pecWorkflowAvailable && !proofBlocksDirectSend && !selectedDepositTypeBlocksRealSend
  const realSendDisabledReason = !selectedDepositType
    ? 'Scegli il tipo di deposito prima di preparare la prova.'
    : !packageReadyForRealSend
    ? 'Esegui prima la prova senza invio reale.'
    : missingRequiredDepositSpecificFields.length
      ? requiredSpecificDataNotice
    : requiredDepositDataBlocked
      ? depositActionBlockedReason(ready, mainActDocument, missingRequiredSlots)
    : proofBlocksDirectSend
      ? 'Invio reale sospeso: completa i controlli obbligatori indicati nella prova.'
        : selectedDepositTypeBlocksRealSend
          ? selectedDepositType?.rules.real_send_blocker || 'Invio reale sospeso: verifica il canale del tipo selezionato.'
        : !pecWorkflowAvailable
          ? officeRecipientBlockingReason || 'IUSENTRA non ha risolto automaticamente la PEC dell’ufficio: aggiorna il catalogo uffici o verifica l’ufficio giudiziario della pratica.'
          : actionBlockedReason
  const signaturesRequiredBeforeAction = false
  const depositStatusText = depositStatusLabel(recordText(deposit, 'status', regia.validation.status || 'Da verificare'))
  const preparationTone: FascicoloRow['tone'] = decisiveValidationRows.length ? 'warning' : ready ? 'success' : 'primary'
  const depositMessage = ready
    ? 'Il fascicolo è pronto per la preparazione del deposito.'
    : 'Lavora sulla proposta documentale: il controllo decisivo avviene quando generi la busta.'
  const documentPhaseTone: FascicoloRow['tone'] = !selectedDepositType ? 'warning' : !mainActDocument ? 'danger' : missingRequiredSlots.length ? 'warning' : packageDocuments.length ? 'success' : 'warning'
  const documentPhaseState = !selectedDepositType
    ? 'Tipo da scegliere'
    : !mainActDocument
    ? 'Atto da scegliere'
    : missingRequiredSlots.length
      ? missingRequiredSlots.length === 1 ? '1 avviso' : `${missingRequiredSlots.length} avvisi`
      : 'Proposta pronta'
  const signaturePhaseTone: FascicoloRow['tone'] = signatureBatchRequired ? 'warning' : 'success'
  const generationPhaseTone: FascicoloRow['tone'] = actionBlocked || signatureBatchRequired || missingRequiredSlots.length ? 'warning' : guidedCompletion ? 'info' : 'success'
  const generationPhaseDetail = actionBlocked
    ? !selectedDepositType
      ? 'Scegli tipo deposito'
      : !officeRecipientReady
      ? officeRecipientShortState
      : !mainActDocument
      ? 'Seleziona atto principale'
      : 'Requisito da completare'
    : missingRequiredSlots.length ? 'Avviso non bloccante' : signatureBatchRequired ? 'Firma e indice insieme' : 'Indice dalla selezione'
  const depositPhases: Array<{ id: DepositPhaseId; href: string; index: string; title: string; state: string; detail: string; tone: FascicoloRow['tone'] }> = [
    {
      id: 'verifica-deposito',
      href: '#verifica-deposito',
      index: '1',
      title: 'Verifica pratica',
      state: decisiveValidationRows.length ? 'Da controllare' : ready ? 'Pronta' : 'In preparazione',
      detail: deliveryOfficialChannel,
      tone: preparationTone,
    },
    {
      id: 'proposta-busta',
      href: '#proposta-busta',
      index: '2',
      title: 'Documenti',
      state: documentPhaseState,
      detail: packageDocuments.length === 1 ? '1 documento in busta' : `${packageDocuments.length} documenti in busta`,
      tone: documentPhaseTone,
    },
    {
      id: 'firma-busta',
      href: '#firma-busta',
      index: '3',
      title: 'Firma',
      state: signatureBatchRequired ? 'Firma software' : 'Documenti pronti',
      detail: unsignedPackageDocuments.length === 1 ? '1 documento da firmare' : `${unsignedPackageDocuments.length} documenti da firmare`,
      tone: signaturePhaseTone,
    },
    {
      id: 'generazione-busta',
      href: '#generazione-busta',
      index: '4',
      title: 'Busta e indice',
      state: actionBlocked ? 'Azione da risolvere' : missingRequiredSlots.length ? 'Avviso da verificare' : guidedCompletion ? 'Controllo pronto' : 'Pronta',
      detail: generationPhaseDetail,
      tone: generationPhaseTone,
    },
    {
      id: 'inventario-fascicolo',
      href: '#inventario-fascicolo',
      index: '5',
      title: 'Inventario',
      state: documentsToClassify.length ? 'Da classificare' : 'Letto',
      detail: `${data.documents.length} documenti nel fascicolo`,
      tone: documentsToClassify.length ? 'warning' : 'success',
    },
  ]
  const activeDepositPhaseIndex = Math.max(0, depositPhases.findIndex((phase) => phase.id === activeDepositPanel))
  const scrollToDepositPhase = (targetId: string, behavior: ScrollBehavior = 'smooth') => {
    if (!targetId || typeof document === 'undefined') return
    const target = document.getElementById(targetId)
    if (!target) return
    if (target instanceof HTMLDetailsElement) target.open = true
    target.scrollIntoView({ behavior, block: 'start' })
  }
  const goToDepositPhase = (targetId: DepositPhaseId, behavior: ScrollBehavior = 'smooth') => {
    setActiveDepositPanel(targetId)
    if (typeof window !== 'undefined') {
      window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}#${targetId}`)
      window.setTimeout(() => scrollToDepositPhase(targetId, behavior), 0)
    }
  }
  const openDepositPhase = (href: string) => (event: MouseEvent<HTMLAnchorElement>) => {
    if (!href.startsWith('#')) return
    event.preventDefault()
    const targetId = href.slice(1)
    if (isDepositPhaseId(targetId)) goToDepositPhase(targetId)
  }
  const afterVerification = (message?: string) => {
    refreshDetail(message || 'Verifica operativa completata. Passa ai documenti da inviare.')
    goToDepositPhase('proposta-busta')
  }
  const afterPreparation = (message?: string) => {
    refreshDetail(message || 'Controllo busta preparato. Apri busta e indice per vedere il risultato.')
    goToDepositPhase('generazione-busta')
  }
  const renderDepositStepControls = (currentId: DepositPhaseId) => {
    const index = depositPhases.findIndex((phase) => phase.id === currentId)
    const previous = index > 0 ? depositPhases[index - 1] : null
    const next = index >= 0 && index < depositPhases.length - 1 ? depositPhases[index + 1] : null
    return (
      <footer className="iu-fas-step-controls" aria-label="Navigazione fase deposito">
        <span className="iu-fas-step-controls__progress">Fase {index + 1} di {depositPhases.length}</span>
        <div>
          {previous ? <button type="button" onClick={() => goToDepositPhase(previous.id)}><ChevronRight size={14} className="is-back"/> {previous.title}</button> : null}
          {next ? <button type="button" className="is-primary" onClick={() => goToDepositPhase(next.id)}>{next.title} <ChevronRight size={14}/></button> : null}
        </div>
      </footer>
    )
  }
  const submitLocalPecPassword = () => {
    if (!localPecPasswordRequest) return
    if (!localPecPassword.trim()) {
      setLocalPecPasswordError('Inserisci la password PEC per completare l’invio dal PC locale.')
      return
    }
    const request = localPecPasswordRequest
    const password = localPecPassword
    setLocalPecPassword('')
    setLocalPecPasswordError('')
    setLocalPecPasswordRequest(null)
    request.resolve(password)
  }
  const cancelLocalPecPassword = () => {
    if (!localPecPasswordRequest) return
    const request = localPecPasswordRequest
    setLocalPecPassword('')
    setLocalPecPasswordError('')
    setLocalPecPasswordRequest(null)
    request.reject(new Error('Invio PEC annullato: password non inserita.'))
  }
  const submitLocalSignaturePin = () => {
    if (!localSignaturePinRequest) return
    if (!localSignaturePin.trim()) {
      setLocalSignaturePinError('Inserisci il PIN per firmare i dati del deposito e proseguire.')
      return
    }
    const request = localSignaturePinRequest
    const pinValue = localSignaturePin
    setLocalSignaturePin('')
    setLocalSignaturePinError('')
    setLocalSignaturePinRequest(null)
    request.resolve(pinValue)
  }
  const cancelLocalSignaturePin = () => {
    if (!localSignaturePinRequest) return
    const request = localSignaturePinRequest
    setLocalSignaturePin('')
    setLocalSignaturePinError('')
    setLocalSignaturePinRequest(null)
    request.reject(new Error('Firma dei dati del deposito annullata: PIN non inserito.'))
  }

  useEffect(() => {
    if (loading || typeof window === 'undefined') return undefined
    const targetId = decodeURIComponent(window.location.hash.replace(/^#/, ''))
    if (!targetId) return undefined
    if (isDepositPhaseId(targetId)) setActiveDepositPanel(targetId)
    const timer = window.setTimeout(() => scrollToDepositPhase(targetId, 'auto'), 160)
    return () => window.clearTimeout(timer)
  }, [loading, f.id])

  const hasLoadedDepositPayload = Boolean(f.id || f.ref || f.client || data.documents.length || regia.header.channel)
  const notFoundTitle = data.requestError ? 'Dati fascicolo non caricati' : 'Fascicolo non trovato'
  const notFoundMessage = data.requestError || 'Non ho trovato il fascicolo richiesto nella copia locale.'

  if (data.notFound) {
    return (
      <main className="iu-content iu-fascicoli-page iu-fascicolo-deposit-page">
        <section className="iu-fas-hero iu-fas-detail-hero">
          <div>
            <span className="iu-fas-eyebrow"><Send size={16}/> Deposito telematico</span>
            <h1>{notFoundTitle}</h1>
            <p>{notFoundMessage}</p>
          </div>
          <div className="iu-fas-hero__actions"><Button href="/fascicoli"><ArrowLeft size={15}/> Torna ai fascicoli</Button></div>
        </section>
      </main>
    )
  }

  if (loading && !hasLoadedDepositPayload) {
    return (
      <main className="iu-content iu-fascicoli-page iu-fascicolo-deposit-page">
        <section className="iu-fas-hero iu-fas-detail-hero">
          <div>
            <span className="iu-fas-eyebrow"><Send size={16}/> Deposito telematico</span>
            <h1>Prepara deposito</h1>
            <p>Caricamento del fascicolo e dei documenti di deposito.</p>
          </div>
          <div className="iu-fas-hero__actions">
            <Button href="/fascicoli"><ArrowLeft size={15}/> Torna ai fascicoli</Button>
          </div>
        </section>
        <section className="iu-fas-loading-panel" aria-live="polite">
          <RefreshCw size={18}/>
          <div>
            <strong>Sto preparando la sequenza deposito</strong>
            <span>La pagina mostra i dati solo quando fascicolo, documenti richiesti e firma sono stati letti.</span>
          </div>
        </section>
      </main>
    )
  }

  return (
    <main className="iu-content iu-fascicoli-page iu-fascicolo-deposit-page">
      <section className="iu-fas-hero iu-fas-detail-hero">
        <div>
          <span className="iu-fas-eyebrow"><Send size={16}/> Deposito telematico</span>
          <h1>Prepara deposito</h1>
          <p><Badge tone={preparationTone}>{depositStatusText}</Badge><span>{f.ref} - {f.client}</span></p>
        </div>
        <div className="iu-fas-hero__actions">
          <Button href={detailHref}><ArrowLeft size={15}/> Torna al fascicolo</Button>
          <Button href={`${detailHref}#documenti`}><FileText size={15}/> Documenti</Button>
          <Button href="/deposito/checklist"><ListChecks size={15}/> Controlli atti</Button>
          {evidenceHref ? <Button href={evidenceHref}><FileArchive size={15}/> Evidence pack</Button> : null}
        </div>
      </section>

      <section className="iu-fas-case-strip">
        <strong>{visibleRg}</strong>
        <span>{f.court || 'Ufficio da verificare'}</span>
        <span>{f.procedureType || f.type}</span>
        <span>{loading ? 'Caricamento...' : 'Dati aggiornati'}</span>
      </section>

      {toast ? <section className={`iu-fas-toast iu-fas-toast--${toast.tone}`}><span>{toast.message}</span><button type="button" onClick={() => setToast(null)}>Chiudi</button></section> : null}

      {localPecPasswordRequest ? (
        <div className="iu-fas-confirm-modal" role="dialog" aria-modal="true" aria-label="Password PEC locale">
          <form
            className="iu-fas-confirm-modal__box"
            onSubmit={(event) => {
              event.preventDefault()
              submitLocalPecPassword()
            }}
          >
            <strong>Password PEC locale</strong>
            <p>La password non viene salvata: viene inviata solo al Local Signer sul PC in uso per spedire il deposito.</p>
            <div className="iu-fas-local-pec-summary" aria-label="Riepilogo invio PEC locale">
              <span>Mittente</span>
              <strong>{localPecPasswordRequest.from || 'PEC studio configurata'}</strong>
              <span>Username SMTP locale</span>
              <strong>{localPecPasswordRequest.username || localPecPasswordRequest.from || 'Username PEC configurato'}</strong>
              <span>Destinatario</span>
              <strong>{localPecPasswordRequest.to || data.depositOffice.pec || 'PEC ufficio verificata'}</strong>
              <span>Oggetto</span>
              <strong>{localPecPasswordRequest.subject || 'DEPOSITO TELEMATICO'}</strong>
              <span>Allegati</span>
              <strong>{localPecPasswordRequest.attachments.length ? localPecPasswordRequest.attachments.map(depositAttachmentDisplayName).join(', ') : 'Pacchetto deposito'}</strong>
            </div>
            <label className="iu-fas-local-pec-password">
              <span>Password PEC</span>
              <input
                type="password"
                value={localPecPassword}
                autoFocus
                autoComplete="current-password"
                onChange={(event) => {
                  setLocalPecPassword(event.currentTarget.value)
                  if (localPecPasswordError) setLocalPecPasswordError('')
                }}
              />
            </label>
            {localPecPasswordError ? <span className="iu-fas-inline-error" role="alert">{localPecPasswordError}</span> : null}
            <footer>
              <button
                type="button"
                onClick={cancelLocalPecPassword}
              >
                Annulla
              </button>
              <button className="is-danger" type="button" onClick={submitLocalPecPassword}>Invia dal PC locale</button>
            </footer>
          </form>
        </div>
      ) : null}

      {localSignaturePinRequest ? (
        <div className="iu-fas-confirm-modal" role="dialog" aria-modal="true" aria-label="PIN firma deposito">
          <form
            className="iu-fas-confirm-modal__box"
            onSubmit={(event) => {
              event.preventDefault()
              submitLocalSignaturePin()
            }}
          >
            <strong>Firma dati deposito</strong>
            <p>Il software firma i dati del deposito sul PC in uso e poi prepara il pacchetto finale. Il PIN resta sul dispositivo locale e non viene salvato.</p>
            <div className="iu-fas-local-pec-summary" aria-label="Riepilogo firma deposito">
              <span>Da firmare</span>
              <strong>{depositAttachmentDisplayName(localSignaturePinRequest.filename) || 'Dati deposito'}</strong>
              <span>File prodotto</span>
              <strong>{depositAttachmentDisplayName(localSignaturePinRequest.outputFilename) || 'Dati firmati'}</strong>
              <span>Passaggio successivo</span>
              <strong>Pacchetto deposito</strong>
            </div>
            <label className="iu-fas-local-pec-password">
              <span>PIN firma</span>
              <input
                type="password"
                value={localSignaturePin}
                autoFocus
                autoComplete="off"
                onChange={(event) => {
                  setLocalSignaturePin(event.currentTarget.value)
                  if (localSignaturePinError) setLocalSignaturePinError('')
                }}
              />
            </label>
            {localSignaturePinError ? <span className="iu-fas-inline-error" role="alert">{localSignaturePinError}</span> : null}
            <footer>
              <button type="button" onClick={cancelLocalSignaturePin}>Annulla</button>
              <button className="is-danger" type="button" onClick={submitLocalSignaturePin}>Firma e continua</button>
            </footer>
          </form>
        </div>
      ) : null}

      <section className="iu-fas-cockpit iu-fas-deposit-cockpit" aria-label="Stato deposito">
        <StatCard icon={<ClipboardCheck size={19}/>} label="Regia" value={`${regia.header.completion}%`} note={depositStatusLabel(regia.header.operationalState || 'da verificare')} tone={preparationTone}/>
        <StatCard icon={<FolderOpen size={19}/>} label="Tutto fascicolo" value={data.documents.length} note={documentsToClassify.length ? `${documentsToClassify.length} da classificare` : 'letto integralmente'} tone={documentsToClassify.length ? 'warning' : 'success'} href="#inventario-fascicolo" onClick={openDepositPhase('#inventario-fascicolo')}/>
        <StatCard icon={<FileText size={19}/>} label="Candidati busta" value={depositCandidateDocuments.length} note={`${signedCandidateDocuments} firmati`} tone="primary" href="#proposta-busta" onClick={openDepositPhase('#proposta-busta')}/>
        <StatCard icon={<FileCheck2 size={19}/>} label="Firma software" value={unsignedCandidateDocuments} note="nel comando busta" tone={unsignedCandidateDocuments ? 'warning' : 'success'} href="#firma-busta" onClick={openDepositPhase('#firma-busta')}/>
        <StatCard icon={<Gavel size={19}/>} label="Atti principali" value={mainActs.length || 0} note="da confermare" tone={mainActs.length ? 'success' : 'warning'} href="#proposta-busta" onClick={openDepositPhase('#proposta-busta')}/>
        <StatCard icon={<Landmark size={19}/>} label="Documenti portale" value={portalCatalog.length} note="separati dalla busta" tone={portalCatalog.length ? 'info' : 'neutral'} href="#inventario-fascicolo" onClick={openDepositPhase('#inventario-fascicolo')}/>
        <StatCard icon={<Mail size={19}/>} label="Ricevute" value={recentDeposits.length} note={recentDeposits[0]?.status || 'nessuna PEC'} tone={recentDeposits.length ? 'purple' : 'neutral'} href="#verifica-deposito" onClick={openDepositPhase('#verifica-deposito')}/>
      </section>

      <section className="iu-fas-deposit-phases" aria-label="Percorso deposito">
        <header>
          <div>
            <strong>Percorso deposito</strong>
            <span>Fase {activeDepositPhaseIndex + 1} di {depositPhases.length}: lavora un pannello alla volta. La busta nasce dalla selezione, dalla firma e dall'indice generati in questo flusso.</span>
          </div>
          <Badge tone={actionBlocked ? 'warning' : signatureBatchRequired ? 'warning' : 'success'}>
            {actionBlocked ? 'Da completare' : signatureBatchRequired ? 'Firma richiesta' : 'Navigabile'}
          </Badge>
        </header>
        <nav aria-label="Fasi operative del deposito">
          {depositPhases.map((phase) => (
            <a
              className={`iu-fas-deposit-phase iu-fas-deposit-phase--${phase.tone}${phase.id === activeDepositPanel ? ' is-active' : ''}`}
              href={phase.href}
              onClick={openDepositPhase(phase.href)}
              aria-current={phase.id === activeDepositPanel ? 'step' : undefined}
              key={phase.href}
            >
              <span className="iu-fas-deposit-phase__index">{phase.index}</span>
              <span className="iu-fas-deposit-phase__copy">
                <strong>{phase.title}</strong>
                <small>{phase.detail}</small>
              </span>
              <Badge tone={phase.tone}>{phase.state}</Badge>
              <ChevronRight size={15} aria-hidden="true"/>
            </a>
          ))}
        </nav>
      </section>

      <section className="iu-fas-detail-grid iu-fas-deposit-step-layout">
        <div className="iu-fas-detail-main iu-fas-deposit-step-main">
          <DetailSection id="verifica-deposito" title="1. Verifica pratica" icon={<ShieldCheck size={17}/>} open={activeDepositPanel === 'verifica-deposito'} onToggle={(nextOpen) => { if (nextOpen) setActiveDepositPanel('verifica-deposito') }} count={decisiveValidationRows.length}>
            <div className="iu-fas-regia__deposit iu-fas-deposit-prepare-box">
              <div>
                <Badge tone={preparationTone}>{decisiveValidationRows.length ? 'Da completare alla generazione' : ready ? 'Pronto per generare' : 'In preparazione'}</Badge>
                <strong>{recordText(deposit, 'label', 'Deposito telematico')}</strong>
                <p>{depositUserFacingMessage(depositMessage)}</p>
                <p className="iu-fas-sync-note"><ShieldCheck size={14}/><strong>{deliveryLabel}</strong><span>{depositUserFacingMessage(deliveryDetail)}</span></p>
                <p className="iu-fas-sync-note"><Gavel size={14}/><strong>Profilo pratica</strong><span>{[practiceProfileName, practiceProfileReason].filter(Boolean).join(' - ') || 'Il profilo determina documenti obbligatori, controlli e canale di deposito.'}</span></p>
                <p className="iu-fas-sync-note"><ListChecks size={14}/><strong>Regola operativa</strong><span>Qui lavori sulla proposta. I requisiti obbligatori vengono controllati quando generi la busta; gli avvisi non fermano il lavoro.</span></p>
                <p className="iu-fas-sync-note"><FileCheck2 size={14}/><strong>Firma nella generazione</strong><span>{immediateBatchSigning || oneStepSigning || signatureBatchRequired ? 'Quando premi Firma e genera busta, il software usa il PIN per firmare in lotto i documenti necessari, salva i documenti firmati e aggiorna i controlli prima del pacchetto.' : 'La firma viene verificata secondo il canale impostato.'}</span></p>
                <p className="iu-fas-sync-note"><PackageCheck size={14}/><strong>Indice documenti</strong><span>{documentIndexGeneratedBySoftware ? 'L’indice viene generato dal software in tempo reale quando viene preparata la busta.' : 'L’indice viene verificato durante la preparazione.'}</span></p>
              </div>
              <div className="iu-fas-regia__actions">
                {predepositAction ? <PostAction action={predepositAction} tone="secondary" onDone={afterVerification} onError={failDetail}><RefreshCw size={15}/> Verifica operativa</PostAction> : null}
                {prepareAction ? <PostAction action={prepareAction} tone="secondary" onDone={afterPreparation} onError={failDetail}><ClipboardCheck size={15}/> {prepareLabel}</PostAction> : null}
                {ready && directPecReady && sendAction ? <PostAction action={sendAction} tone="primary" onDone={refreshDetail} onError={failDetail} confirm="Inviare la busta con la PEC configurata? Verifica prima ufficio, firma, allegati e ricevute attese." confirmTitle="Invia deposito"><Send size={15}/> {sendLabel}</PostAction> : null}
                {portalUploadRequired ? <a className="iu-fas-side-link" href={portalHref} target="_blank" rel="noreferrer"><UploadCloud size={15}/> Apri portale ufficiale</a> : null}
              </div>
            </div>
            {depositActionNotice ? (
              <div className={`iu-fas-action-notice iu-fas-action-notice--${depositActionNotice.tone}`} role="status">
                <Badge tone={depositActionNotice.tone}>{depositActionNotice.tone === 'success' ? 'Azione eseguita' : 'Da controllare'}</Badge>
                <span>{depositUserFacingMessage(depositActionNotice.message)}</span>
              </div>
            ) : null}
            {guidedCompletion ? (
              <div className="iu-fas-guided-block">
                <Badge tone="warning">Completamento richiesto</Badge>
                <strong>{depositUserFacingMessage(missingOperationalStep || 'Pacchetto deposito da completare')}</strong>
                <p>Il software prepara i controlli e registra l’invio solo quando il pacchetto è completo.</p>
                {guidedNextActions.length ? <ul>{guidedNextActions.map((action) => <li key={action}>{depositUserFacingMessage(action)}</li>)}</ul> : null}
              </div>
            ) : null}
            <div className="iu-fas-regia-list iu-fas-deposit-check-list">
              <article>
                <Badge tone={directPecReady ? 'success' : directPecAllowed ? 'warning' : portalUploadRequired ? 'info' : 'warning'}>{deliveryLabel}</Badge>
                <strong>{depositUserFacingMessage(packageKindLabel)}</strong>
                <span>{depositUserFacingMessage(deliveryOfficialChannel)}</span>
                <small>{depositUserFacingMessage(deliveryNote || (deliveryMode === 'direct_pec' ? 'La ricevuta di accettazione PEC avvia il momento rilevante del deposito solo dopo invio conforme.' : 'Dopo l’invio sul portale importa ricevuta, protocollo o esito nel fascicolo.'))}</small>
              </article>
            </div>
            <div className="iu-fas-regia-list iu-fas-deposit-check-list">
              {decisiveValidationRows.map((row, index) => (
                <article className="iu-fas-deposit-check-list__decisive" key={`${row.label}-${row.message}-${index}`}>
                  <Badge tone="warning">{depositIssueLabel(row)}</Badge>
                  <strong>{depositIssueMessage(row)}</strong>
                  {row.note ? <span>{row.note}</span> : null}
                </article>
              ))}
              {!decisiveValidationRows.length ? <p className="iu-empty">Nessun requisito bloccante da risolvere prima del comando di generazione. Gli avvisi restano informativi.</p> : null}
            </div>
            {advisoryValidationRows.length ? (
              <details className="iu-fas-deposit-advisory">
                <summary><AlertTriangle size={14}/> Avvisi e informazioni ({advisoryValidationRows.length})</summary>
                <div className="iu-fas-regia-list iu-fas-deposit-check-list iu-fas-deposit-check-list--advisory">
                  {advisoryValidationRows.map((row, index) => (
                    <article key={`advisory-${row.label}-${row.message}-${index}`}>
                      <Badge tone={row.tone === 'danger' ? 'warning' : row.tone}>{depositIssueLabel(row)}</Badge>
                      <strong>{depositIssueMessage(row)}</strong>
                      {row.note ? <span>{row.note}</span> : null}
                    </article>
                  ))}
                </div>
              </details>
            ) : null}
            {renderDepositStepControls('verifica-deposito')}
          </DetailSection>

          <DetailSection id="proposta-busta" title="2. Documenti da inviare" icon={<PackageCheck size={17}/>} open={activeDepositPanel === 'proposta-busta'} onToggle={(nextOpen) => { if (nextOpen) setActiveDepositPanel('proposta-busta') }} count={packageDocuments.length}>
            <div className="iu-fas-deposit-selection" aria-label="Documenti da inviare nel deposito">
              <header>
                <div>
                  <strong>Documenti da inviare</strong>
                  <span>Puoi aggiungere documenti e includerli nella busta: IUSENTRA firma solo quelli scelti, poi calcola indice e controlli.</span>
                  <span>Il software segnala i candidati; l'avvocato sceglie cosa entra nella busta prima di firmare e generare.</span>
                </div>
                <Badge tone={packageDocuments.length ? 'primary' : 'warning'}>
                  {packageDocuments.length === 1 ? '1 selezionato' : `${packageDocuments.length} selezionati`}
                </Badge>
              </header>
              <DepositTypePreviewPanel
                catalog={data.depositCatalog}
                selectedKey={selectedDepositTypeKey}
                onSelect={(key) => {
                  setSelectedDepositTypeKey(key)
                }}
                currentProfile={practiceProfileName}
              />
              <DepositSpecificDataForm
                entry={selectedDepositType}
                catalog={data.depositCatalog}
                values={depositSpecificData}
                onChange={(fieldId, value) => setDepositSpecificData((current) => ({ ...current, [fieldId]: value }))}
              />
              <div className="iu-fas-deposit-selection__tools">
                <button type="button" onClick={resetDepositSelectionToProposal}><PackageCheck size={14}/> Ripristina documenti collegati</button>
                <button type="button" onClick={deselectAllDepositDocuments}><RotateCcw size={14}/> Deseleziona tutto</button>
                <button type="button" className="is-primary" onClick={() => { void saveDepositClassification() }} disabled={classificationSaving}>
                  <Save size={14}/> {classificationSaving ? 'Salvataggio...' : 'Salva classificazione'}
                </button>
                <a href={`${detailHref}#documenti`}><UploadCloud size={14}/> Apri documenti fascicolo</a>
              </div>
              {data.actions.uploadDocument ? (
                <details className="iu-fas-deposit-upload">
                  <summary><UploadCloud size={14}/> Allega documentazione al fascicolo</summary>
                  <DocumentUploadWorkspace data={data} onDone={refreshDetail} onError={failDetail}/>
                </details>
              ) : null}
              <div className="iu-fas-deposit-selection__list">
                {depositSelectableDocuments.map((doc) => {
                  const classification = effectiveDepositClassificationById[doc.id] || {
                    selected: defaultDepositSelectionIds.includes(doc.id),
                    role: defaultDepositRoleForDocument(doc, '', defaultMainActDocumentId === doc.id),
                    alreadySigned: doc.signed,
                  }
                  const selected = Boolean(classification.selected)
                  const isMainAct = mainActDocument?.id === doc.id
                  const roleValue = normaliseDepositRoleForUi(classification.role || defaultDepositRoleForDocument(doc, '', defaultMainActDocumentId === doc.id))
                  const roleDisplayLabel = depositRoleDisplayLabelForDocument(doc, roleValue)
                  const canRequestSignature = !doc.signed && requiresPackageSignature(doc)
                  const mandatorySignature = selected && defaultSignatureRequiredForDepositRole(doc, roleValue)
                  const signatureRequested = selected && canRequestSignature && (mandatorySignature || Boolean(classification.requiresSignature))
                  const signatureLabel = doc.signed
                    ? 'Firmato'
                    : canRequestSignature ? (signatureRequested ? 'Da firmare' : 'Firma facoltativa') : 'Firma non necessaria'
                  const depositStatusLabel = doc.signed
                    ? 'Firmato'
                    : signatureRequested ? 'Da firmare' : (canRequestSignature ? 'Firma facoltativa' : 'Firma non necessaria')
                  const showSignatureControl = selected || doc.signed || canRequestSignature
                  return (
                    <article className={`iu-fas-deposit-selection__row${selected ? ' is-selected' : ''}${isMainAct ? ' is-main' : ''}`} key={`select-${doc.id}`}>
                      <label className="iu-fas-deposit-selection__include">
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={(event) => updateDepositClassification(doc.id, { selected: event.currentTarget.checked })}
                          aria-label={`Includi nel deposito ${doc.name}`}
                        />
                        <span>Invia</span>
                      </label>
                      <div className="iu-fas-deposit-selection__document">
                        <strong>{doc.name}</strong>
                        <span>{[roleDisplayLabel, depositStatusLabel, doc.size].filter(Boolean).join(' - ')}</span>
                        {doc.signed ? <em>Firma digitale verificata</em> : null}
                        {selected && signatureRequested ? <small>IUSENTRA lo firma in lotto prima di generare la busta.</small> : null}
                      </div>
                      <div className="iu-fas-deposit-document-actions" aria-label={`Azioni documento ${doc.name}`}>
                        {doc.actions.preview ? (
                          <button type="button" title={`Visualizza ${doc.name}`} aria-label={`Visualizza ${doc.name}`} onClick={() => setPreviewDoc({ name: doc.name, url: doc.actions.preview, downloadUrl: doc.actions.download })}>
                            <Eye size={17} strokeWidth={2.4} aria-hidden="true"/>
                          </button>
                        ) : null}
                        {doc.actions.rename ? (
                          <button type="button" title={`Modifica nome ${doc.name}`} aria-label={`Modifica nome ${doc.name}`} onClick={() => startDepositDocumentRename(doc)}>
                            <PencilLine size={17} strokeWidth={2.4} aria-hidden="true"/>
                          </button>
                        ) : null}
                        {doc.actions.download ? (
                          <a href={doc.actions.download} title={`Scarica originale ${doc.name}`} aria-label={`Scarica originale ${doc.name}`}>
                            <Download size={17} strokeWidth={2.4} aria-hidden="true"/>
                          </a>
                        ) : null}
                      </div>
                      {depositRenameDocId === doc.id ? (
                        <form className="iu-fas-doc-rename-form iu-fas-deposit-rename-form" onSubmit={(event) => { void submitDepositDocumentRename(event, doc) }}>
                          <input
                            value={depositRenameDraft}
                            onChange={(event) => setDepositRenameDraft(event.currentTarget.value)}
                            aria-label={`Nuovo nome file ${doc.name}`}
                            autoFocus
                          />
                          <button type="submit" disabled={depositRenameBusy}>{depositRenameBusy ? 'Salvo...' : 'Salva nome'}</button>
                          <button type="button" onClick={cancelDepositDocumentRename} disabled={depositRenameBusy}>Annulla</button>
                          {depositRenameMessage ? <small>{depositRenameMessage}</small> : null}
                        </form>
                      ) : null}
                      <div className="iu-fas-deposit-selection__controls">
                          <DepositRolePicker
                            documentName={doc.name}
                            value={roleValue}
                          onChange={(nextRole) => updateDepositClassification(doc.id, { role: nextRole })}
                        />
                        {showSignatureControl ? (
                          <label className="iu-fas-deposit-selection__signed" aria-disabled={!canRequestSignature || mandatorySignature}>
                            <input
                              type="checkbox"
                              checked={doc.signed || signatureRequested}
                              disabled={doc.signed || !canRequestSignature || mandatorySignature}
                              onChange={(event) => updateDepositClassification(doc.id, {
                                requiresSignature: event.currentTarget.checked,
                                selected: event.currentTarget.checked ? true : selected,
                              })}
                              aria-label={`${mandatorySignature ? 'Firma obbligatoria' : signatureRequested ? 'Firma richiesta' : 'Firma non richiesta'} per ${doc.name}`}
                            />
                            <span>{signatureLabel}</span>
                          </label>
                        ) : null}
                      </div>
                    </article>
                  )
                })}
                {!depositSelectableDocuments.length ? <p className="iu-empty">Nessun documento selezionabile: carica o classifica l'atto principale e gli allegati prima del deposito.</p> : null}
              </div>
            </div>
            {renderDepositStepControls('proposta-busta')}
          </DetailSection>

          <DetailSection id="firma-busta" title="3. Firma documenti" icon={<FileCheck2 size={17}/>} open={activeDepositPanel === 'firma-busta'} onToggle={(nextOpen) => { if (nextOpen) setActiveDepositPanel('firma-busta') }} count={unsignedPackageDocuments.length}>
            <div className="iu-fas-deposit-phase-note">
              <Badge tone={signaturePhaseTone}>{signatureBatchRequired ? 'Firma software' : 'Documenti pronti'}</Badge>
              <strong>{signatureBatchRequired ? 'Il software firmerà i documenti necessari prima del pacchetto' : 'I documenti selezionati non richiedono altre firme'}</strong>
              <span>{signatureBatchRequired ? 'Inserito il PIN una sola volta, IUSENTRA firma in lotto, salva gli esiti e prepara il pacchetto.' : 'Durante la prova il dispositivo firma i dati del deposito, poi il software genera indice e pacchetto.'}</span>
            </div>
            {signatureBatchRequired ? (
              <DepositBatchSignaturePanel
                fascicoloId={f.id || id}
                documents={unsignedPackageDocuments}
                signature={data.signature}
                registerAction={activeDepositPanel === 'firma-busta' ? registerBatchSignatureAction : undefined}
                onDone={refreshDetail}
                onError={failDetail}
              />
            ) : null}
            {renderDepositStepControls('firma-busta')}
          </DetailSection>

          <DetailSection id="generazione-busta" title="4. Pacchetto deposito" icon={<FileArchive size={17}/>} open={activeDepositPanel === 'generazione-busta'} onToggle={(nextOpen) => { if (nextOpen) setActiveDepositPanel('generazione-busta') }} count={packageDocuments.length + 2}>
            <div className="iu-fas-package-office">
              <div>
                <Badge tone={officeRecipientBadgeTone}>{officeRecipientBadgeLabel}</Badge>
                <strong>{data.depositOffice.name || f.court || 'Ufficio giudiziario da verificare'}</strong>
                <span>{data.depositOffice.pec || 'Indirizzo PEC non disponibile.'}</span>
              </div>
              <small>{depositUserFacingMessage(data.depositOffice.message || officeRecipientDefaultMessage)}</small>
              {depositOfficeCodeAvailable ? (
                <small>{depositOfficeVerified ? 'Ufficio verificato' : 'Codice ufficio presente: il certificato viene controllato nella prova.'}</small>
              ) : pctJsonPackageChannel ? (
                <small>Codice ufficio non risolto automaticamente: aggiorna catalogo uffici o verifica l’ufficio della pratica.</small>
              ) : null}
            </div>
            <div className="iu-fas-package-board">
              <article className="iu-fas-package-main">
                <Badge tone={mainActDocument ? (mainActDocument.signed ? 'success' : 'warning') : 'danger'}>Atto principale</Badge>
                <strong>{mainActDocument?.name || 'Da selezionare'}</strong>
                  <span>{mainActDocument ? [mainActDocument.type, mainActDocument.signed ? 'Firmato' : 'Da firmare', mainActDocument.size].filter(Boolean).join(' - ') : 'Il software non seleziona se la classificazione non è certa.'}</span>
                {mainActDocument && !mainActDocument.signed ? <small>Firma software prevista prima del pacchetto.</small> : null}
              </article>
              <article>
                <Badge tone={selectedAttachmentIds.length ? 'primary' : 'neutral'}>Allegati</Badge>
                <strong>{selectedAttachmentIds.length}</strong>
                <span>{selectedAttachmentIds.length ? 'Collegati da scelte e prove già presenti.' : 'Nessun allegato selezionato.'}</span>
              </article>
              <article>
                <Badge tone={notificationProofDocuments.length ? 'info' : 'neutral'}>Prova notifica</Badge>
                <strong>{notificationProofDocuments.length}</strong>
                <span>{notificationProofDocuments.length ? 'Inclusa senza riproporre un nuovo invio.' : 'Nessuna prova già presente.'}</span>
              </article>
              <article>
                <Badge tone={missingRequiredSlots.length ? 'warning' : 'success'}>Scelte manuali</Badge>
                <strong>{missingRequiredSlots.length}</strong>
                <span>{missingRequiredSlots.length ? 'Avvisi da verificare: non bloccano la prova se l’avvocato ha già scelto i documenti.' : 'Scelte obbligatorie collegate.'}</span>
              </article>
              <article>
                <Badge tone={unsignedPackageDocuments.length ? 'warning' : 'success'}>Firme</Badge>
                <strong>{unsignedPackageDocuments.length}</strong>
                <span>{unsignedPackageDocuments.length ? 'Documenti che IUSENTRA firmerà con un solo PIN.' : 'Documenti selezionati già firmati o senza firma richiesta.'}</span>
              </article>
            </div>
            <div className="iu-fas-package-docs">
              <article key="package-datiatto">
                <FileText size={16}/>
                <div>
                  <strong>Dati deposito</strong>
                  <span>Dati preparati dal software in base al tipo deposito e ai documenti selezionati.</span>
                </div>
                <small>Generato</small>
              </article>
              <article key="package-indice-documenti">
                <FileText size={16}/>
                <div>
                  <strong>Indice documenti</strong>
                  <span>Indice generato dal software con atto principale, allegati e prove selezionate.</span>
                </div>
                <DepositPdfPreviewButton
                  action={`/fascicoli/${encodedId}/deposito/indice-documenti`}
                  payload={depositActionPayload}
                  onPreview={setPreviewDoc}
                  onError={failDetail}
                  disabled={indicePreviewDisabled}
                  disabledReason={indicePreviewDisabledReason}
                />
                <small>Generato</small>
              </article>
              {packageDocuments.map((doc) => {
                const proofLabel = notificationProofKind(doc) ? notificationProofLabel(doc) : ''
                const willSign = unsignedPackageDocuments.some((item) => item.id === doc.id)
                const signatureLabel = willSign ? 'Da firmare' : packageDocumentSignatureLabel(doc)
                return (
                  <article key={`package-${doc.id}`}>
                    <FileText size={16}/>
                    <div>
                      <strong>{doc.name}</strong>
                      <span>{[proofLabel, doc.type, signatureLabel, doc.size].filter(Boolean).join(' - ')}</span>
                    </div>
                    {willSign ? <small>Firma software prima della busta</small> : null}
                  </article>
                )
              })}
              {!packageDocuments.length ? <p className="iu-empty">Nessun documento ancora collegato alle scelte deposito: usa la selezione manuale nei documenti richiesti.</p> : null}
            </div>
            {signatureBatchRequired ? (
              <div className="iu-fas-package-signing">
                <div className="iu-fas-deposit-phase-note">
                  <Badge tone="warning">Firma immediata</Badge>
                  <strong>{unsignedPackageDocuments.length === 1 ? '1 documento sarà firmato prima del pacchetto' : `${unsignedPackageDocuments.length} documenti saranno firmati prima del pacchetto`}</strong>
                  <span>Inserisci il PIN una sola volta: IUSENTRA firma il lotto, salva ogni documento firmato nel fascicolo e poi prosegue con indice, pacchetto e testo PEC.</span>
                </div>
                <DepositBatchSignaturePanel
                  fascicoloId={f.id || id}
                  documents={unsignedPackageDocuments}
                  signature={data.signature}
                  registerAction={activeDepositPanel === 'generazione-busta' ? registerBatchSignatureAction : undefined}
                  onDone={refreshDetail}
                  onError={failDetail}
                />
              </div>
            ) : (
              <div className="iu-fas-package-signing iu-fas-package-signing--ready">
                <CheckCircle2 size={16}/>
                <span>Documenti pronti. Durante la prova il dispositivo firma i dati del deposito e il software genera indice, pacchetto e controllo PEC.</span>
              </div>
            )}
            <div className="iu-fas-package-pec-draft">
              <header>
                <div>
                  <strong>Testo PEC</strong>
                  <span>La bozza viene usata automaticamente; l'avvocato la modifica solo se vuole prima della prova o dell'invio.</span>
                </div>
                <button type="button" onClick={() => setPecBodyEditorOpen((open) => !open)}>
                  {pecBodyEditorOpen ? 'Chiudi modifica' : 'Modifica testo PEC'}
                </button>
              </header>
              {pecBodyEditorOpen ? (
                <textarea
                  value={pecBodyDraft || standardPecBody}
                  onChange={(event) => {
                    setPecBodyDraft(event.currentTarget.value)
                    setPecBodyEdited(true)
                    setPackagePreview((current) => current ? { ...current, corpoPec: event.currentTarget.value } : current)
                  }}
                  rows={8}
                  aria-label="Testo del corpo PEC del deposito"
                />
              ) : (
                <pre>{pecBodyDraft || standardPecBody}</pre>
              )}
              {pecBodyEdited ? (
                <button
                  type="button"
                  className="iu-fas-package-pec-draft__reset"
                  onClick={() => {
                    setPecBodyDraft(standardPecBody)
                    setPecBodyEdited(false)
                    setPackagePreview((current) => current ? { ...current, corpoPec: standardPecBody } : current)
                  }}
                >
                  Ripristina testo standard
                </button>
              ) : null}
            </div>
            <div className="iu-fas-package-actions">
              <DepositActionButton
                action={dryRunBustaAction}
                payload={depositDryRunActionPayload}
                disabled={actionBlocked}
                disabledReason={actionBlockedReason}
                beforeSubmit={prepareDepositBeforeSubmit}
                progressItems={DEPOSIT_PROGRESS_USER_STEPS}
                tone="primary"
                confirm={
                  signatureBatchRequired
                      ? 'Firmare ora i documenti selezionati, salvare i file firmati nel fascicolo e poi generare indice, busta di controllo e testo PEC senza invio reale?'
                      : 'Preparare busta, indice documenti, destinatario e testo PEC senza inviare nulla?'
                }
                confirmTitle={signatureBatchRequired ? 'Firma e prepara prova' : 'Prova senza invio'}
                onDone={refreshDetail}
                onError={failDetail}
                onPackageReady={handlePackageReady}
                completeLocalSignature={completeDepositLocalSignature}
              >
                <FileArchive size={15}/> {signatureBatchRequired ? 'Firma e prepara prova' : 'Prova senza invio reale'}
              </DepositActionButton>
              <DepositActionButton
                action={dryRunBustaAction}
                payload={depositSimulationActionPayload}
                disabled={actionBlocked}
                disabledReason={actionBlockedReason}
                beforeSubmit={prepareDepositBeforeSubmit}
                progressItems={DEPOSIT_PROGRESS_USER_STEPS}
                progressLabel="Simulazione PEC in corso"
                tone="secondary"
                confirm="Simulare l'invio PEC senza spedire nulla all'esterno? Il software prepara il pacchetto deposito, controlla corpo e destinatario, confronta la prova con i campioni reali e registra solo una prova senza invio."
                confirmTitle="Simula invio PEC"
                onDone={refreshDetail}
                onError={failDetail}
                onPackageReady={handlePackageReady}
                completeLocalSignature={completeDepositLocalSignature}
              >
                <Mail size={15}/> Simula invio PEC
              </DepositActionButton>
              <DepositActionButton
                action={realSendAction}
                payload={depositActionPayload}
                disabled={actionBlocked || requiredDepositDataBlocked || !packageReadyForRealSend || !realSendAvailable}
                disabledReason={realSendDisabledReason}
                beforeSubmit={prepareDepositBeforeSubmit}
                progressItems={DEPOSIT_PROGRESS_USER_STEPS}
                progressLabel="Invio deposito in corso"
                tone="secondary"
                confirm="Inviare realmente il deposito con la PEC configurata? Usa questo comando solo dopo avere controllato indice, destinatario, oggetto, testo PEC e documenti della prova."
                confirmTitle="Invia deposito reale"
                onDone={refreshDetail}
                onError={failDetail}
                onPackageReady={handlePackageReady}
                completeLocalSignature={completeDepositLocalSignature}
                completeLocalPec={completeDepositLocalPec}
              >
                <Send size={15}/> Invia deposito reale
              </DepositActionButton>
              {portalUploadRequired ? <a className="iu-fas-side-link" href={portalHref} target="_blank" rel="noreferrer"><UploadCloud size={15}/> Apri portale ufficiale</a> : null}
              {requiredSpecificDataNotice ? <a className="iu-fas-side-link" href="#proposta-busta" onClick={openDepositPhase('#proposta-busta')}><Edit3 size={15}/> Completa dati deposito</a> : null}
              {requiredChoicesNotice ? <small>{depositUserFacingMessage(requiredChoicesNotice)}</small> : null}
              {requiredSpecificDataNotice ? <small>{requiredSpecificDataNotice}</small> : null}
              {actionBlocked ? <small>{depositUserFacingMessage(actionBlockedReason || depositActionBlockedReason(ready, mainActDocument, missingRequiredSlots, signaturesRequiredBeforeAction ? unsignedPackageDocuments.length : 0))}</small> : <small>{signatureBatchRequired ? `${unsignedPackageDocuments.length} documenti saranno firmati da IUSENTRA con firma multipla. ` : ''}{directPecReady ? 'Il software prepara pacchetto, invio PEC e presidio ricevute nel fascicolo.' : guidedCompletion ? 'Il software governa controlli, indice, firma dei dati deposito e invio dal PC locale; se manca un requisito lo indica prima dell’invio.' : 'Il software prepara il pacchetto e governa il caricamento finale sul portale ufficiale.'}</small>}
            </div>
            {packagePreview ? (
              <div className="iu-fas-package-preview" role="status">
                <header>
                  <Badge tone={packagePreview.packageReady ? 'success' : 'warning'}>Prova senza invio PEC</Badge>
                  <div>
                    <strong>{depositUserFacingMessage(packagePreview.message)}</strong>
                    <span>Controlla destinatario, oggetto, corpo PEC e documenti prima del deposito reale.</span>
                  </div>
                </header>
                <div className="iu-fas-package-preview__grid">
                  <article>
                    <span>Destinatario PEC</span>
                    <strong>{packagePreview.pecDest || data.depositOffice.pec || 'Da verificare'}</strong>
                  </article>
                  <article>
                    <span>Oggetto PEC</span>
                    <strong>{packagePreview.oggettoPec || 'Da generare'}</strong>
                  </article>
                  <article>
                    <span>Riferimento prova</span>
                    <strong>{packagePreview.idDeposito || 'Non registrato'}</strong>
                  </article>
                </div>
                {compatibilityPercent >= 0 ? (
                  <section className="iu-fas-compat-report" aria-label="Report compatibilità deposito">
                    <header>
                      <Badge tone={compatibilityPercent === 100 ? 'success' : compatibilityPercent >= 80 ? 'warning' : 'danger'}>Compatibilità {compatibilityPercent}%</Badge>
                      <div>
                        <strong>{recordText(compatibilityReport, 'summary', 'Report di compatibilità generato dalla prova senza invio.')}</strong>
                        <span>Confronto con i campioni PEC reali allegati e con i documenti prodotti dalla prova.</span>
                      </div>
                    </header>
                    {compatibilityChecks.length ? (
                      <div className="iu-fas-compat-report__checks">
                        {compatibilityChecks.slice(0, 8).map((item) => {
                          const code = recordText(item, 'code') || recordText(item, 'label')
                          const status = recordText(item, 'status', 'warning')
                          return (
                            <article className={`is-${status}`} key={code}>
                              <span>{status === 'ok' ? 'OK' : status === 'blocco' ? 'Blocco' : 'Avviso'}</span>
                              <strong>{depositUserFacingMessage(recordText(item, 'label', code))}</strong>
                              <small>{depositUserFacingMessage(recordText(item, 'detail'))}</small>
                            </article>
                          )
                        })}
                      </div>
                    ) : null}
                    {compatibilityReceipts.length ? (
                      <div className="iu-fas-compat-report__receipts">
                        <strong>Ricevute da presidiare dopo l'invio reale</strong>
                        <ul>{compatibilityReceipts.map((item) => <li key={recordText(item, 'id', recordText(item, 'label'))}>{recordText(item, 'label')}</li>)}</ul>
                      </div>
                    ) : null}
                  </section>
                ) : null}
                {pecWorkflowAvailable ? (
                  proofBlocksDirectSend ? (
                    <p className="iu-fas-package-preview__confirm">
                      Invio reale sospeso: completa i controlli obbligatori indicati nella prova.
                    </p>
                  ) : (
                    <p className="iu-fas-package-preview__confirm">
                      Controlli software superati: destinatario PEC, indice, documenti, testo e trasporto risultano pronti per l’invio reale.
                    </p>
                  )
                ) : (
                  <p className="iu-fas-package-preview__confirm">
                    {depositUserFacingMessage(officeRecipientBlockingReason || 'IUSENTRA non ha risolto automaticamente la PEC dell’ufficio: aggiorna il catalogo uffici o verifica l’ufficio giudiziario della pratica.')}
                  </p>
                )}
                {packagePreview.documenti.length ? (
                  <div className="iu-fas-package-preview__documents">
                    <strong>Documenti indicati nel pacchetto</strong>
                    <ul>
                      {packagePreview.documenti.map((name) => <li key={name}>{name}</li>)}
                    </ul>
                  </div>
                ) : null}
                {packagePreview.corpoPec ? (
                  <div className="iu-fas-package-preview__body">
                    <strong>Testo PEC predisposto</strong>
                    <pre>{packagePreview.corpoPec}</pre>
                  </div>
                ) : null}
                {packagePreview.nextActions.length ? (
                  <div className="iu-fas-package-preview__next">
                    <strong>{realSendAvailable ? 'Promemoria prima dell’invio reale' : 'Controlli ancora richiesti prima dell’invio reale'}</strong>
                    <ul>{packagePreview.nextActions.map((item) => <li key={item}>{item}</li>)}</ul>
                  </div>
                ) : null}
              </div>
            ) : null}
            {renderDepositStepControls('generazione-busta')}
          </DetailSection>

          <DetailSection id="inventario-fascicolo" title="5. Inventario fascicolo" icon={<FolderOpen size={17}/>} open={activeDepositPanel === 'inventario-fascicolo'} onToggle={(nextOpen) => { if (nextOpen) setActiveDepositPanel('inventario-fascicolo') }} count={data.documents.length}>
            <p className="iu-fas-sync-note"><FolderOpen size={14}/> La preparazione legge tutti i documenti presenti nel fascicolo; la busta usa solo i documenti selezionati dall'avvocato e i controlli del canale.</p>
            <div className="iu-fas-comm-list">
              {data.documents.map((doc) => {
                const role = documentOperationalRole(doc)
                return (
                  <article className="iu-fas-comm-row" key={`inventory-${doc.id}`}>
                    <Badge tone={role.tone}>{role.label}</Badge>
                    <strong>{doc.name}</strong>
                    <span>{[doc.source, doc.portalClass || doc.type, doc.portalDate || doc.documentDate || doc.uploadedAt, doc.size].filter(Boolean).join(' - ')}</span>
                    <small>{role.detail}</small>
                  </article>
                )
              })}
              {!data.documents.length ? <p className="iu-empty">Nessun documento nel fascicolo: carica atto principale e allegati prima del deposito.</p> : null}
            </div>
            {renderDepositStepControls('inventario-fascicolo')}
          </DetailSection>

          <DetailSection id="documenti-deposito" title="Documenti candidati alla busta" icon={<FileText size={17}/>} count={depositCandidateDocuments.length}>
            <div className="iu-fas-doc-section-list">
              {documentSections.map((section) => (
                <section className="iu-fas-doc-auto-section" key={section.id}>
                  <header>
                    <Badge tone={section.tone}>{section.documents.length}</Badge>
                    <div>
                      <strong>{section.title}</strong>
                      <span>{section.note}</span>
                    </div>
                  </header>
                  <div className="iu-fas-doc-list">
                    {section.documents.map((doc) => <DocumentRow doc={doc} key={doc.id} onPreview={setPreviewDoc} onDone={refreshDetail} onError={failDetail}/>)}
                  </div>
                </section>
              ))}
              {!depositCandidateDocuments.length ? <p className="iu-empty">Nessun documento candidato alla busta. Carica o classifica l'atto principale e gli allegati prima di preparare la sessione.</p> : null}
            </div>
          </DetailSection>

          <DetailSection id="catalogo-portale" title="Documenti acquisiti dal portale" icon={<Landmark size={17}/>} count={portalCatalog.length}>
            <div className="iu-fas-comm-list">
              {portalCatalog.map((row) => (
                <article className="iu-fas-comm-row" key={row.id}>
                  <Badge tone={row.tone}>{row.role}</Badge>
                  <strong>{row.name}</strong>
                  <span>{[row.source, row.type, row.date, row.sender].filter(Boolean).join(' - ')}</span>
                  <small>{row.imported ? 'File acquisito nel fascicolo con classificazione portale.' : row.available ? 'Disponibile sul portale: acquisisci il file prima di usarlo.' : 'Documento censito dal portale ma non scaricabile in questa sessione.'}</small>
                </article>
              ))}
              {!portalCatalog.length ? <p className="iu-empty">Nessun documento acquisito dal portale per questo fascicolo.</p> : null}
            </div>
          </DetailSection>

          <DetailSection id="ricevute-deposito" title="Ricevute e cancelleria" icon={<Mail size={17}/>} count={recentDeposits.length}>
            <p className="iu-fas-sync-note"><RefreshCw size={14}/> Le ricevute PEC e le comunicazioni di cancelleria aggiornano il deposito dal presidio operativo del fascicolo.</p>
            <div className="iu-fas-comm-list">
              {communicationDocuments.map((doc) => (
                <article className="iu-fas-comm-row" key={`doc-comm-${doc.id}`}>
                  <Badge tone={doc.statusTone}>{doc.portalClass || doc.type || 'Comunicazione'}</Badge>
                  <strong>{doc.name}</strong>
                  <span>{[doc.source, doc.portalDate || doc.documentDate || doc.uploadedAt, doc.portalSender].filter(Boolean).join(' - ')}</span>
                  <small>Documento classificato come comunicazione o ricevuta: resta fuori dai candidati della busta.</small>
                </article>
              ))}
              {recentDeposits.map((dep) => (
                <article className="iu-fas-comm-row" key={dep.id}>
                  <Badge tone={dep.tone}>{depositStatusLabel(dep.status)}</Badge>
                  <strong>{dep.message || dep.actType || 'Comunicazione deposito'}</strong>
                  <span>{depositMetaLine(dep)}</span>
                  <DepositStateSummary dep={dep}/>
                  <DepositReceiptSteps dep={dep}/>
                  <DepositReceiptActions dep={dep} onDone={refreshDetail} onError={failDetail}/>
                </article>
              ))}
              {!recentDeposits.length && !communicationDocuments.length ? <p className="iu-empty">Nessuna ricevuta collegata al deposito.</p> : null}
            </div>
          </DetailSection>
        </div>
        <aside className="iu-fas-detail-side">
          <DetailSection id="dati-fascicolo-deposito" title="Dati fascicolo" icon={<BadgeCheck size={17}/>}>
            <KvGrid items={[
              { label: 'Fascicolo', value: f.ref || f.id, href: detailHref },
              { label: 'Cliente', value: f.client },
              { label: 'Ufficio', value: f.court },
              { label: 'RG', value: visibleRg, mono: true },
              { label: 'Tipo deposito', value: f.codiceOggettoPst || 'n.d.' },
              { label: 'Canale', value: regia.header.channel || 'da verificare' },
            ]}/>
          </DetailSection>
          <DetailSection id="slot-deposito-rail" title="Documenti richiesti" icon={<PackageCheck size={17}/>} count={sortedSlots.length}>
            <div className="iu-fas-regia-list">
              {sortedSlots.map((slot) => {
                const slotKey = recordText(slot, 'slotKey')
                const linkedDocument = documentsById.get(recordText(slot, 'documentId'))
                const slotText = normaliseText(`${slotKey} ${recordText(slot, 'label')} ${recordText(slot, 'type')}`)
                const isContribution = /contributo/.test(slotText)
                const isAnagrafica = /anagrafica/.test(slotText)
                const isCaseValue = /valore causa/.test(slotText)
                const isAttachments = /allegati/.test(slotText)
                const selectionSatisfied = depositSelectionSatisfiesSlot(slot, packageDocuments, mainActDocument, effectiveDepositClassificationById)
                let slotStatus = slotStatusDisplay(recordText(slot, 'status'), selectionSatisfied)
                let slotMessage = linkedDocument
                  ? `Documento collegato: ${linkedDocument.name}`
                  : depositUserFacingMessage(recordText(slot, 'message', recordText(slot, 'catalogRequirementKind') === 'data' ? 'Dato deposito da verificare.' : 'Documento da collegare'))
                let slotNote = depositUserFacingMessage(recordText(slot, 'suggestedAction') || (linkedDocument ? 'La scelta salvata dall’avvocato determina se entra nella busta.' : 'Seleziona il documento corretto dal fascicolo.'))
                if (isContribution) {
                  const state = data.depositReadiness.contributoUnificato
                  slotStatus = { label: state.ready ? state.label : 'Da definire', tone: state.ready ? 'success' : 'warning' }
                  slotMessage = [state.message, state.amountLabel].filter(Boolean).join(' ')
                  slotNote = state.source ? `Documento di riferimento: ${state.source}` : state.ready ? 'Nessuna azione richiesta.' : 'Completa qui il solo dato necessario.'
                } else if (isAnagrafica) {
                  const state = data.depositReadiness.anagraficaProcedimento
                  slotStatus = { label: state.ready ? 'Pronta' : 'Da completare', tone: state.ready ? 'success' : 'warning' }
                  slotMessage = state.message
                  slotNote = state.missing.length ? `Mancano: ${state.missing.join(', ')}.` : 'Nessuna azione richiesta.'
                } else if (isCaseValue) {
                  const state = data.depositReadiness.valoreCausa
                  slotStatus = { label: state.ready ? 'Pronto' : 'Da inserire', tone: state.ready ? 'success' : 'warning' }
                  slotMessage = state.ready ? `Valore della causa: ${state.valueLabel}` : state.message
                  slotNote = state.ready ? 'Dato già acquisito dal fascicolo.' : 'Inserisci il valore senza uscire dal deposito.'
                } else if (isAttachments) {
                  slotStatus = { label: selectedAttachmentIds.length ? `${selectedAttachmentIds.length} scelti` : 'Facoltativi', tone: selectedAttachmentIds.length ? 'success' : 'neutral' }
                  slotMessage = selectedAttachmentIds.length ? 'Gli allegati scelti dall’avvocato saranno inclusi nella busta.' : 'Nessun allegato aggiuntivo scelto.'
                  slotNote = 'Gli allegati entrano nella busta solo quando l’avvocato li seleziona.'
                }
                const catalogOnly = recordBool(slot, 'catalogOnly')
                const canLinkSlot = Boolean(slotKey && !catalogOnly && !isContribution && !isAnagrafica && !isCaseValue && !isAttachments)
                return (
                  <article className="iu-fas-slot-row" key={`${selectedDepositType?.key || 'regia'}-${slotKey || recordText(slot, 'label')}`}>
                    <Badge tone={slotStatus.tone}>{slotStatus.label}</Badge>
                    <strong>{recordText(slot, 'label')}</strong>
                    <span>{slotMessage}</span>
                    <small>{slotNote}</small>
                    {isContribution && !data.depositReadiness.contributoUnificato.ready ? (
                      <ContributionRequirementForm action={f.paymentSummary.items.contributo_unificato.updateAction} onDone={refreshDetail} onError={failDetail}/>
                    ) : null}
                    {isAnagrafica && !data.depositReadiness.anagraficaProcedimento.ready ? (
                      <div className="iu-fas-slot-actions">
                        <a className="iu-fas-side-link" href={f.operationalEditHref || detailHref}><Edit3 size={14}/> Completa dati fascicolo</a>
                        {data.depositReadiness.anagraficaProcedimento.missing.some((item) => normaliseText(item).includes('avvocato')) ? <a className="iu-fas-side-link" href="/impostazioni?tab=studio"><Edit3 size={14}/> Completa dati avvocato</a> : null}
                      </div>
                    ) : null}
                    {isCaseValue && !data.depositReadiness.valoreCausa.ready ? (
                      <CaseValueRequirementForm action={`/api/v1/ui/fascicoli/${encodedId}/deposito/valore-causa`} defaultValue={f.valueRaw} onDone={refreshDetail} onError={failDetail}/>
                    ) : null}
                    {isAttachments ? <a className="iu-fas-side-link iu-fas-slot-choice-link" href="#proposta-busta" onClick={openDepositPhase('#proposta-busta')}><PackageCheck size={14}/> Scegli documenti</a> : null}
                    {canLinkSlot ? (
                      <JsonPostForm className="iu-fas-slot-link-form" action={`/api/v1/ui/fascicoli/${encodedId}/document-slots/${encodeURIComponent(slotKey)}/link`} onDone={refreshDetail} onError={failDetail}>
                        <select name="document_id" defaultValue={linkedDocument?.id || ''} required>
                          <option value="">Scegli documento</option>
                          {data.documents.map((doc) => <option key={`${slotKey}-${doc.id}`} value={doc.id}>{doc.name} - {packageDocumentSignatureLabel(doc)}</option>)}
                        </select>
                        <button type="submit"><Save size={14}/> Collega</button>
                      </JsonPostForm>
                    ) : null}
                  </article>
                )
              })}
              {!sortedSlots.length ? <p className="iu-empty">Documenti richiesti non ancora disponibili: aggiorna la Regia dopo aver classificato i documenti.</p> : null}
            </div>
          </DetailSection>
          <DetailSection id="audit-deposito" title="Audit" icon={<Fingerprint size={17}/>} count={data.auditTrail.summary.total}>
            <div className="iu-fas-action-stack">
              {evidenceHref ? <a className="iu-fas-side-link" href={evidenceHref}><FileArchive size={15}/> Scarica evidence pack</a> : null}
              {data.actions.auditBundle ? <a className="iu-fas-side-link" href={data.actions.auditBundle}><PackageCheck size={15}/> Bundle audit</a> : null}
              {!evidenceHref && !data.actions.auditBundle ? <p className="iu-empty">Nessun pacchetto audit disponibile per questo fascicolo.</p> : null}
            </div>
          </DetailSection>
        </aside>
      </section>
      <PdfPreviewModal preview={previewDoc} onClose={() => setPreviewDoc(null)}/>
      <FloatingLex context="deposito-fascicolo" title="Lex AI deposito" body="Posso aiutarti a leggere i controlli, ordinare gli allegati e preparare una checklist prima dell'invio." primaryHref="#verifica-deposito" primaryLabel="Controlli deposito" secondaryHref={detailHref} secondaryLabel="Torna al fascicolo" />
    </main>
  )
}

function DepositBatchSignaturePanel({
  fascicoloId,
  documents,
  signature,
  registerAction,
  onDone,
  onError,
}: {
  fascicoloId: string
  documents: FascicoloDocument[]
  signature: FascicoloDetailData['signature']
  registerAction?: (action: BatchSignatureAction | null) => void
  onDone: (message?: string) => void
  onError: (message: string) => void
}) {
  const [localSigner, setLocalSigner] = useState<LocalSignerStatus | null>(null)
  const [checkingSigner, setCheckingSigner] = useState(false)
  const [pin, setPin] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [visibleSignatureMode, setVisibleSignatureMode] = useState<VisibleSignatureMode>('laterale')
  const [visibleSignaturePlace, setVisibleSignaturePlace] = useState('')
  const [visibleSignatureDatetimeMode, setVisibleSignatureDatetimeMode] = useState<VisibleSignatureDatetimeMode>('data_ora')
  const pinInputRef = useRef<HTMLInputElement | null>(null)

  const primaryToken = localSigner?.token?.[0]
  const freshToken = localSigner?.token_probe_fresh?.[0]
  const selectedWindowsCertificate = localSignerWindowsCertificate(localSigner)
  const restartSuggested = localSignerNeedsRestart(localSigner)
  const displayToken = primaryToken || (restartSuggested ? freshToken : selectedWindowsCertificate ? undefined : freshToken)
  const signerRestartRequired = Boolean(restartSuggested && freshToken && !primaryToken)
  const localSignerReachable = Boolean(localSigner && localSigner.ok !== false && (localSigner.versione || localSigner.version || localSigner.piattaforma || localSigner.token || localSigner.token_probe_fresh || selectedWindowsCertificate))
  const localSignerOutdated = localSignerStatusOutdated(localSigner)
  const localSignerCanSign = localSignerStatusCanSign(localSigner)
  const localSignerVersion = localSigner?.versione || localSigner?.version || ''
  const signableDocuments = documents.filter((doc) => !doc.signed && requiresPackageSignature(doc))

  useEffect(() => {
    setVisibleSignatureMode(loadVisibleSignatureMode(signature?.visibleSignatureMode || 'laterale'))
    setVisibleSignaturePlace(signature?.visibleSignaturePlace || '')
    setVisibleSignatureDatetimeMode(loadVisibleSignatureDatetimeMode(signature?.visibleSignatureDatetimeMode || 'data_ora'))
  }, [signature?.visibleSignatureMode, signature?.visibleSignaturePlace, signature?.visibleSignatureDatetimeMode])

  const checkLocalSigner = async (tryStart = false): Promise<LocalSignerStatus | null> => {
    setCheckingSigner(true)
    setError('')
    if (tryStart) {
      setMessage('IUSENTRA sta avviando e verificando automaticamente Local Signer su questo PC.')
      requestLocalSignerStart()
    }
    const attempts = tryStart ? 10 : 1
    try {
      for (let attempt = 0; attempt < attempts; attempt += 1) {
        if (attempt > 0) await sleep(900)
        const payload = await fetchLocalSignerStatus()
        if (payload) {
          const next = await recoverLocalSignerAutomatically(payload, { onMessage: setMessage })
          setLocalSigner(next)
          if (localSignerStatusCanSign(next)) setMessage('')
          return next
        } else {
          if (attempt === attempts - 1) setLocalSigner({ ok: false, messaggio: 'Local Signer non rilevato su questo PC.' })
        }
      }
      return null
    } finally {
      setCheckingSigner(false)
    }
  }

  useEffect(() => {
    if (signableDocuments.length) void checkLocalSigner(false)
  }, [signableDocuments.length])

  const scheduleLocalSignerRestartCheck = () => {
    setError('')
    setMessage('IUSENTRA sta riallineando automaticamente Local Signer e ricontrolla il dispositivo di firma.')
    requestLocalSignerStart()
    for (const delay of [2500, 5000, 8500, 12000]) {
      window.setTimeout(() => { void checkLocalSigner(false) }, delay)
    }
  }

  const uploadSignedDocument = async (doc: FascicoloDocument, signedB64: string): Promise<void> => {
    const signedBytes = base64ToUint8Array(signedB64)
    if (!signedBytes.length) throw new Error(`${doc.name}: Local Signer non ha restituito il file firmato.`)
    const signedBuffer = new Uint8Array(signedBytes).buffer.slice(0)
    const signedName = doc.name.toLowerCase().endsWith('.p7m') ? doc.name : `${doc.name}.p7m`
    const form = new FormData()
    form.append('file', new File([signedBuffer], signedName, { type: 'application/pkcs7-mime' }))
    form.append('note', 'Versione firmata tramite firma multipla deposito')
    form.append('visible_signature_mode', visibleSignatureMode)
    form.append('visible_signature_place', visibleSignaturePlace)
    form.append('visible_signature_datetime_mode', visibleSignatureDatetimeMode)
    const action = doc.actions.sign || `/fascicoli/${encodeURIComponent(fascicoloId)}/documenti/${encodeURIComponent(doc.id)}/firma`
    const uploadResponse = await fetch(action, {
      method: 'POST',
      body: form,
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
    const uploadPayload = await uploadResponse.json().catch(() => ({} as ActionPayload))
    if (!uploadResponse.ok || uploadPayload.ok === false) {
      throw new Error(`${doc.name}: ${String(uploadPayload.messaggio || uploadPayload.errore || `salvataggio firma non riuscito HTTP ${uploadResponse.status}`)}`)
    }
  }

  const signAll = async () => {
    const targetDocuments = documents.filter((doc) => !doc.signed && requiresPackageSignature(doc))
    if (!targetDocuments.length) {
      const message = 'Nessun documento da firmare: tutti i documenti selezionati hanno già una firma digitale verificata.'
      setMessage(message)
      onDone(message)
      return undefined
    }
    if (restartSuggested || localSignerOutdated) {
      const next = await checkLocalSigner(true)
      if (!localSignerStatusCanSign(next)) {
      const message = 'IUSENTRA ha tentato il riallineamento automatico del Local Signer. Se il dispositivo è inserito, attendi pochi secondi: il PIN verrà chiesto solo quando la firma sarà pronta.'
        setError(message)
        throw signatureInputRequired(message)
      }
      const message = 'Local Signer è pronto: inserisci il PIN e ripeti il comando di firma prima di generare la busta.'
      setError(message)
      pinInputRef.current?.focus()
      throw signatureInputRequired(message)
    }
    if (!localSignerCanSign) {
      const next = await checkLocalSigner(true)
      if (!localSignerStatusCanSign(next)) {
        const message = localSignerReachable ? 'Dispositivo non pronto per la firma: verifica che il dispositivo fisico sia inserito. IUSENTRA ha già tentato avvio e aggiornamento del Local Signer.' : 'Local Signer non raggiungibile su questo PC: IUSENTRA ha tentato l’avvio automatico e riproverà la verifica.'
        setError(message)
        throw signatureInputRequired(message)
      }
      const message = 'Local Signer è pronto: inserisci il PIN e ripeti il comando di firma prima di generare la busta.'
      setError(message)
      pinInputRef.current?.focus()
      throw signatureInputRequired(message)
    }
    if (!selectedWindowsCertificate && !primaryToken?.slot_id && primaryToken?.slot_id !== 0) {
      const message = 'Local Signer non ha restituito un dispositivo di firma utilizzabile.'
      setError(message)
      throw signatureInputRequired(message)
    }
    if (!pin.trim()) {
      const message = 'Inserisci il PIN nel pannello Local Signer. Il PIN resta sul PC e non viene salvato.'
      setError(message)
      pinInputRef.current?.focus()
      throw signatureInputRequired(message)
    }
    setBusy(true)
    setError('')
    setMessage('Firma multipla in corso...')
    try {
      const documenti = await Promise.all(targetDocuments.map(async (doc) => {
        if (!doc.actions.download) throw new Error(`${doc.name}: download non disponibile.`)
        const response = await fetch(doc.actions.download, { credentials: 'same-origin' })
        if (!response.ok) throw new Error(`${doc.name}: download non riuscito HTTP ${response.status}.`)
        return {
          documento: arrayBufferToBase64(await response.arrayBuffer()),
          nome: doc.name,
        }
      }))
      const controller = new AbortController()
      const timeout = window.setTimeout(() => controller.abort(), LOCAL_SIGNER_BATCH_TIMEOUT_MS)
      let signResponse: Response
      try {
        const requestOptions: LocalNetworkRequestInit = {
          method: 'POST',
          mode: 'cors',
          targetAddressSpace: 'local',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify({
            documenti,
            pin: pin.trim(),
            slot_id: primaryToken?.slot_id,
            cert_thumbprint: selectedWindowsCertificate?.thumbprint,
            visible_signature_mode: visibleSignatureMode,
            visible_signature_place: visibleSignaturePlace,
            visible_signature_datetime_mode: visibleSignatureDatetimeMode,
          }),
        }
        signResponse = await fetch(localSignerEndpointForStatus('/firma-batch', localSigner), requestOptions)
      } catch (exc) {
        if (exc instanceof DOMException && exc.name === 'AbortError') {
          throw new Error('Local Signer non ha risposto entro 45 secondi. Verifica dispositivo di firma, PIN e servizio locale, poi ripeti la firma.')
        }
        throw exc
      } finally {
        window.clearTimeout(timeout)
      }
      const payload = await parseLocalSignerResponse(signResponse)
      const pinSessionId = recordText(payload, 'pin_session_id')
      const pinSessionTtlSeconds = recordNumber(payload, 'pin_session_ttl_seconds', 0)
      const risultati = Array.isArray(payload.risultati) ? payload.risultati as Array<Record<string, unknown>> : []
      if (!risultati.length) {
        throw new Error(String(payload.errore || payload.messaggio || `Firma multipla non riuscita: HTTP ${signResponse.status}`))
      }
      const errors: string[] = []
      let saved = 0
      for (let index = 0; index < targetDocuments.length; index += 1) {
        const doc = targetDocuments[index]
        const result = risultati.find((item) => Number(item.indice) === index) || risultati[index]
        if (!result || result.ok === false || !result.firmato_b64) {
          errors.push(`${doc.name}: ${String(result?.errore || result?.messaggio || 'firma non completata')}`)
          continue
        }
        try {
          await uploadSignedDocument(doc, String(result.firmato_b64))
          saved += 1
        } catch (exc) {
          errors.push(exc instanceof Error ? exc.message : String(exc))
        }
      }
      setPin('')
      if (errors.length) {
        const prefix = saved ? `${saved} documenti firmati e salvati. ` : ''
        throw new Error(`${prefix}Firma multipla da completare: ${errors.join(' ')}`)
      }
      setMessage(`Firma multipla completata: ${saved} documenti firmati e salvati nel fascicolo.`)
      onDone(`Firma multipla completata: ${saved} documenti firmati e salvati nel fascicolo.`)
      return {
        pinSessionId: pinSessionId || undefined,
        pinSessionTtlSeconds: pinSessionTtlSeconds || undefined,
      }
    } catch (exc) {
      const msg = exc instanceof Error ? exc.message : String(exc)
      setError(msg)
      setMessage('')
      onError(msg)
      throw exc
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    registerAction?.(signableDocuments.length ? signAll : null)
    return () => registerAction?.(null)
  }, [signableDocuments.length, pin, localSignerCanSign, restartSuggested, localSignerReachable, primaryToken?.slot_id, visibleSignatureMode, visibleSignaturePlace, visibleSignatureDatetimeMode])

  if (!documents.length) return null

  const signerTitle = restartSuggested
    ? 'Dispositivo di firma rilevato, riallineamento automatico'
    : selectedWindowsCertificate
    ? 'Local Signer pronto con certificato Windows'
    : displayToken
    ? (localSignerOutdated ? 'Local Signer da aggiornare' : 'Local Signer pronto')
    : localSignerReachable
      ? (localSignerOutdated ? 'Local Signer da aggiornare' : 'Local Signer attivo senza dispositivo di firma')
      : checkingSigner
        ? 'Verifica Local Signer...'
        : 'Local Signer non rilevato'
  const signerDetail = restartSuggested
    ? localSigner?.nota_riavvio_signer || 'Il dispositivo di firma è stato rilevato, IUSENTRA sta riallineando Local Signer prima della firma.'
    : selectedWindowsCertificate
    ? `${localSignerWindowsCertificateLabel(selectedWindowsCertificate)}${selectedWindowsCertificate.scadenza ? ` - scadenza ${selectedWindowsCertificate.scadenza}` : ''}`
    : displayToken
    ? (localSignerOutdated
        ? `Versione rilevata ${localSignerVersion || 'non disponibile'}: IUSENTRA avvia l'aggiornamento automatico prima della firma.`
        : restartSuggested
        ? localSigner?.nota_riavvio_signer || 'Il dispositivo di firma è stato rilevato, IUSENTRA sta riallineando Local Signer prima della firma.'
        : `${localSignerTokenLabel(displayToken)} - lettore ${displayToken.slot_id}`)
    : localSignerReachable
      ? localSigner?.errore_token || localSigner?.errore_libreria || localSigner?.messaggio || 'Servizio locale attivo, ma nessun dispositivo di firma disponibile.'
      : localSigner?.messaggio || localSigner?.error || 'Usa Riallinea automaticamente per avviare il Local Signer dal PC in uso.'

  return (
    <section className="iu-fas-batch-signature">
      <div className={`iu-fas-signer-status ${localSignerCanSign ? 'is-ok' : 'is-warn'}`}>
        <strong>{signerTitle}</strong>
        <span>{depositUserFacingMessage(signerDetail)}</span>
        {displayToken && restartSuggested ? <small>{localSignerTokenLabel(displayToken)} - lettore {displayToken.slot_id}</small> : null}
        {selectedWindowsCertificate?.codice_fiscale && !restartSuggested ? <small>Codice fiscale certificato {selectedWindowsCertificate.codice_fiscale}</small> : null}
        {localSignerVersion ? <small>Versione {localSignerVersion}</small> : null}
      </div>
      {restartSuggested || localSignerOutdated || !localSignerReachable ? (
        <div className="iu-fas-signer-actions">
          <a className="iu-fas-mini-action iu-fas-mini-action--restart" href={LOCAL_SIGNER_RESTART_URI} onClick={scheduleLocalSignerRestartCheck}>
            <RefreshCw size={14}/> Riallinea automaticamente
          </a>
          <button className="iu-fas-mini-action" type="button" onClick={() => checkLocalSigner(false)} disabled={checkingSigner}>
            <RefreshCw size={14}/> Riverifica
          </button>
          {localSignerReachable ? <a className="iu-fas-mini-action" href={localSignerEndpoint('/diagnosi')} target="_blank" rel="noreferrer">Diagnosi locale</a> : null}
        </div>
      ) : null}
      {localSignerCanSign ? (
        <>
          <div className="iu-fas-batch-signature__controls">
            <label>
              <span>PIN firma</span>
              <input
                ref={pinInputRef}
                type="password"
                value={pin}
                onChange={(event) => {
                  setPin(event.target.value)
                  if (error) setError('')
                }}
                autoComplete="off"
                placeholder="PIN dispositivo"
              />
            </label>
            <label>
              <span>Luogo firma</span>
              <input value={visibleSignaturePlace} onChange={(event) => setVisibleSignaturePlace(event.target.value)} placeholder="Comune"/>
            </label>
            <label>
              <span>Posizione firma</span>
              <select value={visibleSignatureMode} onChange={(event) => setVisibleSignatureMode(normalizeVisibleSignatureMode(event.target.value))}>
                {visibleSignatureOptions.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
              </select>
            </label>
            <label>
              <span>Data firma</span>
              <select value={visibleSignatureDatetimeMode} onChange={(event) => setVisibleSignatureDatetimeMode(normalizeVisibleSignatureDatetimeMode(event.target.value))}>
                {visibleSignatureDatetimeOptions.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
              </select>
            </label>
          </div>
          <div className="iu-fas-batch-signature__actions">
            <button className="iu-fas-submit" type="button" onClick={() => { void signAll().catch(() => undefined) }} disabled={busy}>
              <ShieldCheck size={16}/> {busy ? 'Firma multipla...' : `Firma ${documents.length} documenti`}
            </button>
            <button className="iu-fas-mini-action" type="button" onClick={() => checkLocalSigner(false)} disabled={checkingSigner}><RefreshCw size={14}/> Riverifica</button>
          </div>
          <p className="iu-fas-signature-help">Il PIN viene inviato solo al Local Signer su questo PC. Il software firma il lotto, salva ogni documento firmato nel fascicolo e poi aggiorna la proposta busta.</p>
        </>
      ) : (
        <div className="iu-fas-signer-next-step">
          <strong>{restartSuggested || localSignerOutdated ? 'Riallineamento automatico in corso.' : 'Dispositivo non pronto per la firma.'}</strong>
          <span>{restartSuggested || localSignerOutdated ? 'IUSENTRA aggiorna o riapre il servizio locale e ricontrolla il dispositivo prima di firmare il lotto.' : 'Inserisci il dispositivo di firma: IUSENTRA gestisce avvio e aggiornamento del Local Signer.'}</span>
        </div>
      )}
      {message ? <div className="iu-fas-signature-alert iu-fas-signature-alert--ok" role="status"><CheckCircle2 size={16}/><span>{message}</span></div> : null}
      {error ? <div className="iu-fas-signature-alert iu-fas-signature-alert--error" role="alert"><AlertTriangle size={16}/><span>{error}</span></div> : null}
    </section>
  )
}

type DocumentAutoSection = {
  id: string
  title: string
  note: string
  tone: FascicoloRow['tone']
  documents: FascicoloDocument[]
}

type PortalCatalogRow = {
  id: string
  name: string
  type: string
  role: string
  date: string
  sender: string
  source: string
  imported: boolean
  available: boolean
  tone: FascicoloRow['tone']
}

const documentAutoSectionOrder: Array<Omit<DocumentAutoSection, 'documents'>> = [
  { id: 'atti', title: 'Atti e memorie', note: 'Atto principale, difese e bozze redazionali.', tone: 'primary' },
  { id: 'provvedimenti', title: 'Provvedimenti', note: 'Sentenze, ordinanze, decreti e verbali.', tone: 'purple' },
  { id: 'comunicazioni', title: 'Comunicazioni', note: 'PEC, cancelleria, notifiche e messaggi collegati.', tone: 'info' },
  { id: 'pagamenti', title: 'Pagamenti e contributi', note: 'Contributo unificato, PagoPA, bolli, parcelle e note spese.', tone: 'success' },
  { id: 'allegati', title: 'Allegati e supporti', note: 'Procure, contratti, parcelle e allegati di fascicolo.', tone: 'neutral' },
  { id: 'da-verificare', title: 'Da verificare', note: 'Documenti senza sezione certa da controllare.', tone: 'warning' },
]

function documentSearchText(doc: FascicoloDocument): string {
  return normaliseText([doc.type, doc.rawType, doc.name, doc.source, doc.portalClass, doc.portalName, doc.portalSender, doc.statusLabel, doc.catalogRole, doc.catalogLabel, doc.catalogSection, doc.catalogEvidence, doc.depositRole, ...doc.tags].join(' '))
}

function uniqueFascicoloDocuments(documents: FascicoloDocument[]): FascicoloDocument[] {
  const seen = new Set<string>()
  return documents.filter((doc) => {
    if (!doc.id || seen.has(doc.id)) return false
    seen.add(doc.id)
    return true
  })
}

function visibleDocumentTags(doc: FascicoloDocument): string[] {
  const seen = new Set<string>()
  return doc.tags
    .map((tag) => tag.trim())
    .filter((tag) => {
      const key = normaliseText(tag)
      if (!key || /(quickorganizer|import_esterno|backend|frontend|payload|runtime|legacy)/.test(key)) return false
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
}

function isPortalAcquiredDocument(doc: FascicoloDocument): boolean {
  const text = documentSearchText(doc)
  return Boolean(doc.portalClass || doc.portalName || doc.portalDate || doc.portalSender || /portale|polisweb|pst|pdp|pat|ptt|sigit|telematico/.test(text))
}

function isCommunicationDocument(doc: FascicoloDocument): boolean {
  if (doc.catalogRole === 'comunicazione') return true
  if (doc.catalogSection === 'comunicazioni' && !['prova_notifica', 'relata'].includes(doc.catalogRole)) return true
  return /(pec|cancelleria|comunicazion|notifica|relata|busta|rdac|rac|esito|ricevut|accettazion|consegna)/.test(documentSearchText(doc))
}

type NotificationProofKind = 'atto_notificato' | 'relata' | 'pec' | 'rac' | 'rdac' | 'attestazione' | ''

function notificationProofKind(doc: FascicoloDocument): NotificationProofKind {
  const text = documentSearchText(doc)
  const notificationContext = /(notifica|notificaz|originale notificato|legge n\.?\s*53|l\.?\s*53|notifica[_\s-]*id)/.test(text)
  if (notificationContext && /relata/.test(text)) return 'relata'
  if (/originale notificato/.test(text) && /(ricorso|citazione|comparsa|memoria|istanza|atto|decreto)/.test(text)) return 'atto_notificato'
  if (notificationContext && /(accettazione|rac)/.test(text)) return 'rac'
  if (notificationContext && /(consegna|rdac|avvenuta consegna)/.test(text)) return 'rdac'
  if (notificationContext && /(pec inviata|postacert|messaggio pec|\.eml)/.test(text)) return 'pec'
  if (notificationContext && /attestazione di conform/.test(text)) return 'attestazione'
  return ''
}

function isNotificationProofDocument(doc: FascicoloDocument): boolean {
  return Boolean(notificationProofKind(doc))
}

function isNotificationCommunicationDocument(doc: FascicoloDocument): boolean {
  return ['atto_notificato', 'pec', 'rac', 'rdac', 'attestazione'].includes(notificationProofKind(doc))
}

function notificationProofLabel(doc: FascicoloDocument): string {
  const kind = notificationProofKind(doc)
  if (kind === 'atto_notificato') return 'Atto notificato'
  if (kind === 'relata') return 'Relata'
  if (kind === 'pec') return 'PEC inviata'
  if (kind === 'rac') return 'RAC'
  if (kind === 'rdac') return 'RdAC'
  if (kind === 'attestazione') return 'Attestazione'
  return 'Prova notifica'
}

function notificationCommunicationDetail(doc: FascicoloDocument): string {
  const kind = notificationProofKind(doc)
  if (kind === 'atto_notificato') return 'Documento originale notificato: deve provenire dal Portale Servizi, non dall’allegato PEC d’ufficio.'
  if (kind === 'rac') return 'Ricevuta di accettazione della notifica PEC conservata nel fascicolo.'
  if (kind === 'rdac') return 'Ricevuta di avvenuta consegna della notifica PEC conservata nel fascicolo.'
  if (kind === 'pec') return 'Messaggio PEC di invio notifica collegato al documento notificato.'
  if (kind === 'attestazione') return 'Attestazione di conformità collegata alla notifica.'
  return 'Prova di notifica conservata nel fascicolo.'
}

function depositIssueLabel(row: { label?: string; message?: string; note?: string }): string {
  const text = normaliseText(`${row.label || ''} ${row.message || ''}`)
  if (/atto principale/.test(text)) return 'Atto principale'
  if (/codice oggetto|catalogo/.test(text)) return 'Codice deposito'
  if (/ufficio|registro|rg/.test(text)) return 'Dati fascicolo'
  if (/pdf\/?a/.test(text)) return 'Formato atto'
  if (/file|slot|documento non collegato|documento vuoto/.test(text)) return 'Documento busta'
  if (/hash|datiatto|xml|schema|busta|indice/.test(text)) return 'Pacchetto'
  if (/firm|firma|pin|token/.test(text)) return 'Firma'
  if (/preventivo|conferimento|pagamento|acconto|fattura/.test(text)) return 'Informazione studio'
  return row.label || 'Controllo'
}

function depositIssueMessage(row: { message?: string; note?: string; label?: string }): string {
  const text = normaliseText(`${row.message || ''} ${row.note || ''} ${row.label || ''}`)
  if (/hash documento assente|calcolare l'?hash|calcol.*hash/.test(text)) return 'Ricalcola l’impronta del documento prima della generazione.'
  if (/file non collegato|documento non collegato|collega il documento/.test(text)) return 'Collega il documento richiesto alla busta.'
  if (/file non apribile|ricarica il documento|correggi il collegamento/.test(text)) return 'Ricarica il documento oppure correggi il collegamento.'
  if (/documento vuoto|file valido/.test(text)) return 'Ricarica un file valido.'
  return depositUserFacingMessage(row.message || row.note || row.label || 'Controllo registrato')
}

function isDecisiveDepositIssue(row: { tone?: string; label?: string; message?: string; note?: string }): boolean {
  if (row.tone !== 'danger') return false
  const text = normaliseText(`${row.label || ''} ${row.message || ''} ${row.note || ''}`)
  if (/firm|firma|pin|token|certificat/.test(text)) return false
  if (/preventivo|conferimento|pagamento|acconto|fattura|onorari|cliente|avvocato referente|recapito|email|controparte/.test(text)) return false
  return /(atto principale|codice oggetto|catalogo ufficiale|ufficio|registro|rg|documento selezionato|file|percorso|hash|datiatto|xml|schema|busta|indice|pdf\/?a|dimensione|slot|obbligator)/.test(text)
}

function requiresPackageSignature(doc: FascicoloDocument): boolean {
  const proofKind = notificationProofKind(doc)
  if (proofKind && proofKind !== 'relata') return false
  return !doc.signed
}

function documentHasSignedContainerExtension(doc: FascicoloDocument | undefined): boolean {
  return Boolean(doc?.name && /\.(p7m|sig|pkcs7)$/i.test(doc.name.trim()))
}

function documentExplicitlyRequiresSignature(doc: FascicoloDocument | undefined): boolean {
  if (!doc) return false
  const text = normaliseText(`${doc.name} ${doc.type} ${doc.tags.join(' ')}`)
  if (documentHasSignedContainerExtension(doc)) return false
  return /(firma richiesta|firma obbligatoria|firmare obbligatoriamente|sottoscrizione obbligatoria|da sottoscrivere)/.test(text)
}

function packageDocumentSignatureLabel(doc: FascicoloDocument): string {
  if (doc.signed) return 'Firmato'
  if (documentExplicitlyRequiresSignature(doc)) return 'Da firmare'
  return 'Firma non necessaria'
}

function defaultSignatureRequiredForDepositRole(doc: FascicoloDocument | undefined, role: DepositDocumentRole): boolean {
  if (!doc || doc.signed || !requiresPackageSignature(doc)) return false
  return role === 'atto_principale' || role === 'procura' || documentExplicitlyRequiresSignature(doc)
}

function buildDepositPecBody(documenti: string[]): string {
  const files = documenti.map((item) => item.trim()).filter(Boolean)
  const elenco = files.length
    ? `\n\nIl pacchetto contiene i seguenti documenti:\n${files.map((name) => `- ${name}`).join('\n')}`
    : ''
  return [
    'Egregio sig. Cancelliere,',
    '',
    `Allego alla presente il pacchetto di deposito telematico.${elenco}`,
    '',
    '',
  ].join('\n')
}

function portalCatalogRole(value: string): { label: string; tone: FascicoloRow['tone']; depositCandidate: boolean } {
  const text = normaliseText(value)
  if (/(sentenza|ordinanza|decreto|provvediment|verbale)/.test(text)) return { label: 'Provvedimento', tone: 'purple', depositCandidate: false }
  if (/(ricevut|accettazion|consegna|rdac|rac|esito|cancelleria|pec|comunicazion)/.test(text)) return { label: 'Ricevuta / cancelleria', tone: 'info', depositCandidate: false }
  if (/(atto principale|\batto\b|\bricorso\b|\bcitazione\b|\bcomparsa\b|\bmemoria\b|\bistanza\b|deduzion|conclusionale)/.test(text)) return { label: 'Atto', tone: 'primary', depositCandidate: true }
  if (/(allegato|procura|documento|contratto|quietanza)/.test(text)) return { label: 'Allegato', tone: 'neutral', depositCandidate: true }
  return { label: 'Da classificare', tone: 'warning', depositCandidate: false }
}

function isDepositCandidateDocument(doc: FascicoloDocument): boolean {
  if (['atto_principale', 'atto_difensivo', 'procura', 'prova_notifica', 'relata', 'contributo_unificato', 'nota_iscrizione_ruolo', 'provvedimento', 'allegato'].includes(doc.catalogRole)) {
    return doc.depositCandidate !== false
  }
  if (doc.depositCandidate !== undefined) return doc.depositCandidate
  if (isCommunicationDocument(doc)) return false
  if (!isPortalAcquiredDocument(doc)) return true
  return portalCatalogRole(`${doc.portalClass} ${doc.type} ${doc.name}`).depositCandidate
}

function isDepositManualSelectableDocument(doc: FascicoloDocument): boolean {
  if (doc.catalogRole === 'comunicazione' || doc.depositRole === 'fuori_busta') return false
  if (isCommunicationDocument(doc)) return false
  return true
}

function isMainActCandidateDocument(doc: FascicoloDocument): boolean {
  if (doc.catalogRole === 'atto_principale') return true
  if (doc.catalogRole === 'atto_difensivo' && doc.catalogConfidence >= 80) return true
  if (doc.catalogConfidence >= 70 && ['allegato', 'classificato_storico', 'comunicazione', 'contributo_unificato', 'economia_fascicolo', 'nota_iscrizione_ruolo', 'procura', 'prova_notifica', 'provvedimento', 'relata'].includes(doc.catalogRole)) return false
  const text = documentSearchText(doc)
  if (/(procura|contratto|contributo|pagopa|marca|nota iscrizione|nir|ricevut|accettazion|consegna|rdac|rac|relata|pec|notifica_id|perizia|ctu|ctp|perital|verbale|sentenza|ordinanza|decreto|provvediment|liquidazione)/.test(text)) return false
  return /(\batto\b|\bricorso\b|\bcitazione\b|\bcomparsa\b|\bmemoria\b|\bistanza\b|\bappello\b|\breclamo\b|\bopposizione\b|deduzion)/.test(text)
}

function isMainActSlot(slot: Record<string, unknown>): boolean {
  const slotKey = recordText(slot, 'slotKey').toUpperCase()
  const type = recordText(slot, 'type').toUpperCase()
  return slotKey === 'ATTO_PRINCIPALE' || type === 'ATTO_PRINCIPALE'
}

function mainActCandidateScore(doc: FascicoloDocument): number {
  if (!isMainActCandidateDocument(doc)) return 0
  const text = documentSearchText(doc)
  let score = 10
  if (doc.catalogRole === 'atto_principale') score += 80
  if (doc.catalogRole === 'atto_difensivo') score += 55
  if (doc.signed) score += 30
  if (/(^|[^a-z])atto([^a-z]|$)|attoacq|atto acquisito|atto giudiziario/.test(text)) score += 25
  if (/\bricorso\b|\bcitazione\b|\bcomparsa\b|\bappello\b|\breclamo\b|\bopposizione\b/.test(text)) score += 20
  if (/\bmemoria\b|\bistanza\b|deduzion|conclusion/.test(text)) score += 12
  return score
}

function preferredMainActCandidateDocument(documents: FascicoloDocument[]): FascicoloDocument | undefined {
  return documents
    .map((doc, index) => ({ doc, index, score: mainActCandidateScore(doc) }))
    .filter((row) => row.score > 0)
    .sort((a, b) => b.score - a.score || a.index - b.index)[0]?.doc
}

function documentOperationalRole(doc: FascicoloDocument): { label: string; detail: string; tone: FascicoloRow['tone'] } {
  if (isNotificationProofDocument(doc)) {
    return { label: notificationProofLabel(doc), detail: 'Prova di notifica già presente nel fascicolo: si usa per il deposito prova, senza nuovo invio.', tone: 'info' }
  }
  if (doc.catalogLabel && doc.catalogConfidence >= 70) {
    const tone: FascicoloRow['tone'] =
      doc.catalogSection === 'atti' ? 'primary'
        : doc.catalogSection === 'provvedimenti' ? 'purple'
          : doc.catalogSection === 'comunicazioni' ? 'info'
            : doc.catalogSection === 'pagamenti' ? 'success'
              : doc.catalogSection === 'allegati' ? 'neutral'
                : 'warning'
    const detail = doc.catalogEvidence
      ? `Catalogato da OCR e dati del fascicolo: ${doc.catalogEvidence}.`
      : 'Catalogato da OCR e dati del fascicolo.'
    return { label: doc.catalogLabel, detail, tone }
  }
  if (isCommunicationDocument(doc)) {
    return { label: 'Ricevuta / comunicazione', detail: 'Fuori dalla busta: presidio cancelleria e ricevute.', tone: 'info' }
  }
  if (isPortalAcquiredDocument(doc)) {
    const role = portalCatalogRole(`${doc.portalClass} ${doc.type} ${doc.name}`)
    return {
      label: role.label,
      detail: role.depositCandidate ? 'Documento portale candidato come allegato/atto.' : 'Documento portale tenuto come contesto ufficiale.',
      tone: role.tone,
    }
  }
  if (isDepositCandidateDocument(doc)) {
    return { label: 'Candidato busta', detail: 'Letto dall’intero fascicolo per atto o allegato.', tone: doc.signed ? 'success' : 'warning' }
  }
  return { label: 'Da classificare', detail: 'Presente nel fascicolo, da verificare prima del deposito.', tone: 'warning' }
}

function defaultDepositRoleForDocument(doc: FascicoloDocument | undefined, linkedSlotKey = '', isProposedMainAct = false): DepositDocumentRole {
  if (!doc) return 'allegato'
  const slot = normaliseText(linkedSlotKey)
  const text = documentSearchText(doc)
  if (isProposedMainAct || /atto principale|atto_principale|atto da notificare|atto_da_notificare/.test(slot)) return 'atto_principale'
  if (doc.depositRole === 'atto_principale') return 'atto_principale'
  if (doc.depositRole === 'procura') return 'procura'
  if (doc.depositRole === 'prova_notifica') return 'prova_notifica'
  if (doc.depositRole === 'fuori_busta') return 'fuori_busta'
  if (doc.depositRole === 'contributo_unificato' || doc.catalogRole === 'contributo_unificato') return 'allegato'
  if (doc.depositRole === 'allegato' || doc.catalogRole === 'provvedimento' || doc.catalogRole === 'allegato') return 'allegato'
  if (/procura/.test(slot) || /procura/.test(text)) return 'procura'
  if (/prova|notifica|ricevuta/.test(slot) || notificationProofKind(doc)) return 'prova_notifica'
  if (isCommunicationDocument(doc)) return 'fuori_busta'
  if (/contratto|quietanza|busta paga|cedolin|documento|allegat/.test(text)) return 'allegato'
  return 'allegato'
}

function depositRoleLabel(role: DepositDocumentRole): { label: string; tone: FascicoloRow['tone'] } {
  if (role === 'atto_principale') return { label: 'Atto principale', tone: 'primary' }
  if (role === 'procura') return { label: 'Procura alle liti', tone: 'purple' }
  if (role === 'allegato_prova') return { label: 'Allegato', tone: 'success' }
  if (role === 'prova_notifica') return { label: 'Prova notifica', tone: 'info' }
  if (role === 'fuori_busta') return { label: 'Fuori busta', tone: 'neutral' }
  return { label: 'Allegato', tone: 'neutral' }
}

function depositRoleDisplayLabelForDocument(doc: FascicoloDocument, role: DepositDocumentRole): string {
  const technicalLabel = depositRoleLabel(role).label
  if (role !== 'allegato' || !doc.catalogLabel || doc.catalogConfidence < 70) return technicalLabel
  if (['atto_difensivo', 'contributo_unificato', 'nota_iscrizione_ruolo', 'provvedimento', 'relata', 'prova_notifica', 'procura'].includes(doc.catalogRole)) {
    return `${doc.catalogLabel} (allegato busta)`
  }
  if (doc.catalogSection === 'pagamenti') return `${doc.catalogLabel} (allegato busta)`
  return technicalLabel
}

function normaliseDepositClassificationMainAct(
  classificationById: Record<string, DepositDocumentClassification>,
  preferredMainActId = '',
  validMainActIds?: ReadonlySet<string>,
): Record<string, DepositDocumentClassification> {
  const entries = Object.entries(classificationById)
  const preferredSelected = preferredMainActId ? entries.find(([id, row]) => id === preferredMainActId && row.selected) : undefined
  const validSelectedMain = entries.find(([id, row]) => row.selected && row.role === 'atto_principale' && (!validMainActIds || validMainActIds.has(id)))
  const selectedMain = validSelectedMain
    || preferredSelected
    || entries.find(([id, row]) => row.selected && row.role === 'atto_principale' && id === preferredMainActId)
    || entries.find(([, row]) => row.selected && row.role === 'atto_principale')
  const selectedMainId = selectedMain?.[0] || ''
  if (!selectedMainId) return classificationById
  let changed = false
  const next = Object.fromEntries(entries.map(([id, row]) => {
    if (id === selectedMainId && row.role !== 'atto_principale') {
      changed = true
      return [id, { ...row, role: 'atto_principale' as DepositDocumentRole }]
    }
    if (row.selected && row.role === 'atto_principale' && id !== selectedMainId) {
      changed = true
      return [id, { ...row, role: 'allegato' as DepositDocumentRole }]
    }
    return [id, row]
  }))
  return changed ? next : classificationById
}

function depositSelectionRole(doc: FascicoloDocument, isMainAct: boolean, selectedRole?: DepositDocumentRole): { label: string; tone: FascicoloRow['tone'] } {
  if (selectedRole) {
    const role = depositRoleLabel(selectedRole)
    if (selectedRole === 'atto_principale') return { label: role.label, tone: doc.signed ? 'success' : 'warning' }
    return role
  }
  if (isMainAct) return { label: 'Atto principale', tone: doc.signed ? 'success' : 'warning' }
  const proof = notificationProofKind(doc)
  if (proof) return { label: notificationProofLabel(doc), tone: 'info' }
  if (isMainActCandidateDocument(doc)) return { label: 'Atto candidato', tone: doc.signed ? 'success' : 'warning' }
  const role = documentOperationalRole(doc)
  if (role.label === 'Candidato busta') return { label: 'Allegato', tone: role.tone }
  return { label: role.label, tone: role.tone }
}

function depositDocumentMatchesSlot(slot: Record<string, unknown>, doc: FascicoloDocument): boolean {
  const slotText = normaliseText([
    recordText(slot, 'slotKey'),
    recordText(slot, 'label'),
    recordText(slot, 'type'),
    recordText(slot, 'message'),
  ].join(' '))
  const docText = documentSearchText(doc)
  if (/atto principale|atto_principale|atto da notificare|atto_da_notificare/.test(slotText)) return isMainActCandidateDocument(doc)
  if (/procura/.test(slotText)) return doc.catalogRole === 'procura' || /procura/.test(docText)
  if (/contributo|pagamento|pagopa/.test(slotText)) return doc.catalogRole === 'contributo_unificato' || /(contributo|unificato|pagopa|ricevuta telematica|rt xml)/.test(docText)
  if (/marca|bollo/.test(slotText)) return /(marca|bollo)/.test(docText)
  if (/nota iscrizione|nir/.test(slotText)) return /(nota iscrizione|nir|iscrizione a ruolo)/.test(docText)
  if (/prova|notifica|ricevuta/.test(slotText)) return Boolean(notificationProofKind(doc)) || /(prova|notifica|ricevut)/.test(docText)
  if (/allegat|documento/.test(slotText)) return isDepositCandidateDocument(doc) && !isMainActCandidateDocument(doc)
  return false
}

function slotMatchesDepositRole(slot: Record<string, unknown>, role: DepositDocumentRole): boolean {
  const uiRole = normaliseDepositRoleForUi(role)
  const slotText = normaliseText(`${recordText(slot, 'slotKey')} ${recordText(slot, 'label')} ${recordText(slot, 'type')}`)
  if (/atto principale|atto_principale|atto da notificare|atto_da_notificare/.test(slotText)) return uiRole === 'atto_principale'
  if (/procura/.test(slotText)) return uiRole === 'procura'
  if (/prova|notifica|ricevuta|rac|rdac/.test(slotText)) return uiRole === 'prova_notifica'
  if (/allegat|documento/.test(slotText)) return uiRole === 'allegato'
  return false
}

function depositSelectionSatisfiesSlot(
  slot: Record<string, unknown>,
  selectedDocuments: FascicoloDocument[],
  mainAct: FascicoloDocument | undefined,
  classificationById: Record<string, DepositDocumentClassification> = {},
): boolean {
  const slotText = normaliseText(`${recordText(slot, 'slotKey')} ${recordText(slot, 'label')} ${recordText(slot, 'type')}`)
  if (/atto principale|atto_principale|atto da notificare|atto_da_notificare/.test(slotText)) return Boolean(mainAct)
  const linkedDocumentId = recordText(slot, 'documentId')
  if (linkedDocumentId && selectedDocuments.some((doc) => doc.id === linkedDocumentId)) return true
  if (selectedDocuments.some((doc) => slotMatchesDepositRole(slot, classificationById[doc.id]?.role || defaultDepositRoleForDocument(doc)))) return true
  return selectedDocuments.some((doc) => depositDocumentMatchesSlot(slot, doc))
}

function depositReadinessSatisfiesSlot(slot: Record<string, unknown>, readiness: FascicoloDepositReadiness): boolean | null {
  const slotText = normaliseText(`${recordText(slot, 'slotKey')} ${recordText(slot, 'label')} ${recordText(slot, 'type')}`)
  if (/contributo/.test(slotText)) return readiness.contributoUnificato.ready
  if (/anagrafica/.test(slotText)) return readiness.anagraficaProcedimento.ready
  if (/valore causa/.test(slotText)) return readiness.valoreCausa.ready
  return null
}

type MissingDepositSlotsInput = number | Array<Record<string, unknown>>

function missingDepositSlotsCount(slots: MissingDepositSlotsInput): number {
  return Array.isArray(slots) ? slots.length : slots
}

function missingDepositSlotLabel(slot: Record<string, unknown>): string {
  const label = recordText(slot, 'label') || recordText(slot, 'type') || recordText(slot, 'slotKey')
  return depositCatalogRequirementLabel(label || 'documento richiesto')
}

function missingDepositSlotsSummary(slots: MissingDepositSlotsInput): string {
  if (!Array.isArray(slots) || !slots.length) return ''
  const labels = Array.from(new Set(slots.map(missingDepositSlotLabel).filter(Boolean)))
  if (labels.length <= 2) return labels.join(' e ')
  return `${labels.slice(0, 2).join(', ')} e altri ${labels.length - 2}`
}

function slotStatusDisplay(value: string, linked = false): { label: string; tone: FascicoloRow['tone'] } {
  const key = String(value || '').trim().toUpperCase()
  if (linked && key !== 'NON_VALIDO') return { label: 'Scelto', tone: 'success' }
  if (key === 'VALIDO') return { label: 'Collegato', tone: 'success' }
  if (key === 'WARNING') return { label: 'Da verificare', tone: 'warning' }
  if (key === 'NON_APPLICABILE') return { label: 'Non richiesto', tone: 'neutral' }
  if (key === 'MANCANTE') return { label: linked ? 'Collegato' : 'Da scegliere', tone: linked ? 'primary' : 'warning' }
  if (key === 'NON_VALIDO') return { label: linked ? 'Da correggere' : 'Da scegliere', tone: 'warning' }
  return { label: linked ? 'Collegato' : 'Da scegliere', tone: linked ? 'primary' : 'warning' }
}

function depositCatalogRequirementLabel(value: string): string {
  const clean = value.trim().replace(/\s+/g, ' ')
  return clean ? clean.charAt(0).toUpperCase() + clean.slice(1) : 'Requisito deposito'
}

function depositCatalogRequirementKind(label: string): 'file' | 'data' {
  const text = normaliseText(label)
  if (/(contributo|anagrafica|valore causa|data citazione|istanze|riferimento procedimento|dati procedura|dati terzi|modifiche anagrafica)/.test(text)) return 'data'
  return 'file'
}

function depositCatalogSlotKey(label: string, index: number): string {
  const text = normaliseText(label)
  if (/atto da notificare/.test(text)) return 'ATTO_DA_NOTIFICARE'
  if (/atto principale/.test(text)) return 'ATTO_PRINCIPALE'
  if (/procura/.test(text)) return 'PROCURA'
  if (/contributo/.test(text)) return 'CONTRIBUTO_UNIFICATO'
  if (/nota iscrizione|nir/.test(text)) return 'NOTA_ISCRIZIONE_RUOLO'
  if (/provvedimento impugnato/.test(text)) return 'PROVVEDIMENTO_IMPUGNATO'
  if (/prova notifica/.test(text)) return 'PROVA_NOTIFICA'
  if (/relata|richiesta/.test(text)) return 'RELATA_NOTIFICA'
  if (/destinatari/.test(text)) return 'DESTINATARI'
  if (/ricevute/.test(text)) return 'RICEVUTE'
  if (/allegati/.test(text)) return 'ALLEGATI'
  return `REQUISITO_CATALOGO_${index + 1}`
}

function depositCatalogSlotType(label: string): string {
  const text = normaliseText(label)
  if (/atto da notificare/.test(text)) return 'ATTO_DA_NOTIFICARE'
  if (/atto principale/.test(text)) return 'ATTO_PRINCIPALE'
  if (/procura/.test(text)) return 'PROCURA'
  if (/contributo/.test(text)) return 'CONTRIBUTO_UNIFICATO'
  if (/nota iscrizione|nir/.test(text)) return 'NOTA_ISCRIZIONE_RUOLO'
  if (/prova notifica|provvedimento impugnato|relata|ricevute|allegati/.test(text)) return 'DOCUMENTO'
  return depositCatalogRequirementKind(label) === 'data' ? 'DATO_DEPOSITO' : 'DOCUMENTO'
}

function depositCatalogSlotRequired(label: string): boolean {
  const text = normaliseText(label)
  if (/contributo/.test(text)) return true
  if (depositCatalogRequirementKind(label) === 'data') return false
  if (/allegati|ricevute|destinatari/.test(text)) return false
  return true
}

function buildDepositCatalogSlots(
  selectedType: FascicoloDepositCatalogEntry | undefined,
  baseSlots: Array<Record<string, unknown>>,
): Array<Record<string, unknown>> {
  const catalogDocuments = (selectedType?.ui.documents || []).map((item) => item.trim()).filter(Boolean)
  if (!catalogDocuments.length) return [...baseSlots]
  const baseByKey = new Map<string, Record<string, unknown>>()
  baseSlots.forEach((slot) => {
    const key = recordText(slot, 'slotKey').toUpperCase()
    if (key) baseByKey.set(key, slot)
  })
  const mainActBaseSlot = baseSlots.find((slot) => /atto principale|atto_principale/.test(normaliseText([
    recordText(slot, 'slotKey'),
    recordText(slot, 'label'),
    recordText(slot, 'type'),
  ].join(' '))))
  const used = new Set<string>()
  const catalogSlots: Array<Record<string, unknown>> = catalogDocuments.map((label, index) => {
    const slotKey = depositCatalogSlotKey(label, index)
    const baseSlotKey = slotKey === 'ATTO_DA_NOTIFICARE' ? 'ATTO_PRINCIPALE' : slotKey
    const baseSlot = baseByKey.get(slotKey) || baseByKey.get(baseSlotKey) || (slotKey === 'ATTO_DA_NOTIFICARE' ? mainActBaseSlot : undefined)
    if (baseSlot) used.add(baseSlotKey)
    if (baseSlot) {
      const actualBaseKey = recordText(baseSlot, 'slotKey').toUpperCase()
      if (actualBaseKey) used.add(actualBaseKey)
    }
    if (baseSlot && baseSlotKey !== slotKey) used.add(slotKey)
    const kind = depositCatalogRequirementKind(label)
    const labelText = depositCatalogRequirementLabel(label)
    const useCatalogLabel = slotKey === 'ATTO_DA_NOTIFICARE'
    return {
      ...(baseSlot || {}),
      slotKey,
      label: useCatalogLabel ? labelText : (recordText(baseSlot, 'label') || labelText),
      type: useCatalogLabel ? depositCatalogSlotType(label) : (recordText(baseSlot, 'type') || depositCatalogSlotType(label)),
      required: baseSlot ? recordBool(baseSlot, 'required') : depositCatalogSlotRequired(label),
      sortOrder: recordText(baseSlot, 'sortOrder') || String((index + 1) * 10),
      status: recordText(baseSlot, 'status') || (kind === 'data' ? 'WARNING' : 'MANCANTE'),
      catalogOnly: !baseSlot,
      catalogRequirementKind: kind,
      message: recordText(baseSlot, 'message') || (
        kind === 'data'
          ? 'Dato richiesto dal tipo deposito selezionato: verifica nel pannello dati deposito.'
          : 'Documento richiesto dal tipo deposito selezionato.'
      ),
      suggestedAction: recordText(baseSlot, 'suggestedAction') || (
        kind === 'data'
          ? 'Controlla il dato prima della generazione della busta.'
        : 'Classifica o seleziona il documento corretto nella lista Documenti da inviare.'
      ),
    }
  })
  const catalogUsesNotifiableAct = catalogSlots.some((slot) => recordText(slot, 'slotKey').toUpperCase() === 'ATTO_DA_NOTIFICARE')
  const linkedExtraSlots = baseSlots
    .filter((slot) => {
      const key = recordText(slot, 'slotKey').toUpperCase()
      const text = normaliseText([key, recordText(slot, 'label'), recordText(slot, 'type')].join(' '))
      if (catalogUsesNotifiableAct && /atto principale|atto_principale/.test(text)) return false
      return key && !used.has(key) && recordText(slot, 'documentId')
    })
    .map((slot) => ({ ...slot, required: false, catalogAdvisory: true }))
  return [...catalogSlots, ...linkedExtraSlots]
}

function depositPackageKindLabel(value: string): string {
  const key = normaliseText(value)
  if (key.includes('pct_busta_enc')) return 'Pacchetto deposito'
  if (key.includes('sigp')) return 'Pacchetto Giudice di Pace'
  if (key.includes('pdp')) return 'Pacchetto deposito penale'
  if (key.includes('pat')) return 'Pacchetto giustizia amministrativa'
  if (key.includes('ptt')) return 'Pacchetto giustizia tributaria'
  if (key.includes('unep')) return 'Richiesta ufficio notifiche'
  if (key.includes('pec')) return 'Messaggio PEC con ricevute'
  if (key.includes('portal') || key.includes('upload')) return 'Pacchetto per portale ufficiale'
  return 'Pacchetto da verificare'
}

function depositDeliveryNote(note: string, officialChannel: string, practiceProfileName: string, fallbackChannel: string): string {
  const clean = note.trim()
  if (!clean) return ''
  const context = normaliseText(`${officialChannel} ${practiceProfileName} ${fallbackChannel}`)
  if (/(lavoro|rgl|retribuzion)/.test(context) && /pct civile|civile sicid/.test(normaliseText(clean))) {
    return 'Profilo lavoro applicato: usare il canale PCT lavoro/SICID; per altri registri la Regia richiede il canale corrispondente.'
  }
  return clean
}

function depositVisibleReference(primary: string, fallback: string): string {
  const value = String(primary || '').trim()
  const normalized = normaliseText(value).replace(/\s+/g, '')
  if (value && normalized !== 'nd' && normalized !== 'n.d.') return value
  return String(fallback || '').trim() || 'Da verificare'
}

function depositActCodeFromDocument(doc: FascicoloDocument | undefined, profile: Record<string, unknown>): string {
  const text = normaliseText(`${doc?.type || ''} ${doc?.name || ''} ${recordText(profile, 'procedureCode')} ${recordText(profile, 'practiceId')}`)
  if (/comparsa/.test(text)) return 'COMPARSA_RISPOSTA'
  if (/decreto ingiuntivo|ingiuntiv/.test(text)) return 'DECRETO_INGIUNTIVO'
  if (/appello|impugnazion|reclamo/.test(text)) return 'APPELLO'
  if (/citazion/.test(text)) return 'ATTO_DI_CITAZIONE'
  if (/ricorso/.test(text)) return 'RICORSO'
  if (/memoria|note scritte|conclusionale|replica/.test(text)) return 'MEMORIA'
  if (/istanza/.test(text)) return 'ISTANZA'
  return 'ATTO_GENERICO'
}

function depositRegistryCode(fascicolo: FascicoloFull): string {
  const text = normaliseText(`${fascicolo.type} ${fascicolo.procedureType} ${fascicolo.rg}`)
  if (/lavoro|rgl/.test(text)) return 'RGL'
  if (/volontaria|vg/.test(text)) return 'VG'
  if (/esecuz|rge/.test(text)) return 'RGE'
  return 'RG'
}

function depositActionBlockedReason(ready: boolean, mainAct: FascicoloDocument | undefined, missingSlots: MissingDepositSlotsInput, unsignedDocs = 0): string {
  const missingCount = missingDepositSlotsCount(missingSlots)
  const missingSummary = missingDepositSlotsSummary(missingSlots)
  if (!mainAct) return 'Seleziona l’atto principale prima di generare la busta.'
  if (missingCount === 1) return `Completa ${missingSummary || 'la scelta obbligatoria'} prima dell’invio reale.`
  if (missingCount) return `Completa le scelte obbligatorie prima dell’invio reale: ${missingSummary || `${missingCount} documenti richiesti`}.`
  if (unsignedDocs === 1) return '1 documento sarà firmato da IUSENTRA prima della busta.'
  if (unsignedDocs) return `${unsignedDocs} documenti saranno firmati da IUSENTRA prima della busta.`
  if (!ready) return 'Esegui e supera la verifica deposito prima dell’azione finale.'
  return ''
}

function depositGenerationBlockedReason(mainAct: FascicoloDocument | undefined, missingSlots: MissingDepositSlotsInput): string {
  const missingCount = missingDepositSlotsCount(missingSlots)
  const missingSummary = missingDepositSlotsSummary(missingSlots)
  if (!mainAct) return 'Seleziona l’atto principale prima di generare la busta.'
  if (missingCount === 1) return `Completa ${missingSummary || 'la scelta obbligatoria'} prima di generare la prova.`
  if (missingCount) return `Completa le scelte obbligatorie prima di generare la prova: ${missingSummary || `${missingCount} documenti richiesti`}.`
  return ''
}

function portalDepositHref(officialChannel: string, fallbackChannel: string): string {
  const text = normaliseText(`${officialChannel} ${fallbackChannel}`)
  if (/pdp|penale/.test(text)) return '/portali/pdp/acquisizione'
  if (/pat|siga|amministrativ/.test(text)) return '/portali/pat/acquisizione'
  if (/ptt|sigit|tributar/.test(text)) return '/portali/ptt/acquisizione'
  if (/sigp|giudice di pace|gdp/.test(text)) return '/portali/pst/acquisizione'
  return '/portali/pst/acquisizione'
}

function buildPortalCatalogRows(data: FascicoloDetailData): PortalCatalogRow[] {
  const rows: PortalCatalogRow[] = []
  const add = (row: Omit<PortalCatalogRow, 'id' | 'role' | 'tone'>, seed: string) => {
    const role = portalCatalogRole(`${row.type} ${row.name}`)
    const id = normaliseText([seed, row.name, row.type, row.date, row.sender].filter(Boolean).join('|'))
    if (!id || rows.some((item) => item.id === id)) return
    rows.push({ ...row, id, role: role.label, tone: role.tone })
  }
  for (const dep of data.deposits) {
    for (const doc of dep.portalDocuments) {
      add({
        name: doc.name || 'Documento ufficiale',
        type: doc.type || dep.actType || 'Documento',
        date: doc.date || dep.timestamp,
        sender: doc.sender || dep.pec,
        source: dep.source || 'Portale Servizi',
        imported: doc.imported,
        available: doc.available,
      }, `deposito-${dep.id}`)
    }
  }
  for (const doc of data.documents.filter(isPortalAcquiredDocument)) {
    add({
      name: doc.portalName || doc.name || 'Documento ufficiale',
      type: doc.portalClass || doc.type || 'Documento',
      date: doc.portalDate || doc.documentDate || doc.uploadedAt,
      sender: doc.portalSender,
      source: doc.source || 'Portale Servizi',
      imported: true,
      available: true,
    }, `documento-${doc.id}`)
  }
  return rows.sort((a, b) => `${b.date} ${b.name}`.localeCompare(`${a.date} ${a.name}`, 'it'))
}

function documentAutoSectionId(doc: FascicoloDocument): string {
  if (['atti', 'provvedimenti', 'comunicazioni', 'pagamenti', 'allegati', 'da-verificare'].includes(doc.catalogSection)) return doc.catalogSection
  const text = documentSearchText(doc)
  if (/(pec|cancelleria|comunicazion|notifica|relata|busta|rdac|rac|esito|ricevut|accettazion)/.test(text)) return 'comunicazioni'
  if (/(sentenza|ordinanza|decreto|provvediment|verbale)/.test(text)) return 'provvedimenti'
  if (/(atto giudiziario|ricorso|citazione|comparsa|memoria|conclusionale|replica)/.test(text)) return 'atti'
  if (/(procura|contratto|parcella|fattura|allegato|documento ufficiale)/.test(text)) return 'allegati'
  return 'da-verificare'
}

function depositCommunicationText(dep: FascicoloDeposit): string {
  return normaliseText([
    dep.status,
    dep.actType,
    dep.message,
    dep.pec,
    dep.source,
    dep.timestamp,
    dep.roleNumber,
    dep.externalId,
    dep.acceptedAt,
    dep.acceptedBy,
  ].join(' '))
}

function depositMetaLine(dep: FascicoloDeposit): string {
  const docs = dep.documentsCount === 1 ? '1 documento' : dep.documentsCount > 1 ? `${dep.documentsCount} documenti` : ''
  const date = dep.acceptedAt
    ? `Accettato il ${dep.acceptedAt}`
    : dep.sentAt
      ? `Depositato il ${dep.sentAt}`
      : dep.timestamp || 'Data non indicata'
  const role = dep.roleNumber ? `RG ${dep.roleNumber}` : ''
  const external = dep.externalId ? `IDBUSTA ${dep.externalId}` : ''
  const registered = dep.registeredBy ? `registrato da ${dep.registeredBy}` : ''
  return [date, role, external, registered, docs, dep.source].filter(Boolean).join(' - ')
}

function depositStatusLabel(status: string): string {
  const clean = normaliseText(status).replace(/_/g, ' ').trim()
  if (!clean) return 'Da verificare'
  if (/importato da portale/.test(clean)) return 'Importato da portale'
  if (/accettato cancelleria/.test(clean)) return 'Deposito confermato'
  if (/warn controlli/.test(clean)) return 'Controlli con avvisi'
  if (/accettato pec/.test(clean)) return 'Accettato PEC'
  if (/consegnato/.test(clean)) return 'Consegnato'
  if (/errore/.test(clean)) return 'Errore'
  return clean
    .split(/\s+/)
    .map((word) => word ? `${word.charAt(0).toUpperCase()}${word.slice(1)}` : word)
    .join(' ')
}

function isCancelleriaCommunication(dep: FascicoloDeposit): boolean {
  const text = depositCommunicationText(dep)
  return /(accettazion|consegna|rdac|rac|esito|cancelleria|deposito|busta)/.test(text)
}

function depositNextSimulationLabel(dep: FascicoloDeposit): string {
  const next = dep.receiptSteps.find((step) => !step.done)
  if (!next) return 'Prova completata'
  if (next.id === 'accettazione') return 'Genera accettazione'
  if (next.id === 'consegna') return 'Genera consegna'
  if (next.id === 'controlli') return 'Genera controlli'
  if (next.id === 'cancelleria') return 'Genera conferma'
  return `Genera ${next.label.toLowerCase()}`
}

function depositPhaseSummary(dep: FascicoloDeposit): { label: string; body: string; tone: FascicoloRow['tone'] } {
  const status = normaliseText(`${dep.status} ${dep.checks}`)
  const done = new Set(dep.receiptSteps.filter((step) => step.done).map((step) => step.id))
  if (/accettato cancelleria/.test(status) || done.has('cancelleria')) {
    return { label: 'Deposito confermato', body: 'La conferma di cancelleria è registrata nel fascicolo.', tone: 'success' }
  }
  if (/errore|rifiutato/.test(status)) {
    return { label: 'Deposito da presidiare', body: 'È presente un esito negativo o un blocco: verifica le ricevute e gli allegati.', tone: 'danger' }
  }
  if (/warn controlli|warn/.test(status)) {
    return { label: 'Controlli automatici con avvisi', body: "La PEC dei controlli è arrivata: serve verifica dell'avvocato prima della conferma finale.", tone: 'warning' }
  }
  if (done.has('controlli')) {
    return { label: 'Controlli automatici ricevuti', body: 'La fase tecnica è registrata; resta da attendere la conferma della cancelleria.', tone: 'warning' }
  }
  if (done.has('consegna')) {
    return { label: 'Consegna PEC ricevuta', body: 'Il messaggio risulta consegnato: attendi i controlli automatici.', tone: 'primary' }
  }
  if (done.has('accettazione') || /accettato pec/.test(status)) {
    return { label: 'Accettazione PEC ricevuta', body: 'Il gestore PEC ha accettato il messaggio di deposito.', tone: 'success' }
  }
  if (/inviato/.test(status)) {
    return { label: 'Deposito inviato', body: 'Il deposito è registrato: verifica l’arrivo delle ricevute PEC.', tone: 'primary' }
  }
  return { label: 'Deposito da verificare', body: 'Apri il flusso PEC per controllare accettazione, consegna, controlli e conferma.', tone: 'neutral' }
}

function DepositReceiptSteps({ dep }:{dep:FascicoloDeposit}) {
  const visible = dep.simulated || dep.receiptSteps.some((step) => step.done)
  if (!visible || !dep.receiptSteps.length) return null
  return (
    <div className="iu-fas-receipt-steps" aria-label="Stato ricevute deposito">
      {dep.receiptSteps.map((step) => (
        <span className={step.done ? 'is-done' : ''} key={`${dep.id}-${step.id}`}>
          {step.done ? <CheckCircle2 size={13}/> : <Clock3 size={13}/>}
          {step.label}
        </span>
      ))}
    </div>
  )
}

function DepositReceiptActions({ dep, onDone, onError }:{dep:FascicoloDeposit; onDone:(message?:string)=>void; onError:(message:string)=>void}) {
  const done = dep.receiptSteps.length > 0 && dep.receiptSteps.every((step) => step.done)
  if (!dep.checkReceiptsAction && !dep.nextSimulationAction && !dep.simulated) return null
  return (
    <div className="iu-fas-comm-actions">
      {!dep.simulated && dep.checkReceiptsAction ? <PostAction action={dep.checkReceiptsAction} tone="secondary" onDone={onDone} onError={onError}><RefreshCw size={14}/> Controlla PEC</PostAction> : null}
      {dep.nextSimulationAction ? <PostAction action={dep.nextSimulationAction} tone="primary" onDone={onDone} onError={onError}><CheckCircle2 size={14}/> {depositNextSimulationLabel(dep)}</PostAction> : null}
      {dep.simulated ? <small>{done ? 'Prova senza invio reale completata' : 'Prova senza invio reale'}</small> : null}
      {!dep.simulated ? <small>La PEC viene sincronizzata automaticamente; usa il controllo manuale solo per anticipare.</small> : null}
    </div>
  )
}

function DepositStateSummary({ dep }:{dep:FascicoloDeposit}) {
  const summary = depositPhaseSummary(dep)
  const facts = [
    dep.roleNumber ? `RG ${dep.roleNumber}` : '',
    dep.externalId ? `IDBUSTA ${dep.externalId}` : '',
    dep.acceptedAt ? `Accettato il ${dep.acceptedAt}` : '',
    dep.acceptedBy ? `Da ${dep.acceptedBy}` : '',
    dep.registeredBy ? `Registrato da ${dep.registeredBy}` : '',
    dep.sourceMessageId ? `Messaggio deposito ${dep.sourceMessageId}` : '',
  ].filter(Boolean)
  return (
    <div className={`iu-fas-deposit-state iu-fas-deposit-state--${summary.tone}`}>
      <Badge tone={summary.tone}>{summary.label}</Badge>
      <span>{summary.body}</span>
      {facts.length ? <small>{facts.join(' - ')}</small> : null}
    </div>
  )
}

function buildDocumentSections(documents: FascicoloDocument[]): DocumentAutoSection[] {
  const grouped = new Map<string, FascicoloDocument[]>()
  for (const doc of documents) {
    const sectionId = documentAutoSectionId(doc)
    grouped.set(sectionId, [...(grouped.get(sectionId) || []), doc])
  }
  return documentAutoSectionOrder
    .map((section) => ({ ...section, documents: grouped.get(section.id) || [] }))
    .filter((section) => section.documents.length > 0)
}

function DocumentUploadWorkspace({
  data,
  onDone,
  onError,
}: {
  data: FascicoloDetailData
  onDone: (message?: string) => void
  onError: (message: string) => void
}) {
  const [files, setFiles] = useState<File[]>([])
  const [mode, setMode] = useState<'auto' | 'manuale'>('auto')
  const [busy, setBusy] = useState(false)
  if (!data.actions.uploadDocument) return null
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = event.currentTarget
    const formData = new FormData(form)
    const selectedFiles = formData.getAll('files').filter((value): value is File => value instanceof File && Boolean(value.name))
    if (!selectedFiles.length) {
      onError('Seleziona almeno un documento da caricare.')
      return
    }
    setBusy(true)
    try {
      const result = await submitFormJson(data.actions.uploadDocument, formData)
      form.reset()
      setFiles([])
      setMode('auto')
      onDone(result.message || 'Documenti caricati.')
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Caricamento non riuscito.')
    } finally {
      setBusy(false)
    }
  }
  const typeOptions = data.options.documentTypes.length ? data.options.documentTypes : [{ value: 'ALTRO', label: 'Altro' }]
  return (
    <section className="iu-fas-doc-workspace" aria-label="Documenti e atti del fascicolo">
      <form className="iu-fas-doc-upload" onSubmit={submit} encType="multipart/form-data">
        <input type="hidden" name="classificazione_modalita" value={mode}/>
        <label className="iu-fas-field iu-fas-field--wide">
          <span>Carica documenti</span>
          <input
            type="file"
            name="files"
            multiple
            onChange={(event) => setFiles(Array.from(event.currentTarget.files || []))}
          />
          <small className="iu-fas-field-help">Puoi selezionare più file. IUSENTRA li classifica dal nome, oppure puoi scegliere il tipo per ogni documento.</small>
        </label>
        <label className="iu-fas-field">
          <span>Classificazione</span>
          <select value={mode} onChange={(event) => setMode(event.target.value as 'auto' | 'manuale')}>
            <option value="auto">Automatica</option>
            <option value="manuale">Manuale</option>
          </select>
        </label>
        <label className="iu-fas-field">
          <span>Data documento</span>
          <input type="date" name="data_documento"/>
        </label>
        <label className="iu-fas-field">
          <span>Etichette</span>
          <input name="tags" placeholder="urgenza, deposito, prova"/>
        </label>
        <label className="iu-fas-field">
          <span>Note</span>
          <input name="note" placeholder="Nota interna sul documento"/>
        </label>
        <label className="iu-fas-check-field">
          <input type="checkbox" name="firmato" value="1"/>
          <span>Già firmato</span>
        </label>
        {mode === 'manuale' ? (
          <div className="iu-fas-upload-preview" aria-label="Classificazione manuale dei file selezionati">
            {files.length ? files.map((file, index) => (
              <label key={`${file.name}-${index}`}>
                <span>{file.name}</span>
                <select name={`tipo_doc_${index}`} defaultValue="ALTRO">
                  {typeOptions.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
                </select>
              </label>
            )) : <p className="iu-empty">Seleziona uno o più file per assegnare il tipo documento.</p>}
          </div>
        ) : null}
        <button type="submit" disabled={busy}><UploadCloud size={15}/> {busy ? 'Caricamento...' : 'Carica documenti'}</button>
      </form>
    </section>
  )
}

type LocalSignerToken = { slot_id?: number | string; label?: string; manufacturer?: string; model?: string; serial?: string }
type LocalSignerWindowsCertificate = {
  thumbprint?: string
  soggetto?: string
  soggetto_completo?: string
  emittente?: string
  emittente_completo?: string
  scadenza?: string
  codice_fiscale?: string
  auto_selezionato?: boolean
}
type LocalSignerStatus = {
  ok?: boolean
  token?: LocalSignerToken[]
  token_probe_fresh?: LocalSignerToken[]
  certificato_windows_firma_selezionato?: LocalSignerWindowsCertificate
  certificato_windows_selezionato?: LocalSignerWindowsCertificate
  versione?: string
  version?: string
  piattaforma?: string
  messaggio?: string
  error?: string
  errore_token?: string
  errore_libreria?: string
  riavvio_signer_consigliato?: boolean
  nota_riavvio_signer?: string
  __iusentra_base_url?: string
  __iusentra_probe_urls?: string[]
  __iusentra_last_error?: string
}
type LocalSignerRecoveryOptions = {
  onMessage?: (message: string) => void
}
type LocalNetworkRequestInit = RequestInit & { targetAddressSpace?: 'local' }
type FirmaInfo = {
  firme?: unknown[]
  nome?: string
  errore?: string
  signed_status?: Record<string, unknown>
  signed_ui?: { label?: string; tone?: FascicoloRow['tone']; detail?: string }
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

function base64ToUint8Array(value: string): Uint8Array {
  const binary = atob(value)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index)
  return bytes
}

const CMS_ENVELOPED_DATA_OID = [0x06, 0x09, 0x2a, 0x86, 0x48, 0x86, 0xf7, 0x0d, 0x01, 0x07, 0x03]

function bytesIncludeSequence(bytes: Uint8Array, sequence: number[], limit = bytes.length): boolean {
  const end = Math.min(bytes.length, limit)
  if (!sequence.length || end < sequence.length) return false
  for (let index = 0; index <= end - sequence.length; index += 1) {
    let ok = true
    for (let offset = 0; offset < sequence.length; offset += 1) {
      if (bytes[index + offset] !== sequence[offset]) {
        ok = false
        break
      }
    }
    if (ok) return true
  }
  return false
}

function looksLikeCmsEnvelopedData(bytes: Uint8Array): boolean {
  return bytes.length > 128 && bytes[0] === 0x30 && bytesIncludeSequence(bytes, CMS_ENVELOPED_DATA_OID, 512)
}

function assertLocalPecAttoEncBase64(localPayload: Record<string, unknown>): void {
  const attachments = Array.isArray(localPayload.attachments) ? localPayload.attachments : []
  const attoEnc = attachments.find((item) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) return false
    return recordText(item as Record<string, unknown>, 'filename').toLowerCase() === 'atto.enc'
  })
  if (!attoEnc || typeof attoEnc !== 'object' || Array.isArray(attoEnc)) {
    throw new Error('Pacchetto deposito mancante. Rigenera la prova deposito prima dell’invio reale.')
  }
  const contentBase64 = recordText(attoEnc as Record<string, unknown>, 'content_base64').trim()
  if (!contentBase64) {
    throw new Error('Pacchetto deposito non leggibile. Rigenera la prova deposito prima dell’invio reale.')
  }
  let decoded: Uint8Array
  try {
    decoded = base64ToUint8Array(contentBase64)
  } catch {
    throw new Error('Pacchetto deposito non valido. Rigenera la prova deposito prima dell’invio reale.')
  }
  if (!decoded.length || !looksLikeCmsEnvelopedData(decoded)) {
    throw new Error('Pacchetto deposito non conforme. Rigenera la prova prima dell’invio reale.')
  }
  if (!recordBool(attoEnc as Record<string, unknown>, 'ministerial_busta_verified')) {
    throw new Error('Pacchetto deposito non verificato. Ripeti Simula invio PEC prima dell’invio reale.')
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

const LOCAL_SIGNER_RESTART_URI = 'iusentra-local-signer://restart'
const LOCAL_SIGNER_UPDATE_URI = 'iusentra-local-signer://update'
const LOCAL_SIGNER_BATCH_TIMEOUT_MS = 45000
const LOCAL_SIGNER_BROWSER_PROBE_TIMEOUT_MS = 9000
const LOCAL_SIGNER_DEFAULT_BASE_URLS = ['http://127.0.0.1:27272', 'http://localhost:27272']

function isDesktopLocalSignerHost(): boolean {
  if (typeof navigator === 'undefined') return true
  const userAgent = String(navigator.userAgent || '').toLowerCase()
  const platformName = String(navigator.platform || '').toLowerCase()
  const isMobileOrTablet = /android|iphone|ipad|ipod|mobile|tablet|silk|kindle/.test(userAgent)
  const isIpadDesktopMode = platformName.includes('mac') && Number(navigator.maxTouchPoints || 0) > 1
  return !isMobileOrTablet && !isIpadDesktopMode
}

function canRequestLocalSignerProtocol(): boolean {
  if (!isDesktopLocalSignerHost()) return false
  if (typeof navigator === 'undefined') return true
  const activation = (navigator as Navigator & { userActivation?: { isActive?: boolean } }).userActivation
  return activation?.isActive !== false
}

function requestLocalSignerStart(): boolean {
  if (!canRequestLocalSignerProtocol()) return false
  const link = document.createElement('a')
  link.href = LOCAL_SIGNER_RESTART_URI
  link.rel = 'noreferrer'
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  window.setTimeout(() => link.remove(), 1500)
  return true
}

function requestLocalSignerUpdate(): boolean {
  if (!canRequestLocalSignerProtocol()) return false
  const link = document.createElement('a')
  link.href = LOCAL_SIGNER_UPDATE_URI
  link.rel = 'noreferrer'
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  window.setTimeout(() => link.remove(), 1500)
  return true
}

function localSignerTokenLabel(token?: LocalSignerToken): string {
  if (!token) return ''
  return [token.label, token.manufacturer, token.model].filter(Boolean).join(' - ') || 'Dispositivo USB'
}

function localSignerWindowsCertificate(status?: LocalSignerStatus | null): LocalSignerWindowsCertificate | null {
  const cert = status?.certificato_windows_firma_selezionato || status?.certificato_windows_selezionato
  return cert?.thumbprint ? cert : null
}

function localSignerWindowsCertificateLabel(cert?: LocalSignerWindowsCertificate | null): string {
  if (!cert) return ''
  return cert.soggetto || cert.soggetto_completo || 'Certificato Windows'
}

type VisibleSignatureMode = 'laterale' | 'basso_sinistra' | 'basso_destra'
const visibleSignatureOptions: Array<{ value: VisibleSignatureMode; label: string }> = [
  { value: 'laterale', label: 'Laterale verticale' },
  { value: 'basso_sinistra', label: 'In basso a sinistra' },
  { value: 'basso_destra', label: 'In basso a destra' },
]
type VisibleSignatureDatetimeMode = 'data_ora' | 'solo_data' | 'nessuna'
const visibleSignatureDatetimeOptions: Array<{ value: VisibleSignatureDatetimeMode; label: string }> = [
  { value: 'data_ora', label: 'Data e ora' },
  { value: 'solo_data', label: 'Solo data' },
  { value: 'nessuna', label: 'Senza data' },
]
const visibleSignatureStorageKey = 'hacs.firma_visibile.mode'
const visibleSignatureDatetimeStorageKey = 'hacs.firma_visibile.data_ora'

declare global {
  interface Window {
    __IUSENTRA_LOCAL_SIGNER_URL__?: string
    __IUSENTRA_LOCAL_SIGNER_LATEST_VERSION__?: string
  }
}

function normalizeLocalSignerBaseUrl(value?: string): string {
  return String(value || '').trim().replace(/\/+$/, '')
}

function localSignerCandidateBaseUrls(): string[] {
  const configured = typeof window !== 'undefined' ? normalizeLocalSignerBaseUrl(window.__IUSENTRA_LOCAL_SIGNER_URL__) : ''
  const urls = configured ? [configured, ...LOCAL_SIGNER_DEFAULT_BASE_URLS] : LOCAL_SIGNER_DEFAULT_BASE_URLS
  return Array.from(new Set(urls.map((url) => normalizeLocalSignerBaseUrl(url)).filter(Boolean)))
}

function localSignerBaseUrl(): string {
  return localSignerCandidateBaseUrls()[0] || LOCAL_SIGNER_DEFAULT_BASE_URLS[0]
}

function localSignerEndpoint(path: string, baseUrl = localSignerBaseUrl()): string {
  const suffix = path.startsWith('/') ? path : `/${path}`
  return `${normalizeLocalSignerBaseUrl(baseUrl)}${suffix}`
}

function localSignerStatusBaseUrl(status?: LocalSignerStatus | null): string {
  return normalizeLocalSignerBaseUrl(status?.__iusentra_base_url) || localSignerBaseUrl()
}

function localSignerEndpointForStatus(path: string, status?: LocalSignerStatus | null): string {
  return localSignerEndpoint(path, localSignerStatusBaseUrl(status))
}

function localSignerEndpointForPayload(endpoint: string, path: string, status?: LocalSignerStatus | null): string {
  const fallback = localSignerEndpointForStatus(path, status)
  const raw = String(endpoint || '').trim()
  if (!raw) return fallback
  try {
    const parsed = new URL(raw)
    if (['127.0.0.1', 'localhost'].includes(parsed.hostname) && (!parsed.port || parsed.port === '27272')) {
      return `${localSignerStatusBaseUrl(status)}${parsed.pathname}${parsed.search}${parsed.hash}`
    }
  } catch {
    return raw
  }
  return raw
}

function localSignerProbeFailureMessage(status: LocalSignerStatus | null | undefined, action: string): string {
  const probes = Array.isArray(status?.__iusentra_probe_urls) ? status?.__iusentra_probe_urls?.join(', ') : ''
  const detail = String(status?.__iusentra_last_error || status?.messaggio || status?.error || '').trim()
  const suffix = [probes ? `Endpoint provati: ${probes}.` : '', detail ? `Dettaglio browser: ${detail}.` : ''].filter(Boolean).join(' ')
  return `Local Signer non raggiungibile dal browser per ${action}. Avvia il servizio locale sul PC in uso e ripeti la prova deposito.${suffix ? ` ${suffix}` : ''}`
}

function localSignerLatestVersion(): string {
  if (typeof window === 'undefined') return ''
  const configured = window.__IUSENTRA_LOCAL_SIGNER_LATEST_VERSION__
  const monitor = document.getElementById('iusentra-local-signer-monitor') as HTMLElement | null
  return String(configured || monitor?.dataset.latestVersion || '').trim()
}

function compareLocalSignerVersions(left: string, right: string): number {
  const parse = (value: string) => String(value || '').split('.').map((part) => Number.parseInt(part, 10) || 0)
  const a = parse(left)
  const b = parse(right)
  const max = Math.max(a.length, b.length)
  for (let index = 0; index < max; index += 1) {
    const delta = (a[index] || 0) - (b[index] || 0)
    if (delta !== 0) return delta
  }
  return 0
}

function localSignerInstalledVersion(status?: LocalSignerStatus | null): string {
  return String(status?.versione || status?.version || '').trim()
}

function localSignerStatusOutdated(status?: LocalSignerStatus | null): boolean {
  const latest = localSignerLatestVersion()
  const installed = localSignerInstalledVersion(status)
  return Boolean(latest && installed && compareLocalSignerVersions(installed, latest) < 0)
}

function localSignerNeedsRestart(status?: LocalSignerStatus | null): boolean {
  return Boolean((status?.token_probe_fresh?.length && !status?.token?.length) || (status?.riavvio_signer_consigliato && !status?.token?.length))
}

function localSignerStatusCanSign(status?: LocalSignerStatus | null): boolean {
  return Boolean((status?.token?.[0] || localSignerWindowsCertificate(status)) && !localSignerNeedsRestart(status) && !localSignerStatusOutdated(status))
}

async function fetchLocalSignerStatus(timeoutMs = 3500): Promise<LocalSignerStatus | null> {
  const candidateBaseUrls = localSignerCandidateBaseUrls()
  const candidateEndpoints = candidateBaseUrls.length
    ? candidateBaseUrls.map((baseUrl) => ({ baseUrl, endpoint: localSignerEndpoint('/ping', baseUrl) }))
    : [{ baseUrl: localSignerBaseUrl(), endpoint: localSignerEndpoint('/ping') }]
  let lastError = ''
  for (const candidate of candidateEndpoints) {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
    try {
      const requestOptions: LocalNetworkRequestInit = {
        cache: 'no-store',
        mode: 'cors',
        targetAddressSpace: 'local',
        signal: controller.signal,
      }
      const response = await fetch(candidate.endpoint, requestOptions)
      const payload = await response.json().catch(() => ({} as LocalSignerStatus))
      return {
        ...payload,
        ok: response.ok ? payload.ok : false,
        __iusentra_base_url: candidate.baseUrl,
        __iusentra_probe_urls: candidateEndpoints.map((item) => item.endpoint),
      }
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error || '')
    } finally {
      window.clearTimeout(timeout)
    }
  }
  return {
    ok: false,
    messaggio: 'Local Signer non rilevato su questo PC.',
    __iusentra_base_url: localSignerBaseUrl(),
    __iusentra_probe_urls: candidateEndpoints.map((item) => item.endpoint),
    __iusentra_last_error: lastError,
  }
}

async function pollLocalSignerStatus(
  attempts = 10,
  delayMs = 900,
  minimumVersion = '',
  maxDurationMs = 0,
): Promise<LocalSignerStatus | null> {
  const startedAt = Date.now()
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (maxDurationMs > 0 && Date.now() - startedAt >= maxDurationMs) break
    if (attempt > 0) await sleep(delayMs)
    const payload = await fetchLocalSignerStatus(minimumVersion ? 1500 : 3500)
    const installedVersion = localSignerInstalledVersion(payload)
    if (
      payload
      && payload.ok !== false
      && (!minimumVersion || (installedVersion && compareLocalSignerVersions(installedVersion, minimumVersion) >= 0))
    ) return payload
  }
  return null
}

async function recoverLocalSignerAutomatically(
  status: LocalSignerStatus,
  options: LocalSignerRecoveryOptions = {},
): Promise<LocalSignerStatus> {
  if (localSignerStatusOutdated(status)) {
    const latest = localSignerLatestVersion()
    const installed = localSignerInstalledVersion(status)
    options.onMessage?.(`Local Signer ${installed || 'installato'} da aggiornare alla versione ${latest}. IUSENTRA avvia l'aggiornamento automatico e ricontrolla il servizio.`)
    try {
      const updateRequestOptions: LocalNetworkRequestInit = {
        method: 'POST',
        cache: 'no-store',
        mode: 'cors',
        targetAddressSpace: 'local',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ base_url: window.location.origin }),
      }
      const updateResponse = await fetch(localSignerEndpointForStatus('/update', status), updateRequestOptions)
      const updatePayload = await updateResponse.json().catch(() => ({} as Record<string, unknown>))
      if (!updateResponse.ok || updatePayload.ok === false) throw new Error('Aggiornamento locale non avviato')
    } catch {
      requestLocalSignerUpdate()
    }
    const updated = await pollLocalSignerStatus(240, 1500, latest, 360000)
    return updated || status
  }
  if (localSignerNeedsRestart(status)) {
    options.onMessage?.('IUSENTRA sta riallineando automaticamente Local Signer perché il dispositivo di firma è stato rilevato da un controllo fresco.')
    requestLocalSignerStart()
    const restarted = await pollLocalSignerStatus(12, 900)
    return restarted || status
  }
  return status
}

function normalizeVisibleSignatureMode(value?: string): VisibleSignatureMode {
  const raw = String(value || '').trim().toLowerCase().replace(/[-\s]+/g, '_')
  if (['bottom_left', 'left', 'sinistra', 'sx', 'basso_sx'].includes(raw)) return 'basso_sinistra'
  if (['bottom_right', 'right', 'destra', 'dx', 'basso_dx'].includes(raw)) return 'basso_destra'
  if (['laterale', 'side', 'verticale', 'margine', 'margine_destro', 'laterale_dx'].includes(raw)) return 'laterale'
  return raw === 'basso_sinistra' || raw === 'basso_destra' ? raw : 'laterale'
}

function normalizeVisibleSignatureDatetimeMode(value?: string): VisibleSignatureDatetimeMode {
  const raw = String(value || '').trim().toLowerCase().replace(/[-\s]+/g, '_')
  if (['solo_data', 'data', 'date', 'giorno'].includes(raw)) return 'solo_data'
  if (['nessuna', 'nessuno', 'none', 'off', 'senza_data', 'no'].includes(raw)) return 'nessuna'
  return 'data_ora'
}

function loadVisibleSignatureMode(defaultMode: string): VisibleSignatureMode {
  try {
    const stored = window.localStorage.getItem(visibleSignatureStorageKey)
    return normalizeVisibleSignatureMode(stored || defaultMode)
  } catch {
    return normalizeVisibleSignatureMode(defaultMode)
  }
}

function loadVisibleSignatureDatetimeMode(defaultMode: string): VisibleSignatureDatetimeMode {
  try {
    const stored = window.localStorage.getItem(visibleSignatureDatetimeStorageKey)
    return normalizeVisibleSignatureDatetimeMode(stored || defaultMode)
  } catch {
    return normalizeVisibleSignatureDatetimeMode(defaultMode)
  }
}

function ContributionRequirementForm({ action, onDone, onError }:{action:string; onDone:(message?:string)=>void; onError:(message:string)=>void}) {
  const [mode, setMode] = useState('')
  const requiresAmount = mode === 'pagamento_contributo_unificato' || mode === 'prenotazione_a_debito'
  const status = mode === 'esenzione_contributo_unificato' ? 'non_previsto' : requiresAmount ? 'pagato' : ''
  return (
    <JsonPostForm className="iu-fas-slot-link-form iu-fas-slot-resolution-form" action={action} onDone={onDone} onError={onError}>
      <select name="natura" value={mode} onChange={(event) => setMode(event.currentTarget.value)} required aria-label="Stato del contributo unificato">
        <option value="">Scegli lo stato</option>
        <option value="esenzione_contributo_unificato">Esente o non dovuto</option>
        <option value="pagamento_contributo_unificato">Pagato</option>
        <option value="prenotazione_a_debito">Prenotato a debito</option>
      </select>
      <input type="hidden" name="status" value={status}/>
      {requiresAmount ? <input name="importo" type="text" inputMode="decimal" placeholder="Importo, es. 259,00" required aria-label="Importo contributo unificato"/> : null}
      <button type="submit" disabled={!mode}><Save size={14}/> Salva</button>
    </JsonPostForm>
  )
}

function CaseValueRequirementForm({ action, defaultValue, onDone, onError }:{action:string; defaultValue:string; onDone:(message?:string)=>void; onError:(message:string)=>void}) {
  return (
    <JsonPostForm className="iu-fas-slot-link-form iu-fas-slot-resolution-form" action={action} onDone={onDone} onError={onError}>
      <input name="valore_causa" type="text" inputMode="decimal" defaultValue={defaultValue} placeholder="Valore, es. 500,00" required aria-label="Valore della causa"/>
      <button type="submit"><Save size={14}/> Salva</button>
    </JsonPostForm>
  )
}

function JsonPostForm({
  action,
  className,
  children,
  redirectTo,
  encType,
  onDone,
  onError,
}: {
  action: string
  className?: string
  children: ReactNode
  redirectTo?: string
  encType?: string
  onDone?: (message?: string) => void
  onError?: (message: string) => void
}) {
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  if (!action) return null
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setBusy(true)
    setMessage('Salvataggio in corso...')
    try {
      const result = await submitFormJson(action, new FormData(event.currentTarget))
      const nextMessage = result.message || 'Operazione completata.'
      setMessage(nextMessage)
      if (onDone) {
        onDone(nextMessage)
      } else {
        redirectAfterSuccess(result, redirectTo || window.location.href)
      }
    } catch (error) {
      const nextMessage = error instanceof Error ? error.message : 'Operazione non riuscita.'
      setMessage(nextMessage)
      onError?.(nextMessage)
    } finally {
      setBusy(false)
    }
  }
  return (
    <form className={className} onSubmit={submit} encType={encType} data-busy={busy ? 'true' : undefined}>
      {children}
      {message ? <span className="iu-fas-inline-error" role="status">{message}</span> : null}
    </form>
  )
}

function DocumentRow({ doc, onPreview, onDone, onError }:{doc:FascicoloDocument; onPreview:(preview:PreviewDocument)=>void; onDone:(message?:string)=>void; onError:(message:string)=>void}) {
  const [renaming, setRenaming] = useState(false)
  const [draftName, setDraftName] = useState(doc.name)
  const [renameBusy, setRenameBusy] = useState(false)
  const [renameMessage, setRenameMessage] = useState('')
  const tags = visibleDocumentTags(doc)
  const catalogTone: FascicoloRow['tone'] =
    doc.catalogSection === 'atti' ? 'primary'
      : doc.catalogSection === 'provvedimenti' ? 'purple'
        : doc.catalogSection === 'comunicazioni' ? 'info'
          : doc.catalogSection === 'pagamenti' ? 'success'
            : doc.catalogSection === 'allegati' ? 'neutral'
              : 'warning'

  const startRename = () => {
    setDraftName(doc.name)
    setRenameMessage('')
    setRenaming(true)
  }

  const submitRename = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!doc.actions.rename || renameBusy) return
    const value = draftName.trim()
    if (!value) {
      setRenameMessage('Indica il nuovo nome del documento.')
      return
    }
    setRenameBusy(true)
    setRenameMessage('')
    const formData = new FormData()
    formData.set('nome_file', value)
    try {
      const response = await fetch(doc.actions.rename, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          Accept: 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrfToken(),
        },
        body: formData,
      })
      const payload = await response.json().catch(() => ({})) as Record<string, unknown>
      const message = String(payload.message || payload.messaggio || '')
      if (!response.ok || payload.ok === false) throw new Error(message || 'Rinomina non completata.')
      setRenaming(false)
      onDone(message || 'Nome documento aggiornato.')
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Rinomina non completata.'
      setRenameMessage(message)
      onError(message)
    } finally {
      setRenameBusy(false)
    }
  }

  return (
    <article className="iu-fas-doc-row">
      <div className="iu-fas-doc-icon-cell">
        <FileText size={18}/>
        {doc.actions.rename ? (
          <button type="button" title="Rinomina file" aria-label={`Rinomina file ${doc.name}`} onClick={startRename}>
            <PencilLine size={13}/>
          </button>
        ) : null}
      </div>
      <div><strong>{doc.name}</strong><span>{doc.type} · {doc.size || 'dimensione n.d.'} · {doc.documentDate || doc.uploadedAt || 'data n.d.'}</span>{doc.notes ? <p>{doc.notes}</p> : null}{tags.length ? <em>{tags.join(', ')}</em> : null}</div>
      {renaming ? (
        <form className="iu-fas-doc-rename-form" onSubmit={submitRename}>
          <input value={draftName} onChange={(event) => setDraftName(event.currentTarget.value)} aria-label={`Nuovo nome file ${doc.name}`} />
          <button type="submit" disabled={renameBusy}>{renameBusy ? 'Salvo...' : 'Salva nome'}</button>
          <button type="button" onClick={() => setRenaming(false)} disabled={renameBusy}>Annulla</button>
          {renameMessage ? <small>{renameMessage}</small> : null}
        </form>
      ) : null}
      <div className="iu-fas-doc-badges"><Badge tone={doc.statusTone}>{doc.statusLabel || (doc.signed ? 'Firmato' : 'Da firmare')}</Badge>{doc.catalogLabel && doc.catalogConfidence >= 70 ? <Badge tone={catalogTone}>{doc.catalogLabel}</Badge> : null}{doc.source ? <Badge tone="neutral">{doc.source}</Badge> : null}{doc.portalClass ? <Badge tone="info">{doc.portalClass}</Badge> : null}</div>
      <div className="iu-fas-actions iu-fas-actions--wrap">
        {doc.actions.preview ? <button type="button" title="Anteprima interna" onClick={() => onPreview({ name: doc.name, url: doc.actions.preview, downloadUrl: doc.actions.download })}><Eye size={15}/></button> : null}
        {doc.actions.download ? <a href={doc.actions.download} title="Scarica"><Download size={15}/></a> : null}
        {doc.actions.edit ? <a href={doc.actions.edit} title="Modifica documento" aria-label={`Modifica documento ${doc.name}`}><PencilLine size={15}/></a> : null}
        {doc.actions.sign ? <a href={doc.actions.sign} title="Firma digitale"><ShieldCheck size={15}/></a> : null}
        {doc.actions.attest ? <PostAction action={doc.actions.attest} tone="secondary" onDone={onDone} onError={onError}><BadgeCheck size={14}/></PostAction> : null}
        {doc.actions.pdfa ? <PostAction action={doc.actions.pdfa} tone="secondary" confirm="Convertire il documento in PDF/A-2B?" confirmTitle="Conversione PDF/A" onDone={onDone} onError={onError}><FileCheck2 size={14}/></PostAction> : null}
        {doc.actions.delete ? <PostAction action={doc.actions.delete} tone="danger" confirm="Eliminare il documento dal fascicolo?" confirmTitle="Elimina documento" onDone={onDone} onError={onError}><Trash2 size={14}/></PostAction> : null}
      </div>
    </article>
  )
}

export function FascicoloDepositoPage({ id }: { id: string }) {
  return <DepositPreparePage id={id} />
}
