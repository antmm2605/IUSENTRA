import { useEffect, useState } from 'react'
import { ExternalLink, Inbox } from 'lucide-react'
import { penaleApi } from './penaleApi'

type Stato = Awaited<ReturnType<typeof penaleApi.casella>>

/**
 * Capienza della PEC: con la casella piena la notifica penale si perfeziona in cancelleria
 * (art. 16 co. 6 D.L. 179/2012) e sul PST resta solo l'avviso (art. 20 D.M. 44/2011).
 */
export function CasellaPec() {
  const [stato, setStato] = useState<Stato | null>(null)
  useEffect(() => {
    let attivo = true
    penaleApi.casella().then((s) => { if (attivo) setStato(s) }).catch(() => undefined)
    return () => { attivo = false }
  }, [])
  if (!stato || !stato.configurata) return null
  if (!stato.supportata) {
    return (
      <p className="iu-pdp-casella">
        <Inbox size={15}/> Capienza PEC non misurabile{stato.messaggio ? `: ${stato.messaggio}` : ' (il server non la espone)'}.
        <a href={stato.avvisiPst} target="_blank" rel="noreferrer"><ExternalLink size={13}/> Controlla gli avvisi in cancelleria</a>
      </p>
    )
  }
  const percentuale = stato.percentuale ?? 0
  return (
    <div className={`iu-pdp-casella iu-pdp-casella--${stato.livello}`}>
      <Inbox size={15}/>
      <label>
        Casella PEC usata al {percentuale.toFixed(0)}%
        <meter min={0} max={100} low={80} high={95} optimum={20} value={percentuale}>{percentuale.toFixed(0)}%</meter>
      </label>
      {stato.livello !== 'ok' ? (
        <span>Con la casella piena le notifiche penali si perfezionano in cancelleria senza arrivarti: libera spazio.</span>
      ) : null}
      <a href={stato.avvisiPst} target="_blank" rel="noreferrer"><ExternalLink size={13}/> Avvisi in cancelleria</a>
    </div>
  )
}
