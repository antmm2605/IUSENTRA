import { useEffect, useState } from 'react'
import { apiJson } from '../../lib/apiClient'
import { normaliseScheda, type RedazioneScheda } from '../../redazioneAttiData'
import { SchedaCompilazionePanel } from './SchedaCompilazionePanel'

export default function TemplateCompilationGuide({ templateId }: { templateId: string }) {
  const [state, setState] = useState<{ scheda?: RedazioneScheda; error?: string }>({})
  useEffect(() => {
    let active = true
    const controller = new AbortController()
    setState({})
    apiJson<{ compilazione: unknown }>(`/api/v1/ui/template-atti/catalogo/${encodeURIComponent(templateId)}/scheda-compilazione`, { compilazione: null }, { signal: controller.signal })
      .then((result) => {
        const scheda = normaliseScheda(result.compilazione)
        if (active) setState(scheda ? { scheda } : { error: 'Scheda di compilazione non disponibile.' })
      })
      .catch(() => { if (active) setState({ error: 'Non è stato possibile caricare la scheda di compilazione.' }) })
    return () => { active = false; controller.abort() }
  }, [templateId])
  if (state.error) return <p role="alert">{state.error}</p>
  if (!state.scheda) return null
  return <div>
    <p>Requisiti del modello. Nessun fascicolo selezionato: i dati disponibili saranno verificati nella redazione guidata.</p>
    <SchedaCompilazionePanel scheda={state.scheda} />
  </div>
}
