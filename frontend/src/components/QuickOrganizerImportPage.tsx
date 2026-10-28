import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
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
  getStudioTelematicoAutoPrepareStatus,
  getStudioTelematicoImportPage,
  getStudioTelematicoImportProgress,
  getStudioTelematicoStoredPreview,
  previewStudioTelematicoPackage,
  runStudioTelematicoImport,
  startStudioTelematicoAutoPrepare,
  type StudioTelematicoAnalysis,
  type ImportSelection,
  type StudioTelematicoImportPage,
  type StudioTelematicoImportResult,
  type StudioTelematicoPrepareStatus,
  type StudioTelematicoPreview,
} from '../quickOrganizerImportData'
import './QuickOrganizerImportPage.css'
import { useBusyActivity } from '../ui/useBusyActivity'

type WorkState = 'idle' | 'loading' | 'success' | 'error'
type WorkProgress = { active: boolean; label: string; detail: string; value: number }

function importUiText(value: string): string {
  return value
    .replace(/QuickOrganizer\.zip/gi, 'PacchettoPratiche.zip')
    .replace(/PreparaPacchetto(?:StudioTelematico|Pratiche)\.exe/gi, 'preparatore pacchetto')
    .replace(/Studio Telematico|QuickOrganizer/gi, 'gestionale precedente')
    .replace(/\bATTI\b/g, 'Documenti')
    .replace(/\bEMAILS\b/g, 'Comunicazioni')
}

function ImportPanel({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <section className="iu-st-import-panel">
      <header>
        <h2>{importUiText(title)}</h2>
        {subtitle ? <p>{importUiText(subtitle)}</p> : null}
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
        <strong>{importUiText(progress.label || 'Controllo pacchetto')}</strong>
        <span>{importUiText(progress.detail || 'Operazione in corso')}</span>
      </div>
      <progress value={progress.value} max={100} />
    </div>
  )
}

function autoPrepareActive(status: string) {
  return ['pending', 'preparing', 'packing', 'uploading', 'checking'].includes(status)
}

function autoPrepareLabel(status: string) {
  switch (status) {
    case 'preparing':
      return 'Preparazione pacchetto'
    case 'packing':
      return 'Creazione pacchetto'
    case 'uploading':
      return 'Caricamento automatico'
    case 'checking':
      return 'Controllo pacchetto'
    case 'ready':
      return 'Pacchetto pronto'
    case 'error':
      return 'Preparazione interrotta'
    default:
      return 'Avvio preparazione'
  }
}

function completenessTone(analysis: StudioTelematicoAnalysis) {
  if (!analysis.ok) return 'neutral'
  return analysis.canImportComplete ? 'success' : 'warning'
}

function fileLabel(file: File | null) {
  if (!file) return 'Nessun pacchetto selezionato'
  const displayName = importUiText(file.name)
  const sizeMb = file.size / (1024 * 1024)
  if (sizeMb >= 1024) {
    const sizeGb = sizeMb / 1024
    return `${displayName} - ${sizeGb.toLocaleString('it-IT', { maximumFractionDigits: 2 })} GB`
  }
  return `${displayName} - ${sizeMb.toLocaleString('it-IT', { maximumFractionDigits: 1 })} MB`
}

function SummaryCards({ analysis }: { analysis: StudioTelematicoAnalysis }) {
  const summary = analysis.summary
  return (
    <section className="iu-st-import-kpis" aria-label="Riepilogo pacchetto">
      <KpiCard icon={BriefcaseBusiness} label="Pratiche" value={formatImportNumber(summary.matters)} note={`${formatImportNumber(summary.activeMatters)} attive`} tone="primary" />
      <KpiCard icon={UsersRound} label="Clienti e parti" value={formatImportNumber(summary.people)} note={`${formatImportNumber(summary.partyLinks)} collegamenti`} tone="info" />
      <KpiCard icon={FileText} label="Documenti" value={formatImportNumber(summary.documentFilesFound)} note={`${formatImportNumber(summary.documentFilesMissing)} documenti da integrare`} tone={summary.documentFilesMissing ? 'warning' : 'success'} />
      <KpiCard icon={Mail} label="Comunicazioni" value={formatImportNumber(summary.emailFilesFound)} note={`${formatImportNumber(summary.emailFilesMissing)} da integrare`} tone={summary.emailFilesMissing ? 'warning' : 'success'} />
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
          <strong>{importUiText(step.label)}</strong>
          <p>{importUiText(step.description)}</p>
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
        <p>Prima dell'import definitivo conviene recuperare tutti i documenti del fascicolo e le comunicazioni dalla postazione autorizzata.</p>
        <div className="iu-st-import-missing">
          {missingDocuments.length ? (
            <span>
              <b>Documenti:</b> {missingDocuments.map(importUiText).join(', ')}
            </span>
          ) : null}
          {missingEmails.length ? (
            <span>
              <b>Comunicazioni:</b> {missingEmails.map(importUiText).join(', ')}
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
  const complete = result.complete === true && result.errors.length === 0
  return (
    <ImportPanel title={complete ? 'Selezione acquisita e verificata' : 'Acquisizione da verificare'} subtitle="Riepilogo delle acquisizioni nello studio">
      <div className="iu-st-import-result">
        <div className={complete ? 'iu-st-import-ok' : 'iu-st-import-warning'}>
          {complete ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
          <span>{complete ? 'I documenti collegati sono stati acquisiti e verificati.' : 'I dati disponibili sono stati acquisiti. Gli elementi indicati sotto richiedono ancora verifica; conserva il pacchetto originale.'}</span>
        </div>
        <section className="iu-st-import-result-grid" aria-label="Esito import">
          <span><strong>{formatImportNumber(summary.mattersCreated)}</strong> nuove pratiche</span>
          <span><strong>{formatImportNumber(summary.mattersUpdated)}</strong> pratiche aggiornate</span>
          <span><strong>{formatImportNumber(summary.mattersUnchanged)}</strong> pratiche già presenti e invariate</span>
          <span><strong>{formatImportNumber(summary.clientsCreated)}</strong> clienti creati</span>
          <span><strong>{formatImportNumber(summary.subjectsCreated)}</strong> anagrafiche create</span>
          <span><strong>{formatImportNumber(summary.documentsImported)}</strong> documenti acquisiti</span>
          <span><strong>{formatImportNumber(summary.emailsImported)}</strong> email acquisite</span>
          <span><strong>{formatImportNumber(summary.activitiesImported)}</strong> appuntamenti registrati</span>
          <span><strong>{formatImportNumber(summary.duplicatesSkipped)}</strong> duplicati evitati</span>
          {result.recovery ? <span><strong>{formatImportNumber(result.recovery.recovered)}</strong> originali recuperati dai file non collegati</span> : null}
        </section>
        {result.recovery?.pending.length ? (
          <div className="iu-st-import-warning">
            <AlertTriangle size={18} />
            <div>
              <strong>{formatImportNumber(result.recovery.pending.length)} originali da associare o verificare</strong>
              <p>Questi file restano nel pacchetto originale. Nessun documento è stato assegnato a un fascicolo senza una corrispondenza univoca.</p>
              <ul>{result.recovery.pending.slice(0, 20).map((file) => <li key={file.name}>{file.name}: {file.reason}</li>)}</ul>
            </div>
          </div>
        ) : null}
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
              {result.errors.slice(0, 5).map((error) => <p key={error}>{importUiText(error)}</p>)}
            </div>
          </div>
        ) : null}
        {result.warnings.length ? (
          <div className="iu-st-import-warning">
            <AlertTriangle size={18} />
            <div>
              <strong>Avvisi dell'acquisizione</strong>
              {result.warnings.map((warning) => <p key={warning.code}>{importUiText(warning.message)}</p>)}
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
  const importInFlight = useRef(false)
  const selectedStoredPackage = useRef('')
  const previousImportRun = useRef<string | undefined>(undefined)
  const [message, setMessage] = useState('')
  const [allowPartial, setAllowPartial] = useState(false)
  const [selection, setSelection] = useState<ImportSelection>({ matterIds: [], documents: true, emails: true, appointments: true, unassigned: true })
  const [inventoryQuery, setInventoryQuery] = useState('')
  const [analyzeUnassigned, setAnalyzeUnassigned] = useState(false)
  const [inventoryPage, setInventoryPage] = useState(0)
  useEffect(() => {
    setSelection({ matterIds: preview?.analysis.samples.matters.map(matter => matter.id) || [], documents: true, emails: true, appointments: true, unassigned: true })
    setInventoryQuery('')
    setAnalyzeUnassigned(false)
    setInventoryPage(0)
  }, [preview?.importId])
  const [result, setResult] = useState<StudioTelematicoImportResult>(emptyStudioTelematicoResult)
  const [workProgress, setWorkProgress] = useState<WorkProgress>({ active: false, label: '', detail: '', value: 0 })
  const [autoPrepare, setAutoPrepare] = useState<StudioTelematicoPrepareStatus | null>(null)
  const autoImportStartedRef = useRef(false)
  useBusyActivity(loading, 'Caricamento dell’importazione pratiche…')
  useBusyActivity(previewState === 'loading', 'Analisi del pacchetto pratiche…')
  useBusyActivity(importState === 'loading', 'Importazione delle pratiche…')
  useBusyActivity(workProgress.active, 'Elaborazione del pacchetto pratiche…')

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

  useEffect(() => {
    if (!autoPrepare?.statusUrl || !autoPrepareActive(autoPrepare.status)) return undefined
    const controller = new AbortController()
    const timer = window.setInterval(() => {
      getStudioTelematicoAutoPrepareStatus(autoPrepare.statusUrl, controller.signal)
        .then((status) => applyAutoPrepareStatus(status))
        .catch(() => {
          if (!controller.signal.aborted) {
            setWorkProgress((current) => ({
              ...current,
              detail: 'Attendo aggiornamenti dalla postazione autorizzata.',
            }))
          }
        })
    }, 2500)
    return () => {
      controller.abort()
      window.clearInterval(timer)
    }
  }, [autoPrepare?.status, autoPrepare?.statusUrl])

  useEffect(() => {
    if (importState !== 'loading' || !preview?.importId) return
    const controller = new AbortController()
    let pending = false
    const poll = async () => {
      if (pending) return
      pending = true
      try {
        const state = await getStudioTelematicoImportProgress(preview.importId, controller.signal)
        if (!state.ok || controller.signal.aborted || state.runId === previousImportRun.current) return
        if (state.status === 'running') {
          setWorkProgress({ active: true, label: state.phase, detail: state.total ? `${state.done} di ${state.total} elementi della fase corrente` : 'Operazione avviata sul server', value: state.total ? Math.round(state.done * 100 / state.total) : 0 })
        } else if (['complete', 'partial', 'failed', 'interrupted'].includes(state.status)) {
          const complete = state.status === 'complete'
          setImportState(complete ? 'success' : 'error')
          setWorkProgress({ active: false, label: complete ? 'Selezione acquisita e verificata' : 'Acquisizione da verificare', detail: 'Stato confermato dal server', value: 100 })
          setMessage(complete ? 'Il server ha completato e verificato l’acquisizione selezionata.' : 'Il server segnala un’acquisizione incompleta o interrotta. Controlla il riepilogo e i fascicoli; conserva il pacchetto originale.')
        }
      } catch {
        // Un errore del monitor non avvia né annulla l'importazione.
      } finally { pending = false }
    }
    const timer = window.setInterval(() => { void poll() }, 2000)
    return () => { controller.abort(); window.clearInterval(timer) }
  }, [importState, preview?.importId])

  const analysis = preview?.analysis || null
  const sourcePathValue = sourcePath.trim()
  const uploadConfig = data.upload || emptyStudioTelematicoPage.upload
  const chunkUploadAvailable = Boolean(data.actions.uploadStart && data.actions.uploadChunk && data.actions.uploadComplete)
  const largePackageSelected = Boolean(file && file.size > uploadConfig.directLimitBytes)
  const autoPrepareRunning = Boolean(autoPrepare && autoPrepareActive(autoPrepare.status))
  const canRun = useMemo(() => {
    if (!selection.matterIds.length || !data.permissions.canImport || !preview?.ok || importState === 'loading') return false
    return Boolean(preview.analysis.canImportComplete || allowPartial)
  }, [allowPartial, data.permissions.canImport, importState, preview, selection.matterIds.length])

  function triggerAutoPrepareDownload(downloadUrl: string) {
    if (!downloadUrl) return
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = 'AvviaImportPratiche.cmd'
    document.body.appendChild(link)
    link.click()
    link.remove()
  }

  function applyAutoPrepareStatus(status: StudioTelematicoPrepareStatus) {
    const merged = {
      ...status,
      statusUrl: status.statusUrl || autoPrepare?.statusUrl || '',
      downloadUrl: status.downloadUrl || autoPrepare?.downloadUrl || '',
    }
    setAutoPrepare(merged)
    const active = autoPrepareActive(merged.status)
    setWorkProgress({
      active,
      label: autoPrepareLabel(merged.status),
      detail: merged.errore || merged.detail || 'Preparazione pacchetto in corso.',
      value: merged.progress || (active ? 10 : 100),
    })
    if (!merged.ok) {
      setPreviewState('error')
      setMessage(merged.errore || 'Preparazione pacchetto non disponibile.')
      return
    }
    if (merged.status === 'error') {
      setPreviewState('error')
      setMessage(merged.errore || merged.detail || 'Preparazione pacchetto interrotta.')
      return
    }
    if (merged.preview?.ok) {
      setPreview(merged.preview)
      setPreviewState('success')
      setAllowPartial(false)
      const warnings = merged.preview.analysis?.warnings ?? []
      const hasWarnings = !merged.preview.analysis?.canImportComplete || warnings.length > 0
      if (hasWarnings) {
        setMessage(warnings[0]?.message || 'Pacchetto controllato con avvisi. Verifica il riepilogo prima di importare.')
        return
      }
      setMessage('Pacchetto controllato. Scegli i dati da acquisire e conferma l’importazione.')
    }
  }

  async function handleAutoPrepare() {
    autoImportStartedRef.current = false
    setAutoPrepare(null)
    setFile(null)
    setSourcePath('')
    setPreview(null)
    setResult(emptyStudioTelematicoResult)
    setPreviewState('loading')
    setImportState('idle')
    setMessage('Preparazione pacchetto in avvio. La pagina seguirà preparazione, caricamento e controllo.')
    setWorkProgress({
      active: true,
      label: 'Avvio preparazione',
      detail: 'Creo una sessione sicura per la postazione autorizzata.',
      value: 5,
    })
    const started = await startStudioTelematicoAutoPrepare(data.actions.prepareStart || '')
    if (!started.ok) {
      setAutoPrepare(started)
      setPreviewState('error')
      setWorkProgress({
        active: false,
        label: 'Preparazione non avviata',
        detail: started.errore || 'Riprova dalla pagina import.',
        value: 100,
      })
      setMessage(started.errore || 'Preparazione pacchetto non avviata.')
      return
    }
    applyAutoPrepareStatus(started)
    triggerAutoPrepareDownload(started.downloadUrl)
    setMessage('Avviatore scaricato. Se Windows non lo apre subito, apri AvviaImportPratiche.cmd dai download: la pagina continuerà da sola fino al controllo.')
  }

  async function handlePreview() {
    autoImportStartedRef.current = false
    setAutoPrepare(null)
    if (!file && !sourcePathValue) {
      setMessage('Seleziona il pacchetto preparato sul PC del cliente oppure incolla il percorso del file.')
      return
    }
    if (file && file.size > uploadConfig.maxUploadBytes) {
      setPreviewState('error')
      setWorkProgress({
        active: false,
        label: 'Pacchetto troppo grande',
        detail: 'Il pacchetto supera la dimensione massima consentita per il caricamento dallo studio.',
        value: 100,
      })
      setMessage('Il pacchetto supera la dimensione massima consentita. Prepara un archivio più leggero o caricalo dalla postazione locale autorizzata.')
      return
    }
    if (largePackageSelected && !sourcePathValue && !chunkUploadAvailable) {
      setPreviewState('error')
      setWorkProgress({
        active: false,
        label: 'Caricamento a blocchi non disponibile',
        detail: 'Per archivi molto grandi serve il caricamento a blocchi oppure il percorso del file sul PC autorizzato.',
        value: 100,
      })
      setMessage('Il pacchetto è molto grande: usa il percorso locale autorizzato oppure riprova quando il caricamento a blocchi è disponibile.')
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
        ? 'Leggo archivio, documenti, comunicazioni e dati pratica senza ricopiare il file'
        : largePackageSelected
          ? 'Carico il pacchetto a blocchi e poi controllo pratiche, documenti e comunicazioni'
          : 'Carico archivio, documenti, comunicazioni e dati pratica',
      value: 35,
    })
    const checked = await previewStudioTelematicoPackage(data.actions.preview, {
      file: sourcePathValue ? null : file,
      sourcePath: sourcePathValue,
      chunked: file && largePackageSelected && chunkUploadAvailable
        ? {
            startEndpoint: data.actions.uploadStart,
            chunkEndpoint: data.actions.uploadChunk,
            completeEndpoint: data.actions.uploadComplete,
            chunkSizeBytes: uploadConfig.chunkSizeBytes,
            onProgress: ({ value, detail }) => setWorkProgress((current) => ({
              ...current,
              value,
              detail,
            })),
          }
        : undefined,
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
      : checked.errore || 'Controllo non completato. Verifica che il pacchetto sia lo ZIP preparato dalla postazione autorizzata completa.')
  }

  async function handleImport(importId = preview?.importId || '', allowPartialOverride = allowPartial, automatic = false) {
    if (!importId || importInFlight.current) return
    importInFlight.current = true
    previousImportRun.current = (await getStudioTelematicoImportProgress(importId)).runId
    setResult(emptyStudioTelematicoResult)
    setImportState('loading')
    setMessage(automatic
      ? 'Pacchetto completo: import definitivo automatico in corso.'
      : 'Importazione in corso. Creo o aggiorno pratiche, clienti, parti, documenti e comunicazioni senza duplicare i dati già presenti.')
    setWorkProgress({
      active: true,
      label: 'Importazione pratiche',
      detail: 'Registro fascicoli, anagrafiche, documenti e messaggi',
      value: 55,
    })
    try {
      const imported = await runStudioTelematicoImport(data.actions.run, importId, allowPartialOverride, selection, analyzeUnassigned, preview?.sourceSha256 || '')
      if (!imported.ok) {
        const state = await getStudioTelematicoImportProgress(importId)
        if (state.ok && state.status === 'running') {
          setMessage('Il server sta ancora acquisendo i dati. L’avanzamento viene aggiornato automaticamente.')
          return
        }
      }
      setResult(imported)
      setImportState(imported.ok ? 'success' : 'error')
      setWorkProgress({
        active: false,
        label: imported.ok ? (imported.complete ? 'Selezione acquisita e verificata' : 'Acquisizione da verificare') : 'Import non completato',
        detail: imported.ok ? 'Riepilogo acquisizioni pronto' : (imported.errore || 'Controlla gli avvisi'),
        value: 100,
      })
      setMessage(imported.ok ? (imported.complete ? 'Selezione acquisita e verificata.' : 'Acquisizione da verificare. Controlla gli elementi indicati nel riepilogo e conserva il pacchetto originale.') : imported.errore || 'Import non completato.')
    } catch {
      setImportState('error')
      setMessage('La risposta del server non è disponibile. L’importazione potrebbe essere ancora in corso: verifica i fascicoli prima di ripeterla.')
      setWorkProgress({ active: false, label: 'Esito da verificare', detail: 'Risposta del server non ricevuta', value: 0 })
    } finally {
      importInFlight.current = false
    }

  }

  return (
    <Page
      title={importUiText(data.page.title)}
      subtitle={importUiText(data.page.subtitle)}
      actions={
        <>
          <Button type="button" tone="neutral" onClick={handleAutoPrepare} disabled={!data.permissions.canImport || autoPrepareRunning}>
            <Download size={15} />
            {autoPrepareRunning ? 'Preparazione in corso' : 'Prepara pacchetto'}
          </Button>
          <ButtonLink href={data.actions.fascicoli} tone="primary">
            Fascicoli
          </ButtonLink>
        </>
      }
    >
      {loading ? <LoadingState title="Caricamento import pratiche" message="Preparazione del percorso guidato." /> : null}
      {!loading && error ? <EmptyState title="Import pratiche non disponibile" message={importUiText(error)} /> : null}
      {!loading && !error && !data.permissions.canImport ? (
        <EmptyState title="Profilo non autorizzato" message={data.permissions.message || 'Serve un profilo autorizzato dello studio.'} />
      ) : null}
      {!loading && !error && data.permissions.canImport ? (
        <div className="iu-st-import-page">
          <section className="iu-st-import-banner" aria-label="Import guidato">
            <div>
              <strong>Percorso guidato di migrazione</strong>
              <span>Ogni pratica viene ricostruita con cliente, parti, documenti, comunicazioni e agenda quando i file sono presenti.</span>
            </div>
            <Badge tone={analysis ? completenessTone(analysis) : 'info'}>
              {result.ok ? (result.complete ? 'Selezione acquisita e verificata' : 'Da completare') : analysis ? (analysis.canImportComplete ? 'Pronto per importare' : 'Da completare') : 'In attesa pacchetto'}
            </Badge>
          </section>
          <GuidedSteps data={data} />
          <ImportPanel title="Pacchetto cliente" subtitle="Carica il file preparato dalla postazione autorizzata">
            {data.storedPackages?.length ? (
              <div className="iu-st-import-upload">
                <label className="iu-st-import-local-path">
                  <span>Pacchetto già disponibile nello studio</span>
                  <select aria-label="Pacchetto già presente nello studio" defaultValue="" disabled={importState === 'loading'} onChange={(event) => {
                    const stored = data.storedPackages?.find((item) => item.importId === event.currentTarget.value)
                    if (!stored?.analysis) return
                    setFile(null)
                    setSourcePath('')
                    selectedStoredPackage.current = stored.importId
                    setPreview(null)
                    setPreviewState('loading')
                    void getStudioTelematicoStoredPreview(stored.importId).then(fresh => {
                      if (selectedStoredPackage.current !== stored.importId) return
                      setPreview(fresh.ok ? fresh : null)
                      setPreviewState(fresh.ok ? 'success' : 'error')
                      setMessage(fresh.ok ? 'Inventario aggiornato. Scegli gli elementi da acquisire.' : fresh.errore || 'Pacchetto non disponibile.')
                    })
                    setImportState('idle')
                    setAutoPrepare(null)
                    autoImportStartedRef.current = false
                    setWorkProgress({ active: false, label: '', detail: '', value: 0 })
                    setAllowPartial(false)
                    setResult(emptyStudioTelematicoResult)
                    setMessage('Pacchetto già caricato selezionato. Verifica il riepilogo prima di procedere.')
                  }}>
                    <option value="">Seleziona un pacchetto già caricato</option>
                    {data.storedPackages.map((stored) => <option key={stored.importId} value={stored.importId}>{stored.sourceName}</option>)}
                  </select>
                </label>
              </div>
            ) : null}
            <div className="iu-st-import-upload">
              <label className="iu-st-import-file">
                <UploadCloud size={22} />
                <span>{file ? fileLabel(file) : preview?.sourceName || fileLabel(file)}</span>
                <input
                  type="file"
                  disabled={importState === 'loading'}
                  accept={data.acceptedFiles}
                  onChange={(event) => {
                    selectedStoredPackage.current = ''
                    setPreviewState('idle')
                    autoImportStartedRef.current = false
                    setAutoPrepare(null)
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
                  disabled={importState === 'loading'}
                  value={sourcePath}
                  placeholder={'C:\\Users\\utente\\Downloads\\PacchettoPratiche.zip'}
                  onChange={(event) => {
                    selectedStoredPackage.current = ''
                    setPreviewState('idle')
                    autoImportStartedRef.current = false
                    setAutoPrepare(null)
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
            {largePackageSelected && !sourcePathValue ? (
              <div className={`iu-st-import-message is-${chunkUploadAvailable ? 'info' : 'error'}`}>
                <AlertTriangle size={16} />
                <span>{chunkUploadAvailable ? 'Archivio grande rilevato: verrà caricato a blocchi senza superare il limite della richiesta.' : 'Archivio molto grande rilevato: usa il percorso del file sul PC per evitare attese e caricamenti non riusciti.'}</span>
              </div>
            ) : null}
            <div className="iu-st-import-notes">
              {data.notes.map((note) => <span key={note}>{importUiText(note)}</span>)}
            </div>
            <WorkProgressBar progress={workProgress} />
            {message ? (
              <div className={`iu-st-import-message is-${previewState === 'error' || importState === 'error' ? 'error' : 'info'}`}>
                {previewState === 'error' || importState === 'error' ? <AlertTriangle size={16} /> : <CheckCircle2 size={16} />}
                <span>{importUiText(message)}</span>
              </div>
            ) : null}
          </ImportPanel>
          {analysis ? (
            <>
              <SummaryCards analysis={analysis} />
              <MissingFiles analysis={analysis} />
              <ImportPanel title="Scegli cosa acquisire" subtitle="Seleziona le pratiche e i contenuti. Clienti e parti necessari alle pratiche selezionate vengono inclusi per conservare i collegamenti.">
                <fieldset disabled={importState === 'loading'}>
                  <legend>Pratiche da importare</legend>
                  <Button type="button" tone="neutral" onClick={() => setSelection(s => ({ ...s, matterIds: analysis.samples.matters.map(m => m.id), documents: true, emails: true, appointments: true, unassigned: true, excludedIds: [] }))}>Seleziona tutto</Button>
                  <Button type="button" tone="neutral" onClick={() => setSelection(s => ({ ...s, matterIds: [] }))}>Deseleziona pratiche</Button>
                  {analysis.samples.matters.map(matter => <label key={matter.id} className="iu-st-import-choice">
                    <input type="checkbox" checked={selection.matterIds.includes(matter.id)} onChange={event => { const checked = event.currentTarget.checked; setSelection(s => ({ ...s, matterIds: checked ? [...s.matterIds, matter.id] : s.matterIds.filter(id => id !== matter.id) })) }} /> {matter.title} · {matter.status}
                  </label>)}
                  {([['documents', 'Documenti'], ['emails', 'Comunicazioni'], ['appointments', 'Appuntamenti'], ['unassigned', 'Controlla e conserva anche i file senza collegamento certo']] as const).map(([key, label]) => <label key={key} className="iu-st-import-choice">
                    <input type="checkbox" checked={selection[key]} onChange={event => { const checked = event.currentTarget.checked; setSelection(s => ({ ...s, [key]: checked })) }} /> {label}
                  </label>)}
                  <label className="iu-st-import-choice"><input type="checkbox" checked={analyzeUnassigned} onChange={event => setAnalyzeUnassigned(event.currentTarget.checked)} /> Analizza anche il contenuto dei file senza pratica per cercare associazioni (può richiedere molto tempo).</label>
                  <p>{selection.matterIds.length} pratiche selezionate su {analysis.samples.matters.length}. Gli elementi esclusi restano nel pacchetto originale.</p>
                </fieldset>
              </ImportPanel>
              <ImportPanel title="Contenuto del pacchetto" subtitle="Elenco dei record riconosciuti e di tutti i file ZIP. Le voci ARCHIVIO sono file di supporto conservati nel pacchetto; non sono documenti associati a una pratica. La ricerca non cambia la selezione.">
                <p><a href={`/api/v1/ui/import/quickorganizer/${encodeURIComponent(preview?.importId || '')}/pacchetto`} download>Scarica il pacchetto originale completo</a></p>
                <label>Cerca nell’inventario <input type="search" value={inventoryQuery} onChange={event => { setInventoryQuery(event.currentTarget.value); setInventoryPage(0) }} /></label>
                {(() => {
                  const inventory = (analysis.inventory || []).filter(item => `${item.label} ${item.category} ${item.matterId}`.toLocaleLowerCase('it').includes(inventoryQuery.toLocaleLowerCase('it')))
                  const pages = Math.max(1, Math.ceil(inventory.length / 50))
                  return <>
                    <p>{inventory.length} elementi · pagina {inventoryPage + 1} di {pages}</p>
                    <ul>{inventory.slice(inventoryPage * 50, (inventoryPage + 1) * 50).map(item => <li key={item.id} className="iu-st-import-inventory-item">{['TESTI', 'EMAILS', 'AGENDA'].includes(item.category) ? <label><input type="checkbox" aria-label={`Importa ${item.label}`} disabled={importState === 'loading' || !selection.matterIds.includes(item.matterId) || !(item.category === 'TESTI' ? selection.documents : item.category === 'EMAILS' ? selection.emails : selection.appointments)} checked={selection.matterIds.includes(item.matterId) && (item.category === 'TESTI' ? selection.documents : item.category === 'EMAILS' ? selection.emails : selection.appointments) && !(selection.excludedIds || []).includes(item.id)} onChange={event => { const checked = event.currentTarget.checked; setSelection(s => ({ ...s, excludedIds: checked ? (s.excludedIds || []).filter(id => id !== item.id) : [...(s.excludedIds || []), item.id] })) }} /> Importa </label> : null}{item.category} · {item.label}{item.matterId ? ` · pratica ${item.matterId}` : ''}{item.size ? ` · ${formatImportNumber(item.size)} byte` : ''}{item.category === 'FILE' && !item.assigned ? <label> Associa a <select aria-label={`Pratica per ${item.label}`} value={selection.fileAssignments?.[item.id] || ''} disabled={importState === 'loading' || !selection.unassigned} onChange={event => { const value = event.currentTarget.value; setSelection(s => { const fileAssignments = { ...s.fileAssignments }; if (value) fileAssignments[item.id] = value; else delete fileAssignments[item.id]; return { ...s, fileAssignments } }) }}><option value="">Da associare</option>{analysis.samples.matters.filter(m => selection.matterIds.includes(m.id)).map(m => <option key={m.id} value={m.id}>{m.title}</option>)}</select></label> : null}{item.category === 'FILE' ? <a href={`/api/v1/ui/import/quickorganizer/${encodeURIComponent(preview?.importId || '')}/originale/${encodeURIComponent(item.id.split(':')[1])}`} download> Scarica originale</a> : null}</li>)}</ul>
                    <Button type="button" tone="neutral" disabled={inventoryPage === 0} onClick={() => setInventoryPage(p => p - 1)}>Precedente</Button>
                    <Button type="button" tone="neutral" disabled={inventoryPage + 1 >= pages} onClick={() => setInventoryPage(p => p + 1)}>Successiva</Button>
                  </>
                })()}
              </ImportPanel>
              {!result.ok && analysis.warnings.length ? (
                <ImportPanel title="Avvisi del controllo" subtitle="Elementi da verificare prima dell'acquisizione">
                  {analysis.warnings.map((warning) => <p key={warning.code}>{importUiText(warning.message)}</p>)}
                </ImportPanel>
              ) : null}
              <ImportPanel
                title="Conferma import"
                subtitle={analysis.canImportComplete ? 'Il pacchetto risulta completo.' : 'Puoi attendere il pacchetto completo oppure acquisire solo i dati disponibili.'}
              >
                <div className="iu-st-import-confirm">
                  {!analysis.canImportComplete ? (
                    <label>
                      <input type="checkbox" checked={allowPartial} onChange={(event) => setAllowPartial(event.currentTarget.checked)} />
                      <span>Importa comunque le pratiche disponibili e segnala i documenti mancanti nei fascicoli.</span>
                    </label>
                  ) : (
                    <div className="iu-st-import-ok">
                      <CheckCircle2 size={18} />
                      <span>Documenti e comunicazioni risultano presenti nel pacchetto controllato.</span>
                    </div>
                  )}
                  <Button type="button" onClick={() => handleImport()} disabled={!canRun}>
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
