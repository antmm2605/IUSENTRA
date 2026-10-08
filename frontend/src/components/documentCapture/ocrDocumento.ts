import {
  documentoModificabile, documentoWordDaPdf, riconosciPagina,
  type FormatoDocumento, type PaginaRiconosciuta, type SorgenteOcr,
} from '../../services/documentoOcr'
import type { OcrBlock } from './ocrBlocks'
import { documentoOcrHtml } from './ocrExport'

/** Lettura progressiva unica: due richieste al massimo, pagine sempre ordinate. */
export async function leggiDocumentoOcr(
  sorgente: SorgenteOcr,
  signal: AbortSignal,
  pubblica: (pagine: PaginaRiconosciuta[], totale: number, nome: string) => void,
): Promise<void> {
  if (signal.aborted) return
  const prima = await riconosciPagina(sorgente, 1, signal)
  const lette = new Map<number, PaginaRiconosciuta>([[1, prima.pagina]])
  const aggiorna = () => pubblica([...lette.values()].sort((a, b) => a.numero - b.numero), prima.pagineTotali, prima.nome)
  aggiorna()
  let prossima = 2
  let fallita = false
  const lettore = async () => {
    try {
      while (prossima <= prima.pagineTotali && !signal.aborted && !fallita) {
        const numero = prossima++
        const esito = await riconosciPagina(sorgente, numero, signal)
        lette.set(numero, esito.pagina)
        aggiorna()
      }
    } catch (errore) {
      fallita = true
      throw errore
    }
  }
  // Attendere anche la richiesta già partita prima di liberare la revisione.
  const risultati = await Promise.allSettled(Array.from({ length: Math.min(2, Math.max(0, prima.pagineTotali - 1)) }, lettore))
  const errore = risultati.find((risultato) => risultato.status === 'rejected')
  if (errore?.status === 'rejected') throw errore.reason
}

/** Unica scelta del motore e delle correzioni per ogni destinazione. */
export async function convertiDocumentoOcr({ pagine, totale, blocchi, nome, formato, download, originale }: {
  pagine: PaginaRiconosciuta[]
  totale: number
  blocchi: OcrBlock[]
  nome: string
  formato: FormatoDocumento
  download: boolean
  originale?: () => Promise<Blob>
}): Promise<File> {
  if (formato === 'docx' && originale && pagine.length === totale && pagine.every((pagina) => pagina.origine === 'testo')) {
    return documentoWordDaPdf(await originale(), nome, download, blocchi, pagine.flatMap((pagina) => pagina.blocks))
  }
  return documentoModificabile(documentoOcrHtml(blocchi, pagine), nome, formato, download)
}
