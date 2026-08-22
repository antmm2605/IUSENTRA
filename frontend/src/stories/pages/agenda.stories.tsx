import type { Meta, StoryObj } from '@storybook/react-vite'

import { AgendaImportPage } from '../../components/AgendaImportPage'
import { AgendaPage } from '../../components/AgendaPage'
import { NuovaScadenzaPage } from '../../components/NuovaScadenzaPage'
import { NuovoAppuntamentoPage } from '../../components/NuovoAppuntamentoPage'
import { ScadenziarioPage } from '../../components/ScadenziarioPage'
import { TimesheetPage } from '../../components/TimesheetPage'
import { WizardProCompletePage } from '../../components/WizardProCompletePage'
import { WizardProPage } from '../../components/WizardProPage'
import { WizardProStepPage } from '../../components/WizardProStepPage'
import { OggiPage } from '../../pages/daily-plan/OggiPage'
import { createPageStory } from '../pageStory'

const meta = {
  title: 'IUSENTRA/Pagine/Agenda e scadenze',
  tags: ['autodocs'],
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

export const PianoGiornaliero: Story = createPageStory({ sourcePath: 'src/pages/daily-plan/OggiPage.tsx', title: 'Oggi – piano giornaliero', render: () => <OggiPage /> })
export const Calendario: Story = createPageStory({ sourcePath: 'src/components/AgendaPage.tsx', title: 'Agenda', render: () => <AgendaPage /> })
export const ImportazioneCalendario: Story = createPageStory({ sourcePath: 'src/components/AgendaImportPage.tsx', title: 'Importa calendario', render: () => <AgendaImportPage /> })
export const NuovoAppuntamento: Story = createPageStory({ sourcePath: 'src/components/NuovoAppuntamentoPage.tsx', title: 'Nuovo appuntamento', render: () => <NuovoAppuntamentoPage /> })
export const Scadenziario: Story = createPageStory({ sourcePath: 'src/components/ScadenziarioPage.tsx', title: 'Scadenziario', render: () => <ScadenziarioPage /> })
export const NuovaScadenza: Story = createPageStory({ sourcePath: 'src/components/NuovaScadenzaPage.tsx', title: 'Nuova scadenza', render: () => <NuovaScadenzaPage /> })
export const Timesheet: Story = createPageStory({ sourcePath: 'src/components/TimesheetPage.tsx', title: 'Timesheet', render: () => <TimesheetPage /> })
export const PreparazioneUdienza: Story = createPageStory({ sourcePath: 'src/components/WizardProPage.tsx', title: 'Preparazione udienza guidata', render: () => <WizardProPage /> })
export const StepUdienza: Story = createPageStory({ sourcePath: 'src/components/WizardProStepPage.tsx', title: 'Step udienza', render: () => <WizardProStepPage /> })
export const RiepilogoUdienza: Story = createPageStory({ sourcePath: 'src/components/WizardProCompletePage.tsx', title: 'Riepilogo udienza', render: () => <WizardProCompletePage /> })
