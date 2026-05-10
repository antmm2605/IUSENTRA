import { useDeferredValue, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileText,
  Filter,
  Globe2,
  LockKeyhole,
  Plus,
  Search,
  ShieldCheck,
  Trash2,
  UsersRound,
} from 'lucide-react'
import { Badge, Button, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import {
  emptyPrivacyRegistroPage,
  getPrivacyRegistroPage,
  type PrivacyRegistroPageData,
  type PrivacyTreatment,
} from '../privacyRegistroData'
import { redirectAfterSuccess, submitFormJson } from '../formSubmit'
import './PrivacyRegistroPage.css'

type StatusFilter = 'tutti' | 'attivi' | 'inattivi' | 'extra_ue' | 'da_completare'
type SubmitState = { saving: boolean; tone: 'success' | 'danger' | 'neutral'; message: string }

function sourceLabel(source: string): string {
  if (source === 'repository_reali') return 'Dati dello studio'
  if (source === 'errore_controllato') return 'Dati parziali'
  return source || 'Registro privacy'
}

function textOrDash(value: string): string {
  return value || 'n.d.'
}

function emptySubmit(): SubmitState {
  return { saving: false, tone: 'neutral', message: '' }
}

function normalise(value: string): string {
  return value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
}

function DeleteTreatmentButton({ item }: { item: PrivacyTreatment }) {
  const [state, setState] = useState<SubmitState>(() => emptySubmit())
  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!window.confirm(`Eliminare dal registro il trattamento "${item.name}"?`)) return
    setState({ saving: true, tone: 'neutral', message: 'Eliminazione...' })
    try {
      const result = await submitFormJson(item.deleteAction, new FormData(event.currentTarget))
      setState({ saving: false, tone: 'success', message: result.message || 'Trattamento eliminato.' })
      redirectAfterSuccess(result, '/privacy/registro')
    } catch (error) {
      setState({ saving: false, tone: 'danger', message: error instanceof Error ? error.message : 'Eliminazione non riuscita.' })
    }
  }
  return (
    <form onSubmit={handleSubmit}>
      <button type="submit" className="iu-privacy-delete" title="Elimina trattamento" disabled={state.saving}>
        <Trash2 size={16}/>
        <span>{state.saving ? 'Elimino...' : 'Elimina'}</span>
      </button>
    </form>
  )
}

function isTreatmentVisible(item: PrivacyTreatment, query: string, status: StatusFilter): boolean {
  const haystack = normalise([
    item.name,
    item.purpose,
    item.dataCategory,
    item.legalBasis,
    item.subjects,
    item.recipients,
    item.retention,
    item.securityMeasures,
    item.processor,
    item.notes,
  ].join(' '))
  const matchesQuery = !query.trim() || haystack.includes(normalise(query.trim()))
  if (!matchesQuery) return false
  if (status === 'attivi') return item.active
  if (status === 'inattivi') return !item.active
  if (status === 'extra_ue') return item.extraEuTransfer
  if (status === 'da_completare') return item.riskFlags.length > 0
  return true
}

function StatCard({ icon, label, value, note, tone = 'primary' }: { icon: ReactNode; label: string; value: number | string; note: string; tone?: string }) {
  return (
    <article className={`iu-privacy-stat iu-privacy-stat--${tone}`}>
      <div>{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  )
}

function TreatmentCard({ item }: { item: PrivacyTreatment }) {
  const hasWarnings = item.riskFlags.length > 0
  return (
    <article className={`iu-privacy-treatment ${!item.active ? 'is-muted' : ''}`}>
      <header>
        <div className="iu-privacy-treatment__icon"><FileText size={20}/></div>
        <div>
          <div className="iu-privacy-treatment__title">
            <strong>{item.name}</strong>
            <Badge tone={item.active ? 'success' : 'neutral'}>{item.active ? 'Attivo' : 'Inattivo'}</Badge>
            {item.extraEuTransfer ? <Badge tone="warning">Extra UE</Badge> : null}
            {hasWarnings ? <Badge tone="danger">{item.riskFlags.length} avvisi</Badge> : null}
          </div>
          <p>{textOrDash(item.purpose)}</p>
        </div>
        <DeleteTreatmentButton item={item}/>
      </header>
      <dl>
        <div><dt>Base giuridica</dt><dd>{textOrDash(item.legalBasis)}</dd></div>
        <div><dt>Categorie dati</dt><dd>{textOrDash(item.dataCategory)}</dd></div>
        <div><dt>Interessati</dt><dd>{textOrDash(item.subjects)}</dd></div>
        <div><dt>Destinatari</dt><dd>{textOrDash(item.recipients)}</dd></div>
        <div><dt>Conservazione</dt><dd>{textOrDash(item.retention)}</dd></div>
        <div><dt>Misure sicurezza</dt><dd>{textOrDash(item.securityMeasures)}</dd></div>
        <div><dt>Responsabile</dt><dd>{textOrDash(item.processor)}</dd></div>
        <div><dt>Aggiornato</dt><dd>{item.updatedLabel}</dd></div>
      </dl>
      {item.extraEuTransfer || item.destinationCountry ? (
        <div className="iu-privacy-transfer">
          <Globe2 size={16}/>
          <span>Trasferimento extra UE: {textOrDash(item.destinationCountry)}</span>
        </div>
      ) : null}
      {item.riskFlags.length ? (
        <div className="iu-privacy-flags">
          {item.riskFlags.map((flag) => (
            <span className={`iu-privacy-flag iu-privacy-flag--${flag.tone}`} key={`${item.id}-${flag.code}`}>
              <AlertTriangle size={14}/>
              <strong>{flag.label}</strong>
              {flag.message}
            </span>
          ))}
        </div>
      ) : (
        <div className="iu-privacy-ok"><CheckCircle2 size={15}/>Scheda completa nei campi essenziali.</div>
      )}
      {item.notes ? <p className="iu-privacy-note">{item.notes}</p> : null}
    </article>
  )
}

function NewTreatmentForm({ data, open }: { data: PrivacyRegistroPageData; open: boolean }) {
  const [state, setState] = useState<SubmitState>(() => emptySubmit())
  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setState({ saving: true, tone: 'neutral', message: 'Salvataggio in corso...' })
    try {
      const result = await submitFormJson(data.actions.create, new FormData(event.currentTarget))
      setState({ saving: false, tone: 'success', message: result.message || 'Trattamento aggiunto al registro.' })
      redirectAfterSuccess(result, '/privacy/registro')
    } catch (error) {
      setState({ saving: false, tone: 'danger', message: error instanceof Error ? error.message : 'Salvataggio non riuscito.' })
    }
  }
  if (!open) return null
  return (
    <Panel title="Nuovo trattamento" subtitle="Scheda operativa con salvataggio auditato." icon={<Plus size={17}/>}>
      <form className="iu-privacy-form" onSubmit={handleSubmit}>
        <label className="span2">
          <span>Nome / descrizione *</span>
          <input name="nome" required placeholder="Es. Gestione clienti e pratiche legali"/>
        </label>
        <label className="span2">
          <span>Finalità del trattamento</span>
          <textarea name="finalita" rows={3} placeholder="Scopo per cui vengono trattati i dati"/>
        </label>
        <label>
          <span>Categorie di dati</span>
          <input name="categoria_dati" placeholder="Anagrafici, contatto, legali, giudiziari"/>
        </label>
        <label>
          <span>Base giuridica</span>
          <select name="base_giuridica" defaultValue="">
            <option value="">Seleziona base giuridica</option>
            {data.facets.legalBasis.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
          </select>
        </label>
        <label>
          <span>Soggetti interessati</span>
          <input name="soggetti_interessati" placeholder="Clienti, collaboratori, fornitori"/>
        </label>
        <label>
          <span>Destinatari</span>
          <input name="destinatari" placeholder="Autorita giudiziarie, consulenti, soggetti autorizzati"/>
        </label>
        <label>
          <span>Termine di conservazione</span>
          <input name="termine_conservazione" placeholder="Es. 10 anni dalla chiusura del rapporto"/>
        </label>
        <label>
          <span>Misure di sicurezza</span>
          <input name="misure_sicurezza" placeholder="Backup, MFA, cifratura, audit log"/>
        </label>
        <label>
          <span>Responsabile esterno</span>
          <input name="responsabile" placeholder="Ragione sociale o referente"/>
        </label>
        <label>
          <span>Paese destinazione extra UE</span>
          <input name="paese_destinazione" placeholder="Compilare solo se applicabile"/>
        </label>
        <label className="iu-privacy-check">
          <input name="trasferimento_extra_ue" type="checkbox" value="1"/>
          <span>Trasferimento dati extra UE</span>
        </label>
        <label className="span2">
          <span>Note</span>
          <textarea name="note" rows={3} placeholder="Note interne, fonte valutazione o istruzioni operative"/>
        </label>
        <div className="iu-privacy-form__actions span2">
          <Button href={data.actions.list}>Annulla</Button>
          <button type="submit" className="iu-button iu-button--primary" disabled={state.saving}>{state.saving ? 'Salvataggio...' : 'Aggiungi al registro'}</button>
          {state.message ? <span role={state.tone === 'danger' ? 'alert' : 'status'}>{state.message}</span> : null}
        </div>
      </form>
    </Panel>
  )
}

export function PrivacyRegistroPage() {
  const [data, setData] = useState<PrivacyRegistroPageData>(emptyPrivacyRegistroPage)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<StatusFilter>('tutti')
  const [formOpen, setFormOpen] = useState(false)
  const deferredQuery = useDeferredValue(query)

  useEffect(() => {
    let active = true
    setLoading(true)
    getPrivacyRegistroPage()
      .then((payload) => {
        if (!active) return
        setData(payload)
        setFormOpen(payload.page.formOpenByDefault)
      })
      .catch((caught: unknown) => {
        if (!active) return
        setError(caught instanceof Error ? caught.message : 'Registro GDPR non disponibile.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [])

  const visibleTreatments = data.treatments.filter((item) => isTreatmentVisible(item, deferredQuery, status))

  return (
    <main className="iu-content iu-privacy-page">
      <section className="iu-privacy-hero">
        <div className="iu-privacy-hero__icon"><ShieldCheck size={25}/></div>
        <div>
          <span className="iu-privacy-eyebrow">Registro GDPR Art. 30</span>
          <h1>{data.page.title}</h1>
          <p>{data.page.subtitle}</p>
        </div>
        <div className="iu-privacy-hero__actions">
          <Button variant="primary" href={data.actions.create}><Plus size={16}/>Nuovo trattamento</Button>
          <Button href={data.actions.exportAuditCsv}><Download size={16}/>Esporta audit</Button>
        </div>
      </section>

      <section className="iu-privacy-stats" aria-label="Indicatori registro GDPR">
        <StatCard icon={<FileText size={20}/>} label="Trattamenti" value={data.summary.total} note="schede nel registro" tone="primary"/>
        <StatCard icon={<CheckCircle2 size={20}/>} label="Attivi" value={data.summary.active} note={`${data.summary.inactive} inattivi`} tone="success"/>
        <StatCard icon={<Globe2 size={20}/>} label="Extra UE" value={data.summary.extraEu} note="da presidiare" tone="warning"/>
        <StatCard icon={<LockKeyhole size={20}/>} label="Misure mancanti" value={data.summary.missingSecurity} note="sicurezza da completare" tone="danger"/>
        <StatCard icon={<AlertTriangle size={20}/>} label="Avvisi" value={data.summary.warnings} note="campi da verificare" tone="orange"/>
      </section>

      <section className="iu-privacy-toolbar" aria-label="Filtri registro GDPR">
        <label className="iu-privacy-search">
          <Search size={17}/>
          <input value={query} onChange={(event) => setQuery(event.currentTarget.value)} placeholder="Cerca per trattamento, finalità, base giuridica, destinatari..."/>
        </label>
        <label>
          <Filter size={16}/>
          <select value={status} onChange={(event) => setStatus(event.currentTarget.value as StatusFilter)}>
            {data.facets.status.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
          </select>
        </label>
        <button type="button" className="iu-privacy-toggle-form" onClick={() => setFormOpen((current) => !current)}>
          <Plus size={16}/>
          {formOpen ? 'Chiudi form' : 'Nuovo trattamento'}
        </button>
        <span className="iu-sync ok">{loading ? 'Sincronizzazione...' : sourceLabel(data.source)}</span>
      </section>

      {error ? <div className="iu-privacy-alert" role="alert"><AlertTriangle size={16}/>{error}</div> : null}
      <NewTreatmentForm data={data} open={formOpen}/>

      <section className="iu-privacy-layout">
        <div className="iu-privacy-list">
          <Panel
            title="Trattamenti registrati"
            subtitle="Elenco operativo con controlli di completezza essenziali."
            count={visibleTreatments.length}
            icon={<ShieldCheck size={17}/>}
          >
            {visibleTreatments.length ? (
              <div className="iu-privacy-treatment-list">
                {visibleTreatments.map((item) => <TreatmentCard item={item} key={item.id}/>)}
              </div>
            ) : (
              <div className="iu-privacy-empty">
                <FileText size={34}/>
                <strong>Nessun trattamento nella vista corrente</strong>
                <span>Modifica ricerca o filtro, oppure aggiungi una nuova scheda al registro.</span>
              </div>
            )}
          </Panel>
        </div>
        <aside className="iu-privacy-side">
          <Panel title="Azioni operative" subtitle="Collegamenti reali del gestionale." icon={<UsersRound size={17}/>}>
            <div className="iu-privacy-actions">
              <a href={data.actions.create}><Plus size={15}/>Nuovo trattamento</a>
              <a href={data.actions.clienti}><UsersRound size={15}/>Clienti e consensi</a>
              <a href={data.actions.audit}><ShieldCheck size={15}/>Registro attività</a>
              <a href={data.actions.settings}><LockKeyhole size={15}/>Impostazioni studio</a>
            </div>
          </Panel>
          <Panel title="Checklist GDPR" subtitle="Presidi minimi prima della revisione." icon={<CheckCircle2 size={17}/>}>
            <div className="iu-privacy-checklist">
              <span><CheckCircle2 size={15}/>Finalità e base giuridica compilate</span>
              <span><CheckCircle2 size={15}/>Categorie dati e interessati indicati</span>
              <span><CheckCircle2 size={15}/>Termine di conservazione esplicito</span>
              <span><CheckCircle2 size={15}/>Misure tecniche e organizzative presenti</span>
              <span><CheckCircle2 size={15}/>Trasferimenti extra UE verificati</span>
            </div>
          </Panel>
        </aside>
      </section>

      <FloatingLex
        context="registro-gdpr"
        title="Lex AI Registro GDPR"
        body="Legge i trattamenti, evidenzia campi mancanti e aiuta a preparare una revisione privacy senza sostituire il controllo umano."
        primaryHref={data.actions.lex}
        primaryLabel="Apri Lex privacy"
        secondaryHref={data.actions.audit}
        secondaryLabel="Registro attività"
      />
    </main>
  )
}
