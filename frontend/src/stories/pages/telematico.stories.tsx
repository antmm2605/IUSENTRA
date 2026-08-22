import type { Meta, StoryObj } from '@storybook/react-vite'

import { TelematicoPage } from '../../components/TelematicoPage'
import { TelematicoSurfacePage } from '../../components/TelematicoSurfacePage'
import { createPageStory } from '../pageStory'

const meta = {
  title: 'IUSENTRA/Pagine/Servizi telematici',
  tags: ['autodocs'],
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

export const CentroServizi: Story = createPageStory({ sourcePath: 'src/components/TelematicoPage.tsx', title: 'Centro servizi telematici', render: () => <TelematicoPage /> })
export const SuperficiePortali: Story = createPageStory({ sourcePath: 'src/components/TelematicoSurfacePage.tsx', title: 'Superficie portali e checklist', render: () => <TelematicoSurfacePage /> })
