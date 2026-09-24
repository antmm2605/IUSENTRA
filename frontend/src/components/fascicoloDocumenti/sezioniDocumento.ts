/**
 * Le sezioni dei documenti del fascicolo.
 *
 * Una sola tassonomia per tutto il fascicolo: quella del catalogo documentale
 * (pct/document_intelligence, sezioni ammesse dalla correzione manuale). La
 * usano il catalogo, i filtri dell'elenco, la correzione e la lettura del
 * fascicolo: un contratto e' «Contratti» ovunque, non «Allegati» in un punto e
 * «Contratti e incarichi» in un altro.
 */
export type SezioneDocumento = {
  id: string
  label: string
}

export const SEZIONI_DOCUMENTO: readonly SezioneDocumento[] = [
  { id: 'atti', label: 'Atti e memorie' },
  { id: 'provvedimenti', label: 'Provvedimenti' },
  { id: 'procure', label: 'Procure' },
  { id: 'notifiche', label: 'Notifiche' },
  { id: 'comunicazioni', label: 'Comunicazioni' },
  { id: 'contratti', label: 'Contratti' },
  { id: 'pagamenti', label: 'Pagamenti' },
  { id: 'identita', label: 'Documenti d’identità' },
  { id: 'allegati', label: 'Allegati' },
  { id: 'da-verificare', label: 'Senza sezione' },
]

export const ID_SEZIONI_DOCUMENTO: ReadonlySet<string> = new Set(SEZIONI_DOCUMENTO.map((sezione) => sezione.id))

export function etichettaSezione(id: string): string {
  return SEZIONI_DOCUMENTO.find((sezione) => sezione.id === id)?.label || ''
}
