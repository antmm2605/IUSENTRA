import { FileSearch, Search } from 'lucide-react'
import type { DocumentAIRecord } from '../documentiAiData'
import { formatDocumentAIDate, formatDocumentAISize, shortSha } from '../documentiAiData'
import { DocumentStatusBadge } from './DocumentStatusBadge'

export function DocumentListPanel({
  documents,
  selectedId,
  onOpen,
  onSearch,
}:{
  documents: DocumentAIRecord[]
  selectedId: string | null
  onOpen: (document: DocumentAIRecord) => void
  onSearch: (document: DocumentAIRecord) => void
}) {
  return (
    <div className="iu-docai-list" aria-label="Documenti AI del fascicolo">
      {documents.map((document) => (
        <article className={selectedId === document.id ? 'is-selected' : ''} key={document.id}>
          <div className="iu-docai-list__main">
            <strong>{document.original_filename}</strong>
            <span>
              {document.file_type.toUpperCase()} · {formatDocumentAISize(document.size_bytes)} · {formatDocumentAIDate(document.created_at)}
            </span>
            <small title={document.sha256}>SHA-256 {shortSha(document.sha256)}</small>
          </div>
          <div className="iu-docai-list__meta">
            <DocumentStatusBadge status={document.status} />
            <span>{document.page_count ? `${document.page_count} pagine` : 'Pagine n.d.'}</span>
          </div>
          <div className="iu-docai-list__actions">
            <button type="button" onClick={() => onOpen(document)}>
              <FileSearch size={15} aria-hidden="true" />
              Apri
            </button>
            <button type="button" onClick={() => onSearch(document)}>
              <Search size={15} aria-hidden="true" />
              Cerca
            </button>
          </div>
        </article>
      ))}
    </div>
  )
}
