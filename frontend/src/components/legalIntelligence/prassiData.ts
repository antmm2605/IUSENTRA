// Tipi e parametri della ricerca nella prassi (/api/v1/ui/prassi) e nei testi amministrativi
// (/api/v1/ui/giustizia-amministrativa/testi).
export type PrassiVoce = { id: string; ente: string; tipo: string; numero: string; data: string; oggetto: string; url: string; url_testo: string; brano?: string }
export type SentenzaAmministrativa = { id: string; nome_sede: string; tipo: string; numero: string; anno: number; ricorso: string; oggetto: string; pubblicato_il: string; url: string; brano?: string }

export function prassiQueryString(domanda: string, ente: string): string {
  const params = new URLSearchParams({ q: domanda.trim().slice(0, 200) })
  if (ente && ente !== 'ga') params.set('ente', ente)
  return `?${params.toString()}`
}

// Lettore del testo integrale di una sentenza amministrativa per estremi: se l'archivio non lo ha ancora,
// il server lo scarica subito dal sito ufficiale (al più 15 secondi) e lo conserva.
export function testoSuRichiestaHref(organo: string, numero: string, anno: string): string {
  const params = new URLSearchParams({ organo: organo.trim().slice(0, 120), numero: numero.replace(/\D/g, '').slice(0, 9), anno: anno.replace(/\D/g, '').slice(0, 4) })
  return `/api/v1/ui/giustizia-amministrativa/testo/pagina?${params.toString()}`
}
