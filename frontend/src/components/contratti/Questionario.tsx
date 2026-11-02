import type { Domanda, Fatti } from '../../contrattiData'

function Risposta({ domanda, valore, onChange }: { domanda: Domanda; valore: Fatti[string] | undefined; onChange: (valore: Fatti[string] | undefined) => void }) {
  if (domanda.tipo === 'scelta') {
    return (
      <select value={valore === undefined ? '' : String(valore)} aria-label={domanda.testo} onChange={(evento) => { const v = evento.currentTarget.value; onChange(v || undefined) }}>
        <option value="">Da indicare</option>
        {domanda.opzioni.map((opzione) => <option key={opzione} value={opzione}>{opzione.replace(/_/g, ' ')}</option>)}
      </select>
    )
  }
  if (domanda.tipo === 'numero') {
    return <input type="number" min={0} step="any" value={valore === undefined ? '' : String(valore)} aria-label={domanda.testo} onChange={(evento) => { const v = evento.currentTarget.value; onChange(v === '' ? undefined : Number(v)) }} />
  }
  return (
    <div className="iu-ctr-sino" role="radiogroup" aria-label={domanda.testo}>
      {([['Sì', true], ['No', false]] as const).map(([etichetta, scelta]) => (
        <button key={etichetta} type="button" role="radio" aria-checked={valore === scelta} className={valore === scelta ? 'is-attivo' : ''} onClick={() => onChange(valore === scelta ? undefined : scelta)}>{etichetta}</button>
      ))}
    </div>
  )
}

export function Questionario({ titolo, domande, fatti, onChange }: { titolo: string; domande: Domanda[]; fatti: Fatti; onChange: (fatti: Fatti) => void }) {
  if (!domande.length) return null
  const risposte = domande.filter((d) => fatti[d.id] !== undefined).length
  return (
    <fieldset className="iu-ctr-questionario">
      <legend>{titolo} <small>{risposte}/{domande.length} risposte</small></legend>
      {domande.map((domanda) => (
        <div key={domanda.id} className={`iu-ctr-domanda${fatti[domanda.id] === undefined ? ' is-aperta' : ''}`}>
          <span>{domanda.testo}</span>
          <Risposta
            domanda={domanda}
            valore={fatti[domanda.id]}
            onChange={(valore) => {
              const nuovi = { ...fatti }
              if (valore === undefined) delete nuovi[domanda.id]
              else nuovi[domanda.id] = valore
              onChange(nuovi)
            }}
          />
        </div>
      ))}
    </fieldset>
  )
}
