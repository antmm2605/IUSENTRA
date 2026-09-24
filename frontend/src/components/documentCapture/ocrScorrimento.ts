import { useEffect, type RefObject } from 'react'

/**
 * Pagine del documento e foglio del testo scorrono insieme.
 *
 * Il riscontro si fa guardando la stessa riga a sinistra e a destra: quando
 * uno dei due pannelli scorre, l'altro si porta sulla stessa pagina e alla
 * stessa altezza dentro la pagina. Le pagine si riconoscono dall'attributo
 * data-pagina, presente sia sulle immagini sia sui fogli A4.
 */
const IMMAGINI = '.iu-ocr-viewer__foglio'
const TESTO = '.iu-ocr-foglio'
const ECO = 'ocrFermo'

/** Scorre il contenitore senza che l'altro pannello lo segua. */
export function fermaEco(contenitore: HTMLElement, alto: number) {
  const prima = contenitore.scrollTop
  contenitore.scrollTop = alto
  if (Math.abs(contenitore.scrollTop - prima) >= 1) contenitore.dataset[ECO] = '1'
}

/** Pagina in cima alla vista e quanto se n'e' gia' passato, da 0 a 1. */
function posizione(contenitore: HTMLElement): { pagina: string; quota: number } | null {
  const alto = contenitore.getBoundingClientRect().top
  let scelta: { pagina: string; quota: number } | null = null
  for (const elemento of contenitore.querySelectorAll<HTMLElement>('[data-pagina]')) {
    const zona = elemento.getBoundingClientRect()
    if (zona.top - alto > 1) break
    scelta = { pagina: elemento.dataset.pagina || '', quota: zona.height ? Math.min(1, (alto - zona.top) / zona.height) : 0 }
  }
  return scelta
}

/** Riquadri dei blocchi sull'immagine e parti del foglio: lo stesso blocco ha lo stesso id. */
const SUL_FOGLIO = 'data-ocr-blocco'
const SULLA_PAGINA = 'data-blocco'

/**
 * Il blocco in cima alla vista e quanto se n'e' gia' passato.
 *
 * La pagina e il foglio non hanno per forza le stesse proporzioni dentro la
 * pagina (un capoverso corretto si allunga): agganciarsi al blocco tiene
 * accanto le stesse righe anche dove la pagina intera non basterebbe.
 */
function bloccoInCima(contenitore: HTMLElement, attributo: string): { id: string; quota: number } | null {
  const alto = contenitore.getBoundingClientRect().top
  let scelta: { id: string; quota: number; distanza: number } | null = null
  for (const elemento of contenitore.querySelectorAll<Element>(`[${attributo}]`)) {
    const zona = elemento.getBoundingClientRect()
    if (zona.bottom <= alto + 1 || zona.height <= 0) continue
    // il primo che attraversa la cima, altrimenti il piu' vicino sotto
    const distanza = Math.max(0, zona.top - alto)
    if (!scelta || distanza < scelta.distanza) {
      scelta = { id: elemento.getAttribute(attributo) || '', quota: (alto - zona.top) / zona.height, distanza }
      if (distanza === 0) break
    }
  }
  return scelta && scelta.distanza < 400 ? { id: scelta.id, quota: Math.max(-1, Math.min(1, scelta.quota)) } : null
}

function allineaSulBlocco(sorgente: HTMLElement, destinazione: HTMLElement, daImmagini: boolean): boolean {
  const ancora = bloccoInCima(sorgente, daImmagini ? SULLA_PAGINA : SUL_FOGLIO)
  if (!ancora?.id) return false
  const gemello = destinazione.querySelector(`[${daImmagini ? SUL_FOGLIO : SULLA_PAGINA}="${CSS.escape(ancora.id)}"]`)
  if (!gemello) return false
  const zona = gemello.getBoundingClientRect()
  if (zona.height <= 0) return false
  fermaEco(destinazione, destinazione.scrollTop + zona.top - destinazione.getBoundingClientRect().top + ancora.quota * zona.height)
  return true
}

function allinea(sorgente: HTMLElement, destinazione: HTMLElement, daImmagini: boolean) {
  if (allineaSulBlocco(sorgente, destinazione, daImmagini)) return
  const punto = posizione(sorgente)
  if (!punto) return
  const pagina = destinazione.querySelector<HTMLElement>(`[data-pagina="${punto.pagina}"]`)
  if (!pagina) return
  const zona = pagina.getBoundingClientRect()
  const scarto = zona.top - destinazione.getBoundingClientRect().top + punto.quota * zona.height
  fermaEco(destinazione, destinazione.scrollTop + scarto)
}

export function useScorrimentoAppaiato(riquadro: RefObject<HTMLElement | null>, attivo: boolean) {
  useEffect(() => {
    const radice = riquadro.current
    if (!radice || !attivo) return
    let attesa = 0
    const scorre = (evento: Event) => {
      const sorgente = evento.target
      if (!(sorgente instanceof HTMLElement)) return
      const immagini = sorgente.matches(IMMAGINI)
      if (!immagini && !sorgente.matches(TESTO)) return
      if (sorgente.dataset[ECO]) {
        delete sorgente.dataset[ECO]
        return
      }
      const destinazione = radice.querySelector<HTMLElement>(immagini ? TESTO : IMMAGINI)
      if (!destinazione) return
      cancelAnimationFrame(attesa)
      attesa = requestAnimationFrame(() => allinea(sorgente, destinazione, immagini))
    }
    // Lo scorrimento non risale: lo si ascolta in fase di cattura sul riquadro comune.
    radice.addEventListener('scroll', scorre, true)
    return () => {
      cancelAnimationFrame(attesa)
      radice.removeEventListener('scroll', scorre, true)
    }
  }, [riquadro, attivo])
}
