import { Tabs } from '@/ui/Tabs'
import { PRESIDIO_TABS, tabCount } from '../presentation'
import type { PresidioStatus, PresidioTabKey } from '../types'

export function PresidiTabs({
  selected,
  counts,
  onSelect,
}: {
  selected: PresidioTabKey
  counts?: Partial<Record<PresidioStatus, number>>
  onSelect: (tab: PresidioTabKey) => void
}) {
  const items = PRESIDIO_TABS.map((tab) => {
    const count = tabCount(tab.statuses, counts)
    return {
      id: tab.id,
      label: (
        <span className="nlp-tab-label">
          <span>{tab.label}</span>
          {count !== null ? <strong aria-label={count + ' presidi'}>{count}</strong> : null}
        </span>
      ),
    }
  })

  return (
    <nav className="nlp-queue-tabs" aria-label="Code dei presidi">
      <Tabs
        items={items}
        selectedId={selected}
        onSelect={(id) => onSelect(id as PresidioTabKey)}
      />
    </nav>
  )
}
