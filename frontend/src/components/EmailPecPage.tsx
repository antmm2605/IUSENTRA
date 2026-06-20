import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  Archive,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Download,
  Eye,
  FileCheck2,
  FileSignature,
  Inbox,
  Landmark,
  Mail,
  MailCheck,
  MapPin,
  Paperclip,
  PlusCircle,
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
import { csrfToken, submitFormJson } from '../formSubmit'
import { normaliseStudioRuntimeResult, type StudioRuntimeOffice, type StudioRuntimeResult } from '../studioModuleRuntime'
import './EmailPecPage.css'

type MailboxMode = 'pec' | 'ordinaria'
type SortKey = 'recenti' | 'mittente' | 'oggetto' | 'pct'
type JsonRecord = Record<string, unknown>

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

type OfficeKindOption = {
  value: string
  label: string
}

type ComuneOption = {
  codiceIstat: string
  nome: string
  label: string
  cap: string[]
  siglaProvincia: string
  provincia: string
}

const composeOfficeKindOptions: OfficeKindOption[] = [
  { value: '', label: 'Tutti gli uffici richiesti' },
  { value: 'giudice_pace', label: 'Giudice di Pace di' },
  { value: 'tribunale', label: 'Tribunale di' },
  { value: 'procura', label: 'Procura della Repubblica presso il Tribunale di' },
  { value: 'unep', label: 'Unep presso il Tribunale di' },
  { value: 'corte_appello', label: "Corte d'Appello di" },
  { value: 'procura_generale', label: "Procura Generale della Repubblica presso la Corte d'Appello di" },
  { value: 'assise_appello', label: 'Corte di Assise di Appello di' },
  { value: 'assise', label: 'Corte di Assise di' },
  { value: 'procura_minorenni', label: 'Procura della Repubblica presso il Tribunale per i minorenni di' },
  { value: 'tribunale_minorenni', label: 'Tribunale per i Minorenni di' },
]

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

function isPecOperationalWarning(item: EmailPecRow): boolean {
  if (item.pecPresidiata) return false
  const auditWarning = Boolean(item.pecAudit && item.pecAudit.qualityTone !== 'success')
  const status = item.pctStatus || ''
  const pctWarning = Boolean(status && (status.includes('RIFIUT') || status.includes('ERRORE') || status.includes('WARN')))
  return auditWarning || pctWarning
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

type MailActionPayload = {
  ok?: boolean
  messaggio?: string
  message?: string
  errore?: string
  sync_errore?: string
  warning?: boolean
  nuove?: number
  allegati_salvati?: number
  run_id?: string
  has_more?: boolean
  cursor_index?: number
  total_emails?: number
  batch_size?: number
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

function profileValue(audit: PecAuditSummary | undefined, key: string): string {
  return text(record(audit?.proceduralProfile)[key])
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => text(item)).filter(Boolean) : []
}

function recordArray(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.map((item) => record(item)).filter((item) => Object.keys(item).length > 0) : []
}

function uniqueText(values: string[]): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  values.forEach((value) => {
    const clean = text(value)
    const key = clean.toLocaleLowerCase('it-IT')
    if (clean && !seen.has(key)) {
      seen.add(key)
      out.push(clean)
    }
  })
  return out
}

function PecProceduralProfile({ audit, compact = false }: { audit?: PecAuditSummary; compact?: boolean }) {
  if (!audit) return null
  const profile = record(audit.proceduralProfile)
  const remote = record(profile.remote_hearing ?? profile.remoteHearing)
  const cliente = profileValue(audit, 'cliente')
  const ruoloParte = profileValue(audit, 'ruolo_parte')
  const parteProcessuale = profileValue(audit, 'parte_processuale') || profileValue(audit, 'soggetto_processuale')
  const partiProcessuali = uniqueText(stringArray(profile.parti_processuali ?? profile.partiProcessuali))
  const soggettiParti = recordArray(profile.soggetti_parti ?? profile.soggettiParti)
    .map((item) => {
      const ruolo = text(item.ruolo)
      const nome = text(item.valore ?? item.nome ?? item.value ?? item.label)
      if (!nome) return ''
      return ruolo ? `${ruolo}: ${nome}` : nome
    })
    .filter(Boolean)
  const parteConRuolo = parteProcessuale && ruoloParte ? `${parteProcessuale} (${ruoloParte})` : parteProcessuale
  const partiLabel = uniqueText(soggettiParti.length ? soggettiParti : partiProcessuali).join(' / ')
  const facts = [
    ['Cliente', cliente],
    ['Parte/Soggetto', parteConRuolo],
    ['Soggetti e parti', partiLabel],
    ['Ufficio', profileValue(audit, 'ufficio')],
    ['Giudice', profileValue(audit, 'giudice')],
    ['RG', profileValue(audit, 'numero_rg')],
    ['Evento', profileValue(audit, 'tipo_evento') || profileValue(audit, 'oggetto_evento')],
    ['Udienza', profileValue(audit, 'udienza_data_ora')],
    ['Modalità', profileValue(audit, 'modalita_udienza')],
  ].filter(([, value]) => value)
  const links = recordArray(remote.links)
  const times = stringArray(remote.times)
  const pdfPending = stringArray(remote.pdf_pending ?? remote.pdfPending)
  const pdfSources = stringArray(remote.pdf_sources ?? remote.pdfSources)
  const warnings = stringArray(remote.warnings)
  const checklist = (audit.lawyerChecklist.length ? audit.lawyerChecklist : stringArray(profile.checklist_avvocato)).slice(0, compact ? 3 : 5)
  if (!facts.length && !Object.keys(remote).length && !checklist.length) return null
  const mode = text(remote.mode) || profileValue(audit, 'modalita_udienza')
  const remoteDetected = Boolean(remote.detected || remote.pdf_required || remote.pdfRequired || links.length || mode)
  return (
    <section className={`iu-pec-procedural-profile${compact ? ' is-compact' : ''}`} aria-label="Profilo processuale PEC">
      <header>
        <span>Profilo processuale</span>
        <strong>{profileValue(audit, 'fase_pratica') || 'Evento da presidiare'}</strong>
      </header>
      {facts.length ? (
        <div className="iu-pec-profile-facts">
          {facts.map(([label, value]) => (
            <span key={`${label}-${value}`}><b>{label}</b>{value}</span>
          ))}
        </div>
      ) : null}
      {remoteDetected ? (
        <div className="iu-pec-remote-hearing">
          <div>
            <Clock3 size={14} />
            <span>
              <b>{mode ? `Udienza ${mode}` : 'Udienza da remoto'}</b>
              {times.length ? ` - ${times[0]}` : profileValue(audit, 'udienza_data_ora') ? ` - ${profileValue(audit, 'udienza_data_ora')}` : ''}
            </span>
          </div>
          {links.length ? (
            <div className="iu-pec-remote-links">
              {links.slice(0, 3).map((item) => {
                const url = text(item.url)
                if (!url) return null
                const exact = item.exact === true || item.exact_match === true || item.exactMatch === true
                const integrity = text(item.integrity)
                return (
                  <span key={url}>
                    <a href={url} target="_blank" rel="noreferrer">{url}</a>
                    <small>{exact || integrity === 'exact' ? 'Link verificato identico alla fonte letta.' : 'Link da verificare aprendo il PDF originale.'}</small>
                  </span>
                )
              })}
            </div>
          ) : (
            <p>
              <Paperclip size={14} />
              {pdfPending.length
                ? `Leggere/OCR il PDF per il link: ${pdfPending.slice(0, 3).join(', ')}.`
                : pdfSources.length
                  ? `Verificare nel PDF letto le istruzioni di collegamento: ${pdfSources.slice(0, 3).join(', ')}.`
                  : 'Verificare negli allegati PDF il link di collegamento e le istruzioni di accesso.'}
            </p>
          )}
          {warnings.slice(0, 2).map((warning) => <small key={warning}>{warning}</small>)}
        </div>
      ) : null}
      {checklist.length ? (
        <ul className="iu-pec-lawyer-checklist">
          {checklist.map((item) => <li key={item}>{item}</li>)}
        </ul>
      ) : null}
    </section>
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
        <PecProceduralProfile audit={audit} />
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
              <ConfidenceChip label="Udienza" field={fieldConfidence(audit, 'orario_udienza')} />
              <ConfidenceChip label="Modalità" field={fieldConfidence(audit, 'modalita_udienza')} />
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
          <PecProceduralProfile audit={audit} compact />
          <div className="iu-pec-sidebar-confidence" aria-label="Confidence campi PEC">
            <ConfidenceChip label="Mittente" field={fieldConfidence(audit, 'mittente')} />
            <ConfidenceChip label="Invio" field={fieldConfidence(audit, 'data_invio')} />
            <ConfidenceChip label="Consegna" field={fieldConfidence(audit, 'data_consegna')} />
            <ConfidenceChip label="Ricevuta" field={fieldConfidence(audit, 'tipo_ricevuta')} />
            <ConfidenceChip label="Protocollo" field={fieldConfidence(audit, 'protocollo')} />
            <ConfidenceChip label="Contesto" field={fieldConfidence(audit, 'contesto_legale')} />
            <ConfidenceChip label="Udienza" field={fieldConfidence(audit, 'orario_udienza')} />
            <ConfidenceChip label="Modalità" field={fieldConfidence(audit, 'modalita_udienza')} />
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

async function postMailActionPayload(url: string, label: string): Promise<MailActionPayload> {
  if (!url) throw new Error(`${label}: percorso operativo non configurato`)
  const response = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
  })
  if (!response.ok) throw new Error(`${label}: operazione non completata`)
  const contentType = response.headers.get('content-type') || ''
  if (!contentType.includes('application/json')) return { ok: true, message: `${label}: operazione eseguita.` }
  const payload = await response.json() as MailActionPayload
  if (payload.ok === false) throw new Error(payload.errore || `${label}: errore operativo`)
  return payload
}

async function postMailAction(url: string, label: string): Promise<string> {
  const payload = await postMailActionPayload(url, label)
  if (payload.warning && payload.sync_errore) {
    return `${payload.messaggio || payload.message || `${label}: completata con avvisi.`} ${payload.sync_errore}`
  }
  if (label.startsWith('Sincronizzazione')) {
    const nuove = Number(payload.nuove || 0)
    const allegati = Number(payload.allegati_salvati || 0)
    if (nuove || allegati) return `${label} completata: ${nuove} nuovi messaggi, ${allegati} allegati recuperati.`
  }
  return payload.messaggio || payload.message || `${label}: operazione eseguita.`
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
          {includeTelematic && item.pecPresidiata ? <Badge tone="success"><CheckCircle2 size={12} /> Presidiata</Badge> : null}
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
  const hasHtmlVersion = Boolean(detail.bodyHtml)
  const bodyState = detail.bodyCompleteness || ''
  const hasOriginal = bodyState === 'originale_acquisito'
  const title = hasOriginal ? 'Messaggio completo' : bodyState === 'presidio_pec' ? 'Testo del presidio PEC' : 'Testo disponibile'
  const stateLabel = detail.bodyCompletenessLabel || (
    hasOriginal
      ? 'EML originale acquisito.'
      : 'Acquisisci il MIME originale per vedere la PEC completa.'
  )
  return (
    <div className="iu-mail-full-detail" aria-label={title}>
      <header>
        <div>
          <strong>{title}</strong>
          <small>{stateLabel}</small>
        </div>
        <span>{detail.attachments.length} allegati</span>
      </header>
      <pre>{bodyText || 'Nessun testo disponibile per questo messaggio.'}</pre>
      {hasHtmlVersion ? (
        <details className="iu-mail-html-version">
          <summary>Versione grafica originale</summary>
          <iframe
            title="Versione grafica email"
            sandbox=""
            srcDoc={detail.bodyHtml}
          />
        </details>
      ) : null}
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
          {copy.includeTelematic && item.pecPresidiata ? <Badge tone="success"><CheckCircle2 size={12} /> Presidiata</Badge> : null}
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
      {!detail?.item ? (
        <p className="iu-mail-body-preview">{item.preview || 'Caricamento del messaggio completo in corso.'}</p>
      ) : null}
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
  const pstWaiting = rows.filter((item) => item.isPst && !item.pctStatus && !item.pecPresidiata).slice(0, 4)
  const pctAlerts = rows.filter((item) => !item.pecPresidiata && item.pctStatus && (item.pctStatus.includes('RIFIUT') || item.pctStatus.includes('ERRORE') || item.pctStatus.includes('WARN'))).slice(0, 4)
  const auditAlerts = rows.filter((item) => !item.pecPresidiata && item.pecAudit && item.pecAudit.qualityTone !== 'success').slice(0, 4)
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
  onOpenPresidio,
  onRunPresidio,
  running,
}: {
  rows: EmailPecRow[]
  summary: EmailPecPageData['summary']
  onOpenPresidio: (id: string) => void
  onRunPresidio: () => void
  running: boolean
}) {
  const warnings = rows.filter(isPecOperationalWarning)
  const first = warnings[0]
  const count = Math.max(Number(summary.warnings || 0), warnings.length)
  if (!count || !first) return null
  return (
    <section className="iu-mail-auto-notice" aria-label="Avviso automatico PEC" data-iusentra-sequence-slot="main-content">
      <AlertTriangle size={17} />
      <div>
        <strong>Avviso automatico PEC</strong>
        <span>{count} comunicazioni richiedono presidio: filtra le PEC da lavorare, acquisisce i MIME locali e aggiorna allegati, firme, scadenze e fascicolo quando disponibili.</span>
      </div>
      <div className="iu-mail-auto-notice__actions">
        <button type="button" onClick={() => onOpenPresidio(first.id)}>Apri presidio</button>
        <button type="button" onClick={onRunPresidio} disabled={running}>
          {running ? 'Controllo in corso...' : 'Esegui controllo'}
        </button>
      </div>
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
  const [deferredQuery, setDeferredQuery] = useState('')
  const [status, setStatus] = useState<EmailStatus>('tutti')
  const [sort, setSort] = useState<SortKey>('recenti')
  const [onlyPst, setOnlyPst] = useState(false)
  const [onlyAttachments, setOnlyAttachments] = useState(false)
  const [onlyWarnings, setOnlyWarnings] = useState(false)
  const [pctStatus, setPctStatus] = useState('')
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [selectedId, setSelectedId] = useState(currentEmailSelectionId(mode))
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [detail, setDetail] = useState<EmailDetailData | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailReloadKey, setDetailReloadKey] = useState(0)
  const [statusLine, setStatusLine] = useState('')
  const [bulkWorking, setBulkWorking] = useState(false)
  const [presidioWorking, setPresidioWorking] = useState(false)
  const [saveMatterRequest, setSaveMatterRequest] = useState<PecSaveMatterRequest | null>(null)

  const fetchPage = mode === 'ordinaria' ? getEmailOrdinariaPage : getEmailPecPage
  const fetchParams = {
    folder,
    q: deferredQuery,
    stato: status,
    pst: copy.includeTelematic ? onlyPst : false,
    conAllegati: onlyAttachments,
    statoPct: copy.includeTelematic ? pctStatus : '',
  }

  useEffect(() => {
    const timer = window.setTimeout(() => setDeferredQuery(query.trim()), 280)
    return () => window.clearTimeout(timer)
  }, [query])

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
  }, [folder, status, onlyPst, onlyAttachments, pctStatus, deferredQuery])

  const visible = useMemo(
    () => sortRows(
      data.items
        .filter((item) => isInsideQuery(item, query))
        .filter((item) => !onlyWarnings || isPecOperationalWarning(item)),
      sort,
    ),
    [data.items, query, onlyWarnings, sort],
  )
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

  const openPresidio = (id: string) => {
    setFolder('INBOX')
    setStatus('tutti')
    setOnlyPst(false)
    setOnlyAttachments(false)
    setOnlyWarnings(true)
    setPctStatus('')
    setAdvancedOpen(true)
    setQuery('')
    setSelectedId(id)
    writeMailboxSelection(mode, 'INBOX', id)
    setStatusLine('Presidio PEC aperto: sono visibili solo le comunicazioni che richiedono controllo.')
  }

  const runPresidio = () => {
    if (!data.actions.pecLocalAcquire) {
      setStatusLine('Presidio PEC non configurato per questa casella.')
      return
    }
    setPresidioWorking(true)
    setStatusLine('Presidio PEC in corso: acquisisco i MIME locali e aggiorno allegati, firme e scadenze disponibili.')
    const runAllBlocks = async () => {
      let runId = ''
      let message = ''
      let hasMore = true
      let rounds = 0
      while (hasMore && rounds < 240) {
        const separator = data.actions.pecLocalAcquire.includes('?') ? '&' : '?'
        const url = runId ? `${data.actions.pecLocalAcquire}${separator}run_id=${encodeURIComponent(runId)}` : data.actions.pecLocalAcquire
        const payload = await postMailActionPayload(url, 'Presidio PEC')
        rounds += 1
        runId = payload.run_id || runId
        hasMore = payload.has_more === true
        const done = Number(payload.cursor_index || 0)
        const total = Number(payload.total_emails || 0)
        message = payload.messaggio || payload.message || 'Presidio PEC aggiornato.'
        if (hasMore && total) {
          setStatusLine(`${message} Avanzamento ${done}/${total}.`)
        } else {
          setStatusLine(message)
        }
      }
      if (hasMore) {
        throw new Error('Presidio PEC sospeso: raggiunto il limite di sicurezza dei blocchi, rilancia il controllo per proseguire.')
      }
      return message || 'Presidio PEC completato.'
    }
    runAllBlocks()
      .then((message) => {
        setStatusLine(message)
        setOnlyWarnings(true)
        setAdvancedOpen(true)
        load()
        setDetailReloadKey((value) => value + 1)
      })
      .catch((error) => setStatusLine(error instanceof Error ? error.message : 'Presidio PEC: errore operativo'))
      .finally(() => setPresidioWorking(false))
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
          {copy.includeTelematic ? <label className="iu-mail-check"><input type="checkbox" checked={onlyWarnings} onChange={(event) => setOnlyWarnings(event.target.checked)} /><span>Solo da presidiare</span></label> : null}
          <button type="button" onClick={() => { setStatus('tutti'); setOnlyPst(false); setOnlyAttachments(false); setOnlyWarnings(false); setPctStatus(''); setQuery('') }}>Reset</button>
        </section>
      ) : null}

      <section className="iu-mail-status-line" data-iusentra-sequence-slot="main-content">
        <span className={loading ? '' : 'is-ok'}>{loading ? copy.syncingLabel : copy.updatedLabel}</span>
        <small><Clock3 size={14} /> Le azioni sono tracciate e separate tra PEC ed email ordinaria.</small>
        {selectedVisibleCount ? <small>{selectedVisibleCount} messaggi selezionati nella vista corrente.</small> : null}
        {statusLine ? <small className="iu-mail-operation-status">{statusLine}</small> : null}
      </section>

      {copy.includeTelematic ? <PecAutomaticNotice rows={visible} summary={data.summary} onOpenPresidio={openPresidio} onRunPresidio={runPresidio} running={presidioWorking} /> : null}

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

function OfficePecLookupPanel({ onInsert }: { onInsert: (pec: string) => void }) {
  const [open, setOpen] = useState(false)
  const [comune, setComune] = useState('')
  const [selectedComune, setSelectedComune] = useState<ComuneOption | null>(null)
  const [comuneOptions, setComuneOptions] = useState<ComuneOption[]>([])
  const [comuneLoading, setComuneLoading] = useState(false)
  const [officeKind, setOfficeKind] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<StudioRuntimeResult | null>(null)
  const [inserted, setInserted] = useState('')

  useEffect(() => {
    const query = comune.trim()
    if (!open || selectedComune?.nome === query || query.length < 2) {
      setComuneOptions([])
      return
    }
    let active = true
    const timer = window.setTimeout(() => {
      setComuneLoading(true)
      fetch(`/api/v1/ui/territorio/comuni?q=${encodeURIComponent(query)}&limit=12`, {
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      })
        .then((response) => response.ok ? response.json() : { items: [] })
        .then((payload) => {
          if (!active) return
          const items = Array.isArray(payload.items) ? payload.items : []
          setComuneOptions(items.map((item: JsonRecord) => ({
            codiceIstat: text(item.codiceIstat),
            nome: text(item.nome),
            label: text(item.label),
            cap: Array.isArray(item.cap) ? item.cap.map((cap) => text(cap)).filter(Boolean) : [],
            siglaProvincia: text(item.siglaProvincia),
            provincia: text(item.provincia),
          })).filter((item: ComuneOption) => item.codiceIstat && item.nome))
        })
        .catch(() => {
          if (active) setComuneOptions([])
        })
        .finally(() => {
          if (active) setComuneLoading(false)
        })
    }, 220)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [comune, open, selectedComune])

  const searchOffices = async () => {
    const city = comune.trim()
    if (city.length < 2) {
      setError('Inserisci almeno due caratteri del Comune.')
      setResult(null)
      return
    }
    setLoading(true)
    setError('')
    setInserted('')
    const formData = new FormData()
    formData.set('comune', city)
    if (selectedComune?.codiceIstat) formData.set('comune_istat', selectedComune.codiceIstat)
    formData.set('includi_speciali', '1')
    formData.set('solo_pec', '1')
    const kinds = officeKind
      ? [officeKind]
      : composeOfficeKindOptions.map((option) => option.value).filter(Boolean)
    kinds.forEach((kind) => formData.append('tipo_ufficio', kind))
    const token = csrfToken()
    try {
      const response = await fetch('/api/v1/ui/strumenti-legali/uffici_competenti', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          Accept: 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          ...(token ? { 'X-CSRFToken': token } : {}),
        },
        body: formData,
      })
      const payload = normaliseStudioRuntimeResult(await response.json().catch(() => ({})))
      if (!response.ok || !payload.ok) {
        throw new Error(payload.message || 'Ricerca non riuscita.')
      }
      setResult(payload)
      if (!payload.offices.length) {
        setError('Nessuna PEC pubblicata per questi criteri. Prova un filtro diverso o verifica il Comune.')
      }
    } catch (requestError) {
      setResult(null)
      setError(requestError instanceof Error ? requestError.message : 'Ricerca non riuscita.')
    } finally {
      setLoading(false)
    }
  }

  const insertOffice = (office: StudioRuntimeOffice) => {
    if (!office.pec) return
    onInsert(office.pec)
    setInserted(`${office.name}: PEC inserita nel destinatario.`)
  }

  return (
    <section className={`iu-mail-office-lookup ${open ? 'is-open' : ''}`}>
      <button
        className="iu-mail-office-lookup__toggle"
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <span><Landmark size={16} /> Ricerca uffici giudiziari per Comune</span>
        <ChevronDown size={17} />
      </button>
      {open ? (
        <div className="iu-mail-office-lookup__body">
          <div className="iu-mail-office-lookup__filters">
            <label>
              <span>Comune</span>
              <input
                type="text"
                value={comune}
                onChange={(event) => {
                  setComune(event.target.value)
                  setSelectedComune(null)
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault()
                    void searchOffices()
                  }
                }}
                placeholder="Comune di competenza"
              />
            </label>
            <label>
              <span>Ufficio</span>
              <select value={officeKind} onChange={(event) => setOfficeKind(event.target.value)}>
                {composeOfficeKindOptions.map((option) => (
                  <option value={option.value} key={option.value || 'all'}>{option.label}</option>
                ))}
              </select>
            </label>
            <button type="button" onClick={() => void searchOffices()} disabled={loading}>
              <Search size={15} /> {loading ? 'Ricerca in corso...' : 'Cerca PEC'}
            </button>
          </div>
          {comuneLoading || comuneOptions.length ? (
            <div className="iu-mail-office-comuni" aria-label="Comuni trovati">
              {comuneLoading ? <span>Ricerca Comuni...</span> : null}
              {comuneOptions.map((option) => (
                <button
                  type="button"
                  key={option.codiceIstat}
                  onClick={() => {
                    setComune(option.nome)
                    setSelectedComune(option)
                    setComuneOptions([])
                  }}
                >
                  <strong>{option.label}</strong>
                  <span>{option.cap.slice(0, 4).join(', ')}{option.cap.length > 4 ? '...' : ''}</span>
                </button>
              ))}
            </div>
          ) : null}
          {error ? <p className="iu-mail-office-lookup__notice" role="status">{error}</p> : null}
          {inserted ? <p className="iu-mail-office-lookup__success" role="status">{inserted}</p> : null}
          {result?.offices.length ? (
            <div className="iu-mail-office-results" aria-live="polite">
              {result.offices.map((office) => (
                <article className="iu-mail-office-result" key={office.id}>
                  <header>
                    <span><MapPin size={14} /> {office.typeLabel}</span>
                    <strong>{office.name}</strong>
                    <small>{[office.address, office.cap, office.city].filter(Boolean).join(' - ') || 'Sede non indicata'}</small>
                  </header>
                  <div>
                    <b>{office.pec}</b>
                    <button type="button" onClick={() => insertOffice(office)} disabled={!office.pec}>
                      <PlusCircle size={15} /> Inserisci
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : null}
          {result?.warnings.length ? (
            <p className="iu-mail-office-lookup__hint">{result.warnings[0]}</p>
          ) : null}
        </div>
      ) : null}
    </section>
  )
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
          pendingMessage={isOrdinary ? 'Invio email in corso...' : 'Invio PEC in corso...'}
          successMessage={isOrdinary ? 'Email ordinaria inviata con successo.' : 'PEC inviata e registrata nello studio.'}
        >
          {!isOrdinary && params.get('tipo') === 'notifica_l53' ? <input type="hidden" name="tipo_invio" value="notifica_l53" /> : null}
          {!isOrdinary ? <OfficePecLookupPanel onInsert={(pec) => setRecipient((current) => appendAddress(current, pec))} /> : null}
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
              <span><Settings2 size={16} /> <a href={settingsHref}>{isOrdinary ? 'Configurazione SMTP/IMAP' : 'Configurazione PEC'}</a>.</span>
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
