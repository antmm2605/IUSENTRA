import { useEffect, useId, useRef, useState } from 'react'
import { FolderOpen, Loader2, Search, X } from 'lucide-react'
import { Button } from '../../ui/Button'
import { LUNGHEZZA_MINIMA_RICERCA, searchMatters, type MatterMatch } from '../../services/fascicoloSearch'

export type MatterOption = { value: string; label: string }

type Props = {
  matters: MatterOption[]
  value: string
  disabled: boolean
  onChange: (matterId: string, label: string) => void
}

const ATTESA_DIGITAZIONE = 250

function etichettaBreve(match: MatterMatch): string {
  const parti = [match.numero, match.titolo].filter(Boolean)
  return parti.join(' — ') || match.label
}

/**
 * Scelta del fascicolo di destinazione cercando per nome e cognome del cliente.
 *
 * Con l'archivio di uno studio reale un elenco a tendina non è consultabile:
 * l'avvocato cerca la persona che assiste, non l'identificativo della pratica.
 * L'elenco a tendina resta come ripiego quando la ricerca non è ancora avviata.
 */
export function MatterPicker({ matters, value, disabled, onChange }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<MatterMatch[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedLabel, setSelectedLabel] = useState('')
  const fieldId = useId()
  const listId = useId()
  const richiestaAttiva = useRef<AbortController | null>(null)

  useEffect(() => {
    const testo = query.trim()
    if (testo.length < LUNGHEZZA_MINIMA_RICERCA) {
      richiestaAttiva.current?.abort()
      setResults([])
      setLoading(false)
      setError('')
      return
    }
    setLoading(true)
    const timer = window.setTimeout(() => {
      richiestaAttiva.current?.abort()
      const controller = new AbortController()
      richiestaAttiva.current = controller
      searchMatters(testo, controller.signal)
        .then((rows) => { if (!controller.signal.aborted) { setResults(rows); setError('') } })
        .catch((cause: unknown) => {
          if (controller.signal.aborted) return
          setResults([])
          setError(cause instanceof Error ? cause.message : 'Ricerca dei fascicoli non riuscita.')
        })
        .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    }, ATTESA_DIGITAZIONE)
    return () => window.clearTimeout(timer)
  }, [query])

  useEffect(() => () => richiestaAttiva.current?.abort(), [])

  function scegli(matterId: string, label: string) {
    setSelectedLabel(label)
    onChange(matterId, label)
  }

  if (value) {
    return (
      <div className="iu-matter-picker iu-matter-picker--chosen">
        <span className="iu-matter-picker__title">Fascicolo di destinazione</span>
        <p className="iu-matter-picker__chosen">
          <FolderOpen size={15} aria-hidden="true" />
          <span>{selectedLabel || matters.find((matter) => matter.value === value)?.label || value}</span>
        </p>
        <Button type="button" tone="neutral" disabled={disabled} onClick={() => { setSelectedLabel(''); onChange('', '') }}>
          <X size={15} aria-hidden="true" />Cambia fascicolo
        </Button>
      </div>
    )
  }

  const testo = query.trim()
  const cercaAvviata = testo.length >= LUNGHEZZA_MINIMA_RICERCA
  return (
    <div className="iu-matter-picker">
      <label className="iu-acq-field iu-acq-field--wide" htmlFor={fieldId}>
        <span>Fascicolo di destinazione</span>
        <span className="iu-matter-picker__search">
          <Search size={15} aria-hidden="true" />
          <input
            id={fieldId}
            type="search"
            value={query}
            disabled={disabled}
            autoComplete="off"
            placeholder="Cerca per nome e cognome del cliente"
            aria-controls={listId}
            aria-describedby={`${fieldId}-aiuto`}
            onChange={(event) => setQuery(event.target.value)}
          />
          {loading ? <Loader2 size={15} className="iu-matter-picker__spin" aria-hidden="true" /> : null}
        </span>
      </label>
      <p className="iu-acq-hint" id={`${fieldId}-aiuto`}>
        Scrivi il nome del cliente, anche invertito o parziale: la ricerca ignora accenti e punteggiatura e cerca anche nel numero e nell&apos;oggetto della pratica.
      </p>
      {error ? <p className="iu-matter-picker__error" role="alert">{error}</p> : null}
      <ul className="iu-matter-picker__list" id={listId} aria-live="polite">
        {cercaAvviata && !loading && !results.length && !error ? (
          <li className="iu-matter-picker__empty">Nessun fascicolo corrisponde a «{testo}».</li>
        ) : null}
        {(cercaAvviata ? results : []).map((match) => (
          <li key={match.value}>
            <button type="button" disabled={disabled} onClick={() => scegli(match.value, match.label)}>
              <strong>{match.cliente || etichettaBreve(match)}</strong>
              <span>{etichettaBreve(match)}</span>
              {match.stato ? <span className="iu-matter-picker__stato">Stato: {match.stato}</span> : null}
              {match.certo ? <em className="iu-matter-picker__sure">corrispondenza esatta</em> : null}
            </button>
          </li>
        ))}
      </ul>
      {!cercaAvviata && matters.length ? (
        <label className="iu-acq-field iu-acq-field--wide">
          <span>Oppure scegli fra i fascicoli recenti</span>
          <select
            value=""
            disabled={disabled}
            onChange={(event) => {
              const scelto = matters.find((matter) => matter.value === event.target.value)
              if (scelto) scegli(scelto.value, scelto.label)
            }}
          >
            <option value="">Seleziona il fascicolo</option>
            {matters.map((matter) => <option key={matter.value} value={matter.value}>{matter.label}</option>)}
          </select>
        </label>
      ) : null}
    </div>
  )
}
