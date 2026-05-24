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
  LegalOcrReview,
} from '../documentiAiData'
import {
  applyLegalOcrFix,
  approveLegalDocument,
  createLegalDocumentProofBundle,
  fetchDocumentAIDetail,
  fetchDocumentAIList,
  fetchDocumentAIText,
  fetchLegalDocumentEvidence,
  fetchLegalDocuments,
  fetchLegalDocumentTree,
  fetchLegalOcrReview,
  formatDocumentAIDate,
  formatDocumentAISize,
  requestFascicoloLexIndex,
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
  const [ocrReview, setOcrReview] = useState<LegalOcrReview | null>(null)
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
    setOcrReview(null)
    setLegalError('')
    try {
      const [evidencePayload, treePayload, reviewPayload] = await Promise.all([
        fetchLegalDocumentEvidence(document.id),
        fetchLegalDocumentTree(document.id),
        fetchLegalOcrReview(document.id),
      ])
      setLegalEvidence(evidencePayload.data)
      setLegalTree(treePayload.data)
      setOcrReview('run_id' in reviewPayload.data ? reviewPayload.data as LegalOcrReview : null)
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

  const refreshFascicoloLex = async () => {
    setLegalMessage('')
    setLegalError('')
    try {
      const result = await requestFascicoloLexIndex(fascicoloId)
      const included = Array.isArray(result.data?.included) ? result.data.included.length : 0
      const skipped = Array.isArray(result.data?.skipped) ? result.data.skipped.length : 0
      setLegalMessage(`Lex aggiornato con ${included} documenti validati. Esclusi ${skipped} documenti da verificare.`)
      await loadLegalDocuments()
    } catch (actionError) {
      setLegalError(actionError instanceof Error ? actionError.message : 'Aggiornamento Lex non completato.')
    }
  }

  const applyOcrFix = async (fix: Record<string, string>) => {
    if (!selectedLegal) return
    setLegalMessage('')
    setLegalError('')
    try {
      const result = await applyLegalOcrFix(selectedLegal.id, fix)
      setOcrReview(result.data.review)
      setLegalMessage('Correzione registrata nella storia di revisione OCR.')
    } catch (actionError) {
      setLegalError(actionError instanceof Error ? actionError.message : 'Correzione OCR non registrata.')
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
        ocrReview={ocrReview}
        loading={legalLoading}
        error={legalError}
        message={legalMessage}
        onRefresh={loadLegalDocuments}
        onRefreshLex={refreshFascicoloLex}
        onOpen={openLegalDocument}
        onUpload={uploadForensicDocument}
        onApprove={approveSelectedLegal}
        onProofBundle={exportSelectedProof}
        onApplyOcrFix={applyOcrFix}
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
  ocrReview,
  loading,
  error,
  message,
  onRefresh,
  onRefreshLex,
  onOpen,
  onUpload,
  onApprove,
  onProofBundle,
  onApplyOcrFix,
}:{
  documents: LegalDocumentRecord[]
  selected: LegalDocumentRecord | null
  evidence: LegalDocumentEvidence | null
  tree: LegalDocumentTree | null
  ocrReview: LegalOcrReview | null
  loading: boolean
  error: string
  message: string
  onRefresh: () => void
  onRefreshLex: () => void
  onOpen: (document: LegalDocumentRecord) => void
  onUpload: (file: File) => void
  onApprove: () => void
  onProofBundle: () => void
  onApplyOcrFix: (fix: Record<string, string>) => void
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
          <button type="button" onClick={onRefreshLex}>
            <BrainCircuit size={15} aria-hidden="true" /> Aggiorna Lex
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
              <OcrReviewPanel review={ocrReview} onApplyFix={onApplyOcrFix} />
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

function OcrReviewPanel({ review, onApplyFix }:{review: LegalOcrReview | null; onApplyFix: (fix: Record<string, string>) => void}) {
  if (!review?.run_id) return null
  const metrics = review.metrics || {}
  const qc = review.qc || {}
  const hilRequired = Boolean(qc.hil_required)
  return (
    <section className="iu-docai-ocr-review" aria-label="Revisione OCR">
      <header>
        <div>
          <span><FileCheck2 size={14} aria-hidden="true" /> Revisione OCR</span>
          <strong>{hilRequired ? 'Controllo umano richiesto' : 'Lettura affidabile'}</strong>
        </div>
        <Badge tone={hilRequired ? 'warning' : 'success'}>
          confidenza {formatPercentLike(metrics.avg_confidence)}
        </Badge>
      </header>
      <div className="iu-docai-ocr-review__metrics">
        <span>Token bassi {formatPercentLike(metrics['pct_tokens_<0.75'])}</span>
        <span>Campi {review.mandatory_fields.filter((field) => String(field.status || '') === 'ok').length}/{review.mandatory_fields.length}</span>
        <span>Fragili Lex {String(review.lex_export?.fragile_count ?? 0)}</span>
      </div>
      {review.mandatory_fields.length ? (
        <div className="iu-docai-ocr-review__fields">
          {review.mandatory_fields.map((field, index) => (
            <span key={`${String(field.id || 'campo')}-${index}`} className={String(field.status || '') === 'ok' ? 'is-ok' : 'is-ko'}>
              {labelMandatoryField(String(field.id || 'campo'))}: {String(field.value || field.status || 'da verificare')}
            </span>
          ))}
        </div>
      ) : null}
      {review.low_tokens.length ? (
        <div className="iu-docai-ocr-review__tokens">
          {review.low_tokens.slice(0, 24).map((token, index) => (
            <mark key={`${token.token}-${index}`} title={`Confidenza ${formatPercentLike(token.confidence)}`}>
              {token.token}
            </mark>
          ))}
        </div>
      ) : null}
      {review.suggested_fixes.length ? (
        <div className="iu-docai-ocr-review__fixes">
          {review.suggested_fixes.slice(0, 6).map((fix) => (
            <button key={`${fix.rule_id}-${fix.from}-${fix.to}`} type="button" onClick={() => onApplyFix(fix)}>
              Applica {fix.to}
            </button>
          ))}
        </div>
      ) : null}
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

function formatPercentLike(value: unknown): string {
  const number = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(number)) return 'n.d.'
  const normalized = number <= 1 ? number * 100 : number
  return `${new Intl.NumberFormat('it-IT', { maximumFractionDigits: 1 }).format(normalized)}%`
}

function labelMandatoryField(value: string): string {
  const labels: Record<string, string> = {
    cf_avvocato: 'Codice fiscale',
    codice_fiscale: 'Codice fiscale',
    n_rg: 'Numero RG',
    pec: 'PEC',
    date: 'Date',
    importi: 'Importi',
  }
  return labels[value] || value.replaceAll('_', ' ')
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
