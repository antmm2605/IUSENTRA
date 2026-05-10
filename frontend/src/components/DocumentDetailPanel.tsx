import { FileText, History } from 'lucide-react'
import type { DocumentAIDetailPayload, DocumentAIRecord, DocumentAITextPayload } from '../documentiAiData'
import { formatDocumentAIDate, formatDocumentAISize, shortSha } from '../documentiAiData'
import { DocumentStatusBadge } from './DocumentStatusBadge'
import { DocumentTextPanel } from './DocumentTextPanel'
import { DocumentSearchPanel } from './DocumentSearchPanel'

export function DocumentDetailPanel({
  fascicoloId,
  document,
  detail,
  textPayload,
  loading,
  error,
}:{
  fascicoloId: string
  document: DocumentAIRecord | null
  detail: DocumentAIDetailPayload | null
  textPayload: DocumentAITextPayload | null
  loading: boolean
  error: string
}) {
  if (!document) return <p className="iu-docai-muted">Seleziona un documento per aprire informazioni, versioni e testo estratto.</p>
  return (
    <div className="iu-docai-detail">
      <header>
        <div>
          <FileText size={18} aria-hidden="true" />
          <span>
            <strong>{document.original_filename}</strong>
            <small>{document.file_type.toUpperCase()} · {formatDocumentAISize(document.size_bytes)}</small>
          </span>
        </div>
        <DocumentStatusBadge status={document.status} />
      </header>
      {loading ? <p className="iu-docai-muted">Caricamento documento...</p> : null}
      {error ? <p className="iu-docai-message iu-docai-message--error" role="alert">{error}</p> : null}
      <dl className="iu-docai-kv">
        <div><dt>Nome sicuro</dt><dd>{document.safe_filename}</dd></div>
        <div><dt>Hash SHA-256</dt><dd title={document.sha256}>{shortSha(document.sha256)}</dd></div>
        <div><dt>Pagine</dt><dd>{document.page_count ?? 'n.d.'}</dd></div>
        <div><dt>Caricato da</dt><dd>{document.created_by || 'n.d.'}</dd></div>
        <div><dt>Data upload</dt><dd>{formatDocumentAIDate(document.created_at)}</dd></div>
      </dl>
      {detail?.versions.length ? (
        <section className="iu-docai-versions" aria-label="Versioni documento">
          <h4><History size={15} aria-hidden="true" /> Versioni</h4>
          {detail.versions.map((version) => (
            <span key={version.id}>v{version.version_number} · {version.source} · {shortSha(version.sha256)}</span>
          ))}
        </section>
      ) : null}
      <DocumentSearchPanel fascicoloId={fascicoloId} documentId={document.id} />
      <DocumentTextPanel payload={textPayload} />
    </div>
  )
}
