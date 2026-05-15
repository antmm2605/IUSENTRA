import { ShieldCheck } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import type { LegalSkillReviewerNote } from '../types'

export function ReviewerNoteBox({ note }: { note?: LegalSkillReviewerNote | null }) {
  if (!note) return null
  return (
    <Alert className="border-amber-200 bg-amber-50 text-amber-950">
      <ShieldCheck aria-hidden="true" />
      <AlertTitle>Bozza per revisione</AlertTitle>
      <AlertDescription>
        <p>{note.text}</p>
        {note.reasons?.length ? (
          <ul className="mt-2 grid gap-1 pl-4">
            {note.reasons.map((reason) => <li key={reason}>{reason}</li>)}
          </ul>
        ) : null}
      </AlertDescription>
    </Alert>
  )
}
