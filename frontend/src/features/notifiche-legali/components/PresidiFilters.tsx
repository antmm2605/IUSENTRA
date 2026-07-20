import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { ListFilter, RotateCcw } from 'lucide-react'
import { AdvancedFilters } from '@/ui/AdvancedFilters'
import { Button } from '@/ui/Button'
import { FilterBar } from '@/ui/FilterBar'
import { SearchInput } from '@/ui/SearchInput'
import { Select } from '@/ui/Select'
import { TextField } from '@/ui/TextField'
import type { PresidioFilterControls, PresidioOption } from '../types'

export const EMPTY_PRESIDIO_FILTERS: PresidioFilterControls = {
  priority: '',
  fascicolo: '',
  assigned_user: '',
  date_from: '',
  date_to: '',
  recipient: '',
  channel: '',
  legacy: '',
  needs_review: '',
}

function activeFilterCount(value: PresidioFilterControls): number {
  return Object.values(value).filter((item) => String(item).trim() !== '').length
}

export function PresidiFilters({
  value,
  assignees,
  channels,
  disabled,
  onApply,
}: {
  value: PresidioFilterControls
  assignees: PresidioOption[]
  channels: PresidioOption[]
  disabled?: boolean
  onApply: (next: PresidioFilterControls) => void
}) {
  const [draft, setDraft] = useState(value)
  useEffect(() => setDraft(value), [value])
  const count = useMemo(() => activeFilterCount(value), [value])

  const update = <TKey extends keyof PresidioFilterControls>(
    key: TKey,
    next: PresidioFilterControls[TKey],
  ) => {
    setDraft((current) => ({ ...current, [key]: next }))
  }

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    onApply({
      ...draft,
      fascicolo: draft.fascicolo.trim(),
      recipient: draft.recipient.trim(),
    })
  }

  const reset = () => {
    setDraft(EMPTY_PRESIDIO_FILTERS)
    onApply(EMPTY_PRESIDIO_FILTERS)
  }

  return (
    <form className="nlp-filters" onSubmit={submit}>
      <FilterBar activeCount={count}>
        <div className="nlp-filter-main">
          <TextField
            label="Fascicolo o R.G."
            value={draft.fascicolo}
            placeholder="Cerca pratica o R.G."
            disabled={disabled}
            onChange={(event) => update('fascicolo', event.target.value)}
          />
          <label className="nlp-search-field">
            <span>Destinatario</span>
            <SearchInput
              aria-label="Cerca destinatario"
              value={draft.recipient}
              placeholder="Nome, codice fiscale o PEC"
              disabled={disabled}
              onChange={(event) => update('recipient', event.target.value)}
            />
          </label>
          <Select
            label="Priorità"
            value={draft.priority}
            disabled={disabled}
            onChange={(event) => update('priority', event.target.value as PresidioFilterControls['priority'])}
          >
            <option value="">Tutte</option>
            <option value="P0">P0, immediata</option>
            <option value="P1">P1, alta</option>
            <option value="P2">P2, ordinaria</option>
            <option value="P3">P3, bassa</option>
          </Select>
          <div className="nlp-filter-actions">
            <Button type="submit" disabled={disabled}>
              <ListFilter size={16} aria-hidden="true" />
              Applica
            </Button>
            <Button type="button" tone="neutral" disabled={disabled || count === 0} onClick={reset}>
              <RotateCcw size={16} aria-hidden="true" />
              Azzera
            </Button>
          </div>
        </div>
      </FilterBar>

      <AdvancedFilters title="Altri filtri">
        <div className="nlp-filter-advanced">
          <Select
            label="Assegnato a"
            value={draft.assigned_user}
            disabled={disabled}
            onChange={(event) => update('assigned_user', event.target.value)}
          >
            <option value="">Tutti</option>
            {assignees.map((option) => (
              <option value={option.value} key={option.value}>{option.label}</option>
            ))}
          </Select>
          <Select
            label="Canale"
            value={draft.channel}
            disabled={disabled}
            onChange={(event) => update('channel', event.target.value)}
          >
            <option value="">Tutti</option>
            {channels.map((option) => (
              <option value={option.value} key={option.value}>{option.label}</option>
            ))}
          </Select>
          <TextField
            type="date"
            label="Dal"
            value={draft.date_from}
            max={draft.date_to || undefined}
            disabled={disabled}
            onChange={(event) => update('date_from', event.target.value)}
          />
          <TextField
            type="date"
            label="Al"
            value={draft.date_to}
            min={draft.date_from || undefined}
            disabled={disabled}
            onChange={(event) => update('date_to', event.target.value)}
          />
          <Select
            label="Origine"
            value={draft.legacy}
            disabled={disabled}
            onChange={(event) => update('legacy', event.target.value as PresidioFilterControls['legacy'])}
          >
            <option value="">Tutte</option>
            <option value="false">Corrente</option>
            <option value="true">Storica</option>
          </Select>
          <Select
            label="Revisione"
            value={draft.needs_review}
            disabled={disabled}
            onChange={(event) => update('needs_review', event.target.value as PresidioFilterControls['needs_review'])}
          >
            <option value="">Tutti</option>
            <option value="true">Da verificare</option>
            <option value="false">Già verificati</option>
          </Select>
        </div>
      </AdvancedFilters>
    </form>
  )
}
