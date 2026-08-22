import type { Meta, StoryObj } from '@storybook/react-vite'

import { CartelleCondivisePage } from '../../components/CartelleCondivisePage'
import { DocumentiAIPage } from '../../components/DocumentiAIPage'
import { FascicoloDepositoPage } from '../../components/FascicoloDepositoPage'
import { FascicoliPage } from '../../components/FascicoliPage'
import { createPageStory } from '../pageStory'

const meta = {
  title: 'IUSENTRA/Pagine/Fascicoli',
  tags: ['autodocs'],
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

export const ElencoFascicoli: Story = createPageStory({ sourcePath: 'src/components/FascicoliPage.tsx', title: 'Elenco fascicoli', render: () => <FascicoliPage /> })
export const DepositoTelematico: Story = createPageStory({ sourcePath: 'src/components/FascicoloDepositoPage.tsx', title: 'Deposito telematico', render: () => <FascicoloDepositoPage id="FASC-MOCK-001" /> })
export const DocumentiAiEOcr: Story = createPageStory({ sourcePath: 'src/components/DocumentiAIPage.tsx', title: 'Documenti AI e OCR', render: () => <DocumentiAIPage fascicoloId="FASC-MOCK-001" /> })
export const CartelleCondivise: Story = createPageStory({ sourcePath: 'src/components/CartelleCondivisePage.tsx', title: 'Cartelle condivise', render: () => <CartelleCondivisePage /> })
