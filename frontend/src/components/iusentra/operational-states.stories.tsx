import type { Meta, StoryObj } from '@storybook/react-vite'
import { CalendarClock, FileCheck2, FolderOpen } from 'lucide-react'

import { IusEmptyState, IusErrorState, IusLoadingState, IusMetricCard, IusStatusBadge } from '.'

const meta = {
  title: 'IUSENTRA/Componenti legali/Stati operativi',
  tags: ['autodocs'],
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

export const StatiDiPagina: Story = {
  render: () => (
    <div className="grid max-w-3xl gap-4">
      <IusLoadingState title="Caricamento fascicoli" message="Recupero dell'elenco dello studio in corso." />
      <IusEmptyState
        title="Nessun fascicolo nel filtro"
        message="Modifica filtri o crea un fascicolo solo se l'incarico è stato verificato."
        actionHref="/fascicoli/nuovo"
        actionLabel="Nuovo fascicolo"
        area="fascicoli"
        icon={FolderOpen}
      />
      <IusErrorState
        title="PEC temporaneamente non disponibile"
        message="Il controllo non ha modificato messaggi o ricevute. Riprova quando il collegamento è disponibile."
        onRetry={() => undefined}
      />
    </div>
  ),
}

export const IndicatoriLegali: Story = {
  render: () => (
    <div className="grid max-w-3xl gap-4 md:grid-cols-2">
      <IusMetricCard label="Scadenze da presidiare" value="3" note="Una entro due giorni" badge="Urgente" area="agenda" icon={CalendarClock} tone="warning" href="/scadenziario" />
      <IusMetricCard label="Depositi verificati" value="1" note="Fixture sicura" badge="Pronto" area="telematico" icon={FileCheck2} tone="success" href="/telematico" />
      <div className="flex flex-wrap gap-2 md:col-span-2">
        <IusStatusBadge status="Deposito telematico" />
        <IusStatusBadge status="Da verificare" />
        <IusStatusBadge status="Scadenza superata" />
        <IusStatusBadge status="Completato" />
      </div>
    </div>
  ),
}
