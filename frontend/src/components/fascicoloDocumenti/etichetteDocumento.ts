// Marcatori interni delle bozze (registro dei passi «bozza-passo:<chiave>», Lex, editor, note 127-ter): servono al
// software per ritrovare il documento, all'avvocato non dicono nulla. Nella scheda resta un'etichetta chiara.
// Stessa regola del backend: pct/bozze_passi/modello.py (etichette_visibili).
const TAG_TECNICO_BOZZA = /^(?:bozza(?:-[a-z0-9_]+)*|editor-(?:nuovo|richiesta)|preparazione-[a-z0-9_-]+)(?::.*)?$/i

export const ETICHETTA_BOZZA_SOFTWARE = 'Bozza preparata da IUSENTRA'
export const ETICHETTA_BOZZA = 'Bozza'

export function tagTecnicoBozza(tag: string): boolean {
  return TAG_TECNICO_BOZZA.test(tag.trim())
}

export function etichetteVisibili(tags: string[], bozzaDelSoftware = false): string[] {
  const pieni = tags.map((tag) => tag.trim()).filter(Boolean)
  const visibili = pieni.filter((tag) => !tagTecnicoBozza(tag))
  if (bozzaDelSoftware) visibili.unshift(ETICHETTA_BOZZA_SOFTWARE)
  else if (visibili.length < pieni.length) visibili.unshift(ETICHETTA_BOZZA)
  return Array.from(new Set(visibili))
}
