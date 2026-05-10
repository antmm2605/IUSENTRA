import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  CircleDollarSign,
  FileText,
  Gauge,
  Loader2,
  Plus,
  RefreshCw,
  RotateCcw,
  Scale,
  Trash2,
} from 'lucide-react'
import { LoadingState } from '../ui/LoadingState'
import {
  calculateTariffario,
  emptyTariffarioPage,
  getTariffarioPage,
  type TariffarioDynamic,
  type TariffarioManualLine,
  type TariffarioOption,
  type TariffarioPageData,
  type TariffarioPhaseOption,
  type TariffarioProfile,
  type TariffarioResult,
  type TariffarioState,
  type TariffarioSupport,
} from '../tariffarioData'
import './TariffarioPage.css'

type OpenMap = Record<string, boolean>

const levelLabels: Record<string, string> = {
  minimo: 'Minimo',
  base: 'Base',
  massimo: 'Massimo',
}

let accordionMemory: OpenMap = {
  base: true,
  adr: false,
  integrazioni: false,
  odm: false,
  spese: true,
  audit: true,
  tabelle: false,
  canali: false,
  riferimenti: false,
}

function useAccordionState() {
  const [open, setOpen] = useState<OpenMap>(accordionMemory)
  function toggle(id: string) {
    setOpen((current) => {
      const next = { ...current, [id]: !current[id] }
      accordionMemory = next
      return next
    })
  }
  return { open, toggle }
}

function pickValue(options: TariffarioOption[], fallback = '') {
  return options.find((option) => option.value)?.value || fallback
}

function selectedLevelLabel(value: string) {
  return levelLabels[value] || value || 'Base'
}

function complianceLabel(status?: string, exact?: boolean) {
  const value = String(status || '').toLowerCase()
  if (value === 'snapshot_esatto' || exact) return 'Rilevazione esatta'
  if (value === 'ricostruzione') return 'Ricostruzione dichiarata'
  if (value === 'fallback_tecnico') return 'Fallback tecnico'
  return status || 'Copertura da verificare'
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function referenceRows(value: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(value)) {
    return value.map((item) => {
      if (item && typeof item === 'object' && !Array.isArray(item)) return item as Record<string, unknown>
      const label = String(item || '').trim()
      return label ? { title: label } : {}
    }).filter((item) => Object.keys(item).length)
  }
  const record = asRecord(value)
  return Object.values(record).filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object' && !Array.isArray(item)))
}

function Hero({ stats }: { stats: TariffarioPageData['stats'] }) {
  return (
    <section className="iu-tar-hero" aria-labelledby="tariffario-title">
      <div className="iu-tar-hero-main">
        <span className="iu-tar-kicker">CABINA TARIFFARIA</span>
        <h1 id="tariffario-title">Tariffario Forense</h1>
        <p>
          Un workspace unico per calcolo, regola tariffaria, profilo operativo e passaggio diretto a preventivo,
          parcella e XML FatturaPA. Le sezioni normative restano disponibili, ma non invadono più il flusso
          principale di lavoro.
        </p>
      </div>
      <aside className="iu-tar-hero-side" aria-label="Modalità di consultazione">
        <span className="iu-tar-kicker">MODALITÀ DI CONSULTAZIONE</span>
        <p>Il calcolo resta in primo piano. Registro, tabelle, canali e riferimenti si aprono solo quando servono.</p>
        <div className="iu-tar-hero-badges" aria-label="Stato catalogo tariffario">
          <span><CheckCircle2 size={14} aria-hidden="true" /> {stats.profiles} profili</span>
          <span><Scale size={14} aria-hidden="true" /> {stats.rules} regole</span>
          <span><FileText size={14} aria-hidden="true" /> {stats.tables} tabelle</span>
          <span><Gauge size={14} aria-hidden="true" /> {stats.auditAligned}/{stats.auditTotal} allineate</span>
        </div>
      </aside>
    </section>
  )
}

function Field({
  id,
  label,
  help,
  children,
}: {
  id: string
  label: string
  help?: string
  children: ReactNode
}) {
  return (
    <div className="iu-tar-field">
      <label htmlFor={id}>{label}</label>
      {children}
      {help ? <small id={`${id}-help`}>{help}</small> : null}
    </div>
  )
}

function SelectField({
  id,
  label,
  value,
  options,
  help,
  onChange,
}: {
  id: string
  label: string
  value: string
  options: TariffarioOption[]
  help?: string
  onChange: (value: string) => void
}) {
  return (
    <Field id={id} label={label} help={help}>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)} aria-describedby={help ? `${id}-help` : undefined}>
        {options.map((option) => (
          <option key={`${id}-${option.value || option.label}`} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </Field>
  )
}

function TextField({
  id,
  label,
  value,
  help,
  onChange,
}: {
  id: string
  label: string
  value: string
  help?: string
  onChange: (value: string) => void
}) {
  return (
    <Field id={id} label={label} help={help}>
      <input id={id} value={value} onChange={(event) => onChange(event.target.value)} aria-describedby={help ? `${id}-help` : undefined} />
    </Field>
  )
}

function SwitchRow({
  id,
  checked,
  label,
  onChange,
}: {
  id: string
  checked: boolean
  label: string
  onChange: (checked: boolean) => void
}) {
  return (
    <label className="iu-tar-switch" htmlFor={id}>
      <input id={id} type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span aria-hidden="true" />
      <strong>{label}</strong>
    </label>
  )
}

function Accordion({
  id,
  title,
  badges,
  description,
  open,
  onToggle,
  children,
}: {
  id: string
  title: string
  badges?: string[]
  description?: string
  open: boolean
  onToggle: () => void
  children: ReactNode
}) {
  const contentId = `tariffario-${id}`
  return (
    <section className="iu-tar-accordion">
      <button className="iu-tar-accordion-head" type="button" onClick={onToggle} aria-expanded={open} aria-controls={contentId}>
        <span>
          <strong>{title}</strong>
          {description ? <small>{description}</small> : null}
        </span>
        <span className="iu-tar-accordion-meta">
          {badges?.map((badge) => <em key={badge}>{badge}</em>)}
          <ChevronDown size={18} aria-hidden="true" />
        </span>
      </button>
      {open ? <div className="iu-tar-accordion-body" id={contentId}>{children}</div> : null}
    </section>
  )
}

function StepRail() {
  const steps = [
    ['1', 'Parametri', 'materia e valore'],
    ['2', 'Fasi', 'onorari e complessità'],
    ['3', 'Voci extra', 'spese, ADR, accessori'],
    ['4', 'Output', 'preventivo/parcella/XML'],
  ]
  return (
    <ol className="iu-tar-steps" aria-label="Passaggi operativi">
      {steps.map(([number, label, note]) => (
        <li key={number}>
          <span>{number}</span>
          <strong>{label}</strong>
          <small>{note}</small>
        </li>
      ))}
    </ol>
  )
}

function CompensationBaseSection({
  form,
  dynamic,
  complexityOptions,
  onChange,
}: {
  form: TariffarioState
  dynamic: TariffarioDynamic
  complexityOptions: TariffarioOption[]
  onChange: (next: TariffarioState) => void
}) {
  const selectableComplexity = complexityOptions.length
    ? complexityOptions
    : [
        { value: 'bassa', label: 'Bassa', description: '', enabled: true },
        { value: 'media', label: 'Media/Base', description: '', enabled: true },
        { value: 'alta', label: 'Alta', description: '', enabled: true },
        { value: 'molto_alta', label: 'Molto alta / oltre EUR 520.000', description: '', enabled: true },
      ]
  const allPhases = dynamic.phaseOptions.length
    ? dynamic.phaseOptions
    : form.fasi.map((fase) => ({ key: fase, label: fase, value: fase }))
  const phases = allPhases.filter((phase) => {
    const label = `${phase.key || ''} ${phase.label || ''} ${phase.value || ''}`.toLowerCase()
    return !label.includes('compenso unico')
  })
  function togglePhase(value: string, checked: boolean) {
    const fasi = checked ? Array.from(new Set([...form.fasi, value])) : form.fasi.filter((item) => item !== value)
    onChange({ ...form, fasi })
  }
  return (
    <div className="iu-tar-section-cards">
      <article className="iu-tar-inner-card">
        <h3>Fasi da includere</h3>
        <p>Incluse anche il flag compenso unico quando previsto.</p>
        <div className="iu-tar-check-grid">
          {phases.map((phase) => (
            <label className="iu-tar-check" htmlFor={`fase-${phase.key || phase.value}`} key={phase.value}>
              <input
                id={`fase-${phase.key || phase.value}`}
                type="checkbox"
                checked={form.fasi.includes(phase.value)}
                onChange={(event) => togglePhase(phase.value, event.target.checked)}
              />
              <span>{phase.label}</span>
            </label>
          ))}
          <label className="iu-tar-check" htmlFor="compenso-unico">
            <input
              id="compenso-unico"
              type="checkbox"
              checked={form.compenso_unico}
              onChange={(event) => onChange({ ...form, compenso_unico: event.target.checked })}
            />
            <span>Compenso unico</span>
          </label>
        </div>
      </article>
      <article className="iu-tar-inner-card">
        <h3>Opzioni compenso</h3>
        <p>Compresso in un unico pannello operativo.</p>
        <div className="iu-tar-segment" aria-label="Colonna tariffaria selezionata">
          {selectableComplexity.map((option) => (
            <span className={form.complessita === option.value ? 'is-active' : ''} key={option.value}>
              {option.label}
            </span>
          ))}
        </div>
        <SelectField
          id="tariffario-complessita"
          label="Complessità stimata"
          value={form.complessita}
          options={selectableComplexity}
          help="Molto alta usa il valore indeterminabile parametrizzato oltre EUR 520.000: verifica la congruita prima dell'invio al cliente."
          onChange={(value) => onChange({ ...form, complessita: value })}
        />
        <div className="iu-tar-switch-row">
          <SwitchRow id="spese-generali" checked={form.spese_generali} label="Spese generali 15%" onChange={(checked) => onChange({ ...form, spese_generali: checked })} />
          <SwitchRow id="bonus-telematico" checked={form.bonus_telematico} label="Bonus telematico 30%" onChange={(checked) => onChange({ ...form, bonus_telematico: checked })} />
        </div>
        <TextField id="perc-spese-generali" label="Percentuale spese generali" value={form.perc_spese_generali} onChange={(value) => onChange({ ...form, perc_spese_generali: value })} />
        <p className="iu-tar-info">Il motore applica anche CPA, IVA, anticipazioni ex art. 15 e compenso orario quando il percorso li espone.</p>
      </article>
    </div>
  )
}

function AdrVariationSection({ form, dynamic, onChange }: { form: TariffarioState; dynamic: TariffarioDynamic; onChange: (next: TariffarioState) => void }) {
  const phaseControls = dynamic.variationPolicy['phase_controls']
  const controls = Array.isArray(phaseControls) ? phaseControls : []
  return (
    <div className="iu-tar-muted-box">
      <p>La variazione ADR compare solo quando il profilo attivo o una sua integrazione usa mediazione o negoziazione assistita.</p>
      {controls.length ? (
        <div className="iu-tar-variation-grid">
          {controls.map((rawControl) => {
            const control = rawControl && typeof rawControl === 'object' ? rawControl as Record<string, unknown> : {}
            const key = String(control.key || '')
            const label = String(control.label || key)
            return (
              <TextField
                key={key}
                id={`var-${key}`}
                label={label}
                value={String(form[`var_${key}` as keyof TariffarioState] || '')}
                onChange={(value) => onChange({ ...form, [`var_${key}`]: value } as TariffarioState)}
              />
            )
          })}
        </div>
      ) : null}
      <SwitchRow id="adr-accordo" checked={form.adr_accordo} label="Accordo raggiunto in ADR" onChange={(checked) => onChange({ ...form, adr_accordo: checked })} />
    </div>
  )
}

function IntegrationsSection({ form, dynamic, onChange }: { form: TariffarioState; dynamic: TariffarioDynamic; onChange: (next: TariffarioState) => void }) {
  function toggle(id: string, checked: boolean) {
    onChange({
      ...form,
      accessori: checked ? [...form.accessori, id] : form.accessori.filter((item) => item !== id),
    })
  }
  return (
    <div className="iu-tar-list-panel">
      {dynamic.accessori.length ? dynamic.accessori.map((accessory) => (
        <label className="iu-tar-selectable" htmlFor={`accessorio-${accessory.id}`} key={accessory.id}>
          <input id={`accessorio-${accessory.id}`} type="checkbox" checked={form.accessori.includes(accessory.id)} onChange={(event) => toggle(accessory.id, event.target.checked)} />
          <span>
            <strong>{accessory.label || 'Aggiungi mediazione civile / commerciale'}</strong>
            <small>{accessory.description || 'Attiva il calcolo della mediazione come integrazione opzionale quando la materia lo richiede o quando vuoi includerla nel preventivo già in fase iniziale.'}</small>
          </span>
        </label>
      )) : (
        <div className="iu-tar-muted-box">Nessuna integrazione selezionabile per il profilo attivo. Il pannello resta pronto per mediazione, negoziazione e moduli opzionali.</div>
      )}
    </div>
  )
}

function MediationCostsSection({ form, dynamic, onChange }: { form: TariffarioState; dynamic: TariffarioDynamic; onChange: (next: TariffarioState) => void }) {
  const hasSelectedMediationAccessory = dynamic.accessori.some((accessory) => (
    form.accessori.includes(accessory.id) && accessory.tipo_pratica_id === 'mediazione'
  ))
  const isMediationReachable = Boolean(dynamic.mediazioneEnabled || dynamic.mediazioneEligible || hasSelectedMediationAccessory)
  return (
    <div className="iu-tar-section-cards">
      <article className="iu-tar-inner-card">
        <h3>Costi organismo mediazione</h3>
        <p>Il pannello si attiva quando il profilo attivo o una sua integrazione usa la mediazione civile / commerciale.</p>
        <SwitchRow id="odm-attiva" checked={form.mediazione_odm_attiva} label="Includi costi organismo mediazione" onChange={(checked) => onChange({ ...form, mediazione_odm_attiva: checked })} />
        {!isMediationReachable ? (
          <p className="iu-tar-inline-warning">Seleziona un profilo di mediazione o l'integrazione mediazione per includere i costi ODM nel totale.</p>
        ) : null}
        <SelectField
          id="odm-regime"
          label="Regime"
          value={form.mediazione_odm_regime}
          options={[
            { value: 'volontaria', label: 'Volontaria', description: '', enabled: true },
            { value: 'obbligatoria_demandata', label: 'Obbligatoria / demandata', description: '', enabled: true },
          ]}
          onChange={(value) => onChange({ ...form, mediazione_odm_regime: value })}
        />
      </article>
      <article className="iu-tar-inner-card">
        <h3>D.M. 150/2023</h3>
        <p>Spese di avvio, primo incontro, Tabella A e maggiorazioni ufficiali quando la pratica usa la mediazione civile.</p>
        <SelectField
          id="odm-esito"
          label="Esito"
          value={form.mediazione_odm_esito}
          options={[
            { value: 'primo_incontro_senza_accordo', label: 'Primo incontro senza accordo', description: '', enabled: true },
            { value: 'primo_incontro_con_accordo', label: 'Primo incontro con accordo', description: '', enabled: true },
            { value: 'incontri_successivi_senza_accordo', label: 'Incontri successivi senza accordo', description: '', enabled: true },
            { value: 'incontri_successivi_con_accordo', label: 'Incontri successivi con accordo', description: '', enabled: true },
          ]}
          onChange={(value) => onChange({ ...form, mediazione_odm_esito: value })}
        />
        <SwitchRow
          id="odm-art31"
          checked={form.mediazione_odm_art31_maggiorazione_20}
          label="Maggiorazione art. 31, comma 3"
          onChange={(checked) => onChange({ ...form, mediazione_odm_art31_maggiorazione_20: checked })}
        />
      </article>
    </div>
  )
}

function LiveExpensesSection({ form, dynamic, onChange }: { form: TariffarioState; dynamic: TariffarioDynamic; onChange: (next: TariffarioState) => void }) {
  function toggleExpense(key: string, checked: boolean) {
    onChange({ ...form, esborsi: checked ? [...form.esborsi, key] : form.esborsi.filter((item) => item !== key) })
  }
  return (
    <div className="iu-tar-live-expenses">
      <div className="iu-tar-expense-list">
        {dynamic.expenseOptions.length ? dynamic.expenseOptions.map((expense) => (
          <label className="iu-tar-expense" htmlFor={`expense-${expense.key}`} key={expense.key}>
            <input id={`expense-${expense.key}`} type="checkbox" checked={form.esborsi.includes(expense.key)} onChange={(event) => toggleExpense(expense.key, event.target.checked)} />
            <span>
              <strong>{expense.descrizione}</strong>
              <small>Seleziona per includerla nel totale operativo.</small>
            </span>
            <em>{expense.importo_label}</em>
          </label>
        )) : (
          <div className="iu-tar-muted-box">Nessuna spesa viva suggerita dal profilo attivo. Le voci manuali restano disponibili.</div>
        )}
      </div>
      <ManualLineItems form={form} dynamic={dynamic} onChange={onChange} />
    </div>
  )
}

function ManualLineItems({ form, dynamic, onChange }: { form: TariffarioState; dynamic: TariffarioDynamic; onChange: (next: TariffarioState) => void }) {
  function addLine() {
    const line: TariffarioManualLine = {
      id: `manuale-${String(Date.now())}`,
      descrizione: '',
      tipo: dynamic.manualTypes[0] || 'Onorario',
      importo: '',
      fiscale: dynamic.fiscalTypes[0] || 'imponibile',
      inclusa: true,
    }
    onChange({ ...form, manual_lines: [...form.manual_lines, line] })
  }
  function updateLine(id: string, patch: Partial<TariffarioManualLine>) {
    onChange({ ...form, manual_lines: form.manual_lines.map((line) => line.id === id ? { ...line, ...patch } : line) })
  }
  function removeLine(id: string) {
    onChange({ ...form, manual_lines: form.manual_lines.filter((line) => line.id !== id) })
  }
  return (
    <section className="iu-tar-manual">
      <div className="iu-tar-manual-head">
        <div>
          <h3>Voce manuale</h3>
          <p>Per anticipazioni non tabellari, diritti di segreteria o voci concordate con il cliente.</p>
        </div>
        <button className="iu-tar-button iu-tar-button-light" type="button" onClick={addLine}>
          <Plus size={16} aria-hidden="true" />
          Aggiungi voce manuale
        </button>
      </div>
      {form.manual_lines.length ? (
        <div className="iu-tar-manual-list">
          {form.manual_lines.map((line) => (
            <article className="iu-tar-manual-row" key={line.id}>
              <Field id={`manual-descr-${line.id}`} label="Descrizione">
                <input id={`manual-descr-${line.id}`} value={line.descrizione} onChange={(event) => updateLine(line.id, { descrizione: event.target.value })} />
              </Field>
              <Field id={`manual-tipo-${line.id}`} label="Tipo voce">
                <select id={`manual-tipo-${line.id}`} value={line.tipo} onChange={(event) => updateLine(line.id, { tipo: event.target.value })}>
                  {(dynamic.manualTypes.length ? dynamic.manualTypes : ['Onorario', 'Spesa viva', 'Anticipazione art. 15']).map((tipo) => (
                    <option value={tipo} key={tipo}>{tipo}</option>
                  ))}
                </select>
              </Field>
              <Field id={`manual-fiscale-${line.id}`} label="Trattamento">
                <select id={`manual-fiscale-${line.id}`} value={line.fiscale} onChange={(event) => updateLine(line.id, { fiscale: event.target.value })}>
                  {(dynamic.fiscalTypes.length ? dynamic.fiscalTypes : ['imponibile', 'esente', 'anticipazione art. 15']).map((tipo) => (
                    <option value={tipo} key={tipo}>{tipo}</option>
                  ))}
                </select>
              </Field>
              <Field id={`manual-importo-${line.id}`} label="Importo">
                <input id={`manual-importo-${line.id}`} value={line.importo} onChange={(event) => updateLine(line.id, { importo: event.target.value })} />
              </Field>
              <SwitchRow id={`manual-inclusa-${line.id}`} checked={line.inclusa} label="Inclusa" onChange={(checked) => updateLine(line.id, { inclusa: checked })} />
              <button className="iu-tar-icon-button" type="button" onClick={() => removeLine(line.id)} aria-label="Rimuovi voce manuale">
                <Trash2 size={17} aria-hidden="true" />
              </button>
            </article>
          ))}
        </div>
      ) : (
        <p className="iu-tar-empty">Nessuna voce manuale aggiunta. Usa questa sezione per anticipazioni non tabellari, diritti di segreteria o voci concordate con il cliente.</p>
      )}
    </section>
  )
}

function CalculatorPanel({
  data,
  form,
  dynamic,
  open,
  onToggle,
  onChange,
}: {
  data: TariffarioPageData
  form: TariffarioState
  dynamic: TariffarioDynamic
  open: OpenMap
  onToggle: (id: string) => void
  onChange: (next: TariffarioState) => void
}) {
  const [ruleFilters, setRuleFilters] = useState({
    tableCode: '',
    calcMode: '',
    onlySnapshot: false,
    showRicostruzioni: true,
  })
  const gradeOptions = (data.catalog.gradeCatalog[form.materia] || []).map((grade) => ({ value: grade, label: grade, description: '', enabled: true }))
  const ruleRows = data.catalog.ruleCatalog[form.materia] || []
  const tableOptions = [
    { value: '', label: 'Tutte le tabelle', description: '', enabled: true },
    ...(data.catalog.tableOptions || []),
  ]
  const calcModeOptions = [
    { value: '', label: 'Tutti i tipi', description: '', enabled: true },
    ...(data.catalog.calcModeOptions || []),
  ]
  const areaOptions = data.catalog.areaOptions.length ? data.catalog.areaOptions : data.catalog.materiaOptions
  const filteredRuleRows = ruleRows.filter((rule) => {
    if (ruleFilters.tableCode && rule.table_code !== ruleFilters.tableCode) return false
    if (ruleFilters.calcMode && rule.calc_mode !== ruleFilters.calcMode) return false
    if (ruleFilters.onlySnapshot && !(rule.exact_snapshot || rule.compliance_status === 'snapshot_esatto')) return false
    if (!ruleFilters.showRicostruzioni && rule.compliance_status === 'ricostruzione') return false
    return true
  })
  const selectedRule = ruleRows.find((item) => item.rule_code === form.regola_tariffaria)
  const visibleRuleRows = selectedRule && !filteredRuleRows.some((item) => item.rule_code === selectedRule.rule_code)
    ? [selectedRule, ...filteredRuleRows]
    : filteredRuleRows
  const ruleOptions = [
    { value: '', label: 'Regola standard del tariffario', description: '', enabled: true },
    ...visibleRuleRows.map((rule) => ({
      value: rule.rule_code,
      label: rule.label || rule.rule_label || rule.table_label || rule.rule_code,
      description: `${rule.table_code || ''} ${rule.calc_mode || ''} ${rule.compliance_status || ''}`.trim() || rule.matter,
      enabled: true,
    })),
  ]
  function setMateria(value: string) {
    const phases = data.catalog.phaseCatalog[value] || []
    const grades = data.catalog.gradeCatalog[value] || []
    onChange({
      ...form,
      materia: value,
      regola_tariffaria: '',
      grado: grades[0] || form.grado,
      fasi: phases.map((phase) => phase.value).filter(Boolean),
      accessori: [],
      esborsi: [],
    })
  }
  function setRule(value: string) {
    const rule = ruleRows.find((item) => item.rule_code === value)
    onChange({
      ...form,
      regola_tariffaria: value,
      grado: rule?.grado_input_value || form.grado,
    })
  }
  return (
    <section className="iu-tar-panel" aria-labelledby="tariffario-parametri">
      <header className="iu-tar-panel-head">
        <div>
          <h2 id="tariffario-parametri"><Scale size={17} aria-hidden="true" /> Parametri del calcolo</h2>
        </div>
        <span>Il motore compila preventivi e parcelle dalla stessa struttura.</span>
      </header>
      <div className="iu-tar-field-grid">
        <SelectField id="tariffario-area" label="Area" value={form.materia} options={areaOptions} onChange={setMateria} />
        <SelectField id="tariffario-materia" label="Materia" value={form.materia} options={data.catalog.materiaOptions} onChange={setMateria} />
        <SelectField
          id="tariffario-tabella"
          label="Tabella"
          value={ruleFilters.tableCode}
          options={tableOptions}
          onChange={(value) => setRuleFilters((current) => ({ ...current, tableCode: value }))}
        />
        <SelectField
          id="tariffario-calc-mode"
          label="Tipo calcolo"
          value={ruleFilters.calcMode}
          options={calcModeOptions}
          onChange={(value) => setRuleFilters((current) => ({ ...current, calcMode: value }))}
        />
        <SelectField
          id="tariffario-regola"
          label="Regola tariffaria / competenza"
          value={form.regola_tariffaria}
          options={ruleOptions}
          help="Allinea materia, competenza per giurisdizione e pratica suggerita dal motore."
          onChange={setRule}
        />
        <SelectField id="tariffario-grado" label="Grado / sede" value={form.grado} options={gradeOptions.length ? gradeOptions : data.catalog.gradeOptions} onChange={(value) => onChange({ ...form, grado: value })} />
        <TextField
          id="tariffario-valore"
          label="Valore controversia (EUR)"
          value={form.valore}
          help="Usa 0 solo per valore indeterminabile: il motore applica la complessita selezionata e segnala il valore parametrizzato nel registro."
          onChange={(value) => onChange({ ...form, valore: value })}
        />
      </div>
      <div className="iu-tar-filter-switches">
        <SwitchRow
          id="tariffario-solo-snapshot"
          checked={ruleFilters.onlySnapshot}
          label="Solo rilevazioni esatte"
          onChange={(checked) => setRuleFilters((current) => ({ ...current, onlySnapshot: checked }))}
        />
        <SwitchRow
          id="tariffario-ricostruzioni"
          checked={ruleFilters.showRicostruzioni}
          label="Mostra ricostruzioni dichiarate"
          onChange={(checked) => setRuleFilters((current) => ({ ...current, showRicostruzioni: checked }))}
        />
      </div>
      <StepRail />
      <Accordion id="base" title="Compenso base e fasi" badges={['Compenso unico', 'Opzioni fiscali']} description="Fasi tabellari, compenso unico, complessità stimata, spese generali e bonus." open={open.base} onToggle={() => onToggle('base')}>
        <CompensationBaseSection form={form} dynamic={dynamic} complexityOptions={data.catalog.complexityOptions} onChange={onChange} />
      </Accordion>
      <Accordion id="adr" title="Variazioni ADR e accordo" badges={['Mediazione', 'Negoziazione']} description="Si attiva solo quando il profilo o una sua integrazione usa ADR." open={open.adr} onToggle={() => onToggle('adr')}>
        <AdrVariationSection form={form} dynamic={dynamic} onChange={onChange} />
      </Accordion>
      <Accordion id="integrazioni" title="Integrazioni selezionabili" badges={['Accessori']} description="Mediazione, negoziazione e moduli opzionali del profilo attivo." open={open.integrazioni} onToggle={() => onToggle('integrazioni')}>
        <IntegrationsSection form={form} dynamic={dynamic} onChange={onChange} />
      </Accordion>
      <Accordion id="odm" title="Costi organismo mediazione D.M. 150/2023" badges={['ODM']} description="Spese di avvio, primo incontro, Tabella A e maggiorazioni ufficiali quando la pratica usa la mediazione civile." open={open.odm} onToggle={() => onToggle('odm')}>
        <MediationCostsSection form={form} dynamic={dynamic} onChange={onChange} />
      </Accordion>
      <Accordion id="spese" title="Spese vive suggerite e voce manuale" badges={['Esborsi', 'Art. 15 / manuale']} description="Contributo unificato, diritti di segreteria, notifiche e voci concordate con il cliente." open={open.spese} onToggle={() => onToggle('spese')}>
        <LiveExpensesSection form={form} dynamic={dynamic} onChange={onChange} />
      </Accordion>
    </section>
  )
}

function ResultPanel({ result }: { result: TariffarioResult | null }) {
  if (!result) {
    return (
      <section className="iu-tar-result iu-tar-panel">
        <h2>Risultato del calcolo</h2>
        <div className="iu-tar-empty">Esegui il calcolo per aggiornare risultato, voci incluse, riepilogo economico e collegamenti operativi.</div>
      </section>
    )
  }
  const audit = asRecord(result.audit)
  const references = referenceRows(result.references)
  const auditRows = [
    ['Regola', result.ruleLabel || result.ruleCode],
    ['Tabella', result.tableLabel || result.tableCode],
    ['Scaglione', String(audit.scaglione || '')],
    ['Copertura', complianceLabel(result.complianceStatus, result.exactSnapshot)],
    ['Archivio', result.sourceSnapshot],
    ['Tipo calcolo', String(audit.calc_mode || '')],
  ].filter(([, value]) => String(value || '').trim())
  return (
    <section className="iu-tar-result iu-tar-panel" aria-labelledby="tariffario-risultato">
      <header className="iu-tar-panel-head">
        <h2 id="tariffario-risultato"><CircleDollarSign size={17} aria-hidden="true" /> {result.title}</h2>
        <span>Aggiornato dal motore tariffario</span>
      </header>
      <div className="iu-tar-engine-box">
        <strong>{result.engineLabel}</strong>
        <p>{result.engineText}</p>
      </div>
      {result.badges.length ? (
        <div className="iu-tar-result-badges" aria-label="Badge risultato">
          {result.badges.map((badge) => <span key={badge}>{badge}</span>)}
        </div>
      ) : null}
      {result.warnings.length ? (
        <div className="iu-tar-result-warning-list" role="status">
          {result.warnings.map((warning) => (
            <p key={warning}><AlertCircle size={16} aria-hidden="true" /> {warning}</p>
          ))}
        </div>
      ) : null}
      <div className="iu-tar-chips" aria-label="Informazioni risultato">
        {result.metadata.map((item) => (
          <span key={`${item.label}-${item.value}`}>{item.label}: {item.value}</span>
        ))}
      </div>
      <div className="iu-tar-table-wrap">
        <table className="iu-tar-result-table">
          <caption>Dettaglio fasi, forbice tariffaria e totale compenso.</caption>
          <thead>
            <tr>
              <th scope="col">FASE</th>
              {result.table.columns.map((column) => (
                <th className={result.table.selected === column.id ? 'is-selected' : ''} scope="col" key={column.id}>{column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.table.rows.map((row) => (
              <tr className={`iu-tar-row-${row.kind}`} key={row.id}>
                <th scope="row">{row.label}</th>
                {result.table.columns.map((column) => (
                  <td className={result.table.selected === column.id ? 'is-selected' : ''} key={`${row.id}-${column.id}`}>
                    {row.values[column.id] || '-'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {result.note ? <p className="iu-tar-note">{result.note}</p> : null}
      <div className="iu-tar-audit-box" aria-label="Registro tariffario del calcolo">
        <div>
          <h3>Registro tariffario</h3>
          <dl>
            {auditRows.map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{String(value)}</dd>
              </div>
            ))}
          </dl>
          {result.complianceNote ? <p>{result.complianceNote}</p> : null}
        </div>
        <div>
          <h3>Riferimenti normativi</h3>
          {references.length ? (
            <ul className="iu-tar-reference-list">
              {references.slice(0, 8).map((ref, index) => (
                <li key={`${String(ref.code || ref.title || 'ref')}-${index}`}>
                  <strong>{String(ref.title || ref.label || ref.code || 'Riferimento')}</strong>
                  <span>{String(ref.article || ref.description || ref.url || '')}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="iu-tar-empty">Nessun riferimento normativo esposto dal risultato.</p>
          )}
        </div>
      </div>
      <div className="iu-tar-bottom-grid">
        <IncludedItems result={result} />
        <EconomicSummary result={result} />
      </div>
    </section>
  )
}

function IncludedItems({ result }: { result: TariffarioResult }) {
  return (
    <section className="iu-tar-subpanel" aria-labelledby="voci-incluse">
      <h3 id="voci-incluse">Voci incluse nel risultato operativo</h3>
      {result.included.length ? (
        <table className="iu-tar-mini-table">
          <thead>
            <tr>
              <th scope="col">DESCRIZIONE</th>
              <th scope="col">TIPO</th>
              <th scope="col">IMPORTO</th>
            </tr>
          </thead>
          <tbody>
            {result.included.map((item) => (
              <tr key={item.id}>
                <td>{item.descrizione}</td>
                <td>{item.fiscale ? `${item.tipo} - ${item.fiscale}` : item.tipo}</td>
                <td>{item.importo_label}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="iu-tar-empty">Nessuna voce inclusa nel risultato operativo.</p>
      )}
    </section>
  )
}

function EconomicSummary({ result }: { result: TariffarioResult }) {
  return (
    <section className="iu-tar-subpanel" aria-labelledby="riepilogo-economico">
      <h3 id="riepilogo-economico">Riepilogo economico collegato</h3>
      <dl className="iu-tar-economic">
        {result.economic.rows.map((row) => (
          <div className={row.tone === 'primary' ? 'is-total' : ''} key={row.id}>
            <dt>{row.label}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>
      <div className="iu-tar-cta-row">
        {result.actions.preventivo ? <a className="iu-tar-button iu-tar-button-primary" href={result.actions.preventivo}>Crea preventivo guidato</a> : <button className="iu-tar-button iu-tar-button-primary" type="button" disabled>Crea preventivo guidato</button>}
        {result.actions.parcella ? <a className="iu-tar-button iu-tar-button-light" href={result.actions.parcella}>Crea parcella precompilata</a> : <button className="iu-tar-button iu-tar-button-light" type="button" disabled>Crea parcella precompilata</button>}
      </div>
    </section>
  )
}

function RealtimeSummary({
  result,
  busy,
  error,
  onRun,
  onReset,
}: {
  result: TariffarioResult | null
  busy: boolean
  error: string
  onRun: () => void
  onReset: () => void
}) {
  const operationalTotal = result?.economic.total || result?.selectedTotal || 'EUR 0,00'
  return (
    <aside
      className="iu-tar-realtime iu-tar-summary-sticky"
      aria-label="Riepilogo in tempo reale"
      aria-live="polite"
    >
      <div className="iu-tar-realtime-head">
        <span>RIEPILOGO IN TEMPO REALE</span>
        <button className="iu-tar-summary-refresh" type="button" onClick={onRun} disabled={busy}>
          {busy ? <Loader2 size={16} aria-hidden="true" className="iu-tar-spin" /> : <RefreshCw size={16} aria-hidden="true" />}
          Calcola e aggiorna il quadro
        </button>
      </div>
      <strong>{operationalTotal}</strong>
      {error ? (
        <p className="iu-tar-summary-error" role="alert">
          <AlertCircle size={16} aria-hidden="true" />
          {error}
        </p>
      ) : null}
      <p>{result?.engineText || 'Il risultato sarà disponibile dopo il primo calcolo.'}</p>
      <div className="iu-tar-range">
        {['minimo', 'base', 'massimo'].map((level) => (
          <div className={result?.selectedLevel === level ? 'is-selected' : ''} key={level}>
            <small>{selectedLevelLabel(level)}</small>
            <b>{result?.rangeTotals[level] || 'EUR 0,00'}</b>
          </div>
        ))}
      </div>
      <div className="iu-tar-cta-row">
        {result?.actions.preventivo ? <a className="iu-tar-button iu-tar-button-invert" href={result.actions.preventivo}>Crea preventivo</a> : <button className="iu-tar-button iu-tar-button-invert" type="button" disabled>Crea preventivo</button>}
        {result?.actions.parcella ? <a className="iu-tar-button iu-tar-button-ghost" href={result.actions.parcella}>Crea parcella</a> : <button className="iu-tar-button iu-tar-button-ghost" type="button" disabled>Crea parcella</button>}
        <button className="iu-tar-summary-reset" type="button" onClick={onReset} disabled={busy}>
          <RotateCcw size={15} aria-hidden="true" />
          Reset
        </button>
      </div>
    </aside>
  )
}

function StickyRealtimeSummary({
  result,
  busy,
  error,
  onRun,
  onReset,
}: {
  result: TariffarioResult | null
  busy: boolean
  error: string
  onRun: () => void
  onReset: () => void
}) {
  const anchor = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    anchor.current?.querySelector<HTMLElement>('.iu-tar-realtime')?.setAttribute('data-summary-ready', 'true')
  }, [busy, error, result])

  return (
    <div
      ref={anchor}
      className="iu-tar-summary-holder"
    >
      <RealtimeSummary
        result={result}
        busy={busy}
        error={error}
        onRun={onRun}
        onReset={onReset}
      />
    </div>
  )
}

function ActiveProfileCard({ profile }: { profile: TariffarioProfile }) {
  return (
    <section className="iu-tar-side-card" aria-labelledby="profilo-attivo">
      <header>
        <h2 id="profilo-attivo">Profilo attivo</h2>
        <span>validato</span>
      </header>
      <div className="iu-tar-chips">
        {profile.badges.map((badge) => <span key={badge}>{badge}</span>)}
      </div>
      <h3>{profile.title || 'Profilo tariffario operativo'}</h3>
      <p>{profile.description || 'Calcolo su tabella e fasi selezionabili.'}</p>
      {profile.when ? <p>{profile.when}</p> : null}
      <dl className="iu-tar-profile-meta">
        {profile.metadata.map((item) => (
          <div key={`${item.label}-${item.value}`}>
            <dt>{item.label}</dt>
            <dd>{item.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

function SupportAccordion({
  id,
  title,
  badge,
  description,
  open,
  onToggle,
  children,
}: {
  id: string
  title: string
  badge: string
  description: string
  open: boolean
  onToggle: () => void
  children: ReactNode
}) {
  return (
    <section className="iu-tar-support-accordion">
      <button type="button" onClick={onToggle} aria-expanded={open} aria-controls={`support-${id}`}>
        <span>
          <strong>{title}</strong>
          <small>{description}</small>
        </span>
        <em>{badge}</em>
      </button>
      {open ? <div id={`support-${id}`}>{children}</div> : null}
    </section>
  )
}

function NormativeSupportPanel({ support, open, onToggle }: { support: TariffarioSupport; open: OpenMap; onToggle: (id: string) => void }) {
  const auditTotal = support.auditSummary.totale || support.auditRows.length
  const openAudit = (support.auditSummary.ricostruttiva || 0) + (support.auditSummary.da_verificare || 0)
  return (
    <section className="iu-tar-side-card iu-tar-support" aria-labelledby="supporto-operativo">
      <header>
        <div>
          <h2 id="supporto-operativo">Supporto normativo e operativo</h2>
          <p>Apri solo il dettaglio che ti serve</p>
        </div>
        <span>apri se serve</span>
      </header>
      <SupportAccordion
        id="audit"
        title="Registro conformita tariffaria"
        badge={`${auditTotal} regole`}
        description={`${openAudit} aperte - copertura tra rilevazione ufficiale e collegamenti ricostruiti.`}
        open={open.audit}
        onToggle={() => onToggle('audit')}
      >
        <div className="iu-tar-audit-cards">
          {support.auditCards.map((card) => (
            <article key={card.label}>
              <strong>{card.value}</strong>
              <span>{card.label}</span>
            </article>
          ))}
        </div>
        <div className="iu-tar-audit-list">
          {support.auditRows.length ? support.auditRows.map((row, index) => (
            <article key={`${String(row.rule_code || row.label || index)}`}>
              <div>
                <strong>{String(row.label || row.practice_label || row.rule_code || 'Regola tariffaria')}</strong>
                <span>{String(row.compliance_status || 'verifica')}</span>
              </div>
              <p>{String(row.matter || row.category || row.practice_label || '')}</p>
              <small>{String(row.table_label || row.table_code || '')}</small>
              {row.note || row.description ? <p>{String(row.note || row.description)}</p> : null}
            </article>
          )) : <p className="iu-tar-empty">Nessuna voce aperta.</p>}
        </div>
      </SupportAccordion>
      <SupportAccordion
        id="tabelle"
        title="Tabelle normative sincronizzate"
        badge={`${support.tables.length} attive`}
        description="Stato del catalogo normativo usato da tariffario e preventivi."
        open={open.tabelle}
        onToggle={() => onToggle('tabelle')}
      >
        <MiniRows rows={support.tables} fallback="Nessuna tabella normativa disponibile." />
      </SupportAccordion>
      <SupportAccordion
        id="canali"
        title="Canali fatturazione e operativita"
        badge={`${support.channels.length} flussi`}
        description="Dal calcolo al preventivo, parcella, XML e upload esterno."
        open={open.canali}
        onToggle={() => onToggle('canali')}
      >
        <MiniRows rows={support.channels} fallback="Nessun canale operativo disponibile." />
      </SupportAccordion>
      <SupportAccordion
        id="riferimenti"
        title="Riferimenti normativi ufficiali"
        badge={`${support.references.length} fonti`}
        description="Archivio consultabile senza sovraccaricare il flusso di calcolo."
        open={open.riferimenti}
        onToggle={() => onToggle('riferimenti')}
      >
        <MiniRows rows={support.references} fallback="Nessun riferimento disponibile." />
      </SupportAccordion>
    </section>
  )
}

function MiniRows({ rows, fallback }: { rows: Array<Record<string, string | number | boolean | null>>; fallback: string }) {
  if (!rows.length) return <p className="iu-tar-empty">{fallback}</p>
  return (
    <div className="iu-tar-mini-rows">
      {rows.map((row, index) => (
        <article key={`${String(row.id || row.title || row.label || index)}`}>
          <strong>{String(row.title || row.label || row.id || 'Voce')}</strong>
          <span>{String(row.description || row.note || row.status || row.article || '')}</span>
        </article>
      ))}
    </div>
  )
}

export function TariffarioPage() {
  const [data, setData] = useState<TariffarioPageData>(emptyTariffarioPage)
  const [form, setForm] = useState<TariffarioState>(emptyTariffarioPage.state)
  const [profile, setProfile] = useState<TariffarioProfile>(emptyTariffarioPage.profile)
  const [dynamic, setDynamic] = useState<TariffarioDynamic>(emptyTariffarioPage.dynamic)
  const [result, setResult] = useState<TariffarioResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')
  const latestRun = useRef(0)
  const syncedPayload = useRef('')
  const { open, toggle } = useAccordionState()

  function applyPage(next: TariffarioPageData) {
    syncedPayload.current = JSON.stringify(next.state)
    setData(next)
    setForm(next.state)
    setProfile(next.profile)
    setDynamic(next.dynamic)
    setResult(next.result)
    setError('')
  }

  function load() {
    setLoading(true)
    getTariffarioPage()
      .then(applyPage)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  const hasCatalog = useMemo(() => data.catalog.materiaOptions.length > 0, [data.catalog.materiaOptions.length])
  const fallbackRunError = 'Il calcolo non è stato completato. Verifica i parametri e riprova.'

  function updateForm(next: TariffarioState) {
    latestRun.current += 1
    setForm(next)
  }

  async function submitRun() {
    const runId = latestRun.current + 1
    latestRun.current = runId
    setBusy(true)
    setSuccess('')
    setError('')
    const response = await calculateTariffario(form)
    if (runId !== latestRun.current) return
    setBusy(false)
    if (!response.ok || !response.result) {
      setError(response.warnings[0]?.message || fallbackRunError)
      return
    }
    syncedPayload.current = JSON.stringify(response.state)
    setForm(response.state)
    setProfile(response.profile)
    setDynamic(response.dynamic)
    setResult(response.result)
    setSuccess('Calcolo completato.')
  }

  function reset() {
    latestRun.current += 1
    syncedPayload.current = JSON.stringify(data.state)
    setForm(data.state)
    setProfile(data.profile)
    setDynamic(data.dynamic)
    setResult(data.result)
    setError('')
  }

  useEffect(() => {
    if (loading || !hasCatalog) return
    const payload = JSON.stringify(form)
    if (payload === syncedPayload.current) return
    const runId = latestRun.current + 1
    latestRun.current = runId
    const timer = window.setTimeout(async () => {
      setBusy(true)
      setSuccess('')
      setError('')
      const response = await calculateTariffario(form)
      if (runId !== latestRun.current) return
      setBusy(false)
      if (!response.ok || !response.result) {
        setError(response.warnings[0]?.message || fallbackRunError)
        return
      }
      syncedPayload.current = JSON.stringify(response.state)
      setForm(response.state)
      setProfile(response.profile)
      setDynamic(response.dynamic)
      setResult(response.result)
      setSuccess('Calcolo aggiornato.')
      setError('')
    }, 450)
    return () => window.clearTimeout(timer)
  }, [form, hasCatalog, loading])

  if (loading) {
    return <LoadingState title="Caricamento tariffario" message="Recupero catalogo, profili, controlli e risultato iniziale." />
  }

  return (
    <main className="iu-content iu-page iu-tar-page">
      <Hero stats={data.stats} />
      {busy ? <LoadingState title="Calcolo tariffario" message="Salvataggio e aggiornamento del risultato." /> : null}
      {success ? <div className="iu-tar-alert iu-tar-alert-success" role="status">{success}</div> : null}
      {error ? <div className="iu-tar-alert iu-tar-alert-error" role="alert">{error}</div> : null}
      {!hasCatalog ? (
        <section className="iu-tar-panel">
          <h2>Catalogo tariffario non disponibile</h2>
          <p>La schermata e' attiva, ma il catalogo non ha restituito opzioni operative.</p>
          <div className="iu-tar-rollback">
            <strong>Percorso di recupero</strong>
            <a className="iu-tar-button iu-tar-button-light" href="/tariffario?_legacy=1">Apri vista di recupero</a>
          </div>
        </section>
      ) : (
        <>
          <div className="iu-tar-layout">
            <div className="iu-tar-main">
              <CalculatorPanel
                data={data}
                form={form}
                dynamic={dynamic}
                open={open}
                onToggle={toggle}
                onChange={updateForm}
              />
              <ResultPanel result={result} />
            </div>
            <aside className="iu-tar-sidebar">
              <StickyRealtimeSummary result={result} busy={busy} error={error} onRun={submitRun} onReset={reset} />
              <ActiveProfileCard profile={profile} />
              <NormativeSupportPanel support={data.support} open={open} onToggle={toggle} />
            </aside>
          </div>
        </>
      )}
    </main>
  )
}
