import { AlertOctagon, CheckCircle2, ClipboardList, Gavel, Info, Landmark } from 'lucide-react'
import { ETICHETTE_FORMA, dataItaliana, type Decisione, type Esito, type Valutazione } from '../../contrattiData'
import { Badge } from '../../ui/Badge'

function Voce({ esito }: { esito: Esito }) {
  return (
    <>
      <span>{esito.messaggio}</span>
      {esito.norma ? <small className="iu-ctr-norma">{esito.norma}</small> : null}
    </>
  )
}

export function Controlli({ valutazione, decisioni, onDecisione }: {
  valutazione: Valutazione | null
  decisioni: Record<string, Decisione>
  onDecisione: (id: string, decisione: Decisione) => void
}) {
  if (!valutazione) return <p className="iu-ctr-nota">Valutazione in corso…</p>
  const v = valutazione
  return (
    <div className="iu-ctr-sezione">
      <div className={`iu-ctr-forma${v.forma.richiede_pubblico_ufficiale ? ' is-notarile' : ''}`}>
        <Landmark size={18} aria-hidden="true" />
        <div>
          <strong>{ETICHETTE_FORMA[v.forma.forma] || v.forma.forma}</strong>
          {v.forma.nota ? <p>{v.forma.nota}</p> : <p>Lo studio può redigere e far sottoscrivere il testo alle parti.</p>}
        </div>
        {v.variante ? <Badge tone="primary">Variante: {v.variante.nome}</Badge> : null}
      </div>

      <section className="iu-ctr-esiti is-blocco" aria-labelledby="titolo-bloccanti">
        <h4 id="titolo-bloccanti"><AlertOctagon size={16} aria-hidden="true" /> Bloccanti ({v.bloccanti.length})</h4>
        {v.bloccanti.length ? <ul>{v.bloccanti.map((e) => <li key={e.id}><Voce esito={e} /></li>)}</ul> : <p className="iu-ctr-nota">Nessun bloccante con le risposte date.</p>}
      </section>

      <section className="iu-ctr-esiti is-avvocato" aria-labelledby="titolo-avvocato">
        <h4 id="titolo-avvocato"><Gavel size={16} aria-hidden="true" /> Valutazioni dell'avvocato ({v.punti_avvocato.filter((p) => decisioni[p.id]?.valutato).length}/{v.punti_avvocato.length})</h4>
        {v.punti_avvocato.length ? (
          <ul>
            {v.punti_avvocato.map((e) => {
              const decisione = decisioni[e.id] || { valutato: false, nota: '' }
              return (
                <li key={e.id} className={decisione.valutato ? 'is-valutato' : ''}>
                  <Voce esito={e} />
                  <label className="iu-ctr-check">
                    <input type="checkbox" checked={decisione.valutato} onChange={(evento) => { const valutato = evento.currentTarget.checked; onDecisione(e.id, { ...decisione, valutato }) }} />
                    <span>Valutato dall'avvocato</span>
                  </label>
                  <textarea rows={2} placeholder="Motivazione o scelta adottata" aria-label={`Motivazione: ${e.messaggio}`} value={decisione.nota} onChange={(evento) => { const nota = evento.currentTarget.value; onDecisione(e.id, { ...decisione, nota }) }} />
                </li>
              )
            })}
          </ul>
        ) : <p className="iu-ctr-nota">Nessun punto richiede una valutazione con le risposte date.</p>}
      </section>

      <section className="iu-ctr-esiti is-adempimento" aria-labelledby="titolo-adempimenti">
        <h4 id="titolo-adempimenti"><ClipboardList size={16} aria-hidden="true" /> Adempimenti ({v.adempimenti.length})</h4>
        {v.adempimenti.length ? <ul>{v.adempimenti.map((e) => <li key={e.id}><Voce esito={e} /></li>)}</ul> : <p className="iu-ctr-nota">Nessun adempimento specifico.</p>}
      </section>

      {v.avvisi.length ? (
        <section className="iu-ctr-esiti is-avviso" aria-labelledby="titolo-avvisi">
          <h4 id="titolo-avvisi"><Info size={16} aria-hidden="true" /> Avvertenze ({v.avvisi.length})</h4>
          <ul>{v.avvisi.map((e) => <li key={e.id}><Voce esito={e} /></li>)}</ul>
        </section>
      ) : null}

      {v.controlli_sospesi.length ? (
        <section className="iu-ctr-esiti is-sospeso" aria-labelledby="titolo-sospesi">
          <h4 id="titolo-sospesi"><Info size={16} aria-hidden="true" /> Controlli in attesa di risposta ({v.controlli_sospesi.length})</h4>
          <p className="iu-ctr-nota">Questi controlli si decidono quando rispondi alle domande collegate.</p>
          <ul>{v.controlli_sospesi.map((e) => <li key={e.id}><Voce esito={e} /></li>)}</ul>
        </section>
      ) : null}

      {v.novita.length ? (
        <section className="iu-ctr-esiti is-novita" aria-labelledby="titolo-novita">
          <h4 id="titolo-novita"><CheckCircle2 size={16} aria-hidden="true" /> Novità normative da considerare</h4>
          <ul>{v.novita.map((n) => <li key={n.id}><span>{n.titolo}</span><small className="iu-ctr-norma">{n.norma} · dal {dataItaliana(n.decorrenza)}</small></li>)}</ul>
        </section>
      ) : null}
    </div>
  )
}
