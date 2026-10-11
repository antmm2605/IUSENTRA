/** Chiamate JSON della Preparazione udienza (stesso schema di risposta: ok, message, redirect, dati). */
import { apiPostJson } from '../api/client'
export const inviaPreparazione = (url: string, corpo: Record<string, unknown>): Promise<Record<string, unknown>> =>
  apiPostJson(url, corpo, { ok: false, message: 'Connessione interrotta: bozza e comando conservati per il recupero.' },
    { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
