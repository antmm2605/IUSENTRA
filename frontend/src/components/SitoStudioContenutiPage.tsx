import { useEffect, useState } from 'react'
import { ArrowLeft, Pencil, Plus, Trash2 } from 'lucide-react'
import {
  creaBozzaArticolo,
  eliminaSito,
  getElencoSito,
  getImpostazioniSito,
  salvaImpostazioniSito,
  salvaSito,
  sitoContenutiRoute,
  type CampoSito,
  type ElencoSito,
  type ImpostazioniSito,
  type RaccoltaSito,
  type SitoContenutiRoute,
  type ValoriSito,
} from '../sitoStudioContenutiData'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import './SitoStudioContenutiPage.css'

function Campo({ campo, value, error, onChange }: { campo: CampoSito; value: string | boolean; error: string; onChange: (value: string | boolean) => void }) {
  const id = `sito-${campo.name}`
  if (campo.kind === 'checkbox') {
    return (
      <label className="iu-sitoc-field iu-sitoc-field--check" htmlFor={id}>
        <input id={id} type="checkbox" checked={value === true} onChange={(event) => { const checked = event.currentTarget.checked; onChange(checked) }} />
        <span>{campo.label}</span>
      </label>
    )
  }
  const stringValue = typeof value === 'string' ? value : ''
  const common = { id, required: campo.required, 'aria-invalid': error ? true : undefined }
  let control: React.ReactNode
  if (campo.kind === 'textarea') {
    control = <textarea {...common} rows={4} maxLength={campo.maxLength || undefined} value={stringValue} onChange={(event) => { const next = event.currentTarget.value; onChange(next) }} />
  } else if (campo.kind === 'office' || campo.kind === 'weekday') {
    control = (
      <select {...common} value={stringValue} onChange={(event) => { const next = event.currentTarget.value; onChange(next) }}>
        {campo.kind === 'office' ? <option value="">Scegli la sede</option> : null}
        {campo.options.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
      </select>
    )
  } else {
    const type = campo.kind === 'number' ? 'number' : campo.kind === 'email' ? 'email' : campo.kind === 'url' ? 'url' : campo.kind === 'time' ? 'time' : campo.kind === 'color' ? 'color' : 'text'
    control = <input {...common} type={type} maxLength={campo.maxLength || undefined} value={stringValue} onChange={(event) => { const next = event.currentTarget.value; onChange(next) }} />
  }
  return (
    <label className={campo.kind === 'textarea' ? 'iu-sitoc-field iu-sitoc-field--wide' : 'iu-sitoc-field'} htmlFor={id}>
      <span>{campo.label}{campo.required ? ' *' : ''}</span>
      {control}
      {campo.help ? <small>{campo.help}</small> : null}
      {error ? <small className="is-error">{error}</small> : null}
    </label>
  )
}

function Impostazioni() {
  const [data, setData] = useState<ImpostazioniSito | null>(null)
  const [values, setValues] = useState<ValoriSito>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let active = true
    getImpostazioniSito().then((result) => { if (active) { setData(result); setValues(result.values) } })
    return () => { active = false }
  }, [])

  if (!data) return <LoadingState title="Caricamento delle impostazioni del sito" />
  if (!data.ok) return <EmptyState title="Impostazioni non disponibili" message={data.message || 'Serve il permesso di configurazione dello studio.'} />

  async function save() {
    setBusy(true)
    const result = await salvaImpostazioniSito(values)
    setBusy(false)
    setErrors(result.errors)
    setMessage({ ok: result.ok, text: result.message })
    if (result.ok) setValues(result.values)
  }

  return (
    <Page
      title="Sito dello studio: impostazioni"
      subtitle="Dati dello studio, aspetto, pubblicazione, privacy e cookie del sito pubblico."
      actions={(
        <>
          <ButtonLink href="/sito-studio" tone="neutral"><ArrowLeft size={15} aria-hidden="true" /> Cruscotto del sito</ButtonLink>
          {data.publicUrl ? <ButtonLink href={data.publicUrl} tone="success" target="_blank" rel="noopener noreferrer">Apri il sito pubblico</ButtonLink> : null}
        </>
      )}
    >
      <Panel title="Impostazioni">
        <form className="iu-sitoc-form" onSubmit={(event) => { event.preventDefault(); void save() }}>
          {data.fields.map((campo) => (
            <Campo key={campo.name} campo={campo} value={values[campo.name] ?? ''} error={errors[campo.name] || ''} onChange={(value) => setValues((prev) => ({ ...prev, [campo.name]: value }))} />
          ))}
          <div className="iu-sitoc-actions">
            <Button type="submit" tone="primary" disabled={busy}>{busy ? 'Salvataggio…' : 'Salva le impostazioni'}</Button>
          </div>
          {message ? <p className={message.ok ? 'iu-sitoc-msg' : 'iu-sitoc-msg is-error'} role="status">{message.text}</p> : null}
        </form>
      </Panel>
    </Page>
  )
}

function Modulo({ data, route }: { data: ElencoSito; route: Extract<SitoContenutiRoute, { collection: RaccoltaSito }> }) {
  const current = route.mode === 'modifica' ? data.items.find((item) => item.id === route.id) : undefined
  const [values, setValues] = useState<ValoriSito>(current ? current.values : data.defaults)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const back = `/sito-studio/${route.collection}`

  if (route.mode === 'modifica' && !current) return <EmptyState title="Elemento non trovato" message="Potrebbe essere stato eliminato." action={<ButtonLink href={back} tone="neutral">Torna all'elenco</ButtonLink>} />

  async function save() {
    setBusy(true)
    const result = await salvaSito(route.collection, route.mode === 'modifica' ? route.id : '', values)
    setBusy(false)
    setErrors(result.errors)
    setMessage({ ok: result.ok, text: result.message })
    if (result.ok) window.location.assign(result.redirectHref || back)
  }

  async function remove() {
    if (!current || !window.confirm(`Eliminare «${current.title}»?`)) return
    setBusy(true)
    const result = await eliminaSito(route.collection, current.id)
    setBusy(false)
    setMessage({ ok: result.ok, text: result.message })
    if (result.ok) window.location.assign(result.redirectHref || back)
  }

  return (
    <Panel title={current ? `Modifica: ${current.title}` : `Nuovo ${data.collection.singular}`}>
      <form className="iu-sitoc-form" onSubmit={(event) => { event.preventDefault(); void save() }}>
        {data.fields.map((campo) => (
          <Campo key={campo.name} campo={campo} value={values[campo.name] ?? ''} error={errors[campo.name] || ''} onChange={(value) => setValues((prev) => ({ ...prev, [campo.name]: value }))} />
        ))}
        <div className="iu-sitoc-actions">
          <Button type="submit" tone="primary" disabled={busy}>{busy ? 'Salvataggio…' : 'Salva'}</Button>
          <ButtonLink href={back} tone="neutral">Annulla</ButtonLink>
          {current ? <Button type="button" tone="danger" disabled={busy} onClick={() => void remove()}><Trash2 size={15} aria-hidden="true" /> Elimina</Button> : null}
        </div>
        {message ? <p className={message.ok ? 'iu-sitoc-msg' : 'iu-sitoc-msg is-error'} role="status">{message.text}</p> : null}
      </form>
    </Panel>
  )
}

function NuovoArticolo() {
  const [title, setTitle] = useState('')
  const [author, setAuthor] = useState('')
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const [busy, setBusy] = useState(false)
  async function create() {
    setBusy(true)
    const result = await creaBozzaArticolo(title, author)
    setBusy(false)
    setMessage({ ok: result.ok, text: result.message })
    if (result.ok && result.redirectHref) window.location.assign(result.redirectHref)
  }
  return (
    <Page title="Nuovo articolo del sito" subtitle="Crea la bozza: testo, immagine e pubblicazione si completano nell'editor dell'articolo." actions={<ButtonLink href="/sito-studio" tone="neutral"><ArrowLeft size={15} aria-hidden="true" /> Cruscotto del sito</ButtonLink>}>
      <Panel title="Bozza">
        <form className="iu-sitoc-form" onSubmit={(event) => { event.preventDefault(); void create() }}>
          <label className="iu-sitoc-field iu-sitoc-field--wide" htmlFor="sito-articolo-titolo">
            <span>Titolo *</span>
            <input id="sito-articolo-titolo" required maxLength={200} value={title} onChange={(event) => { const value = event.currentTarget.value; setTitle(value) }} />
          </label>
          <label className="iu-sitoc-field" htmlFor="sito-articolo-autore">
            <span>Autore</span>
            <input id="sito-articolo-autore" maxLength={160} value={author} onChange={(event) => { const value = event.currentTarget.value; setAuthor(value) }} />
          </label>
          <div className="iu-sitoc-actions">
            <Button type="submit" tone="primary" disabled={busy || !title.trim()}>{busy ? 'Creazione…' : 'Crea la bozza e apri l\'editor'}</Button>
            <ButtonLink href="/sito-studio/redazione-ai" tone="neutral">Scrivi con la Redazione AI</ButtonLink>
          </div>
          {message ? <p className={message.ok ? 'iu-sitoc-msg' : 'iu-sitoc-msg is-error'} role="status">{message.text}</p> : null}
        </form>
      </Panel>
    </Page>
  )
}

export function SitoStudioContenutiPage() {
  const route = sitoContenutiRoute(window.location.pathname)
  if (route?.mode === 'impostazioni') return <Impostazioni />
  if (route?.mode === 'nuovo-articolo') return <NuovoArticolo />
  if (!route) return <EmptyState title="Sezione non riconosciuta" message="L'indirizzo non corrisponde a una sezione del sito." />
  return <Raccolte route={route} />
}

function Raccolte({ route }: { route: Extract<SitoContenutiRoute, { collection: RaccoltaSito }> }) {
  const [data, setData] = useState<ElencoSito | null>(null)

  useEffect(() => {
    let active = true
    getElencoSito(route.collection).then((result) => { if (active) setData(result) })
    return () => { active = false }
  }, [route.collection])

  if (!data) return <LoadingState title="Caricamento dei contenuti del sito" />
  if (!data.ok) return <EmptyState title="Contenuti non disponibili" message={data.message || 'Serve il permesso di configurazione dello studio.'} />
  return (
    <Page
      title={`Sito dello studio: ${data.collection.label}`}
      subtitle="I contenuti compaiono nelle pagine pubbliche del sito dello studio."
      actions={<ButtonLink href="/sito-studio" tone="neutral"><ArrowLeft size={15} aria-hidden="true" /> Cruscotto del sito</ButtonLink>}
    >
      <nav className="iu-sitoc-tabs" aria-label="Sezioni dei contenuti del sito">
        {data.collections.map((item) => (
          <a key={item.key} href={item.href} aria-current={item.key === route.collection ? 'page' : undefined}>{item.label}</a>
        ))}
      </nav>
      {data.needsOffice ? <p className="iu-sitoc-msg is-error" role="status">Aggiungi prima una sede: gli orari prenotabili appartengono a una sede.</p> : null}
      <div className="iu-sitoc-layout">
        <Panel
          title={data.collection.label}
          subtitle={`${data.items.length} ${data.items.length === 1 ? 'elemento' : 'elementi'}`}
          actions={<ButtonLink href={`/sito-studio/${route.collection}/nuovo`} tone="primary"><Plus size={15} aria-hidden="true" /> Aggiungi</ButtonLink>}
        >
          {data.items.length ? (
            <ul className="iu-sitoc-list">
              {data.items.map((item) => (
                <li key={item.id} className={item.id === route.id ? 'is-current' : ''}>
                  <strong>{item.title}</strong>
                  <Badge tone={item.visible ? 'success' : 'neutral'}>{item.visible ? (route.collection === 'regole-agenda' ? 'attivo' : 'visibile') : (route.collection === 'regole-agenda' ? 'sospeso' : 'nascosto')}</Badge>
                  <ButtonLink href={item.editHref} tone="neutral"><Pencil size={14} aria-hidden="true" /> Modifica</ButtonLink>
                </li>
              ))}
            </ul>
          ) : <EmptyState title="Nessun elemento" message="Aggiungi il primo elemento di questa sezione." />}
        </Panel>
        {route.mode !== 'elenco' ? <Modulo key={`${route.mode}-${route.id}`} data={data} route={route} /> : null}
      </div>
    </Page>
  )
}
