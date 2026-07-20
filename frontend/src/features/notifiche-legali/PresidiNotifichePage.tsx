import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { BellRing, RefreshCw } from 'lucide-react'
import { IusSkeletonTable, IusentraDataSurface, IusentraPageShell, IusentraPaginationBar } from '@/components/iusentra'
import { Button } from '@/ui/Button'
import { ErrorState } from '@/ui/ErrorState'
import { InlineAlert } from '@/ui/InlineAlert'
import { PermissionDeniedState } from '@/ui/PermissionDeniedState'
import { PresidiFilters, EMPTY_PRESIDIO_FILTERS } from './components/PresidiFilters'
import { PresidiTable } from './components/PresidiTable'
import { PresidiTabs } from './components/PresidiTabs'
import { usePresidi } from './hooks/usePresidi'
import { PRESIDIO_TABS } from './presentation'
import type { PresidioFilterControls, PresidioListFilters, PresidioResourceStatus, PresidioTabKey } from './types'
import './PresidiNotifiche.css'

const PresidioDetailDrawer = lazy(() => import('./components/PresidioDetailDrawer'))
const TAB_IDS = new Set(PRESIDIO_TABS.map((tab) => tab.id))

function tabFromLocation(): PresidioTabKey {
  const raw = new URLSearchParams(window.location.search).get('coda') || ''
  return TAB_IDS.has(raw as PresidioTabKey) ? raw as PresidioTabKey : 'review'
}

function detailFromLocation(): string | null {
  return new URLSearchParams(window.location.search).get('presidio')
}

function writeLocation(tab: PresidioTabKey, detailId: string | null) {
  const url = new URL(window.location.href)
  url.searchParams.set('section', 'presidi')
  url.searchParams.set('coda', tab)
  if (detailId) url.searchParams.set('presidio', detailId)
  else url.searchParams.delete('presidio')
  window.history.pushState({}, '', url.pathname + url.search + url.hash)
}

function BlockingState({
  status,
  message,
  onRetry,
}: {
  status: PresidioResourceStatus
  message: string
  onRetry: () => void
}) {
  if (status === 'forbidden') return <PermissionDeniedState />
  const title = status === 'flag-off'
    ? 'Presidi notifiche non attivi'
    : status === 'repository-unavailable'
      ? 'Registro temporaneamente non disponibile'
      : 'Caricamento non riuscito'
  return (
    <div className="nlp-blocking-state">
      <ErrorState title={title} message={message} />
      <Button type="button" tone="neutral" onClick={onRetry}>
        <RefreshCw size={16} aria-hidden="true" />
        Riprova
      </Button>
    </div>
  )
}

export function PresidiNotifichePage() {
  const [activeTab, setActiveTab] = useState<PresidioTabKey>(tabFromLocation)
  const [selectedId, setSelectedId] = useState<string | null>(detailFromLocation)
  const [filters, setFilters] = useState<PresidioFilterControls>(EMPTY_PRESIDIO_FILTERS)
  const [cursor, setCursor] = useState('')
  const [cursorHistory, setCursorHistory] = useState<string[]>([])
  const tab = PRESIDIO_TABS.find((item) => item.id === activeTab) || PRESIDIO_TABS[0]
  const listFilters = useMemo<PresidioListFilters>(() => ({
    ...filters,
    statuses: tab.statuses,
    cursor,
    limit: 30,
  }), [cursor, filters, tab])
  const resource = usePresidi(listFilters)
  const payload = resource.data

  useEffect(() => {
    const sync = () => {
      setActiveTab(tabFromLocation())
      setSelectedId(detailFromLocation())
      setCursor('')
      setCursorHistory([])
    }
    window.addEventListener('popstate', sync)
    return () => window.removeEventListener('popstate', sync)
  }, [])

  const changeTab = (next: PresidioTabKey) => {
    setActiveTab(next)
    setSelectedId(null)
    setCursor('')
    setCursorHistory([])
    writeLocation(next, null)
  }

  const applyFilters = (next: PresidioFilterControls) => {
    setFilters(next)
    setCursor('')
    setCursorHistory([])
  }

  const openDetail = (id: string) => {
    setSelectedId(id)
    writeLocation(activeTab, id)
  }

  const closeDetail = () => {
    setSelectedId(null)
    writeLocation(activeTab, null)
  }

  const goNext = () => {
    const next = payload?.pagination.next_cursor
    if (!next) return
    setCursorHistory((current) => [...current, cursor])
    setCursor(next)
  }

  const goPrevious = () => {
    setCursorHistory((current) => {
      const copy = [...current]
      setCursor(copy.pop() || '')
      return copy
    })
  }

  const initialFailure = !payload
    && ['forbidden', 'flag-off', 'repository-unavailable', 'error'].includes(resource.status)
  const resultLabel = payload?.pagination.total !== null && payload?.pagination.total !== undefined
    ? payload.pagination.total + ' presidi'
    : payload
      ? payload.items.length + ' presidi caricati'
      : 'Registro in caricamento'

  return (
    <IusentraPageShell
      title="Presidi notifiche"
      description="Registro persistente delle notifiche legali, delle ricevute e delle prove da presidiare."
      icon={BellRing}
      actions={(
        <Button type="button" tone="neutral" disabled={resource.busy} onClick={resource.refresh}>
          <RefreshCw className={resource.busy ? 'nlp-spin' : ''} size={16} aria-hidden="true" />
          {resource.busy ? 'Aggiornamento' : 'Aggiorna'}
        </Button>
      )}
      className="nlp-page"
    >
      <PresidiTabs selected={activeTab} counts={payload?.facets?.status} onSelect={changeTab} />
      <PresidiFilters
        value={filters}
        assignees={payload?.filter_options.assignees || []}
        channels={payload?.filter_options.channels || []}
        disabled={resource.status === 'loading'}
        onApply={applyFilters}
      />

      {payload?.partial ? (
        <InlineAlert tone="warning">
          I dati sono parziali. Consulta gli avvisi e riprova prima di assumere decisioni operative.
        </InlineAlert>
      ) : null}
      {payload?.warnings.map((warning) => (
        <InlineAlert tone="warning" key={warning.code || warning.message}>{warning.message}</InlineAlert>
      ))}
      {payload && !payload.permissions.can_write ? (
        <InlineAlert tone="info">
          Consultazione in sola lettura. Le modifiche richiedono il permesso di scrittura sulle comunicazioni.
        </InlineAlert>
      ) : null}
      {payload && resource.status !== 'ready' && resource.status !== 'refreshing'
        ? <InlineAlert tone="warning">{resource.message}</InlineAlert>
        : null}

      {resource.status === 'loading' && !payload ? (
        <section className="nlp-loading" aria-label="Caricamento presidi" aria-busy="true">
          <IusSkeletonTable rows={8} columns={6} />
        </section>
      ) : null}
      {initialFailure
        ? <BlockingState status={resource.status} message={resource.message} onRetry={resource.refresh} />
        : null}

      {payload ? (
        <IusentraDataSurface
          title="Registro operativo"
          subtitle={resultLabel}
          ariaLabel="Elenco dei presidi delle notifiche"
          footer={(
            <IusentraPaginationBar>
              <span>Pagina caricata: {payload.items.length} elementi</span>
              <div>
                <Button type="button" tone="neutral" disabled={!cursorHistory.length || resource.busy} onClick={goPrevious}>
                  Precedenti
                </Button>
                <Button
                  type="button"
                  tone="neutral"
                  disabled={!payload.pagination.has_more || !payload.pagination.next_cursor || resource.busy}
                  onClick={goNext}
                >
                  Successivi
                </Button>
              </div>
            </IusentraPaginationBar>
          )}
        >
          <PresidiTable items={payload.items} onOpen={openDetail} />
        </IusentraDataSurface>
      ) : null}

      {selectedId ? (
        <Suspense fallback={<div className="nlp-detail-loading"><IusSkeletonTable rows={6} columns={2} /></div>}>
          <PresidioDetailDrawer id={selectedId} onClose={closeDetail} onUpdated={resource.refresh} />
        </Suspense>
      ) : null}
    </IusentraPageShell>
  )
}
