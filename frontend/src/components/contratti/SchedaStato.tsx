import { ETICHETTE_STATO, dataOraItaliana, type Pratica, type Valutazione } from '../../contrattiData'

const CAMPI_SCHEDA: [string, string][] = [
  ['funzione', 'Funzione dell’operazione'], ['qualificazione', 'Qualificazione'], ['parti', 'Parti ammesse'],
  ['normativa', 'Normativa'], ['forma', 'Forma'], ['contenuti_obbligatori', 'Contenuti obbligatori'],
  ['clausole_negoziabili', 'Clausole negoziabili'], ['documentazione', 'Documentazione'], ['adempimenti', 'Adempimenti successivi'],
  ['esecuzione', 'Esecuzione e cessazione'], ['controllo_professionale', 'Controllo professionale'], ['versione', 'Versione'],
]

function valoreScheda(valore: unknown): string {
  if (Array.isArray(valore)) return valore.length ? valore.map((voce) => String(voce).trim().replace(/[.;]+$/, '')).join('; ') : '—'
  if (valore && typeof valore === 'object') {
    const v = valore as Record<string, unknown>
    if (v.verifica_normativa) return `Verifica normativa del ${String(v.verifica_normativa).split('-').reverse().join('/')} — da verificare sulla fonte ufficiale`
    return Object.values(v).map(String).join(' · ')
  }
  return valore === undefined || valore === null || valore === '' ? '—' : String(valore).replace(/_/g, ' ')
}

export function SchedaStato({ pratica, valutazione, testi, onTesto }: {
  pratica: Pratica
  valutazione: Valutazione | null
  testi: Record<string, string>
  onTesto: (chiave: string, valore: string) => void
}) {
  const scheda = valutazione?.scheda || {}
  return (
    <div className="iu-ctr-sezione">
      <fieldset className="iu-ctr-form iu-ctr-campi">
        <legend>Elementi della scheda da indicare</legend>
        {(['funzione', 'parti', 'documentazione', 'esecuzione'] as const).map((chiave) => (
          <label key={chiave} className="is-largo">
            <span>{CAMPI_SCHEDA.find(([c]) => c === chiave)?.[1]}</span>
            <textarea rows={2} value={testi[chiave] || ''} onChange={(evento) => { const v = evento.currentTarget.value; onTesto(chiave, v) }} />
          </label>
        ))}
      </fieldset>
      <table className="iu-ctr-tabella iu-ctr-scheda">
        <caption>Scheda di controllo</caption>
        <tbody>
          {CAMPI_SCHEDA.map(([chiave, etichetta]) => (
            <tr key={chiave}><th scope="row">{etichetta}</th><td>{valoreScheda(testi[chiave] || scheda[chiave])}</td></tr>
          ))}
        </tbody>
      </table>
      <div className="iu-ctr-parti">
        <section>
          <h4>Documenti salvati nel fascicolo</h4>
          {pratica.documenti?.length ? (
            <ul className="iu-ctr-elenco">{pratica.documenti.map((d) => <li key={`${d.documento_id}-${d.il}`}>{d.nome} — {ETICHETTE_STATO[d.stato] || d.stato}, {dataOraItaliana(d.il)}</li>)}</ul>
          ) : <p className="iu-ctr-nota">Nessun documento ancora salvato nel fascicolo.</p>}
        </section>
        <section>
          <h4>Storico delle versioni</h4>
          {pratica.storico?.length ? (
            <ul className="iu-ctr-elenco">{pratica.storico.slice(0, 10).map((s, i) => <li key={`${s.il}-${i}`}>{dataOraItaliana(s.il)}{s.autore ? ` · ${s.autore}` : ''}</li>)}</ul>
          ) : <p className="iu-ctr-nota">Nessuna versione precedente.</p>}
        </section>
      </div>
    </div>
  )
}
