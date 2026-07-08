import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { AlertTriangle, BookOpen, Calculator, CheckCircle2, ChevronDown, ChevronUp, ClipboardCheck, FilePenLine, FileText, Gavel, Landmark, ListChecks, RefreshCw, Scale, ShieldCheck, TimerReset, UploadCloud, UsersRound } from 'lucide-react'
import { Badge } from './dashboard'
import {
  codiceFromResponse,
  emptyGuidaPraticaResponse,
  getCodiceGuidaPratica,
  getFascicoloGuidaPratica,
  type GuidaDocumentPlan,
  type GuidaNormativa,
  type GuidaPratica,
  type GuidaPraticaResponse,
} from '../guidaPraticaData'
import './GuidaPraticaSidebar.css'

type TabKey = 'checklist' | 'contesto' | 'normativa' | 'atto' | 'adempimenti'

type Props = {
  fascicoloId?: string
  codice?: string
  fascicoloTitle?: string
}

const STANDARD_GUIDA_KEYS = new Set([
  'codice',
  'denominazione',
  'categoria',
  'sottocategoria',
  'registro_sicid',
  'coverage',
  'codice_deposito',
  'quick_help',
  'normativa',
  'tipologie_di_intervento',
  'presupposti_sostanziali',
  'legittimati_attivi',
  'obbligo_mediazione',
  'obbligo_mediazione_o_negoziazione_assistita',
  'richiesta_provvedimenti_urgenti',
  'avvertimenti_obbligatori',
  'adempimenti_propedeutici',
  'atto_principale',
  'allegati_obbligatori',
  'avvertenze_redazionali',
  'adempimenti_fiscali_telematici',
  'termini_processuali',
  'esiti_processuali_tipici',
  'esiti_processuali_attesi',
  'fonti_verifica_web',
  'presidi_operativi_integrativi',
  'arricchimento_iusentra',
  'catalogo_xsd',
  'macro_area',
  'kb_version',
  'ultimo_aggiornamento',
  'fascicolo_context',
])

function text(value: unknown, fallback = ''): string {
  return String(value ?? fallback).trim()
}

function formatItalianDate(value: unknown): string {
  const raw = text(value)
  const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})(?:$|T)/)
  if (!match) return raw
  const [, year, month, day] = match
  return `${day}/${month}/${year}`
}

function displayScalar(value: unknown, key = ''): string {
  if (typeof value === 'boolean') return value ? 'Sì' : 'No'
  const raw = text(value)
  if (!raw) return ''
  const keyLower = key.toLowerCase()
  if (keyLower.includes('data') || keyLower.includes('date') || keyLower.includes('verificato')) {
    return formatItalianDate(raw)
  }
  return formatItalianDate(raw)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function hasDisplayContent(value: unknown): boolean {
  if (typeof value === 'boolean') return true
  if (Array.isArray(value)) return value.length > 0
  if (isRecord(value)) return Object.keys(value).length > 0
  return Boolean(text(value))
}

function firstReadable(value: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const raw = value[key]
    if (typeof raw === 'boolean') return displayScalar(raw, key)
    const current = displayScalar(raw, key)
    if (current) return current
  }
  return ''
}

function compactRecord(value: Record<string, unknown>): string {
  const rows = Object.entries(value)
    .filter(([, entry]) => !Array.isArray(entry) && !isRecord(entry) && hasDisplayContent(entry))
    .slice(0, 4)
    .map(([key, entry]) => `${readableValue(key)}: ${displayScalar(entry, key)}`)
  return rows.join('; ')
}

function renderStructuredValue(entry: unknown): string {
  if (Array.isArray(entry)) return entry.map((item) => itemTitle(item)).filter(Boolean).join(', ')
  if (typeof entry === 'boolean') return displayScalar(entry)
  if (isRecord(entry)) {
    const compact = compactRecord(entry)
    if (compact) return compact
    const nested = Object.entries(entry)
      .filter(([, value]) => hasDisplayContent(value))
      .slice(0, 5)
      .map(([key, value]) => `${readableValue(key)}: ${renderStructuredValue(value)}`)
      .filter(Boolean)
    return nested.join(' · ')
  }
  return displayScalar(entry)
}

function itemTitle(value: unknown, fallback = 'Voce'): string {
  if (!isRecord(value)) return text(value, fallback)
  return firstReadable(value, ['label', 'titolo', 'testo', 'descrizione', 'azione', 'soggetto', 'esito', 'termine', 'id']) || fallback
}

function itemDetail(value: unknown): string {
  if (!isRecord(value)) return ''
  return firstReadable(value, ['quando', 'verifica', 'criterio', 'fonte', 'effetto', 'decorrenza', 'norma', 'criticita', 'note']) || compactRecord(value)
}

function extraGuidaFields(guida?: GuidaPratica): Array<[string, unknown]> {
  const payload = (guida || {}) as unknown as Record<string, unknown>
  return Object.entries(payload).filter(([key, value]) => !key.startsWith('_') && !STANDARD_GUIDA_KEYS.has(key) && hasDisplayContent(value))
}

function itemKey(prefix: string, index: number, label?: string) {
  return `${prefix}-${index}-${text(label)}`
}

function percent(value: unknown): number {
  const parsed = Number(value ?? 0)
  if (!Number.isFinite(parsed)) return 0
  return Math.max(0, Math.min(100, parsed))
}

function readableValue(value: unknown, fallback = 'Da verificare'): string {
  const raw = text(value)
  if (!raw) return fallback
  const explicit: Record<string, string> = {
    atto_esecutivo: 'Atto esecutivo',
    atto_impugnazione_o_opposizione: 'Impugnazione od opposizione',
    atto_introduttivo_o_deposito_generico: 'Atto introduttivo o deposito',
    atto_introduttivo_o_istanza_telematica: 'Atto o istanza telematica',
    ricorso_accertamento_tecnico_preventivo: 'Ricorso per accertamento tecnico preventivo',
    ricorso_cautelare: 'Ricorso cautelare',
    ricorso_cautelare_o_istruzione_preventiva: 'Ricorso cautelare o istruzione preventiva',
    ricorso_decreto_ingiuntivo: 'Ricorso per decreto ingiuntivo',
    ricorso_famiglia: 'Ricorso famiglia',
    ricorso_famiglia_minori: 'Ricorso famiglia e minori',
    ricorso_immigrazione_protezione: 'Ricorso immigrazione e protezione',
    ricorso_lavoro: 'Ricorso lavoro',
    ricorso_lavoro_previdenza: 'Ricorso lavoro o previdenza',
    ricorso_possessorio: 'Ricorso possessorio',
    ricorso_successioni: 'Ricorso successioni',
    ricorso_societario_o_crisi: 'Ricorso societario o crisi',
    ricorso_volontaria_giurisdizione: 'Ricorso di volontaria giurisdizione',
    boolean: 'Sì / no',
    currency: 'Importo',
    currency_or_exemption: 'Importo o esenzione',
    file_multi: 'Documenti',
    object_avvocato: 'Avvocato',
    object_immobile: 'Immobile',
    object_persona: 'Persona',
    select_ufficio: 'Ufficio giudiziario',
    string: 'Testo breve',
    table: 'Tabella',
    textarea: 'Testo esteso',
  }
  const normalized = raw.trim()
  return explicit[normalized] || normalized
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .toLowerCase()
    .replace(/^\w/u, (char) => char.toUpperCase())
}

function coverageLabel(value: unknown): string {
  const raw = text(value).toLowerCase()
  if (raw === 'curata') return 'Guida curata'
  if (raw === 'curata_parziale') return 'Da completare'
  if (raw === 'profilo_generato') return 'Profilo da completare'
  if (raw === 'catalogo_base') return 'Verifica catalogo'
  return readableValue(raw, 'Da verificare')
}

function guidaCodeLabel(code: string, guida?: GuidaPratica): string {
  if (!code) return ''
  const internal = code.startsWith('GUIDA_') || guida?.guida_interna_non_depositabile
  if (!internal) return `Scheda ${code}`
  const original = text(guida?.codice_originale_ricevuto)
  return original ? `Guida interna - riferimento ricevuto ${original}` : 'Guida interna non depositabile'
}

function Section({ title, icon, children }:{title:string; icon:ReactNode; children:ReactNode}) {
  return (
    <section className="iu-guida-section">
      <h4>{icon}<span>{title}</span></h4>
      {children}
    </section>
  )
}

function StructuredList({ items, prefix, empty = 'Voce da completare.' }:{items?: unknown[]; prefix:string; empty?:string}) {
  const list = items || []
  if (!list.length) return <p className="iu-empty">{empty}</p>
  return (
    <ul className="iu-guida-fields">
      {list.map((item, index) => {
        const title = itemTitle(item)
        const detail = itemDetail(item)
        return <li key={itemKey(prefix, index, title)}><strong>{title}</strong>{detail ? <span>{detail}</span> : null}</li>
      })}
    </ul>
  )
}

function StructuredBlock({ value, empty = 'Voce da completare.' }:{value: unknown; empty?: string}) {
  if (Array.isArray(value)) return <StructuredList items={value} prefix="structured-block" empty={empty}/>
  if (!value && value !== false) return <p className="iu-empty">{empty}</p>
  if (typeof value === 'boolean') return <p className="iu-guida-lead">{displayScalar(value)}</p>
  if (typeof value === 'boolean') return <p className="iu-guida-lead">{value ? 'Sì' : 'No'}</p>
  if (isRecord(value)) {
    return (
      <dl className="iu-guida-mini-kv">
        {Object.entries(value)
          .filter(([, entry]) => text(entry) || typeof entry === 'boolean' || (Array.isArray(entry) && entry.length))
          .map(([key, entry]) => (
            <div key={key}>
              <dt>{readableValue(key)}</dt>
              <dd>{renderStructuredValue(entry)}</dd>
            </div>
          ))}
      </dl>
    )
  }
  return <p className="iu-guida-lead">{text(value, empty)}</p>
}

function NormativaItem({ item }:{item:GuidaNormativa | unknown}) {
  if (!isRecord(item)) {
    return <li><strong>{text(item, 'Norma')}</strong><span>Riferimento da verificare nella scheda.</span></li>
  }
  const fonte = text(item.fonte || item.source || item.codice || item.norma)
  const articolo = text(item.articolo || item.article)
  const label = [fonte, articolo].filter(Boolean).join(' art. ')
  const detail = firstReadable(item, ['descrizione', 'description', 'testo', 'contenuto', 'nota', 'note']) || compactRecord(item)
  return <li><strong>{label || 'Norma'}</strong><span>{detail || 'Descrizione da completare'}</span></li>
}

function ReviewBanner({ guida }:{guida?:GuidaPratica}) {
  if (!guida?.coverage?.needs_reviewer) return null
  return (
    <div className="iu-guida-review" role="note">
      <AlertTriangle size={16}/>
      <span>{guida.coverage.message || 'Guida generata automaticamente: completare la revisione normativa.'}</span>
    </div>
  )
}

function DocumentPlanCard({ plan }: { plan?: GuidaDocumentPlan }) {
  if (!plan?.enabled) return null
  const recommended = plan.template?.recommended
  const alternatives = plan.template?.alternatives || []
  return (
    <section className="iu-guida-document-plan" aria-label="Documento suggerito dalla guida">
      <header>
        <span><FilePenLine size={16}/> Documento guidato</span>
        <Badge tone={plan.template?.autoLoad ? 'success' : recommended ? 'warning' : 'neutral'}>
          {plan.template?.autoLoad ? 'Template automatico' : recommended ? 'Scelta assistita' : 'Import o catalogo'}
        </Badge>
      </header>
      <div className="iu-guida-document-plan__body">
        <div>
          <strong>{plan.documentoSuggerito || 'Documento da produrre'}</strong>
          <p>{plan.template?.reason || 'La guida propone il documento operativo in base alla pratica.'}</p>
        </div>
        {recommended ? (
          <article className="iu-guida-template-suggested">
            <span>Modello filtrato</span>
            <strong>{recommended.title}</strong>
            <small>{[recommended.matter || recommended.area, recommended.channel, recommended.prefillStatus].filter(Boolean).join(' · ')}</small>
            {recommended.reasons?.length ? <em>{recommended.reasons.join(', ')}</em> : null}
            <a href={recommended.href}><FileText size={15}/> Apri modello filtrato</a>
          </article>
        ) : null}
        {alternatives.length ? (
          <details className="iu-guida-template-alternatives">
            <summary>Alternative pertinenti</summary>
            <ul>
              {alternatives.slice(0, 3).map((item) => (
                <li key={item.id || item.compilerCode}>
                  <a href={item.href}>{item.title}</a>
                  <span>{[item.matter || item.area, item.channel].filter(Boolean).join(' · ')}</span>
                </li>
              ))}
            </ul>
          </details>
        ) : null}
        {plan.import?.enabled ? (
          <div className="iu-guida-import-note">
            <UploadCloud size={15}/>
            <span>{plan.import.message || 'Puoi importare PDF o Word e salvarlo collegato al fascicolo.'}</span>
          </div>
        ) : null}
      </div>
    </section>
  )
}

function TermsActionList({ items, guida, fascicoloId }: { items?: unknown[]; guida?: GuidaPratica; fascicoloId?: string }) {
  const list = items || []
  if (!list.length) return <p className="iu-empty">Termini da completare o da verificare nel fascicolo.</p>
  const codice = text(guida?.codice)
  const original = text(guida?.codice_originale_ricevuto)
  const params = new URLSearchParams()
  if (codice) params.set('guida_pratica', codice)
  if (original) params.set('codice_guida', original)
  if (fascicoloId) params.set('id_fascicolo', fascicoloId)
  const href = `/scadenziario${params.toString() ? `?${params.toString()}` : ''}#calcolatore-termini-processuali`
  return (
    <div className="iu-guida-terms-action">
      <ul className="iu-guida-fields">
        {list.map((item, index) => {
          const record = isRecord(item) ? item : {}
          const title = itemTitle(item, 'Termine processuale')
          const detail = firstReadable(record, ['decorrenza', 'norma', 'criticita', 'natura', 'note']) || itemDetail(item)
          const duration = [text(record.giorni) ? `${text(record.giorni)} giorni` : '', text(record.mesi) ? `${text(record.mesi)} mesi` : '', text(record.anni) ? `${text(record.anni)} anni` : ''].filter(Boolean).join(' · ')
          return (
            <li key={itemKey('termine-operativo', index, title)}>
              <strong>{title}</strong>
              {duration ? <span>{duration}</span> : null}
              {detail ? <span>{detail}</span> : null}
            </li>
          )
        })}
      </ul>
      <a className="iu-guida-terms-action__link" href={href}>
        <Calculator size={15}/> Apri nello scadenziario
      </a>
      <small>Il calcolo resta assistito: prima si fissa decorrenza, atto e fase reale della pratica.</small>
    </div>
  )
}

function boolContext(value: unknown): string {
  if (isRecord(value)) return value.presente ? 'Presente' : 'Da verificare'
  return value ? 'Presente' : 'Da verificare'
}

function FascicoloContextCard({ fascicolo }: { fascicolo?: Record<string, unknown> }) {
  if (!fascicolo) return null
  const documentiCount = Number(fascicolo.documenti_count || 0)
  const attivitaCount = Number(fascicolo.attivita_count || 0)
  const parti = Array.isArray(fascicolo.parti) ? fascicolo.parti.filter(isRecord).filter((item) => text(item.nome)) : []
  const rows = ([
    ['Cliente', text(fascicolo.cliente)],
    ['Parti', parti.map((item) => [text(item.ruolo), text(item.nome)].filter(Boolean).join(': ')).filter(Boolean).join(' · ') || text(fascicolo.controparte)],
    ['Ufficio', text(fascicolo.ufficio || fascicolo.tribunale)],
    ['Oggetto pratica', text(fascicolo.oggetto || fascicolo.title)],
    ['Codice ufficiale', text(fascicolo.codice_oggetto_pst || fascicolo.codiceOggettoPst, 'Non valorizzato')],
    ['Valore', text(fascicolo.valore_causa)],
    ['Rito / fase', [text(fascicolo.tipo_procedimento || fascicolo.procedureType), text(fascicolo.stato)].filter(Boolean).join(' · ')],
    ['Preventivo', boolContext(fascicolo.preventivo)],
    ['Conferimento incarico', boolContext(fascicolo.conferimento_incarico)],
    ['Parcella', boolContext(fascicolo.parcella)],
    ['Documenti', documentiCount ? `${documentiCount} nel fascicolo` : 'Nessun documento'],
    ['Attività e scadenze', attivitaCount ? `${attivitaCount} attività registrate` : 'Da verificare'],
  ] as Array<[string, string]>).filter(([, value]) => text(value))
  return (
    <Section title="Contesto letto dal fascicolo" icon={<ShieldCheck size={16}/> }>
      <dl className="iu-guida-context-kv">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      {text(fascicolo.note) ? <p className="iu-guida-context-note">{text(fascicolo.note)}</p> : null}
    </Section>
  )
}

function ChecklistTab({ response, fascicoloId = '' }:{response:GuidaPraticaResponse; fascicoloId?: string}) {
  const checklist = response.checklist
  const guida = response.guida
  const completion = percent(checklist?.percentuale_completamento)
  const missingFields = checklist?.campi_mancanti || []
  const missingAttachments = checklist?.allegati_mancanti || []
  const missingWarnings = checklist?.avvertimenti_mancanti || []
  return (
    <div className="iu-guida-tab-panel">
      <ReviewBanner guida={guida}/>
      <DocumentPlanCard plan={response.documentPlan}/>
      {guida?.termini_processuali?.length ? (
        <Section title="Termini e scadenziario" icon={<TimerReset size={16}/> }>
          <TermsActionList items={guida.termini_processuali} guida={guida} fascicoloId={fascicoloId}/>
        </Section>
      ) : null}
      <div className="iu-guida-progress" aria-label="Completamento guida pratica">
        <div><strong>{completion}%</strong><span>{checklist?.completati ?? 0}/{checklist?.totale ?? 0} requisiti</span></div>
        <progress value={completion} max={100}/>
      </div>
      <Section title="Prima cosa da fare" icon={<ClipboardCheck size={16}/> }>
        <p className="iu-guida-lead">{guida?.quick_help?.prima_cosa_da_fare || 'Verifica codice materia, rito, parti, competenza e documenti fondativi.'}</p>
      </Section>
      <Section title="Campi mancanti" icon={<ListChecks size={16}/> }>
        {missingFields.length ? <ul className="iu-guida-checklist">{missingFields.map((field, index) => <li key={itemKey('field', index, field.id)} className="is-missing"><AlertTriangle size={14}/><span>{field.label || field.id}</span></li>)}</ul> : <p className="iu-guida-ok"><CheckCircle2 size={15}/> Campi obbligatori completati.</p>}
      </Section>
      <Section title="Allegati mancanti" icon={<FileText size={16}/> }>
        {missingAttachments.length ? <ul className="iu-guida-checklist">{missingAttachments.map((item, index) => <li key={itemKey('attachment', index, item.id)} className="is-missing"><AlertTriangle size={14}/><span>{item.label || item.id}</span></li>)}</ul> : <p className="iu-guida-ok"><CheckCircle2 size={15}/> Allegati obbligatori caricati o da verificare nel fascicolo.</p>}
      </Section>
      <Section title="Avvertimenti di rito" icon={<ShieldCheck size={16}/> }>
        {missingWarnings.length ? <ul className="iu-guida-checklist">{missingWarnings.map((item, index) => <li key={itemKey('warning', index, item.testo)} className="is-missing"><AlertTriangle size={14}/><span>{item.testo}</span></li>)}</ul> : <p className="iu-guida-ok"><CheckCircle2 size={15}/> Nessun avvertimento mancante rilevato.</p>}
      </Section>
    </div>
  )
}

function NormativaTab({ guida }:{guida?:GuidaPratica}) {
  const primari = guida?.normativa?.riferimenti_primari || []
  const secondari = guida?.normativa?.riferimenti_secondari || []
  const fontiWeb = guida?.fonti_verifica_web || []
  return (
    <div className="iu-guida-tab-panel">
      <Section title="Riferimenti primari" icon={<Landmark size={16}/> }>
        {primari.length ? <ul className="iu-guida-law-list">{primari.map((item, index) => <NormativaItem key={itemKey('law-primary', index, `${item.fonte}-${item.articolo}`)} item={item}/>)}</ul> : <p className="iu-empty">Riferimenti primari da completare.</p>}
      </Section>
      <Section title="Riferimenti secondari" icon={<BookOpen size={16}/> }>
        {secondari.length ? <ul className="iu-guida-law-list">{secondari.map((item, index) => <NormativaItem key={itemKey('law-secondary', index, `${item.fonte}-${item.articolo}`)} item={item}/>)}</ul> : <p className="iu-empty">Nessun riferimento secondario configurato.</p>}
      </Section>
      {guida?.presupposti_sostanziali?.length ? (
        <Section title="Presupposti sostanziali" icon={<Gavel size={16}/> }>
          <ol className="iu-guida-ordered">{guida.presupposti_sostanziali.map((item, index) => {
            const title = itemTitle(item, 'Presupposto')
            const detail = itemDetail(item)
            return <li key={itemKey('presupposto', index, title)}><strong>{title}</strong>{detail ? <span>{detail}</span> : null}</li>
          })}</ol>
        </Section>
      ) : null}
      {fontiWeb.length ? (
        <Section title="Fonti ufficiali verificate" icon={<ShieldCheck size={16}/> }>
          <ul className="iu-guida-source-list">
            {fontiWeb.map((fonte, index) => {
              const title = text(fonte.titolo || fonte.ente, 'Fonte ufficiale')
              return (
                <li key={itemKey('fonte-web', index, title)}>
                  <strong>{title}</strong>
                  <span>{[fonte.ente, fonte.ambito, fonte.verificato_il ? `verificata il ${formatItalianDate(fonte.verificato_il)}` : ''].filter(Boolean).join(' · ')}</span>
                  {fonte.url ? <a href={fonte.url} target="_blank" rel="noreferrer">Apri fonte</a> : null}
                </li>
              )
            })}
          </ul>
        </Section>
      ) : null}
    </div>
  )
}

function ContestoTab({ response }:{response:GuidaPraticaResponse}) {
  const guida = response.guida
  const mediazione = guida?.obbligo_mediazione || guida?.obbligo_mediazione_o_negoziazione_assistita
  const extraFields = extraGuidaFields(guida)
  return (
    <div className="iu-guida-tab-panel">
      <FascicoloContextCard fascicolo={response.fascicolo}/>
      <Section title="Tipologie di intervento" icon={<Scale size={16}/> }>
        <StructuredList items={guida?.tipologie_di_intervento} prefix="tipologia" empty="Tipologie di intervento da completare."/>
      </Section>
      <Section title="Legittimati attivi" icon={<UsersRound size={16}/> }>
        <StructuredList items={guida?.legittimati_attivi} prefix="legittimato" empty="Legittimati da completare."/>
      </Section>
      <Section title="Mediazione e urgenza" icon={<ShieldCheck size={16}/> }>
        <div className="iu-guida-split">
          <div>
            <strong>Condizione di procedibilità</strong>
            <StructuredBlock value={mediazione} empty="Da verificare sulla materia sostanziale."/>
          </div>
          <div>
            <strong>Provvedimenti urgenti</strong>
            <StructuredBlock value={guida?.richiesta_provvedimenti_urgenti} empty="Da valutare se emergono fumus, periculum o rischio sulla prova."/>
          </div>
        </div>
      </Section>
      {guida?.presidi_operativi_integrativi ? (
        <Section title="Presidi operativi integrativi" icon={<ShieldCheck size={16}/> }>
          <StructuredBlock value={guida.presidi_operativi_integrativi}/>
        </Section>
      ) : null}
      <Section title="Esiti processuali tipici" icon={<TimerReset size={16}/> }>
        <StructuredList items={guida?.esiti_processuali_tipici} prefix="esito" empty="Esiti tipici da completare."/>
      </Section>
      {extraFields.length ? (
        <Section title="Voci specialistiche della scheda" icon={<BookOpen size={16}/> }>
          <ul className="iu-guida-fields">
            {extraFields.map(([key, value]) => (
              <li key={key}>
                <strong>{readableValue(key)}</strong>
                <StructuredBlock value={value}/>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}
    </div>
  )
}

function AttoTab({ guida }:{guida?:GuidaPratica}) {
  const atto = guida?.atto_principale
  const struttura = atto?.struttura_obbligatoria || []
  const campi = atto?.campi_obbligatori || []
  return (
    <div className="iu-guida-tab-panel">
      <Section title="Atto da redigere" icon={<FileText size={16}/> }>
        <p className="iu-guida-lead">{atto?.denominazione || guida?.denominazione || 'Atto principale'}</p>
        <dl className="iu-guida-mini-kv">
          <div><dt>Tipo atto</dt><dd>{readableValue(atto?.tipo_atto)}</dd></div>
          <div><dt>Schema XSD</dt><dd>{atto?.schema_xsd_ministeriale || guida?.quick_help?.schema_xsd || 'Da verificare'}</dd></div>
        </dl>
      </Section>
      <Section title="Struttura obbligatoria" icon={<ListChecks size={16}/> }>
        {struttura.length ? <ol className="iu-guida-ordered">{struttura.map((item, index) => {
          const record: Record<string, unknown> = isRecord(item) ? item : {}
          const title = itemTitle(item, 'Sezione')
          const detail = firstReadable(record, ['contenuto', 'descrizione', 'testo', 'note']) || itemDetail(item)
          return <li key={itemKey('sezione', index, title)}><strong>{title}</strong>{detail ? <span>{detail}</span> : null}</li>
        })}</ol> : <p className="iu-empty">Struttura da completare.</p>}
      </Section>
      <Section title="Campi da compilare" icon={<ClipboardCheck size={16}/> }>
        {campi.length ? <ul className="iu-guida-fields">{campi.map((field, index) => {
          const record: Record<string, unknown> = isRecord(field) ? field : {}
          const title = itemTitle(field, readableValue(record.id, 'Campo'))
          const formula = text(record.formula)
          return <li key={itemKey('campo', index, title)}><strong>{title}</strong><span>{record.required === false ? 'Opzionale' : 'Obbligatorio'} - {readableValue(record.type, 'Campo')}</span>{formula ? <em>{formula}</em> : null}</li>
        })}</ul> : <p className="iu-empty">Campi da configurare.</p>}
      </Section>
    </div>
  )
}

function AdempimentiTab({ guida, fascicoloId = '' }:{guida?:GuidaPratica; fascicoloId?: string}) {
  const adempimenti = guida?.adempimenti_propedeutici || []
  const allegati = guida?.allegati_obbligatori || []
  const avvertenze = [...(guida?.avvertimenti_obbligatori || []), ...(guida?.avvertenze_redazionali || [])]
  const termini = guida?.termini_processuali || []
  return (
    <div className="iu-guida-tab-panel">
      <Section title="Adempimenti propedeutici" icon={<ClipboardCheck size={16}/> }>
        {adempimenti.length ? <ol className="iu-guida-ordered">{adempimenti.map((item, index) => {
          const record: Record<string, unknown> = isRecord(item) ? item : {}
          const title = itemTitle(item, `Passaggio ${text(record.step) || index + 1}`)
          const detail = itemDetail(item)
          const omissione = text(record.sanzione_omissione)
          return <li key={itemKey('adempimento', index, title)}><strong>{title}</strong><span>{record.obbligatorio === false ? 'Consigliato' : 'Obbligatorio'}</span>{detail ? <em>{detail}</em> : null}{omissione ? <em>{omissione}</em> : null}</li>
        })}</ol> : <p className="iu-empty">Adempimenti da configurare.</p>}
      </Section>
      <Section title="Allegati" icon={<FileText size={16}/> }>
        {allegati.length ? <ul className="iu-guida-fields">{allegati.map((item, index) => {
          const record: Record<string, unknown> = isRecord(item) ? item : {}
          const title = itemTitle(item, 'Allegato')
          return <li key={itemKey('allegato', index, title)}><strong>{title}</strong><span>{record.required === false ? 'Facoltativo/consigliato' : 'Obbligatorio'}</span></li>
        })}</ul> : <p className="iu-empty">Allegati da configurare.</p>}
      </Section>
      <Section title="Termini processuali" icon={<TimerReset size={16}/> }>
        <TermsActionList items={termini} guida={guida} fascicoloId={fascicoloId}/>
      </Section>
      {avvertenze.length ? (
        <Section title="Avvertenze redazionali" icon={<AlertTriangle size={16}/> }>
          <ul className="iu-guida-warning-list">{avvertenze.map((item, index) => {
            const title = itemTitle(item, 'Avvertenza')
            const detail = itemDetail(item)
            return <li key={itemKey('avvertenza', index, title)}><strong>{title}</strong>{detail ? <span>{detail}</span> : null}</li>
          })}</ul>
        </Section>
      ) : null}
    </div>
  )
}

export function GuidaPraticaSidebar({ fascicoloId = '', codice = '', fascicoloTitle = '' }: Props) {
  const [response, setResponse] = useState<GuidaPraticaResponse>(emptyGuidaPraticaResponse())
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState<TabKey>('checklist')
  const [expanded, setExpanded] = useState(() => typeof window !== 'undefined' && window.location.hash === '#guida-pratica')
  const [loadedKey, setLoadedKey] = useState('')
  const effectiveCode = useMemo(() => codiceFromResponse(response) || codice, [response, codice])
  const load = () => {
    const nextKey = fascicoloId ? `fascicolo:${fascicoloId}` : codice ? `codice:${codice}` : ''
    if (!nextKey || loading || loadedKey === nextKey) return
    setLoading(true)
    const loader = fascicoloId ? getFascicoloGuidaPratica(fascicoloId) : getCodiceGuidaPratica(codice)
    loader.then((payload) => {
      setResponse(payload)
      setLoadedKey(nextKey)
    }).finally(() => setLoading(false))
  }
  useEffect(() => {
    setResponse(emptyGuidaPraticaResponse())
    setLoadedKey('')
  }, [fascicoloId, codice])
  useEffect(() => {
    if (expanded) load()
  }, [expanded, fascicoloId, codice, loadedKey, loading])
  useEffect(() => {
    const openFromHash = () => {
      if (window.location.hash === '#guida-pratica') setExpanded(true)
    }
    openFromHash()
    window.addEventListener('hashchange', openFromHash)
    return () => window.removeEventListener('hashchange', openFromHash)
  }, [])
  useEffect(() => {
    window.dispatchEvent(new CustomEvent('iusentra:guida-pratica-panel', { detail: { expanded } }))
    return () => {
      window.dispatchEvent(new CustomEvent('iusentra:guida-pratica-panel', { detail: { expanded: false } }))
    }
  }, [expanded])
  useEffect(() => {
    if (expanded || typeof window === 'undefined') return
    const panel = document.getElementById('guida-pratica')
    const rail = panel?.closest('.iu-fas-guide-column')
    if (!panel || !rail) return
    let frame = 0
    const updatePinnedState = () => {
      frame = 0
      const button = panel.querySelector<HTMLElement>('.iu-guida-collapsed-main')
      if (!button) return
      const railRect = rail.getBoundingClientRect()
      const buttonRect = button.getBoundingClientRect()
      const pinTop = 96
      const pinActive = railRect.top <= pinTop && railRect.bottom >= pinTop + buttonRect.height
      panel.classList.toggle('iu-guida-pratica--viewport-pinned', pinActive)
      if (pinActive) {
        panel.style.setProperty('--iu-guida-pin-left', `${Math.round(railRect.left + 8)}px`)
      } else {
        panel.style.removeProperty('--iu-guida-pin-left')
      }
    }
    const requestUpdate = () => {
      if (frame) return
      frame = window.requestAnimationFrame(updatePinnedState)
    }
    updatePinnedState()
    window.addEventListener('scroll', requestUpdate, { passive: true })
    window.addEventListener('resize', requestUpdate)
    return () => {
      if (frame) window.cancelAnimationFrame(frame)
      panel.classList.remove('iu-guida-pratica--viewport-pinned')
      panel.style.removeProperty('--iu-guida-pin-left')
      window.removeEventListener('scroll', requestUpdate)
      window.removeEventListener('resize', requestUpdate)
    }
  }, [expanded])
  const guida = response.guida
  const suggestedMatch = response.matchedFromFascicolo
  const showOptionalEmpty = response.ok && response.guidaPraticaDisponibile === false
  const effectiveCodeLabel = guidaCodeLabel(effectiveCode, guida)
  if (!fascicoloId && !codice) return null
  if (!expanded) {
    return (
      <aside id="guida-pratica" className="iu-guida-pratica iu-guida-pratica--collapsed" aria-label="Guida pratica facoltativa">
        <button type="button" className="iu-guida-collapsed-main" onClick={() => setExpanded(true)}>
          <span><BookOpen size={16}/> Guida pratica</span>
          <strong>{guida?.denominazione || fascicoloTitle || 'Piano assistito'}</strong>
          <small>{effectiveCodeLabel || response.message || 'Facoltativa: il fascicolo resta operativo.'}</small>
        </button>
        <div className="iu-guida-collapsed-actions">
          <Badge tone="neutral">Facoltativa</Badge>
          {guida?.coverage ? <Badge tone={guida.coverage.needs_reviewer ? 'warning' : 'success'}>{coverageLabel(guida.coverage.level)}</Badge> : null}
          <button type="button" onClick={() => setExpanded(true)} title="Apri guida pratica"><ChevronDown size={16}/></button>
        </div>
      </aside>
    )
  }
  return (
    <aside id="guida-pratica" className="iu-guida-pratica" aria-label="Guida pratica della pratica">
      <header className="iu-guida-header">
        <div>
          <span><BookOpen size={16}/> Guida pratica</span>
          <h2>{guida?.denominazione || fascicoloTitle || 'Guida per codice materia'}</h2>
          <p>{effectiveCodeLabel || response.message || 'Guida facoltativa non collegata.'}</p>
          {suggestedMatch?.confirmation_required ? <p className="iu-guida-suggested-note">Suggerimento facoltativo dal contesto fascicolo. Il codice ufficiale resta nella scheda fascicolo e la guida non blocca il lavoro.</p> : null}
        </div>
        <div className="iu-guida-header-actions">
          {response.guidaPraticaFacoltativa !== false ? <Badge tone="neutral">Uso facoltativo</Badge> : null}
          {suggestedMatch ? <Badge tone="warning">Scheda suggerita</Badge> : effectiveCode ? <Badge tone="success">Scheda collegata</Badge> : null}
          {guida?.coverage ? <Badge tone={guida.coverage.needs_reviewer ? 'warning' : 'success'}>{coverageLabel(guida.coverage.level)}</Badge> : null}
          <button type="button" onClick={load} disabled={loading} title="Aggiorna guida pratica"><RefreshCw size={14}/></button>
          <button type="button" onClick={() => setExpanded(false)} title="Nascondi guida pratica"><ChevronUp size={14}/></button>
        </div>
      </header>
      {loading && !response.generatedAt ? (
        <div className="iu-guida-loading"><RefreshCw size={16}/><span>Caricamento guida pratica...</span></div>
      ) : showOptionalEmpty ? (
        <div className="iu-guida-empty" role="note">
          <BookOpen size={17}/>
          <span>{response.message || 'La guida pratica è facoltativa: puoi continuare a lavorare sul fascicolo oppure collegare una materia quando vuoi usarla.'}</span>
        </div>
      ) : !response.ok ? (
        <div className="iu-guida-error"><AlertTriangle size={17}/><span>{response.message || 'Guida non disponibile.'}</span></div>
      ) : (
        <>
          <nav className="iu-guida-tabs" aria-label="Sezioni guida pratica">
            {(['checklist', 'contesto', 'normativa', 'atto', 'adempimenti'] as TabKey[]).map((key) => <button key={key} type="button" className={tab === key ? 'is-active' : ''} onClick={() => setTab(key)}>{key === 'checklist' ? 'Ora' : key === 'contesto' ? 'Contesto' : key === 'normativa' ? 'Normativa' : key === 'atto' ? 'Atto' : 'Adempimenti'}</button>)}
          </nav>
          {tab === 'checklist' ? <ChecklistTab response={response} fascicoloId={fascicoloId}/> : null}
          {tab === 'contesto' ? <ContestoTab response={response}/> : null}
          {tab === 'normativa' ? <NormativaTab guida={guida}/> : null}
          {tab === 'atto' ? <AttoTab guida={guida}/> : null}
          {tab === 'adempimenti' ? <AdempimentiTab guida={guida} fascicoloId={fascicoloId}/> : null}
        </>
      )}
    </aside>
  )
}

export default GuidaPraticaSidebar
