export type CtuDraftValues = Record<string, string | boolean>
type CtuDraftSource = {
  stato: string; dataDepositoRelazione: string; dataComunicazioneDecreto: string; importoLiquidato: string;
  compensoInput: Record<string, unknown>
}
const defaults: Record<string, string> = {
  posizione: '50', vacazioni: '', termine_giorni: '', aumento_eccezionale: '1', motivazione_aumento: '',
  componenti_collegio: '1', patrocinio: '', spese_documentate: '', spese_viaggio: '', contributo_perc: '4', iva_perc: '22',
}
const text = (value: unknown, fallback = '') => value === undefined || value === null ? fallback : String(value)

/** Riusa il confronto a tre vie delle anagrafiche senza perdere le righe del compenso. */
export function ctuDraftSnapshot(source: CtuDraftSource): CtuDraftValues {
  const saved = source.compensoInput || {}
  const rows = Array.isArray(saved.voci) && saved.voci.length ? saved.voci : [{ codice: '', valore: '', quantita: '1' }]
  return {
    stato: source.stato, dataDepositoRelazione: source.dataDepositoRelazione,
    dataComunicazioneDecreto: source.dataComunicazioneDecreto, importoLiquidato: source.importoLiquidato,
    modalita: text(saved.modalita, 'tabella'),
    voci: JSON.stringify(rows.map((row) => ({ codice: text(row.codice), valore: text(row.valore), quantita: text(row.quantita, '1') }))),
    ...Object.fromEntries(Object.entries(defaults).map(([key, fallback]) => [key, text(saved[key], fallback)])),
    collegio_per_intero: saved.collegio_per_intero === true, ritardo: saved.ritardo === true,
  }
}
