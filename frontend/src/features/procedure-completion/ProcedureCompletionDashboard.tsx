import { BookOpenCheck } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ProcedureCompletionGapsPanel } from './ProcedureCompletionGapsPanel'
import { ProcedureCompletionPreview } from './ProcedureCompletionPreview'
import {
  confidenceLabel,
  statusLabel,
  type PceCard,
  type PceDashboard,
  type PceValidation,
} from './procedureCompletionData'

function Counter({ label, value }: { label: string; value: number }) {
  return (
    <div className="pce-counter">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  )
}

export function ProcedureCompletionDashboard({
  dashboard,
  onOpenCard,
  onPreviewCreated,
}: {
  dashboard: PceDashboard
  onOpenCard: (cardId: string) => void
  onPreviewCreated: (esito: { card: PceCard; validation: PceValidation | null }) => void
}) {
  return (
    <div className="pce-stack-lg">
      <section className="pce-counters" aria-label="Indicatori schede procedura">
        <Counter label="Schede" value={dashboard.counters.cards} />
        <Counter label="Da revisionare" value={dashboard.counters.needsReview} />
        <Counter label="Approvate" value={dashboard.counters.approved} />
        <Counter label="Pubblicate" value={dashboard.counters.published} />
        <Counter label="Gap bloccanti" value={dashboard.counters.gapsBlocking} />
      </section>
      <ProcedureCompletionPreview
        canRun={dashboard.permissions.includes('procedure_completion.esegui')}
        onCreated={onPreviewCreated}
      />
      <Card>
        <CardHeader>
          <CardTitle className="pce-panel-title">
            <BookOpenCheck size={18} aria-hidden="true" />
            Schede recenti ({dashboard.cards.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {dashboard.cards.length ? (
            <ul className="pce-card-list" role="list">
              {dashboard.cards.map((card) => (
                <li key={card.id}>
                  <button type="button" className="pce-card-row" onClick={() => onOpenCard(card.id)}>
                    <span className="pce-card-row__body">
                      <strong>{card.denominazione || card.codice}</strong>
                      <small>
                        {[card.codice, card.categoria, card.templateSelezionato ? `template: ${card.templateSelezionato}` : '']
                          .filter(Boolean)
                          .join(' - ')}
                      </small>
                    </span>
                    <span className="pce-card-row__badges">
                      <Badge variant={card.status === 'published' ? 'default' : 'secondary'}>{statusLabel(card.status)}</Badge>
                      <Badge variant="outline">{confidenceLabel(card.confidence)}</Badge>
                      {card.gapsBlocking ? <Badge variant="destructive">{card.gapsBlocking} gap bloccanti</Badge> : null}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="pce-empty">
              Nessuna scheda generata: crea la prima anteprima partendo da un codice oggetto del catalogo PST.
            </p>
          )}
        </CardContent>
      </Card>
      <ProcedureCompletionGapsPanel gaps={dashboard.gaps} title="Coda gap aperti" />
    </div>
  )
}
