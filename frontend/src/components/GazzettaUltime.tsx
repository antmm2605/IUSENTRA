import { useEffect, useState } from 'react'
import { AlertTriangle, ArrowRight, ExternalLink, Landmark } from 'lucide-react'
import { sanitizeDisplayText } from '../displayText'
import { formatDateIt } from '../formatting'
import { GAZZETTA_PAGINA, estremiGazzetta, loadGazzettaUltime, type GazzettaUltime } from '../gazzettaData'
import './GazzettaUltime.css'

function dataIt(valore: string): string {
  return formatDateIt(valore, 'data non indicata')
}

function collegamentoUfficiale(valore: string): string {
  try {
    const url = new URL((valore || '').trim())
    if (url.protocol !== 'https:' || url.username || url.password) return ''
    return ['www.gazzettaufficiale.it', 'gazzettaufficiale.it'].includes(url.hostname) ? url.href : ''
  } catch {
    return ''
  }
}

/** Panoramica, riquadro «Notizie utili»: le ultime 5 pubblicazioni di Serie generale e Corte costituzionale. */
export function GazzettaUltimePubblicazioni() {
  const [dati, setDati] = useState<GazzettaUltime | null>(null)
  const [errore, setErrore] = useState('')

  useEffect(() => {
    const controllo = new AbortController()
    loadGazzettaUltime(controllo.signal)
      .then(setDati)
      .catch((motivo: unknown) => { if (!controllo.signal.aborted) setErrore(motivo instanceof Error ? motivo.message : 'Gazzetta Ufficiale non disponibile.') })
    return () => controllo.abort()
  }, [])

  const inErrore = (dati?.sourceStates || []).some((stato) => ['SG', 'S1'].includes(stato.id) && stato.checked && !stato.ok)
  const haPubblicazioni = Boolean(dati?.items.length)

  return (
    <section className="iu-gazzetta-ultime" aria-labelledby="iu-gazzetta-ultime-titolo">
      <header>
        <h3 id="iu-gazzetta-ultime-titolo"><Landmark size={15} /> Gazzetta Ufficiale · ultime pubblicazioni</h3>
        <a href={GAZZETTA_PAGINA}>Tutte le Gazzette <ArrowRight size={14} /></a>
      </header>
      {errore ? <p className="iu-gazzetta-ultime__stato is-error" role="alert">{sanitizeDisplayText(errore)}</p> : null}
      {inErrore ? (
        <p className="iu-gazzetta-ultime__stato is-error" role="status">
          <AlertTriangle size={13} />
          {haPubblicazioni ? 'Aggiornamento in ritardo. Sono disponibili gli ultimi atti già acquisiti.' : (
            <>L’aggiornamento non è riuscito. <a href="https://www.gazzettaufficiale.it/" target="_blank" rel="noopener noreferrer">Consulta il sito ufficiale</a>.</>
          )}
        </p>
      ) : null}
      {dati?.archiveMissing ? <p className="iu-gazzetta-ultime__stato">{sanitizeDisplayText(dati.message)}</p> : null}
      {!dati && !errore ? <p className="iu-gazzetta-ultime__stato" role="status">Caricamento delle ultime pubblicazioni…</p> : null}
      {dati?.items.length ? (
        <ol>
          {dati.items.map((atto) => {
            const url = collegamentoUfficiale(atto.officialUrl)
            return (
              <li key={atto.id}>
                <span className="iu-gazzetta-ultime__tipo">{sanitizeDisplayText(atto.kindLabel)}</span>
                {url ? (
                  <a href={url} target="_blank" rel="noopener noreferrer" title="Apri l’atto sul sito della Gazzetta Ufficiale">
                    {sanitizeDisplayText(atto.title)} <ExternalLink size={12} />
                  </a>
                ) : <strong>{sanitizeDisplayText(atto.title)}</strong>}
                {atto.description ? <small className="iu-gazzetta-ultime__descrizione">{sanitizeDisplayText(atto.description)}</small> : null}
                <small>{estremiGazzetta(atto, dataIt)}{atto.authority ? ` · ${sanitizeDisplayText(atto.authority)}` : ''}</small>
              </li>
            )
          })}
        </ol>
      ) : null}
    </section>
  )
}
