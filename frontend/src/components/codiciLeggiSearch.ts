type CatalogueAct = { key?: string; label: string; title: string; materia?: string; tipo?: string }

const aliases: Record<string, string> = {
  codice_privacy: 'privacy protezione dati personali',
  '152/2006': 'ambiente ambientale',
  '36/2023': 'appalti contratti pubblici',
  '50/2016': 'appalti contratti pubblici',
  contratti_163_2006: 'appalti contratti pubblici',
  '82/2005': 'digitale cad amministrazione digitale',
  codice_civile: 'cc c.c.',
  codice_procedura_civile: 'cpc c.p.c.',
  codice_penale: 'cp c.p.',
  codice_procedura_penale: 'cpp c.p.p.',
  codice_processo_amministrativo: 'cpa c.p.a.',
  codice_strada: 'cds c.d.s.',
  codice_consumo: 'consumo consumatori',
  codice_crisi: 'crisi impresa insolvenza ccii',
}

// The catalogue and its code grid share the original accent/apostrophe normalization.
export function normaliseCatalogueText(value: string) {
  return value.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[’‘]/g, "'").toLocaleLowerCase('it')
}

const abbreviations = new Set(['cc', 'c.c.', 'cpc', 'c.p.c.', 'cp', 'c.p.', 'cpp', 'c.p.p.', 'cpa', 'c.p.a.', 'cds', 'c.d.s.', 'cad', 'ccii'])

export function matchesCatalogueAct(act: CatalogueAct, query: string) {
  const term = normaliseCatalogueText(query).trim()
  const synonyms = normaliseCatalogueText(aliases[act.key || ''] || '')
  return normaliseCatalogueText(`${act.label} ${act.title} ${act.materia || ''} ${act.tipo || ''}`).includes(term) || (abbreviations.has(term) ? synonyms.split(' ').includes(term) : synonyms.includes(term))
}
