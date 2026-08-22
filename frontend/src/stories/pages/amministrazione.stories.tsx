import type { Meta, StoryObj } from '@storybook/react-vite'

import { AdminDatabasePage } from '../../components/AdminDatabasePage'
import { AmministrazionePage } from '../../components/AmministrazionePage'
import { AuditPage } from '../../components/AuditPage'
import { BackupPage } from '../../components/BackupPage'
import { ImpostazioniPage as LegacyImpostazioniPage } from '../../components/ImpostazioniPage'
import { PrivacyRegistroPage } from '../../components/PrivacyRegistroPage'
import { ProfiloPage } from '../../components/ProfiloPage'
import { ProfiliPage } from '../../components/ProfiliPage'
import { UtentiPage } from '../../components/UtentiPage'
import { ImpostazioniPage as FeatureImpostazioniPage } from '../../features/impostazioni/ImpostazioniPage'
import { createPageStory } from '../pageStory'

const meta = {
  title: 'IUSENTRA/Pagine/Amministrazione e impostazioni',
  tags: ['autodocs'],
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

export const Utenti: Story = createPageStory({ sourcePath: 'src/components/UtentiPage.tsx', title: 'Utenti', render: () => <UtentiPage /> })
export const Profilo: Story = createPageStory({ sourcePath: 'src/components/ProfiloPage.tsx', title: 'Profilo', render: () => <ProfiloPage /> })
export const ProfiliEPermessi: Story = createPageStory({ sourcePath: 'src/components/ProfiliPage.tsx', title: 'Profili e permessi', render: () => <ProfiliPage /> })
export const RegistroGdpr: Story = createPageStory({ sourcePath: 'src/components/PrivacyRegistroPage.tsx', title: 'Registro GDPR', render: () => <PrivacyRegistroPage /> })
export const ImpostazioniOperative: Story = createPageStory({ sourcePath: 'src/components/ImpostazioniPage.tsx', title: 'Impostazioni operative', render: () => <LegacyImpostazioniPage /> })
export const Backup: Story = createPageStory({ sourcePath: 'src/components/BackupPage.tsx', title: 'Backup', render: () => <BackupPage /> })
export const Audit: Story = createPageStory({ sourcePath: 'src/components/AuditPage.tsx', title: 'Audit', render: () => <AuditPage /> })
export const Amministrazione: Story = createPageStory({ sourcePath: 'src/components/AmministrazionePage.tsx', title: 'Amministrazione', render: () => <AmministrazionePage /> })
export const Database: Story = createPageStory({ sourcePath: 'src/components/AdminDatabasePage.tsx', title: 'Database', render: () => <AdminDatabasePage /> })
export const ImpostazioniModulo: Story = createPageStory({ sourcePath: 'src/features/impostazioni/ImpostazioniPage.tsx', title: 'Impostazioni modulo React', render: () => <FeatureImpostazioniPage /> })
