import { useState } from 'react'
import { Check, Copy } from 'lucide-react'
import type { SchedaPortale } from './types'

/** I dati da inserire nel PDP, nello stesso ordine delle sue maschere, con la copia a un clic. */
export function SchedaPdp({ scheda, linkPdp }: { scheda: SchedaPortale; linkPdp: string }) {
  const [copiato, setCopiato] = useState('')
  const copia = async (chiave: string, valore: string) => {
    try { await navigator.clipboard.writeText(valore); setCopiato(chiave); window.setTimeout(() => setCopiato(''), 1500) } catch { setCopiato('') }
  }
  return (
    <div className="iu-pdp-scheda">
      <h5>Scheda per il PDP <a href={linkPdp} target="_blank" rel="noreferrer">apri il portale</a></h5>
      {scheda.sezioni.map((sezione) => (
        <section key={sezione.titolo}>
          <h6>{sezione.titolo}</h6>
          <dl>
            {sezione.voci.map((voce, i) => {
              const chiave = `${sezione.titolo}-${i}`
              return (
                <div key={chiave}>
                  <dt>{voce.etichetta}</dt>
                  <dd>
                    <span>{voce.valore || '—'}</span>
                    {voce.nota ? <small>{voce.nota}</small> : null}
                    {voce.valore ? (
                      <button type="button" aria-label={`Copia ${voce.etichetta}`} onClick={() => void copia(chiave, voce.valore)}>
                        {copiato === chiave ? <Check size={13}/> : <Copy size={13}/>}
                      </button>
                    ) : null}
                  </dd>
                </div>
              )
            })}
          </dl>
        </section>
      ))}
      <p className="iu-pdp-nota">{scheda.canale.nota}</p>
    </div>
  )
}
