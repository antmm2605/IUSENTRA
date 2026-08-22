import type { Meta, StoryObj } from '@storybook/react-vite'

import { ProcedureCompletionPage } from '../../features/procedure-completion/ProcedureCompletionPage'
import { createPageStory } from '../pageStory'

const meta = {
  title: 'IUSENTRA/Pagine/Procedure Completion',
  tags: ['autodocs'],
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

export const SchedeGovernate: Story = createPageStory({
  sourcePath: 'src/features/procedure-completion/ProcedureCompletionPage.tsx',
  title: 'Schede procedura governate',
  render: () => <ProcedureCompletionPage />,
})
