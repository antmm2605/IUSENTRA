import type { Meta, StoryObj } from '@storybook/react-vite'
import { CheckCircle2, ShieldCheck } from 'lucide-react'

import { Button } from './Button'

const meta = {
  title: 'IUSENTRA/Button',
  component: Button,
  args: {
    children: 'Salva configurazione',
    variant: 'primary',
  },
  argTypes: {
    variant: {
      control: 'inline-radio',
      options: ['primary', 'secondary', 'ghost', 'danger'],
    },
    size: {
      control: 'inline-radio',
      options: ['sm', 'md'],
    },
  },
} satisfies Meta<typeof Button>

export default meta
type Story = StoryObj<typeof meta>

export const Primary: Story = {
  args: {
    icon: <CheckCircle2 aria-hidden="true" size={18} />,
  },
}

export const Secondary: Story = {
  args: {
    children: 'Verifica requisiti',
    icon: <ShieldCheck aria-hidden="true" size={18} />,
    variant: 'secondary',
  },
}
