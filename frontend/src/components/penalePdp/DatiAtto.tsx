import type { SchedaAtto } from './types'

type Props = {
  scheda: SchedaAtto
  dati: Record<string, string>
  procura: boolean
  onDati: (dati: Record<string, string>) => void
  onProcura: (valore: boolean) => void
}

const TESTO_PROCURA: Record<string, string> = {
  spunta: 'Atto comprensivo di procura speciale / procura speciale già presente in atti',
  nomina_o_procura: 'Atto comprensivo di nomina del difensore di fiducia e/o conferimento di procura speciale',
}

/** I dati che la maschera del PDP chiede per quell'atto (pena, tipo di rito, impugnazione, anagrafiche…). */
export function DatiAtto({ scheda, dati, procura, onDati, onProcura }: Props) {
  if (!scheda.campi.length && !scheda.procuraSpeciale) return null
  const cambia = (chiave: string, valore: string) => onDati({ ...dati, [chiave]: valore })
  return (
    <fieldset className="iu-pdp-dati">
      <legend>Dati richiesti dal PDP</legend>
      {scheda.campi.map((c) => (
        <label key={c.chiave}>
          <span>{c.etichetta}{c.obbligatorio ? ' *' : ''}</span>
          {c.tipo === 'scelta' ? (
            <select value={dati[c.chiave] || ''} onChange={(e) => cambia(c.chiave, e.target.value)}>
              <option value="">Scegli</option>
              {c.opzioni.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          ) : c.tipo === 'si_no' ? (
            <select value={dati[c.chiave] || ''} onChange={(e) => cambia(c.chiave, e.target.value)}>
              <option value="">—</option><option value="Sì">Sì</option><option value="No">No</option>
            </select>
          ) : (
            <input
              value={dati[c.chiave] || ''}
              inputMode={c.tipo === 'numero' || c.tipo === 'importo' ? 'decimal' : undefined}
              placeholder={c.tipo === 'anagrafica' ? 'Cognome Nome – codice fiscale' : c.tipo === 'importo' ? '0,00' : ''}
              onChange={(e) => cambia(c.chiave, e.target.value)}
            />
          )}
          {c.nota ? <small>{c.nota}</small> : null}
        </label>
      ))}
      {scheda.procuraSpeciale ? (
        <label className="iu-pdp-spunta">
          <input type="checkbox" checked={procura} onChange={(e) => onProcura(e.target.checked)}/>
          {TESTO_PROCURA[scheda.procuraSpeciale]} — altrimenti allega la procura speciale.
        </label>
      ) : null}
      <small className="iu-pdp-fonte">Fonte: {scheda.fonte}</small>
    </fieldset>
  )
}
