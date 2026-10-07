import type { SourceCandidate } from '../sourceEvidenceData'
import './SourceAlternatives.css'

export function SourceAlternatives({ candidates, onOpen }: { candidates: SourceCandidate[]; onOpen: (candidate: SourceCandidate) => void }) {
  return <details className="iu-source-alternatives">
    <summary>Confronta {candidates.length === 1 ? 'la fonte storica' : `${candidates.length} fonti storiche`}</summary>
    <p>Il collegamento al procedimento non è univoco. Consulta gli originali prima di utilizzare queste informazioni.</p>
    <ul>{candidates.map((source, index) => <li key={source.href}><button type="button" onClick={() => onOpen(source)} aria-label={`Visualizza fonte storica ${index + 1}: ${source.label}`}>{index + 1}. {source.label}</button></li>)}</ul>
  </details>
}
