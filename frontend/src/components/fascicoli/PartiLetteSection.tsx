import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, Plus, UsersRound } from 'lucide-react'
import { Badge } from '../dashboard'

export type ParteLetta = {
  nome: string
  ruolo: string
  ruoloLabel: string
  codiceFiscale: string
  codiceFiscaleValido: boolean
  difensore: string
  posizione: string
  verifica: string
  certa: boolean
  eIlCliente: boolean
  giaPresente: boolean
  idSoggetto: string
  documenti: number
  citazione: string
  tipoSoggetto: string
}

const RUOLI_SCELTA: Array<[string, string]> = [
  ['assistito', 'Assistito'],
  ['controparte', 'Controparte'],
  ['difensore_controparte', 'Difensore controparte'],
  ['testimone', 'Testimone'],
  ['ctu', 'CTU'],
]

function statoParte(parte: ParteLetta): { tono: 'success' | 'info' | 'warning'; testo: string } {
  if (parte.eIlCliente) return { tono: 'success', testo: 'È il cliente' }
  if (parte.giaPresente) return { tono: 'success', testo: 'Già nel fascicolo' }
  if (parte.certa) return { tono: 'info', testo: 'Entra in automatico' }
  return { tono: 'warning', testo: 'Da confermare' }
}

// Le parti lette nell'epigrafe degli atti del fascicolo. Quelle certe (lato
// riconosciuto dal difensore dello studio o dal cliente, codice fiscale
// valido) entrano da sole nell'anagrafica; le altre si aggiungono qui con il
// ruolo scelto dall'avvocato. Legge /api/v1/ui/fascicoli/<id>/letture/parti.
export function PartiLetteSection({ fascicoloId, active = true, refreshKey = 0 }: { fascicoloId: string; active?: boolean; refreshKey?: number }) {
  const [parti, setParti] = useState<ParteLetta[]>([])
  const [errore, setErrore] = useState('')
  const [ruoli, setRuoli] = useState<Record<string, string>>({})
  const [inCorso, setInCorso] = useState('')

  const load = useCallback(async () => {
    if (!active || !fascicoloId) return
    try {
      const response = await fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/letture/parti`, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } })
      const payload = await response.json()
      if (!payload.ok) throw new Error(payload.errore || 'Parti lette non disponibili.')
      setParti(Array.isArray(payload.parti) ? payload.parti : [])
      setErrore('')
    } catch (requestError) {
      setErrore(requestError instanceof Error ? requestError.message : 'Parti lette non disponibili.')
    }
  }, [active, fascicoloId])

  useEffect(() => { void load() }, [load, refreshKey])

  const aggiungi = useCallback(async (parte: ParteLetta) => {
    const ruolo = ruoli[parte.nome] || (parte.ruolo === 'parte' ? '' : parte.ruolo)
    if (!ruolo) {
      setErrore(`Scegli il ruolo di ${parte.nome} prima di aggiungerla.`)
      return
    }
    setInCorso(parte.nome)
    try {
      const response = await fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/letture/parti`, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: JSON.stringify({ nome: parte.nome, ruolo }) })
      const payload = await response.json()
      if (!payload.ok) throw new Error(payload.errore || 'Parte non aggiunta.')
      setParti(Array.isArray(payload.parti) ? payload.parti : [])
      setErrore('')
    } catch (requestError) {
      setErrore(requestError instanceof Error ? requestError.message : 'Parte non aggiunta.')
    } finally {
      setInCorso('')
    }
  }, [fascicoloId, ruoli])

  if (!parti.length && !errore) return null
  return (
    <div className="iu-fas-letture__parti" aria-label="Parti lette dagli atti">
      <h5><UsersRound size={14}/> Parti lette dagli atti ({parti.length})</h5>
      {errore ? <p className="iu-fas-lettura__state iu-fas-lettura__state--error" role="alert"><AlertTriangle size={15}/> {errore}</p> : null}
      <ul>
        {parti.map((parte) => {
          const stato = statoParte(parte)
          const aggiungibile = !parte.eIlCliente && !parte.giaPresente
          return (
            <li key={`${parte.ruolo}-${parte.nome}`} className={`is-${stato.tono}`}>
              <div className="iu-fas-letture__parte-testo">
                <Badge tone={stato.tono}>{stato.testo}</Badge>
                <b>{parte.nome}</b>
                <span>{parte.ruoloLabel}{parte.posizione ? ` · ${parte.posizione}` : ''}</span>
                <small>
                  {parte.codiceFiscale ? `C.F. ${parte.codiceFiscale}${parte.codiceFiscaleValido ? '' : ' (controllo non valido)'}` : 'Codice fiscale non indicato'}
                  {parte.difensore ? ` · difesa da ${parte.difensore}` : ''}
                  {` · in ${parte.documenti} document${parte.documenti === 1 ? 'o' : 'i'}`}
                </small>
                {parte.citazione ? <small className="iu-fas-letture__parte-citazione">«{parte.citazione}»</small> : null}
              </div>
              {aggiungibile ? (
                <div className="iu-fas-letture__anomalia-azioni">
                  <select aria-label={`Ruolo di ${parte.nome}`} value={ruoli[parte.nome] || (parte.ruolo === 'parte' ? '' : parte.ruolo)} onChange={(event) => setRuoli((correnti) => ({ ...correnti, [parte.nome]: event.target.value }))}>
                    <option value="">Scegli il ruolo</option>
                    {RUOLI_SCELTA.map(([valore, etichetta]) => <option key={valore} value={valore}>{etichetta}</option>)}
                  </select>
                  <button type="button" disabled={inCorso === parte.nome} onClick={() => void aggiungi(parte)}><Plus size={13}/> {inCorso === parte.nome ? 'Aggiungo…' : 'Aggiungi al fascicolo'}</button>
                </div>
              ) : null}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export default PartiLetteSection
