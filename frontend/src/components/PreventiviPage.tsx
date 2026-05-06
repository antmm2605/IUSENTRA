import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, BriefcaseBusiness, CalendarDays, ExternalLink, FileText, Plus, Trash2 } from 'lucide-react'
import {
  emptyPreventiviPage,
  getNuovoConferimentoPage,
  getNuovoPreventivoPage,
  getPreventiviPage,
  type PreventiviFormDefinition,
  type PreventiviPageData,
  type PreventiviRecord,
} from '../preventiviData'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LegacyPostForm } from '../ui/LegacyPostForm'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import type { LegacyPostField } from '../ui/LegacyPostForm'
import './PreventiviPage.css'

type PageMode = 'archive' | 'new-preventivo' | 'new-conferimento'

const fallbackPreventivo: PreventiviFormDefinition = {
  id: 'nuovo_preventivo',
  title: 'Nuovo preventivo',
  description: 'Il form invia alla route Flask esistente.',
  action: '/preventivi/nuovo',
  method: 'POST',
  submitLabel: 'Crea preventivo',
  enabled: true,
  fields: [],
  defaults: emptyPreventiviPage.forms[0]?.defaults || {
    subject: '',
    issuedAt: '',
    dueAt: '',
    engagementAt: '',
    lawyer: '',
    amount: '',
    hourly: '',
    note: '',
    lineDescription: '',
    lineAmount: '',
    lineType: 'ONORARIO',
    withFund: true,
    withVat: true,
    practiceKind: '',
    feeKind: '',
    value: '',
    complexity: '',
    barNumber: '',
    barCouncil: '',
    openCaseGuided: false,
    art13Notice: true,
    adrClause: true,
  },
}

const fallbackConferimento: PreventiviFormDefinition = {
  ...fallbackPreventivo,
  id: 'nuovo_conferimento',
  title: 'Nuovo conferimento incarico',
  action: '/preventivi/conferimento/nuovo',
  submitLabel: 'Crea conferimento',
}

function modeFromPath(): PageMode {
  const path = window.location.pathname.replace(/\/+$/, '').toLowerCase() || '/preventivi'
  if (path === '/preventivi/nuovo') return 'new-preventivo'
  if (path === '/preventivi/conferimento/nuovo') return 'new-conferimento'
  return 'archive'
}

function displayValue(value: string | number): string {
  if (typeof value === 'number') return new Intl.NumberFormat('it-IT').format(value)
  return value
}

function fieldByName(form: PreventiviFormDefinition | undefined, name: string): LegacyPostField | undefined {
  return form?.fields.find((field) => field.name === name)
}

function hiddenFields(form: PreventiviFormDefinition | undefined): LegacyPostField[] {
  return (form?.fields || []).filter((field) => field.type === 'hidden')
}

function SelectField({
  field,
  label,
  name,
  required = false,
  emptyLabel,
}: {
  field: LegacyPostField | undefined
  label: string
  name: string
  required?: boolean
  emptyLabel: string
}) {
  const options = field?.options?.length ? field.options : [{ value: '', label: emptyLabel }]
  return (
    <label className="iu-prev-field">
      <span>{label}</span>
      <select name={name} required={required} defaultValue={field?.value || ''}>
        {options.map((option) => (
          <option value={option.value} key={option.value || option.label}>
            {option.description ? `${option.label} - ${option.description}` : option.label}
          </option>
        ))}
      </select>
    </label>
  )
}

function HiddenFields({ form }: { form: PreventiviFormDefinition | undefined }) {
  const fields = useMemo(() => hiddenFields(form), [form])
  return (
    <>
      {fields.map((field) => (
        <input type="hidden" name={field.name} value={field.value || ''} key={field.name} />
      ))}
    </>
  )
}

function ContractPanel({ data }: { data: PreventiviPageData }) {
  return (
    <Panel title="Contratto dati" subtitle="Superficie React read-only con scritture su route Flask esistenti.">
      <div className="iu-prev-contract">
        <span>Fonte: {data.source || 'non indicata'}</span>
        <span>Generato: {data.generated_at || 'non disponibile'}</span>
        <span>Scritture: {data.contracts.writes}</span>
        <span>Owner route: {data.contracts.route_owner}</span>
        <span>Mock fallback: {data.contracts.mock_fallback ? 'si' : 'no'}</span>
      </div>
    </Panel>
  )
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

function MetricGrid({ data }: { data: PreventiviPageData }) {
  if (!data.metrics.length) return null
  return (
    <section className="iu-prev-kpis" aria-label="KPI preventivi e incarichi">
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

function ActionStrip({ data }: { data: PreventiviPageData }) {
  const actions = data.actions.filter((action) => action.href)
  if (!actions.length) return null
  return (
    <div className="iu-prev-actions" aria-label="Azioni preventivi">
      {actions.map((action) => (
        <ButtonLink href={action.href} tone={action.tone === 'primary' ? 'primary' : 'neutral'} key={action.id}>
          <ExternalLink size={15} />
          {action.label}
        </ButtonLink>
      ))}
    </div>
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

function RecordRow({ record }: { record: PreventiviRecord }) {
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
        {record.detailHref ? (
          <ButtonLink href={record.detailHref} tone="neutral">
            <ExternalLink size={15} />
            Dettaglio operativo
          </ButtonLink>
        ) : null}
        {record.wizardHref ? (
          <ButtonLink href={record.wizardHref} tone="neutral">
            <BriefcaseBusiness size={15} />
            Wizard compensi
          </ButtonLink>
        ) : null}
      </div>
    </article>
  )
}

function RecordsPanel({ data }: { data: PreventiviPageData }) {
  const preventivi = data.records.filter((record) => record.kind === 'preventivo')
  const conferimenti = data.records.filter((record) => record.kind === 'conferimento')
  if (!data.records.length) {
    return (
      <EmptyState
        title="Nessun preventivo o incarico in archivio"
        message="Quando il backend avra dati reali, compariranno qui con cliente, fascicolo, stato e importi gia determinati dal sistema."
        action={<ButtonLink href="/preventivi/nuovo">Nuovo preventivo</ButtonLink>}
      />
    )
  }
  return (
    <section className="iu-prev-records" aria-label="Archivio preventivi e conferimenti">
      <Panel title="Archivio preventivi" subtitle="Elenco reale dei preventivi con stati e collegamenti operativi.">
        <div className="iu-prev-list">
          {preventivi.length ? preventivi.map((record) => <RecordRow record={record} key={`p-${record.id}`} />) : (
            <EmptyState title="Nessun preventivo" message="Non risultano preventivi nell'archivio corrente." />
          )}
        </div>
      </Panel>
      <Panel title="Conferimenti incarico" subtitle="Incarichi visibili nel repository preventivi.">
        <div className="iu-prev-list">
          {conferimenti.length ? conferimenti.map((record) => <RecordRow record={record} key={`c-${record.id}`} />) : (
            <EmptyState title="Nessun conferimento" message="Non risultano conferimenti incarico nell'archivio corrente." />
          )}
        </div>
      </Panel>
    </section>
  )
}

function NewPreventivoForm({ form }: { form: PreventiviFormDefinition | undefined }) {
  const effectiveForm = form || fallbackPreventivo
  const [voiceRows, setVoiceRows] = useState(['voce-1'])
  const defaults = effectiveForm.defaults
  const customerField = fieldByName(effectiveForm, 'id_cliente')
  const caseField = fieldByName(effectiveForm, 'id_fascicolo')

  return (
    <Panel title="Form preventivo" subtitle="Invio standard al POST Flask con sessione corrente.">
      <LegacyPostForm
        action={effectiveForm.action || '/preventivi/nuovo'}
        title={effectiveForm.title}
        description={effectiveForm.description || 'La determinazione finale resta nel backend.'}
        submitLabel={effectiveForm.submitLabel || 'Crea preventivo'}
        fields={[]}
        disabled={effectiveForm.enabled === false}
      >
        <HiddenFields form={effectiveForm} />
        <div className="iu-prev-form-grid">
          <SelectField field={customerField} label="Cliente" name="id_cliente" required emptyLabel="Seleziona cliente" />
          <SelectField field={caseField} label="Fascicolo" name="id_fascicolo" emptyLabel="Nessun fascicolo collegato" />
          <label className="iu-prev-field">
            <span>Data emissione</span>
            <input type="date" name="data_emissione" defaultValue={defaults.issuedAt} />
          </label>
          <label className="iu-prev-field">
            <span>Scadenza</span>
            <input type="date" name="data_scadenza" defaultValue={defaults.dueAt} />
          </label>
        </div>
        <label className="iu-prev-field">
          <span>Oggetto</span>
          <input type="text" name="oggetto" required defaultValue={defaults.subject} placeholder="Oggetto del mandato o della prestazione" />
        </label>
        <div className="iu-prev-form-grid">
          <label className="iu-prev-field">
            <span>Tipo compenso</span>
            <input type="text" name="tipo_compenso" defaultValue={defaults.feeKind} placeholder="Fisso, a tempo, per fasi" />
          </label>
          <label className="iu-prev-field">
            <span>Tipo procedimento</span>
            <input type="text" name="tipo_procedimento" defaultValue={defaults.practiceKind} placeholder="Materia o procedimento" />
          </label>
          <label className="iu-prev-field">
            <span>Valore pratica</span>
            <input type="number" name="valore_controversia" min="0" step="0.01" defaultValue={defaults.value} />
          </label>
          <label className="iu-prev-field">
            <span>Complessita</span>
            <input type="text" name="complessita" defaultValue={defaults.complexity} placeholder="Bassa, media, alta" />
          </label>
        </div>
        <div className="iu-prev-lines">
          <div className="iu-prev-lines__header">
            <strong>Voci preventivo</strong>
            <Button
              type="button"
              tone="neutral"
              className="iu-prev-icon-button"
              onClick={() => setVoiceRows((current) => [...current, `voce-${Date.now()}-${current.length}`])}
              aria-label="Aggiungi voce"
            >
              <Plus size={16} />
            </Button>
          </div>
          {voiceRows.map((row, index) => (
            <div className="iu-prev-line" key={row}>
              <label className="iu-prev-field">
                <span>Descrizione</span>
                <input
                  type="text"
                  name="voce_descr[]"
                  required
                  defaultValue={index === 0 ? defaults.lineDescription : ''}
                  placeholder="Prestazione professionale"
                />
              </label>
              <label className="iu-prev-field">
                <span>Tipo voce</span>
                <select name="voce_tipo[]" defaultValue={index === 0 ? defaults.lineType : 'ONORARIO'}>
                  <option value="ONORARIO">Onorario</option>
                  <option value="SPESE">Spese</option>
                  <option value="ANTICIPAZIONE">Anticipazione art. 15</option>
                </select>
              </label>
              <label className="iu-prev-field">
                <span>Importo</span>
                <input type="number" name="voce_importo[]" min="0" step="0.01" defaultValue={index === 0 ? defaults.lineAmount : ''} />
              </label>
              <Button
                type="button"
                tone="danger"
                className="iu-prev-icon-button"
                disabled={voiceRows.length === 1}
                onClick={() => setVoiceRows((current) => current.filter((item) => item !== row))}
                aria-label="Rimuovi voce"
              >
                <Trash2 size={16} />
              </Button>
            </div>
          ))}
        </div>
        <div className="iu-prev-options">
          <label><input type="checkbox" name="applica_cassa" value="1" defaultChecked={defaults.withFund} /> Cassa Forense</label>
          <label><input type="checkbox" name="applica_iva" value="1" defaultChecked={defaults.withVat} /> IVA</label>
        </div>
        <label className="iu-prev-field">
          <span>Note</span>
          <textarea name="note" rows={4} defaultValue={defaults.note} placeholder="Note interne o condizioni da conservare nel preventivo" />
        </label>
        <section className="iu-prev-form-note" aria-label="Presidio backend">
          <AlertTriangle size={17} />
          <span>Il risultato economico finale, le stampe e i workflow restano nei percorsi Flask auditati.</span>
        </section>
      </LegacyPostForm>
    </Panel>
  )
}

function NewConferimentoForm({ form }: { form: PreventiviFormDefinition | undefined }) {
  const effectiveForm = form || fallbackConferimento
  const defaults = effectiveForm.defaults
  const customerField = fieldByName(effectiveForm, 'id_cliente')
  const caseField = fieldByName(effectiveForm, 'id_fascicolo')
  const quoteField = fieldByName(effectiveForm, 'id_preventivo')

  return (
    <Panel title="Form conferimento incarico" subtitle="Invio standard al POST Flask con sessione corrente.">
      <LegacyPostForm
        action={effectiveForm.action || '/preventivi/conferimento/nuovo'}
        title={effectiveForm.title}
        description={effectiveForm.description || 'La creazione finale resta nel backend.'}
        submitLabel={effectiveForm.submitLabel || 'Crea conferimento'}
        fields={[]}
        disabled={effectiveForm.enabled === false}
      >
        <HiddenFields form={effectiveForm} />
        <div className="iu-prev-form-grid">
          <SelectField field={customerField} label="Cliente" name="id_cliente" required emptyLabel="Seleziona cliente" />
          <SelectField field={caseField} label="Fascicolo" name="id_fascicolo" emptyLabel="Nessun fascicolo collegato" />
          <SelectField field={quoteField} label="Preventivo collegato" name="id_preventivo" emptyLabel="Nessun preventivo collegato" />
          <label className="iu-prev-field">
            <span>Data incarico</span>
            <input type="date" name="data_incarico" defaultValue={defaults.engagementAt} />
          </label>
        </div>
        <label className="iu-prev-field">
          <span>Oggetto incarico</span>
          <input type="text" name="oggetto" required defaultValue={defaults.subject} placeholder="Oggetto del conferimento" />
        </label>
        <div className="iu-prev-form-grid">
          <label className="iu-prev-field">
            <span>Avvocato referente</span>
            <input type="text" name="avvocato_referente" required defaultValue={defaults.lawyer} />
          </label>
          <label className="iu-prev-field">
            <span>Numero albo</span>
            <input type="text" name="numero_iscrizione_albo" defaultValue={defaults.barNumber} />
          </label>
          <label className="iu-prev-field">
            <span>Ordine avvocati</span>
            <input type="text" name="ordine_avvocati" defaultValue={defaults.barCouncil} />
          </label>
          <label className="iu-prev-field">
            <span>Importo pattuito</span>
            <input type="number" name="compenso_pattuito" min="0" step="0.01" defaultValue={defaults.amount} />
          </label>
          <label className="iu-prev-field">
            <span>Tariffa oraria</span>
            <input type="number" name="tariffa_oraria" min="0" step="0.01" defaultValue={defaults.hourly} />
          </label>
          <label className="iu-prev-field">
            <span>Tipo compenso</span>
            <input type="text" name="tipo_compenso" defaultValue={defaults.feeKind} />
          </label>
          <label className="iu-prev-field">
            <span>Tipo procedimento</span>
            <input type="text" name="tipo_procedimento" defaultValue={defaults.practiceKind} />
          </label>
        </div>
        <div className="iu-prev-options">
          <label><input type="checkbox" name="informativa_art13_resa" value="1" defaultChecked={defaults.art13Notice} /> Informativa art. 13 resa</label>
          <label><input type="checkbox" name="clausola_adr_resa" value="1" defaultChecked={defaults.adrClause} /> Clausola ADR resa</label>
          <label><input type="checkbox" name="apri_fascicolo_guidato" value="1" defaultChecked={defaults.openCaseGuided} /> Apri fascicolo guidato dopo il salvataggio</label>
        </div>
        <label className="iu-prev-field">
          <span>Note incarico</span>
          <textarea name="note" rows={4} defaultValue={defaults.note} placeholder="Patti, condizioni o istruzioni da conservare nel conferimento" />
        </label>
        <section className="iu-prev-form-note" aria-label="Presidio backend">
          <AlertTriangle size={17} />
          <span>Stati, firme, stampe e apertura fascicolo restano nel workflow Flask esistente.</span>
        </section>
      </LegacyPostForm>
    </Panel>
  )
}

function ArchiveView({ data }: { data: PreventiviPageData }) {
  return (
    <>
      <section className="iu-prev-banner">
        <div>
          <FileText size={22} />
          <strong>Mandato e acquisizione incarico</strong>
          <span>Archivio operativo con dati reali. I percorsi sensibili restano sui workflow Flask gia auditati.</span>
        </div>
        <CalendarDays size={22} />
      </section>
      <MetricGrid data={data} />
      <WarningPanel data={data} />
      <ActionStrip data={data} />
      <RecordsPanel data={data} />
      <SectionSummary data={data} />
      <ContractPanel data={data} />
    </>
  )
}

function FormActions({ mode }: { mode: PageMode }) {
  return (
    <div className="iu-prev-actions">
      <ButtonLink href="/preventivi" tone="neutral">Archivio</ButtonLink>
      {mode !== 'new-preventivo' ? <ButtonLink href="/preventivi/nuovo" tone="primary">Nuovo preventivo</ButtonLink> : null}
      {mode !== 'new-conferimento' ? <ButtonLink href="/preventivi/conferimento/nuovo" tone="primary">Nuovo conferimento</ButtonLink> : null}
    </div>
  )
}

export function PreventiviPage() {
  const [mode] = useState<PageMode>(() => modeFromPath())
  const [data, setData] = useState<PreventiviPageData>(emptyPreventiviPage)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    const loader = mode === 'new-preventivo'
      ? getNuovoPreventivoPage
      : mode === 'new-conferimento'
        ? getNuovoConferimentoPage
        : getPreventiviPage
    loader()
      .then((payload) => {
        if (active) setData(payload)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [mode])

  const title = mode === 'new-preventivo'
    ? 'Nuovo preventivo'
    : mode === 'new-conferimento'
      ? 'Nuovo conferimento incarico'
      : 'Preventivi e incarichi'
  const subtitle = mode === 'archive'
    ? 'Archivio mandato con KPI, stati e collegamenti a clienti e fascicoli reali.'
    : 'Form React con invio standard alla route Flask esistente.'
  const preventivoForm = data.forms.find((form) => form.id === 'nuovo_preventivo')
  const conferimentoForm = data.forms.find((form) => form.id === 'nuovo_conferimento')

  return (
    <Page title={title} subtitle={subtitle} actions={<FormActions mode={mode} />}>
      {loading ? (
        <LoadingState title="Caricamento preventivi" message="Recupero archivio, clienti e fascicoli dal repository dello studio." />
      ) : mode === 'new-preventivo' ? (
        <>
          <WarningPanel data={data} />
          <NewPreventivoForm form={preventivoForm} />
          <ContractPanel data={data} />
        </>
      ) : mode === 'new-conferimento' ? (
        <>
          <WarningPanel data={data} />
          <NewConferimentoForm form={conferimentoForm} />
          <ContractPanel data={data} />
        </>
      ) : (
        <ArchiveView data={data} />
      )}
    </Page>
  )
}
