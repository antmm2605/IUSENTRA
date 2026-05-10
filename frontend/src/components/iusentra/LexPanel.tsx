import { Bot, FileText, ShieldCheck, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'
import { IusEmptyState } from './IusEmptyState'
import { IusStatusBadge } from './IusStatusBadge'

export type LexPanelSource = {
  id: string
  label: string
  detail?: string
}

export function LexPanel({
  title = 'Lex AI',
  contextLabel = 'Contesto corrente',
  sources = [],
  insufficientContext = false,
  className,
}: {
  title?: string
  contextLabel?: string
  sources?: LexPanelSource[]
  insufficientContext?: boolean
  className?: string
}) {
  return (
    <aside className={cn('ius-lex-panel', className)} aria-label={title}>
      <header>
        <Bot aria-hidden="true" />
        <div>
          <h2>{title}</h2>
          <p>{contextLabel}</p>
        </div>
        <IusStatusBadge tone={insufficientContext ? 'warning' : 'success'}>
          {insufficientContext ? 'Contesto insufficiente' : 'Fonti disponibili'}
        </IusStatusBadge>
      </header>
      {insufficientContext ? (
        <IusEmptyState
          title="Contesto insufficiente per una risposta affidabile"
          message="Non sono state trovate fonti sufficienti. La risposta richiede verifica professionale."
          area="lex"
          tone="warning"
        />
      ) : sources.length ? (
        <div className="ius-lex-panel__sources">
          {sources.map((source) => (
            <article key={source.id}>
              <FileText aria-hidden="true" />
              <div>
                <strong>{source.label}</strong>
                {source.detail ? <span>{source.detail}</span> : null}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <IusEmptyState
          title="Fonti utilizzate: nessuna fonte disponibile"
          message="Lex puo aprirsi, ma deve dichiarare il limite prima di generare contenuti legali."
          area="lex"
          tone="warning"
        />
      )}
      <footer>
        <span><ShieldCheck aria-hidden="true" /> Privacy e studio governati dai controlli operativi</span>
        <span><Sparkles aria-hidden="true" /> Revisione professionale richiesta</span>
      </footer>
    </aside>
  )
}
