import { useEffect, useRef, useState, type FormEvent } from 'react'
import { AlignCenter, AlignJustify, AlignLeft, ArrowLeft, Bold, Copy, FileDown, FilePlus2, FileUp, Italic, List, ListOrdered, PencilLine, Save, Underline, Wand2 } from 'lucide-react'
import {
  generateStudioTemplate,
  getStudioTemplateDetail,
  getStudioTemplateForm,
  getStudioTemplateUse,
  importDocumentForTemplate,
  runStudioTemplateAction,
  saveStudioTemplate,
  studioTemplateRoute,
  type StudioTemplateDetail,
  type StudioTemplateField,
  type StudioTemplateForm,
  type StudioTemplateSection,
  type StudioTemplateSummary,
  type StudioTemplateUse,
} from '../templateStudioData'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { plainTextToParagraphs, sanitizePastedHtml } from './templateEditor/pasteSanitizer'
import { Panel } from '../ui/Panel'
import './TemplateStudioPage.css'

function csrfToken(): string {
  return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
}

function ActionButton({ action, label, tone = 'neutral', confirmMessage }: { action: string; label: string; tone?: 'neutral' | 'danger' | 'primary'; confirmMessage?: string }) {
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  async function run() {
    if (confirmMessage && !window.confirm(confirmMessage)) return
    setBusy(true)
    const result = await runStudioTemplateAction(action)
    setBusy(false)
    setMessage(result.message)
    if (result.ok && result.redirectHref) window.location.assign(result.redirectHref)
  }
  return (
    <span className="iu-tstudio-post">
      <Button type="button" tone={tone} disabled={busy} onClick={() => void run()}>{busy ? 'Attendere…' : label}</Button>
      {message ? <small role="status">{message}</small> : null}
    </span>
  )
}

function sembraHtml(value: string): boolean {
  return /<(p|div|h[1-6]|ul|ol|li|table|br|blockquote|span|strong|em)\b/i.test(value)
}

function comeHtml(value: string): string {
  if (!value.trim()) return '<p></p>'
  return sembraHtml(value) ? sanitizePastedHtml(value) : plainTextToParagraphs(value)
}

type Comando = { label: string; icon: typeof Bold; command: string; value?: string }

const COMANDI: Comando[] = [
  { label: 'Grassetto', icon: Bold, command: 'bold' },
  { label: 'Corsivo', icon: Italic, command: 'italic' },
  { label: 'Sottolineato', icon: Underline, command: 'underline' },
  { label: 'Elenco puntato', icon: List, command: 'insertUnorderedList' },
  { label: 'Elenco numerato', icon: ListOrdered, command: 'insertOrderedList' },
  { label: 'Allinea a sinistra', icon: AlignLeft, command: 'justifyLeft' },
  { label: 'Centra', icon: AlignCenter, command: 'justifyCenter' },
  { label: 'Giustifica', icon: AlignJustify, command: 'justifyFull' },
]

function RichArea({ initialHtml, onChange, label, minRows = 18 }: { initialHtml: string; onChange: (html: string, plain: string) => void; label: string; minRows?: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const iniziale = useRef(initialHtml)
  useEffect(() => {
    if (ref.current) {
      ref.current.innerHTML = comeHtml(iniziale.current)
      onChange(ref.current.innerHTML, ref.current.innerText)
    }
    // Solo al primo montaggio: poi il contenuto lo governa l'utente.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  function esegui(command: string, value?: string) {
    ref.current?.focus()
    document.execCommand(command, false, value)
    if (ref.current) onChange(ref.current.innerHTML, ref.current.innerText)
  }
  return (
    <div className="iu-tstudio-rich">
      <div className="iu-tstudio-rich__toolbar" role="toolbar" aria-label={`Formattazione: ${label}`}>
        {COMANDI.map((comando) => {
          const Icona = comando.icon
          return (
            <button type="button" key={comando.command} title={comando.label} aria-label={comando.label} onMouseDown={(event) => event.preventDefault()} onClick={() => esegui(comando.command, comando.value)}>
              <Icona size={15} aria-hidden="true" />
            </button>
          )
        })}
      </div>
      <div
        ref={ref}
        className={`iu-tstudio-rich__area iu-tstudio-rich__area--r${Math.min(Math.max(minRows, 8), 24)}`}
        contentEditable
        suppressContentEditableWarning
        role="textbox"
        aria-multiline="true"
        aria-label={label}
        onInput={() => ref.current && onChange(ref.current.innerHTML, ref.current.innerText)}
        onPaste={(event) => {
          event.preventDefault()
          const html = event.clipboardData.getData('text/html')
          const plain = event.clipboardData.getData('text/plain')
          document.execCommand('insertHTML', false, html ? sanitizePastedHtml(html) : plainTextToParagraphs(plain))
        }}
        data-rich-editor
      />
    </div>
  )
}

function inserisciNelCursore(html: string) {
  const area = document.querySelector<HTMLDivElement>('[data-rich-editor]')
  if (!area) return
  area.focus()
  document.execCommand('insertHTML', false, html)
  area.dispatchEvent(new Event('input', { bubbles: true }))
}

function ModelActions({ item }: { item: StudioTemplateSummary }) {
  return (
    <div className="iu-tstudio-actions">
      {item.useHref ? <ButtonLink href={item.useHref} tone="primary"><Wand2 size={16} aria-hidden="true" />Compila</ButtonLink> : null}
      {item.editHref ? <ButtonLink href={item.editHref} tone="neutral"><PencilLine size={16} aria-hidden="true" />Modifica</ButtonLink> : null}
      {item.cloneAction ? <ActionButton action={item.cloneAction} label="Clona" /> : null}
      {item.deleteAction ? <ActionButton action={item.deleteAction} label="Elimina" tone="danger" confirmMessage={`Eliminare il modello «${item.title}»?`} /> : null}
    </div>
  )
}

function Field({ field, value, onChange }: { field: StudioTemplateField; value: string; onChange: (value: string) => void }) {
  const id = `tstudio-${field.name}`
  return (
    <label className={`iu-tstudio-field${field.type === 'textarea' ? ' iu-tstudio-field--wide' : ''}`} htmlFor={id}>
      <span>{field.label}{field.required ? ' *' : ''}</span>
      {field.type === 'textarea' ? (
        <textarea id={id} rows={Math.max(field.rows, 3)} value={value} placeholder={field.placeholder} onChange={(event) => onChange(event.target.value)} />
      ) : field.type === 'select' ? (
        <select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
          <option value="">—</option>
          {field.options.map((opt) => <option value={opt.value} key={opt.value}>{opt.label}</option>)}
        </select>
      ) : (
        <input id={id} type={field.type} value={value} placeholder={field.placeholder} onChange={(event) => onChange(event.target.value)} />
      )}
    </label>
  )
}

function Sections({ sections, values, onChange }: { sections: StudioTemplateSection[]; values: Record<string, string>; onChange: (name: string, value: string) => void }) {
  return (
    <>
      {sections.map((section) => (
        <fieldset className="iu-tstudio-section" key={section.title}>
          <legend>{section.title}</legend>
          <div className="iu-tstudio-grid">
            {section.fields.map((field) => <Field field={field} value={values[field.name] || ''} onChange={(value) => onChange(field.name, value)} key={field.name} />)}
          </div>
        </fieldset>
      ))}
    </>
  )
}

function SchedaView({ id }: { id: string }) {
  const [item, setItem] = useState<StudioTemplateDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  useEffect(() => {
    getStudioTemplateDetail(id).then((payload) => {
      setItem(payload.item)
      setMessage(payload.message)
    }).finally(() => setLoading(false))
  }, [id])
  if (loading) return <LoadingState title="Caricamento modello" message="Lettura della scheda del modello." />
  if (!item) return <Page title="Modello non disponibile"><EmptyState title="Modello non trovato" message={message || 'Il modello indicato non esiste.'} /></Page>
  return (
    <Page
      title={item.title}
      subtitle={[item.category, item.area, item.branch].filter(Boolean).join(' · ') || 'Modello di studio'}
      actions={<ButtonLink href="/template-atti" tone="neutral"><ArrowLeft size={16} aria-hidden="true" />Template</ButtonLink>}
    >
      <Panel title="Azioni" subtitle={item.builtin ? 'Modello integrato: per cambiarlo, clonalo e modifica la copia.' : 'Modello dello studio.'} actions={item.builtin ? <Badge tone="info">Integrato</Badge> : <Badge tone="primary">Studio</Badge>}>
        <ModelActions item={item} />
        {item.compilerHref ? <p className="iu-tstudio-note">Collegato al compilatore: <a href={item.compilerHref}>apri la compilazione guidata</a>.</p> : null}
        {item.notes ? <p className="iu-tstudio-note">{item.notes}</p> : null}
      </Panel>
      <Panel title="Campi da compilare" subtitle="Sezioni e campi guidati del modello.">
        {item.sections.length ? (
          <ul className="iu-tstudio-fields">
            {item.sections.map((section) => (
              <li key={section.title}><strong>{section.title}</strong>: {section.fields.map((field) => field.label).join(', ')}</li>
            ))}
          </ul>
        ) : <EmptyState title="Nessun campo guidato" />}
      </Panel>
      <Panel title="Testo del modello">
        <pre className="iu-tstudio-body">{item.body || 'Testo non disponibile.'}</pre>
      </Panel>
      {item.related.length ? (
        <Panel title="Modelli collegati">
          <ul className="iu-tstudio-related">
            {item.related.map((rel) => <li key={rel.id}><a href={rel.href}>{rel.title}</a></li>)}
          </ul>
        </Panel>
      ) : null}
    </Page>
  )
}

function FormView({ id }: { id: string }) {
  const [form, setForm] = useState<StudioTemplateForm | null>(null)
  const [values, setValues] = useState<StudioTemplateForm['values']>({ titolo: '', categoria: '', corpo: '', note: '' })
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [importing, setImporting] = useState(false)
  const [loadKey, setLoadKey] = useState(0)
  useEffect(() => {
    getStudioTemplateForm(id).then((payload) => {
      setForm(payload)
      setValues(payload.values)
      setLoadKey((current) => current + 1)
    })
  }, [id])

  async function importa(file: File) {
    if (!form?.importAction) return
    setImporting(true)
    const esito = await importDocumentForTemplate(form.importAction, file)
    setImporting(false)
    setMessage(esito.message)
    if (esito.ok) inserisciNelCursore(esito.kind === 'html' ? sanitizePastedHtml(esito.content) : plainTextToParagraphs(esito.content))
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    const result = await saveStudioTemplate(values, id)
    setSaving(false)
    setMessage(result.message)
    setErrors(result.errors)
    if (result.ok && result.item?.detailHref) window.location.assign(result.item.detailHref)
  }

  if (!form) return <LoadingState title="Caricamento" message="Preparazione del modulo." />
  if (!form.ok) return <Page title="Modello non disponibile"><EmptyState title="Modello non trovato" message={form.message} /></Page>
  if (id && form.item?.builtin) {
    return (
      <Page title={form.item.title} subtitle="Modello integrato">
        <Panel title="Modello integrato" subtitle="I modelli integrati non si modificano: clona il modello e modifica la copia.">
          <ModelActions item={form.item} />
        </Panel>
      </Page>
    )
  }
  return (
    <Page
      title={id ? `Modifica «${values.titolo || form.item?.title || ''}»` : 'Nuovo modello di studio'}
      subtitle="Il testo può usare le variabili del modello, ad esempio {{ cliente.nome_completo }} o {{ fascicolo.numero_rg }}."
      actions={<ButtonLink href={id && form.item ? form.item.detailHref : '/template-atti'} tone="neutral"><ArrowLeft size={16} aria-hidden="true" />Indietro</ButtonLink>}
    >
      <Panel title="Dati del modello">
        <form className="iu-tstudio-form" onSubmit={submit}>
          {message ? <p className={`iu-tstudio-message${Object.keys(errors).length ? ' is-error' : ''}`}>{message}</p> : null}
          <div className="iu-tstudio-grid">
            <label className="iu-tstudio-field">
              <span>Titolo *</span>
              <input value={values.titolo} onChange={(event) => setValues({ ...values, titolo: event.target.value })} aria-invalid={Boolean(errors.titolo)} />
              {errors.titolo ? <small>{errors.titolo}</small> : null}
            </label>
            <label className="iu-tstudio-field">
              <span>Categoria</span>
              <select value={values.categoria} onChange={(event) => setValues({ ...values, categoria: event.target.value })}>
                {form.categories.map((categoria) => <option value={categoria} key={categoria}>{categoria}</option>)}
              </select>
            </label>
            <div className="iu-tstudio-field iu-tstudio-field--wide">
              <span>Testo del modello *</span>
              <div className="iu-tstudio-editor">
                <RichArea key={loadKey} label="Testo del modello" initialHtml={values.corpo} onChange={(html) => setValues((current) => ({ ...current, corpo: html }))} />
                <aside className="iu-tstudio-vars" aria-label="Variabili disponibili">
                  <strong>Variabili</strong>
                  {form.variableGroups.map((gruppo) => (
                    <div key={gruppo.title}>
                      <small>{gruppo.title}</small>
                      {gruppo.variables.map((variabile) => (
                        <button type="button" key={variabile} onMouseDown={(event) => event.preventDefault()} onClick={() => inserisciNelCursore(`{{ ${variabile} }}`)}>{`{{ ${variabile} }}`}</button>
                      ))}
                    </div>
                  ))}
                  {form.importAction ? (
                    <label className="iu-tstudio-import">
                      <FileUp size={15} aria-hidden="true" />
                      <span>{importing ? 'Importazione…' : 'Importa documento'}</span>
                      <input type="file" accept=".docx,.pdf,.txt,.rtf" disabled={importing} onChange={(event) => { const file = event.target.files?.[0]; if (file) void importa(file); event.target.value = '' }} />
                    </label>
                  ) : null}
                </aside>
              </div>
              {errors.corpo ? <small>{errors.corpo}</small> : null}
            </div>
            <label className="iu-tstudio-field iu-tstudio-field--wide">
              <span>Note interne</span>
              <textarea rows={3} value={values.note} onChange={(event) => setValues({ ...values, note: event.target.value })} />
            </label>
          </div>
          <div className="iu-tstudio-actions">
            <Button type="submit" tone="primary" disabled={saving}><Save size={16} aria-hidden="true" />{saving ? 'Salvataggio…' : 'Salva modello'}</Button>
          </div>
        </form>
      </Panel>
    </Page>
  )
}

function UsaView({ id }: { id: string }) {
  const [data, setData] = useState<StudioTemplateUse | null>(null)
  const [clientId, setClientId] = useState(() => new URLSearchParams(window.location.search).get('id_cliente') || '')
  const [matterId, setMatterId] = useState(() => new URLSearchParams(window.location.search).get('id_fascicolo') || '')
  const [values, setValues] = useState<Record<string, string>>({})
  const [generated, setGenerated] = useState('')
  const [generatedHtml, setGeneratedHtml] = useState('')
  const [outputKey, setOutputKey] = useState(0)
  const [pdfAction, setPdfAction] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    getStudioTemplateUse(id, clientId, matterId).then((payload) => {
      setData(payload)
      setValues(payload.values)
      if (payload.selectedClientId && payload.selectedClientId !== clientId) setClientId(payload.selectedClientId)
    })
  }, [id, clientId, matterId])

  async function genera(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    const result = await generateStudioTemplate(id, { clientId, matterId, fields: values })
    setBusy(false)
    setMessage(result.ok ? '' : result.message)
    if (result.ok) {
      setGenerated(result.text)
      setGeneratedHtml(result.html || result.text)
      setOutputKey((current) => current + 1)
      setPdfAction(result.pdfAction)
    }
  }

  if (!data) return <LoadingState title="Caricamento" message="Preparo cliente, fascicolo e campi del modello." />
  if (!data.ok || !data.item) return <Page title="Modello non disponibile"><EmptyState title="Modello non trovato" message={data.message} /></Page>
  const token = csrfToken()
  return (
    <Page
      title={`Compila «${data.item.title}»`}
      subtitle="I campi si precompilano dal cliente e dal fascicolo scelti; controlla e completa prima di generare."
      actions={<ButtonLink href={data.item.detailHref} tone="neutral"><ArrowLeft size={16} aria-hidden="true" />Scheda modello</ButtonLink>}
    >
      <Panel title="Dati di partenza">
        <div className="iu-tstudio-grid">
          <label className="iu-tstudio-field">
            <span>Cliente</span>
            <select value={clientId} onChange={(event) => { setClientId(event.target.value); setMatterId('') }}>
              <option value="">— nessun cliente —</option>
              {data.clients.map((client) => <option value={client.id} key={client.id}>{client.label}</option>)}
            </select>
          </label>
          <label className="iu-tstudio-field">
            <span>Fascicolo</span>
            <select value={matterId} disabled={!clientId} onChange={(event) => setMatterId(event.target.value)}>
              <option value="">— nessun fascicolo —</option>
              {data.matters.map((matter) => <option value={matter.id} key={matter.id}>{matter.label}</option>)}
            </select>
          </label>
        </div>
      </Panel>
      <Panel title="Campi del modello">
        <form className="iu-tstudio-form" onSubmit={genera}>
          <Sections sections={data.sections} values={values} onChange={(name, value) => setValues((current) => ({ ...current, [name]: value }))} />
          {message ? <p className="iu-tstudio-message is-error">{message}</p> : null}
          <div className="iu-tstudio-actions">
            <Button type="submit" tone="primary" disabled={busy}><FilePlus2 size={16} aria-hidden="true" />{busy ? 'Generazione…' : 'Genera il testo'}</Button>
          </div>
        </form>
      </Panel>
      {generated ? (
        <Panel title="Revisione finale" subtitle="Rifinisci il testo; il PDF usa il testo di questa casella.">
          <form className="iu-tstudio-form" method="post" action={pdfAction} target="_blank">
            {token ? <input type="hidden" name="_csrf_token" value={token} /> : null}
            <RichArea key={outputKey} label="Testo generato" initialHtml={generatedHtml} minRows={24} onChange={(html, plain) => { setGeneratedHtml(html); setGenerated(plain) }} />
            <input type="hidden" name="testo_generato_html" value={generatedHtml} />
            <input type="hidden" name="testo_generato" value={generated} />
            <div className="iu-tstudio-actions">
              <Button type="submit" tone="primary"><FileDown size={16} aria-hidden="true" />Scarica PDF</Button>
              <Button type="button" tone="neutral" onClick={() => void navigator.clipboard?.writeText(generated)}><Copy size={16} aria-hidden="true" />Copia testo</Button>
            </div>
          </form>
        </Panel>
      ) : null}
    </Page>
  )
}

export function TemplateStudioPage() {
  const route = studioTemplateRoute(window.location.pathname)
  if (!route) return <Page title="Modelli di studio"><EmptyState title="Percorso non riconosciuto" /></Page>
  if (route.mode === 'scheda') return <SchedaView id={route.id} />
  if (route.mode === 'usa') return <UsaView id={route.id} />
  return <FormView id={route.mode === 'modifica' ? route.id : ''} />
}
