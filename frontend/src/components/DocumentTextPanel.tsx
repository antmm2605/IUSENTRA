import type { DocumentAITextPayload } from '../documentiAiData'

export function DocumentTextPanel({ payload }:{payload: DocumentAITextPayload | null}) {
  if (!payload) return <p className="iu-docai-muted">Apri un documento pronto per visualizzare il testo estratto.</p>
  return (
    <div className="iu-docai-text">
      <header>
        <strong>Testo estratto</strong>
        <span>{payload.extraction_engine || 'estrattore n.d.'}</span>
      </header>
      {payload.warnings.length ? (
        <div className="iu-docai-warning-list">
          {payload.warnings.map((warning) => <span key={warning}>{warning}</span>)}
        </div>
      ) : null}
      {payload.pages.length ? (
        payload.pages.map((page) => (
          <article key={page.page_number}>
            <h4>Pagina {page.page_number}</h4>
            <pre>{page.text || 'Nessun testo estraibile in questa pagina.'}</pre>
          </article>
        ))
      ) : (
        <article>
          <pre>{payload.text || 'Nessun testo estraibile.'}</pre>
        </article>
      )}
    </div>
  )
}
