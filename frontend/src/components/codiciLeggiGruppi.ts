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
    const rows = map.get(materia)
    if (rows) rows.push(act)
    else map.set(materia, [act])
  }
  const rank = (m: string) => { const i = MATERIE_ORDINE.indexOf(m); return i < 0 ? MATERIE_ORDINE.length : i }
  return Array.from(map.entries())
    .sort(([a], [b]) => rank(a) - rank(b) || a.localeCompare(b, 'it'))
    .map(([materia, rows]) => ({ materia, acts: rows.sort((a, b) => tipoOrdine(a.tipo) - tipoOrdine(b.tipo) || a.label.localeCompare(b.label, 'it')) }))
}

// Pagina solo la presentazione; tutti gli atti restano ricercabili nei gruppi.
export function paginaMaterie<T extends MateriaAct>(groups: { materia: string; acts: T[] }[], requestedPage: number, pageSize = 48) {
  const size = Math.max(1, Math.min(96, Math.trunc(pageSize) || 48))
  const total = groups.reduce((n, group) => n + group.acts.length, 0)
  const pages = Math.max(1, Math.ceil(total / size))
  const page = Math.min(pages - 1, Math.max(0, Number.isFinite(requestedPage) ? Math.trunc(requestedPage) : 0))
  const start = page * size
  let offset = 0
  const visible = groups.flatMap(group => {
    const begin = Math.max(0, start - offset)
    const end = Math.min(group.acts.length, start + size - offset)
    offset += group.acts.length
    return end > begin ? [{ materia: group.materia, acts: group.acts.slice(begin, end) }] : []
  })
  return { groups: visible, page, pages, total, start: total ? start + 1 : 0, end: Math.min(total, start + size) }
}
