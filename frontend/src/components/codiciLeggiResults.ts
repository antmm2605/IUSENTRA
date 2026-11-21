// Canonical IDs from an older imported edition apply only to their own live response.
// Comparing previously displayed results with a newly selected code would undo the selection.
export function applyCatalogueResponse<T extends { act_id?: number }>(
  signal: Pick<AbortSignal, 'aborted'>,
  requestedAct: string,
  result: T,
  setResult: (result: T) => void,
  setCanonicalAct: (act: string) => void,
) {
  if (signal.aborted) return
  setResult(result)
  if (result.act_id && requestedAct && requestedAct !== String(result.act_id)) {
    setCanonicalAct(String(result.act_id))
  }
}

type Conteggio = { total: number; total_oltre?: boolean }

// Durante il caricamento del catalogo il conteggio non è ancora noto: mai «0 articoli trovati».
export function articoliTrovati(busy: boolean, catalogueBusy: boolean, results: Conteggio) {
  if (busy) return 'Ricerca in corso…'
  if (catalogueBusy && !results.total) return 'Caricamento del catalogo normativo…'
  if (results.total_oltre) return `Più di ${results.total.toLocaleString('it-IT')} articoli trovati: restringi la ricerca`
  return `${results.total.toLocaleString('it-IT')} ${results.total === 1 ? 'articolo trovato' : 'articoli trovati'}`
}
