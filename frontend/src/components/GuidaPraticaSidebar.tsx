import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { AlertTriangle, BookOpen, CheckCircle2, ClipboardCheck, FileText, Gavel, Landmark, ListChecks, RefreshCw, ShieldCheck } from 'lucide-react'
import { Badge } from './dashboard'
import {
  codiceFromResponse,
  emptyGuidaPraticaResponse,
  getCodiceGuidaPratica,
  getFascicoloGuidaPratica,
  type GuidaNormativa,
  type GuidaPratica,
  type GuidaPraticaResponse,
} from '../guidaPraticaData'
import './GuidaPraticaSidebar.css'

type TabKey = 'checklist' | 'normativa' | 'atto' | 'adempimenti'

type Props = {
  fascicoloId?: string
  codice?: string
  fascicoloTitle?: string
}

function text(value: unknown, fallback = ''): string {
  return String(value ?? fallback).trim()
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

function Section({ title, icon, children }:{title:string; icon:ReactNode; children:ReactNode}) {
  return (
    <section className="iu-guida-section">
      <h4>{icon}<span>{title}</span></h4>
      {children}
    </section>
  )
}

function NormativaItem({ item }:{item:GuidaNormativa}) {
  const label = [item.fonte, item.articolo].filter(Boolean).join(' art. ')
  return <li><strong>{label || 'Norma'}</strong><span>{item.descrizione || 'Descrizione da completare'}</span></li>
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

function DepositBanner({ guida }:{guida?:GuidaPratica}) {
  const status = guida?.codice_deposito
  if (!status) return null
  if (status.depositabile) {
    return (
      <div className="iu-guida-deposit is-ok" role="note">
        <ShieldCheck size={16}/>
        <span>{status.messaggio || 'Codice presente nel catalogo ufficiale PST/XSD.'}</span>
      </div>
    )
  }
  return (
    <div className="iu-guida-deposit is-warning" role="note">
      <AlertTriangle size={16}/>
      <span>{status.messaggio || 'Guida interna disponibile, ma non utilizzabile come codice definitivo di deposito.'}</span>
    </div>
  )
}

function ChecklistTab({ response }:{response:GuidaPraticaResponse}) {
  const checklist = response.checklist
  const guida = response.guida
  const completion = percent(checklist?.percentuale_completamento)
  const missingFields = checklist?.campi_mancanti || []
  const missingAttachments = checklist?.allegati_mancanti || []
  const missingWarnings = checklist?.avvertimenti_mancanti || []
  return (
    <div className="iu-guida-tab-panel">
      <DepositBanner guida={guida}/>
      <ReviewBanner guida={guida}/>
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
          <ol className="iu-guida-ordered">{guida.presupposti_sostanziali.map((item, index) => <li key={itemKey('presupposto', index, item)}>{item}</li>)}</ol>
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
        {struttura.length ? <ol className="iu-guida-ordered">{struttura.map((item, index) => <li key={itemKey('sezione', index, item.sezione)}><strong>{item.sezione}</strong>{item.contenuto ? <span>{item.contenuto}</span> : null}</li>)}</ol> : <p className="iu-empty">Struttura da completare.</p>}
      </Section>
      <Section title="Campi da compilare" icon={<ClipboardCheck size={16}/> }>
        {campi.length ? <ul className="iu-guida-fields">{campi.map((field, index) => <li key={itemKey('campo', index, field.id)}><strong>{field.label || readableValue(field.id, 'Campo')}</strong><span>{field.required === false ? 'Opzionale' : 'Obbligatorio'} - {readableValue(field.type, 'Campo')}</span>{field.formula ? <em>{field.formula}</em> : null}</li>)}</ul> : <p className="iu-empty">Campi da configurare.</p>}
      </Section>
    </div>
  )
}

function AdempimentiTab({ guida }:{guida?:GuidaPratica}) {
  const adempimenti = guida?.adempimenti_propedeutici || []
  const allegati = guida?.allegati_obbligatori || []
  const avvertenze = guida?.avvertenze_redazionali || []
  return (
    <div className="iu-guida-tab-panel">
      <Section title="Adempimenti propedeutici" icon={<ClipboardCheck size={16}/> }>
        {adempimenti.length ? <ol className="iu-guida-ordered">{adempimenti.map((item, index) => <li key={itemKey('adempimento', index, item.azione)}><strong>{item.azione}</strong><span>{item.obbligatorio === false ? 'Consigliato' : 'Obbligatorio'}</span>{item.sanzione_omissione ? <em>{item.sanzione_omissione}</em> : null}</li>)}</ol> : <p className="iu-empty">Adempimenti da configurare.</p>}
      </Section>
      <Section title="Allegati" icon={<FileText size={16}/> }>
        {allegati.length ? <ul className="iu-guida-fields">{allegati.map((item, index) => <li key={itemKey('allegato', index, item.id)}><strong>{item.label}</strong><span>{item.required === false ? 'Facoltativo/consigliato' : 'Obbligatorio'}</span></li>)}</ul> : <p className="iu-empty">Allegati da configurare.</p>}
      </Section>
      {avvertenze.length ? (
        <Section title="Avvertenze redazionali" icon={<AlertTriangle size={16}/> }>
          <ul className="iu-guida-warning-list">{avvertenze.map((item, index) => <li key={itemKey('avvertenza', index, item)}>{item}</li>)}</ul>
        </Section>
      ) : null}
    </div>
  )
}

export function GuidaPraticaSidebar({ fascicoloId = '', codice = '', fascicoloTitle = '' }: Props) {
  const [response, setResponse] = useState<GuidaPraticaResponse>(emptyGuidaPraticaResponse())
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState<TabKey>('checklist')
  const effectiveCode = useMemo(() => codiceFromResponse(response) || codice, [response, codice])
  const load = () => {
    setLoading(true)
    const loader = fascicoloId ? getFascicoloGuidaPratica(fascicoloId) : getCodiceGuidaPratica(codice)
    loader.then(setResponse).finally(() => setLoading(false))
  }
  useEffect(load, [fascicoloId, codice])
  const guida = response.guida
  const depositStatus = guida?.codice_deposito
  if (!fascicoloId && !codice) return null
  return (
    <aside id="guida-pratica" className="iu-guida-pratica" aria-label="Guida pratica della pratica">
      <header className="iu-guida-header">
        <div>
          <span><BookOpen size={16}/> Guida pratica</span>
          <h2>{guida?.denominazione || fascicoloTitle || 'Guida per codice materia'}</h2>
          <p>{effectiveCode ? `Codice ${effectiveCode}` : response.message || 'Codice materia da impostare nel fascicolo.'}</p>
        </div>
        <div className="iu-guida-header-actions">
          {depositStatus ? <Badge tone={depositStatus.depositabile ? 'success' : 'warning'}>{depositStatus.depositabile ? 'Codice PST verificato' : 'Guida interna'}</Badge> : null}
          {guida?.coverage ? <Badge tone={guida.coverage.needs_reviewer ? 'warning' : 'success'}>{coverageLabel(guida.coverage.level)}</Badge> : null}
          <button type="button" onClick={load} disabled={loading} title="Aggiorna guida pratica"><RefreshCw size={14}/></button>
        </div>
      </header>
      {loading && !response.generatedAt ? (
        <div className="iu-guida-loading"><RefreshCw size={16}/><span>Caricamento guida pratica...</span></div>
      ) : !response.ok ? (
        <div className="iu-guida-error"><AlertTriangle size={17}/><span>{response.message || 'Guida non disponibile.'}</span></div>
      ) : (
        <>
          <nav className="iu-guida-tabs" aria-label="Sezioni guida pratica">
            {(['checklist', 'normativa', 'atto', 'adempimenti'] as TabKey[]).map((key) => <button key={key} type="button" className={tab === key ? 'is-active' : ''} onClick={() => setTab(key)}>{key === 'checklist' ? 'Checklist' : key === 'normativa' ? 'Normativa' : key === 'atto' ? 'Atto' : 'Adempimenti'}</button>)}
          </nav>
          {tab === 'checklist' ? <ChecklistTab response={response}/> : null}
          {tab === 'normativa' ? <NormativaTab guida={guida}/> : null}
          {tab === 'atto' ? <AttoTab guida={guida}/> : null}
          {tab === 'adempimenti' ? <AdempimentiTab guida={guida}/> : null}
        </>
      )}
    </aside>
  )
}

export default GuidaPraticaSidebar
