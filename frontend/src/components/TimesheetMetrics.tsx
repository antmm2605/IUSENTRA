import { Banknote, CheckCircle2, Clock3, FileText } from 'lucide-react'
import type { TimesheetData } from '../timesheetData'

export function TimesheetMetrics({ data, onFilter, busy }: {
  data: TimesheetData
  onFilter: (filters: Record<string, string>) => void
  busy: boolean
}) {
  const cards = [
    { label: 'Voci totali', value: data.summary.totalEntries, icon: FileText, filter: {}, note: 'Tutte le voci' },
    { label: 'Tempo lavorato', value: data.summary.totalHoursLabel, icon: Clock3, filter: { ordina: 'tempo' }, note: 'Ordina per tempo' },
    { label: 'Valore totale', value: data.summary.totalValueLabel, icon: Banknote, filter: { ordina: 'valore' }, note: 'Ordina per valore' },
    { label: 'Validate', value: data.summary.validated, icon: CheckCircle2, filter: { stato: 'VALIDATO' }, note: 'Mostra validate' },
    { label: 'Aperte', value: data.summary.open, icon: Clock3, filter: { stato: 'APERTO' }, note: 'Mostra aperte' },
    { label: 'Fatturate', value: data.summary.invoiced, icon: Banknote, filter: { stato: 'FATTURATO' }, note: 'Mostra fatturate' },
    { label: 'Fatturabili', value: data.summary.billable, icon: CheckCircle2, filter: { fatturabile: '1' }, note: 'Mostra fatturabili' },
    { label: 'Interne', value: data.summary.notBillable, icon: FileText, filter: { fatturabile: '0' }, note: 'Mostra interne' },
  ]
  const selected = ['stato', 'fatturabile', 'ordina']
  return <section className="iu-timesheet-stats" aria-label="Indicatori e filtri del timesheet nel contesto selezionato">
    {cards.map(card => {
      const filter = card.filter as Record<string, string>
      const active = selected.every(key => (data.filters[key] || '') === (filter[key] || ''))
      return <button type="button" className="iu-timesheet-stat" key={card.label} aria-pressed={active} disabled={busy}
        onClick={() => onFilter({ ...data.filters, stato: '', fatturabile: '', ordina: '', ...filter })}>
        <span><card.icon size={17}/>{card.label}</span><strong>{card.value}</strong><small>{card.note}</small>
      </button>
    })}
  </section>
}
