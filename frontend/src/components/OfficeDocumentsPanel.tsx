import { useEffect, useMemo, useRef, useState } from 'react'
import { CheckCircle2, Download, FileText, FolderSearch2, ShieldCheck } from 'lucide-react'
import type { FascicoloDetailData, FascicoloDocument } from '../fascicoliData'
import { formatDateIt } from '../formatting'
import { pstMinisterialProfileFromParts } from '../lib/pstMinisterialProfile'

type JsonRecord = Record<string, unknown>
type DocumentMode = 'copia' | 'originale'

type OfficeDocument = {
  key: string
  name: string
  type: string
  date: string
  parentId: string
  parentName: string
  isAttachment: boolean
  acquired: boolean
  raw: JsonRecord
}

type Certificate = {
  thumbprint: string
  fiscalCode: string
}

type LocalNetworkRequestInit = RequestInit & { targetAddressSpace?: 'loopback' }

type PstSession = {
  sessionId: string
  officeCode: string
  certThumbprint: string
  expiresAt: number
}

export type OfficeDocumentsOpenRequest = {
  requestId: number
}

type Props = {
  data: FascicoloDetailData
  onDone: (message?: string) => void
  onError: (message: string) => void
  openOfficeDocumentsRequest?: OfficeDocumentsOpenRequest | null
}

const CERT_KEY = 'iusentra.react.pst.cert.v2'
const LEGACY_VIEW_SESSION_KEY = 'iusentra.react.pst.session.v2'
const VIEW_SESSION_KEY = 'iusentra.react.pst.session.view.v3'
const LOCAL_SIGNER_BASES = ['http://127.0.0.1:27272', 'http://localhost:27272']
const JOB_TIMEOUT_MS = 360_000
const DOWNLOAD_TIMEOUT_MS = 480_000

type LocalSignerTransport = 'fetch' | 'xhr'
type LocalSignerRoute = { baseUrl: string; transport: LocalSignerTransport }

let localSignerRoute: LocalSignerRoute | null = null
let localSignerRouteProbe: Promise<LocalSignerRoute> | null = null

function isRecord(value: unknown): value is JsonRecord {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function record(value: unknown): JsonRecord {
  return isRecord(value) ? value : {}
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function text(value: unknown, fallback = ''): string {
  const result = String(value ?? '').trim()
  return result || fallback
}

function number(value: unknown): number {
  const result = Number(value ?? 0)
  return Number.isFinite(result) ? result : 0
}

function readStored(key: string): JsonRecord {
  try {
    return record(JSON.parse(window.sessionStorage.getItem(key) || '{}'))
  } catch {
    return {}
  }
}

function writeStored(key: string, value: JsonRecord) {
  try {
    window.sessionStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Il browser può disabilitare sessionStorage; la richiesta corrente resta valida.
  }
}

function certificateFrom(value: unknown): Certificate | null {
  const root = record(value)
  const row = record(root.certificato_windows_selezionato || root.certificato || root)
  const thumbprint = text(row.thumbprint)
  if (!thumbprint) return null
  const subject = `${text(row.codice_fiscale)} ${text(row.codiceFiscale)} ${text(row.soggetto)} ${text(row.soggetto_completo)}`.toUpperCase()
  return {
    thumbprint,
    fiscalCode: subject.match(/\b[A-Z]{6}[0-9A-Z]{2}[A-Z][0-9A-Z]{2}[A-Z][0-9A-Z]{3}[A-Z]\b/)?.[0] || '',
  }
}

function sessionFrom(
  value: unknown,
  officeCode: string,
  cert: Certificate,
  purpose: 'view' | 'import',
): PstSession | null {
  const row = record(value)
  const returnedPurpose = text(row.purpose || row.session_purpose).toLowerCase()
  if (returnedPurpose && returnedPurpose !== purpose) return null
  const sessionId = purpose === 'import'
    ? text(row.import_session_id || row.download_session_id || row.sessionId || row.session_id || row.pst_session_id)
    : text(row.view_session_id || row.sessionId || row.session_id || row.pst_session_id)
  if (!sessionId) return null
  const rawExpiry = purpose === 'import'
    ? number(row.import_expires_at || row.download_expires_at || row.expiresAt || row.expires_at)
    : number(row.view_expires_at || row.expiresAt || row.expires_at)
  const expiresAt = rawExpiry > 0 ? (rawExpiry < 100_000_000_000 ? rawExpiry * 1000 : rawExpiry) : Date.now() + 1_800_000
  const session: PstSession = {
    sessionId,
    officeCode: text(row.tribunale || row.codice_ufficio || officeCode),
    certThumbprint: text(row.certThumbprint || row.cert_thumbprint || row.cert_key || cert.thumbprint),
    expiresAt,
  }
  if (session.expiresAt < Date.now()) return null
  if (session.certThumbprint && cert.thumbprint && session.certThumbprint.toUpperCase() !== cert.thumbprint.toUpperCase()) return null
  if (session.officeCode && officeCode && session.officeCode !== officeCode) return null
  return session
}

function localXhrRequest(endpoint: string, body?: JsonRecord, timeoutMs = 45_000): Promise<JsonRecord> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest()
    request.open(body ? 'POST' : 'GET', endpoint, true)
    request.timeout = timeoutMs
    request.setRequestHeader('Accept', 'application/json')
    request.setRequestHeader('X-Requested-With', 'XMLHttpRequest')
    if (body) request.setRequestHeader('Content-Type', 'application/json')
    request.onload = () => {
      let payload: JsonRecord = {}
      try {
        payload = record(JSON.parse(request.responseText || '{}'))
      } catch {
        reject(new Error('Risposta non valida dal servizio locale.'))
        return
      }
      if (request.status < 200 || request.status >= 300 || payload.ok === false) {
        reject(new Error(text(payload.errore || payload.error || payload.message, 'Operazione locale non completata.')))
        return
      }
      resolve(payload)
    }
    request.onerror = () => reject(new Error('Collegamento al servizio locale non disponibile.'))
    request.ontimeout = () => reject(new Error('Tempo massimo superato durante il collegamento al servizio locale.'))
    request.send(body ? JSON.stringify(body) : null)
  })
}

async function localFetchRequest(endpoint: string, body?: JsonRecord, timeoutMs = 45_000): Promise<JsonRecord> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const requestOptions: LocalNetworkRequestInit = {
      method: body ? 'POST' : 'GET',
      cache: 'no-store',
      mode: 'cors',
      targetAddressSpace: 'loopback',
      headers: body
        ? { Accept: 'application/json', 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }
        : { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    }
    const response = await fetch(endpoint, requestOptions)
    const payload = record(await response.json().catch(() => ({})))
    if (!response.ok || payload.ok === false) throw new Error(text(payload.errore || payload.error || payload.message, 'Operazione locale non completata.'))
    return payload
  } finally {
    window.clearTimeout(timeout)
  }
}

function localRequest(
  endpoint: string,
  transport: LocalSignerTransport,
  body?: JsonRecord,
  timeoutMs = 45_000,
): Promise<JsonRecord> {
  return transport === 'fetch'
    ? localFetchRequest(endpoint, body, timeoutMs)
    : localXhrRequest(endpoint, body, timeoutMs)
}

async function resolveLocalSignerRoute(): Promise<LocalSignerRoute> {
  if (localSignerRoute) return localSignerRoute
  if (localSignerRouteProbe) return localSignerRouteProbe

  const probe = (async () => {
    let lastError: unknown = null
    for (const baseUrl of LOCAL_SIGNER_BASES) {
      for (const transport of ['fetch', 'xhr'] as const) {
        try {
          await localRequest(`${baseUrl}/ping?light=1`, transport, undefined, 3_500)
          const resolved = { baseUrl, transport }
          localSignerRoute = resolved
          return resolved
        } catch (error) {
          lastError = error
        }
      }
    }
    const reason = lastError instanceof Error && lastError.name !== 'AbortError'
      ? lastError.message
      : 'tempo massimo superato'
    throw new Error(`Local Signer non raggiungibile dal browser. Verifica che sia avviato sul PC in uso e riprova. Dettaglio: ${reason}`)
  })()
  localSignerRouteProbe = probe
  try {
    return await probe
  } finally {
    if (localSignerRouteProbe === probe) localSignerRouteProbe = null
  }
}

async function localSignerJson(path: string, body?: JsonRecord, timeoutMs = 45_000): Promise<JsonRecord> {
  const route = await resolveLocalSignerRoute()
  try {
    // I POST operativi partono una sola volta sul trasporto già scelto con il ping GET.
    // Un errore invalida la cache per l'azione successiva, senza ripetere questa richiesta.
    return await localRequest(`${route.baseUrl}${path}`, route.transport, body, timeoutMs)
  } catch (error) {
    if (localSignerRoute === route) localSignerRoute = null
    const reason = error instanceof Error && error.name !== 'AbortError' ? error.message : 'tempo massimo superato'
    throw new Error(`Operazione Local Signer non completata. Dettaglio: ${reason}`)
  }
}

async function serverJson(path: string, body?: JsonRecord): Promise<JsonRecord> {
  const response = await fetch(path, {
    method: body ? 'POST' : 'GET',
    credentials: 'same-origin',
    headers: body ? { Accept: 'application/json', 'Content-Type': 'application/json' } : { Accept: 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  const payload = record(await response.json().catch(() => ({})))
  if (!response.ok || payload.ok === false) throw new Error(text(payload.errore || payload.error || payload.message, 'Operazione non completata.'))
  return payload
}

type LocalSignerJsonRequest = (path: string, body?: JsonRecord, timeoutMs?: number) => Promise<JsonRecord>

async function ensureCertificate(request: LocalSignerJsonRequest): Promise<Certificate> {
  const stored = certificateFrom(readStored(CERT_KEY))
  if (stored) return stored
  try {
    const automatic = certificateFrom(await request('/ping?auto=1', undefined, 8_000))
    if (automatic) {
      writeStored(CERT_KEY, { thumbprint: automatic.thumbprint, codiceFiscale: automatic.fiscalCode })
      return automatic
    }
  } catch {
    // La selezione esplicita restituisce il messaggio operativo del servizio locale.
  }
  const selected = certificateFrom(await request('/seleziona-certificato?auto=1', undefined, 120_000))
  if (!selected) throw new Error('Seleziona il certificato CNS/CIE per l’accesso al PST e riprova.')
  writeStored(CERT_KEY, { thumbprint: selected.thumbprint, codiceFiscale: selected.fiscalCode })
  return selected
}

function documentIds(row: JsonRecord): string[] {
  return [
    row.id_documento, row.id_documento_portale, row.idDocumento, row.idDoc,
    row.id_cat, row.idCat, row.id_repeatto, row.idRepeatto, row.idRepeatTo,
    row.msg_id, row.msgId, row.msgid,
  ].map((value) => text(value).toLowerCase()).filter(Boolean)
}

function localDocumentIds(doc: FascicoloDocument): string[] {
  return [doc.portalDocumentId, doc.portalIdCat, doc.portalIdRepeatto, doc.portalMessageId]
    .map((value) => text(value).toLowerCase()).filter(Boolean)
}

function flattenDocuments(rows: unknown[], localDocuments: FascicoloDocument[], parent?: JsonRecord): OfficeDocument[] {
  const localIds = new Set(localDocuments.flatMap(localDocumentIds))
  const result: OfficeDocument[] = []
  rows.forEach((value, index) => {
    const source = record(value)
    const row = parent && !text(source.parent_id_documento || source.id_documento_padre)
      ? {
          ...source,
          parent_id_documento: text(parent.id_documento || parent.id_cat || parent.id_repeatto),
          parent_nome: text(parent.nome || parent.nome_documento),
          is_allegato: true,
        }
      : source
    const ids = documentIds(row)
    const name = text(row.nome || row.nome_documento || row.nome_file_originale, `Documento ${index + 1}`)
    const key = ids[0] || `${name.toLowerCase()}::${text(row.data_documento || row.data_deposito)}::${index}`
    result.push({
      key,
      name,
      type: text(row.tipo_atto || row.tipo, 'Documento'),
      date: text(row.data_documento || row.data_deposito || row.data),
      parentId: text(row.parent_id_documento || row.id_documento_padre),
      parentName: text(row.parent_nome),
      isAttachment: Boolean(row.is_allegato || row.parent_id_documento || row.id_documento_padre || parent),
      acquired: ids.some((id) => localIds.has(id)),
      raw: row,
    })
    const children = [row.allegati, row.attachments, row.children, row.documenti_collegati, row.docs_secondari]
      .flatMap((items) => list(items))
    if (children.length) result.push(...flattenDocuments(children, localDocuments, row))
  })
  const seen = new Set<string>()
  return result.filter((item) => {
    if (seen.has(item.key)) return false
    seen.add(item.key)
    return true
  })
}

/**
 * Il PST può esporre lo stesso catalogo in più rami della risposta unica
 * (sommario, catalogo e sezione documenti). Li ricompattiamo per id prima
 * della visualizzazione: nessun ramo parziale deve nascondere documenti
 * restituiti dal medesimo batch autenticato.
 */
function completeCatalogRows(snapshot: JsonRecord, result: JsonRecord): unknown[] {
  const sections = record(snapshot.sezioni)
  const rows = [
    ...list(snapshot.documenti),
    ...list(snapshot.catalogo),
    ...list(snapshot.documents),
    ...list(sections.documenti_fascicolo),
    ...list(result.documenti),
    ...list(result.catalogo),
    ...list(result.documents),
  ]
  const merged = new Map<string, unknown>()
  rows.forEach((value, index) => {
    const row = record(value)
    const ids = documentIds(row)
    const name = text(row.nome || row.nome_documento || row.nome_file_originale)
    const date = text(row.data_documento || row.data_deposito || row.data)
    const key = ids[0] || (name ? `${name.toLowerCase()}::${date}` : `riga-${index}`)
    const existing = record(merged.get(key))
    merged.set(key, Object.keys(existing).length ? { ...existing, ...row } : row)
  })
  return [...merged.values()]
}
function downloadableDocument(row: JsonRecord, mode: DocumentMode): JsonRecord {
  const original = mode === 'originale'
  return {
    ...row,
    id_documento: text(row.id_documento || row.id_documento_portale || row.idDocumento || row.idDoc),
    nome_documento: text(row.nome || row.nome_documento || row.nome_file_originale),
    id_cat: text(row.id_cat || row.idCat),
    id_repeatto: text(row.id_repeatto || row.idRepeatto || row.idRepeatTo),
    msg_id: text(row.msg_id || row.msgId || row.msgid),
    original,
    original_documento_portale: original,
    modalita_documento_portale: mode,
  }
}

function pstOperationId(purpose: 'view' | 'import' | 'download'): string {
  const token = typeof window.crypto?.randomUUID === 'function'
    ? window.crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
  return `office-documents-${purpose}-${token}`
}

function sessionPayload(session: PstSession, cert: Certificate, purpose: 'view' | 'import'): JsonRecord {
  return {
    session_id: session.sessionId,
    pst_session_id: session.sessionId,
    purpose,
    cert_thumbprint: cert.thumbprint,
    cert_key: cert.thumbprint,
    expires_at: session.expiresAt,
  }
}

function savePstFileToBrowser(file: JsonRecord): boolean {
  const encoded = text(file.contenuto_b64 || file.content_base64 || file.base64)
  if (!encoded) return false
  try {
    const binary = window.atob(encoded.includes(',') ? encoded.slice(encoded.indexOf(',') + 1) : encoded)
    const bytes = new Uint8Array(binary.length)
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index)
    const blob = new Blob([bytes], { type: text(file.content_type, 'application/octet-stream') })
    const href = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = href
    link.download = text(file.nome || file.filename || file.name, 'documento-portale').replace(/[\\/:*?"<>|]/g, '_')
    link.hidden = true
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.setTimeout(() => window.URL.revokeObjectURL(href), 2_000)
    return true
  } catch {
    return false
  }
}

function formatWait(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const minuti = Math.floor(seconds / 60)
  const resto = seconds % 60
  return `${minuti} min ${String(resto).padStart(2, '0')}s`
}

// Il PST non espone un avanzamento reale: al posto di una percentuale finta si
// dice all'utente cosa aspettarsi e, se il portale tarda, che sta ancora lavorando.
// Il primo messaggio riguarda il PIN: Windows non sempre concede il primo piano al
// prompt del provider CNS, che resta lampeggiante nella barra delle applicazioni.
function searchWaitHint(seconds: number): string {
  if (seconds < 25) return 'Se la richiesta del PIN non compare in primo piano, guarda la barra delle applicazioni: Windows la apre lampeggiante quando non le concede il fuoco.'
  if (seconds < 60) return 'Il portale ministeriale risponde a lotti: di norma servono da uno a tre minuti.'
  if (seconds < 150) return 'Consultazione ancora in corso. Non chiudere la pagina: il PIN non verrà richiesto una seconda volta.'
  return 'Il portale ministeriale sta rispondendo lentamente, ma l’operazione prosegue. Si interrompe da sola se supera i sei minuti.'
}

export function OfficeDocumentsPanel({ data, onDone, onError, openOfficeDocumentsRequest = null }: Props) {
  const [documents, setDocuments] = useState<OfficeDocument[]>([])
  const [snapshot, setSnapshot] = useState<JsonRecord>({})
  const [selection, setSelection] = useState<string[]>([])
  const [modes, setModes] = useState<Record<string, DocumentMode>>({})
  const [viewSession, setViewSession] = useState<PstSession | null>(null)
  const [busy, setBusy] = useState<'search' | 'import' | 'download' | ''>('')
  const [message, setMessage] = useState('')
  const [downloadProgress, setDownloadProgress] = useState({ completed: 0, total: 0, current: '' })
  const [searchProgress, setSearchProgress] = useState({ completed: 0, total: 4, phase: '', current: '' })
  const [searchStartedAt, setSearchStartedAt] = useState(0)
  const [searchElapsed, setSearchElapsed] = useState(0)
  const searchFlight = useRef<Promise<void> | null>(null)
  const downloadFlight = useRef<Promise<void> | null>(null)

  const source = data.fascicolo.sourceSnapshot
  // Stesso codice operativo del Wizard: `code` è il codice PST canonico;
  // `ministerialCode` identifica l'ufficio ma non va mandato al Local Signer.
  const officeCode = data.depositOffice.code || data.depositOffice.ministerialCode || source.ufficioCodice
  // Profilo ministeriale dedotto dal fascicolo, come fa il wizard di
  // acquisizione: si parte dai campi piu' affidabili e si scende ai
  // descrittivi solo se i primi non bastano.
  const fascicoloPstProfile = useMemo(() => {
    const candidates: unknown[][] = [
      [source.tabellaMinisteriale, source.servizioPst],
      [source.registroPortale, source.procedimento, source.subProcedimento],
      [data.fascicolo.register, data.fascicolo.procedureType, data.fascicolo.type],
      [source.oggetto, data.fascicolo.object, data.fascicolo.title, data.fascicolo.court],
    ]
    for (const parts of candidates) {
      const profile = pstMinisterialProfileFromParts(...parts)
      if (profile.tabella_ministeriale) return profile
    }
    return {}
  }, [data.fascicolo, source])
  const officeName = source.ufficioNome || data.fascicolo.court
  const rgNumber = source.numero || String(data.fascicolo.rgNumber || '')
  const rgYear = source.anno || data.fascicolo.rgYear
  const missing = [!officeCode && 'codice ufficio', !rgNumber && 'numero R.G.', !rgYear && 'anno R.G.'].filter(Boolean) as string[]
  const acquiredCount = useMemo(() => documents.filter((doc) => doc.acquired).length, [documents])
  const selectableDocuments = useMemo(() => documents.filter((doc) => !doc.acquired), [documents])
  const selectedDocuments = useMemo(() => documents.filter((doc) => selection.includes(doc.key)), [documents, selection])
  const selectedImportDocuments = useMemo(() => selectedDocuments.filter((doc) => !doc.acquired), [selectedDocuments])
  const selectAllDocuments = () => setSelection(documents.map((doc) => doc.key))
  const selectOnlyNotAcquired = () => setSelection(selectableDocuments.map((doc) => doc.key))
  const deselectAll = () => setSelection([])
  const setSelectedDocumentsMode = (mode: DocumentMode) => setModes((current) => selectedDocuments.reduce<Record<string, DocumentMode>>(
    (next, doc) => ({ ...next, [doc.key]: mode }),
    { ...current },
  ))

  // La visualizzazione usa un solo lotto autenticato: ricerca, scheda e
  // catalogo ufficiale sono restituiti da /pst/ricerca-snapshot nello stesso
  // processo Local Signer. Non viene avviato un secondo job né un secondo PIN.
  const runSearchOperation = async (operationId: string) => {
    if (missing.length) {
      onError(`Ricerca documenti non avviata: manca ${missing.join(', ')} nel fascicolo.`)
      return
    }
    setBusy('search')
    setSearchStartedAt(Date.now())
    setSearchElapsed(0)
    setSearchProgress({
      completed: 0,
      total: 4,
      phase: 'Certificato e sessione',
      current: 'Verifico il certificato CNS e apro la sessione di consultazione.',
    })
    setMessage('Consultazione diretta del fascicolo d’ufficio in corso…')
    try {
      const cert = await ensureCertificate(localSignerJson)
      setSearchProgress({
        completed: 1,
        total: 4,
        phase: 'Ricerca del fascicolo',
        current: 'Interrogo il registro ministeriale con numero e anno di R.G.',
      })
      const params = new URLSearchParams({
        id_fasc: data.fascicolo.id,
        numero: rgNumber,
        anno: String(rgYear),
        ufficio: officeName,
        ufficio_codice: officeCode,
      })
      const schemaPayload = await serverJson(`/api/v1/ui/telematico/pst/schema-hint?${params.toString()}`)
      const hint = record(schemaPayload.hint)
      setMessage('Lettura dei documenti disponibili in corso…')
      const storedSession = viewSession
        || sessionFrom(readStored(VIEW_SESSION_KEY), officeCode, cert, 'view')
        || sessionFrom(readStored(LEGACY_VIEW_SESSION_KEY), officeCode, cert, 'view')
      setSearchProgress({
        completed: 2,
        total: 4,
        phase: 'Ricerca del fascicolo',
        current: 'Lotto autenticato verso il PST, in attesa della risposta ministeriale.',
      })
      const result = await localSignerJson('/pst/ricerca-snapshot', {
        tribunale: officeCode,
        numero_rg: rgNumber,
        anno_rg: String(rgYear),
        nome_parte: '',
        cf_parte: '',
        oggetto: '',
        ufficio_nome: officeName,
        // Stessa precedenza del Wizard: rito e registro del fascicolo vengono
        // dal resolver centrale; il registro dell’ufficio è solo fallback.
        servizio_pst_preferito: text(hint.servizio_pst_preferito || hint.servizio_pst || fascicoloPstProfile.servizio_pst_preferito || source.servizioPst),
        registro_portale: text(hint.registro_portale || fascicoloPstProfile.registro_portale || source.registroPortale),
        tabella_ministeriale: text(hint.tabella_ministeriale || fascicoloPstProfile.tabella_ministeriale || source.tabellaMinisteriale),
        tipo_registro: text(hint.tipo_registro || hint.registro || fascicoloPstProfile.tipo_registro || fascicoloPstProfile.registro),
        registro: text(hint.registro || fascicoloPstProfile.registro),
        materia: text(hint.materia || fascicoloPstProfile.materia),
        schema: text(hint.schema || fascicoloPstProfile.schema),
        quick_filter: text(hint.quick_filter || fascicoloPstProfile.quick_filter),
        ruolo_polisweb: text(hint.ruolo_polisweb, 'AVV').toUpperCase(),
        cf_avvocato: cert.fiscalCode,
        cert_thumbprint: cert.thumbprint,
        cert_key: cert.thumbprint,
        operation_id: operationId,
        purpose: 'view',
        pst_session_id: storedSession?.sessionId || '',
        search_only: false,
        include_full_snapshot: true,
        single_interactive_batch: true,
      }, JOB_TIMEOUT_MS)
      const nextSnapshot = record(result.snapshot)
      const nextCert = certificateFrom(result)
        || certificateFrom(result.pst_session)
        || certificateFrom(nextSnapshot.pst_session)
        || cert
      if (nextCert.thumbprint) {
        writeStored(CERT_KEY, { thumbprint: nextCert.thumbprint, codiceFiscale: nextCert.fiscalCode })
      }
      const nextSession = sessionFrom(result, officeCode, nextCert, 'view')
        || sessionFrom(result.pst_session, officeCode, nextCert, 'view')
        || sessionFrom(nextSnapshot.pst_session, officeCode, nextCert, 'view')
        || storedSession
      if (!nextSession) throw new Error('Sessione di consultazione non inizializzata.')
      writeStored(VIEW_SESSION_KEY, {
        sessionId: nextSession.sessionId,
        purpose: 'view',
        tribunale: nextSession.officeCode,
        certThumbprint: nextSession.certThumbprint,
        expiresAt: nextSession.expiresAt,
      })
      const catalogSnapshot = nextSnapshot
      const rows = completeCatalogRows(nextSnapshot, result)
      const nextDocuments = flattenDocuments(rows, data.documents)
      setSearchProgress({
        completed: 4,
        total: 4,
        phase: 'Fascicolo visualizzato',
        current: 'Catalogo ricevuto nel lotto PST unico e pronto per la selezione.',
      })
      setSnapshot(catalogSnapshot)
      setViewSession(nextSession)
      setDocuments(nextDocuments)
      setSelection([])
      setModes({})
      const foundMessage = `${nextDocuments.length} documenti disponibili; ${nextDocuments.filter((doc) => doc.acquired).length} già acquisiti.`
      setMessage(nextDocuments.length
        ? foundMessage
        : `Il PST non ha restituito documenti interrogando ${text(hint.tabella_ministeriale || hint.servizio_pst_preferito || fascicoloPstProfile.tabella_ministeriale || source.tabellaMinisteriale) || 'la tabella ministeriale dedotta'} sull’ufficio ${officeCode}. Se il fascicolo appartiene a un altro registro, correggi il rito nel fascicolo oppure usa la procedura guidata di acquisizione.`)
    } catch (error) {
      const reason = error instanceof Error ? error.message : 'Ricerca documenti non completata.'
      setMessage(reason)
      onError(reason)
    } finally {
      setBusy('')
    }
  }

  const runSearch = (): Promise<void> => {
    if (searchFlight.current) return searchFlight.current
    if (downloadFlight.current) return downloadFlight.current
    const operationId = pstOperationId('view')
    const flight = runSearchOperation(operationId)
    searchFlight.current = flight
    void flight.then(
      () => { if (searchFlight.current === flight) searchFlight.current = null },
      () => { if (searchFlight.current === flight) searchFlight.current = null },
    )
    return flight
  }
  // Il PST risponde a lotti e puo' restare in silenzio per minuti: un contatore
  // che avanza dice all'utente che l'operazione e' viva e non bloccata.
  useEffect(() => {
    if (busy !== 'search' || !searchStartedAt) return
    setSearchElapsed(Math.round((Date.now() - searchStartedAt) / 1000))
    const timer = window.setInterval(() => setSearchElapsed(Math.round((Date.now() - searchStartedAt) / 1000)), 1_000)
    return () => window.clearInterval(timer)
  }, [busy, searchStartedAt])

  const lastOpenOfficeDocumentsRequest = useRef(0)
  useEffect(() => {
    if (!openOfficeDocumentsRequest || openOfficeDocumentsRequest.requestId === lastOpenOfficeDocumentsRequest.current) return
    lastOpenOfficeDocumentsRequest.current = openOfficeDocumentsRequest.requestId
    void runSearch()
  }, [openOfficeDocumentsRequest])

  const runImportOperation = async (operationId: string) => {
    if (!selectedImportDocuments.length) {
      onError('Seleziona almeno un documento non ancora acquisito.')
      return
    }
    if (!viewSession) {
      onError('La sessione di consultazione è scaduta: aggiorna prima l’elenco.')
      return
    }
    setBusy('import')
    setDownloadProgress({ completed: 0, total: selectedImportDocuments.length, current: 'Preparo il lotto documentale.' })
    setMessage(`Acquisizione di ${selectedImportDocuments.length} documenti in corso…`)
    try {
      const cert = await ensureCertificate(localSignerJson)
      const storedDownloadSession = viewSession
        || sessionFrom(readStored(VIEW_SESSION_KEY), officeCode, cert, 'view')
        || sessionFrom(readStored(LEGACY_VIEW_SESSION_KEY), officeCode, cert, 'view')
      const selectedRows = selectedImportDocuments.map((doc) => downloadableDocument(doc.raw, modes[doc.key] || 'copia'))
      const job = await localSignerJson('/pst/download-documenti-batch-job', {
        operation_id: operationId,
        tribunale: officeCode,
        codice_ufficio: officeCode,
        cf_avvocato: cert.fiscalCode,
        cert_thumbprint: cert.thumbprint,
        cert_key: cert.thumbprint,
        purpose: 'view',
        pst_session_id: storedDownloadSession?.sessionId || '',
        preflight_auth: false,
        original: false,
        servizio_pst: text(record(snapshot.fascicolo).servizio_pst || source.servizioPst || fascicoloPstProfile.servizio_pst_preferito),
        registro_portale: text(record(snapshot.fascicolo).registro_portale || fascicoloPstProfile.registro_portale || source.registroPortale),
        tabella_ministeriale: text(record(snapshot.fascicolo).tabella_ministeriale || source.tabellaMinisteriale || fascicoloPstProfile.tabella_ministeriale),
        documents: selectedRows,
      }, 60_000)
      const jobId = text(job.job_id)
      if (!jobId) throw new Error('Il lotto documentale PST non è stato avviato.')
      const startedAt = Date.now()
      let status = job
      while (Date.now() - startedAt < DOWNLOAD_TIMEOUT_MS) {
        if (text(status.status) === 'completed') break
        if (text(status.status) === 'failed') throw new Error(text(status.errore || status.error, 'Scaricamento documenti non completato.'))
        const completed = number(status.completed || status.progress_completed)
        const total = number(status.total || status.progress_total || selectedRows.length)
        const current = text(status.current, 'Scaricamento documenti dal PST in corso…')
        setDownloadProgress({ completed, total, current })
        setMessage(total ? `${current} · ${completed}/${total} documenti elaborati` : current)
        await new Promise((resolve) => window.setTimeout(resolve, 1_000))
        status = await localSignerJson(`/pst/jobs/${encodeURIComponent(jobId)}`, { operation_id: operationId }, 60_000)
      }
      if (text(status.status) !== 'completed') throw new Error('Il portale non ha completato lo scaricamento entro il tempo massimo.')
      const signerPayload = record(status.result)
      setDownloadProgress({
        completed: number(status.completed || status.progress_completed || selectedRows.length),
        total: number(status.total || status.progress_total || selectedRows.length),
        current: text(status.current, 'Lotto documentale ricevuto, verifico i file prima dell’importazione.'),
      })
      const files = list(signerPayload.files).map(record)
      if (!files.length) {
        const firstFailure = record(list(signerPayload.failures)[0])
        throw new Error(text(firstFailure.errore || firstFailure.message, 'Nessun documento è stato ricevuto dal portale.'))
      }
      const nextDownloadSession = sessionFrom(signerPayload, officeCode, cert, 'view')
        || sessionFrom(signerPayload.pst_session, officeCode, cert, 'view')
        || storedDownloadSession
      if (!nextDownloadSession) throw new Error('Sessione di scaricamento non inizializzata.')
      writeStored(VIEW_SESSION_KEY, {
        sessionId: nextDownloadSession.sessionId,
        purpose: 'view',
        tribunale: nextDownloadSession.officeCode,
        certThumbprint: nextDownloadSession.certThumbprint,
        expiresAt: nextDownloadSession.expiresAt,
      })
      setViewSession(nextDownloadSession)
      const pstSession = sessionPayload(nextDownloadSession, cert, 'view')
      const selectionPayload = {
        ...record(snapshot.fascicolo),
        id_fascicolo: source.idFascicoloPortale || source.externalId,
        codice_ufficio: officeCode,
        numero_rg: rgNumber,
        anno_rg: String(rgYear),
        pst_session: pstSession,
      }
      const filteredSnapshot = { ...snapshot, fascicolo: selectionPayload, documenti: selectedRows, catalogo: selectedRows, pst_session: pstSession }
      const previewPayload = await serverJson('/api/portali/pst/acquisizione/preview', {
        selection: { ...selectionPayload, snapshot: filteredSnapshot },
        snapshot: filteredSnapshot,
        documenti: selectedRows,
        pst_session: pstSession,
      })
      const preview = {
        ...record(previewPayload.preview),
        fascicolo: selectionPayload,
        documenti: selectedRows,
        catalogo: selectedRows,
        snapshot: filteredSnapshot,
        pst_session: pstSession,
      }
      const imported = await serverJson('/api/portali/pst/acquisizione/import', {
        selection: selectionPayload,
        preview,
        options: {
          scarica_originale_portale: false,
          mantieni_albero_originale: true,
          importa_documenti: true,
          importa_eventi: false,
          importa_scadenze: false,
          importa_parti: false,
          non_duplicare: true,
          importa_solo_nuovi: true,
        },
        mapping: { mode: 'update_existing', target_fascicolo_id: data.fascicolo.id },
        downloaded_files: files,
        pst_session: pstSession,
      })
      const importedCount = number(imported.documenti_importati || imported.imported_documents || files.length)
      setMessage(`${importedCount || files.length} documenti acquisiti nel fascicolo.`)
      setSelection([])
      onDone(`${importedCount || files.length} documenti acquisiti senza creare un nuovo fascicolo.`)
    } catch (error) {
      const reason = error instanceof Error ? error.message : 'Acquisizione documenti non completata.'
      setMessage(reason)
      onError(reason)
    } finally {
      setBusy('')
    }
  }

  const runDownloadOperation = async (operationId: string) => {
    if (!selectedDocuments.length) {
      onError('Seleziona almeno un documento da riscaricare.')
      return
    }
    if (!viewSession) {
      onError('La sessione di consultazione è scaduta: aggiorna prima l’elenco.')
      return
    }
    setBusy('download')
    setDownloadProgress({ completed: 0, total: selectedDocuments.length, current: 'Preparo un unico lotto per i documenti selezionati.' })
    setMessage(`Scaricamento di ${selectedDocuments.length} documenti in corso…`)
    try {
      const cert = await ensureCertificate(localSignerJson)
      const storedDownloadSession = viewSession
        || sessionFrom(readStored(VIEW_SESSION_KEY), officeCode, cert, 'view')
        || sessionFrom(readStored(LEGACY_VIEW_SESSION_KEY), officeCode, cert, 'view')
      const selectedRows = selectedDocuments.map((doc) => downloadableDocument(doc.raw, modes[doc.key] || 'copia'))
      const job = await localSignerJson('/pst/download-documenti-batch-job', {
        operation_id: operationId,
        tribunale: officeCode,
        codice_ufficio: officeCode,
        cf_avvocato: cert.fiscalCode,
        cert_thumbprint: cert.thumbprint,
        cert_key: cert.thumbprint,
        purpose: 'view',
        pst_session_id: storedDownloadSession?.sessionId || '',
        preflight_auth: false,
        original: false,
        servizio_pst: text(record(snapshot.fascicolo).servizio_pst || source.servizioPst || fascicoloPstProfile.servizio_pst_preferito),
        registro_portale: text(record(snapshot.fascicolo).registro_portale || fascicoloPstProfile.registro_portale || source.registroPortale),
        tabella_ministeriale: text(record(snapshot.fascicolo).tabella_ministeriale || source.tabellaMinisteriale || fascicoloPstProfile.tabella_ministeriale),
        documents: selectedRows,
      }, 60_000)
      const jobId = text(job.job_id)
      if (!jobId) throw new Error('Il lotto documentale PST non è stato avviato.')
      const startedAt = Date.now()
      let status = job
      while (Date.now() - startedAt < DOWNLOAD_TIMEOUT_MS) {
        if (text(status.status) === 'completed') break
        if (text(status.status) === 'failed') throw new Error(text(status.errore || status.error, 'Scaricamento documenti non completato.'))
        const completed = number(status.completed || status.progress_completed)
        const total = number(status.total || status.progress_total || selectedRows.length)
        const current = text(status.current, 'Scaricamento documenti dal PST in corso…')
        setDownloadProgress({ completed, total, current })
        setMessage(total ? `${current} · ${completed}/${total} documenti elaborati` : current)
        await new Promise((resolve) => window.setTimeout(resolve, 1_000))
        status = await localSignerJson(`/pst/jobs/${encodeURIComponent(jobId)}`, { operation_id: operationId }, 60_000)
      }
      if (text(status.status) !== 'completed') throw new Error('Il portale non ha completato lo scaricamento entro il tempo massimo.')
      const signerPayload = record(status.result)
      setDownloadProgress({
        completed: number(status.completed || status.progress_completed || selectedRows.length),
        total: number(status.total || status.progress_total || selectedRows.length),
        current: text(status.current, 'Lotto documentale ricevuto, avvio lo scarico nel browser.'),
      })
      const files = list(signerPayload.files).map(record)
      if (!files.length) {
        const firstFailure = record(list(signerPayload.failures)[0])
        throw new Error(text(firstFailure.errore || firstFailure.message, 'Nessun documento è stato ricevuto dal portale.'))
      }
      const nextDownloadSession = sessionFrom(signerPayload, officeCode, cert, 'view')
        || sessionFrom(signerPayload.pst_session, officeCode, cert, 'view')
        || storedDownloadSession
      if (!nextDownloadSession) throw new Error('Sessione di scaricamento non inizializzata.')
      writeStored(VIEW_SESSION_KEY, {
        sessionId: nextDownloadSession.sessionId,
        purpose: 'view',
        tribunale: nextDownloadSession.officeCode,
        certThumbprint: nextDownloadSession.certThumbprint,
        expiresAt: nextDownloadSession.expiresAt,
      })
      setViewSession(nextDownloadSession)
      const saved = files.reduce((count, file) => count + (savePstFileToBrowser(file) ? 1 : 0), 0)
      if (!saved) throw new Error('I file ricevuti dal PST non sono scaricabili dal browser.')
      setMessage(`${saved} documenti scaricati senza modificare il fascicolo.`)
    } catch (error) {
      const reason = error instanceof Error ? error.message : 'Scaricamento documenti non completato.'
      setMessage(reason)
      onError(reason)
    } finally {
      setBusy('')
    }
  }

  const runDownload = (): Promise<void> => {
    if (downloadFlight.current) return downloadFlight.current
    if (searchFlight.current) return searchFlight.current
    const operationId = pstOperationId('download')
    const flight = runDownloadOperation(operationId)
    downloadFlight.current = flight
    void flight.then(
      () => { if (downloadFlight.current === flight) downloadFlight.current = null },
      () => { if (downloadFlight.current === flight) downloadFlight.current = null },
    )
    return flight
  }
  const runImport = (): Promise<void> => {
    if (downloadFlight.current) return downloadFlight.current
    if (searchFlight.current) return searchFlight.current
    const operationId = pstOperationId('import')
    const flight = runImportOperation(operationId)
    downloadFlight.current = flight
    void flight.then(
      () => { if (downloadFlight.current === flight) downloadFlight.current = null },
      () => { if (downloadFlight.current === flight) downloadFlight.current = null },
    )
    return flight
  }
  return (
    <section className="iu-fas-office-docs" aria-label="Documenti del fascicolo d’ufficio">
      <header className="iu-fas-office-docs__head">
        <div>
          <span className="iu-fas-office-docs__eyebrow"><FolderSearch2 size={15}/> Fascicolo d’ufficio</span>
          <strong>Documenti disponibili presso l’ufficio</strong>
          <p>{officeName} · R.G. {rgNumber || 'n.d.'}/{rgYear || 'n.d.'}</p>
        </div>
        <div className="iu-fas-office-docs__head-actions">
          <button
            type="button"
            className="iu-btn iu-btn--primary"
            disabled={Boolean(busy || missing.length)}
            title={missing.length ? `Mancano: ${missing.join(', ')}` : 'Visualizza direttamente nell’app i documenti disponibili presso l’ufficio'}
            onClick={() => void runSearch()}
          >
            <FolderSearch2 size={15}/>
            {busy === 'search' ? 'Visualizzazione…' : documents.length ? 'Aggiorna fascicolo' : 'Visualizza fascicolo'}
          </button>
        </div>
      </header>

      {missing.length ? <p className="iu-fas-office-docs__notice iu-fas-office-docs__notice--warning">Completa {missing.join(', ')} nel fascicolo per avviare la ricerca.</p> : null}
      {message ? <p className="iu-fas-office-docs__notice" aria-live="polite">{message}</p> : null}
      {busy === 'search' ? (
        <div className="iu-fas-office-docs__progress" role="status" aria-live="polite">
          <div className="iu-fas-office-docs__progress-head">
            <FolderSearch2 size={15}/>
            <strong>{searchProgress.phase || 'Consultazione autenticata'}</strong>
            <span>{searchProgress.completed}/{searchProgress.total} fasi PST · {formatWait(searchElapsed)}</span>
          </div>
          <progress value={Math.min(searchProgress.completed, searchProgress.total)} max={searchProgress.total} aria-label={`Consultazione autenticata: fase ${searchProgress.completed} di ${searchProgress.total}`} />
          <p>{searchProgress.current || 'Attendo l’avvio della consultazione PST.'}</p>
          <p className="iu-fas-office-docs__progress-hint">{searchWaitHint(searchElapsed)}</p>
        </div>
      ) : null}
      {(busy === 'import' || busy === 'download') && downloadProgress.total ? (
        <div className="iu-fas-office-docs__progress" role="status" aria-live="polite">
          <div className="iu-fas-office-docs__progress-head">
            <Download size={15}/>
            <strong>{busy === 'download' ? 'Scaricamento selezionati dal PST' : 'Acquisizione documenti dal PST'}</strong>
            <span>{downloadProgress.completed}/{downloadProgress.total} documenti elaborati</span>
          </div>
          <progress value={Math.min(downloadProgress.completed, downloadProgress.total)} max={downloadProgress.total} aria-label={`Scaricamento documenti: ${downloadProgress.completed} di ${downloadProgress.total}`} />
          <p>{downloadProgress.current}</p>
        </div>
      ) : null}

      {documents.length ? (
        <>
          <div className="iu-fas-office-docs__summary">
            <span><FileText size={14}/> {documents.length} disponibili</span>
            <span><CheckCircle2 size={14}/> {acquiredCount} già acquisiti</span>
            <span><ShieldCheck size={14}/> {selectedDocuments.length} selezionati</span>
          </div>
          <div className="iu-fas-office-docs__selection-toolbar" aria-label="Selezione documenti del fascicolo d’ufficio">
            <span>{selectableDocuments.length} non ancora acquisiti · {selectedDocuments.length} selezionati</span>
            <button type="button" className="iu-btn iu-btn--neutral" onClick={selectAllDocuments} disabled={!documents.length || Boolean(busy)}>Seleziona tutto</button>
            <button type="button" className="iu-btn iu-btn--neutral" onClick={selectOnlyNotAcquired} disabled={!selectableDocuments.length || Boolean(busy)}>Seleziona non acquisiti</button>
            <button type="button" className="iu-btn iu-btn--neutral" onClick={deselectAll} disabled={!selection.length || Boolean(busy)}>Deseleziona tutto</button>
            <label>
              <span>Formato selezionati</span>
              <select
                aria-label="Formato per i documenti selezionati"
                value={selectedDocuments.length ? (modes[selectedDocuments[0].key] || 'copia') : 'copia'}
                disabled={!selectedDocuments.length || Boolean(busy)}
                onChange={(event) => setSelectedDocumentsMode(event.target.value as DocumentMode)}
              >
                <option value="copia">Copia</option>
                <option value="originale">Originale</option>
              </select>
            </label>
          </div>
          <div className="iu-fas-office-docs__list">
            {documents.map((doc) => {
              const selected = selection.includes(doc.key)
              return (
                <article className={`iu-fas-office-docs__row${doc.isAttachment ? ' is-attachment' : ''}${doc.acquired ? ' is-acquired' : ''}`} key={doc.key}>
                  <label className="iu-fas-office-docs__select">
                    <input
                      type="checkbox"
                      checked={selected}
                      disabled={Boolean(busy)}
                      onChange={(event) => setSelection((current) => event.target.checked ? [...current, doc.key] : current.filter((key) => key !== doc.key))}
                    />
                    <span className="sr-only">Seleziona {doc.name}</span>
                  </label>
                  <div className="iu-fas-office-docs__identity">
                    <strong>{doc.name}</strong>
                    <span>{doc.isAttachment ? `Allegato${doc.parentName ? ` di ${doc.parentName}` : ''}` : 'Atto principale'} · {doc.type}{doc.date ? ` · ${formatDateIt(doc.date)}` : ''}</span>
                  </div>
                  <div className="iu-fas-office-docs__row-actions">
                    {doc.acquired ? <span className="iu-fas-office-docs__acquired"><CheckCircle2 size={14}/> Acquisito</span> : null}
                    <select
                      aria-label={`${doc.acquired ? 'Formato da riscaricare' : 'Formato da acquisire'} per ${doc.name}`}
                      value={modes[doc.key] || 'copia'}
                      disabled={!selected || Boolean(busy)}
                      onChange={(event) => setModes((current) => ({ ...current, [doc.key]: event.target.value as DocumentMode }))}
                    >
                      <option value="copia">Copia</option>
                      <option value="originale">Originale</option>
                    </select>
                  </div>
                </article>
              )
            })}
          </div>
          <footer className="iu-fas-office-docs__actions">
            <span>I documenti già acquisiti restano riconoscibili e possono essere riscaricati in copia o originale senza creare duplicati nel fascicolo.</span>
            <div className="iu-fas-office-docs__action-buttons">
              <button type="button" className="iu-btn iu-btn--neutral" onClick={() => void runDownload()} disabled={!selectedDocuments.length || Boolean(busy)}>
                <Download size={15}/>{busy === 'download' ? 'Scaricamento…' : `Scarica ${selectedDocuments.length || ''}`}
              </button>
              <button type="button" className="iu-btn iu-btn--primary" onClick={() => void runImport()} disabled={!selectedImportDocuments.length || Boolean(busy)}>
                <Download size={15}/>{busy === 'import' ? 'Acquisizione…' : `Acquisisci nuovi ${selectedImportDocuments.length || ''}`}
              </button>
            </div>
          </footer>
        </>
      ) : null}
    </section>
  )
}
