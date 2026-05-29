import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  BriefcaseBusiness,
  CalendarDays,
  CheckCircle2,
  Download,
  FileText,
  Mail,
  Play,
  RefreshCw,
  UploadCloud,
  UsersRound,
} from 'lucide-react'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import {
  emptyStudioTelematicoPage,
  emptyStudioTelematicoResult,
  formatImportNumber,
  getStudioTelematicoImportPage,
  previewStudioTelematicoPackage,
  runStudioTelematicoImport,
  type StudioTelematicoAnalysis,
  type StudioTelematicoImportPage,
  type StudioTelematicoImportResult,
  type StudioTelematicoPreview,
} from '../quickOrganizerImportData'
import './QuickOrganizerImportPage.css'

type WorkState = 'idle' | 'loading' | 'success' | 'error'
type WorkProgress = { active: boolean; label: string; detail: string; value: number }
const LARGE_PACKAGE_UPLOAD_LIMIT_BYTES = 2 * 1024 * 1024 * 1024

function ImportPanel({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <section className="iu-st-import-panel">
      <header>
        <h2>{title}</h2>
        {subtitle ? <p>{subtitle}</p> : null}
      </header>
      <div className="iu-st-import-panel__body">{children}</div>
    </section>
  )
}

function WorkProgressBar({ progress }: { progress: WorkProgress }) {
  if (!progress.active && !progress.label) return null
  return (
    <div className={`iu-st-import-progress ${progress.active ? 'is-active' : ''}`} aria-live="polite">
      <div>
        <strong>{progress.label || 'Controllo pacchetto'}</strong>
        <span>{progress.detail || 'Operazione in corso'}</span>
      </div>
      <progress value={progress.value} max={100} />
    </div>
  )
}

function completenessTone(analysis: StudioTelematicoAnalysis) {
  if (!analysis.ok) return 'neutral'
  return analysis.canImportComplete ? 'success' : 'warning'
}

function fileLabel(file: File | null) {
  if (!file) return 'Nessun pacchetto selezionato'
  const sizeMb = file.size / (1024 * 1024)
  return `${file.name} - ${sizeMb.toLocaleString('it-IT', { maximumFractionDigits: 1 })} MB`
}

function SummaryCards({ analysis }: { analysis: StudioTelematicoAnalysis }) {
  const summary = analysis.summary
  return (
    <section className="iu-st-import-kpis" aria-label="Riepilogo pacchetto">
      <KpiCard icon={BriefcaseBusiness} label="Pratiche" value={formatImportNumber(summary.matters)} note={`${formatImportNumber(summary.activeMatters)} attive`} tone="primary" />
      <KpiCard icon={UsersRound} label="Clienti e parti" value={formatImportNumber(summary.people)} note={`${formatImportNumber(summary.partyLinks)} collegamenti`} tone="info" />
      <KpiCard icon={FileText} label="ATTI" value={formatImportNumber(summary.documentFilesFound)} note={`${formatImportNumber(summary.documentFilesMissing)} documenti da integrare`} tone={summary.documentFilesMissing ? 'warning' : 'success'} />
      <KpiCard icon={Mail} label="EMAILS" value={formatImportNumber(summary.emailFilesFound)} note={`${formatImportNumber(summary.emailFilesMissing)} da integrare`} tone={summary.emailFilesMissing ? 'warning' : 'success'} />
      <KpiCard icon={CalendarDays} label="Agenda" value={formatImportNumber(summary.appointments)} note={`${formatImportNumber(summary.archivedMatters)} pratiche archiviate`} tone="neutral" />
    </section>
  )
}

function GuidedSteps({ data }: { data: StudioTelematicoImportPage }) {
  return (
    <section className="iu-st-import-steps" aria-label="Percorso guidato">
      {data.steps.map((step, index) => (
        <article key={step.id}>
          <span>{index + 1}</span>
          <strong>{step.label}</strong>
          <p>{step.description}</p>
        </article>
      ))}
    </section>
  )
}

function MissingFiles({ analysis }: { analysis: StudioTelematicoAnalysis }) {
  const missingDocuments = analysis.samples.missingDocuments
  const missingEmails = analysis.samples.missingEmails
  if (!missingDocuments.length && !missingEmails.length) return null
  return (
    <div className="iu-st-import-warning">
      <AlertTriangle size={18} />
      <div>
        <strong>Pacchetto da completare</strong>
        <p>Prima dell'import definitivo conviene recuperare la cartella ATTI con tutti i documenti del fascicolo e la cartella EMAILS dalla postazione del cliente.</p>
        <div className="iu-st-import-missing">
          {missingDocuments.length ? (
            <span>
              <b>ATTI:</b> {missingDocuments.join(', ')}
            </span>
          ) : null}
          {missingEmails.length ? (
            <span>
              <b>EMAILS:</b> {missingEmails.join(', ')}
            </span>
          ) : null}
        </div>
      </div>
    </div>
  )
}

function MatterPreview({ analysis }: { analysis: StudioTelematicoAnalysis }) {
  if (!analysis.samples.matters.length) return null
  return (
    <ImportPanel title="Prime pratiche rilevate" subtitle="Controllo rapido prima dell'acquisizione">
      <div className="iu-st-import-matters">
        {analysis.samples.matters.map((matter) => (
          <article key={`${matter.id}-${matter.title}`}>
            <div>
              <strong>{matter.title}</strong>
              <span>{matter.object || 'Oggetto da verificare dopo l’import'}</span>
            </div>
            <Badge tone={matter.status.toLowerCase().includes('archiv') ? 'neutral' : 'success'}>{matter.status}</Badge>
          </article>
        ))}
      </div>
    </ImportPanel>
  )
}

function ImportResult({ result }: { result: StudioTelematicoImportResult }) {
  if (!result.ok) return null
  const summary = result.summary
  return (
    <ImportPanel title="Import completato" subtitle="Riepilogo delle acquisizioni nello studio">
      <div className="iu-st-import-result">
        <div className="iu-st-import-ok">
          <CheckCircle2 size={18} />
          <span>Le pratiche sono state acquisite in IUSENTRA. Le pratiche già presenti sono state aggiornate senza duplicati.</span>
        </div>
        <section className="iu-st-import-result-grid" aria-label="Esito import">
          <span><strong>{formatImportNumber(summary.mattersCreated)}</strong> nuove pratiche</span>
          <span><strong>{formatImportNumber(summary.mattersUpdated)}</strong> pratiche aggiornate</span>
          <span><strong>{formatImportNumber(summary.clientsCreated)}</strong> clienti creati</span>
          <span><strong>{formatImportNumber(summary.subjectsCreated)}</strong> anagrafiche create</span>
          <span><strong>{formatImportNumber(summary.documentsImported)}</strong> documenti da ATTI</span>
          <span><strong>{formatImportNumber(summary.emailsImported)}</strong> email acquisite</span>
          <span><strong>{formatImportNumber(summary.activitiesImported)}</strong> appuntamenti registrati</span>
          <span><strong>{formatImportNumber(summary.duplicatesSkipped)}</strong> duplicati evitati</span>
        </section>
        {result.matters.length ? (
          <div className="iu-st-import-links">
            {result.matters.slice(0, 8).map((matter) => (
              <ButtonLink href={matter.href} tone="neutral" key={matter.id}>
                {matter.title}
              </ButtonLink>
            ))}
          </div>
        ) : null}
        {result.errors.length ? (
          <div className="iu-st-import-warning">
            <AlertTriangle size={18} />
            <div>
              <strong>Elementi da controllare</strong>
              {result.errors.slice(0, 5).map((error) => <p key={error}>{error}</p>)}
            </div>
          </div>
        ) : null}
      </div>
    </ImportPanel>
  )
}

export function QuickOrganizerImportPage() {
  const [data, setData] = useState<StudioTelematicoImportPage>(emptyStudioTelematicoPage)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [sourcePath, setSourcePath] = useState('')
  const [preview, setPreview] = useState<StudioTelematicoPreview | null>(null)
  const [previewState, setPreviewState] = useState<WorkState>('idle')
  const [importState, setImportState] = useState<WorkState>('idle')
  const [message, setMessage] = useState('')
  const [allowPartial, setAllowPartial] = useState(false)
  const [result, setResult] = useState<StudioTelematicoImportResult>(emptyStudioTelematicoResult)
  const [workProgress, setWorkProgress] = useState<WorkProgress>({ active: false, label: '', detail: '', value: 0 })

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    getStudioTelematicoImportPage(controller.signal)
      .then((payload) => {
        setData(payload)
        setError(payload.ok ? '' : 'Import pratiche non disponibile.')
      })
      .catch(() => setError('Import pratiche non disponibile.'))
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  const analysis = preview?.analysis || null
  const sourcePathValue = sourcePath.trim()
  const largePackageSelected = Boolean(file && file.size > LARGE_PACKAGE_UPLOAD_LIMIT_BYTES)
  const canRun = useMemo(() => {
    if (!data.permissions.canImport || !preview?.ok || importState === 'loading') return false
    return Boolean(preview.analysis.canImportComplete || allowPartial)
  }, [allowPartial, data.permissions.canImport, importState, preview])

  async function handlePreview() {
    if (!file && !sourcePathValue) {
      setMessage('Seleziona il pacchetto preparato sul PC del cliente oppure incolla il percorso del file.')
      return
    }
    if (largePackageSelected && !sourcePathValue && data.localPathEnabled) {
      setPreviewState('error')
      setWorkProgress({
        active: false,
        label: 'Pacchetto grande',
        detail: 'Per archivi molto grandi usa il percorso del file sul PC, così il controllo non ricarica 5 GB dal browser',
        value: 100,
      })
      setMessage('Il pacchetto è molto grande: incolla il percorso completo del file ZIP sul PC e poi avvia il controllo.')
      return
    }
    setPreviewState('loading')
    setImportState('idle')
    setResult(emptyStudioTelematicoResult)
    setMessage(sourcePathValue
      ? 'Controllo del pacchetto dal PC in corso. La pagina resta aggiornata durante la verifica.'
      : 'Caricamento e controllo del pacchetto in corso. La pagina resta aggiornata durante la verifica.')
    setWorkProgress({
      active: true,
      label: 'Controllo pacchetto',
      detail: sourcePathValue
        ? 'Leggo archivio, cartelle ATTI ed EMAILS e dati pratica senza ricopiare il file'
        : 'Carico archivio, cartelle ATTI ed EMAILS e dati pratica',
      value: 35,
    })
    const checked = await previewStudioTelematicoPackage(data.actions.preview, {
      file: sourcePathValue ? null : file,
      sourcePath: sourcePathValue,
    })
    setPreview(checked)
    setPreviewState(checked.ok ? 'success' : 'error')
    setAllowPartial(false)
    const previewWarnings = checked.analysis?.warnings ?? []
    const previewHasAvvisi = checked.ok && (!checked.analysis?.canImportComplete || previewWarnings.length > 0)
    const previewWarningMessage = previewWarnings[0]?.message || 'Controllo completato con avvisi. Verifica il riepilogo prima di importare.'
    setWorkProgress({
      active: false,
      label: checked.ok ? (previewHasAvvisi ? 'Controllo con avvisi' : 'Controllo completato') : 'Controllo non completato',
      detail: checked.ok ? (previewHasAvvisi ? previewWarningMessage : 'Riepilogo pronto per la verifica') : (checked.errore || 'Pacchetto da verificare'),
      value: checked.ok ? 100 : 100,
    })
    setMessage(checked.ok
      ? (previewHasAvvisi ? previewWarningMessage : 'Controllo completato. Verifica il riepilogo prima di importare.')
      : checked.errore || 'Controllo non completato. Verifica che il pacchetto sia lo ZIP preparato dalla postazione Studio Telematico completa.')
  }

  async function handleImport() {
    if (!preview?.importId) return
    setImportState('loading')
    setMessage('Importazione in corso. Creo o aggiorno pratiche, clienti, parti, ATTI ed EMAILS senza duplicare i dati già presenti.')
    setWorkProgress({
      active: true,
      label: 'Importazione pratiche',
      detail: 'Registro fascicoli, anagrafiche, documenti e messaggi',
      value: 55,
    })
    const imported = await runStudioTelematicoImport(data.actions.run, preview.importId, allowPartial)
    setResult(imported)
    setImportState(imported.ok ? 'success' : 'error')
    setWorkProgress({
      active: false,
      label: imported.ok ? 'Import completato' : 'Import non completato',
      detail: imported.ok ? 'Riepilogo acquisizioni pronto' : (imported.errore || 'Controlla gli avvisi'),
      value: 100,
    })
    setMessage(imported.ok ? 'Import completato.' : imported.errore || 'Import non completato.')
  }

  return (
    <Page
      title={data.page.title}
      subtitle={data.page.subtitle}
      actions={
        <>
          <ButtonLink href={data.actions.helper} tone="neutral">
            <Download size={15} />
            Prepara pacchetto
          </ButtonLink>
          <ButtonLink href={data.actions.fascicoli} tone="primary">
            Fascicoli
          </ButtonLink>
        </>
      }
    >
      {loading ? <LoadingState title="Caricamento import pratiche" message="Preparazione del percorso guidato." /> : null}
      {!loading && error ? <EmptyState title="Import pratiche non disponibile" message={error} /> : null}
      {!loading && !error && !data.permissions.canImport ? (
        <EmptyState title="Profilo non autorizzato" message={data.permissions.message || 'Serve un profilo autorizzato dello studio.'} />
      ) : null}
      {!loading && !error && data.permissions.canImport ? (
        <div className="iu-st-import-page">
          <section className="iu-st-import-banner" aria-label="Import guidato">
            <div>
              <strong>Percorso guidato di migrazione</strong>
              <span>Ogni pratica viene ricostruita con cliente, parti, documenti della cartella ATTI, EMAILS e agenda quando i file sono presenti.</span>
            </div>
            <Badge tone={analysis ? completenessTone(analysis) : 'info'}>
              {analysis ? (analysis.canImportComplete ? 'Pronto per importare' : 'Da completare') : 'In attesa pacchetto'}
            </Badge>
          </section>
          <GuidedSteps data={data} />
          <ImportPanel title="Pacchetto cliente" subtitle="Carica il file preparato dalla postazione Studio Telematico">
            <div className="iu-st-import-upload">
              <label className="iu-st-import-file">
                <UploadCloud size={22} />
                <span>{fileLabel(file)}</span>
                <input
                  type="file"
                  accept={data.acceptedFiles}
                  onChange={(event) => {
                    setFile(event.currentTarget.files?.[0] || null)
                    setSourcePath('')
                    setPreview(null)
                    setResult(emptyStudioTelematicoResult)
                    setWorkProgress({ active: false, label: '', detail: '', value: 0 })
                    setMessage('')
                  }}
                />
              </label>
              <Button type="button" onClick={handlePreview} disabled={(!file && !sourcePathValue) || previewState === 'loading'}>
                {previewState === 'loading' ? <RefreshCw size={15} /> : <UploadCloud size={15} />}
                {previewState === 'loading' ? 'Controllo in corso' : 'Controlla pacchetto'}
              </Button>
            </div>
            {data.localPathEnabled ? (
              <label className="iu-st-import-local-path">
                <span>Pacchetto grande sul PC</span>
                <input
                  type="text"
                  value={sourcePath}
                  placeholder={'C:\\Users\\utente\\Downloads\\QuickOrganizer.zip'}
                  onChange={(event) => {
                    setSourcePath(event.currentTarget.value)
                    setFile(null)
                    setPreview(null)
                    setResult(emptyStudioTelematicoResult)
                    setWorkProgress({ active: false, label: '', detail: '', value: 0 })
                    setMessage('')
                  }}
                />
                <small>Per archivi molto grandi incolla qui il percorso completo del file ZIP generato sul PC.</small>
              </label>
            ) : null}
            {largePackageSelected && data.localPathEnabled && !sourcePathValue ? (
              <div className="iu-st-import-message is-error">
                <AlertTriangle size={16} />
                <span>Archivio molto grande rilevato: usa il percorso del file sul PC per evitare attese e caricamenti non riusciti.</span>
              </div>
            ) : null}
            <div className="iu-st-import-notes">
              {data.notes.map((note) => <span key={note}>{note}</span>)}
            </div>
            <WorkProgressBar progress={workProgress} />
            {message ? (
              <div className={`iu-st-import-message is-${previewState === 'error' || importState === 'error' ? 'error' : 'info'}`}>
                {previewState === 'error' || importState === 'error' ? <AlertTriangle size={16} /> : <CheckCircle2 size={16} />}
                <span>{message}</span>
              </div>
            ) : null}
          </ImportPanel>
          {analysis ? (
            <>
              <SummaryCards analysis={analysis} />
              <MissingFiles analysis={analysis} />
              <ImportPanel
                title="Conferma import"
                subtitle={analysis.canImportComplete ? 'Il pacchetto risulta completo.' : 'Puoi attendere il pacchetto completo oppure acquisire solo i dati disponibili.'}
              >
                <div className="iu-st-import-confirm">
                  {!analysis.canImportComplete ? (
                    <label>
                      <input type="checkbox" checked={allowPartial} onChange={(event) => setAllowPartial(event.currentTarget.checked)} />
                      <span>Importa comunque le pratiche disponibili e segnala gli atti mancanti nei fascicoli.</span>
                    </label>
                  ) : (
                    <div className="iu-st-import-ok">
                      <CheckCircle2 size={18} />
                      <span>Cartelle ATTI ed EMAILS risultano presenti nel pacchetto controllato.</span>
                    </div>
                  )}
                  <Button type="button" onClick={handleImport} disabled={!canRun}>
                    {importState === 'loading' ? <RefreshCw size={15} /> : <Play size={15} />}
                    {importState === 'loading' ? 'Import in corso' : 'Importa pratiche'}
                  </Button>
                </div>
              </ImportPanel>
              <MatterPreview analysis={analysis} />
            </>
          ) : null}
          <ImportResult result={result} />
        </div>
      ) : null}
    </Page>
  )
}

export default QuickOrganizerImportPage
