import { useEffect, useState } from 'react'
import { ArrowLeft, Lock, TriangleAlert, Wallet } from 'lucide-react'

/**
 * Widget di pagamento SumUp nella pagina React.
 *
 * Il browser riceve solo l'identificativo del checkout creato dal server
 * (`/api/v1/pubblico/pagamenti/<token>/avvia`): la chiave API dello studio non
 * serve al widget e non lascia mai il server. Lo script del gestore si carica
 * dal dominio già ammesso dalla CSP (`https://gateway.sumup.com`).
 */

const SDK_SUMUP = 'https://gateway.sumup.com/gateway/ecom/card/v2/sdk.js'
const ID_WIDGET = 'sumup-widget'

type IstanzaSumUp = { unmount?: () => void }
type SumUpCard = {
  mount: (opzioni: { id: string; checkoutId: string; locale?: string; onResponse: (tipo: string, corpo: unknown) => void }) => IstanzaSumUp | undefined
}

declare global {
  interface Window {
    SumUpCard?: SumUpCard
  }
}

let caricamentoSdk: Promise<SumUpCard> | null = null

function caricaSdk(): Promise<SumUpCard> {
  if (window.SumUpCard) return Promise.resolve(window.SumUpCard)
  if (caricamentoSdk) return caricamentoSdk
  caricamentoSdk = new Promise<SumUpCard>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = SDK_SUMUP
    script.async = true
    script.addEventListener('load', () => (window.SumUpCard ? resolve(window.SumUpCard) : reject(new Error('SDK SumUp non disponibile'))))
    script.addEventListener('error', () => {
      caricamentoSdk = null
      reject(new Error('SDK SumUp non caricato'))
    })
    document.head.appendChild(script)
  })
  return caricamentoSdk
}

type Props = {
  studioNome: string
  importo: string
  checkoutId: string
  urlEsito: string
  onIndietro: () => void
}

export function SumUpWidget({ studioNome, importo, checkoutId, urlEsito, onIndietro }: Props) {
  const [errore, setErrore] = useState('')

  useEffect(() => {
    let attivo = true
    let istanza: IstanzaSumUp | undefined
    caricaSdk()
      .then((sdk) => {
        if (!attivo) return
        istanza = sdk.mount({
          id: ID_WIDGET,
          checkoutId,
          locale: 'it-IT',
          onResponse: (tipo) => {
            if (tipo === 'success' && urlEsito) window.location.assign(urlEsito)
            else if (tipo === 'error') setErrore('Pagamento non riuscito. Riprova o scegli un altro metodo.')
          },
        })
      })
      .catch(() => {
        if (attivo) setErrore('Il modulo di pagamento SumUp non è disponibile. Riprova o scegli un altro metodo.')
      })
    return () => {
      attivo = false
      istanza?.unmount?.()
    }
  }, [checkoutId, urlEsito])

  return (
    <main className="iu-pgl-scheda" aria-labelledby="iu-pgl-sumup-titolo">
      <header className="iu-pgl-testata is-sumup">
        <div className="iu-pgl-riga">
          <Wallet size={24} aria-hidden="true" />
          <div>
            <p className="iu-pgl-studio" id="iu-pgl-sumup-titolo">{studioNome}</p>
            <p className="iu-pgl-importo-medio">{importo}</p>
          </div>
        </div>
      </header>
      <div className="iu-pgl-corpo">
        {errore ? (
          <div className="iu-pgl-avviso is-danger" role="alert"><TriangleAlert size={18} aria-hidden="true" />{errore}</div>
        ) : null}
        {/* Il contenuto del riquadro è gestito dallo script SumUp, non da React. */}
        <div id={ID_WIDGET} className="iu-pgl-widget" aria-label="Modulo di pagamento SumUp" />
        <div className="iu-pgl-centrato">
          <button type="button" className="iu-pgl-btn iu-pgl-btn--contorno" onClick={onIndietro}>
            <ArrowLeft size={16} aria-hidden="true" />Torna indietro
          </button>
        </div>
        <p className="iu-pgl-sicuro"><Lock size={14} aria-hidden="true" />Pagamento sicuro via SumUp</p>
      </div>
    </main>
  )
}
