import { FileText } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { PceCard } from './procedureCompletionData'

export function ProcedureCompletionTemplateFusionPanel({ card }: { card: PceCard }) {
  const selezionato = card.template_selected.template_id
  return (
    <Card>
      <CardHeader>
        <CardTitle className="pce-panel-title">
          <FileText size={18} aria-hidden="true" />
          Atto principale e template
        </CardTitle>
      </CardHeader>
      <CardContent className="pce-stack">
        <div className="pce-row">
          <span>Atto principale</span>
          {card.atto_principale.stato === 'collegato_a_template' ? (
            <strong>{card.atto_principale.titolo}</strong>
          ) : (
            <Badge variant="secondary">Da revisionare: nessun template collegato</Badge>
          )}
        </div>
        {card.template_candidates.length ? (
          <ul className="pce-template-list">
            {card.template_candidates.map((cand) => (
              <li key={cand.template_id} className={cand.template_id === selezionato ? 'pce-template is-selected' : 'pce-template'}>
                <div className="pce-template__head">
                  <strong>{cand.titolo || cand.template_id}</strong>
                  {cand.template_id === selezionato ? <Badge>Selezionato</Badge> : <Badge variant="outline">Candidato</Badge>}
                  <small>punteggio {cand.score}</small>
                </div>
                {cand.motivi.length ? <small>{cand.motivi.join(' - ')}</small> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="pce-empty">
            Nessun template candidato: creare o collegare un modello nel catalogo atti prima della generazione del documento.
          </p>
        )}
        <p className="pce-hint">Il documento definitivo non viene mai generato senza revisione dell'avvocato.</p>
      </CardContent>
    </Card>
  )
}
