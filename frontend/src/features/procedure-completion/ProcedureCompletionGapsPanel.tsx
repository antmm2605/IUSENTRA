import { CircleAlert } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { PceGap } from './procedureCompletionData'

function severityBadge(severita: PceGap['severita']) {
  if (severita === 'blocking') return <Badge variant="destructive">Bloccante</Badge>
  if (severita === 'warning') return <Badge variant="secondary">Avviso</Badge>
  return <Badge variant="outline">Informativo</Badge>
}

export function ProcedureCompletionGapsPanel({ gaps, title = 'Gap di evidenza' }: { gaps: PceGap[]; title?: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="pce-panel-title">
          <CircleAlert size={18} aria-hidden="true" />
          {title} ({gaps.length})
        </CardTitle>
      </CardHeader>
      <CardContent>
        {gaps.length ? (
          <ul className="pce-gap-list">
            {gaps.map((gap) => (
              <li key={gap.id} className="pce-gap">
                <div className="pce-gap__head">
                  {severityBadge(gap.severita)}
                  <strong>{gap.descrizione}</strong>
                </div>
                {gap.azione_suggerita ? (
                  <small>Azione successiva: {gap.azione_suggerita}</small>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="pce-empty">Nessun gap aperto: restano comunque necessarie revisione e fonti per pubblicare.</p>
        )}
      </CardContent>
    </Card>
  )
}
