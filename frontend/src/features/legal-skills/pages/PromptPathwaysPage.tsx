import { Library, Route } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { IusPageShell } from '@/components/iusentra'
import { PercorsiGuidati } from '../components/PercorsiGuidati'

/** Vecchio indirizzo «/legal-skills/percorsi»: mostra le stesse procedure di «Procedure guidate». */
export function PromptPathwaysPage() {
  return (
    <IusPageShell
      title="Procedure guidate"
      description="Sequenze operative per procedimento: per ogni passo i termini, le norme vigenti e i modelli d'atto collegati."
      icon={Route}
      area="lex"
      actions={<Button asChild variant="outline"><a href="/legal-skills/prompt"><Library aria-hidden="true" /> Richieste pronte per Lex</a></Button>}
    >
      <PercorsiGuidati />
    </IusPageShell>
  )
}
