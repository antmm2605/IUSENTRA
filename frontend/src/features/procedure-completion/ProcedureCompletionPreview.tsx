import { useState, type FormEvent } from 'react'
import { WandSparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { postPcePreview, type PceCard, type PceValidation } from './procedureCompletionData'

export function ProcedureCompletionPreview({
  onCreated,
  canRun,
}: {
  onCreated: (esito: { card: PceCard; validation: PceValidation | null }) => void
  canRun: boolean
}) {
  const [codice, setCodice] = useState('')
  const [denominazione, setDenominazione] = useState('')
  const [categoria, setCategoria] = useState('')
  const [rito, setRito] = useState('')
  const [competenza, setCompetenza] = useState('')
  const [busy, setBusy] = useState(false)
  const [errore, setErrore] = useState('')

  const submit = (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setErrore('')
    postPcePreview({ codice, denominazione, categoria, rito, competenza })
      .then((esito) => {
        if (esito.ok && esito.card) onCreated({ card: esito.card, validation: esito.validation })
        else setErrore(esito.errore || 'Anteprima non completata.')
      })
      .finally(() => setBusy(false))
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="pce-panel-title">
          <WandSparkles size={18} aria-hidden="true" />
          Nuova anteprima scheda procedura
        </CardTitle>
      </CardHeader>
      <CardContent>
        {!canRun ? (
          <p className="pce-hint">Permesso «procedure_completion.esegui» richiesto per generare anteprime.</p>
        ) : (
          <form className="pce-form" onSubmit={submit}>
            <label className="pce-field">
              <span>Codice oggetto PST</span>
              <input value={codice} onChange={(event) => setCodice(event.target.value)} placeholder="es. 010003" />
            </label>
            <label className="pce-field">
              <span>Denominazione</span>
              <input
                value={denominazione}
                onChange={(event) => setDenominazione(event.target.value)}
                placeholder="es. Procedimento di ingiunzione ante causam"
              />
            </label>
            <label className="pce-field">
              <span>Categoria</span>
              <input value={categoria} onChange={(event) => setCategoria(event.target.value)} />
            </label>
            <label className="pce-field">
              <span>Rito</span>
              <input value={rito} onChange={(event) => setRito(event.target.value)} />
            </label>
            <label className="pce-field">
              <span>Competenza</span>
              <input value={competenza} onChange={(event) => setCompetenza(event.target.value)} />
            </label>
            {errore ? <p className="pce-validation__error" role="alert">{errore}</p> : null}
            <div className="pce-actions">
              <Button type="submit" disabled={busy}>
                {busy ? 'Generazione anteprima...' : 'Genera anteprima governata'}
              </Button>
            </div>
            <p className="pce-hint">
              L'input non è trattato come verità giuridica: la scheda nasce dal catalogo ministeriale e dalle fonti
              governate, con gap dichiarati per ogni dato mancante.
            </p>
          </form>
        )}
      </CardContent>
    </Card>
  )
}
