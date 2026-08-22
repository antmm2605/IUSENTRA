import type { Meta, StoryObj } from '@storybook/react-vite'

import { AnagraficaClientiPage } from '../../components/AnagraficaClientiPage'
import { CartellaClientePage } from '../../components/CartellaClientePage'
import { ClientPortalPage } from '../../components/ClientPortalPage'
import { CrmPage } from '../../components/CrmPage'
import { NuovoClientePage } from '../../components/NuovoClientePage'
import { SoggettiPage } from '../../components/SoggettiPage'
import { createPageStory } from '../pageStory'

const meta = {
  title: 'IUSENTRA/Pagine/Anagrafiche e clienti',
  tags: ['autodocs'],
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

export const Clienti: Story = createPageStory({ sourcePath: 'src/components/AnagraficaClientiPage.tsx', title: 'Anagrafica clienti', render: () => <AnagraficaClientiPage /> })
export const NuovoCliente: Story = createPageStory({ sourcePath: 'src/components/NuovoClientePage.tsx', title: 'Nuovo cliente', render: () => <NuovoClientePage /> })
export const SoggettiEParti: Story = createPageStory({ sourcePath: 'src/components/SoggettiPage.tsx', title: 'Soggetti e parti', render: () => <SoggettiPage /> })
export const CartellaCliente: Story = createPageStory({ sourcePath: 'src/components/CartellaClientePage.tsx', title: 'Cartella cliente', render: () => <CartellaClientePage /> })
export const PortaleClienti: Story = createPageStory({ sourcePath: 'src/components/ClientPortalPage.tsx', title: 'Portale clienti studio', render: () => <ClientPortalPage mode="studio" /> })
export const PipelineCrm: Story = createPageStory({ sourcePath: 'src/components/CrmPage.tsx', title: 'Pipeline CRM', render: () => <CrmPage /> })
