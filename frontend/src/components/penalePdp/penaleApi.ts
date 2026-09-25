import { csrfHeader } from '../../api/csrf'
import { apiPostJson, ensureJson } from '../../lib/apiClient'
import type { AccessoAtti, AttoCatalogo, Deposito, FileScelto, PanoramicaPdp, Quadro, SchedaAtto, SchedaPortale } from './types'

const radice = '/api/v1/ui/penale'
const base = (fid: string) => `${radice}/fascicoli/${encodeURIComponent(fid)}`
type Esito<T> = T & { ok: boolean; message?: string }

async function invia<T>(url: string, corpo: unknown, metodo: 'POST' | 'DELETE' = 'POST'): Promise<Esito<T>> {
  const risposta = await apiPostJson<Esito<T>>(url, corpo, { ok: false, message: 'Connessione interrotta: riprova.' } as Esito<T>, { method: metodo })
  if (!risposta.ok) throw new Error(risposta.message || 'Operazione non riuscita.')
  return risposta
}

async function carica<T>(url: string, dati: FormData): Promise<Esito<T>> {
  const risposta = await fetch(url, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', ...csrfHeader() }, body: dati })
  const json = await risposta.json().catch(() => ({ ok: false, message: 'Risposta non valida.' })) as Esito<T>
  if (!risposta.ok || !json.ok) throw new Error(json.message || 'Caricamento non riuscito.')
  return json
}

export const penaleApi = {
  accesso: (fid: string, signal?: AbortSignal) => ensureJson<AccessoAtti>(`${base(fid)}/accesso-atti`, { signal }),
  azioneAccesso: (fid: string, azione: string, dati: FormData = new FormData()) =>
    carica<{ messaggi: Array<{ tono: string; testo: string }> }>(`${base(fid)}/accesso-atti/${azione}`, dati),
  panoramica: (signal?: AbortSignal) => ensureJson<PanoramicaPdp>(`${radice}/panoramica`, { signal }),
  quadro: (fid: string, signal?: AbortSignal) => ensureJson<Quadro>(base(fid), { signal }),
  procedimento: (fid: string, dati: Record<string, unknown>) => invia<Quadro>(`${base(fid)}/procedimento`, dati),
  registro: (fid: string, dati: Record<string, unknown>) => invia<{ registro: unknown }>(`${base(fid)}/registri`, dati),
  eliminaRegistro: (fid: string, id: string) => invia<object>(`${base(fid)}/registri/${id}`, {}, 'DELETE'),
  soggetto: (fid: string, dati: Record<string, unknown>) => invia<{ soggetto: unknown }>(`${base(fid)}/soggetti`, dati),
  eliminaSoggetto: (fid: string, id: string) => invia<object>(`${base(fid)}/soggetti/${id}`, {}, 'DELETE'),
  atti: (fid: string, filtri: Record<string, string>) =>
    ensureJson<{ atti: AttoCatalogo[]; ufficio: string; autorizzato: boolean }>(`${base(fid)}/atti?${new URLSearchParams(filtri)}`),
  scheda: (codice: string, ufficio: string, ruoli: string[]) =>
    ensureJson<{ atto: SchedaAtto; contestuali: Array<{ codice: string; nome: string }> }>(
      `${radice}/atti/${encodeURIComponent(codice)}?${new URLSearchParams({ ufficio, ruoli: ruoli.join(',') })}`),
  prepara: (fid: string, dati: { atto: string; ufficio: string; soggetti: string[]; file: FileScelto[]; dati: Record<string, unknown>; procuraSpeciale: boolean }, id = '') =>
    invia<{ deposito: Deposito; scheda: SchedaPortale }>(`${base(fid)}/depositi${id ? `/${id}` : ''}`, dati),
  dettaglio: (fid: string, id: string) => ensureJson<{ deposito: Deposito; scheda: SchedaPortale }>(`${base(fid)}/depositi/${id}`),
  elimina: (fid: string, id: string) => invia<object>(`${base(fid)}/depositi/${id}`, {}, 'DELETE'),
  stato: (fid: string, id: string, dati: Record<string, string>) => invia<{ deposito: Deposito }>(`${base(fid)}/depositi/${id}/stato`, dati),
  ricevuta: (fid: string, id: string, dati: FormData) => carica<{ deposito: Deposito }>(`${base(fid)}/depositi/${id}/ricevuta`, dati),
  importa: (fid: string, dati: FormData) =>
    carica<{ tipo: string; totale: number; pertinenti: number; ignorate: number; importati: number; aggiornati: number; inAgenda: number }>(`${base(fid)}/import`, dati),
  casella: (forza = false) =>
    ensureJson<{ configurata: boolean; supportata: boolean; percentuale?: number; livello?: string; messaggio?: string; avvisiPst: string }>(
      `${radice}/casella-pec${forza ? '?forza=1' : ''}`),
  caricaDocumento: (fid: string, file: File) => {
    const dati = new FormData()
    dati.append('files', file, file.name)
    dati.append('classificazione_modalita', 'automatica')
    return carica<{ documento_id: string }>(`/fascicoli/${encodeURIComponent(fid)}/documenti/carica`, dati)
  },
}
