import type { Meta, StoryObj } from '@storybook/react-vite'

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from './accordion'
import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from './card'
import { ScrollArea } from './scroll-area'
import { Separator } from './separator'
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from './table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from './tabs'

const meta = {
  title: 'IUSENTRA/Fondamenta/Layout e navigazione',
  tags: ['autodocs'],
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

export const CardOperativa: Story = {
  render: () => (
    <Card className="max-w-xl">
      <CardHeader>
        <CardTitle>Controllo deposito</CardTitle>
        <CardDescription>Riepilogo fittizio della prossima azione governata.</CardDescription>
        <CardAction>Da verificare</CardAction>
      </CardHeader>
      <CardContent>La card mantiene titolo, contesto e azione principale anche con testo esteso.</CardContent>
      <CardFooter>Ultimo controllo: 22/08/2026 18:30</CardFooter>
    </Card>
  ),
}

export const TabellaResponsiva: Story = {
  render: () => (
    <Table>
      <TableCaption>Fascicoli fittizi usati solo per verificare larghezze e allineamento.</TableCaption>
      <TableHeader><TableRow><TableHead>Cliente</TableHead><TableHead>RG</TableHead><TableHead>Stato</TableHead><TableHead className="text-right">Scadenza</TableHead></TableRow></TableHeader>
      <TableBody>
        <TableRow><TableCell>Cliente fittizio</TableCell><TableCell>1234/2026</TableCell><TableCell>Attivo</TableCell><TableCell className="text-right">15/06/2026</TableCell></TableRow>
        <TableRow><TableCell>Controparte fittizia con denominazione volutamente estesa</TableCell><TableCell>9876/2026</TableCell><TableCell>Da verificare</TableCell><TableCell className="text-right">18/06/2026</TableCell></TableRow>
      </TableBody>
    </Table>
  ),
}

export const NavigazioneEContenuto: Story = {
  render: () => (
    <div className="grid max-w-2xl gap-6">
      <Tabs defaultValue="fascicolo"><TabsList><TabsTrigger value="fascicolo">Fascicolo</TabsTrigger><TabsTrigger value="documenti">Documenti</TabsTrigger></TabsList><TabsContent value="fascicolo">Dati essenziali del fascicolo.</TabsContent><TabsContent value="documenti">Documenti collegati e stato firma.</TabsContent></Tabs>
      <Separator />
      <Accordion type="single" collapsible defaultValue="requisiti"><AccordionItem value="requisiti"><AccordionTrigger>Requisiti del deposito</AccordionTrigger><AccordionContent>La checklist evidenzia solo i requisiti obbligatori ancora mancanti.</AccordionContent></AccordionItem><AccordionItem value="audit"><AccordionTrigger>Audit</AccordionTrigger><AccordionContent>Le azioni restano tracciate nel fascicolo.</AccordionContent></AccordionItem></Accordion>
      <ScrollArea className="h-28 rounded-lg border p-3" tabIndex={0}>Testo fittizio ripetuto per verificare scroll, focus e contenuto non tagliato. Testo fittizio ripetuto per verificare scroll, focus e contenuto non tagliato. Testo fittizio ripetuto per verificare scroll, focus e contenuto non tagliato.</ScrollArea>
    </div>
  ),
}
