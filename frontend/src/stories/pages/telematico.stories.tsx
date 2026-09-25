import type { Meta, StoryObj } from '@storybook/react-vite'

import { TelematicoPage } from '../../components/TelematicoPage'
import { TelematicoSurfacePage } from '../../components/TelematicoSurfacePage'
import PdpPenalePage from '../../components/penalePdp/PdpPenalePage'
import { createPageStory } from '../pageStory'

const meta = {
  title: 'IUSENTRA/Pagine/Servizi telematici',
  tags: ['autodocs'],
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

export const CentroServizi: Story = createPageStory({ sourcePath: 'src/components/TelematicoPage.tsx', title: 'Centro servizi telematici', render: () => <TelematicoPage /> })
export const SuperficiePortali: Story = createPageStory({ sourcePath: 'src/components/TelematicoSurfacePage.tsx', title: 'Superficie portali e checklist', render: () => <TelematicoSurfacePage /> })
export const DepositiPenaliPdp: Story = createPageStory({ sourcePath: 'src/components/penalePdp/PdpPenalePage.tsx', title: 'Depositi penali PDP', render: () => <PdpPenalePage /> })
