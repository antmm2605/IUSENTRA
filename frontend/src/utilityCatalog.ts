import type { FunzioneUtility, StrumentoForense } from './strumentiLegaliData'

export type VoceUtility = {
  id: string
  title: string
  subtitle: string
  categoria: string
  strumento?: StrumentoForense
  funzione?: FunzioneUtility
}

export function applicaPrecompilatoUtility(precompilato: Record<string, string>, corrente: Record<string, string>, modificati: ReadonlySet<string>): Record<string, string> {
  const risultato = { ...precompilato }
  for (const nome of modificati) {
    if (nome in risultato && nome in corrente) risultato[nome] = corrente[nome]
  }
  return risultato
}

export function catalogoUtility(strumenti: StrumentoForense[], funzioni: FunzioneUtility[]): VoceUtility[] {
  const voci: VoceUtility[] = strumenti.map(strumento => ({ ...strumento, id: `tool:${strumento.id}`, strumento }))
  for (const funzione of funzioni) {
    // Solo un alias esattamente equivalente è ridondante. Un preset distinto
    // o una destinazione specifica deve restare selezionabile nel catalogo.
    const equivalente = !Object.keys(funzione.preset ?? {}).length && strumenti.some(strumento =>
      strumento.id === funzione.toolId && strumento.title.trim().toLocaleLowerCase('it') === funzione.title.trim().toLocaleLowerCase('it'))
    if (equivalente) continue
    voci.push({ id: `app:${funzione.id}`, title: funzione.title, subtitle: funzione.description, categoria: funzione.section, funzione })
  }
  return voci
}

export function destinazioneUtility(href: string, idFascicolo = ''): string {
  if (!href.startsWith('/') || href.startsWith('//')) return ''
  const url = new URL(href, 'https://iusentra.invalid')
  if (idFascicolo) url.searchParams.set('id_fascicolo', idFascicolo)
  return `${url.pathname}${url.search}${url.hash}`
}
