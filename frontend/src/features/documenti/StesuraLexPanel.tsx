import './StesuraLexPanel.css'
import { useState } from 'react'
import { Bot } from 'lucide-react'
import { Badge } from '../../ui/Badge'
import { Button } from '../../ui/Button'
import { stesuraLex, type StesuraLexEsito } from '../../redazioneAttiData'

const STATI: Record<string, { label: string; tone: 'success' | 'warning' | 'danger' | 'neutral' }> = {
  pronta_per_revisione_avvocato: { label: 'Pronta per la tua revisione', tone: 'success' },
  bozza_con_verifiche_pendenti: { label: 'Bozza con verifiche da fare', tone: 'warning' },
  bozza_incompleta: { label: 'Bozza incompleta', tone: 'warning' },
}

// Lex scrive le parti narrative della scheda con le Fonti vigenti; l'avvocato sceglie cosa inserire nei campi.
export function StesuraLexPanel({
  modelCode,
  fascicoloId,
  clienteId,
  valori,
  onInserisci,
}: {
  modelCode: string
  fascicoloId: string
  clienteId: string
  valori: Record<string, string>
  onInserisci: (campo: string, testo: string) => void
}) {
  const [oggetto, setOggetto] = useState('')
  const [ruolo, setRuolo] = useState('')
  const [esito, setEsito] = useState<StesuraLexEsito | null>(null)
  const [inCorso, setInCorso] = useState(false)
  const [inseriti, setInseriti] = useState<Set<string>>(new Set())

  const scrivi = () => {
    setInCorso(true)
    setInseriti(new Set())
    stesuraLex({ modelCode, fascicoloId, clienteId, oggetto, ruoloAssistito: ruolo, valori })
      .then(setEsito)
      .finally(() => setInCorso(false))
  }
  const stato = esito ? STATI[esito.stato] || { label: esito.stato || 'Stato non disponibile', tone: 'neutral' as const } : null

  return (
    <section aria-label="Stesura di Lex" className="iu-rg-lex">
      <h4 className="iu-rg-subtitle"><Bot size={16} aria-hidden="true" /> Parti dell'atto scritte da Lex</h4>
      <p className="iu-rg-hint">Lex usa solo i dati del fascicolo, le scadenze calcolate e il testo vigente delle norme della scheda. Il modello gira sul server dello studio: nessun dato esce.</p>
      <label className="iu-rg-lex__campo">
        <span>Cosa deve ottenere l'atto per l'assistito</span>
        <textarea rows={3} value={oggetto} onChange={(event) => setOggetto(event.target.value)} placeholder="Es. pagamento del prezzo della fornitura non saldata" />
      </label>
      <label className="iu-rg-lex__campo">
        <span>Ruolo dell'assistito</span>
        <select value={ruolo} onChange={(event) => setRuolo(event.target.value)}>
          <option value="">Non indicato</option>
          <option value="attore">Attore / ricorrente / creditore</option>
          <option value="convenuto">Convenuto / resistente / debitore</option>
        </select>
      </label>
      <Button type="button" tone="neutral" onClick={scrivi} disabled={inCorso || !oggetto.trim()}>
        {inCorso ? 'Lex sta scrivendo (circa un minuto)...' : 'Fai scrivere a Lex'}
      </Button>
      {esito && !esito.ok ? <p className="iu-rg-errore" role="alert">{esito.errore}</p> : null}
      {esito && esito.ok && stato ? (
        <div className="iu-rg-lex__esito">
          <p className="iu-rg-lex__stato"><Badge tone={stato.tone}>{stato.label}</Badge> <small>{esito.modelloAi}</small></p>
          {esito.gravi.length ? (
            <div className="iu-rg-lex__avvisi" role="alert">
              <strong>Errori trovati dalla revisione indipendente</strong>
              <ul>{esito.gravi.map((voce) => <li key={voce}>{voce}</li>)}</ul>
            </div>
          ) : null}
          {esito.pendenti.length || esito.motivi.length ? (
            <details className="iu-rg-lex__verifiche">
              <summary>Verifiche da fare ({esito.pendenti.length + esito.motivi.length})</summary>
              <ul>{[...esito.pendenti, ...esito.motivi].map((voce) => <li key={voce}>{voce}</li>)}</ul>
            </details>
          ) : null}
          {esito.blocchi.map((blocco) => (
            <article className="iu-rg-lex__blocco" key={blocco.blocco}>
              <header>
                <strong>{blocco.blocco}</strong>
                {blocco.campo ? (
                  <Button type="button" tone="neutral" disabled={inseriti.has(blocco.blocco)} onClick={() => {
                    onInserisci(blocco.campo, blocco.testo)
                    setInseriti((correnti) => new Set(correnti).add(blocco.blocco))
                  }}>
                    {inseriti.has(blocco.blocco) ? 'Inserito nel campo' : 'Inserisci nel campo'}
                  </Button>
                ) : <small>Nessun campo del modello corrispondente: copia il testo nell'editor.</small>}
              </header>
              <p>{blocco.testo}</p>
            </article>
          ))}
          {esito.fonti.length ? <p className="iu-rg-hint">Fonti: {esito.fonti.join('; ')}</p> : null}
        </div>
      ) : null}
    </section>
  )
}
