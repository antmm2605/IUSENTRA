import { lazy, Suspense, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { CalendarClock } from 'lucide-react'
import { getAgendaPage, type AgendaEvent } from '../agendaData'
import { OperationalModal } from './OperationalModal'
import { AgendaFocus } from './AgendaPage'
import { SourceDocumentModal, type SourceDocument } from './SourceDocumentModal'
import { inviaPreparazione } from './preparazioneUdienzaApi'
import { FascicoloSearchSelect } from './FascicoloSearchSelect'
import type { Azione, Voce } from './ControlloStudioPage'
import './ControlloStudioContext.css'
const Preparazione = lazy(() => import('./WizardProStepPage'))

type Sessione = { id: string; passo: number }
export default function ControlloStudioAgendaDetail({ voce, azione, onClose, onUpdated, focusToken }: {
  voce: Voce; azione?: Azione; focusToken?: number; onClose: () => void; onUpdated: () => void
}) {
  const [event, setEvent] = useState<AgendaEvent | null>(null)
  const [sessione, setSessione] = useState<Sessione | null>(null)
  const [source, setSource] = useState<SourceDocument | null>(null)
  const [errore, setErrore] = useState('')
  const [loading, setLoading] = useState(true)
  const [scelta, setScelta] = useState('')
  const [fascicoli, setFascicoli] = useState<Array<{ value: string; label: string }>>([])
  const [canWrite, setCanWrite] = useState(false)
  const prepara = Boolean(azione?.href.includes('/wizard-pro/'))
  const href = azione?.href || ''
  const applySession = (redirect: string) => {
    const match = redirect.match(/\/wizard-pro\/([^/]+)\/step\/([1-5])/)
    if (!match) throw new Error('La preparazione non ha restituito una sessione valida.')
    setSessione({ id: decodeURIComponent(match[1]), passo: Number(match[2]) })
  }
  useEffect(() => {
    let active = true
    const load = async () => {
      setLoading(true); setErrore('')
      try {
        if (!prepara) {
          const page = await getAgendaPage(new Date(`${voce.data}T12:00:00`), 'day')
          const found = page.events.find(e => e.id === voce.id.replace(/^agenda-/, ''))
          if (!found) throw new Error('L’impegno selezionato non è disponibile. Aggiorna il quadro dello studio.')
          if (active) setEvent(found)
        } else if (/\/wizard-pro\/[^/]+\/step\//.test(href)) {
          if (active) applySession(href)
        } else {
          const response = await fetch('/api/v1/ui/preparazione-udienza', { credentials: 'same-origin' })
          const data = await response.json()
          if (!response.ok || !data.ok) throw new Error(data.message || 'Preparazione non disponibile.')
          const found = (data.udienze || []).find((u: { idAppuntamento: string }) => u.idAppuntamento === voce.id.replace(/^agenda-/, ''))
          if (!found) throw new Error('L’udienza selezionata non è disponibile per la preparazione.')
          if (!active) return
          setFascicoli(data.fascicoli || []); setCanWrite(Boolean(data.puoModificare))
          if (found.href) applySession(found.href)
          else if (data.puoModificare && (found.idFascicolo || voce.fascicolo.id)) {
            const result = await inviaPreparazione('/api/v1/ui/preparazione-udienza/avvia', {
              idAppuntamento: found.idAppuntamento, idFascicolo: found.idFascicolo || voce.fascicolo.id,
            })
            if (!result.ok) throw new Error(String(result.message || 'Preparazione non aperta.'))
            if (active) { applySession(String(result.redirect)); onUpdated() }
          }
        }
      } catch (cause) { if (active) setErrore(cause instanceof Error ? cause.message : 'Apertura non riuscita.') }
      finally { if (active) setLoading(false) }
    }
    void load()
    return () => { active = false }
  }, [voce.id, voce.data, voce.fascicolo.id, prepara, href])
  const avvia = async () => {
    setLoading(true); setErrore('')
    try {
      const result = await inviaPreparazione('/api/v1/ui/preparazione-udienza/avvia', { idAppuntamento: voce.id.replace(/^agenda-/, ''), idFascicolo: scelta })
      if (!result.ok) throw new Error(String(result.message || 'Preparazione non aperta.'))
      applySession(String(result.redirect)); onUpdated()
    } catch (cause) { setErrore(cause instanceof Error ? cause.message : 'Apertura non riuscita.') }
    finally { setLoading(false) }
  }
  return createPortal(<>
    <OperationalModal open focusToken={focusToken} ariaLabel={prepara ? 'Preparazione dell’udienza selezionata' : 'Impegno selezionato in agenda'}
      eyebrow={<><CalendarClock size={15}/> {prepara ? 'Preparazione udienza' : 'Agenda'}</>} title={voce.titolo}
      subtitle={voce.fascicolo.etichetta || voce.dettaglio} onClose={onClose}
      boxClassName="iu-cs-context" bodyClassName="iu-cs-context__body">
      {loading ? <p role="status">Apertura del contesto selezionato…</p> : errore ? <p role="alert">{errore}</p>
        : !prepara && event ? <AgendaFocus event={event} onOpenSource={e => setSource({ href: e.sourceHref, label: e.sourceLabel || e.title, context: voce.fascicolo.etichetta || voce.titolo })}/>
        : sessione ? <Suspense fallback={<p role="status">Caricamento della preparazione…</p>}><Preparazione sessionId={sessione.id} initialStep={sessione.passo} embedded/></Suspense>
        : canWrite ? <section><p>Collega il fascicolo a questa udienza per aprire la sua preparazione.</p>
          <FascicoloSearchSelect options={fascicoli} value={scelta} onChange={setScelta} disabled={loading}/>
          <button type="button" className="iu-button" disabled={!scelta || loading} onClick={() => void avvia()}>Prepara questa udienza</button>
        </section> : <p>La preparazione non è ancora avviata. Serve il permesso di modifica dell’agenda.</p>}
    </OperationalModal>
    <SourceDocumentModal source={source} onClose={() => setSource(null)}/>
  </>, document.body)
}
