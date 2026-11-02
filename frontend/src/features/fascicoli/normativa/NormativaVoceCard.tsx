import { useState } from 'react'
import { ChevronDown, ChevronUp, ExternalLink, FileText } from 'lucide-react'
import { leggiTestoArchivio } from './normativaApi'
import type { NormativaVoce, TestoArchivio } from './types'

/**
 * Una norma del fascicolo: rubrica, estratto ufficiale del registro, motivo, fonte con data di
 * consultazione e collegamento ufficiale in una nuova scheda. Il testo integrale si espande solo
 * se è nell'archivio Normattiva importato da IUSENTRA; altrimenti resta il collegamento.
 */
export function NormativaVoceCard({ voce, fascicoloId }: { voce: NormativaVoce; fascicoloId: string }) {
  const [aperto, setAperto] = useState(false)
  const [testo, setTesto] = useState<TestoArchivio | null>(null)
  const [stato, setStato] = useState<'' | 'caricamento' | 'errore'>('')
  const urn = voce.archivio?.urn || ''
  const articolo = voce.archivio?.articolo || ''

  async function espandi() {
    if (aperto) { setAperto(false); return }
    setAperto(true)
    if (testo || !urn || !articolo) return
    setStato('caricamento')
    try {
      const data = await leggiTestoArchivio(fascicoloId, urn, articolo)
      setTesto(data.testo); setStato('')
    } catch { setStato('errore') }
  }

  return (
    <li className="iu-fas-normativa__voce">
      <div className="iu-fas-normativa__voce-head">
        <strong>{voce.norma}</strong>
        {voce.rubrica ? <span>{voce.rubrica}</span> : null}
      </div>
      {voce.estratto
        ? <blockquote className="iu-fas-normativa__estratto">{voce.estratto}<small>Estratto dal registro delle fonti verificate</small></blockquote>
        : <p className="iu-fas-normativa__nota">Estratto non registrato: il testo si apre su {voce.fonte}.</p>}
      {voce.perche.length ? (
        <ul className="iu-fas-normativa__perche">
          {voce.perche.slice(0, 3).map((motivo) => <li key={motivo}>{motivo}</li>)}
          {voce.perche.length > 3 ? <li>e altri {voce.perche.length - 3} motivi nel fascicolo</li> : null}
        </ul>
      ) : null}
      <div className="iu-fas-normativa__meta">
        <a href={voce.url} target="_blank" rel="noopener noreferrer">Apri su {voce.fonte} <ExternalLink size={12} aria-hidden="true"/></a>
        {voce.letturaInterna ? <a href={voce.letturaInterna} target="_blank" rel="noopener noreferrer"><FileText size={12} aria-hidden="true"/> Documento conservato</a> : null}
      </div>
      {/* Versione e data della consultazione, come le dichiara il registro. */}
      <small className="iu-fas-normativa__verifica">{voce.verifica ? `Versione: ${voce.verifica}` : 'Collegamento al testo vigente su Normattiva: estratto e data di consultazione non registrati.'}</small>
      {voce.testoInArchivio !== false && urn && articolo ? (
        <button type="button" className="iu-fas-normativa__espandi" aria-expanded={aperto} onClick={espandi}>
          {aperto ? <ChevronUp size={13} aria-hidden="true"/> : <ChevronDown size={13} aria-hidden="true"/>} {aperto ? 'Nascondi il testo' : 'Mostra il testo integrale'}
        </button>
      ) : null}
      {aperto ? (
        <div className="iu-fas-normativa__testo" role="region" aria-label={`Testo di ${voce.norma}`}>
          {stato === 'caricamento' ? <p className="iu-fas-normativa__nota">Lettura del testo dall’archivio…</p> : null}
          {stato === 'errore' ? <p className="iu-fas-normativa__nota" role="alert">Il testo non è disponibile nell’archivio di IUSENTRA: aprilo su {voce.fonte}.</p> : null}
          {testo ? <>
            <small>Testo dall’archivio Normattiva di IUSENTRA, versione {testo.versione}{testo.importatoIl && !testo.versione.includes(testo.importatoIl) ? ` (importato il ${testo.importatoIl})` : ''}. Prima di citarlo verifica le modifiche successive su {voce.fonte}.</small>
            <div className="iu-fas-normativa__corpo">{testo.testo}</div>
          </> : null}
        </div>
      ) : null}
    </li>
  )
}
