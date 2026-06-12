import { useEffect, useRef, useState } from 'react'
import { Square, Volume2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { confidenceLabel, statusLabel, type PceCard } from './procedureCompletionData'

function testoLettura(card: PceCard): string {
  const parti: string[] = ['Voce generata da intelligenza artificiale.']
  if (card.confidence !== 'HIGH') {
    parti.push(
      'Attenzione: scheda con affidabilità documentale non alta. Verificare le fonti ufficiali prima di ogni uso.',
    )
  }
  if (card.status !== 'published') {
    parti.push('Questa scheda è una bozza per revisione avvocato.')
  }
  parti.push(`Scheda della procedura ${card.denominazione || card.codice}.`)
  if (card.categoria) parti.push(`Categoria: ${card.categoria}.`)
  if (card.rito) parti.push(`Rito: ${card.rito}.`)
  if (card.competenza) parti.push(`Competenza: ${card.competenza}.`)
  if (card.articoli_rilevanti.length) {
    parti.push(`Articoli rilevanti: ${card.articoli_rilevanti.slice(0, 8).join('; ')}.`)
  }
  if (card.guida_pratica.length) {
    parti.push(`Guida pratica: ${card.guida_pratica.slice(0, 5).join('. ')}.`)
  }
  if (card.ricevute_attese.length) {
    parti.push(`Ricevute attese dal deposito telematico: ${card.ricevute_attese.join('; ')}.`)
  }
  const bloccanti = card.gap_evidenza.filter((gap) => gap.severita === 'blocking')
  if (bloccanti.length) {
    parti.push(`Gap bloccanti aperti: ${bloccanti.map((gap) => gap.descrizione).join('; ')}.`)
  }
  parti.push('Fine della lettura. Le fonti complete sono consultabili nella scheda.')
  return parti.join(' ')
}

export function ProcedureCompletionVoiceReadPanel({
  card,
  enabled,
  localOnly,
}: {
  card: PceCard
  enabled: boolean
  localOnly: boolean
}) {
  const [reading, setReading] = useState(false)
  const [supportato, setSupportato] = useState(true)
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null)

  useEffect(() => {
    setSupportato(typeof window !== 'undefined' && 'speechSynthesis' in window)
    return () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel()
    }
  }, [])

  if (!enabled) return null

  const avvia = () => {
    if (!supportato) return
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(testoLettura(card))
    utterance.lang = 'it-IT'
    utterance.rate = 0.95
    utterance.onend = () => setReading(false)
    utterance.onerror = () => setReading(false)
    utteranceRef.current = utterance
    setReading(true)
    window.speechSynthesis.speak(utterance)
  }

  const ferma = () => {
    window.speechSynthesis.cancel()
    setReading(false)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="pce-panel-title">
          <Volume2 size={18} aria-hidden="true" />
          Lettura vocale della scheda
        </CardTitle>
      </CardHeader>
      <CardContent className="pce-stack">
        <div className="pce-row">
          <Badge variant="outline">Voce generata da AI</Badge>
          {localOnly ? <Badge variant="secondary">Solo sintesi vocale locale</Badge> : null}
          <Badge variant={card.confidence === 'HIGH' ? 'default' : 'secondary'}>{confidenceLabel(card.confidence)}</Badge>
        </div>
        <p className="pce-hint">
          La lettura usa la sintesi vocale del dispositivo (nessun provider esterno, nessuna imitazione di voci reali)
          e include sempre stato «{statusLabel(card.status)}» e avvertenze quando l'affidabilità non è alta.
          Non vengono letti dati personali non necessari.
        </p>
        {!supportato ? (
          <p className="pce-validation__warning">Sintesi vocale non disponibile su questo dispositivo.</p>
        ) : (
          <div className="pce-actions">
            {!reading ? (
              <Button type="button" onClick={avvia}>
                <Volume2 size={14} aria-hidden="true" /> Leggi la scheda
              </Button>
            ) : (
              <Button type="button" variant="secondary" onClick={ferma}>
                <Square size={14} aria-hidden="true" /> Interrompi lettura
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
