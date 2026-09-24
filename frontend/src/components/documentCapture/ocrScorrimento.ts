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

function allinea(sorgente: HTMLElement, destinazione: HTMLElement) {
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
      attesa = requestAnimationFrame(() => allinea(sorgente, destinazione))
    }
    // Lo scorrimento non risale: lo si ascolta in fase di cattura sul riquadro comune.
    radice.addEventListener('scroll', scorre, true)
    return () => {
      cancelAnimationFrame(attesa)
      radice.removeEventListener('scroll', scorre, true)
    }
  }, [riquadro, attivo])
}
