import type { Meta, StoryObj } from '@storybook/react-vite'

import { CompensiForensiPage } from '../../components/CompensiForensiPage'
import { FatturazionePage } from '../../components/FatturazionePage'
import { IncassiPagamentiPage } from '../../components/IncassiPagamentiPage'
import { PreventiviPage } from '../../components/PreventiviPage'
import { PreventivoWizardPage } from '../../components/PreventivoWizardPage'
import { PrimaNotaPage } from '../../components/PrimaNotaPage'
import { QuickOrganizerImportPage } from '../../components/QuickOrganizerImportPage'
import { SitoStudioBuilderPage } from '../../components/SitoStudioBuilderPage'
import { SitoStudioPage } from '../../components/SitoStudioPage'
import { SitoStudioRedazioneAiPage } from '../../components/SitoStudioRedazioneAiPage'
import { StatistichePage } from '../../components/StatistichePage'
import { StudioModulePage } from '../../components/StudioModulePage'
import { StudioPage } from '../../components/StudioPage'
import StrumentiLegaliPage from '../../components/StrumentiLegaliPage'
import { TariffarioPage } from '../../components/TariffarioPage'
import { createPageStory } from '../pageStory'

const meta = {
  title: 'IUSENTRA/Pagine/Studio ed economico',
  tags: ['autodocs'],
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

export const Studio: Story = createPageStory({ sourcePath: 'src/components/StudioPage.tsx', title: 'Studio', render: () => <StudioPage /> })
export const ModuloStudio: Story = createPageStory({ sourcePath: 'src/components/StudioModulePage.tsx', title: 'Modulo studio', render: () => <StudioModulePage /> })
export const StrumentiForensi: Story = createPageStory({ sourcePath: 'src/components/StrumentiLegaliPage.tsx', title: 'Strumenti forensi', render: () => <StrumentiLegaliPage /> })
export const Statistiche: Story = createPageStory({ sourcePath: 'src/components/StatistichePage.tsx', title: 'Statistiche', render: () => <StatistichePage /> })
export const SitoStudio: Story = createPageStory({ sourcePath: 'src/components/SitoStudioPage.tsx', title: 'Sito studio', render: () => <SitoStudioPage /> })
export const BuilderSito: Story = createPageStory({ sourcePath: 'src/components/SitoStudioBuilderPage.tsx', title: 'Builder sito', render: () => <SitoStudioBuilderPage /> })
export const RedazioneAiSito: Story = createPageStory({ sourcePath: 'src/components/SitoStudioRedazioneAiPage.tsx', title: 'Redazione AI sito', render: () => <SitoStudioRedazioneAiPage /> })
export const Preventivi: Story = createPageStory({ sourcePath: 'src/components/PreventiviPage.tsx', title: 'Preventivi e incarichi', render: () => <PreventiviPage /> })
export const WizardPreventivo: Story = createPageStory({ sourcePath: 'src/components/PreventivoWizardPage.tsx', title: 'Wizard preventivo', render: () => <PreventivoWizardPage /> })
export const Fatturazione: Story = createPageStory({ sourcePath: 'src/components/FatturazionePage.tsx', title: 'Parcelle e fatture', render: () => <FatturazionePage /> })
export const IncassiEPagamenti: Story = createPageStory({ sourcePath: 'src/components/IncassiPagamentiPage.tsx', title: 'Incassi e pagamenti', render: () => <IncassiPagamentiPage /> })
export const CompensiForensi: Story = createPageStory({ sourcePath: 'src/components/CompensiForensiPage.tsx', title: 'Compensi forensi', render: () => <CompensiForensiPage /> })
export const Tariffario: Story = createPageStory({ sourcePath: 'src/components/TariffarioPage.tsx', title: 'Tariffario', render: () => <TariffarioPage /> })
export const PrimaNota: Story = createPageStory({ sourcePath: 'src/components/PrimaNotaPage.tsx', title: 'Prima nota', render: () => <PrimaNotaPage /> })
export const ImportaPratiche: Story = createPageStory({ sourcePath: 'src/components/QuickOrganizerImportPage.tsx', title: 'Importa pratiche', render: () => <QuickOrganizerImportPage /> })
