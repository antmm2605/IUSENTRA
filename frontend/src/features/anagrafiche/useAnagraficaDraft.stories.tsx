import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, waitFor, within } from 'storybook/test'
import { readAnagraficaDraft, useAnagraficaDraft } from './useAnagraficaDraft'

const storageKey = 'iusentra:test:anagrafica:salvataggio-confermato'

function DraftLifecycleProbe() {
  const [values, setValues] = useState(() => {
    window.localStorage.removeItem(storageKey)
    return { note: 'Nota iniziale', _revision: 'prima' }
  })
  const [initialValues, setInitialValues] = useState(values)
  const draft = useAnagraficaDraft({
    storageKey, ready: true, autoRestore: false, values, initialValues,
    protectedFields: new Set(['note']), excludedFields: ['_revision'],
    onRestore: patch => setValues(current => ({ ...current, ...patch })),
  })
  return (
    <form onBlur={draft.handleBlur}>
      <label><span>Nota di collaudo</span><textarea name="note" value={values.note} onChange={event => setValues(current => ({ ...current, note: event.target.value }))} /></label>
      <button type="button" onClick={() => {
        draft.clearAfterSave()
        const confirmed = { ...values, _revision: 'confermata' }
        setInitialValues(confirmed)
        setValues(confirmed)
      }}>Conferma salvataggio</button>
      <button type="button" onClick={() => window.dispatchEvent(new Event('pagehide'))}>Lascia scheda</button>
      <output>{draft.status.message}</output>
    </form>
  )
}

const meta = {
  title: 'IUSENTRA/Anagrafiche/Ciclo della bozza',
  component: DraftLifecycleProbe,
  tags: ['test'],
} satisfies Meta<typeof DraftLifecycleProbe>

export default meta
type Story = StoryObj<typeof meta>

export const ConfermaPoiUscita: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const note = canvas.getByRole('textbox', { name: 'Nota di collaudo' })
    await userEvent.clear(note)
    await userEvent.type(note, 'Nota confermata')
    await userEvent.tab()
    await waitFor(() => expect(readAnagraficaDraft(storageKey)?.values.note).toBe('Nota confermata'))
    await userEvent.click(canvas.getByRole('button', { name: 'Conferma salvataggio' }))
    await userEvent.click(canvas.getByRole('button', { name: 'Lascia scheda' }))
    await waitFor(() => expect(readAnagraficaDraft(storageKey)).toBeNull())

    // Una nuova modifica non confermata deve continuare a essere recuperabile.
    await userEvent.clear(note)
    await userEvent.type(note, 'Modifica successiva non salvata')
    await userEvent.click(canvas.getByRole('button', { name: 'Lascia scheda' }))
    await waitFor(() => expect(readAnagraficaDraft(storageKey)?.values.note).toBe('Modifica successiva non salvata'))
    expect(readAnagraficaDraft(storageKey)?.values).not.toHaveProperty('_revision')
    window.localStorage.removeItem(storageKey)
  },
}
