import { useEffect, useMemo, useState } from 'react'
import { Bell, BellRing, ExternalLink, MessageCircle, RefreshCw, Send, Smartphone } from 'lucide-react'
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
import {
  activatePushNotifications,
  deactivatePushNotifications,
  getPushDeviceStatus,
  sendPushTest,
  type PushActionResult,
  type PushDeviceStatus,
} from '@/lib/pushNotifications'
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

const initialPushStatus: PushDeviceStatus = {
  supported: false,
  enabled: true,
  configured: false,
  active: false,
  permission: 'unsupported',
  message: 'Verifica notifiche in corso.',
}

function pushTone(status: PushDeviceStatus): 'success' | 'warning' | 'neutral' | 'info' {
  if (status.active) return 'success'
  if (!status.supported || !status.configured || status.permission === 'denied') return 'warning'
  return 'info'
}

function pushLabel(status: PushDeviceStatus): string {
  if (!status.supported) return 'Non supportato'
  if (status.enabled === false) return 'Non attive'
  if (!status.configured) return 'Da configurare'
  if (status.permission === 'denied') return 'Bloccato dal dispositivo'
  return status.active ? 'Attivo' : 'Disattivo'
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
  const operationalAlerts = rows(raw.avvisi_operativi)
  const channel = asRecord(raw.channel)
  const canSend = Boolean(raw.can_send || data.permissions.can_send_notifications || data.permissions.can_update)
  const canConfigureServer = Boolean(data.permissions.can_update)
  const [clientId, setClientId] = useState(() => firstClientId(clients))
  const [message, setMessage] = useState('')
  const [link, setLink] = useState('')
  const [result, setResult] = useState<NotificationActionPayload | null>(null)
  const [busy, setBusy] = useState('')
  const [pushStatus, setPushStatus] = useState<PushDeviceStatus>(initialPushStatus)
  const [pushBusy, setPushBusy] = useState('')
  const [pushResult, setPushResult] = useState<PushActionResult | null>(null)

  useEffect(() => {
    if (!clientId && clients.length) setClientId(firstClientId(clients))
  }, [clientId, clients])

  async function refreshPushStatus() {
    const status = await new Promise<PushDeviceStatus | null>((resolve) => {
      let completed = false
      const finish = (value: PushDeviceStatus | null) => {
        if (completed) return
        completed = true
        window.clearTimeout(timeoutId)
        resolve(value)
      }
      const timeoutId = window.setTimeout(() => finish(null), 6_000)
      void getPushDeviceStatus()
        .then((value) => finish(value))
        .catch(() => finish(null))
    })
    if (status) setPushStatus(status)
  }

  useEffect(() => {
    void refreshPushStatus()
  }, [])

  const selected = useMemo(() => clients.find((client) => text(client.id) === clientId), [clientId, clients])
  const actionPayload = { id_cliente: clientId, numero: selected?.numero || '', testo: message }
  const serverNotConfigured = pushStatus.supported && pushStatus.enabled !== false && !pushStatus.configured
  const pushDeviceMessage = serverNotConfigured
    ? canConfigureServer
      ? 'Sistema notifiche non ancora configurato.'
      : "Le notifiche su dispositivo non sono ancora state abilitate dall'amministratore."
    : pushStatus.message

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

  async function runPush(action: 'activate' | 'deactivate' | 'test') {
    setPushBusy(action)
    setPushResult(null)
    try {
      const response = action === 'activate'
        ? await activatePushNotifications()
        : action === 'deactivate'
          ? await deactivatePushNotifications()
          : await sendPushTest()
      setPushResult(response)
      if (typeof response.active === 'boolean') {
        setPushStatus((current) => ({
          ...current,
          supported: true,
          configured: true,
          active: response.active === true,
          permission: response.active ? 'granted' : current.permission,
          message: response.message,
        }))
      }
      await refreshPushStatus()
    } catch {
      setPushResult({ ok: false, message: 'Operazione notifiche non completata. Riprova dal dispositivo in uso.' })
    } finally {
      setPushBusy('')
    }
  }

  return (
    <div className="iu-notify-panel">
      <div className="iu-notify-metrics">
        <span><strong>{text(raw.clienti_con_numero || 0)}</strong> clienti con WhatsApp</span>
        <span><strong>{text(raw.appuntamenti_inviabili || 0)}</strong> promemoria pronti</span>
        <span><strong>{text(raw.registro_totale || 0)}</strong> messaggi nel registro</span>
        <span><strong>{text(raw.avvisi_operativi_non_letti || 0)}</strong> avvisi operativi da leggere</span>
      </div>

      <section className="iu-notify-compose iu-notify-device">
        <header>
          <Smartphone aria-hidden="true" />
          <div>
            <strong>Notifiche su questo dispositivo</strong>
            <span>Ricevi avvisi importanti anche quando il gestionale non è aperto.</span>
          </div>
          <IusStatusBadge tone={pushTone(pushStatus)}>{pushLabel(pushStatus)}</IusStatusBadge>
        </header>
        <div className="iu-notify-device-grid">
          <p>
            <b>Stato dispositivo</b>
            <span>{pushDeviceMessage}</span>
          </p>
          <p>
            <b>iPhone e iPad</b>
            <span>Su iPhone/iPad può essere necessario aggiungere IUSENTRA alla schermata Home e aprirla dall'icona installata.</span>
          </p>
        </div>
        {serverNotConfigured && canConfigureServer ? (
          <div className="iu-notify-admin-note" role="note">
            <strong>Configurazione richiesta</strong>
            <span>Le chiavi notifiche non risultano complete nell'ambiente attivo.</span>
            <span>Dopo il riallineamento, aggiorna questa pagina e attiva il dispositivo.</span>
          </div>
        ) : null}
        <div className="iu-notify-actions">
          <Button
            type="button"
            disabled={!pushStatus.supported || !pushStatus.configured || pushStatus.active || pushBusy === 'activate'}
            onClick={() => void runPush('activate')}
          >
            <BellRing data-icon="inline-start" />
            {pushStatus.active ? 'Notifiche attive su questo dispositivo' : pushBusy === 'activate' ? 'Attivazione...' : 'Attiva notifiche su questo dispositivo'}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={!pushStatus.active || pushBusy === 'deactivate'}
            onClick={() => void runPush('deactivate')}
          >
            <Bell data-icon="inline-start" />
            {pushBusy === 'deactivate' ? 'Disattivazione...' : 'Disattiva notifiche su questo dispositivo'}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={!pushStatus.active || pushBusy === 'test'}
            onClick={() => void runPush('test')}
          >
            <Send data-icon="inline-start" />
            {pushBusy === 'test' ? 'Invio test...' : 'Invia notifica di test'}
          </Button>
        </div>
        {pushResult ? <p className={pushResult.ok ? 'iu-notify-result is-ok' : 'iu-notify-result is-ko'}>{pushResult.message}</p> : null}
      </section>

      <section className="iu-notify-compose">
        <header>
          <BellRing aria-hidden="true" />
          <div>
            <strong>Avvisi operativi</strong>
            <span>Scadenze PEC, agenda e presidi interni creati dal gestionale.</span>
          </div>
          <IusStatusBadge tone={operationalAlerts.length ? 'info' : 'neutral'}>
            {operationalAlerts.length ? `${operationalAlerts.length} avvisi` : 'Nessun avviso'}
          </IusStatusBadge>
        </header>
        <div className="iu-notify-device-grid">
          <p>
            <b>Dispositivi push attivi</b>
            <span>{text(raw.dispositivi_push_attivi || 0)}</span>
          </p>
          <p>
            <b>Consegna interna</b>
            <span>Gli avvisi restano visibili nel gestionale anche quando il push del dispositivo non è ancora attivo.</span>
          </p>
        </div>
        <div className="iu-notify-list">
          {operationalAlerts.length ? operationalAlerts.map((item) => (
            <p key={text(item.id)}>
              <b>{text(item.quando)} - {text(item.titolo)}</b>
              <span>{text(item.messaggio)} {item.letto ? '' : '- da leggere'}</span>
              {text(item.href) ? <a href={text(item.href)}>Apri avviso</a> : null}
            </p>
          )) : <p>{text(raw.avvisi_operativi_errore) || 'Nessun avviso operativo registrato per questo utente.'}</p>}
        </div>
      </section>

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
