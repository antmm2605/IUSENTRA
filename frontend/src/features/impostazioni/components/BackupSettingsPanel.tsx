import { useMemo, useState } from 'react'
import { Archive, ArchiveRestore, CheckCircle2, Download, Play, RefreshCw, ShieldCheck } from 'lucide-react'
import { createBackup, restoreBackup, verifyBackupIntegrity } from '@/backupData'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { IusStatusBadge } from '@/components/iusentra'
import type { SettingsPayload } from '../types'
import './BackupSettingsPanel.css'

type Row = Record<string, unknown>

function asRecord(value: unknown): Row {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Row : {}
}

function rows(value: unknown): Row[] {
  return Array.isArray(value) ? value.filter((item) => item && typeof item === 'object') as Row[] : []
}

function text(value: unknown): string {
  return value === undefined || value === null ? '' : String(value)
}

function number(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function formatSize(value: unknown): string {
  return `${new Intl.NumberFormat('it-IT', { maximumFractionDigits: 2 }).format(number(value))} MB`
}

function formatDate(value: unknown): string {
  const raw = text(value)
  if (!raw) return 'Mai'
  const parsed = new Date(raw)
  if (Number.isNaN(parsed.getTime())) return raw.replace('T', ' ').slice(0, 16)
  return new Intl.DateTimeFormat('it-IT', { timeZone: 'Europe/Rome', dateStyle: 'short', timeStyle: 'short' }).format(parsed)
}

function restoreIdFromPath(): string {
  if (typeof window === 'undefined') return ''
  const match = window.location.pathname.replace(/\/+$/, '').match(/^\/backup\/([^/]+)\/ripristina$/i)
  return match ? decodeURIComponent(match[1]) : ''
}

function defaultComponents(options: Row[]): string[] {
  return options.filter((item) => item.available !== false && item.enabled !== false).map((item) => text(item.id)).filter(Boolean)
}

export function BackupSettingsPanel({ data, onReload }: { data: SettingsPayload; onReload: () => void }) {
  const raw = asRecord(data.backup)
  const status = asRecord(raw.status)
  const actions = asRecord(raw.actions)
  const backups = rows(raw.backups)
  const components = rows(status.configuredComponents)
  const defaults = useMemo(() => defaultComponents(components), [components])
  const [selected, setSelected] = useState(restoreIdFromPath)
  const [type, setType] = useState('COMPLETO')
  const [note, setNote] = useState('')
  const [chosen, setChosen] = useState<string[]>(defaults)
  const [confirmCreate, setConfirmCreate] = useState(false)
  const [confirmVerify, setConfirmVerify] = useState(false)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState('')
  const [restoreFolder, setRestoreFolder] = useState('')
  const [restoreOverwrite, setRestoreOverwrite] = useState(false)
  const [restoreParts, setRestoreParts] = useState<string[]>([])
  const [confirmRestore, setConfirmRestore] = useState(false)
  const selectedId = selected || text(backups[0]?.id)
  const selectedBackup = backups.find((item) => text(item.id) === selectedId)
  const selectedParts = Array.isArray(selectedBackup?.components) ? (selectedBackup?.components as unknown[]).map((item) => text(item)).filter(Boolean) : []
  const canCreate = Boolean(actions.canCreate || data.permissions.can_manage_backup)
  const canVerify = Boolean(actions.canVerify || data.permissions.can_manage_backup)
  const canDownload = Boolean(actions.canDownload)

  async function runCreate() {
    setBusy('create')
    const result = await createBackup({ type, note, components: chosen.length ? chosen : defaults, confirm: confirmCreate })
    setBusy('')
    setMessage(result.message)
    setConfirmCreate(false)
    if (result.ok) onReload()
  }

  async function runVerify() {
    setBusy('verify')
    const result = await verifyBackupIntegrity({ backupId: selectedId, confirm: confirmVerify })
    setBusy('')
    setMessage(result.message)
    setConfirmVerify(false)
    if (result.ok) onReload()
  }

  async function runRestore() {
    setBusy('restore')
    const result = await restoreBackup({
      backupId: selectedId,
      folder: restoreFolder.trim(),
      components: restoreParts,
      overwrite: restoreOverwrite,
      confirm: confirmRestore,
    })
    setBusy('')
    setMessage([result.message, ...Object.values(result.errors)].filter(Boolean).join(' '))
    setConfirmRestore(false)
  }

  function toggleRestorePart(id: string, checked: boolean) {
    setRestoreParts((current) => checked ? Array.from(new Set([...current, id])) : current.filter((item) => item !== id))
  }

  function toggleComponent(id: string, checked: boolean) {
    setChosen((current) => checked ? Array.from(new Set([...current, id])) : current.filter((item) => item !== id))
  }

  return (
    <div className="iu-backup-settings">
      <div className="iu-backup-settings__metrics">
        <span><strong>{text(status.total || 0)}</strong> copie totali</span>
        <span><strong>{text(status.completed || 0)}</strong> completate</span>
        <span><strong>{text((number(status.failed) + number(status.corrupted)) || 0)}</strong> da verificare</span>
        <span><strong>{formatSize(status.totalSizeMb)}</strong> spazio usato</span>
      </div>

      {message ? <p className="iu-backup-settings__message">{message}</p> : null}

      <section className="iu-backup-settings__box">
        <header><Archive aria-hidden="true" /><strong>Crea copia</strong><IusStatusBadge tone={canCreate ? 'success' : 'warning'}>{canCreate ? 'pronto' : 'permesso richiesto'}</IusStatusBadge></header>
        <div className="iu-backup-settings__grid">
          <label><span>Tipo copia</span><select value={type} disabled={!canCreate || busy === 'create'} onChange={(event) => setType(event.currentTarget.value)}><option value="COMPLETO">Completa</option><option value="INCREMENTALE">Incrementale</option></select></label>
          <label><span>Nota</span><Textarea value={note} maxLength={240} disabled={!canCreate || busy === 'create'} onChange={(event) => setNote(event.currentTarget.value)} /></label>
        </div>
        <div className="iu-backup-settings__checks" aria-label="Dati inclusi nella copia">
          {components.map((item) => {
            const id = text(item.id)
            return <label key={id}><input type="checkbox" checked={chosen.includes(id)} disabled={!canCreate || busy === 'create'} onChange={(event) => toggleComponent(id, event.currentTarget.checked)} /><span>{text(item.label) || id}</span></label>
          })}
        </div>
        <label className="iu-backup-settings__confirm"><input type="checkbox" checked={confirmCreate} disabled={!canCreate || busy === 'create'} onChange={(event) => setConfirmCreate(event.currentTarget.checked)} /><span>Confermo la creazione della copia</span></label>
        <Button type="button" disabled={!canCreate || !confirmCreate || busy === 'create'} onClick={() => void runCreate()}><Play data-icon="inline-start" />{busy === 'create' ? 'Creazione...' : 'Crea copia'}</Button>
      </section>

      <section className="iu-backup-settings__box">
        <header><ShieldCheck aria-hidden="true" /><strong>Verifica copia</strong><IusStatusBadge tone="info">{text(asRecord(raw.integrity).label || 'stato disponibile')}</IusStatusBadge></header>
        <div className="iu-backup-settings__grid">
          <label><span>Copia</span><select value={selectedId} disabled={!canVerify || busy === 'verify' || !backups.length} onChange={(event) => setSelected(event.currentTarget.value)}>{backups.map((item) => <option value={text(item.id)} key={text(item.id)}>{formatDate(item.createdAt)} - {text(item.fileName || item.id)}</option>)}</select></label>
          <label><span>Cerca copia</span><Input value={selected} disabled={!backups.length} placeholder="Seleziona dalla lista" onChange={(event) => setSelected(event.currentTarget.value)} /></label>
        </div>
        <label className="iu-backup-settings__confirm"><input type="checkbox" checked={confirmVerify} disabled={!canVerify || busy === 'verify' || !selectedId} onChange={(event) => setConfirmVerify(event.currentTarget.checked)} /><span>Confermo la verifica della copia selezionata</span></label>
        <Button type="button" variant="outline" disabled={!canVerify || !confirmVerify || busy === 'verify' || !selectedId} onClick={() => void runVerify()}><CheckCircle2 data-icon="inline-start" />Verifica</Button>
      </section>

      <section className="iu-backup-settings__box" id="ripristino-backup">
        <header><ArchiveRestore aria-hidden="true" /><strong>Ripristina copia</strong><IusStatusBadge tone="info">in una cartella dedicata</IusStatusBadge></header>
        <p className="iu-backup-settings__hint">Il contenuto della copia selezionata viene estratto in «ripristini/nome-cartella» accanto ai backup, per controllarlo prima di usarlo: i dati in uso non vengono toccati. Le copie cifrate si aprono con la chiave dei backup configurata per lo studio.</p>
        <div className="iu-backup-settings__grid">
          <label><span>Copia</span><select value={selectedId} disabled={!canVerify || busy === 'restore' || !backups.length} onChange={(event) => { setSelected(event.currentTarget.value); setRestoreParts([]) }}>{backups.map((item) => <option value={text(item.id)} key={text(item.id)}>{formatDate(item.createdAt)} - {text(item.fileName || item.id)}</option>)}</select></label>
          <label><span>Nome della cartella</span><Input value={restoreFolder} maxLength={64} disabled={!canVerify || busy === 'restore'} placeholder="ripristino-aaaammgg (automatico se vuoto)" onChange={(event) => setRestoreFolder(event.currentTarget.value)} /></label>
        </div>
        {selectedParts.length ? (
          <div className="iu-backup-settings__checks" aria-label="Parti da ripristinare (nessuna selezione = tutte)">
            {selectedParts.map((id) => <label key={id}><input type="checkbox" checked={restoreParts.includes(id)} disabled={!canVerify || busy === 'restore'} onChange={(event) => toggleRestorePart(id, event.currentTarget.checked)} /><span>{id}</span></label>)}
          </div>
        ) : null}
        <label className="iu-backup-settings__confirm"><input type="checkbox" checked={restoreOverwrite} disabled={!canVerify || busy === 'restore'} onChange={(event) => setRestoreOverwrite(event.currentTarget.checked)} /><span>Sovrascrivi i file già presenti nella cartella</span></label>
        <label className="iu-backup-settings__confirm"><input type="checkbox" checked={confirmRestore} disabled={!canVerify || busy === 'restore' || !selectedId} onChange={(event) => setConfirmRestore(event.currentTarget.checked)} /><span>Confermo il ripristino della copia selezionata</span></label>
        <Button type="button" variant="outline" disabled={!canVerify || !confirmRestore || busy === 'restore' || !selectedId} onClick={() => void runRestore()}><ArchiveRestore data-icon="inline-start" />{busy === 'restore' ? 'Ripristino...' : 'Ripristina'}</Button>
      </section>

      <section className="iu-backup-settings__box">
        <header><RefreshCw aria-hidden="true" /><strong>Copie disponibili</strong><span>{backups.length} nel registro</span></header>
        <div className="iu-backup-settings__list">
          {backups.length ? backups.slice(0, 8).map((item) => (
            <article key={text(item.id)}>
              <div><b>{text(item.fileName || item.id)}</b><span>{formatDate(item.createdAt)} - {formatSize(item.sizeMb)} - {text(item.stateLabel)}</span></div>
              {canDownload && text(item.downloadHref) ? <a href={text(item.downloadHref)}><Download size={15} />Scarica</a> : <IusStatusBadge tone="neutral">protetta</IusStatusBadge>}
            </article>
          )) : <p>Nessuna copia backup registrata.</p>}
        </div>
      </section>
    </div>
  )
}
