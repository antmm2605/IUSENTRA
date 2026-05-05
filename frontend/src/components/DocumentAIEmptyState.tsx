import { FileText, UploadCloud } from 'lucide-react'

export function DocumentAIEmptyState({ onUploadFocus }:{onUploadFocus: () => void}) {
  return (
    <div className="iu-docai-empty">
      <FileText size={30} aria-hidden="true" />
      <strong>Nessun documento AI nel fascicolo</strong>
      <span>Carica un PDF, DOCX o DOC reale per abilitare lettura assistita, ricerca e strumenti Lex.</span>
      <button type="button" onClick={onUploadFocus}>
        <UploadCloud size={16} aria-hidden="true" />
        Carica documento
      </button>
    </div>
  )
}
