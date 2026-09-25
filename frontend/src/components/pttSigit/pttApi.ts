import { apiPostJson, ensureJson } from '../../lib/apiClient'
import type { CatalogoPtt, Connessione, Controllo, DepositoPtt, QuadroPtt } from './types'

const radice = '/api/v1/ui/tributario'
const base = (fid: string) => `${radice}/fascicoli/${encodeURIComponent(fid)}`
type Esito<T> = T & { ok: boolean; message?: string }

async function invia<T>(url: string, corpo: unknown): Promise<Esito<T>> {
  const risposta = await apiPostJson<Esito<T>>(url, corpo, { ok: false, message: 'Connessione interrotta: riprova.' } as Esito<T>)
  if (!risposta.ok) throw new Error(risposta.message || 'Operazione non riuscita.')
  return risposta
}

export const pttApi = {
  catalogo: (signal?: AbortSignal) => ensureJson<CatalogoPtt>(`${radice}/catalogo`, { signal }),
  connessione: (signal?: AbortSignal) => ensureJson<Connessione>(`${radice}/connessione`, { signal }),
  quadro: (fid: string, tipo: string, signal?: AbortSignal) => ensureJson<QuadroPtt>(`${base(fid)}?tipo=${encodeURIComponent(tipo)}`, { signal }),
  procedimento: (fid: string, tipo: string, dati: Record<string, unknown>) => invia<QuadroPtt>(`${base(fid)}/procedimento?tipo=${tipo}`, dati),
  documento: (fid: string, tipo: string, documento: string, dati: { ruolo: string; tipologia: string; descrizione: string }) =>
    invia<QuadroPtt>(`${base(fid)}/documenti/${encodeURIComponent(documento)}?tipo=${tipo}`, dati),
  controllo: (fid: string) => invia<Controllo>(`${base(fid)}/controllo`, {}),
  pacchetto: (fid: string) => `${base(fid)}/pacchetto`,
  termine: (fid: string, termine: string) => invia<{ gia: boolean; scadenza: string }>(`${base(fid)}/termini/${encodeURIComponent(termine)}`, {}),
  deposito: (fid: string, dati: Record<string, unknown>) => invia<{ deposito: DepositoPtt }>(`${base(fid)}/depositi`, dati),
}
