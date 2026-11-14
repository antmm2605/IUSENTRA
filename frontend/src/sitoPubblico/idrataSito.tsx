import { hydrateRoot } from 'react-dom/client'
import { SitoPubblico } from './SitoPubblico'
import type { DatiPaginaSito } from './tipi'
import './SitoPubblico.css'

/**
 * Idratazione nel browser dell'HTML pre-generato. I dati arrivano dallo script JSON non eseguibile
 * #sito-pubblico-dati (stessi dati usati sul server). Dopo l'idratazione si caricano i comportamenti
 * esistenti (menu laterale, avviso cookie, caroselli e FAQ di Bootstrap), che agiscono solo sul DOM.
 */
const SCRIPT_DOPO_IDRATAZIONE = [
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js',
  '/static/js/studio_site_public.js',
]

function caricaInOrdine(indirizzi: string[], versione: string) {
  const [primo, ...resto] = indirizzi
  if (!primo) return
  const script = document.createElement('script')
  script.src = primo.startsWith('/') ? `${primo}?v=${encodeURIComponent(versione)}` : primo
  script.onload = () => caricaInOrdine(resto, versione)
  document.body.appendChild(script)
}

export function idrataSito(radice: HTMLElement, onErrore?: (errore: unknown) => void) {
  const sorgente = document.getElementById('sito-pubblico-dati')
  const dati = JSON.parse(sorgente?.textContent || '{}') as DatiPaginaSito
  hydrateRoot(radice, <SitoPubblico dati={dati}/>, {
    onRecoverableError: (errore) => { onErrore?.(errore); console.warn('Sito pubblico: idratazione con differenze', errore) },
  })
  caricaInOrdine(SCRIPT_DOPO_IDRATAZIONE, radice.dataset.versione || '')
}
