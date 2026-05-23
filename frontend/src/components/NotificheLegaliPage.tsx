import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  FileDown,
  FileCheck2,
  FileSignature,
  FileText,
  FolderOpen,
  Inbox,
  LockKeyhole,
  Mail,
  PencilLine,
  PlusCircle,
  RefreshCw,
  RotateCcw,
  Save,
  Scale,
  Send,
  ShieldCheck,
  Paperclip,
  Trash2,
  UploadCloud,
  UserRound,
  WandSparkles,
} from 'lucide-react'
import { Button, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import {
  emptyNotificheLegaliData,
  getNotificheLegaliData,
  postLegalWorkflow,
  previewLegalRelata,
  saveLegalRelataDraft,
  saveLegalRelataTemplate,
  type LegalAutomationStep,
  type LegalDocumentSuggestion,
  type LegalRelataPreviewResult,
  type LegalPracticeSuggestion,
  type LegalRecipientSuggestion,
  type LegalTemplateFieldToken,
  type LegalWorkflowResult,
  type NotificheLegaliData,
} from '../notificheLegaliData'
import './NotificheLegaliPage.css'

type TabKey = 'notifica' | 'deposito' | 'cliente'

type NotificaDocumentPayload = {
  nome_file: string
  descrizione: string
  origine: string
  hash_sha256: string
  data_comunicazione_cancelleria: string
  fonte_documento?: string
  riferimento_portale?: string
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

const SHA256_HEX_PATTERN = /^[a-f0-9]{64}$/i

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
    setStatus('Calcolo impronta SHA-256...')
    try {
      const digest = await calculateSha256(file)
      onFileComputed(file.name, digest)
      setStatus(`Impronta calcolata: ${digest.slice(0, 12)}...`)
    } catch {
      onFileNameChange(file.name)
      setStatus('Calcolo automatico non disponibile: incolla una impronta SHA-256 valida.')
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
          placeholder="SHA-256 calcolato dal file"
          aria-invalid={hasInvalidSha}
          maxLength={64}
        />
        <small className={hasInvalidSha ? 'is-error' : ''}>
          {hasInvalidSha ? 'L\'impronta SHA-256 deve avere 64 caratteri esadecimali.' : status || 'Scegli il file: IUSENTRA calcola l\'impronta automaticamente.'}
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
  pec_inviata: string
  rac_file: string
  rdac_file: string
}) {
  const rows = [
    values.destinatario_nome ? `Destinatario: ${values.destinatario_nome}` : '',
    values.pec_inviata ? `PEC inviata: ${values.pec_inviata}` : '',
    values.rac_file ? `RAC: ${values.rac_file}` : '',
    values.rdac_file ? `RdAC completa: ${values.rdac_file}` : '',
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
      <small>{shaValue ? `SHA-256 ${shaValue.slice(0, 12)}...` : 'Impronta non calcolata'}</small>
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
          {result.blockers.map((item) => <span key={item}><AlertTriangle size={15} /> {item}</span>)}
        </div>
      ) : null}
      {result.warnings.length ? (
        <div className="iu-legal-list">
          {result.warnings.map((item) => <span key={item}><ShieldCheck size={15} /> {item}</span>)}
        </div>
      ) : null}
      {result.templateLabel ? <div className="iu-legal-output"><span>Modello scelto</span><strong>{result.templateLabel}{result.templateVersion ? ` - ${result.templateVersion}` : ''}</strong></div> : null}
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
                {item.label}{item.filename ? ` - ${item.filename}` : ''}{item.sha256 ? ` - SHA-256 ${item.sha256.slice(0, 12)}...` : ''}{item.generated ? ' - preparato' : ''}
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

  const [notifica, setNotifica] = useState({
    template_id: 'relata_pec_base_l53',
    pratica_codice: '',
    avvocato_nome: '',
    avvocato_cf: '',
    avvocato_foro: '',
    studio_indirizzo: '',
    studio_citta: '',
    luogo: '',
    data_relata: todayLocalDate(),
    mittente_pec: '',
    fonte_pec_mittente: 'ReGIndE',
    mittente_pec_pubblico_elenco: true,
    mittente_avvocato_abilitato: false,
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
  const [selectedRecipientId, setSelectedRecipientId] = useState('')
  const [selectedDocumentId, setSelectedDocumentId] = useState('')
  const [selectedNotificationDocumentIds, setSelectedNotificationDocumentIds] = useState<string[]>([])
  const [manualNotificationDocuments, setManualNotificationDocuments] = useState<ManualNotificationDocument[]>([])
  const [notificationFilesMessage, setNotificationFilesMessage] = useState('')
  const [attestazioniAutomatiche, setAttestazioniAutomatiche] = useState(true)
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

  const [deposito, setDeposito] = useState({
    atto_notificato: '',
    atto_sha256: '',
    relata_firmata: '',
    relata_sha256: '',
    pec_inviata: '',
    pec_inviata_sha256: '',
    destinatario_nome: '',
    rac_file: '',
    rac_sha256: '',
    rdac_file: '',
    rdac_sha256: '',
    ricevuta_completa: false,
    dati_atto_ricevute: '',
  })
  const [depositAutoMessage, setDepositAutoMessage] = useState('')

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
          studio_citta: payload.defaults.studioCitta,
          luogo: payload.defaults.studioCitta,
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
  const templateFieldGroups = useMemo(() => {
    const groups = new Map<string, LegalTemplateFieldToken[]>()
    data.campiDisponibili.forEach((field) => {
      const key = field.group || 'Dati'
      groups.set(key, [...(groups.get(key) || []), field])
    })
    return Array.from(groups.entries()).slice(0, 7)
  }, [data.campiDisponibili])
  const selectedPractice = useMemo(
    () => data.precompilazione.pratiche.find((item) => item.id === selectedPracticeId),
    [data.precompilazione.pratiche, selectedPracticeId],
  )
  const recipientSuggestions = selectedPractice?.destinatari.length ? selectedPractice.destinatari : data.precompilazione.destinatari
  const documentSuggestions = selectedPractice?.documenti || []
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
    () => documentSuggestions.filter((item) => item.documentoUfficio || item.acquisitoDaPortale || item.notificaRichiesta),
    [documentSuggestions],
  )
  const officeMonitor = selectedPractice?.documentoUfficioMonitor
  const pendingOfficeReleases = officeMonitor?.documentiRilasciati || []
  const officeAcquisitionHref = selectedPractice?.portaleAcquisizioneHref || data.portaleServizi.acquisizioneHref
  const officeAcquisitionRequired = Boolean(officeMonitor?.documentiDaAcquisire || officeMonitor?.stato === 'da_acquisire')
  const officeAcquisitionCompleted = officeDocuments.some((item) => item.acquisitoDaPortale)
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
    ? data.automazioneGuidata.notifica
    : tab === 'deposito'
      ? data.automazioneGuidata.deposito
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
    officeAcquisitionCompleted ? 'documento_portale_acquisito' : '',
  ].filter(Boolean).length

  const localDateTime = () => {
    const now = new Date()
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset())
    return now.toISOString().slice(0, 16)
  }

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
        '{{ notifica.luogo }}, {{ notifica.data }}',
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
    }))
  }

  const documentEvidenceName = (documento: LegalDocumentSuggestion) => {
    if (documento.riferimentoPortale && documento.nomeFile) return `${documento.riferimentoPortale} - ${documento.nomeFile}`
    return documento.riferimentoPortale || documento.nomeFile || documento.label
  }

  const depositDocumentPayload = (documento: LegalDocumentSuggestion): EvidenceDocumentPayload => ({
    nome_file: documentEvidenceName(documento),
    descrizione: documento.descrizione || documento.label,
    origine: documento.origine || 'nativo_digitale',
    hash_sha256: documento.hashSha256,
    riferimento_portale: documento.riferimentoPortale,
    file_originale: documento.nomeFile,
  })

  const syncDepositoFromDocuments = (ids: string[]) => {
    const rows = ids
      .map((id) => documentSuggestions.find((item) => item.id === id))
      .filter((item): item is LegalDocumentSuggestion => Boolean(item))
    setDeposito((current) => ({
      ...current,
      atto_notificato: rows.length ? rows.map(documentEvidenceName).join('; ') : current.atto_notificato,
      atto_sha256: rows.length === 1 ? rows[0].hashSha256 || current.atto_sha256 : current.atto_sha256,
    }))
  }

  const applyDocument = (documento: LegalDocumentSuggestion) => {
    setSelectedDocumentId(documento.id)
    setSelectedDepositDocumentIds([documento.id])
    setNotifica((current) => ({
      ...current,
      nome_file: documento.nomeFile || current.nome_file,
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
    setDeposito((current) => ({
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
    const requiresAttestation = documento.necessitaAttestazione || originNeedsAttestazione(documento.origine)
    return {
      nome_file: documento.nomeFile,
      descrizione: documento.descrizione || documento.label,
      origine: documento.origine || 'nativo_digitale',
      hash_sha256: documento.hashSha256,
      data_comunicazione_cancelleria: documento.origine === 'comunicazione_cancelleria' ? documento.dataDocumento : '',
      fonte_documento: documento.fonte,
      riferimento_portale: documento.riferimentoPortale,
      servizio_portale: documento.servizioPortale,
      documento_ufficio: documento.documentoUfficio,
      acquisito_da_portale: documento.acquisitoDaPortale,
      notifica_richiesta: documento.notificaRichiesta,
      data_rilascio_portale: documento.dataRilascioPortale,
      attestazione_conformita: notifica.attestazione_conformita,
      attestazione_conformita_presente: Boolean(notifica.attestazione_conformita.trim()) || (attestazioniAutomatiche && requiresAttestation),
    }
  }

  const manualNotificationDocument = (): NotificaDocumentPayload | null => {
    if (!notifica.nome_file && !notifica.descrizione_documento) return null
    const requiresAttestation = originNeedsAttestazione(notifica.origine_documento)
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
      attestazione_conformita: notifica.attestazione_conformita,
      attestazione_conformita_presente: Boolean(notifica.attestazione_conformita.trim()) || (attestazioniAutomatiche && requiresAttestation),
    }
  }

  const notificationDocumentPayloads = (): NotificaDocumentPayload[] => {
    const selectedRows = selectedNotificationDocuments.map(documentSuggestionPayload)
    const uploadedRows = manualNotificationDocuments.map((documento) => ({
      ...documento,
      attestazione_conformita: documento.attestazione_conformita || notifica.attestazione_conformita,
      attestazione_conformita_presente: Boolean(documento.attestazione_conformita_presente)
        || Boolean(notifica.attestazione_conformita.trim())
        || (attestazioniAutomatiche && originNeedsAttestazione(documento.origine)),
    }))
    const manual = manualNotificationDocument()
    const rows = manual ? [...selectedRows, ...uploadedRows, manual] : [...selectedRows, ...uploadedRows]
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
    setNotificationFilesMessage('Calcolo impronte SHA-256 degli allegati...')
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
        attestazione_conformita: notifica.attestazione_conformita,
        attestazione_conformita_presente: Boolean(notifica.attestazione_conformita.trim()) || (attestazioniAutomatiche && originNeedsAttestazione(origin)),
      })
    }
    setManualNotificationDocuments((current) => [...current, ...calculated])
    const withoutHash = calculated.filter((item) => !item.hash_sha256)
    setNotificationFilesMessage(withoutHash.length ? 'Allegati aggiunti; per alcuni file incolla l’impronta SHA-256 se richiesta dal controllo.' : 'Allegati aggiunti e impronte SHA-256 calcolate.')
  }

  const toggleNotificationDocument = (documento: LegalDocumentSuggestion, checked: boolean) => {
    setSelectedNotificationDocumentIds((current) => {
      const next = checked
        ? Array.from(new Set([...current, documento.id]))
        : current.filter((id) => id !== documento.id)
      return next
    })
    if (checked && !notifica.nome_file) {
      setNotifica((current) => ({
        ...current,
        nome_file: documento.nomeFile || current.nome_file,
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
    }
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
    setSelectedPracticeId(practice.id)
    const unicoDestinatario = practice.destinatari.length === 1 ? practice.destinatari[0] : null
    const documentIds = practice.documenti.map((documento) => documento.id).filter(Boolean)
    const primoDocumento = practice.documenti[0] || null
    const hasFascicoloDocument = practice.documenti.some((documento) => ['copia_fascicolo_informatico', 'comunicazione_cancelleria'].includes(documento.origine))
    const hasScansioneDocument = practice.documenti.some((documento) => documento.origine === 'scansione_analogico')
    setSelectedRecipientId(unicoDestinatario?.id || '')
    setSelectedDocumentId(primoDocumento?.id || '')
    setSelectedNotificationDocumentIds(documentIds)
    setSelectedDepositDocumentIds(documentIds)
    setSelectedClientId(practice.clienteId || '')
    setNotifica((current) => ({
      ...current,
      pratica_codice: practice.numero || current.pratica_codice,
      template_id: hasFascicoloDocument
        ? 'relata_pec_con_attestazione_fascicolo'
        : hasScansioneDocument
          ? 'relata_pec_con_attestazione_scansione_analogica'
          : practice.modelloSuggerito || current.template_id,
      assistito_nome: practice.assistitoNome || current.assistito_nome,
      assistito_cf: practice.assistitoCf || current.assistito_cf,
      procedimento_pendente: practice.procedimento.presente || current.procedimento_pendente,
      ufficio_giudiziario: practice.procedimento.ufficio || current.ufficio_giudiziario,
      sezione: practice.procedimento.sezione || current.sezione,
      numero_rg: practice.procedimento.numeroRg || current.numero_rg,
      anno_rg: practice.procedimento.annoRg || current.anno_rg,
      destinatario_nome: unicoDestinatario?.nome || current.destinatario_nome || practice.controparte,
      destinatario_cf: unicoDestinatario?.codiceFiscalePiva || current.destinatario_cf || practice.controparteCf,
      destinatario_pec: unicoDestinatario?.pec || current.destinatario_pec,
      destinatario_parte_rappresentata: unicoDestinatario?.parteRappresentata || current.destinatario_parte_rappresentata,
      ruolo_destinatario: unicoDestinatario?.ruolo || current.ruolo_destinatario,
      fonte_pec_destinatario: unicoDestinatario?.fontePecSuggerita || current.fonte_pec_destinatario,
      nome_file: primoDocumento?.nomeFile || current.nome_file,
      descrizione_documento: primoDocumento?.descrizione || current.descrizione_documento,
      origine_documento: primoDocumento?.origine || current.origine_documento,
      hash_sha256: primoDocumento?.hashSha256 || current.hash_sha256,
    }))
    setModelFields((current) => ({
      ...current,
      procedimento_giudice: practice.procedimento.giudice || current.procedimento_giudice || '',
      tipo_procedimento: practice.procedimento.tipoProcedimento || current.tipo_procedimento || '',
      destinatario_parte_rappresentata: unicoDestinatario?.parteRappresentata || current.destinatario_parte_rappresentata || '',
    }))
    setCliente((current) => ({
      ...current,
      cliente_nome: practice.assistitoNome || current.cliente_nome,
      ufficio_giudiziario: practice.procedimento.ufficio || current.ufficio_giudiziario,
      numero_rg: practice.procedimento.numeroRg || current.numero_rg,
      anno_rg: practice.procedimento.annoRg || current.anno_rg,
      provvedimento_descrizione: primoDocumento?.descrizione || current.provvedimento_descrizione,
    }))
    setDeposito((current) => ({
      ...current,
      atto_notificato: practice.documenti.length ? practice.documenti.map(documentEvidenceName).join('; ') : current.atto_notificato,
      atto_sha256: practice.documenti.length === 1 ? practice.documenti[0].hashSha256 || current.atto_sha256 : current.atto_sha256,
      destinatario_nome: unicoDestinatario?.nome || current.destinatario_nome,
    }))
  }

  useEffect(() => {
    if (!data.precompilazione.pratiche.length || selectedPracticeId) return
    const params = new URLSearchParams(window.location.search)
    const practiceId = params.get('id_fascicolo') || params.get('id_fasc') || params.get('fascicolo')
    const phase = params.get('fase')
    if (phase === 'deposito') setTab('deposito')
    if (phase === 'notifica') setTab('notifica')
    if (!practiceId) return
    const practice = data.precompilazione.pratiche.find((item) => item.id === practiceId)
    if (practice) applyPractice(practice)
  }, [data.precompilazione.pratiche, selectedPracticeId])

  const buildNotificaPayload = (includeDraft: boolean): Record<string, unknown> => {
    const selectedOfficeAcquired = selectedNotificationDocuments.some((documento) => documento.acquisitoDaPortale)
    const documentOfficeAcquired = selectedOfficeAcquired || officeAcquisitionCompleted
    const payload: Record<string, unknown> = {
      ...notifica,
      operazione: 'notifica_pec_l53',
      template_fields: modelFields,
      oggetto_pec: data.mandatorySubject,
      documenti: notificationDocumentPayloads(),
      attestazione_multipla: attestazioniAutomatiche && notificationNeedsAttestazione,
      documento_ufficio_rilasciato: Boolean(officeDocuments.length || officeAcquisitionRequired || pendingOfficeReleases.length),
      acquisizione_portale_richiesta: officeAcquisitionRequired,
      documento_ufficio_acquisito: documentOfficeAcquired,
      acquisizione_portale_completata: documentOfficeAcquired,
      portale_servizi: data.portaleServizi.defaultPortal,
      portale_acquisizione_href: officeAcquisitionHref,
    }
    if (includeDraft && relataDraftDirty && relataDraftText.trim()) {
      payload.relata_override_text = relataDraftText.trim()
    }
    return payload
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

  const previewPayloadKey = JSON.stringify({ notifica, modelFields, selectedNotificationDocumentIds, manualNotificationDocuments, attestazioniAutomatiche })

  useEffect(() => {
    if (loading || tab !== 'notifica') return undefined
    const handle = window.setTimeout(() => {
      void refreshRelataPreview(true)
    }, 700)
    return () => window.clearTimeout(handle)
  }, [previewPayloadKey, loading, tab])

  const buildDepositoPayload = (): Record<string, unknown> => {
    const atti = selectedDepositDocuments.map(depositDocumentPayload)
    const payload: Record<string, unknown> = { ...deposito }
    if (atti.length) {
      payload.atti_notificati = atti
      payload.atto_notificato = atti.map((item) => item.nome_file).join('; ')
      if (atti.length === 1 && atti[0].hash_sha256) payload.atto_sha256 = atti[0].hash_sha256
    }
    return payload
  }

  const run = async (key: TabKey) => {
    setWorking(true)
    setResult({ ...emptyResult, message: 'Controllo in corso...' })
    const endpoint = key === 'notifica' ? data.azioni.notifica : key === 'deposito' ? data.azioni.provaDeposito : data.azioni.comunicazioneCliente
    const payload = key === 'notifica'
      ? buildNotificaPayload(true)
      : key === 'deposito'
        ? buildDepositoPayload()
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
    setResult(response)
    setWorking(false)
  }

  const clearPracticeSelection = () => {
    setSelectedPracticeId('')
    setSelectedRecipientId('')
    setSelectedDocumentId('')
    setSelectedNotificationDocumentIds([])
    setSelectedDepositDocumentIds([])
    setSelectedClientId('')
  }

  const changeNotifica = (key: keyof typeof notifica, value: string | boolean) => setNotifica((current) => ({ ...current, [key]: value }))
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
    if (key === 'destinatario_nome' || key === 'pec_inviata' || key === 'rac_file' || key === 'rdac_file') {
      return refreshDepositReference(current, next)
    }
    return next
  })
  const updateDepositoFile = (fileKey: keyof typeof deposito, shaKey: keyof typeof deposito, fileName: string, sha256: string) => {
    setDeposito((current) => refreshDepositReference(current, { ...current, [fileKey]: fileName, [shaKey]: sha256 }))
  }
  const applyDepositFile = (current: typeof deposito, kind: DepositEvidenceKind, fileName: string, sha256: string): typeof deposito => {
    const next = { ...current }
    if (kind === 'atto') {
      next.atto_notificato = current.atto_notificato || fileName
      next.atto_sha256 = sha256
    } else if (kind === 'relata') {
      next.relata_firmata = fileName
      next.relata_sha256 = sha256
    } else if (kind === 'pec') {
      next.pec_inviata = fileName
      next.pec_inviata_sha256 = sha256
    } else if (kind === 'rac') {
      next.rac_file = fileName
      next.rac_sha256 = sha256
    } else if (kind === 'rdac') {
      next.rdac_file = fileName
      next.rdac_sha256 = sha256
    }
    return refreshDepositReference(current, next)
  }
  const handleDepositEvidenceFiles = async (files: FileList | null) => {
    const selected = Array.from(files || [])
    if (!selected.length) return
    setDepositAutoMessage('Calcolo impronte SHA-256 in corso...')
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
    setDepositAutoMessage(incomplete.length ? 'Alcune impronte non sono state calcolate: riprova o inseriscile manualmente.' : 'File riconosciuti e impronte SHA-256 calcolate.')
  }
  const changeCliente = (key: keyof typeof cliente, value: string) => setCliente((current) => ({ ...current, [key]: value }))
  const changeModelField = (key: string, value: string) => setModelFields((current) => ({ ...current, [key]: value }))

  return (
    <main className="iu-content iu-legal-notice-page">
      <section className="iu-legal-hero">
        <div>
          <span className="iu-legal-eyebrow"><Scale size={16} /> Notifiche e comunicazioni</span>
          <h1>Notifica, prova e comunicazione restano separate</h1>
          <p>La notifica ex L. 53/1994 prepara relata, controlli PEC e ricevuta completa. Il deposito raccoglie la prova. Il cliente riceve solo una comunicazione informativa.</p>
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
          text="Atto notificato, relata firmata, RAC e RdAC originali."
          onClick={() => { setTab('deposito'); setResult(emptyResult) }}
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
                  <Field label="Pratica IUSENTRA" wide hint="Scegli una pratica per compilare assistito, procedimento, destinatari e documenti già presenti nel gestionale.">
                    <select
                      value={selectedPracticeId}
                      onChange={(event) => {
                        const practice = data.precompilazione.pratiche.find((item) => item.id === event.currentTarget.value)
                        if (practice) applyPractice(practice)
                        else clearPracticeSelection()
                      }}
                    >
                      <option value="">Seleziona pratica</option>
                      {data.precompilazione.pratiche.map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}
                    </select>
                  </Field>
                  <Field label="Destinatario suggerito" hint={recipientSuggestions.length ? 'PEC e fonte vengono proposte dai soggetti collegati.' : 'Aggiungi soggetti con PEC alla pratica per compilare anche questo campo.'}>
                    <select
                      value={selectedRecipientId}
                      onChange={(event) => {
                        const recipient = recipientSuggestions.find((item) => item.id === event.currentTarget.value)
                        if (recipient) applyRecipient(recipient)
                        else setSelectedRecipientId('')
                      }}
                    >
                      <option value="">Seleziona destinatario</option>
                      {recipientSuggestions.map((item) => <option value={item.id} key={`${item.id}-${item.ruolo}`}>{item.label}{item.pec ? ` - ${item.pec}` : ''}</option>)}
                    </select>
                  </Field>
                  <div className="iu-legal-document-picker iu-legal-field--wide">
                    <div className="iu-legal-template-preview__header">
                      <div>
                        <strong>Documenti da notificare</strong>
                        <span>{documentSuggestions.length ? "La pratica seleziona automaticamente tutti i documenti; puoi togliere solo quelli non da notificare." : "Seleziona una pratica con documenti per compilare l'elenco."}</span>
                      </div>
                      {documentSuggestions.length ? (
                        <div className="iu-legal-picker-actions">
                          <button type="button" onClick={() => setSelectedNotificationDocumentIds(documentSuggestions.map((item) => item.id).filter(Boolean))}>
                            <CheckCircle2 size={14} /> Tutti
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
                        <span>Puoi scegliere più PDF o file firmati: IUSENTRA li aggiunge alla relata e calcola le impronte quando il browser lo consente.</span>
                        {notificationFilesMessage ? <small>{notificationFilesMessage}</small> : null}
                      </div>
                      <label className="iu-legal-evidence-uploader__button">
                        <Paperclip size={17} />
                        Scegli allegati
                        <input
                          type="file"
                          multiple
                          accept=".pdf,.pdfa,.p7m"
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
                            <span>{documento.label}{documento.necessitaAttestazione ? ' - attestazione richiesta' : ''}</span>
                          </label>
                        ))}
                      </div>
                    ) : <p className="iu-legal-empty">Nessun documento disponibile per la pratica selezionata.</p>}
                    {notificationDocumentPayloads().length ? (
                      <div className="iu-legal-selected-documents" aria-label="Elenco documenti allegati alla relata">
                        {notificationDocumentPayloads().map((documento, index) => (
                          <span key={`${documento.nome_file}-${index}`}>
                            <FileText size={15} />
                            <em>{index + 1}. {documento.nome_file || 'Documento senza nome'}{documento.descrizione ? ` - ${documento.descrizione}` : ''}</em>
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
                        <strong>{officeAcquisitionRequired ? "Documento d'ufficio da acquisire" : officeAcquisitionCompleted ? "Documento d'ufficio acquisito" : 'Controllo Portale Servizi pronto'}</strong>
                        <span>{officeMonitor?.messaggio || 'IUSENTRA prepara il collegamento con fascicolo, numero RG e ufficio. L’avvocato accede al portale e conferma il documento scaricato.'}</span>
                      </div>
                      <a href={officeAcquisitionHref}><FileDown size={15}/> {officeAcquisitionRequired ? 'Acquisisci dal Portale Servizi' : 'Apri Portale Servizi'}</a>
                    </div>
                    {pendingOfficeReleases.length ? (
                      <div className="iu-legal-office-monitor__list" aria-label="Documenti rilasciati dal portale">
                        {pendingOfficeReleases.map((release, index) => (
                          <span key={release.documentoId || release.riferimentoPortale || `${release.nome}-${index}`}>
                            <Inbox size={15}/>
                            <em>{release.nome || release.tipo || "Documento d'ufficio"}</em>
                            <small>{[release.fontePortale || data.portaleServizi.label, release.ufficio, release.numeroRg && release.annoRg ? `R.G. ${release.numeroRg}/${release.annoRg}` : '', release.dataDeposito].filter(Boolean).join(' · ')}</small>
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
                            <small>{documento.acquisitoDaPortale ? 'Acquisito dal Portale Servizi' : documento.notificaRichiesta ? 'Da notificare' : 'Da verificare'}</small>
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>
                <div className="iu-legal-auto-notes">
                  <span><FolderOpen size={15} /> {data.precompilazione.pratiche.length} pratiche disponibili per la compilazione assistita.</span>
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
                          {relataPreview.blockers.map((item) => <span key={item}><AlertTriangle size={15} /> {item}</span>)}
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
                <label className="iu-legal-check"><input type="checkbox" checked={notifica.mittente_avvocato_abilitato} onChange={(event) => changeNotifica('mittente_avvocato_abilitato', event.currentTarget.checked)} /><span>Avvocato abilitato alla notifica in proprio</span></label>
                <label className="iu-legal-check"><input type="checkbox" checked={notifica.mittente_pec_validata} onChange={(event) => changeNotifica('mittente_pec_validata', event.currentTarget.checked)} /><span>PEC notificante validata</span></label>
                <Field label="Luogo relata"><input value={notifica.luogo} onChange={(event) => changeNotifica('luogo', event.currentTarget.value)} /></Field>
                <Field label="Data relata"><input type="date" value={notifica.data_relata} onChange={(event) => changeNotifica('data_relata', event.currentTarget.value)} /></Field>
                <Field label="Parte assistita"><input value={notifica.assistito_nome} onChange={(event) => changeNotifica('assistito_nome', event.currentTarget.value)} /></Field>
                <Field label="C.F. / P. IVA assistito"><input value={notifica.assistito_cf} onChange={(event) => changeNotifica('assistito_cf', event.currentTarget.value.toUpperCase())} /></Field>
                <Field label="Ruolo destinatario">
                  <select value={notifica.ruolo_destinatario} onChange={(event) => changeNotifica('ruolo_destinatario', event.currentTarget.value)}>
                    {data.ruoliDestinatario.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    <option value="cliente">Cliente (da bloccare come notifica ordinaria)</option>
                  </select>
                </Field>
                <Field label="Destinatario"><input value={notifica.destinatario_nome} onChange={(event) => changeNotifica('destinatario_nome', event.currentTarget.value)} /></Field>
                <Field label="C.F. / P. IVA destinatario"><input value={notifica.destinatario_cf} onChange={(event) => changeNotifica('destinatario_cf', event.currentTarget.value.toUpperCase())} /></Field>
                <Field label="PEC destinatario"><input type="email" value={notifica.destinatario_pec} onChange={(event) => changeNotifica('destinatario_pec', event.currentTarget.value)} /></Field>
                <Field label="Fonte PEC destinatario">
                  <select value={notifica.fonte_pec_destinatario} onChange={(event) => changeNotifica('fonte_pec_destinatario', event.currentTarget.value)}>
                    {data.registriPec.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                  </select>
                </Field>
                <label className="iu-legal-check"><input type="checkbox" checked={notifica.destinatario_pec_pubblico_elenco} onChange={(event) => changeNotifica('destinatario_pec_pubblico_elenco', event.currentTarget.checked)} /><span>PEC destinatario verificata su pubblico elenco</span></label>
                <Field label="Parte rappresentata"><input value={notifica.destinatario_parte_rappresentata} onChange={(event) => changeNotifica('destinatario_parte_rappresentata', event.currentTarget.value)} /></Field>
                <Field label="Data e ora verifica PEC" hint="Da compilare solo dopo il controllo effettivo del pubblico elenco.">
                  <div className="iu-legal-inline-action">
                    <input type="datetime-local" value={notifica.data_verifica_pec} onChange={(event) => changeNotifica('data_verifica_pec', event.currentTarget.value)} />
                    <button type="button" onClick={() => changeNotifica('data_verifica_pec', localDateTime())}>Ora</button>
                  </div>
                </Field>
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
                <Field label="Impronta SHA-256 allegato" hint="Facoltativa per la notifica; viene compilata automaticamente quando scegli file dal browser.">
                  <input value={notifica.hash_sha256} maxLength={64} onChange={(event) => changeNotifica('hash_sha256', normalizeSha256Input(event.currentTarget.value))} placeholder="64 caratteri esadecimali" />
                </Field>
                <div className="iu-legal-template-actions iu-legal-field--wide">
                  <button type="button" onClick={addManualNotificationDocument}>
                    <PlusCircle size={15} /> Aggiungi allegato manuale
                  </button>
                </div>
                {notificationNeedsAttestazione ? (
                  <>
                    <label className="iu-legal-check iu-legal-field--wide">
                      <input type="checkbox" checked={attestazioniAutomatiche} onChange={(event) => setAttestazioniAutomatiche(event.currentTarget.checked)} />
                      <span>Prepara automaticamente le attestazioni per tutti gli allegati che le richiedono</span>
                    </label>
                    <Field label="Attestazione di conformità" wide hint="Puoi integrare il testo; il sistema genera comunque il blocco per copie da fascicolo, comunicazioni di cancelleria e scansioni analogiche.">
                      <textarea value={notifica.attestazione_conformita} rows={4} onChange={(event) => changeNotifica('attestazione_conformita', event.currentTarget.value)} />
                    </Field>
                  </>
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
                <label className="iu-legal-check"><input type="checkbox" checked={notifica.ricevuta_completa} onChange={(event) => changeNotifica('ricevuta_completa', event.currentTarget.checked)} /><span>Ricevuta completa</span></label>
                <label className="iu-legal-check"><input type="checkbox" checked={notifica.relata_firmata} onChange={(event) => changeNotifica('relata_firmata', event.currentTarget.checked)} /><span>Relata firmata</span></label>
                <label className="iu-legal-check"><input type="checkbox" checked={notifica.relata_documento_separato} onChange={(event) => changeNotifica('relata_documento_separato', event.currentTarget.checked)} /><span>Relata come documento separato</span></label>
                <label className="iu-legal-check iu-legal-field--wide"><input type="checkbox" checked={notifica.approvazione_avvocato} onChange={(event) => changeNotifica('approvazione_avvocato', event.currentTarget.checked)} /><span>Approvazione finale dell'avvocato prima dell'invio</span></label>
              </div>
              <button className="iu-legal-submit" type="button" disabled={working} onClick={() => run('notifica')}><ShieldCheck size={16} /> {working ? 'Controllo...' : 'Controlla relata'}</button>
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
                  <Field label="Pratica IUSENTRA" wide hint="Usa la stessa pratica della notifica o scegline una per preparare la prova.">
                    <select
                      value={selectedPracticeId}
                      onChange={(event) => {
                        const practice = data.precompilazione.pratiche.find((item) => item.id === event.currentTarget.value)
                        if (practice) applyPractice(practice)
                        else clearPracticeSelection()
                      }}
                    >
                      <option value="">Seleziona pratica</option>
                      {data.precompilazione.pratiche.map((item) => <option value={item.id} key={`deposito-${item.id}`}>{item.label}</option>)}
                    </select>
                  </Field>
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
                            <span>{item.riferimentoPortale ? `${item.riferimentoPortale} - ${item.label}` : item.label}</span>
                          </label>
                        ))}
                      </div>
                      {selectedDepositDocuments.length ? (
                        <div className="iu-legal-selected-documents">
                          {selectedDepositDocuments.map((item) => (
                            <span key={`deposito-selected-${item.id}`}>
                              <FileCheck2 size={15} />
                              {documentEvidenceName(item)}{item.hashSha256 ? ` - SHA-256 ${item.hashSha256.slice(0, 12)}...` : ''}
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
                  <span><Inbox size={15} /> RAC e RdAC restano originali digitali da associare.</span>
                </div>
              </div>
              <div className="iu-legal-evidence-uploader">
                <div className="iu-legal-evidence-uploader__text">
                  <strong>Allega i file della prova</strong>
                  <span>Scegli insieme atto, relata firmata, PEC inviata, RAC e RdAC: IUSENTRA li riconosce dal nome e calcola automaticamente tutte le impronte SHA-256.</span>
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
                <EvidenceSummaryRow label="RAC" fileName={deposito.rac_file} shaValue={deposito.rac_sha256} />
                <EvidenceSummaryRow label="RdAC" fileName={deposito.rdac_file} shaValue={deposito.rdac_sha256} />
              </div>
              <div className="iu-legal-form-grid iu-legal-form-grid--compact">
                <Field label="Destinatario" hint="Il nominativo può arrivare dalla pratica o essere inserito manualmente.">
                  <input value={deposito.destinatario_nome} onChange={(event) => changeDeposito('destinatario_nome', event.currentTarget.value)} />
                </Field>
                <label className="iu-legal-check"><input type="checkbox" checked={Boolean(deposito.ricevuta_completa)} onChange={(event) => changeDeposito('ricevuta_completa', event.currentTarget.checked)} /><span>Confermo che la RdAC selezionata è completa</span></label>
                <Field label="Riferimenti ricevute in DatiAtto.xml" wide hint="I riferimenti vengono preparati dai file scelti; puoi integrarli prima del controllo.">
                  <textarea value={deposito.dati_atto_ricevute} rows={3} onChange={(event) => changeDeposito('dati_atto_ricevute', event.currentTarget.value)} placeholder="RAC e RdAC associate al destinatario..." />
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
                    label="RAC originale"
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
                    label="RdAC originale"
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
                  <Field label="Pratica IUSENTRA" wide hint="La pratica compila cliente, ufficio, RG e documento informativo.">
                    <select
                      value={selectedPracticeId}
                      onChange={(event) => {
                        const practice = data.precompilazione.pratiche.find((item) => item.id === event.currentTarget.value)
                        if (practice) applyPractice(practice)
                        else clearPracticeSelection()
                      }}
                    >
                      <option value="">Seleziona pratica</option>
                      {data.precompilazione.pratiche.map((item) => <option value={item.id} key={`cliente-pratica-${item.id}`}>{item.label}</option>)}
                    </select>
                  </Field>
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
                  <span><FolderOpen size={15} /> {data.precompilazione.pratiche.length} pratiche utilizzabili.</span>
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
            <Panel title="Passaggi automatici" subtitle={tab === 'deposito' ? 'Prova e deposito' : 'Notifica L. 53/1994'} icon={<ClipboardCheck size={17} />}>
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
          <ResultPanel result={result} />
          <Panel title="Regole di blocco" subtitle="Controlli prima di firma e invio" icon={<AlertTriangle size={17} />}>
            <div className="iu-legal-list">
              <span><ShieldCheck size={15} /> PEC mittente e destinatario da pubblico elenco.</span>
              <span><FileDown size={15} /> Documento d'ufficio rilasciato acquisito dal Portale Servizi prima della relata.</span>
              <span><FileSignature size={15} /> Relata separata e firmata digitalmente.</span>
              <span><Inbox size={15} /> Ricevuta completa, RAC e RdAC originali.</span>
              <span><UserRound size={15} /> Il cliente resta nel percorso informativo.</span>
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
            <Panel title="Catalogo modelli relata" subtitle={data.templateCatalogVersion ? `Versione ${data.templateCatalogVersion}` : 'Modelli caricati'} icon={<FileSignature size={17} />}>
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
        body="Posso aiutarti a controllare relata, attestazione, pubblico elenco PEC e prova da depositare, distinguendo notifica e semplice comunicazione al cliente."
        primaryHref="#lex"
        primaryLabel="Controlla percorso"
        secondaryHref={data.azioni.fascicoli}
        secondaryLabel="Vai ai fascicoli"
      />
    </main>
  )
}
