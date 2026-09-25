import { csrfHeader } from '../../api/csrf'
import { apiPostJson, ensureJson } from '../../lib/apiClient'
import type { CatalogoPat, Connessione, DepositoPat, EsitoRiepilogo, QuadroPat } from './types'

const radice = '/api/v1/ui/amministrativo'
const base = (fid: string) => `${radice}/fascicoli/${encodeURIComponent(fid)}`
type Esito<T> = T & { ok: boolean; message?: string }

async function invia<T>(url: string, corpo: unknown): Promise<Esito<T>> {
  const risposta = await apiPostJson<Esito<T>>(url, corpo, { ok: false, message: 'Connessione interrotta: riprova.' } as Esito<T>)
  if (!risposta.ok) throw new Error(risposta.message || 'Operazione non riuscita.')
  return risposta
}

async function carica<T>(url: string, dati: FormData): Promise<Esito<T>> {
  const risposta = await fetch(url, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', ...csrfHeader() }, body: dati })
  const json = await risposta.json().catch(() => ({ ok: false, message: 'Risposta non valida.' })) as Esito<T>
  if (!risposta.ok || !json.ok) throw new Error(json.message || 'Caricamento non riuscito.')
  return json
}

export const patApi = {
  catalogo: (signal?: AbortSignal) => ensureJson<CatalogoPat>(`${radice}/catalogo`, { signal }),
  connessione: (signal?: AbortSignal) => ensureJson<Connessione>(`${radice}/connessione`, { signal }),
  quadro: (fid: string, tipo: string, signal?: AbortSignal) => ensureJson<QuadroPat>(`${base(fid)}?tipo=${encodeURIComponent(tipo)}`, { signal }),
  procedimento: (fid: string, tipo: string, dati: Record<string, unknown>) => invia<QuadroPat>(`${base(fid)}/procedimento?tipo=${tipo}`, dati),
  parte: (fid: string, tipo: string, soggetto: string, ruolo: string) =>
    invia<QuadroPat>(`${base(fid)}/parti/${encodeURIComponent(soggetto)}?tipo=${tipo}`, { ruolo }),
  documento: (fid: string, tipo: string, documento: string, ruolo: string, descrizione: string) =>
    invia<QuadroPat>(`${base(fid)}/documenti/${encodeURIComponent(documento)}?tipo=${tipo}`, { ruolo, descrizione }),
  excel: (fid: string, ruolo: string) => `${base(fid)}/excel-parti/${ruolo}`,
  pacchetto: (fid: string) => `${base(fid)}/pacchetto`,
  riepilogo: (fid: string, file: File, tipo: string) => {
    const dati = new FormData()
    dati.append('file', file, file.name)
    dati.append('tipo', tipo)
    return carica<{ esito: EsitoRiepilogo; deposito: DepositoPat }>(`${base(fid)}/riepilogo`, dati)
  },
  deposito: (fid: string, dati: Record<string, unknown>) => invia<{ deposito: DepositoPat }>(`${base(fid)}/depositi`, dati),
}
