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
