import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import {
  Bell,
  CalendarDays,
  Check,
  ClipboardList,
  Copy,
  Download,
  ExternalLink,
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
  Video,
} from 'lucide-react'
import {
  acceptInvite,
  clientPortalDocumentUrl,
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
  studioPortalDocumentUrl,
  studioPortalPost,
  uploadClientPortalDocument,
  uploadStudioSignatureDocument,
  type ClientPortalClientPayload,
  type ClientPortalResponse,
  type ClientPortalStudioPayload,
  type PortalRow,
} from '../clientPortalData'
import { reviewStudioDocument } from '../clientPortalSigning'
import { SigningWorkflowPanel } from './client-portal/SigningWorkflowPanel'

type ClientPortalPageProps = {
  mode?: 'studio' | 'client'
}

type Notice = {
  tone: 'success' | 'warning' | 'danger' | 'info'
  text: string
}

type GeneratedInviteLink = {
  url: string
  matterId: string
  clientId: string
  clientName: string
  clientPhone: string
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

function absolutePortalUrl(value: string): string {
  try {
    return new URL(value, window.location.origin).href
  } catch {
    return value
  }
}

function normaliseWhatsAppPhone(value: string): string {
  const digits = value.replace(/\D/g, '')
  if (!digits) return ''
  if (digits.startsWith('00')) return digits.slice(2)
  if (digits.startsWith('39')) return digits
  if (digits.length === 10 && digits.startsWith('3')) return `39${digits}`
  return digits.length >= 8 ? digits : ''
}

function whatsAppWebLink(invite: GeneratedInviteLink): string {
  const message = `Buongiorno, le invio il link riservato al Portale Cliente IUSENTRA: ${invite.url}`
  const phone = normaliseWhatsAppPhone(invite.clientPhone)
  const params = new URLSearchParams({ text: message })
  if (phone) params.set('phone', phone)
  return `https://web.whatsapp.com/send?${params.toString()}`
}

function InviteLinkBox({
  invite,
  onCopy,
}: {
  invite: GeneratedInviteLink
  onCopy: (value: string) => void
}) {
  return (
    <div className="iu-client-portal-linkbox" role="group" aria-label="Link cliente generato">
      <span>Link cliente pronto per {text(invite.clientName, 'il cliente')}</span>
      <input readOnly value={invite.url} onFocus={(event) => event.currentTarget.select()} aria-label="Link cliente"/>
      <div className="iu-client-portal-linkbox__actions">
        <button className="iu-client-portal-button secondary" type="button" onClick={() => onCopy(invite.url)}>
          <Copy size={16} aria-hidden="true"/>Copia link
        </button>
        <a className="iu-client-portal-button secondary" href={invite.url} target="_blank" rel="noreferrer">
          <ExternalLink size={16} aria-hidden="true"/>Apri vista cliente
        </a>
        <a className="iu-client-portal-button" href={whatsAppWebLink(invite)} target="_blank" rel="noreferrer">
          <MessageCircle size={16} aria-hidden="true"/>Invia con WhatsApp Web
        </a>
      </div>
    </div>
  )
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
  const [generatedInvite, setGeneratedInvite] = useState<GeneratedInviteLink | null>(null)
  const [selectedMatterId, setSelectedMatterId] = useState('')
  const [clientSearch, setClientSearch] = useState('')
  const [inviteForm, setInviteForm] = useState({ clientId: '', matterId: '', preventivoId: '', message: '', expiresDays: 14 })
  const [messageBody, setMessageBody] = useState('')
  const [requestTitle, setRequestTitle] = useState('')
  const [signatureTitle, setSignatureTitle] = useState('')
  const [signatureFile, setSignatureFile] = useState<File | null>(null)
  const [signatureSending, setSignatureSending] = useState(false)
  const [appointmentStart, setAppointmentStart] = useState('')
  const [appointmentVideoUrl, setAppointmentVideoUrl] = useState('')
  const [settingsDays, setSettingsDays] = useState(14)
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({})
  const studioChatRef = useRef<HTMLDivElement | null>(null)

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

  useEffect(() => {
    const node = studioChatRef.current
    if (node) node.scrollTop = node.scrollHeight
  }, [payload.messages.length, selectedMatterId])

  const selectedMatter = useMemo(
    () => payload.matters.find((matter) => rowId(matter) === selectedMatterId) || payload.matters[0],
    [payload.matters, selectedMatterId],
  )
  const selectedMessages = payload.messages.filter((message) => text(message.matter_id) === rowId(selectedMatter))
  const selectedDocumentRequests = payload.documentRequests.filter((item) => text(item.matter_id) === rowId(selectedMatter))
  const selectedClientDocuments = (payload.documents || []).filter((item) => text(item.matter_id) === rowId(selectedMatter))
  const unrequestedClientDocuments = selectedClientDocuments.filter((doc) => {
    const requestId = text(doc.request_id)
    // esclude i PDF caricati dallo studio per le firme, le copie interne del
    // workflow (PDF materializzati) e gli upload già agganciati a una richiesta
    if (requestId === 'firma-studio' || requestId.startsWith('preventivo-pdf:') || requestId.startsWith('conferimento-pdf:') || requestId === 'ricevuta-firma') return false
    return !selectedDocumentRequests.some((item) => rowId(item) === requestId)
  })
  const documentsInReview = selectedClientDocuments.filter((doc) => text(doc.status) === 'in_revisione')
  const selectedSignatures = payload.signatures.filter((item) => text(item.matter_id) === rowId(selectedMatter))
  const selectedAppointments = payload.appointments.filter((item) => text(item.matter_id) === rowId(selectedMatter))
  const selectedInvites = payload.invites.filter((item) => text(item.matter_id) === rowId(selectedMatter))
  const selectedGeneratedInvite = generatedInvite && generatedInvite.matterId === rowId(selectedMatter) ? generatedInvite : null
  const filteredClientOptions = useMemo(() => {
    const query = clientSearch.trim().toLowerCase()
    if (!query) return payload.clientOptions
    return payload.clientOptions.filter((item) => (
      `${item.label} ${item.email || ''} ${item.phone || ''} ${item.fiscalCode || ''}`.toLowerCase().includes(query)
    ))
  }, [clientSearch, payload.clientOptions])
  const linkedMatterOptions = useMemo(
    () => payload.matterOptions.filter((item) => !inviteForm.clientId || text(item.clientId) === inviteForm.clientId),
    [inviteForm.clientId, payload.matterOptions],
  )
  const linkedPreventivoOptions = useMemo(
    () => (payload.preventivoOptions || []).filter((item) => inviteForm.clientId && text(item.clientId) === inviteForm.clientId),
    [inviteForm.clientId, payload.preventivoOptions],
  )
  const selectedClientOption = payload.clientOptions.find((item) => item.id === inviteForm.clientId)
  const signaturesEnabled = payload.featureFlags['routes.appV2.clientPortal.signatures'] !== false
  const videoCallsEnabled = payload.featureFlags['routes.appV2.clientPortal.videoCalls'] !== false
  const signingWorkflowEnabled = payload.featureFlags['routes.appV2.clientPortal.signingWorkflow'] === true

  const reviewDocument = async (documentId: string, decision: 'approvato' | 'respinto', note = '') => {
    const response = await reviewStudioDocument(documentId, decision, note)
    setNotice({ tone: response.ok ? 'success' : 'warning', text: text(response.message, response.ok ? 'Revisione registrata.' : 'Revisione non registrata.') })
    if (response.ok) await load()
  }

  useEffect(() => {
    if (!inviteForm.clientId) return
    const nextMatter = linkedMatterOptions[0]
    const currentStillLinked = linkedMatterOptions.some((item) => item.id === inviteForm.matterId)
    if (!currentStillLinked) {
      setInviteForm((current) => ({ ...current, matterId: text(nextMatter?.id) }))
    }
  }, [inviteForm.clientId, inviteForm.matterId, linkedMatterOptions])

  useEffect(() => {
    if (filteredClientOptions.length === 0) return
    if (!inviteForm.clientId || !filteredClientOptions.some((item) => item.id === inviteForm.clientId)) {
      updateInviteClient(filteredClientOptions[0].id)
    }
  }, [filteredClientOptions, inviteForm.clientId])

  const applyDashboard = (response: ClientPortalResponse) => {
    const dashboard = response.dashboard
    if (dashboard?.surface === 'studio') setPayload(dashboard as ClientPortalStudioPayload)
    setNotice({ tone: response.ok ? 'success' : 'warning', text: text(response.message, response.ok ? 'Operazione completata.' : 'Operazione non completata.') })
  }

  const rememberInviteLink = (
    response: ClientPortalResponse & { inviteUrl?: string; invite?: PortalRow },
    requestPayload: { clientId?: string; matterId?: string },
  ) => {
    if (!response.ok || !response.inviteUrl) return
    const invite = response.invite || {}
    const clientId = text(requestPayload.clientId) || text(invite.client_id)
    const client = payload.clientOptions.find((item) => item.id === clientId)
    const matterId = text(invite.matter_id) || rowId(selectedMatter)
    if (matterId) setSelectedMatterId(matterId)
    setGeneratedInvite({
      url: absolutePortalUrl(response.inviteUrl),
      matterId,
      clientId,
      clientName: text(client?.label, text((selectedMatter?.client as PortalRow | undefined)?.display_name, 'Cliente')),
      clientPhone: text(client?.phone),
    })
  }

  const submitInvitePayload = async (requestPayload: typeof inviteForm) => {
    const response = await studioPortalPost<ClientPortalResponse & { inviteUrl?: string; invite?: PortalRow }>(
      '/api/v1/ui/client-portal/studio/invites',
      requestPayload,
    )
    rememberInviteLink(response, requestPayload)
    applyDashboard(response)
    return response
  }

  const createInvite = async (event: FormEvent) => {
    event.preventDefault()
    await submitInvitePayload(inviteForm)
  }

  function updateInviteClient(clientId: string) {
    const nextMatter = payload.matterOptions.find((item) => text(item.clientId) === clientId)
    setInviteForm((current) => ({ ...current, clientId, matterId: text(nextMatter?.id), preventivoId: '' }))
  }

  const createInviteForMatter = async (matter: PortalRow | undefined) => {
    const clientId = text(matter?.client_id)
    const fascicoloId = text(matter?.fascicolo_id)
    if (!clientId || !fascicoloId) {
      setNotice({ tone: 'warning', text: 'Per generare il link collega prima cliente e fascicolo.' })
      return
    }
    const requestPayload = {
      clientId,
      matterId: fascicoloId,
      preventivoId: '',
      message: '',
      expiresDays: numberValue(settingsDays) || numberValue(payload.settings?.inviteExpiresDays) || 14,
    }
    setInviteForm((current) => ({ ...current, ...requestPayload }))
    await submitInvitePayload(requestPayload)
  }

  const copyInviteLink = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value)
    } catch {
      const helper = document.createElement('textarea')
      helper.value = value
      helper.setAttribute('readonly', 'true')
      helper.style.position = 'fixed'
      helper.style.left = '-9999px'
      document.body.appendChild(helper)
      helper.select()
      document.execCommand('copy')
      document.body.removeChild(helper)
    }
    setNotice({ tone: 'success', text: 'Link cliente copiato.' })
  }

  const scrollToPanel = (id: string) => {
    window.setTimeout(() => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0)
  }

  const focusMatterLink = (matter: PortalRow) => {
    setSelectedMatterId(rowId(matter))
    scrollToPanel('portale-clienti-link-cliente')
  }

  const focusMatterChat = (matter: PortalRow) => {
    setSelectedMatterId(rowId(matter))
    scrollToPanel('portale-clienti-chat')
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
    setSignatureSending(true)
    try {
      // Con un PDF allegato la richiesta passa dall'upload multipart: il cliente
      // riceve il documento da leggere e firmare. Senza file resta la richiesta
      // di sola descrizione (compatibilità con il flusso precedente).
      const response = signatureFile
        ? await uploadStudioSignatureDocument(signatureFile, rowId(selectedMatter), signatureTitle)
        : await studioPortalPost('/api/v1/ui/client-portal/studio/signature-requests', {
            matterId: rowId(selectedMatter),
            title: signatureTitle,
          })
      if (response.ok) {
        setSignatureTitle('')
        setSignatureFile(null)
      }
      applyDashboard(response as ClientPortalResponse)
    } finally {
      setSignatureSending(false)
    }
  }

  const addAppointment = async (event: FormEvent) => {
    event.preventDefault()
    const response = await studioPortalPost('/api/v1/ui/client-portal/studio/appointments', {
      matterId: rowId(selectedMatter),
      title: 'Appuntamento con il cliente',
      startsAt: appointmentStart,
      videoUrl: videoCallsEnabled ? appointmentVideoUrl : '',
    })
    if (response.ok) {
      setAppointmentStart('')
      setAppointmentVideoUrl('')
    }
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
              Cerca cliente
              <input value={clientSearch} onChange={(event) => setClientSearch(event.target.value)} placeholder="Nome, email, telefono o codice fiscale"/>
            </label>
            <label>
              Cliente
              <select value={inviteForm.clientId} onChange={(event) => updateInviteClient(event.target.value)} disabled={filteredClientOptions.length === 0}>
                {filteredClientOptions.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
              </select>
            </label>
            {clientSearch ? (
              <p className="iu-client-portal-muted">{filteredClientOptions.length} clienti trovati.</p>
            ) : null}
            {filteredClientOptions.length === 0 ? <p className="iu-client-portal-muted">Nessun cliente trovato con questa ricerca.</p> : null}
            <label>
              Fascicoli collegati
              <select value={inviteForm.matterId} onChange={(event) => setInviteForm((current) => ({ ...current, matterId: event.target.value }))} disabled={linkedMatterOptions.length === 0}>
                {linkedMatterOptions.map((item) => <option key={item.id} value={item.id}>{item.number ? `${item.number} · ${item.label}` : item.label}</option>)}
              </select>
            </label>
            {linkedMatterOptions.length > 0 ? (
              <p className="iu-client-portal-muted">{linkedMatterOptions.length === 1 ? 'Fascicolo associato automaticamente al cliente selezionato.' : `${linkedMatterOptions.length} fascicoli associati a ${text(selectedClientOption?.label, 'questo cliente')}.`}</p>
            ) : (
              <p className="iu-client-portal-muted">Nessun fascicolo collegato al cliente selezionato.</p>
            )}
            {signingWorkflowEnabled && linkedPreventivoOptions.length > 0 ? (
              <label>
                Preventivo da proporre (facoltativo)
                <select value={inviteForm.preventivoId} onChange={(event) => setInviteForm((current) => ({ ...current, preventivoId: event.target.value }))}>
                  <option value="">Nessun preventivo in evidenza</option>
                  {linkedPreventivoOptions.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
                </select>
              </label>
            ) : null}
            <label>
              Validità invito
              <input type="number" min={1} max={90} value={inviteForm.expiresDays} onChange={(event) => setInviteForm((current) => ({ ...current, expiresDays: Number(event.target.value) }))}/>
            </label>
            <label>
              Messaggio per il cliente
              <textarea value={inviteForm.message} onChange={(event) => setInviteForm((current) => ({ ...current, message: event.target.value }))} rows={3}/>
            </label>
            <button className="iu-client-portal-button" type="submit" disabled={!payload.canWrite || filteredClientOptions.length === 0 || linkedMatterOptions.length === 0}>
              <Send size={17} aria-hidden="true"/>Crea invito
            </button>
          </form>
          {generatedInvite ? (
            <InviteLinkBox invite={generatedInvite} onCopy={copyInviteLink}/>
          ) : (
            <p className="iu-client-portal-muted">Il link completo appare qui appena lo studio genera un invito.</p>
          )}
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
                  <div className="iu-client-portal-matter-actions">
                    <button className="iu-client-portal-inline" type="button" onClick={() => focusMatterLink(matter)}>
                      <Link2 size={15} aria-hidden="true"/>Link cliente
                    </button>
                    <button className="iu-client-portal-inline" type="button" onClick={() => focusMatterChat(matter)}>
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
            <section className="iu-client-portal-link-panel" id="portale-clienti-link-cliente" aria-label="Link cliente">
              <div>
                <h3>Link cliente</h3>
                <p>Genera un nuovo collegamento riservato per inviare al cliente l'accesso alla pratica.</p>
              </div>
              <button className="iu-client-portal-button" type="button" onClick={() => createInviteForMatter(selectedMatter)} disabled={!payload.canWrite}>
                <Link2 size={17} aria-hidden="true"/>Genera link cliente
              </button>
              {selectedGeneratedInvite ? (
                <InviteLinkBox invite={selectedGeneratedInvite} onCopy={copyInviteLink}/>
              ) : (
                <p className="iu-client-portal-muted">Per sicurezza il collegamento completo non viene conservato dopo la chiusura della pagina. Rigeneralo quando devi inviarlo o copiarlo.</p>
              )}
              <div className="iu-client-portal-invite-list" aria-label="Inviti cliente">
                {selectedInvites.length === 0 ? <span className="iu-client-portal-muted">Nessun invito registrato per questa pratica.</span> : null}
                {selectedInvites.map((invite) => (
                  <article key={rowId(invite)}>
                    <strong>{statusLabel(invite.status)}</strong>
                    <span>{text(invite.expires_at_label) ? `Scade il ${text(invite.expires_at_label)}` : 'Scadenza non disponibile'}</span>
                  </article>
                ))}
              </div>
            </section>
            <div className="iu-client-portal-workgrid">
              <form className="iu-client-portal-mini-form" onSubmit={addDocumentRequest}>
                <h3>Documenti</h3>
                <input value={requestTitle} onChange={(event) => setRequestTitle(event.target.value)} placeholder="Es. Carta d'identità, busta paga, contratto..."/>
                <button type="submit" disabled={!requestTitle.trim()}><UploadCloud size={16} aria-hidden="true"/>Richiedi al cliente</button>
                {selectedDocumentRequests.length === 0 ? <span className="iu-client-portal-muted">Nessuna richiesta documento per questa pratica.</span> : null}
                {selectedDocumentRequests.map((item) => {
                  const uploaded = selectedClientDocuments.find((doc) => text(doc.request_id) === rowId(item))
                  return (
                    <span className="iu-client-portal-doc-line" key={rowId(item)}>
                      <strong>{text(item.title)}</strong>
                      <PortalBadge value={uploaded ? 'ricevuto' : item.status}/>
                      {uploaded ? (
                        <a href={studioPortalDocumentUrl(rowId(uploaded))} title={`Scarica ${text(uploaded.filename)}`}>
                          <Download size={14} aria-hidden="true"/>{text(uploaded.filename)}
                        </a>
                      ) : null}
                    </span>
                  )
                })}
                {unrequestedClientDocuments.length ? (
                  <>
                    <h4 className="iu-client-portal-doc-subtitle">Altri documenti caricati dal cliente</h4>
                    {unrequestedClientDocuments.map((doc) => (
                      <span className="iu-client-portal-doc-line" key={rowId(doc)}>
                        <a href={studioPortalDocumentUrl(rowId(doc))} title="Scarica documento">
                          <Download size={14} aria-hidden="true"/>{text(doc.filename)}
                        </a>
                        <em>{text(doc.uploaded_at_label)}</em>
                      </span>
                    ))}
                  </>
                ) : null}
                {signingWorkflowEnabled && documentsInReview.length ? (
                  <>
                    <h4 className="iu-client-portal-doc-subtitle">Documenti in revisione</h4>
                    {documentsInReview.map((doc) => (
                      <span className="iu-client-portal-doc-line iu-client-portal-doc-line--review" key={`review-${rowId(doc)}`}>
                        <a href={studioPortalDocumentUrl(rowId(doc))} title="Scarica documento">
                          <Download size={14} aria-hidden="true"/>{text(doc.filename)}
                        </a>
                        <input
                          value={reviewNotes[rowId(doc)] || ''}
                          onChange={(event) => setReviewNotes((current) => ({ ...current, [rowId(doc)]: event.target.value }))}
                          placeholder="Nota per il cliente (facoltativa)"
                          aria-label="Nota di revisione"
                        />
                        <button type="button" onClick={() => void reviewDocument(rowId(doc), 'approvato', reviewNotes[rowId(doc)] || '')}>
                          <Check size={14} aria-hidden="true"/>Approva
                        </button>
                        <button type="button" className="danger" onClick={() => void reviewDocument(rowId(doc), 'respinto', reviewNotes[rowId(doc)] || '')}>
                          Respingi
                        </button>
                      </span>
                    ))}
                  </>
                ) : null}
              </form>
              {signaturesEnabled ? (
                <form className="iu-client-portal-mini-form" onSubmit={addSignature}>
                  <h3>Firme</h3>
                  <input value={signatureTitle} onChange={(event) => setSignatureTitle(event.target.value)} placeholder="Titolo del documento (es. Mandato professionale)"/>
                  <label className="iu-client-portal-file iu-client-portal-file--studio">
                    <UploadCloud size={15} aria-hidden="true"/>
                    {signatureFile ? signatureFile.name : 'Allega PDF da firmare'}
                    <input
                      type="file"
                      accept="application/pdf"
                      onChange={(event) => setSignatureFile(event.target.files?.[0] || null)}
                    />
                  </label>
                  <button type="submit" disabled={signatureSending || (!signatureTitle.trim() && !signatureFile)}>
                    <FileCheck2 size={16} aria-hidden="true"/>{signatureSending ? 'Invio in corso…' : signatureFile ? 'Allega e richiedi firma' : 'Richiedi firma'}
                  </button>
                  {selectedSignatures.length === 0 ? <span className="iu-client-portal-muted">Nessuna richiesta firma per questa pratica.</span> : null}
                  {selectedSignatures.map((item) => (
                    <span className="iu-client-portal-doc-line" key={rowId(item)}>
                      <strong>{text(item.title)}</strong>
                      <PortalBadge value={item.status}/>
                      {text(item.document_id) ? (
                        <a href={studioPortalDocumentUrl(text(item.document_id))} title="Scarica il documento allegato">
                          <Download size={14} aria-hidden="true"/>PDF allegato
                        </a>
                      ) : null}
                    </span>
                  ))}
                </form>
              ) : (
                <section className="iu-client-portal-mini-form" aria-label="Firme">
                  <h3>Firme</h3>
                  <span>Firma semplice non attiva per questo studio.</span>
                </section>
              )}
              <form className="iu-client-portal-mini-form" onSubmit={addAppointment}>
                <h3>Appuntamenti</h3>
                <label>
                  Data e ora
                  <input
                    id="client-portal-appointment-start"
                    name="startsAt"
                    aria-label="Data e ora"
                    type="datetime-local"
                    required
                    value={appointmentStart}
                    onInput={(event) => setAppointmentStart(event.currentTarget.value)}
                    onChange={(event) => setAppointmentStart(event.target.value)}
                  />
                </label>
                {videoCallsEnabled ? (
                  <label>
                    Link videocall
                    <input
                      id="client-portal-appointment-video"
                      name="videoUrl"
                      aria-label="Link videocall"
                      type="url"
                      value={appointmentVideoUrl}
                      onInput={(event) => setAppointmentVideoUrl(event.currentTarget.value)}
                      onChange={(event) => setAppointmentVideoUrl(event.target.value)}
                      placeholder="https://"
                    />
                  </label>
                ) : (
                  <span className="iu-client-portal-muted">Videocall non attiva per questo studio.</span>
                )}
                <button type="submit" disabled={!payload.canWrite || !appointmentStart.trim()}><CalendarDays size={16} aria-hidden="true"/>Proponi</button>
                {selectedAppointments.map((item) => (
                  <span className="iu-client-portal-appointment-line" key={rowId(item)}>
                    {text(item.starts_at_label) ? <>{text(item.starts_at_label)} · </> : null}{statusLabel(item.status)}
                    {text(item.video_url) ? <a href={text(item.video_url)} target="_blank" rel="noreferrer">Apri videocall</a> : null}
                  </span>
                ))}
              </form>
            </div>
          </div>

          <div className="iu-client-portal-panel iu-client-portal-chat" id="portale-clienti-chat">
            <div className="iu-client-portal-panel__head">
              <h2>Chat cliente</h2>
              <MessageCircle size={18} aria-hidden="true"/>
            </div>
            <div className="iu-client-portal-chat__messages" ref={studioChatRef}>
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
              <textarea
                value={messageBody}
                onChange={(event) => setMessageBody(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    if (messageBody.trim()) void sendMessage(event as unknown as FormEvent)
                  }
                }}
                placeholder="Scrivi al cliente (Invio per inviare, Maiusc+Invio per andare a capo)"
                rows={3}
              />
              <button className="iu-client-portal-button" type="submit" disabled={!messageBody.trim()}><Send size={17} aria-hidden="true"/>Invia al cliente</button>
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

const EMPTY_PROFILE_FORM = {
  displayName: '',
  email: '',
  phone: '',
  fiscalCode: '',
  identityExpiresAt: '',
  birthDate: '',
  birthPlace: '',
  address: '',
  cap: '',
  city: '',
  province: '',
  pec: '',
  vatNumber: '',
  profession: '',
}

function profileFormFromPayload(data: ClientPortalClientPayload): typeof EMPTY_PROFILE_FORM {
  const client = data.client || {}
  const preferences = (client.preferences || {}) as Record<string, unknown>
  const anagrafica = (preferences.anagrafica || {}) as Record<string, unknown>
  return {
    displayName: text(client.display_name),
    email: text(client.email),
    phone: text(client.phone),
    fiscalCode: text(client.fiscal_code),
    identityExpiresAt: text(client.identity_expires_at),
    birthDate: text(anagrafica.birthDate),
    birthPlace: text(anagrafica.birthPlace),
    address: text(anagrafica.address),
    cap: text(anagrafica.cap),
    city: text(anagrafica.city),
    province: text(anagrafica.province),
    pec: text(anagrafica.pec),
    vatNumber: text(anagrafica.vatNumber),
    profession: text(anagrafica.profession),
  }
}

function ClientPortalClient() {
  const [payload, setPayload] = useState<ClientPortalClientPayload>(emptyClientPortal)
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState<Notice | null>(null)
  const [messageBody, setMessageBody] = useState('')
  const [profileForm, setProfileForm] = useState(EMPTY_PROFILE_FORM)
  const [questionnaireResponses, setQuestionnaireResponses] = useState<Record<string, string>>({})
  const [survey, setSurvey] = useState({ rating: 5, comment: '' })
  const token = readClientPortalToken()
  const chatScrollRef = useRef<HTMLDivElement | null>(null)
  const signaturesEnabled = payload.featureFlags['routes.appV2.clientPortal.signatures'] !== false
  const signingWorkflowEnabled = payload.featureFlags['routes.appV2.clientPortal.signingWorkflow'] === true

  const load = async () => {
    setLoading(true)
    const data = await loadClientPortal(token)
    setPayload(data)
    setProfileForm(profileFormFromPayload(data))
    setLoading(false)
  }

  useEffect(() => {
    void load()
  }, [])

  useEffect(() => {
    const node = chatScrollRef.current
    if (node) node.scrollTop = node.scrollHeight
  }, [payload.messages?.length])

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
    // pre-controllo lato client: evita l'upload destinato a fallire e spiega subito il limite
    const limits = payload.uploadLimits
    if (limits?.maxUploadMb && file.size > limits.maxUploadMb * 1024 * 1024) {
      const actualMb = (file.size / (1024 * 1024)).toFixed(1)
      setNotice({
        tone: 'warning',
        text: `Il file pesa ${actualMb} MB ma il limite è ${limits.maxUploadMb} MB. Riduci la dimensione (scansione a risoluzione più bassa o PDF diviso) e riprova.`,
      })
      return
    }
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
  const completion = payload.profileCompletion
  const uploadLimits = payload.uploadLimits

  // Stato reale di ogni passo del percorso, calcolato dai dati e non dal solo
  // record statico: il cliente vede subito cosa ha completato e dove andare.
  const consentsDone = (payload.consents || []).length > 0 && (payload.consents || []).every((item) => numberValue(item.accepted) > 0)
  const documentsDone = (payload.documentRequests || []).length > 0 && (payload.documentRequests || []).every((item) => (
    ['caricato', 'ricevuto', 'approvato'].includes(text(item.status)) ||
    (payload.documents || []).some((doc) => text(doc.request_id) === rowId(item))
  ))
  const signaturesDone = (payload.signatures || []).length > 0 && (payload.signatures || []).every((item) => text(item.status) === 'firmato')
  const appointmentsDone = (payload.appointments || []).some((item) => text(item.status) === 'confermato')
  const checklist = [
    { key: 'privacy', title: 'Privacy e consensi', anchor: '#panel-privacy', done: consentsDone, pending: (payload.consents || []).filter((item) => !numberValue(item.accepted)).length },
    { key: 'anagrafica', title: 'Anagrafica cliente', anchor: '#panel-anagrafica', done: Boolean(completion?.complete), pending: completion ? completion.total - completion.filled : 0 },
    { key: 'documenti', title: 'Documenti richiesti', anchor: '#panel-documenti', done: documentsDone, pending: (payload.documentRequests || []).filter((item) => !['caricato', 'ricevuto', 'approvato'].includes(text(item.status)) && !(payload.documents || []).some((doc) => text(doc.request_id) === rowId(item))).length },
    { key: 'firme', title: 'Documenti da firmare', anchor: '#panel-firme', done: signaturesDone, pending: (payload.signatures || []).filter((item) => text(item.status) !== 'firmato').length },
    { key: 'appuntamenti', title: 'Appuntamento o videocall', anchor: '#panel-appuntamenti', done: appointmentsDone, pending: (payload.appointments || []).filter((item) => text(item.status) === 'proposto').length },
  ]
  const checklistDone = checklist.filter((item) => item.done).length
  const updateProfileField = (field: keyof typeof EMPTY_PROFILE_FORM) => (event: { target: { value: string } }) =>
    setProfileForm((current) => ({ ...current, [field]: event.target.value }))

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
        </div>
      </header>
      <NoticeBar notice={notice}/>

      <section className="iu-client-portal-client-summary">
        <article>
          <span>Percorso completato</span>
          <strong>{checklistDone}/{checklist.length}</strong>
          <progress className="iu-client-portal-progress" value={checklistDone} max={checklist.length}>{checklistDone}</progress>
        </article>
        <article>
          <span>Azioni aperte</span>
          <strong>{numberValue(payload.activityCenter?.openItems)}</strong>
        </article>
        <article>
          <span>Avanzamento pratica</span>
          <strong>{progress}%</strong>
        </article>
      </section>

      <section className="iu-client-portal-client-grid">
        <div className="iu-client-portal-panel">
          <div className="iu-client-portal-panel__head"><h2>Cosa devo fare adesso</h2><ClipboardList size={18} aria-hidden="true"/></div>
          <div className="iu-client-portal-timeline iu-client-portal-timeline--interactive">
            {checklist.map((step) => (
              <a href={step.anchor} key={step.key} className={step.done ? 'is-done' : ''}>
                <span className="iu-client-portal-timeline__dot">{step.done ? <Check size={13} aria-hidden="true"/> : null}</span>
                <strong>{step.title}</strong>
                {step.done
                  ? <em className="iu-client-portal-timeline__state is-done">Fatto</em>
                  : <em className="iu-client-portal-timeline__state">{step.pending > 0 ? `${step.pending} da completare` : 'Da fare'} →</em>}
              </a>
            ))}
          </div>
        </div>

        {signingWorkflowEnabled ? (
          <SigningWorkflowPanel onNotice={(tone, text) => setNotice({ tone, text })} />
        ) : null}

        <form className="iu-client-portal-panel iu-client-portal-form" onSubmit={saveProfile} id="panel-anagrafica">
          <div className="iu-client-portal-panel__head">
            <h2>Anagrafica</h2>
            {completion ? (
              <span className={`iu-client-portal-completion ${completion.complete ? 'is-done' : ''}`}>
                {completion.complete ? <><Check size={13} aria-hidden="true"/>Completa</> : `${completion.filled}/${completion.total} campi`}
              </span>
            ) : <UserRound size={18} aria-hidden="true"/>}
          </div>
          {!completion?.complete ? (
            <p className="iu-client-portal-muted">Compila tutti i campi obbligatori (*): lo studio riceverà conferma automatica appena la scheda è completa.</p>
          ) : null}
          <div className="iu-client-portal-form__grid">
            <label>Nome e cognome *<input value={profileForm.displayName} onChange={updateProfileField('displayName')} autoComplete="name"/></label>
            <label>Email *<input type="email" value={profileForm.email} onChange={updateProfileField('email')} autoComplete="email"/></label>
            <label>Telefono *<input value={profileForm.phone} onChange={updateProfileField('phone')} autoComplete="tel"/></label>
            <label>Codice fiscale *<input className="iu-client-portal-input-upper" value={profileForm.fiscalCode} onChange={updateProfileField('fiscalCode')}/></label>
            <label>Data di nascita *<input type="date" value={profileForm.birthDate} onChange={updateProfileField('birthDate')}/></label>
            <label>Luogo di nascita *<input value={profileForm.birthPlace} onChange={updateProfileField('birthPlace')}/></label>
            <label>Indirizzo (via e civico) *<input value={profileForm.address} onChange={updateProfileField('address')} autoComplete="street-address"/></label>
            <label>CAP *<input value={profileForm.cap} onChange={updateProfileField('cap')} inputMode="numeric" maxLength={5}/></label>
            <label>Città *<input value={profileForm.city} onChange={updateProfileField('city')}/></label>
            <label>Provincia *<input className="iu-client-portal-input-upper" value={profileForm.province} onChange={updateProfileField('province')} maxLength={2}/></label>
            <label>PEC<input type="email" value={profileForm.pec} onChange={updateProfileField('pec')}/></label>
            <label>Partita IVA<input value={profileForm.vatNumber} onChange={updateProfileField('vatNumber')} inputMode="numeric"/></label>
            <label>Professione<input value={profileForm.profession} onChange={updateProfileField('profession')}/></label>
            <label>Scadenza documento d'identità<input type="date" value={profileForm.identityExpiresAt} onChange={updateProfileField('identityExpiresAt')}/></label>
          </div>
          <button className="iu-client-portal-button" type="submit">Salva anagrafica</button>
        </form>

        <div className="iu-client-portal-panel" id="panel-privacy">
          <div className="iu-client-portal-panel__head"><h2>Privacy e consensi</h2><ShieldCheck size={18} aria-hidden="true"/></div>
          {(payload.consents || []).map((consent) => (
            <article className="iu-client-portal-action-row" key={rowId(consent)}>
              <div><strong>{text(consent.consent_key, 'Informativa privacy').replace(/_/g, ' ')}</strong><span>{numberValue(consent.accepted) ? `Accettato il ${text(consent.accepted_at_label)}` : 'Da accettare'}</span></div>
              <button type="button" onClick={() => acceptConsent(text(consent.consent_key))} disabled={Boolean(numberValue(consent.accepted))}>{numberValue(consent.accepted) ? 'Accettato ✓' : 'Accetta'}</button>
            </article>
          ))}
        </div>

        <div className="iu-client-portal-panel" id="panel-documenti">
          <div className="iu-client-portal-panel__head"><h2>Documenti</h2><UploadCloud size={18} aria-hidden="true"/></div>
          {uploadLimits ? (
            <p className="iu-client-portal-upload-hint">Formati accettati: {uploadLimits.allowedLabel} · dimensione massima {uploadLimits.maxUploadMb} MB per file.</p>
          ) : null}
          {(payload.documentRequests || []).length === 0 ? <span className="iu-client-portal-muted">Lo studio non ha ancora richiesto documenti.</span> : null}
          {(payload.documentRequests || []).map((requestItem) => {
            const uploaded = (payload.documents || []).find((doc) => text(doc.request_id) === rowId(requestItem))
            return (
              <article className="iu-client-portal-action-row" key={rowId(requestItem)}>
                <div>
                  <strong>{text(requestItem.title)}</strong>
                  <span>{uploaded ? `Caricato: ${text(uploaded.filename)}` : statusLabel(requestItem.status)}</span>
                </div>
                <label className="iu-client-portal-file">
                  <UploadCloud size={16} aria-hidden="true"/>{uploaded ? 'Sostituisci' : 'Carica'}
                  <input
                    type="file"
                    accept={(uploadLimits?.allowedUploadTypes || []).join(',') || undefined}
                    onChange={(event) => { uploadDocument(event.target.files?.[0] || null, rowId(requestItem)); event.target.value = '' }}
                  />
                </label>
              </article>
            )
          })}
        </div>

        <div className="iu-client-portal-panel" id="panel-firme">
          <div className="iu-client-portal-panel__head"><h2>Documenti da firmare</h2><FileCheck2 size={18} aria-hidden="true"/></div>
          {!signaturesEnabled ? <span className="iu-client-portal-muted">Firma semplice non attiva per questo studio.</span> : null}
          {signaturesEnabled && (payload.signatures || []).length === 0 ? <span className="iu-client-portal-muted">Nessun documento in firma.</span> : null}
          {signaturesEnabled && (payload.signatures || []).map((signature) => {
            const documentId = text(signature.document_id)
            const signed = text(signature.status) === 'firmato'
            return (
              <article className="iu-client-portal-action-row iu-client-portal-signature-row" key={rowId(signature)}>
                <div>
                  <strong>{text(signature.title)}</strong>
                  <span>{statusLabel(signature.status)}</span>
                  {documentId ? (
                    <a className="iu-client-portal-doc-download" href={clientPortalDocumentUrl(documentId)}>
                      <Download size={14} aria-hidden="true"/>Scarica e leggi il documento
                    </a>
                  ) : null}
                </div>
                <button type="button" onClick={() => completeSignature(rowId(signature))} disabled={signed}>
                  {signed ? 'Firmato ✓' : 'Conferma firma'}
                </button>
              </article>
            )
          })}
        </div>

        <div className="iu-client-portal-panel iu-client-portal-chat" id="chat-cliente">
          <div className="iu-client-portal-panel__head"><h2>Chat con lo studio</h2><MessageCircle size={18} aria-hidden="true"/></div>
          <div className="iu-client-portal-chat__messages" ref={chatScrollRef}>
            {messages.length === 0 ? (
              <span className="iu-client-portal-muted">Nessun messaggio: scrivi qui per qualsiasi domanda, lo studio risponde appena possibile.</span>
            ) : null}
            {messages.map((message) => (
              <article key={rowId(message)} className={text(message.sender_type) === 'cliente' ? 'from-client' : 'from-studio'}>
                <strong>{text(message.sender_type) === 'cliente' ? 'Tu' : 'Studio'}</strong>
                <p>{text(message.body)}</p>
                <span>{text(message.created_at_label)}</span>
              </article>
            ))}
          </div>
          <form className="iu-client-portal-chat__composer" onSubmit={sendMessage}>
            <textarea
              value={messageBody}
              onChange={(event) => setMessageBody(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  if (messageBody.trim()) void sendMessage(event as unknown as FormEvent)
                }
              }}
              placeholder="Scrivi allo studio (Invio per inviare, Maiusc+Invio per andare a capo)"
              rows={3}
            />
            <button className="iu-client-portal-button" type="submit" disabled={!messageBody.trim()}><Send size={17} aria-hidden="true"/>Invia</button>
          </form>
        </div>

        <div className="iu-client-portal-panel" id="panel-appuntamenti">
          <div className="iu-client-portal-panel__head"><h2>Appuntamenti</h2><CalendarDays size={18} aria-hidden="true"/></div>
          {(payload.appointments || []).length === 0 ? <span className="iu-client-portal-muted">Nessun appuntamento proposto.</span> : null}
          {(payload.appointments || []).map((appointment) => (
            <article className="iu-client-portal-action-row" key={rowId(appointment)}>
              <div>
                <strong>{text(appointment.title)}</strong>
                <span>{text(appointment.starts_at_label) ? <>{text(appointment.starts_at_label)} · </> : null}{statusLabel(appointment.status)}</span>
                {text(appointment.video_url) ? (
                  <a className="iu-client-portal-video-link" href={text(appointment.video_url)} target="_blank" rel="noreferrer">
                    <Video size={15} aria-hidden="true"/>Apri videocall
                  </a>
                ) : null}
              </div>
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
