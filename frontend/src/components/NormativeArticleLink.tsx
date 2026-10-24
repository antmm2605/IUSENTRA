import { useState, type ReactNode } from 'react'
import { SourceDocumentModal, type SourceDocument } from './SourceDocumentModal'
import { articleNumbers, normativeReaderHref } from '../normativeArticleLinks'

/** Un solo comando per leggere la disposizione in tutte le superfici normative. */
export function NormativeArticleLink({ url, article = '', act = '', articleId = 0, sha = '', label = 'Testo ufficiale', children, className }: { url: string; article?: string; act?: string; articleId?: number; sha?: string; label?: string; children?: ReactNode; className?: string }) {
  const [source, setSource] = useState<SourceDocument | null>(null)
  const numbers = articleNumbers(article)
  const refs = numbers.length ? numbers : ['']
  return <>{refs.map((number, index) => {
    const href = normativeReaderHref({ url, article: number, act, id: articleId, sha })
    let safeURL = ''
    try { const parsed = new URL(url); if (parsed.protocol === 'https:' && !parsed.username && !parsed.password) safeURL = parsed.href } catch { /* Fonte non navigabile: non costruire schemi arbitrari. */ }
    const title = `${label}${number ? ` · art. ${number}` : ''}`
    return <span key={number || 'atto'}>{index ? ' · ' : ''}<a className={className} href={href || safeURL || undefined} target="_blank" rel="noopener noreferrer"
      onClick={event => { if (!href || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return; event.preventDefault(); setSource({ href, label: title, context: act || article, kind: 'normativa' }) }}>
      {children || label}{refs.length > 1 ? ` · art. ${number}` : ''}</a></span>
  })}<SourceDocumentModal source={source} onClose={() => setSource(null)} /></>
}
