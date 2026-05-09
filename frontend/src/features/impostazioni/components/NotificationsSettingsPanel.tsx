import { useEffect, useMemo, useState } from 'react'
import { Bell, ExternalLink, MessageCircle, RefreshCw, Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { IusStatusBadge } from '@/components/iusentra'
import { prepareNotificationLink, sendNotification, sendTomorrowReminders } from '../api'
import type { NotificationActionPayload, SettingsPayload, SettingsSection } from '../types'
import './NotificationsSettingsPanel.css'

type Values = Record<string, unknown>

function asRecord(value: unknown): Values {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Values : {}
}

function text(value: unknown): string {
  if (value === undefined || value === null) return ''
  return String(value)
}

function rows(value: unknown): Values[] {
  return Array.isArray(value) ? value.filter((item) => item && typeof item === 'object') as Values[] : []
}

function firstClientId(list: Values[]): string {
  return text(list[0]?.id)
}

export function NotificationsSettingsPanel({
  data,
  onReload,
  onOpenSection,
}: {
  data: SettingsPayload
  onReload: () => void
  onOpenSection: (section: SettingsSection) => void
}) {
  const raw = asRecord(data.notifiche)
  const clients = rows(raw.clienti)
  const appointments = rows(raw.appuntamenti_domani)
  const log = rows(raw.registro)
  const channel = asRecord(raw.channel)
  const canSend = Boolean(raw.can_send || data.permissions.can_send_notifications || data.permissions.can_update)
  const [clientId, setClientId] = useState(() => firstClientId(clients))
  const [message, setMessage] = useState('')
  const [link, setLink] = useState('')
  const [result, setResult] = useState<NotificationActionPayload | null>(null)
  const [busy, setBusy] = useState('')

  useEffect(() => {
    if (!clientId && clients.length) setClientId(firstClientId(clients))
  }, [clientId, clients])

  const selected = useMemo(() => clients.find((client) => text(client.id) === clientId), [clientId, clients])
  const actionPayload = { id_cliente: clientId, numero: selected?.numero || '', testo: message }

  async function run(action: 'link' | 'send' | 'reminders') {
    setBusy(action)
    setResult(null)
    const response = action === 'link'
      ? await prepareNotificationLink(actionPayload)
      : action === 'send'
        ? await sendNotification(actionPayload)
        : await sendTomorrowReminders()
    setBusy('')
    setResult(response)
    if (response.link) setLink(response.link)
    if (response.ok && action !== 'link') onReload()
  }

  return (
    <div className="iu-notify-panel">
      <div className="iu-notify-metrics">
        <span><strong>{text(raw.clienti_con_numero || 0)}</strong> clienti con WhatsApp</span>
        <span><strong>{text(raw.appuntamenti_inviabili || 0)}</strong> promemoria pronti</span>
        <span><strong>{text(raw.registro_totale || 0)}</strong> messaggi nel registro</span>
      </div>

      <section className="iu-notify-compose">
        <header>
          <MessageCircle aria-hidden="true" />
          <div>
            <strong>Messaggio cliente</strong>
            <span>{text(channel.detail || 'Il gestionale prepara il messaggio WhatsApp.')}</span>
          </div>
          <IusStatusBadge tone={channel.automatico ? 'success' : 'info'}>{text(channel.label || 'WhatsApp disponibile')}</IusStatusBadge>
        </header>
        <label className="iu-notify-field">
          <span>Cliente</span>
          <Select value={clientId} disabled={!canSend || !clients.length} onValueChange={setClientId}>
            <SelectTrigger><SelectValue placeholder="Seleziona cliente" /></SelectTrigger>
            <SelectContent><SelectGroup>{clients.map((client) => <SelectItem value={text(client.id)} key={text(client.id)}>{text(client.nome)}</SelectItem>)}</SelectGroup></SelectContent>
          </Select>
        </label>
        <label className="iu-notify-field">
          <span>Testo messaggio</span>
          <Textarea value={message} disabled={!canSend} placeholder="Scrivi il messaggio da inviare al cliente." onChange={(event) => setMessage(event.currentTarget.value)} />
        </label>
        {Array.isArray(raw.quick_texts) && raw.quick_texts.length ? (
          <div className="iu-notify-quick" aria-label="Testi rapidi">
            {raw.quick_texts.map((item) => <Button type="button" variant="outline" key={text(item)} onClick={() => setMessage(text(item))}>{text(item)}</Button>)}
          </div>
        ) : null}
        <div className="iu-notify-actions">
          <Button type="button" variant="outline" disabled={!canSend || !message || busy === 'link'} onClick={() => void run('link')}>
            <ExternalLink data-icon="inline-start" />
            Prepara link WhatsApp
          </Button>
          <Button type="button" disabled={!canSend || !message || busy === 'send'} onClick={() => void run('send')}>
            <Send data-icon="inline-start" />
            {busy === 'send' ? 'Invio...' : 'Invia messaggio'}
          </Button>
          <Button type="button" variant="outline" onClick={() => onOpenSection('whatsapp')}>
            <Bell data-icon="inline-start" />
            Configura WhatsApp
          </Button>
        </div>
        {link ? <a className="iu-notify-link" href={link} target="_blank" rel="noreferrer">Apri WhatsApp</a> : null}
        {result ? <p className={result.ok ? 'iu-notify-result is-ok' : 'iu-notify-result is-ko'}>{result.message}</p> : null}
      </section>

      <section className="iu-notify-compose">
        <header>
          <Bell aria-hidden="true" />
          <div><strong>Promemoria di domani</strong><span>Invia o prepara i messaggi per gli appuntamenti con numero disponibile.</span></div>
          <Button type="button" variant="outline" disabled={!canSend || busy === 'reminders'} onClick={() => void run('reminders')}>
            <RefreshCw data-icon="inline-start" />
            {busy === 'reminders' ? 'Preparazione...' : 'Invia promemoria'}
          </Button>
        </header>
        <div className="iu-notify-list">
          {appointments.length ? appointments.map((item) => <p key={text(item.id)}><b>{text(item.ora)} - {text(item.titolo)}</b><span>{text(item.cliente) || 'Cliente non collegato'} {item.inviabile ? '' : '- numero mancante'}</span></p>) : <p>Nessun appuntamento con promemoria per domani.</p>}
        </div>
      </section>

      <section className="iu-notify-compose">
        <header><Bell aria-hidden="true" /><div><strong>Registro notifiche</strong><span>Ultimi messaggi preparati o inviati dallo studio.</span></div></header>
        <div className="iu-notify-list">
          {log.length ? log.map((item) => <p key={text(item.id)}><b>{text(item.quando)} - {text(item.cliente)}</b><span>{text(item.stato)}</span></p>) : <p>Nessuna notifica registrata.</p>}
        </div>
      </section>
    </div>
  )
}
