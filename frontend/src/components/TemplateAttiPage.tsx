import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { AlignCenter, AlignJustify, AlignLeft, AlignRight, AlertTriangle, ArrowLeft, Bold, Bot, BookOpen, BriefcaseBusiness, CheckCircle2, Code2, Columns3, Copy, Download, Eye, ExternalLink, FileDown, FilePlus2, FileSignature, FileText, Filter, Heading1, Heading2, HelpCircle, Highlighter, IndentDecrease, IndentIncrease, Italic, Layers, List, ListOrdered, Move, Palette, Pilcrow, Plus, Quote, Redo2, RefreshCw, Save, Scale, Search, ShieldCheck, Sparkles, Strikethrough, Tags, Type, Underline, Undo2, UploadCloud, UserRound, XCircle } from 'lucide-react'
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
  type TemplateEditorLayout,
  type TemplateLexAction,
  type TemplateLexProposal,
  type TemplateExample,
  type TemplateAttiPageData,
  type TemplateAttiRecord,
} from '../templateAttiData'
import { displaySourceLabel } from '../displayText'
import { csrfToken, submitFormJson } from '../formSubmit'
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

function allCompilerFields(data: TemplateCompilerData): TemplateCompilerField[] {
  return [...data.baseFields, ...data.extraFields, ...data.contextFields]
}

function fieldValueByName(data: TemplateCompilerData, names: string[]) {
  const normalized = names.map((name) => name.toLowerCase())
  return allCompilerFields(data).find((field) => normalized.includes(field.name.toLowerCase()))
}

function labelForFieldValue(field?: TemplateCompilerField) {
  const rawValue = String(field?.value || '').trim()
  if (!rawValue || !field) return ''
  const option = field.options.find((item) => String(item.value || '').trim() === rawValue)
  return String(option?.label || rawValue).trim()
}

function resolveOfficeLabel(data: TemplateCompilerData) {
  const exact = fieldValueByName(data, [
    'court_name',
    'recipient_or_court',
    'competent_court',
    'issuing_court',
    'appeal_court',
    'competent_judge',
    'competent_authority',
    'ufficio',
    'tribunale',
    'giudice',
  ])
  if (exact) return labelForFieldValue(exact)
  const fuzzy = allCompilerFields(data).find((field) => /ufficio|giudice|tribunale|corte|autor/i.test(`${field.name} ${field.label}`))
  return labelForFieldValue(fuzzy)
}

function stripFixedStampFromDraft(draft: string, data: TemplateCompilerData) {
  let text = String(draft || '')
  const stampLines = data.stamp.lines.map((line) => line.text.trim()).filter(Boolean)
  if (!stampLines.length) return text
  for (const line of stampLines) {
    const escaped = line.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    text = text.trimStart().replace(new RegExp(`^${escaped}\\s*`, 'i'), '')
  }
  return text.trimStart()
}

function appendHiddenInput(form: HTMLFormElement, name: string, value: FormDataEntryValue | string) {
  if (value instanceof File) return
  const input = document.createElement('input')
  input.type = 'hidden'
  input.name = name
  input.value = String(value)
  form.appendChild(input)
}

function guideDraftFromData(data: TemplateCompilerData) {
  if (data.guidePreview.initialText.trim()) return stripFixedStampFromDraft(data.guidePreview.initialText, data)
  const tokenFor = (names: string[], fallback: string) => {
    const field = fieldValueByName(data, names)
    return field ? placeholderName(field) : fallback
  }
  const office = tokenFor(['court_name', 'recipient_or_court', 'competent_court', 'ufficio', 'tribunale'], '[UFFICIO_GIUDIZIARIO]')
  const client = tokenFor(['client_or_sender', 'cliente', 'nome_attore', 'plaintiff'], '[CLIENTE]')
  const counterparty = tokenFor(['counterparty_or_recipient', 'defendant', 'convenuto', 'resistente'], '[CONTROPARTE]')
  const title = tokenFor(['title', 'subject', 'oggetto', 'titolo_atto'], data.model.name || '[TITOLO_ATTO]')
  const facts = tokenFor(['facts', 'motivazioni', 'fatti', 'exposition'], '[ESPOSIZIONE_FATTI]')
  const merits = tokenFor(['merit_exceptions', 'position_on_facts', 'legal_basis', 'normativa'], '[ARGOMENTAZIONI_GIURIDICHE]')
  const requests = tokenFor(['requests_or_conclusions', 'conclusioni', 'domande', 'requests'], '[CONCLUSIONI]')
  const place = tokenFor(['place', 'luogo'], '[LUOGO]')
  const date = tokenFor(['document_date', 'data_atto', 'data'], '[DATA_ATTO]')
  const signature = tokenFor(['signature', 'lawyer', 'difensore'], '[FIRMA]')
  return [
    office,
    '',
    title,
    '',
    `${client}, rappresentato e difeso dall'avvocato indicato nel fascicolo, con procura allegata e domicilio professionale presso lo studio.`,
    '',
    `Contro ${counterparty}.`,
    '',
    'In fatto',
    '',
    facts,
    '',
    'In diritto',
    '',
    merits,
    '',
    'Conclusioni',
    '',
    requests,
    '',
    `${place}, ${date}`,
    '',
    signature,
  ].join('\n')
}

function htmlToPlainText(html: string) {
  const node = document.createElement('div')
  node.innerHTML = html
  return node.innerText || node.textContent || ''
}

function escapeHtml(value: string) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function inlineEditorHtml(value: string) {
  return escapeHtml(value).replace(/\r\n/g, '\n').replace(/\r/g, '\n').replace(/\n/g, '<br>')
}

function looksLikeEditorHtml(value: string) {
  return /<(p|div|h[1-6]|ul|ol|li|blockquote|br|strong|b|em|i|u|s|span|font)\b/i.test(String(value || ''))
}

function plainTextToEditorHtml(value: string) {
  const clean = String(value || '').replace(/\r/g, '').trim()
  if (!clean) return '<p><br></p>'
  return clean
    .split(/\n\s*\n/g)
    .map((block, index) => {
      const lines = block.split('\n').map((line) => line.trim()).filter(Boolean)
      if (!lines.length) return ''
      const joined = lines.map(escapeHtml).join('<br>')
      const first = lines[0] || ''
      if (index <= 1 && first.length <= 96 && first === first.toUpperCase() && /[A-ZÀ-Ù]/.test(first)) {
        return `<h2>${joined}</h2>`
      }
      if (/^\d+\.\s+/.test(first) && lines.every((line) => /^\d+\.\s+/.test(line))) {
        return `<ol>${lines.map((line) => `<li>${escapeHtml(line.replace(/^\d+\.\s+/, ''))}</li>`).join('')}</ol>`
      }
      if (/^-\s+/.test(first) && lines.every((line) => /^-\s+/.test(line))) {
        return `<ul>${lines.map((line) => `<li>${escapeHtml(line.replace(/^-\s+/, ''))}</li>`).join('')}</ul>`
      }
      return `<p>${joined}</p>`
    })
    .filter(Boolean)
    .join('\n') || '<p><br></p>'
}

function draftToEditorHtml(value: string) {
  const clean = String(value || '').trim()
  return looksLikeEditorHtml(clean) ? clean : plainTextToEditorHtml(clean)
}

function editorHtmlToPlainText(html: string) {
  return htmlToPlainText(html)
    .replace(/\u00a0/g, ' ')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function resolveDraftHtmlPlaceholders(html: string, fields: TemplateCompilerField[], values: Record<string, string>) {
  let resolved = String(html || '')
  fields.forEach((field) => {
    const value = fieldValueForDraft(field, values)
    if (!value) return
    resolved = resolved.replaceAll(placeholderName(field), escapeHtml(value))
  })
  return resolved
}

function replaceFieldPlaceholderInHtml(html: string, field: TemplateCompilerField, value: string, previousValue: string) {
  const token = placeholderName(field)
  const formattedValue = field.type === 'date' ? legalDateValue(value) : value
  const replacement = formattedValue.trim() ? inlineEditorHtml(formattedValue) : token
  if (html.includes(token)) return html.replaceAll(token, replacement)
  const previous = String(previousValue || '').trim()
  if (!previous || previous === token || previous === value) return html
  const escapedPrevious = inlineEditorHtml(field.type === 'date' ? legalDateValue(previous) : previous)
  return html.includes(escapedPrevious) ? html.replaceAll(escapedPrevious, replacement) : html
}

function stripHtmlStampFromDraft(html: string, data: TemplateCompilerData) {
  const text = stripFixedStampFromDraft(editorHtmlToPlainText(html), data)
  return plainTextToEditorHtml(text)
}

function fontLabelByKey(data: TemplateCompilerData, key: string) {
  return data.fontRegistry.fonts.find((font) => font.key === key)?.label || key || 'Times New Roman'
}

function normaliseClipboardHtml(html: string, data: TemplateCompilerData) {
  return stripHtmlStampFromDraft(html, data)
}

function fieldForPlaceholder(fields: TemplateCompilerField[], token: string) {
  const normalized = token.replace(/^\[|\]$/g, '').toLowerCase()
  return fields.find((field) => (
    placeholderName(field).replace(/^\[|\]$/g, '').toLowerCase() === normalized
    || field.name.toLowerCase() === normalized
  ))
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
          <p>{record.blockingChecks[0] || record.recommendedChecks[0] || 'Verifica conformità disponibile dalla scheda.'}</p>
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
  if (data.guidePreview.enabled) {
    const redactionMissing = data.compliance.missingFields.filter((item) => !/codice oggetto pst|procura|contributo|deposito|datiatto|allegat/i.test(item))
    return (
      <>
        {redactionMissing.length ? (
          <section className="iu-template-compiler-panel">
            <h3>Dati redazionali da completare</h3>
            <div className="iu-template-compiler-checks iu-template-compiler-checks--block">
              {redactionMissing.slice(0, 8).map((item) => <p key={item}>{item}</p>)}
            </div>
          </section>
        ) : null}
        <NormativeReferencesCard data={data} />
      </>
    )
  }
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
  const redactionChecks = data.checks.blocking.filter((item) => !/codice oggetto pst|procura|contributo|deposito|datiatto|schema ministeriale|allegati essenziali|materia del fascicolo/i.test(item))
  const depositChecks = data.guidePreview.enabled
    ? []
    : [...data.checks.blocking, ...data.checks.recommended].filter((item) => /codice oggetto pst|procura|contributo|deposito|datiatto|schema ministeriale|allegati essenziali|ufficio non ancora risolto|materia del fascicolo/i.test(item))
  return (
    <aside className="iu-template-compiler-aside">
      {!data.guidePreview.enabled && data.stamp.lines.length ? (
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
      {redactionChecks.length || depositChecks.length ? (
        <section className="iu-template-compiler-panel">
          <h3>{data.guidePreview.enabled ? 'Controlli produzione documento' : 'Controlli redazionali'}</h3>
          {redactionChecks.length ? (
            <div className="iu-template-compiler-checks iu-template-compiler-checks--block">
              {redactionChecks.slice(0, 6).map((item) => <p key={item}>{item}</p>)}
            </div>
          ) : null}
          {depositChecks.length ? (
            <div className="iu-template-compiler-checks">
              <strong>Da riprendere prima del deposito</strong>
              {depositChecks.slice(0, 8).map((item) => <p key={item}>{item}</p>)}
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

type TemplateEditorTab = 'Campi' | 'Stile' | 'Lex' | 'Fonti' | 'Controlli' | 'Export'

type ImportedDocumentInfo = {
  fileName: string
  text: string
  html?: string
  fonts: string[]
  encoding: string
  note: string
}

type TemplateEditorProps = {
  data: TemplateCompilerData
  activeTool: string
  draftText: string
  importing: boolean
  importedDocument: ImportedDocumentInfo | null
  importStatus: string
  pdfStatus: string
  saving: boolean
  bodyFontSize: number
  bodyLineHeight: number
  onToolSelect: (tool: string) => void
  onDraftTextChange: (value: string) => void
  onBodyFontSizeChange: (value: number) => void
  onBodyLineHeightChange: (value: number) => void
  onEditorLayoutChange: (value: Partial<TemplateEditorLayout>) => void
  onImport: () => void
  onPreviewPdf: (draftOverride?: string, htmlOverride?: string) => void
  onDownloadWord: (draftOverride?: string, htmlOverride?: string) => void
  onDownloadRtf: (draftOverride?: string, targetModelCode?: string, htmlOverride?: string) => void
  onDownloadMultipleRtf: (targetModelCodes: string[], draftOverride?: string, htmlOverride?: string) => void
  onRefreshPreview: (draftOverride?: string) => void
  onSave: (draftOverride?: string, htmlOverride?: string) => void | Promise<string>
  onPrepareSignature: (draftOverride?: string, htmlOverride?: string) => void
}

function placeholderName(field: TemplateCompilerField) {
  return `[${field.name.replace(/[^a-z0-9]+/gi, '_').replace(/^_+|_+$/g, '').toUpperCase()}]`
}

function lexModeLabel(mode: string) {
  if (mode === 'Template Builder' || mode === 'Template Editor') return 'Costruttore template'
  if (mode === 'Final Check') return 'Controllo finale'
  return mode
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function legalDateTimeNow() {
  return new Intl.DateTimeFormat('it-IT', {
    timeZone: 'Europe/Rome',
    day: '2-digit',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date())
}

function legalDateValue(value: string) {
  const clean = value.trim()
  if (!/^\d{4}-\d{2}-\d{2}$/.test(clean)) return clean
  const [year, month, day] = clean.split('-').map(Number)
  const parsed = new Date(Date.UTC(year, month - 1, day, 12, 0, 0))
  if (Number.isNaN(parsed.getTime())) return clean
  return new Intl.DateTimeFormat('it-IT', {
    timeZone: 'Europe/Rome',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(parsed)
}

function fieldDisplayValue(field: TemplateCompilerField) {
  return field.type === 'date' ? legalDateValue(field.value || '') : field.value || ''
}

function fieldValueForDraft(field: TemplateCompilerField, values: Record<string, string>) {
  const value = String(values[field.name] ?? fieldDisplayValue(field) ?? '').trim()
  return field.type === 'date' ? legalDateValue(value) : value
}

function resolveDraftPlaceholders(text: string, fields: TemplateCompilerField[], values: Record<string, string>) {
  let resolved = String(text || '')
  fields.forEach((field) => {
    const value = fieldValueForDraft(field, values)
    if (!value) return
    resolved = resolved.replaceAll(placeholderName(field), value)
  })
  return resolved
}

function appendQueryToHref(href: string) {
  if (!href) return ''
  const query = window.location.search
  if (!query) return href
  return href.includes('?') ? `${href}&${query.slice(1)}` : `${href}${query}`
}

function classToken(value: string | undefined, fallback: string) {
  const clean = (value || fallback).toLowerCase().replace(/[^a-z0-9_-]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '')
  return clean || fallback
}

function fontVariantClass(prefix: string, key: string | undefined, fallback: string) {
  return `${prefix}--${classToken(key, fallback)}`
}

function bodySizeClass(value: number) {
  const size = Math.max(9, Math.min(22, Math.round(value || 12)))
  return `iu-template-body-size--${size}`
}

function lineHeightClass(value: number) {
  const step = Math.max(12, Math.min(26, Math.round((value || 1.9) * 10)))
  return `iu-template-leading--${step}`
}

function groupCompilerFields(fields: TemplateCompilerField[]) {
  const groups: Array<{ id: string; title: string; fields: TemplateCompilerField[] }> = [
    { id: 'studio', title: 'Dati studio', fields: [] },
    { id: 'parte', title: 'Dati parte', fields: [] },
    { id: 'pratica', title: 'Dati pratica', fields: [] },
    { id: 'dettagli', title: 'Dettagli', fields: [] },
  ]
  fields.forEach((field) => {
    const textValue = `${field.name} ${field.label}`.toLowerCase()
    if (/studio|avvocato|pec|indirizzo_studio|piva|iban/.test(textValue)) groups[0].fields.push(field)
    else if (/cliente|attore|convenuto|parte|controparte|destinatario/.test(textValue)) groups[1].fields.push(field)
    else if (/fascicolo|pratica|rg|tribunale|giudice|ufficio|rito|fase/.test(textValue)) groups[2].fields.push(field)
    else groups[3].fields.push(field)
  })
  return groups.filter((group) => group.fields.length)
}

function firstMeaningfulSentence(value: string) {
  const clean = value.replace(/\s+/g, ' ').trim()
  if (!clean) return ''
  const sentence = clean.match(/[^.!?]{24,}[.!?]/)
  return (sentence?.[0] || clean.slice(0, 220)).trim()
}

function buildLocalLexProposal(action: TemplateLexAction, data: TemplateCompilerData, draftText: string, fields: TemplateCompilerField[], customInstructions: string): TemplateLexProposal {
  const original = firstMeaningfulSentence(draftText) || '[TESTO_DOCUMENTO]'
  const missingPlaceholder = fields.map(placeholderName).find((token) => draftText.includes(token))
  const firstSource = data.compliance.normativeReferences[0]
  const baseId = `${action.id}_${Date.now()}`
  if (action.id === 'correggi_refusi') {
    const proposed = original
      .replace(/\s{2,}/g, ' ')
      .replace(/\s+([,.;:])/g, '$1')
      .replace(/ ,/g, ',')
      .trim()
    return {
      id: baseId,
      mode: action.mode,
      title: action.label,
      original,
      proposed: proposed === original ? `${original} [nessun refuso evidente nel passaggio selezionato]` : proposed,
      reason: 'Correzione locale di spaziatura, punteggiatura e refusi evidenti.',
      risk: 'info',
      status: 'pending',
    }
  }
  if (action.id === 'controlla_placeholder') {
    return {
      id: baseId,
      mode: action.mode,
      title: action.label,
      original: missingPlaceholder || '[CAMPO_VARIABILE]',
      proposed: missingPlaceholder ? `Completa ${missingPlaceholder} prima dell'esportazione finale.` : 'Nessun placeholder non compilato rilevato nel testo visibile.',
      reason: 'Controllo campi variabili con applicazione solo su conferma.',
      risk: missingPlaceholder ? 'warning' : 'success',
      status: 'pending',
    }
  }
  if (action.id === 'controlla_normativa') {
    const sourceText = firstSource
      ? `${firstSource.title || firstSource.article}${firstSource.article ? `, ${firstSource.article}` : ''}${firstSource.officialUrl ? ` (${firstSource.officialUrl})` : ''}`
      : 'Nessuna fonte normativa specifica è ancora collegata al modello: verificare il fascicolo e la materia prima della versione finale.'
    return {
      id: baseId,
      mode: action.mode,
      title: action.label,
      original,
      proposed: `Riferimento da valutare nel testo: ${sourceText}`,
      reason: 'Lex segnala il punto e usa solo fonti tracciate; nessuna norma viene inserita senza accettazione.',
      risk: 'warning',
      status: 'pending',
    }
  }
  if (action.id === 'controlla_privacy') {
    return {
      id: baseId,
      mode: action.mode,
      title: action.label,
      original,
      proposed: 'Conserva nel testo solo i dati personali necessari alla finalità difensiva e alla pratica collegata.',
      reason: 'Controllo privacy e dati personali in locale, senza trasmissione a servizi esterni.',
      risk: 'warning',
      status: 'pending',
    }
  }
  if (action.id === 'genera_clausola') {
    return {
      id: baseId,
      mode: action.mode,
      title: action.label,
      original: '',
      proposed: `Clausola proposta: le parti prendono atto della documentazione esaminata e confermano che ogni ulteriore integrazione sarà valutata dal difensore prima del deposito.${customInstructions ? ` Indicazione Lex: ${customInstructions}` : ''}`,
      reason: "Testo aggiuntivo in diff separato, da accettare prima dell'inserimento.",
      risk: 'info',
      status: 'pending',
    }
  }
  if (action.id === 'espandi_premesse') {
    return {
      id: baseId,
      mode: action.mode,
      title: action.label,
      original,
      proposed: `${original} La ricostruzione dei fatti viene precisata con riferimento ai documenti già presenti nella pratica e alle circostanze confermate dal cliente.`,
      reason: 'Espansione redazionale separata, da accettare o modificare.',
      risk: 'info',
      status: 'pending',
    }
  }
  if (action.id === 'versione_finale') {
    return {
      id: baseId,
      mode: action.mode,
      title: action.label,
      original: missingPlaceholder || original,
      proposed: missingPlaceholder
        ? `Prima della firma resta da completare il campo ${missingPlaceholder}.`
        : 'Versione finale pronta per esportazione o firma: rilettura conclusa, nessun placeholder visibile nel corpo principale.',
      reason: 'Controllo finale locale su placeholder, tono e uso dei dati fascicolo.',
      risk: missingPlaceholder ? 'warning' : 'success',
      status: 'pending',
    }
  }
  const formality = action.id === 'rendi_chiaro_cliente'
    ? 'in termini più chiari, mantenendo il rigore giuridico'
    : action.id === 'rendi_incisivo'
      ? 'con formula più diretta e incisiva'
      : action.id === 'rendi_formale'
        ? 'con tono più formale e istituzionale'
        : 'con tono professionale e lineare'
  return {
    id: baseId,
    mode: action.mode,
    title: action.label,
    original,
    proposed: `${original} [Versione Lex: ${formality}.]`,
    reason: 'Proposta stilistica locale, da accettare o rifiutare.',
    risk: 'info',
    status: 'pending',
  }
}

const TEMPLATE_CATEGORY_TABS = ['Tutti', 'Contratti', 'Diffide', 'Deleghe', 'Pareri', 'Atti']

function compactTemplateCategory(item: TemplateExample) {
  const searchable = `${item.title} ${item.description} ${item.category} ${item.tags.join(' ')}`.toLowerCase()
  if (/(diffid|mora|sollecito|stragiudizial)/i.test(searchable)) return 'Diffide'
  if (/(deleg|procura|mandato|rappresentanza)/i.test(searchable)) return 'Deleghe'
  if (/(parere|responsabilit|consulenz|valutazion)/i.test(searchable)) return 'Pareri'
  if (/(contratt|locazion|comodat|accordo|incarico|scrittura privata|privacy|gdpr|clausol)/i.test(searchable)) return 'Contratti'
  return 'Atti'
}

function ProfessionalTemplateEditorWorkspace({
  data,
  activeTool,
  draftText,
  importing,
  importedDocument,
  importStatus,
  pdfStatus,
  saving,
  bodyFontSize,
  bodyLineHeight,
  onToolSelect,
  onDraftTextChange,
  onBodyFontSizeChange,
  onBodyLineHeightChange,
  onEditorLayoutChange,
  onImport,
  onPreviewPdf,
  onDownloadWord,
  onDownloadRtf,
  onDownloadMultipleRtf,
  onRefreshPreview,
  onSave,
  onPrepareSignature,
}: TemplateEditorProps) {
  const fields = allCompilerFields(data)
  const fieldGroups = useMemo(() => groupCompilerFields(fields), [data.model.code, data.baseFields, data.extraFields, data.contextFields])
  const [activeTab, setActiveTab] = useState<TemplateEditorTab>('Campi')
  const [templateSearch, setTemplateSearch] = useState('')
  const [templateCategory, setTemplateCategory] = useState('Tutti')
  const [selectedTemplateId, setSelectedTemplateId] = useState('')
  const [multipleOpen, setMultipleOpen] = useState(false)
  const [multipleSelection, setMultipleSelection] = useState<Record<string, boolean>>({})
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({})
  const [contextClienteId, setContextClienteId] = useState(data.selectors.selectedClienteId || '')
  const [contextFascicoloId, setContextFascicoloId] = useState(data.selectors.selectedFascicoloId || '')
  const [documentFont, setDocumentFont] = useState(data.editorLayout.fontFamily || data.fontRegistry.defaults.document)
  const [headingFont, setHeadingFont] = useState(data.editorLayout.headingFontFamily || data.fontRegistry.defaults.heading)
  const [uiFont, setUiFont] = useState(data.editorLayout.uiFontFamily || data.fontRegistry.defaults.ui)
  const [placeholderFont, setPlaceholderFont] = useState(data.editorLayout.placeholderFontFamily || data.fontRegistry.defaults.placeholder)
  const [fallbackFont, setFallbackFont] = useState(data.editorLayout.fallbackFontFamily || data.fontRegistry.defaults.fallback)
  const [stylePreset, setStylePreset] = useState(data.editorLayout.stylePreset || data.fontRegistry.defaults.stylePreset)
  const [textAlign, setTextAlign] = useState(data.editorLayout.textAlign || 'justify')
  const [stampPosition, setStampPosition] = useState(data.editorLayout.stampPosition || 'top-center')
  const [stampOffsetY, setStampOffsetY] = useState(Number(data.editorLayout.stampOffsetY || 0))
  const [activeLexMode, setActiveLexMode] = useState(data.lexRevision.modes[0] || 'Correttore')
  const [customInstructions, setCustomInstructions] = useState('')
  const [proposals, setProposals] = useState<TemplateLexProposal[]>(data.lexRevision.seedProposals)
  const [auditRows, setAuditRows] = useState<string[]>([])
  const [workspaceStatus, setWorkspaceStatus] = useState('')
  const editorRef = useRef<HTMLDivElement>(null)
  const savedSelectionRef = useRef<Range | null>(null)
  const lastPlainDraftFromEditorRef = useRef('')
  const panelRef = useRef<HTMLDivElement>(null)
  const selectedTemplate = data.templateExamples.find((item) => item.id === selectedTemplateId) || data.templateExamples.find((item) => item.selected) || data.templateExamples[0]
  const categories = useMemo(() => TEMPLATE_CATEGORY_TABS, [])
  const visibleTemplates = data.templateExamples.filter((item) => {
    const byCategory = templateCategory === 'Tutti' || compactTemplateCategory(item) === templateCategory
    const textValue = `${item.title} ${item.description} ${item.tags.join(' ')}`.toLowerCase()
    return byCategory && (!templateSearch.trim() || textValue.includes(templateSearch.trim().toLowerCase()))
  })
  const visibleMultipleTemplates = data.templateExamples.slice(0, 10)
  const visibleMultipleCodes = new Set(visibleMultipleTemplates.map((item) => item.code || item.id).filter(Boolean))
  const selectedMultipleCount = visibleMultipleTemplates.filter((item) => multipleSelection[item.code || item.id] === true).length
  const completedFields = fields.filter((field) => (fieldValues[field.name] || field.value || '').trim()).length
  const completion = fields.length ? Math.round((completedFields / fields.length) * 100) : 100
  const lexActions = data.lexRevision.actions
  const statusText = [workspaceStatus, importStatus, pdfStatus].filter(Boolean).join(' ')
  const baseDraftText = draftText
  const editorClassName = [
    'iu-template-pro-editor',
    fontVariantClass('iu-template-ui-font', uiFont, 'inter'),
  ].join(' ')
  const paperClassName = [
    'iu-template-pro-paper',
    fontVariantClass('iu-template-doc-font', documentFont, 'source_serif'),
    fontVariantClass('iu-template-heading-font', headingFont, 'merriweather'),
    fontVariantClass('iu-template-placeholder-font', placeholderFont, 'ibm_plex_mono'),
    bodySizeClass(bodyFontSize),
    lineHeightClass(bodyLineHeight),
    `iu-template-align--${classToken(textAlign, 'justify')}`,
    `iu-template-stamp-position--${classToken(stampPosition, 'top_center')}`,
  ].join(' ')

  const stampRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const values: Record<string, string> = {}
    fields.forEach((field) => {
      values[field.name] = fieldDisplayValue(field)
    })
    setFieldValues(values)
    setSelectedTemplateId((current) => current || data.templateExamples.find((item) => item.selected)?.id || data.templateExamples[0]?.id || '')
    setProposals(data.lexRevision.seedProposals)
    setStampPosition(data.editorLayout.stampPosition || 'top-center')
    setStampOffsetY(Number(data.editorLayout.stampOffsetY || 0))
    setContextClienteId(data.selectors.selectedClienteId || '')
    setContextFascicoloId(data.selectors.selectedFascicoloId || '')
  }, [data.model.code])

  useEffect(() => {
    const editor = editorRef.current
    if (!editor) return
    if (baseDraftText === lastPlainDraftFromEditorRef.current && editor.innerHTML.trim()) return
    editor.innerHTML = draftToEditorHtml(baseDraftText)
    lastPlainDraftFromEditorRef.current = editorHtmlToPlainText(editor.innerHTML)
  }, [baseDraftText, data.model.code])

  useEffect(() => {
    onEditorLayoutChange({
      fontFamily: documentFont,
      headingFontFamily: headingFont,
      uiFontFamily: uiFont,
      placeholderFontFamily: placeholderFont,
      fallbackFontFamily: fallbackFont,
      stylePreset,
      fontSize: bodyFontSize,
      lineHeight: bodyLineHeight,
      textAlign,
      stampPosition,
      stampOffsetY,
    })
  }, [documentFont, headingFont, uiFont, placeholderFont, fallbackFont, stylePreset, bodyFontSize, bodyLineHeight, textAlign, stampPosition, stampOffsetY, data.model.code])

  const setTab = (tab: TemplateEditorTab) => {
    setActiveTab(tab)
    onToolSelect(tab)
    window.requestAnimationFrame(() => {
      if (panelRef.current) panelRef.current.scrollTop = 0
    })
  }

  const updateField = (field: TemplateCompilerField, value: string) => {
    const previousValue = fieldValues[field.name] || fieldDisplayValue(field)
    const editor = editorRef.current
    if (editor) {
      const nextHtml = replaceFieldPlaceholderInHtml(editor.innerHTML, field, value, previousValue)
      if (nextHtml !== editor.innerHTML) {
        editor.innerHTML = nextHtml
        lastPlainDraftFromEditorRef.current = editorHtmlToPlainText(nextHtml)
        onDraftTextChange(lastPlainDraftFromEditorRef.current)
      }
    }
    setFieldValues((current) => ({ ...current, [field.name]: value }))
    setWorkspaceStatus(`${field.label} aggiornato nell'anteprima; il segnaposto resta modificabile nel template.`)
  }

  const saveSelection = () => {
    const editor = editorRef.current
    const stamp = stampRef.current
    const selection = window.getSelection()
    if (!selection || selection.rangeCount === 0) return
    const range = selection.getRangeAt(0)
    if ((editor && editor.contains(range.commonAncestorContainer)) || (stamp && stamp.contains(range.commonAncestorContainer))) {
      savedSelectionRef.current = range.cloneRange()
    }
  }

  const restoreSelection = () => {
    const editor = editorRef.current
    const stamp = stampRef.current
    if (!editor) return false
    editor.focus()
    const selection = window.getSelection()
    if (!selection) return false
    selection.removeAllRanges()
    if (
      savedSelectionRef.current
      && ((editor && editor.contains(savedSelectionRef.current.commonAncestorContainer)) || (stamp && stamp.contains(savedSelectionRef.current.commonAncestorContainer)))
    ) {
      selection.addRange(savedSelectionRef.current)
      return true
    }
    const range = document.createRange()
    range.selectNodeContents(editor)
    range.collapse(false)
    selection.addRange(range)
    savedSelectionRef.current = range.cloneRange()
    return true
  }

  const editorHtml = () => editorRef.current?.innerHTML || draftToEditorHtml(baseDraftText)
  const editorPlainText = () => editorHtmlToPlainText(editorHtml())
  const exportPlainText = () => resolveDraftPlaceholders(stripFixedStampFromDraft(editorPlainText(), data), fields, fieldValues)
  const exportHtml = () => resolveDraftHtmlPlaceholders(normaliseClipboardHtml(editorHtml(), data), fields, fieldValues)

  const syncEditorToDraft = (status?: string) => {
    const plain = editorPlainText()
    lastPlainDraftFromEditorRef.current = plain
    onDraftTextChange(plain)
    saveSelection()
    if (status) setWorkspaceStatus(status)
  }

  const setEditorContentFromText = (text: string, status?: string) => {
    const editor = editorRef.current
    const html = draftToEditorHtml(text)
    if (editor) {
      editor.innerHTML = html
      editor.focus()
    }
    lastPlainDraftFromEditorRef.current = editorHtmlToPlainText(html)
    onDraftTextChange(lastPlainDraftFromEditorRef.current)
    if (status) setWorkspaceStatus(status)
  }

  const hasEditorSelection = () => {
    const editor = editorRef.current
    const stamp = stampRef.current
    const selection = window.getSelection()
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return false
    const container = selection.getRangeAt(0).commonAncestorContainer
    return Boolean((editor && editor.contains(container)) || (stamp && stamp.contains(container)))
  }

  const insertEditorHtml = (html: string, status?: string) => {
    restoreSelection()
    document.execCommand('insertHTML', false, html)
    syncEditorToDraft(status)
  }

  const insertEditorText = (text: string, status?: string) => {
    restoreSelection()
    document.execCommand('insertText', false, text)
    syncEditorToDraft(status)
  }

  const insertDocumentBlock = (text: string) => {
    const block = String(text || '').trim()
    if (!block) return
    insertEditorHtml(plainTextToEditorHtml(block), 'Testo inserito nel documento.')
  }

  const insertFieldToken = (field: TemplateCompilerField) => {
    insertEditorText(placeholderName(field), `Campo ${field.label} associato al documento.`)
  }

  const applyContextSelection = () => {
    const params = new URLSearchParams(window.location.search)
    if (contextClienteId) params.set('id_cliente', contextClienteId)
    else params.delete('id_cliente')
    if (contextFascicoloId) {
      params.set('id_fascicolo', contextFascicoloId)
      params.set('case_id', contextFascicoloId)
    } else {
      params.delete('id_fascicolo')
      params.delete('case_id')
    }
    const suffix = params.toString()
    setWorkspaceStatus('Ricarico il template con cliente e fascicolo selezionati.')
    window.location.assign(`${window.location.pathname}${suffix ? `?${suffix}` : ''}`)
  }

  const openTemplateFromSidebar = (item: TemplateExample) => {
    setSelectedTemplateId(item.id)
    const href = appendQueryToHref(item.href || `/template-atti/compila/${encodeURIComponent(item.code || data.model.code)}`)
    if ((item.code || '').trim() && item.code !== data.model.code) {
      setWorkspaceStatus(`Apro il modello ${item.title}.`)
      window.location.assign(href)
      return
    }
    setWorkspaceStatus(`Template corrente confermato: ${item.title}.`)
  }

  const selectVisibleMultipleTemplates = () => {
    setMultipleSelection((current) => {
      const next = { ...current }
      visibleMultipleTemplates.forEach((item) => {
        const key = item.code || item.id
        if (key) next[key] = true
      })
      return next
    })
    setWorkspaceStatus(`${visibleMultipleTemplates.length} modelli visibili selezionati per la compilazione multipla.`)
  }

  const clearMultipleTemplates = () => {
    setMultipleSelection((current) => {
      const next = { ...current }
      visibleMultipleTemplates.forEach((item) => {
        const key = item.code || item.id
        if (key) next[key] = false
      })
      return next
    })
    setWorkspaceStatus('Selezione multipla svuotata.')
  }

  const runMultipleCompilation = () => {
    const selectedCodes = Object.entries(multipleSelection)
      .filter(([code, selected]) => selected && visibleMultipleCodes.has(code))
      .map(([code]) => code)
    if (!selectedCodes.length) {
      setWorkspaceStatus('Seleziona almeno un modello per la compilazione multipla.')
      return
    }
    onDownloadMultipleRtf(selectedCodes, exportPlainText(), exportHtml())
    setWorkspaceStatus(`Archivio RTF in preparazione per ${selectedCodes.length} modelli selezionati.`)
  }

  const applyFormat = (command: string) => {
    restoreSelection()
    if (command === 'justifyLeft' || command === 'justifyCenter' || command === 'justifyRight' || command === 'justifyFull') {
      const nextAlign = command === 'justifyLeft'
        ? 'left'
        : command === 'justifyCenter'
          ? 'center'
          : command === 'justifyRight'
            ? 'right'
            : 'justify'
      document.execCommand(command, false)
      syncEditorToDraft(
        nextAlign === 'left'
          ? 'Allineamento a sinistra applicato alla selezione.'
          : nextAlign === 'center'
            ? 'Allineamento centrato applicato alla selezione.'
            : nextAlign === 'right'
              ? 'Allineamento a destra applicato alla selezione.'
              : 'Testo selezionato giustificato.',
      )
      return
    }
    if (command === 'formatBlock:h1' || command === 'formatBlock:h2' || command === 'formatBlock:p' || command === 'formatBlock:blockquote') {
      const block = command.split(':')[1]
      document.execCommand('formatBlock', false, block)
      syncEditorToDraft(block === 'p' ? 'Paragrafo applicato alla selezione.' : 'Stile blocco applicato alla selezione.')
      return
    }
    if (command === 'hiliteColor') {
      document.execCommand('hiliteColor', false, '#fff2c2')
      syncEditorToDraft('Evidenziazione applicata alla selezione.')
      return
    }
    if (command === 'insertHorizontalRule') {
      insertEditorHtml('<p><br></p>', 'Spazio paragrafo inserito.')
      return
    }
    document.execCommand(command, false)
    const labels: Record<string, string> = {
      bold: 'Grassetto applicato alla selezione.',
      italic: 'Corsivo applicato alla selezione.',
      underline: 'Sottolineato applicato alla selezione.',
      strikeThrough: 'Barrato applicato alla selezione.',
      insertUnorderedList: 'Elenco puntato applicato alla selezione.',
      insertOrderedList: 'Elenco numerato applicato alla selezione.',
      indent: 'Rientro aumentato.',
      outdent: 'Rientro ridotto.',
      undo: 'Ultima modifica annullata.',
      redo: 'Modifica ripristinata.',
    }
    syncEditorToDraft(labels[command] || 'Comando applicato alla selezione.')
  }

  const applyFontSelection = (fontKey: string) => {
    setDocumentFont(fontKey)
    if (hasEditorSelection()) {
      restoreSelection()
      document.execCommand('fontName', false, fontLabelByKey(data, fontKey))
      syncEditorToDraft('Font applicato alla selezione.')
      return
    }
    setWorkspaceStatus('Font documento applicato.')
  }

  const applySizeSelection = (size: number) => {
    onBodyFontSizeChange(size)
    if (hasEditorSelection()) {
      restoreSelection()
      document.execCommand('fontSize', false, '4')
      editorRef.current?.querySelectorAll('font[size="4"]').forEach((node) => {
        const element = node as HTMLElement
        element.style.fontSize = `${size}pt`
        element.removeAttribute('size')
      })
      syncEditorToDraft('Dimensione applicata alla selezione.')
      return
    }
    setWorkspaceStatus('Dimensione corpo documento applicata.')
  }

  const applyPreset = (presetKey: string) => {
    const preset = data.fontRegistry.stylePresets.find((item) => item.key === presetKey)
    setStylePreset(presetKey)
    if (!preset) return
    if (preset.documentFont) setDocumentFont(preset.documentFont)
    if (preset.headingFont) setHeadingFont(preset.headingFont)
    if (preset.fontSize) onBodyFontSizeChange(preset.fontSize)
    if (preset.lineHeight) onBodyLineHeightChange(preset.lineHeight)
    setWorkspaceStatus(`Preset stile applicato: ${preset.label}.`)
  }

  const addAudit = (message: string) => {
    setAuditRows((current) => [`${legalDateTimeNow()} - ${message}`, ...current].slice(0, 10))
  }

  const runLexAction = (action: TemplateLexAction) => {
    const fallbackProposal = buildLocalLexProposal(action, data, exportPlainText(), fields, customInstructions)
    const formData = new FormData()
    formData.set('model_code', data.model.code)
    formData.set('title', data.model.name)
    formData.set('testo_generato', exportPlainText())
    formData.set('testo_generato_html', exportHtml())
    formData.set('lex_mode', action.mode)
    formData.set('lex_action', action.id)
    if (customInstructions.trim()) formData.set('istruzioni_lex', customInstructions.trim())
    fields.forEach((field) => formData.set(field.name, fieldValues[field.name] || field.value || ''))
    formData.set('id_fascicolo', data.selectors.selectedFascicoloId)
    formData.set('case_id', data.selectors.selectedFascicoloId)
    formData.set('id_cliente', data.selectors.selectedClienteId)
    setWorkspaceStatus('Lex sta leggendo template, fascicolo, fonti e testo selezionato...')
    fetch(`/template-atti/api/assistente-redazionale/${encodeURIComponent(data.model.code)}`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        ...(csrfToken() ? { 'X-CSRFToken': csrfToken() } : {}),
      },
      body: formData,
    })
      .then((response) => response.json())
      .then((payload) => {
        const analysis = (payload?.analysis || {}) as Record<string, unknown>
        const issues = Array.isArray(analysis.issues) ? analysis.issues as Array<Record<string, unknown>> : []
        const nextSteps = Array.isArray(analysis.next_steps) ? analysis.next_steps.map((item) => String(item || '').trim()).filter(Boolean) : []
        const profile = (analysis.profile || {}) as Record<string, unknown>
        const schema = (analysis.schema_channel || {}) as Record<string, unknown>
        const firstIssue = issues.find((issue) => String(issue.title || issue.message || issue.detail || '').trim()) || {}
        const sourceSummary = [
          String(schema.label || '').trim(),
          String(profile.label || '').trim(),
          String((analysis.contextual_compliance as Record<string, unknown> | undefined)?.sourceLabel || '').trim(),
        ].filter(Boolean).join(' - ')
        const remoteProposed = [
          String(analysis.summary || '').trim(),
          String(firstIssue.suggested_action || firstIssue.detail || firstIssue.title || '').trim(),
          nextSteps.slice(0, 3).join('\n'),
          customInstructions.trim() ? `Istruzioni dell'avvocato: ${customInstructions.trim()}` : '',
        ].filter(Boolean).join('\n\n') || fallbackProposal.proposed
        const proposed = action.id === 'genera_clausola' ? fallbackProposal.proposed : remoteProposed
        const proposal: TemplateLexProposal = {
          ...fallbackProposal,
          id: `${action.id}_${Date.now()}`,
          proposed,
          reason: sourceSummary
            ? `Lex ha usato il profilo ${sourceSummary}, i campi del fascicolo e i controlli redazionali disponibili.`
            : fallbackProposal.reason,
          risk: issues.some((issue) => String(issue.level || '').toUpperCase() === 'BLOCK') ? 'warning' : fallbackProposal.risk,
          status: 'pending',
        }
        setProposals((current) => [proposal, ...current])
        addAudit(`Lex ha creato una proposta "${action.label}" con contesto fascicolo e fonti.`)
        setWorkspaceStatus('Proposta Lex pronta: accetta, modifica o rifiuta prima di applicarla.')
      })
      .catch(() => {
        setProposals((current) => [fallbackProposal, ...current])
        addAudit(`Lex ha creato una proposta locale "${action.label}".`)
        setWorkspaceStatus('Proposta Lex locale pronta: accetta, modifica o rifiuta prima di applicarla.')
      })
  }

  const updateProposal = (id: string, proposed: string) => {
    setProposals((current) => current.map((proposal) => proposal.id === id ? { ...proposal, proposed, status: 'modified' } : proposal))
  }

  const acceptProposal = (proposal: TemplateLexProposal) => {
    if (proposal.status === 'accepted') return
    const currentText = editorPlainText()
    let nextText = currentText
    if (proposal.original && proposal.proposed && currentText.includes(proposal.original)) {
      nextText = currentText.replace(proposal.original, proposal.proposed)
    } else if (proposal.proposed && !proposal.proposed.startsWith('Nessun')) {
      nextText = `${currentText.trim()}\n\n${proposal.proposed}`.trim()
    }
    setEditorContentFromText(nextText)
    setProposals((current) => current.map((item) => item.id === proposal.id ? { ...item, status: 'accepted' } : item))
    addAudit(`Proposta accettata: ${proposal.title}.`)
  }

  const rejectProposal = (proposal: TemplateLexProposal) => {
    setProposals((current) => current.map((item) => item.id === proposal.id ? { ...item, status: 'rejected' } : item))
    addAudit(`Proposta rifiutata: ${proposal.title}.`)
  }

  const acceptAll = () => {
    proposals.filter((proposal) => proposal.status === 'pending' || proposal.status === 'modified').forEach(acceptProposal)
  }

  const copyDocument = () => {
    const plain = exportPlainText()
    const html = exportHtml()
    const clipboard = navigator.clipboard
    if (clipboard && 'write' in clipboard && typeof ClipboardItem !== 'undefined') {
      clipboard.write([
        new ClipboardItem({
          'text/html': new Blob([html], { type: 'text/html' }),
          'text/plain': new Blob([plain], { type: 'text/plain' }),
        }),
      ])
        .then(() => setWorkspaceStatus('Documento copiato negli appunti con formattazione.'))
        .catch(() => clipboard.writeText(plain).then(() => setWorkspaceStatus('Documento copiato negli appunti.')).catch(() => setWorkspaceStatus('Copia non disponibile dal browser corrente.')))
      return
    }
    clipboard?.writeText(plain)
      .then(() => setWorkspaceStatus('Documento copiato negli appunti.'))
      .catch(() => setWorkspaceStatus('Copia non disponibile dal browser corrente.'))
  }

  const saveCurrentDraft = () => {
    setWorkspaceStatus('Salvo il documento nel fascicolo...')
    Promise.resolve(onSave(exportPlainText(), exportHtml()))
      .then((link) => {
        if (link) {
          setWorkspaceStatus('Documento salvato nel fascicolo come bozza modificabile.')
        }
      })
      .catch(() => setWorkspaceStatus('Documento non salvato nel fascicolo: controlla i campi richiesti.'))
  }

  const panelTabs: TemplateEditorTab[] = ['Campi', 'Stile', 'Lex', 'Fonti', 'Controlli', 'Export']
  const inlineTools = [
    { label: 'Catalogo template atti', icon: ArrowLeft, action: () => window.location.assign(data.catalogHref || '/template-atti/catalogo') },
    { label: 'Titolo principale', icon: Heading1, action: () => applyFormat('formatBlock:h1') },
    { label: 'Titolo sezione', icon: Heading2, action: () => applyFormat('formatBlock:h2') },
    { label: 'Paragrafo', icon: Pilcrow, action: () => applyFormat('formatBlock:p') },
    { label: 'Grassetto', icon: Bold, action: () => applyFormat('bold') },
    { label: 'Corsivo', icon: Italic, action: () => applyFormat('italic') },
    { label: 'Sottolineato', icon: Underline, action: () => applyFormat('underline') },
    { label: 'Barrato', icon: Strikethrough, action: () => applyFormat('strikeThrough') },
    { label: 'Evidenzia', icon: Highlighter, action: () => applyFormat('hiliteColor') },
    { label: 'Allinea a sinistra', icon: AlignLeft, action: () => applyFormat('justifyLeft') },
    { label: 'Centra', icon: AlignCenter, action: () => applyFormat('justifyCenter') },
    { label: 'Allinea a destra', icon: AlignRight, action: () => applyFormat('justifyRight') },
    { label: 'Giustifica', icon: AlignJustify, action: () => applyFormat('justifyFull') },
    { label: 'Elenco puntato', icon: List, action: () => applyFormat('insertUnorderedList') },
    { label: 'Elenco numerato', icon: ListOrdered, action: () => applyFormat('insertOrderedList') },
    { label: 'Riduci rientro', icon: IndentDecrease, action: () => applyFormat('outdent') },
    { label: 'Aumenta rientro', icon: IndentIncrease, action: () => applyFormat('indent') },
    { label: 'Citazione', icon: Quote, action: () => applyFormat('formatBlock:blockquote') },
    { label: 'Annulla', icon: Undo2, action: () => applyFormat('undo') },
    { label: 'Ripristina', icon: Redo2, action: () => applyFormat('redo') },
    { label: 'Segnaposto', icon: Code2, action: () => setTab('Campi') },
  ]

  return (
    <section className={editorClassName} aria-label="Editor professionale template atti">
      <header className="iu-template-pro-topbar">
        <div className="iu-template-pro-brand">
          <span>
            <Scale size={17} aria-hidden="true" />
          </span>
          <div>
            <strong>IUSENTRA</strong>
            <small>Catalogo template legali RTF</small>
          </div>
        </div>
        <div className="iu-template-pro-actions">
          <button type="button" onClick={() => window.location.assign(data.catalogHref || '/template-atti/catalogo')}>
            <ArrowLeft size={15} aria-hidden="true" />
            Catalogo
          </button>
          <button type="button" className="is-success" disabled={importing} onClick={onImport}>
            <UploadCloud size={15} aria-hidden="true" />
            {importing ? 'Importazione...' : 'Importa documento'}
          </button>
          <button type="button" onClick={() => { setMultipleOpen((open) => !open); setTab('Export') }}>
            <Columns3 size={15} aria-hidden="true" />
            Compilazione multipla
          </button>
          <button type="button" onClick={() => window.location.assign('/template-atti/nuovo')}>
            <Plus size={15} aria-hidden="true" />
            Nuovo Template
          </button>
          <button type="button" onClick={() => setTab('Fonti')}>
            <HelpCircle size={15} aria-hidden="true" />
            Guida
          </button>
          <button type="button" className="is-danger" onClick={() => onDownloadRtf(exportPlainText(), undefined, exportHtml())}>
            <FileDown size={15} aria-hidden="true" />
            Esporta RTF
          </button>
        </div>
      </header>
      <div className="iu-template-pro-toolbar" aria-label="Barra strumenti documento">
        <select aria-label="Font documento" value={documentFont} onChange={(event) => applyFontSelection(event.currentTarget.value)}>
          {data.fontRegistry.fonts.map((font) => <option value={font.key} key={font.key}>{font.label}</option>)}
        </select>
        <select aria-label="Dimensione testo" value={bodyFontSize} onChange={(event) => applySizeSelection(Number(event.currentTarget.value))}>
          {[9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 22].map((size) => <option value={size} key={size}>{size}pt</option>)}
        </select>
        <div className="iu-template-pro-toolbar__icons">
          {inlineTools.map((tool) => {
            const Icon = tool.icon
            return (
              <button type="button" title={tool.label} aria-label={tool.label} key={tool.label} onMouseDown={(event) => event.preventDefault()} onClick={tool.action}>
                <Icon size={15} aria-hidden="true" />
              </button>
            )
          })}
        </div>
        <span className="iu-template-pro-toolbar__spacer" />
        <span className="iu-template-pro-toolbar__hint">Campi variabili</span>
        <button type="button" className="iu-template-pro-toolbar__panel" title="Mostra campi" onClick={() => setTab('Campi')}>
          <Columns3 size={15} aria-hidden="true" />
        </button>
      </div>
      {statusText ? <p className="iu-template-pro-status" role="status">{statusText}</p> : null}
      <div className="iu-template-pro-layout">
        <aside className="iu-template-pro-sidebar" aria-label="Catalogo template">
          <label className="iu-template-pro-search">
            <Search size={15} aria-hidden="true" />
            <input value={templateSearch} placeholder="Cerca template..." onChange={(event) => setTemplateSearch(event.currentTarget.value)} />
          </label>
          <div className="iu-template-pro-cats" aria-label="Categorie template">
            {categories.map((category) => (
              <button type="button" className={templateCategory === category ? 'is-active' : ''} key={category} onClick={() => setTemplateCategory(category)}>
                {category}
              </button>
            ))}
          </div>
          <div className="iu-template-pro-list">
            {visibleTemplates.slice(0, 12).map((item) => (
              <button type="button" className={`iu-template-pro-card${selectedTemplate?.id === item.id ? ' is-active' : ''}`} data-testid={`template-switch-${item.code || item.id}`} key={item.id} onClick={() => openTemplateFromSidebar(item)}>
                <span><FileText size={18} aria-hidden="true" /></span>
                <strong>{item.title}</strong>
                <small>{item.description || item.category}</small>
                <em>{item.fieldsCount || fields.length} campi</em>
              </button>
            ))}
          </div>
          <footer>{visibleTemplates.length} template disponibili</footer>
        </aside>
        <main className="iu-template-pro-canvas">
          <nav className="iu-template-pro-flow" aria-label="Flusso documento">
            {(data.editorWorkflow.length ? data.editorWorkflow : data.guidePreview.steps).slice(0, 10).map((step) => (
              <span className={`is-${step.state}`} key={step.id}>{step.label}</span>
            ))}
          </nav>
          <article className={paperClassName}>
            <div
              ref={stampRef}
              className="iu-template-pro-paper__stamp"
              contentEditable
              suppressContentEditableWarning
              spellCheck={false}
              tabIndex={0}
              onBlur={saveSelection}
              onKeyUp={saveSelection}
              onMouseUp={saveSelection}
              style={{ '--iu-template-stamp-offset-y': `${stampOffsetY}mm` } as CSSProperties}
            >
              {data.stamp.lines.length ? data.stamp.lines.map((line, index) => (
                <span className={line.bold ? 'is-bold' : ''} key={`${line.text}-${index}`}>{line.text}</span>
              )) : (
                <>
                  <span className="is-bold">[NOME_STUDIO]</span>
                  <span>[INDIRIZZO_STUDIO]</span>
                </>
              )}
            </div>
              <div className="iu-template-pro-paper__body-shell">
                <div
                  ref={editorRef}
                  className="iu-template-pro-paper__body"
                  contentEditable
                  suppressContentEditableWarning
                  spellCheck
                  data-testid="professional-template-editor"
                  role="textbox"
                  aria-multiline="true"
                  onInput={() => syncEditorToDraft()}
                  onKeyUp={saveSelection}
                  onMouseUp={saveSelection}
                  onBlur={saveSelection}
                  onFocus={saveSelection}
                  aria-label="Corpo documento modificabile"
                />
              </div>
              <footer className="iu-template-pro-paper__page-footer">
                <span>Pagina 1</span>
                <span>Il timbro viene ripetuto nelle esportazioni su ogni pagina.</span>
              </footer>
          </article>
          <div className="iu-template-pro-page-boundary" aria-label="Fine pagina e inizio pagina successiva">
            <span>Fine pagina 1</span>
            <strong>Inizio pagina 2</strong>
          </div>
        </main>
        <aside className="iu-template-pro-fields" aria-label="Pannello editor template">
          <header>
            <div>
              <strong>{activeTab === 'Campi' ? 'Campi da compilare' : activeTab === 'Export' ? 'Esporta e firma' : activeTab}</strong>
              <small>{selectedTemplate?.title || data.model.name}</small>
            </div>
            <button type="button" title="Chiudi pannello" aria-label="Chiudi pannello" onClick={() => setTab('Campi')}>
              <XCircle size={16} aria-hidden="true" />
            </button>
          </header>
          <nav className="iu-template-pro-tabs" aria-label="Schede editor">
            {panelTabs.map((tab) => (
              <button type="button" className={activeTab === tab ? 'is-active' : ''} key={tab} onClick={() => setTab(tab)}>
                {tab === 'Export' ? 'Esporta' : tab}
              </button>
            ))}
          </nav>
          <div className="iu-template-pro-panel" ref={panelRef}>
            {activeTab === 'Campi' ? (
              <>
                <section className="iu-template-pro-context-card" aria-label="Cliente e fascicolo collegati">
                  <header>
                    <strong>Collegamento IUSENTRA</strong>
                    <span>{data.selectors.selectedFascicoloLabel || data.selectors.selectedClienteLabel || 'Seleziona cliente e fascicolo'}</span>
                  </header>
                  <label>
                    <span><UserRound size={14} aria-hidden="true" /> Cliente</span>
                    <select value={contextClienteId} onChange={(event) => {
                      const nextCliente = event.currentTarget.value
                      setContextClienteId(nextCliente)
                      const firstCase = data.selectors.fascicoli.find((item) => !nextCliente || item.clienteId === nextCliente)
                      if (firstCase && (!contextFascicoloId || data.selectors.fascicoli.find((item) => item.value === contextFascicoloId)?.clienteId !== nextCliente)) {
                        setContextFascicoloId(firstCase.value)
                      }
                    }}>
                      <option value="">Seleziona cliente</option>
                      {data.selectors.clienti.map((cliente) => <option value={cliente.value} key={cliente.value}>{cliente.label}</option>)}
                    </select>
                  </label>
                  <label>
                    <span><BriefcaseBusiness size={14} aria-hidden="true" /> Fascicolo</span>
                    <select value={contextFascicoloId} onChange={(event) => {
                      const value = event.currentTarget.value
                      setContextFascicoloId(value)
                      const selectedCase = data.selectors.fascicoli.find((item) => item.value === value)
                      if (selectedCase?.clienteId) setContextClienteId(selectedCase.clienteId)
                    }}>
                      <option value="">Seleziona fascicolo</option>
                      {data.selectors.fascicoli
                        .filter((fascicolo) => !contextClienteId || !fascicolo.clienteId || fascicolo.clienteId === contextClienteId)
                        .map((fascicolo) => <option value={fascicolo.value} key={fascicolo.value}>{fascicolo.label}</option>)}
                    </select>
                  </label>
                  <button type="button" onClick={applyContextSelection}>
                    <RefreshCw size={14} aria-hidden="true" />
                    Compila con dati fascicolo
                  </button>
                </section>
                {fieldGroups.map((group) => (
                  <section className="iu-template-pro-field-group" key={group.id}>
                    <h3>{group.title}</h3>
                    {group.fields.map((field) => (
                      <label key={field.name}>
                        <span>{field.label}</span>
                        {field.type === 'textarea' ? (
                          <textarea data-testid={`template-field-input-${field.name}`} value={fieldValues[field.name] || ''} placeholder={field.placeholder || field.label} onChange={(event) => updateField(field, event.currentTarget.value)} />
                        ) : field.options.length ? (
                          <select data-testid={`template-field-input-${field.name}`} value={fieldValues[field.name] || ''} onChange={(event) => updateField(field, event.currentTarget.value)}>
                            <option value="">{field.placeholder || 'Seleziona'}</option>
                            {field.options.map((option) => <option value={option.value} key={`${field.name}-${option.value}`}>{option.label}</option>)}
                          </select>
                        ) : (
                          <input data-testid={`template-field-input-${field.name}`} value={fieldValues[field.name] || ''} placeholder={field.placeholder || field.label} onChange={(event) => updateField(field, event.currentTarget.value)} />
                        )}
                        <div className="iu-template-pro-field-tools">
                          <small>{placeholderName(field)}</small>
                          <button type="button" onClick={() => insertFieldToken(field)}>
                            <Code2 size={13} aria-hidden="true" />
                            Inserisci campo
                          </button>
                        </div>
                        {field.note?.text ? <em>{field.note.text}</em> : null}
                      </label>
                    ))}
                  </section>
                ))}
                {importedDocument ? (
                  <section className="iu-template-pro-import-card" aria-label="Documento importato">
                    <h3>Template personalizzato importato</h3>
                    <p>{importedDocument.note || 'Documento acquisito: puoi svuotare la pagina, reinserire il testo e associare i campi del fascicolo.'}</p>
                    <dl>
                      <div><dt>File</dt><dd>{importedDocument.fileName}</dd></div>
                      <div><dt>Codifica</dt><dd>{importedDocument.encoding || 'riconosciuta automaticamente'}</dd></div>
                      <div><dt>Font rilevati</dt><dd>{importedDocument.fonts.length ? importedDocument.fonts.slice(0, 6).join(', ') : 'non dichiarati nel file'}</dd></div>
                    </dl>
                    <div>
                      <button type="button" onClick={() => { onDraftTextChange(''); setWorkspaceStatus('Pagina vuota pronta per associare i campi del fascicolo.') }}>Pagina vuota</button>
                      <button type="button" disabled={!importedDocument.text.trim() && !String(importedDocument.html || '').trim()} onClick={() => { onDraftTextChange(importedDocument.html || importedDocument.text); setWorkspaceStatus('Documento importato inserito nel template personalizzato.') }}>Inserisci testo importato</button>
                    </div>
                  </section>
                ) : null}
                <div className="iu-template-pro-progress">
                  <span>Compilazione</span>
                  <progress value={completion} max={100} />
                  <strong>{completion}%</strong>
                </div>
              </>
            ) : null}
            {activeTab === 'Stile' ? (
              <section className="iu-template-pro-style">
                <label>
                  <span>Preset stile documento</span>
                  <select value={stylePreset} onChange={(event) => applyPreset(event.currentTarget.value)}>
                    {data.fontRegistry.stylePresets.map((preset) => <option value={preset.key} key={preset.key}>{preset.label}</option>)}
                  </select>
                </label>
                <label>
                  <span>Font documento</span>
                  <select value={documentFont} onChange={(event) => setDocumentFont(event.currentTarget.value)}>
                    {data.fontRegistry.fonts.map((font) => <option value={font.key} key={font.key}>{font.label}</option>)}
                  </select>
                </label>
                <label>
                  <span>Font titoli</span>
                  <select value={headingFont} onChange={(event) => setHeadingFont(event.currentTarget.value)}>
                    {data.fontRegistry.fonts.map((font) => <option value={font.key} key={font.key}>{font.label}</option>)}
                  </select>
                </label>
                <label>
                  <span>Font area di lavoro</span>
                  <select value={uiFont} onChange={(event) => setUiFont(event.currentTarget.value)}>
                    {data.fontRegistry.fonts.filter((font) => font.category === 'moderno' || font.usage.includes('interfaccia')).map((font) => <option value={font.key} key={font.key}>{font.label}</option>)}
                  </select>
                </label>
                <label>
                  <span>Font placeholder</span>
                  <select value={placeholderFont} onChange={(event) => setPlaceholderFont(event.currentTarget.value)}>
                    {data.fontRegistry.fonts.filter((font) => font.tone === 'mono' || font.category === 'placeholder').map((font) => <option value={font.key} key={font.key}>{font.label}</option>)}
                  </select>
                </label>
                <label>
                  <span>Fallback esportazione</span>
                  <select value={fallbackFont} onChange={(event) => setFallbackFont(event.currentTarget.value)}>
                    {data.fontRegistry.fonts.map((font) => <option value={font.key} key={font.key}>{font.label}</option>)}
                  </select>
                </label>
                <div className="iu-template-guide-format-controls" aria-label="Formato testo">
                  <span>Corpo testo</span>
                  <button type="button" onClick={() => onBodyFontSizeChange(Math.max(9, bodyFontSize - 1))}>A-</button>
                  <strong>{bodyFontSize} pt</strong>
                  <button type="button" onClick={() => onBodyFontSizeChange(Math.min(22, bodyFontSize + 1))}>A+</button>
                  <span>Interlinea</span>
                  <button type="button" onClick={() => onBodyLineHeightChange(Math.max(1.2, Number((bodyLineHeight - 0.1).toFixed(2))))}>-</button>
                  <strong>{bodyLineHeight.toFixed(2)}</strong>
                  <button type="button" onClick={() => onBodyLineHeightChange(Math.min(2.6, Number((bodyLineHeight + 0.1).toFixed(2))))}>+</button>
                </div>
                <div className="iu-template-pro-segmented" aria-label="Allineamento documento">
                  {[
                    ['left', 'Sinistra'],
                    ['center', 'Centro'],
                    ['right', 'Destra'],
                    ['justify', 'Giustifica'],
                  ].map(([value, label]) => (
                    <button type="button" className={textAlign === value ? 'is-active' : ''} key={value} onMouseDown={(event) => event.preventDefault()} onClick={() => {
                      setTextAlign(value)
                      applyFormat(value === 'left' ? 'justifyLeft' : value === 'center' ? 'justifyCenter' : value === 'right' ? 'justifyRight' : 'justifyFull')
                    }}>
                      {label}
                    </button>
                  ))}
                </div>
                <div className="iu-template-pro-stamp-controls" aria-label="Posizione timbro studio">
                  <strong><Move size={14} aria-hidden="true" /> Timbro studio spostabile</strong>
                  <div>
                    {[
                      ['top-left', 'Alto sinistra'],
                      ['top-center', 'Alto centro'],
                      ['top-right', 'Alto destra'],
                      ['middle-left', 'Centro sinistra'],
                      ['middle-right', 'Centro destra'],
                    ].map(([value, label]) => (
                      <button type="button" className={stampPosition === value ? 'is-active' : ''} key={value} onClick={() => { setStampPosition(value); setWorkspaceStatus(`Timbro spostato: ${label}.`) }}>
                        {label}
                      </button>
                    ))}
                  </div>
                  <label className="iu-template-pro-stamp-offset">
                    <span>Sposta timbro in alto/basso</span>
                    <input type="range" min="-40" max="80" value={stampOffsetY} onChange={(event) => {
                      const value = Number(event.currentTarget.value)
                      setStampOffsetY(value)
                      setWorkspaceStatus(value === 0 ? 'Timbro riportato alla posizione base.' : value > 0 ? `Timbro spostato verso il basso di ${value} mm.` : `Timbro spostato verso l'alto di ${Math.abs(value)} mm.`)
                    }} />
                    <strong>{stampOffsetY > 0 ? `+${stampOffsetY}` : stampOffsetY} mm</strong>
                  </label>
                  <p>Seleziona una riga del timbro o del testo e usa font, dimensione, grassetto o corsivo dalla barra strumenti.</p>
                </div>
              </section>
            ) : null}
            {activeTab === 'Lex' ? (
              <section className="iu-template-pro-lex">
                <div className="iu-template-pro-privacy">
                  <ShieldCheck size={16} aria-hidden="true" />
                  <span>{data.lexRevision.privacyPolicy.message}</span>
                </div>
                <div className="iu-template-pro-modes">
                  {data.lexRevision.modes.map((mode) => (
                    <button type="button" className={activeLexMode === mode ? 'is-active' : ''} key={mode} onClick={() => setActiveLexMode(mode)}>
                      {lexModeLabel(mode)}
                    </button>
                  ))}
                </div>
                <label>
                  <span>Istruzioni personalizzate per Lex</span>
                  <textarea value={customInstructions} placeholder="Es. mantieni tono assertivo e richiami sintetici alle fonti già presenti" onChange={(event) => setCustomInstructions(event.currentTarget.value)} />
                </label>
                <div className="iu-template-pro-lex-actions">
                  {lexActions.map((action) => (
                    <button type="button" key={action.id} onClick={() => runLexAction(action)}>
                      <Sparkles size={14} aria-hidden="true" />
                      {action.label}
                    </button>
                  ))}
                </div>
                <div className="iu-template-pro-proposals">
                  <header>
                    <strong>Proposte in diff</strong>
                    <button type="button" disabled={!proposals.some((proposal) => proposal.status === 'pending' || proposal.status === 'modified')} onClick={acceptAll}>Applica tutte le proposte accettabili</button>
                  </header>
                  {proposals.length ? proposals.map((proposal) => (
                    <article className={`iu-template-pro-diff-card is-${proposal.status}`} key={proposal.id}>
                      <div>
                        <Badge tone={proposal.risk}>{lexModeLabel(proposal.mode)}</Badge>
                        <Badge tone={proposal.status === 'accepted' ? 'success' : proposal.status === 'rejected' ? 'danger' : 'warning'}>{proposal.status === 'accepted' ? 'Accettata' : proposal.status === 'rejected' ? 'Rifiutata' : proposal.status === 'modified' ? 'Modificata' : 'Da decidere'}</Badge>
                      </div>
                      <h4>{proposal.title}</h4>
                      {proposal.original ? <del>{proposal.original}</del> : null}
                      <textarea value={proposal.proposed} onChange={(event) => updateProposal(proposal.id, event.currentTarget.value)} />
                      <p>{proposal.reason}</p>
                      <footer>
                        <button type="button" onClick={() => acceptProposal(proposal)}>Accetta</button>
                        <button type="button" onClick={() => rejectProposal(proposal)}>Rifiuta</button>
                      </footer>
                    </article>
                  )) : <p>Nessuna proposta aperta.</p>}
                </div>
                {auditRows.length ? (
                  <div className="iu-template-pro-audit">
                    <strong>Registro proposte</strong>
                    {auditRows.map((row) => <span key={row}>{row}</span>)}
                  </div>
                ) : null}
              </section>
            ) : null}
            {activeTab === 'Fonti' ? (
              <section className="iu-template-pro-sources">
                <h3>Guida pratica integrata</h3>
                <p>{data.guidePreview.subtitle || data.summary}</p>
                <button type="button" onClick={() => insertDocumentBlock(data.guidePreview.subtitle || data.summary)}>
                  <BookOpen size={14} aria-hidden="true" />
                  Inserisci guida nel template
                </button>
                {(data.compliance.normativeReferences.length ? data.compliance.normativeReferences : []).slice(0, 8).map((ref) => (
                  <article key={ref.id || ref.title}>
                    <strong>{ref.title || ref.sourceTitle || ref.article}</strong>
                    <span>{ref.article || ref.reasonForApplication}</span>
                    <button type="button" onClick={() => insertDocumentBlock(`Riferimento normativo: ${ref.title || ref.sourceTitle || ref.article}${ref.article ? `, ${ref.article}` : ''}.`)}>
                      Inserisci riferimento
                    </button>
                  </article>
                ))}
                {!data.compliance.normativeReferences.length ? <p>Fonti disponibili nella pratica e nei controlli del modello.</p> : null}
              </section>
            ) : null}
            {activeTab === 'Controlli' ? (
              <section className="iu-template-pro-checks">
                <h3>Controllo finale</h3>
                <p><CheckCircle2 size={14} aria-hidden="true" /><strong>Controllo placeholder</strong>: verifica campi variabili, segnaposto residui e valori da confermare prima della versione finale.</p>
                <p><CheckCircle2 size={14} aria-hidden="true" /><strong>Controllo legal_basis</strong>: verifica la base giuridica dichiarata e i riferimenti normativi collegati al modello.</p>
                <p><CheckCircle2 size={14} aria-hidden="true" /><strong>Controllo privacy/PII</strong>: evidenzia dati personali, dati sensibili e contenuti da trattare con policy privacy esplicita.</p>
                {[...data.checks.blocking, ...data.checks.recommended, ...data.compliance.nextActions].slice(0, 12).map((item) => (
                  <p key={item}><CheckCircle2 size={14} aria-hidden="true" />{item}</p>
                ))}
                {!data.checks.blocking.length && !data.checks.recommended.length ? <p><CheckCircle2 size={14} aria-hidden="true" />Controlli redazionali pronti.</p> : null}
              </section>
            ) : null}
            {activeTab === 'Export' ? (
              <section className="iu-template-pro-export">
                <button type="button" onClick={() => onDownloadRtf(exportPlainText(), undefined, exportHtml())}><Download size={15} aria-hidden="true" />RTF</button>
                <button type="button" onClick={() => onDownloadWord(exportPlainText(), exportHtml())}><FileDown size={15} aria-hidden="true" />DOCX</button>
                <button type="button" onClick={() => onPreviewPdf(exportPlainText(), exportHtml())}><Eye size={15} aria-hidden="true" />PDF</button>
                <button type="button" onClick={copyDocument}><Copy size={15} aria-hidden="true" />Copia</button>
                <button type="button" disabled={saving} onClick={saveCurrentDraft}><Save size={15} aria-hidden="true" />{saving ? 'Salvataggio...' : 'Salva nel fascicolo'}</button>
                <button type="button" onClick={() => onPrepareSignature(exportPlainText(), exportHtml())}><FileSignature size={15} aria-hidden="true" />Firma documento</button>
                <button type="button" onClick={() => onRefreshPreview(exportPlainText())}><RefreshCw size={15} aria-hidden="true" />Rigenera dal template</button>
                {multipleOpen ? (
                  <div className="iu-template-pro-multiple" aria-label="Compilazione multipla">
                    <strong>Compilazione multipla</strong>
                    <p>Usa i dati e il testo corrente per preparare più modelli RTF collegati alla stessa pratica.</p>
                    <div className="iu-template-pro-multiple-actions">
                      <button type="button" onClick={selectVisibleMultipleTemplates}>Seleziona visibili</button>
                      <button type="button" onClick={clearMultipleTemplates}>Deseleziona</button>
                      <span>{selectedMultipleCount} selezionati</span>
                    </div>
                    {visibleMultipleTemplates.map((item) => (
                      <label key={`multi-${item.code || item.id}`}>
                        <input
                          type="checkbox"
                          checked={multipleSelection[item.code || item.id] === true}
                          onChange={(event) => setMultipleSelection((current) => ({ ...current, [item.code || item.id]: event.currentTarget.checked }))}
                        />
                        <span>{item.title}</span>
                      </label>
                    ))}
                    <button type="button" onClick={runMultipleCompilation}><Columns3 size={15} aria-hidden="true" />Genera RTF selezionati</button>
                  </div>
                ) : null}
              </section>
            ) : null}
          </div>
        </aside>
      </div>
    </section>
  )
}

function GuidePreviewWorkspace({
  data,
  activeTool,
  draftText,
  importing,
  importedDocument,
  importStatus,
  pdfStatus,
  saving,
  bodyFontSize,
  bodyLineHeight,
  onToolSelect,
  onDraftTextChange,
  onBodyFontSizeChange,
  onBodyLineHeightChange,
  onEditorLayoutChange,
  onImport,
  onPreviewPdf,
  onDownloadWord,
  onDownloadRtf,
  onDownloadMultipleRtf,
  onRefreshPreview,
  onSave,
  onPrepareSignature,
}: {
  data: TemplateCompilerData
  activeTool: string
  draftText: string
  importing: boolean
  importedDocument: ImportedDocumentInfo | null
  importStatus: string
  pdfStatus: string
  saving: boolean
  bodyFontSize: number
  bodyLineHeight: number
  onToolSelect: (tool: string) => void
  onDraftTextChange: (value: string) => void
  onBodyFontSizeChange: (value: number) => void
  onBodyLineHeightChange: (value: number) => void
  onEditorLayoutChange: (value: Partial<TemplateEditorLayout>) => void
  onImport: () => void
  onPreviewPdf: (draftOverride?: string, htmlOverride?: string) => void
  onDownloadWord: (draftOverride?: string, htmlOverride?: string) => void
  onDownloadRtf: (draftOverride?: string, targetModelCode?: string, htmlOverride?: string) => void
  onDownloadMultipleRtf: (targetModelCodes: string[], draftOverride?: string, htmlOverride?: string) => void
  onRefreshPreview: (draftOverride?: string) => void
  onSave: (draftOverride?: string, htmlOverride?: string) => void
  onPrepareSignature: (draftOverride?: string, htmlOverride?: string) => void
}) {
  return (
    <ProfessionalTemplateEditorWorkspace
      data={data}
      activeTool={activeTool}
      draftText={draftText}
      importing={importing}
      importedDocument={importedDocument}
      importStatus={importStatus}
      pdfStatus={pdfStatus}
      saving={saving}
      bodyFontSize={bodyFontSize}
      bodyLineHeight={bodyLineHeight}
      onToolSelect={onToolSelect}
      onDraftTextChange={onDraftTextChange}
      onBodyFontSizeChange={onBodyFontSizeChange}
      onBodyLineHeightChange={onBodyLineHeightChange}
      onEditorLayoutChange={onEditorLayoutChange}
      onImport={onImport}
      onPreviewPdf={onPreviewPdf}
      onDownloadWord={onDownloadWord}
      onDownloadRtf={onDownloadRtf}
      onDownloadMultipleRtf={onDownloadMultipleRtf}
      onRefreshPreview={onRefreshPreview}
      onSave={onSave}
      onPrepareSignature={onPrepareSignature}
    />
  )
  const preview = data.guidePreview
  const toolbar = [
    { label: 'Setup', icon: ShieldCheck },
    { label: 'Pagine', icon: FileText },
    { label: 'Blocchi', icon: Layers },
    { label: 'Testi', icon: Type },
    { label: 'Aspetto', icon: Palette },
    { label: 'Fonti', icon: BookOpen },
    { label: 'AI', icon: Bot },
  ]
  const lines = data.stamp.lines.slice(0, 7)
  const guideBodyEditorClassName = [
    'iu-template-guide-body-editor',
    bodySizeClass(bodyFontSize),
    lineHeightClass(bodyLineHeight),
  ].join(' ')
  const visibleTemplateCode = data.model.code || preview.template.code
  const secondaryTemplateCode = preview.template.code && preview.template.code !== visibleTemplateCode ? preview.template.code : ''
  const sourceRows = data.compliance.normativeReferences.length
    ? data.compliance.normativeReferences.slice(0, 3).map((ref) => ref.title || ref.article || ref.sourceTitle)
    : []
  const toolPanel = (() => {
    if (activeTool === 'Setup') {
      return (
        <div>
          <b>Setup documento</b>
          <span>Il timbro legge i dati studio e l'atto resta collegato al fascicolo.</span>
          <ButtonLink href="/impostazioni?tab=studio" tone="neutral">Dati Studio</ButtonLink>
        </div>
      )
    }
    if (activeTool === 'Pagine') {
      return (
        <div>
          <b>Pagine</b>
          <span>Formato A4, margini e timbro coerenti con il modello PDF approvato.</span>
          <Button type="button" tone="neutral" onClick={() => onPreviewPdf()}>Verifica PDF</Button>
        </div>
      )
    }
    if (activeTool === 'Blocchi') {
      return (
        <div>
          <b>Blocchi atto</b>
          <span>{data.sections.map((section) => section.label).filter(Boolean).slice(0, 5).join(' · ') || 'Intestazione · Parti · Fatti · Diritto · Richieste'}</span>
        </div>
      )
    }
    if (activeTool === 'Aspetto') {
      return (
        <div>
          <b>Aspetto</b>
          <span>Stile studio e corpo testo leggibile nel modello.</span>
          <div className="iu-template-guide-format-controls" aria-label="Formato testo anteprima">
            <span>Corpo testo</span>
            <button type="button" onClick={() => onBodyFontSizeChange(Math.max(10, bodyFontSize - 1))}>A-</button>
            <strong>{bodyFontSize} pt</strong>
            <button type="button" onClick={() => onBodyFontSizeChange(Math.min(22, bodyFontSize + 1))}>A+</button>
            <span>Interlinea</span>
            <button type="button" onClick={() => onBodyLineHeightChange(Math.max(1.25, Number((bodyLineHeight - 0.1).toFixed(2))))}>-</button>
            <strong>{bodyLineHeight.toFixed(2)}</strong>
            <button type="button" onClick={() => onBodyLineHeightChange(Math.min(2.2, Number((bodyLineHeight + 0.1).toFixed(2))))}>+</button>
          </div>
          <Button type="button" tone="neutral" onClick={() => onDownloadWord()}>Scarica Word</Button>
        </div>
      )
    }
    if (activeTool === 'Fonti') {
      return (
        <div>
          <b>Fonti</b>
          <span>{sourceRows.length ? sourceRows.join(' · ') : 'Fonti e riferimenti del template disponibili nel fascicolo e nella guida.'}</span>
        </div>
      )
    }
    if (activeTool === 'AI') {
      return (
        <div>
          <b>AI</b>
          <span>Lex legge fascicolo, guida, template e testo in anteprima come contesto operativo.</span>
          <Button type="button" tone="neutral" onClick={() => window.dispatchEvent(new CustomEvent('iusentra:lex-open'))}>
            <Sparkles size={15} aria-hidden="true" />
            Apri Lex
          </Button>
        </div>
      )
    }
    return (
      <div>
        <b>Testi</b>
        <span>Il testo sotto è modificabile direttamente prima di PDF, Word o salvataggio nel fascicolo.</span>
        <Button type="button" tone="neutral" disabled={!preview.renderEndpoint} onClick={() => onRefreshPreview()}>Aggiorna anteprima dal template</Button>
      </div>
    )
  })()
  return (
    <section className="iu-template-guide-workspace" aria-label="Anteprima modifica Guida Pratica">
      <nav className="iu-template-guide-steps" aria-label="Passaggi guida pratica">
        {preview.steps.map((step) => (
          <span className={`iu-template-guide-step is-${step.state}`} key={step.id}>{step.label}</span>
        ))}
      </nav>
      <div className="iu-template-guide-shell">
        <div className="iu-template-guide-rail" aria-hidden="true">
          <strong>GP</strong>
          <span>Guida sotto</span>
        </div>
        <div className="iu-template-guide-body">
          <article className="iu-template-guide-hero">
            <div>
              <p className="iu-template-eyebrow">{preview.eyebrow}</p>
              <h2>{preview.title}</h2>
              <p>{preview.subtitle}</p>
            </div>
            <div className="iu-template-guide-hero__actions">
              <Button type="button" tone="neutral" disabled={!preview.importEndpoint || importing} onClick={onImport}>
                <UploadCloud size={16} aria-hidden="true" />
                {importing ? 'Importazione...' : preview.importLabel}
              </Button>
              <Button type="button" tone="neutral" disabled={!preview.previewPdfHref} onClick={() => onPreviewPdf()}>
                <Eye size={16} aria-hidden="true" />
                {preview.previewLabel}
              </Button>
              <Button type="button" tone="primary" disabled={saving || !data.selectors.selectedFascicoloId} onClick={() => onSave()}>
                <Save size={16} aria-hidden="true" />
                {saving ? 'Salvataggio...' : preview.saveLabel}
              </Button>
            </div>
          </article>
          {importStatus ? <p className="iu-template-guide-status" role="status">{importStatus}</p> : null}
          {pdfStatus ? <p className="iu-template-guide-status" role="status">{pdfStatus}</p> : null}
          <section className="iu-template-guide-editor iu-od-card">
            <header className="iu-template-guide-editor__head">
              <strong>Editor documento in anteprima</strong>
              <Badge tone="info">{preview.badge}</Badge>
            </header>
            <div className="iu-template-guide-editor__grid">
              <aside className="iu-template-guide-toolbar" aria-label="Strumenti editor documento">
                {toolbar.map((item) => {
                  const Icon = item.icon
                  const selected = activeTool === item.label
                  return (
                    <button type="button" className={selected ? 'is-active' : ''} key={item.label} title={item.label} aria-label={item.label} aria-pressed={selected} onClick={() => onToolSelect(item.label)}>
                      <Icon size={18} aria-hidden="true" />
                      <span>{item.label}</span>
                    </button>
                  )
                })}
              </aside>
              <article className="iu-template-guide-page-preview" aria-label="Pagina documento">
                <div className="iu-template-guide-paper">
                  <div className="iu-template-guide-paper__stamp" aria-label="Timbro studio">
                    {lines.length ? lines.map((line, index) => (
                      <span className={line.bold ? 'is-bold' : ''} key={`${line.text}-${index}`}>{line.text}</span>
                    )) : (
                      <>
                        <span className="is-bold">STUDIO LEGALE</span>
                        <span>Dati studio da Impostazioni</span>
                      </>
                    )}
                  </div>
                  <label className="iu-template-guide-editable iu-template-guide-editable--page">
                    <span>Corpo atto modificabile</span>
                    <textarea
                      data-testid="guide-body-editor"
                      className={guideBodyEditorClassName}
                      name="testo_generato"
                      value={draftText}
                      onChange={(event) => onDraftTextChange(event.currentTarget.value)}
                      aria-label="Corpo atto modificabile"
                      spellCheck
                    />
                  </label>
                </div>
              </article>
              <aside className="iu-template-guide-side">
                <section className="iu-template-guide-tool-panel">
                  <header>
                    <strong>{activeTool}</strong>
                    <span>operativo</span>
                  </header>
                  {toolPanel}
                </section>
                <section>
                  <header>
                    <strong>Template proposto</strong>
                    <span>automatico</span>
                  </header>
                  <div className="iu-template-guide-card">
                    <b>{visibleTemplateCode} {preview.template.name}</b>
                    {secondaryTemplateCode ? <small>Catalogo guida: {secondaryTemplateCode}</small> : null}
                    <small>{preview.template.reason}</small>
                  </div>
                  <div className="iu-template-guide-actions">
                    <ButtonLink href={data.catalogHref} tone="neutral">Cambia</ButtonLink>
                    <Button type="button" tone="neutral" disabled={!preview.renderEndpoint} onClick={() => onRefreshPreview()}>Aggiorna</Button>
                    <Button type="button" tone="neutral" onClick={() => onPreviewPdf()}>PDF</Button>
                    <Button type="button" tone="neutral" onClick={() => onDownloadWord()}>Word</Button>
                  </div>
                </section>
                <section>
                  <header>
                    <strong>Motivo guida</strong>
                  </header>
                  <p>{preview.reason}</p>
                </section>
                <section>
                  <header>
                    <strong>Documento avvocato</strong>
                    <span>facoltativo</span>
                  </header>
                  <button type="button" className="iu-template-guide-import-card" disabled={!preview.importEndpoint || importing} onClick={onImport}>
                    <b>{preview.import.note || "Importa nell'anteprima"}</b>
                    <small>{preview.import.formats}</small>
                  </button>
                </section>
                <section>
                  <header>
                    <strong>Impaginazione</strong>
                    <span>modello PDF</span>
                  </header>
                  {preview.layoutChecks.map((check) => (
                    <div className="iu-template-guide-check" key={check.label}>
                      <b>{check.label}</b>
                      <small>{check.value}</small>
                      <Badge tone={check.tone}>{check.tone === 'success' ? 'ok' : 'verifica'}</Badge>
                    </div>
                  ))}
                </section>
              </aside>
            </div>
          </section>
        </div>
      </div>
    </section>
  )
}

function TemplateCompilerView({ modelCode }: { modelCode: string }) {
  const [data, setData] = useState<TemplateCompilerData>(emptyTemplateCompilerPage)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [submitMessage, setSubmitMessage] = useState('')
  const [submitError, setSubmitError] = useState('')
  const [importing, setImporting] = useState(false)
  const [importStatus, setImportStatus] = useState('')
  const [importedDocument, setImportedDocument] = useState<ImportedDocumentInfo | null>(null)
  const [pdfStatus, setPdfStatus] = useState('')
  const [, setLastSavedEditorUrl] = useState('')
  const [activeGuideTool, setActiveGuideTool] = useState('Testi')
  const [guideDraftText, setGuideDraftText] = useState<string | null>(null)
  const [guideFontSize, setGuideFontSize] = useState(12)
  const [guideLineHeight, setGuideLineHeight] = useState(1.9)
  const guideImportRef = useRef<HTMLInputElement>(null)
  const contextRef = useRef<HTMLDivElement>(null)
  const compilerRef = useRef<HTMLDivElement>(null)
  const previewRenderTimerRef = useRef<number | undefined>(undefined)
  const guideEditorLayoutRef = useRef<Partial<TemplateEditorLayout>>({})
  const hiddenQuery = useMemo(queryHiddenInputs, [])

  useEffect(() => {
    document.body.classList.add('iu-template-pro-fullscreen')
    return () => document.body.classList.remove('iu-template-pro-fullscreen')
  }, [])

  function load() {
    setLoading(true)
    getTemplateAttiCompilerPage(modelCode)
      .then((payload) => {
        setData(payload)
        setGuideDraftText(guideDraftFromData(payload))
        setGuideFontSize(payload.guidePreview.editorLayout?.fontSize || payload.editorLayout.fontSize || 12)
        setGuideLineHeight(payload.guidePreview.editorLayout?.lineHeight || payload.editorLayout.lineHeight || 1.9)
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [modelCode])

  useEffect(() => () => {
    if (previewRenderTimerRef.current) window.clearTimeout(previewRenderTimerRef.current)
  }, [])

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

  const rememberGuideEditorLayout = (layout: Partial<TemplateEditorLayout>) => {
    guideEditorLayoutRef.current = { ...guideEditorLayoutRef.current, ...layout }
  }

  const submitCompiler = () => {
    const state = data.compliance.overallState || data.compliance.state
    const guideMode = data.guidePreview.enabled
    if (!data.selectors.selectedFascicoloId || submitting || (!guideMode && state === 'block')) return
    const formData = collectControlData(compilerRef.current)
    if (guideMode) {
      formData.set('requested_draft', 'working_draft')
      formData.set('confirmed_warning', '1')
    } else if (state === 'warning') {
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

  const buildGuideFormData = (draftOverride?: string, htmlOverride?: string) => {
    const rawDraft = draftOverride ?? guideDraftText ?? guideDraftFromData(data)
    const richHtml = htmlOverride || draftToEditorHtml(rawDraft)
    const formData = new FormData()
    hiddenQuery.forEach((item) => formData.set(item.name, item.value))
    collectControlData(compilerRef.current).forEach((value, name) => formData.set(name, value))
    formData.set('_react_return', '1')
    formData.set('model_code', data.model.code || modelCode)
    formData.set('title', data.model.name || data.guidePreview.template.name || 'Atto')
    formData.set('testo_generato', stripFixedStampFromDraft(editorHtmlToPlainText(richHtml), data))
    formData.set('testo_generato_html', stripHtmlStampFromDraft(richHtml, data))
    formData.set('testo_generato__editor_layout', JSON.stringify({
      font_family: guideEditorLayoutRef.current.fontFamily || data.editorLayout.fontFamily || data.fontRegistry.defaults.document,
      heading_font_family: guideEditorLayoutRef.current.headingFontFamily || data.editorLayout.headingFontFamily || data.fontRegistry.defaults.heading,
      placeholder_font_family: guideEditorLayoutRef.current.placeholderFontFamily || data.editorLayout.placeholderFontFamily || data.fontRegistry.defaults.placeholder,
      fallback_font_family: guideEditorLayoutRef.current.fallbackFontFamily || data.editorLayout.fallbackFontFamily || data.fontRegistry.defaults.fallback,
      document_style_preset: guideEditorLayoutRef.current.stylePreset || data.editorLayout.stylePreset || data.fontRegistry.defaults.stylePreset,
      font_size: guideFontSize,
      font_size_pt: guideEditorLayoutRef.current.fontSize || guideFontSize,
      line_height: guideLineHeight,
      text_align: guideEditorLayoutRef.current.textAlign || data.editorLayout.textAlign || 'justify',
      stamp_position: guideEditorLayoutRef.current.stampPosition || data.editorLayout.stampPosition || 'top-center',
      stamp_offset_y_mm: Number(guideEditorLayoutRef.current.stampOffsetY ?? data.editorLayout.stampOffsetY ?? 0),
      page_scale: data.guidePreview.editorLayout.pageScale || 100,
    }))
    formData.set('id_fascicolo', data.selectors.selectedFascicoloId)
    formData.set('case_id', data.selectors.selectedFascicoloId)
    formData.set('id_cliente', data.selectors.selectedClienteId)
    formData.set('requested_draft', 'working_draft')
    formData.set('confirmed_warning', '1')
    if (data.guidePreview.guideCode) formData.set('guida_pratica', data.guidePreview.guideCode)
    return formData
  }

  const refreshGuidePreviewFromCompiler = (draftOverride?: string) => {
    if (!data.guidePreview.renderEndpoint) return
    const formData = buildGuideFormData(draftOverride)
    setPdfStatus('Aggiorno anteprima dal template compilato...')
    submitFormJson(data.guidePreview.renderEndpoint, formData)
      .then((result) => {
        const text = String(result.testo_generato || result.text || '')
        if (text.trim()) setGuideDraftText(stripFixedStampFromDraft(text, data))
        setPdfStatus(result.message || 'Anteprima aggiornata dal template compilato.')
      })
      .catch((error) => setPdfStatus(error instanceof Error ? error.message : 'Anteprima non aggiornata. Il testo visibile resta modificabile.'))
  }

  const scheduleGuidePreviewFromCompiler = () => {
    if (!data.guidePreview.renderEndpoint) return
    if (previewRenderTimerRef.current) window.clearTimeout(previewRenderTimerRef.current)
    previewRenderTimerRef.current = window.setTimeout(refreshGuidePreviewFromCompiler, 700)
  }

  const saveGuidePreview = (draftOverride?: string, htmlOverride?: string) => {
    if (!data.guidePreview.saveEndpoint) {
      submitCompiler()
      return Promise.resolve('')
    }
    if (!data.selectors.selectedFascicoloId || submitting) return Promise.resolve('')
    setSubmitting(true)
    setSubmitError('')
    setSubmitMessage('')
    setPdfStatus('')
    return submitFormJson(data.guidePreview.saveEndpoint, buildGuideFormData(draftOverride, htmlOverride))
      .then((result) => {
        const link = result.editor_url || result.redirect_url || result.redirect || ''
        if (link) setLastSavedEditorUrl(link)
        setSubmitMessage(result.message || (link ? `Documento salvato nel fascicolo. Apri: ${link}` : 'Documento salvato nel fascicolo.'))
        return String(result.signature_url || link || '')
      })
      .catch((error) => {
        setSubmitError(error instanceof Error ? error.message : 'Documento non salvato nel fascicolo.')
        return ''
      })
      .finally(() => setSubmitting(false))
  }

  const submitGuideDocument = (
    endpoint: string,
    status: string,
    success: string,
    draftOverride?: string,
    htmlOverride?: string,
    configureFormData?: (formData: FormData) => void,
  ) => {
    if (!endpoint) return
    const formData = buildGuideFormData(draftOverride, htmlOverride)
    const title = data.model.name || data.guidePreview.template.name || 'Atto'
    if (!String(formData.get('title') || '').trim()) formData.set('title', title)
    if (!String(formData.get('testo_generato') || '').trim()) {
      formData.set(
        'testo_generato',
        `${title}\n\n${data.summary || 'Bozza generata dal template filtrato dalla Guida Pratica.'}`,
      )
    }
    configureFormData?.(formData)
    setPdfStatus(status)
    const form = document.createElement('form')
    form.method = 'POST'
    form.action = endpoint
    form.target = '_blank'
    form.enctype = 'multipart/form-data'
    const token = csrfToken()
    if (token) {
      appendHiddenInput(form, '_csrf_token', token)
      appendHiddenInput(form, 'csrf_token', token)
    }
    formData.forEach((value, name) => appendHiddenInput(form, name, value))
    document.body.appendChild(form)
    form.submit()
    form.remove()
    setPdfStatus(success)
  }

  const downloadGuideWord = (draftOverride?: string, htmlOverride?: string) => {
    submitGuideDocument(data.guidePreview.wordHref, 'Preparo documento DOCX...', 'Documento DOCX aperto.', draftOverride, htmlOverride)
  }

  const downloadGuideRtf = (draftOverride?: string, targetModelCode?: string, htmlOverride?: string) => {
    const endpoint = targetModelCode
      ? `/template-atti/compila/${encodeURIComponent(targetModelCode)}/rtf`
      : data.guidePreview.rtfHref
    submitGuideDocument(endpoint, 'Preparo documento RTF...', 'Documento RTF aperto.', draftOverride, htmlOverride)
  }

  const downloadGuideMultipleRtf = (targetModelCodes: string[], draftOverride?: string, htmlOverride?: string) => {
    const codes = targetModelCodes.map((code) => String(code || '').trim()).filter(Boolean)
    if (!codes.length) {
      setPdfStatus('Seleziona almeno un modello per la compilazione multipla.')
      return
    }
    submitGuideDocument(
      '/template-atti/api/compilazione-multipla-rtf',
      'Preparo archivio RTF...',
      'Archivio RTF aperto.',
      draftOverride,
      htmlOverride,
      (formData) => {
        formData.delete('model_codes')
        codes.forEach((code) => formData.append('model_codes', code))
        formData.set('title', 'Compilazione multipla Template Atti')
      },
    )
  }

  const previewPdf = (draftOverride?: string, htmlOverride?: string) => {
    submitGuideDocument(data.guidePreview.previewPdfHref, 'Apro anteprima PDF...', 'Anteprima PDF aperta.', draftOverride, htmlOverride)
  }

  const prepareSignature = (draftOverride?: string, htmlOverride?: string) => {
    const openSignatureFromEditor = (editorUrl: string) => {
      if (/\/fascicoli\/[^/]+\/documenti\/[^/]+\/firma/i.test(String(editorUrl || ''))) {
        window.location.assign(editorUrl)
        return
      }
      const match = String(editorUrl || '').match(/\/fascicoli\/([^/]+)\/documenti\/([^/]+)\/editor/i)
      if (!match) {
        setPdfStatus('Salvataggio completato. Apri il documento dal fascicolo per firmarlo.')
        return
      }
      window.location.assign(`/fascicoli/${encodeURIComponent(match[1])}/documenti/${encodeURIComponent(match[2])}/firma`)
    }
    setPdfStatus('Salvo il documento nel fascicolo prima della firma...')
    saveGuidePreview(draftOverride, htmlOverride).then((link) => {
      if (link) openSignatureFromEditor(link)
    })
  }

  const importGuideDocument = () => {
    guideImportRef.current?.click()
  }

  const handleGuideImportFile = (file?: File) => {
    if (!file || importing) return
    const formData = new FormData()
    formData.append('file', file)
    setImporting(true)
    setImportStatus('Importo il documento nell\'anteprima...')
    submitFormJson(data.guidePreview.importEndpoint || '/template-atti/api/importa-documento', formData)
      .then((result) => {
        const importPayload = result as Record<string, unknown>
        const content = String(result.contenuto || result.content || '')
        const fontPayload = importPayload.fonts || importPayload.detectedFonts
        const fonts = Array.isArray(fontPayload)
          ? fontPayload.map((item: unknown) => String(item || '').trim()).filter(Boolean)
          : []
        const importedHtml = result.tipo === 'html' || result.tipo === 'pdf_layout' ? content : ''
        const importedText = importedHtml ? htmlToPlainText(content) : content
        setImportedDocument({
          fileName: String(importPayload.filename || file.name || ''),
          text: importedText,
          html: importedHtml,
          fonts,
          encoding: String(importPayload.encoding || importPayload.codifica || ''),
          note: String(importPayload.note || 'Documento importato: puoi associarlo ai campi del fascicolo dal pannello Campi.'),
        })
        if (content.trim()) {
          setGuideDraftText(importedHtml || importedText)
          setImportStatus('Documento importato correttamente. Accenti, font rilevati e campi del fascicolo sono disponibili per il template personalizzato.')
        } else {
          setImportStatus(result.errore || result.message || 'Documento importato, ma senza testo estraibile. Puoi salvarlo come originale dal fascicolo.')
        }
      })
      .catch((error) => setImportStatus(error instanceof Error ? error.message : 'Documento non importato nell\'anteprima.'))
      .finally(() => {
        setImporting(false)
        if (guideImportRef.current) guideImportRef.current.value = ''
      })
  }

  if (loading) {
    return <LoadingState title="Caricamento compilazione" message="Recupero campi, dati disponibili e controlli del modello." />
  }

  return (
    <main className="iu-content iu-page iu-template-pro-host" aria-label="Editor professionale template atti">
      <input
        ref={guideImportRef}
        type="file"
        accept=".pdf,.doc,.docx,.rtf,.txt,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/rtf,text/plain"
        className="iu-template-guide-file-input"
        onChange={(event) => handleGuideImportFile(event.currentTarget.files?.[0])}
      />
      <div className="iu-template-compiler-page">
        <GuidePreviewWorkspace
          data={data}
          activeTool={activeGuideTool}
          draftText={guideDraftText ?? guideDraftFromData(data)}
          importing={importing}
          importedDocument={importedDocument}
          importStatus={importStatus}
          pdfStatus={submitMessage || submitError || pdfStatus}
          saving={submitting}
          bodyFontSize={guideFontSize}
          bodyLineHeight={guideLineHeight}
          onToolSelect={setActiveGuideTool}
          onDraftTextChange={(value) => setGuideDraftText(value)}
          onBodyFontSizeChange={setGuideFontSize}
          onBodyLineHeightChange={setGuideLineHeight}
          onEditorLayoutChange={rememberGuideEditorLayout}
          onImport={importGuideDocument}
          onPreviewPdf={previewPdf}
          onDownloadWord={downloadGuideWord}
          onDownloadRtf={downloadGuideRtf}
          onDownloadMultipleRtf={downloadGuideMultipleRtf}
          onRefreshPreview={refreshGuidePreviewFromCompiler}
          onSave={saveGuidePreview}
          onPrepareSignature={prepareSignature}
        />

        {false ? (
          <>
            <section className={`iu-template-compiler-hero iu-od-surface${data.guidePreview.enabled ? ' iu-template-compiler-hero--compact' : ''}`}>
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
                  <p>Cliente e pratica collegano il template ai dati già disponibili nello studio.</p>
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

            <div className="iu-template-compiler-form iu-od-card" ref={compilerRef} onInput={scheduleGuidePreviewFromCompiler} onChange={scheduleGuidePreviewFromCompiler}>
              <input type="hidden" name="_react_return" value="1" />
              <input type="hidden" name="id_cliente" value={data.selectors.selectedClienteId} />
              <input type="hidden" name="id_fascicolo" value={data.selectors.selectedFascicoloId} />
              <input type="hidden" name="requested_draft" value={data.guidePreview.enabled || (data.compliance.overallState || data.compliance.state) === 'warning' ? 'working_draft' : 'final_draft'} />
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
                <Button type="button" tone="primary" disabled={!data.selectors.selectedFascicoloId || submitting || (!data.guidePreview.enabled && (data.compliance.overallState || data.compliance.state) === 'block')} title={!data.selectors.selectedFascicoloId ? 'Seleziona prima una pratica collegata.' : !data.guidePreview.enabled && (data.compliance.overallState || data.compliance.state) === 'block' ? 'Completa i controlli bloccanti prima di creare la bozza.' : undefined} onClick={submitCompiler}>
                  <Save size={17} aria-hidden="true" />
                  {submitting ? 'Creazione in corso...' : !data.guidePreview.enabled && (data.compliance.overallState || data.compliance.state) === 'block' ? 'Completa i controlli' : data.selectors.selectedFascicoloId ? data.submitLabel : 'Seleziona pratica collegata'}
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
          </>
        ) : null}
      </div>
    </main>
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
              message="La schermata resta neutra finché non sono disponibili template consultabili."
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
