// Controllo della catena del fascicolo: tipi del payload di /api/v1/ui/fascicoli/<id>/guardiano-catena
// e la frase da mostrare. Il controllo gira in sfondo sul server (pct/catena): qui si legge solo il suo registro.

export type AvvisoCatena = { codice: string; descrizione: string; perche: string; norma: string; dal: string }

export type ControlloCatenaPayload = {
  ok?: boolean
  stato?: 'verificato' | 'in_aggiornamento' | 'mai_controllato' | 'non_disponibile'
  statoEtichetta?: string
  avvisi?: AvvisoCatena[]
}

export function avvisiDaMostrare(payload: ControlloCatenaPayload | null | undefined): AvvisoCatena[] {
  if (!payload?.ok || !Array.isArray(payload.avvisi)) return []
  return payload.avvisi.filter((avviso) => Boolean(avviso?.descrizione))
}

export function primaLettera(testo: string): string {
  return testo ? testo.charAt(0).toUpperCase() + testo.slice(1) : testo
}

export function statoDelControllo(payload: ControlloCatenaPayload | null | undefined): string {
  if (!payload?.ok) return ''
  return payload.stato === 'in_aggiornamento' ? 'Controllo della catena in aggiornamento: i dati del fascicolo sono appena cambiati.' : ''
}
