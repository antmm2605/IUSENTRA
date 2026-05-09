import { useState, type FormEvent, type ReactNode } from 'react'
import { redirectAfterSuccess, submitFormJson } from '../formSubmit'

export function JsonPostForm({
  action,
  className,
  children,
  redirectTo,
  encType,
  pendingMessage = 'Salvataggio in corso...',
  successMessage = 'Operazione completata.',
}: {
  action: string
  className?: string
  children: ReactNode
  redirectTo?: string
  encType?: string
  pendingMessage?: string
  successMessage?: string
}) {
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  if (!action) return null
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setBusy(true)
    setMessage(pendingMessage)
    try {
      const result = await submitFormJson(action, new FormData(event.currentTarget))
      setMessage(result.message || successMessage)
      redirectAfterSuccess(result, redirectTo || window.location.href)
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
