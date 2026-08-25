import { useState } from 'react'
import { AlertTriangle, MonitorCheck, RefreshCw, Settings2 } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  IusFormSection,
  IusLoadingState,
  IusPageShell,
  IusErrorState,
  IusStatusBadge,
} from '@/components/iusentra'
import { SETTINGS_FIELDS, SETTINGS_SECTIONS } from './constants'
import { BackupSettingsPanel } from './components/BackupSettingsPanel'
import { BillingSettingsPanel } from './components/BillingSettingsPanel'
import { CalendarSettingsPanel } from './components/CalendarSettingsPanel'
import { SettingsActions } from './components/SettingsActions'
import { NotificationsSettingsPanel } from './components/NotificationsSettingsPanel'
import { PaymentsSettingsPanel } from './components/PaymentsSettingsPanel'
import { SettingsSectionForm } from './components/SettingsSectionForm'
import { SettingsSummary } from './components/SettingsSummary'
import { payloadForSection, rawPayloadForSection, useImpostazioni } from './hooks/useImpostazioni'
import type { SettingsSection } from './types'
import './ImpostazioniPage.css'

function SectionBadge({ section }: { section: SettingsSection }) {
  const meta = SETTINGS_SECTIONS.find((item) => item.id === section)
  if (!meta) return null
  return <IusStatusBadge tone={meta.tone}>{meta.label}</IusStatusBadge>
}

export function ImpostazioniPage() {
  const settings = useImpostazioni()
  const [summaryVisible, setSummaryVisible] = useState(true)
  const canUpdate = settings.data.permissions.can_update
  const rawValues = rawPayloadForSection(settings.data, settings.activeSection)

  return (
    <IusPageShell
      title="Impostazioni"
      description="Dati studio, canali di comunicazione, firma digitale, automazioni e AI locale in un unico pannello operativo."
      icon={Settings2}
      tone="primary"
      actions={
        <div className="iu-settings-page__actions">
          <Button
            type="button"
            variant="outline"
            aria-pressed={!summaryVisible}
            aria-controls="settings-summary"
            onClick={() => setSummaryVisible((visible) => !visible)}
          >
            <MonitorCheck data-icon="inline-start" />
            {summaryVisible ? 'Schermo intero' : 'Mostra riepilogo'}
          </Button>
          <Button type="button" variant="outline" onClick={settings.load}>
            <RefreshCw data-icon="inline-start" />
            Aggiorna
          </Button>
        </div>
      }
      className="iu-settings-page"
    >
      {settings.loading ? (
        <IusLoadingState title="Caricamento impostazioni" message="Lettura della configurazione studio senza esporre password o chiavi." />
      ) : null}

      {!settings.loading && !settings.data.ok ? (
        <IusErrorState title="Impostazioni non disponibili" message={settings.message || 'Non riesco a leggere la configurazione dello studio.'} onRetry={settings.load} />
      ) : null}

      {!settings.loading && settings.data.ok ? (
        <div className={`iu-settings-layout${summaryVisible ? '' : ' iu-settings-layout--wide'}`}>
          <section className="iu-settings-main">
            {settings.message ? (
              <Alert className="iu-settings-alert is-success">
                <Settings2 />
                <AlertTitle>Stato aggiornato</AlertTitle>
                <AlertDescription>{settings.message}</AlertDescription>
              </Alert>
            ) : null}

            <Tabs value={settings.activeSection} onValueChange={(value) => settings.openSection(value as SettingsSection)} className="iu-settings-tabs">
              <TabsList className="iu-settings-tabs__list" variant="line" aria-label="Sezioni impostazioni">
                {SETTINGS_SECTIONS.map((section) => {
                  const Icon = section.icon
                  return (
                    <TabsTrigger value={section.id} key={section.id}>
                      <Icon data-icon="inline-start" />
                      {section.label}
                    </TabsTrigger>
                  )
                })}
              </TabsList>

              {SETTINGS_SECTIONS.map((section) => {
                const Icon = section.icon
                const isActiveSection = section.id === settings.activeSection
                return (
                  <TabsContent
                    value={section.id}
                    key={section.id}
                    hidden={!isActiveSection}
                    aria-hidden={!isActiveSection}
                    className="iu-settings-tabs__content"
                  >
                    <IusFormSection
                      title={section.label}
                      description={section.description}
                      icon={Icon}
                      tone={section.tone}
                      actions={<SectionBadge section={section.id} />}
                    >
                      {section.id === 'backup' ? (
                        <BackupSettingsPanel
                          data={settings.data}
                          onReload={settings.load}
                        />
                      ) : section.id === 'fatturazione' ? (
                        <BillingSettingsPanel
                          data={settings.data}
                          canUpdate={canUpdate}
                          saving={settings.saving === section.id}
                          onSave={settings.save}
                          onReload={settings.load}
                        />
                      ) : section.id === 'calendari' ? (
                        <CalendarSettingsPanel
                          data={settings.data}
                          onReload={settings.load}
                        />
                      ) : section.id === 'pagamenti' ? (
                        <PaymentsSettingsPanel
                          data={settings.data}
                          canUpdate={canUpdate}
                          saving={settings.saving === section.id}
                          onSave={settings.save}
                        />
                      ) : section.id === 'notifiche' ? (
                        <NotificationsSettingsPanel
                          data={settings.data}
                          onReload={settings.load}
                          onOpenSection={settings.openSection}
                        />
                      ) : (
                        <SettingsSectionForm
                          section={section.id}
                          fields={SETTINGS_FIELDS[section.id]}
                          initialValues={isActiveSection ? settings.values : payloadForSection(settings.data, section.id)}
                          rawValues={isActiveSection ? rawValues : rawPayloadForSection(settings.data, section.id)}
                          canUpdate={canUpdate}
                          saving={settings.saving === section.id}
                          onSave={settings.save}
                        >
                          {(formValues) => (
                            <SettingsActions
                              section={section.id}
                              values={formValues}
                              data={settings.data}
                              testResult={isActiveSection ? settings.testResult : null}
                              aiStatus={settings.aiStatus}
                              onTest={settings.test}
                              onRefreshAi={settings.refreshAi}
                              onPrepareAi={settings.prepareAi}
                              onReload={settings.load}
                            />
                          )}
                        </SettingsSectionForm>
                      )}
                    </IusFormSection>
                  </TabsContent>
                )
              })}
            </Tabs>
          </section>

          {summaryVisible ? <SettingsSummary data={settings.data} /> : null}
        </div>
      ) : null}

      {!settings.loading && settings.data.ok && !canUpdate ? (
        <Alert className="iu-settings-alert is-warning">
          <AlertTriangle />
          <AlertTitle>Permesso richiesto</AlertTitle>
          <AlertDescription>Per modificare queste impostazioni serve il permesso admin.configura.</AlertDescription>
        </Alert>
      ) : null}
    </IusPageShell>
  )
}

export default ImpostazioniPage
