import { renderToString } from 'react-dom/server'
import { SitoPubblico } from './SitoPubblico'
import type { DatiPaginaSito } from './tipi'

/**
 * Pre-generazione delle pagine del sito pubblico, eseguita da Node (binario dell'immagine) in un processo
 * breve lanciato da web/services/sito_pubblico_prerender.py: legge da stdin {"richieste": [DatiPaginaSito]}
 * e scrive su stdout {"html": [string]}, nello stesso ordine. Nessun accesso a rete o file.
 */
type ProcessoNode = {
  stdin: { setEncoding(codifica: string): void; on(evento: string, gestore: (parte?: string) => void): void }
  stdout: { write(testo: string): void }
  exitCode?: number
}

declare const process: ProcessoNode

export function generaPagine(richieste: DatiPaginaSito[]): string[] {
  return richieste.map((dati) => renderToString(<SitoPubblico dati={dati}/>))
}

let ingresso = ''
process.stdin.setEncoding('utf8')
process.stdin.on('data', (parte) => { ingresso += parte || '' })
process.stdin.on('end', () => {
  try {
    const { richieste } = JSON.parse(ingresso) as { richieste: DatiPaginaSito[] }
    process.stdout.write(JSON.stringify({ html: generaPagine(richieste) }))
  } catch (errore) {
    process.stdout.write(JSON.stringify({ errore: errore instanceof Error ? errore.message : String(errore) }))
    process.exitCode = 1
  }
})
