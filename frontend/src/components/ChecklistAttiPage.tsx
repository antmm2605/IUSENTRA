import { useEffect, useState } from 'react'
import { ArrowLeft, CheckCircle2, CircleDashed, FileText, FolderOpen, ListChecks, SkipForward, Upload } from 'lucide-react'
import {
  checklistRoute,
  createWizardIndex,
  getChecklistCatalog,
  getChecklistDetail,
  getWizard,
  skipWizardStep,
  uploadWizardDocument,
  type ChecklistCatalog,
  type ChecklistCheck,
  type ChecklistDetail,
  type ChecklistRoute,
  type WizardData,
  type WizardStep,
} from '../checklistAttiData'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import './ChecklistAttiPage.css'

function Checks({ items }: { items: ChecklistCheck[] }) {
  if (!items.length) return null
  return (
    <ul className="iu-chk-checks">
      {items.map((item, index) => (
        <li key={`${item.text}-${index}`} className={item.critical ? 'is-critical' : ''}>
          <span>{item.text}</span>
          {item.critical ? <Badge tone="danger">bloccante</Badge> : null}
          {item.note ? <small>{item.note}</small> : null}
        </li>
      ))}
    </ul>
  )
}

function CatalogView() {
  const initial = new URLSearchParams(window.location.search)
  const [area, setArea] = useState(initial.get('area') || '')
  const [q, setQ] = useState(initial.get('q') || '')
  const [data, setData] = useState<ChecklistCatalog | null>(null)

  useEffect(() => {
    let active = true
    const timer = window.setTimeout(() => {
      getChecklistCatalog(area, q.trim()).then((result) => { if (active) setData(result) })
      const params = new URLSearchParams()
      if (area) params.set('area', area)
      if (q.trim()) params.set('q', q.trim())
      window.history.replaceState(null, '', `/checklist${params.toString() ? `?${params}` : ''}`)
    }, 250)
    return () => { active = false; window.clearTimeout(timer) }
  }, [area, q])

  return (
    <Page title="Checklist degli atti" subtitle="Per ogni atto: i documenti da allegare, i controlli prima del deposito e il canale.">
      <div className="iu-chk-filters">
        <label>
          <span>Area</span>
          <select value={area} onChange={(event) => { const value = event.currentTarget.value; setArea(value) }}>
            <option value="">Tutte le aree</option>
            {(data?.areas || []).map((item) => <option key={item.name} value={item.name}>{item.name} ({item.count})</option>)}
          </select>
        </label>
        <label>
          <span>Cerca</span>
          <input type="search" value={q} placeholder="Atto, materia, canale…" onChange={(event) => { const value = event.currentTarget.value; setQ(value) }} />
        </label>
      </div>
      {!data ? <LoadingState title="Caricamento del catalogo" /> : null}
      {data && data.ok ? (
        <>
          <p className="iu-chk-totals">
            {data.totals.templates} atti in {data.totals.areas} aree · {data.totals.requiredDocuments} documenti obbligatori · {data.totals.criticalChecks} controlli bloccanti
          </p>
          {data.catalog.length ? data.catalog.map((areaItem) => (
            <Panel key={areaItem.name} title={areaItem.name} subtitle={`${areaItem.templates} atti`}>
              {areaItem.branches.map((branch) => (
                <section key={branch.name} className="iu-chk-branch">
                  <h3>{branch.name}</h3>
                  {branch.subbranches.map((sub) => (
                    <div key={sub.name} className="iu-chk-sub">
                      {sub.name && sub.name !== branch.name ? <h4>{sub.name}</h4> : null}
                      <div className="iu-chk-grid">
                        {sub.templates.map((template) => (
                          <a key={template.id} href={template.href} className="iu-chk-card">
                            <strong>{template.name}</strong>
                            <small>{template.description}</small>
                            <span className="iu-chk-card__meta">
                              <Badge tone="info">{template.channel.label || template.channel.code}</Badge>
                              <span>{template.requiredDocuments} documenti</span>
                              {template.criticalChecks ? <span>{template.criticalChecks} bloccanti</span> : null}
                            </span>
                          </a>
                        ))}
                      </div>
                    </div>
                  ))}
                </section>
              ))}
            </Panel>
          )) : <EmptyState title="Nessun atto con questi filtri" message="Cambia area o testo di ricerca." />}
        </>
      ) : null}
    </Page>
  )
}

function DetailView({ templateId }: { templateId: string }) {
  const [state, setState] = useState<{ ok: boolean; message: string; item: ChecklistDetail | null } | null>(null)
  useEffect(() => {
    let active = true
    getChecklistDetail(templateId, window.location.search).then((result) => { if (active) setState(result) })
    return () => { active = false }
  }, [templateId])
  if (!state) return <LoadingState title="Caricamento della checklist" />
  if (!state.ok || !state.item) return <EmptyState title="Checklist non trovata" message={state.message} action={<ButtonLink href="/checklist" tone="neutral">Catalogo</ButtonLink>} />
  const item = state.item
  return (
    <Page
      title={item.name}
      subtitle={[item.area, item.branch, item.subbranch].filter(Boolean).join(' · ')}
      actions={(
        <>
          <ButtonLink href="/checklist" tone="neutral"><ArrowLeft size={15} aria-hidden="true" /> Catalogo</ButtonLink>
          {item.matter?.wizardHref ? <ButtonLink href={item.matter.wizardHref} tone="primary"><ListChecks size={15} aria-hidden="true" /> Raccogli i documenti nel fascicolo</ButtonLink> : null}
        </>
      )}
    >
      <div className="iu-chk-layout">
        <div className="iu-chk-stack">
          <Panel title="Documenti da allegare" subtitle={`${item.documents.filter((d) => d.required).length} obbligatori su ${item.documents.length}`}>
            <ol className="iu-chk-docs">
              {item.documents.map((doc) => (
                <li key={doc.number}>
                  <strong>{doc.description}</strong>
                  <code>{doc.fileName}</code>
                  <Badge tone={doc.required ? 'warning' : 'neutral'}>{doc.required ? 'obbligatorio' : 'facoltativo'}</Badge>
                  {doc.note ? <small>{doc.note}</small> : null}
                </li>
              ))}
            </ol>
          </Panel>
          <Panel title="Controlli prima del deposito"><Checks items={item.checks} /></Panel>
        </div>
        <div className="iu-chk-stack">
          <Panel title="Canale di deposito">
            <p><strong>{item.channel.label || item.channel.code}</strong></p>
            {item.channel.note ? <p className="iu-chk-note">{item.channel.note}</p> : null}
          </Panel>
          <Panel title="Cartella del fascicolo">
            <p><FolderOpen size={15} aria-hidden="true" /> <code>{item.folderName}</code></p>
            <small className="iu-chk-note">Parte: {item.context.party || 'controparte'} · RG: {item.context.rg || 'da indicare'}</small>
          </Panel>
          {item.generalNotes ? <Panel title="Note"><p className="iu-chk-note">{item.generalNotes}</p></Panel> : null}
          {item.matter ? <Panel title="Fascicolo"><a href={`/fascicoli/${encodeURIComponent(item.matter.id)}`}>{item.matter.title || item.matter.id}</a></Panel> : null}
        </div>
      </div>
    </Page>
  )
}

function statusBadge(step: WizardStep) {
  if (step.status === 'done') return <Badge tone="success">caricato</Badge>
  if (step.status === 'skipped') return <Badge tone="neutral">non allegato</Badge>
  return <Badge tone={step.required ? 'warning' : 'neutral'}>{step.required ? 'da caricare' : 'facoltativo'}</Badge>
}

function StepsList({ data, current }: { data: WizardData; current?: number }) {
  const base = `/fascicoli/${encodeURIComponent(data.matter.id)}/wizard/${encodeURIComponent(data.template.id)}`
  return (
    <ol className="iu-chk-steps">
      {data.steps.map((step) => (
        <li key={step.number} className={step.number === current ? 'is-current' : ''}>
          {step.status === 'done' ? <CheckCircle2 size={16} aria-hidden="true" /> : <CircleDashed size={16} aria-hidden="true" />}
          <a href={`${base}/step/${step.number}`}>{step.number}. {step.description}</a>
          {statusBadge(step)}
        </li>
      ))}
    </ol>
  )
}

function StepView({ data, step, onReload }: { data: WizardData; step: WizardStep; onReload: (next?: string) => Promise<void> }) {
  const [file, setFile] = useState<File | null>(null)
  const [documentType, setDocumentType] = useState('')
  const [documentDate, setDocumentDate] = useState('')
  const [signed, setSigned] = useState(false)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const base = `/fascicoli/${encodeURIComponent(data.matter.id)}/wizard/${encodeURIComponent(data.template.id)}`
  const next = data.steps.find((item) => item.number > step.number)
  const nextHref = next ? `${base}/step/${next.number}` : `${base}/completa`

  async function upload() {
    if (!file) { setMessage({ ok: false, text: 'Scegli il file da caricare.' }); return }
    setBusy(true)
    const result = await uploadWizardDocument(data.matter.uploadAction, step, file, { documentType, documentDate, signed, note })
    setBusy(false)
    setMessage({ ok: result.ok, text: result.message || (result.ok ? 'Documento caricato.' : 'Documento non caricato.') })
    if (result.ok) await onReload(nextHref)
  }

  async function skip() {
    setBusy(true)
    const result = await skipWizardStep(data.skipAction, step.number)
    setBusy(false)
    setMessage({ ok: result.ok, text: result.message })
    if (result.ok) await onReload(nextHref)
  }

  return (
    <Panel title={`Passo ${step.number} di ${data.steps.length}: ${step.description}`} subtitle={step.required ? 'Documento obbligatorio' : 'Documento facoltativo'}>
      <p className="iu-chk-note">Nome nel fascicolo: <code>{step.uploadName}</code>{step.note ? ` · ${step.note}` : ''}</p>
      {step.document ? (
        <p className="iu-chk-existing">
          <FileText size={15} aria-hidden="true" /> Già nel fascicolo: <strong>{step.document.name}</strong>
          {step.document.viewHref ? <a href={step.document.viewHref} target="_blank" rel="noopener noreferrer">Apri</a> : null}
        </p>
      ) : null}
      <div className="iu-chk-form">
        <label className="iu-chk-form__wide">
          <span>{step.document ? 'Sostituisci o aggiungi un file' : 'File da caricare'}</span>
          <input type="file" onChange={(event) => { const picked = event.currentTarget.files?.[0] || null; setFile(picked) }} />
        </label>
        <label>
          <span>Tipo di documento</span>
          <select value={documentType} onChange={(event) => { const value = event.currentTarget.value; setDocumentType(value) }}>
            <option value="">Riconoscimento automatico</option>
            {data.documentTypes.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}
          </select>
        </label>
        <label>
          <span>Data del documento</span>
          <input type="date" value={documentDate} onChange={(event) => { const value = event.currentTarget.value; setDocumentDate(value) }} />
        </label>
        <label className="iu-chk-check">
          <input type="checkbox" checked={signed} onChange={(event) => { const value = event.currentTarget.checked; setSigned(value) }} />
          <span>Il file è già firmato digitalmente</span>
        </label>
        <label className="iu-chk-form__wide">
          <span>Nota (facoltativa)</span>
          <input type="text" value={note} maxLength={300} onChange={(event) => { const value = event.currentTarget.value; setNote(value) }} />
        </label>
      </div>
      <div className="iu-chk-actions">
        <Button type="button" tone="primary" disabled={busy} onClick={() => void upload()}><Upload size={15} aria-hidden="true" /> {busy ? 'Caricamento…' : 'Carica e continua'}</Button>
        {!step.required && step.status === 'pending' ? <Button type="button" tone="neutral" disabled={busy} onClick={() => void skip()}><SkipForward size={15} aria-hidden="true" /> Non allegare</Button> : null}
        <ButtonLink href={nextHref} tone="neutral">{next ? 'Passo successivo' : 'Riepilogo'}</ButtonLink>
      </div>
      {message ? <p className={message.ok ? 'iu-chk-msg' : 'iu-chk-msg is-error'} role="status">{message.text}</p> : null}
    </Panel>
  )
}

function CompleteView({ data, onReload }: { data: WizardData; onReload: (next?: string) => Promise<void> }) {
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  async function index() {
    setBusy(true)
    const result = await createWizardIndex(data.indexAction)
    setBusy(false)
    setMessage({ ok: result.ok, text: result.message })
    if (result.ok) await onReload()
  }
  return (
    <>
      <Panel title="Riepilogo dei documenti" subtitle={data.complete ? 'Tutti i documenti obbligatori sono nel fascicolo.' : `Mancano ${data.missingRequired} documenti obbligatori.`}>
        <ol className="iu-chk-docs">
          {data.steps.map((step) => (
            <li key={step.number}>
              <strong>{step.number}. {step.description}</strong>
              {step.document ? (
                <span className="iu-chk-existing">
                  {step.document.name}
                  {step.document.viewHref ? <a href={step.document.viewHref} target="_blank" rel="noopener noreferrer">Apri</a> : null}
                  {step.document.downloadHref ? <a href={step.document.downloadHref}>Scarica</a> : null}
                </span>
              ) : <code>{step.fileName}</code>}
              {statusBadge(step)}
            </li>
          ))}
        </ol>
        <div className="iu-chk-actions">
          <Button type="button" tone="neutral" disabled={busy} onClick={() => void index()}><FileText size={15} aria-hidden="true" /> {busy ? 'Preparazione…' : 'Aggiungi l\'indice dei documenti al fascicolo'}</Button>
          {data.complete && data.matter.depositHref ? <ButtonLink href={data.matter.depositHref} tone="primary">{data.matter.depositLabel}</ButtonLink> : null}
        </div>
        {message ? <p className={message.ok ? 'iu-chk-msg' : 'iu-chk-msg is-error'} role="status">{message.text}</p> : null}
      </Panel>
      <Panel title="Controlli prima del deposito"><Checks items={data.template.checks} /></Panel>
    </>
  )
}

function WizardView({ route }: { route: Extract<ChecklistRoute, { matterId: string }> }) {
  const [data, setData] = useState<WizardData | null>(null)

  async function reload(nextHref?: string) {
    if (nextHref) { window.location.assign(nextHref); return }
    setData(await getWizard(route.matterId, route.templateId))
  }

  useEffect(() => {
    let active = true
    getWizard(route.matterId, route.templateId).then((result) => {
      if (!active) return
      if (route.mode === 'avvia' && result.ok) {
        const base = `/fascicoli/${encodeURIComponent(route.matterId)}/wizard/${encodeURIComponent(route.templateId)}`
        window.location.replace(result.nextStep ? `${base}/step/${result.nextStep}` : `${base}/completa`)
        return
      }
      setData(result)
    })
    return () => { active = false }
  }, [route.matterId, route.templateId, route.mode])

  if (!data) return <LoadingState title="Caricamento del percorso guidato" />
  if (!data.ok) return <EmptyState title="Percorso non disponibile" message={data.message} action={<ButtonLink href="/checklist" tone="neutral">Catalogo</ButtonLink>} />
  const step = route.mode === 'passo' ? data.steps.find((item) => item.number === route.step) : undefined
  return (
    <Page
      title={data.template.name}
      subtitle={[data.matter.title, data.matter.rg && `RG ${data.matter.rg}`, data.matter.office].filter(Boolean).join(' · ')}
      actions={(
        <>
          <ButtonLink href={data.matter.href} tone="neutral"><ArrowLeft size={15} aria-hidden="true" /> Fascicolo</ButtonLink>
          <ButtonLink href={`/checklist/${encodeURIComponent(data.template.id)}?id_fasc=${encodeURIComponent(data.matter.id)}`} tone="neutral">Checklist dell'atto</ButtonLink>
        </>
      )}
    >
      <div className="iu-chk-layout">
        <div className="iu-chk-stack">
          {route.mode === 'passo' && step ? <StepView data={data} step={step} onReload={reload} /> : null}
          {route.mode === 'passo' && !step ? <EmptyState title="Passo non trovato" message="Il modello non ha questo passo." /> : null}
          {route.mode === 'completa' ? <CompleteView data={data} onReload={reload} /> : null}
        </div>
        <div className="iu-chk-stack">
          <Panel title="Passi" subtitle={`Cartella: ${data.folderName}`}><StepsList data={data} current={step?.number} /></Panel>
          <Panel title="Canale di deposito"><p>{data.template.channel.label}</p>{data.template.channel.note ? <p className="iu-chk-note">{data.template.channel.note}</p> : null}</Panel>
        </div>
      </div>
    </Page>
  )
}

export function ChecklistAttiPage() {
  const route = checklistRoute(window.location.pathname)
  if (!route) return <EmptyState title="Pagina non riconosciuta" message="L'indirizzo non corrisponde alla checklist degli atti." />
  if (route.mode === 'catalogo') return <CatalogView />
  if (route.mode === 'scheda') return <DetailView templateId={route.templateId} />
  return <WizardView route={route} />
}
