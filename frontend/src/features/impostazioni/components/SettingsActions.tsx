import { useEffect, useMemo, useRef, useState } from 'react'
import { Bot, CheckCircle2, CircleAlert, ClipboardCheck, Cpu, Database, Download, FileOutput, FileQuestion, HardDrive, Play, RefreshCw, ShieldCheck, Smartphone, Workflow } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { IusStatusBadge } from '@/components/iusentra'
import {
  checkLocalAiViaLocalSigner,
  detectMobileAiInstallPlan,
  localAiModelLabel,
  prepareLocalAiViaLocalSigner,
  type LocalAiLocalResult,
  type MobileAiInstallPlan,
} from '../localAi'
import { saveSignatureCertificateStatus } from '../api'
import { checkLocalSigner, testPecSmtpViaLocalSigner, type LocalSignerCheck } from '../localSigner'
import type { AiRuntimePayload, SettingTone, SettingsPayload, SettingsSection, TestResult } from '../types'

function aiStatusLabel(aiStatus: AiRuntimePayload | null): string {
  const details = aiStatus?.status_payload?.runtime
  if (details && typeof details === 'object' && !Array.isArray(details) && 'status' in details) {
    const status = String((details as Record<string, unknown>).status || '').toLowerCase()
    if (['ok', 'ready', 'running', 'available'].includes(status)) return 'pronta'
    if (['disabled', 'off'].includes(status)) return 'disattivata'
    if (['missing', 'unavailable', 'error', 'failed'].includes(status)) return 'da verificare'
  }
  return 'non verificato'
}

function ResultAlert({ result }: { result: TestResult | LocalSignerCheck | AiRuntimePayload | LocalAiLocalResult | null }) {
  if (!result) return null
  const ok = Boolean(result.ok)
  const message = 'message' in result ? String(result.message || '') : ''
  return (
    <Alert className={ok ? 'iu-settings-alert is-success' : 'iu-settings-alert is-warning'}>
      {ok ? <CheckCircle2 /> : <RefreshCw />}
      <AlertTitle>{ok ? 'Verifica completata' : 'Verifica da completare'}</AlertTitle>
      <AlertDescription>{message || 'Risultato disponibile.'}</AlertDescription>
    </Alert>
  )
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function asText(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function numberLabel(value: unknown, suffix: string): string {
  const raw = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(raw) || raw <= 0) return ''
  const amount = raw >= 10 ? Math.round(raw) : Number(raw.toFixed(1))
  return `${amount} ${suffix}`
}

function aiProfileLabel(value: unknown): string {
  const profile = asText(value).toLowerCase()
  if (profile === 'strong') return 'PC adatto a modelli completi'
  if (profile === 'medium') return 'PC adatto a modelli medi'
  if (profile === 'weak') return 'PC da usare con modelli leggeri'
  return 'PC da verificare'
}

function aiPayload(localAiResult: LocalAiLocalResult | null, aiStatus: AiRuntimePayload | null): Record<string, unknown> {
  if (localAiResult?.payload) return localAiResult.payload
  return record(aiStatus?.status_payload)
}

function lexDatasetStatus(data: SettingsPayload): Record<string, unknown> {
  return record(record(data.ai).lex_dataset_status)
}

function aiInstallerHref(payload: Record<string, unknown>): string {
  const installer = record(payload.installer)
  return asText(installer.asset_download_url) || asText(installer.latest_release_url) || 'https://ollama.com/download'
}

function aiDetailRows(payload: Record<string, unknown>): Array<{ label: string; value: string; icon: typeof Cpu }> {
  const runtime = record(payload.runtime)
  const models = record(payload.resolved_models)
  const pc = [
    aiProfileLabel(runtime.hardware_profile),
    numberLabel(runtime.ram_gb, 'GB RAM'),
    numberLabel(runtime.disk_free_gb, 'GB liberi'),
  ].filter(Boolean).join(', ')
  return [
    { label: 'PC verificato', value: pc, icon: Cpu },
    { label: "Risposte dell'assistente", value: localAiModelLabel(asText(models.chat) || 'automatico'), icon: Bot },
    { label: 'Ricerca nei documenti', value: localAiModelLabel(asText(models.embed) || 'automatico'), icon: HardDrive },
  ].filter((row) => Boolean(row.value))
}

function openMobileLexFromSettings(plan: MobileAiInstallPlan | null) {
  const detail = {
    context: 'impostazioni-ai-mobile',
    title: 'Lex AI mobile',
    body: plan?.isPortable
      ? 'Uso il motore AI autorizzato dello studio e tengo conto del dispositivo rilevato.'
      : 'Posso aiutarti a preparare AI locale sul PC dello studio.',
    pagePath: window.location.pathname,
  }
  window.dispatchEvent(new CustomEvent('iusentra:lex-context', { detail }))
  window.dispatchEvent(new CustomEvent('iusentra:open-floating-lex', { detail }))
}

function MobileAiSetupPanel({
  plan,
  installerHref,
  onPreparePc,
  preparing,
}: {
  plan: MobileAiInstallPlan | null
  installerHref: string
  onPreparePc: () => void
  preparing: boolean
}) {
  const isPortable = plan?.isPortable === true
  const rows = plan ? [
    { label: 'Dispositivo', value: plan.deviceLabel, icon: Smartphone },
    { label: 'Risorse rilevate', value: plan.resourceLabel, icon: Cpu },
    { label: isPortable ? 'Language model' : 'Modello consigliato', value: plan.modelLabel, icon: Bot },
    { label: 'Percorso sicuro', value: plan.pathLabel, icon: ShieldCheck },
  ] : [
    { label: 'Dispositivo', value: 'Rilevamento in corso', icon: Smartphone },
  ]

  return (
    <div className="iu-settings-mobile-ai">
      <div className="iu-settings-mobile-ai__head">
        <div>
          <strong>AI su telefono e tablet</strong>
          <span>
            Su telefono e tablet non si installa Ollama: Lex usa il motore AI nell'ambiente di produzione IUSENTRA.
          </span>
        </div>
        <IusStatusBadge tone={isPortable ? 'info' : 'success'}>
          {isPortable ? 'Telefono o tablet rilevato' : 'PC rilevato'}
        </IusStatusBadge>
      </div>
      <div className="iu-settings-mobile-ai__grid" aria-live="polite">
        {rows.map((row) => {
          const Icon = row.icon
          return (
            <article key={row.label}>
              <Icon />
              <div>
                <span>{row.label}</span>
                <strong>{row.value}</strong>
              </div>
            </article>
          )
        })}
      </div>
      {plan?.missingSignals ? (
        <Alert className="iu-settings-alert is-warning">
          <RefreshCw />
          <AlertTitle>Rilevamento incompleto</AlertTitle>
          <AlertDescription>
            Questo dispositivo non espone RAM, core o spazio libero. IUSENTRA non forza download pesanti: usa Lex con il motore AI dello studio finché il dispositivo non è verificabile.
          </AlertDescription>
        </Alert>
      ) : null}
      {isPortable ? (
        <Alert className="iu-settings-alert is-info">
          <ShieldCheck />
          <AlertTitle>Ollama resta nell'ambiente di produzione</AlertTitle>
          <AlertDescription>
            Il telefono o tablet usa IUSENTRA come interfaccia sicura. Il language model, gli embedding, il download dei modelli e l'indicizzazione restano nell'ambiente di produzione sempre acceso, così Lex continua a funzionare anche quando i PC dello studio sono spenti.
          </AlertDescription>
        </Alert>
      ) : null}
      <div className="iu-settings-actions-panel__buttons">
        <Button type="button" variant="outline" onClick={() => openMobileLexFromSettings(plan)}>
          <Bot data-icon="inline-start" />
          Apri Lex AI
        </Button>
        {!isPortable ? (
          <>
            <Button type="button" variant="outline" disabled={!plan?.canPrepareOnThisDevice || preparing} onClick={onPreparePc}>
              <Cpu data-icon="inline-start" />
              {preparing ? 'Preparazione in corso' : 'Prepara su questo PC'}
            </Button>
            <Button type="button" variant="outline" asChild>
              <a href={installerHref} target="_blank" rel="noreferrer">
                <Download data-icon="inline-start" />
                Scarica Ollama ufficiale
              </a>
            </Button>
          </>
        ) : null}
      </div>
    </div>
  )
}

const lexDatasetIcons = {
  rag: Database,
  qa_review: FileQuestion,
  alpaca: FileOutput,
  sharegpt: FileOutput,
  manual_training: Workflow,
  latest_job: ClipboardCheck,
  errors: CircleAlert,
}

type LexReviewItem = {
  id: string
  question: string
  answer: string
  status: string
  tone: SettingTone
  sourceTitle: string
  sourceDetail: string
  privacy: string
  reviewNote: string
}

type LexReviewQueue = {
  ok: boolean
  message: string
  summary: {
    total: number
    pending: number
    approved: number
    rejected: number
  }
  items: LexReviewItem[]
}

function toneValue(value: unknown): SettingTone {
  const tone = asText(value) as SettingTone
  if (['primary', 'success', 'warning', 'danger', 'neutral', 'info'].includes(tone)) return tone
  return 'neutral'
}

function numberValue(value: unknown): number {
  const parsed = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function daysLabel(value: unknown): string {
  if (value === undefined || value === null || value === '') return ''
  const days = numberValue(value)
  if (!Number.isFinite(days)) return ''
  if (days < 0) return `scaduto da ${Math.abs(days)} ${Math.abs(days) === 1 ? 'giorno' : 'giorni'}`
  if (days === 0) return 'scade oggi'
  return `mancano ${days} ${days === 1 ? 'giorno' : 'giorni'}`
}

function normalizeReviewQueue(payload: unknown): LexReviewQueue {
  const source = record(payload)
  const summary = record(source.summary)
  const items = Array.isArray(source.items)
    ? source.items.map(record).map((item) => ({
        id: asText(item.id),
        question: asText(item.question),
        answer: asText(item.answer),
        status: asText(item.status) || 'Da revisionare',
        tone: toneValue(item.tone),
        sourceTitle: asText(item.sourceTitle) || 'Documento studio',
        sourceDetail: asText(item.sourceDetail),
        privacy: asText(item.privacy) || 'uso interno',
        reviewNote: asText(item.reviewNote),
      })).filter((item) => Boolean(item.id))
    : []
  return {
    ok: Boolean(source.ok),
    message: asText(source.message),
    summary: {
      total: numberValue(summary.total),
      pending: numberValue(summary.pending),
      approved: numberValue(summary.approved),
      rejected: numberValue(summary.rejected),
    },
    items,
  }
}

function LexDatasetStatusPanel({ status }: { status: Record<string, unknown> }) {
  const cards = Array.isArray(status.cards) ? status.cards.map(record) : []
  const privacy = record(status.privacy)
  const schedule = record(status.schedule)
  const [reviewOpen, setReviewOpen] = useState(false)
  const [reviewLoading, setReviewLoading] = useState(false)
  const [reviewQueue, setReviewQueue] = useState<LexReviewQueue | null>(null)
  const [reviewError, setReviewError] = useState('')
  const [reviewAction, setReviewAction] = useState('')
  const [reviewEdits, setReviewEdits] = useState<Record<string, { question: string; answer: string }>>({})
  if (!cards.length) return null
  const storeReviewQueue = (payload: unknown) => {
    const queue = normalizeReviewQueue(payload)
    const edits: Record<string, { question: string; answer: string }> = {}
    queue.items.forEach((item) => {
      edits[item.id] = { question: item.question, answer: item.answer }
    })
    setReviewQueue(queue)
    setReviewEdits(edits)
  }
  const loadReviewQueue = async () => {
    setReviewOpen(true)
    setReviewLoading(true)
    setReviewError('')
    try {
      const response = await fetch('/api/v1/ui/impostazioni/ai/lex-dataset/review', {
        headers: { Accept: 'application/json' },
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok || !record(payload).ok) {
        throw new Error(asText(record(payload).message) || 'Coda revisione non disponibile.')
      }
      storeReviewQueue(payload)
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : 'Coda revisione non disponibile.')
    } finally {
      setReviewLoading(false)
    }
  }
  const updateReviewEdit = (id: string, field: 'question' | 'answer', value: string) => {
    setReviewEdits((current) => ({
      ...current,
      [id]: {
        question: current[id]?.question || '',
        answer: current[id]?.answer || '',
        [field]: value,
      },
    }))
  }
  const saveReview = async (item: LexReviewItem, action: 'approve' | 'reject') => {
    setReviewAction(item.id)
    setReviewError('')
    const edit = reviewEdits[item.id] || { question: item.question, answer: item.answer }
    try {
      const response = await fetch(`/api/v1/ui/impostazioni/ai/lex-dataset/review/${encodeURIComponent(item.id)}`, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action,
          question: edit.question,
          answer: edit.answer,
          note: action === 'approve' ? 'Approvata da Impostazioni AI.' : 'Scartata da Impostazioni AI.',
        }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok || !record(payload).ok) {
        throw new Error(asText(record(payload).message) || 'Revisione non salvata.')
      }
      storeReviewQueue(payload)
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : 'Revisione non salvata.')
    } finally {
      setReviewAction('')
    }
  }
  const openCard = (card: Record<string, unknown>) => {
    if (asText(card.id) === 'qa_review') {
      void loadReviewQueue()
      return
    }
    const label = asText(card.label) || 'Archivio Lex'
    window.dispatchEvent(new CustomEvent('iusentra:lex-context', {
      detail: {
        context: asText(card.action_context) || 'impostazioni-ai-archivio',
        title: `Lex AI - ${label}`,
        body: asText(card.note) || 'Controllo archivio e revisione Lex dello studio.',
        pagePath: window.location.pathname,
      },
    }))
    window.dispatchEvent(new CustomEvent('iusentra:open-floating-lex'))
  }

  return (
    <section className="iu-settings-lex-dataset" aria-label="Archivio e revisione Lex">
      <div className="iu-settings-lex-dataset__head">
        <div>
          <strong>Archivio e revisione Lex</strong>
          <span>{asText(privacy.message) || "Il contesto resta nell'ambiente IUSENTRA autorizzato e gli esempi richiedono revisione."}</span>
          <span>{asText(schedule.label) ? `${asText(schedule.label)} ogni notte alle ${asText(schedule.time) || '01:45'}` : ''}</span>
          <span>
            Questo pannello non installa né addestra il language model: controlla documenti indicizzati,
            coda di revisione ed export facoltativi.
          </span>
        </div>
        <IusStatusBadge tone="info">{asText(status.storage_label) || 'Archivio riservato'}</IusStatusBadge>
      </div>
      <div className="iu-settings-lex-dataset__grid">
        {cards.map((card) => {
          const id = asText(card.id)
          const Icon = lexDatasetIcons[id as keyof typeof lexDatasetIcons] || Bot
          const value = asText(card.value)
          return (
            <button type="button" key={id || asText(card.label)} onClick={() => openCard(card)}>
              <Icon />
              <div>
                <span>{asText(card.label)}</span>
                <strong>{asText(card.status)}</strong>
                <small>{asText(card.note)}</small>
              </div>
              <IusStatusBadge tone={toneValue(card.tone)}>{value || asText(card.action_label) || 'Apri'}</IusStatusBadge>
            </button>
          )
        })}
      </div>
      {reviewOpen ? (
        <div className="iu-settings-lex-review" aria-live="polite">
          <div className="iu-settings-lex-review__head">
            <div>
              <strong>Coda revisione domande</strong>
              <span>{reviewQueue?.message || 'Le domande sono generate da IUSENTRA: lo studio approva, corregge o scarta.'}</span>
            </div>
            <div className="iu-settings-lex-review__counts">
              <IusStatusBadge tone="warning">{reviewQueue?.summary.pending ?? 0} da vedere</IusStatusBadge>
              <IusStatusBadge tone="success">{reviewQueue?.summary.approved ?? 0} approvate</IusStatusBadge>
              <IusStatusBadge tone="danger">{reviewQueue?.summary.rejected ?? 0} scartate</IusStatusBadge>
            </div>
          </div>
          {reviewError ? (
            <Alert className="iu-settings-alert is-warning">
              <CircleAlert />
              <AlertTitle>Revisione non aggiornata</AlertTitle>
              <AlertDescription>{reviewError}</AlertDescription>
            </Alert>
          ) : null}
          {reviewLoading ? (
            <div className="iu-settings-lex-review__empty">
              <RefreshCw />
              <span>Caricamento coda revisione.</span>
            </div>
          ) : reviewQueue?.items.length ? (
            <div className="iu-settings-lex-review__list">
              {reviewQueue.items.map((item) => {
                const edit = reviewEdits[item.id] || { question: item.question, answer: item.answer }
                const busy = reviewAction === item.id
                return (
                  <article key={item.id} className="iu-settings-lex-review__item">
                    <div className="iu-settings-lex-review__meta">
                      <div>
                        <strong>{item.sourceTitle}</strong>
                        <span>{item.sourceDetail || item.privacy}</span>
                      </div>
                      <IusStatusBadge tone={item.tone}>{item.status}</IusStatusBadge>
                    </div>
                    <label>
                      <span>Domanda proposta</span>
                      <textarea
                        rows={2}
                        value={edit.question}
                        onChange={(event) => updateReviewEdit(item.id, 'question', event.currentTarget.value)}
                      />
                    </label>
                    <label>
                      <span>Risposta proposta</span>
                      <textarea
                        rows={3}
                        value={edit.answer}
                        onChange={(event) => updateReviewEdit(item.id, 'answer', event.currentTarget.value)}
                      />
                    </label>
                    <div className="iu-settings-lex-review__actions">
                      <Button type="button" size="sm" onClick={() => void saveReview(item, 'approve')} disabled={busy}>
                        <CheckCircle2 data-icon="inline-start" />
                        {busy ? 'Salvataggio' : 'Salva e approva'}
                      </Button>
                      <Button type="button" size="sm" variant="outline" onClick={() => void saveReview(item, 'reject')} disabled={busy}>
                        <CircleAlert data-icon="inline-start" />
                        Scarta
                      </Button>
                    </div>
                  </article>
                )
              })}
            </div>
          ) : (
            <div className="iu-settings-lex-review__empty">
              <CheckCircle2 />
              <span>Nessuna domanda in attesa. Il dataset resta fermo finché lo studio non approva nuovo materiale.</span>
            </div>
          )}
        </div>
      ) : null}
    </section>
  )
}

export function SettingsActions({
  section,
  values,
  data,
  testResult,
  aiStatus,
  onTest,
  onRefreshAi,
  onPrepareAi,
  onReload,
}: {
  section: SettingsSection
  values: Record<string, unknown>
  data: SettingsPayload
  testResult: TestResult | null
  aiStatus: AiRuntimePayload | null
  onTest: (testId: string, values: Record<string, unknown>) => Promise<TestResult>
  onRefreshAi: () => Promise<AiRuntimePayload>
  onPrepareAi: (force?: boolean) => Promise<AiRuntimePayload>
  onReload: () => unknown
}) {
  const [localSigner, setLocalSigner] = useState<LocalSignerCheck | null>(null)
  const [certificateSaving, setCertificateSaving] = useState(false)
  const [certificateMessage, setCertificateMessage] = useState('')
  const [pecLocalResult, setPecLocalResult] = useState<LocalSignerCheck | null>(null)
  const [pecChecking, setPecChecking] = useState(false)
  const [localAiResult, setLocalAiResult] = useState<LocalAiLocalResult | null>(null)
  const [mobileAiPlan, setMobileAiPlan] = useState<MobileAiInstallPlan | null>(null)
  const [aiChecking, setAiChecking] = useState(false)
  const [aiPreparing, setAiPreparing] = useState(false)
  const aiAutoCheckKey = useMemo(
    () => `${data.local_signer.base_url}|${data.local_signer.restart_protocol}|${String(values.ollama_url || values.base_url || '')}`,
    [data.local_signer.base_url, data.local_signer.restart_protocol, values],
  )
  const aiAutoChecked = useRef('')

  useEffect(() => {
    if (section !== 'ai' || !mobileAiPlan || mobileAiPlan.isPortable || localAiResult || aiChecking) return
    if (!data.local_signer.base_url || aiAutoChecked.current === aiAutoCheckKey) return
    aiAutoChecked.current = aiAutoCheckKey
    setAiChecking(true)
    checkLocalAiViaLocalSigner(
      data.local_signer.base_url,
      data.local_signer.restart_protocol,
      values,
    )
      .then(setLocalAiResult)
      .catch(() => undefined)
      .finally(() => setAiChecking(false))
  }, [aiAutoCheckKey, aiChecking, data.local_signer.base_url, data.local_signer.restart_protocol, localAiResult, mobileAiPlan, section, values])

  useEffect(() => {
    if (section !== 'ai') return
    let mounted = true
    void detectMobileAiInstallPlan().then((plan) => {
      if (mounted) setMobileAiPlan(plan)
    })
    return () => {
      mounted = false
    }
  }, [section])

  if (section === 'studio' || section === 'scheduler') {
    return (
      <Alert className="iu-settings-alert">
        <ShieldCheck />
        <AlertTitle>Controllo configurazione</AlertTitle>
        <AlertDescription>
          Questa sezione viene controllata al momento del salvataggio e registrata nello storico dello studio.
        </AlertDescription>
      </Alert>
    )
  }

  if (section === 'firma') {
    const firmaSettings = record(data.firma)
    const savedExpiry = asText(firmaSettings.certificato_scadenza_it) || asText(firmaSettings.certificato_scadenza)
    const savedDays = firmaSettings.certificato_giorni_scadenza
    const savedSubject = asText(firmaSettings.certificato_soggetto)
    const savedFiscalCode = asText(firmaSettings.certificato_codice_fiscale)
    const savedIssuer = asText(firmaSettings.certificato_emittente)
    const latestCertificate = localSigner?.certificate
    const visibleExpiry = latestCertificate?.scadenza_it || savedExpiry
    const visibleDays = latestCertificate?.giorni_scadenza ?? savedDays
    const visibleSubject = latestCertificate?.soggetto || savedSubject
    const visibleFiscalCode = latestCertificate?.codice_fiscale || savedFiscalCode
    const visibleIssuer = latestCertificate?.emittente || savedIssuer
    const visibleDaysNumber = visibleDays === undefined || visibleDays === null || visibleDays === '' ? null : numberValue(visibleDays)
    const warningActive = Boolean(firmaSettings.certificato_avviso_login) || (visibleDaysNumber !== null && visibleDaysNumber <= 20)

    const runLocalSignerCheck = async () => {
      setCertificateMessage('')
      const result = await checkLocalSigner(data.local_signer.base_url, data.local_signer.restart_protocol)
      setLocalSigner(result)
      if (!result.certificate?.scadenza) {
        setCertificateMessage('Local Signer verificato: nessuna scadenza certificato leggibile in questa risposta.')
        return
      }
      setCertificateSaving(true)
      try {
        const saved = await saveSignatureCertificateStatus({ ...result.certificate })
        setCertificateMessage(saved.message || 'Scadenza certificato firma salvata.')
        void onReload()
      } catch {
        setCertificateMessage('Scadenza letta, ma il salvataggio nelle impostazioni non è riuscito. Ripeti la verifica.')
      } finally {
        setCertificateSaving(false)
      }
    }

    return (
      <div className="iu-settings-actions-panel">
        <div>
          <strong>IUSENTRA Local Signer</strong>
          <span>Il dispositivo di firma viene verificato sul PC in uso, senza inviare il PIN allo studio online.</span>
        </div>
        <article className={`iu-settings-certificate ${warningActive && visibleExpiry ? 'is-warning' : ''}`}>
          <div className="iu-settings-certificate__head">
            <ShieldCheck aria-hidden="true" />
            <div>
              <span>Certificato memorizzato</span>
              <strong>{visibleExpiry || 'Nessuna scadenza salvata'}</strong>
            </div>
            {visibleExpiry ? <IusStatusBadge tone={warningActive ? 'warning' : 'success'}>{daysLabel(visibleDays) || 'data salvata'}</IusStatusBadge> : null}
          </div>
          <dl>
            {visibleFiscalCode ? <div><dt>Codice fiscale</dt><dd>{visibleFiscalCode}</dd></div> : null}
            {visibleSubject ? <div><dt>Intestatario</dt><dd>{visibleSubject}</dd></div> : null}
            {visibleIssuer ? <div><dt>Emesso da</dt><dd>{visibleIssuer}</dd></div> : null}
          </dl>
          {!visibleExpiry ? <p>Premi verifica dispositivo per leggere e salvare automaticamente la scadenza dal certificato presente sul PC.</p> : null}
        </article>
        <div className="iu-settings-actions-panel__buttons">
          <Button type="button" variant="outline" disabled={certificateSaving} onClick={() => void runLocalSignerCheck()}>
            <ShieldCheck data-icon="inline-start" />
            {certificateSaving ? 'Salvataggio scadenza' : 'Verifica dispositivo collegato'}
          </Button>
          <Button type="button" variant="outline" asChild>
            <a href={data.local_signer.downloads.windows} target="_blank" rel="noreferrer">
              <Download data-icon="inline-start" />
              Installa su Windows
            </a>
          </Button>
        </div>
        {certificateMessage ? (
          <Alert className={certificateMessage.includes('non è riuscito') ? 'iu-settings-alert is-warning' : 'iu-settings-alert is-info'}>
            <ClipboardCheck />
            <AlertTitle>Aggiornamento certificato</AlertTitle>
            <AlertDescription>{certificateMessage}</AlertDescription>
          </Alert>
        ) : null}
        <ResultAlert result={localSigner} />
      </div>
    )
  }

  if (section === 'ai') {
    const payload = aiPayload(localAiResult, aiStatus)
    const rows = aiDetailRows(payload)
    const installerHref = aiInstallerHref(payload)
    const isPortableAiDevice = mobileAiPlan?.isPortable === true
    const isDetectingAiDevice = mobileAiPlan === null

    const runAiCheck = async () => {
      setAiChecking(true)
      try {
        setLocalAiResult(await checkLocalAiViaLocalSigner(
          data.local_signer.base_url,
          data.local_signer.restart_protocol,
          values,
        ))
      } finally {
        setAiChecking(false)
      }
    }

    const runAiPrepare = async () => {
      setAiPreparing(true)
      try {
        setLocalAiResult(await prepareLocalAiViaLocalSigner(
          data.local_signer.base_url,
          data.local_signer.restart_protocol,
          values,
          false,
        ))
      } finally {
        setAiPreparing(false)
      }
    }

    return (
      <div className="iu-settings-actions-panel">
        {isDetectingAiDevice ? (
          <div>
            <strong>Rilevamento dispositivo</strong>
            <span>IUSENTRA verifica se stai usando PC, telefono o tablet prima di proporre azioni locali.</span>
          </div>
        ) : isPortableAiDevice ? (
          <Alert className="iu-settings-alert is-info">
            <ShieldCheck />
            <AlertTitle>AI nell'ambiente di produzione</AlertTitle>
            <AlertDescription>
              Da telefono e tablet Lex usa il motore AI nell'ambiente di produzione IUSENTRA.
              Language model, embedding e indice documenti restano in un ambiente sempre acceso;
              i controlli locali di Ollama restano disponibili solo sui PC dello studio.
            </AlertDescription>
          </Alert>
        ) : (
          <>
            <div>
              <strong>AI locale sul PC</strong>
              <span>
                IUSENTRA controlla il computer, sceglie i modelli adatti e prepara Ollama se manca.
                Stato: <IusStatusBadge>{localAiResult?.ok ? 'pronta' : aiStatusLabel(aiStatus)}</IusStatusBadge>
              </span>
            </div>
            <div className="iu-settings-actions-panel__buttons">
              <Button type="button" variant="outline" disabled={aiChecking} onClick={() => { void runAiCheck() }}>
                <RefreshCw data-icon="inline-start" />
                {aiChecking ? 'Controllo in corso' : 'Verifica PC e modelli'}
              </Button>
              <Button type="button" variant="outline" disabled={aiPreparing} onClick={() => { void runAiPrepare() }}>
                <Bot data-icon="inline-start" />
                {aiPreparing ? 'Preparazione in corso' : 'Prepara AI locale'}
              </Button>
              <Button type="button" variant="outline" asChild>
                <a href={installerHref} target="_blank" rel="noreferrer">
                  <Download data-icon="inline-start" />
                  Scarica Ollama
                </a>
              </Button>
            </div>
            <ResultAlert result={localAiResult || aiStatus} />
            {rows.length > 0 && (
              <div className="iu-settings-ai-grid" aria-live="polite">
                {rows.map((row) => {
                  const Icon = row.icon
                  return (
                    <article key={row.label}>
                      <Icon />
                      <div>
                        <span>{row.label}</span>
                        <strong>{row.value}</strong>
                      </div>
                    </article>
                  )
                })}
              </div>
            )}
          </>
        )}
        <MobileAiSetupPanel
          plan={mobileAiPlan}
          installerHref={installerHref}
          onPreparePc={() => { void runAiPrepare() }}
          preparing={aiPreparing}
        />
        <LexDatasetStatusPanel status={lexDatasetStatus(data)} />
      </div>
    )
  }

  if (section === 'pec') {
    const runPecSendCheck = async () => {
      setPecChecking(true)
      setPecLocalResult(null)
      try {
        const result = await testPecSmtpViaLocalSigner(
          data.local_signer.base_url,
          data.local_signer.restart_protocol,
          values,
          data.pec.password,
        )
        setPecLocalResult(result)
      } finally {
        setPecChecking(false)
      }
    }

    const runPecReceiveCheck = () => {
      setPecLocalResult(null)
      void onTest('pec-imap', values)
    }

    return (
      <div className="iu-settings-actions-panel">
        <div>
          <strong>Verifiche PEC</strong>
          <span>Il controllo dell'invio parte dal PC in uso: la password resta sul dispositivo locale.</span>
        </div>
        <div className="iu-settings-actions-panel__buttons">
          <Button type="button" variant="outline" disabled={pecChecking} onClick={() => { void runPecSendCheck() }}>
            <Play data-icon="inline-start" />
            {pecChecking ? 'Verifica in corso' : 'Verifica invio PEC'}
          </Button>
          <Button type="button" variant="outline" onClick={runPecReceiveCheck}>
            <Play data-icon="inline-start" />
            Verifica ricezione PEC
          </Button>
        </div>
        <ResultAlert result={pecLocalResult || testResult} />
      </div>
    )
  }

  if (section === 'sdi') {
    const mode = asText(values.modalita)
    const channelReady = Boolean(values.canale_configurato) || Boolean(values.codice_canale || values.nome_intermediario || values.indirizzo_servizio)
    const modeLabel = mode === 'canale_accreditato'
      ? 'Canale accreditato dello studio'
      : mode === 'intermediario'
        ? 'Intermediario delegato'
        : 'Portale o registrazione manuale'
    return (
      <div className="iu-settings-actions-panel">
        <div>
          <strong>Presidio SdI</strong>
          <span>{modeLabel}. {channelReady ? 'Dati canale presenti: verifica accordi e ricevute sul servizio reale.' : 'Invio automatico non attivo finché manca un canale reale configurato.'}</span>
        </div>
        <Alert className={channelReady ? 'iu-settings-alert is-success' : 'iu-settings-alert is-warning'}>
          <ShieldCheck />
          <AlertTitle>{channelReady ? 'Canale da verificare sul servizio reale' : 'Registrazione manuale presidiata'}</AlertTitle>
          <AlertDescription>
            IUSENTRA prepara XML FatturaPA e registra identificativo, ricevute ed esiti. La trasmissione al Sistema di Interscambio avviene solo tramite portale, intermediario o canale accreditato configurato dallo studio.
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  const tests = section === 'smtp'
    ? [['smtp', 'Verifica invio email'], ['smtp-imap', 'Verifica ricezione email']]
    : [['whatsapp', 'Invia test WhatsApp']]

  return (
    <div className="iu-settings-actions-panel">
      <div>
        <strong>Verifiche operative</strong>
        <span>I test usano i valori inseriti, preservando le credenziali salvate se il campo resta vuoto.</span>
      </div>
      <div className="iu-settings-actions-panel__buttons">
        {tests.map(([id, label]) => (
          <Button type="button" variant="outline" onClick={() => { void onTest(id, values) }} key={id}>
            <Play data-icon="inline-start" />
            {label}
          </Button>
        ))}
      </div>
      <ResultAlert result={testResult} />
    </div>
  )
}
