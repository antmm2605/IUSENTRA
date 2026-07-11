import { ArrowRight, CalendarDays } from 'lucide-react'
import { Button } from '@/components/ui/button'

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

export function todayInRome(): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Rome',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  const part = (type: 'year' | 'month' | 'day') =>
    parts.find((entry) => entry.type === type)?.value || ''
  return `${part('year')}-${part('month')}-${part('day')}`
}

export function addDaysToIsoDate(value: string, days: number): string {
  const [year, month, day] = value.split('-').map(Number)
  const shifted = new Date(Date.UTC(year, month - 1, day + days, 12))
  return [
    shifted.getUTCFullYear(),
    String(shifted.getUTCMonth() + 1).padStart(2, '0'),
    String(shifted.getUTCDate()).padStart(2, '0'),
  ].join('-')
}

function isValidFutureDate(value: string, today: string): boolean {
  return ISO_DATE.test(value) && addDaysToIsoDate(value, 0) === value && value >= today
}

export function initialDailyPlanDate(): string {
  const today = todayInRome()
  if (typeof window === 'undefined') return today
  const requested = new URLSearchParams(window.location.search).get('date') || ''
  return isValidFutureDate(requested, today) ? requested : today
}

export function syncDailyPlanDateUrl(value: string): void {
  const url = new URL(window.location.href)
  if (value === todayInRome()) url.searchParams.delete('date')
  else url.searchParams.set('date', value)
  window.history.replaceState(window.history.state, '', url)
}

export function DailyPlanDateControls({
  value,
  onChange,
}: {
  value: string
  onChange: (value: string) => void
}) {
  const today = todayInRome()
  const shortcuts = [
    { label: 'Oggi', value: today },
    { label: 'Domani', value: addDaysToIsoDate(today, 1) },
    { label: 'Dopodomani', value: addDaysToIsoDate(today, 2) },
  ]

  return (
    <section
      aria-label="Data del piano"
      className="flex flex-col gap-2 border-b pb-3 sm:flex-row sm:items-center sm:justify-between"
    >
      <div role="group" aria-label="Scelte rapide" className="grid grid-cols-3 rounded-md border p-0.5">
        {shortcuts.map((option) => (
          <Button
            key={option.value}
            type="button"
            size="sm"
            variant={value === option.value ? 'secondary' : 'ghost'}
            className="iu-od-focus-ring rounded-sm"
            aria-pressed={value === option.value}
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </Button>
        ))}
      </div>
      <form
        className="flex min-w-0 items-center gap-1.5"
        onSubmit={(event) => {
          event.preventDefault()
          const selected = String(new FormData(event.currentTarget).get('date') || '')
          if (isValidFutureDate(selected, today)) onChange(selected)
        }}
      >
        <label className="flex min-w-0 items-center gap-2 text-sm font-medium">
          <CalendarDays size={16} aria-hidden="true" />
          <span className="sr-only">Scegli una data</span>
          <input
            type="date"
            name="date"
            min={today}
            value={value}
            aria-label="Scegli una data del piano"
            className="iu-od-focus-ring h-9 min-w-0 rounded-md border bg-background px-2 text-sm sm:w-auto"
            onChange={(event) => {
              if (isValidFutureDate(event.target.value, today)) onChange(event.target.value)
            }}
          />
        </label>
        <Button
          type="submit"
          size="icon-lg"
          variant="outline"
          className="iu-od-focus-ring rounded-md"
          aria-label="Apri data selezionata"
          title="Apri data selezionata"
        >
          <ArrowRight aria-hidden="true" />
        </Button>
      </form>
    </section>
  )
}
