import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  ExternalLink,
  FileText,
  Mail,
  Plus,
  ReceiptText,
  Save,
  Search,
  Sparkles,
  Trash2,
  XCircle,
} from 'lucide-react'
import {
  cancelFatturazioneDocument,
  createFattura,
  emptyFatturazionePage,
  getFatturazioneDetail,
  getFatturazionePage,
  getNuovaFatturaPage,
  markFatturazionePaid,
  updateFatturazioneStatus,
  type CreateFatturaPayload,
  type CreateFatturaResult,
  type FatturazioneDetail,
  type FatturazioneFiscalDefaults,
  type FatturazioneFormDefinition,
  type FatturazioneMatter,
  type FatturazionePageData,
  type FatturazionePersonalizedData,
  type FatturazionePersonalizedParty,
  type FatturazioneRecord,
  type FatturazioneMutationResult,
  type FatturazioneVoiceDefault,
} from '../fatturazioneData'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
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
      cassa_previdenziale: 'CAF',
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

function requestedFatturazioneDetailId(): string {
  const params = new URLSearchParams(window.location.search)
  return params.get('id_documento') || params.get('id_parcella') || ''
}

function rowFromDefault(item: FatturazioneVoiceDefault, index: number): VoiceRow {
  return {
    rowId: `voce-${index + 1}`,
    descrizione: item.descrizione,
    quantita: item.quantita || '1',
    prezzo_unitario: item.prezzo_unitario,
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

function numericInputValue(value: string, fallback: number): number {
  const parsed = Number.parseFloat(value.replace(',', '.'))
  return Number.isFinite(parsed) ? parsed : fallback
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
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(value)
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

function InvoiceRow({
  record,
  data,
  savingId,
  onDetail,
  onStatus,
  onCancel,
  onPaid,
}: {
  record: FatturazioneRecord
  data: FatturazionePageData
  savingId: string
  onDetail: (record: FatturazioneRecord) => void
  onStatus: (record: FatturazioneRecord, stato: string) => void
  onCancel: (record: FatturazioneRecord) => void
  onPaid: (record: FatturazioneRecord) => void
}) {
  const [nextStatus, setNextStatus] = useState(record.state)
  return (
    <article className="iu-fatt-record">
      <div className="iu-fatt-record__main">
        <span>{record.number || record.id}</span>
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
              {savingId === record.id ? 'saving' : 'Aggiorna'}
            </Button>
          </div>
        ) : null}
        {data.permissions.canMarkPaid && record.state !== 'PAGATA' ? (
          <Button type="button" tone="success" disabled={savingId === record.id} onClick={() => onPaid(record)}>
            Segna pagata
          </Button>
        ) : null}
        {data.permissions.canCancel && record.state !== 'ANNULLATA' ? (
          <Button type="button" tone="danger" disabled={savingId === record.id} onClick={() => onCancel(record)}>
            Annulla
          </Button>
        ) : null}
        {record.pdfHref ? (
          <ButtonLink href={record.pdfHref} tone="neutral">
            <FileText size={15} />
            PDF
          </ButtonLink>
        ) : null}
        {record.xmlHref ? (
          <ButtonLink href={record.xmlHref} tone="neutral">
            <FileText size={15} />
            XML
          </ButtonLink>
        ) : null}
      </div>
    </article>
  )
}

function MetricGrid({ data }: { data: FatturazionePageData }) {
  return (
    <section className="iu-fatt-kpis" aria-label="Indicatori fatturazione">
      {data.metrics.map((metric) => (
        <KpiCard
          label={metric.label}
          value={displayValue(metric.value)}
          note={metric.note}
          badge={<Badge tone={metric.tone}>{metric.tone}</Badge>}
          key={metric.id}
        />
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
          <span>{result?.message || 'Il salvataggio non e\' stato completato.'}</span>
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
        {rows.length ? rows.map((row) => <span key={row}>{row}</span>) : <span>La richiesta non e stata accettata.</span>}
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
              type="number"
              min="0"
              step="0.01"
              value={row.prezzo_unitario}
              onChange={(event) => updateRow(row.rowId, { prezzo_unitario: event.currentTarget.value })}
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
                <option value="CAF">Avvocati</option>
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

function ArchiveDetailPanel({ detail, loading }: { detail: FatturazioneDetail | null; loading: boolean }) {
  if (loading) return <LoadingState title="Caricamento dettaglio" message="Lettura della sintesi operativa." />
  if (!detail) return null
  return (
    <Panel title={`Dettaglio ${detail.number || detail.id}`} subtitle={detail.customerName}>
      <div className="iu-fatt-detail">
        <span>Stato: {detail.stateLabel}</span>
        <span>Importo: {detail.amountDisplay || 'non indicato'}</span>
        {detail.caseTitle ? <span>Fascicolo: {detail.caseTitle}</span> : null}
        {detail.paymentMethod ? <span>Pagamento: {detail.paymentMethod}</span> : null}
      </div>
      {detail.voci.length ? (
        <div className="iu-fatt-detail-lines">
          {detail.voci.map((voice, index) => (
            <div className="iu-fatt-detail-line" key={`${voice.descrizione}-${index}`}>
              <span>{voice.descrizione}</span>
              <small>Quantita {voice.quantita || '1'}</small>
              <strong>{voice.prezzoDisplay}</strong>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState title="Nessuna voce sintetica" message="Non sono disponibili righe di dettaglio per questo documento." />
      )}
    </Panel>
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
  const [detail, setDetail] = useState<FatturazioneDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [savingId, setSavingId] = useState('')
  const [mutationResult, setMutationResult] = useState<FatturazioneMutationResult | null>(null)
  const [mutationErrors, setMutationErrors] = useState<Record<string, string>>({})
  const [autoOpenedId, setAutoOpenedId] = useState('')
  const lowered = query.trim().toLowerCase()
  const requestedDetailId = requestedFatturazioneDetailId()
  const records = data.records.filter((record) => {
    if (!lowered) return true
    return [record.number, record.customerName, record.caseTitle, record.stateLabel]
      .join(' ')
      .toLowerCase()
      .includes(lowered)
  })

  async function reloadAfter(result: FatturazioneMutationResult) {
    setMutationResult(result)
    setMutationErrors(result.errors || {})
    if (result.ok) {
      onReload(await getFatturazionePage())
    }
  }

  async function loadDetail(record: FatturazioneRecord) {
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

  return (
    <>
      <section className="iu-fatt-banner" aria-label="Documenti economici">
        <strong>PDF, XML ed export restano governati</strong>
        <span>Archivio, indicatori, dettaglio sintetico e azioni di stato usano controlli protetti.</span>
      </section>
      <WarningPanel data={data} />
      <SdiWorkflowPanel data={data} />
      <MetricGrid data={data} />
      <section className="iu-fatt-grid" aria-label="Sezioni fatturazione">
        {data.sections.map((section) => (
          <Panel title={section.title} subtitle={section.kind} key={section.id}>
            {section.items.length ? (
              <div className="iu-fatt-list">
                {section.items.map((item) => (
                  <div className="iu-fatt-list__item" key={item.id}>
                    <span>{item.label}</span>
                    <strong>{displayValue(item.value)}</strong>
                    {item.note ? <small>{item.note}</small> : null}
                    <Badge tone={item.tone}>{item.tone}</Badge>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title={section.emptyMessage} />
            )}
          </Panel>
        ))}
      </section>
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
        <label className="iu-fatt-search">
          <Search size={16} />
          <input value={query} onChange={(event) => setQuery(event.currentTarget.value)} placeholder="Cerca per cliente, numero, fascicolo o stato" />
        </label>
        <ArchiveMutationState result={mutationResult} errors={mutationErrors} />
        {records.length ? (
          <div className="iu-fatt-records">
            {records.map((record) => (
              <InvoiceRow
                record={record}
                data={data}
                savingId={savingId}
                onDetail={loadDetail}
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
            message={data.records.length ? 'La ricerca locale non ha trovato documenti nell elenco ricevuto.' : "L'archivio economico non contiene documenti per la vista corrente."}
            action={<ButtonLink href="/fatturazione/nuova" tone="primary">Nuova parcella</ButtonLink>}
          />
        )}
      </Panel>
      <ArchiveDetailPanel detail={detail} loading={detailLoading} />
      <ContractPanel data={data} />
      <TechnicalRollback />
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
      subtitle={isNew ? 'Pagina operativa con salvataggio validato e calcolo fiscale governato.' : 'Archivio economico con indicatori reali e documenti avanzati governati.'}
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
