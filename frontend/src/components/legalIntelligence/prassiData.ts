// Tipi e parametri della ricerca nella prassi (/api/v1/ui/prassi) e nei testi amministrativi
// (/api/v1/ui/giustizia-amministrativa/testi).
export type PrassiVoce = { id: string; ente: string; tipo: string; numero: string; data: string; oggetto: string; url: string; url_testo: string; brano?: string }
export type SentenzaAmministrativa = { id: string; nome_sede: string; tipo: string; numero: string; anno: number; ricorso: string; oggetto: string; pubblicato_il: string; url: string; brano?: string }

export function prassiQueryString(domanda: string, ente: string): string {
  const params = new URLSearchParams({ q: domanda.trim().slice(0, 200) })
  if (ente && ente !== 'ga') params.set('ente', ente)
  return `?${params.toString()}`
}
