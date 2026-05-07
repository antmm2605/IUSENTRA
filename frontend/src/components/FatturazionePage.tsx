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
  Trash2,
  XCircle,
} from 'lucide-react'
import {
  createFattura,
  emptyFatturazionePage,
  getFatturazionePage,
  getNuovaFatturaPage,
  type CreateFatturaPayload,
  type CreateFatturaResult,
  type FatturazioneFiscalDefaults,
  type FatturazioneFormDefinition,
  type FatturazioneMatter,
  type FatturazionePageData,
  type FatturazioneRecord,
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
            <Badge tone="warning">{warning.code}</Badge>
            <span>{warning.message}</span>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function ContractPanel({ data }: { data: FatturazionePageData }) {
  return (
    <Panel title="Contratto dati" subtitle="Lettura React con proprieta' fiscale canonica conservata nel backend.">
      <div className="iu-fatt-contract">
        <span>Fonte: {data.source || 'non indicata'}</span>
        <span>Generato: {data.generated_at || 'non disponibile'}</span>
        <span>Scritture: {data.contracts.writes}</span>
        <span>Owner route: {data.contracts.route_owner}</span>
        <span>Calcolo: {data.contracts.canonical_calculation || 'backend'}</span>
        <span>Mock fallback: {data.contracts.mock_fallback ? 'si' : 'no'}</span>
      </div>
    </Panel>
  )
}

function InvoiceRow({ record }: { record: FatturazioneRecord }) {
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
        {record.detailHref ? (
          <ButtonLink href={record.detailHref} tone="neutral">
            <ExternalLink size={15} />
            Dettaglio backend
          </ButtonLink>
        ) : null}
        {record.pdfHref ? (
          <ButtonLink href={record.pdfHref} tone="neutral">
            <FileText size={15} />
            PDF backend
          </ButtonLink>
        ) : null}
        {record.xmlHref ? (
          <ButtonLink href={record.xmlHref} tone="neutral">
            <FileText size={15} />
            XML backend
          </ButtonLink>
        ) : null}
      </div>
    </article>
  )
}

function MetricGrid({ data }: { data: FatturazionePageData }) {
  return (
    <section className="iu-fatt-kpis" aria-label="KPI fatturazione">
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
          <span>Documento {result.item.number || result.item.id} creato dal backend.</span>
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
          <span>Serve il permesso backend di creazione o modifica fatturazione.</span>
        </div>
      </section>
    )
  }
  if (status === 'server') {
    return (
      <section className="iu-fatt-state iu-fatt-state--danger" aria-live="polite">
        <AlertTriangle size={20} />
        <div>
          <strong>Errore server</strong>
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
        {rows.length ? rows.map((row) => <span key={row}>{row}</span>) : <span>Il backend ha rifiutato il payload.</span>}
      </div>
    </section>
  )
}

function TechnicalRollback() {
  return (
    <section className="iu-fatt-rollback" aria-label="Rollback tecnico">
      <div>
        <strong>Rollback tecnico</strong>
        <span>Disponibile solo per assistenza e confronto con il template storico, non come flusso principale.</span>
      </div>
      <ButtonLink href="/fatturazione/nuova?_legacy=1" tone="warning">
        <ExternalLink size={15} />
        Apri template storico
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
    <Panel title="Nuova parcella" subtitle="Salvataggio JSON con validazione, permessi e audit backend.">
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

        <section className="iu-fatt-form-note" aria-label="Calcolo backend">
          <strong>Calcolo definitivo nel backend</strong>
          <span>React invia voci e opzioni; numerazione, imponibile, imposte e importi finali sono determinati dai servizi di fatturazione.</span>
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
                Apri dettaglio backend
              </ButtonLink>
            ) : null}
          </div>
        ) : null}
      </form>
      <TechnicalRollback />
    </Panel>
  )
}

function ArchiveView({ data }: { data: FatturazionePageData }) {
  const exportAction = data.actions.find((action) => action.id === 'export')
  return (
    <>
      <section className="iu-fatt-banner" aria-label="Documenti economici backend">
        <strong>PDF, XML ed export restano backend</strong>
        <span>La shell React mostra archivio e KPI reali; dettagli, download e variazioni di stato restano sui blueprint Flask.</span>
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
        subtitle={`${data.records.length} elementi letti dal repository reale`}
        actions={exportAction ? (
          <ButtonLink href={exportAction.href} tone="neutral">
            <Download size={15} />
            {exportAction.label}
          </ButtonLink>
        ) : null}
      >
        {data.records.length ? (
          <div className="iu-fatt-records">
            {data.records.map((record) => <InvoiceRow record={record} key={record.id || record.number} />)}
          </div>
        ) : (
          <EmptyState
            title="Nessuna parcella visualizzabile"
            message="L'archivio economico non contiene documenti per la vista corrente."
            action={<ButtonLink href="/fatturazione/nuova" tone="primary">Nuova parcella</ButtonLink>}
          />
        )}
      </Panel>
      <ContractPanel data={data} />
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
      subtitle={isNew ? 'UI React operativa con salvataggio JSON e calcolo fiscale canonico nel backend.' : 'Archivio economico con KPI reali e documenti avanzati conservati nel backend.'}
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
      {loading ? <LoadingState title="Caricamento fatturazione" message="Lettura dei repository economici reali in corso." /> : null}
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
          message="Il backend non ha restituito dati visualizzabili per questa superficie."
          action={isNew ? <ButtonLink href="/clienti" tone="primary">Apri clienti</ButtonLink> : <ButtonLink href="/fatturazione/nuova" tone="primary">Nuova parcella</ButtonLink>}
        />
      ) : null}
      {!loading && !loadError && hasData ? (
        isNew ? (
          <>
            <section className="iu-fatt-banner" aria-label="Form operativo">
              <strong>Scrittura JSON backend</strong>
              <span>La pagina raccoglie i dati minimi; creazione, numerazione, validazione, audit e importi definitivi restano nei servizi Flask.</span>
            </section>
            <WarningPanel data={data} />
            <NewInvoiceForm data={data} form={form} />
            <ContractPanel data={data} />
          </>
        ) : (
          <ArchiveView data={data} />
        )
      ) : null}
    </Page>
  )
}
