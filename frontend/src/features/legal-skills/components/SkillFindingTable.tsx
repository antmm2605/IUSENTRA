import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { LegalSkillFinding } from '../types'

function severityVariant(severity: string): 'default' | 'outline' | 'destructive' | 'secondary' {
  if (severity === 'high') return 'destructive'
  if (severity === 'low') return 'secondary'
  return 'outline'
}

export function SkillFindingTable({ findings }: { findings: LegalSkillFinding[] }) {
  if (!findings.length) return <p className="text-sm text-muted-foreground">Nessun punto rilevato.</p>
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Punto</TableHead>
          <TableHead>Stato</TableHead>
          <TableHead>Sintesi</TableHead>
          <TableHead>Azione</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {findings.map((finding) => (
          <TableRow key={`${finding.title}-${finding.summary}`}>
            <TableCell className="font-medium">{finding.title}</TableCell>
            <TableCell><Badge variant={severityVariant(finding.severity)}>{finding.status}</Badge></TableCell>
            <TableCell>{finding.summary}</TableCell>
            <TableCell>{finding.recommendation}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
