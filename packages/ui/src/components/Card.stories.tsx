import type { Meta, StoryObj } from '@storybook/react-vite'

import { Button } from './Button'
import { Card } from './Card'

const meta = {
  title: 'IUSENTRA/Card',
  component: Card,
  args: {
    eyebrow: 'Fascicoli',
    title: 'Controllo attività',
    description: 'Riepilogo compatto per evidenziare stato e prossima azione.',
    body: 'Usare questa card per superfici operative con dati reali, stati chiari e azioni collegate.',
  },
} satisfies Meta<typeof Card>

export default meta
type Story = StoryObj<typeof meta>

export const Operativa: Story = {
  args: {
    footer: (
      <>
        <Button variant="secondary">Rivedi</Button>
        <Button>Conferma</Button>
      </>
    ),
  },
}
