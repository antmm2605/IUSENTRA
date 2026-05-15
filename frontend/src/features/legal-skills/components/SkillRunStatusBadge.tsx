import { Badge } from '@/components/ui/badge'

export function SkillRunStatusBadge({ status }: { status: string }) {
  const label = status === 'completed' ? 'Completata' : status === 'degraded' ? 'Da integrare' : status === 'disabled' ? 'Non attiva' : 'In revisione'
  const variant = status === 'completed' ? 'secondary' : status === 'degraded' ? 'outline' : 'default'
  return <Badge variant={variant}>{label}</Badge>
}
