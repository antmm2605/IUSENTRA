/**
 * Tiene viva la conversazione del portale senza ricaricare la pagina.
 *
 * Chiede solo la coda a partire da un segnalibro e la unisce a quello che gia'
 * mostra. La coda comprende l'ultimo secondo gia' visto — gli orari si salvano
 * al secondo e due messaggi simultanei non sarebbero distinguibili — quindi
 * l'unione scarta per identificativo cio' che c'e' gia': ripetere e'
 * recuperabile, perdere un messaggio fra avvocato e cliente no.
 *
 * Si ferma quando la scheda non e' in primo piano: un portale aperto e
 * dimenticato non deve tenere occupato il server, e riprende da solo al
 * ritorno. Dopo un errore rallenta invece di insistere.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import {
  identificativoMessaggio,
  segnalibroDa,
  unisciMessaggi as unisci,
  type MessaggioPortale,
} from '../lib/conversazionePortale'

export type { MessaggioPortale } from '../lib/conversazionePortale'
export { unisciMessaggi } from '../lib/conversazionePortale'

type RispostaConversazione = {
  ok?: boolean
  messages?: MessaggioPortale[]
  cursor?: string
}

const INTERVALLO_PREDEFINITO = 5000
const INTERVALLO_MASSIMO = 60000

export function useConversazioneViva(opzioni: {
  attiva: boolean
  iniziali: MessaggioPortale[]
  carica: (segnalibro: string) => Promise<RispostaConversazione>
  intervalloMs?: number
}): MessaggioPortale[] {
  const { attiva, iniziali, carica, intervalloMs = INTERVALLO_PREDEFINITO } = opzioni
  const [messaggi, setMessaggi] = useState<MessaggioPortale[]>(iniziali)
  const segnalibro = useRef('')
  const attesa = useRef(intervalloMs)
  const caricaRef = useRef(carica)
  caricaRef.current = carica

  const firmaIniziali = iniziali.map((messaggio, posizione) => identificativoMessaggio(messaggio, posizione)).join('|')
  useEffect(() => {
    // Il payload della pagina resta la base: quando si ricarica, la
    // conversazione riparte da li' senza perdere quello gia' arrivato in coda.
    setMessaggi((correnti) => unisci(correnti, iniziali))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [firmaIniziali])

  useEffect(() => {
    const ultimo = segnalibroDa(messaggi)
    if (ultimo) segnalibro.current = ultimo
  }, [messaggi])

  const giro = useCallback(async () => {
    if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return
    try {
      const risposta = await caricaRef.current(segnalibro.current)
      if (risposta?.ok === false) {
        attesa.current = Math.min(attesa.current * 2, INTERVALLO_MASSIMO)
        return
      }
      attesa.current = intervalloMs
      const arrivati = Array.isArray(risposta?.messages) ? risposta.messages : []
      if (arrivati.length) setMessaggi((correnti) => unisci(correnti, arrivati))
    } catch {
      attesa.current = Math.min(attesa.current * 2, INTERVALLO_MASSIMO)
    }
  }, [intervalloMs])

  useEffect(() => {
    if (!attiva) return undefined
    let vivo = true
    let timer: ReturnType<typeof setTimeout> | undefined
    const pianifica = () => {
      if (!vivo) return
      timer = setTimeout(async () => {
        await giro()
        pianifica()
      }, attesa.current)
    }
    pianifica()
    const alRitorno = () => {
      if (document.visibilityState === 'visible') void giro()
    }
    document.addEventListener('visibilitychange', alRitorno)
    return () => {
      vivo = false
      if (timer) clearTimeout(timer)
      document.removeEventListener('visibilitychange', alRitorno)
    }
  }, [attiva, giro])

  return messaggi
}
