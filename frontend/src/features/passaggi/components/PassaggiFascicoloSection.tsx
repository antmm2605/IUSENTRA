import { useCallback, useEffect, useMemo, useState } from 'react'
import { Route } from 'lucide-react'
import { leggiPassaggi } from '../api'
import type { Passaggio } from '../types'
import { CorreggiRegolaDialog } from './CorreggiRegolaDialog'
import { PassaggioCard } from './PassaggioCard'
import '../passaggi.css'

// «Come ha lavorato il software»: le azioni automatiche sul fascicolo come
// sequenza di passaggi, raggruppati per chi li ha prodotti (presidio PEC,
// decreto 127-ter…). Ogni passaggio si può correggere: la correzione diventa
// una regola dello studio. Dati da /api/v1/ui/fascicoli/<id>/passaggi.
export function PassaggiFascicoloSection({ fascicoloId, active = true }: { fascicoloId: string; active?: boolean }) {
  const [passaggi, setPassaggi] = useState<Passaggio[]>([])
  const [errore, setErrore] = useState('')
  const [caricato, setCaricato] = useState(false)
  const [daCorreggere, setDaCorreggere] = useState<Passaggio | null>(null)

  const carica = useCallback(async (signal?: AbortSignal) => {
    try {
      const risposta = await leggiPassaggi(fascicoloId, signal)
      setPassaggi(risposta.ok ? risposta.passaggi : [])
      setErrore(risposta.ok ? '' : risposta.errore || 'Passaggi del software non disponibili.')
      setCaricato(true)
    } catch (eccezione) {
      if (!(eccezione instanceof DOMException && eccezione.name === 'AbortError')) setErrore('Passaggi del software non disponibili.')
    }
  }, [fascicoloId])

  useEffect(() => {
    if (!active) return undefined
    const controllo = new AbortController()
    void carica(controllo.signal)
    return () => controllo.abort()
  }, [active, carica])

  const gruppi = useMemo(() => {
    const mappa = new Map<string, Passaggio[]>()
    for (const passaggio of passaggi) mappa.set(passaggio.produttore, [...(mappa.get(passaggio.produttore) || []), passaggio])
    return [...mappa.entries()]
  }, [passaggi])

  if (caricato && !passaggi.length && !errore) return null

  return (
    <section className="iu-passaggi" aria-label="Come ha lavorato il software">
      <div className="iu-passaggi__testa">
        <h4><Route size={16} /> Come ha lavorato il software</h4>
        <span>{passaggi.length ? `${passaggi.length} passaggi, ognuno con la sua regola e la sua norma` : 'caricamento…'}</span>
      </div>
      <p className="iu-passaggi__nota">Se una regola o un passaggio è sbagliato, correggilo: diventa una regola dello studio e il software la applica ai casi simili, senza mai superare i vincoli di legge.</p>
      {errore ? <p className="iu-passaggi__nota" role="alert">{errore}</p> : null}
      {gruppi.map(([produttore, voci]) => (
        <div className="iu-passaggi__gruppo" key={produttore}>
          <h5>{produttore[0]?.toUpperCase()}{produttore.slice(1)}</h5>
          <ol className="iu-passaggi__lista">
            {voci.map((passaggio) => <PassaggioCard key={passaggio.chiave} passaggio={passaggio} onCorreggi={setDaCorreggere} />)}
          </ol>
        </div>
      ))}
      <CorreggiRegolaDialog fascicoloId={fascicoloId} passaggio={daCorreggere} onClose={() => setDaCorreggere(null)} onSalvata={() => void carica()} />
    </section>
  )
}
