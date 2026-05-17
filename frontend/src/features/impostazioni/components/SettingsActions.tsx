import { useEffect, useMemo, useRef, useState } from 'react'
import { Bot, CheckCircle2, Cpu, Download, HardDrive, Play, RefreshCw, ShieldCheck, Smartphone } from 'lucide-react'
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
import { checkLocalSigner, testPecSmtpViaLocalSigner, type LocalSignerCheck } from '../localSigner'
import type { AiRuntimePayload, SettingsPayload, SettingsSection, TestResult } from '../types'

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
  const rows = plan ? [
    { label: 'Dispositivo', value: plan.deviceLabel, icon: Smartphone },
    { label: 'Risorse rilevate', value: plan.resourceLabel, icon: Cpu },
    { label: 'Modello consigliato', value: plan.modelLabel, icon: Bot },
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
            IUSENTRA rileva il dispositivo e sceglie il percorso piu sicuro: modello locale solo quando il sistema lo consente, altrimenti Lex usa il motore AI dello studio.
          </span>
        </div>
        <IusStatusBadge tone={plan?.isPortable ? 'info' : 'success'}>
          {plan?.isPortable ? 'Mobile rilevato' : 'PC rilevato'}
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
            Questo dispositivo non espone RAM, core o spazio libero. IUSENTRA non forza download pesanti: usa Lex con il motore AI dello studio finche' il dispositivo non e' verificabile.
          </AlertDescription>
        </Alert>
      ) : null}
      <div className="iu-settings-actions-panel__buttons">
        <Button type="button" variant="outline" onClick={() => openMobileLexFromSettings(plan)}>
          <Bot data-icon="inline-start" />
          Apri Lex AI
        </Button>
        <Button type="button" variant="outline" disabled={!plan?.canPrepareOnThisDevice || preparing} onClick={onPreparePc}>
          <Smartphone data-icon="inline-start" />
          {preparing ? 'Preparazione in corso' : 'Prepara su questo dispositivo'}
        </Button>
        <Button type="button" variant="outline" asChild>
          <a href={installerHref} target="_blank" rel="noreferrer">
            <Download data-icon="inline-start" />
            Scarica Ollama ufficiale
          </a>
        </Button>
      </div>
    </div>
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
}: {
  section: SettingsSection
  values: Record<string, unknown>
  data: SettingsPayload
  testResult: TestResult | null
  aiStatus: AiRuntimePayload | null
  onTest: (testId: string, values: Record<string, unknown>) => Promise<TestResult>
  onRefreshAi: () => Promise<AiRuntimePayload>
  onPrepareAi: (force?: boolean) => Promise<AiRuntimePayload>
}) {
  const [localSigner, setLocalSigner] = useState<LocalSignerCheck | null>(null)
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
    if (section !== 'ai' || localAiResult || aiChecking) return
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
  }, [aiAutoCheckKey, aiChecking, data.local_signer.base_url, data.local_signer.restart_protocol, localAiResult, section, values])

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
    return (
      <div className="iu-settings-actions-panel">
        <div>
          <strong>IUSENTRA Local Signer</strong>
          <span>Il dispositivo di firma viene verificato sul PC in uso, senza inviare il PIN allo studio online.</span>
        </div>
        <div className="iu-settings-actions-panel__buttons">
          <Button type="button" variant="outline" onClick={() => {
            void checkLocalSigner(data.local_signer.base_url, data.local_signer.restart_protocol).then(setLocalSigner)
          }}>
            <ShieldCheck data-icon="inline-start" />
            Verifica dispositivo collegato
          </Button>
          <Button type="button" variant="outline" asChild>
            <a href={data.local_signer.downloads.windows} target="_blank" rel="noreferrer">
              <Download data-icon="inline-start" />
              Installa su Windows
            </a>
          </Button>
        </div>
        <ResultAlert result={localSigner} />
      </div>
    )
  }

  if (section === 'ai') {
    const payload = aiPayload(localAiResult, aiStatus)
    const rows = aiDetailRows(payload)
    const installerHref = aiInstallerHref(payload)

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
        <MobileAiSetupPanel
          plan={mobileAiPlan}
          installerHref={installerHref}
          onPreparePc={() => { void runAiPrepare() }}
          preparing={aiPreparing}
        />
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
