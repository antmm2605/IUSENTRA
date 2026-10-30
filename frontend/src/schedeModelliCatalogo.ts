export type ModelloNorme = { id: string; compilazione_url?: string; codice: string; titolo: string; materia: string; tipo: string; provenienza: string; schede_normative: string[]; stato_norme: string; numero_riferimenti: number; ricerca: string }
export type FiltriModelli = { testo: string; materia: string; tipo: string; provenienza: string; norme: string }
export const filtriModelliVuoti: FiltriModelli = { testo: '', materia: '', tipo: '', provenienza: '', norme: '' }
export function testoRicercaModello(value: string) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('it-IT').replace(/[_.,;:/()-]+/g, ' ').replace(/\s+/g, ' ').trim()
}
export function indicizzaModelli(rows: ModelloNorme[]) {
  return rows.map(row => ({ row, testo: testoRicercaModello(`${row.codice} ${row.titolo} ${row.materia} ${row.tipo} ${row.provenienza} ${row.ricerca}`) }))
}
export function filtraModelli(index: ReturnType<typeof indicizzaModelli>, filter: FiltriModelli) {
  const query = testoRicercaModello(filter.testo)
  const exactCode = index.some(({ row }) => testoRicercaModello(row.codice) === query)
  const terms = query.split(' ').filter(Boolean)
  return index.filter(({ row, testo }) => (!filter.materia || row.materia === filter.materia)
    && (!filter.tipo || row.tipo === filter.tipo) && (!filter.provenienza || row.provenienza === filter.provenienza)
    && (!filter.norme || row.stato_norme === filter.norme) && (exactCode ? testoRicercaModello(row.codice) === query : terms.every(term => testo.includes(term)))).map(item => item.row)
}
