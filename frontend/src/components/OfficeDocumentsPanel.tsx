import { useMemo, useState } from 'react'
import { CheckCircle2, Download, FileText, FolderSearch2, RefreshCw, ShieldCheck } from 'lucide-react'
import type { FascicoloDetailData, FascicoloDocument } from '../fascicoliData'
import { formatDateIt } from '../formatting'

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

type LocalNetworkRequestInit = RequestInit & { targetAddressSpace?: 'local' }

type PstSession = {
  sessionId: string
  officeCode: string
  certThumbprint: string
  expiresAt: number
}

type PortalAssistantSession = {
  sessionId: string
  status: string
  message: string
  fileCount: number
  manual?: boolean
}

type Props = {
  data: FascicoloDetailData
  onDone: (message?: string) => void
  onError: (message: string) => void
}

const CERT_KEY = 'iusentra.react.pst.cert.v2'
const SESSION_KEY = 'iusentra.react.pst.session.v2'
const LOCAL_SIGNER_BASES = ['http://127.0.0.1:27272', 'http://localhost:27272']
const OFFICIAL_PST_BASE = 'https://servizipst.giustizia.it/PST/it'
const OFFICIAL_PST_ACCESS_URL = 'https://servizipst.giustizia.it/PST/authentication/it/pst_ar.wp'
const JOB_TIMEOUT_MS = 360_000
const DOWNLOAD_TIMEOUT_MS = 480_000
const PORTAL_OPEN_TIMEOUT_MS = 20_000

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

function encodePstQuery(params: Record<string, string>): string {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    const clean = text(value)
    if (clean) query.set(key, clean)
  })
  return query
    .toString()
    .replaceAll('%2F', '/')
    .replaceAll('%40', '@')
    .replaceAll('%5B', '[')
    .replaceAll('%5D', ']')
}

function officialPstRegister(source: FascicoloDetailData['fascicolo']['sourceSnapshot'], hint: JsonRecord): string {
  const registro = text(source.registroPortale || hint.registro_portale || hint.registro || hint.tipo_registro).toUpperCase()
  if (registro) return registro
  const servizio = text(source.servizioPst || hint.servizio_pst_preferito || hint.servizio_pst).toUpperCase()
  if (servizio.includes('SIL')) return 'LAV'
  if (servizio.includes('SIVG')) return 'VG'
  if (servizio.includes('SIMIN') || servizio.includes('MIN')) return 'MIN'
  if (servizio.includes('SIGP')) return 'GDP'
  if (servizio.includes('SIECIC')) return 'FALL'
  return 'RGN'
}

function officialPstSlug(registry: string): string {
  const registro = registry.toUpperCase()
  if (registro === 'LAV') return 'lav'
  if (['GDP', 'GP'].includes(registro)) return 'sigp'
  if (['VG', 'SIVG'].includes(registro)) return 'sivg'
  if (['MIN', 'SIMIN'].includes(registro)) return 'min'
  if (['RGN', 'SICID', 'CONTENZIOSO', 'CIVILE'].includes(registro)) return 'sicid'
  return ''
}

function officialPstSearchUrl(registry: string, officeCode: string, fiscalCode: string): string {
  const registro = registry.toUpperCase()
  const pageByRegistry: Record<string, string> = {
    FALL: 'pst_2_1_3_3.wp',
    ESIM: 'pst_2_1_4_3.wp',
    ESM: 'pst_2_1_5_3.wp',
  }
  const page = pageByRegistry[registro]
  if (!page) return ''
  const query = encodePstQuery({
    ufficioRicerca: officeCode,
    ruoloRicerca: 'AVV@AVV',
    registroRicerca: registro,
    pa: fiscalCode ? `[${fiscalCode}]` : '',
  })
  return `${OFFICIAL_PST_BASE}/${page}?${query}`
}

function officialPstAccessUrl(): string {
  return OFFICIAL_PST_ACCESS_URL
}

function openOfficialPstWindow(): boolean {
  const target = window.open(officialPstAccessUrl(), '_blank', 'noopener,noreferrer')
  return Boolean(target)
}

function officialPstDocumentsUrl(args: {
  source: FascicoloDetailData['fascicolo']['sourceSnapshot']
  hint: JsonRecord
  officeCode: string
  rgNumber: string
  rgYear: string | number
  fiscalCode: string
}): string {
  const registry = officialPstRegister(args.source, args.hint)
  const searchUrl = officialPstSearchUrl(registry, args.officeCode, args.fiscalCode)
  if (searchUrl) return searchUrl
  const slug = officialPstSlug(registry)
  if (!slug) return officialPstAccessUrl()
  const registroRicerca = ['GDP', 'GP'].includes(registry) ? 'GDP' : registry
  const query = ['GDP', 'GP'].includes(registry)
    ? encodePstQuery({
        actionPath: '/ExtStr2/do/consultazioneregistri/sicid/dettagliofascicolo/documentiFascicolo.action',
        currentFrame: '0',
        ufficioRicerca: args.officeCode,
        ruoloRicerca: 'AVV@AVV',
        numero: args.rgNumber,
        anno: String(args.rgYear),
        registroRicerca: 'GDP',
        pa: args.fiscalCode ? `[${args.fiscalCode}]` : '',
      })
    : encodePstQuery({
        actionPath: '/ExtStr2/do/consultazioneregistri/sicid/dettagliofascicolo/documentiFascicolo.action',
        currentFrame: '0',
        registroRicerca,
        ruoloRicerca: 'AVV@AVV',
        ufficioRicerca: args.officeCode,
        numero: args.rgNumber,
        anno: String(args.rgYear),
        subpro: text(args.source.subProcedimento),
        pa: args.fiscalCode ? `[${args.fiscalCode}]` : '',
      })
  return `${OFFICIAL_PST_BASE}/${slug}_infofascicolo.wp?${query}`
}

function openPortalPlaceholder(): Window | null {
  try {
    const portalWindow = window.open('', '_blank')
    if (!portalWindow) return null
    try {
      portalWindow.opener = null
      portalWindow.document.title = 'Portale Servizi'
      portalWindow.document.body.innerHTML = '<main style="font-family: system-ui, sans-serif; padding: 24px; color: #111827;">Apertura del Portale Servizi...</main>'
    } catch {
      // La navigazione ufficiale verrà impostata appena l'URL è pronto.
    }
    return portalWindow
  } catch {
    return null
  }
}

function navigatePortalPlaceholder(portalWindow: Window | null, officialUrl: string): boolean {
  if (!officialUrl) return false
  try {
    if (portalWindow && !portalWindow.closed) {
      portalWindow.location.href = officialUrl
      return true
    }
  } catch {
    // Se la scheda non è controllabile, proviamo l'apertura diretta.
  }
  try {
    return Boolean(window.open(officialUrl, '_blank', 'noopener,noreferrer'))
  } catch {
    return false
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

function sessionFrom(value: unknown, officeCode: string, cert: Certificate): PstSession | null {
  const row = record(value)
  const sessionId = text(row.sessionId || row.session_id || row.pst_session_id || row.view_session_id)
  if (!sessionId) return null
  const rawExpiry = number(row.expiresAt || row.expires_at || row.view_expires_at)
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

async function localRequest(endpoint: string, body?: JsonRecord, timeoutMs = 45_000): Promise<JsonRecord> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const requestOptions: LocalNetworkRequestInit = {
      method: body ? 'POST' : 'GET',
      cache: 'no-store',
      mode: 'cors',
      targetAddressSpace: 'local',
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
  } catch (fetchError) {
    try {
      return await localXhrRequest(endpoint, body, timeoutMs)
    } catch (xhrError) {
      throw xhrError instanceof Error ? xhrError : fetchError
    }
  } finally {
    window.clearTimeout(timeout)
  }
}

async function localSignerJson(path: string, body?: JsonRecord, timeoutMs = 45_000): Promise<JsonRecord> {
  let lastError: unknown = null
  for (const base of LOCAL_SIGNER_BASES) {
    try {
      return await localRequest(`${base}${path}`, body, timeoutMs)
    } catch (error) {
      lastError = error
    }
  }
  const reason = lastError instanceof Error && lastError.name !== 'AbortError' ? lastError.message : 'tempo massimo superato'
  throw new Error(`Local Signer non raggiungibile dal browser. Verifica che sia avviato sul PC in uso e riprova. Dettaglio: ${reason}`)
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

async function ensureCertificate(): Promise<Certificate> {
  const stored = certificateFrom(readStored(CERT_KEY))
  if (stored) return stored
  return { thumbprint: '', fiscalCode: '' }
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

function sessionPayload(session: PstSession, cert: Certificate): JsonRecord {
  return {
    session_id: session.sessionId,
    pst_session_id: session.sessionId,
    purpose: 'view',
    cert_thumbprint: cert.thumbprint,
    cert_key: cert.thumbprint,
    expires_at: session.expiresAt,
  }
}

export function OfficeDocumentsPanel({ data, onDone, onError }: Props) {
  const [documents, setDocuments] = useState<OfficeDocument[]>([])
  const [snapshot, setSnapshot] = useState<JsonRecord>({})
  const [selection, setSelection] = useState<string[]>([])
  const [modes, setModes] = useState<Record<string, DocumentMode>>({})
  const [session, setSession] = useState<PstSession | null>(null)
  const [assistantSession, setAssistantSession] = useState<PortalAssistantSession | null>(null)
  const [busy, setBusy] = useState<'portal' | 'collect' | 'search' | 'import' | ''>('')
  const [message, setMessage] = useState('')

  const source = data.fascicolo.sourceSnapshot
  const officeCode = source.ufficioCodice || data.depositOffice.ministerialCode || data.depositOffice.code
  const officeName = source.ufficioNome || data.fascicolo.court
  const rgNumber = source.numero || String(data.fascicolo.rgNumber || '')
  const rgYear = source.anno || data.fascicolo.rgYear
  const missing = [!officeCode && 'codice ufficio', !rgNumber && 'numero R.G.', !rgYear && 'anno R.G.'].filter(Boolean) as string[]
  const storedCertificate = useMemo(() => certificateFrom(readStored(CERT_KEY)), [])
  const portalUrl = useMemo(() => officialPstDocumentsUrl({
    source,
    hint: {},
    officeCode,
    rgNumber,
    rgYear,
    fiscalCode: storedCertificate?.fiscalCode || '',
  }), [source, officeCode, rgNumber, rgYear, storedCertificate?.fiscalCode])
  const searchDisabled = Boolean(busy || missing.length)
  const acquiredCount = useMemo(() => documents.filter((doc) => doc.acquired).length, [documents])
  const selectedDocuments = useMemo(() => documents.filter((doc) => selection.includes(doc.key) && !doc.acquired), [documents, selection])

  const openAssistedPortal = async () => {
    if (missing.length) {
      onError(`Apertura Portale Servizi non avviata: manca ${missing.join(', ')} nel fascicolo.`)
      return
    }
    const accessUrl = officialPstAccessUrl()
    const targetUrl = portalUrl
    const portalWindow = openPortalPlaceholder()
    setBusy('portal')
    setMessage('Apertura del Portale Servizi nella sessione assistita del PC...')
    try {
      const started = await localSignerJson('/portal-assistant/session/start', {
        portale: 'pst',
        official_url: accessUrl,
        target_url: targetUrl,
        fascicolo_id: data.fascicolo.id,
        purpose: 'documenti_fascicolo',
        context: {
          ufficio: officeName,
          ufficio_codice: officeCode,
          numero_rg: rgNumber,
          anno_rg: String(rgYear),
          registro: officialPstRegister(source, {}),
          infofascicolo_url: portalUrl,
        },
      }, PORTAL_OPEN_TIMEOUT_MS)
      const sessionId = text(started.session_id)
      if (!sessionId) throw new Error('Sessione assistita non inizializzata dal servizio locale.')
      const opened = await localSignerJson(`/portal-assistant/session/${encodeURIComponent(sessionId)}/open`, {
        official_url: accessUrl,
        target_url: targetUrl,
        portale: 'pst',
      }, PORTAL_OPEN_TIMEOUT_MS)
      const watched = record(await localSignerJson(`/portal-assistant/session/${encodeURIComponent(sessionId)}/watch-downloads`, {
        portale: 'pst',
      }, PORTAL_OPEN_TIMEOUT_MS).catch(() => ({})))
      const files = list(watched.files || opened.files || started.files)
      setAssistantSession({
        sessionId,
        status: text(watched.status || opened.status || started.status, 'portale_ufficiale_assistito_aperto'),
        message: text(watched.message || opened.message || started.message),
        fileCount: files.length,
      })
      try {
        if (portalWindow && !portalWindow.closed) portalWindow.close()
      } catch {
        // La sessione assistita locale ha gia' aperto il portale; la scheda segnaposto non serve piu'.
      }
      setMessage(`Portale Servizi aperto. Dopo l'accesso la finestra viene portata su InfoFascicolo > Documenti per R.G. ${rgNumber}/${rgYear}; scarica i file scelti e poi usa "Raccogli download".`)
    } catch (error) {
      const reason = error instanceof Error ? error.message : 'Portale Servizi non aperto.'
      const opened = navigatePortalPlaceholder(portalWindow, accessUrl) || openOfficialPstWindow()
      setAssistantSession({
        sessionId: '',
        status: opened ? 'portale_ufficiale_aperto' : 'portale_ufficiale_da_aprire',
        message: opened
          ? 'Portale Servizi aperto. Dopo avere scaricato i documenti scelti, usa "Raccogli download" o "Carica documenti".'
          : 'Apri il Portale Servizi dal collegamento ufficiale, scarica i documenti scelti e poi usa "Raccogli download" o "Carica documenti".',
        fileCount: 0,
        manual: true,
      })
      setMessage(
        opened
          ? 'Portale Servizi aperto. Accedi, vai in InfoFascicolo > Documenti, scarica i documenti scelti e poi usa "Raccogli download" o "Carica documenti".'
          : `${reason} Apri il Portale Servizi dal collegamento ufficiale, scarica i documenti scelti e poi usa "Raccogli download" o "Carica documenti".`
      )
      if (!opened) onError(reason)
    } finally {
      setBusy('')
    }
  }

  const collectAssistedDownloads = async () => {
    if (!assistantSession) {
      onError('Apri prima il Portale Servizi e scarica i documenti scelti.')
      return
    }
    setBusy('collect')
    setMessage('Raccolta dei documenti scaricati dal Portale Servizi in corso...')
    try {
      const collected = assistantSession.sessionId
        ? await localSignerJson(`/portal-assistant/session/${encodeURIComponent(assistantSession.sessionId)}/collect`, {
            portale: 'pst',
            limit: 100,
            max_age_hours: 24,
          }, DOWNLOAD_TIMEOUT_MS)
        : await localSignerJson('/downloads/raccogli', {
            limit: 100,
            max_age_hours: 24,
          }, DOWNLOAD_TIMEOUT_MS)
      const files = list(collected.files).map(record)
      if (!files.length) {
        throw new Error('Nessun download recente trovato: scarica dal Portale Servizi il documento scelto e poi riprova.')
      }
      const imported = await serverJson('/api/portali/pst/acquisizione/importa-file', {
        fascicolo_id: data.fascicolo.id,
        downloaded_files: files,
        mapping: { mode: 'update_existing', target_fascicolo_id: data.fascicolo.id },
        options: {
          importa_documenti: true,
          importa_eventi: false,
          importa_scadenze: false,
          importa_parti: false,
          non_duplicare: true,
          importa_solo_nuovi: true,
        },
      })
      const summary = record(imported.summary || record(imported.result).summary)
      const importedCount = number(summary.documenti || imported.documenti_importati || files.length)
      setAssistantSession((current) => current ? {
        ...current,
        status: text(collected.status, 'file_ufficiali_raccolti'),
        message: text(collected.message),
        fileCount: files.length,
      } : current)
      setMessage(`${importedCount || files.length} documenti salvati nel fascicolo corrente.`)
      onDone(`${importedCount || files.length} documenti salvati nel fascicolo corrente.`)
    } catch (error) {
      const reason = error instanceof Error ? error.message : 'Raccolta dei download non completata.'
      setMessage(reason)
      onError(reason)
    } finally {
      setBusy('')
    }
  }

  const runSearch = async (openOfficialPortal = true) => {
    if (missing.length) {
      onError(`Ricerca documenti non avviata: manca ${missing.join(', ')} nel fascicolo.`)
      return
    }
    const portalWindow = openOfficialPortal ? openPortalPlaceholder() : null
    setBusy('search')
    setMessage('Apertura del Portale Servizi e lettura del fascicolo d’ufficio in corso...')
    try {
      const cert = await ensureCertificate()
      const params = new URLSearchParams({
        id_fasc: data.fascicolo.id,
        numero: rgNumber,
        anno: String(rgYear),
        ufficio: officeName,
        ufficio_codice: officeCode,
      })
      const schemaPayload = await serverJson(`/api/v1/ui/telematico/pst/schema-hint?${params.toString()}`)
      const hint = record(schemaPayload.hint)
      const officialUrl = officialPstDocumentsUrl({
        source,
        hint,
        officeCode,
        rgNumber,
        rgYear,
        fiscalCode: cert.fiscalCode,
      })
      let portalOpened = !openOfficialPortal || navigatePortalPlaceholder(portalWindow, officialUrl)
      if (!portalOpened) {
        const portalSession = await localSignerJson('/portal-assistant/session/start', {
          portale: 'pst',
          official_url: officialUrl,
          fascicolo_id: data.fascicolo.id,
          purpose: 'documenti_fascicolo',
        }, PORTAL_OPEN_TIMEOUT_MS)
        const portalSessionId = text(portalSession.session_id)
        if (portalSessionId) {
          await localSignerJson(`/portal-assistant/session/${encodeURIComponent(portalSessionId)}/open`, {
            official_url: officialUrl,
          }, PORTAL_OPEN_TIMEOUT_MS)
          portalOpened = true
        }
      }
      if (!portalOpened) {
        throw new Error("Portale Servizi non aperto: consenti l'apertura della nuova scheda e riprova.")
      }
      setMessage(`${openOfficialPortal ? 'Portale Servizi aperto sulla consultazione ufficiale.' : 'Portale Servizi aperto nella nuova scheda.'} Lettura dei documenti disponibili in corso...`)
      const storedSession = sessionFrom(readStored(SESSION_KEY), officeCode, cert)
      const job = await localSignerJson('/pst/fascicolo-snapshot-job', {
        selection: {
          id_fascicolo: source.idFascicoloPortale || source.externalId,
          codice_ufficio: officeCode,
          numero_rg: rgNumber,
          anno_rg: String(rgYear),
        },
        codice_ufficio: officeCode,
        numero_rg: rgNumber,
        anno_rg: String(rgYear),
        id_fascicolo: source.idFascicoloPortale || source.externalId,
        sub_procedimento: source.subProcedimento,
        id_dfa: source.idDfa,
        id_ruolo_jpw: source.idRuoloJpw,
        servizio_pst: source.servizioPst || text(hint.servizio_pst_preferito),
        registro_portale: source.registroPortale || text(hint.registro_portale),
        tabella_ministeriale: source.tabellaMinisteriale || text(hint.tabella_ministeriale),
        tipo_registro: text(hint.tipo_registro || hint.registro),
        materia: text(hint.materia),
        schema: text(hint.schema),
        cf_avvocato: cert.fiscalCode,
        cert_thumbprint: cert.thumbprint,
        cert_key: cert.thumbprint,
        purpose: 'view',
        pst_session_id: storedSession?.sessionId || '',
      }, 60_000)
      const jobId = text(job.job_id)
      if (!jobId) throw new Error('La consultazione non è stata avviata.')
      const startedAt = Date.now()
      let status = job
      while (Date.now() - startedAt < JOB_TIMEOUT_MS) {
        if (text(status.status) === 'completed') break
        if (text(status.status) === 'failed') throw new Error(text(status.errore || status.error, 'Consultazione non completata.'))
        setMessage(text(status.current, 'Lettura dei documenti disponibili…'))
        await new Promise((resolve) => window.setTimeout(resolve, 2_500))
        status = await localSignerJson(`/pst/jobs/${encodeURIComponent(jobId)}`, {}, 60_000)
      }
      if (text(status.status) !== 'completed') throw new Error('Il portale non ha completato la consultazione entro il tempo massimo.')
      const result = record(status.result)
      const nextSnapshot = record(result.snapshot)
      const nextCert = certificateFrom(result)
        || certificateFrom(result.pst_session)
        || certificateFrom(nextSnapshot.pst_session)
        || cert
      if (nextCert.thumbprint) {
        writeStored(CERT_KEY, { thumbprint: nextCert.thumbprint, codiceFiscale: nextCert.fiscalCode })
      }
      const nextSession = sessionFrom(result, officeCode, nextCert)
        || sessionFrom(result.pst_session, officeCode, nextCert)
        || sessionFrom(nextSnapshot.pst_session, officeCode, nextCert)
        || storedSession
      if (!nextSession) throw new Error('Sessione di consultazione non inizializzata.')
      writeStored(SESSION_KEY, {
        sessionId: nextSession.sessionId,
        tribunale: nextSession.officeCode,
        certThumbprint: nextSession.certThumbprint,
        expiresAt: nextSession.expiresAt,
      })
      const rows = list(nextSnapshot.documenti || nextSnapshot.catalogo || result.documenti)
      const nextDocuments = flattenDocuments(rows, data.documents)
      setSnapshot(nextSnapshot)
      setSession(nextSession)
      setDocuments(nextDocuments)
      setSelection([])
      setModes({})
      setMessage(nextDocuments.length ? `${nextDocuments.length} documenti disponibili; ${nextDocuments.filter((doc) => doc.acquired).length} già acquisiti.` : 'Nessun nuovo documento disponibile nel fascicolo d’ufficio.')
    } catch (error) {
      try {
        if (portalWindow && !portalWindow.closed) portalWindow.close()
      } catch {
        // La scheda potrebbe gia' essere fuori controllo dopo la navigazione ufficiale.
      }
      const reason = error instanceof Error ? error.message : 'Ricerca documenti non completata.'
      setMessage(reason)
      onError(reason)
    } finally {
      setBusy('')
    }
  }

  const runImport = async () => {
    if (!selectedDocuments.length) {
      onError('Seleziona almeno un documento da acquisire.')
      return
    }
    if (!session) {
      onError('La sessione di consultazione è scaduta: aggiorna prima l’elenco.')
      return
    }
    setBusy('import')
    setMessage(`Acquisizione di ${selectedDocuments.length} documenti in corso…`)
    try {
      const cert = await ensureCertificate()
      const selectedRows = selectedDocuments.map((doc) => downloadableDocument(doc.raw, modes[doc.key] || 'copia'))
      const signerPayload = await localSignerJson('/pst/download-documenti-batch', {
        tribunale: officeCode,
        codice_ufficio: officeCode,
        cf_avvocato: cert.fiscalCode,
        cert_thumbprint: cert.thumbprint,
        cert_key: cert.thumbprint,
        purpose: 'view',
        pst_session_id: session.sessionId,
        preflight_auth: false,
        original: false,
        servizio_pst: source.servizioPst || text(record(snapshot.fascicolo).servizio_pst),
        registro_portale: source.registroPortale || text(record(snapshot.fascicolo).registro_portale),
        tabella_ministeriale: source.tabellaMinisteriale || text(record(snapshot.fascicolo).tabella_ministeriale),
        documents: selectedRows,
      }, DOWNLOAD_TIMEOUT_MS)
      const files = list(signerPayload.files).map(record)
      if (!files.length) {
        const firstFailure = record(list(signerPayload.failures)[0])
        throw new Error(text(firstFailure.errore || firstFailure.message, 'Nessun documento è stato ricevuto dal portale.'))
      }
      const pstSession = sessionPayload(session, cert)
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
            title={missing.length ? `Mancano: ${missing.join(', ')}` : 'Apri il Portale Servizi nella sessione assistita del PC'}
            onClick={() => void openAssistedPortal()}
          >
            <FolderSearch2 size={15}/>
            {busy === 'portal' ? 'Apertura...' : 'Apri Portale Servizi'}
          </button>
          <button
            type="button"
            className="iu-btn iu-btn--secondary"
            disabled={!assistantSession || Boolean(busy)}
            title={assistantSession ? 'Importa nel fascicolo i file scaricati dal Portale Servizi' : 'Apri prima il Portale Servizi'}
            onClick={() => void collectAssistedDownloads()}
          >
            <Download size={15}/>
            {busy === 'collect' ? 'Raccolta...' : 'Raccogli download'}
          </button>
          <button
            type="button"
            className="iu-btn iu-btn--secondary"
            disabled={searchDisabled}
            title={missing.length ? `Mancano: ${missing.join(', ')}` : 'Aggiorna l’elenco interno dei documenti disponibili'}
            onClick={() => void runSearch(false)}
          >
            <RefreshCw size={15} className={busy === 'search' ? 'iu-spin' : ''}/>
            {documents.length ? 'Aggiorna elenco' : 'Leggi elenco'}
          </button>
        </div>
      </header>

      {missing.length ? <p className="iu-fas-office-docs__notice iu-fas-office-docs__notice--warning">Completa {missing.join(', ')} nel fascicolo per avviare la ricerca.</p> : null}
      {assistantSession ? <p className="iu-fas-office-docs__notice">
        {assistantSession.manual
          ? "Portale ufficiale aperto: scarica solo i documenti scelti dall'avvocato, poi raccoglili nel fascicolo o caricali manualmente."
          : "Sessione assistita attiva: scarica dal portale solo i documenti scelti dall'avvocato, poi raccoglili nel fascicolo."}
        {' '}File rilevati: {assistantSession.fileCount}.
      </p> : null}
      {message ? <p className="iu-fas-office-docs__notice" aria-live="polite">{message}</p> : null}

      {documents.length ? (
        <>
          <div className="iu-fas-office-docs__summary">
            <span><FileText size={14}/> {documents.length} disponibili</span>
            <span><CheckCircle2 size={14}/> {acquiredCount} già acquisiti</span>
            <span><ShieldCheck size={14}/> {selectedDocuments.length} selezionati</span>
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
                      disabled={doc.acquired || Boolean(busy)}
                      onChange={(event) => setSelection((current) => event.target.checked ? [...current, doc.key] : current.filter((key) => key !== doc.key))}
                    />
                    <span className="sr-only">Seleziona {doc.name}</span>
                  </label>
                  <div className="iu-fas-office-docs__identity">
                    <strong>{doc.name}</strong>
                    <span>{doc.isAttachment ? `Allegato${doc.parentName ? ` di ${doc.parentName}` : ''}` : 'Atto principale'} · {doc.type}{doc.date ? ` · ${formatDateIt(doc.date)}` : ''}</span>
                  </div>
                  {doc.acquired ? (
                    <span className="iu-fas-office-docs__acquired"><CheckCircle2 size={14}/> Acquisito</span>
                  ) : (
                    <select
                      aria-label={`Formato da acquisire per ${doc.name}`}
                      value={modes[doc.key] || 'copia'}
                      disabled={!selected || Boolean(busy)}
                      onChange={(event) => setModes((current) => ({ ...current, [doc.key]: event.target.value as DocumentMode }))}
                    >
                      <option value="copia">Copia</option>
                      <option value="originale">Originale</option>
                    </select>
                  )}
                </article>
              )
            })}
          </div>
          <footer className="iu-fas-office-docs__actions">
            <span>La scelta resta manuale: vengono acquisiti soltanto i documenti selezionati.</span>
            <button type="button" className="iu-btn iu-btn--primary" onClick={() => void runImport()} disabled={!selectedDocuments.length || Boolean(busy)}>
              <Download size={15}/>{busy === 'import' ? 'Acquisizione…' : `Acquisisci ${selectedDocuments.length || ''}`}
            </button>
          </footer>
        </>
      ) : null}
    </section>
  )
}
