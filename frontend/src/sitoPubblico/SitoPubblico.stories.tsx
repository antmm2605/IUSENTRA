import { useEffect, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import { createRoot, hydrateRoot } from 'react-dom/client'
import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, waitFor, within } from 'storybook/test'
import { SitoPubblico } from './SitoPubblico'
import type { DatiPaginaSito } from './tipi'
import richieste from './__fixtures__/tutti-i-blocchi.json'
import htmlServer from './__fixtures__/tutti-i-blocchi.ssr.json'

/**
 * Collaudo del sito pubblico: l'HTML prodotto da Node (fixture rigenerata e verificata da
 * tests/test_sito_pubblico_react.py) viene idratato nel browser senza alcuna differenza, e il
 * disegno fatto dal browser coincide con quello del server per tutti i 39 tipi di blocco.
 */
const pagine = richieste as unknown as DatiPaginaSito[]
const html = htmlServer as string[]

/**
 * Forma canonica del markup: elementi, attributi in ordine alfabetico e testi (i testi adiacenti uniti).
 * L'ordine degli attributi e i commenti vuoti che renderToString mette fra i testi non sono differenze.
 */
function canonico(nodo: Node): string {
  if (nodo.nodeType === Node.TEXT_NODE) return nodo.textContent || ''
  if (nodo.nodeType !== Node.ELEMENT_NODE) return ''
  const elemento = nodo as Element
  // La scelta di un <select> controllato è un attributo nel server e una proprietà nel browser.
  const attributi = [...elemento.attributes].filter((a) => !(elemento instanceof HTMLOptionElement && a.name === 'selected'))
    .map((a) => `${a.name}="${a.value}"`).concat(elemento instanceof HTMLOptionElement ? [`scelto=${elemento.selected}`] : []).sort().join(' ')
  return `<${elemento.tagName.toLowerCase()} ${attributi}>${[...elemento.childNodes].map(canonico).join('')}</${elemento.tagName.toLowerCase()}>`
}

function normalizza(radice: HTMLElement): string {
  return [...radice.childNodes].map(canonico).join('')
}

type Esito = { pagina: number; differenze: number; uguale: boolean; scarto?: string }

function Collaudo() {
  const contenitore = useRef<HTMLDivElement>(null)
  const [esiti, setEsiti] = useState<Esito[]>([])
  useEffect(() => {
    const radice = contenitore.current
    if (!radice) return
    const risultati: Esito[] = []
    // Fuori dal ciclo di vita del componente: flushSync disegna subito.
    const avvio = setTimeout(() => {
    pagine.forEach((dati, indice) => {
      // 1) Idratazione dell'HTML del server.
      const idratato = document.createElement('div')
      idratato.innerHTML = html[indice]
      radice.appendChild(idratato)
      let differenze = 0
      flushSync(() => { hydrateRoot(idratato, <SitoPubblico dati={dati}/>, { onRecoverableError: () => { differenze += 1 } }) })
      // 2) Disegno da zero nel browser.
      const disegnato = document.createElement('div')
      radice.appendChild(disegnato)
      flushSync(() => { createRoot(disegnato).render(<SitoPubblico dati={dati}/>) })
      const browser = normalizza(disegnato)
      const letto = document.createElement('div')
      letto.innerHTML = html[indice]
      const server = normalizza(letto)
      let punto = 0
      while (punto < browser.length && browser[punto] === server[punto]) punto += 1
      risultati.push({ pagina: indice, differenze, uguale: browser === server, scarto: browser === server ? undefined : `browser «${browser.slice(Math.max(0, punto - 80), punto + 80)}» server «${server.slice(Math.max(0, punto - 80), punto + 80)}»` })
    })
    setTimeout(() => setEsiti(risultati), 300)
    }, 0)
    return () => clearTimeout(avvio)
  }, [])
  return (
    <div>
      <output aria-label="Esito del collaudo">{esiti.length ? JSON.stringify(esiti) : 'in corso'}</output>
      <div ref={contenitore} hidden/>
    </div>
  )
}

const meta = {
  title: 'IUSENTRA/Sito pubblico/Stesso markup sul server e nel browser',
  component: Collaudo,
  tags: ['test'],
  // Il markup del sito usa i fogli di stile pubblici (Bootstrap e studio_site_public.css), non caricati
  // in Storybook: il contrasto si verifica sulla pagina reale, qui si collauda solo il markup.
  parameters: { a11y: { test: 'off' } },
} satisfies Meta<typeof Collaudo>
export default meta
type Story = StoryObj<typeof meta>

export const TuttiITipiDiBlocco: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await waitFor(() => expect(canvas.getByLabelText('Esito del collaudo').textContent).not.toBe('in corso'), { timeout: 10000 })
    const esiti = JSON.parse(canvas.getByLabelText('Esito del collaudo').textContent || '[]') as Esito[]
    expect(esiti).toHaveLength(pagine.length)
    for (const esito of esiti) {
      expect(esito.differenze).toBe(0)
      expect(esito.scarto).toBeUndefined()
    }
  },
}

export const PaginaIniziale: Story = {
  render: () => <SitoPubblico dati={pagine[0]}/>,
}

/** Controllo del collaudo: un HTML diverso da quello del componente deve risultare una differenza. */
export const DifferenzaRilevata: Story = {
  render: () => <span>controllo</span>,
  play: async () => {
    const prova = document.createElement('div')
    prova.innerHTML = html[1].replace('Contatta lo studio', 'Testo alterato')
    document.body.appendChild(prova)
    let differenze = 0
    await new Promise<void>((fatto) => setTimeout(() => {
      flushSync(() => { hydrateRoot(prova, <SitoPubblico dati={pagine[1]}/>, { onRecoverableError: () => { differenze += 1 } }) })
      setTimeout(fatto, 300)
    }, 0))
    prova.remove()
    expect(differenze).toBeGreaterThan(0)
  },
}
