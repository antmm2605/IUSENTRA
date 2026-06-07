import { FormEvent, useEffect, useMemo, useState } from 'react'
import {
  Bell,
  CalendarDays,
  Check,
  ClipboardList,
  Download,
  FileCheck2,
  FileText,
  Link2,
  Loader2,
  MessageCircle,
  RefreshCw,
  Send,
  Settings2,
  ShieldCheck,
  UploadCloud,
  UserRound,
  UsersRound,
} from 'lucide-react'
import {
  acceptInvite,
  clientPortalPost,
  clientPortalTokenFromPath,
  clearClientPortalToken,
  emptyClientPortal,
  emptyStudioPortal,
  exportClientPortalConversation,
  loadClientPortal,
  loadInvitePreview,
  loadStudioClientPortal,
  readClientPortalToken,
  storeClientPortalToken,
  studioPortalPost,
  uploadClientPortalDocument,
  type ClientPortalClientPayload,
  type ClientPortalResponse,
  type ClientPortalStudioPayload,
  type PortalRow,
} from '../clientPortalData'

type ClientPortalPageProps = {
  mode?: 'studio' | 'client'
}

type Notice = {
  tone: 'success' | 'warning' | 'danger' | 'info'
  text: string
}

function text(value: unknown, fallback = ''): string {
  const cleaned = String(value ?? '').trim()
  return cleaned || fallback
}

function numberValue(value: unknown): number {
  const parsed = Number(value ?? 0)
  return Number.isFinite(parsed) ? parsed : 0
}

function rowId(row: PortalRow | undefined): string {
  return text(row?.id)
}

function statusLabel(value: unknown): string {
  const raw = text(value, 'in attesa').replace(/_/g, ' ')
  return raw.charAt(0).toUpperCase() + raw.slice(1)
}

function NoticeBar({ notice }: { notice: Notice | null }) {
  if (!notice) return null
  return <div className={`iu-client-portal-notice tone-${notice.tone}`} role="status">{notice.text}</div>
}

function LoadingPanel({ label = 'Caricamento in corso' }: { label?: string }) {
  return (
    <div className="iu-client-portal-loading">
      <Loader2 size={20} aria-hidden="true"/>
      <span>{label}</span>
    </div>
  )
}

function EmptyPanel({ icon: Icon, title, body }: { icon: typeof UsersRound; title: string; body: string }) {
  return (
    <div className="iu-client-portal-empty">
      <Icon size={22} aria-hidden="true"/>
      <strong>{title}</strong>
      <span>{body}</span>
    </div>
  )
}

function PortalBadge({ value }: { value: unknown }) {
  return <span className="iu-client-portal-badge">{statusLabel(value)}</span>
}

function StudioKpis({ payload }: { payload: ClientPortalStudioPayload }) {
  const summary = payload.summary || {}
  const items = [
    { label: 'Clienti attivati', value: numberValue(summary.clients), icon: UsersRound },
    { label: 'Pratiche collegate', value: numberValue(summary.matters), icon: ClipboardList },
    { label: 'Inviti attivi', value: numberValue(summary.activeInvites), icon: Link2 },
    { label: 'Azioni aperte', value: numberValue(summary.pendingDocuments) + numberValue(summary.pendingSignatures), icon: Bell },
  ]
  return (
    <section className="iu-client-portal-kpis" aria-label="Sintesi Portale Clienti">
      {items.map((item) => (
        <article className="iu-client-portal-kpi" key={item.label}>
          <item.icon size={19} aria-hidden="true"/>
          <span>{item.label}</span>
          <strong>{item.value}</strong>
        </article>
      ))}
    </section>
  )
}

function ClientPortalStudio() {
  const [payload, setPayload] = useState<ClientPortalStudioPayload>(emptyStudioPortal)
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState<Notice | null>(null)
  const [inviteLink, setInviteLink] = useState('')
  const [selectedMatterId, setSelectedMatterId] = useState('')
  const [inviteForm, setInviteForm] = useState({ clientId: '', matterId: '', message: '', expiresDays: 14 })
  const [messageBody, setMessageBody] = useState('')
  const [requestTitle, setRequestTitle] = useState('')
  const [signatureTitle, setSignatureTitle] = useState('')
  const [appointmentStart, setAppointmentStart] = useState('')
  const [settingsDays, setSettingsDays] = useState(14)

  const load = async () => {
    setLoading(true)
    const data = await loadStudioClientPortal()
    setPayload(data)
    setSettingsDays(numberValue(data.settings?.inviteExpiresDays) || 14)
    setSelectedMatterId((current) => current || rowId(data.matters[0]))
    setInviteForm((current) => ({
      ...current,
      clientId: current.clientId || text(data.clientOptions[0]?.id),
      matterId: current.matterId || text(data.matterOptions[0]?.id),
    }))
    setLoading(false)
  }

  useEffect(() => {
    void load()
  }, [])

  const selectedMatter = useMemo(
    () => payload.matters.find((matter) => rowId(matter) === selectedMatterId) || payload.matters[0],
    [payload.matters, selectedMatterId],
  )
  const selectedMessages = payload.messages.filter((message) => text(message.matter_id) === rowId(selectedMatter))
  const selectedDocumentRequests = payload.documentRequests.filter((item) => text(item.matter_id) === rowId(selectedMatter))
  const selectedSignatures = payload.signatures.filter((item) => text(item.matter_id) === rowId(selectedMatter))
  const selectedAppointments = payload.appointments.filter((item) => text(item.matter_id) === rowId(selectedMatter))
  const signaturesEnabled = payload.featureFlags['routes.appV2.clientPortal.signatures'] !== false

  const applyDashboard = (response: ClientPortalResponse) => {
    const dashboard = response.dashboard
    if (dashboard?.surface === 'studio') setPayload(dashboard as ClientPortalStudioPayload)
    setNotice({ tone: response.ok ? 'success' : 'warning', text: text(response.message, response.ok ? 'Operazione completata.' : 'Operazione non completata.') })
  }

  const createInvite = async (event: FormEvent) => {
    event.preventDefault()
    const response = await studioPortalPost<ClientPortalResponse & { inviteUrl?: string }>('/api/v1/ui/client-portal/studio/invites', inviteForm)
    if (response.ok && response.inviteUrl) setInviteLink(response.inviteUrl)
    applyDashboard(response)
  }

  const sendMessage = async (event: FormEvent) => {
    event.preventDefault()
    if (!rowId(selectedMatter)) return
    const response = await studioPortalPost('/api/v1/ui/client-portal/studio/messages', { matterId: rowId(selectedMatter), body: messageBody })
    if (response.ok) setMessageBody('')
    applyDashboard(response)
  }

  const addDocumentRequest = async (event: FormEvent) => {
    event.preventDefault()
    const response = await studioPortalPost('/api/v1/ui/client-portal/studio/document-requests', {
      matterId: rowId(selectedMatter),
      title: requestTitle,
      required: true,
    })
    if (response.ok) setRequestTitle('')
    applyDashboard(response)
  }

  const addSignature = async (event: FormEvent) => {
    event.preventDefault()
    const response = await studioPortalPost('/api/v1/ui/client-portal/studio/signature-requests', {
      matterId: rowId(selectedMatter),
      title: signatureTitle,
    })
    if (response.ok) setSignatureTitle('')
    applyDashboard(response)
  }

  const addAppointment = async (event: FormEvent) => {
    event.preventDefault()
    const response = await studioPortalPost('/api/v1/ui/client-portal/studio/appointments', {
      matterId: rowId(selectedMatter),
      title: 'Appuntamento con il cliente',
      startsAt: appointmentStart,
    })
    if (response.ok) setAppointmentStart('')
    applyDashboard(response)
  }

  const saveSettings = async (event: FormEvent) => {
    event.preventDefault()
    const response = await studioPortalPost('/api/v1/ui/client-portal/studio/settings', { inviteExpiresDays: settingsDays })
    setNotice({ tone: response.ok ? 'success' : 'warning', text: text(response.message, 'Impostazioni aggiornate.') })
  }

  const createEvidencePack = async () => {
    const response = await studioPortalPost('/api/v1/ui/client-portal/studio/evidence-packs', { matterId: rowId(selectedMatter) })
    applyDashboard(response)
  }

  if (loading) return <LoadingPanel label="Caricamento Portale Clienti"/>

  return (
    <main className="iu-client-portal iu-client-portal--studio">
      <header className="iu-client-portal-header">
        <div>
          <p className="iu-client-portal-overline">Area studio</p>
          <h1>Portale Clienti</h1>
          <span>Inviti, documenti, firme, chat e appuntamenti collegati ai fascicoli reali dello studio.</span>
        </div>
        <button className="iu-client-portal-button secondary" type="button" onClick={load}>
          <RefreshCw size={17} aria-hidden="true"/>Aggiorna
        </button>
      </header>
      <NoticeBar notice={notice}/>
      <StudioKpis payload={payload}/>

      <section className="iu-client-portal-layout">
        <aside className="iu-client-portal-panel iu-client-portal-panel--rail">
          <div className="iu-client-portal-panel__head">
            <h2>Nuovo invito</h2>
            <Link2 size={18} aria-hidden="true"/>
          </div>
          <form className="iu-client-portal-form" onSubmit={createInvite}>
            <label>
              Cliente
              <select value={inviteForm.clientId} onChange={(event) => setInviteForm((current) => ({ ...current, clientId: event.target.value }))}>
                {payload.clientOptions.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
              </select>
            </label>
            <label>
              Fascicolo
              <select value={inviteForm.matterId} onChange={(event) => setInviteForm((current) => ({ ...current, matterId: event.target.value }))}>
                {payload.matterOptions.map((item) => <option key={item.id} value={item.id}>{item.number ? `${item.number} · ${item.label}` : item.label}</option>)}
              </select>
            </label>
            <label>
              Validità invito
              <input type="number" min={1} max={90} value={inviteForm.expiresDays} onChange={(event) => setInviteForm((current) => ({ ...current, expiresDays: Number(event.target.value) }))}/>
            </label>
            <label>
              Messaggio per il cliente
              <textarea value={inviteForm.message} onChange={(event) => setInviteForm((current) => ({ ...current, message: event.target.value }))} rows={3}/>
            </label>
            <button className="iu-client-portal-button" type="submit" disabled={!payload.canWrite}>
              <Send size={17} aria-hidden="true"/>Crea invito
            </button>
          </form>
          {inviteLink ? (
            <div className="iu-client-portal-linkbox">
              <span>Link cliente pronto</span>
              <a href={inviteLink} target="_blank" rel="noreferrer">Apri vista cliente</a>
            </div>
          ) : null}
        </aside>

        <section className="iu-client-portal-panel iu-client-portal-panel--main">
          <div className="iu-client-portal-panel__head">
            <h2>Pratiche cliente</h2>
            <span>{payload.matters.length} pratiche</span>
          </div>
          {payload.matters.length === 0 ? (
            <EmptyPanel icon={UsersRound} title="Nessun cliente attivato" body="Crea un invito da un cliente e un fascicolo esistenti per aprire il portale."/>
          ) : (
            <div className="iu-client-portal-matter-list">
              {payload.matters.map((matter) => (
                <article className={rowId(matter) === rowId(selectedMatter) ? 'is-active' : ''} key={rowId(matter)}>
                  <button type="button" onClick={() => setSelectedMatterId(rowId(matter))}>
                    <strong>{text(matter.title, 'Pratica cliente')}</strong>
                    <span>{text((matter.client as PortalRow | undefined)?.display_name, 'Cliente')}</span>
                    <PortalBadge value={matter.status}/>
                  </button>
                  <div>
                    <button className="iu-client-portal-inline" type="button" onClick={() => setSelectedMatterId(rowId(matter))}>
                      <MessageCircle size={15} aria-hidden="true"/>Avvia chat
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </section>

      {selectedMatter ? (
        <section className="iu-client-portal-detail">
          <div className="iu-client-portal-panel">
            <div className="iu-client-portal-panel__head">
              <h2>{text(selectedMatter.title, 'Pratica cliente')}</h2>
              <button className="iu-client-portal-button secondary" type="button" onClick={createEvidencePack}>
                <FileCheck2 size={17} aria-hidden="true"/>Prepara pacchetto finale
              </button>
            </div>
            <div className="iu-client-portal-workgrid">
              <form className="iu-client-portal-mini-form" onSubmit={addDocumentRequest}>
                <h3>Documenti</h3>
                <input value={requestTitle} onChange={(event) => setRequestTitle(event.target.value)} placeholder="Documento da richiedere"/>
                <button type="submit"><UploadCloud size={16} aria-hidden="true"/>Richiedi</button>
                {selectedDocumentRequests.map((item) => <span key={rowId(item)}>{text(item.title)} · {statusLabel(item.status)}</span>)}
              </form>
              {signaturesEnabled ? (
                <form className="iu-client-portal-mini-form" onSubmit={addSignature}>
                  <h3>Firme</h3>
                  <input value={signatureTitle} onChange={(event) => setSignatureTitle(event.target.value)} placeholder="Documento da firmare"/>
                  <button type="submit"><FileCheck2 size={16} aria-hidden="true"/>Richiedi firma</button>
                  {selectedSignatures.map((item) => <span key={rowId(item)}>{text(item.title)} · {statusLabel(item.status)}</span>)}
                </form>
              ) : (
                <section className="iu-client-portal-mini-form" aria-label="Firme">
                  <h3>Firme</h3>
                  <span>Firma semplice non attiva per questo studio.</span>
                </section>
              )}
              <form className="iu-client-portal-mini-form" onSubmit={addAppointment}>
                <h3>Appuntamenti</h3>
                <input type="datetime-local" value={appointmentStart} onChange={(event) => setAppointmentStart(event.target.value)}/>
                <button type="submit"><CalendarDays size={16} aria-hidden="true"/>Proponi</button>
                {selectedAppointments.map((item) => <span key={rowId(item)}>{text(item.starts_at_label)} · {statusLabel(item.status)}</span>)}
              </form>
            </div>
          </div>

          <div className="iu-client-portal-panel iu-client-portal-chat" id="portale-clienti-chat">
            <div className="iu-client-portal-panel__head">
              <h2>Chat cliente</h2>
              <MessageCircle size={18} aria-hidden="true"/>
            </div>
            <div className="iu-client-portal-chat__messages">
              {selectedMessages.length === 0 ? <span className="iu-client-portal-muted">Nessun messaggio nella pratica.</span> : null}
              {selectedMessages.map((message) => (
                <article key={rowId(message)} className={text(message.sender_type) === 'studio' ? 'from-studio' : 'from-client'}>
                  <strong>{text(message.sender_type) === 'studio' ? 'Studio' : 'Cliente'}</strong>
                  <p>{text(message.body)}</p>
                  <span>{text(message.created_at_label)}</span>
                </article>
              ))}
            </div>
            <form className="iu-client-portal-chat__composer" onSubmit={sendMessage}>
              <textarea value={messageBody} onChange={(event) => setMessageBody(event.target.value)} placeholder="Scrivi al cliente" rows={3}/>
              <button className="iu-client-portal-button" type="submit"><Send size={17} aria-hidden="true"/>Scrivi al cliente</button>
            </form>
          </div>
        </section>
      ) : null}

      <section className="iu-client-portal-panel iu-client-portal-settings">
        <div className="iu-client-portal-panel__head">
          <h2>Impostazioni portale</h2>
          <Settings2 size={18} aria-hidden="true"/>
        </div>
        <form className="iu-client-portal-settings__form" onSubmit={saveSettings}>
          <label>
            Giorni validità invito
            <input type="number" min={1} max={90} value={settingsDays} onChange={(event) => setSettingsDays(Number(event.target.value))}/>
          </label>
          <button className="iu-client-portal-button secondary" type="submit">Salva impostazioni</button>
        </form>
      </section>
    </main>
  )
}

function ClientPortalInvite({ token }: { token: string }) {
  const [payload, setPayload] = useState<ClientPortalClientPayload>(emptyClientPortal)
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState<Notice | null>(null)

  useEffect(() => {
    let alive = true
    loadInvitePreview(token).then((data) => {
      if (!alive) return
      setPayload(data)
      setLoading(false)
    })
    return () => { alive = false }
  }, [token])

  const activate = async () => {
    const response = await acceptInvite(token)
    if (response.ok) {
      storeClientPortalToken(token)
      window.location.replace('/portale-cliente')
    } else {
      setNotice({ tone: 'warning', text: text(response.message, 'Invito non attivato.') })
    }
  }

  if (loading) return <LoadingPanel label="Verifica invito"/>
  if (!payload.ok) {
    return (
      <main className="iu-client-portal-public">
        <section className="iu-client-portal-public__card">
          <ShieldCheck size={30} aria-hidden="true"/>
          <h1>Invito non disponibile</h1>
          <p>{text(payload.message, 'Contatta lo studio per ricevere un nuovo invito.')}</p>
        </section>
      </main>
    )
  }

  return (
    <main className="iu-client-portal-public">
      <section className="iu-client-portal-public__card">
        <ShieldCheck size={30} aria-hidden="true"/>
        <p className="iu-client-portal-overline">Accesso cliente</p>
        <h1>{text(payload.matter?.title, 'La tua pratica')}</h1>
        <p>Entra nello spazio riservato per documenti, privacy, appuntamenti e comunicazioni con lo studio.</p>
        <NoticeBar notice={notice}/>
        <div className="iu-client-portal-public__actions">
          <button className="iu-client-portal-button" type="button" onClick={activate}>
            <Check size={17} aria-hidden="true"/>Entra nel portale
          </button>
          <a className="iu-client-portal-button secondary" href="/portale-cliente">Ho già accesso</a>
        </div>
      </section>
    </main>
  )
}

function ClientPortalClient() {
  const [payload, setPayload] = useState<ClientPortalClientPayload>(emptyClientPortal)
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState<Notice | null>(null)
  const [messageBody, setMessageBody] = useState('')
  const [profileForm, setProfileForm] = useState({ displayName: '', email: '', phone: '', fiscalCode: '', identityExpiresAt: '' })
  const [questionnaireResponses, setQuestionnaireResponses] = useState<Record<string, string>>({})
  const [survey, setSurvey] = useState({ rating: 5, comment: '' })
  const token = readClientPortalToken()
  const signaturesEnabled = payload.featureFlags['routes.appV2.clientPortal.signatures'] !== false

  const load = async () => {
    setLoading(true)
    const data = await loadClientPortal(token)
    setPayload(data)
    setProfileForm({
      displayName: text(data.client?.display_name),
      email: text(data.client?.email),
      phone: text(data.client?.phone),
      fiscalCode: text(data.client?.fiscal_code),
      identityExpiresAt: text(data.client?.identity_expires_at),
    })
    setLoading(false)
  }

  useEffect(() => {
    void load()
  }, [])

  const applyClientResponse = (response: ClientPortalResponse) => {
    if (response.dashboard?.surface === 'client') setPayload(response.dashboard as ClientPortalClientPayload)
    setNotice({ tone: response.ok ? 'success' : 'warning', text: text(response.message, response.ok ? 'Operazione completata.' : 'Operazione non completata.') })
  }

  const saveProfile = async (event: FormEvent) => {
    event.preventDefault()
    applyClientResponse(await clientPortalPost('/api/v1/ui/client-portal/public/profile', profileForm))
  }

  const acceptConsent = async (key: string) => {
    applyClientResponse(await clientPortalPost('/api/v1/ui/client-portal/public/consents', { key, accepted: true }))
  }

  const sendMessage = async (event: FormEvent) => {
    event.preventDefault()
    const response = await clientPortalPost('/api/v1/ui/client-portal/public/messages', { body: messageBody })
    if (response.ok) setMessageBody('')
    applyClientResponse(response)
  }

  const uploadDocument = async (file: File | null, requestId: string) => {
    if (!file) return
    applyClientResponse(await uploadClientPortalDocument(file, requestId))
  }

  const completeSignature = async (signatureId: string) => {
    applyClientResponse(await clientPortalPost(`/api/v1/ui/client-portal/public/signatures/${signatureId}/complete`, { declaration: 'Confermo la firma semplice del documento.' }))
  }

  const updateAppointment = async (appointmentId: string, status: string) => {
    applyClientResponse(await clientPortalPost(`/api/v1/ui/client-portal/public/appointments/${appointmentId}`, { status }))
  }

  const markNotification = async (notificationId: string) => {
    applyClientResponse(await clientPortalPost(`/api/v1/ui/client-portal/public/notifications/${notificationId}/read`, {}))
  }

  const submitQuestionnaire = async (questionnaireId: string) => {
    applyClientResponse(await clientPortalPost(`/api/v1/ui/client-portal/public/questionnaires/${questionnaireId}`, { responses: questionnaireResponses }))
  }

  const submitSurvey = async (event: FormEvent) => {
    event.preventDefault()
    applyClientResponse(await clientPortalPost('/api/v1/ui/client-portal/public/surveys', survey))
  }

  const exportConversation = async () => {
    const response = await exportClientPortalConversation(text(payload.matter?.id))
    if (!response.ok) {
      setNotice({ tone: 'warning', text: text(response.message, 'Conversazione non esportata.') })
      return
    }
    const blob = new Blob([JSON.stringify(response, null, 2)], { type: 'application/json;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'conversazione-portale-cliente.json'
    anchor.click()
    URL.revokeObjectURL(url)
    setNotice({ tone: 'success', text: 'Conversazione esportata.' })
  }

  if (loading) return <LoadingPanel label="Caricamento area cliente"/>
  if (!token || !payload.ok) {
    return (
      <main className="iu-client-portal-public">
        <section className="iu-client-portal-public__card">
          <ShieldCheck size={30} aria-hidden="true"/>
          <h1>Accesso cliente richiesto</h1>
          <p>Apri il link ricevuto dallo studio o richiedi un nuovo invito.</p>
          <button className="iu-client-portal-button secondary" type="button" onClick={() => { clearClientPortalToken(); window.location.href = '/' }}>Torna al sito</button>
        </section>
      </main>
    )
  }

  const progress = numberValue(payload.matter?.progress)
  const messages = payload.messages || []

  return (
    <main className="iu-client-portal-public iu-client-portal-public--dashboard">
      <header className="iu-client-portal-client-hero">
        <div>
          <p className="iu-client-portal-overline">Area riservata cliente</p>
          <h1>{text(payload.matter?.title, 'La tua pratica')}</h1>
          <span>{text(payload.activityCenter?.nextAction, 'Controlla le attività richieste dallo studio.')}</span>
        </div>
        <div className="iu-client-portal-client-hero__actions">
          <a className="iu-client-portal-button" href="#chat-cliente"><MessageCircle size={17} aria-hidden="true"/>Scrivi allo studio</a>
          <a className="iu-client-portal-button secondary" href="#chat-cliente"><MessageCircle size={17} aria-hidden="true"/>Apri chat</a>
        </div>
      </header>
      <NoticeBar notice={notice}/>

      <section className="iu-client-portal-client-summary">
        <article>
          <span>Completamento</span>
          <strong>{progress}%</strong>
          <progress className="iu-client-portal-progress" value={progress} max={100}>{progress}%</progress>
        </article>
        <article>
          <span>Azioni aperte</span>
          <strong>{numberValue(payload.activityCenter?.openItems)}</strong>
        </article>
        <article>
          <span>Notifiche</span>
          <strong>{(payload.notifications || []).filter((item) => !text(item.read_at)).length}</strong>
        </article>
      </section>

      <section className="iu-client-portal-client-grid">
        <div className="iu-client-portal-panel">
          <div className="iu-client-portal-panel__head"><h2>Cosa devo fare adesso</h2><ClipboardList size={18} aria-hidden="true"/></div>
          <div className="iu-client-portal-timeline">
            {(payload.steps || []).map((step) => (
              <article key={rowId(step)}>
                <span/>
                <strong>{text(step.title)}</strong>
                <PortalBadge value={step.status}/>
              </article>
            ))}
          </div>
        </div>

        <form className="iu-client-portal-panel iu-client-portal-form" onSubmit={saveProfile}>
          <div className="iu-client-portal-panel__head"><h2>Anagrafica</h2><UserRound size={18} aria-hidden="true"/></div>
          <label>Nome e cognome<input value={profileForm.displayName} onChange={(event) => setProfileForm((current) => ({ ...current, displayName: event.target.value }))}/></label>
          <label>Email<input value={profileForm.email} onChange={(event) => setProfileForm((current) => ({ ...current, email: event.target.value }))}/></label>
          <label>Telefono<input value={profileForm.phone} onChange={(event) => setProfileForm((current) => ({ ...current, phone: event.target.value }))}/></label>
          <label>Codice fiscale<input value={profileForm.fiscalCode} onChange={(event) => setProfileForm((current) => ({ ...current, fiscalCode: event.target.value }))}/></label>
          <label>Scadenza documento<input type="date" value={profileForm.identityExpiresAt} onChange={(event) => setProfileForm((current) => ({ ...current, identityExpiresAt: event.target.value }))}/></label>
          <button className="iu-client-portal-button" type="submit">Salva anagrafica</button>
        </form>

        <div className="iu-client-portal-panel">
          <div className="iu-client-portal-panel__head"><h2>Privacy e consensi</h2><ShieldCheck size={18} aria-hidden="true"/></div>
          {(payload.consents || []).map((consent) => (
            <article className="iu-client-portal-action-row" key={rowId(consent)}>
              <div><strong>{text(consent.consent_key, 'Informativa privacy').replace(/_/g, ' ')}</strong><span>{numberValue(consent.accepted) ? 'Accettato' : 'Da accettare'}</span></div>
              <button type="button" onClick={() => acceptConsent(text(consent.consent_key))} disabled={Boolean(numberValue(consent.accepted))}>Accetta</button>
            </article>
          ))}
        </div>

        <div className="iu-client-portal-panel">
          <div className="iu-client-portal-panel__head"><h2>Documenti</h2><UploadCloud size={18} aria-hidden="true"/></div>
          {(payload.documentRequests || []).map((requestItem) => (
            <article className="iu-client-portal-action-row" key={rowId(requestItem)}>
              <div><strong>{text(requestItem.title)}</strong><span>{statusLabel(requestItem.status)}</span></div>
              <label className="iu-client-portal-file">
                <UploadCloud size={16} aria-hidden="true"/>Carica
                <input type="file" onChange={(event) => uploadDocument(event.target.files?.[0] || null, rowId(requestItem))}/>
              </label>
            </article>
          ))}
          {(payload.documents || []).map((document) => <span className="iu-client-portal-muted" key={rowId(document)}>{text(document.filename)} · {text(document.uploaded_at_label)}</span>)}
        </div>

        <div className="iu-client-portal-panel">
          <div className="iu-client-portal-panel__head"><h2>Firme</h2><FileCheck2 size={18} aria-hidden="true"/></div>
          {!signaturesEnabled ? <span className="iu-client-portal-muted">Firma semplice non attiva per questo studio.</span> : null}
          {signaturesEnabled && (payload.signatures || []).length === 0 ? <span className="iu-client-portal-muted">Nessun documento in firma.</span> : null}
          {signaturesEnabled && (payload.signatures || []).map((signature) => (
            <article className="iu-client-portal-action-row" key={rowId(signature)}>
              <div><strong>{text(signature.title)}</strong><span>{statusLabel(signature.status)}</span></div>
              <button type="button" onClick={() => completeSignature(rowId(signature))} disabled={text(signature.status) === 'firmato'}>Firma</button>
            </article>
          ))}
        </div>

        <div className="iu-client-portal-panel iu-client-portal-chat" id="chat-cliente">
          <div className="iu-client-portal-panel__head"><h2>Chat con lo studio</h2><MessageCircle size={18} aria-hidden="true"/></div>
          <div className="iu-client-portal-chat__messages">
            {messages.length === 0 ? <span className="iu-client-portal-muted">Nessun messaggio ancora presente.</span> : null}
            {messages.map((message) => (
              <article key={rowId(message)} className={text(message.sender_type) === 'cliente' ? 'from-client' : 'from-studio'}>
                <strong>{text(message.sender_type) === 'cliente' ? 'Tu' : 'Studio'}</strong>
                <p>{text(message.body)}</p>
                <span>{text(message.created_at_label)}</span>
              </article>
            ))}
          </div>
          <form className="iu-client-portal-chat__composer" onSubmit={sendMessage}>
            <textarea value={messageBody} onChange={(event) => setMessageBody(event.target.value)} placeholder="Scrivi allo studio" rows={3}/>
            <button className="iu-client-portal-button" type="submit"><Send size={17} aria-hidden="true"/>Invia</button>
          </form>
        </div>

        <div className="iu-client-portal-panel">
          <div className="iu-client-portal-panel__head"><h2>Appuntamenti</h2><CalendarDays size={18} aria-hidden="true"/></div>
          {(payload.appointments || []).length === 0 ? <span className="iu-client-portal-muted">Nessun appuntamento proposto.</span> : null}
          {(payload.appointments || []).map((appointment) => (
            <article className="iu-client-portal-action-row" key={rowId(appointment)}>
              <div><strong>{text(appointment.title)}</strong><span>{text(appointment.starts_at_label)} · {statusLabel(appointment.status)}</span></div>
              <div className="iu-client-portal-row-actions">
                <button type="button" onClick={() => updateAppointment(rowId(appointment), 'confermato')}>Conferma</button>
                <button type="button" onClick={() => updateAppointment(rowId(appointment), 'annullato')}>Annulla</button>
              </div>
            </article>
          ))}
        </div>

        <div className="iu-client-portal-panel">
          <div className="iu-client-portal-panel__head"><h2>Centro attività</h2><Bell size={18} aria-hidden="true"/></div>
          {(payload.notifications || []).map((notification) => (
            <article className="iu-client-portal-action-row" key={rowId(notification)}>
              <div><strong>{text(notification.title)}</strong><span>{text(notification.body)} {text(notification.created_at_label)}</span></div>
              <button type="button" onClick={() => markNotification(rowId(notification))} disabled={Boolean(text(notification.read_at))}>Letta</button>
            </article>
          ))}
        </div>

        <div className="iu-client-portal-panel">
          <div className="iu-client-portal-panel__head"><h2>Questionari</h2><FileText size={18} aria-hidden="true"/></div>
          {(payload.questionnaires || []).map((questionnaire) => {
            const questions = Array.isArray(questionnaire.questions) ? questionnaire.questions as Array<{ id: string; label: string }> : []
            return (
              <article className="iu-client-portal-questionnaire" key={rowId(questionnaire)}>
                <strong>{text(questionnaire.title)}</strong>
                {questions.map((question) => (
                  <label key={question.id}>
                    {question.label}
                    <textarea rows={2} value={questionnaireResponses[question.id] || ''} onChange={(event) => setQuestionnaireResponses((current) => ({ ...current, [question.id]: event.target.value }))}/>
                  </label>
                ))}
                <button type="button" onClick={() => submitQuestionnaire(rowId(questionnaire))}>Invia questionario</button>
              </article>
            )
          })}
        </div>

        <form className="iu-client-portal-panel iu-client-portal-form" onSubmit={submitSurvey}>
          <div className="iu-client-portal-panel__head"><h2>Valutazione finale</h2><Check size={18} aria-hidden="true"/></div>
          <label>Valutazione<input type="number" min={1} max={5} value={survey.rating} onChange={(event) => setSurvey((current) => ({ ...current, rating: Number(event.target.value) }))}/></label>
          <label>Commento<textarea rows={3} value={survey.comment} onChange={(event) => setSurvey((current) => ({ ...current, comment: event.target.value }))}/></label>
          <button className="iu-client-portal-button secondary" type="submit">Invia valutazione</button>
        </form>

        <div className="iu-client-portal-panel">
          <div className="iu-client-portal-panel__head"><h2>Pacchetto finale</h2><Download size={18} aria-hidden="true"/></div>
          {(payload.evidencePacks || []).length === 0 ? <span className="iu-client-portal-muted">Lo studio non ha ancora preparato il riepilogo finale.</span> : null}
          {(payload.evidencePacks || []).map((pack) => <span className="iu-client-portal-muted" key={rowId(pack)}>Preparato il {text(pack.created_at_label)}</span>)}
          <button className="iu-client-portal-button secondary" type="button" onClick={exportConversation}>Esporta conversazione</button>
        </div>
      </section>
    </main>
  )
}

export function ClientPortalPage({ mode }: ClientPortalPageProps) {
  const tokenFromPath = clientPortalTokenFromPath()
  const clientMode = mode === 'client' || window.location.pathname.startsWith('/portale-cliente')
  if (clientMode && tokenFromPath) return <ClientPortalInvite token={tokenFromPath}/>
  if (clientMode) return <ClientPortalClient/>
  return <ClientPortalStudio/>
}

export default ClientPortalPage
