export type MateriaAct = { id: number; key?: string; label: string; title: string; articles: number; category: string; materia?: string; tipo?: string }

// Stesso ordine dichiarato in lex/normativa/materie.py (MATERIE).
export const MATERIE_ORDINE = [
  'Costituzione e fonti', 'Diritto civile', 'Persone e famiglia', 'Procedura civile e ADR',
  'Ordinamento giudiziario e spese di giustizia', 'Diritto e procedura penale', 'Diritto amministrativo e appalti',
  'Lavoro e previdenza', 'Diritto tributario', 'Impresa, crisi e proprietà intellettuale',
  'Banca, finanza e assicurazioni', 'Consumatori', 'Privacy, digitale e comunicazioni',
  'Ambiente, edilizia e beni culturali', 'Circolazione e trasporti', 'Immigrazione', 'Professione forense',
  'Diritto dell’Unione europea', 'Ordinamento militare', 'Altre norme',
]

const tipoOrdine = (tipo = '') => (tipo === 'Codice' ? 0 : tipo === 'Costituzione' ? -1 : 1)

// Gruppi per materia: prima i codici, poi le altre fonti in ordine alfabetico.
export function groupByMateria<T extends MateriaAct>(acts: T[]) {
  const map = new Map<string, T[]>()
  for (const act of acts) {
    const materia = act.materia || 'Altre norme'
    map.set(materia, [...(map.get(materia) || []), act])
  }
  const rank = (m: string) => { const i = MATERIE_ORDINE.indexOf(m); return i < 0 ? MATERIE_ORDINE.length : i }
  return Array.from(map.entries())
    .sort(([a], [b]) => rank(a) - rank(b) || a.localeCompare(b, 'it'))
    .map(([materia, rows]) => ({ materia, acts: rows.sort((a, b) => tipoOrdine(a.tipo) - tipoOrdine(b.tipo) || a.label.localeCompare(b.label, 'it')) }))
}
