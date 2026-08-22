import type { Meta, StoryObj } from '@storybook/react-vite'

import { DocumentEditorPage } from '../../components/DocumentEditorPage'
import { DocumentToolsPage } from '../../components/DocumentToolsPage'
import { EditorProfessionalePage } from '../../components/EditorProfessionalePage'
import { GiurisprudenzaPage } from '../../components/GiurisprudenzaPage'
import { LegalIntelligencePage } from '../../components/LegalIntelligencePage'
import { LexLearningPage } from '../../components/LexLearningPage'
import { RedazioneAttiPage } from '../../components/RedazioneAttiPage'
import { RicercaStudioPage } from '../../components/RicercaStudioPage'
import { TemplateAttiPage } from '../../components/TemplateAttiPage'
import { createPageStory } from '../pageStory'

const meta = {
  title: 'IUSENTRA/Pagine/Documenti e ricerca',
  tags: ['autodocs'],
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

export const TemplateAtti: Story = createPageStory({ sourcePath: 'src/components/TemplateAttiPage.tsx', title: 'Template atti', render: () => <TemplateAttiPage /> })
export const EditorFascicolo: Story = createPageStory({ sourcePath: 'src/components/DocumentEditorPage.tsx', title: 'Editor fascicolo', render: () => <DocumentEditorPage /> })
export const StrumentiDocumentali: Story = createPageStory({ sourcePath: 'src/components/DocumentToolsPage.tsx', title: 'Strumenti documentali', render: () => <DocumentToolsPage /> })
export const EditorProfessionale: Story = createPageStory({ sourcePath: 'src/components/EditorProfessionalePage.tsx', title: 'Editor professionale', render: () => <EditorProfessionalePage /> })
export const RicercaLegale: Story = createPageStory({ sourcePath: 'src/components/LegalIntelligencePage.tsx', title: 'Ricerca legale', render: () => <LegalIntelligencePage /> })
export const Giurisprudenza: Story = createPageStory({ sourcePath: 'src/components/GiurisprudenzaPage.tsx', title: 'Archivio giurisprudenza', render: () => <GiurisprudenzaPage /> })
export const RedazioneAtti: Story = createPageStory({ sourcePath: 'src/components/RedazioneAttiPage.tsx', title: 'Redazione atti', render: () => <RedazioneAttiPage /> })
export const ApprendimentoLex: Story = createPageStory({ sourcePath: 'src/components/LexLearningPage.tsx', title: 'Apprendimento Lex', render: () => <LexLearningPage /> })
export const RicercaStudio: Story = createPageStory({ sourcePath: 'src/components/RicercaStudioPage.tsx', title: 'Ricerca studio', render: () => <RicercaStudioPage initialQuery="fascicolo" /> })
