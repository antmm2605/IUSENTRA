export type RiepilogoAnnualeData = {
  ok: true
  anno: number
  regime: 'forfettario' | 'ordinario'
  compensi_incassati: number
  anticipazioni_rimborsate: number
  anticipazioni_per_clienti: number
  spese_deducibili: number
  contributi_previdenziali_versati: number
  imposte_versate: number
  mesi: Array<{ mese: string; incassi: number; pagamenti: number }>
  stima?: Record<string, string | number>
  registro_iva?: { liquidazioni: Array<Record<string, string | number>>; proforma_escluse: number; totale_imponibile: number; totale_iva: number; fatture: number; note: string[] }
  note: string[]
  avvisi: string[]
}

const record = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)
const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.every(x => typeof x === 'string')

/** Rifiuta risposte parziali: un importo assente non equivale a zero. */
export function validateRiepilogoAnnuale(payload: unknown, anno: number): RiepilogoAnnualeData {
  const invalid = () => { throw new Error('Riepilogo incompleto o non valido. Riprova il caricamento.') }
  if (!record(payload) || payload.ok !== true || payload.anno !== anno || !['forfettario', 'ordinario'].includes(String(payload.regime))) return invalid()
  for (const key of ['compensi_incassati', 'anticipazioni_rimborsate', 'anticipazioni_per_clienti', 'spese_deducibili', 'contributi_previdenziali_versati', 'imposte_versate']) {
    if (!finite(payload[key])) return invalid()
  }
  if (!strings(payload.note) || !strings(payload.avvisi) || !Array.isArray(payload.mesi) || payload.mesi.length !== 12 || !payload.mesi.every(m => record(m) && typeof m.mese === 'string' && finite(m.incassi) && finite(m.pagamenti))) return invalid()
  if (payload.stima !== undefined && (!record(payload.stima) || !Object.values(payload.stima).every(v => typeof v === 'string' || finite(v)))) return invalid()
  // I valori usati come importi devono essere numeri, mai stringhe convertite implicitamente.
  if (record(payload.stima)) {
    for (const key of ['reddito_forfettario', 'contributi_dedotti', 'imponibile', 'aliquota', 'imposta_sostitutiva', 'reddito_lavoro_autonomo']) {
      if (key in payload.stima && !finite(payload.stima[key])) return invalid()
    }
  }
  if (payload.regime === 'ordinario' && !record(payload.registro_iva)) return invalid()
  if (payload.registro_iva !== undefined) {
    const iva = payload.registro_iva
    if (!record(iva) || !strings(iva.note) || !Array.isArray(iva.liquidazioni)) return invalid()
    for (const key of ['totale_imponibile', 'totale_iva', 'proforma_escluse', 'fatture']) if (!finite(iva[key])) return invalid()
    if (!iva.liquidazioni.every(l => record(l) && typeof l.periodo === 'string' && finite(l.iva_a_debito) && (!('interessi_1_per_cento' in l) || finite(l.interessi_1_per_cento)))) return invalid()
  }
  return payload as RiepilogoAnnualeData
}

export async function getRiepilogoAnnuale(anno: number, startup: boolean, signal: AbortSignal): Promise<RiepilogoAnnualeData> {
  const response = await fetch(`/api/v1/ui/prima-nota/riepilogo?anno=${anno}${startup ? '&startup=1' : ''}`, { credentials: 'same-origin', signal, headers: { Accept: 'application/json' } })
  if (!response.ok) throw new Error('Riepilogo non disponibile. Riprova il caricamento.')
  return validateRiepilogoAnnuale(await response.json(), anno)
}
