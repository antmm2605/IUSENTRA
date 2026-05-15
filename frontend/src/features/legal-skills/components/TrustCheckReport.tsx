import { ShieldAlert } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { TrustFinding } from '../types'

export function TrustCheckReport({ findings = [], verdict = 'clean' }: { findings?: TrustFinding[]; verdict?: string }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><ShieldAlert aria-hidden="true" /> Controllo fiducia <Badge variant="outline">{verdict}</Badge></CardTitle>
      </CardHeader>
      <CardContent>
        {findings.length ? (
          <ul className="grid gap-2 text-sm text-muted-foreground">
            {findings.map((finding) => <li key={`${finding.code}-${finding.message}`}>{finding.message}</li>)}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">Nessun rilievo nel controllo statico.</p>
        )}
      </CardContent>
    </Card>
  )
}
