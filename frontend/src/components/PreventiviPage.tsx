import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import {
  AlertTriangle,
  BriefcaseBusiness,
  CheckCircle2,
  Download,
  ExternalLink,
  FileText,
  Plus,
  Save,
  Search,
  Trash2,
  XCircle,
} from 'lucide-react'
import {
  createConferimento,
  createPreventivo,
  emptyPreventiviPage,
  getConferimentoDetail,
  getNuovoConferimentoPage,
  getNuovoPreventivoPage,
  getPreventiviPage,
  getPreventivoDetail,
  updateConferimentoStatus,
  updatePreventivoStatus,
  type ConferimentoDetail,
  type CreateConferimentoPayload,
  type CreateConferimentoResult,
  type CreatePreventivoPayload,
  type CreatePreventivoResult,
  type PreventiviFormDefaults,
  type PreventiviPageData,
  type PreventivoDetail,
  type PreventivoFiscalOptions,
  type PreventivoRow,
  type PreventivoVoiceInput,
} from '../preventiviData'
import { codiceOggettoPstSource } from '../data/praticheCollegateCatalog'
import { displaySourceLabel, displayWritesLabel, sanitizeDisplayText } from '../displayText'
import { CodiceOggettoPstSearch } from './CodiceOggettoPstSearch'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import './PreventiviPage.css'

type PageMode = 'archive' | 'new-preventivo' | 'new-conferimento' | 'detail-conferimento'
type SaveStatus = 'idle' | 'loading' | 'saving' | 'success' | 'validation' | 'permission' | 'error'

type PreventivoVoiceRow = {
  rowId: string
  descrizione: string
  tipo: string
  importo: string
}

type PreventivoFormState = {
  id_cliente: string
  id_fascicolo: string
  oggetto: string
  data_emissione: string
  data_scadenza: string
  tipo_compenso: string
  tipo_procedimento: string
  valore_controversia: string
  complessita: string
  voci: PreventivoVoiceRow[]
  opzioni_fiscali: PreventivoFiscalOptions
  note: string
  hidden: Record<string, string>
}

type ConferimentoFormState = {
  id_cliente: string
  id_fascicolo: string
  id_preventivo: string
  oggetto: string
  avvocato_referente: string
  numero_iscrizione_albo: string
  ordine_avvocati: string
  data_incarico: string
  tipo_compenso: string
  tipo_procedimento: string
  compenso_pattuito: string
  informativa_art13_resa: boolean
  clausola_adr_resa: boolean
  apri_fascicolo_guidato: boolean
  note: string
  hidden: Record<string, string>
}

const emptyVoice: PreventivoVoiceRow = {
  rowId: 'voce-1',
  descrizione: '',
  tipo: 'ONORARIO',
  importo: '',
}

const defaultFiscalOptions: PreventivoFiscalOptions = {
  applica_iva: true,
  applica_cassa: true,
  applica_ritenuta: false,
}

function modeFromPath(): PageMode {
  const path = window.location.pathname.replace(/\/+$/, '').toLowerCase() || '/preventivi'
  if (path === '/preventivi/nuovo') return 'new-preventivo'
  if (path === '/preventivi/conferimento/nuovo') return 'new-conferimento'
  if (/^\/preventivi\/conferimento\/[^/]+$/.test(path)) return 'detail-conferimento'
  return 'archive'
}

function detailIdFromPath(): string {
  const match = window.location.pathname.replace(/\/+$/, '').match(/^\/preventivi\/conferimento\/([^/]+)$/i)
  return match ? decodeURIComponent(match[1]) : ''
}

function preventivoIdFromLocation(): string {
  const pathMatch = window.location.pathname.replace(/\/+$/, '').match(/^\/preventivi\/p\/([^/]+)$/i)
  if (pathMatch) return decodeURIComponent(pathMatch[1])
  const params = new URLSearchParams(window.location.search)
  return params.get('id_preventivo') || params.get('preventivo') || ''
}

function displayValue(value: string | number): string {
  if (typeof value === 'number') return new Intl.NumberFormat('it-IT').format(value)
  return value
}

function numericInputValue(value: string): number {
  const parsed = Number.parseFloat(value.replace(',', '.'))
  return Number.isFinite(parsed) ? parsed : 0
}

function nextHiddenWithCodice(current: Record<string, string>, codice: string): Record<string, string> {
  const source = codiceOggettoPstSource(codice)
  return {
    ...current,
    codice_oggetto_pst: codice,
    fonte_codice_oggetto: source.fonteCodiceOggetto,
    file_fonte_codice_oggetto: source.fileFonteCodiceOggetto,
  }
}

function voiceFromDefault(defaults: PreventiviFormDefaults): PreventivoVoiceRow[] {
  const rows = defaults.voci.map((voice, index) => ({
    rowId: `voce-${index + 1}`,
    descrizione: voice.descrizione,
    tipo: voice.tipo || 'ONORARIO',
    importo: voice.importo,
  }))
  return rows.length ? rows : [emptyVoice]
}

function preventivoState(defaults: PreventiviFormDefaults): PreventivoFormState {
  return {
    id_cliente: defaults.id_cliente,
    id_fascicolo: defaults.id_fascicolo,
    oggetto: defaults.oggetto,
    data_emissione: defaults.data_emissione,
    data_scadenza: defaults.data_scadenza,
    tipo_compenso: defaults.tipo_compenso,
    tipo_procedimento: defaults.tipo_procedimento,
    valore_controversia: defaults.valore_controversia,
    complessita: defaults.complessita,
    voci: voiceFromDefault(defaults),
    opzioni_fiscali: defaults.opzioni_fiscali || defaultFiscalOptions,
    note: defaults.note,
    hidden: defaults.hidden,
  }
}

function conferimentoState(defaults: PreventiviFormDefaults): ConferimentoFormState {
  return {
    id_cliente: defaults.id_cliente,
    id_fascicolo: defaults.id_fascicolo,
    id_preventivo: defaults.id_preventivo,
    oggetto: defaults.oggetto,
    avvocato_referente: defaults.avvocato_referente,
    numero_iscrizione_albo: defaults.numero_iscrizione_albo,
    ordine_avvocati: defaults.ordine_avvocati,
    data_incarico: defaults.data_incarico,
    tipo_compenso: defaults.tipo_compenso,
    tipo_procedimento: defaults.tipo_procedimento,
    compenso_pattuito: defaults.compenso_pattuito,
    informativa_art13_resa: true,
    clausola_adr_resa: true,
    apri_fascicolo_guidato: false,
    note: defaults.note,
    hidden: defaults.hidden,
  }
}

function errorsToRows(errors: Record<string, string>): string[] {
  return Object.entries(errors)
    .map(([field, message]) => `${field}: ${message}`)
    .filter(Boolean)
}

function WarningPanel({ data }: { data: PreventiviPageData }) {
  if (!data.warnings.length) return null
  return (
    <Panel title="Avvisi mandato">
      <div className="iu-prev-warnings">
        {data.warnings.map((warning) => (
          <div className="iu-prev-warning" key={`${warning.code}-${warning.message}`}>
            <Badge tone="warning">{warning.code}</Badge>
            <span>{warning.message}</span>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function ContractPanel({ data }: { data: PreventiviPageData }) {
  return (
    <Panel title="Presidio dati" subtitle="Scritture tracciate con fonte governata nei servizi di studio.">
      <div className="iu-prev-contract">
        <span>Origine: {displaySourceLabel(data.source || '')}</span>
        <span>Generato: {data.generated_at || 'non disponibile'}</span>
        <span>Azioni: {displayWritesLabel(data.contracts.writes || '')}</span>
        <span>Operativa: {data.contracts.operational ? 'si' : 'no'}</span>
        <span>Dati reali: {data.contracts.mock_fallback ? 'da verificare' : 'si'}</span>
      </div>
    </Panel>
  )
}

function StatusMessage({
  status,
  result,
  errors,
}: {
  status: SaveStatus
  result: CreatePreventivoResult | CreateConferimentoResult | null
  errors: Record<string, string>
}) {
  if (status === 'idle' || status === 'loading' || status === 'saving') return null
  if (status === 'success' && result?.item) {
    return (
      <section className="iu-prev-state iu-prev-state--success" aria-live="polite">
        <CheckCircle2 size={20} />
        <div>
          <strong>{result.message}</strong>
          <span>Elemento {result.item.number || result.item.id} salvato correttamente.</span>
        </div>
      </section>
    )
  }
  if (status === 'permission') {
    return (
      <section className="iu-prev-state iu-prev-state--danger" aria-live="polite">
        <XCircle size={20} />
        <div>
          <strong>Permesso negato</strong>
          <span>Serve un permesso operativo per salvare o aggiornare il mandato.</span>
        </div>
      </section>
    )
  }
  if (status === 'error') {
    return (
      <section className="iu-prev-state iu-prev-state--danger" aria-live="polite">
        <AlertTriangle size={20} />
        <div>
          <strong>Operazione non completata</strong>
          <span>{result?.message || 'Operazione non completata.'}</span>
        </div>
      </section>
    )
  }
  const rows = errorsToRows(errors)
  return (
    <section className="iu-prev-state iu-prev-state--warning" aria-live="polite">
      <AlertTriangle size={20} />
      <div>
        <strong>Controlla i campi evidenziati</strong>
        {rows.length ? rows.map((row) => <span key={row}>{sanitizeDisplayText(row)}</span>) : <span>La richiesta non e stata accettata.</span>}
      </div>
    </section>
  )
}

function TechnicalRollback({ href }: { href: string }) {
  return (
    <section className="iu-prev-rollback" aria-label="Percorso di recupero">
      <div>
        <strong>Percorso di recupero</strong>
        <span>Disponibile per assistenza e confronto con il template storico, non come flusso principale.</span>
      </div>
      <ButtonLink href={href} tone="warning">
        <ExternalLink size={15} />
        Apri template storico
      </ButtonLink>
    </section>
  )
}

function MetricGrid({ data }: { data: PreventiviPageData }) {
  if (!data.metrics.length) return null
  return (
    <section className="iu-prev-kpis" aria-label="Indicatori preventivi e incarichi">
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

function FiscalOptions({
  values,
  onChange,
}: {
  values: PreventivoFiscalOptions
  onChange: (values: PreventivoFiscalOptions) => void
}) {
  const options: Array<{ name: keyof PreventivoFiscalOptions; label: string }> = [
    { name: 'applica_cassa', label: 'Cassa Forense' },
    { name: 'applica_iva', label: 'IVA' },
    { name: 'applica_ritenuta', label: 'Ritenuta' },
  ]
  return (
    <div className="iu-prev-options" aria-label="Opzioni fiscali">
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

function VoiceEditor({
  rows,
  onChange,
}: {
  rows: PreventivoVoiceRow[]
  onChange: (rows: PreventivoVoiceRow[]) => void
}) {
  function updateRow(rowId: string, patch: Partial<PreventivoVoiceRow>) {
    onChange(rows.map((row) => (row.rowId === rowId ? { ...row, ...patch } : row)))
  }

  return (
    <div className="iu-prev-lines">
      <div className="iu-prev-lines__header">
        <strong>Voci preventivo</strong>
        <Button
          type="button"
          tone="neutral"
          className="iu-prev-icon-button"
          onClick={() => onChange([...rows, { ...emptyVoice, rowId: `voce-${Date.now()}-${rows.length}` }])}
          aria-label="Aggiungi voce"
          title="Aggiungi voce"
        >
          <Plus size={16} />
        </Button>
      </div>
      {rows.map((row) => (
        <div className="iu-prev-line" key={row.rowId}>
          <label className="iu-prev-field">
            <span>Descrizione</span>
            <input
              type="text"
              required
              value={row.descrizione}
              onChange={(event) => updateRow(row.rowId, { descrizione: event.currentTarget.value })}
              placeholder="Prestazione professionale"
            />
          </label>
          <label className="iu-prev-field">
            <span>Tipo voce</span>
            <select value={row.tipo} onChange={(event) => updateRow(row.rowId, { tipo: event.currentTarget.value })}>
              <option value="ONORARIO">Onorario</option>
              <option value="SPESE">Spese</option>
              <option value="ANTICIPAZIONE">Anticipazione</option>
            </select>
          </label>
          <label className="iu-prev-field">
            <span>Importo</span>
            <input
              type="number"
              min="0"
              step="0.01"
              value={row.importo}
              onChange={(event) => updateRow(row.rowId, { importo: event.currentTarget.value })}
            />
          </label>
          <Button
            type="button"
            tone="danger"
            className="iu-prev-icon-button"
            disabled={rows.length === 1}
            onClick={() => onChange(rows.filter((item) => item.rowId !== row.rowId))}
            aria-label="Rimuovi voce"
            title="Rimuovi voce"
          >
            <Trash2 size={16} />
          </Button>
        </div>
      ))}
    </div>
  )
}

function NewPreventivoForm({ data }: { data: PreventiviPageData }) {
  const [formState, setFormState] = useState<PreventivoFormState>(() => preventivoState(data.form.defaults || data.defaults))
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const [result, setResult] = useState<CreatePreventivoResult | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    setFormState(preventivoState(data.form.defaults || data.defaults))
    setSaveStatus('idle')
    setResult(null)
    setErrors({})
  }, [data.form, data.defaults])

  const filteredMatters = useMemo(
    () => data.matters.filter((matter) => !formState.id_cliente || matter.idCliente === formState.id_cliente),
    [data.matters, formState.id_cliente],
  )

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!data.permissions.canCreate) {
      setSaveStatus('permission')
      setErrors({ permission: 'Permesso di creazione preventivi mancante.' })
      return
    }
    setSaveStatus('saving')
    const payload: CreatePreventivoPayload = {
      ...formState.hidden,
      id_cliente: formState.id_cliente,
      id_fascicolo: formState.id_fascicolo,
      oggetto: formState.oggetto,
      data_emissione: formState.data_emissione,
      data_scadenza: formState.data_scadenza,
      tipo_compenso: formState.tipo_compenso,
      tipo_procedimento: formState.tipo_procedimento,
      valore_controversia: numericInputValue(formState.valore_controversia),
      complessita: formState.complessita,
      voci: formState.voci.map((row): PreventivoVoiceInput => ({
        descrizione: row.descrizione,
        tipo: row.tipo,
        importo: numericInputValue(row.importo),
      })),
      opzioni_fiscali: formState.opzioni_fiscali,
      note: formState.note,
    }
    const response = await createPreventivo(payload)
    setResult(response)
    setErrors(response.errors || {})
    if (response.ok) setSaveStatus('success')
    else if (response.status === 403 || response.errors?.permission) setSaveStatus('permission')
    else if (response.status && response.status >= 500) setSaveStatus('error')
    else setSaveStatus('validation')
  }

  if (!data.clients.length) {
    return (
      <Panel title="Nuovo preventivo" subtitle="La creazione richiede almeno un cliente reale.">
        <EmptyState
          title="Nessun cliente disponibile"
          message="Inserisci o sincronizza un cliente prima di creare un preventivo."
          action={<ButtonLink href="/clienti" tone="primary">Apri clienti</ButtonLink>}
        />
        <TechnicalRollback href="/preventivi/nuovo?_legacy=1" />
      </Panel>
    )
  }

  return (
    <Panel title="Form preventivo" subtitle="Salvataggio con validazione, permessi e audit.">
      <form className="iu-prev-operational" onSubmit={onSubmit}>
        <StatusMessage status={saveStatus} result={result} errors={errors} />
        <div className="iu-prev-form-grid">
          <label className="iu-prev-field">
            <span>Cliente</span>
            <select
              required
              value={formState.id_cliente}
              onChange={(event) => setFormState((current) => ({ ...current, id_cliente: event.currentTarget.value, id_fascicolo: '' }))}
            >
              <option value="">Seleziona cliente</option>
              {data.clients.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
            </select>
          </label>
          <label className="iu-prev-field">
            <span>Fascicolo</span>
            <select value={formState.id_fascicolo} onChange={(event) => setFormState((current) => ({ ...current, id_fascicolo: event.currentTarget.value }))}>
              <option value="">Nessun fascicolo collegato</option>
              {filteredMatters.map((matter) => <option value={matter.value} key={matter.value}>{matter.label}</option>)}
            </select>
          </label>
          <label className="iu-prev-field">
            <span>Data emissione</span>
            <input type="date" required value={formState.data_emissione} onChange={(event) => setFormState((current) => ({ ...current, data_emissione: event.currentTarget.value }))} />
          </label>
          <label className="iu-prev-field">
            <span>Scadenza</span>
            <input type="date" required value={formState.data_scadenza} onChange={(event) => setFormState((current) => ({ ...current, data_scadenza: event.currentTarget.value }))} />
          </label>
        </div>
        <label className="iu-prev-field">
          <span>Oggetto</span>
          <input type="text" required value={formState.oggetto} onChange={(event) => setFormState((current) => ({ ...current, oggetto: event.currentTarget.value }))} placeholder="Oggetto del mandato o della prestazione" />
        </label>
        <div className="iu-prev-form-grid">
          <label className="iu-prev-field">
            <span>Tipo compenso</span>
            <input type="text" value={formState.tipo_compenso} onChange={(event) => setFormState((current) => ({ ...current, tipo_compenso: event.currentTarget.value }))} placeholder="Fisso, a tempo, per fasi" />
          </label>
          <label className="iu-prev-field">
            <span>Tipo procedimento</span>
            <input type="text" value={formState.tipo_procedimento} onChange={(event) => setFormState((current) => ({ ...current, tipo_procedimento: event.currentTarget.value }))} placeholder="Materia o procedimento" />
          </label>
          <CodiceOggettoPstSearch
            value={formState.hidden.codice_oggetto_pst || ''}
            onChange={(codice, label) => setFormState((current) => ({
              ...current,
              tipo_procedimento: label || current.tipo_procedimento,
              hidden: nextHiddenWithCodice(current.hidden, codice),
            }))}
          />
          <label className="iu-prev-field">
            <span>Valore pratica</span>
            <input type="number" min="0" step="0.01" value={formState.valore_controversia} onChange={(event) => setFormState((current) => ({ ...current, valore_controversia: event.currentTarget.value }))} />
          </label>
          <label className="iu-prev-field">
            <span>Complessita</span>
            <input type="text" value={formState.complessita} onChange={(event) => setFormState((current) => ({ ...current, complessita: event.currentTarget.value }))} placeholder="Bassa, media, alta" />
          </label>
        </div>
        <VoiceEditor rows={formState.voci} onChange={(voci) => setFormState((current) => ({ ...current, voci }))} />
        <FiscalOptions values={formState.opzioni_fiscali} onChange={(opzioni_fiscali) => setFormState((current) => ({ ...current, opzioni_fiscali }))} />
        <label className="iu-prev-field">
          <span>Note</span>
          <textarea rows={4} value={formState.note} onChange={(event) => setFormState((current) => ({ ...current, note: event.currentTarget.value }))} placeholder="Note interne o condizioni da conservare nel preventivo" />
        </label>
        <section className="iu-prev-form-note" aria-label="Presidio operativo">
          <AlertTriangle size={17} />
          <span>Il sistema determina importi finali, parametri forensi, numerazione e persistenza.</span>
        </section>
        <div className="iu-prev-action-row">
          <Button type="submit" tone="primary" disabled={saveStatus === 'saving' || !data.permissions.canCreate}>
            {saveStatus === 'saving' ? <Save size={16} /> : <FileText size={16} />}
            {saveStatus === 'saving' ? 'Salvataggio in corso' : 'Crea preventivo'}
          </Button>
          <ButtonLink href="/preventivi" tone="neutral">Archivio</ButtonLink>
        </div>
        {saveStatus === 'success' ? (
          <div className="iu-prev-success-actions">
            <ButtonLink href="/preventivi" tone="primary">Torna all'archivio</ButtonLink>
            {result?.redirect_href ? <ButtonLink href={result.redirect_href} tone="neutral">Apri dettaglio</ButtonLink> : null}
          </div>
        ) : null}
      </form>
      <TechnicalRollback href="/preventivi/nuovo?_legacy=1" />
    </Panel>
  )
}

function NewConferimentoForm({ data }: { data: PreventiviPageData }) {
  const [formState, setFormState] = useState<ConferimentoFormState>(() => conferimentoState(data.form.defaults || data.defaults))
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const [result, setResult] = useState<CreateConferimentoResult | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    setFormState(conferimentoState(data.form.defaults || data.defaults))
    setSaveStatus('idle')
    setResult(null)
    setErrors({})
  }, [data.form, data.defaults])

  const filteredMatters = useMemo(
    () => data.matters.filter((matter) => !formState.id_cliente || matter.idCliente === formState.id_cliente),
    [data.matters, formState.id_cliente],
  )

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!data.permissions.canCreate) {
      setSaveStatus('permission')
      setErrors({ permission: 'Permesso di creazione conferimenti mancante.' })
      return
    }
    setSaveStatus('saving')
    const payload: CreateConferimentoPayload = {
      ...formState.hidden,
      id_cliente: formState.id_cliente,
      id_fascicolo: formState.id_fascicolo,
      id_preventivo: formState.id_preventivo,
      oggetto: formState.oggetto,
      avvocato_referente: formState.avvocato_referente,
      numero_iscrizione_albo: formState.numero_iscrizione_albo,
      ordine_avvocati: formState.ordine_avvocati,
      data_incarico: formState.data_incarico,
      tipo_compenso: formState.tipo_compenso,
      tipo_procedimento: formState.tipo_procedimento,
      compenso_pattuito: numericInputValue(formState.compenso_pattuito),
      informativa_art13_resa: formState.informativa_art13_resa,
      clausola_adr_resa: formState.clausola_adr_resa,
      apri_fascicolo_guidato: formState.apri_fascicolo_guidato,
      note: formState.note,
    }
    const response = await createConferimento(payload)
    setResult(response)
    setErrors(response.errors || {})
    if (response.ok) setSaveStatus('success')
    else if (response.status === 403 || response.errors?.permission) setSaveStatus('permission')
    else if (response.status && response.status >= 500) setSaveStatus('error')
    else setSaveStatus('validation')
  }

  if (!data.clients.length) {
    return (
      <Panel title="Nuovo conferimento" subtitle="La creazione richiede almeno un cliente reale.">
        <EmptyState
          title="Nessun cliente disponibile"
          message="Inserisci o sincronizza un cliente prima di creare un conferimento."
          action={<ButtonLink href="/clienti" tone="primary">Apri clienti</ButtonLink>}
        />
        <TechnicalRollback href="/preventivi/conferimento/nuovo?_legacy=1" />
      </Panel>
    )
  }

  return (
    <Panel title="Form conferimento incarico" subtitle="Salvataggio con validazione, permessi e audit.">
      <form className="iu-prev-operational" onSubmit={onSubmit}>
        <StatusMessage status={saveStatus} result={result} errors={errors} />
        <div className="iu-prev-form-grid">
          <label className="iu-prev-field">
            <span>Preventivo collegato</span>
            <select
              value={formState.id_preventivo}
              onChange={(event) => {
                const selected = data.estimates.find((estimate) => estimate.value === event.currentTarget.value)
                setFormState((current) => ({
                  ...current,
                  id_preventivo: event.currentTarget.value,
                  id_cliente: selected?.idCliente || current.id_cliente,
                }))
              }}
            >
              <option value="">Nessun preventivo collegato</option>
              {data.estimates.map((estimate) => <option value={estimate.value} key={estimate.value}>{estimate.label}</option>)}
            </select>
          </label>
          <label className="iu-prev-field">
            <span>Cliente</span>
            <select required value={formState.id_cliente} onChange={(event) => setFormState((current) => ({ ...current, id_cliente: event.currentTarget.value, id_fascicolo: '' }))}>
              <option value="">Seleziona cliente</option>
              {data.clients.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
            </select>
          </label>
          <label className="iu-prev-field">
            <span>Fascicolo</span>
            <select value={formState.id_fascicolo} onChange={(event) => setFormState((current) => ({ ...current, id_fascicolo: event.currentTarget.value }))}>
              <option value="">Nessun fascicolo collegato</option>
              {filteredMatters.map((matter) => <option value={matter.value} key={matter.value}>{matter.label}</option>)}
            </select>
          </label>
          <label className="iu-prev-field">
            <span>Data incarico</span>
            <input type="date" required value={formState.data_incarico} onChange={(event) => setFormState((current) => ({ ...current, data_incarico: event.currentTarget.value }))} />
          </label>
        </div>
        <label className="iu-prev-field">
          <span>Oggetto incarico</span>
          <input type="text" required value={formState.oggetto} onChange={(event) => setFormState((current) => ({ ...current, oggetto: event.currentTarget.value }))} placeholder="Oggetto del conferimento" />
        </label>
        <div className="iu-prev-form-grid">
          <label className="iu-prev-field">
            <span>Avvocato referente</span>
            <input type="text" required value={formState.avvocato_referente} onChange={(event) => setFormState((current) => ({ ...current, avvocato_referente: event.currentTarget.value }))} />
          </label>
          <label className="iu-prev-field">
            <span>Numero albo</span>
            <input type="text" value={formState.numero_iscrizione_albo} onChange={(event) => setFormState((current) => ({ ...current, numero_iscrizione_albo: event.currentTarget.value }))} />
          </label>
          <label className="iu-prev-field">
            <span>Ordine avvocati</span>
            <input type="text" value={formState.ordine_avvocati} onChange={(event) => setFormState((current) => ({ ...current, ordine_avvocati: event.currentTarget.value }))} />
          </label>
          <label className="iu-prev-field">
            <span>Compenso pattuito</span>
            <input type="number" min="0" step="0.01" value={formState.compenso_pattuito} onChange={(event) => setFormState((current) => ({ ...current, compenso_pattuito: event.currentTarget.value }))} />
          </label>
          <label className="iu-prev-field">
            <span>Tipo compenso</span>
            <input type="text" value={formState.tipo_compenso} onChange={(event) => setFormState((current) => ({ ...current, tipo_compenso: event.currentTarget.value }))} />
          </label>
          <label className="iu-prev-field">
            <span>Tipo procedimento</span>
            <input type="text" value={formState.tipo_procedimento} onChange={(event) => setFormState((current) => ({ ...current, tipo_procedimento: event.currentTarget.value }))} />
          </label>
          <CodiceOggettoPstSearch
            value={formState.hidden.codice_oggetto_pst || ''}
            onChange={(codice, label) => setFormState((current) => ({
              ...current,
              tipo_procedimento: label || current.tipo_procedimento,
              hidden: nextHiddenWithCodice(current.hidden, codice),
            }))}
          />
        </div>
        <div className="iu-prev-options" aria-label="Clausole e informative">
          <label>
            <input type="checkbox" checked={formState.informativa_art13_resa} onChange={(event) => setFormState((current) => ({ ...current, informativa_art13_resa: event.currentTarget.checked }))} />
            <span>Informativa art. 13 resa</span>
          </label>
          <label>
            <input type="checkbox" checked={formState.clausola_adr_resa} onChange={(event) => setFormState((current) => ({ ...current, clausola_adr_resa: event.currentTarget.checked }))} />
            <span>Clausola ADR resa</span>
          </label>
          <label>
            <input type="checkbox" checked={formState.apri_fascicolo_guidato} disabled={!data.permissions.canOpenMatterAfterSave} onChange={(event) => setFormState((current) => ({ ...current, apri_fascicolo_guidato: event.currentTarget.checked }))} />
            <span>Apertura fascicolo guidata</span>
          </label>
        </div>
        <label className="iu-prev-field">
          <span>Note incarico</span>
          <textarea rows={4} value={formState.note} onChange={(event) => setFormState((current) => ({ ...current, note: event.currentTarget.value }))} placeholder="Patti, condizioni o istruzioni da conservare nel conferimento" />
        </label>
        <section className="iu-prev-form-note" aria-label="Presidio operativo">
          <AlertTriangle size={17} />
          <span>Documento, firme e apertura fascicolo restano nei percorsi autorizzati.</span>
        </section>
        <div className="iu-prev-action-row">
          <Button type="submit" tone="primary" disabled={saveStatus === 'saving' || !data.permissions.canCreate}>
            {saveStatus === 'saving' ? <Save size={16} /> : <BriefcaseBusiness size={16} />}
            {saveStatus === 'saving' ? 'Salvataggio in corso' : 'Crea conferimento'}
          </Button>
          <ButtonLink href="/preventivi" tone="neutral">Archivio</ButtonLink>
        </div>
        {saveStatus === 'success' ? (
          <div className="iu-prev-success-actions">
            <ButtonLink href="/preventivi" tone="primary">Torna all'archivio</ButtonLink>
            {result?.redirect_href ? <ButtonLink href={result.redirect_href} tone="neutral">Apri dettaglio</ButtonLink> : null}
          </div>
        ) : null}
      </form>
      <TechnicalRollback href="/preventivi/conferimento/nuovo?_legacy=1" />
    </Panel>
  )
}

function DetailPanel({
  detail,
  status,
}: {
  detail: PreventivoDetail | null
  status: SaveStatus
}) {
  if (status === 'loading') return <LoadingState title="Caricamento dettaglio" message="Lettura della sintesi operativa." />
  if (!detail) return null
  return (
    <Panel title={`Dettaglio ${detail.number || detail.id}`} subtitle={detail.subject}>
      <div className="iu-prev-detail">
        <span>Cliente: {detail.customerName}</span>
        {detail.caseTitle ? <span>Fascicolo: {detail.caseTitle}</span> : null}
        <span>Stato: {detail.stateLabel}</span>
        <span>Importo: {detail.amountDisplay || 'non indicato'}</span>
      </div>
      {detail.voci.length ? (
        <div className="iu-prev-detail-lines">
          {detail.voci.map((voice, index) => (
            <div className="iu-prev-detail-line" key={`${voice.descrizione}-${index}`}>
              <span>{voice.descrizione}</span>
              <small>{voice.tipo}</small>
              <strong>{voice.importoDisplay}</strong>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState title="Nessuna voce di dettaglio" message="Non sono disponibili voci sintetiche per questo preventivo." />
      )}
    </Panel>
  )
}

function DetailFact({ label, value }: { label: string; value: string }) {
  if (!value) return null
  return (
    <div className="iu-prev-detail-fact">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function ConferimentoDetailView({
  detail,
  statuses,
  warnings,
  status,
  errors,
  onStatusUpdate,
}: {
  detail: ConferimentoDetail
  statuses: PreventiviPageData['statuses']
  warnings: PreventiviPageData['warnings']
  status: SaveStatus
  errors: Record<string, string>
  onStatusUpdate: (stato: string) => void
}) {
  const [nextStatus, setNextStatus] = useState(detail.state)

  useEffect(() => {
    setNextStatus(detail.state)
  }, [detail.state])

  return (
    <section className="iu-prev-detail-page" aria-label="Dettaglio conferimento incarico">
      <section className="iu-prev-banner">
        <div>
          <BriefcaseBusiness size={22} />
          <strong>Conferimento {detail.number || detail.id}</strong>
          <span>{detail.subject}</span>
        </div>
        <Badge tone={detail.stateTone}>{detail.stateLabel}</Badge>
      </section>

      {status === 'permission' || status === 'validation' || status === 'error' ? (
        <StatusMessage status={status} result={null} errors={errors} />
      ) : null}
      {status === 'success' ? (
        <section className="iu-prev-state iu-prev-state--success" aria-live="polite">
          <CheckCircle2 size={20} />
          <div>
            <strong>Stato aggiornato</strong>
            <span>Il conferimento e stato aggiornato correttamente.</span>
          </div>
        </section>
      ) : null}

      {warnings.length ? (
        <Panel title="Avvisi incarico">
          <div className="iu-prev-warnings">
            {warnings.map((warning) => (
              <div className="iu-prev-warning" key={`${warning.code}-${warning.message}`}>
                <Badge tone="warning">{warning.code}</Badge>
                <span>{warning.message}</span>
              </div>
            ))}
          </div>
        </Panel>
      ) : null}

      <section className="iu-prev-detail-layout">
        <Panel title="Quadro incarico" subtitle="Dati principali letti dall'archivio mandato.">
          <div className="iu-prev-detail-facts">
            <DetailFact label="Cliente" value={detail.customerName} />
            <DetailFact label="Fascicolo" value={detail.caseTitle || 'Da collegare'} />
            <DetailFact label="Compenso pattuito" value={detail.amountDisplay || 'Non indicato'} />
            <DetailFact label="Data incarico" value={detail.engagementAt || 'Non indicata'} />
            <DetailFact label="Avvocato referente" value={detail.lawyer || 'Non indicato'} />
            <DetailFact label="Ordine" value={detail.barCouncil} />
            <DetailFact label="Numero albo" value={detail.barNumber} />
            <DetailFact label="Tipo compenso" value={detail.compensationType} />
            <DetailFact label="Tipo procedimento" value={detail.proceedingType} />
            <DetailFact label="Preventivo collegato" value={detail.preventivoNumber || detail.preventivoId || 'Non collegato'} />
            <DetailFact label="Firma cliente" value={detail.signed ? `Registrata${detail.signedAt ? ` il ${detail.signedAt}` : ''}` : 'Da registrare'} />
          </div>
          {detail.notes ? <p className="iu-prev-detail-note">{detail.notes}</p> : null}
        </Panel>

        <Panel title="Azioni operative" subtitle="Collegamenti sicuri senza uscire dal flusso di studio.">
          <div className="iu-prev-detail-actions">
            {detail.pdfHref ? <ButtonLink href={detail.pdfHref} tone="primary"><Download size={15} />PDF conferimento</ButtonLink> : null}
            {detail.customerHref ? <ButtonLink href={detail.customerHref} tone="neutral"><ExternalLink size={15} />Apri cliente</ButtonLink> : null}
            {detail.matterHref ? <ButtonLink href={detail.matterHref} tone="neutral"><ExternalLink size={15} />Apri fascicolo</ButtonLink> : null}
            {!detail.matterHref && detail.newMatterHref ? <ButtonLink href={detail.newMatterHref} tone="primary"><Plus size={15} />Apri fascicolo</ButtonLink> : null}
            {detail.completeCustomerHref ? <ButtonLink href={detail.completeCustomerHref} tone="warning"><AlertTriangle size={15} />Completa cliente</ButtonLink> : null}
            {detail.preventivoHref ? <ButtonLink href="/preventivi" tone="neutral"><FileText size={15} />Archivio preventivi</ButtonLink> : null}
          </div>
          {statuses.length ? (
            <div className="iu-prev-status-action iu-prev-status-action--detail">
              <select value={nextStatus} onChange={(event) => setNextStatus(event.currentTarget.value)} aria-label="Nuovo stato conferimento">
                {statuses.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
              </select>
              <Button type="button" tone="neutral" disabled={status === 'saving' || nextStatus === detail.state} onClick={() => onStatusUpdate(nextStatus)}>
                {status === 'saving' ? 'Aggiornamento' : 'Aggiorna stato'}
              </Button>
            </div>
          ) : null}
        </Panel>
      </section>

      <section className="iu-prev-grid" aria-label="Percorso conferimento">
        <Panel title="Presidi incarico" subtitle="Stato operativo di cliente, firma, fascicolo e preventivo.">
          <div className="iu-prev-section-list">
            {detail.workflow.map((item) => (
              <div className="iu-prev-section-item" key={item.id}>
                <span>{item.label}</span>
                <strong>{displayValue(item.value)}</strong>
                {item.note ? <small>{item.note}</small> : null}
                <Badge tone={item.tone}>{item.tone}</Badge>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="Clausole e informative" subtitle="Presidi collegati al conferimento.">
          <div className="iu-prev-section-list">
            <div className="iu-prev-section-item"><span>Informativa art. 13</span><strong>{detail.clauses.informativaArt13 ? 'Resa' : 'Da completare'}</strong><Badge tone={detail.clauses.informativaArt13 ? 'success' : 'warning'}>{detail.clauses.informativaArt13 ? 'ok' : 'attenzione'}</Badge></div>
            <div className="iu-prev-section-item"><span>Clausola ADR</span><strong>{detail.clauses.clausolaAdr ? 'Resa' : 'Da completare'}</strong><Badge tone={detail.clauses.clausolaAdr ? 'success' : 'warning'}>{detail.clauses.clausolaAdr ? 'ok' : 'attenzione'}</Badge></div>
            <div className="iu-prev-section-item"><span>Clausola controversie</span><strong>{detail.clauses.controversie ? 'Attiva' : 'Non attiva'}</strong><Badge tone={detail.clauses.controversie ? 'info' : 'neutral'}>{detail.clauses.controversie ? 'attiva' : 'neutra'}</Badge></div>
          </div>
        </Panel>
      </section>
    </section>
  )
}

function RecordRow({
  record,
  data,
  onDetail,
  onStatus,
  savingId,
}: {
  record: PreventivoRow
  data: PreventiviPageData
  onDetail: (record: PreventivoRow) => void
  onStatus: (record: PreventivoRow, stato: string) => void
  savingId: string
}) {
  const [nextStatus, setNextStatus] = useState(record.state)
  const isPreventivo = record.kind === 'preventivo'
  const kindLabel = record.kind === 'conferimento' ? 'Conferimento' : 'Preventivo'
  const dateLabel = record.kind === 'conferimento'
    ? `Incarico ${record.engagementAt || 'non indicato'}`
    : `Emissione ${record.issuedAt || 'non indicata'}`
  return (
    <article className="iu-prev-record">
      <div className="iu-prev-record__main">
        <span>{kindLabel} {record.number || record.id}</span>
        <strong>{record.subject}</strong>
        <small>{record.customerName}</small>
        {record.caseTitle ? <small>{record.caseTitle}</small> : null}
      </div>
      <div className="iu-prev-record__meta">
        <span>{dateLabel}</span>
        {record.dueAt ? <span>Scadenza {record.dueAt}</span> : null}
      </div>
      <div className="iu-prev-record__amount">
        <strong>{record.amountDisplay || 'Importo non indicato'}</strong>
        <Badge tone={record.stateTone}>{record.stateLabel}</Badge>
      </div>
      <div className="iu-prev-record__actions">
        {isPreventivo ? (
          <Button type="button" tone="neutral" onClick={() => onDetail(record)}>
            <Search size={15} />
            Dettaglio operativo
          </Button>
        ) : record.detailHref ? (
          <ButtonLink href={record.detailHref} tone="neutral">
            <ExternalLink size={15} />
            Dettaglio
          </ButtonLink>
        ) : null}
        {isPreventivo && data.permissions.canUpdateStatus ? (
          <div className="iu-prev-status-action">
            <select value={nextStatus} onChange={(event) => setNextStatus(event.currentTarget.value)} aria-label="Nuovo stato preventivo">
              {data.statuses.map((status) => <option value={status.value} key={status.value}>{status.label}</option>)}
            </select>
            <Button type="button" tone="neutral" disabled={savingId === record.id || nextStatus === record.state} onClick={() => onStatus(record, nextStatus)}>
              {savingId === record.id ? 'Aggiornamento' : 'Aggiorna'}
            </Button>
          </div>
        ) : null}
        {record.kind === 'preventivo' && data.permissions.canCreateConferimento ? (
          <ButtonLink href={`/preventivi/conferimento/nuovo?id_preventivo=${encodeURIComponent(record.id)}`} tone="neutral">
            <BriefcaseBusiness size={15} />
            Conferimento
          </ButtonLink>
        ) : null}
      </div>
    </article>
  )
}

function RecordsPanel({ data, onReload }: { data: PreventiviPageData; onReload: (data: PreventiviPageData) => void }) {
  const [query, setQuery] = useState('')
  const [detail, setDetail] = useState<PreventivoDetail | null>(null)
  const [detailStatus, setDetailStatus] = useState<SaveStatus>('idle')
  const [mutationStatus, setMutationStatus] = useState<SaveStatus>('idle')
  const [mutationErrors, setMutationErrors] = useState<Record<string, string>>({})
  const [savingId, setSavingId] = useState('')
  const [autoOpenedId, setAutoOpenedId] = useState('')
  const lowered = query.trim().toLowerCase()
  const requestedPreventivoId = preventivoIdFromLocation()
  const filtered = data.records.filter((record) => {
    if (!lowered) return true
    return [record.number, record.subject, record.customerName, record.caseTitle, record.stateLabel]
      .join(' ')
      .toLowerCase()
      .includes(lowered)
  })

  async function loadDetail(record: PreventivoRow) {
    setDetailStatus('loading')
    setDetail(null)
    const response = await getPreventivoDetail(record.id)
    if (response.ok) {
      setDetail(response.item)
      setDetailStatus('success')
    } else {
      setDetailStatus('error')
      setMutationErrors(response.errors || { detail: response.message || 'Dettaglio non disponibile.' })
    }
  }

  useEffect(() => {
    if (!requestedPreventivoId || autoOpenedId === requestedPreventivoId) return
    const record = data.records.find((item) => item.kind === 'preventivo' && item.id === requestedPreventivoId)
    if (!record) return
    setAutoOpenedId(requestedPreventivoId)
    setQuery(record.number || record.subject || '')
    loadDetail(record)
  }, [autoOpenedId, data.records, requestedPreventivoId])

  async function mutateStatus(record: PreventivoRow, stato: string) {
    setSavingId(record.id)
    setMutationStatus('saving')
    setMutationErrors({})
    const response = await updatePreventivoStatus(record.id, { stato })
    if (response.ok) {
      const refreshed = await getPreventiviPage()
      onReload(refreshed)
      setMutationStatus('success')
    } else if (response.status === 403 || response.errors?.permission) {
      setMutationStatus('permission')
      setMutationErrors(response.errors || {})
    } else {
      setMutationStatus('validation')
      setMutationErrors(response.errors || {})
    }
    setSavingId('')
  }

  if (!data.records.length) {
    return (
      <EmptyState
        title="Nessun preventivo o incarico in archivio"
        message="Quando saranno disponibili dati reali, compariranno qui con cliente, fascicolo, stato e importi gia determinati dal sistema."
        action={<ButtonLink href="/preventivi/wizard" tone="primary">Preventivo guidato</ButtonLink>}
      />
    )
  }

  return (
    <section className="iu-prev-records" aria-label="Archivio preventivi e conferimenti">
      <Panel
        title="Archivio preventivi e incarichi"
        subtitle={`${filtered.length} elementi visualizzati su ${data.records.length}`}
        actions={(
          <div className="iu-prev-action-row">
            <ButtonLink href="/preventivi/wizard" tone="primary">Preventivo guidato</ButtonLink>
            <ButtonLink href="/preventivi/nuovo" tone="neutral">Nuovo preventivo</ButtonLink>
          </div>
        )}
      >
        <label className="iu-prev-search">
          <Search size={16} />
          <input value={query} onChange={(event) => setQuery(event.currentTarget.value)} placeholder="Cerca per cliente, oggetto, fascicolo o stato" />
        </label>
        {mutationStatus === 'permission' || mutationStatus === 'validation' || mutationStatus === 'error' ? (
          <StatusMessage status={mutationStatus} result={null} errors={mutationErrors} />
        ) : null}
        {mutationStatus === 'success' ? (
          <section className="iu-prev-state iu-prev-state--success" aria-live="polite">
            <CheckCircle2 size={20} />
            <div>
              <strong>Stato aggiornato</strong>
              <span>Stato aggiornato correttamente.</span>
            </div>
          </section>
        ) : null}
        <div className="iu-prev-list">
          {filtered.length ? filtered.map((record) => (
            <RecordRow
              record={record}
              data={data}
              onDetail={loadDetail}
              onStatus={mutateStatus}
              savingId={savingId}
              key={`${record.kind}-${record.id || record.number}`}
            />
          )) : (
            <EmptyState title="Nessun risultato" message="La ricerca locale non ha trovato elementi nell'elenco disponibile." />
          )}
        </div>
      </Panel>
      <DetailPanel detail={detail} status={detailStatus} />
    </section>
  )
}

function SectionSummary({ data }: { data: PreventiviPageData }) {
  const sections = data.sections.filter((section) => section.items.length)
  if (!sections.length) return null
  return (
    <section className="iu-prev-grid" aria-label="Stati e funzioni conservate">
      {sections.map((section) => (
        <Panel title={section.title} subtitle={section.emptyMessage} key={section.id}>
          <div className="iu-prev-section-list">
            {section.items.map((item) => (
              <div className="iu-prev-section-item" key={item.id}>
                <span>{item.label}</span>
                <strong>{displayValue(item.value)}</strong>
                {item.note ? <small>{item.note}</small> : null}
                <Badge tone={item.tone}>{item.tone}</Badge>
              </div>
            ))}
          </div>
        </Panel>
      ))}
    </section>
  )
}

function ArchiveView({ data, onReload }: { data: PreventiviPageData; onReload: (data: PreventiviPageData) => void }) {
  return (
    <>
      <section className="iu-prev-banner">
        <div>
          <FileText size={22} />
          <strong>Archivio preventivi operativo</strong>
          <span>Elenco, indicatori, dettaglio sintetico e stato preventivo sono tracciati; documenti e percorsi avanzati restano governati.</span>
        </div>
        <ButtonLink href="/preventivi/wizard" tone="primary"><BriefcaseBusiness size={16} />Preventivo guidato</ButtonLink>
      </section>
      <MetricGrid data={data} />
      <WarningPanel data={data} />
      <RecordsPanel data={data} onReload={onReload} />
      <SectionSummary data={data} />
      <ContractPanel data={data} />
      <TechnicalRollback href="/preventivi?_legacy=1" />
    </>
  )
}

function FormActions({ mode }: { mode: PageMode }) {
  return (
    <div className="iu-prev-actions">
      <ButtonLink href="/preventivi" tone="neutral">Archivio</ButtonLink>
      <ButtonLink href="/preventivi/wizard" tone="primary">Preventivo guidato</ButtonLink>
      {mode !== 'new-preventivo' ? <ButtonLink href="/preventivi/nuovo" tone="neutral">Nuovo preventivo</ButtonLink> : null}
      {mode !== 'new-conferimento' ? <ButtonLink href="/preventivi/conferimento/nuovo" tone="neutral">Nuovo conferimento</ButtonLink> : null}
    </div>
  )
}

export function PreventiviPage() {
  const [mode] = useState<PageMode>(() => modeFromPath())
  const [data, setData] = useState<PreventiviPageData>(emptyPreventiviPage)
  const [conferimentoDetail, setConferimentoDetail] = useState<ConferimentoDetail | null>(null)
  const [conferimentoStatuses, setConferimentoStatuses] = useState<PreventiviPageData['statuses']>([])
  const [conferimentoWarnings, setConferimentoWarnings] = useState<PreventiviPageData['warnings']>([])
  const [detailStatus, setDetailStatus] = useState<SaveStatus>('idle')
  const [detailErrors, setDetailErrors] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  useEffect(() => {
    let active = true
    if (mode === 'detail-conferimento') {
      const idConferimento = detailIdFromPath()
      setLoading(true)
      setLoadError('')
      setConferimentoDetail(null)
      setDetailStatus('idle')
      setDetailErrors({})
      if (!idConferimento) {
        setLoadError('Conferimento non indicato.')
        setLoading(false)
        return () => {
          active = false
        }
      }
      getConferimentoDetail(idConferimento)
        .then((payload) => {
          if (!active) return
          setConferimentoDetail(payload.item)
          setConferimentoStatuses(payload.statuses)
          setConferimentoWarnings(payload.warnings)
          if (!payload.ok) {
            setLoadError(payload.message || 'Conferimento non disponibile.')
            setDetailErrors(payload.errors)
          }
        })
        .catch(() => {
          if (active) setLoadError('Errore nel caricamento del conferimento.')
        })
        .finally(() => {
          if (active) setLoading(false)
        })
      return () => {
        active = false
      }
    }
    const loader = mode === 'new-preventivo'
      ? getNuovoPreventivoPage
      : mode === 'new-conferimento'
        ? getNuovoConferimentoPage
        : getPreventiviPage
    setLoading(true)
    setLoadError('')
    loader()
      .then((payload) => {
        if (!active) return
        setData(payload)
        if (payload.ok === false && payload.warnings.length) {
          setLoadError(payload.warnings[0]?.message || 'Dati non disponibili.')
        }
      })
      .catch(() => {
        if (active) setLoadError('Errore nel caricamento dei dati preventivi.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [mode])

  async function handleConferimentoStatus(stato: string) {
    if (!conferimentoDetail) return
    setDetailStatus('saving')
    setDetailErrors({})
    const response = await updateConferimentoStatus(conferimentoDetail.id, { stato })
    if (response.ok) {
      const refreshed = await getConferimentoDetail(conferimentoDetail.id)
      setConferimentoDetail(refreshed.item)
      setConferimentoStatuses(refreshed.statuses)
      setConferimentoWarnings(refreshed.warnings)
      setDetailStatus('success')
    } else if (response.status === 403 || response.errors?.permission) {
      setDetailStatus('permission')
      setDetailErrors(response.errors || {})
    } else if (response.status && response.status >= 500) {
      setDetailStatus('error')
      setDetailErrors(response.errors || {})
    } else {
      setDetailStatus('validation')
      setDetailErrors(response.errors || {})
    }
  }

  const title = mode === 'new-preventivo'
    ? 'Nuovo preventivo'
    : mode === 'new-conferimento'
      ? 'Nuovo conferimento incarico'
      : mode === 'detail-conferimento'
        ? 'Conferimento incarico'
      : 'Preventivi e incarichi'
  const subtitle = mode === 'archive'
    ? 'Archivio mandato con indicatori, stati, dettaglio operativo e collegamenti reali.'
    : mode === 'detail-conferimento'
      ? 'Dettaglio operativo con cliente, fascicolo, firma, PDF e stato incarico.'
    : 'Pagina operativa con salvataggio validato e fonte dati governata.'
  const hasData = mode === 'detail-conferimento'
    ? Boolean(conferimentoDetail)
    : data.records.length > 0 || data.clients.length > 0 || data.metrics.length > 0 || data.sections.some((section) => section.items.length > 0)

  return (
    <Page title={title} subtitle={subtitle} actions={<FormActions mode={mode} />}>
      {loading ? <LoadingState title={mode === 'detail-conferimento' ? 'Caricamento conferimento' : 'Caricamento preventivi'} message="Recupero dati reali da clienti e fascicoli." /> : null}
      {!loading && loadError ? (
        <section className="iu-prev-state iu-prev-state--danger" aria-live="polite">
          <AlertTriangle size={20} />
          <div>
            <strong>Dati non disponibili</strong>
            <span>{loadError}</span>
          </div>
        </section>
      ) : null}
      {!loading && !loadError && !hasData ? (
        <EmptyState
          title="Nessun dato mandato disponibile"
          message="Non sono disponibili dati visualizzabili per questa superficie."
          action={<ButtonLink href="/clienti" tone="primary">Apri clienti</ButtonLink>}
        />
      ) : null}
      {!loading && !loadError && hasData ? (
        mode === 'new-preventivo' ? (
          <>
            <WarningPanel data={data} />
            <NewPreventivoForm data={data} />
            <ContractPanel data={data} />
          </>
        ) : mode === 'new-conferimento' ? (
          <>
            <WarningPanel data={data} />
            <NewConferimentoForm data={data} />
            <ContractPanel data={data} />
          </>
        ) : mode === 'detail-conferimento' && conferimentoDetail ? (
          <ConferimentoDetailView
            detail={conferimentoDetail}
            statuses={conferimentoStatuses}
            warnings={conferimentoWarnings}
            status={detailStatus}
            errors={detailErrors}
            onStatusUpdate={handleConferimentoStatus}
          />
        ) : (
          <ArchiveView data={data} onReload={setData} />
        )
      ) : null}
    </Page>
  )
}
