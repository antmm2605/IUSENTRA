import type { Meta, StoryObj } from '@storybook/react-vite'

import { Page } from '../../ui/Page'
import { createPageStory } from '../pageStory'

const meta = {
  title: 'IUSENTRA/Pagine/Fondamenta',
  tags: ['autodocs'],
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

export const PrimitivaPagina: Story = createPageStory({
  sourcePath: 'src/ui/Page.tsx',
  title: 'Primitiva Page',
  render: () => (
    <Page title="Superficie operativa" subtitle="Gerarchia, heading e azioni di una pagina IUSENTRA.">
      <section className="iu-panel"><h2>Contenuto operativo</h2><p>Fixture Storybook sicura, priva di dati di studio.</p></section>
    </Page>
  ),
})
