import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, fn, userEvent, within } from 'storybook/test'
import { QuadroFascicolo, normalizzaQuadro } from './QuadroFascicolo'
import type { QuadroLettura } from './QuadroFascicolo'
import { SezioneFascicolo } from './SezioneFascicolo'
import { TestataFascicolo } from './TestataFascicolo'

// Risposta d'esempio con la forma del contratto GET /api/v1/ui/fascicoli/<id>/quadro (dati di collaudo, non reali).
const risposta = {
  ok: true,
  stato: { codice: 'da_archiviare', etichetta: 'Definita, da archiviare', dettaglio: 'Sentenza depositata, fascicolo da chiudere.' },
  righe: [
    { tema: 'documenti', titolo: 'Documenti', testo: '43 documenti catalogati, 2 da classificare', livello: 'info', sezione: 'sezione-documenti' },
    { tema: 'prossimo_passo', titolo: 'Prossimo passo', testo: 'Archiviare il fascicolo con lo ZIP', livello: 'attenzione', sezione: 'sezione-andamento' },
    { tema: 'termini', titolo: 'Termini', testo: 'Nessun termine aperto', livello: 'ok', sezione: 'sezione-termini' },
    { tema: 'economia', titolo: 'Economia', testo: 'Parcella emessa, pagamento da registrare', livello: 'urgente', sezione: 'sezione-economia' },
    { tema: 'notifiche', titolo: 'Notifiche', testo: 'Sentenza notificata il 12/10/2026', livello: 'ok', sezione: 'sezione-comunicazioni' },
  ],
  generato_il: '2026-11-10T09:30:00+01:00',
}
const dati = normalizzaQuadro(risposta)
const apriSezione = fn()
const riprova = fn()

function Pagina({ lettura }:{ lettura: QuadroLettura }) {
  return (
    <div>
      <TestataFascicolo rg="161/2026" ufficio="Tribunale di Reggio Calabria" rito="lavoro" giudice="Francesca Rossi" cliente="Cliente di collaudo" controparte="Ministero" valore={5200} stato={lettura.fase === 'pronto' ? lettura.dati.stato.etichetta : 'Definito'} statoTono="warning"/>
      <QuadroFascicolo lettura={lettura} onRiprova={riprova} onApriSezione={apriSezione}/>
      <SezioneFascicolo id="sezione-andamento"><p>Pannelli dell’andamento.</p></SezioneFascicolo>
      <SezioneFascicolo id="sezione-deposito" apriQuando={false} avviso="Nessun deposito da preparare"><p>Presidio del deposito.</p></SezioneFascicolo>
    </div>
  )
}

const meta = {
  title: 'IUSENTRA/Fascicoli/Quadro del fascicolo',
  component: Pagina,
  tags: ['test'],
  beforeEach: () => { apriSezione.mockClear(); riprova.mockClear() },
} satisfies Meta<typeof Pagina>

export default meta
type Story = StoryObj<typeof meta>

export const Pronto: Story = {
  args: { lettura: dati ? { fase: 'pronto', dati } : { fase: 'assente' } },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const righe = canvas.getAllByRole('link')
    // Le righe seguono l'ordine dei temi, qualunque sia l'ordine della risposta.
    const attesi = ['Prossimo passo', 'Termini', 'Economia', 'Notifiche', 'Documenti']
    await expect(righe).toHaveLength(attesi.length)
    for (const [indice, tema] of attesi.entries()) await expect(righe[indice]).toHaveTextContent(tema)
    await expect(righe[2]).toHaveAttribute('href', '#sezione-economia')
    await expect(canvas.getByText('Definita, da archiviare')).toBeInTheDocument()
    await userEvent.click(canvas.getByRole('link', { name: /Economia/ }))
    await expect(apriSezione).toHaveBeenCalledWith('sezione-economia')
    await expect(canvas.getByText('Nessun deposito da preparare')).toBeInTheDocument()
  },
}

export const Errore: Story = {
  args: { lettura: { fase: 'errore', messaggio: 'Il quadro del fascicolo non è disponibile in questo momento. Le sezioni qui sotto restano consultabili.' } },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByRole('alert')).toHaveTextContent('non è disponibile')
    await userEvent.click(canvas.getByRole('button', { name: /Riprova/ }))
    await expect(riprova).toHaveBeenCalled()
  },
}

export const ServizioAssente: Story = {
  args: { lettura: { fase: 'assente' } },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.queryByRole('heading', { name: /Quadro del fascicolo/ })).toBeNull()
    // La pagina resta integra: testata e sezioni ci sono anche senza quadro.
    await expect(canvas.getByText('Cliente di collaudo c. Ministero')).toBeInTheDocument()
    await expect(canvas.getByText('Andamento')).toBeInTheDocument()
  },
}
