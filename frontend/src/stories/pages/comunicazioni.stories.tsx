import type { Meta, StoryObj } from '@storybook/react-vite'

import { EmailPecPage } from '../../components/EmailPecPage'
import { MessaggiPage } from '../../components/MessaggiPage'
import { NotificheLegaliPage } from '../../components/NotificheLegaliPage'
import { PresidiNotifichePage } from '../../features/notifiche-legali/PresidiNotifichePage'
import { createPageStory } from '../pageStory'

const meta = {
  title: 'IUSENTRA/Pagine/Comunicazioni',
  tags: ['autodocs'],
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

export const CasellaPec: Story = createPageStory({ sourcePath: 'src/components/EmailPecPage.tsx', title: 'Casella PEC', render: () => <EmailPecPage /> })
export const Messaggi: Story = createPageStory({ sourcePath: 'src/components/MessaggiPage.tsx', title: 'Messaggi', render: () => <MessaggiPage /> })
export const NotificheLegali: Story = createPageStory({ sourcePath: 'src/components/NotificheLegaliPage.tsx', title: 'Notifiche legali', render: () => <NotificheLegaliPage /> })
export const PresidiNotifiche: Story = createPageStory({ sourcePath: 'src/features/notifiche-legali/PresidiNotifichePage.tsx', title: 'Presìdi notifiche', render: () => <PresidiNotifichePage /> })
