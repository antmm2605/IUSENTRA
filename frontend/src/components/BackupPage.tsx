import { useEffect, useMemo, useState } from 'react'
import { Archive, CheckCircle2, Download, Play, RefreshCw, ShieldAlert, ShieldCheck } from 'lucide-react'
import {
  createBackup,
  emptyBackupPage,
  getBackupPage,
  verifyBackupIntegrity,
  type BackupComponentOption,
  type BackupMutationResult,
  type BackupPageData,
  type BackupRow,
} from '../backupData'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import './BackupPage.css'

type LoadStatus = 'loading' | 'ready' | 'error'
type SaveStatus = 'idle' | 'saving' | 'success' | 'error'

type CreateState = {
  type: string
  components: string[]
  note: string
  confirm: boolean
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat('it-IT').format(value)
}

function formatSize(value: number): string {
  return `${new Intl.NumberFormat('it-IT', { maximumFractionDigits: 2 }).format(value)} MB`
}

function formatDate(value: string): string {
  if (!value) return 'Data non indicata'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value.replace('T', ' ').slice(0, 16)
  return new Intl.DateTimeFormat('it-IT', { dateStyle: 'short', timeStyle: 'short' }).format(parsed)
}

function validationItems(errors: Record<string, string>): string[] {
  return Object.values(errors).filter(Boolean)
}

function defaultComponents(options: BackupComponentOption[]): string[] {
  return options.filter((option) => option.available && option.enabled).map((option) => option.id)
}

function matchesQuery(record: BackupRow, query: string): boolean {
  const needle = query.trim().toLowerCase()
  if (!needle) return true
  return [
    record.fileName,
    record.type,
    record.stateLabel,
    record.note,
    record.createdAt,
    ...record.components,
  ].some((value) => value.toLowerCase().includes(needle))
}

function StatusMessage({
  status,
  message,
  errors,
}: {
  status: SaveStatus
  message: string
  errors: Record<string, string>
}) {
  if (status === 'idle' && !message && !Object.keys(errors).length) return null
  const tone = status === 'success' ? 'success' : status === 'saving' ? 'info' : 'danger'
  const title = status === 'success'
    ? 'Operazione completata'
    : status === 'saving'
      ? 'Operazione in corso'
      : errors.permission
        ? 'Permesso negato'
        : 'Controlla i dati'
  return (
    <div className={`iu-backup-status iu-backup-status--${tone}`} aria-live="polite">
      <div>
        {status === 'success' ? <CheckCircle2 size={18} /> : status === 'saving' ? <RefreshCw size={18} /> : <ShieldAlert size={18} />}
        <strong>{title}</strong>
      </div>
      {message ? <p>{message}</p> : null}
      {validationItems(errors).length ? (
        <ul>
          {validationItems(errors).map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

function Warnings({ data }: { data: BackupPageData }) {
  if (!data.warnings.length) return null
  return (
    <Panel title="Avvisi operativi" subtitle="Limiti dichiarati dal backend per questa tranche">
      <div className="iu-backup-warnings">
        {data.warnings.map((warning) => (
          <div className="iu-backup-warning" key={`${warning.code}-${warning.message}`}>
            <Badge tone="warning">{warning.code}</Badge>
            <span>{warning.message}</span>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function BackupRecordItem({
  record,
  canDownload,
}: {
  record: BackupRow
  canDownload: boolean
}) {
  const cannotDownload = !canDownload ? 'Permesso backup.leggi richiesto.' : 'Download non disponibile per questa copia.'
  return (
    <article className="iu-backup-record">
      <div className="iu-backup-record__main">
        <time>{formatDate(record.createdAt)}</time>
        <strong>{record.fileName || record.id}</strong>
        <span>{record.type || 'Tipo non indicato'} - {formatNumber(record.filesCount)} file - {formatSize(record.sizeMb)}</span>
        {record.note ? <small>{record.note}</small> : null}
        {record.error ? <small>{record.error}</small> : null}
      </div>
      <div className="iu-backup-record__state">
        <Badge tone={record.stateTone}>{record.stateLabel || record.state || 'Stato non indicato'}</Badge>
        {record.encrypted ? <Badge tone="warning">Protetto</Badge> : <Badge tone="neutral">Non cifrato</Badge>}
        <span>{record.components.length ? record.components.join(', ') : 'Componenti non indicati'}</span>
      </div>
      <div className="iu-backup-record__actions">
        {canDownload && record.downloadHref ? (
          <ButtonLink href={record.downloadHref} tone="neutral">
            <Download size={16} />
            Scarica
          </ButtonLink>
        ) : (
          <Button type="button" tone="neutral" disabled title={cannotDownload}>
            <Download size={16} />
            Scarica
          </Button>
        )}
      </div>
    </article>
  )
}

function PermissionHint({
  allowed,
  text,
}: {
  allowed: boolean
  text: string
}) {
  if (allowed) return null
  return <small className="iu-backup-help">{text}</small>
}

export function BackupPage() {
  const [data, setData] = useState<BackupPageData>(emptyBackupPage)
  const [loadStatus, setLoadStatus] = useState<LoadStatus>('loading')
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const [message, setMessage] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [query, setQuery] = useState('')
  const [createState, setCreateState] = useState<CreateState>({ type: 'COMPLETO', components: [], note: '', confirm: false })
  const [verifyBackupId, setVerifyBackupId] = useState('')
  const [verifyConfirm, setVerifyConfirm] = useState(false)

  async function loadPage() {
    setLoadStatus('loading')
    try {
      const payload = await getBackupPage()
      setData(payload)
      setLoadStatus('ready')
      const defaults = defaultComponents(payload.status.configuredComponents)
      setCreateState((current) => ({
        ...current,
        components: current.components.length ? current.components : defaults,
      }))
      const firstBackup = payload.backups.find((record) => record.state === 'OK') || payload.backups[0]
      setVerifyBackupId((current) => current || firstBackup?.id || '')
    } catch {
      setLoadStatus('error')
      setMessage('Backup non disponibile.')
      setErrors({ _form: 'Errore durante la lettura dei dati backup.' })
    }
  }

  useEffect(() => {
    let active = true
    getBackupPage()
      .then((payload) => {
        if (!active) return
        setData(payload)
        setLoadStatus('ready')
        setCreateState((current) => ({
          ...current,
          components: current.components.length ? current.components : defaultComponents(payload.status.configuredComponents),
        }))
        const firstBackup = payload.backups.find((record) => record.state === 'OK') || payload.backups[0]
        setVerifyBackupId(firstBackup?.id || '')
      })
      .catch(() => {
        if (!active) return
        setLoadStatus('error')
        setMessage('Backup non disponibile.')
        setErrors({ _form: 'Errore durante la lettura dei dati backup.' })
      })
    return () => {
      active = false
    }
  }, [])

  const filteredBackups = useMemo(
    () => data.backups.filter((record) => matchesQuery(record, query)),
    [data.backups, query],
  )
  const availableComponents = data.status.configuredComponents.filter((option) => option.available)
  const createDirty = createState.note.trim().length > 0
    || createState.type !== 'COMPLETO'
    || createState.confirm
    || createState.components.join('|') !== defaultComponents(data.status.configuredComponents).join('|')
  const hasData = data.backups.length > 0 || data.status.total > 0 || data.status.configuredComponents.length > 0
  const canCreate = data.actions.canCreate
  const canVerify = data.actions.canVerify
  const canDownload = data.actions.canDownload
  const selectedVerifyBackup = data.backups.find((record) => record.id === verifyBackupId)

  function setComponent(componentId: string, checked: boolean) {
    setCreateState((current) => ({
      ...current,
      components: checked
        ? Array.from(new Set([...current.components, componentId]))
        : current.components.filter((item) => item !== componentId),
    }))
    setSaveStatus('idle')
    setErrors({})
  }

  async function applyMutation(callback: () => Promise<BackupMutationResult>) {
    setSaveStatus('saving')
    setMessage('')
    setErrors({})
    try {
      const result = await callback()
      if (result.ok) {
        setSaveStatus('success')
        setMessage(result.message)
        setErrors({})
        await loadPage()
      } else {
        setSaveStatus('error')
        setMessage(result.message)
        setErrors(result.errors)
        if (result.backup || result.integrity) await loadPage()
      }
    } catch {
      setSaveStatus('error')
      setMessage('Operazione non completata.')
      setErrors({ _form: 'Errore di rete durante il salvataggio.' })
    }
  }

  function runCreate() {
    if (!createState.confirm) {
      setSaveStatus('error')
      setMessage('Conferma esplicitamente la creazione del backup.')
      setErrors({ confirm: 'La creazione richiede conferma.' })
      return
    }
    applyMutation(() => createBackup(createState, data.actions.createEndpoint)).then(() => {
      setCreateState((current) => ({ ...current, confirm: false }))
    })
  }

  function runVerify() {
    if (!verifyConfirm) {
      setSaveStatus('error')
      setMessage('Conferma esplicitamente la verifica integrita.')
      setErrors({ confirm: 'La verifica richiede conferma.' })
      return
    }
    applyMutation(() => verifyBackupIntegrity(
      { backupId: verifyBackupId, confirm: verifyConfirm },
      data.actions.verifyEndpoint,
    )).then(() => setVerifyConfirm(false))
  }

  return (
    <Page
      title="Backup"
      subtitle="Registro backup reale, creazione copie e verifica integrita tramite API JSON protette."
      actions={
        <Button type="button" tone="neutral" onClick={loadPage} disabled={loadStatus === 'loading' || saveStatus === 'saving'}>
          <RefreshCw size={16} />
          Aggiorna
        </Button>
      }
    >
      {loadStatus === 'loading' ? <LoadingState title="Caricamento backup" message="Lettura del registro backup reale in corso." /> : null}
      {loadStatus === 'error' ? <StatusMessage status="error" message={message} errors={errors} /> : null}
      {loadStatus === 'ready' ? (
        <>
          <section className="iu-backup-kpis" aria-label="Stato backup">
            <KpiCard label="Backup totali" value={formatNumber(data.status.total)} note="Record nel registro reale" badge={<Badge tone="primary">registro</Badge>} />
            <KpiCard label="Completati" value={formatNumber(data.status.completed)} note={`Ultimo: ${formatDate(data.status.lastBackupAt)}`} badge={<Badge tone="success">ok</Badge>} />
            <KpiCard label="Anomalie" value={formatNumber(data.status.failed + data.status.corrupted)} note="Falliti o da verificare" badge={<Badge tone={data.status.failed + data.status.corrupted ? 'warning' : 'neutral'}>integrita</Badge>} />
            <KpiCard label="Spazio" value={formatSize(data.status.totalSizeMb)} note="Somma copie completate" badge={<Badge tone="info">storage</Badge>} />
          </section>

          <StatusMessage status={saveStatus} message={message} errors={errors} />
          <Warnings data={data} />

          {!hasData ? (
            <EmptyState
              title="Nessun backup disponibile"
              message="Il registro backup non contiene ancora copie visualizzabili. La creazione resta disponibile solo con permesso backend."
            />
          ) : null}

          <section className="iu-backup-workspace" aria-label="Operazioni backup">
            <Panel
              title="Crea backup"
              subtitle="La destinazione resta governata dal backend, senza parametri di percorso dal frontend."
              actions={createDirty ? <Badge tone="warning">Parametri modificati</Badge> : <Badge tone="neutral">Pronto</Badge>}
            >
              <div className="iu-backup-form">
                <label className="iu-backup-field">
                  <span>Tipo</span>
                  <select
                    value={createState.type}
                    onChange={(event) => {
                      setCreateState((current) => ({ ...current, type: event.target.value }))
                      setSaveStatus('idle')
                    }}
                    disabled={!canCreate || saveStatus === 'saving'}
                  >
                    <option value="COMPLETO">Completo</option>
                    <option value="INCREMENTALE">Incrementale</option>
                  </select>
                </label>
                <label className="iu-backup-field iu-backup-field--wide">
                  <span>Nota</span>
                  <textarea
                    value={createState.note}
                    maxLength={240}
                    onChange={(event) => {
                      setCreateState((current) => ({ ...current, note: event.target.value }))
                      setSaveStatus('idle')
                    }}
                    disabled={!canCreate || saveStatus === 'saving'}
                  />
                  <small>{createState.note.length}/240 caratteri</small>
                </label>
                <fieldset className="iu-backup-checks">
                  <legend>Componenti</legend>
                  <div className="iu-backup-check-grid">
                    {availableComponents.map((option) => (
                      <label className="iu-backup-check" key={option.id}>
                        <input
                          type="checkbox"
                          checked={createState.components.includes(option.id)}
                          onChange={(event) => setComponent(option.id, event.target.checked)}
                          disabled={!canCreate || saveStatus === 'saving'}
                        />
                        <span>{option.label}</span>
                      </label>
                    ))}
                  </div>
                  {!availableComponents.length ? <small>Nessun componente configurato dal runtime backup.</small> : null}
                </fieldset>
                <label className="iu-backup-check iu-backup-check--confirm">
                  <input
                    type="checkbox"
                    checked={createState.confirm}
                    onChange={(event) => setCreateState((current) => ({ ...current, confirm: event.target.checked }))}
                    disabled={!canCreate || saveStatus === 'saving'}
                  />
                  <span>Confermo la creazione della copia backup</span>
                </label>
                <div className="iu-backup-form-actions">
                  <Button type="button" tone="primary" onClick={runCreate} disabled={!canCreate || saveStatus === 'saving'} title={!canCreate ? 'Permesso backup.esegui richiesto.' : undefined}>
                    <Play size={16} />
                    {saveStatus === 'saving' ? 'Operazione in corso' : 'Avvia backup'}
                  </Button>
                  <PermissionHint allowed={canCreate} text="Il backend non consente la creazione backup alla sessione corrente." />
                </div>
              </div>
            </Panel>

            <Panel title="Verifica integrita" subtitle={data.integrity.label || 'Stato verifica letto dal registro backup.'}>
              <div className="iu-backup-form">
                <label className="iu-backup-field">
                  <span>Copia backup</span>
                  <select
                    value={verifyBackupId}
                    onChange={(event) => {
                      setVerifyBackupId(event.target.value)
                      setSaveStatus('idle')
                    }}
                    disabled={!canVerify || saveStatus === 'saving' || !data.backups.length}
                  >
                    {data.backups.map((record) => (
                      <option value={record.id} key={record.id}>
                        {formatDate(record.createdAt)} - {record.fileName || record.id}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="iu-backup-integrity">
                  <Badge tone={data.integrity.state === 'attention' ? 'warning' : data.integrity.state === 'ok' ? 'success' : 'neutral'}>
                    {data.integrity.label || 'Verifica non disponibile'}
                  </Badge>
                  <span>{selectedVerifyBackup ? `${selectedVerifyBackup.stateLabel} - ${formatSize(selectedVerifyBackup.sizeMb)}` : 'Nessuna copia selezionata'}</span>
                </div>
                <label className="iu-backup-check iu-backup-check--confirm">
                  <input
                    type="checkbox"
                    checked={verifyConfirm}
                    onChange={(event) => setVerifyConfirm(event.target.checked)}
                    disabled={!canVerify || saveStatus === 'saving' || !verifyBackupId}
                  />
                  <span>Confermo la verifica integrita della copia selezionata</span>
                </label>
                <div className="iu-backup-form-actions">
                  <Button type="button" tone="neutral" onClick={runVerify} disabled={!canVerify || saveStatus === 'saving' || !verifyBackupId} title={!canVerify ? 'Permesso backup.esegui richiesto.' : undefined}>
                    <ShieldCheck size={16} />
                    Verifica
                  </Button>
                  <PermissionHint allowed={canVerify} text="Il backend non consente la verifica backup alla sessione corrente." />
                </div>
              </div>
            </Panel>
          </section>

          <Panel title="Lista backup" subtitle={`${filteredBackups.length} copie visibili su ${data.backups.length}`}>
            <div className="iu-backup-toolbar">
              <label className="iu-backup-search">
                <Archive size={16} />
                <input
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Cerca per file, stato, tipo o componente"
                />
              </label>
              <Badge tone="neutral">{query.trim() ? 'Filtro locale' : 'Dati ricevuti'}</Badge>
            </div>
            {filteredBackups.length ? (
              <div className="iu-backup-records">
                {filteredBackups.map((record) => <BackupRecordItem record={record} canDownload={canDownload} key={record.id} />)}
              </div>
            ) : (
              <EmptyState title="Nessuna copia corrisponde al filtro" message="La ricerca opera sui dati gia ricevuti dall'API." />
            )}
          </Panel>

          <Panel title="Ripristino e cancellazione" subtitle="Funzioni non migrate nella UI React di questa tranche">
            <div className="iu-backup-protected">
              <div>
                <Badge tone="warning">Restore non migrato</Badge>
                <span>Il ripristino resta fuori dal flusso React e continua a passare da route legacy protette.</span>
              </div>
              <div>
                <Badge tone="neutral">Delete non introdotto</Badge>
                <span>La cancellazione backup non viene esposta da API JSON in questa PR.</span>
              </div>
            </div>
          </Panel>

          <Panel title="Rollback tecnico" subtitle="Disponibile solo come fallback operativo, non come azione primaria">
            <div className="iu-backup-rollback">
              <span>La pagina legacy exact resta raggiungibile con parametro tecnico; i subpath backup continuano a non essere serviti dalla shell React.</span>
              <ButtonLink href={data.actions.legacyHref} tone="neutral">
                Apri rollback tecnico
              </ButtonLink>
            </div>
          </Panel>

          <Panel title="Contratto dati" subtitle="Payload operativo JSON">
            <div className="iu-backup-contract">
              <span>Fonte: {data.source || 'non indicata'}</span>
              <span>Generato: {data.generated_at || 'non disponibile'}</span>
              <span>Scritture: {data.contracts.writes}</span>
              <span>Owner route: {data.contracts.route_owner}</span>
              <span>Operativo: {data.contracts.operational ? 'si' : 'no'}</span>
              <span>Restore migrato: {data.contracts.restore_migrated ? 'si' : 'no'}</span>
            </div>
          </Panel>
        </>
      ) : null}
    </Page>
  )
}
