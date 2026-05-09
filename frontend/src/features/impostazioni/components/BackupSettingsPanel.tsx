import { useMemo, useState } from 'react'
import { Archive, CheckCircle2, Download, Play, RefreshCw, ShieldCheck } from 'lucide-react'
import { createBackup, verifyBackupIntegrity } from '@/backupData'
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
  return new Intl.DateTimeFormat('it-IT', { dateStyle: 'short', timeStyle: 'short' }).format(parsed)
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
  const [selected, setSelected] = useState('')
  const [type, setType] = useState('COMPLETO')
  const [note, setNote] = useState('')
  const [chosen, setChosen] = useState<string[]>(defaults)
  const [confirmCreate, setConfirmCreate] = useState(false)
  const [confirmVerify, setConfirmVerify] = useState(false)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState('')
  const selectedId = selected || text(backups[0]?.id)
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
