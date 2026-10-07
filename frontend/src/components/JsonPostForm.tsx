import { publishMutationRefresh } from '../operationalRefresh'
import { useState, type FormEvent, type ReactNode } from 'react'
import { redirectAfterSuccess, submitFormJson, type FormSubmitResult } from '../formSubmit'

export function JsonPostForm({
  action,
  className,
  children,
  redirectTo,
  encType,
  pendingMessage = 'Salvataggio in corso...',
  successMessage = 'Operazione completata.',
  customSubmit,
  onSuccess,
}: {
  action: string
  className?: string
  children: ReactNode
  redirectTo?: string
  encType?: string
  pendingMessage?: string
  successMessage?: string
  customSubmit?: (form: HTMLFormElement) => Promise<FormSubmitResult>
  onSuccess?: (result: FormSubmitResult, form: HTMLFormElement) => void | Promise<void>
}) {
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  if (!action) return null
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (busy) return
    const form = event.currentTarget
    setBusy(true)
    setMessage(pendingMessage)
    try {
      const result = customSubmit
        ? await customSubmit(form)
        : await submitFormJson(action, new FormData(form))
      if (customSubmit && result.ok) publishMutationRefresh(action)
      setMessage(result.message || successMessage)
      if (onSuccess && result.ok) {
        try {
          await onSuccess(result, form)
        } catch {
          setMessage('Operazione salvata. Non è stato possibile aggiornare i dati della pagina: riprova l’aggiornamento senza ripetere il salvataggio.')
        }
      } else {
        redirectAfterSuccess(result, redirectTo || window.location.href)
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Operazione non riuscita.')
    } finally {
      setBusy(false)
    }
  }
  return (
    <form className={className} onSubmit={submit} encType={encType} data-busy={busy ? 'true' : undefined}>
      {children}
      {message ? <span role="status">{message}</span> : null}
    </form>
  )
}
