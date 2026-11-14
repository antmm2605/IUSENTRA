import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, within } from 'storybook/test'
import { LettoreSentenza } from './LettoreSentenzaApp'
import type { DocumentoLettore } from './lettoreSentenzaDati'

const provvedimento: DocumentoLettore = {
  tipo: 'provvedimento',
  occhiello: 'IUSENTRA · Lettura del provvedimento',
  titolo: 'Cassazione 12345/2026',
  righe: ['Corte di Cassazione · Sezione 3 · Deposito 14/10/2026'],
  provenienza: 'Trascrizione da fonte non ufficiale',
  fonteUrl: 'javascript:alert(1)',
  avvisi: [],
  blocchi: [
    { tipo: 'titolo', testo: 'MOTIVI DELLA DECISIONE', ancora: 'sezione-0' },
    { tipo: 'paragrafo', testo: '<script>alert(1)</script> Il ricorso è infondato.', ancora: '' },
  ],
  integrita: [{ etichetta: 'SHA-256 del testo visualizzato', valore: 'a'.repeat(64) }],
  nota: 'Impaginazione di lettura del testo archiviato.',
  testoSempliceUrl: '?format=txt',
}

const meta = {
  title: 'IUSENTRA/Giurisprudenza/Lettore dei provvedimenti',
  component: LettoreSentenza,
  tags: ['test'],
} satisfies Meta<typeof LettoreSentenza>
export default meta
type Story = StoryObj<typeof meta>

export const TestoComeTestoMaiHtml: Story = {
  args: { documento: provvedimento },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    expect(canvas.getByRole('heading', { level: 1, name: 'Cassazione 12345/2026' })).toBeInTheDocument()
    expect(canvas.getByText(/<script>alert\(1\)<\/script> Il ricorso è infondato\./)).toBeInTheDocument()
    expect(canvasElement.querySelector('article script')).toBeNull()
    expect(canvas.queryByRole('link', { name: /Apri la fonte/ })).toBeNull()
    expect(canvas.getByRole('link', { name: 'MOTIVI DELLA DECISIONE' })).toHaveAttribute('href', '#sezione-0')
  },
}

export const TraduzioneConOriginale: Story = {
  args: {
    documento: {
      ...provvedimento,
      tipo: 'traduzione',
      occhiello: 'IUSENTRA · Traduzione di servizio',
      provenienza: 'Traduzione automatica, non ufficiale',
      blocchi: [],
      linguaOriginale: 'fr',
      originaleUrl: '/giurisprudenza/corpus/1/testo?embed=source',
      parti: [{ originale: 'La Cour rejette le pourvoi.', traduzione: 'La Corte rigetta il ricorso.', avviso: '' }],
    },
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    expect(canvas.getByText('Originale (fr)')).toBeInTheDocument()
    expect(canvas.getByText('La Corte rigetta il ricorso.')).toBeInTheDocument()
    expect(canvas.getByRole('link', { name: 'Leggi il testo originale' })).toHaveAttribute('href', '/giurisprudenza/corpus/1/testo?embed=source')
  },
}
