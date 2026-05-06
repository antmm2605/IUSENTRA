import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  Loader2,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Star,
  Trash2,
} from 'lucide-react'
import {
  createPreventivoWizard,
  emptyPreventivoWizardPage,
  getPreventivoWizardPage,
  runPreventivoWizardCalculation,
  type PreventivoWizardPageData,
  type WizardCalculationResponse,
  type WizardClient,
  type WizardDraftRow,
  type WizardMode,
  type WizardPractice,
} from '../preventivoWizardData'
import {
  dateToItalian,
  formatEuro,
  isCompensoUnicoProfile,
  mergeCalculatedRowsWithManualRows,
  normalizeAmountInput,
  parseEuroInput,
  phaseKeyLabel,
  validateWizardForm,
  type WizardValidationErrors,
} from '../preventivoWizardUtils'
import { LoadingState } from '../ui/LoadingState'
import './PreventivoWizardPage.css'

type OpenMap = Record<string, boolean>

type QuickClient = {
  tipo: string
  nome: string
  cognome: string
  ragione_sociale: string
  email: string
  telefono: string
  codice_fiscale: string
  partita_iva: string
}

type ClauseState = {
  attiva: boolean
  modello: string
  fonte: string
  testo: string
  trattativa_individuale: boolean
}

type FinalOptions = {
  genera_conferimento: boolean
  apri_fascicolo_guidato: boolean
  informativa_art13_resa: boolean
}

const favoriteStorageKey = 'iusentra.preventivoWizard.favoritePractices'
const modeStorageKey = 'iusentra.preventivoWizard.mode'

const initialOpen: OpenMap = {
  cliente: true,
  tipologia: true,
  tassonomia: true,
  aggiuntive: false,
  calcolo: true,
  parametri: true,
  economici: true,
  fasi: true,
  adr: false,
  mediazione: false,
  integrazioni: false,
  spese: false,
  bozza: true,
  note: true,
  clausola: true,
  finali: true,
  refs: false,
  checklist: false,
  logic: false,
  coverage: false,
}

function safeStorageRead(key: string): string {
  try {
    return window.localStorage.getItem(key) || ''
  } catch {
    return ''
  }
}

function safeStorageWrite(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value)
  } catch {
    // La persistenza locale dei soli preferiti non è necessaria al salvataggio.
  }
}

function readFavorites(): string[] {
  const raw = safeStorageRead(favoriteStorageKey)
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw) as unknown
    return Array.isArray(parsed) ? parsed.map((item) => String(item || '').trim()).filter(Boolean) : []
  } catch {
    return []
  }
}

function Field({
  id,
  label,
  help,
  error,
  children,
}: {
  id: string
  label: string
  help?: string
  error?: string
  children: ReactNode
}) {
  const helpId = help ? `${id}-help` : undefined
  const errorId = error ? `${id}-error` : undefined
  return (
    <div className={`iu-pwiz-field ${error ? 'has-error' : ''}`}>
      <label htmlFor={id}>{label}</label>
      {children}
      {help ? <small id={helpId}>{help}</small> : null}
      {error ? <span className="iu-pwiz-error" id={errorId}>{error}</span> : null}
    </div>
  )
}

function TextInput({
  id,
  label,
  value,
  placeholder,
  help,
  error,
  type = 'text',
  onChange,
}: {
  id: string
  label: string
  value: string
  placeholder?: string
  help?: string
  error?: string
  type?: string
  onChange: (value: string) => void
}) {
  return (
    <Field id={id} label={label} help={help} error={error}>
      <input
        id={id}
        type={type}
        value={value}
        placeholder={placeholder}
        aria-describedby={[help ? `${id}-help` : '', error ? `${id}-error` : ''].filter(Boolean).join(' ') || undefined}
        onChange={(event) => onChange(event.target.value)}
      />
    </Field>
  )
}

function SelectInput({
  id,
  label,
  value,
  help,
  error,
  children,
  onChange,
}: {
  id: string
  label: string
  value: string
  help?: string
  error?: string
  children: ReactNode
  onChange: (value: string) => void
}) {
  return (
    <Field id={id} label={label} help={help} error={error}>
      <select
        id={id}
        value={value}
        aria-describedby={[help ? `${id}-help` : '', error ? `${id}-error` : ''].filter(Boolean).join(' ') || undefined}
        onChange={(event) => onChange(event.target.value)}
      >
        {children}
      </select>
    </Field>
  )
}

function SwitchRow({
  id,
  checked,
  label,
  help,
  onChange,
}: {
  id: string
  checked: boolean
  label: string
  help?: string
  onChange: (checked: boolean) => void
}) {
  return (
    <label className="iu-pwiz-switch" htmlFor={id}>
      <input id={id} type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span aria-hidden="true" />
      <strong>{label}</strong>
      {help ? <small>{help}</small> : null}
    </label>
  )
}

function StepCard({
  id,
  number,
  title,
  microcopy,
  label,
  open,
  onToggle,
  children,
}: {
  id: string
  number: string
  title: string
  microcopy: string
  label: string
  open: boolean
  onToggle: () => void
  children: ReactNode
}) {
  const contentId = `preventivo-wizard-step-${id}`
  return (
    <section className="iu-pwiz-step">
      <button className="iu-pwiz-step__head" type="button" onClick={onToggle} aria-expanded={open} aria-controls={contentId}>
        <span className="iu-pwiz-step__number">{number}</span>
        <span>
          <strong>{title}</strong>
          <small>{microcopy}</small>
        </span>
        <em>{label}</em>
        <ChevronDown size={18} aria-hidden="true" />
      </button>
      {open ? <div className="iu-pwiz-step__body" id={contentId}>{children}</div> : null}
    </section>
  )
}

function Accordion({
  id,
  title,
  description,
  badge,
  open,
  onToggle,
  children,
}: {
  id: string
  title: string
  description?: string
  badge?: string
  open: boolean
  onToggle: () => void
  children: ReactNode
}) {
  const contentId = `pwiz-accordion-${id}`
  return (
    <section className="iu-pwiz-accordion">
      <button type="button" onClick={onToggle} aria-expanded={open} aria-controls={contentId}>
        <span>
          <strong>{title}</strong>
          {description ? <small>{description}</small> : null}
        </span>
        <span>
          {badge ? <em>{badge}</em> : null}
          <ChevronDown size={17} aria-hidden="true" />
        </span>
      </button>
      {open ? <div id={contentId}>{children}</div> : null}
    </section>
  )
}

function Hero({ mode, onMode, backHref }: { mode: WizardMode; onMode: (mode: WizardMode) => void; backHref: string }) {
  return (
    <section className="iu-pwiz-hero" aria-labelledby="preventivo-guidato-title">
      <div className="iu-pwiz-hero__mark" aria-hidden="true">W</div>
      <div className="iu-pwiz-hero__copy">
        <span>CONSOLE GUIDATA</span>
        <h1 id="preventivo-guidato-title">Preventivo guidato</h1>
        <p>Nuovo cliente, tipologia pratica, motore normativo e bozza iniziale in un unico flusso, con meno rumore visivo e più spazio al lavoro reale.</p>
      </div>
      <div className="iu-pwiz-hero__actions">
        <div className="iu-pwiz-mode" role="group" aria-label="Modalità  wizard">
          <button type="button" className={mode === 'guidato' ? 'is-active' : ''} onClick={() => onMode('guidato')}>Guidato</button>
          <button type="button" className={mode === 'avanzato' ? 'is-active' : ''} onClick={() => onMode('avanzato')}>Avanzato</button>
        </div>
        <a className="iu-pwiz-back" href={backHref}><ArrowLeft size={16} aria-hidden="true" /> Torna ai preventivi</a>
        <div className="iu-pwiz-flow" aria-label="Flusso professionale">
          <strong>Flusso professionale</strong>
          <span>cliente</span>
          <span>tariffario</span>
          <span>bozza</span>
          <span>conferimento</span>
          <small>stato locale sicuro</small>
        </div>
      </div>
    </section>
  )
}

function StepRail() {
  const steps = [
    ['1', 'Cliente', 'Dati, fascicolo, oggetto'],
    ['2', 'Profilo pratica', 'Catalogo e tassonomia'],
    ['3', 'Calcolo', 'Fasi, spese, imposte'],
    ['4', 'Bozza', 'Voci, note e clausole'],
  ]
  return (
    <ol className="iu-pwiz-rail" aria-label="Sezioni principali preventivo guidato">
      {steps.map(([number, title, note]) => (
        <li key={number}>
          <span>{number}</span>
          <strong>{title}</strong>
          <small>{note}</small>
        </li>
      ))}
    </ol>
  )
}

function Tags({ values }: { values: string[] }) {
  const filtered = values.filter(Boolean)
  if (!filtered.length) return null
  return <div className="iu-pwiz-tags">{filtered.map((value) => <span key={value}>{value}</span>)}</div>
}

function StatusMessages({ warnings, message }: { warnings: string[]; message: string }) {
  if (!warnings.length && !message) return null
  return (
    <div className="iu-pwiz-messages" role="status">
      {message ? <p className="is-success"><CheckCircle2 size={16} aria-hidden="true" /> {message}</p> : null}
      {warnings.map((warning) => <p key={warning}><AlertCircle size={16} aria-hidden="true" /> {warning}</p>)}
    </div>
  )
}

function Sidebar({
  practice,
  client,
  calculation,
  data,
  open,
  onToggle,
}: {
  practice: WizardPractice | null
  client: WizardClient | null
  calculation: WizardCalculationResponse | null
  data: PreventivoWizardPageData
  open: OpenMap
  onToggle: (id: string) => void
}) {
  const total = calculation?.economic?.totale_label || formatEuro(0)
  const base = calculation?.economic?.imponibile_label || formatEuro(0)
  const refs = practice?.normative_references.length ? practice.normative_references : []
  const checklist = practice?.checklist_iniziale || []
  return (
    <aside className="iu-pwiz-sidebar" aria-label="Riepilogo intelligente">
      <div className="iu-pwiz-side-card">
        <header>
          <span>RIEPILOGO INTELLIGENTE</span>
          <em>desktop sticky</em>
        </header>
        <h2>Vista compatta del preventivo</h2>
        <Tags values={[
          practice?.area || '',
          practice?.area_tassonomica || '',
          practice?.macro_area_tassonomica || '',
          practice?.sottobranca_tassonomica || '',
          practice?.motore_label || '',
          practice?.redattore_label || '',
          practice?.label || '',
          data.support.audit.aligned ? 'Verificata su snapshot' : '',
        ]} />
        <h3>{practice?.label || 'Tipologia non selezionata'}</h3>
        <p>{practice?.summary || 'Seleziona una tipologia per attivare profilo, calcolo e riferimenti.'}</p>
        {practice?.area_tassonomica ? <p>Tassonomia tecnica di supporto: {practice.area_tassonomica} / {practice.macro_area_tassonomica} / {practice.sottobranca_tassonomica}</p> : null}
        {practice?.when_to_use ? <p>{practice.when_to_use}</p> : null}
        {practice?.base_normativa ? <p className="iu-pwiz-side-note">Regola allineata al catalogo tariffario e alla tabella ufficiale presente nello snapshot DM 147/2022.</p> : null}
        {client ? <p className="iu-pwiz-side-client">Cliente: <strong>{client.label}</strong></p> : null}
        <div className="iu-pwiz-money-grid">
          <div><span>Compenso base</span><strong>{base}</strong></div>
          <div><span>Totale</span><strong>{total}</strong></div>
        </div>
      </div>
      <div className="iu-pwiz-side-card iu-pwiz-side-accordions">
        <Accordion id="refs" title="Riferimenti normativi" badge={String(refs.length || data.support.references.length)} open={open.refs} onToggle={() => onToggle('refs')}>
          <div className="iu-pwiz-side-list">
            {(refs.length ? refs : data.support.references.slice(0, 8)).map((ref, index) => (
              <article key={`${ref.title || 'fonte'}-${index}`}>
                <strong>{String(ref.title || 'Riferimento')}</strong>
                <span>{String(ref.article || ref.description || '')}</span>
              </article>
            ))}
          </div>
        </Accordion>
        <Accordion id="checklist" title="Checklist iniziale" badge={String(checklist.length)} open={open.checklist} onToggle={() => onToggle('checklist')}>
          {checklist.length ? <ul className="iu-pwiz-check-list">{checklist.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="iu-pwiz-empty">Checklist disponibile dopo la selezione della tipologia.</p>}
        </Accordion>
        <Accordion id="logic" title="Logica di lavoro consigliata" open={open.logic} onToggle={() => onToggle('logic')}>
          <p>{practice?.when_to_use || 'Il motore suggerirà  la logica di lavoro dopo la selezione del profilo.'}</p>
        </Accordion>
        <Accordion id="coverage" title="Copertura tariffaria" badge={`${data.support.audit.aligned}/${data.support.audit.total || 0}`} open={open.coverage} onToggle={() => onToggle('coverage')}>
          <p>Copertura snapshot: {data.support.audit.aligned} regole allineate su {data.support.audit.total || 0}. Voci aperte: {data.support.audit.open}.</p>
        </Accordion>
        {calculation?.economic ? (
          <dl className="iu-pwiz-side-fiscal">
            <div><dt>Imponibile voci</dt><dd>{calculation.economic.imponibile_label}</dd></div>
            <div><dt>CPA 4%</dt><dd>{calculation.economic.cpa_label}</dd></div>
            <div><dt>IVA 22%</dt><dd>{calculation.economic.iva_label}</dd></div>
            <div><dt>Anticipazioni art. 15</dt><dd>{calculation.economic.anticipazioni_label}</dd></div>
            <div className="is-total"><dt>Totale teorico fattura</dt><dd>{calculation.economic.totale_label}</dd></div>
          </dl>
        ) : null}
      </div>
    </aside>
  )
}

export function PreventivoWizardPage() {
  const [data, setData] = useState<PreventivoWizardPageData>(emptyPreventivoWizardPage)
  const [loading, setLoading] = useState(true)
  const [mode, setMode] = useState<WizardMode>(() => safeStorageRead(modeStorageKey) === 'avanzato' ? 'avanzato' : 'guidato')
  const [open, setOpen] = useState<OpenMap>(initialOpen)
  const [favorites, setFavorites] = useState<string[]>(() => readFavorites())
  const [errors, setErrors] = useState<WizardValidationErrors>({})
  const [warnings, setWarnings] = useState<string[]>([])
  const [message, setMessage] = useState('')
  const [busyCalc, setBusyCalc] = useState(false)
  const [busyCreate, setBusyCreate] = useState(false)
  const [cancelArmed, setCancelArmed] = useState(false)

  const [customerId, setCustomerId] = useState('')
  const [caseId, setCaseId] = useState('')
  const [quickClientEnabled, setQuickClientEnabled] = useState(false)
  const [quickClient, setQuickClient] = useState<QuickClient>({
    tipo: 'PERSONA_FISICA',
    nome: '',
    cognome: '',
    ragione_sociale: '',
    email: '',
    telefono: '',
    codice_fiscale: '',
    partita_iva: '',
  })
  const [object, setObject] = useState('')
  const [issuedAt, setIssuedAt] = useState('')
  const [dueAt, setDueAt] = useState('')
  const [area, setArea] = useState('')
  const [procedure, setProcedure] = useState('')
  const [workflow, setWorkflow] = useState('')
  const [channel, setChannel] = useState('')
  const [taxonomyArea, setTaxonomyArea] = useState('')
  const [taxonomyMacro, setTaxonomyMacro] = useState('')
  const [taxonomySub, setTaxonomySub] = useState('')
  const [extraTaxonomies, setExtraTaxonomies] = useState<Array<Record<string, string>>>([])
  const [searchTerm, setSearchTerm] = useState('')
  const [advancedFilters, setAdvancedFilters] = useState(false)
  const [favoritesOnly, setFavoritesOnly] = useState(false)
  const [compactCards, setCompactCards] = useState(false)
  const [practiceId, setPracticeId] = useState('')
  const [value, setValue] = useState('0')
  const [rule, setRule] = useState('')
  const [grade, setGrade] = useState('')
  const [complexity, setComplexity] = useState('media')
  const [hourlyRate, setHourlyRate] = useState('0')
  const [estimatedHours, setEstimatedHours] = useState('0')
  const [anticipations, setAnticipations] = useState('0')
  const [lawyer, setLawyer] = useState('')
  const [phases, setPhases] = useState<string[]>([])
  const [bonusTelematico, setBonusTelematico] = useState(false)
  const [generalExpenses, setGeneralExpenses] = useState(true)
  const [generalExpensesPct, setGeneralExpensesPct] = useState('15')
  const [applyCpa, setApplyCpa] = useState(true)
  const [applyIva, setApplyIva] = useState(true)
  const [adrAgreement, setAdrAgreement] = useState(false)
  const [mediazioneOdm, setMediazioneOdm] = useState({
    attiva: false,
    regime: 'volontaria',
    esito: 'primo_incontro_senza_accordo',
    art31: false,
  })
  const [accessories, setAccessories] = useState<string[]>([])
  const [expenses, setExpenses] = useState<string[]>([])
  const [rows, setRows] = useState<WizardDraftRow[]>([])
  const [notes, setNotes] = useState('')
  const [clause, setClause] = useState<ClauseState>({
    attiva: false,
    modello: '',
    fonte: '',
    testo: '',
    trattativa_individuale: false,
  })
  const [finalOptions, setFinalOptions] = useState<FinalOptions>({
    genera_conferimento: true,
    apri_fascicolo_guidato: false,
    informativa_art13_resa: true,
  })
  const [calculation, setCalculation] = useState<WizardCalculationResponse | null>(null)

  function toggleOpen(id: string) {
    setOpen((current) => ({ ...current, [id]: !current[id] }))
  }

  function updateMode(next: WizardMode) {
    setMode(next)
    safeStorageWrite(modeStorageKey, next)
    if (next === 'avanzato') {
      setOpen((current) => ({
        ...current,
        tassonomia: true,
        aggiuntive: true,
        adr: true,
        mediazione: true,
        integrazioni: true,
        spese: true,
        note: true,
        clausola: true,
      }))
    }
  }

  const practices = data.catalog.practices
  const selectedPractice = practiceId ? practices[practiceId] || null : null
  const selectedClient = customerId ? data.clients.find((client) => client.id === customerId) || null : null
  const filteredCases = customerId ? data.cases.filter((item) => item.customerId === customerId) : data.cases
  const hasCompensoUnico = isCompensoUnicoProfile(selectedPractice)
  const visibleTaxonomySources = selectedPractice?.tassonomia_sources?.length || data.catalog.taxonomySources.length

  function applyPractice(practice: WizardPractice, replaceText = false) {
    setPracticeId(practice.id)
    setArea(practice.area || area)
    setProcedure(practice.procedura_operativa_codice || '')
    setWorkflow(practice.workflow_operativo_codice || '')
    setChannel(practice.canale_operativo || '')
    setTaxonomyArea(practice.area_tassonomica)
    setTaxonomyMacro(practice.macro_area_tassonomica)
    setTaxonomySub(practice.sottobranca_tassonomica)
    setRule(practice.regola_tariffaria_default)
    setGrade(practice.grado_default)
    setValue(String(practice.valore_suggerito || '0'))
    setPhases(practice.fasi_default_keys.length ? practice.fasi_default_keys : practice.fasi_default.map((item) => item.toLowerCase()))
    setAccessories(practice.accessori_calcolo.filter((item) => item.default_checked).map((item) => item.id))
    if (replaceText || !object) setObject(practice.oggetto_template || `Preventivo professionale per ${practice.label}`)
    if (replaceText || !notes) setNotes(practice.note_template)
    setWarnings([])
    setErrors({})
  }

  useEffect(() => {
    let active = true
    getPreventivoWizardPage()
      .then((payload) => {
        if (!active) return
        setData(payload)
        setCustomerId(String(payload.prefill.idCliente || ''))
        setCaseId(String(payload.prefill.idFascicolo || ''))
        setIssuedAt(payload.defaults.issuedAt)
        setDueAt(payload.defaults.dueAt)
        setGeneralExpenses(payload.defaults.speseGenerali)
        setGeneralExpensesPct(payload.defaults.percSpeseGenerali)
        setApplyCpa(payload.defaults.applicaCpa)
        setApplyIva(payload.defaults.applicaIva)
        setFinalOptions((current) => ({ ...current, informativa_art13_resa: payload.defaults.informativaArt13 }))
        const defaultClause = payload.options.defaultClause
        setClause({
          attiva: false,
          modello: defaultClause.id,
          fonte: defaultClause.source,
          testo: defaultClause.defaultText,
          trattativa_individuale: false,
        })
        const prefillPractice = String(payload.prefill.idPratica || '')
        const firstPractice = payload.catalog.practices[prefillPractice]
          || payload.catalog.practices.amministrazione_sostegno
          || Object.values(payload.catalog.practices)[0]
        if (firstPractice) {
          applyPractice(firstPractice, true)
          setArea(String(payload.prefill.area || firstPractice.area))
          setValue(String(payload.prefill.valore || firstPractice.valore_suggerito || '0'))
          setGrade(String(payload.prefill.grado || firstPractice.grado_default))
          setRule(String(payload.prefill.regolaTariffaria || firstPractice.regola_tariffaria_default))
          setComplexity(String(payload.prefill.complessita || 'media'))
          const prefillPhases = Array.isArray(payload.prefill.fasi) ? payload.prefill.fasi.map(String).filter(Boolean) : []
          if (prefillPhases.length) setPhases(prefillPhases)
          setBonusTelematico(Boolean(payload.prefill.bonusTelematico))
          setGeneralExpenses(Boolean(payload.prefill.speseGenerali ?? payload.defaults.speseGenerali))
          setApplyCpa(Boolean(payload.prefill.applicaCpa ?? payload.defaults.applicaCpa))
          setApplyIva(Boolean(payload.prefill.applicaIva ?? payload.defaults.applicaIva))
          setAnticipations(String(payload.prefill.anticipazioni || '0'))
          setObject(String(payload.prefill.oggetto || firstPractice.oggetto_template || `Preventivo professionale per ${firstPractice.label}`))
          setNotes(firstPractice.note_template)
        }
        if (payload.warnings.length) setWarnings(payload.warnings.map((warning) => warning.message))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const filteredPractices = useMemo(() => {
    const needle = searchTerm.trim().toLowerCase()
    return Object.values(practices).filter((practice) => {
      if (area && practice.area !== area) return false
      if (procedure && practice.procedura_operativa_codice !== procedure) return false
      if (workflow && practice.workflow_operativo_codice !== workflow) return false
      if (channel && practice.canale_operativo !== channel) return false
      if (taxonomyArea && practice.area_tassonomica !== taxonomyArea) return false
      if (taxonomyMacro && practice.macro_area_tassonomica !== taxonomyMacro) return false
      if (taxonomySub && practice.sottobranca_tassonomica !== taxonomySub) return false
      if (favoritesOnly && !favorites.includes(practice.id)) return false
      if (!needle) return true
      const haystack = [
        practice.label,
        practice.summary,
        practice.when_to_use,
        practice.area,
        practice.area_tassonomica,
        practice.macro_area_tassonomica,
        practice.sottobranca_tassonomica,
      ].join(' ').toLowerCase()
      return haystack.includes(needle)
    })
  }, [area, procedure, workflow, channel, taxonomyArea, taxonomyMacro, taxonomySub, favoritesOnly, favorites, practices, searchTerm])

  function toggleFavorite(id: string) {
    setFavorites((current) => {
      const next = current.includes(id) ? current.filter((item) => item !== id) : [...current, id]
      safeStorageWrite(favoriteStorageKey, JSON.stringify(next))
      return next
    })
  }

  function togglePhase(key: string, checked: boolean) {
    setPhases((current) => checked ? Array.from(new Set([...current, key])) : current.filter((item) => item !== key))
  }

  function toggleAccessory(id: string, checked: boolean) {
    setAccessories((current) => checked ? [...current, id] : current.filter((item) => item !== id))
  }

  function toggleExpense(key: string, checked: boolean) {
    setExpenses((current) => checked ? [...current, key] : current.filter((item) => item !== key))
  }

  function addManualRow() {
    const row: WizardDraftRow = {
      id: `manuale-${Date.now()}`,
      descrizione: '',
      tipo: data.options.voiceTypes[0]?.value || 'Onorario',
      importo: 0,
      importo_label: formatEuro(0),
      fiscale: 'imponibile',
      source: 'manuale',
      locked: false,
    }
    setRows((current) => [...current, row])
  }

  function updateRow(id: string, patch: Partial<WizardDraftRow>) {
    setRows((current) => current.map((row) => row.id === id ? { ...row, ...patch } : row))
  }

  function removeRow(id: string) {
    setRows((current) => current.filter((row) => row.id !== id))
  }

  function addExtraTaxonomy() {
    setExtraTaxonomies((current) => [
      ...current,
      {
        uid: `tax-${Date.now()}`,
        area_tassonomica: taxonomyArea,
        macro_area_tassonomica: taxonomyMacro,
        sottobranca_tassonomica: taxonomySub,
        tipologia_pratica_id: practiceId,
        tipologia_pratica_label: selectedPractice?.label || '',
        tipo_compenso: selectedPractice?.tipo_compenso_default || '',
      },
    ])
  }

  function buildPayload(includeRows = true): Record<string, unknown> {
    const practice = selectedPractice
    return {
      id_cliente: customerId,
      id_fascicolo: caseId,
      cliente_rapido_attivo: quickClientEnabled,
      cliente_rapido: quickClient,
      oggetto: object,
      data_emissione: issuedAt,
      data_scadenza: dueAt,
      id_pratica: practiceId,
      area_pratica: practice?.area || area,
      area_tassonomica: practice?.area_tassonomica || taxonomyArea,
      macro_area_tassonomica: practice?.macro_area_tassonomica || taxonomyMacro,
      sottobranca_tassonomica: practice?.sottobranca_tassonomica || taxonomySub,
      tassonomia_codice: practice?.tassonomia_codice || '',
      procedura_operativa_codice: practice?.procedura_operativa_codice || procedure,
      procedura_operativa_nome: practice?.procedura_operativa_nome || '',
      subbranch_operativa_codice: practice?.subbranch_operativa_codice || '',
      workflow_operativo_codice: practice?.workflow_operativo_codice || workflow,
      copertura_operativa: practice?.copertura_operativa || '',
      canale_operativo: practice?.canale_operativo || channel,
      registro_operativo: practice?.registro_operativo || '',
      tipo_compenso: practice?.tipo_compenso_default || '',
      tipo_procedimento: practice?.label || '',
      valore: value,
      grado: grade,
      regola_tariffaria: rule,
      complessita: complexity,
      tariffa_oraria: hourlyRate,
      ore_stimate: estimatedHours,
      anticipazioni: anticipations,
      avvocato_referente: lawyer,
      fasi: phases,
      compenso_unico: phases.includes('compenso_unico'),
      bonus_telematico: bonusTelematico,
      spese_generali: generalExpenses,
      perc_spese_generali: generalExpensesPct,
      applica_cpa: applyCpa,
      applica_iva: applyIva,
      adr_accordo: adrAgreement,
      mediazione_odm_attiva: mediazioneOdm.attiva,
      mediazione_odm_regime: mediazioneOdm.regime,
      mediazione_odm_esito: mediazioneOdm.esito,
      mediazione_odm_art31_maggiorazione_20: mediazioneOdm.art31,
      accessori: accessories,
      esborsi: expenses,
      manual_lines: rows.filter((row) => row.source === 'manuale'),
      rows: includeRows ? rows : [],
      note: notes,
      clausola: clause,
      opzioni_finali: finalOptions,
      informativa_art13_resa: finalOptions.informativa_art13_resa,
      fonti_tassonomia: practice?.tassonomia_sources || [],
      classificazioni_tassonomiche: extraTaxonomies,
      log_calcolo: String(calculation?.audit?.log_calcolo || ''),
      from_page: 'wizard',
    }
  }

  function currentValidation(requireRows: boolean): WizardValidationErrors {
    return validateWizardForm({
      customerId,
      quickClientEnabled,
      quickClientName: quickClient.nome,
      quickClientSurname: quickClient.cognome,
      quickClientCompany: quickClient.ragione_sociale,
      object,
      issuedAt,
      dueAt,
      practiceId,
      rows: requireRows ? rows : rows.length ? rows : [{ id: 'placeholder', descrizione: 'placeholder', tipo: 'Onorario', importo: 1, importo_label: '', fiscale: 'imponibile', source: 'validation' }],
      clauseEnabled: clause.attiva,
      clauseText: clause.testo,
    })
  }

  async function submitCalculation() {
    const nextErrors = currentValidation(false)
    setErrors(nextErrors)
    setMessage('')
    if (Object.keys(nextErrors).length) {
      setWarnings(['Completa i campi evidenziati prima di calcolare la bozza.'])
      return null
    }
    setBusyCalc(true)
    const response = await runPreventivoWizardCalculation(buildPayload(false))
    setBusyCalc(false)
    setWarnings(response.warnings.map((warning) => warning.message))
    if (!response.ok) {
      setCalculation(response)
      return response
    }
    setCalculation(response)
    setRows(mergeCalculatedRowsWithManualRows(response.rows, rows))
    if (response.note && !notes) setNotes(response.note)
    setMessage('Bozza aggiornata dal motore tariffario.')
    return response
  }

  async function submitCreate() {
    const nextErrors = currentValidation(true)
    setErrors(nextErrors)
    setMessage('')
    if (Object.keys(nextErrors).length) {
      setWarnings(['Completa i campi evidenziati prima di creare il preventivo.'])
      return
    }
    setBusyCreate(true)
    const response = await createPreventivoWizard(buildPayload(true))
    setBusyCreate(false)
    setWarnings(response.warnings.map((warning) => warning.message))
    if (!response.ok) return
    setMessage(response.messages.map((item) => item.message).filter(Boolean).join(' '))
    const redirect = response.redirect_url || response.detail_url
    if (redirect) window.location.assign(redirect)
  }

  function cancel() {
    if (!cancelArmed && (object || rows.length || customerId || quickClientEnabled)) {
      setCancelArmed(true)
      setWarnings(['Premi di nuovo Annulla per uscire dal wizard senza salvare.'])
      return
    }
    window.location.assign(data.actions.back || '/preventivi')
  }

  function resetClauseText() {
    const model = data.options.clauseModels.find((item) => item.id === clause.modello)
    setClause((current) => ({
      ...current,
      testo: model?.default_text || data.options.defaultClause.defaultText,
      fonte: model?.source || data.options.defaultClause.source,
    }))
  }

  if (loading) {
    return <LoadingState title="Caricamento preventivo guidato" message="Recupero clienti, fascicoli, catalogo, tassonomia e presidi tariffari dal backend." />
  }

  const totalLabel = calculation?.economic?.totale_label || formatEuro(0)
  const baseLabel = calculation?.economic?.imponibile_label || formatEuro(0)
  const canCreate = !busyCreate && Boolean(practiceId && object.trim() && rows.length)
  const compactClass = compactCards ? 'is-compact' : ''

  return (
    <main className="iu-content iu-pwiz-page">
      <Hero mode={mode} onMode={updateMode} backHref={data.actions.back || '/preventivi'} />
      <StepRail />
      <StatusMessages warnings={warnings} message={message} />
      <div className="iu-pwiz-layout">
        <div className="iu-pwiz-main">
          <StepCard
            id="cliente"
            number="1"
            title="Cliente e contesto"
            microcopy="Parti da cliente e pratica corretti per avere il miglior profilo possibile."
            label="FASE INIZIALE"
            open={open.cliente}
            onToggle={() => toggleOpen('cliente')}
          >
            <div className="iu-pwiz-grid two">
              <SelectInput id="wizard-cliente" label="Cliente *" value={customerId} help="Il wizard si precompila meglio se parti dal cliente corretto." error={errors.customer} onChange={(value) => { setCustomerId(value); setCaseId('') }}>
                <option value="">Seleziona cliente</option>
                {data.clients.map((client) => <option value={client.id} key={client.id}>{client.label}</option>)}
              </SelectInput>
              <SelectInput id="wizard-fascicolo" label="Fascicolo collegato" value={caseId} help="Opzionale. Se presente, il preventivo resta agganciato alla pratica." onChange={setCaseId}>
                <option value="">Nessun fascicolo collegato</option>
                {filteredCases.map((matter) => <option value={matter.id} key={matter.id}>{matter.label}</option>)}
              </SelectInput>
            </div>
            {!data.clients.length ? <p className="iu-pwiz-empty">Nessun cliente disponibile nel repository corrente. Usa l'inserimento rapido se devi creare un cliente potenziale.</p> : null}
            <SwitchRow id="quick-client" checked={quickClientEnabled} label="Cliente non ancora censito: inserimento rapido" help="Creo un cliente potenziale con dati minimi e completo l'anagrafica quando il preventivo viene accettato." onChange={setQuickClientEnabled} />
            {quickClientEnabled ? (
              <div className="iu-pwiz-quick-client">
                <SelectInput id="quick-tipo" label="Tipo cliente" value={quickClient.tipo} onChange={(value) => setQuickClient((current) => ({ ...current, tipo: value }))}>
                  {data.options.quickClientTypes.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
                </SelectInput>
                {quickClient.tipo === 'PERSONA_GIURIDICA' ? (
                  <TextInput id="quick-ragione" label="Nome / denominazione" value={quickClient.ragione_sociale} onChange={(value) => setQuickClient((current) => ({ ...current, ragione_sociale: value }))} />
                ) : (
                  <>
                    <TextInput id="quick-nome" label="Nome" value={quickClient.nome} onChange={(value) => setQuickClient((current) => ({ ...current, nome: value }))} />
                    <TextInput id="quick-cognome" label="Cognome" value={quickClient.cognome} onChange={(value) => setQuickClient((current) => ({ ...current, cognome: value }))} />
                  </>
                )}
                <TextInput id="quick-email" label="Email" value={quickClient.email} type="email" onChange={(value) => setQuickClient((current) => ({ ...current, email: value }))} />
                <TextInput id="quick-phone" label="Telefono" value={quickClient.telefono} onChange={(value) => setQuickClient((current) => ({ ...current, telefono: value }))} />
                <TextInput id="quick-cf" label="Codice fiscale / P.IVA" value={quickClient.codice_fiscale} onChange={(value) => setQuickClient((current) => ({ ...current, codice_fiscale: value }))} />
                {quickClient.tipo === 'PERSONA_GIURIDICA' ? <TextInput id="quick-piva" label="Partita IVA" value={quickClient.partita_iva} onChange={(value) => setQuickClient((current) => ({ ...current, partita_iva: value }))} /> : null}
              </div>
            ) : null}
            <div className="iu-pwiz-grid object">
              <TextInput id="wizard-oggetto" label="Oggetto del preventivo *" value={object} placeholder="Preventivo professionale per amministrazione di sostegno" error={errors.object} onChange={setObject} />
              <TextInput id="wizard-emissione" label="Data emissione" type="date" value={issuedAt} error={errors.issuedAt} onChange={setIssuedAt} />
              <TextInput id="wizard-scadenza" label="Scadenza" type="date" value={dueAt} error={errors.dueAt} onChange={setDueAt} />
              <SwitchRow id="informativa-art13-top" checked={finalOptions.informativa_art13_resa} label="Informativa art. 13" onChange={(checked) => setFinalOptions((current) => ({ ...current, informativa_art13_resa: checked }))} />
            </div>
          </StepCard>

          <StepCard
            id="tipologia"
            number="2"
            title="Tipologia e motore preventivo"
            microcopy="Toolbar compatta, ricerca veloce, preferite e selezione guidata del profilo operativo."
            label="MOTORE E REDATTORE"
            open={open.tipologia}
            onToggle={() => toggleOpen('tipologia')}
          >
            <section className="iu-pwiz-subpanel">
              <h3>CLASSIFICAZIONE OPERATIVA</h3>
              <div className="iu-pwiz-grid three">
                <SelectInput id="proc" label="Procedura / servizio" value={procedure} onChange={setProcedure}>
                  <option value="">Tutte le procedure</option>
                  {data.catalog.procedures.filter((option) => option.value).map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
                </SelectInput>
                <SelectInput id="workflow" label="Workflow" value={workflow} onChange={setWorkflow}>
                  <option value="">Tutti i workflow</option>
                  {data.catalog.workflows.filter((option) => option.value).map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
                </SelectInput>
                <SelectInput id="channel" label="Canale" value={channel} onChange={setChannel}>
                  <option value="">Tutti i canali</option>
                  {data.catalog.channels.filter((option) => option.value).map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
                </SelectInput>
              </div>
              <p>La classificazione operativa guida davvero il catalogo: procedura, workflow e canale selezionano il profilo professionale prima della tassonomia di supporto.</p>
              {selectedPractice ? (
                <Tags values={[selectedPractice.label, selectedPractice.procedura_operativa_nome, selectedPractice.workflow_operativo_codice, selectedPractice.canale_operativo]} />
              ) : (
                <div className="iu-pwiz-empty"><strong>Classificazione operativa non ancora selezionata</strong><span>Scegli una procedura, un workflow o una tipologia: qui vedrai subito il profilo operativo reale che alimenta preventivo, conferimento, fascicolo, parcella e fattura.</span></div>
              )}
            </section>
            <Accordion id="taxonomy" title="Tassonomia tecnica di supporto" description="CLASSIFICAZIONE TASSONOMICA" open={open.tassonomia} onToggle={() => toggleOpen('tassonomia')}>
              <div className="iu-pwiz-grid three">
                <SelectInput id="tax-area" label="Area tassonomica" value={taxonomyArea} onChange={setTaxonomyArea}>
                  <option value="">Tutte le aree tassonomiche</option>
                  {data.catalog.taxonomySummary.areas.map((item) => <option value={item} key={item}>{item}</option>)}
                </SelectInput>
                <SelectInput id="tax-macro" label="Macro-area" value={taxonomyMacro} onChange={setTaxonomyMacro}>
                  <option value="">Tutte le macro-aree</option>
                  {data.catalog.taxonomySummary.macroAreas.map((item) => <option value={item} key={item}>{item}</option>)}
                </SelectInput>
                <SelectInput id="tax-sub" label="Sottobranca" value={taxonomySub} onChange={setTaxonomySub}>
                  <option value="">Tutte le sottobranche</option>
                  {data.catalog.taxonomySummary.subBranches.map((item) => <option value={item} key={item}>{item}</option>)}
                </SelectInput>
              </div>
              <div className="iu-pwiz-tax-box">
                <Tags values={[taxonomyArea, taxonomyMacro, taxonomySub, `${filteredPractices.length} tipologie compatibili`]} />
                <p>Tassonomia tecnica attiva: {[taxonomyArea, taxonomyMacro, taxonomySub].filter(Boolean).join(' / ') || 'non selezionata'}</p>
                <p>{visibleTaxonomySources} fonti ufficiali aggregate pronte per il tracciato del preventivo.</p>
              </div>
            </Accordion>
            {(mode === 'avanzato' || extraTaxonomies.length > 0) ? (
              <Accordion id="aggiuntive" title="Classificazioni tassonomiche aggiuntive" description="Aggiungi altri sviluppi della pratica: ogni classificazione può collegare una tipologia tariffaria e genera una voce autonoma nel preventivo." open={open.aggiuntive} onToggle={() => toggleOpen('aggiuntive')}>
                <button className="iu-pwiz-light-button" type="button" onClick={addExtraTaxonomy}><Plus size={16} aria-hidden="true" /> Aggiungi classificazione</button>
                {extraTaxonomies.length ? (
                  <div className="iu-pwiz-extra-tax">
                    {extraTaxonomies.map((item) => (
                      <article key={item.uid}>
                        <strong>{item.tipologia_pratica_label || 'Classificazione aggiuntiva'}</strong>
                        <span>{[item.area_tassonomica, item.macro_area_tassonomica, item.sottobranca_tassonomica].filter(Boolean).join(' / ')}</span>
                        <button type="button" onClick={() => setExtraTaxonomies((current) => current.filter((row) => row.uid !== item.uid))}><Trash2 size={15} aria-hidden="true" /> Rimuovi</button>
                      </article>
                    ))}
                  </div>
                ) : <p className="iu-pwiz-empty">Nessuna classificazione aggiuntiva inserita.</p>}
              </Accordion>
            ) : null}
            <section className="iu-pwiz-area-practice">
              <h3>AREA PRATICA</h3>
              <div className="iu-pwiz-area-pills">
                <button className={!area ? 'is-active' : ''} type="button" onClick={() => setArea('')}>Tutte</button>
                {data.catalog.areas.map((item) => (
                  <button className={area === item.value ? 'is-active' : ''} type="button" onClick={() => setArea(item.value)} key={item.id}>{item.label}</button>
                ))}
              </div>
            </section>
            <section className="iu-pwiz-searchbar">
              <label htmlFor="tipologia-search">Ricerca tipologie</label>
              <div>
                <Search size={17} aria-hidden="true" />
                <input id="tipologia-search" value={searchTerm} placeholder="Es. recupero crediti, mediazione, penale..." onChange={(event) => setSearchTerm(event.target.value)} />
              </div>
              <button type="button" className={advancedFilters ? 'is-active' : ''} onClick={() => setAdvancedFilters((current) => !current)}>Filtri avanzati</button>
              <button type="button" className={favoritesOnly ? 'is-active' : ''} onClick={() => setFavoritesOnly((current) => !current)}>Preferite</button>
              <button type="button" className={compactCards ? 'is-active' : ''} onClick={() => setCompactCards((current) => !current)}>Vista compatta</button>
            </section>
            {advancedFilters ? <p className="iu-pwiz-info">I filtri avanzati usano i campi reali del catalogo: area, procedura, workflow, canale e tassonomia.</p> : null}
            <div className={`iu-pwiz-practice-grid ${compactClass}`}>
              {filteredPractices.length ? filteredPractices.slice(0, mode === 'guidato' ? 12 : 80).map((practice) => (
                <article className={`iu-pwiz-practice ${practice.id === practiceId ? 'is-selected' : ''}`} key={practice.id}>
                  <button type="button" onClick={() => applyPractice(practice, true)} aria-pressed={practice.id === practiceId}>
                    <strong>{practice.label}</strong>
                    <span>{practice.summary}</span>
                    <em>{practice.tipo_compenso_default}</em>
                    <em>{practice.motore_label}</em>
                  </button>
                  <button className={`iu-pwiz-star ${favorites.includes(practice.id) ? 'is-active' : ''}`} type="button" onClick={() => toggleFavorite(practice.id)} aria-label={`Preferito ${practice.label}`}>
                    <Star size={16} aria-hidden="true" />
                  </button>
                </article>
              )) : <p className="iu-pwiz-empty">Nessuna tipologia compatibile con i filtri correnti.</p>}
            </div>
            {errors.practice ? <p className="iu-pwiz-error">{errors.practice}</p> : null}
          </StepCard>

          <StepCard
            id="compenso"
            number="3"
            title="Compenso base e fasi"
            microcopy="Fasi tabellari, compenso unico, complessità  stimata, spese generali e bonus."
            label="CALCOLO"
            open={open.calcolo}
            onToggle={() => toggleOpen('calcolo')}
          >
            <Accordion id="parametri" title="Parametri economici e competenza" description="Allinea valore, regola tariffaria e grado alla pratica selezionata." open={open.parametri} onToggle={() => toggleOpen('parametri')}>
              <div className="iu-pwiz-grid four">
                <TextInput id="valore" label="Valore pratica / controversia" value={value} onChange={(next) => setValue(normalizeAmountInput(next))} />
                <SelectInput id="rule" label="Regola tariffaria / competenza" value={rule} help="Collega la tipologia alla competenza per giurisdizione o rito applicabile." onChange={setRule}>
                  <option value="">Regola standard del profilo</option>
                  {selectedPractice?.regole_tariffarie.map((item) => {
                    const code = String(item.rule_code || '')
                    const label = String(item.label || item.rule_label || item.table_label || code)
                    return code ? <option value={code} key={code}>{label}</option> : null
                  })}
                </SelectInput>
                <SelectInput id="grade" label="Grado / sede" value={grade} onChange={setGrade}>
                  {(selectedPractice?.regole_tariffarie.length ? Array.from(new Set(selectedPractice.regole_tariffarie.flatMap((item) => Array.isArray(item.allowed_grade_input_values) ? item.allowed_grade_input_values.map(String) : [String(item.grado_input_value || '')]).filter(Boolean))) : [selectedPractice?.grado_default || '']).map((item) => <option value={item} key={item}>{item}</option>)}
                </SelectInput>
                <SelectInput id="complexity" label="Complessità stimata" value={complexity} help="Bassa usa la forbice minima, media il valore base, alta la forbice massima; se il valore non è determinato, IUSENTRA usa il primo scaglione reale disponibile." onChange={setComplexity}>
                  {data.options.complexity.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
                </SelectInput>
                <TextInput id="hourly-rate" label="Tariffa oraria" value={hourlyRate} onChange={(next) => setHourlyRate(normalizeAmountInput(next))} />
                <TextInput id="estimated-hours" label="Ore stimate" value={estimatedHours} onChange={(next) => setEstimatedHours(normalizeAmountInput(next))} />
                <TextInput id="anticipations" label="Anticipazioni art. 15" value={anticipations} onChange={(next) => setAnticipations(normalizeAmountInput(next))} />
                <TextInput id="lawyer" label="Avvocato referente" value={lawyer} placeholder="Avv. referente" onChange={setLawyer} />
              </div>
            </Accordion>
            <Accordion id="fasi" title="Compenso base e fasi" description="Fasi tabellari, compenso unico, complessità  stimata, spese generali e bonus." open={open.fasi} onToggle={() => toggleOpen('fasi')}>
              <div className="iu-pwiz-duo">
                <article>
                  <h3>FASI DA INCLUDERE</h3>
                  <p>Include anche il flag compenso unico quando previsto.</p>
                  {hasCompensoUnico ? <p className="iu-pwiz-info">Il profilo tariffario attivo usa una tabella a compenso unico: le fasi operative restano visibili per continuità  del preventivo; con il flag acceso viene calcolata la voce unica, con il flag spento il wizard usa le fasi tabellari selezionate.</p> : null}
                  <div className="iu-pwiz-check-grid">
                    {Array.from(new Set([...(selectedPractice?.fasi_default_keys || []), ...(hasCompensoUnico ? ['compenso_unico'] : [])])).map((key) => (
                      <label className="iu-pwiz-check" htmlFor={`phase-${key}`} key={key}>
                        <input id={`phase-${key}`} type="checkbox" checked={phases.includes(key)} onChange={(event) => togglePhase(key, event.target.checked)} />
                        <span>{phaseKeyLabel(key)}</span>
                      </label>
                    ))}
                  </div>
                </article>
                <article>
                  <h3>OPZIONI COMPENSO</h3>
                  <p>Compresso in un unico pannello operativo.</p>
                  <div className="iu-pwiz-check-grid">
                    <SwitchRow id="bonus" checked={bonusTelematico} label="Bonus telematico 30%" onChange={setBonusTelematico} />
                    <SwitchRow id="general-expenses" checked={generalExpenses} label="Spese generali 15%" onChange={setGeneralExpenses} />
                    <SwitchRow id="cpa" checked={applyCpa} label="Applica CPA 4%" onChange={setApplyCpa} />
                    <SwitchRow id="iva" checked={applyIva} label="Applica IVA 22%" onChange={setApplyIva} />
                  </div>
                  <TextInput id="general-expenses-pct" label="Percentuale spese generali" value={generalExpensesPct} help="Il motore applica anche CPA, IVA, anticipazioni ex art. 15 e compenso orario." onChange={(next) => setGeneralExpensesPct(normalizeAmountInput(next))} />
                </article>
              </div>
            </Accordion>
            {(mode === 'avanzato' || selectedPractice?.variation_policy.kind) ? (
              <Accordion id="adr" title="Variazioni ADR e accordo" description="La variazione ADR si attiva quando selezioni mediazione, negoziazione assistita o un'integrazione ADR collegata." open={open.adr} onToggle={() => toggleOpen('adr')}>
                <SwitchRow id="adr-agreement" checked={adrAgreement} label="Accordo raggiunto in ADR" onChange={setAdrAgreement} />
              </Accordion>
            ) : null}
            {(mode === 'avanzato' || mediazioneOdm.attiva) ? (
              <Accordion id="mediazione" title="Costi organismo mediazione D.M. 150/2023" description="Il pannello si attiva quando la pratica principale o una classificazione aggiuntiva usa la mediazione civile / commerciale." open={open.mediazione} onToggle={() => toggleOpen('mediazione')}>
                <div className="iu-pwiz-grid two">
                  <SwitchRow id="mediazione-odm" checked={mediazioneOdm.attiva} label="Includi costi organismo mediazione" onChange={(checked) => setMediazioneOdm((current) => ({ ...current, attiva: checked }))} />
                  <SelectInput id="mediazione-regime" label="Regime" value={mediazioneOdm.regime} onChange={(next) => setMediazioneOdm((current) => ({ ...current, regime: next }))}>
                    <option value="volontaria">Volontaria</option>
                    <option value="obbligatoria_demandata">Obbligatoria / demandata</option>
                  </SelectInput>
                  <SelectInput id="mediazione-esito" label="Esito mediazione" value={mediazioneOdm.esito} onChange={(next) => setMediazioneOdm((current) => ({ ...current, esito: next }))}>
                    <option value="primo_incontro_senza_accordo">Primo incontro senza accordo</option>
                    <option value="primo_incontro_con_accordo">Primo incontro con accordo</option>
                    <option value="incontri_successivi_senza_accordo">Incontri successivi senza accordo</option>
                    <option value="incontri_successivi_con_accordo">Incontri successivi con accordo</option>
                  </SelectInput>
                  <SwitchRow id="mediazione-art31" checked={mediazioneOdm.art31} label="Maggiorazione art. 31, comma 3" onChange={(checked) => setMediazioneOdm((current) => ({ ...current, art31: checked }))} />
                </div>
              </Accordion>
            ) : null}
            <Accordion id="integrazioni" title="Integrazioni selezionabili" open={open.integrazioni} onToggle={() => toggleOpen('integrazioni')}>
              {selectedPractice?.accessori_calcolo.length ? selectedPractice.accessori_calcolo.map((item) => (
                <label className="iu-pwiz-selectable" htmlFor={`acc-${item.id}`} key={item.id}>
                  <input id={`acc-${item.id}`} type="checkbox" checked={accessories.includes(item.id)} onChange={(event) => toggleAccessory(item.id, event.target.checked)} />
                  <span><strong>{item.label}</strong><small>{item.description}</small></span>
                </label>
              )) : <p className="iu-pwiz-empty">Nessuna integrazione selezionabile per questa tipologia.</p>}
            </Accordion>
            <Accordion id="spese" title="Spese vive suggerite" open={open.spese} onToggle={() => toggleOpen('spese')}>
              {selectedPractice?.esborsi_tipici.length ? selectedPractice.esborsi_tipici.map((expense, index) => {
                const key = expense.key || `${selectedPractice.id}:${index}`
                return (
                  <label className="iu-pwiz-expense" htmlFor={`expense-${key}`} key={key}>
                    <input id={`expense-${key}`} type="checkbox" checked={expenses.includes(key)} onChange={(event) => toggleExpense(key, event.target.checked)} />
                    <span><strong>{expense.descrizione}</strong><small>{expense.source || 'Spesa viva suggerita dal profilo'}</small></span>
                    <em>{formatEuro(expense.importo)}</em>
                  </label>
                )
              }) : <p className="iu-pwiz-empty">Nessuna spesa viva suggerita dal profilo attivo.</p>}
            </Accordion>
          </StepCard>

          <StepCard
            id="bozza"
            number="4"
            title="Bozza del preventivo"
            microcopy="Tabella operativa con editing rapido di importi, voci manuali e note collassabili."
            label="BOZZA"
            open={open.bozza}
            onToggle={() => toggleOpen('bozza')}
          >
            <section className="iu-pwiz-subpanel">
              <div className="iu-pwiz-subpanel__head">
                <div>
                  <h3>BOZZA OPERATIVA</h3>
                  <p>Puoi correggere descrizioni e importi direttamente in tabella.</p>
                </div>
                <button className="iu-pwiz-light-button" type="button" onClick={addManualRow}><Plus size={16} aria-hidden="true" /> Aggiungi voce manuale</button>
              </div>
              <div className="iu-pwiz-table-wrap">
                <table className="iu-pwiz-table">
                  <caption>Bozza operativa preventivo</caption>
                  <thead>
                    <tr>
                      <th scope="col">DESCRIZIONE</th>
                      <th scope="col">TIPO VOCE</th>
                      <th scope="col">IMPORTO</th>
                      <th scope="col">AZIONI</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.length ? rows.map((row) => (
                      <tr key={row.id}>
                        <td>
                          <input value={row.descrizione} aria-label="Descrizione voce" onChange={(event) => updateRow(row.id, { descrizione: event.target.value })} />
                          {errors[`row-${row.id}-descrizione`] ? <span className="iu-pwiz-error">{errors[`row-${row.id}-descrizione`]}</span> : null}
                        </td>
                        <td>
                          <select value={row.tipo} aria-label="Tipo voce" onChange={(event) => updateRow(row.id, { tipo: event.target.value })}>
                            {data.options.voiceTypes.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
                          </select>
                          <select value={row.fiscale} aria-label="Trattamento fiscale" onChange={(event) => updateRow(row.id, { fiscale: event.target.value })}>
                            {data.options.manualFiscalTypes.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
                          </select>
                        </td>
                        <td>
                          <input value={String(row.importo).replace('.', ',')} inputMode="decimal" aria-label="Importo voce" onChange={(event) => updateRow(row.id, { importo: parseEuroInput(event.target.value), importo_label: formatEuro(parseEuroInput(event.target.value)) })} />
                          {errors[`row-${row.id}-importo`] ? <span className="iu-pwiz-error">{errors[`row-${row.id}-importo`]}</span> : null}
                        </td>
                        <td><button className="iu-pwiz-icon-button" type="button" onClick={() => removeRow(row.id)} aria-label="Rimuovi voce"><Trash2 size={16} /></button></td>
                      </tr>
                    )) : (
                      <tr><td colSpan={4}><p className="iu-pwiz-empty">Esegui il calcolo per generare le prime righe oppure aggiungi una voce manuale.</p></td></tr>
                    )}
                  </tbody>
                </table>
              </div>
              {errors.rows ? <p className="iu-pwiz-error">{errors.rows}</p> : null}
              {calculation?.economic ? (
                <dl className="iu-pwiz-economic">
                  <div><dt>Imponibile voci</dt><dd>{calculation.economic.imponibile_label}</dd></div>
                  <div><dt>CPA</dt><dd>{calculation.economic.cpa_label}</dd></div>
                  <div><dt>IVA</dt><dd>{calculation.economic.iva_label}</dd></div>
                  <div><dt>Anticipazioni art. 15</dt><dd>{calculation.economic.anticipazioni_label}</dd></div>
                  <div className="is-total"><dt>Totale</dt><dd>{calculation.economic.totale_label}</dd></div>
                </dl>
              ) : null}
            </section>
            <Accordion id="note" title="Note professionali e condizioni" open={open.note} onToggle={() => toggleOpen('note')}>
              <textarea className="iu-pwiz-textarea" value={notes} rows={7} onChange={(event) => setNotes(event.target.value)} aria-label="Note professionali e condizioni" />
            </Accordion>
            <Accordion id="clausola" title="Clausola per la risoluzione delle controversie" description="Nasce nel preventivo, resta modificabile e viene trasferita nel conferimento di incarico." open={open.clausola} onToggle={() => toggleOpen('clausola')}>
              <div className="iu-pwiz-clause-grid">
                <div>
                  <SwitchRow id="clause-enabled" checked={clause.attiva} label="Includi clausola per la risoluzione delle controversie" help="Il testo proposto potrà  essere adattato prima del conferimento di incarico." onChange={(checked) => setClause((current) => ({ ...current, attiva: checked }))} />
                  <SelectInput id="clause-model" label="Modello clausola" value={clause.modello} onChange={(value) => {
                    const model = data.options.clauseModels.find((item) => item.id === value)
                    setClause((current) => ({ ...current, modello: value, fonte: model?.source || '', testo: model?.default_text || current.testo }))
                  }}>
                    {data.options.clauseModels.map((model) => <option value={model.id} key={model.id}>{model.label}</option>)}
                  </SelectInput>
                  <SwitchRow id="clause-trattativa" checked={clause.trattativa_individuale} label="Trattativa individuale documentabile sulla clausola già  svolta" onChange={(checked) => setClause((current) => ({ ...current, trattativa_individuale: checked }))} />
                  <Field id="clause-text" label="Testo da adattare" error={errors.clauseText}>
                    <textarea id="clause-text" className="iu-pwiz-textarea" rows={8} value={clause.testo} onChange={(event) => setClause((current) => ({ ...current, testo: event.target.value }))} />
                  </Field>
                  <button className="iu-pwiz-light-button" type="button" onClick={resetClauseText}><RotateCcw size={16} aria-hidden="true" /> Ripristina testo standard</button>
                  <p className="iu-pwiz-microcopy">Fonte modello: {clause.fonte || 'nessuna fonte impostata'}</p>
                </div>
                <aside className="iu-pwiz-clause-warning">
                  <strong>{data.options.clauseModels.find((item) => item.id === clause.modello)?.label || 'Tutela cliente / consumatore'}</strong>
                  <em>Trattativa individuale documentabile sulla clausola già  svolta</em>
                  <p>Da usare con particolare attenzione se il cliente opera come consumatore: la fonte richiede una trattativa seria, effettiva e individuale.</p>
                </aside>
              </div>
            </Accordion>
            <Accordion id="finali" title="Opzioni finali" open={open.finali} onToggle={() => toggleOpen('finali')}>
              <div className="iu-pwiz-final-options">
                <SwitchRow id="gen-conf" checked={finalOptions.genera_conferimento} label="Genera anche il conferimento incarico" onChange={(checked) => setFinalOptions((current) => ({ ...current, genera_conferimento: checked, apri_fascicolo_guidato: checked ? current.apri_fascicolo_guidato : false }))} />
                <SwitchRow id="open-case" checked={finalOptions.apri_fascicolo_guidato} label="Poi apri il fascicolo guidato" help={!finalOptions.genera_conferimento ? 'Disponibile dopo aver attivato il conferimento.' : undefined} onChange={(checked) => setFinalOptions((current) => ({ ...current, apri_fascicolo_guidato: checked }))} />
                <SwitchRow id="art13" checked={finalOptions.informativa_art13_resa} label="Informativa art. 13 resa" onChange={(checked) => setFinalOptions((current) => ({ ...current, informativa_art13_resa: checked }))} />
              </div>
            </Accordion>
          </StepCard>
        </div>
        <Sidebar practice={selectedPractice} client={selectedClient} calculation={calculation} data={data} open={open} onToggle={toggleOpen} />
      </div>
      <div className="iu-pwiz-footer" role="region" aria-label="Azioni preventivo guidato">
        <div className="iu-pwiz-footer-total">
          <span className="iu-pwiz-footer-total-label">TOTALE PREVENTIVO</span>
          <strong className="iu-pwiz-footer-total-value">{totalLabel}</strong>
          <small className="iu-pwiz-footer-total-meta">Base imponibile: {baseLabel} - emissione {dateToItalian(issuedAt)}</small>
        </div>
        <nav className="iu-pwiz-footer-actions" aria-label="Azioni finali preventivo">
          <button className="iu-pwiz-light-button" type="button" onClick={cancel}>Annulla</button>
          <button className="iu-pwiz-primary-button" type="button" disabled={busyCalc || !practiceId} onClick={submitCalculation}>
            {busyCalc ? <Loader2 className="iu-pwiz-spin" size={17} aria-hidden="true" /> : <RefreshCw size={17} aria-hidden="true" />}
            Calcola e aggiorna la bozza
          </button>
          <button className="iu-pwiz-create-button" type="button" disabled={!canCreate} onClick={submitCreate}>
            {busyCreate ? <Loader2 className="iu-pwiz-spin" size={17} aria-hidden="true" /> : null}
            Crea preventivo
          </button>
        </nav>
        <div className="iu-pwiz-footer-tags">
          {finalOptions.genera_conferimento ? <span>conferimento incarico pronto</span> : null}
          {finalOptions.informativa_art13_resa ? <span>informativa art. 13 resa</span> : null}
        </div>
      </div>
    </main>
  )
}
