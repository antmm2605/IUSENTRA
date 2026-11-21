export type ModelloNorme = { id: string; compilazione_url?: string; codice: string; titolo: string; materia: string; tipo: string; provenienza: string; schede_normative: string[]; stato_norme: string; numero_riferimenti: number; ricerca: string; provenienze?: string[] }
export type FiltriModelli = { testo: string; materia: string; tipo: string; provenienza: string; norme: string }
export const filtriModelliVuoti: FiltriModelli = { testo: '', materia: '', tipo: '', provenienza: '', norme: '' }
export function testoRicercaModello(value: string) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('it-IT').replace(/[_.,;:/()-]+/g, ' ').replace(/\s+/g, ' ').trim()
}
/** Stessa materia scritta in due modi dai due cataloghi: un solo nome nel filtro (verifica visiva LEX-08). */
const MATERIE_EQUIVALENTI: Record<string, string> = {
  amministrativo: 'Diritto amministrativo',
  civile: 'Diritto civile',
  penale: 'Diritto penale',
  tributario: 'Diritto tributario',
  'diritto del lavoro': 'Lavoro e previdenza',
  'lavoro e previdenza': 'Lavoro e previdenza',
  'diritto di famiglia': 'Famiglia e persone',
  'famiglia e persone': 'Famiglia e persone',
}
export function materiaCanonica(materia: string) {
  const nome = (materia || '').trim()
  return MATERIE_EQUIVALENTI[nome.toLocaleLowerCase('it-IT')] ?? nome
}
export function indicizzaModelli(rows: ModelloNorme[]) {
  return rows.map(row => ({ row, testo: testoRicercaModello(`${row.codice} ${row.titolo} ${row.materia} ${row.tipo} ${row.provenienza} ${row.ricerca}`) }))
}
export function filtraModelli(index: ReturnType<typeof indicizzaModelli>, filter: FiltriModelli) {
  const query = testoRicercaModello(filter.testo)
  const exactCode = index.some(({ row }) => testoRicercaModello(row.codice) === query)
  const terms = query.split(' ').filter(Boolean)
  return index.filter(({ row, testo }) => (!filter.materia || materiaCanonica(row.materia) === materiaCanonica(filter.materia))
    && (!filter.tipo || row.tipo === filter.tipo) && (!filter.provenienza || row.provenienza === filter.provenienza || Boolean(row.provenienze?.includes(filter.provenienza)))
    && (!filter.norme || row.stato_norme === filter.norme) && (exactCode ? testoRicercaModello(row.codice) === query : terms.every(term => testo.includes(term)))).map(item => item.row)
}

const PRIORITA_PROVENIENZA: Record<string, number> = { 'Archivio dei modelli': 0, 'Compilatore guidato': 1, 'Catalogo professionale': 2 }
/** Lo stesso modello (stesso codice) arriva da più cataloghi: nella ricerca compare una volta sola, con tutte le
 *  provenienze. Si apre la voce dell'archivio dei modelli (il modello vero); il compilatore guidato, se c'è, resta
 *  il percorso di compilazione (collaudo a vista 21/11/2026). */
export function raggruppaPerCodice(rows: ModelloNorme[]): ModelloNorme[] {
  const gruppi = new Map<string, ModelloNorme[]>()
  for (const row of rows) {
    const chiave = (row.codice || row.id).toLocaleUpperCase('it-IT')
    gruppi.set(chiave, [...(gruppi.get(chiave) || []), row])
  }
  return [...gruppi.values()].map(gruppo => {
    const ordinati = [...gruppo].sort((a, b) => (PRIORITA_PROVENIENZA[a.provenienza] ?? 9) - (PRIORITA_PROVENIENZA[b.provenienza] ?? 9))
    const scelto = ordinati.find(row => row.stato_norme === 'associate') || ordinati[0]
    const guidato = ordinati.find(row => row.provenienza === 'Compilatore guidato')
    const provenienze = [...new Set(ordinati.map(row => row.provenienza))]
    return { ...scelto, compilazione_url: guidato?.compilazione_url || scelto.compilazione_url, provenienze, provenienza: provenienze.join(' · '),
      ricerca: ordinati.map(row => row.ricerca).join(' ') }
  })
}
