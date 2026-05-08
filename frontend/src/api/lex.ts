export type LexContextState = {
  context: string
  sources: Array<{ id: string; label: string; detail?: string }>
  insufficientContext: boolean
}

export function buildLexInsufficientContext(context = 'generale'): LexContextState {
  return {
    context,
    sources: [],
    insufficientContext: true,
  }
}
