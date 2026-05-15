import { ExternalLink } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { LegalSkillCitation } from '../types'

export function CitationList({ citations }: { citations: LegalSkillCitation[] }) {
  if (!citations.length) {
    return <p className="text-sm text-muted-foreground">Nessuna fonte verificabile collegata.</p>
  }
  return (
    <div className="grid gap-2">
      {citations.map((citation, index) => (
        <article key={`${citation.label}-${index}`} className="rounded-lg border bg-card p-3">
          <div className="flex flex-wrap items-center gap-2">
            <strong className="text-sm">{citation.label}</strong>
            <Badge variant="outline">{citation.reliability || 'da verificare'}</Badge>
            <span className="text-xs text-muted-foreground">{citation.reference}</span>
          </div>
          {citation.excerpt ? <p className="mt-2 text-sm text-muted-foreground">{citation.excerpt}</p> : null}
          {citation.url ? (
            <a className="mt-2 inline-flex items-center gap-1 text-sm text-primary" href={citation.url} target="_blank" rel="noreferrer">
              Apri fonte <ExternalLink aria-hidden="true" />
            </a>
          ) : null}
        </article>
      ))}
    </div>
  )
}
