import { useState } from 'react'
import { Bot, CheckCircle2, Download, Play, RefreshCw, ShieldCheck } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { IusStatusBadge } from '@/components/iusentra'
import { checkLocalSigner, type LocalSignerCheck } from '../localSigner'
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

function ResultAlert({ result }: { result: TestResult | LocalSignerCheck | AiRuntimePayload | null }) {
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
    return (
      <div className="iu-settings-actions-panel">
        <div>
          <strong>AI locale</strong>
          <span>Stato corrente: <IusStatusBadge>{aiStatusLabel(aiStatus)}</IusStatusBadge></span>
        </div>
        <div className="iu-settings-actions-panel__buttons">
          <Button type="button" variant="outline" onClick={() => { void onRefreshAi() }}>
            <RefreshCw data-icon="inline-start" />
            Verifica AI locale
          </Button>
          <Button type="button" variant="outline" onClick={() => { void onPrepareAi(false) }}>
            <Bot data-icon="inline-start" />
            Prepara motore locale
          </Button>
        </div>
        <ResultAlert result={aiStatus} />
      </div>
    )
  }

  const tests = section === 'pec'
    ? [['pec-smtp', 'Verifica invio PEC'], ['pec-imap', 'Verifica ricezione PEC']]
    : section === 'smtp'
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
