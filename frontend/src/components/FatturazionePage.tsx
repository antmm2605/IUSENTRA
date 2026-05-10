import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  ExternalLink,
  FileText,
  Plus,
  ReceiptText,
  Save,
  Search,
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

const fallbackFormState: FormState = {
  id_cliente: '',
  id_fascicolo: '',
  data_emissione: '',
  data_scadenza: '',
  note: '',
  voci: [defaultVoice],
  opzioni_fiscali: defaultFiscalOptions,
  hidden: {},
}

function displayValue(value: string | number): string {
  if (typeof value === 'number') return new Intl.NumberFormat('it-IT').format(value)
  return value
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

function stateFromForm(form: FatturazioneFormDefinition | undefined): FormState {
  const defaults = form?.defaults
  const rows = (defaults?.voci || []).map(rowFromDefault)
  return {
    id_cliente: defaults?.id_cliente || '',
    id_fascicolo: defaults?.id_fascicolo || '',
    data_emissione: defaults?.data_emissione || '',
    data_scadenza: defaults?.data_scadenza || '',
    note: defaults?.note || '',
    voci: rows.length ? rows : [defaultVoice],
    opzioni_fiscali: defaults?.opzioni_fiscali || defaultFiscalOptions,
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
    voci: formState.voci.map((row) => ({
      descrizione: row.descrizione,
      quantita: numericInputValue(row.quantita, 1),
      prezzo_unitario: numericInputValue(row.prezzo_unitario, 0),
      tipo: row.tipo || 'ONORARIO',
    })),
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

function ContractPanel({ data }: { data: FatturazionePageData }) {
  return (
    <Panel title="Presidio dati" subtitle="Lettura operativa con proprieta' fiscale governata.">
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
        {record.paymentMethod ? <small>{record.paymentMethod}</small> : null}
      </div>
      <div className="iu-fatt-record__actions">
        <Button type="button" tone="neutral" onClick={() => onDetail(record)}>
          <Search size={15} />
          Dettaglio JSON
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
}: {
  values: FatturazioneFiscalDefaults
  onChange: (values: FatturazioneFiscalDefaults) => void
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
  const canSave = form?.enabled !== false
  const noClients = data.clients.length === 0

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
    <Panel title="Nuova parcella" subtitle="Salvataggio con validazione, permessi e audit.">
      <form className="iu-fatt-operational" onSubmit={onSubmit}>
        <StatusMessage status={saveStatus} result={result} errors={errors} />
        <div className="iu-fatt-form-grid">
          <label className="iu-fatt-field">
            <span>Cliente</span>
            <select
              required
              value={formState.id_cliente}
              onChange={(event) => setFormState((current) => ({ ...current, id_cliente: event.currentTarget.value, id_fascicolo: '' }))}
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
              onChange={(event) => setFormState((current) => ({ ...current, id_fascicolo: event.currentTarget.value }))}
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
            <span>Data emissione</span>
            <input
              type="date"
              required
              value={formState.data_emissione}
              onChange={(event) => setFormState((current) => ({ ...current, data_emissione: event.currentTarget.value }))}
            />
          </label>
          <label className="iu-fatt-field">
            <span>Scadenza pagamento</span>
            <input
              type="date"
              required
              value={formState.data_scadenza}
              onChange={(event) => setFormState((current) => ({ ...current, data_scadenza: event.currentTarget.value }))}
            />
          </label>
        </div>

        <VoiceEditor
          rows={formState.voci}
          onChange={(voci) => setFormState((current) => ({ ...current, voci }))}
        />

        <FiscalOptions
          values={formState.opzioni_fiscali}
          onChange={(opzioni_fiscali) => setFormState((current) => ({ ...current, opzioni_fiscali }))}
        />

        <label className="iu-fatt-field">
          <span>Note e causale</span>
          <textarea
            rows={4}
            value={formState.note}
            onChange={(event) => setFormState((current) => ({ ...current, note: event.currentTarget.value }))}
            placeholder="Causale o note per il documento"
          />
        </label>

        <section className="iu-fatt-form-note" aria-label="Calcolo definitivo">
          <strong>Calcolo definitivo governato</strong>
          <span>La pagina invia voci e opzioni; numerazione, imponibile, imposte e importi finali sono determinati dai servizi di fatturazione.</span>
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
      <TechnicalRollback href="/fatturazione?_legacy=1" />
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
          <strong>success</strong>
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
        <strong>validation error</strong>
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
  const lowered = query.trim().toLowerCase()
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
