import type { Meta, StoryObj } from '@storybook/react-vite'
import { CheckCircle2, LoaderCircle, Save } from 'lucide-react'

import { Button } from './button'
import { Input } from './input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './select'
import { Textarea } from './textarea'

const meta = {
  title: 'IUSENTRA/Fondamenta/Controlli di form',
  tags: ['autodocs'],
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

export const Pulsanti: Story = {
  render: () => (
    <div className="grid max-w-2xl gap-4">
      <div className="flex flex-wrap gap-2">
        <Button><Save data-icon="inline-start" /> Salva</Button>
        <Button variant="outline">Verifica requisiti</Button>
        <Button variant="secondary">Salva bozza</Button>
        <Button variant="ghost">Annulla</Button>
        <Button variant="destructive">Rimuovi allegato</Button>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button disabled><LoaderCircle data-icon="inline-start" /> Salvataggio</Button>
        <Button aria-invalid="true">Correggi i dati</Button>
        <Button size="sm"><CheckCircle2 data-icon="inline-start" /> Conferma</Button>
      </div>
    </div>
  ),
}

export const CampiDiTesto: Story = {
  render: () => (
    <div className="grid max-w-xl gap-4">
      <label className="grid gap-1.5 text-sm font-medium">
        Oggetto PEC
        <Input defaultValue="Deposito telematico – fascicolo fittizio" />
      </label>
      <label className="grid gap-1.5 text-sm font-medium">
        Errore con spiegazione
        <Input aria-invalid="true" defaultValue="" placeholder="Campo obbligatorio" />
        <span className="text-sm text-destructive">Inserisci un oggetto prima di proseguire.</span>
      </label>
      <label className="grid gap-1.5 text-sm font-medium">
        Nota operativa
        <Textarea defaultValue="Fixture sicura per controllare altezza, focus, testo lungo e stato disabilitato." />
      </label>
      <Textarea aria-label="Nota operativa in sola lettura" disabled value="Modifica non disponibile con permesso di sola lettura." readOnly />
    </div>
  ),
}

export const Selettori: Story = {
  render: () => (
    <div className="grid max-w-xl gap-4">
      <label className="grid gap-1.5 text-sm font-medium">
        Priorità
        <Select defaultValue="alta">
          <SelectTrigger aria-label="Priorità"><SelectValue placeholder="Seleziona priorità" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="bassa">Bassa</SelectItem>
            <SelectItem value="media">Media</SelectItem>
            <SelectItem value="alta">Alta</SelectItem>
          </SelectContent>
        </Select>
      </label>
    </div>
  ),
}
