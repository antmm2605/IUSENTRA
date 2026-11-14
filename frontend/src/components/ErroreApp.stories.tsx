import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, within } from 'storybook/test'
import ErroreApp from './ErroreApp'

function conRadice(dati: Record<string, string>) {
  return function Radice() {
    const radice = document.getElementById('errore-react-root') ?? document.body.appendChild(Object.assign(document.createElement('div'), { id: 'errore-react-root' }))
    Object.entries(dati).forEach(([chiave, valore]) => { radice.dataset[chiave] = valore })
    return <ErroreApp/>
  }
}

const meta = {
  title: 'IUSENTRA/Errori/Pagine d’errore',
  component: ErroreApp,
  tags: ['test'],
} satisfies Meta<typeof ErroreApp>
export default meta
type Story = StoryObj<typeof meta>

export const NonTrovataCollegato: Story = {
  render: conRadice({ errore: '404', titolo: 'Pagina non trovata', messaggio: 'La pagina che cerchi non esiste o è stata spostata.', autenticato: '1' }),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    expect(canvas.getByRole('heading', { name: 'Pagina non trovata' })).toBeInTheDocument()
    expect(canvas.getByRole('link', { name: 'Torna alla panoramica' })).toHaveAttribute('href', '/')
  },
}

export const AccessoNegatoAnonimo: Story = {
  render: conRadice({ errore: '403', titolo: 'Accesso negato', messaggio: 'Non hai i permessi necessari per aprire questa pagina.', autenticato: '0' }),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    expect(canvas.getByText('Errore 403')).toBeInTheDocument()
    expect(canvas.getByRole('link', { name: 'Accedi allo studio' }).getAttribute('href')).toMatch(/^\/login\?next=/)
  },
}
