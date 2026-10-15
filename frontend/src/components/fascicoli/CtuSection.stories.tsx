import { useEffect, useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, fn, userEvent, waitFor, within } from 'storybook/test'
import CtuSection from './CtuSection'
import { OPERATIONAL_REFRESH_EVENT } from '../../operationalRefresh'
import { OPERATIONAL_REFRESH_STATUS } from '../../hooks/useOperationalRefresh'

const reads = fn(async () => new Response(JSON.stringify({
  ok: true, incarichi: [], writeProtocol: { persistentCommands: false, revision: null },
}), { status: 200, headers: { 'Content-Type': 'application/json' } }))

function VisibilityProbe() {
  const [active, setActive] = useState(false)
  const [processed, setProcessed] = useState(0)
  useEffect(() => {
    const updated = () => setProcessed(value => value + 1)
    window.addEventListener(OPERATIONAL_REFRESH_STATUS, updated)
    return () => window.removeEventListener(OPERATIONAL_REFRESH_STATUS, updated)
  }, [])
  return <>
    <button type="button" onClick={() => setActive(value => !value)}>{active ? 'Chiudi pannello' : 'Apri pannello'}</button>
    <button type="button" onClick={() => {
      for (let count = 0; count < 2; count++) window.dispatchEvent(new CustomEvent(OPERATIONAL_REFRESH_EVENT,
        { detail: { domains: ['fascicoli'], remote: true } }))
    }}>Aggiornamento controllato</button>
    <output aria-label="Aggiornamenti elaborati">{processed}</output>
    <div hidden={!active}><CtuSection fascicoloId="COLLAUDO" active={active}/></div>
  </>
}

const meta = {
  title: 'IUSENTRA/Fascicoli/CTU su richiesta',
  component: VisibilityProbe,
  tags: ['test'],
  beforeEach: () => {
    const original = window.fetch
    reads.mockClear()
    window.fetch = (input, options) => String(input).endsWith('/COLLAUDO/ctu') ? reads() : original(input, options)
    return () => { window.fetch = original }
  },
} satisfies Meta<typeof VisibilityProbe>
export default meta
type Story = StoryObj<typeof meta>

export const BozzaEInvalidazioneNascosta: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    expect(reads).not.toHaveBeenCalled()
    await userEvent.click(canvas.getByRole('button', { name: 'Apri pannello' }))
    await waitFor(() => expect(reads).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(canvas.getByLabelText('Aggiornamenti elaborati')).toHaveTextContent('1'))
    await userEvent.click(canvas.getByRole('button', { name: 'Nuovo incarico CTU' }))
    await userEvent.type(canvas.getByRole('textbox', { name: 'Nome CTU' }), 'Bozza controllata')
    await userEvent.click(canvas.getByRole('button', { name: 'Chiudi pannello' }))
    await userEvent.click(canvas.getByRole('button', { name: 'Aggiornamento controllato' }))
    // Il segnale di fine coda prova che l'invalidazione è stata elaborata.
    await waitFor(() => expect(canvas.getByLabelText('Aggiornamenti elaborati')).toHaveTextContent('2'))
    expect(reads).toHaveBeenCalledTimes(1)
    await userEvent.click(canvas.getByRole('button', { name: 'Apri pannello' }))
    await waitFor(() => expect(reads).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(canvas.getByLabelText('Aggiornamenti elaborati')).toHaveTextContent('3'))
    expect(canvas.getByRole('textbox', { name: 'Nome CTU' })).toHaveValue('Bozza controllata')
  },
}
