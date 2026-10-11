import { mergeRegistryRefresh } from './features/anagrafiche/mergeRegistryRefresh'
import type { SchedaUdienza } from './components/preparazioneUdienzaTipi'
type Values = Record<string, string | boolean>
type DraftStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>
type StoredDraft = { baseline: Values; values: Values; esitoBaseline: SchedaUdienza['esito']; esito: SchedaUdienza['esito']; outcomeDirty: boolean }
function draftKey(scope: string, id: string) {
  if (!/^[a-f0-9]{64}$/.test(scope) || !/^[A-Za-z0-9_-]{1,150}$/.test(id)) throw new Error('Contesto bozza non valido.')
  return `iusentra.preparazione.draft.v1.${scope}.${id}`
}
function validValues(value: unknown): value is Values {
  return !!value && typeof value === 'object' && !Array.isArray(value) && Object.entries(value).every(([key, item]) =>
    !['__proto__', 'constructor', 'prototype'].includes(key) && (typeof item === 'string' || typeof item === 'boolean'))
}
function validOutcome(value: unknown): value is SchedaUdienza['esito'] {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const v = value as SchedaUdienza['esito']
  return ['valore', 'rinvioData', 'rinvioOra', 'noteVerbale', 'azioni', 'rinvioAgendaHref'].every(key => typeof v[key as keyof typeof v] === 'string')
    && Array.isArray(v.termini) && v.termini.length <= 200 && v.termini.every(term => term && typeof term.descrizione === 'string'
      && typeof term.data === 'string' && typeof term.perentorio === 'boolean' && (term.id_scadenza === undefined || typeof term.id_scadenza === 'string'))
}
export function preservePreparationDraft(storage: DraftStorage, scope: string, baseline: SchedaUdienza, current: SchedaUdienza, outcomeDirty: boolean) {
  const key = draftKey(scope, current.id), values = preparationSnapshot(current), previous = preparationSnapshot(baseline)
  if (!outcomeDirty && JSON.stringify(values) === JSON.stringify(previous)) { storage.removeItem(key); return }
  const value: StoredDraft = { baseline: previous, values, esitoBaseline: baseline.esito, esito: current.esito, outcomeDirty }
  const raw = JSON.stringify(value)
  if (raw.length > 524288) throw new Error('Bozza troppo grande per essere conservata nella finestra.')
  storage.setItem(key, raw)
}
export function restorePreparationDraft(storage: Pick<Storage, 'getItem'>, scope: string, incoming: SchedaUdienza) {
  const raw = storage.getItem(draftKey(scope, incoming.id))
  if (raw === null) return { values: incoming, conflicts: [] as string[], outcomeDirty: false }
  if (raw.length > 524288) throw new Error('Bozza conservata troppo grande: contenuto preservato.')
  const value: unknown = JSON.parse(raw)
  const draft = value as StoredDraft
  if (!value || typeof value !== 'object' || Array.isArray(value) || !validValues(draft.baseline) || !validValues(draft.values)
      || !validOutcome(draft.esitoBaseline) || !validOutcome(draft.esito) || typeof draft.outcomeDirty !== 'boolean') {
    throw new Error('Bozza conservata non recuperabile: contenuto preservato.')
  }
  const local = { ...incoming, campi: { ...Object.fromEntries(Object.keys(incoming.campi).map(key => [key, draft.values[key] ?? incoming.campi[key]])), documento_extra: String(draft.values.documento_extra || '') },
    tipoUdienza: String(draft.values.tipo_udienza ?? incoming.tipoUdienza),
    documenti: incoming.documenti.map(row => ({ ...row, stato: String(draft.values[`documento:${row.indice}`] ?? row.stato) })),
    verifiche: incoming.verifiche.map(row => ({ ...row, fatta: Boolean(draft.values[`verifica:${row.id}`] ?? row.fatta) })) }
  const merged = mergePreparationRefresh(local, draft.baseline, incoming)
  if (draft.outcomeDirty) {
    merged.values.esito = draft.esito; merged.values.completata = false
    if (JSON.stringify(incoming.esito) !== JSON.stringify(draft.esitoBaseline)) merged.conflicts.push('esito')
  }
  return { ...merged, outcomeDirty: draft.outcomeDirty }
}
export const preparationStepFields: Record<number, string[]> = {
  1: ['step1_note'], 3: ['note_preparazione', 'argomenti_principali', 'richieste_giudice', 'eccezioni_da_sollevare'],
  4: ['precheck_firma_ok', 'precheck_docs_pronti', 'precheck_cliente_notificato', 'precheck_trasporto_ok', 'precheck_note'],
}
export function preparationSnapshot(source: SchedaUdienza): Values {
  return { ...source.campi, documento_extra: String(source.campi.documento_extra || ''), tipo_udienza: source.tipoUdienza,
    ...Object.fromEntries(source.documenti.map(row => [`documento:${row.indice}`, row.stato])),
    ...Object.fromEntries(source.verifiche.map(row => [`verifica:${row.id}`, row.fatta])) }
}
export function mergePreparationRefresh(current: SchedaUdienza, previous: Values, incoming: SchedaUdienza) {
  const merged = mergeRegistryRefresh(preparationSnapshot(current), previous, preparationSnapshot(incoming))
  return { conflicts: merged.conflicts, values: { ...incoming,
    campi: { ...Object.fromEntries(Object.keys(incoming.campi).map(key => [key, merged.values[key]])), documento_extra: String(merged.values.documento_extra || '') },
    tipoUdienza: String(merged.values.tipo_udienza),
    documenti: incoming.documenti.map(row => ({ ...row, stato: String(merged.values[`documento:${row.indice}`]) })),
    verifiche: incoming.verifiche.map(row => ({ ...row, fatta: Boolean(merged.values[`verifica:${row.id}`]) })) } }
}
/** Solo i campi inviati diventano baseline della risposta, mai altre bozze. */
export function acknowledgedPreparationValues(previous: Values, action: string, body: Record<string, unknown>): Values {
  if (action === 'passo') return { ...previous, ...(body.campi as Values || {}) }
  if (action === 'documento') return { ...previous, [`documento:${body.indice}`]: String(body.stato) }
  if (action === 'verifica') return { ...previous, [`verifica:${body.id}`]: Boolean(body.fatta) }
  return previous
}

export function applyPreparationDraft(current: SchedaUdienza, action: string, body: Record<string, unknown>): SchedaUdienza {
  if (action === 'esito') return { ...current, completata: false, esito: { ...current.esito,
    valore: String(body.esito || ''), rinvioData: String(body.rinvioData || ''), rinvioOra: String(body.rinvioOra || '09:00'),
    noteVerbale: String(body.noteVerbale || ''), azioni: String(body.azioni || ''),
    termini: Array.isArray(body.termini) ? body.termini as SchedaUdienza['esito']['termini'] : [] } }
  if (action === 'passo') {
    const fields = body.campi as Values || {}
    const { tipo_udienza, ...campi } = fields
    return { ...current, campi: { ...current.campi, ...campi }, tipoUdienza: tipo_udienza === undefined ? current.tipoUdienza : String(tipo_udienza) }
  }
  if (action === 'documento') return { ...current, documenti: current.documenti.map(row => row.indice === body.indice ? { ...row, stato: String(body.stato) } : row) }
  if (action === 'verifica') return { ...current, verifiche: current.verifiche.map(row => row.id === body.id ? { ...row, fatta: Boolean(body.fatta) } : row) }
  return current
}
