import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, BrainCircuit, RefreshCw } from 'lucide-react'
import type { DocumentAIDetailPayload, DocumentAIListPayload, DocumentAIRecord, DocumentAITextPayload } from '../documentiAiData'
import { fetchDocumentAIDetail, fetchDocumentAIList, fetchDocumentAIText } from '../documentiAiData'
import { Badge } from './dashboard'
import { DocumentAIEmptyState } from './DocumentAIEmptyState'
import { DocumentDetailPanel } from './DocumentDetailPanel'
import { DocumentListPanel } from './DocumentListPanel'
import { DocumentUploadPanel } from './DocumentUploadPanel'
import './DocumentiAIPage.css'

type LoadingState = 'idle' | 'loading' | 'success' | 'error'

export function DocumentiAIPage({ fascicoloId }:{fascicoloId: string}) {
  const uploadAnchor = useRef<HTMLDivElement | null>(null)
  const [payload, setPayload] = useState<DocumentAIListPayload | null>(null)
  const [state, setState] = useState<LoadingState>('loading')
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<DocumentAIRecord | null>(null)
  const [detail, setDetail] = useState<DocumentAIDetailPayload | null>(null)
  const [textPayload, setTextPayload] = useState<DocumentAITextPayload | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState('')

  const documents = useMemo(() => payload?.documents || [], [payload])

  const loadList = async () => {
    setState('loading')
    setError('')
    try {
      const nextPayload = await fetchDocumentAIList(fascicoloId)
      setPayload(nextPayload)
      setState('success')
      setSelected((current) => {
        if (!current) return current
        return nextPayload.documents.find((document) => document.id === current.id) || null
      })
    } catch (loadError) {
      setState('error')
      setError(loadError instanceof Error ? loadError.message : 'Documenti AI non disponibili.')
    }
  }

  useEffect(() => {
    let active = true
    setState('loading')
    setError('')
    fetchDocumentAIList(fascicoloId)
      .then((nextPayload) => {
        if (!active) return
        setPayload(nextPayload)
        setState('success')
      })
      .catch((loadError) => {
        if (!active) return
        setState('error')
        setError(loadError instanceof Error ? loadError.message : 'Documenti AI non disponibili.')
      })
    return () => { active = false }
  }, [fascicoloId])

  const openDocument = async (document: DocumentAIRecord) => {
    setSelected(document)
    setDetail(null)
    setTextPayload(null)
    setDetailError('')
    setDetailLoading(true)
    try {
      const nextDetail = await fetchDocumentAIDetail(fascicoloId, document.id)
      setDetail(nextDetail)
      if (document.status === 'ready') {
        setTextPayload(await fetchDocumentAIText(fascicoloId, document.id))
      }
    } catch (loadError) {
      setDetailError(loadError instanceof Error ? loadError.message : 'Documento non disponibile.')
    } finally {
      setDetailLoading(false)
    }
  }

  const focusUpload = () => uploadAnchor.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })

  return (
    <section className="iu-docai-page" aria-label="Documenti AI">
      <header className="iu-docai-header">
        <div>
          <span><BrainCircuit size={17} aria-hidden="true" /> Documenti AI</span>
          <h3>Documenti AI</h3>
          <p>Analisi, ricerca e lettura assistita dei documenti del fascicolo</p>
        </div>
        <div className="iu-docai-header__badges">
          <Badge tone="warning">react_operational_partial</Badge>
          <Badge tone={payload?.capabilities.lex_tools ? 'success' : 'neutral'}>Lex tools</Badge>
          <button type="button" onClick={loadList} disabled={state === 'loading'}>
            <RefreshCw size={15} aria-hidden="true" />
            Aggiorna
          </button>
        </div>
      </header>
      {error ? (
        <div className="iu-docai-message iu-docai-message--error" role="alert">
          <AlertTriangle size={16} aria-hidden="true" />
          <span>{error}</span>
        </div>
      ) : null}
      <div ref={uploadAnchor}>
        <DocumentUploadPanel fascicoloId={fascicoloId} onUploaded={loadList} />
      </div>
      {state === 'loading' ? <p className="iu-docai-muted">Caricamento documenti AI...</p> : null}
      {state !== 'loading' && !documents.length ? <DocumentAIEmptyState onUploadFocus={focusUpload} /> : null}
      {documents.length ? (
        <div className="iu-docai-layout">
          <DocumentListPanel
            documents={documents}
            selectedId={selected?.id || null}
            onOpen={openDocument}
            onSearch={openDocument}
          />
          <DocumentDetailPanel
            fascicoloId={fascicoloId}
            document={selected}
            detail={detail}
            textPayload={textPayload}
            loading={detailLoading}
            error={detailError}
          />
        </div>
      ) : null}
    </section>
  )
}
