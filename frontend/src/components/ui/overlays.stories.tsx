import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react-vite'
import { MoreHorizontal } from 'lucide-react'

import { Button } from './button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from './dialog'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from './dropdown-menu'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from './sheet'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './tooltip'

function DialogScenario() {
  const [open, setOpen] = useState(false)
  return <Dialog open={open} onOpenChange={setOpen}><DialogTrigger asChild><Button>Apri conferma</Button></DialogTrigger><DialogContent><DialogHeader><DialogTitle>Conferma operazione</DialogTitle><DialogDescription>La storia controlla focus, chiusura e posizione della modale con dati fittizi.</DialogDescription></DialogHeader><DialogFooter showCloseButton><Button onClick={() => setOpen(false)}>Conferma</Button></DialogFooter></DialogContent></Dialog>
}

function SheetScenario() {
  const [open, setOpen] = useState(false)
  return <Sheet open={open} onOpenChange={setOpen}><SheetTrigger asChild><Button variant="outline">Apri pannello</Button></SheetTrigger><SheetContent><SheetHeader><SheetTitle>Dati fascicolo</SheetTitle><SheetDescription>Il pannello laterale resta leggibile su desktop e mobile.</SheetDescription></SheetHeader></SheetContent></Sheet>
}

const meta = {
  title: 'IUSENTRA/Fondamenta/Overlay e menu',
  tags: ['autodocs'],
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

export const ModaleConferma: Story = { render: () => <DialogScenario /> }
export const PannelloLaterale: Story = { render: () => <SheetScenario /> }
export const MenuAzioni: Story = {
  render: () => <DropdownMenu><DropdownMenuTrigger asChild><Button variant="outline" size="icon" aria-label="Apri azioni"><MoreHorizontal /></Button></DropdownMenuTrigger><DropdownMenuContent><DropdownMenuItem>Apri fascicolo</DropdownMenuItem><DropdownMenuItem>Duplica bozza</DropdownMenuItem><DropdownMenuSeparator /><DropdownMenuItem variant="destructive">Archivia</DropdownMenuItem></DropdownMenuContent></DropdownMenu>,
}
export const SuggerimentoAccessibile: Story = {
  render: () => <TooltipProvider><Tooltip defaultOpen><TooltipTrigger asChild><Button variant="outline">Icona informativa</Button></TooltipTrigger><TooltipContent>Spiegazione disponibile anche da tastiera.</TooltipContent></Tooltip></TooltipProvider>,
}
