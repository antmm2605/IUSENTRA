import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Download, ExternalLink, FileText, Plus, ReceiptText } from 'lucide-react'
import {
  emptyFatturazionePage,
  getFatturazionePage,
  getNuovaFatturaPage,
  type FatturazioneFormDefinition,
  type FatturazionePageData,
  type FatturazioneRecord,
} from '../fatturazioneData'
import { Badge } from '../ui/Badge'
import { ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LegacyPostForm } from '../ui/LegacyPostForm'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import type { LegacyPostField } from '../ui/LegacyPostForm'
import './FatturazionePage.css'

const fallbackDefaults = {
  issuedAt: '',
  dueAt: '',
  description: '',
  quantity: '1',
  unitAmount: '',
  notes: '',
  withFund: true,
  withVat: true,
  withWithholding: false,
  withStamp: false,
}

function displayValue(value: string | number): string {
  if (typeof value === 'number') return new Intl.NumberFormat('it-IT').format(value)
  return value
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
    <Panel title="Contratto dati" subtitle="GET React con scritture e documenti conservati sui percorsi legacy.">
      <div className="iu-fatt-contract">
        <span>Fonte: {data.source || 'non indicata'}</span>
        <span>Generato: {data.generated_at || 'non disponibile'}</span>
        <span>Scritture: {data.contracts.writes}</span>
        <span>Owner route: {data.contracts.route_owner}</span>
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
            Dettaglio legacy
          </ButtonLink>
        ) : null}
        {record.pdfHref ? (
          <ButtonLink href={record.pdfHref} tone="neutral">
            <FileText size={15} />
            PDF legacy
          </ButtonLink>
        ) : null}
        {record.xmlHref ? (
          <ButtonLink href={record.xmlHref} tone="neutral">
            <FileText size={15} />
            XML legacy
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

function fieldByName(form: FatturazioneFormDefinition | undefined, name: string): LegacyPostField | undefined {
  return form?.fields.find((field) => field.name === name)
}

function HiddenFields({ form }: { form: FatturazioneFormDefinition | undefined }) {
  const fields = useMemo(
    () => (form?.fields || []).filter((field) => field.type === 'hidden'),
    [form],
  )
  return (
    <>
      {fields.map((field) => (
        <input type="hidden" name={field.name} value={field.value || ''} key={field.name} />
      ))}
    </>
  )
}

function NewInvoiceForm({ form }: { form: FatturazioneFormDefinition | undefined }) {
  const [voiceRows, setVoiceRows] = useState(['voce-1'])
  const defaults = form?.defaults || fallbackDefaults
  const customerField = fieldByName(form, 'id_cliente')
  const caseField = fieldByName(form, 'id_fascicolo')
  const formAction = form?.action || '/fatturazione/nuova'

  return (
    <Panel title="Form parcella" subtitle="Invio standard al POST legacy con sessione Flask e controllo backend.">
      <LegacyPostForm
        action={formAction}
        title={form?.title || 'Nuova parcella'}
        description={form?.description || 'Il calcolo finale resta nel modulo legacy.'}
        submitLabel={form?.submitLabel || 'Crea parcella'}
        fields={[]}
        disabled={form?.enabled === false}
      >
        <HiddenFields form={form} />
        <div className="iu-fatt-form-grid">
          <label className="iu-fatt-field">
            <span>Cliente</span>
            <select name="id_cliente" required defaultValue={customerField?.value || ''}>
              {(customerField?.options || [{ value: '', label: 'Seleziona cliente' }]).map((option) => (
                <option value={option.value} key={option.value || option.label}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="iu-fatt-field">
            <span>Pratica</span>
            <select name="id_fascicolo" defaultValue={caseField?.value || ''}>
              {(caseField?.options || [{ value: '', label: 'Nessuna pratica' }]).map((option) => (
                <option value={option.value} key={option.value || option.label}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="iu-fatt-field">
            <span>Data emissione</span>
            <input type="date" name="data_emissione" defaultValue={defaults.issuedAt} />
          </label>
          <label className="iu-fatt-field">
            <span>Scadenza pagamento</span>
            <input type="date" name="data_scadenza" defaultValue={defaults.dueAt} />
          </label>
        </div>
        <div className="iu-fatt-service-list">
          <div className="iu-fatt-service-list__header">
            <strong>Voci prestazioni</strong>
            <button
              type="button"
              className="iu-fatt-icon-button"
              onClick={() => setVoiceRows((current) => [...current, `voce-${Date.now()}-${current.length}`])}
              aria-label="Aggiungi voce"
            >
              <Plus size={16} />
            </button>
          </div>
          {voiceRows.map((row, index) => (
            <div className="iu-fatt-service-row" key={row}>
              <label className="iu-fatt-field">
                <span>Descrizione</span>
                <input
                  type="text"
                  name="voce_descr[]"
                  required
                  defaultValue={index === 0 ? defaults.description : ''}
                  placeholder="Prestazione professionale"
                />
              </label>
              <label className="iu-fatt-field">
                <span>Quantita</span>
                <input
                  type="number"
                  name="voce_qty[]"
                  min="0.01"
                  step="0.01"
                  defaultValue={index === 0 ? defaults.quantity : '1'}
                />
              </label>
              <label className="iu-fatt-field">
                <span>Importo unitario</span>
                <input
                  type="number"
                  name="voce_prezzo[]"
                  min="0"
                  step="0.01"
                  defaultValue={index === 0 ? defaults.unitAmount : ''}
                />
              </label>
              <button
                type="button"
                className="iu-fatt-icon-button iu-fatt-icon-button--danger"
                disabled={voiceRows.length === 1}
                onClick={() => setVoiceRows((current) => current.filter((item) => item !== row))}
                aria-label="Rimuovi voce"
              >
                <AlertTriangle size={16} />
              </button>
            </div>
          ))}
        </div>
        <div className="iu-fatt-options">
          <label><input type="checkbox" name="applica_cassa" value="1" defaultChecked={defaults.withFund} /> Cassa Forense</label>
          <label><input type="checkbox" name="applica_iva" value="1" defaultChecked={defaults.withVat} /> IVA</label>
          <label><input type="checkbox" name="applica_ritenuta" value="1" defaultChecked={defaults.withWithholding} /> Ritenuta</label>
          <label><input type="checkbox" name="applica_bollo" value="1" defaultChecked={defaults.withStamp} /> Bollo</label>
        </div>
        <label className="iu-fatt-field">
          <span>Note e causale</span>
          <textarea name="note" rows={4} defaultValue={defaults.notes} placeholder="Causale o note per il documento" />
        </label>
        <section className="iu-fatt-form-note" aria-label="Calcolo backend">
          <strong>Il calcolo finale resta backend legacy</strong>
          <span>React raccoglie i campi e invia il form; imponibile, imposte, PDF e XML sono determinati dalle route storiche.</span>
        </section>
      </LegacyPostForm>
    </Panel>
  )
}

function ArchiveView({ data }: { data: FatturazionePageData }) {
  const exportAction = data.actions.find((action) => action.id === 'export')
  return (
    <>
      <section className="iu-fatt-banner" aria-label="Documenti economici legacy">
        <strong>PDF, XML ed export restano legacy</strong>
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
  const isNew = window.location.pathname.replace(/\/+$/, '').toLowerCase() === '/fatturazione/nuova'

  useEffect(() => {
    let active = true
    const loadPage = isNew ? getNuovaFatturaPage : getFatturazionePage
    loadPage()
      .then((payload) => {
        if (active) setData(payload)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [isNew])

  const hasData = data.metrics.length > 0 || data.records.length > 0 || data.forms.length > 0 || data.sections.some((section) => section.items.length > 0)
  const form = data.forms.find((item) => item.id === 'nuova_parcella') || data.forms[0]

  return (
    <Page
      title={isNew ? 'Nuova parcella' : 'Fatturazione'}
      subtitle={isNew ? 'Form React verso POST legacy, senza calcoli fiscali nel browser.' : 'Archivio economico con KPI reali e documenti avanzati conservati nel legacy.'}
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
      {!loading && !hasData ? (
        <EmptyState
          title="Nessun dato economico disponibile"
          message="Il bridge non ha restituito dati visualizzabili per questa superficie."
          action={<ButtonLink href="/fatturazione?_legacy=1" tone="warning">Apri archivio legacy</ButtonLink>}
        />
      ) : null}
      {!loading && hasData ? (
        isNew ? (
          <>
            <section className="iu-fatt-banner" aria-label="Form legacy">
              <strong>Scrittura conservata nel POST legacy</strong>
              <span>La pagina raccoglie i dati minimi; creazione, calcolo, numerazione e redirect restano nel blueprint fatturazione.</span>
            </section>
            <WarningPanel data={data} />
            <NewInvoiceForm form={form} />
            <ContractPanel data={data} />
          </>
        ) : (
          <ArchiveView data={data} />
        )
      ) : null}
    </Page>
  )
}
