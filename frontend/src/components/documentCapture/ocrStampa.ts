/**
 * Stampa del documento dalla revisione: l'originale o quello modificato.
 *
 * Si stampa sempre un PDF, cosi' la pagina stampata e' quella del documento
 * e non la schermata dell'applicazione. L'originale e' il PDF nativo del
 * fascicolo (o il file caricato): e' l'atto che fa fede. Il modificato e' il
 * testo corretto in revisione, impaginato dal server come per il salvataggio.
 */
import type { SorgenteOcr } from '../../services/documentoOcr'

async function comincia(blob: Blob, lunghezza = 5): Promise<string> {
  const testa = await blob.slice(0, lunghezza).arrayBuffer()
  return String.fromCharCode(...new Uint8Array(testa))
}

/** E' davvero un PDF: lo dicono i primi byte, non il nome o il tipo dichiarato. */
export async function eUnPdf(blob: Blob): Promise<boolean> {
  return (await comincia(blob)) === '%PDF-'
}

/**
 * Il PDF nativo del documento letto. Per un documento del fascicolo e' quello
 * dell'anteprima (per un .p7m, il PDF firmato estratto); per un file caricato
 * e' il file stesso. Se l'originale non e' un PDF (un'immagine, una
 * scansione) si ripiega sulle pagine lette, che ne sono la copia per immagine.
 */
export async function pdfOriginale(sorgente: SorgenteOcr | null, ripiego: () => Promise<Blob>): Promise<Blob> {
  if (sorgente?.tipo === 'file' && (await eUnPdf(sorgente.file))) return sorgente.file
  if (sorgente?.tipo === 'fascicolo') {
    const indirizzo = `/fascicoli/${encodeURIComponent(sorgente.fascicoloId)}/documenti/${encodeURIComponent(sorgente.documentoId)}/visualizza`
    const risposta = await fetch(indirizzo, { credentials: 'same-origin' }).catch(() => null)
    const blob = risposta?.ok ? await risposta.blob() : null
    if (blob && (await eUnPdf(blob))) return new Blob([blob], { type: 'application/pdf' })
  }
  return ripiego()
}

/**
 * Apre la finestra di stampa del browser sul PDF, senza lasciare la pagina.
 * Se il browser non stampa da una cornice, il PDF si apre in una scheda
 * nuova da cui stamparlo.
 */
export function stampaPdf(blob: Blob): void {
  const indirizzo = URL.createObjectURL(new Blob([blob], { type: 'application/pdf' }))
  const cornice = document.createElement('iframe')
  cornice.className = 'iu-ocr-stampa'
  cornice.title = 'Documento da stampare'
  const pulisci = () => {
    cornice.remove()
    URL.revokeObjectURL(indirizzo)
  }
  cornice.addEventListener('load', () => {
    try {
      cornice.contentWindow?.focus()
      cornice.contentWindow?.print()
    } catch {
      window.open(indirizzo, '_blank', 'noopener')
    }
    // la finestra di stampa legge il PDF finche' e' aperta: si pulisce dopo
    window.setTimeout(pulisci, 120_000)
  }, { once: true })
  cornice.src = indirizzo
  document.body.appendChild(cornice)
}
