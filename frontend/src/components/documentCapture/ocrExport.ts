/** Esporta le misure della revisione insieme al testo corretto. */
import { blocksToHtml, type OcrBlock } from './ocrBlocks'
import { disposizioniDellaPagina, marginiDellaPagina, pagineDelFoglio } from './ocrPagina'
import type { PaginaRiconosciuta } from '../../services/documentoOcr'
import { aCapoValidi } from './ocrACapo'
import { trattiTra } from './ocrTratti'

export function documentoOcrHtml(blocchi: OcrBlock[], pagine: PaginaRiconosciuta[]): string {
  return pagineDelFoglio(blocchi).map(({ numero, blocchi: foglio }) => {
    const pagina = pagine.find(pagina => pagina.numero === numero)
    const anteprima = pagina?.anteprima
    const geometria = anteprima && anteprima.scala > 0
      ? { numero, larghezza: anteprima.larghezza / anteprima.scala, altezza: anteprima.altezza / anteprima.scala }
      : undefined
    if (!geometria) return blocksToHtml(foglio)
    const margini = marginiDellaPagina(foglio, geometria)
    const misure = pagina?.dimensioniPt || { larghezza: 595.28, altezza: 841.89 }
    const pt = (mm: number, verticale = false) => Math.round(mm * (verticale ? misure.altezza / 297 : misure.larghezza / 210) * 100) / 100
    const disposizioni = disposizioniDellaPagina(foglio, geometria)
    const corpo = foglio.find(blocco => blocco.format.corpo > 0)?.format.corpo || 12
    const contenuto = foglio.map((blocco, indice) => {
      const esportabile = blocco.kind === 'numero_pagina' ? { ...blocco, kind: 'paragrafo' as const } : blocco
      const parsed = new DOMParser().parseFromString(blocksToHtml([esportabile]), 'text/html')
      const elemento = parsed.body.firstElementChild as HTMLElement | null
      if (!elemento) return ''
      if (blocco.box) {
        const [x0, y0, x1, y1] = blocco.box
        elemento.dataset.ocrX = String(Math.round(x0 / geometria.larghezza * misure.larghezza * 100) / 100)
        elemento.dataset.ocrY = String(Math.round(y0 / geometria.altezza * misure.altezza * 100) / 100)
        elemento.dataset.ocrWidth = String(Math.round((x1 - x0) / geometria.larghezza * misure.larghezza * 100) / 100)
        elemento.dataset.ocrHeight = String(Math.round((y1 - y0) / geometria.altezza * misure.altezza * 100) / 100)
        if (!blocco.format.corpo) elemento.dataset.ocrEstimatedFont = 'true'
      }
      const tagli = aCapoValidi(blocco)
      if (tagli.length && (blocco.kind === 'paragrafo' || blocco.kind === 'titolo')) {
        const inizi = [0, ...tagli], fini = [...tagli, blocco.text.length]
        elemento.innerHTML = inizi.map((inizio, riga) => {
          const fine = fini[riga]
          const testo = { ...blocco, text: blocco.text.slice(inizio, fine), tratti: trattiTra(blocco.tratti || [], inizio, fine) }
          return new DOMParser().parseFromString(blocksToHtml([testo]), 'text/html').body.firstElementChild?.innerHTML || ''
        }).join('<br>')
      }
      // La distanza misurata prevale sullo spazio predefinito dell'editor.
      const disposizione = disposizioni[indice]
      for (const campo of ['marginTop', 'marginLeft', 'marginRight', 'textIndent'] as const) {
        const valore = disposizione?.[campo]
        if (typeof valore === 'string' && /^-?[\d.]+mm$/.test(valore)) elemento.style[campo] = `${pt(parseFloat(valore), campo === 'marginTop')}pt`
      }
      elemento.style.marginBottom = '0pt'
      const passo = (disposizione as Record<string, string> | undefined)?.['--iu-ocr-interlinea']
      if (passo && /^[\d.]+mm$/.test(passo) && !blocco.format.interlinea) elemento.style.lineHeight = `${pt(parseFloat(passo), true)}pt`
      // Il font può variare fra capoversi anche in una pagina misurata.
      if (blocco.kind !== 'tabella' && blocco.format.famiglia) {
        const span = parsed.createElement('span')
        span.style.fontFamily = blocco.format.famiglia
        if (blocco.format.corpo) span.style.fontSize = `${blocco.format.corpo}pt`
        while (elemento.firstChild) span.append(elemento.firstChild)
        elemento.append(span)
      }
      return parsed.body.innerHTML
    }).join('')
    return `<section class="iu-doc-pagina" data-larghezza="${misure.larghezza}" data-altezza="${misure.altezza}" data-margine-alto="${pt(margini.alto, true)}" data-margine-destro="${pt(margini.destro)}" data-margine-basso="${pt(margini.basso, true)}" data-margine-sinistro="${pt(margini.sinistro)}" data-allineamento="left" data-interlinea="${corpo * 1.2}" style="font-size:${corpo}pt">${contenuto}</section>`
  }).join('')
}
