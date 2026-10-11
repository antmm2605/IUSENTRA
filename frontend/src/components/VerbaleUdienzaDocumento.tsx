import { useRef, useState } from 'react'
import { FileText, LoaderCircle } from 'lucide-react'
import { apiPostJson } from '../api/client'
import type { SchedaUdienza } from './preparazioneUdienzaTipi'
import type { Azioni } from './PreparazioneUdienzaPassi'

type Intento = { titolo: string; html: string; command_id: string }
const escape = (value: string) => value.replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]!))

export function VerbaleUdienzaDocumento({ scheda: s, azioni: a }: { scheda: SchedaUdienza; azioni: Azioni }) {
  const [occupato, setOccupato] = useState(false)
  const [errore, setErrore] = useState('')
  const [editor, setEditor] = useState('')
  const inCorso = useRef(false)
  const fascicolo = s.causa.fascicolo.id || ''
  const scope = s.writeProtocol?.scope || ''
  const key = `iusentra:verbale-documento:${scope}:${s.id}`
  const crea = async () => {
    if (inCorso.current || !fascicolo || !scope) return
    inCorso.current = true
    setOccupato(true)
    setErrore('')
    try {
      const stored = sessionStorage.getItem(key)
      let intent: Intento
      if (stored) {
        intent = JSON.parse(stored)
        if (!intent || typeof intent.html !== 'string' || typeof intent.titolo !== 'string' || !/^[a-f0-9-]{36}$/.test(intent.command_id)) throw new Error('Richiesta conservata non valida: bozza preservata.')
      } else {
        const testo = String(s.campi.verbale_preparazione || '')
        if (!testo.trim()) throw new Error('Scrivi la bozza del verbale prima di creare il documento.')
        const saved = await a.salvaCampi(3, { verbale_preparazione: testo })
        if (saved !== 'saved') throw new Error('Attendi la conferma del salvataggio della bozza prima di creare il documento.')
        intent = { titolo: `Preparazione verbale udienza ${s.id}`.slice(0, 100), command_id: crypto.randomUUID(),
          html: `<h1>Preparazione del verbale di udienza</h1><p>${escape(s.causa.fascicolo.etichetta || '')}</p><p>${escape(s.udienza.ufficio)}</p>${testo.split(/\r?\n/).map(line => `<p>${escape(line) || '<br>'}</p>`).join('')}` }
        sessionStorage.setItem(key, JSON.stringify(intent))
      }
      const result = await apiPostJson<Record<string, unknown>>(`/api/editor/${encodeURIComponent(fascicolo)}/nuovo`, { ...intent, preparazione_id: s.id },
        { ok: false, message: 'Creazione non confermata. Riprova per recuperare la stessa richiesta.' },
        { activity: 'Preparazione del documento…', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      if (result.ok !== true) throw new Error(String(result.message || result.errore || 'Creazione non confermata.'))
      if (typeof result.document_id !== 'string' || !/^[A-Za-z0-9_-]+$/.test(result.document_id)) throw new Error('Documento senza riferimento valido: recupera la stessa richiesta.')
      setEditor(`/fascicoli/${encodeURIComponent(fascicolo)}/documenti/${encodeURIComponent(result.document_id)}/editor`)
      // Conservare l'intento consente di riaprire lo stesso documento dopo
      // un cambio di passo o il ricaricamento, senza crearne un duplicato.
    } catch (error) { setErrore(error instanceof Error ? error.message : 'Creazione non confermata. Riprova.') }
    finally { inCorso.current = false; setOccupato(false) }
  }
  const href = s.verbaleDocumento?.href || editor
  const problema = s.verbaleDocumento?.message || ''
  return <div>
    {href ? <a href={href} target="_blank" rel="noreferrer"><FileText size={15}/> Apri il verbale nell’editor</a>
      : <button type="button" disabled={Boolean(problema) || !a.puoModificare || a.occupato || occupato || !fascicolo || !scope} onClick={() => void crea()}>
        {occupato ? <LoaderCircle size={15} className="animate-spin"/> : <FileText size={15}/>} {occupato ? 'Preparazione del documento…' : 'Crea documento del verbale'}
      </button>}
    {errore ? <p role="alert">{errore}</p> : null}
    {problema ? <p role="alert">{problema}</p> : null}
  </div>
}
