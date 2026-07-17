import { useState } from 'react'
import { CheckCircle2, RefreshCw, TriangleAlert } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { applyBillingDefaultsToProformas } from '../api'
import { SETTINGS_FIELDS } from '../constants'
import { payloadForSection, rawPayloadForSection } from '../hooks/useImpostazioni'
import type { BillingDefaultsApplyResult, SettingsPayload, SettingsSection } from '../types'
import { SettingsSectionForm } from './SettingsSectionForm'
import './BillingSettingsPanel.css'

export function BillingSettingsPanel({
  data,
  canUpdate,
  saving,
  onSave,
  onReload,
}: {
  data: SettingsPayload
  canUpdate: boolean
  saving: boolean
  onSave: (section: SettingsSection, values: Record<string, unknown>, files?: Record<string, File | null>) => Promise<boolean>
  onReload: () => void
}) {
  const [confirming, setConfirming] = useState(false)
  const [applying, setApplying] = useState(false)
  const [result, setResult] = useState<BillingDefaultsApplyResult | null>(null)
  const stats = data.fatturazione_stats

  async function applyDefaults() {
    setApplying(true)
    setResult(null)
    const response = await applyBillingDefaultsToProformas()
    setApplying(false)
    setConfirming(false)
    setResult(response)
    if (response.ok) onReload()
  }

  return (
    <SettingsSectionForm
      section="fatturazione"
      fields={SETTINGS_FIELDS.fatturazione}
      initialValues={payloadForSection(data, 'fatturazione')}
      rawValues={rawPayloadForSection(data, 'fatturazione')}
      canUpdate={canUpdate}
      saving={saving}
      onSave={onSave}
    >
      <section className="iu-billing-defaults-sync" aria-label="Aggiornamento proforme esistenti">
        <div className="iu-billing-defaults-sync__summary">
          <div>
            <strong>Proforme esistenti</strong>
            <span>{stats.aggiornabili} aggiornabili{stats.escluse ? `, ${stats.escluse} escluse` : ''}</span>
          </div>
          {!confirming ? (
            <Button
              type="button"
              variant="outline"
              disabled={!canUpdate || saving || applying || stats.aggiornabili === 0}
              onClick={() => { setConfirming(true); setResult(null) }}
            >
              <RefreshCw data-icon="inline-start" />
              Aggiorna proforme
            </Button>
          ) : null}
        </div>

        {confirming ? (
          <Alert className="iu-settings-alert is-warning">
            <TriangleAlert />
            <AlertTitle>Conferma aggiornamento di {stats.aggiornabili} proforme</AlertTitle>
            <AlertDescription>
              Le regole fiscali, il metodo di pagamento e le coordinate dello studio saranno riallineati. Le date già assegnate resteranno invariate.
            </AlertDescription>
            <div className="iu-billing-defaults-sync__actions">
              <Button type="button" variant="outline" disabled={applying} onClick={() => setConfirming(false)}>Annulla</Button>
              <Button type="button" disabled={applying} onClick={() => void applyDefaults()}>
                <RefreshCw data-icon="inline-start" />
                {applying ? 'Aggiornamento...' : 'Conferma aggiornamento'}
              </Button>
            </div>
          </Alert>
        ) : null}

        {result ? (
          <Alert className={`iu-settings-alert ${result.ok ? 'is-success' : 'is-warning'}`}>
            {result.ok ? <CheckCircle2 /> : <TriangleAlert />}
            <AlertTitle>{result.ok ? 'Proforme aggiornate' : 'Aggiornamento non completato'}</AlertTitle>
            <AlertDescription>{result.message}</AlertDescription>
          </Alert>
        ) : null}
      </section>
    </SettingsSectionForm>
  )
}
