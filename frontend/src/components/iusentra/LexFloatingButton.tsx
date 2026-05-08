import { Bot, GripVertical } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function LexFloatingButton({
  label = 'Apri Lex',
  context,
  className,
}: {
  label?: string
  context?: string
  className?: string
}) {
  return (
    <Button
      type="button"
      className={cn('ius-lex-floating-button', className)}
      aria-label={label}
      data-lex-open
      data-lex-context={context}
      onClick={() => window.dispatchEvent(new CustomEvent('iusentra:open-floating-lex', { detail: { context } }))}
    >
      <GripVertical data-icon="inline-start" aria-hidden="true" />
      <Bot aria-hidden="true" />
      <span>Lex</span>
    </Button>
  )
}
