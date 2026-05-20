import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, ArrowLeft, BookOpen, BriefcaseBusiness, CheckCircle2, ExternalLink, FileText, Filter, RefreshCw, Save, Search, ShieldCheck, Tags, UserRound } from 'lucide-react'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import { openDesignContract } from '../ui/openDesign'
import {
  emptyTemplateAttiPage,
  emptyTemplateCompilerPage,
  getTemplateAttiCompilerPage,
  getTemplateAttiCatalogoPage,
  getTemplateAttiPage,
  type TemplateCompilerData,
  type TemplateCompilerField,
  type TemplateAttiPageData,
  type TemplateAttiRecord,
} from '../templateAttiData'
import { displaySourceLabel } from '../displayText'
import { submitFormJson } from '../formSubmit'
import { FloatingLex } from './FloatingLex'
import './TemplateAttiPage.css'

function isCatalogoRoute() {
  return (window.location.pathname.replace(/\/+$/, '') || '/').toLowerCase() === '/template-atti/catalogo'
}

function compilerCodeFromRoute() {
  const match = (window.location.pathname.replace(/\/+$/, '') || '').match(/^\/template-atti\/compila\/([^/]+)$/i)
  return match ? decodeURIComponent(match[1]) : ''
}

function queryHiddenInputs() {
  const params = new URLSearchParams(window.location.search)
  const hidden: Array<{ name: string; value: string }> = []
  params.forEach((value, name) => {
    if (!['id_cliente', 'id_fascicolo', 'case_id'].includes(name)) {
      hidden.push({ name, value })
    }
  })
  return hidden
}

function collectControlData(root: HTMLElement | null) {
  const formData = new FormData()
  if (!root) return formData
  root.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>('input, select, textarea').forEach((control) => {
    if (!control.name || control.disabled) return
    if (control instanceof HTMLInputElement && ['checkbox', 'radio'].includes(control.type) && !control.checked) return
    formData.append(control.name, control.value)
  })
  return formData
}

function ContractStrip({ data }: { data: TemplateAttiPageData }) {
  return (
    <aside className="iu-doc-contract iu-od-surface">
      <ShieldCheck size={18} aria-hidden="true" />
      <div>
        <strong>{openDesignContract.system}</strong>
        <span>Catalogo atti collegato ai dati dello studio</span>
      </div>
    </aside>
  )
}

function cartabiaStateLabel(state: string) {
  const normalised = state.toLowerCase()
  if (normalised === 'cartabia_ready') return 'Verificato dai controlli IUSENTRA'
  if (normalised === 'cartabia_review_required') return 'Bloccato per fonte o regola mancante'
  if (normalised === 'needs_review') return 'Da completare'
  if (normalised === 'draft_professionale') return 'Bozza professionale'
  if (normalised === 'deprecated') return 'Non utilizzabile'
  if (normalised === 'internal_only') return 'Uso interno'
  return state.replaceAll('_', ' ')
}

function WarningList({ data }: { data: TemplateAttiPageData }) {
  if (!data.warnings.length) return null
  return (
    <div className="iu-doc-warnings" role="status">
      {data.warnings.map((warning) => (
        <p className="iu-doc-warning iu-od-warning" key={`${warning.code}-${warning.message}`}>
          {warning.message}
        </p>
      ))}
    </div>
  )
}

function Metrics({ data }: { data: TemplateAttiPageData }) {
  if (!data.metrics.length) return null
  return (
    <section className="iu-doc-metrics" aria-label="Indicatori template atti">
      {data.metrics.map((metric) => (
        <KpiCard
          key={metric.id}
          label={metric.label}
          value={metric.value || 0}
          note={metric.note}
          badge={<Badge tone={metric.tone}>{metric.tone === 'neutral' ? 'Dato' : 'Attivo'}</Badge>}
        />
      ))}
    </section>
  )
}

function Sections({ data }: { data: TemplateAttiPageData }) {
  if (!data.sections.length) return null
  return (
    <section className="iu-doc-section-grid" aria-label="Informazioni template atti">
      {data.sections.map((section) => (
        <Panel title={section.title} subtitle={section.kind} key={section.id}>
          {section.items.length ? (
            <div className="iu-doc-chip-list">
              {section.items.map((item) => (
                <span className="iu-doc-chip" key={item.id}>
                  <strong>{item.label}</strong>
                  <span>{item.value || 'Dato'}</span>
                </span>
              ))}
            </div>
          ) : (
            <EmptyState title={section.emptyMessage} />
          )}
        </Panel>
      ))}
    </section>
  )
}

function StudioStampPreview({ data }: { data: TemplateAttiPageData }) {
  if (!data.studioStamp.lines.length) return null
  return (
    <section className="iu-template-stamp iu-od-surface" aria-label="Anteprima timbro studio">
      <div className="iu-template-stamp__preview">
        {data.studioStamp.lines.map((line, index) => (
          <span
            key={`${line.text}-${index}`}
            className={[
              'iu-template-stamp__line',
              line.bold ? 'iu-template-stamp__line--bold' : '',
              line.size >= 12 ? 'iu-template-stamp__line--large' : line.size >= 10 ? 'iu-template-stamp__line--medium' : 'iu-template-stamp__line--small',
            ].filter(Boolean).join(' ')}
          >
            {line.text}
          </span>
        ))}
      </div>
      <div>
        <p className="iu-template-eyebrow">Timbro studio</p>
        <h3>Intestazione applicata automaticamente</h3>
        <p>Il modello usa i dati configurati dello studio e li ripete in alto a sinistra su ogni pagina dell'atto.</p>
      </div>
    </section>
  )
}

function TemplateCard({ record, onOpen }: { record: TemplateAttiRecord; onOpen: (record: TemplateAttiRecord) => void }) {
  return (
    <article className="iu-template-card iu-od-card">
      <header className="iu-template-card__header">
        <div>
          <span className="iu-template-card__kind">{record.kind}</span>
          <h3>{record.title}</h3>
          {record.subtitle ? <p>{record.subtitle}</p> : null}
        </div>
        {record.stateLabel ? <Badge tone={record.stateTone}>{record.stateLabel}</Badge> : null}
      </header>
      {record.description ? <p className="iu-template-card__description">{record.description}</p> : null}
      <dl className="iu-template-meta">
        {record.category ? (
          <div>
            <dt>Categoria</dt>
            <dd>{record.category}</dd>
          </div>
        ) : null}
        {record.matter || record.area ? (
          <div>
            <dt>Materia</dt>
            <dd>{record.matter || record.area}</dd>
          </div>
        ) : null}
        {record.channel ? (
          <div>
            <dt>Canale</dt>
            <dd>{record.channel}</dd>
          </div>
        ) : null}
        {record.updatedAt ? (
          <div>
            <dt>Aggiornato</dt>
            <dd>{record.updatedAt}</dd>
          </div>
        ) : null}
      </dl>
      {record.complianceLabel ? (
        <div className="iu-template-badges">
          <Badge tone="info">{record.complianceLabel}</Badge>
          {record.portal ? <Badge tone="neutral">{record.portal}</Badge> : null}
        </div>
      ) : null}
      <div className="iu-template-badges">
        {record.cartabiaState ? <Badge tone={record.requiresLawyerReview ? 'warning' : 'success'}>{cartabiaStateLabel(record.cartabiaState)}</Badge> : null}
        {record.prefillStatus === 'precompilabile' ? <Badge tone="success">Precompilabile</Badge> : null}
        {record.requiresLawyerReview ? <Badge tone="warning">Verifica bloccante</Badge> : null}
      </div>
      {record.requiredVariables.length ? (
        <div className="iu-template-vars">
          <span className="iu-template-vars__label">
            <Tags size={15} aria-hidden="true" />
            Variabili richieste
          </span>
          <div className="iu-template-vars__list">
            {record.requiredVariables.map((variable) => (
              <span className="iu-template-var" key={`${record.id}-${variable.name}`}>
                {variable.label || variable.name}
              </span>
            ))}
          </div>
        </div>
      ) : null}
      <footer className="iu-od-action-row iu-template-card__actions">
        <Button type="button" tone="primary" onClick={() => onOpen(record)}>
          <ExternalLink size={16} aria-hidden="true" />
          Apri scheda
        </Button>
        <ButtonLink href={record.href} tone="neutral">{record.primaryActionLabel}</ButtonLink>
      </footer>
    </article>
  )
}

function TemplateDetail({ record }: { record?: TemplateAttiRecord }) {
  if (!record) return null
  return (
    <section className="iu-template-detail iu-od-card" aria-label="Scheda template">
      <div>
        <span className="iu-template-card__kind">{record.kind}</span>
        <h2>{record.title}</h2>
        <p>{record.description || record.subtitle || 'Scheda operativa del modello selezionato.'}</p>
      </div>
      <dl className="iu-template-meta">
        <div><dt>Categoria</dt><dd>{record.category || 'Non indicata'}</dd></div>
        <div><dt>Materia</dt><dd>{record.matter || record.area || 'Non indicata'}</dd></div>
        <div><dt>Canale</dt><dd>{record.channel || 'Non indicato'}</dd></div>
        <div><dt>Variabili</dt><dd>{record.requiredVariables.length}</dd></div>
        <div><dt>Cartabia</dt><dd>{record.cartabiaState ? cartabiaStateLabel(record.cartabiaState) : 'Da verificare'}</dd></div>
        <div><dt>Dati disponibili</dt><dd>{record.prefillAvailable}</dd></div>
      </dl>
      <div className="iu-template-checks">
        <div>
          <strong><CheckCircle2 size={15} aria-hidden="true" /> Fonti dati</strong>
          <p>{record.dataSources.length ? record.dataSources.join(', ') : 'Da selezionare in redazione.'}</p>
        </div>
        <div>
          <strong><AlertTriangle size={15} aria-hidden="true" /> Controlli</strong>
          <p>{record.blockingChecks[0] || record.recommendedChecks[0] || 'Verifica conformita disponibile dalla scheda.'}</p>
        </div>
      </div>
      {record.requiredVariables.length ? (
        <div className="iu-template-vars__list">
          {record.requiredVariables.map((variable) => <span className="iu-template-var" key={`${record.id}-${variable.name}`}>{variable.label || variable.name}</span>)}
        </div>
      ) : null}
      <div className="iu-od-action-row">
        <ButtonLink href={record.href} tone="primary">{record.primaryActionLabel}</ButtonLink>
      </div>
    </section>
  )
}

function CatalogFilters({
  query,
  category,
  channel,
  cartabia,
  prefill,
  categories,
  channels,
  cartabiaStates,
  prefillStates,
  onQuery,
  onCategory,
  onChannel,
  onCartabia,
  onPrefill,
}: {
  query: string
  category: string
  channel: string
  cartabia: string
  prefill: string
  categories: string[]
  channels: string[]
  cartabiaStates: string[]
  prefillStates: string[]
  onQuery: (value: string) => void
  onCategory: (value: string) => void
  onChannel: (value: string) => void
  onCartabia: (value: string) => void
  onPrefill: (value: string) => void
}) {
  return (
    <section className="iu-template-filters iu-od-card" aria-label="Filtri catalogo template">
      <div className="iu-template-filter">
        <label htmlFor="template-search">
          <Search size={15} aria-hidden="true" />
          Cerca
        </label>
        <input id="template-search" value={query} onChange={(event) => onQuery(event.target.value)} />
      </div>
      <div className="iu-template-filter">
        <label htmlFor="template-category">
          <Filter size={15} aria-hidden="true" />
          Categoria
        </label>
        <select id="template-category" value={category} onChange={(event) => onCategory(event.target.value)}>
          <option value="">Tutte</option>
          {categories.map((item) => (
            <option value={item} key={item}>
              {item}
            </option>
          ))}
        </select>
      </div>
      <div className="iu-template-filter">
        <label htmlFor="template-channel">
          <BookOpen size={15} aria-hidden="true" />
          Canale
        </label>
        <select id="template-channel" value={channel} onChange={(event) => onChannel(event.target.value)}>
          <option value="">Tutti</option>
          {channels.map((item) => (
            <option value={item} key={item}>
              {item}
            </option>
          ))}
        </select>
      </div>
      <div className="iu-template-filter">
        <label htmlFor="template-cartabia">
          <ShieldCheck size={15} aria-hidden="true" />
          Stato Cartabia
        </label>
        <select id="template-cartabia" value={cartabia} onChange={(event) => onCartabia(event.target.value)}>
          <option value="">Tutti</option>
          {cartabiaStates.map((item) => (
            <option value={item} key={item}>{item.replaceAll('_', ' ')}</option>
          ))}
        </select>
      </div>
      <div className="iu-template-filter">
        <label htmlFor="template-prefill">
          <Tags size={15} aria-hidden="true" />
          Dati
        </label>
        <select id="template-prefill" value={prefill} onChange={(event) => onPrefill(event.target.value)}>
          <option value="">Tutti</option>
          {prefillStates.map((item) => (
            <option value={item} key={item}>{item}</option>
          ))}
        </select>
      </div>
    </section>
  )
}

function CompilerField({ field }: { field: TemplateCompilerField }) {
  const noteClass = field.note ? `iu-template-compiler-note iu-template-compiler-note--${field.note.tone}` : ''
  const className = field.type === 'richtext' || field.type === 'textarea' || field.type === 'multiselect' || field.type === 'repeater'
    ? 'iu-template-compiler-field iu-template-compiler-field--wide'
    : 'iu-template-compiler-field'
  return (
    <div className={className}>
      <label htmlFor={`compiler-${field.name}`}>
        {field.label}
        {field.required ? <span aria-hidden="true"> *</span> : null}
      </label>
      {field.type === 'select' ? (
        <select id={`compiler-${field.name}`} name={field.name} defaultValue={field.value} required={field.required} aria-invalid={field.error ? 'true' : 'false'}>
          <option value="">{field.placeholder || 'Seleziona'}</option>
          {field.options.map((option) => (
            <option key={`${field.name}-${option.value}`} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : field.type === 'richtext' || field.type === 'textarea' || field.type === 'multiselect' || field.type === 'repeater' ? (
        <textarea
          id={`compiler-${field.name}`}
          name={field.name}
          defaultValue={field.value}
          placeholder={field.placeholder}
          required={field.required}
          rows={field.type === 'richtext' ? 7 : 5}
          aria-invalid={field.error ? 'true' : 'false'}
        />
      ) : (
        <input
          id={`compiler-${field.name}`}
          name={field.name}
          type={field.type === 'number' || field.type === 'date' ? field.type : 'text'}
          defaultValue={field.value}
          placeholder={field.placeholder}
          required={field.required}
          aria-invalid={field.error ? 'true' : 'false'}
        />
      )}
      {field.error ? <p className="iu-template-compiler-error">{field.error}</p> : null}
      {field.note ? <p className={noteClass}>{field.note.text}</p> : null}
      {field.warnings.map((warning) => (
        <p className="iu-template-compiler-note iu-template-compiler-note--warning" key={`${field.name}-${warning}`}>
          {warning}
        </p>
      ))}
    </div>
  )
}

function ComplianceStatusCard({ data }: { data: TemplateCompilerData }) {
  const compliance = data.compliance
  const state = compliance.overallState || compliance.state
  const tone: 'success' | 'danger' | 'warning' = state === 'ok' ? 'success' : state === 'block' ? 'danger' : 'warning'
  return (
    <section className="iu-template-compiler-panel iu-template-compliance-panel">
      <header>
        <div>
          <p className="iu-template-eyebrow">Presidio normativo</p>
          <h3>Regole applicabili all'atto</h3>
        </div>
        <Badge tone={tone}>{state === 'ok' ? 'Pronto per editor' : state === 'block' ? 'Bloccato' : 'Conferma richiesta'}</Badge>
      </header>
      <dl className="iu-template-compliance-meta">
        <div>
          <dt>Area</dt>
          <dd>{compliance.processArea || data.model.area || 'Da verificare'}</dd>
        </div>
        <div>
          <dt>Stato</dt>
          <dd>{state ? cartabiaStateLabel(state) : 'Da verificare'}</dd>
        </div>
        <div>
          <dt>Fonti</dt>
          <dd>{compliance.evidenceCount ? `${compliance.evidenceCount} fonti ufficiali documentate` : 'Fonte da documentare'}</dd>
        </div>
        <div>
          <dt>Regole</dt>
          <dd>{compliance.rulesetVersion || 'Versione non indicata'}</dd>
        </div>
      </dl>
      {compliance.reasonedExplanation ? <p>{compliance.reasonedExplanation}</p> : null}
      {compliance.blocking.length ? (
        <div className="iu-template-compiler-checks iu-template-compiler-checks--block">
          {compliance.blocking.slice(0, 5).map((item) => <p key={item}>{item}</p>)}
        </div>
      ) : null}
    </section>
  )
}

function ReliabilityScoreCard({ data }: { data: TemplateCompilerData }) {
  const score = data.compliance.reliabilityScore
  return (
    <section className="iu-template-compiler-panel">
      <h3>Affidabilità</h3>
      <div className="iu-template-compiler-badges">
        <Badge tone={score.value >= 0.86 ? 'success' : score.value >= 0.65 ? 'warning' : 'danger'}>{Math.round(score.value * 100)}%</Badge>
        {score.label ? <Badge tone="neutral">{score.label}</Badge> : null}
      </div>
      {[...score.factors, ...score.capsApplied].slice(0, 5).map((item) => <p key={item}>{item}</p>)}
    </section>
  )
}

function NormativeReferencesCard({ data }: { data: TemplateCompilerData }) {
  const refs = data.compliance.normativeReferences
  if (!refs.length) return null
  return (
    <section className="iu-template-compiler-panel">
      <h3>Riferimenti applicabili</h3>
      <div className="iu-template-compliance-list">
        {refs.slice(0, 6).map((item) => (
          <p key={item.id || `${item.title}-${item.article}`}>
            <strong>{item.article || item.title}</strong>
            {item.reasonForApplication ? `: ${item.reasonForApplication}` : ''}
            {item.verificationStatus ? ` (${item.verificationStatus.replaceAll('_', ' ')})` : ''}
          </p>
        ))}
      </div>
    </section>
  )
}

function LayoutProfileCard({ data }: { data: TemplateCompilerData }) {
  const layout = data.compliance.layoutProfile
  const title = String(layout.title || layout.layout_profile_id || layout.layoutProfileId || '')
  if (!title) return null
  return (
    <section className="iu-template-compiler-panel">
      <h3>Layout atto</h3>
      <p>{title}</p>
      <div className="iu-template-compiler-badges">
        <Badge tone={layout.ok === false ? 'danger' : 'success'}>{layout.ok === false ? 'Da correggere' : 'Applicato'}</Badge>
        {layout.text_align ? <Badge tone="neutral">{String(layout.text_align)}</Badge> : null}
      </div>
    </section>
  )
}

function StudioStampCard({ data }: { data: TemplateCompilerData }) {
  const stamp = data.compliance.stampPolicy
  const policy = asPolicy(stamp.policy || stamp)
  return (
    <section className="iu-template-compiler-panel iu-template-compiler-stamp">
      <h3>Timbro su ogni pagina</h3>
      <div className="iu-template-compiler-badges">
        <Badge tone={stamp.ok === false ? 'danger' : 'success'}>{stamp.ok === false ? 'Da correggere' : 'Alto a sinistra'}</Badge>
        <Badge tone={policy.repeat ? 'success' : 'danger'}>{policy.repeat ? 'Ogni pagina' : 'Solo prima pagina'}</Badge>
      </div>
      {data.stamp.lines.length ? (
        <div>
          {data.stamp.lines.map((line, index) => (
            <span key={`${line.text}-${index}`} className={line.bold ? 'iu-template-compiler-stamp__bold' : ''}>{line.text}</span>
          ))}
        </div>
      ) : null}
    </section>
  )
}

function asPolicy(input: unknown): { repeat: boolean } {
  const item = input && typeof input === 'object' ? input as Record<string, unknown> : {}
  return { repeat: item.repeat_on_each_page === true || item.repeatOnEachPage === true }
}

function MissingFieldsCard({ data }: { data: TemplateCompilerData }) {
  if (!data.compliance.missingFields.length) return null
  return (
    <section className="iu-template-compiler-panel">
      <h3>Dati da completare</h3>
      <div className="iu-template-compiler-checks iu-template-compiler-checks--block">
        {data.compliance.missingFields.slice(0, 8).map((item) => <p key={item}>{item}</p>)}
      </div>
    </section>
  )
}

function MissingDocumentsCard({ data }: { data: TemplateCompilerData }) {
  if (!data.compliance.missingDocuments.length) return null
  return (
    <section className="iu-template-compiler-panel">
      <h3>Documenti da collegare</h3>
      {data.compliance.missingDocuments.slice(0, 6).map((item) => <p key={String(item.title || item.label || '')}>{String(item.title || item.label || '')}</p>)}
    </section>
  )
}

function LexActionCard({ data }: { data: TemplateCompilerData }) {
  if (!data.compliance.nextActions.length) return null
  return (
    <section className="iu-template-compiler-panel">
      <h3>Azioni richieste</h3>
      {data.compliance.nextActions.slice(0, 5).map((item) => <p key={item}>{item}</p>)}
    </section>
  )
}

function CompliancePanel({ data }: { data: TemplateCompilerData }) {
  return (
    <>
      <ComplianceStatusCard data={data} />
      <ReliabilityScoreCard data={data} />
      <NormativeReferencesCard data={data} />
      <LayoutProfileCard data={data} />
      <StudioStampCard data={data} />
      <MissingFieldsCard data={data} />
      <MissingDocumentsCard data={data} />
      <LexActionCard data={data} />
    </>
  )
}

function CompilerSidePanel({ data }: { data: TemplateCompilerData }) {
  const missing = [...data.baseFields, ...data.extraFields].filter((field) => field.note?.tone === 'missing').length
  const found = [...data.baseFields, ...data.extraFields].filter((field) => field.note?.tone === 'found').length
  return (
    <aside className="iu-template-compiler-aside">
      {data.stamp.lines.length ? (
        <section className="iu-template-compiler-panel iu-template-compiler-stamp" aria-label="Anteprima timbro studio">
          <h3>Timbro studio</h3>
          <div>
            {data.stamp.lines.map((line, index) => (
              <span key={`${line.text}-${index}`} className={line.bold ? 'iu-template-compiler-stamp__bold' : ''}>
                {line.text}
              </span>
            ))}
          </div>
        </section>
      ) : null}
      <section className="iu-template-compiler-panel">
        <h3>Dati IUSENTRA</h3>
        <div className="iu-template-compiler-badges">
          <Badge tone="success">Trovati {found}</Badge>
          {missing ? <Badge tone="warning">Da completare {missing}</Badge> : <Badge tone="success">Completi</Badge>}
        </div>
        <p>
          {data.selectors.selectedClienteLabel || data.selectors.selectedFascicoloLabel
            ? [data.selectors.selectedClienteLabel, data.selectors.selectedFascicoloLabel].filter(Boolean).join(' - ')
            : 'Seleziona cliente e pratica quando disponibili.'}
        </p>
      </section>
      {data.checks.blocking.length || data.checks.recommended.length ? (
        <section className="iu-template-compiler-panel">
          <h3>Controlli redazionali</h3>
          {data.checks.blocking.length ? (
            <div className="iu-template-compiler-checks iu-template-compiler-checks--block">
              {data.checks.blocking.slice(0, 6).map((item) => <p key={item}>{item}</p>)}
            </div>
          ) : null}
          {data.checks.recommended.length ? (
            <div className="iu-template-compiler-checks">
              {data.checks.recommended.slice(0, 6).map((item) => <p key={item}>{item}</p>)}
            </div>
          ) : null}
        </section>
      ) : null}
      {data.attachments.length ? (
        <section className="iu-template-compiler-panel">
          <h3>Allegati suggeriti</h3>
          <ul>
            {data.attachments.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </section>
      ) : null}
      {data.sections.length ? (
        <section className="iu-template-compiler-panel">
          <h3>Sezioni dell'atto</h3>
          <div className="iu-template-compiler-badges">
            {data.sections.map((section) => <Badge tone="neutral" key={section.label}>{section.label}</Badge>)}
          </div>
        </section>
      ) : null}
    </aside>
  )
}

function TemplateCompilerView({ modelCode }: { modelCode: string }) {
  const [data, setData] = useState<TemplateCompilerData>(emptyTemplateCompilerPage)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [submitMessage, setSubmitMessage] = useState('')
  const [submitError, setSubmitError] = useState('')
  const contextRef = useRef<HTMLDivElement>(null)
  const compilerRef = useRef<HTMLDivElement>(null)
  const hiddenQuery = useMemo(queryHiddenInputs, [])

  function load() {
    setLoading(true)
    getTemplateAttiCompilerPage(modelCode)
      .then(setData)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [modelCode])

  const applyContext = (intent = '') => {
    const params = new URLSearchParams(window.location.search)
    const formData = collectControlData(contextRef.current)
    formData.forEach((value, name) => {
      const textValue = String(value || '').trim()
      if (textValue) params.set(name, textValue)
      else params.delete(name)
    })
    if (intent) params.set('intent', intent)
    else params.delete('intent')
    const suffix = params.toString()
    window.location.assign(`${window.location.pathname}${suffix ? `?${suffix}` : ''}`)
  }

  const submitCompiler = () => {
    const state = data.compliance.overallState || data.compliance.state
    if (!data.selectors.selectedFascicoloId || submitting || state === 'block') return
    const formData = collectControlData(compilerRef.current)
    if (state === 'warning') {
      const confirmed = window.confirm('I controlli richiedono una bozza di lavoro da revisionare. Vuoi confermare la creazione?')
      if (!confirmed) return
      formData.set('requested_draft', 'working_draft')
      formData.set('confirmed_warning', '1')
    } else {
      formData.set('requested_draft', 'final_draft')
      formData.delete('confirmed_warning')
    }
    setSubmitting(true)
    setSubmitError('')
    setSubmitMessage('')
    submitFormJson(data.formAction, formData)
      .then((result) => {
        setSubmitMessage(result.message || 'Bozza creata. Apertura del documento in corso.')
        const editorUrl = result.editor_url || result.redirect
        if (editorUrl) {
          window.setTimeout(() => window.location.assign(editorUrl), 300)
        }
      })
      .catch((error) => setSubmitError(error instanceof Error ? error.message : 'Non ho potuto creare la bozza. Controlla i campi richiesti.'))
      .finally(() => setSubmitting(false))
  }

  if (loading) {
    return <LoadingState title="Caricamento compilazione" message="Recupero campi, dati disponibili e controlli del modello." />
  }

  return (
    <Page
      title="Compila template atto"
      subtitle={`${data.model.name} - ${data.model.code}${data.model.area ? ` - ${data.model.area}` : ''}`}
      actions={
        <>
          <ButtonLink href={data.catalogHref} tone="neutral">
            <ArrowLeft size={16} aria-hidden="true" />
            Catalogo
          </ButtonLink>
          <Button type="button" tone="neutral" onClick={load}>
            <RefreshCw size={16} aria-hidden="true" />
            Aggiorna
          </Button>
        </>
      }
    >
      <FloatingLex
        context="template-atti-compilatore"
        contextType="template_act"
        modelCode={data.model.code || modelCode}
        caseId={data.selectors.selectedFascicoloId}
        clientId={data.selectors.selectedClienteId}
        activeContext={{
          context_type: 'template_act',
          model_code: data.model.code || modelCode,
          case_id: data.selectors.selectedFascicoloId,
          client_id: data.selectors.selectedClienteId,
        }}
      />
      <div className="iu-template-compiler-page">
        <section className="iu-template-compiler-hero iu-od-surface">
          <div>
            <p className="iu-template-eyebrow">Redazione guidata</p>
            <h2>{data.model.name}</h2>
            <p>{data.summary || 'Compila il modello con i dati presenti in IUSENTRA e completa solo cio che manca.'}</p>
          </div>
          <Badge tone="info">{data.model.code}</Badge>
        </section>

        <div className="iu-template-compiler-layout">
          <main className="iu-template-compiler-main">
            <div className="iu-template-context-form iu-od-card" ref={contextRef}>
              {hiddenQuery.map((item) => <input type="hidden" name={item.name} value={item.value} key={`${item.name}-${item.value}`} />)}
              <input type="hidden" name="model_code" value={data.model.code} />
              <header>
                <span className="iu-template-step">1</span>
                <div>
                  <h3>Precompila dalla pratica</h3>
                  <p>Cliente e pratica collegano il template ai dati gia' disponibili nello studio.</p>
                </div>
              </header>
              <div className="iu-template-context-grid">
                <label>
                  <span><UserRound size={15} aria-hidden="true" /> Cliente</span>
                  <select name="id_cliente" defaultValue={data.selectors.selectedClienteId}>
                    <option value="">Nessun cliente</option>
                    {data.selectors.clienti.map((cliente) => <option value={cliente.value} key={cliente.value}>{cliente.label}</option>)}
                  </select>
                </label>
                <label>
                  <span><BriefcaseBusiness size={15} aria-hidden="true" /> Pratica collegata</span>
                  <select name="id_fascicolo" defaultValue={data.selectors.selectedFascicoloId}>
                    <option value="">Nessuna pratica</option>
                    {data.selectors.fascicoli.map((fascicolo) => <option value={fascicolo.value} key={fascicolo.value}>{fascicolo.label}</option>)}
                  </select>
                </label>
              </div>
              <div className="iu-od-action-row">
                <Button type="button" tone="neutral" onClick={() => applyContext()}>
                  <RefreshCw size={16} aria-hidden="true" />
                  Precompila dati
                </Button>
                <Button type="button" tone="neutral" onClick={() => applyContext('complete_missing')}>
                  <FileText size={16} aria-hidden="true" />
                  Completa dati mancanti
                </Button>
              </div>
            </div>

            <div className="iu-template-compiler-form iu-od-card" ref={compilerRef}>
              <input type="hidden" name="_react_return" value="1" />
              <input type="hidden" name="id_cliente" value={data.selectors.selectedClienteId} />
              <input type="hidden" name="id_fascicolo" value={data.selectors.selectedFascicoloId} />
              <input type="hidden" name="requested_draft" value={(data.compliance.overallState || data.compliance.state) === 'warning' ? 'working_draft' : 'final_draft'} />
              {Object.entries(data.hidden).map(([name, value]) => <input type="hidden" name={name} value={value} key={name} />)}
              <section>
                <header>
                  <span className="iu-template-step iu-template-step--green">2</span>
                  <h3>Dati base dell'atto</h3>
                </header>
                <div className="iu-template-compiler-grid">
                  {data.baseFields.map((field) => <CompilerField field={field} key={field.name} />)}
                </div>
              </section>
              {data.extraFields.length ? (
                <section>
                  <header>
                    <span className="iu-template-step iu-template-step--yellow">3</span>
                    <h3>Campi specifici del modello</h3>
                  </header>
                  <div className="iu-template-compiler-grid">
                    {data.extraFields.map((field) => <CompilerField field={field} key={field.name} />)}
                  </div>
                </section>
              ) : null}
              {submitError ? <p className="iu-template-compiler-error" role="alert">{submitError}</p> : null}
              {submitMessage ? <p className="iu-template-compiler-note iu-template-compiler-note--found" role="status">{submitMessage}</p> : null}
              <footer className="iu-template-compiler-actions">
                <Button type="button" tone="primary" disabled={!data.selectors.selectedFascicoloId || submitting || (data.compliance.overallState || data.compliance.state) === 'block'} title={!data.selectors.selectedFascicoloId ? 'Seleziona prima una pratica collegata.' : (data.compliance.overallState || data.compliance.state) === 'block' ? 'Completa i controlli bloccanti prima di creare la bozza.' : undefined} onClick={submitCompiler}>
                  <Save size={17} aria-hidden="true" />
                  {submitting ? 'Creazione in corso...' : (data.compliance.overallState || data.compliance.state) === 'block' ? 'Completa i controlli' : data.selectors.selectedFascicoloId ? data.submitLabel : 'Seleziona pratica collegata'}
                </Button>
                <ButtonLink href={data.catalogHref} tone="neutral">Annulla</ButtonLink>
              </footer>
            </div>
          </main>
          <div className="iu-template-compiler-aside-stack">
            <CompliancePanel data={data} />
            <CompilerSidePanel data={data} />
          </div>
        </div>
      </div>
    </Page>
  )
}

function TemplateCatalogView() {
  const catalogo = isCatalogoRoute()
  const [data, setData] = useState<TemplateAttiPageData>(emptyTemplateAttiPage)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [channel, setChannel] = useState('')
  const [cartabia, setCartabia] = useState('')
  const [prefill, setPrefill] = useState('')
  const [selectedId, setSelectedId] = useState(new URLSearchParams(window.location.search).get('scheda') || '')

  function load() {
    setLoading(true)
    const loader = catalogo ? getTemplateAttiCatalogoPage : getTemplateAttiPage
    loader()
      .then(setData)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [catalogo])

  const categories = useMemo(
    () => [...new Set(data.records.map((record) => record.category).filter(Boolean))].sort(),
    [data.records],
  )
  const channels = useMemo(
    () => [...new Set(data.records.map((record) => record.channel).filter(Boolean))].sort(),
    [data.records],
  )
  const cartabiaStates = useMemo(
    () => [...new Set(data.records.map((record) => record.cartabiaState).filter(Boolean))].sort(),
    [data.records],
  )
  const prefillStates = useMemo(
    () => [...new Set(data.records.map((record) => record.prefillStatus).filter(Boolean))].sort(),
    [data.records],
  )
  const filteredRecords = useMemo(() => {
    const search = query.trim().toLowerCase()
    return data.records.filter((record) => {
      const matchesSearch = !search || [record.title, record.subtitle, record.description, record.category, record.matter, record.area]
        .join(' ')
        .toLowerCase()
        .includes(search)
      const matchesCategory = !category || record.category === category
      const matchesChannel = !channel || record.channel === channel
      const matchesCartabia = !cartabia || record.cartabiaState === cartabia
      const matchesPrefill = !prefill || record.prefillStatus === prefill
      return matchesSearch && matchesCategory && matchesChannel && matchesCartabia && matchesPrefill
    })
  }, [cartabia, category, channel, data.records, prefill, query])
  const selectedRecord = data.records.find((record) => record.id === selectedId) || filteredRecords[0]

  const openRecord = (record: TemplateAttiRecord) => {
    setSelectedId(record.id)
    window.history.replaceState({}, '', `${window.location.pathname}?scheda=${encodeURIComponent(record.id)}`)
    window.requestAnimationFrame(() => document.querySelector('.iu-template-detail')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }

  if (loading) {
    return <LoadingState title="Caricamento template atti" message="Recupero catalogo e informazioni reali." />
  }

  return (
    <Page
      title={catalogo ? 'Catalogo template atti' : 'Template atti'}
      subtitle="Catalogo operativo con scheda in pagina e avvio diretto della produzione atti."
      actions={
        <>
          <Button type="button" tone="neutral" onClick={load}>
            <RefreshCw size={16} aria-hidden="true" />
            Aggiorna
          </Button>
          <ButtonLink href="/redazione-atti" tone="primary">
            Redazione atti
          </ButtonLink>
        </>
      }
    >
      <FloatingLex
        context={catalogo ? 'template-atti-catalogo' : 'template-atti'}
        contextType="template_act"
        modelCode={selectedRecord?.id}
        activeContext={{
          context_type: 'template_act',
          model_code: selectedRecord?.id,
        }}
      />
      <div className="iu-template-page iu-od-stack">
        <ContractStrip data={data} />
        <WarningList data={data} />
        <Metrics data={data} />
        <section className="iu-template-hero iu-od-surface">
          <div>
            <p className="iu-template-eyebrow">Documenti e modelli</p>
            <h2>{catalogo ? 'Catalogo consultabile e pronto alla redazione' : 'Ingresso operativo ai template dello studio'}</h2>
            <p>
              La pagina mostra catalogo, categorie, materie, canali e variabili, apre la scheda senza uscire e porta
              il modello selezionato nella produzione atti.
            </p>
          </div>
          <div className="iu-od-action-row iu-template-hero__actions">
            {data.actions.map((action) => (
              <ButtonLink key={action.id} href={action.href} tone={action.tone === 'primary' ? 'primary' : 'neutral'}>
                <ExternalLink size={16} aria-hidden="true" />
                {action.label}
              </ButtonLink>
            ))}
          </div>
        </section>
        <StudioStampPreview data={data} />
        {!catalogo ? <Sections data={data} /> : null}
        {catalogo ? (
          <CatalogFilters
            query={query}
            category={category}
            channel={channel}
            cartabia={cartabia}
            prefill={prefill}
            categories={categories}
            channels={channels}
            cartabiaStates={cartabiaStates}
            prefillStates={prefillStates}
            onQuery={setQuery}
            onCategory={setCategory}
            onChannel={setChannel}
            onCartabia={setCartabia}
            onPrefill={setPrefill}
          />
        ) : null}
        <TemplateDetail record={selectedRecord} />
        <Panel
          title={catalogo ? 'Template del catalogo' : 'Template principali'}
          subtitle={catalogo ? 'Filtri applicati agli atti disponibili.' : 'Informazioni reali e collegamenti sicuri.'}
        >
          {filteredRecords.length ? (
            <div className="iu-template-grid">
              {filteredRecords.map((record) => (
                <TemplateCard record={record} onOpen={openRecord} key={record.id} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="Nessun template disponibile"
              message="La schermata resta neutra finche' non sono disponibili template consultabili."
              action={
                <ButtonLink href="/documenti" tone="neutral">
                  Apri documenti
                </ButtonLink>
              }
            />
          )}
        </Panel>
        <aside className="iu-template-source iu-od-meta">
          Presidio dati: {displaySourceLabel(data.source)} - aggiornato {data.generated_at || 'non indicato'}
        </aside>
      </div>
    </Page>
  )
}

export function TemplateAttiPage() {
  const compilerCode = compilerCodeFromRoute()
  if (compilerCode) {
    return <TemplateCompilerView modelCode={compilerCode} />
  }
  return <TemplateCatalogView />
}
