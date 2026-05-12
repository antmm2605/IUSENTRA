import { useState } from 'react'
import {
  AlertTriangle,
  CalendarCheck2,
  CalendarPlus,
  Cloud,
  Copy,
  Globe2,
  KeyRound,
  PlayCircle,
  RefreshCw,
  ShieldCheck,
  Trash2,
  Unplug,
} from 'lucide-react'
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
  connectAppleCalendar,
  connectCalendarProof,
  connectGoogleCalendar,
  connectMicrosoftCalendar,
  connectWebcalCalendar,
  deleteCalendarProfile,
  disconnectCalendarAccount,
  regenerateCalendarLinks,
  resolveCalendarConflict,
  syncCalendarAccount,
  syncCalendarProfile,
  toggleCalendarProfile,
  toggleLinkedCalendar,
} from '../api'
import type { CalendarActionPayload, SettingsPayload } from '../types'
import './CalendarSettingsPanel.css'

type Row = Record<string, unknown>
type CalendarResult = CalendarActionPayload & { auth_url?: string }
type BadgeTone = 'primary' | 'success' | 'warning' | 'danger' | 'neutral' | 'info'

// createCalendarProfile resta disponibile negli endpoint storici; i nuovi WebCal passano dal motore calendario.

function asRecord(value: unknown): Row {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Row : {}
}

function rows(value: unknown): Row[] {
  return Array.isArray(value) ? value.filter((item) => item && typeof item === 'object') as Row[] : []
}

function text(value: unknown): string {
  return value === undefined || value === null ? '' : String(value)
}

function numberText(value: unknown): string {
  const parsed = Number(value || 0)
  return Number.isFinite(parsed) ? String(parsed) : '0'
}

function feedItems(raw: Row): Array<{ id: string; label: string; value: string }> {
  const feeds = asRecord(raw.feeds)
  return [
    { id: 'completo', label: 'Agenda e scadenze', value: text(feeds.completo) },
    { id: 'agenda', label: 'Solo agenda', value: text(feeds.agenda) },
    { id: 'scadenze', label: 'Solo scadenze', value: text(feeds.scadenze) },
  ].filter((item) => item.value)
}

function tone(value: unknown): BadgeTone {
  const raw = text(value)
  return ['primary', 'success', 'warning', 'danger', 'neutral', 'info'].includes(raw) ? raw as BadgeTone : 'neutral'
}

function summaryText(value: unknown): string {
  const item = asRecord(value)
  return [text(item.title), text(item.when), text(item.status)].filter(Boolean).join(' - ')
}

export function CalendarSettingsPanel({ data, onReload }: { data: SettingsPayload; onReload: () => void }) {
  const raw = asRecord(data.calendari)
  const profiles = rows(raw.profiles)
  const accounts = rows(raw.accounts)
  const linkedCalendars = rows(raw.connected_calendars)
  const conflicts = rows(raw.conflicts)
  const canUpdate = Boolean(raw.can_update || data.permissions.can_manage_calendar || data.permissions.can_update)
  const [webcalForm, setWebcalForm] = useState({ nome: '', source_url: '', default_tipo: 'ALTRO', default_reminder_minuti: '60' })
  const [appleForm, setAppleForm] = useState({ display_name: 'Apple iCloud', server_url: '', username: '', password: '', calendar_name: 'Calendario iCloud' })
  const [busy, setBusy] = useState('')
  const [message, setMessage] = useState('')

  async function copy(value: string) {
    await navigator.clipboard?.writeText(value)
    setMessage('Link copiato.')
  }

  async function run(action: () => Promise<CalendarResult>, marker: string) {
    setBusy(marker)
    const result = await action()
    setBusy('')
    setMessage(result.message)
    const authUrl = text(result.auth_url)
    if (result.ok && authUrl) {
      window.location.assign(authUrl)
      return
    }
    if (result.ok) onReload()
  }

  function updateWebcal(name: keyof typeof webcalForm, value: string) {
    setWebcalForm((current) => ({ ...current, [name]: value }))
  }

  function updateApple(name: keyof typeof appleForm, value: string) {
    setAppleForm((current) => ({ ...current, [name]: value }))
  }

  return (
    <div className="iu-calendar-settings">
      <div className="iu-calendar-settings__metrics">
        <span><strong>{numberText(raw.profile_count)}</strong> calendari collegati</span>
        <span><strong>{numberText(raw.active_profiles)}</strong> attivi</span>
        <span><strong>{numberText(raw.agenda_count)}</strong> appuntamenti</span>
        <span><strong>{numberText(raw.deadline_count)}</strong> scadenze</span>
      </div>

      {message ? <p className="iu-calendar-settings__message">{message}</p> : null}

      <section className="iu-calendar-settings__box">
        <header><Cloud aria-hidden="true" /><strong>Collega account</strong><IusStatusBadge tone={canUpdate ? 'success' : 'warning'}>{canUpdate ? 'pronto' : 'permesso richiesto'}</IusStatusBadge></header>
        <div className="iu-calendar-settings__connectors">
          <Button type="button" variant="outline" disabled={!canUpdate || busy === 'google'} onClick={() => void run(connectGoogleCalendar, 'google')}><Globe2 data-icon="inline-start" />Google Calendar</Button>
          <Button type="button" variant="outline" disabled={!canUpdate || busy === 'microsoft'} onClick={() => void run(connectMicrosoftCalendar, 'microsoft')}><Cloud data-icon="inline-start" />Outlook / Microsoft 365</Button>
          <Button type="button" variant="outline" disabled={!canUpdate || busy === 'proof'} onClick={() => void run(connectCalendarProof, 'proof')}><PlayCircle data-icon="inline-start" />Ambiente prova locale</Button>
        </div>
        <div className="iu-calendar-settings__split">
          <div className="iu-calendar-settings__mini-form">
            <h4><CalendarPlus aria-hidden="true" />Aggiungi WebCal / ICS</h4>
            <label><span>Nome</span><Input value={webcalForm.nome} disabled={!canUpdate} placeholder="Calendario udienze" onChange={(event) => updateWebcal('nome', event.currentTarget.value)} /></label>
            <label><span>Link calendario</span><Input value={webcalForm.source_url} disabled={!canUpdate} placeholder="https://... oppure webcal://..." onChange={(event) => updateWebcal('source_url', event.currentTarget.value)} /></label>
            <div className="iu-calendar-settings__compact-grid">
              <label><span>Tipo predefinito</span><Select value={webcalForm.default_tipo} disabled={!canUpdate} onValueChange={(value) => updateWebcal('default_tipo', value)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="ALTRO">Altro</SelectItem><SelectItem value="UDIENZA">Udienza</SelectItem><SelectItem value="CONSULTAZIONE">Consultazione</SelectItem><SelectItem value="RIUNIONE">Riunione</SelectItem><SelectItem value="SCADENZA">Scadenza</SelectItem><SelectItem value="DEPOSITO">Deposito</SelectItem></SelectGroup></SelectContent></Select></label>
              <label><span>Minuti prima</span><Input value={webcalForm.default_reminder_minuti} disabled={!canUpdate} type="number" min={0} onChange={(event) => updateWebcal('default_reminder_minuti', event.currentTarget.value)} /></label>
            </div>
            <Button type="button" disabled={!canUpdate || !webcalForm.source_url || busy === 'webcal'} onClick={() => void run(() => connectWebcalCalendar({ ...webcalForm, provider: 'webcal' }), 'webcal')}>Aggiungi calendario</Button>
          </div>
          <div className="iu-calendar-settings__mini-form">
            <h4><KeyRound aria-hidden="true" />Collega Apple iCloud</h4>
            <label><span>Nome account</span><Input value={appleForm.display_name} disabled={!canUpdate} onChange={(event) => updateApple('display_name', event.currentTarget.value)} /></label>
            <label><span>Indirizzo CalDAV</span><Input value={appleForm.server_url} disabled={!canUpdate} placeholder="https://caldav.icloud.com" onChange={(event) => updateApple('server_url', event.currentTarget.value)} /></label>
            <div className="iu-calendar-settings__compact-grid">
              <label><span>Utente iCloud</span><Input value={appleForm.username} disabled={!canUpdate} autoComplete="username" onChange={(event) => updateApple('username', event.currentTarget.value)} /></label>
              <label><span>Password per app</span><Input value={appleForm.password} disabled={!canUpdate} type="password" autoComplete="new-password" onChange={(event) => updateApple('password', event.currentTarget.value)} /></label>
            </div>
            <Button type="button" disabled={!canUpdate || !appleForm.server_url || !appleForm.username || !appleForm.password || busy === 'apple'} onClick={() => void run(() => connectAppleCalendar(appleForm), 'apple')}>Collega iCloud</Button>
          </div>
        </div>
      </section>

      <section className="iu-calendar-settings__box">
        <header><ShieldCheck aria-hidden="true" /><strong>Calendari collegati</strong><span>{linkedCalendars.length} calendari</span></header>
        <div className="iu-calendar-settings__linked">
          {linkedCalendars.length ? linkedCalendars.map((calendar) => {
            const id = text(calendar.id)
            const accountId = text(calendar.account_id)
            return (
              <article key={id}>
                <div className="iu-calendar-settings__linked-main">
                  <b>{text(calendar.name)}</b>
                  <span>{text(calendar.provider_label)} - {text(calendar.account)} - {text(calendar.direction_label)}</span>
                  <small>{text(calendar.role_label)} - riservatezza {text(calendar.privacy_label).toLowerCase()} - ultimo allineamento {text(calendar.last_sync_at)}</small>
                  {text(calendar.last_error) ? <em>{text(calendar.last_error)}</em> : null}
                </div>
                <div className="iu-calendar-settings__row-actions">
                  <IusStatusBadge tone={tone(calendar.status_tone)}>{text(calendar.status_label)}</IusStatusBadge>
                  <Button type="button" variant="outline" disabled={!canUpdate || busy === accountId} onClick={() => void run(() => syncCalendarAccount(accountId), accountId)}>Allinea ora</Button>
                  <Button type="button" variant="outline" disabled={!canUpdate || busy === id} onClick={() => void run(() => toggleLinkedCalendar(id), id)}>{calendar.enabled ? 'Metti in pausa' : 'Riattiva'}</Button>
                  <Button type="button" variant="ghost" disabled={!canUpdate || busy === accountId} aria-label="Scollega account" onClick={() => void run(() => disconnectCalendarAccount(accountId), accountId)}><Unplug aria-hidden="true" /></Button>
                </div>
              </article>
            )
          }) : <p>Nessun calendario bidirezionale collegato.</p>}
        </div>
      </section>

      <section className="iu-calendar-settings__box">
        <header><AlertTriangle aria-hidden="true" /><strong>Conflitti calendario</strong><span>{conflicts.length} aperti</span></header>
        <div className="iu-calendar-settings__conflicts">
          {conflicts.length ? conflicts.map((conflict) => {
            const id = text(conflict.id)
            return (
              <article key={id}>
                <div>
                  <b>{text(conflict.conflict_label)}</b>
                  <span>IUSENTRA: {summaryText(conflict.local_summary)}</span>
                  <span>Calendario esterno: {summaryText(conflict.remote_summary)}</span>
                </div>
                <div className="iu-calendar-settings__row-actions">
                  <Button type="button" variant="outline" disabled={!canUpdate || busy === `${id}-local`} onClick={() => void run(() => resolveCalendarConflict(id, 'use_local'), `${id}-local`)}>Usa IUSENTRA</Button>
                  <Button type="button" variant="outline" disabled={!canUpdate || busy === `${id}-remote`} onClick={() => void run(() => resolveCalendarConflict(id, 'use_remote'), `${id}-remote`)}>Usa calendario esterno</Button>
                  <Button type="button" variant="ghost" disabled={!canUpdate || busy === `${id}-ignore`} onClick={() => void run(() => resolveCalendarConflict(id, 'ignore'), `${id}-ignore`)}>Ignora</Button>
                </div>
              </article>
            )
          }) : <p>Nessun conflitto aperto.</p>}
        </div>
      </section>

      <section className="iu-calendar-settings__box">
        <header><CalendarCheck2 aria-hidden="true" /><strong>Link riservati da sottoscrivere</strong><IusStatusBadge tone="info">lettura</IusStatusBadge></header>
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
        <header><RefreshCw aria-hidden="true" /><strong>Sottoscrizioni in sola lettura</strong><span>{profiles.length} calendari</span></header>
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
          }) : <p>Nessuna sottoscrizione in sola lettura collegata.</p>}
        </div>
      </section>
    </div>
  )
}
