import type { Meta, StoryObj } from '@storybook/react-vite'
import { AlertTriangle, CheckCircle2, Clock3 } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from './alert'
import { Badge } from './badge'
import { Skeleton } from './skeleton'

const meta = {
  title: 'IUSENTRA/Fondamenta/Feedback e stati',
  tags: ['autodocs'],
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

export const StatoOperativo: Story = {
  render: () => (
    <div className="grid max-w-2xl gap-4">
      <Alert>
        <CheckCircle2 />
        <AlertTitle>Controllo completato</AlertTitle>
        <AlertDescription>La verifica usa solo dati fittizi e non modifica fascicoli, documenti o scadenze.</AlertDescription>
      </Alert>
      <Alert variant="destructive">
        <AlertTriangle />
        <AlertTitle>Configurazione mancante</AlertTitle>
        <AlertDescription>Inserisci il dato richiesto nello stesso flusso prima di inviare.</AlertDescription>
      </Alert>
      <div className="flex flex-wrap gap-2" aria-label="Varianti badge">
        <Badge><Clock3 /> In lavorazione</Badge>
        <Badge variant="secondary">Da verificare</Badge>
        <Badge variant="outline">Sola lettura</Badge>
        <Badge variant="destructive">Scadenza urgente</Badge>
        <Badge variant="ghost">Archivio</Badge>
      </div>
    </div>
  ),
}

export const Caricamento: Story = {
  render: () => (
    <section className="grid max-w-2xl gap-3 rounded-xl border bg-card p-4" aria-busy="true" aria-label="Caricamento dati fascicolo">
      <Skeleton className="h-6 w-48" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-4/5" />
      <div className="flex gap-2"><Skeleton className="h-8 w-28" /><Skeleton className="h-8 w-32" /></div>
    </section>
  ),
}
