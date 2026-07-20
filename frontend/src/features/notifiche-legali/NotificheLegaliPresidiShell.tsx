import { Suspense, useEffect, useState, type ReactNode } from 'react'
import { IusSkeletonTable } from '@/components/iusentra'
import { Tabs } from '@/ui/Tabs'
import { PresidiNotifichePage } from './PresidiNotifichePage'
import './PresidiNotifiche.css'

type LegalNotificationSection = 'presidi' | 'operazioni'

const LEGACY_QUERY_KEYS = [
  'fase',
  'id_fascicolo',
  'id_fasc',
  'fascicolo',
  'documenti',
  'documenti_ids',
  'id_documento',
  'id_documenti',
  'documento',
]

function sectionFromLocation(): LegalNotificationSection {
  const params = new URLSearchParams(window.location.search)
  if (params.get('section') === 'operazioni') return 'operazioni'
  if (LEGACY_QUERY_KEYS.some((key) => params.has(key))) return 'operazioni'
  return 'presidi'
}

function writeSection(section: LegalNotificationSection) {
  const url = new URL(window.location.href)
  url.searchParams.set('section', section)
  if (section === 'presidi') {
    LEGACY_QUERY_KEYS.forEach((key) => url.searchParams.delete(key))
  } else {
    url.searchParams.delete('coda')
    url.searchParams.delete('presidio')
  }
  window.history.pushState({}, '', url.pathname + url.search + url.hash)
}

export function NotificheLegaliPresidiShell({ legacyPage }: { legacyPage: ReactNode }) {
  const [section, setSection] = useState<LegalNotificationSection>(sectionFromLocation)

  useEffect(() => {
    const sync = () => setSection(sectionFromLocation())
    window.addEventListener('popstate', sync)
    return () => window.removeEventListener('popstate', sync)
  }, [])

  const selectSection = (next: string) => {
    const sectionId = next === 'operazioni' ? 'operazioni' : 'presidi'
    setSection(sectionId)
    writeSection(sectionId)
  }

  return (
    <div className="nlp-shell">
      <nav className="nlp-section-nav" aria-label="Sezioni notifiche legali">
        <Tabs
          selectedId={section}
          onSelect={selectSection}
          items={[
            { id: 'presidi', label: 'Presidi notifiche' },
            { id: 'operazioni', label: 'Operazioni di notifica' },
          ]}
        />
      </nav>
      {section === 'presidi' ? (
        <PresidiNotifichePage />
      ) : (
        <Suspense
          fallback={(
            <section className="iu-content nlp-legacy-loading" aria-busy="true">
              <IusSkeletonTable rows={7} columns={4} />
            </section>
          )}
        >
          {legacyPage}
        </Suspense>
      )}
    </div>
  )
}
