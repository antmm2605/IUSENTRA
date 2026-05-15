import { AlertTriangle } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

export function EscalationBox({ title = 'Verifica richiesta', message }: { title?: string; message: string }) {
  return (
    <Alert className="border-amber-200 bg-amber-50 text-amber-950">
      <AlertTriangle aria-hidden="true" />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  )
}
