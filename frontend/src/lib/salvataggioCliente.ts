/**
 * Dove andare dopo «Salva modifiche» nella scheda cliente.
 *
 * Il difetto: dopo un salvataggio riuscito si navigava **sempre**, anche in
 * modifica. Chi stava correggendo una scheda si ritrovava buttato fuori dal
 * modulo a ogni salvataggio, e per continuare doveva rientrare.
 *
 * Il comportamento giusto cambia nei tre casi:
 *
 * | Situazione                              | Dopo il salvataggio                |
 * |-----------------------------------------|------------------------------------|
 * | nuovo cliente                           | la cartella del cliente appena nato |
 * | modifica                                | **resta sulla scheda**              |
 * | modifica aperta da un'altra pagina      | torna da dove si e' arrivati        |
 *
 * Il campo nascosto `next_url` era gia' nel modulo, ma nessuno lo leggeva.
 */

/** `edit` quando la pagina e' /clienti/&lt;id&gt;/modifica. */
export type ModoScheda = 'create' | 'edit' | string

export interface ContestoSalvataggio {
  mode: ModoScheda
  /** parametri della pagina: in modifica contiene idCliente */
  query?: { idCliente?: string | null } | null
  /** valore del campo nascosto `next_url` del modulo */
  nextUrl?: string | null
  /** id restituito dal salvataggio: in creazione e' il cliente appena nato */
  idSalvato?: string | null
}

/**
 * Accetta solo percorsi interni.
 *
 * `next_url` arriva dalla barra degli indirizzi. Il server applica gia' la
 * stessa regola (`is_safe_internal_path`), ma il momento in cui l'utente
 * uscirebbe dal gestionale e' subito dopo un salvataggio riuscito — cioe'
 * quando si fida di quello che vede — e un controllo in piu' qui non costa
 * nulla.
 *
 * Respinge: indirizzi assoluti, `//host`, `/\host` e i caratteri di controllo
 * (una tabulazione dopo la barra, in certi browser, trasforma il percorso in
 * `//host`).
 */
export function destinazioneInterna(valore: string | null | undefined): string | null {
  if (!valore) return null
  const pulito = valore.trim()
  if (!pulito.startsWith('/')) return null
  if (pulito.startsWith('//')) return null
  if (pulito.startsWith('/\\')) return null
  for (let i = 0; i < pulito.length; i += 1) {
    const codice = pulito.charCodeAt(i)
    if (codice < 32 || codice === 127) return null
  }
  if (pulito.split('/').some((parte) => parte.trim() === '..')) return null
  return pulito
}

/**
 * Dove mandare l'utente dopo il salvataggio.
 * `null` significa: non navigare, resta dove sei.
 */
export function destinazioneDopoSalvataggio(contesto: ContestoSalvataggio): string | null {
  const richiesta = destinazioneInterna(contesto.nextUrl)
  if (richiesta) return richiesta

  if (contesto.mode === 'edit') return null

  const id = contesto.idSalvato || contesto.query?.idCliente || null
  return id ? `/clienti/${encodeURIComponent(id)}` : '/clienti'
}

/** Il messaggio da mostrare: dice all'avvocato che cosa e' successo davvero. */
export function messaggioSalvataggio(destinazione: string | null, dalServer?: string | null): string {
  if (dalServer) return dalServer
  return destinazione ? 'Cliente salvato.' : 'Modifiche salvate.'
}
