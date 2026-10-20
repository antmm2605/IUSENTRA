import { useBusyActivity } from '../ui/useBusyActivity'
import { useCallback, useEffect, useRef, useState } from 'react'
import { messaggiDaAttributo, type MessaggioPagina } from '../pubblicoTokenApi'
import { avviaPagamento, caricaCheckout, caricaEsito, percorsoCheckout, type Provider, type StatoPagamento } from '../pagamentoLinkData'
import { SumUpWidget } from './pagamentoLink/SumUpWidget'
import { Messaggi, VistaCheckout, VistaEsito, VistaGiaPagato, VistaScaduto } from './pagamentoLink/PagamentoViste'
import './PagamentoLinkApp.css'

/**
 * Pagina di pagamento del cliente (`/pagamenti/paga/<token>`). I dati arrivano
 * da `/api/v1/pubblico/pagamenti/<token>`: il server crea il pagamento presso il
 * gestore e restituisce solo l'indirizzo a cui andare (Stripe, PayPal,
 * Satispay), l'identificativo del checkout SumUp o le coordinate del bonifico.
 */

type Radice = { token: string; vista: string; provider: string; studio: string; messaggi: MessaggioPagina[] }

function leggiRadice(): Radice {
  const dataset = document.getElementById('pagamento-react-root')?.dataset ?? {}
  return {
    token: dataset.token || '',
    vista: dataset.vista || 'checkout',
    provider: dataset.provider || '',
    studio: dataset.studio || '',
    messaggi: messaggiDaAttributo(dataset.messaggi),
  }
}

const TITOLI: Record<StatoPagamento['tipo'], string> = {
  caricamento: 'Pagamento',
  checkout: 'Pagamento',
  gia_pagato: 'Già pagato',
  scaduto: 'Link scaduto',
  sumup: 'Pagamento SumUp',
  esito: 'Pagamento',
  errore: 'Pagamento',
}

export default function PagamentoLinkApp() {
  const [radice] = useState(leggiRadice)
  const token = radice.token
  const checkoutHref = useRef(percorsoCheckout(token))
  const [stato, setStato] = useState<StatoPagamento>(() => (radice.vista === 'scaduto' ? { tipo: 'scaduto' } : { tipo: 'caricamento' }))
  const [messaggi, setMessaggi] = useState<MessaggioPagina[]>(radice.messaggi)
  const [inCorso, setInCorso] = useState<Provider | null>(null)
  const [ricarica, setRicarica] = useState(0)
  useBusyActivity(stato.tipo === 'caricamento', 'Caricamento della pagina di pagamento…')
  useBusyActivity(inCorso !== null, 'Preparazione della procedura di pagamento…')

  useEffect(() => {
    if (radice.vista === 'scaduto') return undefined
    const controller = new AbortController()
    const carica = radice.vista === 'esito' && ricarica === 0
      ? caricaEsito(token, radice.provider, controller.signal)
      : caricaCheckout(token, controller.signal)
    carica.then(setStato).catch(() => undefined)
    return () => controller.abort()
  }, [token, radice.vista, radice.provider, ricarica])

  useEffect(() => {
    document.title = `${TITOLI[stato.tipo]} — ${radice.studio}`
  }, [stato.tipo, radice.studio])

  const scegli = useCallback(async (provider: Provider) => {
    setInCorso(provider)
    setMessaggi([])
    const esito = await avviaPagamento(token, provider, stato.tipo === 'checkout' ? stato.dati.paymentRevision : undefined)
    if (esito.tipo === 'redirect') {
      // Pagina del gestore: il pulsante resta occupato finché il browser non cambia pagina.
      window.location.assign(esito.url)
      return
    }
    setInCorso(null)
    if (esito.tipo === 'aggiornato') {
      setStato(await caricaCheckout(token))
      setMessaggi([{categoria:'warning',testo:esito.messaggio}])
    } else if (esito.tipo === 'scaduto') {
      setStato({ tipo: 'scaduto' })
    } else if (esito.tipo === 'sumup') {
      checkoutHref.current = esito.urlEsito.replace(/\/successo(?:\?.*)?$/, '')
      setStato((corrente) => ({
        tipo: 'sumup',
        checkoutId: esito.checkoutId,
        urlEsito: esito.urlEsito,
        importo: corrente.tipo === 'checkout' ? corrente.dati.importo : '',
      }))
    } else if (esito.tipo === 'bonifico') {
      if (esito.urlEsito.replace(/\/successo(?:\?.*)?$/, '') !== percorsoCheckout(token)) {
        window.location.assign(esito.urlEsito)
        return
      }
      if (esito.urlEsito) window.history.pushState({ vista: 'esito' }, '', esito.urlEsito)
      setStato({ tipo: 'esito', dati: esito.esito })
    } else {
      setMessaggi([{ categoria: 'danger', testo: esito.messaggio }])
    }
  }, [token, stato])

  const tornaAlCheckout = useCallback(() => {
    if (checkoutHref.current !== percorsoCheckout(token)) { window.location.assign(checkoutHref.current); return }
    if (window.location.pathname !== percorsoCheckout(token)) window.history.pushState({ vista: 'checkout' }, '', percorsoCheckout(token))
    setStato({ tipo: 'caricamento' })
    setRicarica((valore) => valore + 1)
  }, [token])

  useEffect(() => {
    function indietro() {
      setRicarica((valore) => valore + 1)
    }
    window.addEventListener('popstate', indietro)
    return () => window.removeEventListener('popstate', indietro)
  }, [])

  const studioNome = radice.studio

  return (
    <div className="iu-pgl-app">
      {stato.tipo === 'caricamento' ? (
        <main className="iu-pgl-scheda is-stretta" aria-busy="true" aria-live="polite">
          <div className="iu-pgl-corpo is-centrata">
            <span className="iu-pgl-spinner" aria-hidden="true" />
            <p className="iu-pgl-muted">Caricamento del pagamento in corso…</p>
          </div>
        </main>
      ) : null}
      {stato.tipo === 'checkout' ? (
        <VistaCheckout studioNome={studioNome} dati={stato.dati} messaggi={messaggi} inCorso={inCorso} onScegli={scegli} />
      ) : null}
      {stato.tipo === 'gia_pagato' ? <VistaGiaPagato studioNome={studioNome} dati={stato.dati} /> : null}
      {stato.tipo === 'scaduto' ? <VistaScaduto studioNome={studioNome} /> : null}
      {stato.tipo === 'sumup' ? (
        <SumUpWidget studioNome={studioNome} importo={stato.importo} checkoutId={stato.checkoutId} urlEsito={stato.urlEsito} onIndietro={tornaAlCheckout} />
      ) : null}
      {stato.tipo === 'esito' ? <VistaEsito studioNome={studioNome} dati={stato.dati} /> : null}
      {stato.tipo === 'errore' ? (
        <main className="iu-pgl-scheda is-stretta">
          <div className="iu-pgl-corpo">
            <Messaggi messaggi={[{ categoria: 'danger', testo: stato.messaggio }]} />
          </div>
        </main>
      ) : null}
    </div>
  )
}
