import type { ReactNode } from 'react'
import './ui.css'

export type TabItem = {
  id: string
  label: ReactNode
}

export function Tabs({
  items,
  selectedId,
  onSelect,
}: {
  items: TabItem[]
  selectedId: string
  onSelect: (id: string) => void
}) {
  return (
    <div className="iu-tabs" role="tablist">
      {items.map((item) => (
        <button
          type="button"
          className="iu-tab"
          role="tab"
          aria-selected={item.id === selectedId}
          key={item.id}
          onClick={() => onSelect(item.id)}
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}
