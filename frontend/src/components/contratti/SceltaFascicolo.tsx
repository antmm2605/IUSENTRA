import { useEffect, useState } from 'react'
import { getFascicoli, type FascicoloScelta } from '../../contrattiData'

export function SceltaFascicolo({ valore, onChange }: { valore: string; onChange: (id: string, fascicolo?: FascicoloScelta) => void }) {
  const [ricerca, setRicerca] = useState('')
  const [elenco, setElenco] = useState<FascicoloScelta[]>([])

  useEffect(() => {
    let attivo = true
    const timer = window.setTimeout(() => {
      getFascicoli(ricerca.trim()).then((dati) => { if (attivo) setElenco(dati.ok ? dati.fascicoli : []) })
    }, 250)
    return () => { attivo = false; window.clearTimeout(timer) }
  }, [ricerca])

  const selezionato = elenco.find((voce) => voce.id === valore)
  return (
    <div className="iu-ctr-fascicolo">
      <label>
        <span>Cerca fascicolo</span>
        <input type="search" value={ricerca} placeholder="Numero, titolo o cliente" onChange={(evento) => { const testo = evento.currentTarget.value; setRicerca(testo) }} />
      </label>
      <label>
        <span>Fascicolo collegato</span>
        <select value={valore} onChange={(evento) => { const id = evento.currentTarget.value; onChange(id, elenco.find((voce) => voce.id === id)) }}>
          <option value="">Nessun fascicolo</option>
          {valore && !selezionato ? <option value={valore}>Fascicolo {valore}</option> : null}
          {elenco.map((voce) => <option key={voce.id} value={voce.id}>{voce.numero} · {voce.titolo}{voce.cliente ? ` (${voce.cliente})` : ''}</option>)}
        </select>
      </label>
    </div>
  )
}
