import { useEffect, useState } from 'react'
import { Download, Smartphone } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { appInstallata, ascoltaInstallazione, dispositivoApple, installaApp, installazioneDisponibile } from '@/lib/appInstallabile'

/** Installazione dell'app su telefono, tablet e computer (PWA), con le istruzioni per iPhone e iPad. */
export function InstallaAppSezione() {
  const [, aggiorna] = useState(0)
  const [esito, setEsito] = useState('')
  useEffect(() => ascoltaInstallazione(() => aggiorna((n) => n + 1)), [])
  const installata = appInstallata()
  const disponibile = installazioneDisponibile()

  const installa = async () => {
    const risultato = await installaApp()
    setEsito(risultato === 'accepted' ? 'IUSENTRA è stata installata: la trovi fra le app del dispositivo.' : risultato === 'dismissed' ? 'Installazione annullata.' : 'Il browser non consente l\'installazione da qui.')
  }

  return (
    <div className="iu-notify-install" aria-label="Installa IUSENTRA">
      <p>
        <b><Smartphone aria-hidden="true" size={15}/> App IUSENTRA</b>
        <span>
          {installata
            ? 'Stai usando l\'app installata su questo dispositivo.'
            : dispositivoApple()
              ? 'Su iPhone e iPad apri IUSENTRA con Safari, tocca Condividi e poi «Aggiungi alla schermata Home»: l\'icona apre l\'app a schermo intero e abilita le notifiche.'
              : disponibile
                ? 'Installa IUSENTRA come app: si apre dalla schermata Home o dal menu Start, a schermo intero, con le notifiche.'
                : 'Dal menu del browser scegli «Installa app» o «Aggiungi a schermata Home» per avere IUSENTRA fra le app del dispositivo.'}
        </span>
      </p>
      {!installata && disponibile ? (
        <Button type="button" onClick={() => void installa()}><Download data-icon="inline-start"/> Installa IUSENTRA</Button>
      ) : null}
      {esito ? <span role="status">{esito}</span> : null}
    </div>
  )
}
