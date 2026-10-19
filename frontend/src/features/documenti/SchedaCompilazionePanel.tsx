import { ClipboardCheck } from 'lucide-react'
import { Badge } from '../../ui/Badge'
import type { RedazioneScheda } from '../../redazioneAttiData'

const STATI: Record<string, { label: string; tone: 'success' | 'warning' | 'neutral' | 'danger' }> = {
  compilato: { label: 'Dal gestionale', tone: 'success' },
  da_confermare: { label: 'Letto nei documenti: conferma', tone: 'warning' },
  documento_presente: { label: 'Documento presente: verifica', tone: 'warning' },
  calcolo: { label: 'Calcolato dal software', tone: 'neutral' },
  proposta_lex: { label: 'Proposta di Lex da confermare', tone: 'neutral' },
  da_chiedere: { label: 'Da indicare', tone: 'danger' },
  facoltativo: { label: 'Facoltativo', tone: 'neutral' },
}

// Scheda di compilazione dell'atto: da dove viene ogni dato e solo le domande che servono.
export function SchedaCompilazionePanel({ scheda }: { scheda: RedazioneScheda }) {
  return (
    <section aria-label="Scheda di compilazione" className="iu-rg-scheda">
      <h4 className="iu-rg-subtitle"><ClipboardCheck size={16} aria-hidden="true" /> Scheda di compilazione: {scheda.titolo}</h4>
      {scheda.domande.length ? (
        <div className="iu-rg-scheda-domande">
          <p className="iu-rg-hint">Servono da te solo queste informazioni:</p>
          <ol>
            {scheda.domande.map((domanda) => (
              <li key={domanda.campo}>
                {domanda.domanda}{domanda.obbligatorio ? '' : ' (facoltativo)'}
                {domanda.seManca ? <small>{domanda.seManca}</small> : null}
              </li>
            ))}
          </ol>
        </div>
      ) : <p className="iu-rg-hint">Il fascicolo contiene già tutti i dati che la scheda richiede.</p>}
      <details className="iu-rg-scheda-campi">
        <summary>Provenienza di ogni dato ({scheda.campi.length})</summary>
        <ul>
          {scheda.campi.map((campo) => {
            const stato = STATI[campo.stato] || { label: campo.stato, tone: 'neutral' as const }
            return (
              <li key={campo.campo}>
                <span>{campo.etichetta}</span>
                <Badge tone={stato.tone}>{stato.label}</Badge>
                {campo.valore ? <strong>{campo.valore.length > 80 ? `${campo.valore.slice(0, 80)}...` : campo.valore}</strong> : null}
                {campo.norme.length ? <small>{campo.norme.join('; ')}</small> : null}
              </li>
            )
          })}
        </ul>
      </details>
      {scheda.astensione.length ? (
        <p className="iu-rg-hint">Lex non redige l’atto se: {scheda.astensione.join('; ')}.</p>
      ) : null}
    </section>
  )
}
