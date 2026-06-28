import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  ExternalLink,
  FileSignature,
  FileText,
  Hash,
  Mail,
  Maximize2,
  Minimize2,
  PenLine,
  Plus,
  ReceiptText,
  RefreshCw,
  Save,
  Search,
  Send,
  Sparkles,
  Trash2,
  X,
  XCircle,
} from 'lucide-react'
import {
  cancelFatturazioneDocument,
  confirmFatturazioneCommercialistaPec,
  confirmFatturazioneSdiPecSent,
  confirmFatturazioneXmlSigned,
  createFattura,
  emptyFatturazionePage,
  getFatturazioneDetail,
  getFatturazionePage,
  getNuovaFatturaPage,
  markFatturazionePaid,
  prepareFatturazioneCommercialista,
  prepareFatturazioneSdiPec,
  prepareFatturazioneXmlSignature,
  recordFatturazioneSdiOutcome,
  saveFatturazioneNumbering,
  sendFatturazioneCommercialistaEmail,
  updateFatturazioneDetail,
  updateFatturazioneStatus,
  type CreateFatturaPayload,
  type CreateFatturaResult,
  type FatturazioneDraft,
  type FatturazioneDetail,
  type FatturazioneDetailUpdatePayload,
  type FatturazioneFiscalDefaults,
  type FatturazioneFormDefinition,
  type FatturazioneMatter,
  type FatturazionePageData,
  type FatturazionePersonalizedData,
  type FatturazionePersonalizedParty,
  type FatturazioneRecord,
  type FatturazioneMutationResult,
  type FatturazioneNumberingResult,
  type FatturazioneVoiceDefault,
  type FatturazioneWorkflowResult,
} from '../fatturazioneData'
import { getSettings, saveSettingsSection } from '../features/impostazioni/api'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import { formatEuroInput, formatEuroIt, parseItalianAmount } from '../formatting'
import './FatturazionePage.css'

type VoiceRow = FatturazioneVoiceDefault & {
  rowId: string
}

type FormState = {
  id_cliente: string
  id_fascicolo: string
  data_emissione: string
  data_scadenza: string
  note: string
  voci: VoiceRow[]
  opzioni_fiscali: FatturazioneFiscalDefaults
  percentuale_spese_generali: string
  metodo_pagamento: string
  dati_personalizzati: FatturazionePersonalizedData
  hidden: Record<string, string>
}

type SaveStatus = 'idle' | 'saving' | 'success' | 'validation' | 'permission' | 'server'
type PaymentFilter = 'all' | 'bonifico' | 'senza_bonifico'
type IssueFilter = 'all' | 'emessa' | 'da_emettere'
type DetailTab = 'dettaglio' | 'pdf' | 'xml' | 'commercialista'
type ActionNotice = { tone: 'success' | 'warning' | 'danger' | 'info'; text: string } | null
type EditableVoice = {
  rowId: string
  descrizione: string
  quantita: string
  prezzo_unitario: string
  tipo: string
}

type QuickSdiPecSettings = {
  pec_notifiche: string
  pec_indirizzo: string
  pec_username: string
  pec_smtp_host: string
  pec_smtp_port: string
  pec_imap_host: string
  pec_imap_port: string
  pec_use_ssl: boolean
}

type QuickCommercialistaSettings = {
  nome_commercialista: string
  email_commercialista: string
  pec_commercialista: string
}

const defaultVoice: VoiceRow = {
  rowId: 'voce-1',
  descrizione: '',
  quantita: '1',
  prezzo_unitario: '',
  tipo: 'ONORARIO',
}

const defaultFiscalOptions: FatturazioneFiscalDefaults = {
  applica_iva: true,
  applica_cassa: true,
  applica_ritenuta: false,
  applica_bollo: false,
}

const noVatRegimes = new Set(['RF19', 'RF02'])
const allStatesFilter = 'all'
const defaultQuickSdiPecSettings: QuickSdiPecSettings = {
  pec_notifiche: '',
  pec_indirizzo: '',
  pec_username: '',
  pec_smtp_host: 'smtp.pec.aruba.it',
  pec_smtp_port: '465',
  pec_imap_host: 'imaps.pec.aruba.it',
  pec_imap_port: '993',
  pec_use_ssl: true,
}

const defaultQuickCommercialistaSettings: QuickCommercialistaSettings = {
  nome_commercialista: '',
  email_commercialista: '',
  pec_commercialista: '',
}

const fallbackFormState: FormState = {
  id_cliente: '',
  id_fascicolo: '',
  data_emissione: '',
  data_scadenza: '',
  note: '',
  voci: [defaultVoice],
  opzioni_fiscali: defaultFiscalOptions,
  percentuale_spese_generali: '15',
  metodo_pagamento: 'Bonifico',
  dati_personalizzati: {
    transmission: {
      identificativo_fiscale: '',
      codice_invio: '',
      telefono: '',
      email: '',
    },
    studio: {
      partita_iva: '',
      codice_fiscale: '',
      nome_denominazione: '',
      denominazione: '',
      nome: '',
      cognome: '',
      indirizzo: '',
      indirizzo_completo: '',
      cap: '',
      citta: '',
      provincia: '',
      nazione: 'IT',
      pec: '',
      email: '',
      telefono: '',
      codice_destinatario: '',
      iban: '',
      istituto_finanziario: '',
    },
    recipient: {
      partita_iva: '',
      codice_fiscale: '',
      nome_denominazione: '',
      denominazione: '',
      nome: '',
      cognome: '',
      indirizzo: '',
      indirizzo_completo: '',
      cap: '',
      citta: '',
      provincia: '',
      nazione: 'IT',
      pec: '',
      email: '',
      telefono: '',
      codice_destinatario: '',
      iban: '',
      istituto_finanziario: '',
    },
    document: {
      tipo_documento: 'TD01',
      tipo_documento_label: 'Fattura',
      numero_documento: '',
      data_documento: '',
      causale_oggetto: '',
      regime_fiscale: 'RF01',
      regime_fiscale_label: 'Regime ordinario',
      esigibilita_iva: 'I',
      esigibilita_iva_label: 'Immediata',
      cassa_previdenziale: 'TC01',
      cassa_previdenziale_label: 'Avvocati',
      percentuale_spese_generali: '15',
      fascicolo_label: '',
    },
    payment: {
      modalita_pagamento: 'MP05',
      modalita_pagamento_label: 'Bonifico',
      modalita_pagamento_codice: 'MP05',
      beneficiario: '',
      istituto_finanziario: '',
      iban: '',
      bic_swift: '',
      data_decorrenza: '',
      giorni_termini: '30',
      importo_pagamento: '',
    },
  },
  hidden: {},
}

function displayValue(value: string | number): string {
  if (typeof value === 'number') return new Intl.NumberFormat('it-IT').format(value)
  return value
}

function hasMetricValue(value: string | number): boolean {
  if (typeof value === 'number') return value !== 0
  const normalized = value.replace(/\s+/g, '').toUpperCase()
  return !['0', '0,00', '0.00', '€0', '€0,00', '€0.00', 'EUR0', 'EUR0,00', 'EUR0.00'].includes(normalized)
}

function requestedFatturazioneDetailId(): string {
  const params = new URLSearchParams(window.location.search)
  return params.get('id_documento') || params.get('id_parcella') || ''
}

function settingsPlainRecord(raw: Record<string, unknown> | undefined): Record<string, unknown> {
  if (!raw) return {}
  return Object.fromEntries(
    Object.entries(raw).map(([key, value]) => {
      if (value && typeof value === 'object' && !Array.isArray(value) && 'present' in value) return [key, '']
      return [key, value]
    }),
  )
}

function settingsTextValue(raw: unknown, fallback = ''): string {
  if (raw === undefined || raw === null) return fallback
  if (typeof raw === 'boolean') return raw ? '1' : ''
  return String(raw).trim() || fallback
}

function settingsBoolValue(raw: unknown, fallback = false): boolean {
  if (typeof raw === 'boolean') return raw
  if (raw === undefined || raw === null || raw === '') return fallback
  return ['1', 'true', 'si', 'sì', 'yes', 'on'].includes(String(raw).trim().toLowerCase())
}

function rowFromDefault(item: FatturazioneVoiceDefault, index: number): VoiceRow {
  return {
    rowId: `voce-${index + 1}`,
    descrizione: item.descrizione,
    quantita: item.quantita || '1',
    prezzo_unitario: currencyInputValue(item.prezzo_unitario),
    tipo: item.tipo || 'ONORARIO',
  }
}

function isVatExcludedRegime(regime: string | undefined): boolean {
  return noVatRegimes.has((regime || '').trim().toUpperCase())
}

function regimeLabel(regime: string): string {
  return ({
    RF01: 'Regime ordinario',
    RF19: 'Regime forfettario',
    RF02: 'Regime minimo',
  })[regime] || 'Regime fiscale'
}

function stateFromForm(form: FatturazioneFormDefinition | undefined): FormState {
  const defaults = form?.defaults
  const rows = (defaults?.voci || []).map(rowFromDefault)
  const regime = defaults?.dati_personalizzati?.document.regime_fiscale || 'RF01'
  const ivaLocked = isVatExcludedRegime(regime)
  return {
    id_cliente: defaults?.id_cliente || '',
    id_fascicolo: defaults?.id_fascicolo || '',
    data_emissione: defaults?.data_emissione || '',
    data_scadenza: defaults?.data_scadenza || '',
    note: defaults?.note || '',
    voci: rows.length ? rows : [defaultVoice],
    opzioni_fiscali: {
      ...(defaults?.opzioni_fiscali || defaultFiscalOptions),
      applica_iva: ivaLocked ? false : (defaults?.opzioni_fiscali?.applica_iva ?? defaultFiscalOptions.applica_iva),
    },
    percentuale_spese_generali: defaults?.percentuale_spese_generali || '15',
    metodo_pagamento: defaults?.metodo_pagamento || defaults?.dati_personalizzati?.payment.modalita_pagamento_label || 'Bonifico',
    dati_personalizzati: defaults?.dati_personalizzati || fallbackFormState.dati_personalizzati,
    hidden: defaults?.hidden || form?.hidden || {},
  }
}

function numericInputValue(value: string | number, fallback: number): number {
  return parseItalianAmount(value, fallback)
}

function displayErrors(errors: Record<string, string>): string[] {
  return Object.entries(errors)
    .map(([field, message]) => `${field}: ${message}`)
    .filter(Boolean)
}

function buildPayload(formState: FormState): CreateFatturaPayload {
  return {
    ...formState.hidden,
    id_cliente: formState.id_cliente,
    id_fascicolo: formState.id_fascicolo,
    data_emissione: formState.data_emissione,
    data_scadenza: formState.data_scadenza,
    note: formState.note,
    opzioni_fiscali: formState.opzioni_fiscali,
    percentuale_spese_generali: formState.percentuale_spese_generali,
    metodo_pagamento: formState.metodo_pagamento,
    dati_personalizzati: formState.dati_personalizzati,
    voci: formState.voci.map((row) => ({
      descrizione: row.descrizione,
      quantita: numericInputValue(row.quantita, 1),
      prezzo_unitario: numericInputValue(row.prezzo_unitario, 0),
      tipo: row.tipo || 'ONORARIO',
    })),
  }
}

function currency(value: number): string {
  return formatEuroIt(value)
}

function currencyInputValue(value: string | number): string {
  return formatEuroInput(value)
}

function machineAmountValue(value: string | number): string {
  return numericInputValue(value, 0).toFixed(2)
}

function lineTotal(row: VoiceRow): number {
  return numericInputValue(row.quantita, 1) * numericInputValue(row.prezzo_unitario, 0)
}

function mergeParty(current: FatturazionePersonalizedParty, incoming?: FatturazionePersonalizedParty): FatturazionePersonalizedParty {
  if (!incoming) return current
  return { ...current, ...incoming }
}

function computePreview(formState: FormState) {
  const ivaLocked = isVatExcludedRegime(formState.dati_personalizzati.document.regime_fiscale)
  const competenze = formState.voci
    .filter((row) => (row.tipo || 'ONORARIO') !== 'SPESE' && (row.tipo || 'ONORARIO') !== 'ANTICIPO')
    .reduce((sum, row) => sum + lineTotal(row), 0)
  const speseImponibili = formState.voci
    .filter((row) => row.tipo === 'SPESE')
    .reduce((sum, row) => sum + lineTotal(row), 0)
  const anticipazioni = formState.voci
    .filter((row) => row.tipo === 'ANTICIPO')
    .reduce((sum, row) => sum + lineTotal(row), 0)
  const percSpeseGenerali = numericInputValue(formState.percentuale_spese_generali, 0)
  const speseGenerali = Math.max(0, competenze * (percSpeseGenerali / 100))
  const imponibile = competenze + speseImponibili + speseGenerali
  const cassa = formState.opzioni_fiscali.applica_cassa ? imponibile * 0.04 : 0
  const baseIva = imponibile + cassa
  const iva = formState.opzioni_fiscali.applica_iva && !ivaLocked ? baseIva * 0.22 : 0
  const bollo = formState.opzioni_fiscali.applica_bollo ? 2 : 0
  const ritenutaBase = competenze + speseGenerali
  const ritenuta = formState.opzioni_fiscali.applica_ritenuta ? ritenutaBase * 0.2 : 0
  const totaleDocumento = baseIva + iva + bollo + anticipazioni
  const totale = totaleDocumento - ritenuta
  return {
    competenze,
    speseImponibili,
    anticipazioni,
    speseGenerali,
    imponibile,
    cassa,
    baseIva,
    iva,
    bollo,
    ritenuta,
    totaleDocumento,
    totale,
  }
}

function WarningPanel({ data }: { data: FatturazionePageData }) {
  if (!data.warnings.length) return null
  return (
    <Panel title="Avvisi economici">
      <div className="iu-fatt-warnings">
        {data.warnings.map((warning) => (
          <div className="iu-fatt-warning" key={`${warning.code}-${warning.message}`}>
            <Badge tone="warning">Avviso</Badge>
            <span>{warning.message}</span>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function SdiWorkflowPanel({ data }: { data: FatturazionePageData }) {
  if (!data.sdiWorkflow.length && !data.officialSources.length) return null
  return (
    <Panel title="Invio e monitoraggio SdI" subtitle={data.sdiChannel.message || data.sdiChannel.label}>
      <div className="iu-fatt-sdi-panel">
        <div className="iu-fatt-sdi-channel">
          <Badge tone={data.sdiChannel.configured ? 'success' : 'warning'}>{data.sdiChannel.label}</Badge>
          <span>
            {data.sdiChannel.configured
              ? 'Invio automatico disponibile solo con la configurazione reale attiva.'
              : 'Senza canale accreditato o intermediario IUSENTRA prepara XML e registra identificativo/esiti, ma non spedisce al Sistema di Interscambio.'}
          </span>
        </div>
        <div className="iu-fatt-sdi-steps">
          {data.sdiWorkflow.map((step) => (
            <article key={step.id}>
              <Badge tone={step.tone}>{step.label}</Badge>
              <span>{step.message}</span>
            </article>
          ))}
        </div>
        {data.officialSources.length ? (
          <div className="iu-fatt-sdi-sources">
            {data.officialSources.map((source) => (
              <a href={source.url} target="_blank" rel="noreferrer" key={source.id}>
                <FileText size={15}/>
                <span>{source.label}</span>
                <small>{source.authority}</small>
              </a>
            ))}
          </div>
        ) : null}
      </div>
    </Panel>
  )
}

function ContractPanel({ data }: { data: FatturazionePageData }) {
  return (
    <Panel title="Presidio dati" subtitle="Lettura operativa con proprietà fiscale governata.">
      <div className="iu-fatt-contract">
        <span>Generato: {data.generated_at || 'non disponibile'}</span>
        <span>Calcolo: governato</span>
        <span>Consultazione: {data.contracts.operational ? 'attiva' : 'non disponibile'}</span>
      </div>
    </Panel>
  )
}

function FiscalGuardrailsPanel({ data }: { data: FatturazionePageData }) {
  const hasSdi = data.sdiWorkflow.length > 0 || data.officialSources.length > 0
  const hasWarnings = data.warnings.length > 0
  if (!hasSdi && !hasWarnings) return null

  return (
    <details className="iu-fatt-presidi">
      <summary>
        <span>
          <FileText size={16} />
          <strong>Presidi fiscali e SdI</strong>
        </span>
        <small>{data.sdiChannel.message || data.sdiChannel.label}</small>
      </summary>
      <div className="iu-fatt-presidi__body">
        {hasWarnings ? (
          <section className="iu-fatt-presidi__group" aria-label="Avvisi economici">
            {data.warnings.map((warning) => (
              <div className="iu-fatt-presidi__row" key={`${warning.code}-${warning.message}`}>
                <Badge tone="warning">Avviso</Badge>
                <span>{warning.message}</span>
              </div>
            ))}
          </section>
        ) : null}
        <section className="iu-fatt-presidi__group" aria-label="Canale SdI">
          <div className="iu-fatt-presidi__row">
            <Badge tone={data.sdiChannel.configured ? 'success' : 'warning'}>{data.sdiChannel.label}</Badge>
            <span>
              {data.sdiChannel.configured
                ? 'Canale configurato. XML, identificativi ed esiti restano collegati ai documenti.'
                : 'XML FatturaPA e identificativi restano disponibili; invio solo con canale o intermediario configurato.'}
            </span>
          </div>
          {data.sdiWorkflow.map((step) => (
            <div className="iu-fatt-presidi__row" key={step.id}>
              <Badge tone={step.tone}>{step.label}</Badge>
              <span>{step.message}</span>
            </div>
          ))}
        </section>
        {data.officialSources.length ? (
          <nav className="iu-fatt-presidi__sources" aria-label="Fonti tecniche fatturazione">
            {data.officialSources.map((source) => (
              <a href={source.url} target="_blank" rel="noreferrer" key={source.id}>
                <FileText size={15} />
                <span>{source.label}</span>
                <small>{source.authority}</small>
              </a>
            ))}
          </nav>
        ) : null}
      </div>
    </details>
  )
}

function normalizeFilterValue(value: string | number | null | undefined) {
  return String(value || '').trim().toLowerCase()
}

function hasRegisteredTransfer(record: FatturazioneRecord) {
  const method = normalizeFilterValue(record.paymentMethod)
  return record.state === 'PAGATA' && (Boolean(record.paidAt) || method.includes('bonifico'))
}

function isIssuedInvoice(record: FatturazioneRecord) {
  return ['EMESSA', 'PAGATA', 'SCADUTA'].includes(record.state)
}

function isToIssueInvoice(record: FatturazioneRecord) {
  return record.state === 'BOZZA' || record.isProforma
}

function CompactOperations({
  data,
  totalRecords,
  visibleRecords,
  stateFilter,
  paymentFilter,
  issueFilter,
  onStateFilter,
  onPaymentFilter,
  onIssueFilter,
  exportAction,
}: {
  data: FatturazionePageData
  totalRecords: number
  visibleRecords: number
  stateFilter: string
  paymentFilter: PaymentFilter
  issueFilter: IssueFilter
  onStateFilter: (value: string) => void
  onPaymentFilter: (value: PaymentFilter) => void
  onIssueFilter: (value: IssueFilter) => void
  exportAction?: FatturazionePageData['actions'][number]
}) {
  const stateItems = data.sections.find((section) => section.id === 'stati')?.items || []
  const selectedState = stateFilter.toLowerCase()
  const bonificoCount = data.records.filter(hasRegisteredTransfer).length
  const issuedCount = data.records.filter(isIssuedInvoice).length

  return (
    <section className="iu-fatt-ops" aria-label="Azioni rapide fatturazione">
      <header className="iu-fatt-ops__head">
        <strong>Azioni rapide</strong>
        <span>{visibleRecords} filtrati su {totalRecords}</span>
      </header>
      <div className="iu-fatt-chipbar" aria-label="Filtri rapidi per stato parcella">
        <button
          type="button"
          className={`iu-fatt-chip ${stateFilter === allStatesFilter ? 'is-active' : ''}`}
          onClick={() => onStateFilter(allStatesFilter)}
          data-tone="neutral"
          aria-pressed={stateFilter === allStatesFilter}
        >
          <Hash size={15} />
          <span>Tutte</span>
          <strong>{totalRecords}</strong>
        </button>
        {stateItems.map((item) => {
          const code = item.id.toUpperCase()
          return (
            <button
              type="button"
              className={`iu-fatt-chip ${selectedState === item.id ? 'is-active' : ''}`}
              onClick={() => onStateFilter(code)}
              data-tone={item.tone}
              aria-pressed={selectedState === item.id}
              key={item.id}
            >
              <ReceiptText size={15} />
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </button>
          )
        })}
      </div>
      <div className="iu-fatt-chipbar iu-fatt-chipbar--actions" aria-label="Azioni operative fatturazione">
        <button
          type="button"
          className={`iu-fatt-chip ${paymentFilter === 'bonifico' ? 'is-active' : ''}`}
          onClick={() => onPaymentFilter(paymentFilter === 'bonifico' ? 'all' : 'bonifico')}
          data-tone="success"
          aria-pressed={paymentFilter === 'bonifico'}
        >
          <CheckCircle2 size={15} />
          <span>Bonifico registrato</span>
          <strong>{bonificoCount}</strong>
        </button>
        <button
          type="button"
          className={`iu-fatt-chip ${issueFilter === 'emessa' ? 'is-active' : ''}`}
          onClick={() => onIssueFilter(issueFilter === 'emessa' ? 'all' : 'emessa')}
          data-tone="primary"
          aria-pressed={issueFilter === 'emessa'}
        >
          <ReceiptText size={15} />
          <span>Parcella emessa</span>
          <strong>{issuedCount}</strong>
        </button>
        <a className="iu-fatt-chip" href="/fatturazione/nuova" data-tone="primary">
          <Plus size={15} />
          <span>Nuova parcella</span>
        </a>
        {exportAction ? (
          <a className="iu-fatt-chip" href={exportAction.href} data-tone="warning">
            <Download size={15} />
            <span>Export CSV</span>
          </a>
        ) : null}
        <a className="iu-fatt-chip" href="#fatturazione-numerazione" data-tone="info">
          <Save size={15} />
          <span>Numerazione</span>
          <strong>{data.nextNumber || 'n.d.'}</strong>
        </a>
        <a className="iu-fatt-chip" href="/impostazioni/sdi" data-tone={data.sdiChannel.configured ? 'success' : 'warning'}>
          <Mail size={15} />
          <span>Canale SdI</span>
          <strong>{data.sdiChannel.configured ? 'Attivo' : 'Da fare'}</strong>
        </a>
      </div>
    </section>
  )
}

function InvoiceRow({
  record,
  data,
  savingId,
  onDetail,
  onOpenTab,
  onStatus,
  onCancel,
  onPaid,
}: {
  record: FatturazioneRecord
  data: FatturazionePageData
  savingId: string
  onDetail: (record: FatturazioneRecord) => void
  onOpenTab: (record: FatturazioneRecord, tab: DetailTab) => void
  onStatus: (record: FatturazioneRecord, stato: string) => void
  onCancel: (record: FatturazioneRecord) => void
  onPaid: (record: FatturazioneRecord) => void
}) {
  const [nextStatus, setNextStatus] = useState(record.state)
  return (
    <article className="iu-fatt-record">
      <div className="iu-fatt-record__main">
        <div className="iu-fatt-record__meta">
          <span>{record.number || record.id}</span>
          <Badge tone={record.isProforma ? 'warning' : 'primary'}>{record.documentKindLabel}</Badge>
          {record.proformaSourceLabel ? <small>{record.proformaSourceLabel}</small> : null}
        </div>
        <strong>{record.customerName}</strong>
        {record.caseTitle ? <small>{record.caseTitle}</small> : null}
      </div>
      <div className="iu-fatt-record__dates">
        <span>Emissione {record.issuedAt || 'non indicata'}</span>
        <span>Scadenza {record.dueAt || 'non indicata'}</span>
        {record.paidAt ? <span>Incasso {record.paidAt}</span> : null}
      </div>
      <div className="iu-fatt-record__amount">
        <strong>{record.amountDisplay || 'Importo non indicato'}</strong>
        <Badge tone={record.stateTone}>{record.stateLabel}</Badge>
        <Badge tone={record.sdiStateTone}>{record.sdiStateLabel}</Badge>
        {record.sdiIdentifier ? <small>SdI {record.sdiIdentifier}</small> : null}
        {record.sdiStatusMessage ? <small>{record.sdiStatusMessage}</small> : null}
        {record.paymentMethod ? <small>{record.paymentMethod}</small> : null}
      </div>
      <div className="iu-fatt-record__actions">
        <Button type="button" tone="neutral" onClick={() => onDetail(record)}>
          <Search size={15} />
          Apri dettaglio
        </Button>
        {data.permissions.canUpdateStatus ? (
          <div className="iu-fatt-status-action">
            <select value={nextStatus} onChange={(event) => setNextStatus(event.currentTarget.value)} aria-label="Nuovo stato documento">
              {data.statuses.map((status) => <option value={status.value} key={status.value}>{status.label}</option>)}
            </select>
            <Button type="button" tone="neutral" disabled={savingId === record.id || nextStatus === record.state} onClick={() => onStatus(record, nextStatus)}>
              {savingId === record.id ? 'Salvataggio' : 'Aggiorna'}
            </Button>
          </div>
        ) : null}
        {data.permissions.canUpdateStatus && record.isProforma && record.state === 'BOZZA' ? (
          <Button type="button" tone="primary" disabled={savingId === record.id} onClick={() => onStatus(record, 'EMESSA')}>
            <ReceiptText size={15} />
            Emetti parcella
          </Button>
        ) : null}
        {data.permissions.canMarkPaid && record.state !== 'PAGATA' ? (
          <Button type="button" tone="success" disabled={savingId === record.id} onClick={() => onPaid(record)}>
            <CheckCircle2 size={15} />
            {record.isProforma ? 'Registra bonifico' : 'Segna pagata'}
          </Button>
        ) : null}
        {data.permissions.canCancel && record.state !== 'ANNULLATA' ? (
          <Button type="button" tone="danger" disabled={savingId === record.id} onClick={() => onCancel(record)}>
            Annulla
          </Button>
        ) : null}
        {record.pdfHref ? (
          <Button type="button" tone="neutral" onClick={() => onOpenTab(record, 'pdf')}>
            <FileText size={15} />
            PDF
          </Button>
        ) : null}
        {record.xmlHref ? (
          <Button type="button" tone="neutral" onClick={() => onOpenTab(record, 'xml')}>
            <FileText size={15} />
            XML
          </Button>
        ) : null}
      </div>
    </article>
  )
}

function NumberingPanel({
  data,
  onSaved,
}: {
  data: FatturazionePageData
  onSaved: (result: FatturazioneNumberingResult) => void
}) {
  const [anno, setAnno] = useState(String(data.numbering.anno || new Date().getFullYear()))
  const [ultimoNumero, setUltimoNumero] = useState(String(data.numbering.ultimoNumeroConfigurato || ''))
  const [saving, setSaving] = useState(false)
  const [result, setResult] = useState<FatturazioneNumberingResult | null>(null)

  useEffect(() => {
    setAnno(String(data.numbering.anno || new Date().getFullYear()))
    setUltimoNumero(String(data.numbering.ultimoNumeroConfigurato || ''))
  }, [data.numbering.anno, data.numbering.ultimoNumeroConfigurato])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    const response = await saveFatturazioneNumbering({
      anno: Number(anno),
      ultimoNumeroUsato: Number(ultimoNumero || 0),
    })
    setResult(response)
    onSaved(response)
    setSaving(false)
  }

  const errors = result?.errors || {}
  return (
    <Panel title="Numerazione fatture" subtitle={`Prossimo numero ${data.numbering.prossimoNumero || data.nextNumber || 'n.d.'}`}>
      <form className="iu-fatt-numbering" onSubmit={submit}>
        <label className="iu-fatt-field">
          <span>Anno</span>
          <input
            value={anno}
            onChange={(event) => setAnno(event.currentTarget.value)}
            inputMode="numeric"
            disabled={!data.permissions.canConfigureNumbering || saving}
          />
        </label>
        <label className="iu-fatt-field">
          <span>Ultimo numero usato</span>
          <input
            value={ultimoNumero}
            onChange={(event) => setUltimoNumero(event.currentTarget.value)}
            inputMode="numeric"
            disabled={!data.permissions.canConfigureNumbering || saving}
          />
        </label>
        <div className="iu-fatt-numbering__summary">
          <Hash size={16} />
          <span>Esistente {data.numbering.ultimoNumeroEsistente}</span>
          <strong>{data.numbering.prossimoNumero || data.nextNumber || 'n.d.'}</strong>
        </div>
        <Button type="submit" tone="primary" disabled={!data.permissions.canConfigureNumbering || saving}>
          <Save size={15} />
          {saving ? 'Salvataggio' : 'Salva numerazione'}
        </Button>
      </form>
      {result ? (
        <section className={`iu-fatt-numbering-state ${result.ok ? 'is-success' : 'is-error'}`} aria-live="polite">
          {result.ok ? <CheckCircle2 size={17} /> : <AlertTriangle size={17} />}
          <span>{result.message}</span>
          {Object.values(errors).map((error) => <small key={error}>{error}</small>)}
        </section>
      ) : null}
    </Panel>
  )
}

function MetricGrid({ data }: { data: FatturazionePageData }) {
  const metrics = data.metrics.filter((metric) => hasMetricValue(metric.value))
  if (!metrics.length) return null
  return (
    <section className="iu-fatt-metrics-strip" aria-label="Indicatori fatturazione">
      {metrics.map((metric) => (
        <article className="iu-fatt-metric-pill" data-tone={metric.tone} key={metric.id}>
          <span>{metric.label}</span>
          <strong>{displayValue(metric.value)}</strong>
          <small>{metric.note}</small>
        </article>
      ))}
    </section>
  )
}

function StatusMessage({
  status,
  result,
  errors,
}: {
  status: SaveStatus
  result: CreateFatturaResult | null
  errors: Record<string, string>
}) {
  if (status === 'idle' || status === 'saving') return null
  if (status === 'success' && result?.item) {
    return (
      <section className="iu-fatt-state iu-fatt-state--success" aria-live="polite">
        <CheckCircle2 size={20} />
        <div>
          <strong>{result.message}</strong>
          <span>Documento {result.item.number || result.item.id} creato correttamente.</span>
        </div>
      </section>
    )
  }
  if (status === 'permission') {
    return (
      <section className="iu-fatt-state iu-fatt-state--danger" aria-live="polite">
        <XCircle size={20} />
        <div>
          <strong>Permesso negato</strong>
          <span>Serve il permesso di creazione o modifica fatturazione.</span>
        </div>
      </section>
    )
  }
  if (status === 'server') {
    return (
      <section className="iu-fatt-state iu-fatt-state--danger" aria-live="polite">
        <AlertTriangle size={20} />
        <div>
          <strong>Operazione non completata</strong>
          <span>{result?.message || 'Il salvataggio non è stato completato.'}</span>
        </div>
      </section>
    )
  }
  const rows = displayErrors(errors)
  return (
    <section className="iu-fatt-state iu-fatt-state--warning" aria-live="polite">
      <AlertTriangle size={20} />
      <div>
        <strong>Controlla i campi evidenziati</strong>
        {rows.length ? rows.map((row) => <span key={row}>{row}</span>) : <span>La richiesta non è stata accettata.</span>}
      </div>
    </section>
  )
}

function TechnicalRollback({ href = '/fatturazione/nuova?_legacy=1' }: { href?: string }) {
  return (
    <section className="iu-fatt-rollback" aria-label="Percorso di recupero">
      <div>
        <strong>Percorso di recupero</strong>
        <span>Disponibile solo per assistenza e confronto con il template storico, non come flusso principale.</span>
      </div>
      <ButtonLink href={href} tone="warning">
        <ExternalLink size={15} />
        Apri percorso di recupero
      </ButtonLink>
    </section>
  )
}

function VoiceEditor({
  rows,
  onChange,
}: {
  rows: VoiceRow[]
  onChange: (rows: VoiceRow[]) => void
}) {
  function updateRow(rowId: string, patch: Partial<VoiceRow>) {
    onChange(rows.map((row) => (row.rowId === rowId ? { ...row, ...patch } : row)))
  }

  return (
    <div className="iu-fatt-service-list">
      <div className="iu-fatt-service-list__header">
        <strong>Voci prestazioni</strong>
        <button
          type="button"
          className="iu-fatt-icon-button"
          onClick={() => onChange([...rows, { ...defaultVoice, rowId: `voce-${Date.now()}-${rows.length}` }])}
          aria-label="Aggiungi voce"
          title="Aggiungi voce"
        >
          <Plus size={16} />
        </button>
      </div>
      {rows.map((row) => (
        <div className="iu-fatt-service-row" key={row.rowId}>
          <label className="iu-fatt-field">
            <span>Descrizione</span>
            <input
              type="text"
              required
              value={row.descrizione}
              onChange={(event) => updateRow(row.rowId, { descrizione: event.currentTarget.value })}
              placeholder="Prestazione professionale"
            />
          </label>
          <label className="iu-fatt-field">
            <span>Quantita</span>
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={row.quantita}
              onChange={(event) => updateRow(row.rowId, { quantita: event.currentTarget.value })}
            />
          </label>
          <label className="iu-fatt-field">
            <span>Importo unitario</span>
            <input
              type="text"
              inputMode="decimal"
              value={row.prezzo_unitario}
              onChange={(event) => updateRow(row.rowId, { prezzo_unitario: event.currentTarget.value })}
              onBlur={(event) => updateRow(row.rowId, { prezzo_unitario: currencyInputValue(event.currentTarget.value) })}
              placeholder="€ 0,00"
            />
          </label>
          <label className="iu-fatt-field">
            <span>Tipo</span>
            <select value={row.tipo} onChange={(event) => updateRow(row.rowId, { tipo: event.currentTarget.value })}>
              <option value="ONORARIO">Onorario</option>
              <option value="SPESE">Spese</option>
              <option value="ANTICIPO">Anticipo</option>
              <option value="ALTRO">Altro</option>
            </select>
          </label>
          <button
            type="button"
            className="iu-fatt-icon-button iu-fatt-icon-button--danger"
            disabled={rows.length === 1}
            onClick={() => onChange(rows.filter((item) => item.rowId !== row.rowId))}
            aria-label="Rimuovi voce"
            title="Rimuovi voce"
          >
            <Trash2 size={16} />
          </button>
        </div>
      ))}
    </div>
  )
}

function FiscalOptions({
  values,
  onChange,
  disableIva,
}: {
  values: FatturazioneFiscalDefaults
  onChange: (values: FatturazioneFiscalDefaults) => void
  disableIva?: boolean
}) {
  const options: Array<{ name: keyof FatturazioneFiscalDefaults; label: string }> = [
    { name: 'applica_cassa', label: 'Cassa Forense' },
    { name: 'applica_iva', label: 'IVA' },
    { name: 'applica_ritenuta', label: 'Ritenuta' },
    { name: 'applica_bollo', label: 'Bollo' },
  ]
  return (
    <div className="iu-fatt-options" aria-label="Opzioni fiscali">
      {options.map((option) => (
        <label key={option.name}>
          <input
            type="checkbox"
            checked={values[option.name]}
            disabled={option.name === 'applica_iva' && disableIva}
            onChange={(event) => onChange({ ...values, [option.name]: event.currentTarget.checked })}
          />
          <span>{option.label}</span>
        </label>
      ))}
    </div>
  )
}

function NewInvoiceForm({
  data,
  form,
}: {
  data: FatturazionePageData
  form: FatturazioneFormDefinition | undefined
}) {
  const [formState, setFormState] = useState<FormState>(() => stateFromForm(form))
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const [result, setResult] = useState<CreateFatturaResult | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    setFormState(stateFromForm(form))
    setSaveStatus('idle')
    setResult(null)
    setErrors({})
  }, [form])

  const filteredMatters = useMemo(
    () => data.matters.filter((matter) => !formState.id_cliente || matter.idCliente === formState.id_cliente),
    [data.matters, formState.id_cliente],
  )
  const preview = useMemo(() => computePreview(formState), [formState])
  const canSave = form?.enabled !== false
  const noClients = data.clients.length === 0
  const clientProfile = data.clientProfiles[formState.id_cliente]
  const matterProfile = data.matterProfiles[formState.id_fascicolo]
  const ivaLocked = isVatExcludedRegime(formState.dati_personalizzati.document.regime_fiscale)

  function updatePersonalized<K extends keyof FatturazionePersonalizedData>(
    section: K,
    patch: Partial<FatturazionePersonalizedData[K]>,
  ) {
    setFormState((current) => ({
      ...current,
      dati_personalizzati: {
        ...current.dati_personalizzati,
        [section]: {
          ...current.dati_personalizzati[section],
          ...patch,
        },
      },
    }))
  }

  function applyClientToRecipient(clientId: string) {
    const incoming = data.clientProfiles[clientId]
    if (!incoming) return
    setFormState((current) => ({
      ...current,
      id_cliente: clientId,
      id_fascicolo: '',
      dati_personalizzati: {
        ...current.dati_personalizzati,
        recipient: {
          ...mergeParty(current.dati_personalizzati.recipient, incoming),
          codice_destinatario: current.dati_personalizzati.recipient.codice_destinatario || '0000000',
        },
      },
    }))
  }

  function applyStudioDefaults() {
    setFormState((current) => ({
      ...current,
      dati_personalizzati: {
        ...current.dati_personalizzati,
        studio: data.studioProfile,
        transmission: {
          ...current.dati_personalizzati.transmission,
          identificativo_fiscale:
            data.studioProfile.codice_fiscale || data.studioProfile.partita_iva || current.dati_personalizzati.transmission.identificativo_fiscale,
          telefono: data.studioProfile.telefono || current.dati_personalizzati.transmission.telefono,
          email: data.studioProfile.email || current.dati_personalizzati.transmission.email,
        },
        payment: {
          ...current.dati_personalizzati.payment,
          beneficiario: data.studioProfile.nome_denominazione || current.dati_personalizzati.payment.beneficiario,
          istituto_finanziario: data.studioProfile.istituto_finanziario || current.dati_personalizzati.payment.istituto_finanziario,
          iban: data.studioProfile.iban || current.dati_personalizzati.payment.iban,
        },
      },
    }))
  }

  function onMatterChange(matterId: string) {
    const incoming = data.matterProfiles[matterId]
    setFormState((current) => ({
      ...current,
      id_fascicolo: matterId,
      dati_personalizzati: {
        ...current.dati_personalizzati,
        document: {
          ...current.dati_personalizzati.document,
          fascicolo_label: incoming?.titolo || '',
          causale_oggetto: current.dati_personalizzati.document.causale_oggetto || incoming?.titolo || current.note,
        },
      },
    }))
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canSave) {
      setSaveStatus('permission')
      setErrors({ permission: 'Permesso di scrittura mancante.' })
      return
    }
    setSaveStatus('saving')
    setErrors({})
    setResult(null)
    const response = await createFattura(buildPayload(formState))
    setResult(response)
    setErrors(response.errors || {})
    if (response.ok) {
      setSaveStatus('success')
    } else if (response.status === 403 || response.errors?.permission) {
      setSaveStatus('permission')
    } else if (response.status && response.status >= 500) {
      setSaveStatus('server')
    } else {
      setSaveStatus('validation')
    }
  }

  if (noClients) {
    return (
      <Panel title="Nuova parcella" subtitle="La creazione richiede almeno un cliente reale.">
        <EmptyState
          title="Nessun cliente disponibile"
          message="Inserisci o sincronizza un cliente prima di creare una parcella."
          action={<ButtonLink href="/clienti" tone="primary">Apri clienti</ButtonLink>}
        />
        <TechnicalRollback />
      </Panel>
    )
  }

  return (
    <Panel title="Nuova parcella personalizzata" subtitle="Precompilazione da studio, cliente, fascicolo e impostazioni disponibili.">
      <form className="iu-fatt-operational" onSubmit={onSubmit}>
        <StatusMessage status={saveStatus} result={result} errors={errors} />
        <section className="iu-fatt-rich-card">
          <div className="iu-fatt-section-head">
            <div>
              <span className="iu-fatt-kicker">Anagrafica e pratica</span>
              <h3>Collega i dati reali del gestionale</h3>
            </div>
            <Badge tone="primary">Archivio reale</Badge>
          </div>
          <div className="iu-fatt-form-grid">
            <label className="iu-fatt-field">
              <span>Cliente</span>
              <select
                required
                value={formState.id_cliente}
                onChange={(event) => applyClientToRecipient(event.currentTarget.value)}
              >
                <option value="">Seleziona cliente</option>
                {data.clients.map((option) => (
                  <option value={option.value} key={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="iu-fatt-field">
              <span>Pratica</span>
              <select
                value={formState.id_fascicolo}
                onChange={(event) => onMatterChange(event.currentTarget.value)}
              >
                <option value="">Nessuna pratica</option>
                {filteredMatters.map((matter: FatturazioneMatter) => (
                  <option value={matter.value} key={matter.value}>
                    {matter.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="iu-fatt-field">
              <span>Data documento</span>
              <input
                type="date"
                required
                value={formState.data_emissione}
                onChange={(event) => {
                  const value = event.currentTarget.value
                  setFormState((current) => ({
                    ...current,
                    data_emissione: value,
                    dati_personalizzati: {
                      ...current.dati_personalizzati,
                      document: {
                        ...current.dati_personalizzati.document,
                        data_documento: value,
                      },
                    },
                  }))
                }}
              />
            </label>
            <label className="iu-fatt-field">
              <span>Scadenza pagamento</span>
              <input
                type="date"
                required
                value={formState.data_scadenza}
                onChange={(event) => {
                  const value = event.currentTarget.value
                  setFormState((current) => ({
                    ...current,
                    data_scadenza: value,
                    dati_personalizzati: {
                      ...current.dati_personalizzati,
                      payment: {
                        ...current.dati_personalizzati.payment,
                        data_decorrenza: value,
                      },
                    },
                  }))
                }}
              />
            </label>
          </div>
          <div className="iu-fatt-inline-summary">
            <div>
              <strong>{clientProfile?.nome_denominazione || 'Cliente da selezionare'}</strong>
              <span>{clientProfile?.codice_fiscale || clientProfile?.partita_iva || 'Identificativo fiscale non disponibile'}</span>
            </div>
            <div>
              <strong>{matterProfile?.titolo || 'Nessuna pratica collegata'}</strong>
              <span>{matterProfile?.numero_rg ? `RG ${matterProfile.numero_rg}` : 'Puoi creare la parcella anche senza pratica'}</span>
            </div>
          </div>
        </section>

        <section className="iu-fatt-rich-card">
          <div className="iu-fatt-section-head">
            <div>
              <span className="iu-fatt-kicker">Trasmissione</span>
              <h3>Dati generali relativi alla trasmissione</h3>
            </div>
            <Button type="button" tone="neutral" onClick={applyStudioDefaults}>
              <Sparkles size={16} />
              Usa dati studio
            </Button>
          </div>
          <div className="iu-fatt-form-grid">
            <label className="iu-fatt-field">
              <span>Identificativo fiscale del trasmittente</span>
              <input
                value={formState.dati_personalizzati.transmission.identificativo_fiscale}
                onChange={(event) => updatePersonalized('transmission', { identificativo_fiscale: event.currentTarget.value })}
                placeholder="Codice fiscale del trasmittente"
              />
            </label>
            <label className="iu-fatt-field">
              <span>Codice di invio</span>
              <input
                value={formState.dati_personalizzati.transmission.codice_invio}
                onChange={(event) => updatePersonalized('transmission', { codice_invio: event.currentTarget.value.toUpperCase() })}
                placeholder={data.nextNumber || '26001'}
              />
            </label>
            <label className="iu-fatt-field">
              <span>Telefono trasmittente</span>
              <input
                value={formState.dati_personalizzati.transmission.telefono}
                onChange={(event) => updatePersonalized('transmission', { telefono: event.currentTarget.value })}
                placeholder="Recapito telefonico"
              />
            </label>
            <label className="iu-fatt-field">
              <span>Email trasmittente</span>
              <input
                type="email"
                value={formState.dati_personalizzati.transmission.email}
                onChange={(event) => updatePersonalized('transmission', { email: event.currentTarget.value })}
                placeholder="Email non PEC"
              />
            </label>
          </div>
        </section>

        <section className="iu-fatt-rich-card">
          <div className="iu-fatt-section-head">
            <div>
              <span className="iu-fatt-kicker">Studio</span>
              <h3>Dati dello studio</h3>
            </div>
            <Badge tone="success">Precompilati</Badge>
          </div>
          <div className="iu-fatt-form-grid">
            <label className="iu-fatt-field">
              <span>Nome o denominazione</span>
              <input
                value={formState.dati_personalizzati.studio.nome_denominazione}
                onChange={(event) => updatePersonalized('studio', { nome_denominazione: event.currentTarget.value })}
              />
            </label>
            <label className="iu-fatt-field">
              <span>Cognome</span>
              <input
                value={formState.dati_personalizzati.studio.cognome}
                onChange={(event) => updatePersonalized('studio', { cognome: event.currentTarget.value })}
                placeholder="Lascia vuoto per studio associato"
              />
            </label>
            <label className="iu-fatt-field">
              <span>Indirizzo</span>
              <input
                value={formState.dati_personalizzati.studio.indirizzo}
                onChange={(event) => updatePersonalized('studio', { indirizzo: event.currentTarget.value, indirizzo_completo: event.currentTarget.value })}
              />
            </label>
            <label className="iu-fatt-field">
              <span>CAP</span>
              <input value={formState.dati_personalizzati.studio.cap} onChange={(event) => updatePersonalized('studio', { cap: event.currentTarget.value })} />
            </label>
            <label className="iu-fatt-field">
              <span>Citta</span>
              <input value={formState.dati_personalizzati.studio.citta} onChange={(event) => updatePersonalized('studio', { citta: event.currentTarget.value })} />
            </label>
            <label className="iu-fatt-field">
              <span>Provincia</span>
              <input value={formState.dati_personalizzati.studio.provincia} onChange={(event) => updatePersonalized('studio', { provincia: event.currentTarget.value.toUpperCase() })} />
            </label>
            <label className="iu-fatt-field">
              <span>Partita IVA</span>
              <input value={formState.dati_personalizzati.studio.partita_iva} onChange={(event) => updatePersonalized('studio', { partita_iva: event.currentTarget.value })} />
            </label>
            <label className="iu-fatt-field">
              <span>Codice fiscale</span>
              <input value={formState.dati_personalizzati.studio.codice_fiscale} onChange={(event) => updatePersonalized('studio', { codice_fiscale: event.currentTarget.value })} />
            </label>
          </div>
        </section>

        <section className="iu-fatt-rich-card">
          <div className="iu-fatt-section-head">
            <div>
              <span className="iu-fatt-kicker">Destinatario</span>
              <h3>Dati del destinatario</h3>
            </div>
            <Button type="button" tone="neutral" disabled={!formState.id_cliente} onClick={() => applyClientToRecipient(formState.id_cliente)}>
              <Mail size={16} />
              Ricarica anagrafica cliente
            </Button>
          </div>
          <div className="iu-fatt-form-grid">
            <label className="iu-fatt-field">
              <span>Partita IVA</span>
              <input value={formState.dati_personalizzati.recipient.partita_iva} onChange={(event) => updatePersonalized('recipient', { partita_iva: event.currentTarget.value })} />
            </label>
            <label className="iu-fatt-field">
              <span>Codice fiscale</span>
              <input value={formState.dati_personalizzati.recipient.codice_fiscale} onChange={(event) => updatePersonalized('recipient', { codice_fiscale: event.currentTarget.value })} />
            </label>
            <label className="iu-fatt-field">
              <span>Nome o denominazione</span>
              <input value={formState.dati_personalizzati.recipient.nome_denominazione} onChange={(event) => updatePersonalized('recipient', { nome_denominazione: event.currentTarget.value, denominazione: event.currentTarget.value })} />
            </label>
            <label className="iu-fatt-field">
              <span>Cognome</span>
              <input value={formState.dati_personalizzati.recipient.cognome} onChange={(event) => updatePersonalized('recipient', { cognome: event.currentTarget.value })} placeholder="Solo se persona fisica" />
            </label>
            <label className="iu-fatt-field">
              <span>Indirizzo</span>
              <input value={formState.dati_personalizzati.recipient.indirizzo} onChange={(event) => updatePersonalized('recipient', { indirizzo: event.currentTarget.value, indirizzo_completo: event.currentTarget.value })} />
            </label>
            <label className="iu-fatt-field">
              <span>CAP</span>
              <input value={formState.dati_personalizzati.recipient.cap} onChange={(event) => updatePersonalized('recipient', { cap: event.currentTarget.value })} />
            </label>
            <label className="iu-fatt-field">
              <span>Citta</span>
              <input value={formState.dati_personalizzati.recipient.citta} onChange={(event) => updatePersonalized('recipient', { citta: event.currentTarget.value })} />
            </label>
            <label className="iu-fatt-field">
              <span>Provincia</span>
              <input value={formState.dati_personalizzati.recipient.provincia} onChange={(event) => updatePersonalized('recipient', { provincia: event.currentTarget.value.toUpperCase() })} />
            </label>
            <label className="iu-fatt-field">
              <span>Nazione</span>
              <input value={formState.dati_personalizzati.recipient.nazione} onChange={(event) => updatePersonalized('recipient', { nazione: event.currentTarget.value.toUpperCase() })} placeholder="IT" />
            </label>
            <label className="iu-fatt-field">
              <span>PEC del destinatario</span>
              <input type="email" value={formState.dati_personalizzati.recipient.pec || ''} onChange={(event) => updatePersonalized('recipient', { pec: event.currentTarget.value })} />
            </label>
            <label className="iu-fatt-field">
              <span>Codice univoco del destinatario</span>
              <input value={formState.dati_personalizzati.recipient.codice_destinatario || ''} onChange={(event) => updatePersonalized('recipient', { codice_destinatario: event.currentTarget.value.toUpperCase() })} placeholder="0000000" />
            </label>
          </div>
        </section>

        <section className="iu-fatt-rich-card">
          <div className="iu-fatt-section-head">
            <div>
              <span className="iu-fatt-kicker">Documento</span>
              <h3>Corpo del documento</h3>
            </div>
            <Badge tone="warning">Numero assegnato al salvataggio</Badge>
          </div>
          <div className="iu-fatt-form-grid">
            <label className="iu-fatt-field">
              <span>Tipo documento</span>
              <select value={formState.dati_personalizzati.document.tipo_documento} onChange={(event) => updatePersonalized('document', { tipo_documento: event.currentTarget.value })}>
                <option value="TD01">Fattura</option>
                <option value="TD04">Nota di credito</option>
              </select>
            </label>
            <label className="iu-fatt-field">
              <span>Numero documento</span>
              <input value={formState.dati_personalizzati.document.numero_documento || data.nextNumber} readOnly />
            </label>
            <label className="iu-fatt-field iu-fatt-field--wide">
              <span>Causale o oggetto</span>
              <textarea
                rows={3}
                value={formState.dati_personalizzati.document.causale_oggetto}
                onChange={(event) => {
                  const value = event.currentTarget.value
                  setFormState((current) => ({
                    ...current,
                    note: value,
                    dati_personalizzati: {
                      ...current.dati_personalizzati,
                      document: {
                        ...current.dati_personalizzati.document,
                        causale_oggetto: value,
                      },
                    },
                  }))
                }}
                placeholder="Riferimento pratica, fascicolo, parti o oggetto"
              />
            </label>
            <label className="iu-fatt-field">
              <span>Regime fiscale</span>
              <select
                value={formState.dati_personalizzati.document.regime_fiscale}
                onChange={(event) => {
                  const regime = event.currentTarget.value
                  const locked = isVatExcludedRegime(regime)
                  setFormState((current) => ({
                    ...current,
                    opzioni_fiscali: {
                      ...current.opzioni_fiscali,
                      applica_iva: locked ? false : current.opzioni_fiscali.applica_iva,
                    },
                    dati_personalizzati: {
                      ...current.dati_personalizzati,
                      document: {
                        ...current.dati_personalizzati.document,
                        regime_fiscale: regime,
                        regime_fiscale_label: regimeLabel(regime),
                      },
                    },
                  }))
                }}
              >
                <option value="RF01">Regime ordinario</option>
                <option value="RF19">Regime forfettario</option>
                <option value="RF02">Regime minimo</option>
              </select>
            </label>
            <label className="iu-fatt-field">
              <span>Esigibilita IVA</span>
              <select value={formState.dati_personalizzati.document.esigibilita_iva} onChange={(event) => updatePersonalized('document', { esigibilita_iva: event.currentTarget.value })}>
                <option value="I">Immediata</option>
                <option value="D">Differita</option>
                <option value="S">Scissione pagamenti</option>
              </select>
            </label>
            <label className="iu-fatt-field">
              <span>Cassa previdenziale</span>
              <select value={formState.dati_personalizzati.document.cassa_previdenziale} onChange={(event) => updatePersonalized('document', { cassa_previdenziale: event.currentTarget.value })}>
                <option value="TC01">Avvocati</option>
                <option value="ALTRO">Altra cassa</option>
              </select>
            </label>
            <label className="iu-fatt-field">
              <span>Spese generali %</span>
              <input
                type="number"
                min="0"
                max="100"
                step="0.01"
                value={formState.percentuale_spese_generali}
                onChange={(event) => {
                  const value = event.currentTarget.value
                  setFormState((current) => ({
                    ...current,
                    percentuale_spese_generali: value,
                    dati_personalizzati: {
                      ...current.dati_personalizzati,
                      document: {
                        ...current.dati_personalizzati.document,
                        percentuale_spese_generali: value,
                      },
                    },
                  }))
                }}
              />
            </label>
          </div>
        </section>

        <VoiceEditor
          rows={formState.voci}
          onChange={(voci) => setFormState((current) => ({ ...current, voci }))}
        />

        <section className="iu-fatt-rich-card">
          <div className="iu-fatt-section-head">
            <div>
              <span className="iu-fatt-kicker">Fiscalita e pagamento</span>
              <h3>Dati integrativi e pagamento</h3>
            </div>
            <Badge tone="success">Calcolo guidato</Badge>
          </div>
          <FiscalOptions
            values={formState.opzioni_fiscali}
            disableIva={ivaLocked}
            onChange={(opzioni_fiscali) => setFormState((current) => ({ ...current, opzioni_fiscali }))}
          />
          {ivaLocked ? (
            <div className="iu-fatt-form-note" aria-label="Regime senza IVA">
              <strong>IVA esclusa dal calcolo</strong>
              <span>{regimeLabel(formState.dati_personalizzati.document.regime_fiscale)}: l&apos;imposta non viene applicata nella parcella.</span>
            </div>
          ) : null}
          <div className="iu-fatt-form-grid">
            <label className="iu-fatt-field">
              <span>Modalita di pagamento</span>
              <select
                value={formState.dati_personalizzati.payment.modalita_pagamento_label}
                onChange={(event) => {
                  const label = event.currentTarget.value
                  const codeMap: Record<string, string> = {
                    Bonifico: 'MP05',
                    Contanti: 'MP01',
                    Assegno: 'MP02',
                    PayPal: 'MP12',
                    'Carta di credito': 'MP08',
                    Altro: 'MP05',
                  }
                  setFormState((current) => ({
                    ...current,
                    metodo_pagamento: label,
                    dati_personalizzati: {
                      ...current.dati_personalizzati,
                      payment: {
                        ...current.dati_personalizzati.payment,
                        modalita_pagamento_label: label,
                        modalita_pagamento_codice: codeMap[label] || 'MP05',
                      },
                    },
                  }))
                }}
              >
                <option value="Bonifico">Bonifico</option>
                <option value="Contanti">Contanti</option>
                <option value="Assegno">Assegno</option>
                <option value="Carta di credito">Carta di credito</option>
                <option value="PayPal">PayPal</option>
                <option value="Altro">Altro</option>
              </select>
            </label>
            <label className="iu-fatt-field">
              <span>Beneficiario</span>
              <input value={formState.dati_personalizzati.payment.beneficiario} onChange={(event) => updatePersonalized('payment', { beneficiario: event.currentTarget.value })} />
            </label>
            <label className="iu-fatt-field">
              <span>Istituto finanziario</span>
              <input value={formState.dati_personalizzati.payment.istituto_finanziario} onChange={(event) => updatePersonalized('payment', { istituto_finanziario: event.currentTarget.value })} />
            </label>
            <label className="iu-fatt-field">
              <span>IBAN</span>
              <input value={formState.dati_personalizzati.payment.iban} onChange={(event) => updatePersonalized('payment', { iban: event.currentTarget.value })} />
            </label>
            <label className="iu-fatt-field">
              <span>BIC o SWIFT</span>
              <input value={formState.dati_personalizzati.payment.bic_swift} onChange={(event) => updatePersonalized('payment', { bic_swift: event.currentTarget.value })} />
            </label>
            <label className="iu-fatt-field">
              <span>Giorni termini di pagamento</span>
              <input value={formState.dati_personalizzati.payment.giorni_termini} onChange={(event) => updatePersonalized('payment', { giorni_termini: event.currentTarget.value })} />
            </label>
            <label className="iu-fatt-field">
              <span>Importo pagamento personalizzato</span>
              <input value={formState.dati_personalizzati.payment.importo_pagamento} onChange={(event) => updatePersonalized('payment', { importo_pagamento: event.currentTarget.value })} placeholder="Lascia vuoto per il totale" />
            </label>
          </div>
        </section>

        <section className="iu-fatt-preview-card">
          <div className="iu-fatt-section-head">
            <div>
              <span className="iu-fatt-kicker">Anteprima</span>
              <h3>Riepilogo economico della parcella</h3>
            </div>
            <Badge tone="warning">Conferma finale al salvataggio</Badge>
          </div>
          <div className="iu-fatt-preview-grid">
            <div><span>Totale competenze</span><strong>{currency(preview.competenze)}</strong></div>
            <div><span>Spese imponibili</span><strong>{currency(preview.speseImponibili)}</strong></div>
            <div><span>Anticipazioni</span><strong>{currency(preview.anticipazioni)}</strong></div>
            <div><span>Spese generali</span><strong>{currency(preview.speseGenerali)}</strong></div>
            <div><span>CPA 4%</span><strong>{currency(preview.cassa)}</strong></div>
            <div><span>IVA 22%</span><strong>{currency(preview.iva)}</strong></div>
            <div><span>Ritenuta 20%</span><strong>{currency(preview.ritenuta)}</strong></div>
            <div><span>Totale documento</span><strong>{currency(preview.totaleDocumento)}</strong></div>
          </div>
          <div className="iu-fatt-preview-total">
            <span>Totale generale</span>
            <strong>{currency(preview.totale)}</strong>
          </div>
        </section>

        <section className="iu-fatt-form-note" aria-label="Calcolo definitivo">
          <strong>Calcolo definitivo governato</strong>
          <span>La pagina prepara i dati della parcella; numerazione, imposte e importi finali vengono verificati prima del salvataggio definitivo.</span>
        </section>

        <div className="iu-fatt-action-row">
          <Button type="submit" tone="primary" disabled={saveStatus === 'saving' || !canSave}>
            {saveStatus === 'saving' ? <ReceiptText size={16} /> : <Save size={16} />}
            {saveStatus === 'saving' ? 'Salvataggio in corso' : form?.submitLabel || 'Crea parcella'}
          </Button>
          <ButtonLink href="/fatturazione" tone="neutral">
            <ReceiptText size={16} />
            Archivio
          </ButtonLink>
        </div>

        {saveStatus === 'success' ? (
          <div className="iu-fatt-success-actions">
            <ButtonLink href="/fatturazione" tone="primary">
              <ReceiptText size={16} />
              Torna all'archivio
            </ButtonLink>
            {result?.redirect_href ? (
              <ButtonLink href={result.redirect_href} tone="neutral">
                <ExternalLink size={16} />
                Apri dettaglio
              </ButtonLink>
            ) : null}
          </div>
        ) : null}
      </form>
      <TechnicalRollback href="/fatturazione/nuova?_legacy=1" />
    </Panel>
  )
}

function localSignerBase(endpoint: string) {
  return endpoint || 'http://127.0.0.1:27272'
}

async function postLocalJson(endpoint: string, payload: Record<string, unknown>, timeoutMs = 45000): Promise<Record<string, unknown> | null> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(localSignerBase(endpoint), {
      method: 'POST',
      signal: controller.signal,
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    return await response.json() as Record<string, unknown>
  } catch {
    return null
  } finally {
    window.clearTimeout(timer)
  }
}

function workflowText(value: unknown) {
  if (value === undefined || value === null) return ''
  if (typeof value === 'object') return ''
  return String(value).trim()
}

function editableVoices(detail: FatturazioneDetail | null): EditableVoice[] {
  const rows = detail?.voci || []
  if (!rows.length) {
    return [{ rowId: `voce-${Date.now()}`, descrizione: '', quantita: '1', prezzo_unitario: '', tipo: 'ONORARIO' }]
  }
  return rows.map((voice, index) => ({
    rowId: `${detail?.id || 'voce'}-${index}-${voice.descrizione}`,
    descrizione: voice.descrizione,
    quantita: voice.quantita || '1',
    prezzo_unitario: currencyInputValue(voice.prezzoUnitario),
    tipo: voice.tipo || 'ONORARIO',
  }))
}

function DraftEditor({
  draft,
  onChange,
}: {
  draft: FatturazioneDraft
  onChange: (draft: FatturazioneDraft) => void
}) {
  return (
    <div className="iu-fatt-draft">
      <label>
        <span>Destinatario</span>
        <input value={draft.to} onChange={(event) => onChange({ ...draft, to: event.currentTarget.value })} />
      </label>
      <label>
        <span>Oggetto</span>
        <input value={draft.subject} onChange={(event) => onChange({ ...draft, subject: event.currentTarget.value })} />
      </label>
      <label className="iu-fatt-draft__body">
        <span>Corpo email</span>
        <textarea value={draft.body} onChange={(event) => onChange({ ...draft, body: event.currentTarget.value })} rows={7} />
      </label>
      <div className="iu-fatt-draft__attachments">
        <strong>Allegati</strong>
        {draft.attachments.length ? draft.attachments.map((attachment) => (
          <span key={attachment.filename}>{attachment.filename}</span>
        )) : <span>Nessun allegato predisposto.</span>}
      </div>
    </div>
  )
}

function ArchiveDetailPanel({
  detail,
  loading,
  onClose,
  onReloadPage,
  onReloadDetail,
  initialTab,
}: {
  detail: FatturazioneDetail | null
  loading: boolean
  onClose: () => void
  onReloadPage: () => Promise<void>
  onReloadDetail: () => Promise<void>
  initialTab: DetailTab
}) {
  const [activeTab, setActiveTab] = useState<DetailTab>('dettaglio')
  const [voices, setVoices] = useState<EditableVoice[]>([])
  const [note, setNote] = useState('')
  const [notice, setNotice] = useState<ActionNotice>(null)
  const [busy, setBusy] = useState('')
  const [pdfFullscreen, setPdfFullscreen] = useState(false)
  const [pin, setPin] = useState('')
  const [pecPassword, setPecPassword] = useState('')
  const [sdiDraft, setSdiDraft] = useState<FatturazioneDraft | null>(null)
  const [sdiLocalPec, setSdiLocalPec] = useState<FatturazioneWorkflowResult['localPec']>(undefined)
  const [outcomeState, setOutcomeState] = useState('CONSEGNATA')
  const [outcomeId, setOutcomeId] = useState('')
  const [outcomeReceipt, setOutcomeReceipt] = useState('')
  const [outcomeNote, setOutcomeNote] = useState('')
  const [commercialistaChannel, setCommercialistaChannel] = useState('ordinaria')
  const [commercialistaAttachments, setCommercialistaAttachments] = useState('pdf')
  const [commercialistaDraft, setCommercialistaDraft] = useState<FatturazioneDraft | null>(null)
  const [commercialistaLocalPec, setCommercialistaLocalPec] = useState<FatturazioneWorkflowResult['localPec']>(undefined)
  const [commercialistaPassword, setCommercialistaPassword] = useState('')
  const [quickSdiPecOpen, setQuickSdiPecOpen] = useState(false)
  const [quickSdiPecLoaded, setQuickSdiPecLoaded] = useState(false)
  const [quickSdiPec, setQuickSdiPec] = useState<QuickSdiPecSettings>(defaultQuickSdiPecSettings)
  const [quickCommercialistaOpen, setQuickCommercialistaOpen] = useState(false)
  const [quickCommercialistaLoaded, setQuickCommercialistaLoaded] = useState(false)
  const [quickCommercialista, setQuickCommercialista] = useState<QuickCommercialistaSettings>(defaultQuickCommercialistaSettings)

  useEffect(() => {
    setVoices(editableVoices(detail))
    setNote(detail?.note || '')
    setNotice(null)
    setSdiDraft(null)
    setSdiLocalPec(undefined)
    setCommercialistaDraft(null)
    setCommercialistaLocalPec(undefined)
    setActiveTab(initialTab)
    setQuickSdiPecOpen(false)
    setQuickSdiPecLoaded(false)
    setQuickSdiPec({ ...defaultQuickSdiPecSettings, pec_notifiche: detail?.workflow.sdiPecAddress || '' })
    setQuickCommercialistaOpen(false)
    setQuickCommercialistaLoaded(false)
    setQuickCommercialista({
      nome_commercialista: detail?.workflow.commercialistaName || '',
      email_commercialista: detail?.workflow.commercialistaEmail || '',
      pec_commercialista: detail?.workflow.commercialistaPec || '',
    })
  }, [detail?.id, initialTab])

  if (loading) {
    return (
      <div className="iu-fatt-overlay" role="dialog" aria-modal="true" aria-label="Dettaglio fatturazione">
        <section className="iu-fatt-modal">
          <LoadingState title="Caricamento dettaglio" message="Apro la finestra operativa della fattura." />
        </section>
      </div>
    )
  }
  if (!detail) return null
  const currentDetail = detail

  async function afterMutation(result: { ok: boolean; message: string }) {
    setNotice({ tone: result.ok ? 'success' : 'warning', text: result.message })
    if (result.ok) {
      await onReloadPage()
      await onReloadDetail()
    }
  }

  async function saveDetail() {
    setBusy('detail')
    const payload: FatturazioneDetailUpdatePayload = {
      note,
      voci: voices.map((voice) => ({
        descrizione: voice.descrizione,
        quantita: voice.quantita,
        prezzo_unitario: machineAmountValue(voice.prezzo_unitario),
        tipo: voice.tipo,
      })),
    }
    await afterMutation(await updateFatturazioneDetail(currentDetail.id, payload))
    setBusy('')
  }

  function updateVoice(rowId: string, patch: Partial<EditableVoice>) {
    setVoices((current) => current.map((voice) => voice.rowId === rowId ? { ...voice, ...patch } : voice))
  }

  function addVoice() {
    setVoices((current) => [...current, { rowId: `voce-${Date.now()}`, descrizione: '', quantita: '1', prezzo_unitario: '', tipo: 'ONORARIO' }])
  }

  function removeVoice(rowId: string) {
    setVoices((current) => current.length > 1 ? current.filter((voice) => voice.rowId !== rowId) : current)
  }

  async function signXml() {
    if (!pin.trim()) {
      setNotice({ tone: 'warning', text: "Inserisci il PIN del dispositivo di firma per firmare l'XML." })
      return
    }
    setBusy('sign')
    const prepared = await prepareFatturazioneXmlSignature(currentDetail.id)
    if (!prepared.ok || !prepared.document) {
      setNotice({ tone: 'warning', text: prepared.message })
      setBusy('')
      return
    }
    const endpoint = workflowText(prepared.localSigner?.endpoint) || 'http://127.0.0.1:27272/firma'
    const signed = await postLocalJson(endpoint, {
      documento: prepared.document.contentBase64,
      pin,
      visible_signature_mode: 'nessuna',
      visible_signature_datetime_mode: 'nessuna',
    })
    if (!signed?.ok || !workflowText(signed.firmato_b64)) {
      setNotice({ tone: 'warning', text: workflowText(signed?.errore || signed?.message) || 'Firma XML non completata dal Local Signer.' })
      setBusy('')
      return
    }
    const confirmed = await confirmFatturazioneXmlSigned(currentDetail.id, {
      signed_base64: workflowText(signed.firmato_b64),
      fileName: prepared.document.fileName,
      intestatario: workflowText(signed.intestatario),
      scadenza: workflowText(signed.scadenza),
    })
    await afterMutation(confirmed)
    setBusy('')
  }

  async function prepareSdiPec() {
    setBusy('sdi-prepare')
    const result = await prepareFatturazioneSdiPec(currentDetail.id)
    if (result.ok && result.draft) {
      setSdiDraft(result.draft)
      setSdiLocalPec(result.localPec)
    }
    setNotice({ tone: result.ok ? 'success' : 'warning', text: result.message })
    setBusy('')
    if (!result.ok && result.errors.pec_notifiche) {
      void openQuickSdiPecSettings()
    }
  }

  async function sendSdiPec() {
    if (!sdiDraft || !sdiLocalPec) {
      setNotice({ tone: 'warning', text: 'Prepara prima la PEC SdI.' })
      return
    }
    if (!pecPassword.trim()) {
      setNotice({ tone: 'warning', text: 'Inserisci la password PEC: viene inviata solo al Local Signer locale.' })
      return
    }
    setBusy('sdi-send')
    const localPayload = {
      ...sdiLocalPec.payload,
      password: pecPassword,
      to: sdiDraft.to,
      subject: sdiDraft.subject,
      body: sdiDraft.body,
    }
    const sent = await postLocalJson(sdiLocalPec.endpoint, localPayload, 65000)
    if (!sent?.ok || !workflowText(sent.message_id)) {
      setNotice({ tone: 'warning', text: workflowText(sent?.messaggio || sent?.message) || 'Invio PEC SdI non completato dal Local Signer.' })
      setBusy('')
      return
    }
    const confirmed = await confirmFatturazioneSdiPecSent(currentDetail.id, {
      message_id: workflowText(sent.message_id),
      destinatario: sdiDraft.to,
      oggetto: sdiDraft.subject,
    })
    await afterMutation(confirmed)
    setBusy('')
  }

  async function saveOutcome() {
    setBusy('outcome')
    const result = await recordFatturazioneSdiOutcome(currentDetail.id, {
      sdi_stato: outcomeState,
      sdi_identificativo: outcomeId,
      sdi_ricevuta: outcomeReceipt,
      sdi_note: outcomeNote,
    })
    await afterMutation(result)
    setBusy('')
  }

  async function openQuickSdiPecSettings() {
    setQuickSdiPecOpen(true)
    if (quickSdiPecLoaded) return
    setBusy('quick-sdi-load')
    const settings = await getSettings()
    if (!settings.ok) {
      setNotice({ tone: 'warning', text: settings.warnings[0]?.message || 'Impostazioni non disponibili.' })
      setBusy('')
      return
    }
    const sdi = settingsPlainRecord(settings.sdi as Record<string, unknown>)
    const pec = settingsPlainRecord(settings.pec as Record<string, unknown>)
    setQuickSdiPec({
      pec_notifiche: settingsTextValue(sdi.pec_notifiche, currentDetail.workflow.sdiPecAddress),
      pec_indirizzo: settingsTextValue(pec.indirizzo),
      pec_username: settingsTextValue(pec.username),
      pec_smtp_host: settingsTextValue(pec.smtp_host, defaultQuickSdiPecSettings.pec_smtp_host),
      pec_smtp_port: settingsTextValue(pec.smtp_port, defaultQuickSdiPecSettings.pec_smtp_port),
      pec_imap_host: settingsTextValue(pec.imap_host, defaultQuickSdiPecSettings.pec_imap_host),
      pec_imap_port: settingsTextValue(pec.imap_port, defaultQuickSdiPecSettings.pec_imap_port),
      pec_use_ssl: settingsBoolValue(pec.use_ssl, defaultQuickSdiPecSettings.pec_use_ssl),
    })
    setQuickSdiPecLoaded(true)
    setBusy('')
  }

  function updateQuickSdiPec(patch: Partial<QuickSdiPecSettings>) {
    setQuickSdiPec((current) => ({ ...current, ...patch }))
  }

  async function saveQuickSdiPecSettings() {
    const sdiDestination = quickSdiPec.pec_notifiche.trim()
    if (!sdiDestination) {
      setNotice({ tone: 'warning', text: 'Inserisci la PEC per notifiche SdI prima di proseguire.' })
      return
    }
    setBusy('quick-sdi-save')
    const settings = await getSettings()
    if (!settings.ok) {
      setNotice({ tone: 'warning', text: settings.warnings[0]?.message || 'Impostazioni non disponibili.' })
      setBusy('')
      return
    }
    const sdi = settingsPlainRecord(settings.sdi as Record<string, unknown>)
    const pec = settingsPlainRecord(settings.pec as Record<string, unknown>)
    const sdiResult = await saveSettingsSection('sdi', {
      ...sdi,
      abilitato: true,
      pec_notifiche: sdiDestination,
    })
    if (!sdiResult.ok) {
      setNotice({ tone: 'warning', text: sdiResult.message || 'PEC SdI non salvata.' })
      setBusy('')
      return
    }
    const shouldSavePec = Boolean(
      quickSdiPec.pec_indirizzo.trim()
      || quickSdiPec.pec_username.trim()
      || quickSdiPec.pec_smtp_host.trim()
      || quickSdiPec.pec_imap_host.trim(),
    )
    if (shouldSavePec) {
      const pecResult = await saveSettingsSection('pec', {
        ...pec,
        indirizzo: quickSdiPec.pec_indirizzo.trim(),
        username: quickSdiPec.pec_username.trim() || quickSdiPec.pec_indirizzo.trim(),
        smtp_host: quickSdiPec.pec_smtp_host.trim() || defaultQuickSdiPecSettings.pec_smtp_host,
        smtp_port: quickSdiPec.pec_smtp_port.trim() || defaultQuickSdiPecSettings.pec_smtp_port,
        imap_host: quickSdiPec.pec_imap_host.trim() || defaultQuickSdiPecSettings.pec_imap_host,
        imap_port: quickSdiPec.pec_imap_port.trim() || defaultQuickSdiPecSettings.pec_imap_port,
        use_ssl: quickSdiPec.pec_use_ssl,
      })
      if (!pecResult.ok) {
        setNotice({ tone: 'warning', text: pecResult.message || 'Parametri PEC studio non salvati.' })
        setBusy('')
        return
      }
    }
    setNotice({ tone: 'success', text: 'PEC SdI salvata. Puoi preparare la PEC senza uscire dal pannello.' })
    setQuickSdiPecOpen(false)
    setQuickSdiPecLoaded(false)
    await onReloadPage()
    await onReloadDetail()
    setBusy('')
  }

  async function openQuickCommercialistaSettings() {
    setQuickCommercialistaOpen(true)
    if (quickCommercialistaLoaded) return
    setBusy('quick-commercialista-load')
    const settings = await getSettings()
    if (!settings.ok) {
      setNotice({ tone: 'warning', text: settings.warnings[0]?.message || 'Impostazioni non disponibili.' })
      setBusy('')
      return
    }
    const sdi = settingsPlainRecord(settings.sdi as Record<string, unknown>)
    setQuickCommercialista({
      nome_commercialista: settingsTextValue(sdi.nome_commercialista, currentDetail.workflow.commercialistaName),
      email_commercialista: settingsTextValue(sdi.email_commercialista, currentDetail.workflow.commercialistaEmail),
      pec_commercialista: settingsTextValue(sdi.pec_commercialista, currentDetail.workflow.commercialistaPec),
    })
    setQuickCommercialistaLoaded(true)
    setBusy('')
  }

  function updateQuickCommercialista(patch: Partial<QuickCommercialistaSettings>) {
    setQuickCommercialista((current) => ({ ...current, ...patch }))
  }

  async function saveQuickCommercialistaSettings() {
    const email = quickCommercialista.email_commercialista.trim()
    const pec = quickCommercialista.pec_commercialista.trim()
    if (commercialistaChannel === 'ordinaria' && !email) {
      setNotice({ tone: 'warning', text: "Inserisci l'email ordinaria del commercialista prima di preparare la bozza." })
      return
    }
    if (commercialistaChannel === 'pec' && !pec) {
      setNotice({ tone: 'warning', text: 'Inserisci la PEC del commercialista prima di preparare la bozza PEC.' })
      return
    }
    if (!email && !pec) {
      setNotice({ tone: 'warning', text: 'Inserisci almeno un indirizzo del commercialista.' })
      return
    }
    setBusy('quick-commercialista-save')
    const settings = await getSettings()
    if (!settings.ok) {
      setNotice({ tone: 'warning', text: settings.warnings[0]?.message || 'Impostazioni non disponibili.' })
      setBusy('')
      return
    }
    const sdi = settingsPlainRecord(settings.sdi as Record<string, unknown>)
    const sdiResult = await saveSettingsSection('sdi', {
      ...sdi,
      email_commercialista: email,
      pec_commercialista: pec,
      nome_commercialista: quickCommercialista.nome_commercialista.trim(),
    })
    if (!sdiResult.ok) {
      setNotice({ tone: 'warning', text: sdiResult.message || 'Commercialista non salvato.' })
      setBusy('')
      return
    }
    setNotice({ tone: 'success', text: 'Commercialista salvato. Puoi preparare la bozza dallo stesso pannello.' })
    setQuickCommercialistaOpen(false)
    setQuickCommercialistaLoaded(false)
    await onReloadPage()
    await onReloadDetail()
    setBusy('')
  }

  async function prepareCommercialista() {
    setBusy('commercialista-prepare')
    const result = await prepareFatturazioneCommercialista(currentDetail.id, {
      channel: commercialistaChannel,
      attachments: commercialistaAttachments,
    })
    if (result.ok && result.draft) {
      setCommercialistaDraft(result.draft)
      setCommercialistaLocalPec(result.localPec)
    }
    setNotice({ tone: result.ok ? 'success' : 'warning', text: result.message })
    setBusy('')
    if (!result.ok && (result.errors.email_commercialista || result.errors.pec_commercialista)) {
      void openQuickCommercialistaSettings()
    }
  }

  async function sendCommercialista() {
    if (!commercialistaDraft) {
      setNotice({ tone: 'warning', text: 'Prepara prima la bozza per il commercialista.' })
      return
    }
    setBusy('commercialista-send')
    if (commercialistaDraft.channel === 'pec') {
      if (!commercialistaLocalPec || !commercialistaPassword.trim()) {
        setNotice({ tone: 'warning', text: 'Per inviare via PEC inserisci la password PEC locale.' })
        setBusy('')
        return
      }
      const sent = await postLocalJson(commercialistaLocalPec.endpoint, {
        ...commercialistaLocalPec.payload,
        password: commercialistaPassword,
        to: commercialistaDraft.to,
        subject: commercialistaDraft.subject,
        body: commercialistaDraft.body,
      }, 65000)
      if (!sent?.ok || !workflowText(sent.message_id)) {
        setNotice({ tone: 'warning', text: workflowText(sent?.messaggio || sent?.message) || 'PEC al commercialista non completata dal Local Signer.' })
        setBusy('')
        return
      }
      await afterMutation(await confirmFatturazioneCommercialistaPec(currentDetail.id, {
        message_id: workflowText(sent.message_id),
        destinatario: commercialistaDraft.to,
        oggetto: commercialistaDraft.subject,
      }))
      setBusy('')
      return
    }
    const result = await sendFatturazioneCommercialistaEmail(currentDetail.id, {
      to: commercialistaDraft.to,
      subject: commercialistaDraft.subject,
      body: commercialistaDraft.body,
      attachmentFiles: commercialistaDraft.attachments.map((attachment) => attachment.storageFile || attachment.filename),
    })
    await afterMutation(result)
    setBusy('')
  }

  const signedXmlName = workflowText(detail.workflow.signedXml.fileName)
  const sdiSent = detail.sdiSentLabel || workflowText(detail.workflow.sdiSend.sentAt)
  const commercialistaSent = workflowText(detail.workflow.commercialista.sentAt)
  const sdiPecMissing = !detail.workflow.sdiPecAddress.trim()
  const commercialistaPecAddress = detail.workflow.commercialistaPec || detail.workflow.commercialistaEmail
  const commercialistaTarget = commercialistaChannel === 'pec' ? commercialistaPecAddress : detail.workflow.commercialistaEmail
  const commercialistaMissing = commercialistaChannel === 'pec' ? !commercialistaPecAddress.trim() : !detail.workflow.commercialistaEmail.trim()
  const commercialistaSentChannel = workflowText(detail.workflow.commercialista.channel)
  const commercialistaSentRecipient = workflowText(detail.workflow.commercialista.recipient)
  const modalClass = ['iu-fatt-modal', pdfFullscreen && activeTab === 'pdf' ? 'is-pdf-fullscreen' : ''].filter(Boolean).join(' ')

  return (
    <div className="iu-fatt-overlay" role="dialog" aria-modal="true" aria-label={`Dettaglio ${detail.number || detail.id}`}>
      <section className={modalClass}>
        <header className="iu-fatt-modal__header">
          <div>
            <span>Parcelle e Fatture</span>
            <h2>Dettaglio {detail.number || detail.id}</h2>
            <p>{detail.customerName}{detail.caseTitle ? ` - ${detail.caseTitle}` : ''}</p>
          </div>
          <div className="iu-fatt-modal__header-actions">
            {activeTab === 'pdf' ? (
              <Button type="button" tone="neutral" onClick={() => setPdfFullscreen((current) => !current)}>
                {pdfFullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
                {pdfFullscreen ? 'Riduci' : 'Tutto schermo'}
              </Button>
            ) : null}
            <Button type="button" tone="neutral" onClick={onClose} aria-label="Chiudi dettaglio">
              <X size={15} />
              Chiudi
            </Button>
          </div>
        </header>

        <nav className="iu-fatt-modal__tabs" aria-label="Sezioni dettaglio fattura">
          {[
            ['dettaglio', 'Dettaglio'],
            ['pdf', 'Anteprima PDF'],
            ['xml', 'XML e SdI'],
            ['commercialista', 'Commercialista'],
          ].map(([id, label]) => (
            <button type="button" className={activeTab === id ? 'is-active' : ''} onClick={() => setActiveTab(id as DetailTab)} key={id}>
              {label}
            </button>
          ))}
        </nav>

        {notice ? (
          <section className={`iu-fatt-state iu-fatt-state--${notice.tone === 'success' ? 'success' : 'warning'}`} aria-live="polite">
            {notice.tone === 'success' ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
            <div><strong>{notice.tone === 'success' ? 'Operazione registrata' : 'Controllo richiesto'}</strong><span>{notice.text}</span></div>
          </section>
        ) : null}

        <div className="iu-fatt-modal__body">
          {activeTab === 'dettaglio' ? (
            <section className="iu-fatt-detail-editor">
              <div className="iu-fatt-detail-summary">
                <span>Stato: {detail.stateLabel}</span>
                <span>Importo: {detail.amountDisplay || 'non indicato'}</span>
                {detail.paymentMethod ? <span>Pagamento: {detail.paymentMethod}</span> : null}
              </div>
              <div className="iu-fatt-edit-lines">
                {voices.map((voice) => (
                  <div className="iu-fatt-edit-line" key={voice.rowId}>
                    <label>
                      <span>Descrizione</span>
                      <input value={voice.descrizione} onChange={(event) => updateVoice(voice.rowId, { descrizione: event.currentTarget.value })} />
                    </label>
                    <label>
                      <span>Quantità</span>
                      <input value={voice.quantita} onChange={(event) => updateVoice(voice.rowId, { quantita: event.currentTarget.value })} inputMode="decimal" />
                    </label>
                    <label>
                      <span>Prezzo unitario</span>
                      <input
                        value={voice.prezzo_unitario}
                        onChange={(event) => updateVoice(voice.rowId, { prezzo_unitario: event.currentTarget.value })}
                        onBlur={(event) => updateVoice(voice.rowId, { prezzo_unitario: currencyInputValue(event.currentTarget.value) })}
                        inputMode="decimal"
                        placeholder="€ 0,00"
                      />
                    </label>
                    <label>
                      <span>Tipo</span>
                      <select value={voice.tipo} onChange={(event) => updateVoice(voice.rowId, { tipo: event.currentTarget.value })}>
                        <option value="ONORARIO">Onorario</option>
                        <option value="SPESE">Spese</option>
                        <option value="ANTICIPO">Anticipazioni</option>
                        <option value="ALTRO">Altro</option>
                      </select>
                    </label>
                    <Button type="button" tone="neutral" onClick={() => removeVoice(voice.rowId)}>
                      <Trash2 size={14} />
                      Rimuovi
                    </Button>
                  </div>
                ))}
              </div>
              <div className="iu-fatt-action-row">
                <Button type="button" tone="neutral" onClick={addVoice}><Plus size={15} /> Aggiungi voce</Button>
                <Button type="button" tone="primary" disabled={busy === 'detail'} onClick={saveDetail}><Save size={15} /> {busy === 'detail' ? 'Salvataggio' : 'Salva dettaglio'}</Button>
              </div>
              <label className="iu-fatt-draft__body">
                <span>Note operative</span>
                <textarea value={note} onChange={(event) => setNote(event.currentTarget.value)} rows={4} />
              </label>
            </section>
          ) : null}

          {activeTab === 'pdf' ? (
            <section className="iu-fatt-pdf-panel">
              <div className="iu-fatt-action-row">
                <ButtonLink href={`${detail.pdfHref}?download=1`} tone="neutral"><Download size={15} /> Scarica PDF</ButtonLink>
                <Button type="button" tone="neutral" onClick={() => setPdfFullscreen((current) => !current)}>
                  {pdfFullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
                  {pdfFullscreen ? 'Riduci anteprima' : 'Tutto schermo'}
                </Button>
              </div>
              <iframe title={`Anteprima PDF ${detail.number || detail.id}`} src={detail.pdfHref} />
            </section>
          ) : null}

          {activeTab === 'xml' ? (
            <section className="iu-fatt-workflow">
              <div className="iu-fatt-workflow__status">
                <Badge tone={detail.sdiStateTone}>{detail.sdiStateLabel}</Badge>
                <strong>XML originale disponibile</strong>
                <span>{detail.sdiStatusMessage}</span>
                {signedXmlName ? <strong>XML firmato: {signedXmlName}</strong> : <strong>XML firmato da generare con Local Signer</strong>}
                {detail.workflow.sdiPecAddress ? <span>PEC SdI: {detail.workflow.sdiPecAddress}</span> : <span>PEC SdI non configurata</span>}
                {sdiSent ? <span>PEC SdI inviata: {sdiSent}</span> : <span>PEC SdI non ancora inviata</span>}
              </div>
              {(sdiPecMissing || quickSdiPecOpen) ? (
                <section className="iu-fatt-quick-settings" aria-label="Configurazione rapida PEC SdI">
                  <div className="iu-fatt-quick-settings__head">
                    <div>
                      <strong>Configura PEC SdI</strong>
                      <span>Salva il destinatario SdI e i parametri PEC studio senza uscire dalla fattura.</span>
                    </div>
                    {!quickSdiPecOpen ? (
                      <Button type="button" tone="neutral" disabled={busy === 'quick-sdi-load'} onClick={() => { void openQuickSdiPecSettings() }}>
                        <PenLine size={15} />
                        Inserisci impostazioni PEC
                      </Button>
                    ) : null}
                  </div>
                  {quickSdiPecOpen ? (
                    <>
                      <div className="iu-fatt-quick-settings__grid">
                        <label className="is-wide">
                          <span>PEC per notifiche SdI</span>
                          <input type="email" value={quickSdiPec.pec_notifiche} onChange={(event) => updateQuickSdiPec({ pec_notifiche: event.currentTarget.value })} placeholder="es. sdi01@pec.fatturapa.it" />
                        </label>
                        <label>
                          <span>PEC studio mittente</span>
                          <input type="email" value={quickSdiPec.pec_indirizzo} onChange={(event) => updateQuickSdiPec({ pec_indirizzo: event.currentTarget.value })} placeholder="studio@pec.it" />
                        </label>
                        <label>
                          <span>Username PEC</span>
                          <input value={quickSdiPec.pec_username} onChange={(event) => updateQuickSdiPec({ pec_username: event.currentTarget.value })} placeholder="di solito uguale alla PEC" />
                        </label>
                        <label>
                          <span>Host invio PEC</span>
                          <input value={quickSdiPec.pec_smtp_host} onChange={(event) => updateQuickSdiPec({ pec_smtp_host: event.currentTarget.value })} />
                        </label>
                        <label>
                          <span>Porta invio PEC</span>
                          <input inputMode="numeric" value={quickSdiPec.pec_smtp_port} onChange={(event) => updateQuickSdiPec({ pec_smtp_port: event.currentTarget.value })} />
                        </label>
                        <label>
                          <span>Host ricezione PEC</span>
                          <input value={quickSdiPec.pec_imap_host} onChange={(event) => updateQuickSdiPec({ pec_imap_host: event.currentTarget.value })} />
                        </label>
                        <label>
                          <span>Porta ricezione PEC</span>
                          <input inputMode="numeric" value={quickSdiPec.pec_imap_port} onChange={(event) => updateQuickSdiPec({ pec_imap_port: event.currentTarget.value })} />
                        </label>
                        <label className="iu-fatt-quick-settings__check">
                          <input type="checkbox" checked={quickSdiPec.pec_use_ssl} onChange={(event) => updateQuickSdiPec({ pec_use_ssl: event.currentTarget.checked })} />
                          <span>Usa SSL per la PEC</span>
                        </label>
                      </div>
                      <div className="iu-fatt-action-row">
                        <Button type="button" tone="primary" disabled={busy === 'quick-sdi-save'} onClick={saveQuickSdiPecSettings}>
                          <Save size={15} />
                          {busy === 'quick-sdi-save' ? 'Salvataggio' : 'Salva e prosegui'}
                        </Button>
                        <Button type="button" tone="neutral" onClick={() => setQuickSdiPecOpen(false)}>
                          <X size={15} />
                          Chiudi impostazioni rapide
                        </Button>
                      </div>
                    </>
                  ) : null}
                </section>
              ) : null}
              <div className="iu-fatt-workflow__grid">
                <label>
                  <span>PIN firma digitale</span>
                  <input type="password" value={pin} onChange={(event) => setPin(event.currentTarget.value)} autoComplete="off" />
                </label>
                <ButtonLink href={detail.xmlHref} tone="neutral">
                  <FileText size={15} />
                  Scarica XML originale
                </ButtonLink>
                <Button type="button" tone="primary" disabled={busy === 'sign'} onClick={signXml}>
                  <FileSignature size={15} />
                  {busy === 'sign' ? 'Firma in corso' : 'Firma XML'}
                </Button>
                <Button type="button" tone="neutral" disabled={busy === 'sdi-prepare'} onClick={prepareSdiPec}>
                  <PenLine size={15} />
                  Prepara PEC SdI
                </Button>
              </div>
              {sdiDraft ? (
                <>
                  <DraftEditor draft={sdiDraft} onChange={setSdiDraft} />
                  <div className="iu-fatt-workflow__grid">
                    <label>
                      <span>Password PEC locale</span>
                      <input type="password" value={pecPassword} onChange={(event) => setPecPassword(event.currentTarget.value)} autoComplete="off" />
                    </label>
                    <Button type="button" tone="success" disabled={busy === 'sdi-send'} onClick={sendSdiPec}>
                      <Send size={15} />
                      {busy === 'sdi-send' ? 'Invio in corso' : 'Invia PEC SdI'}
                    </Button>
                  </div>
                </>
              ) : null}
              <div className="iu-fatt-outcome">
                <h3>Registra esito SdI</h3>
                <label>
                  <span>Esito</span>
                  <select value={outcomeState} onChange={(event) => setOutcomeState(event.currentTarget.value)}>
                    <option value="CONSEGNATA">Consegnata</option>
                    <option value="MANCATA_CONSEGNA">Mancata consegna</option>
                    <option value="SCARTATA">Scartata</option>
                    <option value="DECORRENZA_TERMINI">Decorrenza termini</option>
                    <option value="INVIATA">Inviata</option>
                  </select>
                </label>
                <label><span>Identificativo SdI</span><input value={outcomeId} onChange={(event) => setOutcomeId(event.currentTarget.value)} /></label>
                <label><span>Ricevuta o protocollo</span><input value={outcomeReceipt} onChange={(event) => setOutcomeReceipt(event.currentTarget.value)} /></label>
                <label className="iu-fatt-draft__body"><span>Note esito</span><textarea value={outcomeNote} onChange={(event) => setOutcomeNote(event.currentTarget.value)} rows={3} /></label>
                <Button type="button" tone="primary" disabled={busy === 'outcome'} onClick={saveOutcome}><RefreshCw size={15} /> Registra esito</Button>
              </div>
            </section>
          ) : null}

          {activeTab === 'commercialista' ? (
            <section className="iu-fatt-workflow">
              <div className="iu-fatt-workflow__status">
                <strong>{detail.workflow.commercialistaName || commercialistaTarget || 'Commercialista non configurato'}</strong>
                <span>Canale scelto: {commercialistaChannel === 'pec' ? 'PEC' : 'email ordinaria'}</span>
                {commercialistaTarget ? <span>Destinatario: {commercialistaTarget}</span> : <span>Destinatario non configurato</span>}
                {commercialistaSent ? (
                  <span>Commercialista inviato{commercialistaSentChannel ? ` via ${commercialistaSentChannel}` : ''}: {commercialistaSent}{commercialistaSentRecipient ? ` - ${commercialistaSentRecipient}` : ''}</span>
                ) : (
                  <span>Commercialista non ancora inviato</span>
                )}
              </div>
              {(commercialistaMissing || quickCommercialistaOpen) ? (
                <section className="iu-fatt-quick-settings" aria-label="Configurazione rapida commercialista">
                  <div className="iu-fatt-quick-settings__head">
                    <div>
                      <strong>Configura commercialista</strong>
                      <span>Salva email ordinaria e PEC del commercialista senza uscire dalla fattura.</span>
                    </div>
                    {!quickCommercialistaOpen ? (
                      <Button type="button" tone="neutral" disabled={busy === 'quick-commercialista-load'} onClick={() => { void openQuickCommercialistaSettings() }}>
                        <PenLine size={15} />
                        Inserisci commercialista
                      </Button>
                    ) : null}
                  </div>
                  {quickCommercialistaOpen ? (
                    <>
                      <div className="iu-fatt-quick-settings__grid">
                        <label>
                          <span>Nome commercialista</span>
                          <input value={quickCommercialista.nome_commercialista} onChange={(event) => updateQuickCommercialista({ nome_commercialista: event.currentTarget.value })} placeholder="Studio contabile" />
                        </label>
                        <label>
                          <span>Email ordinaria commercialista</span>
                          <input type="email" value={quickCommercialista.email_commercialista} onChange={(event) => updateQuickCommercialista({ email_commercialista: event.currentTarget.value })} placeholder="commercialista@email.it" />
                        </label>
                        <label className="is-wide">
                          <span>PEC commercialista</span>
                          <input type="email" value={quickCommercialista.pec_commercialista} onChange={(event) => updateQuickCommercialista({ pec_commercialista: event.currentTarget.value })} placeholder="commercialista@pec.it" />
                        </label>
                      </div>
                      <div className="iu-fatt-action-row">
                        <Button type="button" tone="primary" disabled={busy === 'quick-commercialista-save'} onClick={saveQuickCommercialistaSettings}>
                          <Save size={15} />
                          {busy === 'quick-commercialista-save' ? 'Salvataggio' : 'Salva e prosegui'}
                        </Button>
                        <Button type="button" tone="neutral" onClick={() => setQuickCommercialistaOpen(false)}>
                          <X size={15} />
                          Chiudi configurazione
                        </Button>
                      </div>
                    </>
                  ) : null}
                </section>
              ) : null}
              <div className="iu-fatt-workflow__grid">
                <label>
                  <span>Canale</span>
                  <select value={commercialistaChannel} onChange={(event) => {
                    setCommercialistaChannel(event.currentTarget.value)
                    setCommercialistaDraft(null)
                    setCommercialistaLocalPec(undefined)
                  }}>
                    <option value="ordinaria">Email ordinaria</option>
                    <option value="pec">PEC</option>
                  </select>
                </label>
                <label>
                  <span>Allegati</span>
                  <select value={commercialistaAttachments} onChange={(event) => {
                    setCommercialistaAttachments(event.currentTarget.value)
                    setCommercialistaDraft(null)
                    setCommercialistaLocalPec(undefined)
                  }}>
                    <option value="pdf">Solo PDF</option>
                    <option value="pdf_xml_firmato">PDF più XML firmato</option>
                  </select>
                </label>
                <Button type="button" tone="neutral" disabled={busy === 'commercialista-prepare'} onClick={prepareCommercialista}>
                  <PenLine size={15} />
                  Prepara bozza
                </Button>
              </div>
              {commercialistaDraft ? (
                <>
                  <DraftEditor draft={commercialistaDraft} onChange={setCommercialistaDraft} />
                  {commercialistaDraft.channel === 'pec' ? (
                    <label className="iu-fatt-workflow__password">
                      <span>Password PEC locale</span>
                      <input type="password" value={commercialistaPassword} onChange={(event) => setCommercialistaPassword(event.currentTarget.value)} autoComplete="off" />
                    </label>
                  ) : null}
                  <Button type="button" tone="success" disabled={busy === 'commercialista-send'} onClick={sendCommercialista}>
                    <Mail size={15} />
                    {commercialistaDraft.channel === 'pec' ? 'Invia PEC commercialista' : 'Invia email commercialista'}
                  </Button>
                </>
              ) : null}
            </section>
          ) : null}
        </div>
      </section>
    </div>
  )
}

function ArchiveMutationState({ result, errors }: { result: FatturazioneMutationResult | null; errors: Record<string, string> }) {
  if (!result) return null
  if (result.ok) {
    return (
      <section className="iu-fatt-state iu-fatt-state--success" aria-live="polite">
        <CheckCircle2 size={20} />
        <div>
          <strong>Operazione completata</strong>
          <span>{result.message}</span>
        </div>
      </section>
    )
  }
  const rows = displayErrors(errors)
  return (
    <section className="iu-fatt-state iu-fatt-state--warning" aria-live="polite">
      <AlertTriangle size={20} />
      <div>
        <strong>Controlla i dati inseriti</strong>
        {rows.length ? rows.map((row) => <span key={row}>{row}</span>) : <span>{result.message}</span>}
      </div>
    </section>
  )
}

function ArchiveView({ data, onReload }: { data: FatturazionePageData; onReload: (data: FatturazionePageData) => void }) {
  const exportAction = data.actions.find((action) => action.id === 'export')
  const [query, setQuery] = useState('')
  const [stateFilter, setStateFilter] = useState(allStatesFilter)
  const [paymentFilter, setPaymentFilter] = useState<PaymentFilter>('all')
  const [issueFilter, setIssueFilter] = useState<IssueFilter>('all')
  const [clientFilter, setClientFilter] = useState('')
  const [matterFilter, setMatterFilter] = useState('')
  const [detail, setDetail] = useState<FatturazioneDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailInitialTab, setDetailInitialTab] = useState<DetailTab>('dettaglio')
  const [savingId, setSavingId] = useState('')
  const [mutationResult, setMutationResult] = useState<FatturazioneMutationResult | null>(null)
  const [mutationErrors, setMutationErrors] = useState<Record<string, string>>({})
  const [autoOpenedId, setAutoOpenedId] = useState('')
  const lowered = query.trim().toLowerCase()
  const loweredClient = clientFilter.trim().toLowerCase()
  const loweredMatter = matterFilter.trim().toLowerCase()
  const requestedDetailId = requestedFatturazioneDetailId()
  const records = data.records.filter((record) => {
    if (stateFilter !== allStatesFilter && record.state !== stateFilter) return false
    if (paymentFilter === 'bonifico' && !hasRegisteredTransfer(record)) return false
    if (paymentFilter === 'senza_bonifico' && hasRegisteredTransfer(record)) return false
    if (issueFilter === 'emessa' && !isIssuedInvoice(record)) return false
    if (issueFilter === 'da_emettere' && !isToIssueInvoice(record)) return false
    if (loweredClient && !record.customerName.toLowerCase().includes(loweredClient)) return false
    const matterSearch = [record.caseId, record.caseReference, record.caseRg, record.caseTitle]
      .join(' ')
      .toLowerCase()
    if (loweredMatter && !matterSearch.includes(loweredMatter)) return false
    if (!lowered) return true
    return [record.number, record.customerName, record.caseId, record.caseReference, record.caseRg, record.caseTitle, record.stateLabel, record.paymentMethod, record.documentKindLabel]
      .join(' ')
      .toLowerCase()
      .includes(lowered)
  })
  const hasFilters = Boolean(
    lowered ||
    loweredClient ||
    loweredMatter ||
    stateFilter !== allStatesFilter ||
    paymentFilter !== 'all' ||
    issueFilter !== 'all'
  )

  async function reloadAfter(result: FatturazioneMutationResult) {
    setMutationResult(result)
    setMutationErrors(result.errors || {})
    if (result.ok) {
      onReload(await getFatturazionePage())
    }
  }

  async function loadDetail(record: FatturazioneRecord, tab: DetailTab = 'dettaglio') {
    setDetailInitialTab(tab)
    setDetailLoading(true)
    setDetail(null)
    const response = await getFatturazioneDetail(record.id)
    if (response.ok) {
      setDetail(response.item)
      setMutationResult(null)
      setMutationErrors({})
    } else {
      setMutationResult({ ok: false, message: response.message || 'Dettaglio non disponibile.', errors: response.errors, item: null })
      setMutationErrors(response.errors)
    }
    setDetailLoading(false)
  }

  function openDetailTab(record: FatturazioneRecord, tab: DetailTab) {
    loadDetail(record, tab)
  }

  async function reloadCurrentDetail() {
    const currentId = detail?.id
    if (!currentId) return
    setDetailLoading(true)
    const response = await getFatturazioneDetail(currentId)
    if (response.ok) {
      setDetail(response.item)
    } else {
      setMutationResult({ ok: false, message: response.message || 'Dettaglio non disponibile.', errors: response.errors, item: null })
      setMutationErrors(response.errors)
    }
    setDetailLoading(false)
  }

  async function reloadArchivePage() {
    onReload(await getFatturazionePage())
  }

  useEffect(() => {
    if (!requestedDetailId || autoOpenedId === requestedDetailId) return
    const record = data.records.find((item) => item.id === requestedDetailId)
    if (!record) return
    setAutoOpenedId(requestedDetailId)
    setQuery(record.number || record.customerName || '')
    loadDetail(record)
  }, [autoOpenedId, data.records, requestedDetailId])

  async function updateStatus(record: FatturazioneRecord, stato: string) {
    setSavingId(record.id)
    await reloadAfter(await updateFatturazioneStatus(record.id, { stato }))
    setSavingId('')
  }

  async function cancelRecord(record: FatturazioneRecord) {
    setSavingId(record.id)
    await reloadAfter(await cancelFatturazioneDocument(record.id))
    setSavingId('')
  }

  async function markPaid(record: FatturazioneRecord) {
    setSavingId(record.id)
    await reloadAfter(await markFatturazionePaid(record.id))
    setSavingId('')
  }

  async function handleNumberingSaved(result: FatturazioneNumberingResult) {
    if (result.ok) {
      onReload(await getFatturazionePage())
    }
  }

  function resetFilters() {
    setQuery('')
    setStateFilter(allStatesFilter)
    setPaymentFilter('all')
    setIssueFilter('all')
    setClientFilter('')
    setMatterFilter('')
  }

  return (
    <>
      <CompactOperations
        data={data}
        totalRecords={data.records.length}
        visibleRecords={records.length}
        stateFilter={stateFilter}
        paymentFilter={paymentFilter}
        issueFilter={issueFilter}
        onStateFilter={setStateFilter}
        onPaymentFilter={setPaymentFilter}
        onIssueFilter={setIssueFilter}
        exportAction={exportAction}
      />
      <Panel
        title="Archivio parcelle e fatture"
        subtitle={`${records.length} elementi visualizzati su ${data.records.length}`}
        actions={exportAction ? (
          <ButtonLink href={exportAction.href} tone="neutral">
            <Download size={15} />
            {exportAction.label}
          </ButtonLink>
        ) : null}
      >
        <div className="iu-fatt-filters" aria-label="Filtri archivio fatturazione">
          <label className="iu-fatt-search">
            <Search size={16} />
            <input
              aria-label="Cerca nell'archivio fatturazione"
              value={query}
              onChange={(event) => setQuery(event.currentTarget.value)}
              placeholder="Cerca per cliente, numero, fascicolo o stato"
            />
          </label>
          <label className="iu-fatt-filter-field">
            <span>Bonifico registrato</span>
            <select
              aria-label="Filtro bonifico registrato"
              value={paymentFilter}
              onChange={(event) => setPaymentFilter(event.currentTarget.value as PaymentFilter)}
            >
              <option value="all">Tutti</option>
              <option value="bonifico">Sì</option>
              <option value="senza_bonifico">No</option>
            </select>
          </label>
          <label className="iu-fatt-filter-field">
            <span>Parcella emessa</span>
            <select
              aria-label="Filtro parcella emessa"
              value={issueFilter}
              onChange={(event) => setIssueFilter(event.currentTarget.value as IssueFilter)}
            >
              <option value="all">Tutte</option>
              <option value="emessa">Emessa</option>
              <option value="da_emettere">Da emettere</option>
            </select>
          </label>
          <label className="iu-fatt-filter-field">
            <span>Cliente</span>
            <input
              aria-label="Filtro cliente"
              value={clientFilter}
              onChange={(event) => setClientFilter(event.currentTarget.value)}
              placeholder="Nome cliente"
            />
          </label>
          <label className="iu-fatt-filter-field">
            <span>Nr fascicolo</span>
            <input
              aria-label="Filtro numero fascicolo"
              value={matterFilter}
              onChange={(event) => setMatterFilter(event.currentTarget.value)}
              placeholder="RG o ID fascicolo"
            />
          </label>
          <Button type="button" tone="neutral" disabled={!hasFilters} onClick={resetFilters}>
            Azzera filtri
          </Button>
        </div>
        <ArchiveMutationState result={mutationResult} errors={mutationErrors} />
        {records.length ? (
          <div className="iu-fatt-records">
            {records.map((record) => (
              <InvoiceRow
                record={record}
                data={data}
                savingId={savingId}
                onDetail={loadDetail}
                onOpenTab={openDetailTab}
                onStatus={updateStatus}
                onCancel={cancelRecord}
                onPaid={markPaid}
                key={record.id || record.number}
              />
            ))}
          </div>
        ) : (
          <EmptyState
            title={data.records.length ? 'Nessun risultato' : 'Nessuna parcella visualizzabile'}
            message={data.records.length ? "La ricerca locale non ha trovato documenti nell'elenco ricevuto." : "L'archivio economico non contiene documenti per la vista corrente."}
            action={<ButtonLink href="/fatturazione/nuova" tone="primary">Nuova parcella</ButtonLink>}
          />
        )}
      </Panel>
      <div id="fatturazione-numerazione">
        <NumberingPanel data={data} onSaved={handleNumberingSaved} />
      </div>
      <MetricGrid data={data} />
      <ArchiveDetailPanel
        detail={detail}
        loading={detailLoading}
        onClose={() => setDetail(null)}
        onReloadPage={reloadArchivePage}
        onReloadDetail={reloadCurrentDetail}
        initialTab={detailInitialTab}
      />
      <FiscalGuardrailsPanel data={data} />
    </>
  )
}

export function FatturazionePage() {
  const [data, setData] = useState<FatturazionePageData>(emptyFatturazionePage)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const isNew = window.location.pathname.replace(/\/+$/, '').toLowerCase() === '/fatturazione/nuova'

  useEffect(() => {
    let active = true
    const loadPage = isNew ? getNuovaFatturaPage : getFatturazionePage
    setLoading(true)
    setLoadError('')
    loadPage()
      .then((payload) => {
        if (!active) return
        setData(payload)
        if (payload.ok === false && payload.warnings.length) {
          setLoadError(payload.warnings[0]?.message || 'Dati non disponibili.')
        }
      })
      .catch(() => {
        if (active) setLoadError('Errore nel caricamento dei dati fatturazione.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [isNew])

  const hasData = data.metrics.length > 0 || data.records.length > 0 || data.clients.length > 0 || data.sections.some((section) => section.items.length > 0)
  const form = data.form || data.forms.find((item) => item.id === 'nuova_parcella') || data.forms[0]

  return (
    <Page
      title={isNew ? 'Nuova parcella' : 'Fatturazione'}
      subtitle={isNew ? 'Pagina operativa con salvataggio validato e calcolo fiscale governato.' : 'Proforme, parcelle e incassi collegati ai fascicoli.'}
      className={isNew ? undefined : 'iu-fatt-page'}
      actions={
        isNew ? (
          <ButtonLink href="/fatturazione" tone="neutral">
            <ReceiptText size={16} />
            Archivio
          </ButtonLink>
        ) : (
          <ButtonLink href="/fatturazione/nuova" tone="primary">
            <Plus size={16} />
            Nuova parcella
          </ButtonLink>
        )
      }
    >
      {loading ? <LoadingState title="Caricamento fatturazione" message="Lettura degli archivi economici reali in corso." /> : null}
      {!loading && loadError ? (
        <section className="iu-fatt-state iu-fatt-state--danger" aria-live="polite">
          <AlertTriangle size={20} />
          <div>
            <strong>Dati non disponibili</strong>
            <span>{loadError}</span>
          </div>
        </section>
      ) : null}
      {!loading && !hasData && !loadError ? (
        <EmptyState
          title="Nessun dato economico disponibile"
          message="Non sono disponibili dati visualizzabili per questa superficie."
          action={isNew ? <ButtonLink href="/clienti" tone="primary">Apri clienti</ButtonLink> : <ButtonLink href="/fatturazione/nuova" tone="primary">Nuova parcella</ButtonLink>}
        />
      ) : null}
      {!loading && !loadError && hasData ? (
        isNew ? (
          <>
            <section className="iu-fatt-banner" aria-label="Form operativo">
              <strong>Scrittura tracciata</strong>
              <span>La pagina raccoglie i dati minimi; creazione, numerazione, validazione, controlli e importi definitivi restano nei servizi dello studio.</span>
            </section>
            <WarningPanel data={data} />
            <SdiWorkflowPanel data={data} />
            <NewInvoiceForm data={data} form={form} />
            <ContractPanel data={data} />
          </>
        ) : (
          <ArchiveView data={data} onReload={setData} />
        )
      ) : null}
    </Page>
  )
}
