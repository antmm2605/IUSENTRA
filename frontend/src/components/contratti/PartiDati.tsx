import type { DatiPratica, Parte } from '../../contrattiData'

const CAMPI_PARTE: [keyof Parte, string, string][] = [
  ['nome', 'Nome e cognome o ragione sociale', ''],
  ['codice_fiscale', 'Codice fiscale / Partita IVA', ''],
  ['sede', 'Residenza o sede', 'Via, numero, CAP, Comune'],
  ['pec', 'PEC', 'nome@pec.it'],
  ['rappresentante', 'Legale rappresentante o procuratore', 'Solo per società o firma per procura'],
]

function righe(testo: string): string[] {
  return testo.split('\n')
}

export function PartiDati({ ruoli, campi, dati, onChange }: { ruoli: string[]; campi: { id: string; etichetta: string }[]; dati: DatiPratica; onChange: (dati: DatiPratica) => void }) {
  const parti = ruoli.map((_, indice) => (dati.parti || [])[indice] || {})
  const valori = dati.campi || {}
  const aggiornaParte = (indice: number, chiave: keyof Parte, valore: string) => {
    const nuove = parti.map((p, i) => (i === indice ? { ...p, [chiave]: valore } : p))
    onChange({ ...dati, parti: nuove })
  }
  return (
    <div className="iu-ctr-sezione">
      <div className="iu-ctr-parti">
        {ruoli.map((ruolo, indice) => (
          <fieldset key={ruolo} className="iu-ctr-form">
            <legend>{ruolo}</legend>
            {CAMPI_PARTE.map(([chiave, etichetta, suggerimento]) => (
              <label key={chiave}>
                <span>{etichetta}</span>
                <input type="text" value={parti[indice][chiave] || ''} placeholder={suggerimento} maxLength={300} onChange={(evento) => { const v = evento.currentTarget.value; aggiornaParte(indice, chiave, v) }} />
              </label>
            ))}
          </fieldset>
        ))}
      </div>
      <fieldset className="iu-ctr-form iu-ctr-campi">
        <legend>Elementi del contratto</legend>
        {campi.map((campo) => (
          <label key={campo.id} className={campo.id === 'oggetto' ? 'is-largo' : ''}>
            <span>{campo.etichetta}</span>
            {campo.id === 'oggetto'
              ? <textarea rows={3} value={valori[campo.id] || ''} onChange={(evento) => { const v = evento.currentTarget.value; onChange({ ...dati, campi: { ...valori, [campo.id]: v } }) }} />
              : <input type="text" value={valori[campo.id] || ''} placeholder={campo.id === 'data' || campo.id === 'decorrenza' ? 'gg/mm/aaaa' : ''} onChange={(evento) => { const v = evento.currentTarget.value; onChange({ ...dati, campi: { ...valori, [campo.id]: v } }) }} />}
          </label>
        ))}
      </fieldset>
      <div className="iu-ctr-parti">
        <label className="iu-ctr-form">
          <span>Premesse (una per riga)</span>
          <textarea rows={4} value={(dati.premesse || []).join('\n')} onChange={(evento) => { const v = evento.currentTarget.value; onChange({ ...dati, premesse: righe(v) }) }} />
        </label>
        <label className="iu-ctr-form">
          <span>Allegati (uno per riga)</span>
          <textarea rows={4} value={(dati.allegati || []).join('\n')} onChange={(evento) => { const v = evento.currentTarget.value; onChange({ ...dati, allegati: righe(v) }) }} />
        </label>
      </div>
    </div>
  )
}
