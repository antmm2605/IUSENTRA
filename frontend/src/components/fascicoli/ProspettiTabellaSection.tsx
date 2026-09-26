import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, Table2 } from 'lucide-react'
import { Badge } from '../dashboard'

type Riga = { voce: string; importo: string; totale: boolean }

export type ProspettoLetto = {
  fattoId: string
  documento: string
  etichetta: string
  totale: string
  righe: Riga[]
  pagina: number
  origine: string
  somma: 'ok' | 'errore' | 'attenzione' | ''
  sommaDettaglio: string
  norma: string
  verificaEtichetta: string
}

const euro = new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' })

function importo(valore: string): string {
  const numero = Number(valore)
  return Number.isFinite(numero) ? euro.format(numero) : valore
}

const SOMMA: Record<string, { testo: string; tono: 'success' | 'danger' | 'warning' }> = {
  ok: { testo: 'I conti tornano', tono: 'success' },
  errore: { testo: 'I conti non tornano', tono: 'danger' },
  attenzione: { testo: 'Senza totale da verificare', tono: 'warning' },
}

// I prospetti a tabella letti nei documenti (nota spese, liquidazione,
// proforma, precetto, interessi): ogni importo resta con la sua voce e i conti
// si rifanno. Doppia rappresentazione: la tabella come struttura, il testo del
// documento com'è. Legge /api/v1/ui/fascicoli/<id>/letture/prospetti.
export function ProspettiTabellaSection({ fascicoloId, active = true, refreshKey = 0 }: { fascicoloId: string; active?: boolean; refreshKey?: number }) {
  const [prospetti, setProspetti] = useState<ProspettoLetto[]>([])
  const [errore, setErrore] = useState('')

  const load = useCallback(async () => {
    if (!active || !fascicoloId) return
    try {
      const response = await fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/letture/prospetti`, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } })
      const payload = await response.json()
      if (!payload.ok) throw new Error(payload.errore || 'Prospetti a tabella non disponibili.')
      setProspetti(Array.isArray(payload.prospetti) ? payload.prospetti : [])
      setErrore('')
    } catch (requestError) {
      setErrore(requestError instanceof Error ? requestError.message : 'Prospetti a tabella non disponibili.')
    }
  }, [active, fascicoloId])

  useEffect(() => { void load() }, [load, refreshKey])

  if (!prospetti.length && !errore) return null
  return (
    <div className="iu-fas-letture__parti iu-fas-letture__prospetti" aria-label="Prospetti a tabella letti nei documenti">
      <h5><Table2 size={14}/> Prospetti a tabella ({prospetti.length})</h5>
      {errore ? <p className="iu-fas-lettura__state iu-fas-lettura__state--error" role="alert"><AlertTriangle size={15}/> {errore}</p> : null}
      <ul>
        {prospetti.map((prospetto) => {
          const somma = SOMMA[prospetto.somma] ?? SOMMA.attenzione
          return (
            <li key={prospetto.fattoId} className={prospetto.somma === 'errore' ? 'is-warning' : ''}>
              <div className="iu-fas-letture__parte-testo">
                <span><Badge tone={somma.tono}>{somma.testo}</Badge> <Badge tone="info">{prospetto.verificaEtichetta}</Badge></span>
                <b>{prospetto.documento}{prospetto.pagina ? ` · pagina ${prospetto.pagina}` : ''}</b>
                <table className="iu-fas-letture__prospetto">
                  <tbody>
                    {prospetto.righe.map((riga, indice) => (
                      <tr key={`${prospetto.fattoId}-${indice}`} className={riga.totale ? 'is-totale' : ''}>
                        <td>{riga.voce}</td>
                        <td>{importo(riga.importo)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <small>{prospetto.sommaDettaglio}</small>
                {prospetto.norma ? <small>Norma: {prospetto.norma}</small> : null}
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export default ProspettiTabellaSection
