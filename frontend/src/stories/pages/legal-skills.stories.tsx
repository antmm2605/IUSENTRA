import type { Meta, StoryObj } from '@storybook/react-vite'

import { ColdStartInterviewPage } from '../../features/legal-skills/pages/ColdStartInterviewPage'
import { LegalSkillRunPage } from '../../features/legal-skills/pages/LegalSkillRunPage'
import { LegalSkillsCatalogPage } from '../../features/legal-skills/pages/LegalSkillsCatalogPage'
import { LegalSkillsProfilePage } from '../../features/legal-skills/pages/LegalSkillsProfilePage'
import { LegalSkillsReviewPage } from '../../features/legal-skills/pages/LegalSkillsReviewPage'
import { LegalSkillsRunPage } from '../../features/legal-skills/pages/LegalSkillsRunPage'
import { PracticeProfilePage } from '../../features/legal-skills/pages/PracticeProfilePage'
import { PromptLibraryPage } from '../../features/legal-skills/pages/PromptLibraryPage'
import { PromptPathwaysPage } from '../../features/legal-skills/pages/PromptPathwaysPage'
import { ReviewerQueuePage } from '../../features/legal-skills/pages/ReviewerQueuePage'
import { SkillRunDetailPage } from '../../features/legal-skills/pages/SkillRunDetailPage'
import { createPageStory } from '../pageStory'

const meta = {
  title: 'IUSENTRA/Pagine/Legal Skills',
  tags: ['autodocs'],
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

export const Catalogo: Story = createPageStory({ sourcePath: 'src/features/legal-skills/pages/LegalSkillsCatalogPage.tsx', title: 'Catalogo Legal Skills', render: () => <LegalSkillsCatalogPage /> })
export const ProfiloStudio: Story = createPageStory({ sourcePath: 'src/features/legal-skills/pages/PracticeProfilePage.tsx', title: 'Profilo studio', render: () => <PracticeProfilePage /> })
export const ConfigurazioneIniziale: Story = createPageStory({ sourcePath: 'src/features/legal-skills/pages/ColdStartInterviewPage.tsx', title: 'Configurazione iniziale', render: () => <ColdStartInterviewPage /> })
export const Esecuzione: Story = createPageStory({ sourcePath: 'src/features/legal-skills/pages/LegalSkillRunPage.tsx', title: 'Esecuzione Legal Skill', render: () => <LegalSkillRunPage /> })
export const DettaglioEsecuzione: Story = createPageStory({ sourcePath: 'src/features/legal-skills/pages/SkillRunDetailPage.tsx', title: 'Dettaglio esecuzione', render: () => <SkillRunDetailPage /> })
export const CodaRevisione: Story = createPageStory({ sourcePath: 'src/features/legal-skills/pages/ReviewerQueuePage.tsx', title: 'Coda revisione', render: () => <ReviewerQueuePage /> })
export const LibreriaPrompt: Story = createPageStory({ sourcePath: 'src/features/legal-skills/pages/PromptLibraryPage.tsx', title: 'Libreria prompt', render: () => <PromptLibraryPage /> })
export const Percorsi: Story = createPageStory({ sourcePath: 'src/features/legal-skills/pages/PromptPathwaysPage.tsx', title: 'Percorsi', render: () => <PromptPathwaysPage /> })
export const ProfiloLegacy: Story = createPageStory({ sourcePath: 'src/features/legal-skills/pages/LegalSkillsProfilePage.tsx', title: 'Profilo legacy', render: () => <LegalSkillsProfilePage /> })
export const EsecuzioneLegacy: Story = createPageStory({ sourcePath: 'src/features/legal-skills/pages/LegalSkillsRunPage.tsx', title: 'Esecuzione legacy', render: () => <LegalSkillsRunPage /> })
export const RevisioneLegacy: Story = createPageStory({ sourcePath: 'src/features/legal-skills/pages/LegalSkillsReviewPage.tsx', title: 'Revisione legacy', render: () => <LegalSkillsReviewPage /> })
