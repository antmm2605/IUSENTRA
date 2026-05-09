import { useState } from 'react'
import { CalendarCheck2, Copy, RefreshCw, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { IusStatusBadge } from '@/components/iusentra'
import {
  createCalendarProfile,
  deleteCalendarProfile,
  regenerateCalendarLinks,
  syncCalendarProfile,
  toggleCalendarProfile,
} from '../api'
import type { SettingsPayload } from '../types'
import './CalendarSettingsPanel.css'

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

function feedItems(raw: Row): Array<{ id: string; label: string; value: string }> {
  const feeds = asRecord(raw.feeds)
  return [
    { id: 'completo', label: 'Agenda e scadenze', value: text(feeds.completo) },
    { id: 'agenda', label: 'Solo agenda', value: text(feeds.agenda) },
    { id: 'scadenze', label: 'Solo scadenze', value: text(feeds.scadenze) },
  ].filter((item) => item.value)
}

export function CalendarSettingsPanel({ data, onReload }: { data: SettingsPayload; onReload: () => void }) {
  const raw = asRecord(data.calendari)
  const profiles = rows(raw.profiles)
  const canUpdate = Boolean(raw.can_update || data.permissions.can_manage_calendar || data.permissions.can_update)
  const [form, setForm] = useState({ nome: '', provider: 'webcal', source_url: '', default_tipo: 'ALTRO', default_reminder_minuti: '60' })
  const [busy, setBusy] = useState('')
  const [message, setMessage] = useState('')

  async function copy(value: string) {
    await navigator.clipboard?.writeText(value)
    setMessage('Link copiato.')
  }

  async function run(action: () => Promise<{ ok: boolean; message: string }>, marker: string) {
    setBusy(marker)
    const result = await action()
    setBusy('')
    setMessage(result.message)
    if (result.ok) onReload()
  }

  function update(name: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [name]: value }))
  }

  return (
    <div className="iu-calendar-settings">
      <div className="iu-calendar-settings__metrics">
        <span><strong>{text(raw.profile_count || 0)}</strong> calendari collegati</span>
        <span><strong>{text(raw.active_profiles || 0)}</strong> attivi</span>
        <span><strong>{text(raw.agenda_count || 0)}</strong> appuntamenti</span>
        <span><strong>{text(raw.deadline_count || 0)}</strong> scadenze</span>
      </div>

      {message ? <p className="iu-calendar-settings__message">{message}</p> : null}

      <section className="iu-calendar-settings__box">
        <header><CalendarCheck2 aria-hidden="true" /><strong>Link da aggiungere al calendario</strong><IusStatusBadge tone="info">riservati</IusStatusBadge></header>
        <div className="iu-calendar-settings__feeds">
          {feedItems(raw).map((item) => (
            <article key={item.id}>
              <div><b>{item.label}</b><span>{item.value}</span></div>
              <Button type="button" variant="outline" onClick={() => void copy(item.value)}><Copy data-icon="inline-start" />Copia</Button>
            </article>
          ))}
        </div>
        <div className="iu-calendar-settings__actions">
          {text(raw.google_url) ? <a href={text(raw.google_url)} target="_blank" rel="noreferrer">Apri in Google Calendar</a> : null}
        <Button type="button" variant="outline" disabled={!canUpdate || busy === 'links'} onClick={() => void run(regenerateCalendarLinks, 'links')}><RefreshCw data-icon="inline-start" />Rigenera link</Button>
        </div>
      </section>

      <section className="iu-calendar-settings__box">
        <header><CalendarCheck2 aria-hidden="true" /><strong>Aggiungi calendario esterno</strong><IusStatusBadge tone={canUpdate ? 'success' : 'warning'}>{canUpdate ? 'pronto' : 'permesso richiesto'}</IusStatusBadge></header>
        <div className="iu-calendar-settings__grid">
          <label><span>Nome</span><Input value={form.nome} disabled={!canUpdate} placeholder="Agenda personale" onChange={(event) => update('nome', event.currentTarget.value)} /></label>
          <label><span>Tipo calendario</span><Select value={form.provider} disabled={!canUpdate} onValueChange={(value) => update('provider', value)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="google">Google Calendar</SelectItem><SelectItem value="outlook">Microsoft Outlook</SelectItem><SelectItem value="apple">Apple Calendar</SelectItem><SelectItem value="webcal">Altro calendario</SelectItem></SelectGroup></SelectContent></Select></label>
          <label className="is-wide"><span>Link calendario</span><Input value={form.source_url} disabled={!canUpdate} placeholder="https://... oppure webcal://..." onChange={(event) => update('source_url', event.currentTarget.value)} /></label>
          <label><span>Tipo appuntamento</span><Select value={form.default_tipo} disabled={!canUpdate} onValueChange={(value) => update('default_tipo', value)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="ALTRO">Altro</SelectItem><SelectItem value="UDIENZA">Udienza</SelectItem><SelectItem value="CONSULTAZIONE">Consultazione</SelectItem><SelectItem value="RIUNIONE">Riunione</SelectItem><SelectItem value="SCADENZA">Scadenza</SelectItem><SelectItem value="DEPOSITO">Deposito</SelectItem></SelectGroup></SelectContent></Select></label>
          <label><span>Minuti prima</span><Input value={form.default_reminder_minuti} disabled={!canUpdate} type="number" min={0} onChange={(event) => update('default_reminder_minuti', event.currentTarget.value)} /></label>
        </div>
        <Button type="button" disabled={!canUpdate || !form.source_url || busy === 'create'} onClick={() => void run(() => createCalendarProfile(form), 'create')}>Aggiungi calendario</Button>
      </section>

      <section className="iu-calendar-settings__box">
        <header><RefreshCw aria-hidden="true" /><strong>Calendari collegati</strong><span>{profiles.length} calendari</span></header>
        <div className="iu-calendar-settings__profiles">
          {profiles.length ? profiles.map((profile) => {
            const id = text(profile.id)
            return (
              <article key={id}>
                <div><b>{text(profile.nome)}</b><span>{text(profile.provider_label)} - {text(profile.last_sync_at)} - {text(profile.status_label)}</span></div>
                <div className="iu-calendar-settings__row-actions">
                  <Button type="button" variant="outline" disabled={!canUpdate || busy === id} onClick={() => void run(() => syncCalendarProfile(id), id)}>Aggiorna ora</Button>
                  <Button type="button" variant="outline" disabled={!canUpdate || busy === id} onClick={() => void run(() => toggleCalendarProfile(id), id)}>{profile.enabled ? 'Disattiva' : 'Attiva'}</Button>
                  <Button type="button" variant="ghost" disabled={!canUpdate || busy === id} aria-label="Elimina calendario" onClick={() => void run(() => deleteCalendarProfile(id), id)}><Trash2 aria-hidden="true" /></Button>
                </div>
              </article>
            )
          }) : <p>Nessun calendario esterno collegato.</p>}
        </div>
      </section>
    </div>
  )
}
