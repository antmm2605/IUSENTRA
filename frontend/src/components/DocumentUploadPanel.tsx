import { useRef, useState, type FormEvent } from 'react'
import { AlertTriangle, UploadCloud } from 'lucide-react'
import { uploadDocumentAI } from '../documentiAiData'

type UploadState = 'idle' | 'loading' | 'success' | 'error'

export function DocumentUploadPanel({
  fascicoloId,
  onUploaded,
}:{
  fascicoloId: string
  onUploaded: () => void
}) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [state, setState] = useState<UploadState>('idle')
  const [message, setMessage] = useState('')

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const file = inputRef.current?.files?.[0]
    if (!file) {
      setState('error')
      setMessage('Seleziona un file PDF, DOCX o DOC.')
      return
    }
    setState('loading')
    setMessage('Caricamento ed estrazione in corso...')
    try {
      const payload = await uploadDocumentAI(fascicoloId, file)
      setState(payload.document.status === 'ready' ? 'success' : 'error')
      setMessage(
        payload.document.status === 'ready'
          ? 'Documento caricato ed estratto correttamente.'
          : 'Documento salvato, ma estrazione testo non completata.',
      )
      if (inputRef.current) inputRef.current.value = ''
      onUploaded()
    } catch (error) {
      setState('error')
      setMessage(error instanceof Error ? error.message : 'Upload non completato.')
    }
  }

  return (
    <form className="iu-docai-upload" onSubmit={submit}>
      <div>
        <label htmlFor="document-ai-file">Documento fascicolo</label>
        <input
          ref={inputRef}
          id="document-ai-file"
          name="file"
          type="file"
          accept=".pdf,.docx,.doc,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        />
        <small>Formati ammessi: PDF, DOCX, DOC. Limite configurato dal backend.</small>
      </div>
      <button type="submit" disabled={state === 'loading'}>
        <UploadCloud size={16} aria-hidden="true" />
        {state === 'loading' ? 'Carico...' : 'Carica'}
      </button>
      {message ? (
        <p className={`iu-docai-message iu-docai-message--${state}`} role={state === 'error' ? 'alert' : 'status'}>
          {state === 'error' ? <AlertTriangle size={15} aria-hidden="true" /> : null}
          {message}
        </p>
      ) : null}
    </form>
  )
}
