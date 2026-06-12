import { ArrowLeft, BookOpenCheck, ListChecks, ScrollText } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ProcedureCompletionGapsPanel } from './ProcedureCompletionGapsPanel'
import { ProcedureCompletionReviewPanel } from './ProcedureCompletionReviewPanel'
import { ProcedureCompletionSourcesPanel } from './ProcedureCompletionSourcesPanel'
import { ProcedureCompletionTemplateFusionPanel } from './ProcedureCompletionTemplateFusionPanel'
import { ProcedureCompletionVoiceReadPanel } from './ProcedureCompletionVoiceReadPanel'
import {
  confidenceLabel,
  statusLabel,
  type PceCard,
  type PceDashboard,
  type PceValidation,
} from './procedureCompletionData'

function Fact({ label, value }: { label: string; value: string }) {
  if (!value) return null
  return (
    <div className="pce-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function ElencoConFonte({ titolo, voci }: { titolo: string; voci: Array<Record<string, string>> }) {
  if (!voci.length) return null
  return (
    <div>
      <h4 className="pce-subtitle">{titolo}</h4>
      <ul className="pce-fact-list">
        {voci.map((voce, indice) => {
          const testo = voce.termine || voce.adempimento || voce.allegato || voce.condizione || Object.values(voce)[0] || ''
          const fonte = voce.base_normativa || voce.fonte || voce.fonte_id || voce.evidenza || ''
          return (
            <li key={`${titolo}-${indice}`}>
              <span>{testo}</span>
              {fonte ? <Badge variant="outline">{fonte}</Badge> : <Badge variant="secondary">Fonte da verificare</Badge>}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export function ProcedureCompletionCardDetail({
  card,
  validation,
  dashboard,
  onBack,
  onUpdated,
}: {
  card: PceCard
  validation: PceValidation | null
  dashboard: PceDashboard
  onBack: () => void
  onUpdated: (esito: { card: PceCard | null; validation: PceValidation | null }) => void
}) {
  return (
    <div className="pce-stack-lg">
      <div className="pce-detail-head">
        <Button type="button" variant="ghost" onClick={onBack}>
          <ArrowLeft size={14} aria-hidden="true" /> Torna alle schede
        </Button>
        {card.status !== 'published' ? (
          <p className="pce-draft-banner" role="status">Bozza per revisione avvocato</p>
        ) : null}
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="pce-panel-title">
            <BookOpenCheck size={18} aria-hidden="true" />
            {card.denominazione || card.codice}
          </CardTitle>
        </CardHeader>
        <CardContent className="pce-stack">
          <div className="pce-row">
            <Badge variant={card.status === 'published' ? 'default' : 'secondary'}>{statusLabel(card.status)}</Badge>
            <Badge variant="outline">{confidenceLabel(card.confidence)}</Badge>
            <Badge variant="outline">Non è una certezza legale</Badge>
          </div>
          {card.avvertimenti_obbligatori.map((avviso) => (
            <p className="pce-warning" key={avviso}>{avviso}</p>
          ))}
          <div className="pce-grid">
            <Fact label="Codice oggetto" value={card.codice} />
            <Fact label="Categoria" value={card.categoria} />
            <Fact label="Rito" value={card.rito} />
            <Fact label="Competenza" value={card.competenza} />
            <Fact label="Fonte catalogo" value={card.fonte_catalogo.catalogo ? `${card.fonte_catalogo.catalogo} - ${card.fonte_catalogo.descrizione || ''}` : ''} />
            <Fact label="Uffici destinatari" value={card.uffici_destinatari.join(', ')} />
          </div>
          {card.articoli_rilevanti.length ? (
            <div>
              <h4 className="pce-subtitle">Articoli rilevanti</h4>
              <div className="pce-row pce-row--wrap">
                {card.articoli_rilevanti.map((articolo) => (
                  <Badge key={articolo} variant="secondary">{articolo}</Badge>
                ))}
              </div>
            </div>
          ) : null}
          {card.sintesi_articoli.length ? (
            <div>
              <h4 className="pce-subtitle">Sintesi documentali (dalle fonti collegate)</h4>
              <ul className="pce-fact-list">
                {card.sintesi_articoli.slice(0, 8).map((voce) => (
                  <li key={voce.riferimento}>
                    <Badge variant="outline">{voce.riferimento}</Badge>
                    <span>{voce.sintesi}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {card.guida_pratica.length ? (
            <div>
              <h4 className="pce-subtitle">Guida pratica</h4>
              <ul className="pce-plain-list">
                {card.guida_pratica.map((voce) => <li key={voce}>{voce}</li>)}
              </ul>
            </div>
          ) : null}
          <ElencoConFonte titolo="Condizioni di procedibilità" voci={card.condizioni_procedibilita} />
          <ElencoConFonte titolo="Termini processuali" voci={card.termini_processuali} />
          <ElencoConFonte titolo="Adempimenti fiscali" voci={card.adempimenti_fiscali} />
          <ElencoConFonte titolo="Allegati obbligatori" voci={card.allegati_obbligatori} />
          {card.rischi_operativi.length ? (
            <div>
              <h4 className="pce-subtitle">Rischi operativi</h4>
              <ul className="pce-plain-list">
                {card.rischi_operativi.map((voce) => <li key={voce}>{voce}</li>)}
              </ul>
            </div>
          ) : null}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="pce-panel-title">
            <ListChecks size={18} aria-hidden="true" />
            Ciclo di vita e telematico
          </CardTitle>
        </CardHeader>
        <CardContent className="pce-stack">
          {card.lifecycle_steps.length ? (
            <ol className="pce-lifecycle">
              {card.lifecycle_steps.map((step) => (
                <li key={`${step.ordine}-${step.step}`}>{step.label || step.step}</li>
              ))}
            </ol>
          ) : (
            <p className="pce-empty">Passi del ciclo di vita non generati per questa procedura.</p>
          )}
          <div className="pce-grid">
            <Fact
              label="Firma digitale"
              value={card.firma_digitale.richiesta ? `Richiesta (${String(card.firma_digitale.base_normativa || '')})` : ''}
            />
            <Fact
              label="Deposito telematico"
              value={card.deposito_telematico.canale ? `${String(card.deposito_telematico.canale)} (${String(card.deposito_telematico.base_normativa || '')})` : ''}
            />
            <Fact label="Ricevute attese" value={card.ricevute_attese.join('; ')} />
            <Fact label="Notifiche" value={String(card.notifiche.modalita || '')} />
            <Fact
              label="Prova notifica"
              value={Array.isArray(card.prova_notifica.elementi) ? (card.prova_notifica.elementi as string[]).join('; ') : ''}
            />
          </div>
          <p className="pce-hint">
            <ScrollText size={12} aria-hidden="true" /> Le basi normative indicate provengono dalle fonti tecniche del
            catalogo PST: nessun deposito, invio PEC o firma viene eseguito automaticamente.
          </p>
        </CardContent>
      </Card>
      <ProcedureCompletionSourcesPanel sources={card.sources} citations={card.citations} />
      <ProcedureCompletionTemplateFusionPanel card={card} />
      <ProcedureCompletionGapsPanel gaps={card.gap_evidenza} />
      <ProcedureCompletionReviewPanel
        card={card}
        validation={validation}
        permissions={dashboard.permissions}
        onUpdated={onUpdated}
      />
      <ProcedureCompletionVoiceReadPanel
        card={card}
        enabled={dashboard.flags.voiceRead}
        localOnly={dashboard.flags.voiceReadLocalOnly}
      />
    </div>
  )
}
