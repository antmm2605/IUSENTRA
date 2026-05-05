import { Badge } from './dashboard'
import type { DocumentAIStatus } from '../documentiAiData'

const labels: Record<DocumentAIStatus, string> = {
  uploaded: 'Caricato',
  processing: 'In estrazione',
  ready: 'Pronto',
  error: 'Errore',
  archived: 'Archiviato',
}

const tones: Record<DocumentAIStatus, 'neutral' | 'info' | 'success' | 'danger' | 'warning'> = {
  uploaded: 'info',
  processing: 'warning',
  ready: 'success',
  error: 'danger',
  archived: 'neutral',
}

export function DocumentStatusBadge({ status }:{status: DocumentAIStatus}) {
  return <Badge tone={tones[status] || 'neutral'}>{labels[status] || status}</Badge>
}
