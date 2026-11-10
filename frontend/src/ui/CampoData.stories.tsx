import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, waitFor, within } from 'storybook/test'

import { CampoData } from './CampoData'

/** Banco di prova: mostra il valore tecnico che il codice chiamante riceve (lo stesso dell'input nativo). */
function BancoCampoData({ conOra = false, iniziale = '', min, max }: { conOra?: boolean; iniziale?: string; min?: string; max?: string }) {
  const [valore, setValore] = useState(iniziale)
  return (
    <div className="iu-field">
      <label className="iu-field">
        <span>{conOra ? 'Data e ora dell’udienza' : 'Data documento'}</span>
        <CampoData conOra={conOra} value={valore} onChange={setValore} min={min} max={max} />
      </label>
      <output aria-label="Valore inviato">{valore || '(vuoto)'}</output>
    </div>
  )
}

const meta = {
  title: 'IUSENTRA/Fondamenta/Campo data italiano',
  component: BancoCampoData,
  tags: ['autodocs', 'test'],
} satisfies Meta<typeof BancoCampoData>

export default meta
type Story = StoryObj<typeof meta>

export const DataDocumento: Story = {
  args: { iniziale: '2026-07-27' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const campo = canvas.getByRole('textbox', { name: 'Data documento' })
    await expect(campo).toHaveValue('27/07/2026')
    await userEvent.clear(campo)
    await userEvent.type(campo, '31/02/2026')
    await expect(canvas.getByLabelText('Valore inviato')).toHaveTextContent('(vuoto)')
    await userEvent.tab()
    await expect(await canvas.findByRole('alert')).toHaveTextContent('Data non valida')
    await userEvent.clear(campo)
    await userEvent.type(campo, '29.02.2028')
    await userEvent.tab()
    await expect(campo).toHaveValue('29/02/2028')
    await expect(canvas.getByLabelText('Valore inviato')).toHaveTextContent('2028-02-29')
  },
}

export const CalendarioDaTastiera: Story = {
  args: { iniziale: '2026-07-27' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const corpo = within(canvasElement.ownerDocument.body)
    await userEvent.click(canvas.getByRole('button', { name: /Apri il calendario/ }))
    const griglia = await corpo.findByRole('grid', { name: 'Calendario di luglio 2026' })
    await expect(within(griglia).getAllByRole('columnheader').map((cella) => cella.textContent)).toEqual(['lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom'])
    await waitFor(() => expect(corpo.getByRole('button', { name: 'lunedì 27 luglio 2026' })).toHaveFocus())
    await userEvent.keyboard('{ArrowRight}{ArrowDown}{Enter}')
    await expect(canvas.getByRole('textbox', { name: 'Data documento' })).toHaveValue('04/08/2026')
    await expect(canvas.getByLabelText('Valore inviato')).toHaveTextContent('2026-08-04')
  },
}

export const DataEOra: Story = {
  args: { conOra: true, iniziale: '2026-11-05T09:30' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const campo = canvas.getByRole('textbox', { name: 'Data e ora dell’udienza' })
    await expect(campo).toHaveValue('05/11/2026 09:30')
    await userEvent.clear(campo)
    await userEvent.type(campo, '06/11/2026')
    await userEvent.tab()
    await expect(await canvas.findByRole('alert')).toHaveTextContent('Indica anche l’ora')
    await userEvent.click(campo)
    await userEvent.type(campo, ' 10:15')
    await expect(canvas.getByLabelText('Valore inviato')).toHaveTextContent('2026-11-06T10:15')
  },
}

export const ConLimiti: Story = {
  args: { iniziale: '', min: '2026-11-10' },
}
