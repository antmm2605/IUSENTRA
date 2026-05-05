import { useState, type FormEvent } from 'react'
import { Search } from 'lucide-react'
import type { DocumentAISearchPayload } from '../documentiAiData'
import { searchDocumentAI } from '../documentiAiData'

type SearchState = 'idle' | 'loading' | 'success' | 'empty' | 'error'

export function DocumentSearchPanel({
  fascicoloId,
  documentId,
}:{
  fascicoloId: string
  documentId: string | null
}) {
  const [query, setQuery] = useState('')
  const [payload, setPayload] = useState<DocumentAISearchPayload | null>(null)
  const [state, setState] = useState<SearchState>('idle')
  const [message, setMessage] = useState('')

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!documentId) {
      setState('error')
      setMessage('Apri un documento prima di cercare.')
      return
    }
    if (!query.trim()) {
      setState('error')
      setMessage('Inserisci una parola o frase da cercare.')
      return
    }
    setState('loading')
    setMessage('')
    try {
      const result = await searchDocumentAI(fascicoloId, documentId, query.trim(), 20)
      setPayload(result)
      setState(result.results.length ? 'success' : 'empty')
    } catch (error) {
      setPayload(null)
      setState('error')
      setMessage(error instanceof Error ? error.message : 'Ricerca non completata.')
    }
  }

  return (
    <div className="iu-docai-search">
      <form onSubmit={submit}>
        <label htmlFor="document-ai-search">Cerca nel documento</label>
        <div>
          <input
            id="document-ai-search"
            value={query}
            onChange={(event) => setQuery(event.currentTarget.value)}
            placeholder="Parola o frase"
          />
          <button type="submit" disabled={state === 'loading'}>
            <Search size={15} aria-hidden="true" />
            {state === 'loading' ? 'Cerco...' : 'Cerca'}
          </button>
        </div>
      </form>
      {state === 'idle' ? <p className="iu-docai-muted">I risultati useranno solo il testo estratto dal documento aperto.</p> : null}
      {state === 'empty' ? <p className="iu-docai-muted">Nessun risultato nel documento selezionato.</p> : null}
      {state === 'error' ? <p className="iu-docai-message iu-docai-message--error" role="alert">{message}</p> : null}
      {payload?.results.length ? (
        <div className="iu-docai-results">
          {payload.results.map((result, index) => (
            <article key={`${result.start_offset ?? index}-${result.end_offset ?? index}`}>
              <span>{result.page_number ? `Pagina ${result.page_number}` : 'Pagina n.d.'}</span>
              <p>{result.snippet}</p>
            </article>
          ))}
        </div>
      ) : null}
    </div>
  )
}
