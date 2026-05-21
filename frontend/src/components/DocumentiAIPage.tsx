import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, Archive, BrainCircuit, FileCheck2, RefreshCw, Scale, ShieldCheck, Upload } from 'lucide-react'
import type {
  DocumentAIDetailPayload,
  DocumentAIListPayload,
  DocumentAIRecord,
  DocumentAITextPayload,
  LegalDocumentEvidence,
  LegalDocumentRecord,
  LegalDocumentTree,
} from '../documentiAiData'
import {
  approveLegalDocument,
  createLegalDocumentProofBundle,
  fetchDocumentAIDetail,
  fetchDocumentAIList,
  fetchDocumentAIText,
  fetchLegalDocumentEvidence,
  fetchLegalDocuments,
  fetchLegalDocumentTree,
  formatDocumentAIDate,
  formatDocumentAISize,
  requestLegalDocumentLexIndex,
  shortSha,
  uploadLegalDocument,
} from '../documentiAiData'
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
  const [legalDocuments, setLegalDocuments] = useState<LegalDocumentRecord[]>([])
  const [legalLoading, setLegalLoading] = useState(false)
  const [legalError, setLegalError] = useState('')
  const [selectedLegal, setSelectedLegal] = useState<LegalDocumentRecord | null>(null)
  const [legalEvidence, setLegalEvidence] = useState<LegalDocumentEvidence | null>(null)
  const [legalTree, setLegalTree] = useState<LegalDocumentTree | null>(null)
  const [legalMessage, setLegalMessage] = useState('')

  const documents = useMemo(() => payload?.documents || [], [payload])

  const loadLegalDocuments = async () => {
    setLegalLoading(true)
    setLegalError('')
    try {
      const nextPayload = await fetchLegalDocuments(fascicoloId)
      setLegalDocuments(nextPayload.data || [])
      setSelectedLegal((current) => {
        if (!current) return current
        return (nextPayload.data || []).find((document) => document.id === current.id) || null
      })
    } catch (loadError) {
      setLegalError(loadError instanceof Error ? loadError.message : 'Presidio forense non disponibile.')
    } finally {
      setLegalLoading(false)
    }
  }

  const loadList = async () => {
    setState('loading')
    setError('')
    try {
      const nextPayload = await fetchDocumentAIList(fascicoloId)
      setPayload(nextPayload)
      await loadLegalDocuments()
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
        loadLegalDocuments()
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

  const openLegalDocument = async (document: LegalDocumentRecord) => {
    setSelectedLegal(document)
    setLegalEvidence(null)
    setLegalTree(null)
    setLegalError('')
    try {
      const [evidencePayload, treePayload] = await Promise.all([
        fetchLegalDocumentEvidence(document.id),
        fetchLegalDocumentTree(document.id),
      ])
      setLegalEvidence(evidencePayload.data)
      setLegalTree(treePayload.data)
    } catch (loadError) {
      setLegalError(loadError instanceof Error ? loadError.message : 'Documento forense non disponibile.')
    }
  }

  const uploadForensicDocument = async (file: File) => {
    setLegalMessage('')
    setLegalError('')
    try {
      await uploadLegalDocument(fascicoloId, file)
      setLegalMessage('Documento acquisito, analizzato e inviato alla revisione quando necessario.')
      await loadLegalDocuments()
    } catch (uploadError) {
      setLegalError(uploadError instanceof Error ? uploadError.message : 'Acquisizione non completata.')
    }
  }

  const approveSelectedLegal = async () => {
    if (!selectedLegal) return
    setLegalMessage('')
    try {
      await approveLegalDocument(selectedLegal.id)
      await requestLegalDocumentLexIndex(selectedLegal.id)
      setLegalMessage('Documento approvato e inviato a Lex solo dopo validazione.')
      await loadLegalDocuments()
      await openLegalDocument(selectedLegal)
    } catch (actionError) {
      setLegalError(actionError instanceof Error ? actionError.message : 'Revisione non completata.')
    }
  }

  const exportSelectedProof = async () => {
    if (!selectedLegal) return
    setLegalMessage('')
    try {
      await createLegalDocumentProofBundle(selectedLegal.id)
      setLegalMessage('Pacchetto prova creato con file, hash, OCR, estrazioni e audit.')
      await openLegalDocument(selectedLegal)
    } catch (actionError) {
      setLegalError(actionError instanceof Error ? actionError.message : 'Pacchetto prova non creato.')
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
          <Badge tone="success">Presidio documenti</Badge>
          <Badge tone={payload?.capabilities.lex_tools ? 'success' : 'neutral'}>Strumenti Lex</Badge>
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
      <ForensicDocumentsPanel
        documents={legalDocuments}
        selected={selectedLegal}
        evidence={legalEvidence}
        tree={legalTree}
        loading={legalLoading}
        error={legalError}
        message={legalMessage}
        onRefresh={loadLegalDocuments}
        onOpen={openLegalDocument}
        onUpload={uploadForensicDocument}
        onApprove={approveSelectedLegal}
        onProofBundle={exportSelectedProof}
      />
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

function ForensicDocumentsPanel({
  documents,
  selected,
  evidence,
  tree,
  loading,
  error,
  message,
  onRefresh,
  onOpen,
  onUpload,
  onApprove,
  onProofBundle,
}:{
  documents: LegalDocumentRecord[]
  selected: LegalDocumentRecord | null
  evidence: LegalDocumentEvidence | null
  tree: LegalDocumentTree | null
  loading: boolean
  error: string
  message: string
  onRefresh: () => void
  onOpen: (document: LegalDocumentRecord) => void
  onUpload: (file: File) => void
  onApprove: () => void
  onProofBundle: () => void
}) {
  const fileInput = useRef<HTMLInputElement | null>(null)
  const selectedValidation = String(evidence?.validation?.result || selected?.status || '')
  const selectedLex = String(evidence?.lex_index?.status || '')
  return (
    <section className="iu-docai-forensic" aria-label="Revisione documentale forense">
      <header>
        <div>
          <span><Scale size={16} aria-hidden="true" /> Lettura forense</span>
          <h4>OCR, ZIP PEC, validazione e Lex</h4>
          <p>Ogni file conserva hash, catena padre-figlio, audit e invio a Lex solo dopo validazione.</p>
        </div>
        <div className="iu-docai-forensic__actions">
          <input
            ref={fileInput}
            type="file"
            multiple
            onChange={(event) => {
              Array.from(event.currentTarget.files || []).forEach(onUpload)
              event.currentTarget.value = ''
            }}
            aria-label="Carica documenti per lettura forense"
          />
          <button type="button" onClick={() => fileInput.current?.click()}>
            <Upload size={15} aria-hidden="true" /> Carica
          </button>
          <button type="button" onClick={onRefresh} disabled={loading}>
            <RefreshCw size={15} aria-hidden="true" /> Aggiorna
          </button>
        </div>
      </header>
      {error ? <div className="iu-docai-message iu-docai-message--error" role="alert"><AlertTriangle size={16} aria-hidden="true" /> {error}</div> : null}
      {message ? <div className="iu-docai-message iu-docai-message--success"><FileCheck2 size={16} aria-hidden="true" /> {message}</div> : null}
      <div className="iu-docai-forensic__grid">
        <div className="iu-docai-forensic__list">
          {loading ? <p className="iu-docai-muted">Aggiornamento documenti forensi...</p> : null}
          {!loading && !documents.length ? <p className="iu-docai-muted">Nessun documento forense acquisito per questo fascicolo.</p> : null}
          {documents.slice(0, 12).map((document) => (
            <button
              key={document.id}
              type="button"
              className={selected?.id === document.id ? 'is-selected' : ''}
              onClick={() => onOpen(document)}
            >
              <strong>{document.original_filename}</strong>
              <span>{document.source_type} · {formatDocumentAISize(document.file_size)} · {shortSha(document.sha256)}</span>
              <span>
                <Badge tone={document.security_status === 'validated' ? 'success' : 'warning'}>{document.security_status === 'validated' ? 'sicuro' : 'revisione'}</Badge>
                <Badge tone={document.status === 'validated' ? 'success' : document.status === 'needs_review' ? 'warning' : 'neutral'}>{labelStatus(document.status)}</Badge>
              </span>
            </button>
          ))}
        </div>
        <aside className="iu-docai-forensic__detail">
          {!selected ? <p className="iu-docai-muted">Apri un documento per vedere classificazione, campi estratti, eventi e albero allegati.</p> : null}
          {selected ? (
            <>
              <div className="iu-docai-forensic__title">
                <div>
                  <strong>{selected.original_filename}</strong>
                  <small>{formatDocumentAIDate(selected.created_at)} · {selected.mime_type}</small>
                </div>
                <Badge tone={selectedLex === 'completed' ? 'success' : 'neutral'}>{selectedLex === 'completed' ? 'in Lex' : 'fuori Lex'}</Badge>
              </div>
              <dl className="iu-docai-kv">
                <div><dt>Classificazione</dt><dd>{String(evidence?.classification?.document_type || 'Da verificare')}</dd></div>
                <div><dt>Validazione</dt><dd>{labelStatus(selectedValidation)}</dd></div>
                <div><dt>Fascicolo</dt><dd>{String(evidence?.case_match?.status || 'Da associare')}</dd></div>
                <div><dt>Catena prova</dt><dd>{evidence?.hash_chain?.length || 0} passaggi</dd></div>
              </dl>
              <div className="iu-docai-forensic__badges">
                <Badge tone={evidence?.events?.length ? 'warning' : 'neutral'}>{evidence?.events?.length || 0} eventi proposti</Badge>
                <Badge tone={evidence?.entities?.length ? 'success' : 'neutral'}>{evidence?.entities?.length || 0} dati estratti</Badge>
                <Badge tone={tree?.children?.length ? 'warning' : 'neutral'}><Archive size={12} aria-hidden="true" /> {tree?.children?.length || 0} allegati</Badge>
              </div>
              <ArchiveTreeView nodes={tree?.children || []} />
              <div className="iu-docai-forensic__actions">
                <button type="button" onClick={onApprove}><ShieldCheck size={15} aria-hidden="true" /> Approva</button>
                <button type="button" onClick={onProofBundle}><Archive size={15} aria-hidden="true" /> Pacchetto prova</button>
              </div>
            </>
          ) : null}
        </aside>
      </div>
    </section>
  )
}

function ArchiveTreeView({ nodes }:{nodes: LegalDocumentTree['children']}) {
  if (!nodes.length) return null
  return (
    <ul className="iu-docai-tree">
      {nodes.map((node, index) => (
        <li key={`${node.document?.id || index}`}>
          <span>{node.document?.original_filename || 'Allegato'} <small>{labelStatus(String(node.document?.status || ''))}</small></span>
          <ArchiveTreeView nodes={node.children || []} />
        </li>
      ))}
    </ul>
  )
}

function labelStatus(value: string): string {
  const labels: Record<string, string> = {
    validated: 'validato',
    valid: 'validato',
    acquired: 'acquisito',
    needs_review: 'da rivedere',
    rejected: 'rifiutato',
    unsafe_file: 'bloccato',
    unreadable_document: 'non leggibile',
    completed: 'completato',
    blocked: 'bloccato',
  }
  return labels[value] || value || 'n.d.'
}
