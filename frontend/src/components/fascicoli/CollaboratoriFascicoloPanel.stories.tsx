import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, fn, userEvent, waitFor, within } from 'storybook/test'
import { CollaboratoriFascicoloPanel } from './CollaboratoriFascicoloPanel'

const ruoli = [
  { value: 'LETTURA', label: 'Lettura', tone: 'info', description: 'Può consultare il fascicolo senza modificare i dati.' },
  { value: 'SCRITTURA', label: 'Scrittura', tone: 'primary', description: 'Può consultare e aggiornare i contenuti del fascicolo.' },
  { value: 'GESTORE', label: 'Gestore', tone: 'warning', description: 'Può aggiornare il fascicolo e gestire gli altri collaboratori.' },
]
const accesso = {
  idUser: 'u-2', username: 'praticante', name: 'Maria Rossi', role: 'LETTURA', roleLabel: 'Lettura', roleTone: 'info',
  sharedBy: 'avvocato', sharedAt: '2026-11-01T10:00:00', sharedAtLabel: '01/11/2026', deadline: '', deadlineLabel: 'Nessuna scadenza',
  daysToDeadline: null, expired: false, expiring: false, notes: 'Ricerca giurisprudenza', tags: ['ricerca'],
}
const chiamate = fn(async (_url: string, _options?: RequestInit) => new Response('{}'))

function rispondi(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

const meta = {
  title: 'IUSENTRA/Fascicoli/Collaboratori del fascicolo',
  component: CollaboratoriFascicoloPanel,
  tags: ['test'],
  args: { fascicoloId: 'COLLAUDO', active: true },
  beforeEach: () => {
    const original = window.fetch
    let condiviso = false
    chiamate.mockClear()
    window.fetch = async (input, options) => {
      const url = String(input)
      if (!url.includes('/api/v1/fascicoli/COLLAUDO/collaboratori')) return original(input, options)
      await chiamate(url, options)
      if (options?.method === 'POST') { condiviso = true; return rispondi({ stato: 'ok', messaggio: 'Fascicolo condiviso con Luca Bianchi.' }, 201) }
      return rispondi({
        matter: { id: 'COLLAUDO', number: '2026/001', title: 'Opposizione a decreto ingiuntivo' },
        permissions: { canManage: true },
        collaborators: condiviso ? [accesso, { ...accesso, idUser: 'u-3', username: 'collega', name: 'Luca Bianchi' }] : [accesso],
        availableUsers: condiviso ? [] : [{ id: 'u-3', username: 'collega', name: 'Luca Bianchi' }],
        roleOptions: ruoli,
      })
    }
    return () => { window.fetch = original }
  },
} satisfies Meta<typeof CollaboratoriFascicoloPanel>
export default meta
type Story = StoryObj<typeof meta>

export const ElencoECondivisione: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await waitFor(() => expect(canvas.getByText('Maria Rossi')).toBeInTheDocument())
    await userEvent.selectOptions(canvas.getByRole('combobox', { name: 'Collaboratore' }), 'u-3')
    await userEvent.click(canvas.getByRole('button', { name: 'Condividi il fascicolo' }))
    await waitFor(() => expect(canvas.getByRole('status')).toHaveTextContent('Fascicolo condiviso con Luca Bianchi.'))
    const post = chiamate.mock.calls.find(([, options]) => options?.method === 'POST')
    expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({ id_utente: 'u-3', ruolo: 'LETTURA' })
    await waitFor(() => expect(canvas.getByText('Tutti gli utenti attivi hanno già accesso a questo fascicolo.')).toBeInTheDocument())
  },
}

export const ChiusoNonCarica: Story = {
  args: { active: false },
  play: async () => {
    expect(chiamate).not.toHaveBeenCalled()
  },
}
