import { ExternalLink, Landmark, ShieldAlert } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { PceCitation, PceSource } from './procedureCompletionData'

function trustBadge(source: PceSource) {
  if (source.trust_class === 'A') return <Badge>Fonte primaria (A)</Badge>
  if (source.trust_class === 'B') return <Badge variant="secondary">Fonte istituzionale (B)</Badge>
  return <Badge variant="outline">Fonte non primaria</Badge>
}

export function ProcedureCompletionSourcesPanel({
  sources,
  citations,
}: {
  sources: PceSource[]
  citations: PceCitation[]
}) {
  const nonPrimarie = sources.filter((src) => src.trust_class !== 'A')
  return (
    <Card>
      <CardHeader>
        <CardTitle className="pce-panel-title">
          <Landmark size={18} aria-hidden="true" />
          Fonti e citazioni ({sources.length} fonti, {citations.length} citazioni)
        </CardTitle>
      </CardHeader>
      <CardContent className="pce-stack">
        {nonPrimarie.length ? (
          <p className="pce-warning" role="status">
            <ShieldAlert size={14} aria-hidden="true" />
            {nonPrimarie.length === sources.length
              ? 'Nessuna fonte primaria collegata: i contenuti derivano da fonti tecniche o istituzionali.'
              : 'Alcune fonti non sono primarie o non sono il testo definitivo: verificare su fonte ufficiale.'}
          </p>
        ) : null}
        <ul className="pce-source-list">
          {sources.map((source) => (
            <li key={source.id} className="pce-source">
              <div className="pce-source__head">
                <strong>{source.title || 'Fonte senza titolo'}</strong>
                {trustBadge(source)}
                {source.copyright_policy === 'summary_only' ? (
                  <Badge variant="outline">Solo sintesi</Badge>
                ) : null}
              </div>
              {source.authority ? <small>{source.authority}</small> : null}
              {source.excerpt ? <p className="pce-source__excerpt">{source.excerpt}</p> : null}
              {source.url ? (
                <a href={source.url} target="_blank" rel="noreferrer" className="pce-source__link">
                  <ExternalLink size={12} aria-hidden="true" /> Apri fonte ufficiale
                </a>
              ) : null}
            </li>
          ))}
          {!sources.length ? <li className="pce-empty">Nessuna fonte collegata: scheda non approvabile.</li> : null}
        </ul>
        {citations.length ? (
          <div>
            <h4 className="pce-subtitle">Citazioni puntuali</h4>
            <ul className="pce-citation-list">
              {citations.map((cit) => (
                <li key={cit.id}>
                  <Badge variant="secondary">{cit.riferimento}</Badge>
                  {cit.snippet ? <span className="pce-citation__snippet">{cit.snippet}</span> : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
