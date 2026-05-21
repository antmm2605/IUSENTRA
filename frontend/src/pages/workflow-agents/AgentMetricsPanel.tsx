import { BarChart3, CheckCircle2, Clock3, Target } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { IusMetricCard } from '@/components/iusentra'
import type { WorkflowAgentMetrics } from './api'

export function AgentMetricsPanel({ metrics }: { metrics: WorkflowAgentMetrics }) {
  const targetLabel = metrics.target_80_met ? 'Target raggiunto' : 'Target da migliorare'
  return (
    <section className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <IusMetricCard label="Riduzione media" value={`${metrics.average_saving_percentage || 0}%`} icon={Target} tone={metrics.target_80_met ? 'success' : 'warning'} />
        <IusMetricCard label="Minuti risparmiati" value={`${metrics.saved_minutes || 0}`} icon={Clock3} tone="primary" />
        <IusMetricCard label="Azioni approvate" value={`${metrics.accepted_actions || 0}`} icon={CheckCircle2} tone="success" />
        <IusMetricCard label="Percorsi completati" value={`${metrics.run_count || 0}`} icon={BarChart3} tone="neutral" />
      </div>
      <Card size="sm">
        <CardHeader>
          <CardTitle className="flex items-center justify-between gap-2">
            Soglia 80%
            <Badge variant={metrics.target_80_met ? 'default' : 'secondary'}>{targetLabel}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm text-muted-foreground">
          {metrics.top_workflows.length ? metrics.top_workflows.slice(0, 4).map((item) => (
            <div key={item.workflow_code} className="flex items-center justify-between gap-3 rounded-md border px-3 py-2">
              <span>{item.workflow_code.replaceAll('_', ' ')}</span>
              <strong className="text-foreground">{item.average_saving_percentage}%</strong>
            </div>
          )) : <p>Nessun dato consolidato disponibile.</p>}
        </CardContent>
      </Card>
    </section>
  )
}
