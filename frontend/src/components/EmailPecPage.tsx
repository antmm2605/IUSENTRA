import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  Archive,
  CheckCircle2,
  Clock3,
  Download,
  Eye,
  FileCheck2,
  FileSignature,
  Inbox,
  Mail,
  MailCheck,
  Paperclip,
  RefreshCw,
  Reply,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  Undo2,
  Wrench,
} from 'lucide-react'
import { Badge, Button, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import { JsonPostForm } from './JsonPostForm'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip'
import {
  emptyEmailOrdinariaPage,
  emptyEmailPecPage,
  folderLabel,
  getEmailOrdinariaPage,
  getEmailOrdinariaDetail,
  getEmailPecPage,
  getEmailPecDetail,
  submitEmailBulkAction,
  type EmailFolder,
  type EmailDetailData,
  type EmailPecPageData,
  type EmailPecRow,
  type EmailStatus,
  type PecAuditField,
  type PecAuditSummary,
} from '../emailData'
import { csrfToken, submitFormJson, type FormSubmitResult } from '../formSubmit'
import './EmailPecPage.css'

type MailboxMode = 'pec' | 'ordinaria'
type SortKey = 'recenti' | 'mittente' | 'oggetto' | 'pct'
type JsonRecord = Record<string, unknown>

const LOCAL_SIGNER_BASE_URL = 'http://127.0.0.1:27272'
const LEGAL_NOTIFICATION_SUBJECT = 'notificazione ai sensi della legge n. 53 del 1994'

function textValue(value: unknown, fallback = ''): string {
  const text = typeof value === 'string' ? value.trim() : ''
  return text || fallback
}

async function fetchJsonWithTimeout(endpoint: string, timeoutMs: number, init?: RequestInit): Promise<JsonRecord> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(endpoint, { ...init, signal: controller.signal })
    const payload = await response.json().catch(() => ({})) as JsonRecord
    if (!response.ok || payload.ok === false) {
      throw new Error(textValue(payload.message, textValue(payload.messaggio, textValue(payload.errore, 'Operazione non riuscita.'))))
    }
    return payload
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('Local Signer non ha risposto entro il tempo limite. Verifica che sia aperto sul PC dello studio.')
    }
    if (error instanceof TypeError) {
      throw new Error('Local Signer non rilevato sul PC dello studio. Avvialo e riprova.')
    }
    throw error
  } finally {
    window.clearTimeout(timer)
  }
}

function fileAttachment(file: File): Promise<JsonRecord> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = String(reader.result || '')
      const contentBase64 = result.includes(',') ? result.split(',').pop() || '' : result
      resolve({
        filename: file.name,
        content_base64: contentBase64,
        mime_type: file.type || 'application/octet-stream',
      })
    }
    reader.onerror = () => reject(new Error(`Allegato ${file.name} non leggibile dal browser.`))
    reader.readAsDataURL(file)
  })
}

async function savedPecSmtpPayload(): Promise<JsonRecord> {
  const token = csrfToken()
  const result = await fetchJsonWithTimeout('/impostazioni/pec/local-smtp-payload', 10000, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...(token ? { 'X-CSRFToken': token } : {}),
    },
    body: JSON.stringify({}),
  })
  const payload = result.payload
  if (!payload || typeof payload !== 'object') {
    throw new Error('Configurazione PEC non disponibile. Verifica le impostazioni PEC dello studio.')
  }
  return payload as JsonRecord
}

const sortLabels: Record<SortKey, string> = {
  recenti: 'Più recenti',
  mittente: 'Mittente / destinatario',
  oggetto: 'Oggetto',
  pct: 'Esito PCT',
}

const mailboxCopy: Record<MailboxMode, {
  mode: MailboxMode
  includeTelematic: boolean
  emptyData: EmailPecPageData
  title: string
  eyebrow: string
  heroTitle: string
  heroText: string
  openLabel: string
  composeLabel: string
  syncLabel: string
  syncingLabel: string
  updatedLabel: string
  folderAria: string
  filtersAria: string
  statsAria: string
  emptyTitle: string
  emptyText: string
  previewEmptyTitle: string
  previewEmptyText: string
  sourceFallback: string
  lexContext: string
  lexTitle: string
  lexBody: string
  lexPrimaryLabel: string
}> = {
  pec: {
    mode: 'pec',
    includeTelematic: true,
    emptyData: emptyEmailPecPage,
    title: 'Email PEC',
    eyebrow: 'Email PEC',
    heroTitle: 'Casella PEC dello studio',
    heroText: 'Posta certificata, messaggi PST, allegati, esiti PCT e comunicazioni di cancelleria in una vista professionale unica.',
    openLabel: 'Apri casella',
    composeLabel: 'Componi PEC',
    syncLabel: 'Sincronizzazione PEC',
    syncingLabel: 'Sincronizzazione vista PEC...',
    updatedLabel: 'Dati PEC aggiornati',
    folderAria: 'Cartelle PEC',
    filtersAria: 'Filtri casella PEC',
    statsAria: 'Indicatori email PEC',
    emptyTitle: 'Nessuna PEC nella vista corrente',
    emptyText: 'Prova ad aggiornare IMAP, cambiare cartella o rimuovere i filtri.',
    previewEmptyTitle: 'Seleziona una PEC',
    previewEmptyText: 'La lettura rapida comparirà qui, con esiti PCT, allegati e azioni operative.',
    sourceFallback: 'casella PEC',
    lexContext: 'email-pec',
    lexTitle: 'Lex AI PEC',
    lexBody: 'Posso leggere il contesto della PEC selezionata, preparare risposta, estrarre RG, suggerire fascicolo e verificare esito PCT o comunicazione di cancelleria.',
    lexPrimaryLabel: 'Cerca comunicazioni',
  },
  ordinaria: {
    mode: 'ordinaria',
    includeTelematic: false,
    emptyData: emptyEmailOrdinariaPage,
    title: 'Email ordinaria',
    eyebrow: 'Email ordinaria',
    heroTitle: 'Casella email ordinaria dello studio',
    heroText: 'Messaggi ordinari ricevuti e inviati tramite la configurazione SMTP/IMAP dello studio, separati dalla PEC e consultabili senza confondere gli esiti telematici.',
    openLabel: 'Apri email',
    composeLabel: 'Componi email',
    syncLabel: 'Sincronizzazione email ordinaria',
    syncingLabel: 'Sincronizzazione vista email...',
    updatedLabel: 'Email ordinaria aggiornata',
    folderAria: 'Cartelle email ordinaria',
    filtersAria: 'Filtri email ordinaria',
    statsAria: 'Indicatori email ordinaria',
    emptyTitle: 'Nessuna email nella vista corrente',
    emptyText: 'Prova ad aggiornare IMAP, cambiare cartella o rimuovere i filtri.',
    previewEmptyTitle: 'Seleziona una email',
    previewEmptyText: 'La lettura rapida comparirà qui, con allegati, mittente, destinatari e azioni operative.',
    sourceFallback: 'casella email ordinaria',
    lexContext: 'email-ordinaria',
    lexTitle: 'Lex AI Email',
    lexBody: 'Posso aiutarti a preparare risposta, estrarre riferimenti cliente o fascicolo, riassumere il messaggio e proporre la prossima azione.',
    lexPrimaryLabel: 'Cerca comunicazioni',
  },
}

type MailboxCopy = (typeof mailboxCopy)[MailboxMode]

function sourceLabel(source: string, fallback: string): string {
  if (source === 'repository_reali') return 'dati dello studio'
  if (source === 'errore_controllato') return 'dati parziali'
  return source || fallback
}

type ComposeClient = {
  id: string
  name: string
  email: string
  pec: string
  fiscalId: string
}

function text(value: unknown): string {
  return typeof value === 'string' || typeof value === 'number' ? String(value).trim() : ''
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function firstText(recordValue: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const value = text(recordValue[key])
    if (value) return value
  }
  return ''
}

function composeClientName(item: Record<string, unknown>): string {
  return firstText(item, ['nome_completo', 'nomeCompleto', 'denominazione', 'ragione_sociale', 'label', 'name']) ||
    [text(item.nome), text(item.cognome)].filter(Boolean).join(' ').trim()
}

function composeClientsFromPayload(payload: unknown): ComposeClient[] {
  const source = Array.isArray(payload)
    ? payload
    : Array.isArray(record(payload).data)
      ? record(payload).data as unknown[]
      : Array.isArray(record(payload).items)
        ? record(payload).items as unknown[]
        : []
  return source.map((raw) => {
    const item = record(raw)
    const recapiti = record(item.recapiti)
    return {
      id: firstText(item, ['id', 'id_cliente', 'uuid']),
      name: composeClientName(item),
      email: firstText(item, ['email', 'mail']) || firstText(recapiti, ['email', 'mail']),
      pec: firstText(item, ['pec']) || firstText(recapiti, ['pec']),
      fiscalId: firstText(item, ['codice_fiscale', 'codiceFiscale', 'partita_iva', 'partitaIva']),
    }
  }).filter((item) => item.id && item.name).slice(0, 8)
}

function appendAddress(current: string, next: string): string {
  const address = next.trim()
  if (!address) return current
  const parts = current.split(/[;,]/).map((item) => item.trim()).filter(Boolean)
  if (parts.some((item) => item.toLowerCase() === address.toLowerCase())) return current
  return [...parts, address].join(', ')
}

function StatCard({ icon, label, value, note, tone = 'primary' }: { icon: ReactNode; label: string; value: number | string; note: string; tone?: EmailPecRow['tone'] }) {
  return (
    <article className={`iu-mail-stat iu-mail-stat--${tone}`}>
      <div>{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  )
}

function normaliseText(value: string): string {
  return value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
}

function folderIcon(folder: EmailFolder) {
  if (folder === 'INVIATI') return <Send size={15} />
  if (folder === 'CESTINO') return <Trash2 size={15} />
  return <Inbox size={15} />
}

function rowPerson(item: EmailPecRow): string {
  if (item.folder === 'INVIATI') return item.recipients || 'Destinatario non indicato'
  return item.senderName || item.sender || 'Mittente non indicato'
}

function initials(value: string, fallback: string): string {
  const parts = value.replace(/[<>@.]/g, ' ').split(/\s+/).filter(Boolean)
  return parts.slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || fallback
}

function isInsideQuery(item: EmailPecRow, query: string): boolean {
  const needle = normaliseText(query.trim())
  if (!needle) return true
  return normaliseText([
    item.sender,
    item.senderName,
    item.recipients,
    item.subject,
    item.preview,
    item.pctStatus,
    item.origin,
  ].join(' ')).includes(needle)
}

function sortRows(rows: EmailPecRow[], sort: SortKey): EmailPecRow[] {
  const copy = [...rows]
  if (sort === 'mittente') return copy.sort((a, b) => rowPerson(a).localeCompare(rowPerson(b), 'it'))
  if (sort === 'oggetto') return copy.sort((a, b) => a.subject.localeCompare(b.subject, 'it'))
  if (sort === 'pct') return copy.sort((a, b) => (b.pctStatus || '').localeCompare(a.pctStatus || '', 'it'))
  return copy.sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''))
}

function auditEventLabel(value: string): string {
  const labels: Record<string, string> = {
    pct_deposito: 'Deposito PCT',
    comunicazione_cancelleria: 'Cancelleria',
    notifica_l53: 'Notifica L. 53',
    notifica_giudice_pace: 'Giudice di Pace',
    notifica_unep: 'UNEP',
    pat_notifica_o_deposito: 'PAT',
    ptt_notifica_o_deposito: 'PTT',
    penale_snt: 'SNT penale',
    penale_deposito_portale: 'Portale penale',
    ricevuta_pec: 'Ricevuta PEC',
  }
  return labels[value] || value.replace(/_/g, ' ')
}

function fieldConfidence(audit: PecAuditSummary | undefined, key: string): PecAuditField | undefined {
  return audit?.confidence?.[key]
}

function confidencePercent(value: number): string {
  return `${Math.round(Math.max(0, Math.min(1, value || 0)) * 100)}%`
}

function fieldDisplayValue(field?: PecAuditField): string {
  if (!field) return 'Dato non disponibile'
  if (field.value && typeof field.value === 'object' && !Array.isArray(field.value)) {
    const recordValue = field.value as Record<string, unknown>
    return text(recordValue.email) || text(recordValue.name) || 'Valore strutturato'
  }
  if (typeof field.value === 'boolean') return field.value ? 'Sì' : 'No'
  return text(field.value) || 'Dato non disponibile'
}

function ConfidenceChip({ label, field }: { label: string; field?: PecAuditField }) {
  const confidence = field?.confidence ?? 0
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className={`iu-pec-confidence ${confidence >= 0.85 ? 'is-high' : confidence >= 0.6 ? 'is-mid' : 'is-low'}`}>
          <b>{label}</b>
          <strong>{confidencePercent(confidence)}</strong>
        </span>
      </TooltipTrigger>
      <TooltipContent>
        <span>{fieldDisplayValue(field)}. {field?.motivation || 'Confidenza non calcolata.'}</span>
      </TooltipContent>
    </Tooltip>
  )
}

function PecAuditBadges({ audit }: { audit?: PecAuditSummary }) {
  if (!audit) return null
  return (
    <>
      <Badge tone={audit.qualityTone}>{audit.qualityLabel}</Badge>
      <Badge tone={audit.signatureTone}>{audit.signatureLabel}</Badge>
      {audit.persisted === false ? <Badge tone={audit.storageTone}>{audit.storageLabel}</Badge> : null}
      {audit.eventType ? <Badge tone="info">{auditEventLabel(audit.eventType)}</Badge> : null}
    </>
  )
}

function auditOutcomeText(audit?: PecAuditSummary): string {
  if (!audit) return ''
  if (audit.persisted === false) {
    return 'Esito provvisorio: il software ha controllato i dati visibili, ma deve acquisire il MIME originale per chiudere conservazione, firme, OCR e verifica completa.'
  }
  if (audit.qualityTone === 'danger') return 'Esito critico: sono presenti anomalie da presidiare prima di archiviare o collegare la PEC.'
  if (audit.qualityTone === 'warning') return 'Esito da presidiare: il controllo automatico ha trovato elementi da verificare con azione operativa.'
  return 'Esito positivo: il controllo automatico non segnala anomalie bloccanti nella matrice configurata.'
}

function auditSuggestedAction(audit?: PecAuditSummary): string {
  if (!audit) return ''
  const recommended = audit.recommendedActions.find(Boolean)
  if (recommended) return recommended
  const firstIssue = audit.validationIssues.find((item) => item.detail || item.title)
  if (firstIssue) return firstIssue.detail || firstIssue.title
  if (audit.persisted === false) return 'Esegui controllo: acquisizione MIME da IMAP, verifica allegati/firme e aggiornamento esito.'
  if (audit.eventType === 'pct_deposito') return 'Verifica sequenza deposito: accettazione, consegna, esito controlli e accettazione finale.'
  if (audit.eventType) return 'Collega la comunicazione al fascicolo e presidia i termini indicati dalla PEC.'
  return 'Nessuna azione urgente rilevata; conserva la PEC nel fascicolo corretto se pertinente.'
}

function formatPecAuditDate(value: string): string {
  const raw = value.slice(0, 10)
  if (!raw) return ''
  try {
    return new Date(`${raw}T12:00:00`).toLocaleDateString('it-IT', { day: '2-digit', month: 'long', year: 'numeric' })
  } catch {
    return raw
  }
}

function auditDeadlineStatus(audit?: PecAuditSummary): string {
  const proposal = record(audit?.deadlineProposal)
  const autoCreate = proposal.auto_create === true || proposal.autoCreate === true
  const dueDate = text(proposal.due_date ?? proposal.dueDate)
  if (!autoCreate && !dueDate) return ''
  const dueLabel = formatPecAuditDate(dueDate) || dueDate
  if (dueLabel) return `Scadenza automatica di presidio: ${dueLabel}.`
  return 'Scadenza automatica di presidio prevista dal controllo PEC.'
}

function PecDepositLifecycle({ audit }: { audit?: PecAuditSummary }) {
  const lifecycle = record(audit?.depositLifecycle)
  const stage = record(lifecycle.current_stage)
  if (!Object.keys(lifecycle).length) return null
  const expectedNext = Array.isArray(lifecycle.expected_next) ? lifecycle.expected_next.map(record) : []
  const communication = text(lifecycle.communication)
  return (
    <div className="iu-pec-deposit-flow">
      <span>Deposito telematico</span>
      <strong>{text(stage.label) || 'Fase da ricondurre'}</strong>
      {expectedNext.length ? (
        <p>Da attendere o verificare: {expectedNext.map((item) => text(item.label)).filter(Boolean).join(', ')}.</p>
      ) : null}
      {communication ? <p>{communication}</p> : null}
    </div>
  )
}

function PecAuditInlineNotice({
  audit,
  onAction,
}: {
  audit?: PecAuditSummary
  onAction: (url: string, label: string) => void
}) {
  if (!audit) return null
  const question = audit.agentQuestions[0]
  const deadlineStatus = auditDeadlineStatus(audit)
  const issues = audit.validationIssues.slice(0, 4)
  const questions = audit.agentQuestions.slice(0, 5)
  const references = audit.normativeReferences.slice(0, 5)
  const unavailableTitle = 'Disponibile dopo l\'acquisizione del MIME originale'
  const actionButton = (url: string, label: string, icon: ReactNode) => (
    <button
      type="button"
      disabled={!url}
      title={url ? label : unavailableTitle}
      onClick={() => {
        if (url) onAction(url, label)
      }}
    >
      {icon} {label}
    </button>
  )
  return (
    <TooltipProvider delayDuration={120}>
      <div className="iu-pec-audit-panel" aria-label="Controllo automatico PEC">
        <header>
          <div>
            <span>Controllo automatico PEC</span>
            <strong>{audit.eventType ? auditEventLabel(audit.eventType) : audit.qualityLabel}</strong>
            <small>{auditOutcomeText(audit)} Azione suggerita: {auditSuggestedAction(audit)}{question ? ` Domanda guida: ${question}` : ''}</small>
            {deadlineStatus ? <p className="iu-pec-deadline-status"><Clock3 size={14} /> {deadlineStatus}</p> : null}
          </div>
          <div className="iu-pec-audit-badges">
            <PecAuditBadges audit={audit} />
          </div>
        </header>
        <div className="iu-pec-audit-grid">
          <article>
            <h3>Campi estratti</h3>
            <div className="iu-pec-confidence-grid">
              <ConfidenceChip label="Mittente" field={fieldConfidence(audit, 'mittente')} />
              <ConfidenceChip label="Invio" field={fieldConfidence(audit, 'data_invio')} />
              <ConfidenceChip label="Consegna" field={fieldConfidence(audit, 'data_consegna')} />
              <ConfidenceChip label="Ricevuta" field={fieldConfidence(audit, 'tipo_ricevuta')} />
              <ConfidenceChip label="Protocollo" field={fieldConfidence(audit, 'protocollo')} />
              <ConfidenceChip label="Contesto" field={fieldConfidence(audit, 'contesto_legale')} />
            </div>
            <small>Le percentuali indicano la qualità dell'estrazione automatica, non una decisione legale conclusiva.</small>
          </article>
          <article>
            <h3>Anomalie e allegati</h3>
            <PecDepositLifecycle audit={audit} />
            {issues.length ? (
              <ul>
                {issues.map((issue) => (
                  <li key={`${issue.code}-${issue.title}`}>
                    <AlertTriangle size={14} />
                    <span><b>{issue.title}</b>{issue.detail ? ` - ${issue.detail}` : ''}</span>
                  </li>
                ))}
              </ul>
            ) : <p>Nessuna anomalia segnalata dalla matrice automatica.</p>}
            {audit.attachments.length ? (
              <div className="iu-pec-attachment-strip">
                {audit.attachments.slice(0, 4).map((attachment) => (
                  <span key={`${attachment.name}-${attachment.classification}`}>
                    {attachment.name} · {attachment.classification || 'da confermare'}
                  </span>
                ))}
              </div>
            ) : null}
          </article>
          <article>
            <h3>Domande operative</h3>
            <ol>
              {questions.map((question) => <li key={question}>{question}</li>)}
            </ol>
            {references.length ? (
              <div className="iu-pec-norms">
                {references.map((reference) => <span key={reference.label}>{reference.label}</span>)}
              </div>
            ) : null}
          </article>
        </div>
        <footer>
          {audit.quickActions.runAudit ? (
            <button type="button" onClick={() => onAction(audit.quickActions.runAudit, 'Esegui controllo')}>
              <ShieldCheck size={15} /> Esegui controllo
            </button>
          ) : null}
          {actionButton(audit.quickActions.saveMatter, 'Salva nel fascicolo', <FileCheck2 size={15} />)}
          {actionButton(audit.quickActions.requestMissingAttachment, 'Richiedi allegato mancante', <Paperclip size={15} />)}
          {actionButton(audit.quickActions.scheduleDeadline, 'Scadenza automatica', <Clock3 size={15} />)}
          {audit.quickActions.openMime ? <a href={audit.quickActions.openMime} target="_blank" rel="noreferrer"><Download size={15} /> Apri MIME</a> : null}
        </footer>
      </div>
    </TooltipProvider>
  )
}

function PecAuditSidebarPanel({
  audit,
  item,
  onAction,
}: {
  audit?: PecAuditSummary
  item?: EmailPecRow
  onAction: (url: string, label: string) => void
}) {
  if (!audit) return null
  const issues = audit.validationIssues.slice(0, 3)
  const questions = audit.agentQuestions.slice(0, 3)
  const references = audit.normativeReferences.slice(0, 4)
  const deadlineStatus = auditDeadlineStatus(audit)
  const unavailableTitle = 'Disponibile dopo l\'acquisizione del MIME originale'
  const actionButton = (url: string, label: string, icon: ReactNode) => (
    <button
      type="button"
      disabled={!url}
      title={url ? label : unavailableTitle}
      onClick={() => {
        if (url) onAction(url, label)
      }}
    >
      {icon} {label}
    </button>
  )
  return (
    <Panel title="PEC selezionata" subtitle={item?.subject || 'Presidio automatico'} icon={<ShieldCheck size={17} />} count={audit.validationIssues.length}>
      <TooltipProvider delayDuration={120}>
        <div className="iu-pec-sidebar-card">
          <div className="iu-pec-sidebar-head">
            <strong>{audit.eventType ? auditEventLabel(audit.eventType) : audit.qualityLabel}</strong>
            <div className="iu-pec-audit-badges">
              <PecAuditBadges audit={audit} />
            </div>
          </div>
          <PecDepositLifecycle audit={audit} />
          <div className="iu-pec-sidebar-confidence" aria-label="Confidence campi PEC">
            <ConfidenceChip label="Mittente" field={fieldConfidence(audit, 'mittente')} />
            <ConfidenceChip label="Invio" field={fieldConfidence(audit, 'data_invio')} />
            <ConfidenceChip label="Consegna" field={fieldConfidence(audit, 'data_consegna')} />
            <ConfidenceChip label="Ricevuta" field={fieldConfidence(audit, 'tipo_ricevuta')} />
            <ConfidenceChip label="Protocollo" field={fieldConfidence(audit, 'protocollo')} />
            <ConfidenceChip label="Contesto" field={fieldConfidence(audit, 'contesto_legale')} />
          </div>
          <small>Le percentuali indicano la qualità dell'estrazione automatica, non una decisione legale conclusiva.</small>
          <p className="iu-pec-sidebar-outcome">{auditOutcomeText(audit)} <b>Azione suggerita:</b> {auditSuggestedAction(audit)}</p>
          {deadlineStatus ? <p className="iu-pec-deadline-status"><Clock3 size={14} /> {deadlineStatus}</p> : null}
          {issues.length ? (
            <ul className="iu-pec-sidebar-list">
              {issues.map((issue) => (
                <li key={`${issue.code}-${issue.title}`}>
                  <AlertTriangle size={14} />
                  <span><b>{issue.title}</b>{issue.detail ? ` - ${issue.detail}` : ''}</span>
                </li>
              ))}
            </ul>
          ) : <p className="iu-empty">Nessuna anomalia segnalata dalla matrice automatica.</p>}
          {questions.length ? (
            <ol className="iu-pec-sidebar-questions">
              {questions.map((item) => <li key={item}>{item}</li>)}
            </ol>
          ) : null}
          {audit.attachments.length ? (
            <div className="iu-pec-attachment-strip">
              {audit.attachments.slice(0, 4).map((attachment) => (
                <span key={`${attachment.name}-${attachment.classification}`}>
                  {attachment.name} · {attachment.classification || 'da confermare'}
                </span>
              ))}
            </div>
          ) : null}
          {references.length ? (
            <div className="iu-pec-norms">
              {references.map((reference) => <span key={reference.label}>{reference.label}</span>)}
            </div>
          ) : null}
          <div className="iu-pec-sidebar-actions">
            {audit.quickActions.runAudit ? (
              <button type="button" onClick={() => onAction(audit.quickActions.runAudit, 'Esegui controllo')}>
                <ShieldCheck size={15} /> Esegui controllo
              </button>
            ) : null}
            {actionButton(audit.quickActions.saveMatter, 'Salva nel fascicolo', <FileCheck2 size={15} />)}
            {actionButton(audit.quickActions.requestMissingAttachment, 'Richiedi allegato mancante', <Paperclip size={15} />)}
            {actionButton(audit.quickActions.scheduleDeadline, 'Scadenza automatica', <Clock3 size={15} />)}
            {audit.quickActions.openMime ? <a href={audit.quickActions.openMime} target="_blank" rel="noreferrer"><Download size={15} /> Apri MIME</a> : null}
          </div>
        </div>
      </TooltipProvider>
    </Panel>
  )
}

function PecPrimaryActions({
  audit,
  onAction,
}: {
  audit?: PecAuditSummary
  onAction: (url: string, label: string) => void
}) {
  if (!audit) return null
  const unavailableTitle = 'Disponibile dopo l\'acquisizione del MIME originale'
  const button = (url: string, label: string, icon: ReactNode) => (
    <button
      type="button"
      disabled={!url}
      title={url ? label : unavailableTitle}
      onClick={() => {
        if (url) onAction(url, label)
      }}
    >
      {icon} {label}
    </button>
  )
  const linkOrButton = (url: string, label: string, icon: ReactNode) => (
    url
      ? <a href={url} target="_blank" rel="noreferrer">{icon} {label}</a>
      : button('', label, icon)
  )
  return (
    <div className="iu-pec-primary-actions" aria-label="Azioni PEC">
      {linkOrButton(audit.quickActions.openMime, 'Apri MIME', <Download size={15} />)}
      {audit.quickActions.runAudit ? button(audit.quickActions.runAudit, 'Esegui controllo', <ShieldCheck size={15} />) : null}
      {button(audit.quickActions.saveMatter, 'Salva nel fascicolo', <FileCheck2 size={15} />)}
      {button(audit.quickActions.scheduleDeadline, 'Scadenza automatica', <Clock3 size={15} />)}
    </div>
  )
}

type PecSaveMatterRequest = {
  url: string
  subject: string
}

type PecSaveCandidate = {
  id: string
  label: string
  numero: string
  titolo: string
  nomeCliente: string
  stato: string
  reason: string
  href: string
}

function pecSaveCandidateFromPayload(value: unknown): PecSaveCandidate {
  const item = record(value)
  return {
    id: text(item.id),
    label: text(item.label),
    numero: text(item.numero),
    titolo: text(item.titolo),
    nomeCliente: text(item.nome_cliente ?? item.nomeCliente),
    stato: text(item.stato),
    reason: text(item.reason),
    href: text(item.href),
  }
}

async function postPecSaveJson(url: string, payload: JsonRecord): Promise<JsonRecord> {
  const token = csrfToken()
  const response = await fetch(url, {
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
  const data = await response.json().catch(() => ({})) as JsonRecord
  if (!response.ok && !Object.keys(data).length) throw new Error('Salvataggio nel fascicolo non completato.')
  return data
}

function PecSaveMatterDialog({
  request,
  onClose,
  onSaved,
}: {
  request: PecSaveMatterRequest
  onClose: () => void
  onSaved: (message: string) => void
}) {
  const [nome, setNome] = useState('')
  const [cognome, setCognome] = useState('')
  const [candidates, setCandidates] = useState<PecSaveCandidate[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [message, setMessage] = useState('')
  const [working, setWorking] = useState(false)
  const [savedHref, setSavedHref] = useState('')

  const selected = candidates.find((item) => item.id === selectedId)

  const prepare = () => {
    if (!nome.trim() && !cognome.trim()) {
      setMessage('Indica almeno nome o cognome del cliente.')
      return
    }
    setWorking(true)
    setMessage('')
    setSavedHref('')
    postPecSaveJson(request.url, { prepara: true, nome: nome.trim(), cognome: cognome.trim() })
      .then((payload) => {
        const nextCandidates = Array.isArray(payload.candidates)
          ? payload.candidates.map(pecSaveCandidateFromPayload).filter((item) => item.id)
          : []
        setCandidates(nextCandidates)
        setSelectedId(nextCandidates[0]?.id || '')
        setMessage(text(payload.message ?? payload.messaggio ?? payload.errore) || (nextCandidates.length ? 'Conferma il fascicolo aperto.' : 'Nessun fascicolo aperto trovato.'))
      })
      .catch((error) => setMessage(error instanceof Error ? error.message : 'Ricerca fascicolo non completata.'))
      .finally(() => setWorking(false))
  }

  const confirm = () => {
    if (!selectedId) {
      setMessage('Seleziona il fascicolo da confermare.')
      return
    }
    setWorking(true)
    setMessage('')
    postPecSaveJson(request.url, { fascicolo_id: selectedId })
      .then((payload) => {
        if (payload.ok === false) throw new Error(text(payload.message ?? payload.messaggio ?? payload.errore) || 'Salvataggio non completato.')
        const nextMessage = text(payload.message ?? payload.messaggio) || 'MIME PEC salvato nel fascicolo.'
        setSavedHref(text(payload.fascicolo_href ?? payload.document_href))
        setMessage(nextMessage)
        onSaved(nextMessage)
      })
      .catch((error) => setMessage(error instanceof Error ? error.message : 'Salvataggio non completato.'))
      .finally(() => setWorking(false))
  }

  return (
    <div className="iu-pec-save-dialog" role="dialog" aria-modal="true" aria-label="Salva MIME nel fascicolo">
      <div className="iu-pec-save-dialog__panel">
        <header>
          <div>
            <span>Salva MIME nel fascicolo</span>
            <strong>{request.subject || 'PEC selezionata'}</strong>
          </div>
          <button type="button" onClick={onClose}>Chiudi</button>
        </header>
        <div className="iu-pec-save-dialog__fields">
          <label>
            <span>Nome cliente</span>
            <input value={nome} onChange={(event) => setNome(event.target.value)} autoFocus />
          </label>
          <label>
            <span>Cognome cliente</span>
            <input value={cognome} onChange={(event) => setCognome(event.target.value)} />
          </label>
          <button type="button" onClick={prepare} disabled={working}>
            <Search size={15} /> {working ? 'Ricerca...' : 'Cerca fascicolo aperto'}
          </button>
        </div>
        {message ? <p className={savedHref ? 'is-ok' : ''}>{message}</p> : null}
        {candidates.length ? (
          <div className="iu-pec-save-dialog__candidates" aria-label="Fascicoli aperti trovati">
            {candidates.map((candidate) => (
              <label className={selectedId === candidate.id ? 'is-selected' : ''} key={candidate.id}>
                <input type="radio" name="pec-fascicolo" checked={selectedId === candidate.id} onChange={() => setSelectedId(candidate.id)} />
                <span>
                  <strong>{candidate.label || candidate.titolo || candidate.id}</strong>
                  <small>{[candidate.nomeCliente, candidate.stato, candidate.reason].filter(Boolean).join(' - ')}</small>
                </span>
              </label>
            ))}
          </div>
        ) : null}
        {selected ? (
          <div className="iu-pec-save-dialog__confirm">
            <span>Confermi l'inserimento del MIME in <b>{selected.label || selected.titolo}</b>?</span>
            <button type="button" onClick={confirm} disabled={working}>
              <FileCheck2 size={15} /> {working ? 'Salvataggio...' : 'Conferma e salva'}
            </button>
          </div>
        ) : null}
        {savedHref ? <a className="iu-pec-save-dialog__link" href={savedHref}>Apri fascicolo</a> : null}
      </div>
    </div>
  )
}

async function postMailAction(url: string, label: string): Promise<string> {
  if (!url) throw new Error(`${label}: percorso operativo non configurato`)
  const response = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  })
  if (!response.ok) throw new Error(`${label}: operazione non completata`)
  const contentType = response.headers.get('content-type') || ''
  if (!contentType.includes('application/json')) return `${label}: operazione eseguita.`
  const payload = await response.json() as {
    ok?: boolean
    messaggio?: string
    errore?: string
    sync_errore?: string
    warning?: boolean
    nuove?: number
    allegati_salvati?: number
  }
  if (payload.ok === false) throw new Error(payload.errore || `${label}: errore operativo`)
  if (payload.warning && payload.sync_errore) {
    return `${payload.messaggio || `${label}: completata con avvisi.`} ${payload.sync_errore}`
  }
  if (label.startsWith('Sincronizzazione')) {
    const nuove = Number(payload.nuove || 0)
    const allegati = Number(payload.allegati_salvati || 0)
    if (nuove || allegati) return `${label} completata: ${nuove} nuovi messaggi, ${allegati} allegati recuperati.`
  }
  return payload.messaggio || `${label}: operazione eseguita.`
}

function routeEmailId(mode: MailboxMode): string {
  const segment = mode === 'ordinaria' ? 'email-ordinaria' : 'email'
  const match = window.location.pathname.match(new RegExp(`^/(?:app-v2/)?${segment}/messaggio/([^/]+)`, 'i'))
  return match ? decodeURIComponent(match[1]) : ''
}

function mailboxBasePath(mode: MailboxMode): string {
  const prefix = window.location.pathname.startsWith('/app-v2/') ? '/app-v2' : ''
  return `${prefix}/${mode === 'ordinaria' ? 'email-ordinaria' : 'email'}`
}

function currentEmailSelectionId(mode: MailboxMode): string {
  const routed = routeEmailId(mode)
  if (routed) return routed
  return new URLSearchParams(window.location.search).get('id') || ''
}

function writeMailboxSelection(mode: MailboxMode, folder: EmailFolder, id: string): void {
  const params = new URLSearchParams(window.location.search)
  params.set('cartella', folder)
  if (id) params.set('id', id)
  else params.delete('id')
  const query = params.toString()
  window.history.replaceState(null, '', `${mailboxBasePath(mode)}/${query ? `?${query}` : ''}`)
}

function FolderTabs({ data, folder, onChange, ariaLabel }: { data: EmailPecPageData; folder: EmailFolder; onChange: (folder: EmailFolder) => void; ariaLabel: string }) {
  return (
    <div className="iu-mail-folders" role="tablist" aria-label={ariaLabel}>
      {data.facets.folders.map((facet) => (
        <button className={folder === facet.value ? 'is-active' : ''} type="button" onClick={() => onChange(facet.value)} key={facet.value}>
          {folderIcon(facet.value)}
          <span>{facet.label}</span>
          <b>{facet.count}</b>
        </button>
      ))}
    </div>
  )
}

function EmailListRow({
  item,
  selected,
  checked,
  onSelect,
  onToggleChecked,
  includeTelematic,
  fallbackInitials,
}: {
  item: EmailPecRow
  selected: boolean
  checked: boolean
  onSelect: () => void
  onToggleChecked: () => void
  includeTelematic: boolean
  fallbackInitials: string
}) {
  const person = rowPerson(item)
  return (
    <button className={`iu-mail-row ${selected ? 'is-selected' : ''} ${item.unread ? 'is-unread' : ''}`} type="button" onClick={onSelect}>
      <span className="iu-mail-row__check" onClick={(event) => event.stopPropagation()}>
        <input type="checkbox" checked={checked} disabled={item.auditOnly} onChange={onToggleChecked} aria-label={`Seleziona ${item.subject || person}`} />
      </span>
      <span className="iu-mail-avatar">{initials(person, fallbackInitials)}</span>
      <span className="iu-mail-main">
        <span className="iu-mail-row__top">
          <strong>{person}</strong>
          <time>{item.timeLabel}</time>
        </span>
        <span className="iu-mail-subject">{item.subject || '(nessun oggetto)'}</span>
        <span className="iu-mail-preview">{item.preview || 'Nessuna anteprima disponibile.'}</span>
        <span className="iu-mail-tags">
          {item.auditOnly ? <Badge tone="info"><ShieldCheck size={12} /> Audit PEC</Badge> : includeTelematic && item.isPst ? <Badge tone="primary"><ShieldCheck size={12} /> PST</Badge> : null}
          {includeTelematic && item.pctStatus ? <Badge tone={item.pctStatus.includes('RIFIUT') || item.pctStatus.includes('ERRORE') ? 'danger' : 'warning'}>{item.pctStatus}</Badge> : null}
          {includeTelematic ? <PecAuditBadges audit={item.pecAudit} /> : null}
          {item.attachmentCount ? <em><Paperclip size={12} /> {item.attachmentCount}</em> : null}
        </span>
      </span>
    </button>
  )
}

function EmailFullDetail({
  item,
  detail,
  loading,
}: {
  item?: EmailPecRow
  detail: EmailDetailData | null
  loading: boolean
}) {
  if (!item) return null
  if (loading) {
    return <div className="iu-mail-full-detail"><strong>Caricamento messaggio completo...</strong></div>
  }
  if (!detail?.item) return null
  const bodyText = detail.bodyText || detail.item.preview
  return (
    <div className="iu-mail-full-detail" aria-label="Messaggio completo">
      <header>
        <strong>Messaggio completo</strong>
        <span>{detail.attachments.length} allegati</span>
      </header>
      {detail.bodyHtml ? (
        <iframe
          title="Corpo HTML email"
          sandbox=""
          srcDoc={detail.bodyHtml}
        />
      ) : (
        <pre>{bodyText || 'Nessun testo disponibile per questo messaggio.'}</pre>
      )}
      {detail.attachments.length ? (
        <div className="iu-mail-attachments">
          {detail.attachments.map((attachment) => (
            <article key={`${detail.item?.id}-${attachment.index}`}>
              <Paperclip size={16} />
              <div>
                <strong>{attachment.name}</strong>
                <span>{attachment.mime || 'file'} {attachment.sizeLabel ? `- ${attachment.sizeLabel}` : ''}</span>
              </div>
              {attachment.available && attachment.previewHref ? <a href={attachment.previewHref}>Apri</a> : null}
              {attachment.available && attachment.viewHref ? <a href={attachment.viewHref} target="_blank" rel="noreferrer">Visualizza</a> : null}
              {attachment.available && attachment.downloadHref ? <a href={attachment.downloadHref}>Scarica</a> : null}
              {!attachment.available ? <span>{attachment.statusLabel || 'Da recuperare con la sincronizzazione'}</span> : null}
            </article>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function EmailPreview({
  item,
  detail,
  detailLoading,
  onAction,
  copy,
}: {
  item?: EmailPecRow
  detail: EmailDetailData | null
  detailLoading: boolean
  onAction: (url: string, label: string) => void
  copy: MailboxCopy
}) {
  if (!item) {
    return (
      <section className="iu-mail-preview-card iu-mail-preview-empty">
        <Mail size={38} />
        <h2>{copy.previewEmptyTitle}</h2>
        <p>{copy.previewEmptyText}</p>
      </section>
    )
  }
  const person = rowPerson(item)
  const hasTelematicBanner = copy.includeTelematic && (item.pctStatus || item.isPst)
  return (
    <section className="iu-mail-preview-card">
      <header>
        <div>
          <span className="iu-mail-preview-eyebrow">{folderIcon(item.folder)} {folderLabel(item.folder)} · {item.origin || copy.sourceFallback}</span>
          <h2>{item.subject || '(nessun oggetto)'}</h2>
        </div>
        <div className="iu-mail-preview-status">
          {item.unread ? <Badge tone="primary">Non letta</Badge> : <Badge tone="success">Letta</Badge>}
          {copy.includeTelematic && item.isPst ? <Badge tone="primary"><ShieldCheck size={12} /> PST</Badge> : null}
          {copy.includeTelematic ? <PecAuditBadges audit={detail?.pecAudit ?? item.pecAudit} /> : null}
        </div>
      </header>
      {copy.includeTelematic ? <PecPrimaryActions audit={detail?.pecAudit ?? item.pecAudit} onAction={onAction} /> : null}
      <div className="iu-mail-meta">
        <div><span>{item.folder === 'INVIATI' ? 'A' : 'Da'}</span><strong>{person}</strong></div>
        <div><span>{item.folder === 'INVIATI' ? 'Mittente' : 'Destinatari'}</span><strong>{item.folder === 'INVIATI' ? (item.sender || '-') : (item.recipients || '-')}</strong></div>
        <div><span>Data</span><strong>{item.timeLabel || item.timestamp || '-'}</strong></div>
        <div><span>Allegati</span><strong>{item.attachmentCount || 0}</strong></div>
      </div>
      {hasTelematicBanner ? (
        <div className="iu-mail-pct-banner">
          <ShieldCheck size={18} />
          <div>
            <strong>{item.pctStatus ? `Esito telematico rilevato: ${item.pctStatus}` : 'Comunicazione PST rilevata'}</strong>
            <span>Lex può aiutarti a collegare questa PEC a fascicolo, deposito, comunicazione cancelleria o prossima azione.</span>
          </div>
        </div>
      ) : null}
      <p className="iu-mail-body-preview">{item.preview || 'Nessuna anteprima testuale disponibile. Apri la vista completa per leggere HTML e allegati.'}</p>
      {copy.includeTelematic ? <PecAuditInlineNotice audit={detail?.pecAudit ?? item.pecAudit} onAction={onAction} /> : null}
      <footer>
        <Button variant="primary" href={item.detailHref}><Eye size={15} /> Apri</Button>
        {item.folder !== 'CESTINO' ? <Button href={item.replyHref}><Reply size={15} /> Rispondi</Button> : null}
        {item.folder !== 'CESTINO'
          ? <button type="button" onClick={() => onAction(item.trashHref, 'Sposta nel cestino')}><Trash2 size={15} /> Cestino</button>
          : <button type="button" onClick={() => onAction(item.restoreHref, 'Ripristina')}><Undo2 size={15} /> Ripristina</button>}
        {item.unread
          ? <button type="button" onClick={() => onAction(item.markReadHref, 'Segna letta')}><MailCheck size={15} /> Letta</button>
          : <button type="button" onClick={() => onAction(item.markUnreadHref, 'Segna non letta')}><Mail size={15} /> Non letta</button>}
      </footer>
      <EmailFullDetail item={item} detail={detail} loading={detailLoading} />
    </section>
  )
}

function PecInspector({
  data,
  rows,
  selectedItem,
  selectedAudit,
  onAction,
}: {
  data: EmailPecPageData
  rows: EmailPecRow[]
  selectedItem?: EmailPecRow
  selectedAudit?: PecAuditSummary
  onAction: (url: string, label: string) => void
}) {
  const pstWaiting = rows.filter((item) => item.isPst && !item.pctStatus).slice(0, 4)
  const pctAlerts = rows.filter((item) => item.pctStatus && (item.pctStatus.includes('RIFIUT') || item.pctStatus.includes('ERRORE') || item.pctStatus.includes('WARN'))).slice(0, 4)
  const auditAlerts = rows.filter((item) => item.pecAudit && item.pecAudit.qualityTone !== 'success').slice(0, 4)
  return (
    <aside className="iu-mail-inspector">
      <Panel title="Cabina PEC" subtitle="Controlli utili per studio legale" icon={<ShieldCheck size={17} />}>
        <div className="iu-mail-briefing">
          <article>
            <span>PEC/PST riconosciute</span>
            <strong>{data.summary.pst}</strong>
            <small>Messaggi con valore operativo telematico nella casella.</small>
          </article>
          <article>
            <span>Auto-collegate</span>
            <strong>{data.summary.autoLinked}</strong>
            <small>Esiti o comunicazioni già registrati nei fascicoli.</small>
          </article>
        </div>
      </Panel>
      <Panel title="Controlli automatici" icon={<FileCheck2 size={17} />} count={auditAlerts.length}>
        {auditAlerts.length ? (
          <div className="iu-mail-alerts">
            {auditAlerts.map((item) => (
              <a href={item.operationalHref || item.detailHref} key={`audit-${item.id}`}>
                <PecAuditBadges audit={item.pecAudit} />
                <strong>{item.subject}</strong>
                <span>{item.pecAudit?.eventType ? auditEventLabel(item.pecAudit.eventType) : rowPerson(item)}</span>
              </a>
            ))}
          </div>
        ) : <p className="iu-empty">Nessuna anomalia nella vista corrente.</p>}
      </Panel>
      <PecAuditSidebarPanel audit={selectedAudit} item={selectedItem} onAction={onAction} />
      <Panel title="Esiti da presidiare" icon={<AlertTriangle size={17} />} count={pctAlerts.length}>
        {pctAlerts.length ? (
          <div className="iu-mail-alerts">
            {pctAlerts.map((item) => (
              <a href={item.operationalHref || item.detailHref} key={item.id}>
                <Badge tone="danger">{item.pctStatus}</Badge>
                <strong>{item.subject}</strong>
                <span>{rowPerson(item)}</span>
              </a>
            ))}
          </div>
        ) : <p className="iu-empty">Nessun esito critico nella cartella visibile.</p>}
      </Panel>
      <Panel title="PST in attesa" icon={<FileCheck2 size={17} />} count={pstWaiting.length}>
        {pstWaiting.length ? (
          <div className="iu-mail-alerts">
            {pstWaiting.map((item) => (
              <a href={item.operationalHref || item.detailHref} key={item.id}>
                <Badge tone="warning">da collegare</Badge>
                <strong>{item.subject}</strong>
                <span>{item.timeLabel}</span>
              </a>
            ))}
          </div>
        ) : <p className="iu-empty">Nessuna PEC PST in attesa nella vista corrente.</p>}
      </Panel>
      <Panel title="Azioni rapide" icon={<Sparkles size={17} />}>
        <div className="iu-mail-quick-actions">
          <a href={data.actions.compose}><Send size={15} /> Nuova PEC</a>
          <a href={data.actions.legalNotice}><FileSignature size={15} /> Notifica ex L. 53</a>
          <a href={data.actions.settings}><Settings2 size={15} /> Parametri PEC</a>
          <a href={data.actions.localPecTest}><Wrench size={15} /> Test SMTP dal PC</a>
        </div>
      </Panel>
    </aside>
  )
}

function OrdinaryInspector({ data, rows }: { data: EmailPecPageData; rows: EmailPecRow[] }) {
  const unread = rows.filter((item) => item.unread).slice(0, 4)
  const withAttachments = rows.filter((item) => item.attachmentCount > 0).slice(0, 4)
  return (
    <aside className="iu-mail-inspector">
      <Panel title="Cabina email" subtitle="Posta ordinaria separata dalla PEC" icon={<Mail size={17} />}>
        <div className="iu-mail-briefing">
          <article>
            <span>Da leggere</span>
            <strong>{data.summary.unread}</strong>
            <small>Messaggi ordinari non ancora lavorati.</small>
          </article>
          <article>
            <span>Allegati</span>
            <strong>{data.summary.attachments}</strong>
            <small>File recuperati dalla casella ordinaria.</small>
          </article>
        </div>
      </Panel>
      <Panel title="Email da leggere" icon={<MailCheck size={17} />} count={unread.length}>
        {unread.length ? (
          <div className="iu-mail-alerts">
            {unread.map((item) => (
              <a href={item.detailHref} key={item.id}>
                <Badge tone="primary">non letta</Badge>
                <strong>{item.subject}</strong>
                <span>{rowPerson(item)}</span>
              </a>
            ))}
          </div>
        ) : <p className="iu-empty">Nessuna email ordinaria non letta nella vista corrente.</p>}
      </Panel>
      <Panel title="Allegati recenti" icon={<Paperclip size={17} />} count={withAttachments.length}>
        {withAttachments.length ? (
          <div className="iu-mail-alerts">
            {withAttachments.map((item) => (
              <a href={item.detailHref} key={item.id}>
                <Badge tone="orange">{item.attachmentCount} allegati</Badge>
                <strong>{item.subject}</strong>
                <span>{item.timeLabel}</span>
              </a>
            ))}
          </div>
        ) : <p className="iu-empty">Nessun allegato nella vista corrente.</p>}
      </Panel>
      <Panel title="Azioni rapide" icon={<Sparkles size={17} />}>
        <div className="iu-mail-quick-actions">
          <a href={data.actions.compose}><Send size={15} /> Nuova email</a>
          <a href={data.actions.settings}><Settings2 size={15} /> Parametri SMTP/IMAP</a>
          <a href={data.actions.sync}><RefreshCw size={15} /> Aggiorna casella</a>
        </div>
      </Panel>
    </aside>
  )
}

function PecAutomaticNotice({
  rows,
  summary,
  onSelect,
}: {
  rows: EmailPecRow[]
  summary: EmailPecPageData['summary']
  onSelect: (id: string) => void
}) {
  const warnings = rows.filter((item) => {
    const auditWarning = item.pecAudit && item.pecAudit.qualityTone !== 'success'
    const pctWarning = item.pctStatus && (item.pctStatus.includes('RIFIUT') || item.pctStatus.includes('ERRORE') || item.pctStatus.includes('WARN'))
    return auditWarning || pctWarning
  })
  const first = warnings[0]
  const count = Math.max(Number(summary.warnings || 0), warnings.length)
  if (!count || !first) return null
  return (
    <section className="iu-mail-auto-notice" aria-label="Avviso automatico PEC" data-iusentra-sequence-slot="main-content">
      <AlertTriangle size={17} />
      <div>
        <strong>Avviso automatico PEC</strong>
        <span>{count} comunicazioni richiedono presidio: controlla qualità di acquisizione, firme, allegati o esiti telematici prima di archiviare.</span>
      </div>
      <button type="button" onClick={() => onSelect(first.id)}>Apri presidio</button>
    </section>
  )
}

function MailboxStats({ data, mode }: { data: EmailPecPageData; mode: MailboxMode }) {
  if (mode === 'ordinaria') {
    return (
      <section className="iu-mail-stats" aria-label={mailboxCopy.ordinaria.statsAria} data-iusentra-sequence-slot="primary-actions">
        <StatCard icon={<Mail size={19} />} label="Totali" value={data.summary.total} note="email ordinarie archiviate" tone="primary" />
        <StatCard icon={<Inbox size={19} />} label="In arrivo" value={data.summary.inbox} note="ricevute via IMAP" tone="info" />
        <StatCard icon={<MailCheck size={19} />} label="Non lette" value={data.summary.unread} note="da lavorare" tone={data.summary.unread ? 'warning' : 'success'} />
        <StatCard icon={<Send size={19} />} label="Inviate" value={data.summary.sent} note="email inviate dallo studio" tone="success" />
        <StatCard icon={<Trash2 size={19} />} label="Cestino" value={data.summary.trash} note="spostate localmente" tone="neutral" />
        <StatCard icon={<Paperclip size={19} />} label="Allegati" value={data.summary.attachments} note="file recuperati" tone="orange" />
      </section>
    )
  }
  return (
    <section className="iu-mail-stats" aria-label={mailboxCopy.pec.statsAria} data-iusentra-sequence-slot="primary-actions">
      <StatCard icon={<Mail size={19} />} label="Totali" value={data.summary.total} note="messaggi archiviati" tone="primary" />
      <StatCard icon={<Inbox size={19} />} label="In arrivo" value={data.summary.inbox} note="ricevute in casella" tone="info" />
      <StatCard icon={<MailCheck size={19} />} label="Non lette" value={data.summary.unread} note="da lavorare" tone={data.summary.unread ? 'warning' : 'success'} />
      <StatCard icon={<Send size={19} />} label="Inviate" value={data.summary.sent} note="PEC inviate dallo studio" tone="success" />
      <StatCard icon={<Trash2 size={19} />} label="Cestino" value={data.summary.trash} note="spostate localmente" tone="neutral" />
      <StatCard icon={<ShieldCheck size={19} />} label="PST/PCT" value={data.summary.pst} note="messaggi telematici" tone="purple" />
      <StatCard icon={<Paperclip size={19} />} label="Allegati" value={data.summary.attachments} note="file recuperati" tone="orange" />
      <StatCard icon={<CheckCircle2 size={19} />} label="Collegate" value={data.summary.autoLinked} note="auto-esiti registrati" tone="success" />
    </section>
  )
}

function EmailMailboxPage({ mode }: { mode: MailboxMode }) {
  const copy = mailboxCopy[mode]
  const [data, setData] = useState<EmailPecPageData>(copy.emptyData)
  const [loading, setLoading] = useState(true)
  const [folder, setFolder] = useState<EmailFolder>('INBOX')
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<EmailStatus>('tutti')
  const [sort, setSort] = useState<SortKey>('recenti')
  const [onlyPst, setOnlyPst] = useState(false)
  const [onlyAttachments, setOnlyAttachments] = useState(false)
  const [pctStatus, setPctStatus] = useState('')
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [selectedId, setSelectedId] = useState(currentEmailSelectionId(mode))
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [detail, setDetail] = useState<EmailDetailData | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailReloadKey, setDetailReloadKey] = useState(0)
  const [statusLine, setStatusLine] = useState('')
  const [bulkWorking, setBulkWorking] = useState(false)
  const [saveMatterRequest, setSaveMatterRequest] = useState<PecSaveMatterRequest | null>(null)

  const fetchPage = mode === 'ordinaria' ? getEmailOrdinariaPage : getEmailPecPage
  const fetchParams = {
    folder,
    q: query,
    stato: status,
    pst: copy.includeTelematic ? onlyPst : false,
    conAllegati: onlyAttachments,
    statoPct: copy.includeTelematic ? pctStatus : '',
  }

  const load = () => {
    setLoading(true)
    fetchPage(fetchParams)
      .then(setData)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    fetchPage(fetchParams)
      .then((payload) => { if (active) setData(payload) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [folder, status, onlyPst, onlyAttachments, pctStatus])

  const visible = useMemo(() => sortRows(data.items.filter((item) => isInsideQuery(item, query)), sort), [data.items, query, sort])
  const selected = detail?.item && detail.item.id === selectedId ? detail.item : visible.find((item) => item.id === selectedId) || visible[0]
  const visibleIds = useMemo(() => visible.filter((item) => !item.auditOnly).map((item) => item.id), [visible])
  const selectedVisibleCount = useMemo(() => visibleIds.filter((id) => selectedIds.has(id)).length, [selectedIds, visibleIds])
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.has(id))
  const bulkActionKind = folder === 'CESTINO' ? 'delete' : 'trash'
  const bulkActionLabel = folder === 'CESTINO' ? 'Elimina selezione' : 'Sposta nel cestino'
  const selectedAudit = detail?.pecAudit ?? selected?.pecAudit

  const selectMessage = (id: string) => {
    setSelectedId(id)
    writeMailboxSelection(mode, folder, id)
  }

  const changeFolder = (nextFolder: EmailFolder) => {
    setFolder(nextFolder)
    setSelectedId('')
    writeMailboxSelection(mode, nextFolder, '')
  }

  useEffect(() => {
    setSelectedIds((current) => {
      const validIds = new Set(data.items.map((item) => item.id))
      const next = new Set<string>()
      current.forEach((id) => {
        if (validIds.has(id)) next.add(id)
      })
      if (next.size === current.size) return current
      return next
    })
  }, [data.items])

  useEffect(() => {
    const routeId = currentEmailSelectionId(mode)
    if (routeId) {
      if (selectedId !== routeId) setSelectedId(routeId)
      return
    }
    if (!visible.length) {
      setSelectedId('')
      return
    }
    if (!visible.some((item) => item.id === selectedId)) setSelectedId(visible[0].id)
  }, [mode, selectedId, visible])

  useEffect(() => {
    const id = selectedId || currentEmailSelectionId(mode)
    if (!id) {
      setDetail(null)
      return
    }
    let active = true
    setDetailLoading(true)
    const loader = mode === 'ordinaria' ? getEmailOrdinariaDetail : getEmailPecDetail
    loader(id)
      .then((payload) => {
        if (active) setDetail(payload.item ? payload : null)
      })
      .finally(() => {
        if (active) setDetailLoading(false)
      })
    return () => { active = false }
  }, [mode, selectedId, detailReloadKey])

  const runAction = (url: string, label: string) => {
    if (copy.includeTelematic && url.includes('/salva-fascicolo')) {
      setSaveMatterRequest({ url, subject: selected?.subject || detail?.item?.subject || 'PEC selezionata' })
      setStatusLine('Indica nome e cognome del cliente per trovare il fascicolo aperto.')
      return
    }
    setStatusLine(`${label} in corso...`)
    postMailAction(url, label)
      .then((message) => {
        setStatusLine(message)
        load()
        setDetailReloadKey((value) => value + 1)
      })
      .catch((error) => setStatusLine(error instanceof Error ? error.message : `${label}: errore operativo`))
  }

  const toggleSelection = (id: string) => {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAllVisible = () => {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (allVisibleSelected) {
        visibleIds.forEach((id) => next.delete(id))
      } else {
        visibleIds.forEach((id) => next.add(id))
      }
      return next
    })
  }

  const runBulkAction = () => {
    const ids = visibleIds.filter((id) => selectedIds.has(id))
    if (!ids.length) {
      setStatusLine('Seleziona almeno un messaggio.')
      return
    }
    setBulkWorking(true)
    setStatusLine(`${bulkActionLabel} in corso...`)
    submitEmailBulkAction(data.actions.bulkAction, ids, bulkActionKind)
      .then((message) => {
        setStatusLine(message)
        setSelectedIds((current) => {
          const next = new Set(current)
          ids.forEach((id) => next.delete(id))
          return next
        })
        load()
      })
      .catch((error) => setStatusLine(error instanceof Error ? error.message : `${bulkActionLabel}: errore operativo`))
      .finally(() => setBulkWorking(false))
  }

  const runSync = () => runAction(data.actions.sync, copy.syncLabel)
  const runAutoEsiti = () => {
    if (data.actions.autoEsiti) runAction(data.actions.autoEsiti, 'Auto-esiti')
  }
  const sortOptions = (copy.includeTelematic ? Object.keys(sortLabels) : ['recenti', 'mittente', 'oggetto']) as SortKey[]

  return (
    <main className="iu-content iu-email-page iusentra-route-sequence">
      <section className="iu-mail-hero" data-iusentra-sequence-slot="page-header">
        <div>
          <span className="iu-mail-eyebrow">{copy.includeTelematic ? <ShieldCheck size={16} /> : <Mail size={16} />} {copy.eyebrow}</span>
          <h1>{copy.heroTitle}</h1>
          <p>{copy.heroText}</p>
        </div>
        <div className="iu-mail-hero__actions">
          <Button href={data.actions.operationalInbox}><Archive size={15} /> {copy.openLabel}</Button>
          <Button href={data.actions.settings}><Settings2 size={15} /> Impostazioni</Button>
          {data.actions.autoEsiti ? <button type="button" onClick={runAutoEsiti}><Sparkles size={15} /> Auto-esiti</button> : null}
          <button type="button" onClick={runSync}><RefreshCw size={15} /> Aggiorna</button>
          <Button
            variant="primary"
            href={data.actions.compose}
            disabled={!data.actions.compose}
            title={data.actions.compose ? copy.composeLabel : 'Configura la casella per comporre nuovi messaggi'}
          >
            <Send size={16} /> {copy.composeLabel}
          </Button>
        </div>
      </section>

      <MailboxStats data={data} mode={mode} />

      <section className="iu-mail-toolbar" aria-label={copy.filtersAria} data-iusentra-sequence-slot="filters">
        <FolderTabs data={data} folder={folder} onChange={changeFolder} ariaLabel={copy.folderAria} />
        <label className="iu-mail-search"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') load() }} placeholder="Cerca mittente, destinatario, oggetto, riferimento..." /></label>
        <button className="iu-mail-filter-btn" type="button" onClick={() => setAdvancedOpen((value) => !value)} aria-expanded={advancedOpen}><SlidersHorizontal size={16} /> Filtri</button>
        <button className="iu-mail-icon-btn" type="button" onClick={load} aria-label="Aggiorna vista"><RefreshCw size={17} /></button>
      </section>

      {advancedOpen ? (
        <section className="iu-mail-advanced" aria-label={`Filtri avanzati ${copy.title}`} data-iusentra-sequence-slot="context-filters">
          <label><span>Stato lettura</span><select value={status} onChange={(event) => setStatus(event.target.value as EmailStatus)}>{data.facets.statuses.map((facet) => <option value={facet.value} key={facet.value}>{facet.label} ({facet.count})</option>)}</select></label>
          {copy.includeTelematic ? <label><span>Esito PCT</span><select value={pctStatus} onChange={(event) => setPctStatus(event.target.value)}>{data.facets.pctStatuses.map((facet) => <option value={facet.value} key={facet.value || 'all'}>{facet.label} ({facet.count})</option>)}</select></label> : null}
          <label><span>Ordinamento</span><select value={sort} onChange={(event) => setSort(event.target.value as SortKey)}>{sortOptions.map((item) => <option value={item} key={item}>{sortLabels[item]}</option>)}</select></label>
          {copy.includeTelematic ? <label className="iu-mail-check"><input type="checkbox" checked={onlyPst} onChange={(event) => setOnlyPst(event.target.checked)} /><span>Solo PEC/PST</span></label> : null}
          <label className="iu-mail-check"><input type="checkbox" checked={onlyAttachments} onChange={(event) => setOnlyAttachments(event.target.checked)} /><span>Solo con allegati</span></label>
          <button type="button" onClick={() => { setStatus('tutti'); setOnlyPst(false); setOnlyAttachments(false); setPctStatus(''); setQuery('') }}>Reset</button>
        </section>
      ) : null}

      <section className="iu-mail-status-line" data-iusentra-sequence-slot="main-content">
        <span className={loading ? '' : 'is-ok'}>{loading ? copy.syncingLabel : copy.updatedLabel}</span>
        <small><Clock3 size={14} /> Le azioni sono tracciate e separate tra PEC ed email ordinaria.</small>
        {selectedVisibleCount ? <small>{selectedVisibleCount} messaggi selezionati nella vista corrente.</small> : null}
        {statusLine ? <small className="iu-mail-operation-status">{statusLine}</small> : null}
      </section>

      {copy.includeTelematic ? <PecAutomaticNotice rows={visible} summary={data.summary} onSelect={selectMessage} /> : null}

      <section className="iu-mail-layout" data-iusentra-sequence-slot="main-content">
        <div className="iu-mail-list-card">
          <header>
            <div><strong>{visible.length} messaggi</strong><span>{folderLabel(folder)} · {sourceLabel(data.source, copy.sourceFallback)}</span></div>
            <a href={`${data.actions.operationalInbox}?cartella=${folder}`}><Download size={15} /> Apri cartella</a>
          </header>
          {visible.length ? (
            <div className="iu-mail-list-select-all">
              <label>
                <input type="checkbox" checked={allVisibleSelected} onChange={toggleAllVisible} />
                <span>Seleziona tutti i messaggi visibili</span>
              </label>
            </div>
          ) : null}
          {selectedVisibleCount ? (
            <div className="iu-mail-bulkbar">
              <strong>{selectedVisibleCount} selezionati</strong>
              <span>{folder === 'CESTINO' ? "Nel cestino puoi eliminare definitivamente piu' messaggi insieme." : "Puoi spostare nel cestino piu' messaggi della vista corrente."}</span>
              <button type="button" onClick={runBulkAction} disabled={bulkWorking}>
                <Trash2 size={15} /> {bulkWorking ? `${bulkActionLabel}...` : bulkActionLabel}
              </button>
            </div>
          ) : null}
          <div className="iu-mail-list">
            {visible.map((item) => (
              <EmailListRow
                item={item}
                selected={selected?.id === item.id}
                checked={selectedIds.has(item.id)}
                onSelect={() => selectMessage(item.id)}
                onToggleChecked={() => toggleSelection(item.id)}
                includeTelematic={copy.includeTelematic}
                fallbackInitials={mode === 'pec' ? 'PEC' : 'EM'}
                key={item.id}
              />
            ))}
            {!visible.length ? (
              <div className="iu-mail-empty">
                <Mail size={34} />
                <strong>{copy.emptyTitle}</strong>
                <span>{copy.emptyText}</span>
              </div>
            ) : null}
          </div>
        </div>
        <EmailPreview item={selected} detail={detail} detailLoading={detailLoading} onAction={runAction} copy={copy} />
        {mode === 'pec'
          ? <PecInspector data={data} rows={visible} selectedItem={selected} selectedAudit={selectedAudit} onAction={runAction} />
          : <OrdinaryInspector data={data} rows={visible} />}
      </section>

      <section className="iu-mail-lower-grid" data-iusentra-sequence-slot="support-sidebar">
        <Panel title={mode === 'pec' ? 'Qualità PEC' : 'Qualità email'} subtitle={mode === 'pec' ? 'Controlli prima di deposito, cancelleria e fascicolo' : 'Controlli su casella ordinaria, allegati e risposte'} icon={<ShieldCheck size={17} />}>
          <div className="iu-mail-checklist">
            <span><CheckCircle2 size={16} /> In arrivo, inviate e cestino restano visibili come cartelle distinte.</span>
            <span><FileCheck2 size={16} /> {mode === 'pec' ? 'PEC/PST ed esiti PCT sono evidenziati senza aprire ogni messaggio.' : 'La posta ordinaria resta separata dalla PEC e dalla telematica.'}</span>
            <span><Paperclip size={16} /> Allegati e anteprima restano accessibili dalla vista rapida.</span>
          </div>
        </Panel>
        <Panel title="Integrazioni operative" subtitle="Fascicoli e comunicazioni" icon={<Sparkles size={17} />}>
          <div className="iu-mail-integrations">
            <a href="/fascicoli">Fascicoli</a>
            <a href={mode === 'pec' ? '/telematico' : '/messaggi'}>{mode === 'pec' ? 'Servizi telematici' : 'Messaggi'}</a>
            <a href={mode === 'pec' ? '/deposito/checklist' : '/clienti'}>{mode === 'pec' ? 'Checklist deposito' : 'Clienti'}</a>
          </div>
        </Panel>
      </section>

      <FloatingLex
        context={copy.lexContext}
        title={copy.lexTitle}
        body={copy.lexBody}
        primaryHref={data.actions.lex}
        primaryLabel={copy.lexPrimaryLabel}
        secondaryHref="/fascicoli"
        secondaryLabel="Vai ai fascicoli"
      />
      {saveMatterRequest ? (
        <PecSaveMatterDialog
          request={saveMatterRequest}
          onClose={() => setSaveMatterRequest(null)}
          onSaved={(message) => {
            setStatusLine(message)
            load()
            setDetailReloadKey((value) => value + 1)
          }}
        />
      ) : null}
    </main>
  )
}

export function EmailPecPage() {
  return <EmailMailboxPage mode="pec" />
}

export function EmailOrdinariaPage() {
  return <EmailMailboxPage mode="ordinaria" />
}

export function EmailComposePage({ mode }: { mode: MailboxMode }) {
  const copy = mailboxCopy[mode]
  const params = new URLSearchParams(window.location.search)
  const isOrdinary = mode === 'ordinaria'
  const action = isOrdinary ? '/email-ordinaria/scrivi' : '/email/scrivi'
  const backHref = isOrdinary ? '/email-ordinaria/?cartella=INBOX' : '/email/?cartella=INBOX'
  const settingsHref = isOrdinary ? '/impostazioni?tab=smtp' : '/impostazioni?tab=pec'
  const [recipient, setRecipient] = useState(params.get('a') || '')
  const [subject, setSubject] = useState(params.get('oggetto') || '')
  const [body, setBody] = useState('')
  const [clientQuery, setClientQuery] = useState('')
  const [clientMatches, setClientMatches] = useState<ComposeClient[]>([])
  const [clientLoading, setClientLoading] = useState(false)
  const [selectedClientIds, setSelectedClientIds] = useState<string[]>([])
  const [attachmentNames, setAttachmentNames] = useState<string[]>([])

  useEffect(() => {
    const query = clientQuery.trim()
    if (query.length < 2) {
      setClientMatches([])
      return
    }
    let active = true
    const timer = window.setTimeout(() => {
      setClientLoading(true)
      const search = new URLSearchParams({ q: query, autocomplete: '1', limit: '8' })
      fetch(`/api/clienti?${search.toString()}`, {
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      })
        .then((response) => response.ok ? response.json() : [])
        .then((payload) => {
          if (active) setClientMatches(composeClientsFromPayload(payload))
        })
        .catch(() => {
          if (active) setClientMatches([])
        })
        .finally(() => {
          if (active) setClientLoading(false)
        })
    }, 180)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [clientQuery])

  const selectClient = (client: ComposeClient) => {
    const address = isOrdinary ? client.email || client.pec : client.pec || client.email
    setRecipient((current) => appendAddress(current, address))
    setSelectedClientIds((current) => current.includes(client.id) ? current : [...current, client.id])
    setClientQuery('')
    setClientMatches([])
  }

  const submitPecViaLocalSigner = async (form: HTMLFormElement): Promise<FormSubmitResult> => {
    const formData = new FormData(form)
    const destinatario = String(formData.get('a') || '').trim()
    const oggetto = String(formData.get('oggetto') || '').trim()
    const corpo = String(formData.get('corpo') || '').trim()
    if (!destinatario || !oggetto) {
      throw new Error('Compila destinatario e oggetto.')
    }
    if (params.get('tipo') === 'notifica_l53' || oggetto.toLowerCase().includes(LEGAL_NOTIFICATION_SUBJECT)) {
      throw new Error('Per notifiche ex L. 53/1994 usa il percorso guidato Notifica ex L. 53/1994: servono relata separata, firma digitale, PEC da pubblico elenco e ricevuta completa.')
    }
    const savedPayload = await savedPecSmtpPayload()
    const files = formData.getAll('allegati').filter((item): item is File => item instanceof File && Boolean(item.name))
    const attachments = await Promise.all(files.map(fileAttachment))
    const localPayload: JsonRecord = {
      ...savedPayload,
      to: destinatario,
      subject: oggetto,
      body: corpo,
      attachments,
    }
    const localResult = await fetchJsonWithTimeout(`${LOCAL_SIGNER_BASE_URL}/pec/send`, 120000, {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(localPayload),
    })
    const messageId = textValue(localResult.message_id)
    if (!messageId) {
      throw new Error('Il Local Signer ha completato la chiamata senza Message-ID: sincronizza la casella PEC e verifica l\'invio.')
    }
    const confirm = new FormData()
    confirm.set('a', destinatario)
    confirm.set('oggetto', oggetto)
    confirm.set('corpo', corpo)
    confirm.set('id_cliente', String(formData.get('id_cliente') || ''))
    confirm.set('message_id', messageId)
    return submitFormJson('/email/scrivi/conferma-locale', confirm)
  }

  return (
    <main className="iu-content iu-mail-compose-page iusentra-route-sequence">
      <section className="iu-mail-compose-hero">
        <div>
          <span className="iu-mail-eyebrow">{isOrdinary ? <Mail size={16} /> : <ShieldCheck size={16} />} {copy.eyebrow}</span>
          <h1>{isOrdinary ? 'Componi email ordinaria' : 'Componi PEC'}</h1>
          <p>
            {isOrdinary
              ? 'Invia un messaggio tramite la configurazione SMTP ordinaria dello studio, mantenendolo separato dalla PEC.'
              : 'Prepara un messaggio PEC usando il canale certificato configurato nello studio.'}
          </p>
        </div>
        <div className="iu-mail-compose-hero__actions">
          <Button href={backHref}><Archive size={15} /> Torna alla casella</Button>
          <Button href={settingsHref}><Settings2 size={15} /> Impostazioni</Button>
        </div>
      </section>

      <section className="iu-mail-compose-grid">
        <JsonPostForm
          className="iu-mail-compose-form"
          action={action}
          encType="multipart/form-data"
          customSubmit={isOrdinary ? undefined : submitPecViaLocalSigner}
          pendingMessage={isOrdinary ? 'Invio email in corso...' : 'Invio PEC dal PC locale in corso...'}
          successMessage={isOrdinary ? 'Email ordinaria inviata con successo.' : 'PEC inviata dal PC locale e registrata nello studio.'}
        >
          <label>
            <span>Destinatario</span>
            <input
              type="text"
              name="a"
              value={recipient}
              onChange={(event) => setRecipient(event.target.value)}
              placeholder={isOrdinary ? 'email cliente o destinatari separati da virgola' : 'PEC cliente o destinatari separati da virgola'}
              autoComplete="email"
              required
            />
          </label>
          <label>
            <span>Cliente</span>
            <input
              type="text"
              value={clientQuery}
              onChange={(event) => setClientQuery(event.target.value)}
              placeholder="Cerca cliente per compilare il destinatario"
            />
          </label>
          {clientQuery.trim().length >= 2 || clientMatches.length ? (
            <div className="iu-mail-compose-clients" aria-live="polite">
              {clientLoading ? <span>Ricerca clienti in corso...</span> : null}
              {!clientLoading && !clientMatches.length ? <span>Nessun cliente trovato con recapito disponibile.</span> : null}
              {clientMatches.map((client) => {
                const address = isOrdinary ? client.email || client.pec : client.pec || client.email
                return (
                  <button type="button" onClick={() => selectClient(client)} disabled={!address} key={client.id}>
                    <strong>{client.name}</strong>
                    <span>{address || 'Recapito email assente'}{client.fiscalId ? ` · ${client.fiscalId}` : ''}</span>
                  </button>
                )
              })}
            </div>
          ) : null}
          <input type="hidden" name="id_cliente" value={selectedClientIds[0] || ''} />
          <label>
            <span>Oggetto</span>
            <input
              type="text"
              name="oggetto"
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
              placeholder="Oggetto del messaggio"
              required
            />
          </label>
          <label>
            <span>Messaggio</span>
            <textarea
              name="corpo"
              value={body}
              onChange={(event) => setBody(event.target.value)}
              rows={14}
              placeholder="Scrivi il messaggio..."
            />
          </label>
          <label className="iu-mail-compose-file">
            <span>Allegati</span>
            <input
              type="file"
              name="allegati"
              multiple
              onChange={(event) => setAttachmentNames(Array.from(event.currentTarget.files || []).map((file) => file.name))}
            />
          </label>
          <footer>
            <button type="submit"><Send size={16} /> Invia</button>
            <a href={backHref}>Annulla</a>
          </footer>
        </JsonPostForm>

        <aside className="iu-mail-compose-side">
          <Panel title={isOrdinary ? 'Canale ordinario' : 'Canale PEC'} subtitle="Controllo operativo" icon={isOrdinary ? <Mail size={17} /> : <ShieldCheck size={17} />}>
            <div className="iu-mail-compose-checks">
              <span><CheckCircle2 size={16} /> Invio collegato alla casella selezionata.</span>
              <span><Paperclip size={16} /> Puoi aggiungere uno o piu allegati prima dell'invio.</span>
              <span><CheckCircle2 size={16} /> Rientro automatico in <strong>{isOrdinary ? 'Email ordinaria' : 'Email PEC'}</strong>.</span>
              <span><Settings2 size={16} /> Configurazione da <a href={settingsHref}>{isOrdinary ? 'SMTP/IMAP ordinario' : 'PEC'}</a>.</span>
            </div>
          </Panel>
          <Panel title="Anteprima rapida" subtitle="Controllo prima dell'invio" icon={<Eye size={17} />}>
            <div className="iu-mail-compose-preview">
              <span>A</span>
              <strong>{recipient || 'Destinatario non indicato'}</strong>
              <span>Oggetto</span>
              <strong>{subject || 'Oggetto non indicato'}</strong>
              <span>Allegati</span>
              <strong>{attachmentNames.length ? attachmentNames.join(', ') : 'Nessun allegato selezionato'}</strong>
              <p>{body || 'Il testo comparirà qui mentre componi il messaggio.'}</p>
            </div>
          </Panel>
        </aside>
      </section>

      <FloatingLex
        context={copy.lexContext}
        title={copy.lexTitle}
        body={copy.lexBody}
        primaryHref="#lex"
        primaryLabel={copy.lexPrimaryLabel}
        secondaryHref={backHref}
        secondaryLabel={copy.title}
      />
    </main>
  )
}
