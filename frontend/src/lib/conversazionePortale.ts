/**
 * Unione dei messaggi della conversazione del portale: nessuno si perde.
 *
 * La coda chiesta al server comprende l'ultimo secondo gia' visto, perche' gli
 * orari si salvano con il secondo come unita' minima e due messaggi simultanei
 * non sarebbero distinguibili. Qui si scarta per identificativo cio' che c'e'
 * gia' e si rimette tutto in ordine: ripetere e' recuperabile, perdere un
 * messaggio fra avvocato e cliente no.
 *
 * Logica pura, senza React: la stessa unione vale per la pagina dello studio e
 * per quella del cliente, e si puo' provare da sola.
 */

export type MessaggioPortale = {
  id?: string
  body?: string
  sender_type?: string
  created_at?: string
  created_at_label?: string
  [chiave: string]: unknown
}

/** L'identificativo con cui si riconosce un messaggio gia' mostrato. */
export function identificativoMessaggio(messaggio: MessaggioPortale, posizione: number): string {
  return String(messaggio.id || `${messaggio.created_at || ''}#${posizione}`)
}

/** Dal piu' vecchio al piu' recente; a parita' di istante decide l'identificativo. */
export function ordinaMessaggi(messaggi: MessaggioPortale[]): MessaggioPortale[] {
  return [...messaggi].sort((primo, secondo) => {
    const quandoPrimo = String(primo.created_at || '')
    const quandoSecondo = String(secondo.created_at || '')
    if (quandoPrimo !== quandoSecondo) return quandoPrimo < quandoSecondo ? -1 : 1
    return String(primo.id || '') < String(secondo.id || '') ? -1 : 1
  })
}

/** I messaggi correnti piu' quelli arrivati, senza doppioni e in ordine. */
export function unisciMessaggi(
  correnti: MessaggioPortale[],
  arrivati: MessaggioPortale[],
): MessaggioPortale[] {
  const perIdentificativo = new Map<string, MessaggioPortale>()
  correnti.forEach((messaggio, posizione) =>
    perIdentificativo.set(identificativoMessaggio(messaggio, posizione), messaggio),
  )
  arrivati.forEach((messaggio, posizione) =>
    perIdentificativo.set(identificativoMessaggio(messaggio, posizione), messaggio),
  )
  return ordinaMessaggi([...perIdentificativo.values()])
}

/** Il segnalibro da cui ripartire: l'istante dell'ultimo messaggio mostrato. */
export function segnalibroDa(messaggi: MessaggioPortale[]): string {
  const ultimo = messaggi[messaggi.length - 1]
  return ultimo?.created_at ? String(ultimo.created_at) : ''
}
