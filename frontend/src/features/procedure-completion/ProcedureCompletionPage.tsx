import { useCallback, useEffect, useState } from 'react'
import { BookOpenCheck } from 'lucide-react'
import { IusErrorState, IusLoadingState, IusPageShell } from '@/components/iusentra'
import { ProcedureCompletionCardDetail } from './ProcedureCompletionCardDetail'
import { ProcedureCompletionDashboard } from './ProcedureCompletionDashboard'
import {
  getPceCard,
  getPceDashboard,
  type PceCard,
  type PceDashboard,
  type PceValidation,
} from './procedureCompletionData'
import './procedure-completion.css'

export function ProcedureCompletionPage() {
  const [dashboard, setDashboard] = useState<PceDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [card, setCard] = useState<PceCard | null>(null)
  const [validation, setValidation] = useState<PceValidation | null>(null)

  const loadDashboard = useCallback(() => {
    setLoading(true)
    getPceDashboard()
      .then(setDashboard)
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    loadDashboard()
  }, [loadDashboard])

  const openCard = (cardId: string) => {
    setLoading(true)
    getPceCard(cardId)
      .then((esito) => {
        if (esito.ok && esito.card) {
          setCard(esito.card)
          setValidation(esito.validation)
        }
      })
      .finally(() => setLoading(false))
  }

  if (loading && !dashboard) {
    return <IusLoadingState title="Caricamento schede procedura" />
  }
  if (!dashboard || !dashboard.ok) {
    return (
      <IusErrorState
        title="Procedure Completion non disponibile"
        message={dashboard?.errore || 'Funzione non attiva per questo studio o permessi mancanti.'}
      />
    )
  }

  return (
    <IusPageShell
      title="Schede procedura governate"
      description="Completamento delle schede operative da catalogo ministeriale, template e fonti ufficiali: ogni scheda resta una bozza per revisione avvocato finché non pubblicata."
      area="lex"
      icon={BookOpenCheck}
    >
      <div className="pce-page">
        {card ? (
          <ProcedureCompletionCardDetail
            card={card}
            validation={validation}
            dashboard={dashboard}
            onBack={() => {
              setCard(null)
              setValidation(null)
              loadDashboard()
            }}
            onUpdated={(esito) => {
              if (esito.card) setCard(esito.card)
              if (esito.validation) setValidation(esito.validation)
            }}
          />
        ) : (
          <ProcedureCompletionDashboard
            dashboard={dashboard}
            onOpenCard={openCard}
            onPreviewCreated={(esito) => {
              setCard(esito.card)
              setValidation(esito.validation)
            }}
          />
        )}
      </div>
    </IusPageShell>
  )
}

export default ProcedureCompletionPage
