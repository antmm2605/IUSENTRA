import { AlertTriangle, CheckCircle2, ShieldCheck } from 'lucide-react'
import { IusStatusBadge } from '@/components/iusentra'
import type { SettingsPayload } from '../types'

export function SettingsSummary({ data }: { data: SettingsPayload }) {
  const configured = data.sections.filter((section) => section.tone === 'success').length
  return (
    <aside id="settings-summary" className="iu-settings-summary" aria-label="Riepilogo impostazioni">
      <header>
        <ShieldCheck />
        <div>
          <strong>Presidio configurazione</strong>
          <span>{configured} di {data.sections.length || 11} sezioni configurate</span>
        </div>
      </header>
      <div className="iu-settings-summary__grid">
        {data.sections.map((section) => (
          <article key={section.label}>
            {section.tone === 'success' ? <CheckCircle2 /> : <AlertTriangle />}
            <div>
              <span>{section.label}</span>
              <IusStatusBadge tone={section.tone}>{section.status}</IusStatusBadge>
            </div>
          </article>
        ))}
      </div>
      <footer>
        <ShieldCheck />
        <span>Configurazione salvata e protetta nello studio.</span>
      </footer>
    </aside>
  )
}
